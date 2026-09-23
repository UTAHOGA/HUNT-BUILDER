"""Evaluate the existing preference shadow-calibration layer on rolling folds.

Each held-out fold is calibrated only from earlier physical adjacent-year
folds.  The underlying Utah preference mechanics and applicant forecast remain
unchanged.  This is development evidence, not a promotion artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah_draw_predictive.preference_calibration import (  # noqa: E402
    apply_preference_calibration_candidate,
    probability_bin,
)


FAMILIES = {
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
}


def _as_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def metrics(rows: list[dict[str, Any]], probability_field: str) -> dict[str, Any]:
    errors = [
        abs(_as_float(row[probability_field]) - _as_float(row["actual_probability"]))
        for row in rows
    ]
    ordered = sorted(errors)
    p90 = ordered[min(int(0.90 * (len(ordered) - 1)), len(ordered) - 1)] if ordered else None
    return {
        "rows": len(rows),
        "mae": sum(errors) / len(errors) if errors else None,
        "p90": p90,
        "tail_rows_over_25pp": sum(error > 0.25 for error in errors),
        "tail_rate_over_25pp": sum(error > 0.25 for error in errors) / len(errors) if errors else None,
        "false_guarantees": sum(
            _as_float(row[probability_field]) >= 0.999999
            and _as_float(row["actual_probability"]) < 0.999999
            for row in rows
        ),
    }


def build_table(
    training: list[dict[str, str]],
    *,
    minimum_specific_rows: int,
    minimum_fallback_rows: int,
    prior_strength: float,
) -> pd.DataFrame:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    fallback: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in training:
        family = row["draw_design"]
        bucket = probability_bin(row["predicted_probability"])
        grouped[(family, row["residency"], bucket)].append(row)
        fallback[(family, bucket)].append(row)

    table_rows: list[dict[str, Any]] = []
    for (family, residency, bucket), rows in sorted(grouped.items()):
        if len(rows) < minimum_specific_rows:
            continue
        correction = median(
            [
            _as_float(row["actual_probability"]) - _as_float(row["predicted_probability"])
            for row in rows
            ]
        )
        table_rows.append(
            {
                "draw_system_type": family,
                "residency": residency,
                "probability_bin": bucket,
                "correction_probability_delta": correction,
                "shrinkage_weight": len(rows) / (len(rows) + prior_strength),
                "recommended_calibration_method": "rolling_prior_fold_family_residency_probability_bucket_median_residual",
                "overfit_risk": "medium",
                "calibration_value_type": "probability_delta",
                "training_rows": len(rows),
            }
        )
    for (family, bucket), rows in sorted(fallback.items()):
        if len(rows) < minimum_fallback_rows:
            continue
        correction = median(
            [
            _as_float(row["actual_probability"]) - _as_float(row["predicted_probability"])
            for row in rows
            ]
        )
        table_rows.append(
            {
                "draw_system_type": family,
                "residency": "ALL",
                "probability_bin": bucket,
                "correction_probability_delta": correction,
                "shrinkage_weight": len(rows) / (len(rows) + prior_strength),
                "recommended_calibration_method": "rolling_prior_fold_family_probability_bucket_fallback_median_residual",
                "overfit_risk": "medium",
                "calibration_value_type": "probability_delta",
                "training_rows": len(rows),
            }
        )
    return pd.DataFrame(table_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--minimum-specific-rows", type=int, default=25)
    parser.add_argument("--minimum-fallback-rows", type=int, default=50)
    parser.add_argument("--prior-strength", type=float, default=25.0)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {args.out_dir}")
    args.out_dir.mkdir(parents=True)

    with args.scores.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = [
            row for row in csv.DictReader(handle) if row.get("draw_design") in FAMILIES
        ]
    folds = sorted({row["fold"] for row in source_rows})
    training: list[dict[str, str]] = []
    candidate_rows: list[dict[str, Any]] = []
    fold_reports: dict[str, Any] = {}
    table_history: list[dict[str, Any]] = []

    for fold in folds:
        held_out = [row for row in source_rows if row["fold"] == fold]
        table = build_table(
            training,
            minimum_specific_rows=args.minimum_specific_rows,
            minimum_fallback_rows=args.minimum_fallback_rows,
            prior_strength=args.prior_strength,
        )
        frame = pd.DataFrame(
            [
                {
                    **row,
                    "draw_system_type": row["draw_design"],
                    "p_draw": _as_float(row["predicted_probability"]),
                }
                for row in held_out
            ]
        )
        calibrated = apply_preference_calibration_candidate(frame, table)
        fold_output: list[dict[str, Any]] = []
        for row in calibrated.to_dict(orient="records"):
            candidate = dict(row)
            candidate["candidate_probability"] = float(row["p_draw_calibrated_candidate"])
            fold_output.append(candidate)
            candidate_rows.append(candidate)
        fold_reports[fold] = {
            "training_rows": len(training),
            "calibration_table_rows": len(table),
            "applied_rows": sum(bool(row["calibration_applied_candidate"]) for row in fold_output),
            "baseline": metrics(fold_output, "predicted_probability"),
            "candidate": metrics(fold_output, "candidate_probability"),
        }
        if not table.empty:
            for row in table.to_dict(orient="records"):
                table_history.append({"held_out_fold": fold, **row})
        training.extend(held_out)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        grouped[(str(row["draw_design"]), str(row["residency"]))].append(row)
    report = {
        "status": "DEVELOPMENT_ONLY_NOT_CERTIFICATION",
        "candidate": "ROLLING_PRIOR_FOLD_EXISTING_PREFERENCE_SHADOW_CALIBRATION",
        "target_values_used_for_same_fold_calibration": False,
        "minimum_specific_rows": args.minimum_specific_rows,
        "minimum_fallback_rows": args.minimum_fallback_rows,
        "prior_strength": args.prior_strength,
        "baseline": metrics(candidate_rows, "predicted_probability"),
        "candidate_metrics": metrics(candidate_rows, "candidate_probability"),
        "by_family_residency": {
            "|".join(key): {
                "baseline": metrics(rows, "predicted_probability"),
                "candidate": metrics(rows, "candidate_probability"),
            }
            for key, rows in sorted(grouped.items())
        },
        "folds": fold_reports,
    }
    pd.DataFrame(candidate_rows).to_csv(args.out_dir / "rolling_candidate_scores.csv", index=False)
    pd.DataFrame(table_history).to_csv(args.out_dir / "rolling_calibration_tables.csv", index=False)
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
