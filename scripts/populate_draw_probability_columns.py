#!/usr/bin/env python3
"""Populate missing p_draw columns from canonical draw-result evidence.

For each requested actual draw year, this updates both the yearly canonical CSV
and that year's slice of draw_results_long.csv. It does not fabricate odds for
rows with no applicant denominator.
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
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_probability(value: float) -> str:
    value = max(0.0, min(1.0, value))
    return f"{value:.10g}"


def format_percent(value: float) -> str:
    return f"{value * 100:.10g}"


def probability_from_ratio(value: object) -> float | None:
    ratio = clean(value)
    if not ratio or ratio.upper() == "N/A" or "in" not in ratio.lower():
        return None
    try:
        denominator = float(ratio.lower().split("in", 1)[1].strip().replace(",", ""))
    except ValueError:
        return None
    return 1 / denominator if denominator > 0 else None


def permit_count(row: dict[str, str], prefix: str) -> float | None:
    if prefix == "total":
        direct_total = to_float(row.get("total_permits"))
        if direct_total is not None:
            return direct_total
    direct = to_float(row.get(f"{prefix}_total_permits"))
    if direct is not None:
        return direct
    bonus = to_float(row.get(f"{prefix}_bonus_permits"))
    regular = to_float(row.get(f"{prefix}_regular_permits"))
    if bonus is not None or regular is not None:
        return (bonus or 0) + (regular or 0)
    return None


def derive_probability(row: dict[str, str], prefix: str) -> float | None:
    # Applicants/permits are the strongest evidence and avoid mixed legacy
    # units where some old p_draw values were already percent-style values.
    applicants = to_float(row.get(f"{prefix}_eligible_applicants"))
    permits = permit_count(row, prefix)
    if applicants is not None and permits is not None:
        if applicants > 0:
            return permits / applicants
        if permits == 0:
            return None

    ratio_probability = probability_from_ratio(row.get(f"{prefix}_success_ratio"))
    if ratio_probability is not None:
        return ratio_probability

    percent = to_float(row.get(f"{prefix}_p_draw_percent"))
    if percent is not None:
        return percent / 100

    existing = to_float(row.get(f"{prefix}_p_draw"))
    if existing is not None:
        return existing / 100 if existing > 1 else existing

    return None


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
    for row_number, row in enumerate(rows, start=2):
        if path == LONG_FILE and clean(row.get("actual_draw_year")) != str(year):
            continue
        target_rows += 1
        for prefix in ("resident", "nonresident", "total"):
            p_col = f"{prefix}_p_draw"
            pct_col = f"{prefix}_p_draw_percent"
            if p_col not in header:
                continue
            probability = derive_probability(row, prefix)
            if probability is None:
                continue
            desired = format_probability(probability)
            current = clean(row.get(p_col))
            if current != desired:
                row[p_col] = desired
                changes.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "row_number": row_number,
                        "actual_draw_year": year,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "column": p_col,
                        "old_value": current,
                        "new_value": desired,
                    }
                )
            if pct_col in header and not clean(row.get(pct_col)):
                pct = format_percent(probability)
                row[pct_col] = pct
                changes.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "row_number": row_number,
                        "actual_draw_year": year,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "column": pct_col,
                        "old_value": "",
                        "new_value": pct,
                    }
                )

    if write and changes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / "backups" / f"{path.stem}.before_p_draw_population_{year}_{stamp}{path.suffix}"
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
        "draw_probability_population_applied.csv" if args.write else "draw_probability_population_dry_run.csv"
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
        "draw_probability_population_applied_summary.json"
        if args.write
        else "draw_probability_population_dry_run_summary.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
