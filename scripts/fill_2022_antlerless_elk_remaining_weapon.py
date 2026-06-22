#!/usr/bin/env python3
"""Fill the remaining 2022 antlerless elk weapon blanks from aligned rows."""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2022_for_2023_canonical_yearly_draw_results.csv"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "weapon_backfill"
BACKUP_DIR = AUDIT_DIR / "backups"
AUDIT_CSV = AUDIT_DIR / "2022_antlerless_elk_remaining_weapon_fill_audit.csv"
SUMMARY_JSON = AUDIT_DIR / "2022_antlerless_elk_remaining_weapon_fill_summary.json"

ALIGNED_WEAPON_BY_CODE_NAME = {
    ("EA1253", "Southwest Desert, Desert Experimental Range"): "Any Legal Weapon",
    ("EA1255", "5s"): "Any Legal Weapon",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames, rows = read_csv(CANONICAL)
    audit_rows: list[dict[str, str]] = []

    for row_number, row in enumerate(rows, start=2):
        if clean(row.get("weapon")):
            continue
        code = clean(row.get("hunt_code")).upper()
        name = clean(row.get("hunt_name"))
        species = clean(row.get("species"))
        sex_type = clean(row.get("sex_type"))
        if species != "Elk" or sex_type != "Antlerless":
            continue
        weapon = ALIGNED_WEAPON_BY_CODE_NAME.get((code, name))
        if not weapon:
            continue
        row["weapon"] = weapon
        audit_rows.append(
            {
                "row_number": str(row_number),
                "hunt_code": code,
                "hunt_name": name,
                "species": species,
                "sex_type": sex_type,
                "source_file": clean(row.get("source_file")),
                "new_weapon": weapon,
                "reason": "exact hunt_code + hunt_name aligned to same weapon in long/canonical history",
            }
        )

    if audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{CANONICAL.stem}.before_2022_antlerless_elk_weapon_fill_{stamp}{CANONICAL.suffix}"
        shutil.copy2(CANONICAL, backup)
        write_csv(CANONICAL, fieldnames, rows)
    else:
        backup = None

    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_number",
                "hunt_code",
                "hunt_name",
                "species",
                "sex_type",
                "source_file",
                "new_weapon",
                "reason",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    remaining = sum(1 for row in rows if not clean(row.get("weapon")))
    summary = {
        "canonical": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "audit_csv": str(AUDIT_CSV.relative_to(ROOT)).replace("\\", "/"),
        "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/") if backup else "",
        "filled_rows": len(audit_rows),
        "remaining_weapon_blanks_in_2022_canonical": remaining,
        "filled_by_hunt_code": dict(Counter(row["hunt_code"] for row in audit_rows)),
        "filled_by_weapon": dict(Counter(row["new_weapon"] for row in audit_rows)),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
