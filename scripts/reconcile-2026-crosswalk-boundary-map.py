#!/usr/bin/env python3
"""Create resolved/remainder buckets for the 2026 hunt-code boundary reconciliation."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
ROLLUP = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_code_resolution_rollup.csv"
STATUS = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_database_status_check.csv"
CANDIDATES = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/crosswalk_2026_additional_source_candidates.csv"
OUT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"

ALL_OUT = OUT_DIR / "current_2026_hunt_code_boundary_reconciliation.csv"
RESOLVED_OUT = OUT_DIR / "resolved_current_2026_boundary_identity_ready.csv"
CONFLICT_OUT = OUT_DIR / "remaining_current_2026_permit_conflicts_with_boundaries.csv"
RESOLVED_CONFLICT_OUT = OUT_DIR / "resolved_current_2026_permit_conflicts_database_matched.csv"
MANUAL_OUT = OUT_DIR / "remaining_current_2026_manual_remap_with_boundaries.csv"
SUMMARY_OUT = OUT_DIR / "current_2026_hunt_code_boundary_reconciliation_summary.json"

OUTPUT_COLUMNS = [
    "hunt_code",
    "boundary_id",
    "hunt_name_database",
    "species_database",
    "sex_type_database",
    "weapon_database",
    "hunt_type_database",
    "hunt_class_database",
    "rollup_bucket",
    "resolution_status",
    "database_family_match",
    "boundary_confirmed",
    "permit_conflict",
    "current_allotment_res",
    "current_allotment_nr",
    "current_allotment_total",
    "current_allotment_source",
    "current_allotment_status",
    "recommended_total_from_conflict_file",
    "database_total_from_conflict_file",
    "database_total_matches_recommended_total",
    "best_crosswalk_status",
    "best_confidence",
    "evidence_source_count",
    "evidence_sources",
    "confirmed_boundary_ids_from_evidence",
    "candidate_boundary_ids_from_evidence",
    "historical_hunt_codes_from_evidence",
    "regulation_present",
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


def unique_join(values: list[str]) -> str:
    return "|".join(sorted(dict.fromkeys(value for value in values if value)))


def resolution_status(status_row: dict[str, str]) -> str:
    next_status = status_row.get("next_status", "")
    if next_status == "DATABASE_IDENTITY_READY":
        return "RESOLVED_HUNT_CODE_BOUNDARY_IDENTITY"
    if next_status == "PERMIT_CONFLICT_REVIEW_REQUIRED":
        if status_row.get("database_total_matches_recommended_total") == "true":
            return "RESOLVED_PERMIT_CONFLICT_BY_DATABASE_TRUTH"
        return "REMAINS_PERMIT_CONFLICT_REVIEW"
    if next_status == "MANUAL_REMAP_REQUIRED":
        return "REMAINS_MANUAL_REMAP"
    return next_status or "REVIEW_REQUIRED"


def main() -> int:
    db_by_code = {row["hunt_code"]: row for row in read_csv(DATABASE) if row.get("hunt_code")}
    rollup_by_code = {row["hunt_code"]: row for row in read_csv(ROLLUP) if row.get("hunt_code")}
    status_rows = read_csv(STATUS)
    candidates_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(CANDIDATES):
        if row.get("current_hunt_code"):
            candidates_by_code[row["current_hunt_code"]].append(row)

    reconciled_rows: list[dict[str, str]] = []
    for status_row in status_rows:
        code = status_row["hunt_code"]
        db = db_by_code.get(code, {})
        rollup = rollup_by_code.get(code, {})
        candidates = candidates_by_code.get(code, [])
        confirmed_boundary_ids = [
            row.get("current_boundary_id", "")
            for row in candidates
            if row.get("boundary_match") == "YES"
        ]
        candidate_boundary_ids = [
            row.get("current_boundary_id", "")
            for row in candidates
            if row.get("current_boundary_id")
        ]
        historical_codes = [row.get("historical_hunt_code", "") for row in candidates if row.get("historical_hunt_code")]
        evidence_sources = unique_join([row.get("evidence_source", "") for row in candidates])

        notes = []
        if status_row.get("next_status") == "DATABASE_IDENTITY_READY":
            notes.append("Hunt-code identity and database boundary mapping are ready for downstream use.")
        if status_row.get("next_status") == "PERMIT_CONFLICT_REVIEW_REQUIRED":
            if status_row.get("database_total_matches_recommended_total") == "true":
                notes.append("Identity is current/active and DATABASE total matches the selected/recommended total.")
            else:
                notes.append("Identity is current/active but permit totals need source-precedence review.")
        if status_row.get("next_status") == "MANUAL_REMAP_REQUIRED":
            notes.append("Manual crosswalk/remap remains before this row should be treated as resolved.")
        if status_row.get("database_family_match", "").startswith("NO"):
            notes.append(f"Database display-family comparison flagged {status_row.get('database_family_match')}.")

        reconciled_rows.append(
            {
                "hunt_code": code,
                "boundary_id": db.get("boundary_id", status_row.get("database_boundary_id", "")),
                "hunt_name_database": db.get("hunt_name", rollup.get("hunt_name", "")),
                "species_database": db.get("species", rollup.get("species", "")),
                "sex_type_database": db.get("sex_type", rollup.get("sex_type", "")),
                "weapon_database": db.get("weapon", rollup.get("weapon", "")),
                "hunt_type_database": db.get("hunt_type", rollup.get("hunt_type", "")),
                "hunt_class_database": db.get("hunt_class", ""),
                "rollup_bucket": rollup.get("recommended_resolution_bucket", status_row.get("rollup_bucket", "")),
                "resolution_status": resolution_status(status_row),
                "database_family_match": status_row.get("database_family_match", ""),
                "boundary_confirmed": rollup.get("boundary_confirmed", status_row.get("rollup_boundary_confirmed", "")),
                "permit_conflict": rollup.get("permit_conflict", status_row.get("rollup_permit_conflict", "")),
                "current_allotment_res": db.get("permit_allotment_2026_res", ""),
                "current_allotment_nr": db.get("permit_allotment_2026_nr", ""),
                "current_allotment_total": db.get("permit_allotment_2026_total", ""),
                "current_allotment_source": db.get("permit_allotment_2026_source", ""),
                "current_allotment_status": db.get("permit_allotment_2026_status", ""),
                "recommended_total_from_conflict_file": status_row.get("recommended_total", ""),
                "database_total_from_conflict_file": status_row.get("database_total", ""),
                "database_total_matches_recommended_total": status_row.get("database_total_matches_recommended_total", ""),
                "best_crosswalk_status": rollup.get("best_crosswalk_status", ""),
                "best_confidence": rollup.get("best_confidence", ""),
                "evidence_source_count": rollup.get("evidence_source_count", ""),
                "evidence_sources": evidence_sources or rollup.get("evidence_sources", ""),
                "confirmed_boundary_ids_from_evidence": unique_join(confirmed_boundary_ids),
                "candidate_boundary_ids_from_evidence": unique_join(candidate_boundary_ids),
                "historical_hunt_codes_from_evidence": unique_join(historical_codes),
                "regulation_present": rollup.get("regulation_present", ""),
                "notes": " ".join(notes),
            }
        )

    resolved = [row for row in reconciled_rows if row["resolution_status"] == "RESOLVED_HUNT_CODE_BOUNDARY_IDENTITY"]
    resolved_conflicts = [
        row for row in reconciled_rows if row["resolution_status"] == "RESOLVED_PERMIT_CONFLICT_BY_DATABASE_TRUTH"
    ]
    conflicts = [row for row in reconciled_rows if row["resolution_status"] == "REMAINS_PERMIT_CONFLICT_REVIEW"]
    manual = [row for row in reconciled_rows if row["resolution_status"] == "REMAINS_MANUAL_REMAP"]

    write_csv(ALL_OUT, reconciled_rows)
    write_csv(RESOLVED_OUT, resolved)
    write_csv(RESOLVED_CONFLICT_OUT, resolved_conflicts)
    write_csv(CONFLICT_OUT, conflicts)
    write_csv(MANUAL_OUT, manual)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "database": DATABASE.relative_to(ROOT).as_posix(),
            "rollup": ROLLUP.relative_to(ROOT).as_posix(),
            "database_status": STATUS.relative_to(ROOT).as_posix(),
            "candidates": CANDIDATES.relative_to(ROOT).as_posix(),
        },
        "row_counts": {
            "all_reconciled_rows": len(reconciled_rows),
            "resolved_identity_rows": len(resolved),
            "resolved_permit_conflict_database_matched_rows": len(resolved_conflicts),
            "remaining_permit_conflict_rows": len(conflicts),
            "remaining_manual_remap_rows": len(manual),
        },
        "resolution_status_counts": dict(Counter(row["resolution_status"] for row in reconciled_rows)),
        "family_match_counts": dict(Counter(row["database_family_match"].split(":")[0] for row in reconciled_rows)),
        "current_allotment_total_blank_counts": {
            "resolved_identity_rows_blank_total": sum(1 for row in resolved if not row["current_allotment_total"]),
            "resolved_permit_conflict_database_matched_rows_blank_total": sum(
                1 for row in resolved_conflicts if not row["current_allotment_total"]
            ),
            "permit_conflict_rows_blank_total": sum(1 for row in conflicts if not row["current_allotment_total"]),
            "manual_rows_blank_total": sum(1 for row in manual if not row["current_allotment_total"]),
        },
        "manual_remap_codes": [row["hunt_code"] for row in manual],
        "permit_conflict_codes": [row["hunt_code"] for row in conflicts],
        "outputs": {
            "all_reconciliation_csv": ALL_OUT.relative_to(ROOT).as_posix(),
            "resolved_identity_csv": RESOLVED_OUT.relative_to(ROOT).as_posix(),
            "resolved_permit_conflicts_database_matched_csv": RESOLVED_CONFLICT_OUT.relative_to(ROOT).as_posix(),
            "remaining_permit_conflicts_csv": CONFLICT_OUT.relative_to(ROOT).as_posix(),
            "remaining_manual_remap_csv": MANUAL_OUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_OUT.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "No DATABASE.csv values were modified.",
            "Resolved identity rows mean hunt_code and boundary identity are reconciled; they do not imply permit totals were populated.",
        ],
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
