#!/usr/bin/env python3
"""Safely sync 2023 canonical rows from the corrected DATABASE.csv.

Rules:
- Match DATABASE rows to 2023 draw-result rows by hunt_code + species + sex_type + weapon.
- Only update hunt_name/boundary_id from exact identity matches.
- Add/populate permits_2023_res, permits_2023_nr, permits_2023_total from existing
  row-level permit columns, grouped by hunt_code.
- Apply the same 2023 slice updates to draw_results_long.csv.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CANONICAL_2023 = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2023_for_2024_canonical_yearly_draw_results.csv"
)
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def norm(value: object) -> str:
    return clean(value).casefold()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def identity_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        norm(row.get("species")),
        norm(row.get("sex_type") or row.get("sex")),
        norm(row.get("weapon")),
    )


def number(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def build_database_map() -> dict[tuple[str, str, str, str], dict[str, str]]:
    _, rows = read_csv(DATABASE)
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = identity_key(row)
        if all(key):
            grouped[key].append(row)
    return {key: matches[0] for key, matches in grouped.items() if len(matches) == 1}


def ensure_permit_columns(header: list[str]) -> list[str]:
    wanted = ["permits_2023_res", "permits_2023_nr", "permits_2023_total"]
    if all(column in header for column in wanted):
        return header

    new_header = list(header)
    insert_after = "permits_year_total" if "permits_year_total" in new_header else "total_permits"
    insert_at = new_header.index(insert_after) + 1 if insert_after in new_header else len(new_header)
    for column in reversed(wanted):
        if column not in new_header:
            new_header.insert(insert_at, column)
    return new_header


def hunt_totals(rows: list[dict[str, str]]) -> dict[str, tuple[str, str, str]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        res = number(row.get("resident_total_permits"))
        nr = number(row.get("nonresident_total_permits"))
        totals[code][0] += res or 0
        totals[code][1] += nr or 0
    return {code: (str(res), str(nr), str(res + nr)) for code, (res, nr) in totals.items()}


def sync_rows(
    path: Path,
    header: list[str],
    rows: list[dict[str, str]],
    database_map: dict[tuple[str, str, str, str], dict[str, str]],
    write: bool,
) -> tuple[list[str], list[dict[str, str]], dict[str, object], list[dict[str, object]]]:
    is_long = path == LONG_FILE
    target_rows = [row for row in rows if clean(row.get("actual_draw_year")) == "2023"] if is_long else rows
    totals = hunt_totals(target_rows)
    new_header = ensure_permit_columns(header)
    changes: list[dict[str, object]] = []
    exact_matches = 0
    code_only = 0
    no_match = 0
    database_codes = {key[0] for key in database_map}

    for row_number, row in enumerate(rows, start=2):
        if is_long and clean(row.get("actual_draw_year")) != "2023":
            continue

        key = identity_key(row)
        db_row = database_map.get(key)
        if db_row:
            exact_matches += 1
            for column in ("hunt_name", "boundary_id"):
                if column not in new_header:
                    continue
                current = clean(row.get(column))
                desired = clean(db_row.get(column))
                if desired and current != desired:
                    row[column] = desired
                    changes.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "row_number": row_number,
                            "hunt_code": clean(row.get("hunt_code")).upper(),
                            "column": column,
                            "old_value": current,
                            "new_value": desired,
                            "match_kind": "database_exact_identity",
                        }
                    )
        elif clean(row.get("hunt_code")).upper() in database_codes:
            code_only += 1
        else:
            no_match += 1

        code = clean(row.get("hunt_code")).upper()
        if code in totals:
            for column, desired in zip(
                ("permits_2023_res", "permits_2023_nr", "permits_2023_total"),
                totals[code],
            ):
                current = clean(row.get(column))
                if current != desired:
                    row[column] = desired
                    changes.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "row_number": row_number,
                            "hunt_code": code,
                            "column": column,
                            "old_value": current,
                            "new_value": desired,
                            "match_kind": "hunt_code_sum_from_row_level_permits",
                        }
                    )

    summary = {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "target_2023_rows": len(target_rows),
        "exact_database_identity_matches": exact_matches,
        "code_only_not_applied": code_only,
        "no_database_code_match": no_match,
        "cell_updates": len(changes),
        "updates_by_column": dict(Counter(str(change["column"]) for change in changes)),
        "write_mode": write,
    }
    return new_header, rows, summary, changes


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    database_map = build_database_map()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    summaries: list[dict[str, object]] = []
    all_changes: list[dict[str, object]] = []
    for path in (CANONICAL_2023, LONG_FILE):
        header, rows = read_csv(path)
        new_header, new_rows, summary, changes = sync_rows(path, header, rows, database_map, args.write)
        summaries.append(summary)
        all_changes.extend(changes)
        if args.write and changes:
            backup = AUDIT_DIR / "backups" / f"{path.stem}.before_2023_database_sync_{stamp}{path.suffix}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            write_csv(path, new_header, new_rows)

    changes_path = AUDIT_DIR / (
        "draw_results_2023_for_2024_database_sync_applied.csv"
        if args.write
        else "draw_results_2023_for_2024_database_sync_dry_run.csv"
    )
    with changes_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["path", "row_number", "hunt_code", "column", "old_value", "new_value", "match_kind"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_changes)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(DATABASE.relative_to(ROOT)),
        "database_unique_identity_keys": len(database_map),
        "write_mode": args.write,
        "summaries": summaries,
        "changes_csv": str(changes_path.relative_to(ROOT)),
    }
    report_path = AUDIT_DIR / (
        "draw_results_2023_for_2024_database_sync_applied_summary.json"
        if args.write
        else "draw_results_2023_for_2024_database_sync_dry_run_summary.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
