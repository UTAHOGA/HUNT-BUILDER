#!/usr/bin/env python3
"""Remove archived 2025 hunt EA1281 from the active 2026 data surfaces.

EA1281's Dec. 20, 2025-Jan. 11, 2026 season caused a stale HuntTableData
snapshot to be labeled as a 2026 hunt. DWR's current detail endpoint identifies
the hunt as HUNT_YEAR=2025 and STATUS=OFF, and the 2026 antlerless guidebook
does not list it. Historical 2025 draw truth is intentionally untouched.

The command previews by default. Pass ``--write`` to apply the two-row-surface
repair after all identity and historical-preservation checks pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
CURRENT_CANONICAL = (
    ROOT
    / "data_truth/draw_results_truth/normalized/canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
HISTORICAL_CANONICAL = (
    ROOT
    / "data_truth/draw_results_truth/normalized/canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
SUMMARY = (
    ROOT
    / "data_truth/crosswalk_truth/validation"
    / "ea1281_archived_2025_not_current_2026_summary.json"
)
AUDIT_DIR = ROOT / "audits/ea1281_archived_2025_not_current_2026"
HUNT_CODE = "EA1281"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    db_fields, db_rows = read_csv(DATABASE)
    canonical_fields, canonical_rows = read_csv(CURRENT_CANONICAL)
    _, historical_rows = read_csv(HISTORICAL_CANONICAL)
    db_matches = [row for row in db_rows if row.get("hunt_code") == HUNT_CODE]
    canonical_matches = [
        row for row in canonical_rows if row.get("hunt_code") == HUNT_CODE
    ]
    historical_matches = [
        row for row in historical_rows if row.get("hunt_code") == HUNT_CODE
    ]

    if len(db_matches) not in {0, 1}:
        raise RuntimeError(f"Expected zero or one active DATABASE row; found {len(db_matches)}")
    if len(canonical_matches) not in {0, 1}:
        raise RuntimeError(
            f"Expected zero or one 2026 canonical row; found {len(canonical_matches)}"
        )
    if canonical_matches and canonical_matches[0].get("record_type") != "hunt_planner_permit_reference":
        raise RuntimeError("EA1281 current canonical row is not the expected permit reference")
    if len(historical_matches) != 36:
        raise RuntimeError(
            f"Expected 36 preserved 2025 historical rows; found {len(historical_matches)}"
        )

    db_before_hash = sha256(DATABASE)
    canonical_before_hash = sha256(CURRENT_CANONICAL)
    db_after = [row for row in db_rows if row.get("hunt_code") != HUNT_CODE]
    canonical_after = [
        row for row in canonical_rows if row.get("hunt_code") != HUNT_CODE
    ]
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if args.write and (db_matches or canonical_matches):
        backup_dir = AUDIT_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(DATABASE, backup_dir / f"DATABASE.before_{stamp}.csv")
        shutil.copy2(
            CURRENT_CANONICAL,
            backup_dir / f"{CURRENT_CANONICAL.stem}.before_{stamp}.csv",
        )
        write_csv_atomic(DATABASE, db_fields, db_after)
        write_csv_atomic(CURRENT_CANONICAL, canonical_fields, canonical_after)

    summary = {
        "artifact": "ea1281_archived_2025_not_current_2026",
        "generated_at_utc": timestamp,
        "write": args.write,
        "hunt_code": HUNT_CODE,
        "disposition": "RETIRED_2025_HUNT_EXCLUDED_FROM_ACTIVE_2026",
        "official_detail": {
            "url": "https://dwrapps.utah.gov/huntboundary/HaNumber?roles=&hn=EA1281",
            "hunt_year": 2025,
            "status": "OFF",
            "season": "Dec 20 2025 - Jan 11 2026",
            "quota_res": 67,
            "quota_nres": 8,
            "quota_total": 75,
            "updated": "Jul 17, 2026",
        },
        "current_list": {
            "url": "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Elk&gender=Antlerless",
            "ea1281_match_count_verified_2026_09_02": 0,
        },
        "guidebook": {
            "path": "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/antlerless_guidebook.pdf",
            "ea1281_match_count": 0,
            "deep_creek_match_count": 0,
            "current_mt_dutton_north_codes_listed": ["EA1291", "EA1292"],
        },
        "database_rows_before": len(db_rows),
        "database_rows_after": len(db_after),
        "database_ea1281_rows_removed": len(db_matches),
        "database_sha256_before": db_before_hash,
        "database_sha256_after": sha256(DATABASE) if args.write else "",
        "canonical_rows_before": len(canonical_rows),
        "canonical_rows_after": len(canonical_after),
        "canonical_ea1281_rows_removed": len(canonical_matches),
        "canonical_sha256_before": canonical_before_hash,
        "canonical_sha256_after": sha256(CURRENT_CANONICAL) if args.write else "",
        "historical_2025_ea1281_rows_preserved": len(historical_matches),
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
