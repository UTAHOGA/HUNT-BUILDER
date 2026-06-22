#!/usr/bin/env python3
"""Promote complete 2026 scorable/quota outputs back to yearly canonical.

This restores the source-preserving 2026 shape:
- point-level and Sportsman rows from outputs/2026 scorable draw results.csv
- non-scorable quota rows from outputs/2026 quota allotment rows.csv

It also replaces the 2026 slice in draw_results_long.csv with the promoted
canonical rows, expanding the long schema when needed.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
SCORABLE = ROOT / "outputs" / "2026 scorable draw results.csv"
QUOTA = ROOT / "outputs" / "2026 quota allotment rows.csv"
AUDIT_DIR = ROOT / "audits" / "2026_canonical_reconciliation"
BACKUP_DIR = AUDIT_DIR / "backups"


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def union_header(*headers: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for header in headers:
        for column in header:
            if column not in seen:
                out.append(column)
                seen.add(column)
    return out


def row_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("year") or row.get("source_year"))


def key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        clean(row.get("actual_draw_year")),
        clean(row.get("model_target_year")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")),
        clean(row.get("points")),
        clean(row.get("record_type")),
        clean(row.get("source_file")),
    )


def count_blanks(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if clean(row.get(field)) == "")


def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    scorable_header, scorable_rows = read_csv(SCORABLE)
    quota_header, quota_rows = read_csv(QUOTA)
    canonical_old_header, canonical_old_rows = read_csv(CANONICAL)
    long_header, long_rows = read_csv(LONG)

    promoted_header = union_header(scorable_header, quota_header)
    promoted_rows = [
        {column: row.get(column, "") for column in promoted_header}
        for row in [*scorable_rows, *quota_rows]
    ]

    duplicate_keys = [k for k, count in Counter(key(row) for row in promoted_rows).items() if count > 1]
    if duplicate_keys:
        dup_path = AUDIT_DIR / "promote_2026_scorable_to_canonical_duplicate_keys.csv"
        write_csv(
            dup_path,
            ["actual_draw_year", "model_target_year", "hunt_code", "residency", "points", "record_type", "source_file"],
            [
                {
                    "actual_draw_year": item[0],
                    "model_target_year": item[1],
                    "hunt_code": item[2],
                    "residency": item[3],
                    "points": item[4],
                    "record_type": item[5],
                    "source_file": item[6],
                }
                for item in duplicate_keys
            ],
        )

    canonical_backup = BACKUP_DIR / f"{CANONICAL.stem}.before_promote_2026_scorable_{timestamp}{CANONICAL.suffix}"
    long_backup = BACKUP_DIR / f"{LONG.stem}.before_promote_2026_scorable_{timestamp}{LONG.suffix}"
    shutil.copy2(CANONICAL, canonical_backup)
    shutil.copy2(LONG, long_backup)

    write_csv(CANONICAL, promoted_header, promoted_rows)

    new_long_header = union_header(long_header, promoted_header)
    retained_long = [row for row in long_rows if row_year(row) != "2026"]
    new_long_rows = [
        {column: row.get(column, "") for column in new_long_header}
        for row in retained_long
    ]
    new_long_rows.extend({column: row.get(column, "") for column in new_long_header} for row in promoted_rows)
    write_csv(LONG, new_long_header, new_long_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_source": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "scorable_source": str(SCORABLE.relative_to(ROOT)).replace("\\", "/"),
        "quota_source": str(QUOTA.relative_to(ROOT)).replace("\\", "/"),
        "canonical_backup": str(canonical_backup.relative_to(ROOT)).replace("\\", "/"),
        "long_backup": str(long_backup.relative_to(ROOT)).replace("\\", "/"),
        "old_canonical_rows": len(canonical_old_rows),
        "old_canonical_columns": len(canonical_old_header),
        "promoted_canonical_rows": len(promoted_rows),
        "promoted_canonical_columns": len(promoted_header),
        "scorable_rows": len(scorable_rows),
        "quota_rows": len(quota_rows),
        "long_rows_before": len(long_rows),
        "long_rows_after": len(new_long_rows),
        "long_columns_before": len(long_header),
        "long_columns_after": len(new_long_header),
        "record_type_counts": dict(Counter(clean(row.get("record_type")) or "(blank)" for row in promoted_rows).most_common()),
        "blank_counts": {
            "hunt_code": count_blanks(promoted_rows, "hunt_code"),
            "total_permits": count_blanks([row for row in promoted_rows if clean(row.get("record_type")) != "hunt_planner_permit_quota"], "total_permits"),
            "eligible_applicants": count_blanks([row for row in promoted_rows if clean(row.get("record_type")) != "hunt_planner_permit_quota"], "eligible_applicants"),
            "permits_2026_res": count_blanks(promoted_rows, "permits_2026_res"),
            "permits_2026_nr": count_blanks(promoted_rows, "permits_2026_nr"),
            "permits_2026_total": count_blanks(promoted_rows, "permits_2026_total"),
        },
        "duplicate_strict_key_groups": len(duplicate_keys),
    }
    summary_path = AUDIT_DIR / "promote_2026_scorable_to_canonical_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
