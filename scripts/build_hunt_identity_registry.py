#!/usr/bin/env python3
"""Build and apply a stable hunt identity registry.

The registry is intentionally stricter than hunt_code alone.  It uses:
actual_draw_year + hunt_code + species + sex_type + weapon

Boundary ID is validated and backfilled after the biological hunt identity
matches. It is not the primary match key because boundary-only matching already
allowed name drift.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
REGISTRY_PATH = ROOT / "processed_data" / "hunt_identity_registry.csv"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"

IDENTITY_COLUMNS = [
    "actual_draw_year",
    "model_target_year",
    "hunt_code",
    "species",
    "sex_type",
    "weapon",
    "boundary_id",
]

SYNC_COLUMNS = [
    "boundary_id",
    "hunt_name",
]

TEXT_SOURCE_COLUMNS = [
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "draw_design",
    "season",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def norm(value: object) -> str:
    return clean(value).casefold()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, header: list[str], rows: Iterable[dict[str, object] | list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if rows and isinstance(next(iter(rows)), dict):  # type: ignore[arg-type]
            raise RuntimeError("write_csv received an iterator of dicts; materialize before calling")


def write_dict_csv(path: Path, header: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_list_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def canonical_year_from_path(path: Path) -> int | None:
    parts = path.name.split("_")
    if len(parts) > 2 and parts[2].isdigit():
        return int(parts[2])
    return None


def actual_year(row: dict[str, str], fallback: int | None = None) -> str:
    for column in ("actual_draw_year", "draw_year", "year", "source_year"):
        value = clean(row.get(column))
        if value.isdigit():
            return value
    return str(fallback or "")


def model_year(row: dict[str, str], year: str) -> str:
    value = clean(row.get("model_target_year"))
    if value.isdigit():
        return value
    return str(int(year) + 1) if year.isdigit() else ""


def identity_key(row: dict[str, str], year: str | None = None) -> tuple[str, str, str, str, str]:
    yr = year or actual_year(row)
    return (
        yr,
        clean(row.get("hunt_code")).upper(),
        norm(row.get("species")),
        norm(row.get("sex_type")),
        norm(row.get("weapon")),
    )


def code_key(row: dict[str, str], year: str | None = None) -> tuple[str, str]:
    yr = year or actual_year(row)
    return (
        yr,
        clean(row.get("hunt_code")).upper(),
    )


def choose_value(rows: list[dict[str, str]], column: str) -> tuple[str, bool]:
    values = [clean(row.get(column)) for row in rows if clean(row.get(column))]
    if not values:
        return "", False
    counts = Counter(values)
    value, _ = counts.most_common(1)[0]
    normalized = {norm(value) for value in values}
    return value, len(normalized) > 1


def source_row(row: dict[str, str], year: str, source_file: str, source_rank: int) -> dict[str, str]:
    out = {
        "actual_draw_year": year,
        "model_target_year": model_year(row, year),
        "hunt_code": clean(row.get("hunt_code")).upper(),
        "boundary_id": clean(row.get("boundary_id")),
        "source_file": source_file,
        "source_rank": str(source_rank),
    }
    for column in TEXT_SOURCE_COLUMNS:
        out[column] = clean(row.get(column))
    return out


def build_source_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    if DATABASE.exists():
        _, database_rows = read_csv_rows(DATABASE)
        for row in database_rows:
            if clean(row.get("hunt_code")) and clean(row.get("boundary_id")):
                rows.append(source_row(row, "2026", str(DATABASE.relative_to(ROOT)), 0))

    for path in sorted(CANONICAL_DIR.glob("draw_results_*_for_*_canonical_yearly_draw_results.csv")):
        year = canonical_year_from_path(path)
        if year is None:
            continue
        _, canonical_rows = read_csv_rows(path)
        for row in canonical_rows:
            if clean(row.get("hunt_code")) and clean(row.get("boundary_id")):
                rows.append(source_row(row, str(year), str(path.relative_to(ROOT)), 10 + year))

    return rows


@dataclass
class RegistryBuild:
    registry_rows: list[dict[str, object]]
    identity_map: dict[tuple[str, str, str, str, str], dict[str, object]]
    code_map: dict[tuple[str, str], dict[str, object]]
    conflict_rows: list[dict[str, object]]
    source_rows: int


def build_registry() -> RegistryBuild:
    source_rows = build_source_rows()
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        key = identity_key(row, row["actual_draw_year"])
        if all(key[:2]) and all(key[2:]):
            grouped[key].append(row)

    registry_rows: list[dict[str, object]] = []
    identity_map: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    conflict_rows: list[dict[str, object]] = []

    for key, rows in sorted(grouped.items()):
        year, hunt_code, species_norm, sex_norm, weapon_norm = key
        boundary_id, boundary_conflict = choose_value(rows, "boundary_id")
        row_out: dict[str, object] = {
            "identity_key": "|".join(key),
            "actual_draw_year": year,
            "model_target_year": str(int(year) + 1) if year.isdigit() else "",
            "hunt_code": hunt_code,
            "boundary_id": boundary_id,
            "source_row_count": len(rows),
            "source_files": "; ".join(sorted({clean(row.get("source_file")) for row in rows if clean(row.get("source_file"))})[:8]),
        }
        has_conflict = boundary_conflict
        if boundary_conflict:
            conflict_rows.append(
                {
                    "identity_key": row_out["identity_key"],
                    "column": "boundary_id",
                    "values": "; ".join(sorted({clean(row.get("boundary_id")) for row in rows if clean(row.get("boundary_id"))})),
                    "source_files": row_out["source_files"],
                }
            )
        for column in TEXT_SOURCE_COLUMNS:
            value, conflict = choose_value(rows, column)
            row_out[column] = value
            if conflict:
                has_conflict = True
                conflict_rows.append(
                    {
                        "identity_key": row_out["identity_key"],
                        "column": column,
                        "values": "; ".join(sorted({clean(row.get(column)) for row in rows if clean(row.get(column))})),
                        "source_files": row_out["source_files"],
                    }
                )
        row_out["identity_status"] = "field_conflict" if has_conflict else "unique_identity"
        registry_rows.append(row_out)
        identity_map[key] = row_out

    by_code: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in registry_rows:
        by_code[(str(row["actual_draw_year"]), str(row["hunt_code"]))].append(row)

    code_map: dict[tuple[str, str], dict[str, object]] = {}
    for key, candidates in by_code.items():
        if len(candidates) == 1:
            code_map[key] = candidates[0]

    return RegistryBuild(
        registry_rows=registry_rows,
        identity_map=identity_map,
        code_map=code_map,
        conflict_rows=conflict_rows,
        source_rows=len(source_rows),
    )


def registry_header() -> list[str]:
    return [
        "identity_key",
        *IDENTITY_COLUMNS,
        "hunt_name",
        "hunt_type",
        "draw_design",
        "season",
        "source_row_count",
        "source_files",
        "identity_status",
    ]


def target_files() -> list[Path]:
    return [
        CANONICAL_DIR / "draw_results_2023_for_2024_canonical_yearly_draw_results.csv",
        CANONICAL_DIR / "draw_results_2024_for_2025_canonical_yearly_draw_results.csv",
        CANONICAL_DIR / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv",
        CANONICAL_DIR / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2023_for_2024_candidate_promotion_file_records.csv",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2024_for_2025_candidate_promotion_file_records.csv",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2025_for_2026_candidate_promotion_file_records.csv",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2026_for_2027_candidate_promotion_file_records.csv",
        LONG_FILE,
        ROOT / "processed_data" / "hunt-master-canonical-2026-source-of-truth.csv",
        ROOT / "processed_data" / "hunt_master_enriched.csv",
        ROOT / "processed_data" / "hunt_unit_reference_linked.csv",
        ROOT / "processed_data" / "draw_reality_engine_v2.csv",
        ROOT / "processed_data" / "point_ladder_view.csv",
        ROOT / "processed_data" / "library" / "canonical_current_hunts_2026.csv",
        ROOT / "processed_data" / "research_page" / "hunt_application_outlook.csv",
    ]


def target_default_year(path: Path) -> str | None:
    name = path.name
    if "2023_for_2024" in name:
        return "2023"
    if "2024_for_2025" in name:
        return "2024"
    if "2025_for_2026" in name:
        return "2025"
    if "2026_for_2027" in name or "2026" in str(path.relative_to(ROOT)):
        return "2026"
    if path in {
        ROOT / "processed_data" / "hunt_master_enriched.csv",
        ROOT / "processed_data" / "hunt_unit_reference_linked.csv",
        ROOT / "processed_data" / "draw_reality_engine_v2.csv",
        ROOT / "processed_data" / "point_ladder_view.csv",
        ROOT / "processed_data" / "research_page" / "hunt_application_outlook.csv",
    }:
        return "2026"
    return None


def row_year_for_target(path: Path, row: dict[str, str]) -> str:
    if path == LONG_FILE:
        return actual_year(row)
    return actual_year(row, int(target_default_year(path) or "0") or None)


def apply_registry(build: RegistryBuild, write: bool) -> list[dict[str, object]]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    applied: list[list[object]] = []
    conflicts: list[list[object]] = []
    summary: list[dict[str, object]] = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = AUDIT_DIR / "backups"

    for path in target_files():
        if not path.exists():
            summary.append({"path": str(path.relative_to(ROOT)), "status": "missing"})
            continue
        header, rows = read_csv_rows(path)
        if not {"hunt_code", "boundary_id"}.issubset(set(header)):
            summary.append({"path": str(path.relative_to(ROOT)), "status": "missing_required_key_columns"})
            continue

        changed = 0
        considered = 0
        no_match = 0
        conflict_count = 0
        unique_code_candidates = 0
        exact_match = 0

        for row_number, row in enumerate(rows, start=2):
            year = row_year_for_target(path, row)
            if not year:
                no_match += 1
                continue
            if path == LONG_FILE and year not in {"2023", "2024", "2025", "2026"}:
                continue
            considered += 1

            key = identity_key(row, year)
            registry_row = None
            match_kind = ""
            if all(key):
                registry_row = build.identity_map.get(key)
                if registry_row:
                    exact_match += 1
                    match_kind = "exact_identity"

            if registry_row is None:
                if build.code_map.get(code_key(row, year)):
                    unique_code_candidates += 1
                no_match += 1
                continue

            for column in SYNC_COLUMNS:
                if column not in header:
                    continue
                current = clean(row.get(column))
                desired = clean(registry_row.get(column))
                if not desired or current == desired:
                    continue
                row[column] = desired
                changed += 1
                applied.append([str(path.relative_to(ROOT)), row_number, column, row.get("hunt_code"), row.get("boundary_id"), current, desired, match_kind])

        if write and changed:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{path.stem}.before_identity_registry_sync_{stamp}{path.suffix}"
            shutil.copy2(path, backup_path)
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

        summary.append(
            {
                "path": str(path.relative_to(ROOT)),
                "status": "ok",
                "rows": len(rows),
                "considered_rows": considered,
                "exact_identity_matches": exact_match,
                "unique_code_candidates_audited_only": unique_code_candidates,
                "cell_updates": changed,
                "no_registry_match": no_match,
                "conflicts_audited": conflict_count,
            }
        )

    write_list_csv(
        AUDIT_DIR / ("identity_registry_sync_applied.csv" if write else "identity_registry_sync_dry_run.csv"),
        ["path", "row_number", "column", "hunt_code", "boundary_id", "old_value", "new_value", "match_kind"],
        applied,
    )
    write_list_csv(
        AUDIT_DIR / ("identity_registry_sync_conflicts.csv" if write else "identity_registry_sync_dry_run_conflicts.csv"),
        ["path", "row_number", "column", "hunt_code", "boundary_id", "current_value", "registry_value", "match_kind"],
        conflicts,
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Apply safe downstream syncs after building registry.")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    build = build_registry()
    write_dict_csv(REGISTRY_PATH, registry_header(), build.registry_rows)
    write_dict_csv(
        AUDIT_DIR / "hunt_identity_registry_conflicts.csv",
        ["identity_key", "column", "values", "source_files"],
        build.conflict_rows,
    )
    summary = apply_registry(build, write=args.write)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(REGISTRY_PATH.relative_to(ROOT)),
        "source_rows": build.source_rows,
        "registry_rows": len(build.registry_rows),
        "unique_code_keys": len(build.code_map),
        "identity_conflict_cells": len(build.conflict_rows),
        "write_mode": args.write,
        "sync_summary": summary,
    }
    report_path = AUDIT_DIR / ("hunt_identity_registry_apply_summary.json" if args.write else "hunt_identity_registry_dry_run_summary.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
