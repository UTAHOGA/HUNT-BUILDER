#!/usr/bin/env python3
"""Compare the current 2026 crosswalk rollup against DATABASE.csv."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
ROLLUP = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_code_resolution_rollup.csv"
DISCREPANCIES = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_permit_or_boundary_discrepancies.csv"
OUT_CSV = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_database_status_check.csv"
OUT_JSON = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_database_status_check_summary.json"

OUTPUT_COLUMNS = [
    "hunt_code",
    "rollup_bucket",
    "rollup_boundary_confirmed",
    "rollup_permit_conflict",
    "database_presence",
    "database_boundary_id",
    "database_family_match",
    "database_permit_allotment_res",
    "database_permit_allotment_nr",
    "database_permit_allotment_total",
    "database_permit_allotment_source",
    "database_permit_allotment_status",
    "database_has_current_allotment_total",
    "database_total_matches_recommended_total",
    "recommended_total",
    "database_total",
    "discrepancy_status",
    "next_status",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def same_text(a: str, b: str) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def family_match(rollup: dict[str, str], db: dict[str, str]) -> str:
    if not db:
        return "NO_DATABASE_ROW"
    fields = ("hunt_name", "species", "sex_type", "weapon", "hunt_type")
    mismatches = [field for field in fields if rollup.get(field) and db.get(field) and not same_text(rollup[field], db[field])]
    return "YES" if not mismatches else "NO:" + "|".join(mismatches)


def next_status(rollup: dict[str, str], db: dict[str, str], discrepancy: dict[str, str]) -> str:
    if not db:
        return "DATABASE_ROW_MISSING"
    if rollup.get("recommended_resolution_bucket") == "MANUAL_REMAP_REQUIRED":
        return "MANUAL_REMAP_REQUIRED"
    if discrepancy:
        return "PERMIT_CONFLICT_REVIEW_REQUIRED"
    if rollup.get("recommended_resolution_bucket") == "BOUNDARY_CONFIRMED_IDENTITY_READY":
        return "DATABASE_IDENTITY_READY"
    return "REVIEW_REQUIRED"


def main() -> int:
    db_rows = {row["hunt_code"]: row for row in read_csv(DATABASE) if row.get("hunt_code")}
    rollup_rows = read_csv(ROLLUP)
    discrepancy_rows = {row["hunt_code"]: row for row in read_csv(DISCREPANCIES) if row.get("hunt_code")}

    output_rows: list[dict[str, str]] = []
    for row in rollup_rows:
        code = row["hunt_code"]
        db = db_rows.get(code, {})
        discrepancy = discrepancy_rows.get(code, {})
        db_total = db.get("permit_allotment_2026_total", "")
        recommended_total = discrepancy.get("recommended_total", "")
        has_total = "true" if db_total else "false"
        total_match = ""
        if recommended_total or db_total:
            total_match = "true" if recommended_total == db_total else "false"

        notes = []
        if not db:
            notes.append("Code is absent from DATABASE.csv.")
        if row.get("recommended_resolution_bucket") == "MANUAL_REMAP_REQUIRED":
            notes.append("Crosswalk rollup still requires manual remap.")
        if discrepancy:
            notes.append("Current permit evidence has conflicting totals.")
        if db and not db_total:
            notes.append("DATABASE row exists but current allotment total is blank.")

        output_rows.append(
            {
                "hunt_code": code,
                "rollup_bucket": row.get("recommended_resolution_bucket", ""),
                "rollup_boundary_confirmed": row.get("boundary_confirmed", ""),
                "rollup_permit_conflict": row.get("permit_conflict", ""),
                "database_presence": "PRESENT" if db else "MISSING",
                "database_boundary_id": db.get("boundary_id", ""),
                "database_family_match": family_match(row, db),
                "database_permit_allotment_res": db.get("permit_allotment_2026_res", ""),
                "database_permit_allotment_nr": db.get("permit_allotment_2026_nr", ""),
                "database_permit_allotment_total": db_total,
                "database_permit_allotment_source": db.get("permit_allotment_2026_source", ""),
                "database_permit_allotment_status": db.get("permit_allotment_2026_status", ""),
                "database_has_current_allotment_total": has_total,
                "database_total_matches_recommended_total": total_match,
                "recommended_total": recommended_total,
                "database_total": discrepancy.get("database_total", db_total),
                "discrepancy_status": discrepancy.get("discrepancy_status", ""),
                "next_status": next_status(row, db, discrepancy),
                "notes": " ".join(notes),
            }
        )

    write_csv(OUT_CSV, output_rows)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_csv": DATABASE.relative_to(ROOT).as_posix(),
        "rollup_csv": ROLLUP.relative_to(ROOT).as_posix(),
        "row_counts": {
            "database_rows": len(db_rows),
            "rollup_rows": len(rollup_rows),
            "status_check_rows": len(output_rows),
            "database_present": sum(1 for row in output_rows if row["database_presence"] == "PRESENT"),
            "database_missing": sum(1 for row in output_rows if row["database_presence"] == "MISSING"),
            "database_has_current_allotment_total": sum(
                1 for row in output_rows if row["database_has_current_allotment_total"] == "true"
            ),
            "database_blank_current_allotment_total": sum(
                1 for row in output_rows if row["database_has_current_allotment_total"] == "false"
            ),
        },
        "next_status_counts": dict(Counter(row["next_status"] for row in output_rows)),
        "rollup_bucket_counts": dict(Counter(row["rollup_bucket"] for row in output_rows)),
        "family_match_counts": dict(Counter(row["database_family_match"].split(":")[0] for row in output_rows)),
        "database_total_matches_recommended_total_counts": dict(
            Counter(row["database_total_matches_recommended_total"] or "<not_compared>" for row in output_rows)
        ),
        "manual_remap_codes": [
            row["hunt_code"] for row in output_rows if row["next_status"] == "MANUAL_REMAP_REQUIRED"
        ],
        "permit_conflict_codes": [
            row["hunt_code"] for row in output_rows if row["next_status"] == "PERMIT_CONFLICT_REVIEW_REQUIRED"
        ],
        "outputs": {
            "csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "summary_json": OUT_JSON.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No DATABASE.csv values were modified.",
            "This check uses permit_allotment_2026_* as the current DATABASE numeric field family.",
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
