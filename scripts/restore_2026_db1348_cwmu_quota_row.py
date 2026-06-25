#!/usr/bin/env python3
"""Restore DB1348 as a 2026 CWMU permit-reference row.

DB1348 is present in DATABASE.csv and the reviewed CWMU workbook, but it can be
lost when scorable-only cleanup removes non-point-ladder rows. Keep it out of
the scorable point file and restore it only to permit-reference/canonical display truth.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = "DB1348"

DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
CANONICAL = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
PERMIT_REFERENCE = ROOT / "outputs/2026 permit reference rows.csv"
LIBRARY = ROOT / "processed_data/library/canonical_current_hunts_2026.csv"
SUMMARY = ROOT / "audits/2026_canonical_reconciliation/restore_2026_db1348_cwmu_permit_reference_row_summary.csv"


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in headers})
    tmp.replace(path)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def find_database_row() -> dict[str, str]:
    _, rows = read_rows(DATABASE)
    for row in rows:
        if clean(row.get("hunt_code")).upper() == CODE:
            return row
    raise SystemExit(f"{CODE} not found in {DATABASE}")


def permit_reference_row(headers: list[str], db: dict[str, str]) -> dict[str, str]:
    base = {field: "" for field in headers}
    values = {
        "actual_draw_year": "2026",
        "model_target_year": "2027",
        "source_scope": "DWR_HUNT_PLANNER_CWMU",
        "source_namespace": "2026_HUNT_PLANNER_PERMIT_REFERENCE",
        "draw_source_namespace": "DWR_HUNT_PLANNER_2026",
        "source_file": clean(db.get("permit_allotment_2026_source_file"))
        or "https://dwrapps.utah.gov/huntboundary/HaNumber?roles=&hn=DB1348",
        "page_kind": "PERMIT_REFERENCE_ROW",
        "hunt_code": CODE,
        "hunt_name": clean(db.get("hunt_name")) or "Kimberly CWMU",
        "species": clean(db.get("species")) or "Deer",
        "sex_type": clean(db.get("sex_type")) or "Buck",
        "draw_design": clean(db.get("hunt_class")) or "Max/Weighted Split",
        "weapon": clean(db.get("weapon")) or "Any Legal Weapon",
        "hunt_type": clean(db.get("hunt_type")) or "CWMU",
        "season": clean(db.get("season")) or "Contact CWMU Operator for 2026 season dates",
        "record_type": "hunt_planner_permit_reference",
        "boundary_id": clean(db.get("boundary_id")) or "922",
        "algorithm_status": "NON_SCORABLE_PERMIT_REFERENCE",
        "source_dataset": "DWR_HUNT_PLANNER_2026_CWMU_REFRESH_FROM_DATABASE",
        "extraction_status": "DATABASE_CWMU_RESTORED",
        "parse_method": "DB1348_RESTORED_FROM_DATABASE_AND_CWMU_WORKBOOK",
        "qa_status": "permit_number_only_not_draw_result",
        "notes": "2026 Hunt Planner CWMU buck deer permit-number reference row; not a draw-result point row.",
        "permits_2026_res": clean(db.get("permits_2026_res"))
        or clean(db.get("permit_allotment_2026_res"))
        or "1",
        "permits_2026_nr": clean(db.get("permits_2026_nr"))
        or clean(db.get("permit_allotment_2026_nr"))
        or "0",
        "permits_2026_total": clean(db.get("permits_2026_total"))
        or clean(db.get("permit_allotment_2026_total"))
        or "1",
    }
    for key, value in values.items():
        if key in base:
            base[key] = value
    return base


def ensure_permit_reference_row(path: Path, db: dict[str, str]) -> tuple[int, int]:
    headers, rows = read_rows(path)
    before = len(rows)
    replacement = permit_reference_row(headers, db)
    exists = False
    for row in rows:
        if clean(row.get("hunt_code")).upper() != CODE:
            continue
        exists = True
        row.update(replacement)
    if not exists:
        rows.append(replacement)
    write_rows(path, headers, rows)
    return before, len(rows)


def update_library(db: dict[str, str]) -> tuple[int, int]:
    headers, rows = read_rows(LIBRARY)
    touched = 0
    for row in rows:
        if clean(row.get("hunt_code")).upper() != CODE:
            continue
        for src, dest in (
            ("hunt_name", "hunt_name"),
            ("sex_type", "sex_type"),
            ("species", "species"),
            ("weapon", "weapon"),
            ("hunt_type", "hunt_type"),
            ("hunt_class", "hunt_class"),
            ("season", "season"),
            ("boundary_id", "boundary_id"),
            ("permits_2026_res", "permit_allotment_2026_res"),
            ("permits_2026_nr", "permit_allotment_2026_nr"),
            ("permits_2026_total", "permit_allotment_2026_total"),
        ):
            if src in row and clean(db.get(dest)):
                row[src] = clean(db.get(dest))
        touched += 1
    if touched:
        write_rows(LIBRARY, headers, rows)
    return len(rows), touched


def main() -> int:
    db = find_database_row()
    canonical_before, canonical_after = ensure_permit_reference_row(CANONICAL, db)
    permit_reference_before, permit_reference_after = ensure_permit_reference_row(PERMIT_REFERENCE, db)
    library_rows, library_touched = update_library(db)

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "hunt_code",
        "canonical_rows_before",
        "canonical_rows_after",
        "permit_reference_rows_before",
        "permit_reference_rows_after",
        "library_rows",
        "library_rows_touched",
        "boundary_id",
        "hunt_name",
        "permits_2026_res",
        "permits_2026_nr",
        "permits_2026_total",
    ]
    summary = {
        "hunt_code": CODE,
        "canonical_rows_before": str(canonical_before),
        "canonical_rows_after": str(canonical_after),
        "permit_reference_rows_before": str(permit_reference_before),
        "permit_reference_rows_after": str(permit_reference_after),
        "library_rows": str(library_rows),
        "library_rows_touched": str(library_touched),
        "boundary_id": clean(db.get("boundary_id")),
        "hunt_name": clean(db.get("hunt_name")),
        "permits_2026_res": clean(db.get("permits_2026_res")) or clean(db.get("permit_allotment_2026_res")),
        "permits_2026_nr": clean(db.get("permits_2026_nr")) or clean(db.get("permit_allotment_2026_nr")),
        "permits_2026_total": clean(db.get("permits_2026_total")) or clean(db.get("permit_allotment_2026_total")),
    }
    write_rows(SUMMARY, headers, [summary])
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
