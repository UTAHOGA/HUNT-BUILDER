#!/usr/bin/env python3
"""Backfill blank boundary_id cells from exact-code boundary sources.

Sources, in conservative order:
- processed_data/boundaries/{hunt_code}.geojson
- pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv
- pipeline/RAW/hunt_unit_database/2026/arcgis/udwr_huntnumber_boundary_table1.json
- processed_data/dwr_huntplanner_hanumber_2026.json, database_boundary_id only

Only blank boundary_id cells are filled. A hunt code is eligible only when all
available sources collapse to one boundary ID. Conflicting codes are skipped.
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DIR = ROOT / "processed_data" / "boundaries"
DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
ARCGIS_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "arcgis" / "udwr_huntnumber_boundary_table1.json"
HUNTPLANNER_PATH = ROOT / "processed_data" / "dwr_huntplanner_hanumber_2026.json"
LONG_PATH = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_DIR = ROOT / "pipeline" / "R2_OFFLOAD" / "incoming"
AUDIT_CSV = AUDIT_DIR / "blank_boundary_id_exact_code_backfill_audit.csv"
SUMMARY_JSON = AUDIT_DIR / "blank_boundary_id_exact_code_backfill_summary.json"


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def add_source(sources: dict[str, list[dict[str, str]]], code: Any, boundary_id: Any, source: str, boundary_name: Any = "") -> None:
    code_text = clean(code).upper()
    boundary_id_text = clean(boundary_id)
    if not code_text or not boundary_id_text:
        return
    sources[code_text].append(
        {
            "boundary_id": boundary_id_text,
            "source": source,
            "boundary_name": clean(boundary_name),
        }
    )


def first_feature_properties(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    features = data.get("features") or []
    if features and isinstance(features[0], dict):
        return dict(features[0].get("properties") or {})
    return dict(data.get("properties") or {})


def build_boundary_sources() -> tuple[dict[str, str], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    sources: dict[str, list[dict[str, str]]] = defaultdict(list)

    for path in BOUNDARY_DIR.glob("*.geojson"):
        try:
            props = first_feature_properties(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        add_source(
            sources,
            path.stem,
            props.get("boundary_id") or props.get("BoundaryID") or props.get("BOUNDARYID"),
            "direct_geojson",
            props.get("boundary_name") or props.get("Boundary_Name") or props.get("BOUNDARY_NAME"),
        )

    if DATABASE_PATH.exists():
        _, rows = read_csv(DATABASE_PATH)
        for row in rows:
            add_source(sources, row.get("hunt_code"), row.get("boundary_id"), "database_csv", row.get("hunt_name"))

    if ARCGIS_PATH.exists():
        data = json.loads(ARCGIS_PATH.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            attrs = feature.get("attributes") or {}
            add_source(
                sources,
                attrs.get("HUNT_NUMBER"),
                attrs.get("BOUNDARYID"),
                "arcgis_huntnumber_boundary_table",
                attrs.get("BOUNDARY_NAME"),
            )

    if HUNTPLANNER_PATH.exists():
        rows = json.loads(HUNTPLANNER_PATH.read_text(encoding="utf-8"))
        for row in rows:
            add_source(
                sources,
                row.get("hunt_code"),
                row.get("database_boundary_id"),
                "huntplanner_database_boundary_id",
                row.get("database_hunt_name") or row.get("dwr_hunt_name"),
            )

    single: dict[str, str] = {}
    conflicts: dict[str, list[dict[str, str]]] = {}
    for code, entries in sources.items():
        ids = {entry["boundary_id"] for entry in entries if entry["boundary_id"]}
        if len(ids) == 1:
            single[code] = next(iter(ids))
        elif len(ids) > 1:
            conflicts[code] = entries
    return single, sources, conflicts


def target_paths() -> list[Path]:
    return [LONG_PATH] + sorted(CANONICAL_DIR.glob("draw_results_20*_canonical_yearly_draw_results.csv"))


def backfill_file(
    path: Path,
    id_by_code: dict[str, str],
    sources_by_code: dict[str, list[dict[str, str]]],
) -> tuple[int, int, list[dict[str, Any]], str]:
    headers, rows = read_csv(path)
    if "boundary_id" not in headers or "hunt_code" not in headers:
        return 0, 0, [], ""

    changed = 0
    remaining_blank = 0
    audit_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        if clean(row.get("boundary_id")):
            continue
        code = clean(row.get("hunt_code")).upper()
        if not code:
            remaining_blank += 1
            continue
        boundary_id = id_by_code.get(code, "")
        if not boundary_id:
            remaining_blank += 1
            continue
        row["boundary_id"] = boundary_id
        changed += 1
        source_entries = sources_by_code.get(code, [])
        audit_rows.append(
            {
                "target_file": str(path),
                "row_number": row_number,
                "actual_draw_year": clean(row.get("actual_draw_year") or row.get("year")),
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "weapon": clean(row.get("weapon")),
                "old_boundary_id": "",
                "new_boundary_id": boundary_id,
                "source_names": "|".join(sorted({entry["source"] for entry in source_entries})),
                "source_boundary_names": "|".join(sorted({entry["boundary_name"] for entry in source_entries if entry["boundary_name"]})),
                "action": "FILLED",
                "reason": "blank boundary_id filled from exact hunt_code sources with one unambiguous boundary_id",
            }
        )

    if changed:
        try:
            write_csv(path, headers, rows)
        except PermissionError as exc:
            tmp = path.with_suffix(path.suffix + ".tmp")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return 0, remaining_blank + changed, [], str(exc)
    return changed, remaining_blank, audit_rows, ""


def main() -> None:
    id_by_code, sources_by_code, conflicts = build_boundary_sources()
    audit_rows: list[dict[str, Any]] = []
    changed_by_file: dict[str, int] = {}
    remaining_by_file: dict[str, int] = {}
    write_failures: dict[str, str] = {}
    for path in target_paths():
        if not path.exists():
            continue
        changed, remaining, file_audit, write_error = backfill_file(path, id_by_code, sources_by_code)
        if write_error:
            write_failures[str(path)] = write_error
        if changed or remaining:
            changed_by_file[str(path)] = changed
            remaining_by_file[str(path)] = remaining
        audit_rows.extend(file_audit)

    audit_fields = [
        "target_file",
        "row_number",
        "actual_draw_year",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "old_boundary_id",
        "new_boundary_id",
        "source_names",
        "source_boundary_names",
        "action",
        "reason",
    ]
    write_csv(AUDIT_CSV, audit_fields, audit_rows)
    summary = {
        "source_code_count": len(sources_by_code),
        "single_boundary_source_code_count": len(id_by_code),
        "conflicting_source_code_count": len(conflicts),
        "rows_filled_total": len(audit_rows),
        "rows_filled_by_file": changed_by_file,
        "remaining_blank_boundary_rows_by_file": remaining_by_file,
        "write_failures": write_failures,
        "conflicting_source_codes_sample": sorted(conflicts)[:50],
        "audit_csv": str(AUDIT_CSV),
        "note": "Only blank boundary_id cells were filled. Nonblank boundary_id values were not changed.",
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
