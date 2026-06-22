#!/usr/bin/env python3
"""Populate permits_<year>_res/nr/total in canonical yearly and long files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"


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


def numeric(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def target_path_for_year(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def ensure_columns(header: list[str], year: int) -> list[str]:
    wanted = [f"permits_{year}_res", f"permits_{year}_nr", f"permits_{year}_total"]
    if all(column in header for column in wanted):
        return header
    out = list(header)
    insert_after = "permits_year_total" if "permits_year_total" in out else "total_p_draw_percent"
    insert_at = out.index(insert_after) + 1 if insert_after in out else len(out)
    for column in reversed(wanted):
        if column not in out:
            out.insert(insert_at, column)
    return out


def build_hunt_totals(rows: list[dict[str, str]]) -> dict[str, tuple[str, str, str]]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        res = numeric(row.get("resident_total_permits"))
        nr = numeric(row.get("nonresident_total_permits"))
        totals[code][0] += res or 0
        totals[code][1] += nr or 0
    return {code: (str(res), str(nr), str(res + nr)) for code, (res, nr) in totals.items()}


def desired_permits(row: dict[str, str], hunt_totals: dict[str, tuple[str, str, str]]) -> tuple[str, str, str]:
    generic = (
        clean(row.get("permits_year_res")),
        clean(row.get("permits_year_nr")),
        clean(row.get("permits_year_total")),
    )
    if any(generic):
        res = generic[0] or "0"
        nr = generic[1] or "0"
        total = generic[2]
        if not total:
            total = str((numeric(res) or 0) + (numeric(nr) or 0))
        return res, nr, total
    code = clean(row.get("hunt_code")).upper()
    return hunt_totals.get(code, ("", "", ""))


def update_file(path: Path, year: int, write: bool) -> tuple[list[dict[str, object]], dict[str, object]]:
    header, rows = read_csv(path)
    new_header = ensure_columns(header, year)
    target_rows = [row for row in rows if path != LONG_FILE or clean(row.get("actual_draw_year")) == str(year)]
    totals = build_hunt_totals(target_rows)
    changes: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        if path == LONG_FILE and clean(row.get("actual_draw_year")) != str(year):
            continue
        desired = desired_permits(row, totals)
        for column, value in zip((f"permits_{year}_res", f"permits_{year}_nr", f"permits_{year}_total"), desired):
            if value == "":
                continue
            current = clean(row.get(column))
            if current != value:
                row[column] = value
                changes.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "row_number": row_number,
                        "actual_draw_year": year,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "column": column,
                        "old_value": current,
                        "new_value": value,
                    }
                )

    if write and changes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / "backups" / f"{path.stem}.before_year_specific_permits_{year}_{stamp}{path.suffix}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        write_csv(path, new_header, rows)

    return changes, {
        "path": str(path.relative_to(ROOT)),
        "actual_draw_year": year,
        "target_rows": len(target_rows),
        "cell_updates": len(changes),
        "updates_by_column": dict(Counter(str(change["column"]) for change in changes)),
    }


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
            changes, summary = update_file(path, year, args.write)
            all_changes.extend(changes)
            summaries.append(summary)

    changes_path = AUDIT_DIR / (
        "year_specific_permit_population_applied.csv" if args.write else "year_specific_permit_population_dry_run.csv"
    )
    with changes_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["path", "row_number", "actual_draw_year", "hunt_code", "column", "old_value", "new_value"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
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
        "year_specific_permit_population_applied_summary.json"
        if args.write
        else "year_specific_permit_population_dry_run_summary.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
