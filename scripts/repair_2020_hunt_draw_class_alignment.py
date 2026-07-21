#!/usr/bin/env python3
"""Align 2020 split-source hunt_draw_class with source-specific hunt_class.

This is metadata-only. It does not change hunt codes, points, applicant counts,
success counts, probabilities, permit counts, or row counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET_YEAR = "2021"
SOURCE_YEAR = "2020"
CANONICAL = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
)
LONG_FILE = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_ROOT = REPO / "audits" / "source_design_alignment" / "2020_for_2021"

SPLIT_DESIGNS = {
    "BONUS_LE_BIG_GAME",
    "BONUS_CWMU_BIG_GAME",
    "BONUS_OIL_BIG_GAME",
    "BONUS_ANTLERLESS_MOOSE",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def row_target_year(row: dict[str, str]) -> str:
    return clean(row.get("model_target_year") or row.get("target_year") or row.get("draw_year"))


def row_source_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("source_year"))


def should_repair(row: dict[str, str]) -> bool:
    if row_target_year(row) != TARGET_YEAR or row_source_year(row) != SOURCE_YEAR:
        return False
    if clean(row.get("draw_system_type") or row.get("draw_design")).upper() not in SPLIT_DESIGNS:
        return False
    source_file = clean(row.get("source_file"))
    if not source_file.startswith("2020_PERMITS=2021_MODEL"):
        return False
    hunt_class = clean(row.get("hunt_class"))
    return bool(hunt_class and clean(row.get("hunt_draw_class")) != hunt_class)


def repair_file(path: Path, stamp: str, apply: bool) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    changed = []
    for line_number, row in enumerate(rows, start=2):
        if not should_repair(row):
            continue
        changed.append(
            {
                "path": str(path),
                "line": str(line_number),
                "hunt_code": clean(row.get("hunt_code")),
                "points": clean(row.get("points")),
                "source_file": clean(row.get("source_file")),
                "old_hunt_draw_class": clean(row.get("hunt_draw_class")),
                "new_hunt_draw_class": clean(row.get("hunt_class")),
            }
        )
        if "hunt_draw_class" in fields:
            row["hunt_draw_class"] = clean(row.get("hunt_class"))

    backup = ""
    if apply and changed:
        backup_path = path.with_name(f"{path.stem}.backup_2020_hunt_draw_class_alignment_{stamp}{path.suffix}")
        shutil.copy2(path, backup_path)
        backup = str(backup_path)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return {"path": str(path), "rows": len(rows), "changed_rows": len(changed), "backup": backup, "changed": changed}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-long", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = AUDIT_ROOT / f"hunt_draw_class_alignment_{stamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)
    files = [CANONICAL]
    if args.include_long:
        files.append(LONG_FILE)
    summaries = []
    changed = []
    for path in files:
        result = repair_file(path, stamp, args.apply)
        summaries.append({k: v for k, v in result.items() if k != "changed"})
        changed.extend(result["changed"])
    fields = ["path", "line", "hunt_code", "points", "source_file", "old_hunt_draw_class", "new_hunt_draw_class"]
    with (audit_dir / "changed_rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(changed)
    (audit_dir / "summary.json").write_text(
        json.dumps(
            {"apply": args.apply, "include_long": args.include_long, "changed_rows": len(changed), "files": summaries},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"audit_dir": str(audit_dir), "changed_rows": len(changed)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
