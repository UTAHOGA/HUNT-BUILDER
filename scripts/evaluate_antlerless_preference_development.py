"""Evaluate source-only antlerless preference repairs on predeclared folds.

This is a development comparison, not certification. It rebuilds forecasts
from source-year canonical truth, applies the exact final mixed probability
calculation, and compares only with the already-retained official score rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.preference_antlerless import (
    _build_truth_ladders,
    build_preference_antlerless_predictions,
)
from engine.utah_draw_predictive.run_all_families import (
    _finalize_prediction_output_row,
    _with_historical_target_metadata,
    _with_run_fields,
    _write_csv,
)
from engine.utah_predictive_mixed.materialize import mixed_row
from engine.utah_predictive_mixed.models import BlendWeights
from scripts.audit_core_le_deer_repair import BASE, read, stats


FAMILIES = (
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
)

PRE_DRAW_FAMILY_BY_DESIGN = {
    "PREFERENCE_ANTLERLESS_DEER": "antlerless_deer",
    "PREFERENCE_ANTLERLESS_ELK": "antlerless_elk",
    "PREFERENCE_DOE_PRONGHORN": "doe_pronghorn",
}


def read_pre_draw_quota_context(path: Path) -> dict[tuple[int, str, str], dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed: dict[tuple[int, str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("source_timing") != "FINAL_PUBLISHED_PRE_DRAW_QUOTA":
            raise ValueError(
                "Quota context is not final published pre-draw authority; "
                "RAC recommendations are cross-check-only"
            )
        if str(row.get("eligible_for_probability_quota") or "").lower() != "true":
            raise ValueError("Quota context row is not eligible for forecast probability")
        code = str(row.get("hunt_code") or "").strip().upper()
        if not code:
            continue
        key = (int(row["permit_year"]), str(row["family"]), code)
        if key in indexed:
            raise ValueError(f"Duplicate pre-draw quota context: {key}")
        indexed[key] = row
    return indexed


def apply_pre_draw_quota_context(
    rows: list[dict[str, object]],
    *,
    target_year: int,
    context: dict[tuple[int, str, str], dict[str, str]],
) -> tuple[list[dict[str, object]], int]:
    enriched: list[dict[str, object]] = []
    matched_codes: set[tuple[str, str]] = set()
    for source_row in rows:
        row = dict(source_row)
        design = str(row.get("draw_system_type") or "").strip()
        family = PRE_DRAW_FAMILY_BY_DESIGN.get(design)
        code = str(row.get("hunt_code") or "").strip().upper()
        authority = context.get((target_year, family, code)) if family and code else None
        if authority is not None:
            row["target_permits_total"] = authority["total_permits"]
            if authority.get("resident_permits") and authority.get("nonresident_permits"):
                row["target_permits_res"] = authority["resident_permits"]
                row["target_permits_nr"] = authority["nonresident_permits"]
            else:
                row["target_permits_res"] = ""
                row["target_permits_nr"] = ""
            row["target_permits_source"] = "OFFICIAL_FINAL_PUBLISHED_PRE_DRAW_QUOTA"
            row["target_permits_source_file"] = authority["source_path"]
            row["target_permits_source_page"] = authority["source_page"]
            row["target_permits_source_sha256"] = authority["source_sha256"]
            row["quota_source"] = "OFFICIAL_FINAL_PUBLISHED_PRE_DRAW_QUOTA"
            row["quota_source_status"] = "FINAL_PRE_DRAW_TARGET_YEAR_NOT_DRAW_RESULT"
            matched_codes.add((family, code))
        enriched.append(row)
    return enriched, len(matched_codes)


def safe_stats(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {"n": 0, "mae": None, "p90": None, "tail": None, "bias": None}
    return stats(rows)


def score_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row.get("draw_design_key") or row.get("draw_system_type") or "").strip(),
        str(row.get("hunt_code") or "").strip().upper(),
        str(row.get("residency") or "").strip(),
        str(row.get("points") or "").strip(),
    )


def source_prior_row(
    row: dict[str, object],
    source_ladders: dict[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
    source_year: int,
) -> dict[str, str] | None:
    family = str(row.get("draw_system_type") or "").strip()
    hunt_code = str(row.get("hunt_code") or "").strip().upper()
    draw_pool = str(row.get("draw_pool") or "").strip()
    residency = str(row.get("residency") or "").strip() or "All"
    try:
        points = int(float(str(row.get("points") or "")))
    except ValueError:
        return None
    # Preference applicants who did not draw advance one point. The comparable
    # prior-year cohort for a forecast at P is therefore the official source
    # row at P-1, not the same point. Zero-point entrants have no prior point
    # rung and remain owned by the source-only family transition forecast.
    if str(row.get("algorithm_status") or "") == "MODELED_PREFERENCE":
        if points <= 0:
            return None
        prior_points = points - 1
    else:
        prior_points = points
    ladder = source_ladders.get((family, source_year, hunt_code, draw_pool, residency))
    if ladder is None:
        candidates = [
            values
            for (candidate_family, year, code, _pool, lane), values in source_ladders.items()
            if candidate_family == family
            and year == source_year
            and code == hunt_code
            and lane == residency
        ]
        if len(candidates) != 1:
            return None
        ladder = candidates[0]
    values = ladder.get(prior_points)
    if values is None:
        return None
    eligible = int(values.get("eligible", 0))
    drawn = int(values.get("drawn", 0))
    return {
        "hunt_code": hunt_code,
        "residency": "" if residency == "All" else residency,
        "points": str(prior_points),
        "eligible_applicants": str(eligible),
        "regular_permits": str(drawn),
        "total_permits": str(drawn),
        "success_ratio": "" if eligible <= 0 else f"{drawn / eligible:.10f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--source-year-start", type=int, default=2017)
    parser.add_argument("--source-year-end", type=int, default=2022)
    parser.add_argument("--pre-draw-quota-context", type=Path)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise SystemExit("Use a separately named development artifact; refusing overwrite")
    args.out_dir.mkdir(parents=True)

    history: list[dict[str, str]] = []
    all_scores: list[dict[str, object]] = []
    all_gap_rows: list[dict[str, object]] = []
    reports: dict[str, object] = {}
    input_hashes: dict[str, str] = {}
    quota_context = (
        read_pre_draw_quota_context(args.pre_draw_quota_context)
        if args.pre_draw_quota_context
        else {}
    )
    if args.pre_draw_quota_context:
        input_hashes["pre_draw_quota_context"] = hashlib.sha256(
            args.pre_draw_quota_context.read_bytes()
        ).hexdigest()

    for source_year in range(2017, args.source_year_end + 1):
        path = REPO / (
            "data_truth/draw_results_truth/normalized/canonical_yearly/"
            f"draw_results_{source_year}_for_{source_year + 1}_canonical_yearly_draw_results.csv"
        )
        source = read(path)
        history.extend(source)
        input_hashes[str(source_year)] = hashlib.sha256(path.read_bytes()).hexdigest()
        if source_year < args.source_year_start:
            continue

        engine_history = _with_historical_target_metadata(history, source_year, source_year + 1)
        engine_source = _with_historical_target_metadata(source, source_year, source_year + 1)
        pre_draw_quota_codes = 0
        if quota_context:
            engine_source, pre_draw_quota_codes = apply_pre_draw_quota_context(
                engine_source,
                target_year=source_year + 1,
                context=quota_context,
            )
        source_ladders, _, _ = _build_truth_ladders(engine_source, {source_year})
        forecasts = build_preference_antlerless_predictions(
            engine_history,
            engine_source,
            source_year + 1,
            list(range(2017, source_year + 1)),
        )
        finalized: list[dict[str, object]] = []
        for family in FAMILIES:
            family_name = {
                "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
                "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
                "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
            }[family]
            family_rows = [row for row in forecasts if row.get("draw_system_type") == family]
            for row in _with_run_fields(family_rows, source_year, source_year + 2, family_name):
                finalized_row = _finalize_prediction_output_row(row)
                finalized.append(
                    mixed_row(
                        finalized_row,
                        source_prior_row(finalized_row, source_ladders, source_year),
                        None,
                        BlendWeights(),
                        forecast_year=source_year + 1,
                    )
                )
        _write_csv(args.out_dir / f"{source_year}_forecast.csv", finalized)

        lookup: dict[tuple[str, str, str, str], dict[str, object]] = {}
        duplicate_keys: list[tuple[str, str, str, str]] = []
        for row in finalized:
            key = score_key(row)
            if key in lookup:
                duplicate_keys.append(key)
            lookup[key] = row

        fold_scores: list[dict[str, object]] = []
        missing: list[tuple[str, str, str, str]] = []
        gap_rows: list[dict[str, object]] = []
        baseline_rows = read(
            BASE
            / f"historical_folds/{source_year}_to_{source_year + 1}/comparison_phase/"
            "draw_line_aware_prediction_vs_actual_rowlevel.csv"
        )
        for actual in baseline_rows:
            if actual.get("draw_design_key") not in FAMILIES or actual.get("scoring_decision") != "score_probability":
                continue
            match = lookup.get(score_key(actual), {})
            probability = str(match.get("p_draw_mean") or "").strip()
            if not probability:
                missing_key = score_key(actual)
                missing.append(missing_key)
                family, hunt_code, residency, points = missing_key
                comparable = [
                    ladder
                    for (draw_system_type, year, code, _pool, lane), ladder in source_ladders.items()
                    if draw_system_type == family
                    and year == source_year
                    and code == hunt_code
                    and lane == residency
                ]
                source_awards = sum(
                    int(values.get("drawn", 0))
                    for ladder in comparable
                    for values in ladder.values()
                )
                if match.get("algorithm_status") == "NO_TRANSITION_EVIDENCE":
                    classification = "NO_PROGRAM_RESIDENCY_TRANSITION_EVIDENCE"
                elif not comparable:
                    classification = "NO_SOURCE_COMPARABLE_LANE"
                elif source_awards <= 0:
                    classification = "SOURCE_LANE_ZERO_AWARDS_PROXY"
                else:
                    classification = "UNRESOLVED_ENGINE_GAP"
                gap_rows.append(
                    {
                        "source_year": source_year,
                        "target_year": source_year + 1,
                        "draw_system_type": family,
                        "hunt_code": hunt_code,
                        "residency": residency,
                        "points": points,
                        "source_lane_present": str(bool(comparable)).upper(),
                        "source_lane_awards": source_awards,
                        "coverage_classification": classification,
                        "source_classified": str(classification != "UNRESOLVED_ENGINE_GAP").upper(),
                        "candidate_algorithm_status": match.get("algorithm_status", ""),
                        "candidate_reason_codes": match.get("reason_codes", ""),
                    }
                )
                continue
            predicted_value = float(probability)
            actual_value = float(actual["actual_probability"])
            error = predicted_value - actual_value
            fold_scores.append(
                {
                    **actual,
                    "baseline_probability": actual["predicted_probability"],
                    "predicted_probability": probability,
                    # The retained comparison row belongs to the frozen
                    # baseline. Recompute candidate errors after substituting
                    # the candidate's exact final website probability.
                    "error": f"{error:.10f}",
                    "absolute_error": f"{abs(error):.10f}",
                    "candidate_algorithm_status": match.get("algorithm_status", ""),
                    "candidate_draw_pool": match.get("draw_pool", ""),
                    "candidate_quota": match.get("public_permits_2026", ""),
                    "candidate_quota_source": match.get("reason_codes", ""),
                }
            )
        by_family = {
            family: safe_stats([row for row in fold_scores if row["draw_design_key"] == family])
            for family in FAMILIES
            if any(row["draw_design_key"] == family for row in fold_scores)
        }
        reports[str(source_year)] = {
            "all": safe_stats(fold_scores),
            "by_family": by_family,
            "forecast_rows": len(finalized),
            "pre_draw_quota_codes": pre_draw_quota_codes,
            "missing_score_keys": missing,
            "missing_score_key_classifications": dict(
                sorted(Counter(row["coverage_classification"] for row in gap_rows).items())
            ),
            "unresolved_missing_score_keys": sum(
                row["coverage_classification"] == "UNRESOLVED_ENGINE_GAP" for row in gap_rows
            ),
            "duplicate_score_keys": duplicate_keys,
        }
        all_scores.extend(fold_scores)
        all_gap_rows.extend(gap_rows)
        print(source_year, json.dumps(reports[str(source_year)]), flush=True)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in all_scores:
        grouped[str(row["draw_design_key"])].append(row)
    report = {
        "purpose": "DEVELOPMENT_ONLY_NOT_CERTIFICATION",
        "source_years": [args.source_year_start, args.source_year_end],
        "input_hashes": input_hashes,
        "overall": safe_stats(all_scores),
        "by_family": {family: safe_stats(rows) for family, rows in grouped.items()},
        "folds": reports,
        "implementation_sha256": {
            str(path): hashlib.sha256((REPO / path).read_bytes()).hexdigest()
            for path in (
                Path("engine/utah_draw_predictive/preference_antlerless.py"),
                Path("engine/utah_draw_predictive/run_all_families.py"),
                Path("engine/utah_predictive_mixed/materialize.py"),
            )
        },
    }
    _write_csv(args.out_dir / "paired_development_scores.csv", all_scores)
    _write_csv(args.out_dir / "coverage_gap_classifications.csv", all_gap_rows)
    (args.out_dir / "development_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
