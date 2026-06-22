#!/usr/bin/env python3
"""Backfill blank boundary_id values using trusted exact hunt-code/name joins."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "boundary_backfill"
BACKUP_DIR = AUDIT_DIR / "backups"

YEARS = list(range(2019, 2027))
TRUSTED_CANONICAL_YEARS = [2024, 2025, 2026]


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def norm_name(value: object) -> str:
    text = clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\b(the|unit|hunt|limited|entry|general|season|premium|once|lifetime)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


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


def add_candidate(
    by_code_name: dict[tuple[str, str], Counter[str]],
    by_code: dict[str, Counter[str]],
    code: str,
    name: str,
    boundary_id: str,
) -> None:
    code = clean(code).upper()
    boundary_id = clean(boundary_id)
    normalized_name = norm_name(name)
    if not code or not boundary_id:
        return
    by_code[code][boundary_id] += 1
    if normalized_name:
        by_code_name[(code, normalized_name)][boundary_id] += 1


def build_candidates() -> tuple[dict[tuple[str, str], Counter[str]], dict[str, Counter[str]]]:
    by_code_name: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    by_code: dict[str, Counter[str]] = defaultdict(Counter)

    _, db_rows = read_csv(DATABASE)
    for row in db_rows:
        add_candidate(by_code_name, by_code, row.get("hunt_code", ""), row.get("hunt_name", ""), row.get("boundary_id", ""))

    for year in TRUSTED_CANONICAL_YEARS:
        _, rows = read_csv(canonical_path(year))
        for row in rows:
            add_candidate(by_code_name, by_code, row.get("hunt_code", ""), row.get("hunt_name", ""), row.get("boundary_id", ""))

    return by_code_name, by_code


def choose(counter: Counter[str]) -> str:
    values = [value for value in counter if value]
    return values[0] if len(values) == 1 else ""


def process_year(
    year: int,
    by_code_name: dict[tuple[str, str], Counter[str]],
    by_code: dict[str, Counter[str]],
    *,
    write: bool,
) -> dict[str, object]:
    path = canonical_path(year)
    fieldnames, rows = read_csv(path)
    audit_rows: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []

    if "boundary_id" not in fieldnames:
        return {
            "year": year,
            "write": write,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "rows": len(rows),
            "filled": 0,
            "ambiguous": 0,
            "blank_before": 0,
            "blank_after": 0,
            "backup_path": "",
            "audit_rows": [],
            "ambiguous_rows": [],
        }

    blank_before = sum(1 for row in rows if not clean(row.get("boundary_id")))
    for row_number, row in enumerate(rows, start=2):
        if clean(row.get("boundary_id")):
            continue
        code = clean(row.get("hunt_code")).upper()
        name_key = norm_name(row.get("hunt_name"))
        boundary_id = choose(by_code_name.get((code, name_key), Counter()))
        reason = "exact hunt_code + normalized hunt_name"
        if not boundary_id:
            boundary_id = choose(by_code.get(code, Counter()))
            reason = "single unambiguous boundary for exact hunt_code"
        if boundary_id:
            row["boundary_id"] = boundary_id
            audit_rows.append(
                {
                    "year": str(year),
                    "row_number": str(row_number),
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "new_boundary_id": boundary_id,
                    "reason": reason,
                }
            )
        else:
            candidates = sorted(by_code.get(code, Counter()))
            if candidates:
                ambiguous_rows.append(
                    {
                        "year": str(year),
                        "row_number": str(row_number),
                        "hunt_code": code,
                        "hunt_name": clean(row.get("hunt_name")),
                        "candidate_boundary_ids": " | ".join(candidates),
                    }
                )

    blank_after = sum(1 for row in rows if not clean(row.get("boundary_id")))
    backup = None
    if write and audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{path.stem}.before_boundary_backfill_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        write_csv(path, fieldnames, rows)

    return {
        "year": year,
        "write": write,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "rows": len(rows),
        "filled": len(audit_rows),
        "ambiguous": len(ambiguous_rows),
        "blank_before": blank_before,
        "blank_after": blank_after,
        "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/") if backup else "",
        "audit_rows": audit_rows,
        "ambiguous_rows": ambiguous_rows,
    }


def write_audit(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    by_code_name, by_code = build_candidates()
    summaries = [process_year(year, by_code_name, by_code, write=args.write) for year in YEARS]
    audit_rows = [row for summary in summaries for row in summary.pop("audit_rows")]
    ambiguous_rows = [row for summary in summaries for row in summary.pop("ambiguous_rows")]
    audit_path = write_audit(
        AUDIT_DIR / "boundary_backfill_audit.csv",
        audit_rows,
        ["year", "row_number", "hunt_code", "hunt_name", "new_boundary_id", "reason"],
    )
    ambiguous_path = write_audit(
        AUDIT_DIR / "boundary_backfill_ambiguous.csv",
        ambiguous_rows,
        ["year", "row_number", "hunt_code", "hunt_name", "candidate_boundary_ids"],
    )
    summary = {
        "write": args.write,
        "trusted_canonical_years": TRUSTED_CANONICAL_YEARS,
        "database": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
        "audit_path": audit_path,
        "ambiguous_path": ambiguous_path,
        "total_filled": len(audit_rows),
        "total_ambiguous": len(ambiguous_rows),
        "filled_by_year": {str(summary["year"]): summary["filled"] for summary in summaries},
        "blank_after_by_year": {str(summary["year"]): summary["blank_after"] for summary in summaries},
        "summaries": summaries,
    }
    (AUDIT_DIR / "boundary_backfill_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
