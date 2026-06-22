#!/usr/bin/env python3
"""Backfill 2022/2023 canonical metadata from exact trusted hunt-code matches.

This intentionally does not rewrite hunt_name. It only fills blank metadata
fields where a single unambiguous value exists for the same hunt_code in newer
standardized canonical years or DATABASE.csv.
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
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_DIR = ROOT / "audits" / "dwr_table_shape_canonical_rebuild" / "metadata_backfill_2022_2023"
BACKUP_DIR = AUDIT_DIR / "backups"

TARGET_YEARS = [2022, 2023]
TRUSTED_CANONICAL_YEARS = [2024, 2025, 2026]
FIELDS_TO_FILL = [
    "boundary_id",
    "species",
    "sex_type",
    "hunt_type",
    "draw_design",
    "weapon",
]

DATABASE_FIELD_MAP = {
    "boundary_id": "boundary_id",
    "species": "species",
    "sex_type": "sex_type",
    "hunt_type": "hunt_type",
    "weapon": "weapon",
}

DRAW_DESIGN_BY_DATABASE_SYSTEM = {
    "BONUS_CWMU_BIG_GAME": "Max/Weighted Split",
    "BONUS_LE_BIG_GAME": "Max/Weighted Split",
    "BONUS_OIL_BIG_GAME": "Max/Weighted Split",
    "BONUS_TURKEY": "Preference",
    "PREFERENCE_ANTLERLESS": "Preference",
    "PREFERENCE_DEDICATED_HUNTER_DEER": "Preference",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER": "Preference",
    "SPORTSMAN_RANDOM_ONLY": "Random",
    "OTC_CAPPED_PERMITS": "Capped Permits",
    "OTC_UNLIMITED": "Unlimited",
}


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def add_candidate(
    candidates: dict[str, dict[str, Counter[tuple[str, str]]]],
    code: str,
    field: str,
    value: str,
    source: str,
) -> None:
    if code and field and value:
        candidates[code][field][(value, source)] += 1


def build_trusted_candidates() -> dict[str, dict[str, Counter[tuple[str, str]]]]:
    candidates: dict[str, dict[str, Counter[tuple[str, str]]]] = defaultdict(lambda: defaultdict(Counter))

    for year in TRUSTED_CANONICAL_YEARS:
        _, rows = read_csv(canonical_path(year))
        for row in rows:
            code = clean(row.get("hunt_code")).upper()
            if not code:
                continue
            for field in FIELDS_TO_FILL:
                add_candidate(
                    candidates,
                    code,
                    field,
                    clean(row.get(field)),
                    f"canonical_{year}",
                )

    _, db_rows = read_csv(DATABASE)
    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        for target_field, db_field in DATABASE_FIELD_MAP.items():
            add_candidate(candidates, code, target_field, clean(row.get(db_field)), "DATABASE.csv")
        system_type = clean(row.get("draw_2026_system_type"))
        add_candidate(
            candidates,
            code,
            "draw_design",
            DRAW_DESIGN_BY_DATABASE_SYSTEM.get(system_type, ""),
            f"DATABASE.csv:draw_2026_system_type={system_type}",
        )

    return candidates


def choose_unique(
    counter: Counter[tuple[str, str]],
) -> tuple[str, str, str]:
    values: dict[str, Counter[str]] = defaultdict(Counter)
    for (value, source), count in counter.items():
        values[value][source] += count
    if len(values) != 1:
        return "", "", "ambiguous"
    value = next(iter(values.keys()))
    source_counts = values[value]
    source = "; ".join(f"{name}({count})" for name, count in sorted(source_counts.items()))
    return value, source, "single_value_exact_hunt_code"


def blank_counts(rows: list[dict[str, str]], fields: list[str]) -> dict[str, int]:
    return {field: sum(1 for row in rows if not clean(row.get(field))) for field in fields}


def process_year(
    year: int,
    candidates: dict[str, dict[str, Counter[tuple[str, str]]]],
    *,
    write: bool,
) -> dict[str, object]:
    path = canonical_path(year)
    fieldnames, rows = read_csv(path)
    audit_rows: list[dict[str, str]] = []
    ambiguous_rows: list[dict[str, str]] = []
    before = blank_counts(rows, FIELDS_TO_FILL)

    for index, row in enumerate(rows, start=2):
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        for field in FIELDS_TO_FILL:
            if field not in fieldnames or clean(row.get(field)):
                continue
            value, source, status = choose_unique(candidates.get(code, {}).get(field, Counter()))
            if value:
                audit_rows.append(
                    {
                        "year": str(year),
                        "row_number": str(index),
                        "hunt_code": code,
                        "points": clean(row.get("points")),
                        "record_type": clean(row.get("record_type")),
                        "field": field,
                        "old_value": "",
                        "new_value": value,
                        "source": source,
                        "status": status,
                    }
                )
                row[field] = value
            elif status == "ambiguous":
                values = sorted({value for value, _source in candidates.get(code, {}).get(field, Counter())})
                ambiguous_rows.append(
                    {
                        "year": str(year),
                        "row_number": str(index),
                        "hunt_code": code,
                        "points": clean(row.get("points")),
                        "record_type": clean(row.get("record_type")),
                        "field": field,
                        "candidate_values": " | ".join(values),
                    }
                )

    after = blank_counts(rows, FIELDS_TO_FILL)
    if write and audit_rows:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"{path.stem}.before_metadata_backfill_{stamp}{path.suffix}"
        shutil.copy2(path, backup)
        write_csv(path, fieldnames, rows)
    else:
        backup = None

    return {
        "year": year,
        "write": write,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/") if backup else "",
        "rows": len(rows),
        "cell_changes": len(audit_rows),
        "ambiguous_blank_cells": len(ambiguous_rows),
        "blank_counts_before": before,
        "blank_counts_after": after,
        "audit_rows": audit_rows,
        "ambiguous_rows": ambiguous_rows,
    }


def write_audit(name: str, rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = build_trusted_candidates()
    summaries = [process_year(year, candidates, write=args.write) for year in TARGET_YEARS]

    audit_rows = [row for summary in summaries for row in summary.pop("audit_rows")]
    ambiguous_rows = [row for summary in summaries for row in summary.pop("ambiguous_rows")]
    audit_path = write_audit(
        "metadata_backfill_audit.csv",
        audit_rows,
        ["year", "row_number", "hunt_code", "points", "record_type", "field", "old_value", "new_value", "source", "status"],
    )
    ambiguous_path = write_audit(
        "metadata_backfill_ambiguous_candidates.csv",
        ambiguous_rows,
        ["year", "row_number", "hunt_code", "points", "record_type", "field", "candidate_values"],
    )
    summary = {
        "write": args.write,
        "target_years": TARGET_YEARS,
        "trusted_canonical_years": TRUSTED_CANONICAL_YEARS,
        "database": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
        "audit_path": audit_path,
        "ambiguous_path": ambiguous_path,
        "summaries": summaries,
        "changes_by_field": dict(Counter(row["field"] for row in audit_rows)),
        "ambiguous_by_field": dict(Counter(row["field"] for row in ambiguous_rows)),
    }
    (AUDIT_DIR / "metadata_backfill_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
