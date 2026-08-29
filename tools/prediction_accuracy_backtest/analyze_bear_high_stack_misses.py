"""Classify source-only Black Bear false guarantees by permit and cohort evidence.

This tool is deliberately read-only.  It opens the already-frozen lane-fold
inputs and identifies whether a deterministic false guarantee had fewer actual
max-point permits than forecast, or whether the held-out applicant stack
exceeded the correctly forecast max-point pool.  The latter rows are joined to
their source-year predecessor rung so a cohort behavior can be evaluated
without reading target truth into the forecast.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
AUDIT_ROOT = ROOT / "audits" / "prediction_blind_year_to_year"

# These are the only four source-only, held-out Black Bear residency-lane
# folds.  The last fold uses its scoped permit-proxy repair; the other three
# use the archived-PDF identity repair.
FOLDS = (
    ("2018_to_2019", "black_bear_residency_lanes_2018_to_2019_20260828", "historical_identity_repair"),
    ("2019_to_2020", "black_bear_residency_lanes_2019_to_2020_20260828", "historical_identity_repair"),
    ("2020_to_2021", "black_bear_residency_lanes_2020_to_2021_20260828", "historical_identity_repair"),
    ("2021_to_2022", "black_bear_residency_lanes_2021_to_2022_20260828", "lane_proxy_repair"),
)


def clean(value: object) -> str:
    return str(value or "").strip()


def integer(value: object) -> int:
    try:
        return int(float(clean(value)))
    except ValueError:
        return 0


def number(value: object) -> float:
    try:
        return float(clean(value))
    except ValueError:
        return 0.0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def bucket(points: int) -> str:
    if points == 0:
        return "0"
    if points <= 2:
        return "1_2"
    if points <= 5:
        return "3_5"
    if points <= 9:
        return "6_9"
    return "10_plus"


def write_rows(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fold_paths(fold_dir: str, variant: str) -> tuple[str, str, Path, Path, Path, Path]:
    base = AUDIT_ROOT / fold_dir
    variant_root = base / variant
    source_year, target_year = fold_dir.split("_lanes_", 1)[1].split("_20260828", 1)[0].split("_to_")
    source_candidates = [
        variant_root / f"source_truth_through_{source_year}.csv",
        base / "historical_identity_repair" / f"source_truth_through_{source_year}.csv",
        base / f"source_truth_through_{source_year}.csv",
    ]
    actual_candidates = [
        variant_root / f"actual_{target_year}_residency_lanes.csv",
        base / "historical_identity_repair" / f"actual_{target_year}_residency_lanes.csv",
        base / f"actual_{target_year}_residency_lanes.csv",
    ]
    source = next((path for path in source_candidates if path.exists()), None)
    actual = next((path for path in actual_candidates if path.exists()), None)
    if source is None or actual is None:
        raise FileNotFoundError(f"Missing frozen source or actual for {fold_dir}")
    comparison = variant_root / "comparison_phase" / "draw_line_aware_actual_ladder_scoring_rows.csv"
    forecast = variant_root / "prediction_phase" / "predictions" / f"{source_year}_{target_year}_bonus_bear.csv"
    return source_year, target_year, source, actual, comparison, forecast


def analyze_fold(name: str, fold_dir: str, variant: str) -> list[dict[str, object]]:
    source_year, target_year, source_path, actual_path, comparison_path, forecast_path = fold_paths(fold_dir, variant)
    score_rows = read_rows(comparison_path)
    forecast_rows = read_rows(forecast_path)
    source_rows = read_rows(source_path)
    actual_rows = read_rows(actual_path)

    forecasts = {
        (clean(row["hunt_code"]), clean(row["residency"]), integer(row["points"])): row
        for row in forecast_rows
    }
    source_by_key: dict[tuple[str, str, int], dict[str, str]] = {}
    for row in source_rows:
        # The frozen input contains earlier history for retention fitting.  The
        # predecessor ladder is the final source-year actual, whose model key
        # is the fold's target year.
        if integer(row.get("model_target_year")) != integer(target_year):
            continue
        key = (clean(row.get("hunt_code")), clean(row.get("residency")), integer(row.get("points")))
        if key[0].startswith("BR") and key[1] in {"Resident", "Nonresident"}:
            source_by_key[key] = row
    actual_by_lane: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in actual_rows:
        code = clean(row.get("hunt_code"))
        residency = clean(row.get("residency"))
        if code.startswith("BR") and residency in {"Resident", "Nonresident"}:
            actual_by_lane[(code, residency)].append(row)

    output: list[dict[str, object]] = []
    for score in score_rows:
        if (
            clean(score.get("family_actual")) != "bonus_bear"
            or clean(score.get("scoreability_status")) != "scoreable"
            or number(score.get("predicted_probability")) < 0.999999
            or number(score.get("actual_probability")) >= 0.999999
        ):
            continue
        code = clean(score["hunt_code"])
        residency = clean(score["residency"])
        points = integer(score["points"])
        forecast = forecasts.get((code, residency, points))
        if forecast is None:
            raise KeyError(f"Missing frozen Bear forecast for {name} {code} {residency} {points}")
        lane_actual = actual_by_lane[(code, residency)]
        actual_max_permits = sum(integer(row.get("bonus_permits")) for row in lane_actual)
        forecast_max_permits = integer(forecast.get("max_point_permits_2026"))
        actual_at = sum(integer(row.get("eligible_applicants")) for row in lane_actual if integer(row.get("points")) == points)
        actual_above = sum(integer(row.get("eligible_applicants")) for row in lane_actual if integer(row.get("points")) > points)
        source_lane = [
            row
            for (source_code, source_residency, _), row in source_by_key.items()
            if source_code == code and source_residency == residency
        ]
        source_above_unsuccessful = sum(
            max(0, integer(row.get("eligible_applicants")) - integer(row.get("bonus_permits")) - integer(row.get("regular_permits")))
            for row in source_lane
            if integer(row.get("points")) > points
        )
        source_above_eligible = sum(
            integer(row.get("eligible_applicants")) for row in source_lane if integer(row.get("points")) > points
        )
        source_top_applicant_point = max(
            (integer(row.get("points")) for row in source_lane if integer(row.get("eligible_applicants")) > 0),
            default=-1,
        )
        target_top_applicant_point = max(
            (integer(row.get("points")) for row in lane_actual if integer(row.get("eligible_applicants")) > 0),
            default=-1,
        )
        target_above_source_top = sum(
            integer(row.get("eligible_applicants"))
            for row in lane_actual
            if integer(row.get("points")) > source_top_applicant_point
        )
        source_previous = source_by_key.get((code, residency, points - 1), {})
        source_same = source_by_key.get((code, residency, points), {})
        predecessor_eligible = integer(source_previous.get("eligible_applicants"))
        predecessor_unsuccessful = max(
            0,
            predecessor_eligible - integer(source_previous.get("bonus_permits")) - integer(source_previous.get("regular_permits")),
        )
        source_same_eligible = integer(source_same.get("eligible_applicants"))
        forecast_at = integer(forecast.get("applicants_at_level"))
        forecast_above = integer(forecast.get("applicants_above"))
        cause = "PERMIT_PROXY_OVERESTIMATE" if actual_max_permits < forecast_max_permits else "HIGH_STACK_DEMAND_MISS"
        output.append(
            {
                "fold": name,
                "hunt_code": code,
                "subtype": clean(forecast.get("bear_draw_subtype")),
                "residency": residency,
                "points": points,
                "point_bucket": bucket(points),
                "point_relation": clean(score.get("point_relation_to_draw_line")),
                "cause": cause,
                "forecast_max_permits": forecast_max_permits,
                "actual_max_permits": actual_max_permits,
                "forecast_above": forecast_above,
                "actual_above": actual_above,
                "forecast_at": forecast_at,
                "actual_at": actual_at,
                "forecast_stack": forecast_above + forecast_at,
                "actual_stack": actual_above + actual_at,
                "source_predecessor_eligible": predecessor_eligible,
                "source_predecessor_unsuccessful": predecessor_unsuccessful,
                "source_same_point_eligible": source_same_eligible,
                "source_above_eligible": source_above_eligible,
                "source_above_unsuccessful": source_above_unsuccessful,
                "latent_reentry_floor_above": max(0, actual_above - source_above_unsuccessful),
                "source_upper_stack_all_drawn": int(source_above_eligible > 0 and source_above_unsuccessful == 0),
                "source_top_applicant_point": source_top_applicant_point,
                "target_top_applicant_point": target_top_applicant_point,
                "target_applicants_above_source_top": target_above_source_top,
                "forecast_at_minus_rollforward": forecast_at - predecessor_unsuccessful,
                "actual_at_minus_rollforward": actual_at - predecessor_unsuccessful,
                "actual_probability": number(score.get("actual_probability")),
            }
        )
    return output


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in ("fold", "cause", "subtype", "residency", "point_bucket", "point_relation"))
        grouped[key].append(row)
    summary = []
    for key, group in sorted(grouped.items()):
        summary.append(
            {
                "fold": key[0],
                "cause": key[1],
                "subtype": key[2],
                "residency": key[3],
                "point_bucket": key[4],
                "point_relation": key[5],
                "rows": len(group),
                "mean_actual_stack_minus_forecast": round(sum(int(row["actual_stack"]) - int(row["forecast_stack"]) for row in group) / len(group), 4),
                "mean_actual_at_minus_rollforward": round(sum(int(row["actual_at_minus_rollforward"]) for row in group) / len(group), 4),
            }
        )
    return summary


def historical_latent_reentry() -> list[dict[str, object]]:
    """Measure re-entry that cannot come from a source unsuccessful cohort.

    A point-only applicant or a high-point holder who sat out the prior draw is
    not represented in that draw's hunt ladder.  For adjacent official years,
    the minimum such re-entry at target point ``p`` is the positive remainder
    after source point ``p - 1`` unsuccessful applicants have advanced.
    """
    path = ROOT / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2018_2022_pdf_residency_ladders.csv"
    rows = read_rows(path)
    index = {
        (integer(row["reported_draw_year"]), clean(row["hunt_code"]), clean(row["residency"]), integer(row["points"])): row
        for row in rows
    }
    lane_points: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    for year, code, residency, points in index:
        if residency == "Resident":
            lane_points[(year, code, residency)].add(points)
    output: list[dict[str, object]] = []
    for (source_year, code, residency), points in lane_points.items():
        target_year = source_year + 1
        if (target_year, code, residency) not in lane_points:
            continue
        for point in lane_points[(target_year, code, residency)]:
            if point <= 0:
                continue
            target = index[(target_year, code, residency, point)]
            predecessor = index.get((source_year, code, residency, point - 1), {})
            same_point = index.get((source_year, code, residency, point), {})
            predecessor_unsuccessful = max(
                0,
                integer(predecessor.get("eligible_applicants"))
                - integer(predecessor.get("bonus_permits"))
                - integer(predecessor.get("regular_permits")),
            )
            target_eligible = integer(target.get("eligible_applicants"))
            source_same_eligible = integer(same_point.get("eligible_applicants"))
            latent = max(0, target_eligible - predecessor_unsuccessful)
            output.append(
                {
                    "source_year": source_year,
                    "target_year": target_year,
                    "hunt_code": code,
                    "subtype": clean(target.get("source_classification")),
                    "residency": residency,
                    "points": point,
                    "point_bucket": bucket(point),
                    "target_eligible": target_eligible,
                    "source_predecessor_unsuccessful": predecessor_unsuccessful,
                    "source_same_point_eligible": source_same_eligible,
                    "latent_reentry_minimum": latent,
                    "source_predecessor_all_drawn": int(
                        integer(predecessor.get("eligible_applicants")) > 0 and predecessor_unsuccessful == 0
                    ),
                }
            )
    return output


def summarize_historical_reentry(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["subtype"]), str(row["point_bucket"]))].append(row)
    summary = []
    for (subtype, point_bucket), group in sorted(grouped.items()):
        latent = sum(integer(row["latent_reentry_minimum"]) for row in group)
        source_same = sum(integer(row["source_same_point_eligible"]) for row in group)
        summary.append(
            {
                "subtype": subtype,
                "point_bucket": point_bucket,
                "adjacent_year_rows": len(group),
                "rows_with_latent_reentry": sum(integer(row["latent_reentry_minimum"]) > 0 for row in group),
                "latent_reentry_total": latent,
                "source_same_point_total": source_same,
                "latent_reentry_rate_vs_same_point": round(latent / source_same, 6) if source_same else "",
            }
        )
    return summary


def historical_top_tail_reentry() -> list[dict[str, object]]:
    """Measure target applicants that appear above the source active ladder."""
    path = ROOT / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2018_2022_pdf_residency_ladders.csv"
    rows = read_rows(path)
    index: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if clean(row.get("residency")) == "Resident" and clean(row.get("source_classification")) == "TRUE_BEAR_BONUS_DRAW":
            index[(integer(row["reported_draw_year"]), clean(row["hunt_code"]), clean(row["residency"]))].append(row)
    output: list[dict[str, object]] = []
    for (source_year, code, residency), source_lane in index.items():
        target_lane = index.get((source_year + 1, code, residency))
        if not target_lane:
            continue
        source_top = max(
            (integer(row["points"]) for row in source_lane if integer(row["eligible_applicants"]) > 0),
            default=-1,
        )
        target_top = max(
            (integer(row["points"]) for row in target_lane if integer(row["eligible_applicants"]) > 0),
            default=-1,
        )
        target_tail = sum(integer(row["eligible_applicants"]) for row in target_lane if integer(row["points"]) > source_top)
        output.append(
            {
                "source_year": source_year,
                "target_year": source_year + 1,
                "hunt_code": code,
                "residency": residency,
                "source_top_applicant_point": source_top,
                "target_top_applicant_point": target_top,
                "target_applicants_above_source_top": target_tail,
                "target_has_new_top_tail": int(target_tail > 0),
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=AUDIT_ROOT / "black_bear_residency_lanes_high_stack_analysis_20260828",
        help="Audit-only output directory; existing truth and forecast inputs are never modified.",
    )
    args = parser.parse_args()
    rows: list[dict[str, object]] = []
    for fold in FOLDS:
        rows.extend(analyze_fold(*fold))
    high_stack = [row for row in rows if row["cause"] == "HIGH_STACK_DEMAND_MISS"]
    reentry = historical_latent_reentry()
    top_tail = historical_top_tail_reentry()
    write_rows(args.out_dir / "all_false_guarantee_roots.csv", rows)
    write_rows(args.out_dir / "high_stack_demand_misses.csv", high_stack)
    write_rows(args.out_dir / "high_stack_demand_miss_summary.csv", summarize(high_stack))
    write_rows(args.out_dir / "historical_latent_reentry_transitions.csv", reentry)
    write_rows(args.out_dir / "historical_latent_reentry_summary.csv", summarize_historical_reentry(reentry))
    write_rows(args.out_dir / "historical_top_tail_reentry.csv", top_tail)
    print(
        {
            "false_guarantees": len(rows),
            "permit_proxy_overestimates": sum(row["cause"] == "PERMIT_PROXY_OVERESTIMATE" for row in rows),
            "high_stack_demand_misses": len(high_stack),
            "output": str(args.out_dir),
        }
    )


if __name__ == "__main__":
    main()
