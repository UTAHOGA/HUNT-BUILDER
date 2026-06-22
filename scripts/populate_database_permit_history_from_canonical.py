#!/usr/bin/env python3
"""Populate DATABASE.csv permit history columns from yearly canonical truth files.

The database is a hunt/unit display table, so this script only imports summary
permit fields. Point-ladder applicant/probability rows stay in draw_results_long.
Matching is strict by hunt_code + species + sex_type + weapon first, then by a
single unambiguous hunt_code only when there is exactly one canonical identity
for that code in that year.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def norm(value: object) -> str:
    text = clean(value).lower()
    replacements = {
        "&": " and ",
        "h.a.m.s.": "hamms",
        "hams": "hamms",
        "hunter's choice": "hunters choice",
        "hunter\u2019s choice": "hunters choice",
        "rocky mtn": "rocky mountain",
        "mtn": "mountain",
        "alw": "any legal weapon",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(text.split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def identity(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        norm(row.get("species")),
        norm(row.get("sex_type")),
        norm(row.get("weapon")),
    )


def source_label(year: int) -> str:
    return f"CANONICAL_YEARLY_DRAW_RESULTS_{year}_FOR_{year + 1}_MODEL"


def nonblank(value: object) -> bool:
    return clean(value) != ""


def build_year_index(year: int) -> tuple[dict[tuple[str, str, str, str], dict[str, str]], dict[str, dict[str, str]], set[tuple[str, str, str, str]], set[str]]:
    _, rows = read_csv(canonical_path(year))
    res_col = f"permits_{year}_res"
    nr_col = f"permits_{year}_nr"
    total_col = f"permits_{year}_total"
    by_identity_values: dict[tuple[str, str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    by_identity_row: dict[tuple[str, str, str, str], dict[str, str]] = {}
    code_to_identities: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)

    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        values = (clean(row.get(res_col)), clean(row.get(nr_col)), clean(row.get(total_col)))
        if not any(values):
            continue
        key = identity(row)
        by_identity_values[key].add(values)
        by_identity_row.setdefault(
            key,
            {
                f"permits_{year}_res": values[0],
                f"permits_{year}_nr": values[1],
                f"permits_{year}_total": values[2],
                f"permits_{year}_source": source_label(year),
            },
        )
        code_to_identities[code].add(key)

    conflicting_identities = {key for key, values in by_identity_values.items() if len(values) > 1}
    identity_index = {
        key: value
        for key, value in by_identity_row.items()
        if key not in conflicting_identities
    }
    unique_code_index: dict[str, dict[str, str]] = {}
    ambiguous_codes: set[str] = set()
    for code, identities in code_to_identities.items():
        usable = [key for key in identities if key in identity_index]
        if len(usable) == 1:
            unique_code_index[code] = identity_index[usable[0]]
        elif len(usable) > 1:
            ambiguous_codes.add(code)
    return identity_index, unique_code_index, conflicting_identities, ambiguous_codes


def ensure_columns(header: list[str], years: list[int]) -> list[str]:
    updated = list(header)
    for year in years:
        for suffix in ("res", "nr", "total", "source"):
            column = f"permits_{year}_{suffix}"
            if column not in updated:
                updated.append(column)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    years = sorted(set(args.year or range(2019, 2027)))

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    header, rows = read_csv(DATABASE)
    header = ensure_columns(header, years)
    for row in rows:
        for column in header:
            row.setdefault(column, "")

    indexes = {year: build_year_index(year) for year in years}
    changes: list[dict[str, str]] = []
    row_summaries: list[dict[str, str]] = []

    for row_number, row in enumerate(rows, start=2):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        db_identity = identity(row)
        for year in years:
            identity_index, unique_code_index, conflicting_identities, ambiguous_codes = indexes[year]
            values = identity_index.get(db_identity)
            match_method = "identity"
            if values is None and code in unique_code_index:
                values = unique_code_index[code]
                match_method = "unique_hunt_code"
            elif values is None and db_identity in conflicting_identities:
                match_method = "conflicting_identity_skipped"
            elif values is None and code in ambiguous_codes:
                match_method = "ambiguous_hunt_code_skipped"
            elif values is None:
                match_method = "no_match"

            if values is None:
                row_summaries.append(
                    {
                        "row_number": str(row_number),
                        "hunt_code": code,
                        "year": str(year),
                        "match_method": match_method,
                    }
                )
                continue

            row_summaries.append(
                {
                    "row_number": str(row_number),
                    "hunt_code": code,
                    "year": str(year),
                    "match_method": match_method,
                }
            )
            for column, new_value in values.items():
                old_value = clean(row.get(column))
                if old_value == clean(new_value):
                    continue
                if column.endswith("_source") and old_value and nonblank(row.get(column)):
                    continue
                row[column] = clean(new_value)
                changes.append(
                    {
                        "row_number": str(row_number),
                        "hunt_code": code,
                        "year": str(year),
                        "match_method": match_method,
                        "column": column,
                        "old_value": old_value,
                        "new_value": clean(new_value),
                    }
                )

    if args.write and changes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / "backups" / f"DATABASE.before_permit_history_population_{stamp}.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DATABASE, backup)
        write_csv(DATABASE, header, rows)

    changes_path = AUDIT_DIR / (
        "database_permit_history_population_applied.csv"
        if args.write
        else "database_permit_history_population_dry_run.csv"
    )
    with changes_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["row_number", "hunt_code", "year", "match_method", "column", "old_value", "new_value"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(changes)

    match_path = AUDIT_DIR / (
        "database_permit_history_match_audit_applied.csv"
        if args.write
        else "database_permit_history_match_audit_dry_run.csv"
    )
    with match_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["row_number", "hunt_code", "year", "match_method"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row_summaries)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write_mode": args.write,
        "database": str(DATABASE.relative_to(ROOT)),
        "years": years,
        "database_rows": len(rows),
        "cell_updates": len(changes),
        "updates_by_column": dict(Counter(change["column"] for change in changes)),
        "matches_by_method": dict(Counter(row["match_method"] for row in row_summaries)),
        "changes_csv": str(changes_path.relative_to(ROOT)),
        "match_audit_csv": str(match_path.relative_to(ROOT)),
    }
    report_path = AUDIT_DIR / (
        "database_permit_history_population_applied_summary.json"
        if args.write
        else "database_permit_history_population_dry_run_summary.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
