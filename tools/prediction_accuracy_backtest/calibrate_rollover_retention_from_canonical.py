#!/usr/bin/env python3
"""Calibrate point-ladder rollover retention from canonical scorable outputs.

For adjacent year pairs, compare prior-year unsuccessful applicants at point P
to next-year applicants at point P+1 for the same hunt/residency/record type.
The observed ratio is not pure retention because hunters can switch hunts or
enter/exit the system, so the script reports capped robust estimates and
coverage/error diagnostics instead of treating ratios as gospel.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO / "audits" / "prediction_blind_year_to_year" / "rollover_retention_calibration"
SCORABLE_PATTERN = "outputs/{year} scorable draw results.csv"
SCORABLE_RECORD_TYPES = {"point_level_draw_result", "point_row"}


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    value_float = parse_float(value)
    if value_float is None or not value_float.is_integer():
        return None
    return int(value_float)


def norm_code(value: Any) -> str:
    return clean(value).upper()


def norm_residency(value: Any) -> str:
    text = clean(value).lower()
    if text in {"res", "resident"}:
        return "Resident"
    if text in {"nr", "nonresident", "non-resident", "non resident"}:
        return "Nonresident"
    return clean(value)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def expand_residency_rows(row: Mapping[str, str]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        applicants = parse_float(row.get(f"{prefix}_eligible_applicants"))
        drawn = parse_float(row.get(f"{prefix}_total_permits"))
        p_draw = parse_float(row.get(f"{prefix}_p_draw"))
        success_ratio = parse_float(row.get(f"{prefix}_success_ratio"))
        p_draw_percent = parse_float(row.get(f"{prefix}_p_draw_percent"))
        if applicants is None:
            continue
        out = dict(row)
        out["residency"] = residency
        out["eligible_applicants"] = applicants
        out["drawn_applicants"] = drawn or 0.0
        probability = p_draw if p_draw is not None else success_ratio
        if probability is None and p_draw_percent is not None:
            probability = p_draw_percent / 100.0 if p_draw_percent > 1.0 else p_draw_percent
        if probability is None and applicants > 0:
            probability = (drawn or 0.0) / applicants
        out["p_draw"] = min(max(probability or 0.0, 0.0), 1.0)
        expanded.append(out)
    return expanded


def point_bucket(point: int) -> str:
    if point == 0:
        return "0"
    if point <= 5:
        return "1-5"
    if point <= 10:
        return "6-10"
    if point <= 15:
        return "11-15"
    if point <= 20:
        return "16-20"
    return "21+"


def ladder_key(row: Mapping[str, Any], point: int | None = None) -> tuple[str, str, str, str, str, int]:
    return (
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        clean(row.get("record_type")).lower(),
        clean(row.get("draw_design")),
        clean(row.get("draw_pool")) or "standard",
        int(row.get("points") if point is None else point),
    )


def group_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        clean(row.get("record_type")).lower(),
        clean(row.get("draw_design")),
        clean(row.get("draw_pool")) or "standard",
    )


def load_year(year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = REPO / SCORABLE_PATTERN.format(year=year)
    headers, rows = read_csv(path)
    out: list[dict[str, Any]] = []
    excluded = Counter()
    for row in rows:
        record_type = clean(row.get("record_type")).lower()
        if record_type not in SCORABLE_RECORD_TYPES:
            excluded["non_point_record_type"] += 1
            continue
        point = parse_int(row.get("points"))
        if point is None:
            excluded["non_integer_point"] += 1
            continue
        for expanded in expand_residency_rows(row):
            applicants = expanded["eligible_applicants"]
            if applicants <= 0:
                excluded["zero_applicants"] += 1
                continue
            drawn = max(float(expanded["drawn_applicants"]), 0.0)
            out.append(
                {
                    "year": year,
                    "hunt_code": norm_code(row.get("hunt_code")),
                    "boundary_id": clean(row.get("boundary_id")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "species": clean(row.get("species")),
                    "residency": expanded["residency"],
                    "record_type": record_type,
                    "draw_design": clean(row.get("draw_design")),
                    "draw_pool": clean(row.get("draw_pool")) or "standard",
                    "points": point,
                    "point_bucket": point_bucket(point),
                    "eligible_applicants": applicants,
                    "drawn_applicants": min(drawn, applicants),
                    "unsuccessful_applicants": max(applicants - min(drawn, applicants), 0.0),
                    "p_draw": expanded["p_draw"],
                }
            )
    return out, {
        "year": year,
        "path": rel(path),
        "input_rows": len(rows),
        "input_columns": len(headers),
        "usable_point_rows": len(out),
        "excluded_rows": dict(excluded),
    }


def line_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return group_key(row)


def guarantee_line_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Find the contiguous top-end point level where actual odds are guaranteed."""
    if not rows:
        return {
            "guaranteed_line_points": "",
            "max_applicant_points": "",
            "highest_non_guaranteed_points": "",
            "line_confidence": "NO_APPLICANT_ROWS",
        }
    rows_by_point: dict[int, dict[str, Any]] = {}
    for row in rows:
        point = int(row["points"])
        existing = rows_by_point.get(point)
        if existing is None:
            rows_by_point[point] = dict(row)
            continue
        existing["eligible_applicants"] = float(existing["eligible_applicants"]) + float(row["eligible_applicants"])
        existing["drawn_applicants"] = float(existing["drawn_applicants"]) + float(row["drawn_applicants"])
        existing["p_draw"] = min(
            float(existing["drawn_applicants"]) / float(existing["eligible_applicants"])
            if float(existing["eligible_applicants"]) > 0
            else 0.0,
            1.0,
        )
    sorted_points = sorted(rows_by_point, reverse=True)
    max_point = sorted_points[0]
    top_guaranteed: list[int] = []
    for point in sorted_points:
        row = rows_by_point[point]
        applicants = float(row["eligible_applicants"])
        drawn = float(row["drawn_applicants"])
        p_draw = float(row["p_draw"])
        guaranteed = applicants > 0 and (p_draw >= 0.999999 or drawn >= applicants)
        if guaranteed:
            top_guaranteed.append(point)
            continue
        break
    guaranteed_line = min(top_guaranteed) if top_guaranteed else ""
    highest_non_guaranteed = ""
    for point in sorted_points:
        if guaranteed_line != "" and point >= int(guaranteed_line):
            continue
        row = rows_by_point[point]
        applicants = float(row["eligible_applicants"])
        drawn = float(row["drawn_applicants"])
        p_draw = float(row["p_draw"])
        if applicants > 0 and p_draw < 0.999999 and drawn < applicants:
            highest_non_guaranteed = point
            break
    return {
        "guaranteed_line_points": guaranteed_line,
        "max_applicant_points": max_point,
        "highest_non_guaranteed_points": highest_non_guaranteed,
        "top_guaranteed_point_count": len(top_guaranteed),
        "line_confidence": "HAS_TOP_GUARANTEED_ZONE" if top_guaranteed else "NO_GUARANTEED_APPLICANT_POINT",
    }


def compute_guarantee_lines(rows: list[dict[str, Any]], year: int) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[line_key(row)].append(row)
    lines: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for key, group_rows in grouped.items():
        sample = group_rows[0]
        line = guarantee_line_for_rows(group_rows)
        line.update(
            {
                "year": year,
                "hunt_code": sample["hunt_code"],
                "boundary_id": sample["boundary_id"],
                "hunt_name": sample["hunt_name"],
                "species": sample["species"],
                "residency": sample["residency"],
                "draw_design": sample["draw_design"],
                "record_type": sample["record_type"],
                "draw_pool": sample["draw_pool"],
                "applicant_point_rows": len(group_rows),
                "total_applicants": sum(float(row["eligible_applicants"]) for row in group_rows),
            }
        )
        lines[key] = line
    return lines


def relative_bucket(distance: int | None) -> str:
    if distance is None:
        return "NO_LINE"
    if distance <= -10:
        return "<=-10"
    if distance >= 5:
        return "5+"
    return str(distance)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else math.nan


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    index = min(max(int(round((len(ordered) - 1) * pct)), 0), len(ordered) - 1)
    return ordered[index]


def fmt(value: float) -> str:
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{value:.6f}"


def calibrate_pair(prior_year: int, next_year: int, output_dir: Path) -> dict[str, Any]:
    prior_rows, prior_audit = load_year(prior_year)
    next_rows, next_audit = load_year(next_year)
    prior_lines = compute_guarantee_lines(prior_rows, prior_year)
    next_lines = compute_guarantee_lines(next_rows, next_year)
    next_by_key = {ladder_key(row): row for row in next_rows}

    observations: list[dict[str, Any]] = []
    for row in prior_rows:
        unsuccessful = float(row["unsuccessful_applicants"])
        if unsuccessful <= 0:
            continue
        next_point = int(row["points"]) + 1
        next_row = next_by_key.get(ladder_key(row, next_point))
        if not next_row:
            continue
        prior_line = prior_lines.get(line_key(row), {})
        next_line = next_lines.get(line_key(next_row), {})
        prior_guaranteed_line = parse_int(prior_line.get("guaranteed_line_points"))
        next_guaranteed_line = parse_int(next_line.get("guaranteed_line_points"))
        distance = int(row["points"]) - prior_guaranteed_line if prior_guaranteed_line is not None else None
        next_distance = next_point - next_guaranteed_line if next_guaranteed_line is not None else None
        next_applicants = float(next_row["eligible_applicants"])
        raw_ratio = next_applicants / unsuccessful if unsuccessful > 0 else math.nan
        capped_retention = min(max(raw_ratio, 0.0), 1.0)
        excess_or_switcher_signal = max(next_applicants - unsuccessful, 0.0)
        retained_share_of_next = min(unsuccessful, next_applicants) / next_applicants if next_applicants > 0 else math.nan
        observations.append(
            {
                "prior_year": prior_year,
                "next_year": next_year,
                "hunt_code": row["hunt_code"],
                "boundary_id": row["boundary_id"],
                "hunt_name": row["hunt_name"],
                "species": row["species"],
                "residency": row["residency"],
                "draw_design": row["draw_design"],
                "record_type": row["record_type"],
                "points": row["points"],
                "next_points": next_point,
                "point_bucket": row["point_bucket"],
                "prior_guaranteed_line_points": "" if prior_guaranteed_line is None else prior_guaranteed_line,
                "next_guaranteed_line_points": "" if next_guaranteed_line is None else next_guaranteed_line,
                "points_relative_to_prior_guaranteed_line": "" if distance is None else distance,
                "next_points_relative_to_next_guaranteed_line": "" if next_distance is None else next_distance,
                "relative_to_prior_line_bucket": relative_bucket(distance),
                "prior_line_confidence": prior_line.get("line_confidence", ""),
                "next_line_confidence": next_line.get("line_confidence", ""),
                "prior_applicants": row["eligible_applicants"],
                "prior_drawn": row["drawn_applicants"],
                "prior_unsuccessful": unsuccessful,
                "next_applicants_at_plus_one": next_applicants,
                "raw_next_over_unsuccessful_ratio": raw_ratio,
                "capped_retention_estimate": capped_retention,
                "retained_share_of_next_applicants": retained_share_of_next,
                "excess_or_switcher_signal": excess_or_switcher_signal,
            }
        )

    fields = [
        "prior_year",
        "next_year",
        "hunt_code",
        "boundary_id",
        "hunt_name",
        "species",
        "residency",
        "draw_design",
        "record_type",
        "points",
        "next_points",
        "point_bucket",
        "prior_guaranteed_line_points",
        "next_guaranteed_line_points",
        "points_relative_to_prior_guaranteed_line",
        "next_points_relative_to_next_guaranteed_line",
        "relative_to_prior_line_bucket",
        "prior_line_confidence",
        "next_line_confidence",
        "prior_applicants",
        "prior_drawn",
        "prior_unsuccessful",
        "next_applicants_at_plus_one",
        "raw_next_over_unsuccessful_ratio",
        "capped_retention_estimate",
        "retained_share_of_next_applicants",
        "excess_or_switcher_signal",
    ]
    observation_path = output_dir / f"observations_{prior_year}_to_{next_year}.csv"
    write_csv(observation_path, fields, observations)
    line_fields = [
        "year",
        "hunt_code",
        "boundary_id",
        "hunt_name",
        "species",
        "residency",
        "draw_design",
        "record_type",
        "draw_pool",
        "guaranteed_line_points",
        "max_applicant_points",
        "highest_non_guaranteed_points",
        "top_guaranteed_point_count",
        "line_confidence",
        "applicant_point_rows",
        "total_applicants",
    ]
    prior_line_path = output_dir / f"guaranteed_lines_{prior_year}.csv"
    next_line_path = output_dir / f"guaranteed_lines_{next_year}.csv"
    write_csv(prior_line_path, line_fields, prior_lines.values())
    write_csv(next_line_path, line_fields, next_lines.values())

    return {
        "prior_year": prior_year,
        "next_year": next_year,
        "prior_audit": prior_audit,
        "next_audit": next_audit,
        "observation_rows": len(observations),
        "observation_path": rel(observation_path),
        "prior_guaranteed_line_path": rel(prior_line_path),
        "next_guaranteed_line_path": rel(next_line_path),
        "observations": observations,
    }


def summarize_groups(observations: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[tuple(clean(row.get(field)) for field in fields)].append(row)
    out: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        capped = [float(row["capped_retention_estimate"]) for row in rows]
        raw = [float(row["raw_next_over_unsuccessful_ratio"]) for row in rows]
        share = [float(row["retained_share_of_next_applicants"]) for row in rows]
        prior_unsuccessful = sum(float(row["prior_unsuccessful"]) for row in rows)
        next_applicants = sum(float(row["next_applicants_at_plus_one"]) for row in rows)
        weighted_capped = (
            sum(float(row["capped_retention_estimate"]) * float(row["prior_unsuccessful"]) for row in rows) / prior_unsuccessful
            if prior_unsuccessful > 0
            else math.nan
        )
        aggregate_raw_ratio = next_applicants / prior_unsuccessful if prior_unsuccessful > 0 else math.nan
        item = {field: key[index] for index, field in enumerate(fields)}
        item.update(
            {
                "observation_rows": len(rows),
                "prior_unsuccessful_total": fmt(prior_unsuccessful),
                "next_plus_one_applicant_total": fmt(next_applicants),
                "aggregate_next_over_unsuccessful_ratio": fmt(aggregate_raw_ratio),
                "median_capped_retention": fmt(median(capped)),
                "mean_capped_retention": fmt(mean(capped)),
                "weighted_capped_retention_by_unsuccessful": fmt(weighted_capped),
                "p25_capped_retention": fmt(percentile(capped, 0.25)),
                "p75_capped_retention": fmt(percentile(capped, 0.75)),
                "median_raw_ratio": fmt(median(raw)),
                "median_retained_share_of_next": fmt(median(share)),
                "rows_with_ratio_over_one": sum(1 for value in raw if value > 1.0),
            }
        )
        out.append(item)
    return out


def cumulative_pair_rows(pair_summaries: list[dict[str, Any]], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pair_summaries:
        prior_year = int(pair["prior_year"])
        next_year = int(pair["next_year"])
        through_rows = [
            row
            for row in observations
            if int(row["prior_year"]) >= int(pair_summaries[0]["prior_year"]) and int(row["next_year"]) <= next_year
        ]
        pair_rows = [row for row in observations if int(row["prior_year"]) == prior_year and int(row["next_year"]) == next_year]
        pair_metrics = summarize_groups(pair_rows, ["prior_year", "next_year"])[0] if pair_rows else {}
        cumulative_metrics = summarize_groups(through_rows, ["next_year"])[0] if through_rows else {}
        rows.append(
            {
                "prior_year": prior_year,
                "next_year": next_year,
                "year_pair_observation_rows": pair_metrics.get("observation_rows", 0),
                "year_pair_prior_unsuccessful_total": pair_metrics.get("prior_unsuccessful_total", ""),
                "year_pair_next_plus_one_applicant_total": pair_metrics.get("next_plus_one_applicant_total", ""),
                "year_pair_aggregate_ratio": pair_metrics.get("aggregate_next_over_unsuccessful_ratio", ""),
                "year_pair_weighted_capped_retention": pair_metrics.get("weighted_capped_retention_by_unsuccessful", ""),
                "year_pair_median_capped_retention": pair_metrics.get("median_capped_retention", ""),
                "cumulative_through_next_year_observation_rows": cumulative_metrics.get("observation_rows", 0),
                "cumulative_through_next_year_prior_unsuccessful_total": cumulative_metrics.get("prior_unsuccessful_total", ""),
                "cumulative_through_next_year_next_plus_one_applicant_total": cumulative_metrics.get("next_plus_one_applicant_total", ""),
                "cumulative_through_next_year_aggregate_ratio": cumulative_metrics.get("aggregate_next_over_unsuccessful_ratio", ""),
                "cumulative_through_next_year_weighted_capped_retention": cumulative_metrics.get("weighted_capped_retention_by_unsuccessful", ""),
                "cumulative_through_next_year_median_capped_retention": cumulative_metrics.get("median_capped_retention", ""),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pair_summaries = []
    all_observations: list[dict[str, Any]] = []
    for prior_year in range(args.start_year, args.end_year):
        pair = calibrate_pair(prior_year, prior_year + 1, args.output_dir)
        observations = pair.pop("observations")
        all_observations.extend(observations)
        pair_summaries.append(pair)

    group_specs = {
        "by_year_pair_point_bucket": ["prior_year", "next_year", "point_bucket"],
        "by_year_pair_relative_to_prior_guaranteed_line": ["prior_year", "next_year", "relative_to_prior_line_bucket"],
        "by_year_pair_draw_design_point_bucket": ["prior_year", "next_year", "draw_design", "point_bucket"],
        "by_year_pair_draw_design_relative_to_prior_guaranteed_line": [
            "prior_year",
            "next_year",
            "draw_design",
            "relative_to_prior_line_bucket",
        ],
        "by_year_pair_species_draw_design_relative_to_prior_guaranteed_line": [
            "prior_year",
            "next_year",
            "species",
            "draw_design",
            "relative_to_prior_line_bucket",
        ],
        "by_point_bucket": ["point_bucket"],
        "by_relative_to_prior_guaranteed_line": ["relative_to_prior_line_bucket"],
        "by_draw_design_relative_to_prior_guaranteed_line": ["draw_design", "relative_to_prior_line_bucket"],
        "by_species_draw_design_relative_to_prior_guaranteed_line": ["species", "draw_design", "relative_to_prior_line_bucket"],
        "by_hunt_relative_to_prior_guaranteed_line": ["hunt_code", "residency", "draw_design", "relative_to_prior_line_bucket"],
        "by_draw_design_point_bucket": ["draw_design", "point_bucket"],
        "by_species_draw_design_point_bucket": ["species", "draw_design", "point_bucket"],
        "by_residency_point_bucket": ["residency", "point_bucket"],
        "by_year_pair": ["prior_year", "next_year"],
    }
    summary_paths = {}
    base_fields = [
        "observation_rows",
        "prior_unsuccessful_total",
        "next_plus_one_applicant_total",
        "aggregate_next_over_unsuccessful_ratio",
        "median_capped_retention",
        "mean_capped_retention",
        "weighted_capped_retention_by_unsuccessful",
        "p25_capped_retention",
        "p75_capped_retention",
        "median_raw_ratio",
        "median_retained_share_of_next",
        "rows_with_ratio_over_one",
    ]
    for name, fields in group_specs.items():
        rows = summarize_groups(all_observations, fields)
        path = args.output_dir / f"{name}.csv"
        write_csv(path, fields + base_fields, rows)
        summary_paths[name] = rel(path)

    cumulative_path = args.output_dir / "year_pair_and_cumulative_rollup.csv"
    cumulative_fields = [
        "prior_year",
        "next_year",
        "year_pair_observation_rows",
        "year_pair_prior_unsuccessful_total",
        "year_pair_next_plus_one_applicant_total",
        "year_pair_aggregate_ratio",
        "year_pair_weighted_capped_retention",
        "year_pair_median_capped_retention",
        "cumulative_through_next_year_observation_rows",
        "cumulative_through_next_year_prior_unsuccessful_total",
        "cumulative_through_next_year_next_plus_one_applicant_total",
        "cumulative_through_next_year_aggregate_ratio",
        "cumulative_through_next_year_weighted_capped_retention",
        "cumulative_through_next_year_median_capped_retention",
    ]
    write_csv(cumulative_path, cumulative_fields, cumulative_pair_rows(pair_summaries, all_observations))
    summary_paths["year_pair_and_cumulative_rollup"] = rel(cumulative_path)

    top_switcher_signal = sorted(all_observations, key=lambda row: float(row["excess_or_switcher_signal"]), reverse=True)[:250]
    top_path = args.output_dir / "top_excess_or_switcher_signal_rows.csv"
    write_csv(
        top_path,
        [
            "prior_year",
            "next_year",
            "hunt_code",
            "hunt_name",
            "species",
            "residency",
            "draw_design",
            "points",
            "next_points",
            "prior_unsuccessful",
            "next_applicants_at_plus_one",
            "raw_next_over_unsuccessful_ratio",
            "excess_or_switcher_signal",
        ],
        top_switcher_signal,
    )

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "method": "prior_year_unsuccessful_applicants_at_point_P_compared_to_next_year_applicants_at_point_P_plus_1",
        "caution": "Ratios above 1.0 indicate switchers/new entrants or hunt-code/crosswalk effects; capped retention is used for retention-rate estimates.",
        "pair_summaries": pair_summaries,
        "total_observation_rows": len(all_observations),
        "summary_paths": summary_paths | {"top_excess_or_switcher_signal_rows": rel(top_path)},
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps({"total_observation_rows": len(all_observations), "summary_paths": summary_paths}, indent=2))


if __name__ == "__main__":
    main()
