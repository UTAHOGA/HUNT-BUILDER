#!/usr/bin/env python3
"""Export yearly scorable and non-scorable draw-result CSV slices.

The canonical yearly files remain source-preserving. These output CSVs are
engine/display-facing slices so prediction code can consume only real draw
result rows without mixing in quota, allocation, point-purchase, or reference
rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
OUTPUT_DIR = ROOT / "outputs"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"

DEFAULT_YEARS = range(2019, 2027)

SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "point_level",
    "sportsman_total",
    "sportsman_total_draw_result",
    "sportsman_random_total",
}

NON_SCORABLE_RECORD_TYPES = {
    "hunt_planner_permit_reference",
    "hunt_planner_permit_quota",
    "quota",
    "quota_row",
    "permit_quota",
    "hunt_total_draw_result",
    "total",
    "total_row",
    "supplemental_permit_total_row",
    "availability_only",
    "conservation_auction_allocation",
    "allocation_only",
    "reference_only",
    "point_purchase_reference",
    "cwmu_contact_operator_reference_only",
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def lower_clean(value: Any) -> str:
    return clean(value).lower()


def system_clean(value: Any) -> str:
    return clean(value).upper().replace(" ", "_").replace("/", "_").replace("-", "_")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def is_conservation_or_reference(row: dict[str, str]) -> bool:
    hunt_type = lower_clean(row.get("hunt_type"))
    draw_design = lower_clean(row.get("draw_design") or row.get("draw_pool") or row.get("hunt_class"))
    draw_system = system_clean(row.get("draw_system_type") or row.get("draw_design"))
    source_scope = lower_clean(row.get("source_scope"))
    text = " ".join(
        lower_clean(row.get(field))
        for field in (
            "record_type",
            "row_type",
            "hunt_type",
            "draw_design",
            "draw_pool",
            "hunt_class",
            "source_scope",
            "source_file",
            "notes",
            "qa_status",
            "algorithm_status",
        )
    )
    return (
        hunt_type == "conservation"
        or draw_design in {"organizations", "organization"}
        or draw_system in {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL", "GUARANTEED_LIFETIME_PERMIT"}
        or "conservation_auction_allocation" in text
        or "allocation/reference" in text
        or "allocation_only" in text
        or "reference_only" in text
        or "point_purchase" in text
        or "point-only" in text
        or "point only" in text
        or "conservation" in source_scope
    )


def is_sportsman_total(row: dict[str, str]) -> bool:
    kind = lower_clean(row.get("record_type") or row.get("row_type") or row.get("record_kind"))
    if kind in {"sportsman_total", "sportsman_total_draw_result", "sportsman_random_total"}:
        return True
    if kind != "hunt_total_draw_result":
        return False

    text = " ".join(
        lower_clean(row.get(field))
        for field in (
            "hunt_type",
            "draw_design",
            "hunt_class",
            "hunt_draw_class",
            "draw_source_namespace",
            "source_scope",
            "source_file",
            "hunt_name",
        )
    )
    return "sportsman" in text


def is_scorable(row: dict[str, str]) -> bool:
    if is_conservation_or_reference(row):
        return False

    kind = lower_clean(row.get("record_type") or row.get("row_type") or row.get("record_kind"))
    if is_sportsman_total(row):
        return True
    if kind in NON_SCORABLE_RECORD_TYPES:
        return False
    if kind in SCORABLE_RECORD_TYPES:
        return True

    # Last-resort guard for older rows: a real ladder row has code, point level,
    # residency, applicants, and permit fields. Quota/reference rows do not.
    return bool(
        clean(row.get("hunt_code"))
        and clean(row.get("points")) != ""
        and clean(row.get("residency"))
        and clean(row.get("eligible_applicants"))
        and clean(row.get("total_permits"))
    )


def normalize_scorable_output_row(row: dict[str, str], fieldnames: list[str]) -> dict[str, str]:
    output = dict(row)
    if is_sportsman_total(output):
        if "record_type" in fieldnames:
            output["record_type"] = "sportsman_total"
        if "row_type" in fieldnames:
            output["row_type"] = "sportsman_total"
    return output


def count_blank(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if clean(row.get(field)) == "")


def count_blank_any(rows: list[dict[str, str]], fields: tuple[str, ...]) -> int:
    return sum(1 for row in rows if all(clean(row.get(field)) == "" for field in fields))


def first_nonblank(row: dict[str, str], *fields: str) -> str:
    for field in fields:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def count_zero_applicants(rows: list[dict[str, str]]) -> int:
    count = 0
    for row in rows:
        text = first_nonblank(
            row,
            "eligible_applicants",
            "total_eligible_applicants",
            "resident_eligible_applicants",
            "nonresident_eligible_applicants",
        ).replace(",", "")
        try:
            if int(float(text)) == 0:
                count += 1
        except ValueError:
            pass
    return count


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(clean(row.get(field)) or "(blank)" for row in rows).most_common())


def existing_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def split_year(year: int, write: bool, preserve_existing: bool) -> dict[str, Any]:
    source = canonical_path(year)
    fieldnames, rows = read_csv(source)

    scorable_rows: list[dict[str, str]] = []
    reference_rows: list[dict[str, str]] = []
    permit_reference_rows: list[dict[str, str]] = []
    normalized_sportsman_rows = 0

    for row in rows:
        kind = lower_clean(row.get("record_type") or row.get("row_type") or row.get("record_kind"))
        if kind in {"hunt_planner_permit_reference", "hunt_planner_permit_quota"}:
            permit_reference_rows.append(row)

        if is_scorable(row):
            normalized = normalize_scorable_output_row(row, fieldnames)
            if normalized.get("record_type") != row.get("record_type") or normalized.get("row_type") != row.get("row_type"):
                normalized_sportsman_rows += 1
            scorable_rows.append(normalized)
        else:
            reference_rows.append(row)

    permit_res = f"permits_{year}_res"
    permit_nr = f"permits_{year}_nr"
    permit_total = f"permits_{year}_total"
    p_columns = [column for column in fieldnames if column in {"p_draw", "p_draw_percent"} or column.endswith("_p_draw") or column.endswith("_p_draw_percent")]
    applicant_fields = (
        "eligible_applicants",
        "total_eligible_applicants",
        "resident_eligible_applicants",
        "nonresident_eligible_applicants",
    )

    outputs = {
        "scorable": OUTPUT_DIR / f"{year} scorable draw results.csv",
        "reference": OUTPUT_DIR / f"{year} non-scorable reference rows.csv",
        "permit_reference": OUTPUT_DIR / f"{year} permit reference rows.csv",
    }
    rows_by_output = {
        "scorable": scorable_rows,
        "reference": reference_rows,
        "permit_reference": permit_reference_rows,
    }
    preserved_outputs: dict[str, str] = {}
    if write:
        for output_kind, output_path in outputs.items():
            if preserve_existing and output_path.exists() and output_kind in {"scorable", "permit_reference"}:
                preserved_outputs[output_kind] = str(output_path.relative_to(ROOT)).replace("\\", "/")
                continue
            write_csv(output_path, fieldnames, rows_by_output[output_kind])

    return {
        "year": year,
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "source_rows": len(rows),
        "source_columns": len(fieldnames),
        "record_type_counts": count_by(rows, "record_type"),
        "scorable_rows": len(scorable_rows),
        "reference_rows": len(reference_rows),
        "permit_reference_rows": len(permit_reference_rows),
        "normalized_legacy_sportsman_rows": normalized_sportsman_rows,
        "unique_hunt_codes_scorable": len({clean(row.get("hunt_code")).upper() for row in scorable_rows if clean(row.get("hunt_code"))}),
        "zero_applicant_scorable_rows": count_zero_applicants(scorable_rows),
        "blank_scorable_fields": {
            "hunt_code": count_blank(scorable_rows, "hunt_code"),
            "residency_row_label": count_blank(scorable_rows, "residency"),
            "points": count_blank(scorable_rows, "points"),
            "eligible_applicants_any": count_blank_any(scorable_rows, applicant_fields),
            "total_eligible_applicants": count_blank(scorable_rows, "total_eligible_applicants")
            if "total_eligible_applicants" in fieldnames
            else None,
            "total_permits": count_blank(scorable_rows, "total_permits"),
            permit_res: count_blank(scorable_rows, permit_res) if permit_res in fieldnames else None,
            permit_nr: count_blank(scorable_rows, permit_nr) if permit_nr in fieldnames else None,
            permit_total: count_blank(scorable_rows, permit_total) if permit_total in fieldnames else None,
            "p_draw": count_blank(scorable_rows, "p_draw") if "p_draw" in fieldnames else None,
            "p_draw_percent": count_blank(scorable_rows, "p_draw_percent") if "p_draw_percent" in fieldnames else None,
        },
        "p_columns_present": p_columns,
        "outputs": {name: str(path.relative_to(ROOT)).replace("\\", "/") for name, path in outputs.items()},
        "output_file_rows": {name: existing_row_count(path) for name, path in outputs.items()},
        "preserved_existing_outputs": preserved_outputs,
        "write": write,
    }


def write_reports(results: list[dict[str, Any]], write: bool) -> None:
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write": write,
        "rule": "Scorable outputs include point-level draw-result rows plus Sportsman total rows; permit-reference/allocation/reference rows are excluded.",
        "years": results,
    }
    report_path = OUTPUT_DIR / "yearly_scorable_split_report.json"
    audit_path = AUDIT_DIR / "yearly_scorable_split_audit.csv"

    if write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        audit_rows = []
        for item in results:
            for kind, output in item["outputs"].items():
                rows_key = {
                    "scorable": "scorable_rows",
                    "reference": "reference_rows",
                    "permit_reference": "permit_reference_rows",
                }[kind]
                audit_rows.append(
                    {
                        "year": item["year"],
                        "output_kind": kind,
                        "rows": item[rows_key],
                        "path": output,
                        "normalized_legacy_sportsman_rows": item["normalized_legacy_sportsman_rows"]
                        if kind == "scorable"
                        else "",
                        "zero_applicant_scorable_rows": item["zero_applicant_scorable_rows"] if kind == "scorable" else "",
                    }
                )
        write_csv(
            audit_path,
            [
                "year",
                "output_kind",
                "rows",
                "path",
                "normalized_legacy_sportsman_rows",
                "zero_applicant_scorable_rows",
            ],
            audit_rows,
        )
    print(json.dumps(report, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write output CSVs and reports.")
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Do not overwrite existing scorable/quota output CSVs. Reference outputs are still regenerated.",
    )
    parser.add_argument("--year", type=int, action="append", help="Year to export. Repeatable. Defaults to 2019-2026.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = sorted(set(args.year or DEFAULT_YEARS))
    results = [split_year(year, write=args.write, preserve_existing=args.preserve_existing) for year in years]
    write_reports(results, write=args.write)


if __name__ == "__main__":
    main()
