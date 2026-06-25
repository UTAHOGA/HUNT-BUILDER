#!/usr/bin/env python3
"""Identify Max/Weighted mixed cutoff points and same-hunt rollover.

This script is intentionally scoped to the Max/Weighted Split draw design.
For each hunt/year/residency it identifies:

* top applicant point
* top contiguous 100% guaranteed stack, when present
* highest mixed/unsuccessful point, which is the rollover anchor
* next-year applicants at anchor + 1 for the same hunt identity

Hunt identity is code-first, then hunt name, species, sex, and weapon.
Boundary ID and season are reported for confidence, but are not allowed to
override the code/name/species/sex/weapon identity.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO / "audits" / "prediction_blind_year_to_year" / "max_weighted_mixed_cutoff_rollover"
SCORABLE_PATTERN = "outputs/{year} scorable draw results.csv"
TARGET_DRAW_DESIGN = "Max/Weighted Split"
POINT_RECORD_TYPES = {"point_level_draw_result", "point_row"}


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_text(value: Any) -> str:
    return " ".join(clean(value).lower().replace("-", " ").split())


def norm_code(value: Any) -> str:
    return clean(value).upper()


def parse_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


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


def probability(row: Mapping[str, Any], prefix: str) -> float | None:
    for field in (f"{prefix}_p_draw", f"{prefix}_success_ratio"):
        value = parse_float(row.get(field))
        if value is not None:
            return min(max(value / 100.0 if value > 1.0 else value, 0.0), 1.0)
    pct = parse_float(row.get(f"{prefix}_p_draw_percent"))
    if pct is not None:
        return min(max(pct / 100.0, 0.0), 1.0)
    applicants = parse_float(row.get(f"{prefix}_eligible_applicants"))
    drawn = parse_float(row.get(f"{prefix}_total_permits"))
    if applicants and applicants > 0 and drawn is not None:
        return min(max(drawn / applicants, 0.0), 1.0)
    return None


def sex_value(row: Mapping[str, Any]) -> str:
    return clean(row.get("sex_type")) or clean(row.get("sex"))


def identity_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    return (
        norm_code(row.get("hunt_code")),
        norm_text(row.get("hunt_name")),
        norm_text(row.get("species")),
        norm_text(row.get("sex_type") or row.get("sex")),
        norm_text(row.get("weapon")),
        clean(row.get("residency")),
        clean(row.get("draw_pool")) or "standard",
    )


def code_residency_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (norm_code(row.get("hunt_code")), clean(row.get("residency")), clean(row.get("draw_pool")) or "standard")


def descriptive_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        norm_text(row.get("hunt_name")),
        norm_text(row.get("species")),
        norm_text(row.get("sex_type") or row.get("sex")),
        norm_text(row.get("weapon")),
        clean(row.get("residency")),
        clean(row.get("draw_pool")) or "standard",
    )


def expand_rows(raw: Mapping[str, str], year: int) -> list[dict[str, Any]]:
    if clean(raw.get("record_type")).lower() not in POINT_RECORD_TYPES:
        return []
    if clean(raw.get("draw_design")) != TARGET_DRAW_DESIGN:
        return []
    point = parse_int(raw.get("points"))
    if point is None:
        return []
    output: list[dict[str, Any]] = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        applicants = parse_float(raw.get(f"{prefix}_eligible_applicants"))
        if applicants is None or applicants <= 0:
            continue
        drawn = parse_float(raw.get(f"{prefix}_total_permits")) or 0.0
        drawn = min(max(drawn, 0.0), applicants)
        output.append(
            {
                "year": year,
                "hunt_code": norm_code(raw.get("hunt_code")),
                "hunt_name": clean(raw.get("hunt_name")),
                "species": clean(raw.get("species")),
                "sex_type": sex_value(raw),
                "weapon": clean(raw.get("weapon")),
                "season": clean(raw.get("season")),
                "boundary_id": clean(raw.get("boundary_id")),
                "residency": residency,
                "draw_pool": clean(raw.get("draw_pool")) or "standard",
                "draw_design": clean(raw.get("draw_design")),
                "record_type": clean(raw.get("record_type")).lower(),
                "points": point,
                "eligible_applicants": applicants,
                "drawn_applicants": drawn,
                "unsuccessful_applicants": max(applicants - drawn, 0.0),
                "p_draw": probability(raw, prefix),
            }
        )
    return output


def load_year(year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = REPO / SCORABLE_PATTERN.format(year=year)
    headers, raw_rows = read_csv(path)
    rows: list[dict[str, Any]] = []
    excluded = Counter()
    for raw in raw_rows:
        expanded = expand_rows(raw, year)
        if not expanded:
            excluded["not_usable_max_weighted_point_row"] += 1
        rows.extend(expanded)
    return rows, {
        "year": year,
        "path": rel(path),
        "input_rows": len(raw_rows),
        "input_columns": len(headers),
        "usable_rows": len(rows),
        "excluded_rows": dict(excluded),
    }


def aggregate_group(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_point: dict[int, dict[str, Any]] = {}
    for row in rows:
        point = int(row["points"])
        if point not in by_point:
            by_point[point] = dict(row)
        else:
            target = by_point[point]
            target["eligible_applicants"] = float(target["eligible_applicants"]) + float(row["eligible_applicants"])
            target["drawn_applicants"] = float(target["drawn_applicants"]) + float(row["drawn_applicants"])
            target["unsuccessful_applicants"] = max(float(target["eligible_applicants"]) - float(target["drawn_applicants"]), 0.0)
            target["p_draw"] = (
                min(float(target["drawn_applicants"]) / float(target["eligible_applicants"]), 1.0)
                if float(target["eligible_applicants"]) > 0
                else None
            )
    return by_point


def is_guaranteed(row: Mapping[str, Any]) -> bool:
    applicants = float(row.get("eligible_applicants") or 0.0)
    drawn = float(row.get("drawn_applicants") or 0.0)
    p_draw = row.get("p_draw")
    p_value = float(p_draw) if p_draw not in (None, "") else drawn / applicants if applicants > 0 else 0.0
    return applicants > 0 and (drawn >= applicants or p_value >= 0.999999)


def identify_cutoff(year: int, identity: tuple[str, str, str, str, str, str, str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_point = aggregate_group(rows)
    sample = rows[0]
    points_desc = sorted(by_point, reverse=True)
    top_point = points_desc[0] if points_desc else ""
    guaranteed_stack: list[int] = []
    for point in points_desc:
        if is_guaranteed(by_point[point]):
            guaranteed_stack.append(point)
            continue
        break
    mixed_cutoff = ""
    for point in points_desc:
        if float(by_point[point]["unsuccessful_applicants"]) > 0:
            mixed_cutoff = point
            break
    if mixed_cutoff == "":
        structure = "ALL_APPLICANT_POINTS_GUARANTEED"
    elif mixed_cutoff == top_point:
        structure = "TOP_POINT_MIXED"
    elif guaranteed_stack:
        structure = "HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF"
    else:
        structure = "MIXED_CUTOFF_WITH_NONCONTIGUOUS_TOP_PATTERN"
    cutoff_row = by_point.get(mixed_cutoff) if mixed_cutoff != "" else {}
    guaranteed_bottom = min(guaranteed_stack) if guaranteed_stack else ""
    return {
        "year": year,
        "hunt_code": sample["hunt_code"],
        "hunt_name": sample["hunt_name"],
        "species": sample["species"],
        "sex_type": sample["sex_type"],
        "weapon": sample["weapon"],
        "residency": sample["residency"],
        "draw_pool": sample["draw_pool"],
        "boundary_id": sample["boundary_id"],
        "season": sample["season"],
        "draw_design": TARGET_DRAW_DESIGN,
        "identity_key": "|".join(str(part) for part in identity),
        "top_applicant_point": top_point,
        "guaranteed_stack_points": ";".join(str(point) for point in guaranteed_stack),
        "guaranteed_stack_count": len(guaranteed_stack),
        "lowest_guaranteed_stack_point": guaranteed_bottom,
        "mixed_cutoff_point": mixed_cutoff,
        "mixed_cutoff_next_year_point": "" if mixed_cutoff == "" else int(mixed_cutoff) + 1,
        "cutoff_structure": structure,
        "point_rows": len(by_point),
        "total_applicants": sum(float(row["eligible_applicants"]) for row in by_point.values()),
        "mixed_cutoff_applicants": cutoff_row.get("eligible_applicants", ""),
        "mixed_cutoff_drawn": cutoff_row.get("drawn_applicants", ""),
        "mixed_cutoff_unsuccessful": cutoff_row.get("unsuccessful_applicants", ""),
        "mixed_cutoff_p_draw": cutoff_row.get("p_draw", ""),
    }


def group_year(rows: list[dict[str, Any]], year: int) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str, str, str, str], dict[int, dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[identity_key(row)].append(row)
    cutoffs = [identify_cutoff(year, key, values) for key, values in grouped.items()]
    point_lookup = {key: aggregate_group(values) for key, values in grouped.items()}
    return cutoffs, point_lookup


def match_next_identity(prior_cutoff: Mapping[str, Any], next_cutoffs: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    exact = [
        row
        for row in next_cutoffs
        if row["hunt_code"] == prior_cutoff["hunt_code"]
        and norm_text(row["hunt_name"]) == norm_text(prior_cutoff["hunt_name"])
        and norm_text(row["species"]) == norm_text(prior_cutoff["species"])
        and norm_text(row["sex_type"]) == norm_text(prior_cutoff["sex_type"])
        and norm_text(row["weapon"]) == norm_text(prior_cutoff["weapon"])
        and row["residency"] == prior_cutoff["residency"]
        and row["draw_pool"] == prior_cutoff["draw_pool"]
    ]
    if exact:
        return "EXACT_CODE_NAME_SPECIES_SEX_WEAPON", exact[0]
    same_code = [
        row
        for row in next_cutoffs
        if row["hunt_code"] == prior_cutoff["hunt_code"] and row["residency"] == prior_cutoff["residency"] and row["draw_pool"] == prior_cutoff["draw_pool"]
    ]
    if same_code:
        return "SAME_CODE_DESCRIPTIVE_CHANGED_REVIEW", same_code[0]
    same_description = [
        row
        for row in next_cutoffs
        if norm_text(row["hunt_name"]) == norm_text(prior_cutoff["hunt_name"])
        and norm_text(row["species"]) == norm_text(prior_cutoff["species"])
        and norm_text(row["sex_type"]) == norm_text(prior_cutoff["sex_type"])
        and norm_text(row["weapon"]) == norm_text(prior_cutoff["weapon"])
        and row["residency"] == prior_cutoff["residency"]
        and row["draw_pool"] == prior_cutoff["draw_pool"]
    ]
    if same_description:
        return "NAME_SPECIES_SEX_WEAPON_MATCH_CODE_CHANGED_REVIEW", same_description[0]
    return "NO_NEXT_YEAR_HUNT_MATCH", None


def build_rollover_rows(
    prior_year: int,
    next_year: int,
    prior_cutoffs: list[dict[str, Any]],
    next_cutoffs: list[dict[str, Any]],
    next_point_lookup: dict[tuple[str, str, str, str, str, str, str], dict[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    next_by_identity = {row["identity_key"]: row for row in next_cutoffs}
    del next_by_identity
    rows: list[dict[str, Any]] = []
    for cutoff in prior_cutoffs:
        mixed_point = parse_int(cutoff.get("mixed_cutoff_point"))
        unsuccessful = parse_float(cutoff.get("mixed_cutoff_unsuccessful"))
        if mixed_point is None or unsuccessful is None or unsuccessful <= 0:
            continue
        match_type, next_match = match_next_identity(cutoff, next_cutoffs)
        next_point = mixed_point + 1
        next_applicants = ""
        next_boundary_id = ""
        next_hunt_name = ""
        next_mixed_cutoff = ""
        next_cutoff_structure = ""
        if next_match:
            next_identity = (
                norm_code(next_match.get("hunt_code")),
                norm_text(next_match.get("hunt_name")),
                norm_text(next_match.get("species")),
                norm_text(next_match.get("sex_type")),
                norm_text(next_match.get("weapon")),
                clean(next_match.get("residency")),
                clean(next_match.get("draw_pool")) or "standard",
            )
            point_row = next_point_lookup.get(next_identity, {}).get(next_point)
            next_applicants = point_row.get("eligible_applicants", "") if point_row else ""
            next_boundary_id = next_match.get("boundary_id", "")
            next_hunt_name = next_match.get("hunt_name", "")
            next_mixed_cutoff = next_match.get("mixed_cutoff_point", "")
            next_cutoff_structure = next_match.get("cutoff_structure", "")
        next_value = parse_float(next_applicants)
        raw_ratio = next_value / unsuccessful if next_value is not None and unsuccessful > 0 else ""
        capped_retention = min(max(raw_ratio, 0.0), 1.0) if raw_ratio != "" else ""
        rows.append(
            {
                "prior_year": prior_year,
                "next_year": next_year,
                "hunt_code": cutoff["hunt_code"],
                "hunt_name": cutoff["hunt_name"],
                "next_hunt_name": next_hunt_name,
                "species": cutoff["species"],
                "sex_type": cutoff["sex_type"],
                "weapon": cutoff["weapon"],
                "residency": cutoff["residency"],
                "draw_pool": cutoff["draw_pool"],
                "boundary_id": cutoff["boundary_id"],
                "next_boundary_id": next_boundary_id,
                "same_hunt_match_type": match_type,
                "prior_cutoff_structure": cutoff["cutoff_structure"],
                "prior_top_applicant_point": cutoff["top_applicant_point"],
                "prior_guaranteed_stack_points": cutoff["guaranteed_stack_points"],
                "prior_mixed_cutoff_point": mixed_point,
                "expected_next_point": next_point,
                "prior_mixed_cutoff_applicants": cutoff["mixed_cutoff_applicants"],
                "prior_mixed_cutoff_drawn": cutoff["mixed_cutoff_drawn"],
                "prior_mixed_cutoff_unsuccessful": unsuccessful,
                "next_year_applicants_at_expected_point": next_applicants,
                "raw_next_over_unsuccessful_ratio": raw_ratio,
                "capped_retention_estimate": capped_retention,
                "next_year_mixed_cutoff_point": next_mixed_cutoff,
                "next_year_cutoff_structure": next_cutoff_structure,
            }
        )
    return rows


def summarize(rows: list[Mapping[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(clean(row.get(field)) for field in fields)].append(row)
    output = []
    for key, values in sorted(grouped.items()):
        matched = [row for row in values if parse_float(row.get("next_year_applicants_at_expected_point")) is not None]
        prior_unsuccessful = sum(parse_float(row.get("prior_mixed_cutoff_unsuccessful")) or 0.0 for row in matched)
        next_applicants = sum(parse_float(row.get("next_year_applicants_at_expected_point")) or 0.0 for row in matched)
        capped_weighted = (
            sum((parse_float(row.get("capped_retention_estimate")) or 0.0) * (parse_float(row.get("prior_mixed_cutoff_unsuccessful")) or 0.0) for row in matched)
            / prior_unsuccessful
            if prior_unsuccessful > 0
            else ""
        )
        item = {field: key[index] for index, field in enumerate(fields)}
        item.update(
            {
                "rollover_rows": len(values),
                "matched_next_point_rows": len(matched),
                "prior_unsuccessful_total": prior_unsuccessful if matched else "",
                "next_applicants_total": next_applicants if matched else "",
                "aggregate_next_over_unsuccessful_ratio": next_applicants / prior_unsuccessful if prior_unsuccessful > 0 else "",
                "weighted_capped_retention": capped_weighted,
                "no_next_year_match_rows": sum(1 for row in values if row.get("same_hunt_match_type") == "NO_NEXT_YEAR_HUNT_MATCH"),
                "descriptive_change_review_rows": sum(1 for row in values if "REVIEW" in clean(row.get("same_hunt_match_type"))),
            }
        )
        output.append(item)
    return output


CUTOFF_FIELDS = [
    "year",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "residency",
    "draw_pool",
    "boundary_id",
    "season",
    "draw_design",
    "top_applicant_point",
    "guaranteed_stack_points",
    "guaranteed_stack_count",
    "lowest_guaranteed_stack_point",
    "mixed_cutoff_point",
    "mixed_cutoff_next_year_point",
    "cutoff_structure",
    "point_rows",
    "total_applicants",
    "mixed_cutoff_applicants",
    "mixed_cutoff_drawn",
    "mixed_cutoff_unsuccessful",
    "mixed_cutoff_p_draw",
]

ROLLOVER_FIELDS = [
    "prior_year",
    "next_year",
    "hunt_code",
    "hunt_name",
    "next_hunt_name",
    "species",
    "sex_type",
    "weapon",
    "residency",
    "draw_pool",
    "boundary_id",
    "next_boundary_id",
    "same_hunt_match_type",
    "prior_cutoff_structure",
    "prior_top_applicant_point",
    "prior_guaranteed_stack_points",
    "prior_mixed_cutoff_point",
    "expected_next_point",
    "prior_mixed_cutoff_applicants",
    "prior_mixed_cutoff_drawn",
    "prior_mixed_cutoff_unsuccessful",
    "next_year_applicants_at_expected_point",
    "raw_next_over_unsuccessful_ratio",
    "capped_retention_estimate",
    "next_year_mixed_cutoff_point",
    "next_year_cutoff_structure",
]

SUMMARY_FIELDS = [
    "prior_year",
    "next_year",
    "prior_cutoff_structure",
    "same_hunt_match_type",
    "rollover_rows",
    "matched_next_point_rows",
    "prior_unsuccessful_total",
    "next_applicants_total",
    "aggregate_next_over_unsuccessful_ratio",
    "weighted_capped_retention",
    "no_next_year_match_rows",
    "descriptive_change_review_rows",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    year_rows: dict[int, list[dict[str, Any]]] = {}
    audits = []
    cutoffs_by_year: dict[int, list[dict[str, Any]]] = {}
    point_lookup_by_year: dict[int, dict[tuple[str, str, str, str, str, str, str], dict[int, dict[str, Any]]]] = {}
    for year in range(args.start_year, args.end_year + 1):
        rows, audit = load_year(year)
        year_rows[year] = rows
        audits.append(audit)
        cutoffs, point_lookup = group_year(rows, year)
        cutoffs_by_year[year] = cutoffs
        point_lookup_by_year[year] = point_lookup
        write_csv(args.output_dir / f"max_weighted_mixed_cutoffs_{year}.csv", CUTOFF_FIELDS, cutoffs)

    all_rollover_rows: list[dict[str, Any]] = []
    for prior_year in range(args.start_year, args.end_year):
        next_year = prior_year + 1
        rows = build_rollover_rows(
            prior_year,
            next_year,
            cutoffs_by_year[prior_year],
            cutoffs_by_year[next_year],
            point_lookup_by_year[next_year],
        )
        all_rollover_rows.extend(rows)
        write_csv(args.output_dir / f"mixed_cutoff_rollover_{prior_year}_to_{next_year}.csv", ROLLOVER_FIELDS, rows)

    write_csv(args.output_dir / "mixed_cutoff_rollover_all_years.csv", ROLLOVER_FIELDS, all_rollover_rows)
    summary = summarize(all_rollover_rows, ["prior_year", "next_year", "prior_cutoff_structure", "same_hunt_match_type"])
    write_csv(args.output_dir / "mixed_cutoff_rollover_summary_by_year.csv", SUMMARY_FIELDS, summary)
    write_csv(
        args.output_dir / "mixed_cutoff_rollover_summary_cumulative.csv",
        [
            "prior_cutoff_structure",
            "same_hunt_match_type",
            "rollover_rows",
            "matched_next_point_rows",
            "prior_unsuccessful_total",
            "next_applicants_total",
            "aggregate_next_over_unsuccessful_ratio",
            "weighted_capped_retention",
            "no_next_year_match_rows",
            "descriptive_change_review_rows",
        ],
        summarize(all_rollover_rows, ["prior_cutoff_structure", "same_hunt_match_type"]),
    )
    write_json(
        args.output_dir / "manifest.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": TARGET_DRAW_DESIGN,
            "identity_rule": "hunt_code first, hunt_name second, then species, sex_type, weapon, residency, draw_pool; boundary_id and season are confidence fields only",
            "start_year": args.start_year,
            "end_year": args.end_year,
            "audits": audits,
            "output_dir": rel(args.output_dir),
            "rollover_rows": len(all_rollover_rows),
        },
    )
    print(f"Wrote {rel(args.output_dir)}")
    print(f"Rollover rows: {len(all_rollover_rows)}")


if __name__ == "__main__":
    main()
