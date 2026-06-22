#!/usr/bin/env python3
"""Populate aggregate total draw-result columns from resident/nonresident fields.

The yearly canonical files keep resident and nonresident point rows in the same
record. This script fills the aggregate total_* draw-result columns from those
source values in both the yearly canonical CSV and the matching slice of
draw_results_long.csv.
"""

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
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"

TOTAL_SOURCE_FIELDS = [
    ("total_eligible_applicants", "resident_eligible_applicants", "nonresident_eligible_applicants"),
    ("total_bonus_permits", "resident_bonus_permits", "nonresident_bonus_permits"),
    ("total_regular_permits", "resident_regular_permits", "nonresident_regular_permits"),
    ("total_permits", "resident_total_permits", "nonresident_total_permits"),
]


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: object) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "NONE", "NAN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.10g}"


def sum_sources(row: dict[str, str], left: str, right: str) -> float | None:
    values = [to_float(row.get(left)), to_float(row.get(right))]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def fallback_total_permits(row: dict[str, str], year: int) -> float | None:
    record_type = clean(row.get("record_type")).lower()
    if record_type == "point_level_draw_result":
        return None
    return to_float(row.get(f"permits_{year}_total"))


def format_success_ratio(applicants: float | None, permits: float | None) -> str | None:
    if applicants is None or permits is None:
        return None
    if applicants <= 0 or permits <= 0:
        return "N/A" if applicants > 0 and permits == 0 else None
    denominator = applicants / permits
    if abs(denominator - round(denominator)) < 1e-9:
        shown = f"{int(round(denominator)):,}"
    else:
        shown = f"{denominator:,.1f}"
    return f"1 in {shown}"


def target_path_for_year(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def update_rows(
    *,
    path: Path,
    year: int,
    header: list[str],
    rows: list[dict[str, str]],
    write: bool,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    changes: list[dict[str, object]] = []
    target_rows = 0
    header_set = set(header)
    for row_number, row in enumerate(rows, start=2):
        if path == LONG_FILE and clean(row.get("actual_draw_year")) != str(year):
            continue
        target_rows += 1
        for total_col, left_col, right_col in TOTAL_SOURCE_FIELDS:
            if total_col not in header_set or left_col not in header_set or right_col not in header_set:
                continue
            total = sum_sources(row, left_col, right_col)
            if total is None and total_col == "total_permits":
                total = fallback_total_permits(row, year)
            if total is None:
                continue
            desired = format_number(total)
            current = clean(row.get(total_col))
            if current != desired:
                row[total_col] = desired
                changes.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "row_number": row_number,
                        "actual_draw_year": year,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "column": total_col,
                        "old_value": current,
                        "new_value": desired,
                    }
                )

        if "total_success_ratio" in header_set:
            ratio = format_success_ratio(
                to_float(row.get("total_eligible_applicants")),
                to_float(row.get("total_permits")),
            )
            if ratio is not None and clean(row.get("total_success_ratio")) != ratio:
                current = clean(row.get("total_success_ratio"))
                row["total_success_ratio"] = ratio
                changes.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "row_number": row_number,
                        "actual_draw_year": year,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "column": "total_success_ratio",
                        "old_value": current,
                        "new_value": ratio,
                    }
                )

    if write and changes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / "backups" / f"{path.stem}.before_total_draw_result_population_{year}_{stamp}{path.suffix}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        write_csv(path, header, rows)

    summary = {
        "path": str(path.relative_to(ROOT)),
        "actual_draw_year": year,
        "target_rows": target_rows,
        "cell_updates": len(changes),
        "updates_by_column": dict(Counter(str(change["column"]) for change in changes)),
    }
    return changes, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    all_changes: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for year in args.year:
        for path in (target_path_for_year(year), LONG_FILE):
            header, rows = read_csv(path)
            changes, summary = update_rows(path=path, year=year, header=header, rows=rows, write=args.write)
            all_changes.extend(changes)
            summaries.append(summary)

    changes_path = AUDIT_DIR / (
        "total_draw_result_population_applied.csv" if args.write else "total_draw_result_population_dry_run.csv"
    )
    with changes_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["path", "row_number", "actual_draw_year", "hunt_code", "column", "old_value", "new_value"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_changes)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write_mode": args.write,
        "years": args.year,
        "summaries": summaries,
        "changes_csv": str(changes_path.relative_to(ROOT)),
    }
    report_path = AUDIT_DIR / (
        "total_draw_result_population_applied_summary.json"
        if args.write
        else "total_draw_result_population_dry_run_summary.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
