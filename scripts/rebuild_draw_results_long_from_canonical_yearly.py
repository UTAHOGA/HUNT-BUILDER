#!/usr/bin/env python3
"""Rebuild draw_results_long.csv from official yearly canonical files.

This is intentionally strict: if any canonical yearly file still has the old
`residency` split-row column, the script refuses to write the long file. The
long file should be one durable shape, not mixed old/new row models.  The
explicit ``--allow-split-row-canonical`` mode supports the repository's current
uniform split-row canonical set without silently mixing shapes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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


def validate_headers(
    files: list[Path],
    headers: dict[Path, list[str]],
    allow_split_row_canonical: bool,
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for path in files:
        header = headers[path]
        if "residency" in header and not allow_split_row_canonical:
            problems.append(
                {
                    "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "problem": "old_split_residency_column_present",
                }
            )
        required_columns = (
            ["actual_draw_year", "residency", "eligible_applicants", "total_permits"]
            if allow_split_row_canonical
            else ["resident_eligible_applicants", "nonresident_eligible_applicants"]
        )
        for required in required_columns:
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rebuild(
    write: bool,
    allow_split_row_canonical: bool = False,
    backup_existing: bool = True,
) -> dict[str, object]:
    files = canonical_files()
    headers = {path: read_header(path) for path in files}
    problems = validate_headers(files, headers, allow_split_row_canonical)
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
    build_path = output_path.with_suffix(output_path.suffix + ".tmp") if write else output_path
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = ""
    prior_output_sha256 = _sha256(LONG_FILE) if write and LONG_FILE.exists() else ""
    if write and backup_existing and LONG_FILE.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{LONG_FILE.stem}.before_dwr_table_shape_{timestamp}{LONG_FILE.suffix}"
        shutil.copy2(LONG_FILE, backup)
        backup_path = str(backup.relative_to(ROOT)).replace("\\", "/")

    years_seen: dict[str, int] = {}
    with build_path.open("w", newline="", encoding="utf-8") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=output_header, lineterminator="\n")
        writer.writeheader()
        for path in files:
            count = 0
            with path.open(newline="", encoding="utf-8-sig") as in_handle:
                reader = csv.DictReader(in_handle)
                for row in reader:
                    writer.writerow({column: row.get(column, "") for column in output_header})
                    actual_draw_year = str(row.get("actual_draw_year") or "").strip()
                    if actual_draw_year:
                        years_seen[actual_draw_year] = years_seen.get(actual_draw_year, 0) + 1
                    count += 1
            row_counts[str(path.relative_to(ROOT)).replace("\\", "/")] = count
            total_rows += count

    if write:
        build_path.replace(output_path)

    return {
        "write": write,
        "blocked": False,
        "output_path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        "backup_path": backup_path,
        "prior_output_sha256": prior_output_sha256,
        "output_sha256": _sha256(output_path),
        "canonical_shape": "split_residency_rows" if allow_split_row_canonical else "collapsed_residency_columns",
        "canonical_file_count": len(files),
        "rows": total_rows,
        "columns": len(output_header),
        "actual_draw_year_row_counts": dict(sorted(years_seen.items())),
        "row_counts": row_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--allow-split-row-canonical",
        action="store_true",
        help="Rebuild from the current uniform split-residency canonical yearly files.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Record the prior hash but do not duplicate the existing large generated long file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = rebuild(
        write=args.write,
        allow_split_row_canonical=args.allow_split_row_canonical,
        backup_existing=not args.no_backup,
    )
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if summary.get("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
