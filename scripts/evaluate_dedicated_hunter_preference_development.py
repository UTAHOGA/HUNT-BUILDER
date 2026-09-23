"""Source-only adjacent-year evaluation for Dedicated Hunter preference draws.

This development audit keeps adult and youth pools separate, builds forecasts
only from canonical truth available through the source year, and scores against
the next canonical year.  It does not update the certification registry or any
published prediction artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.dedicated_hunter import (
    DEDICATED_HUNTER_POOL,
    YOUTH_DEDICATED_HUNTER_POOL,
    _build_truth_ladders,
    build_preference_dedicated_hunter_predictions,
)
from engine.utah_draw_predictive.run_all_families import (
    _finalize_prediction_output_row,
    _with_historical_target_metadata,
    _with_run_fields,
    _write_csv,
)
from engine.utah_predictive_mixed.materialize import mixed_row
from engine.utah_predictive_mixed.models import BlendWeights


CANONICAL_ROOT = REPO / "data_truth/draw_results_truth/normalized/canonical_yearly"
DRAW_SYSTEM_TYPE = "PREFERENCE_DEDICATED_HUNTER_DEER"


def read(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def canonical_path(year: int) -> Path:
    return CANONICAL_ROOT / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def normalized_pool(value: object) -> str:
    text = str(value or "").strip().lower()
    return YOUTH_DEDICATED_HUNTER_POOL if "youth" in text else DEDICATED_HUNTER_POOL


def row_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        normalized_pool(row.get("draw_pool")),
        str(row.get("hunt_code") or "").strip().upper(),
        str(row.get("residency") or "").strip() or "All",
        str(row.get("points") or "").strip(),
    )


def prior_row(
    row: dict[str, object],
    source_ladders: dict[tuple[str, int, str, str], dict[int, dict[str, int]]],
    source_year: int,
    mode: str,
) -> dict[str, str] | None:
    if mode == "family_only":
        return None
    try:
        points = int(float(str(row.get("points") or "")))
    except ValueError:
        return None
    if mode == "cohort_prior":
        if points <= 0:
            return None
        points -= 1
    pool = normalized_pool(row.get("draw_pool"))
    hunt_code = str(row.get("hunt_code") or "").strip().upper()
    residency = str(row.get("residency") or "").strip() or "All"
    values = source_ladders.get((pool, source_year, hunt_code, residency), {}).get(points)
    if values is None:
        return None
    eligible = int(values.get("eligible", 0))
    drawn = int(values.get("drawn", 0))
    return {
        "hunt_code": hunt_code,
        "residency": "" if residency == "All" else residency,
        "points": str(points),
        "eligible_applicants": str(eligible),
        "regular_permits": str(drawn),
        "total_permits": str(drawn),
        "success_ratio": "" if eligible <= 0 else f"{drawn / eligible:.10f}",
    }


def stats(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {
            "n": 0,
            "mae": None,
            "p90": None,
            "tail_over_25pp": None,
            "false_guarantees": 0,
        }
    errors = sorted(float(row["absolute_error"]) for row in rows)
    p90_index = max(0, min(len(errors) - 1, int(0.9 * len(errors) + 0.999999) - 1))
    return {
        "n": len(rows),
        "mae": sum(errors) / len(errors),
        "p90": errors[p90_index],
        "tail_over_25pp": sum(error > 0.25 for error in errors) / len(errors),
        "false_guarantees": sum(
            float(row["predicted_probability"]) >= 0.999999
            and float(row["actual_probability"]) < 0.999999
            for row in rows
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--final-mode",
        choices=("production_same_point", "cohort_prior", "family_only"),
        default="production_same_point",
    )
    args = parser.parse_args()
    if args.out_dir.exists():
        raise SystemExit("Use a separately named development artifact; refusing overwrite")
    args.out_dir.mkdir(parents=True)

    history: list[dict[str, str]] = []
    all_scores: list[dict[str, object]] = []
    all_gaps: list[dict[str, object]] = []
    fold_reports: dict[str, object] = {}
    input_hashes: dict[str, str] = {}

    for source_year in range(2017, 2026):
        source_path = canonical_path(source_year)
        target_path = canonical_path(source_year + 1)
        source = read(source_path)
        target = read(target_path)
        history.extend(source)
        input_hashes[str(source_year)] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        input_hashes[str(source_year + 1)] = hashlib.sha256(target_path.read_bytes()).hexdigest()

        engine_history = _with_historical_target_metadata(history, source_year, source_year + 1)
        engine_source = _with_historical_target_metadata(source, source_year, source_year + 1)
        source_ladders, _, _ = _build_truth_ladders(engine_source, {source_year})
        target_ladders, _, _ = _build_truth_ladders(target, {source_year + 1})
        forecasts = build_preference_dedicated_hunter_predictions(
            engine_history,
            engine_source,
            source_year + 1,
            list(range(2017, source_year + 1)),
        )

        finalized: list[dict[str, object]] = []
        for forecast in _with_run_fields(
            forecasts,
            source_year,
            source_year + 2,
            "dedicated_hunter",
        ):
            item = _finalize_prediction_output_row(forecast)
            finalized.append(
                mixed_row(
                    item,
                    prior_row(item, source_ladders, source_year, args.final_mode),
                    None,
                    BlendWeights(),
                    forecast_year=source_year + 1,
                )
            )
        _write_csv(args.out_dir / f"{source_year}_forecast.csv", finalized)

        lookup: dict[tuple[str, str, str, str], dict[str, object]] = {}
        duplicate_keys: list[tuple[str, str, str, str]] = []
        for row in finalized:
            key = row_key(row)
            if key in lookup:
                duplicate_keys.append(key)
            lookup[key] = row

        fold_scores: list[dict[str, object]] = []
        fold_gaps: list[dict[str, object]] = []
        for (pool, _year, hunt_code, residency), ladder in sorted(target_ladders.items()):
            for points, values in sorted(ladder.items()):
                eligible = int(values.get("eligible", 0))
                if eligible <= 0:
                    continue
                drawn = int(values.get("drawn", 0))
                key = (pool, hunt_code, residency, str(points))
                forecast = lookup.get(key)
                probability_text = str((forecast or {}).get("p_draw_mean") or "").strip()
                source_lane = source_ladders.get((pool, source_year, hunt_code, residency))
                if not probability_text:
                    if source_lane is None:
                        classification = "NO_SOURCE_COMPARABLE_LANE"
                    elif points not in source_lane and points - 1 not in source_lane:
                        classification = "NEW_POINT_LEVEL_WITHOUT_SOURCE_COHORT"
                    elif forecast and forecast.get("algorithm_status") == "NO_TRANSITION_EVIDENCE":
                        classification = "NO_TRANSITION_EVIDENCE"
                    elif forecast:
                        classification = "BLANK_FORECAST_PROBABILITY"
                    else:
                        classification = "UNRESOLVED_MISSING_FORECAST"
                    fold_gaps.append(
                        {
                            "source_year": source_year,
                            "target_year": source_year + 1,
                            "draw_pool": pool,
                            "hunt_code": hunt_code,
                            "residency": residency,
                            "points": points,
                            "eligible_applicants": eligible,
                            "coverage_classification": classification,
                            "source_classified": str(classification != "UNRESOLVED_MISSING_FORECAST").upper(),
                        }
                    )
                    continue
                predicted = float(probability_text)
                actual = drawn / eligible
                error = predicted - actual
                fold_scores.append(
                    {
                        "source_year": source_year,
                        "target_year": source_year + 1,
                        "draw_system_type": DRAW_SYSTEM_TYPE,
                        "draw_pool": pool,
                        "hunt_code": hunt_code,
                        "residency": residency,
                        "points": points,
                        "eligible_applicants": eligible,
                        "drawn_permits": drawn,
                        "predicted_probability": f"{predicted:.10f}",
                        "actual_probability": f"{actual:.10f}",
                        "error": f"{error:.10f}",
                        "absolute_error": f"{abs(error):.10f}",
                    }
                )

        fold_reports[str(source_year)] = {
            "all": stats(fold_scores),
            "adult": stats([row for row in fold_scores if row["draw_pool"] == DEDICATED_HUNTER_POOL]),
            "youth": stats([row for row in fold_scores if row["draw_pool"] == YOUTH_DEDICATED_HUNTER_POOL]),
            "forecast_rows": len(finalized),
            "duplicate_forecast_keys": [list(key) for key in duplicate_keys],
            "coverage_gaps": dict(Counter(row["coverage_classification"] for row in fold_gaps)),
        }
        all_scores.extend(fold_scores)
        all_gaps.extend(fold_gaps)
        print(source_year, json.dumps(fold_reports[str(source_year)]), flush=True)

    adult_scores = [row for row in all_scores if row["draw_pool"] == DEDICATED_HUNTER_POOL]
    youth_scores = [row for row in all_scores if row["draw_pool"] == YOUTH_DEDICATED_HUNTER_POOL]
    recurring = Counter(
        (row["draw_pool"], row["hunt_code"], row["residency"])
        for row in all_scores
        if float(row["absolute_error"]) > 0.25
    )
    report = {
        "purpose": "DEVELOPMENT_ONLY_NOT_CERTIFICATION",
        "final_probability_mode": args.final_mode,
        "source_years": [2017, 2025],
        "input_hashes": dict(sorted(input_hashes.items(), key=lambda item: int(item[0]))),
        "all": stats(all_scores),
        "adult": stats(adult_scores),
        "youth": stats(youth_scores),
        "coverage_gaps": dict(Counter(row["coverage_classification"] for row in all_gaps)),
        "unresolved_coverage_gaps": sum(
            row["coverage_classification"] == "UNRESOLVED_MISSING_FORECAST" for row in all_gaps
        ),
        "recurring_over_25pp_hunt_lane": [
            {"draw_pool": key[0], "hunt_code": key[1], "residency": key[2], "count": count}
            for key, count in recurring.most_common()
            if count >= 2
        ],
        "folds": fold_reports,
        "implementation_sha256": {
            path: hashlib.sha256((REPO / path).read_bytes()).hexdigest()
            for path in (
                "engine/utah_draw_predictive/dedicated_hunter.py",
                "engine/utah_predictive_mixed/materialize.py",
                "scripts/evaluate_dedicated_hunter_preference_development.py",
            )
        },
    }
    _write_csv(args.out_dir / "paired_scores.csv", all_scores)
    _write_csv(args.out_dir / "coverage_gaps.csv", all_gaps)
    (args.out_dir / "development_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
