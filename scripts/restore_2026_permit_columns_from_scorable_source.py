#!/usr/bin/env python3
"""Restore 2026 permit columns from preserved scorable/permit-reference source rows."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
SCORABLE = ROOT / "outputs" / "2026 scorable draw results.csv"
PERMIT_REFERENCE = ROOT / "outputs" / "2026 permit reference rows.csv"
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
PERMIT_COLUMNS = ["permits_2026_res", "permits_2026_nr", "permits_2026_total"]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def key(row: dict[str, str]) -> tuple[str, ...]:
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
        clean(row.get("residency")),
        clean(row.get("points")),
        clean(row.get("record_type")),
    )


def source_map() -> dict[tuple[str, ...], dict[str, str]]:
    _sf, scorable = read_csv(SCORABLE)
    _pf, permit_reference = read_csv(PERMIT_REFERENCE)
    return {key(row): row for row in [*scorable, *permit_reference]}


def restore(path: Path, source_by_key: dict[tuple[str, ...], dict[str, str]]) -> tuple[int, Counter[str]]:
    fields, rows = read_csv(path)
    updates = 0
    by_column: Counter[str] = Counter()
    for row in rows:
        if clean(row.get("actual_draw_year") or row.get("year")) != "2026":
            continue
        source = source_by_key.get(key(row))
        if not source:
            continue
        for column in PERMIT_COLUMNS:
            if column not in fields:
                fields.append(column)
            old = row.get(column, "")
            new = source.get(column, "")
            if old != new:
                row[column] = new
                updates += 1
                by_column[column] += 1
    write_csv(path, fields, rows)
    return updates, by_column


def blank_counts(path: Path) -> dict[str, int]:
    _fields, rows = read_csv(path)
    rows = [row for row in rows if clean(row.get("actual_draw_year") or row.get("year")) == "2026"]
    return {column: sum(1 for row in rows if clean(row.get(column)) == "") for column in PERMIT_COLUMNS}


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source_by_key = source_map()
    result = {}
    for path in (CANONICAL, LONG):
        updates, by_column = restore(path, source_by_key)
        result[str(path.relative_to(ROOT)).replace("\\", "/")] = {
            "updates": updates,
            "updates_by_column": dict(by_column),
            "blank_counts_after": blank_counts(path),
        }
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_rows": len(source_by_key),
        "results": result,
    }
    out = AUDIT_DIR / "restore_2026_permit_columns_from_scorable_source_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
