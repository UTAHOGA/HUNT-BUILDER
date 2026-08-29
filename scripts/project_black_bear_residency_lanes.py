#!/usr/bin/env python3
"""Create an audit-only truth projection with official Bear residency lanes.

Legacy canonical/long Bear rows retain a combined ladder.  The retained DWR
PDF extraction provides the published resident and nonresident ladders.  This
tool substitutes those lanes only for the matching historic Bear point rows;
it never estimates a split and never modifies its input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


# The legacy canonical keeps some older Black Bear rows under a generic or
# reference-only design label even though the retained DWR PDF page identifies
# the actual program. These fields preserve that page-level identity only on
# this audit projection; they do not alter canonical source truth.
HISTORICAL_BEAR_IDENTITY_FIELDS = [
    "bear_source_classification",
    "bear_source_identity_source",
    "bear_source_identity_file",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def integer(value: object) -> int:
    try:
        return int(float(clean(value).replace(",", "")))
    except ValueError:
        return 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def actual_year(row: dict[str, str]) -> int:
    return integer(row.get("actual_draw_year") or row.get("year"))


def is_bear_point(row: dict[str, str], years: set[int]) -> bool:
    return (
        actual_year(row) in years
        and clean(row.get("hunt_code")).upper().startswith("BR")
        and "POINT" in clean(row.get("record_type") or row.get("row_type")).upper()
        and clean(row.get("points")).isdigit()
    )


def is_bear_hunt_total(row: dict[str, str], years: set[int], codes: set[str]) -> bool:
    return (
        actual_year(row) in years
        and clean(row.get("hunt_code")).upper() in codes
        and "TOTAL" in clean(row.get("record_type") or row.get("row_type")).upper()
    )


def lane_probability(apps: int, permits: int) -> str:
    if apps <= 0:
        return ""
    return f"{min(1.0, permits / apps):.10f}".rstrip("0").rstrip(".")


def project(
    rows: list[dict[str, str]],
    lane_rows: list[dict[str, str]],
    through_year: int | None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    # A source-side blind fold must not merely ignore later Bear lanes; it must
    # not carry later official rows in the file passed to the engine at all.
    # Target-side callers pass their one frozen target canonical instead.
    source_rows = [
        row
        for row in rows
        if through_year is None or actual_year(row) == 0 or actual_year(row) <= through_year
    ]
    input_years = {actual_year(row) for row in source_rows if actual_year(row) > 0}
    lanes: dict[tuple[int, str, int], list[dict[str, str]]] = defaultdict(list)
    for lane in lane_rows:
        year = integer(lane.get("reported_draw_year"))
        if (through_year is not None and year > through_year) or year not in input_years:
            continue
        code, points = clean(lane.get("hunt_code")).upper(), integer(lane.get("points"))
        if code and clean(lane.get("residency")) in {"Resident", "Nonresident"}:
            lanes[(year, code, points)].append(lane)
    if any(len(value) != 2 for value in lanes.values()):
        raise RuntimeError("Each official Bear year/code/point identity must publish exactly two residency lanes.")

    years = {year for year, _, _ in lanes}
    codes = {code for _, code, _ in lanes}
    parents = {
        (actual_year(row), clean(row.get("hunt_code")).upper(), integer(row.get("points"))): row
        for row in source_rows
        if is_bear_point(row, years)
    }
    if set(lanes) != set(parents):
        raise RuntimeError(
            f"Official Bear lane identity differs from input point rows: "
            f"missing_parent={len(set(lanes) - set(parents))}, missing_lane={len(set(parents) - set(lanes))}"
        )

    output = [row for row in source_rows if not is_bear_point(row, years) and not is_bear_hunt_total(row, years, codes)]
    for key in sorted(lanes):
        parent = parents[key]
        for lane in sorted(lanes[key], key=lambda row: clean(row["residency"])):
            item = dict(parent)
            apps = integer(lane.get("eligible_applicants"))
            bonus = integer(lane.get("bonus_permits"))
            regular = integer(lane.get("regular_permits"))
            permits = integer(lane.get("total_permits"))
            probability = lane_probability(apps, permits)
            item.update(
                {
                    "residency": clean(lane["residency"]),
                    "metric_scope": clean(lane["residency"]).lower(),
                    "eligible_applicants": str(apps),
                    "bonus_permits": str(bonus),
                    "regular_permits": str(regular),
                    "total_permits": str(permits),
                    "successful_applicants": str(permits),
                    "unsuccessful_applicants": str(max(0, apps - permits)),
                    "p_draw": probability,
                    "p_draw_percent": "" if not probability else f"{float(probability) * 100:.8f}".rstrip("0").rstrip("."),
                    "source_file": clean(lane["source_file"]),
                    "source_path": clean(lane["source_file"]),
                    "hunt_name": clean(lane["hunt_name"]),
                    "pdf_page": clean(lane["page_number"]),
                    "official_page": clean(lane["page_number"]),
                    "qa_status": "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED",
                    "notes": "Read-only audit projection from retained official Black Bear PDF residency ladder.",
                    "bear_source_classification": clean(lane["source_classification"]),
                    "bear_source_identity_source": "RETAINED_OFFICIAL_BLACK_BEAR_PDF",
                    "bear_source_identity_file": clean(lane["source_file"]),
                }
            )
            output.append(item)
    output.sort(key=lambda row: (actual_year(row), clean(row.get("hunt_code")), integer(row.get("points")), clean(row.get("residency"))))
    return output, {
        "official_lane_point_keys": len(lanes),
        "official_lane_rows": sum(len(value) for value in lanes.values()),
        "replaced_combined_bear_point_rows": len(parents),
        "removed_combined_bear_hunt_totals": sum(1 for row in source_rows if is_bear_hunt_total(row, years, codes)),
        "later_rows_excluded": len(rows) - len(source_rows),
        "projected_years": sorted(years),
        "projected_codes": len(codes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--official-lanes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--through-year", type=int)
    args = parser.parse_args()
    fields, rows = read_csv(args.input)
    _, lane_rows = read_csv(args.official_lanes)
    projected, counts = project(rows, lane_rows, args.through_year)
    output_fields = [*fields]
    for field in HISTORICAL_BEAR_IDENTITY_FIELDS:
        if field not in output_fields:
            output_fields.append(field)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(projected)
    manifest = {
        "purpose": "audit_only_official_black_bear_residency_lane_projection",
        "input": str(args.input).replace("\\", "/"),
        "input_sha256": sha256(args.input),
        "official_lanes": str(args.official_lanes).replace("\\", "/"),
        "official_lanes_sha256": sha256(args.official_lanes),
        "through_year": args.through_year,
        "output": str(args.output).replace("\\", "/"),
        "output_sha256": sha256(args.output),
        "input_rows": len(rows),
        "output_rows": len(projected),
        **counts,
        "status": "READ_ONLY_OFFICIAL_LANE_PROJECTION_READY",
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
