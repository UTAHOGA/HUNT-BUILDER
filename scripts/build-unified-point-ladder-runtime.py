#!/usr/bin/env python3
"""Build a unified point ladder runtime candidate.

Default behavior is non-mutating: write only to data_model/runtime_drafts and
an audit CSV. Production promotion requires --promote.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ALLOCATION = Path("data_model/runtime_drafts/point_ladder_allocation_complete_v2026.csv")
RUNTIME = Path("data_model/runtime_drafts/point_ladder_runtime_actual_draw_v2026.csv")
OUTPUT = Path("data_model/runtime_drafts/point_ladder_unified_runtime_v2026.csv")
AUDIT = Path("audits/prediction_engine_full_audit/point_ladder_unified_join_audit.csv")
PRODUCTION = Path("processed_data/point_ladder_view.csv")

KEY_FIELDS = ["hunt_code", "residency", "points"]
COMPAT_FIELDS = ["hunt_type", "hunt_class"]
RUNTIME_PREFERRED_FIELDS = {
    "draw_pool",
    "actual_applicants_2025",
    "actual_bonus_permits_2025",
    "actual_regular_permits_2025",
    "actual_total_permits_2025",
    "odds_2025_actual",
    "projected_applicants_2026",
    "projected_nonwinners_2025",
    "projected_points_2026",
    "max_pool_projection_2026",
    "ladder_status",
    "source_file",
    "source_sha256",
    "validation_status",
    "validation_notes",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def normalize(value: object) -> str:
    return str(value or "").strip()


def normalize_residency(value: object) -> str:
    lowered = normalize(value).lower()
    if lowered in {"res", "resident"}:
        return "Resident"
    if lowered in {"nr", "nonresident", "non-resident", "non resident"}:
        return "Nonresident"
    if lowered in {"all", "both"}:
        return "All"
    return normalize(value)


def normalize_points(value: object) -> str:
    text = normalize(value)
    try:
        parsed = float(text)
    except ValueError:
        return text
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def safe_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize(row.get("hunt_code")).upper(),
        normalize_residency(row.get("residency")),
        normalize_points(row.get("points") or row.get("point")),
    )


def compatible(base: dict[str, str], runtime: dict[str, str]) -> bool:
    for field in COMPAT_FIELDS:
        left = normalize(base.get(field)).lower()
        right = normalize(runtime.get(field)).lower()
        if left and right and left != right:
            return False
    return True


def ordered_fields(allocation_fields: list[str], runtime_fields: list[str]) -> list[str]:
    fields: list[str] = []
    for field in allocation_fields + runtime_fields + ["unified_join_status", "unified_join_note"]:
        if field not in fields:
            fields.append(field)
    return fields


def merge_rows(allocation_rows: list[dict[str, str]], runtime_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    runtime_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in runtime_rows:
        key = safe_key(row)
        if key[0]:
            runtime_by_key.setdefault(key, []).append(row)

    output: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    emitted_runtime_ids: set[int] = set()

    for base in allocation_rows:
        key = safe_key(base)
        matches = [row for row in runtime_by_key.get(key, []) if compatible(base, row)]
        if not matches:
            merged = dict(base)
            if not normalize(merged.get("draw_pool")):
                merged["draw_pool"] = "standard"
            merged["unified_join_status"] = "allocation_only"
            merged["unified_join_note"] = "No compatible runtime actual-draw row found."
            output.append(merged)
            audit.append(make_audit_row(base, None, "allocation_only", "No compatible runtime actual-draw row found."))
            continue

        for match in matches:
            merged = dict(base)
            for field, value in match.items():
                if field in RUNTIME_PREFERRED_FIELDS or not normalize(merged.get(field)):
                    merged[field] = value
            if not normalize(merged.get("draw_pool")):
                merged["draw_pool"] = "standard"
            merged["unified_join_status"] = "joined"
            merged["unified_join_note"] = "Allocation/completeness row joined to compatible runtime actual-draw row."
            output.append(merged)
            audit.append(make_audit_row(base, match, "joined", "Compatible safe-key join."))
            emitted_runtime_ids.add(id(match))

    for row in runtime_rows:
        if id(row) in emitted_runtime_ids:
            continue
        merged = dict(row)
        merged["unified_join_status"] = "runtime_only"
        merged["unified_join_note"] = "Runtime actual-draw row had no allocation/completeness match."
        output.append(merged)
        audit.append(make_audit_row(None, row, "runtime_only", "Runtime row preserved without allocation match."))

    return output, audit


def make_audit_row(
    allocation: dict[str, str] | None,
    runtime: dict[str, str] | None,
    status: str,
    note: str,
) -> dict[str, str]:
    source = runtime or allocation or {}
    key = safe_key(source)
    return {
        "hunt_code": key[0],
        "residency": key[1],
        "points": key[2],
        "allocation_hunt_type": normalize((allocation or {}).get("hunt_type")),
        "runtime_hunt_type": normalize((runtime or {}).get("hunt_type")),
        "allocation_hunt_class": normalize((allocation or {}).get("hunt_class")),
        "runtime_hunt_class": normalize((runtime or {}).get("hunt_class")),
        "allocation_draw_pool": normalize((allocation or {}).get("draw_pool")),
        "runtime_draw_pool": normalize((runtime or {}).get("draw_pool")),
        "join_status": status,
        "note": note,
    }


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    codes = {normalize(row.get("hunt_code")).upper() for row in rows if normalize(row.get("hunt_code"))}
    keys = {safe_key(row) for row in rows if safe_key(row)[0]}
    return {
        "row_count": len(rows),
        "hunt_code_count": len(codes),
        "safe_key_count": len(keys),
        "join_status_counts": dict(Counter(row.get("unified_join_status", "") for row in rows)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--allocation", default=str(ALLOCATION))
    parser.add_argument("--runtime", default=str(RUNTIME))
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--audit", default=str(AUDIT))
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    allocation_path = root / args.allocation
    runtime_path = root / args.runtime
    output_path = root / args.output
    audit_path = root / args.audit

    allocation_fields, allocation_rows = read_csv(allocation_path)
    runtime_fields, runtime_rows = read_csv(runtime_path)
    unified_rows, audit_rows = merge_rows(allocation_rows, runtime_rows)
    unified_fields = ordered_fields(allocation_fields, runtime_fields)

    write_csv(output_path, unified_fields, unified_rows)
    write_csv(
        audit_path,
        [
            "hunt_code",
            "residency",
            "points",
            "allocation_hunt_type",
            "runtime_hunt_type",
            "allocation_hunt_class",
            "runtime_hunt_class",
            "allocation_draw_pool",
            "runtime_draw_pool",
            "join_status",
            "note",
        ],
        audit_rows,
    )

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "allocation": summarize(allocation_rows),
        "runtime": summarize(runtime_rows),
        "unified": summarize(unified_rows),
        "output": output_path.relative_to(root).as_posix(),
        "audit": audit_path.relative_to(root).as_posix(),
        "promoted": False,
    }

    if args.promote:
        production_path = root / PRODUCTION
        backup = root / "processed_data" / "promotion_backups" / f"point_ladder_view_before_unified_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(production_path, backup)
        shutil.copy2(output_path, production_path)
        result["promoted"] = True
        result["backup"] = backup.relative_to(root).as_posix()
        result["production"] = production_path.relative_to(root).as_posix()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
