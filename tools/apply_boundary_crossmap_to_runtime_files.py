#!/usr/bin/env python3
"""Apply reviewed hunt_code -> boundary_id mappings to allowed runtime files."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TARGET_CODES = {"DA1051", "EA1295", "EA1299", "EA1300"}


CSV_TARGETS = [
    Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"),
    Path("processed_data/hunt_unit_reference_linked.csv"),
]

JSON_TARGETS = [
    Path("data/hunt-master-canonical-2026-source-of-truth.json"),
    Path("data/hunt-master-canonical-2026-foundation.json"),
    Path("processed_data/hunt_research_2026_summary.json"),
]

SPLIT_HUNT_DIR = Path("processed_data/hunt_research_2026_split/hunts")


def norm(value: Any) -> str:
    return str(value or "").strip().upper()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def records_ref(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("records", "hunts", "rows", "data"):
            if isinstance(data.get(key), list):
                return [row for row in data[key] if isinstance(row, dict)]
    return []


def load_boundary_map(root: Path, target_codes: set[str]) -> dict[str, dict[str, str]]:
    index = read_json(root / "processed_data/display-boundary-index-2026.json")
    rows = records_ref(index)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        code = norm(row.get("hunt_code"))
        if code not in target_codes:
            continue
        boundary_id = str(row.get("boundary_id") or "").strip()
        if not boundary_id:
            continue
        result[code] = {
            "boundary_id": boundary_id,
            "boundary_geojson_path": str(row.get("boundary_geojson_path") or "").strip(),
            "boundary_kmz_path": str(row.get("boundary_kmz_path") or "").strip(),
            "boundary_kml_path": str(row.get("boundary_kml_path") or "").strip(),
            "boundary_source_file": str(row.get("boundary_source_file") or "").strip(),
        }
    missing = sorted(target_codes - set(result))
    if missing:
        raise SystemExit(f"Missing reviewed boundary-index rows for: {', '.join(missing)}")
    return result


def update_csv(
    path: Path,
    boundary_map: dict[str, dict[str, str]],
    ledger: list[dict[str, Any]],
    root: Path,
    resolve_conflicts: bool,
) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if "hunt_code" not in fieldnames or "boundary_id" not in fieldnames:
        return
    changed = False
    for index, row in enumerate(rows, start=2):
        code = norm(row.get("hunt_code"))
        if code not in boundary_map:
            continue
        before = str(row.get("boundary_id") or "")
        after = boundary_map[code]["boundary_id"]
        if before == after:
            continue
        if before.strip() and not resolve_conflicts:
            continue
        row["boundary_id"] = after
        changed = True
        ledger.append(mutation(path, index, code, "boundary_id", before, after, boundary_map[code], root))
    if changed:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(path)


def update_json_records(
    path: Path,
    boundary_map: dict[str, dict[str, str]],
    ledger: list[dict[str, Any]],
    root: Path,
    resolve_conflicts: bool,
) -> None:
    if not path.exists():
        return
    data = read_json(path)
    rows = records_ref(data)
    changed = False
    for index, row in enumerate(rows, start=1):
        code = norm(row.get("hunt_code"))
        if code not in boundary_map:
            continue
        for field in ("boundary_id", "boundaryId", "boundaryID", "BoundaryID", "boundary_id_numeric"):
            if field not in row:
                continue
            before = str(row.get(field) or "")
            after = boundary_map[code]["boundary_id"]
            if before == after or (before.strip() and not resolve_conflicts):
                continue
            row[field] = after
            changed = True
            ledger.append(mutation(path, index, code, field, before, after, boundary_map[code], root))
        for field, map_key in (
            ("boundary_geojson_path", "boundary_geojson_path"),
            ("boundary_kmz_path", "boundary_kmz_path"),
            ("boundary_kml_path", "boundary_kml_path"),
            ("boundary_source_file", "boundary_source_file"),
        ):
            if field not in row:
                continue
            before = str(row.get(field) or "")
            after = boundary_map[code].get(map_key, "")
            if not after or before == after or before.strip():
                continue
            row[field] = after
            changed = True
            ledger.append(mutation(path, index, code, field, before, after, boundary_map[code], root))
    if changed:
        write_json(path, data)


def update_split_hunts(
    root: Path,
    boundary_map: dict[str, dict[str, str]],
    ledger: list[dict[str, Any]],
    resolve_conflicts: bool,
) -> None:
    for code in sorted(boundary_map):
        path = root / SPLIT_HUNT_DIR / f"{code}.json"
        if not path.exists():
            continue
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        changed = False
        for field in ("boundary_id", "boundaryId", "boundaryID", "BoundaryID", "boundary_id_numeric"):
            if field not in data:
                continue
            before = str(data.get(field) or "")
            after = boundary_map[code]["boundary_id"]
            if before == after or (before.strip() and not resolve_conflicts):
                continue
            data[field] = after
            changed = True
            ledger.append(mutation(path, 1, code, field, before, after, boundary_map[code], root))
        for field, map_key in (
            ("boundary_geojson_path", "boundary_geojson_path"),
            ("boundary_kmz_path", "boundary_kmz_path"),
            ("boundary_kml_path", "boundary_kml_path"),
            ("boundary_source_file", "boundary_source_file"),
        ):
            before = str(data.get(field) or "")
            after = boundary_map[code].get(map_key, "")
            if not after or before == after or before.strip():
                continue
            data[field] = after
            changed = True
            ledger.append(mutation(path, 1, code, field, before, after, boundary_map[code], root))
        if changed:
            write_json(path, data)


def mutation(
    path: Path,
    row_number: int,
    code: str,
    field: str,
    before: str,
    after: str,
    source: dict[str, str],
    root: Path,
) -> dict[str, Any]:
    rel = path.resolve().relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return {
        "target_file": rel,
        "target_row_number": row_number,
        "hunt_code": code,
        "field": field,
        "before_value": before,
        "after_value": after,
        "source_file": source.get("boundary_source_file", ""),
        "source_boundary_geojson_path": source.get("boundary_geojson_path", ""),
        "rule_name": "reviewed_kmz_boundary_crossmap",
        "reason": "Boundary ID extracted from reviewed DWR KMZ-derived boundary index row.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default="audits/boundary_runtime")
    parser.add_argument("--codes", nargs="*", default=sorted(DEFAULT_TARGET_CODES))
    parser.add_argument("--resolve-conflicts", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    target_codes = {norm(code) for code in args.codes if norm(code)}
    boundary_map = load_boundary_map(root, target_codes)
    ledger: list[dict[str, Any]] = []

    for target in CSV_TARGETS:
        update_csv(root / target, boundary_map, ledger, root, args.resolve_conflicts)
    for target in JSON_TARGETS:
        update_json_records(root / target, boundary_map, ledger, root, args.resolve_conflicts)
    update_split_hunts(root, boundary_map, ledger, args.resolve_conflicts)

    fieldnames = [
        "target_file",
        "target_row_number",
        "hunt_code",
        "field",
        "before_value",
        "after_value",
        "source_file",
        "source_boundary_geojson_path",
        "rule_name",
        "reason",
    ]
    ledger_csv = out_dir / "boundary_crossmap_runtime_apply_ledger.csv"
    with ledger_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ledger)

    summary = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "target_codes": sorted(boundary_map),
        "mutations": len(ledger),
        "ledger_csv": str(ledger_csv.relative_to(root)),
        "files_changed": sorted({row["target_file"] for row in ledger}),
    }
    (out_dir / "boundary_crossmap_runtime_apply_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Boundary Crossmap Runtime Apply",
        "",
        f"- Mutations: `{len(ledger)}`",
        f"- Target codes: `{', '.join(sorted(boundary_map))}`",
        "",
        "## Files Changed",
        "",
    ]
    for file in summary["files_changed"]:
        lines.append(f"- `{file}`")
    (out_dir / "boundary_crossmap_runtime_apply_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
