#!/usr/bin/env python3
"""Rebuild yearly canonical draw-result files into official DWR table shape.

The current canonical files contain many parser-normalized residency-split rows:
one Resident row and one Nonresident row for the same DWR table point level.
DWR's published table shape is one point row with resident columns on the left
and nonresident columns on the right. This script restores that durable truth
shape while preserving source metadata and writing an audit for every year.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild"
BACKUP_DIR = AUDIT_DIR / "backups"

METRIC_COLUMNS = {
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
}
DROP_COLUMNS = {
    "residency",
    *METRIC_COLUMNS,
}
SOURCE_COLUMNS = [
    "source_scope",
    "source_namespace",
    "draw_source_namespace",
    "source_file",
    "pdf_page",
    "page_kind",
    "algorithm_status",
    "source_dataset",
    "extraction_status",
    "parse_method",
    "qa_status",
    "notes",
]
IDENTITY_COLUMNS = [
    "actual_draw_year",
    "model_target_year",
    "boundary_id",
    "hunt_code",
    "hunt_name",
    "sex_type",
    "species",
    "hunt_type",
    "weapon",
    "season",
    "draw_design",
    "points",
    "record_type",
]
SIDE_METRIC_COLUMNS = [
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "resident_success_ratio",
    "resident_p_draw",
    "resident_p_draw_percent",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "nonresident_success_ratio",
    "nonresident_p_draw",
    "nonresident_p_draw_percent",
    "total_eligible_applicants",
    "total_bonus_permits",
    "total_regular_permits",
    "total_permits",
    "total_success_ratio",
    "total_p_draw",
    "total_p_draw_percent",
]
AUDIT_COLUMNS = [
    "source_residencies",
    "source_row_count",
    "collapse_conflict_count",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def available_years() -> list[int]:
    years: list[int] = []
    for path in CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv"):
        parts = path.name.split("_")
        if len(parts) > 2 and parts[2].isdigit():
            years.append(int(parts[2]))
    return sorted(set(years))


def normalize_residency(value: str) -> str:
    text = clean(value).lower().replace("-", " ")
    if text in {"resident", "res"}:
        return "resident"
    if text in {"nonresident", "non resident", "nonres", "nr"}:
        return "nonresident"
    return "total"


def normalize_record_type(value: str) -> str:
    text = clean(value)
    lower = text.lower()
    if lower in {"point_row", "point", "point_level", "point_level_draw_result"}:
        return "point_level_draw_result"
    if lower in {"total", "total_row", "hunt_total", "hunt_total_draw_result"}:
        return "hunt_total_draw_result"
    if lower in {"sportsman_total", "sportsman_total_draw_result"}:
        return "sportsman_total"
    if lower in {"availability_only", "availability"}:
        return "availability_only"
    return text


def numeric(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def numeric_or_blank(value: object) -> object:
    number = numeric(value)
    if number is None:
        return clean(value)
    return int(number) if number.is_integer() else number


def sum_numeric(values: Iterable[object]) -> object:
    total = 0.0
    found = False
    for value in values:
        number = numeric(value)
        if number is None:
            continue
        total += number
        found = True
    if not found:
        return ""
    return int(total) if total.is_integer() else total


def first_nonblank(values: Iterable[object]) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def merge_text_values(values: Iterable[object]) -> str:
    seen: list[str] = []
    for value in values:
        text = clean(value)
        if text and text not in seen:
            seen.append(text)
    return " | ".join(seen)


def key_for(row: dict[str, str]) -> tuple[str, ...]:
    record_type = normalize_record_type(row.get("record_type", ""))
    return (
        clean(row.get("actual_draw_year")),
        clean(row.get("model_target_year")),
        clean(row.get("source_scope")),
        clean(row.get("source_namespace")),
        clean(row.get("draw_source_namespace")),
        clean(row.get("source_file")),
        clean(row.get("pdf_page")),
        clean(row.get("page_kind")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("hunt_name")),
        clean(row.get("species")),
        clean(row.get("sex_type")),
        clean(row.get("draw_design")),
        clean(row.get("weapon")),
        clean(row.get("hunt_type")),
        clean(row.get("season")),
        clean(row.get("points")),
        record_type,
        clean(row.get("boundary_id")),
        clean(row.get("algorithm_status")),
        clean(row.get("source_dataset")),
        clean(row.get("extraction_status")),
        clean(row.get("parse_method")),
        clean(row.get("qa_status")),
    )


def permit_columns(header: list[str]) -> list[str]:
    return [column for column in header if column.startswith("permits_") and column.rsplit("_", 1)[-1] in {"res", "nr", "total"}]


def extra_columns(header: list[str]) -> list[str]:
    used = set(IDENTITY_COLUMNS) | set(SIDE_METRIC_COLUMNS) | set(SOURCE_COLUMNS) | set(AUDIT_COLUMNS)
    used |= set(DROP_COLUMNS)
    used |= set(permit_columns(header))
    return [column for column in header if column not in used]


def output_header(input_header: list[str]) -> list[str]:
    header = [
        *IDENTITY_COLUMNS,
        *SIDE_METRIC_COLUMNS,
        *permit_columns(input_header),
        *SOURCE_COLUMNS,
        *AUDIT_COLUMNS,
        *extra_columns(input_header),
    ]
    seen: set[str] = set()
    deduped: list[str] = []
    for column in header:
        if column not in seen:
            deduped.append(column)
            seen.add(column)
    return deduped


def is_already_dwr_table_shape(header: list[str]) -> bool:
    return (
        "residency" not in header
        and "resident_eligible_applicants" in header
        and "nonresident_eligible_applicants" in header
    )


def choose_side_value(
    rows: list[dict[str, str]],
    column: str,
    year_conflicts: list[dict[str, str]],
    context: dict[str, str],
    side: str,
) -> str:
    values = [clean(row.get(column)) for row in rows if clean(row.get(column))]
    if not values:
        return ""
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    if len(unique) > 1:
        year_conflicts.append(
            {
                **context,
                "side": side,
                "column": column,
                "values": " | ".join(unique),
            }
        )
    return unique[0]


def collapse_group(
    group_rows: list[dict[str, str]],
    input_header: list[str],
    conflicts: list[dict[str, str]],
) -> dict[str, object]:
    first = group_rows[0]
    resident_rows = [row for row in group_rows if normalize_residency(row.get("residency", "")) == "resident"]
    nonresident_rows = [row for row in group_rows if normalize_residency(row.get("residency", "")) == "nonresident"]
    total_rows = [row for row in group_rows if normalize_residency(row.get("residency", "")) == "total"]
    context = {
        "actual_draw_year": clean(first.get("actual_draw_year")),
        "hunt_code": clean(first.get("hunt_code")).upper(),
        "points": clean(first.get("points")),
        "record_type": normalize_record_type(first.get("record_type", "")),
        "source_file": clean(first.get("source_file")),
        "pdf_page": clean(first.get("pdf_page")),
    }
    before_conflicts = len(conflicts)
    output: dict[str, object] = {}
    for column in IDENTITY_COLUMNS:
        if column == "record_type":
            output[column] = normalize_record_type(first.get(column, ""))
        elif column == "hunt_code":
            output[column] = clean(first.get(column)).upper()
        elif column in {"actual_draw_year", "model_target_year", "boundary_id", "points"}:
            output[column] = numeric_or_blank(first.get(column))
        else:
            output[column] = first_nonblank(row.get(column) for row in group_rows)

    for side, side_rows in [("resident", resident_rows), ("nonresident", nonresident_rows)]:
        for metric in METRIC_COLUMNS:
            output[f"{side}_{metric}"] = numeric_or_blank(
                choose_side_value(side_rows, metric, conflicts, context, side)
            )

    total_metric_sources = total_rows if total_rows else group_rows
    for metric in ["eligible_applicants", "bonus_permits", "regular_permits", "total_permits"]:
        explicit = first_nonblank(row.get(metric) for row in total_rows)
        if explicit:
            output[f"total_{metric}"] = numeric_or_blank(explicit)
        else:
            output[f"total_{metric}"] = sum_numeric(
                [
                    output.get(f"resident_{metric}", ""),
                    output.get(f"nonresident_{metric}", ""),
                ]
            )
    for metric in ["success_ratio", "p_draw", "p_draw_percent"]:
        output[f"total_{metric}"] = numeric_or_blank(first_nonblank(row.get(metric) for row in total_metric_sources))

    for column in permit_columns(input_header):
        output[column] = numeric_or_blank(first_nonblank(row.get(column) for row in group_rows))

    for column in SOURCE_COLUMNS:
        if column == "notes":
            output[column] = merge_text_values(row.get(column) for row in group_rows)
        else:
            output[column] = first_nonblank(row.get(column) for row in group_rows)

    residencies = sorted({normalize_residency(row.get("residency", "")) for row in group_rows})
    output["source_residencies"] = "; ".join(residencies)
    output["source_row_count"] = len(group_rows)
    for column in extra_columns(input_header):
        output[column] = numeric_or_blank(first_nonblank(row.get(column) for row in group_rows))

    output["collapse_conflict_count"] = len(conflicts) - before_conflicts
    return output


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, header: list[str], rows: Iterable[dict[str, object]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in header})
    tmp_path.replace(path)


def rebuild_year(year: int, *, write: bool) -> dict[str, object]:
    source_path = canonical_path(year)
    input_header, input_rows = read_rows(source_path)
    if is_already_dwr_table_shape(input_header):
        summary = {
            "year": year,
            "source_path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "write": False,
            "already_dwr_table_shape": True,
            "rows_before": len(input_rows),
            "rows_after": len(input_rows),
            "columns_before": len(input_header),
            "columns_after": len(input_header),
            "row_reduction": 0,
            "collapse_conflicts": 0,
            "backup_path": "",
        }
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        audit_prefix = AUDIT_DIR / f"{year}_for_{year + 1}"
        (audit_prefix.with_name(f"{audit_prefix.name}_summary.json")).write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary

    if "residency" not in input_header:
        raise ValueError(
            f"{source_path} is neither old split-row shape nor DWR table shape: missing residency column"
        )

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        grouped[key_for(row)].append(row)

    conflicts: list[dict[str, str]] = []
    collapsed_rows = [
        collapse_group(group, input_header, conflicts)
        for _, group in sorted(grouped.items(), key=lambda item: item[0])
    ]
    header = output_header(input_header)
    row_type_counts = Counter(clean(row.get("record_type")) or "(blank)" for row in collapsed_rows)
    source_residency_counts = Counter(clean(row.get("source_residencies")) or "(blank)" for row in collapsed_rows)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_prefix = AUDIT_DIR / f"{year}_for_{year + 1}"
    write_rows(audit_prefix.with_name(f"{audit_prefix.name}_collapse_conflicts.csv"), list(conflicts[0].keys()) if conflicts else ["actual_draw_year", "hunt_code", "points", "record_type", "source_file", "pdf_page", "side", "column", "values"], conflicts)

    if write:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = BACKUP_DIR / f"{source_path.stem}.before_dwr_table_shape_{timestamp}{source_path.suffix}"
        shutil.copy2(source_path, backup_path)
        write_rows(source_path, header, collapsed_rows)
    else:
        preview_path = audit_prefix.with_name(f"{audit_prefix.name}_DWR_TABLE_SHAPE_PREVIEW.csv")
        write_rows(preview_path, header, collapsed_rows)
        backup_path = ""

    summary = {
        "year": year,
        "source_path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "write": write,
        "rows_before": len(input_rows),
        "rows_after": len(collapsed_rows),
        "columns_before": len(input_header),
        "columns_after": len(header),
        "row_reduction": len(input_rows) - len(collapsed_rows),
        "collapse_conflicts": len(conflicts),
        "record_type_counts": dict(row_type_counts),
        "source_residency_counts": dict(source_residency_counts),
        "backup_path": str(backup_path.relative_to(ROOT)).replace("\\", "/") if backup_path else "",
    }
    (audit_prefix.with_name(f"{audit_prefix.name}_summary.json")).write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--write", action="store_true", help="Overwrite canonical files after creating backups.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = available_years() if args.all else (args.year or [2025])
    summaries = [rebuild_year(year, write=args.write) for year in years]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "manifest.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
