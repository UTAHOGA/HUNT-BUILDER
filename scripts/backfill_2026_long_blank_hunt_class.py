#!/usr/bin/env python3
"""Backfill safe 2026 hunt_class blanks in draw_results_long.csv.

This script only fills blank hunt_class cells when the same row already has a
nonblank draw_design value and DATABASE.csv confirms the same hunt code uses
that value as hunt_class. It intentionally does not infer resident/nonresident
permit splits when the source only carries total permits.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LONG_PATH = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_DIR = ROOT / "pipeline" / "R2_OFFLOAD" / "incoming"
AUDIT_CSV = AUDIT_DIR / "2026_long_hunt_class_blank_backfill_audit.csv"
SUMMARY_JSON = AUDIT_DIR / "2026_long_hunt_class_blank_backfill_summary.json"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_database_hunt_class() -> dict[str, str]:
    _, rows = read_csv(DATABASE_PATH)
    out: dict[str, str] = {}
    conflicts: dict[str, set[str]] = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        value = clean(row.get("hunt_class"))
        if not code or not value:
            continue
        if code in out and out[code] != value:
            conflicts.setdefault(code, {out[code]}).add(value)
            continue
        out[code] = value
    if conflicts:
        formatted = {code: sorted(values) for code, values in conflicts.items()}
        raise RuntimeError(f"Conflicting DATABASE hunt_class values: {formatted}")
    return out


def main() -> None:
    db_hunt_class = build_database_hunt_class()
    headers, rows = read_csv(LONG_PATH)
    required = {"actual_draw_year", "hunt_code", "hunt_class", "draw_design"}
    missing = sorted(required - set(headers))
    if missing:
        raise RuntimeError(f"Missing required columns in draw_results_long.csv: {missing}")

    audit_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    changed = 0
    for index, row in enumerate(rows, start=2):
        if clean(row.get("actual_draw_year")) != "2026":
            continue
        if clean(row.get("hunt_class")):
            continue
        code = clean(row.get("hunt_code")).upper()
        draw_design = clean(row.get("draw_design"))
        database_hunt_class = db_hunt_class.get(code, "")
        audit = {
            "row_number": index,
            "hunt_code": code,
            "hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "sex_type": clean(row.get("sex_type")),
            "weapon": clean(row.get("weapon")),
            "hunt_type": clean(row.get("hunt_type")),
            "old_hunt_class": "",
            "draw_design": draw_design,
            "database_hunt_class": database_hunt_class,
            "new_hunt_class": "",
            "action": "",
            "reason": "",
        }
        if draw_design and database_hunt_class and draw_design == database_hunt_class:
            row["hunt_class"] = draw_design
            audit["new_hunt_class"] = draw_design
            audit["action"] = "FILLED"
            audit["reason"] = "blank hunt_class matched row draw_design and DATABASE hunt_class"
            audit_rows.append(audit)
            changed += 1
        else:
            audit["action"] = "SKIPPED"
            audit["reason"] = "no exact draw_design/DATABASE hunt_class agreement"
            skipped_rows.append(audit)

    if changed:
        write_csv(LONG_PATH, headers, rows)
    write_csv(
        AUDIT_CSV,
        [
            "row_number",
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "weapon",
            "hunt_type",
            "old_hunt_class",
            "draw_design",
            "database_hunt_class",
            "new_hunt_class",
            "action",
            "reason",
        ],
        audit_rows + skipped_rows,
    )
    summary = {
        "target": str(LONG_PATH),
        "database_source": str(DATABASE_PATH),
        "audit_csv": str(AUDIT_CSV),
        "rows_filled": changed,
        "rows_skipped": len(skipped_rows),
        "codes_filled": sorted({str(row["hunt_code"]) for row in audit_rows}),
        "note": "Only blank hunt_class cells were filled; resident/nonresident permit blanks were not inferred from total-only rows.",
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
