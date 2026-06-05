#!/usr/bin/env python3
"""Fill blank DATABASE.csv boundary_id values from the reviewed display boundary index."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def norm(value: Any) -> str:
    return str(value or "").strip().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--database", default="pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
    parser.add_argument("--boundary-index", default="processed_data/display-boundary-index-2026.json")
    parser.add_argument("--out-dir", default="audits/boundary_runtime")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--resolve-conflicts", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    database_path = root / args.database
    index_path = root / args.boundary_index
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    index_data = json.loads(index_path.read_text(encoding="utf-8-sig"))
    index_rows = index_data.get("records", []) if isinstance(index_data, dict) else index_data
    index_by_code = {
        norm(row.get("hunt_code")): row
        for row in index_rows
        if isinstance(row, dict) and norm(row.get("hunt_code")) and str(row.get("boundary_id") or "").strip()
    }

    with database_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if "hunt_code" not in fieldnames or "boundary_id" not in fieldnames:
        raise SystemExit("DATABASE.csv must contain hunt_code and boundary_id columns")

    audit_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        code = norm(row.get("hunt_code"))
        if not code:
            continue
        index_row = index_by_code.get(code)
        db_boundary = str(row.get("boundary_id") or "").strip()
        index_boundary = str(index_row.get("boundary_id") or "").strip() if index_row else ""
        action = "ok_existing_match"
        if not index_row:
            action = "no_boundary_index_mapping"
        elif not db_boundary and index_boundary:
            action = "fill_blank_boundary_id"
            if args.apply:
                row["boundary_id"] = index_boundary
        elif db_boundary and index_boundary and db_boundary != index_boundary:
            action = "review_existing_conflict_not_overwritten"
            if args.apply and args.resolve_conflicts:
                row["boundary_id"] = index_boundary
                action = "resolve_existing_conflict_to_boundary_index"
        audit_rows.append({
            "row_number": row_number,
            "hunt_code": code,
            "hunt_name": row.get("hunt_name") or "",
            "species": row.get("species") or "",
            "sex_type": row.get("sex_type") or "",
            "weapon": row.get("weapon") or "",
            "database_boundary_id_before": db_boundary,
            "boundary_index_boundary_id": index_boundary,
            "boundary_index_source_file": index_row.get("boundary_source_file") if index_row else "",
            "boundary_index_geojson_path": index_row.get("boundary_geojson_path") if index_row else "",
            "action": action,
        })

    if args.apply:
        tmp = database_path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(database_path)

    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["action"]] = counts.get(row["action"], 0) + 1

    audit_csv = out_dir / "database_boundary_id_reconciliation.csv"
    with audit_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "applied": bool(args.apply),
        "database_rows": len(rows),
        "database_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}),
        "boundary_index_rows": len(index_rows),
        "boundary_index_unique_hunt_codes": len(index_by_code),
        "action_counts": counts,
        "resolve_conflicts": bool(args.resolve_conflicts),
        "audit_csv": str(audit_csv.relative_to(root)),
    }
    (out_dir / "database_boundary_id_reconciliation.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# DATABASE Boundary ID Reconciliation",
        "",
        f"- Applied: `{bool(args.apply)}`",
        f"- DATABASE rows: `{len(rows)}`",
        f"- DATABASE unique hunt codes: `{summary['database_unique_hunt_codes']}`",
        f"- Boundary index unique hunt codes: `{summary['boundary_index_unique_hunt_codes']}`",
        "",
        "## Action Counts",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: `{counts[key]}`")
    (out_dir / "database_boundary_id_reconciliation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
