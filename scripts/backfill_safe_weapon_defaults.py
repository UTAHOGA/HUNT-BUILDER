#!/usr/bin/env python3
"""Fill only safe, deterministic blank weapon values in canonical yearly files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "weapon_backfill"
BACKUP_DIR = AUDIT_DIR / "backups"
YEARS = list(range(2019, 2027))


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


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


def infer_weapon(row: dict[str, str]) -> tuple[str, str]:
    species = clean(row.get("species")).lower()
    sex_type = clean(row.get("sex_type")).lower()
    hunt_type = clean(row.get("hunt_type")).lower()
    source = clean(row.get("source_file")).lower()
    code_prefix = clean(row.get("hunt_code")).upper()[:2]

    if species == "cougar":
        return "Any Legal Weapon", "legacy cougar draw rows are any legal weapon"
    if species == "deer" and sex_type == "buck" and hunt_type == "dedicated hunter":
        return "Any Legal Weapon", "dedicated hunter deer is any legal weapon"
    if code_prefix == "MB" and species in {"moose", "MOOSE".lower()} and sex_type == "bull":
        return "Any Legal Weapon", "bull moose O.I.L. rows are any legal weapon"
    if "bull moose" in source and code_prefix == "MB":
        return "Any Legal Weapon", "bull moose source file"
    return "", ""


def process_year(year: int, *, write: bool) -> dict[str, object]:
    path = canonical_path(year)
    fieldnames, rows = read_csv(path)
    if "weapon" not in fieldnames:
        return {"year": year, "rows": len(rows), "filled": 0, "backup_path": "", "audit_rows": []}

    audit_rows: list[dict[str, str]] = []
    blank_before = sum(1 for row in rows if not clean(row.get("weapon")))
    for row_number, row in enumerate(rows, start=2):
        if clean(row.get("weapon")):
            continue
        weapon, reason = infer_weapon(row)
        if not weapon:
            continue
        row["weapon"] = weapon
        audit_rows.append(
            {
                "year": str(year),
                "row_number": str(row_number),
                "hunt_code": clean(row.get("hunt_code")),
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "hunt_type": clean(row.get("hunt_type")),
                "new_weapon": weapon,
                "reason": reason,
            }
        )

    backup = None
    if write and audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{path.stem}.before_weapon_backfill_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        write_csv(path, fieldnames, rows)

    blank_after = sum(1 for row in rows if not clean(row.get("weapon")))
    return {
        "year": year,
        "write": write,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(rows),
        "blank_before": blank_before,
        "blank_after": blank_after,
        "filled": len(audit_rows),
        "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/") if backup else "",
        "audit_rows": audit_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summaries = [process_year(year, write=args.write) for year in YEARS]
    audit_rows = [row for summary in summaries for row in summary.pop("audit_rows")]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / "weapon_backfill_audit.csv"
    fieldnames = [
        "year",
        "row_number",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "new_weapon",
        "reason",
    ]
    with audit_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "write": args.write,
        "audit_path": str(audit_path.relative_to(ROOT)).replace("\\", "/"),
        "total_filled": len(audit_rows),
        "filled_by_year": {str(summary["year"]): summary["filled"] for summary in summaries},
        "changes_by_reason": dict(Counter(row["reason"] for row in audit_rows)),
        "summaries": summaries,
    }
    (AUDIT_DIR / "weapon_backfill_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
