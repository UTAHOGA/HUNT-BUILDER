#!/usr/bin/env python3
"""Rebuild draw_results_long.csv from DWR-table-shaped yearly canonical files.

This is intentionally strict: if any canonical yearly file still has the old
`residency` split-row column, the script refuses to write the long file. The
long file should be one durable shape, not mixed old/new row models.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild"
BACKUP_DIR = AUDIT_DIR / "backups"
REPORT_PATH = AUDIT_DIR / "draw_results_long_rebuild_summary.json"


FRONT_COLUMNS = [
    "actual_draw_year",
    "model_target_year",
    "boundary_id",
    "hunt_code",
    "hunt_name",
    "sex_type",
    "species",
    "hunt_type",
    "weapon",
    "season",
    "draw_design",
    "points",
    "record_type",
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "resident_success_ratio",
    "resident_p_draw",
    "resident_p_draw_percent",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "nonresident_success_ratio",
    "nonresident_p_draw",
    "nonresident_p_draw_percent",
    "total_eligible_applicants",
    "total_bonus_permits",
    "total_regular_permits",
    "total_permits",
    "total_success_ratio",
    "total_p_draw",
    "total_p_draw_percent",
]

DROP_COLUMNS = {
    "source_year",
    "year",
    "model_year",
    "truth_year",
    "permits_year",
    "permits_year_res",
    "permits_year_nr",
    "permits_year_total",
}


def canonical_files() -> list[Path]:
    return sorted(CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv"))


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        return next(reader)


def union_header(headers: list[list[str]]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for column in FRONT_COLUMNS:
        if any(column in header for header in headers):
            output.append(column)
            seen.add(column)
    permit_columns = sorted(
        {
            column
            for header in headers
            for column in header
            if column.startswith("permits_")
            and column.rsplit("_", 1)[-1] in {"res", "nr", "total"}
            and column not in DROP_COLUMNS
        }
    )
    for column in permit_columns:
        if column not in seen:
            output.append(column)
            seen.add(column)
    for header in headers:
        for column in header:
            if column not in seen and column not in DROP_COLUMNS:
                output.append(column)
                seen.add(column)
    return output


def validate_headers(files: list[Path], headers: dict[Path, list[str]]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for path in files:
        header = headers[path]
        if "residency" in header:
            problems.append(
                {
                    "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "problem": "old_split_residency_column_present",
                }
            )
        for required in ["resident_eligible_applicants", "nonresident_eligible_applicants"]:
            if required not in header:
                problems.append(
                    {
                        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "problem": f"missing_required_column:{required}",
                    }
                )
    return problems


def write_problem_audit(problems: list[dict[str, str]]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "draw_results_long_rebuild_blockers.csv"
    fields = ["file", "problem"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(problems)


def rebuild(write: bool) -> dict[str, object]:
    files = canonical_files()
    headers = {path: read_header(path) for path in files}
    problems = validate_headers(files, headers)
    if problems:
        write_problem_audit(problems)
        return {
            "write": False,
            "blocked": True,
            "problem_count": len(problems),
            "problem_audit": str((AUDIT_DIR / "draw_results_long_rebuild_blockers.csv").relative_to(ROOT)).replace("\\", "/"),
        }

    output_header = union_header(list(headers.values()))
    row_counts: dict[str, int] = {}
    total_rows = 0
    output_path = LONG_FILE if write else AUDIT_DIR / "draw_results_long_DWR_TABLE_SHAPE_PREVIEW.csv"
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = ""
    if write:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{LONG_FILE.stem}.before_dwr_table_shape_{timestamp}{LONG_FILE.suffix}"
        shutil.copy2(LONG_FILE, backup)
        backup_path = str(backup.relative_to(ROOT)).replace("\\", "/")

    with output_path.open("w", newline="", encoding="utf-8") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=output_header, lineterminator="\n")
        writer.writeheader()
        for path in files:
            count = 0
            with path.open(newline="", encoding="utf-8-sig") as in_handle:
                reader = csv.DictReader(in_handle)
                for row in reader:
                    writer.writerow({column: row.get(column, "") for column in output_header})
                    count += 1
            row_counts[str(path.relative_to(ROOT)).replace("\\", "/")] = count
            total_rows += count

    return {
        "write": write,
        "blocked": False,
        "output_path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        "backup_path": backup_path,
        "canonical_file_count": len(files),
        "rows": total_rows,
        "columns": len(output_header),
        "row_counts": row_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = rebuild(write=args.write)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if summary.get("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
