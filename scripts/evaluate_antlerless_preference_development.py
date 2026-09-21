"""Evaluate source-only antlerless preference repairs on predeclared folds.

This is a development comparison, not certification. It rebuilds forecasts
from source-year canonical truth, applies the exact final mixed probability
calculation, and compares only with the already-retained official score rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.preference_antlerless import build_preference_antlerless_predictions
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


def score_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row.get("draw_design_key") or row.get("draw_system_type") or "").strip(),
        str(row.get("hunt_code") or "").strip().upper(),
        str(row.get("residency") or "").strip(),
        str(row.get("points") or "").strip(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--source-year-start", type=int, default=2017)
    parser.add_argument("--source-year-end", type=int, default=2022)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise SystemExit("Use a separately named development artifact; refusing overwrite")
    args.out_dir.mkdir(parents=True)

    history: list[dict[str, str]] = []
    all_scores: list[dict[str, object]] = []
    reports: dict[str, object] = {}
    input_hashes: dict[str, str] = {}

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
                finalized.append(
                    mixed_row(
                        _finalize_prediction_output_row(row),
                        None,
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
                missing.append(score_key(actual))
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
            family: stats([row for row in fold_scores if row["draw_design_key"] == family])
            for family in FAMILIES
            if any(row["draw_design_key"] == family for row in fold_scores)
        }
        reports[str(source_year)] = {
            "all": stats(fold_scores),
            "by_family": by_family,
            "forecast_rows": len(finalized),
            "missing_score_keys": missing,
            "duplicate_score_keys": duplicate_keys,
        }
        all_scores.extend(fold_scores)
        print(source_year, json.dumps(reports[str(source_year)]), flush=True)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in all_scores:
        grouped[str(row["draw_design_key"])].append(row)
    report = {
        "purpose": "DEVELOPMENT_ONLY_NOT_CERTIFICATION",
        "source_years": [args.source_year_start, args.source_year_end],
        "input_hashes": input_hashes,
        "overall": stats(all_scores),
        "by_family": {family: stats(rows) for family, rows in grouped.items()},
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
    (args.out_dir / "development_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
