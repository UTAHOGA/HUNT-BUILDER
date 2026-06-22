#!/usr/bin/env python3
"""Propagate 2026 permit columns across rows for the same hunt code."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "outputs" / "2026 scorable draw results.csv",
    ROOT / "outputs" / "2026 quota allotment rows.csv",
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
]
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
COLUMNS = ["permits_2026_res", "permits_2026_nr", "permits_2026_total"]


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


def year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("year") or row.get("source_year"))


def code(row: dict[str, str]) -> str:
    return clean(row.get("hunt_code")).upper()


def is_sportsman(row: dict[str, str]) -> bool:
    return "sportsman" in " ".join(clean(row.get(k)).lower() for k in ["hunt_type", "source_file", "source_scope", "draw_source_namespace"])


def score_tuple(values: tuple[str, str, str]) -> tuple[int, int]:
    res, nr, total = values
    nonblank = sum(1 for value in values if value != "")
    numeric_total = int(total) if total.isdigit() else -1
    return nonblank, numeric_total


def build_truth() -> dict[str, tuple[str, str, str]]:
    candidates: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path in FILES[:2]:
        _fields, rows = read_csv(path)
        for row in rows:
            hunt_code = code(row)
            if not hunt_code:
                continue
            res = clean(row.get("permits_2026_res"))
            nr = clean(row.get("permits_2026_nr"))
            total = clean(row.get("permits_2026_total"))
            if is_sportsman(row) and total and not res and not nr:
                res, nr = total, "0"
            if any([res, nr, total]):
                candidates[hunt_code].append((res, nr, total))

    truth: dict[str, tuple[str, str, str]] = {}
    for hunt_code, values in candidates.items():
        nonzero = [item for item in values if item != ("0", "0", "0")]
        pool = nonzero or values
        truth[hunt_code] = sorted(pool, key=score_tuple, reverse=True)[0]
    return truth


def should_update(old: str, new: str) -> bool:
    if new == "":
        return False
    return old != new


def update_file(path: Path, truth: dict[str, tuple[str, str, str]]) -> dict[str, Any]:
    fields, rows = read_csv(path)
    for column in COLUMNS:
        if column not in fields:
            fields.append(column)
    changes = 0
    by_column: Counter[str] = Counter()
    for row in rows:
        if year(row) != "2026":
            continue
        values = truth.get(code(row))
        if not values:
            continue
        for column, new in zip(COLUMNS, values):
            old = clean(row.get(column))
            if should_update(old, new):
                row[column] = new
                changes += 1
                by_column[column] += 1
    write_csv(path, fields, rows)
    target_rows = [row for row in rows if year(row) == "2026"]
    return {
        "rows_2026": len(target_rows),
        "updates": changes,
        "updates_by_column": dict(by_column),
        "blank_counts_after": {column: sum(1 for row in target_rows if clean(row.get(column)) == "") for column in COLUMNS},
        "zero_zero_zero_rows": sum(1 for row in target_rows if tuple(clean(row.get(column)) for column in COLUMNS) == ("0", "0", "0")),
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    truth = build_truth()
    results = {str(path.relative_to(ROOT)).replace("\\", "/"): update_file(path, truth) for path in FILES}
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "truth_hunt_codes": len(truth),
        "results": results,
    }
    out = AUDIT_DIR / "propagate_2026_permit_columns_by_hunt_code_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
