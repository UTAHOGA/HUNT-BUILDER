"""Audit adult antlerless errors with the exact historical scorer identities.

This is a diagnostic only.  It reads the already-frozen forecast projections
and canonical-derived historical truth, and never changes a forecast or truth
value.  Target-year observations are used only to label the held-out error.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import (  # noqa: E402
    build_ladders,
    read_csv,
)


LONG_TRUTH = ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
ADULT_ANTLERLESS_DESIGNS = {
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    fieldnames = fieldnames or ["no_rows"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _quota_direction(source_quota: float, target_quota: float) -> str:
    if source_quota <= 0 and target_quota > 0:
        return "TARGET_QUOTA_INTRODUCED"
    if target_quota > source_quota:
        return "TARGET_QUOTA_INCREASED"
    if target_quota < source_quota:
        return "TARGET_QUOTA_DECREASED"
    return "QUOTA_UNCHANGED"


def _count_direction(forecast_count: int, target_count: float) -> str:
    if forecast_count <= 0 and target_count > 0:
        return "FORECAST_ZERO_TARGET_POSITIVE"
    if forecast_count > target_count:
        return "FORECAST_STACK_OVER_TARGET"
    if forecast_count < target_count:
        return "FORECAST_STACK_UNDER_TARGET"
    return "FORECAST_STACK_MATCHED_TARGET"


def _fold_dirs(base: Path) -> Iterable[Path]:
    for path in sorted(base.iterdir()):
        if path.is_dir() and "_to_" in path.name and path.name.split("_to_")[0].isdigit():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--review-name", default="review_source_replayed")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--truth", type=Path, default=LONG_TRUTH)
    args = parser.parse_args()

    args.base = args.base.resolve()
    args.out_dir = args.out_dir.resolve()
    args.truth = args.truth.resolve()

    if args.out_dir.exists():
        raise FileExistsError(f"Output directory already exists: {args.out_dir}")
    args.out_dir.mkdir(parents=True)

    score_path = args.base / args.review_name / "all_scored_rows.csv"
    score_header, score_rows = read_csv(score_path)
    if not score_header:
        raise ValueError(f"No score rows found: {score_path}")

    _truth_header, truth_rows = read_csv(args.truth)
    truth_by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        year = _as_int(row.get("actual_draw_year"))
        if year:
            truth_by_year[year].append(row)

    scores_by_fold: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in score_rows:
        if row.get("draw_design") in ADULT_ANTLERLESS_DESIGNS:
            scores_by_fold[row.get("fold", "")].append(row)

    audit_rows: list[dict[str, Any]] = []
    for fold_dir in _fold_dirs(args.base):
        fold = fold_dir.name
        fold_scores = scores_by_fold.get(fold, [])
        if not fold_scores:
            continue
        source_year, target_year = (_as_int(part) for part in fold.split("_to_", 1))

        forecast_candidates = list((fold_dir / "scoring_projection").glob("*_frozen_forecast_legacy_pool_scoring_projection.csv"))
        target_candidates = list((fold_dir / "scoring_projection").glob("*_frozen_actual_residency_scoring_projection.csv"))
        if len(forecast_candidates) != 1 or len(target_candidates) != 1:
            raise ValueError(f"Expected one forecast and target projection for {fold}")
        forecast_path = forecast_candidates[0]
        target_path = target_candidates[0]
        _forecast_header, forecast_rows = read_csv(forecast_path)
        _target_header, target_rows = read_csv(target_path)
        forecast_by_row_number = {index: row for index, row in enumerate(forecast_rows, start=2)}
        source_ladders, _source_draw_years, _source_model_targets = build_ladders(truth_by_year[source_year])
        target_ladders, _target_draw_years, _target_model_targets = build_ladders(target_rows)

        for score in fold_scores:
            row_number = _as_int(score.get("prediction_row_number"))
            forecast = forecast_by_row_number.get(row_number)
            if forecast is None:
                raise ValueError(f"Missing forecast row {row_number} in {fold}")

            points = _as_int(score.get("points"))
            key = (
                score.get("draw_design", ""),
                score.get("draw_pool_key", ""),
                score.get("hunt_code", ""),
                score.get("residency", ""),
            )
            source_ladder = source_ladders.get(key)
            target_ladder = target_ladders.get(key)
            target_point = target_ladder.points.get(points) if target_ladder else None
            source_point = source_ladder.points.get(points - 1) if source_ladder and points > 0 else None
            source_baseline_point = (
                source_point
                if points > 0
                else (source_ladder.points.get(0) if source_ladder else None)
            )

            source_quota = sum(point.actual_drawn for point in source_ladder.points.values()) if source_ladder else 0.0
            target_quota = sum(point.actual_drawn for point in target_ladder.points.values()) if target_ladder else 0.0
            source_eligible = source_point.actual_eligible_applicants if source_point else 0.0
            source_drawn = source_point.actual_drawn if source_point else 0.0
            source_unsuccessful = source_point.actual_unsuccessful if source_point else 0.0
            target_eligible = target_point.actual_eligible_applicants if target_point else _as_float(score.get("actual_eligible_applicants"))
            forecast_count = _as_int(
                forecast.get("forecast_applicants_at_level") or forecast.get("applicants_at_level")
            )
            forecast_above = _as_int(
                forecast.get("forecast_applicants_above") or forecast.get("applicants_above")
            )
            source_unsuccessful_above_predecessor = (
                sum(
                    point.actual_unsuccessful
                    for source_points, point in source_ladder.points.items()
                    if source_points >= points
                )
                if source_ladder
                else 0.0
            )
            target_applicants_above = (
                sum(
                    point.actual_eligible_applicants
                    for target_points, point in target_ladder.points.items()
                    if target_points > points
                )
                if target_ladder
                else 0.0
            )
            arrival_residual_lower_bound = max(target_eligible - source_unsuccessful, 0.0)
            error = _as_float(score.get("absolute_error"))

            if str(forecast.get("hunt_code", "")).upper() != str(score.get("hunt_code", "")).upper():
                raise ValueError(f"Forecast row/code mismatch in {fold}: {row_number}")
            if str(forecast.get("residency", "")) != str(score.get("residency", "")):
                raise ValueError(f"Forecast row/residency mismatch in {fold}: {row_number}")
            if _as_int(forecast.get("points")) != points:
                raise ValueError(f"Forecast row/point mismatch in {fold}: {row_number}")

            audit_rows.append(
                {
                    "fold": fold,
                    "source_year": source_year,
                    "target_year": target_year,
                    "draw_design": score.get("draw_design", ""),
                    "hunt_code": score.get("hunt_code", ""),
                    "residency": score.get("residency", ""),
                    "points": points,
                    "draw_pool_key": score.get("draw_pool_key", ""),
                    "predicted_probability": score.get("predicted_probability", ""),
                    "actual_probability": score.get("actual_probability", ""),
                    "absolute_error": score.get("absolute_error", ""),
                    "tail_error_over_25pp": error > 0.25,
                    "source_lane_found": source_ladder is not None,
                    "target_lane_found": target_ladder is not None,
                    "source_predecessor_point_found": source_point is not None,
                    "source_baseline_point_found": source_baseline_point is not None,
                    "target_point_found": target_point is not None,
                    "source_lane_quota": round(source_quota, 6),
                    "target_lane_quota": round(target_quota, 6),
                    "quota_direction": _quota_direction(source_quota, target_quota),
                    "source_predecessor_eligible": round(source_eligible, 6),
                    "source_predecessor_drawn": round(source_drawn, 6),
                    "source_predecessor_unsuccessful": round(source_unsuccessful, 6),
                    "source_baseline_probability": (
                        ""
                        if source_baseline_point is None
                        or source_baseline_point.actual_probability is None
                        else round(source_baseline_point.actual_probability, 10)
                    ),
                    "source_unsuccessful_above_predecessor": round(
                        source_unsuccessful_above_predecessor, 6
                    ),
                    "target_eligible_at_point": round(target_eligible, 6),
                    "target_applicants_above": round(target_applicants_above, 6),
                    "arrival_residual_lower_bound": round(arrival_residual_lower_bound, 6),
                    "forecast_applicants_at_level": forecast_count,
                    "forecast_applicants_above": forecast_above,
                    "forecast_above_direction": _count_direction(
                        forecast_above, target_applicants_above
                    ),
                    "forecast_remaining_quota_at_point": max(
                        _as_int(
                            forecast.get("public_permits_target")
                            or forecast.get("public_permits_2026")
                        )
                        - forecast_above,
                        0,
                    ),
                    "actual_remaining_quota_at_point": max(
                        target_quota - target_applicants_above,
                        0.0,
                    ),
                    "forecast_count_direction": _count_direction(forecast_count, target_eligible),
                    "forecast_public_permits_target": _as_int(
                        forecast.get("public_permits_target") or forecast.get("public_permits_2026")
                    ),
                    "forecast_quota_source_type": forecast.get("quota_source_type", ""),
                    "forecast_algorithm_status": forecast.get("algorithm_status", ""),
                    "forecast_draw_pool": forecast.get("draw_pool", ""),
                    "forecast_hunt_class": forecast.get("hunt_class", ""),
                    "forecast_hunt_type": forecast.get("hunt_type", ""),
                    "forecast_reason_codes": forecast.get("reason_codes", ""),
                    "forecast_row_number": row_number,
                    "forecast_projection": str(forecast_path.relative_to(ROOT)),
                    "target_projection": str(target_path.relative_to(ROOT)),
                }
            )

    if not audit_rows:
        raise ValueError("No adult antlerless scored rows were found")

    group_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        grouped[
            (
                str(row["draw_design"]),
                str(row["residency"]),
                str(row["quota_direction"]),
                str(row["forecast_count_direction"]),
            )
        ].append(row)
    for key, rows in sorted(grouped.items()):
        errors = [_as_float(row["absolute_error"]) for row in rows]
        group_rows.append(
            {
                "draw_design": key[0],
                "residency": key[1],
                "quota_direction": key[2],
                "forecast_count_direction": key[3],
                "scored_rows": len(rows),
                "mae_pp": round(100.0 * sum(errors) / len(errors), 6),
                "tail_rows_over_25pp": sum(error > 0.25 for error in errors),
                "tail_rate_over_25pp": round(sum(error > 0.25 for error in errors) / len(errors), 8),
            }
        )

    tail_rows = [row for row in audit_rows if row["tail_error_over_25pp"]]
    _write_csv(args.out_dir / "adult_antlerless_transition_error_rows.csv", audit_rows)
    _write_csv(args.out_dir / "adult_antlerless_transition_tail_rows.csv", tail_rows)
    _write_csv(args.out_dir / "adult_antlerless_transition_error_summary.csv", group_rows)
    manifest = {
        "status": "READ_ONLY_TARGET_LABELED_DIAGNOSTIC",
        "forecast_behavior_changed": False,
        "truth_values_changed": False,
        "target_values_used_for_forecast": False,
        "score_input": str(score_path.relative_to(ROOT)),
        "score_input_sha256": _sha256(score_path),
        "truth_input": str(args.truth.relative_to(ROOT)),
        "truth_input_sha256": _sha256(args.truth),
        "adult_antlerless_scored_rows": len(audit_rows),
        "adult_antlerless_tail_rows": len(tail_rows),
        "source_lane_missing_rows": sum(not row["source_lane_found"] for row in audit_rows),
        "target_lane_missing_rows": sum(not row["target_lane_found"] for row in audit_rows),
        "output_files": [
            "adult_antlerless_transition_error_rows.csv",
            "adult_antlerless_transition_tail_rows.csv",
            "adult_antlerless_transition_error_summary.csv",
        ],
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
