from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CLOUDFARE_MASTER = Path(r"C:\Users\tyler\Desktop\GitHub\Cloudfare\hunt_master_enriched.csv")
BACKUP_ROOT = ROOT / "processed_data" / "backups"
AUDIT_OUT = ROOT / "processed_data" / "audits" / "research_feeder_database_permit_sync_audit.csv"
SUMMARY_OUT = ROOT / "processed_data" / "audits" / "research_feeder_database_permit_sync_summary.json"
DOC_OUT = ROOT / "docs" / "research_feeder_database_permit_sync.md"


TARGETS = [
    {
        "label": "hunt_master_enriched",
        "path": ROOT / "processed_data" / "hunt_master_enriched.csv",
        "allow_lfs_replacement": True,
        "replacement": CLOUDFARE_MASTER,
        "public_permits": True,
    },
    {
        "label": "hunt_unit_reference_linked",
        "path": ROOT / "processed_data" / "hunt_unit_reference_linked.csv",
        "allow_lfs_replacement": False,
        "replacement": None,
        "public_permits": True,
    },
    {
        "label": "draw_reality_engine",
        "path": ROOT / "processed_data" / "draw_reality_engine.csv",
        "allow_lfs_replacement": False,
        "replacement": None,
        "public_permits": True,
    },
    {
        "label": "point_ladder_view",
        "path": ROOT / "processed_data" / "point_ladder_view.csv",
        "allow_lfs_replacement": False,
        "replacement": None,
        "public_permits": True,
    },
]

SYNC_FIELDS = [
    ("permits_2024_res", "permits_2024_res"),
    ("permits_2024_nr", "permits_2024_nr"),
    ("permits_2024_total", "permits_2024_total"),
    ("permits_2025_res", "permits_2025_res"),
    ("permits_2025_nr", "permits_2025_nr"),
    ("permits_2025_total", "permits_2025_total"),
    ("permit_allotment_2026_res", "permit_allotment_2026_res"),
    ("permit_allotment_2026_nr", "permit_allotment_2026_nr"),
    ("permit_allotment_2026_total", "permit_allotment_2026_total"),
    ("permits_2026_res", "permit_allotment_2026_res"),
    ("permits_2026_nr", "permit_allotment_2026_nr"),
    ("permits_2026_total", "permit_allotment_2026_total"),
]

SOURCE_FIELDS = [
    ("permits_2024_source", "permits_2024_source"),
    ("permits_2025_source", "permits_2025_source"),
    ("permit_allotment_2026_source", "permit_allotment_2026_source"),
    ("permits_2026_source", "permit_allotment_2026_source"),
]

SOURCE_LABEL_2026 = "DATABASE_2026_CURRENT_PERMIT_ALLOTMENT__2027_MODEL"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_number(value: Any) -> str:
    text = clean(value).replace(",", "")
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return clean(value)
    return str(int(number)) if number.is_integer() else str(number)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = [{key: clean(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def is_lfs_pointer(path: Path) -> bool:
    if not path.exists() or path.stat().st_size > 1024:
        return False
    head = path.read_text(encoding="utf-8", errors="ignore")[:120]
    return "git-lfs.github.com/spec" in head


def load_database() -> dict[str, dict[str, str]]:
    fields, rows = read_csv(DATABASE)
    required = {"hunt_code", "permit_allotment_2026_total"}
    missing = required - set(fields)
    if missing:
        raise RuntimeError(f"DATABASE.csv missing required fields: {sorted(missing)}")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        normalized = {key: clean(value) for key, value in row.items()}
        for field in {
            "permits_2024_res",
            "permits_2024_nr",
            "permits_2024_total",
            "permits_2025_res",
            "permits_2025_nr",
            "permits_2025_total",
            "permit_allotment_2026_res",
            "permit_allotment_2026_nr",
            "permit_allotment_2026_total",
        }:
            normalized[field] = normalize_number(normalized.get(field, ""))
        out[code] = normalized
    return out


def public_permit_for(row: dict[str, str], db_row: dict[str, str]) -> str:
    residency = clean(row.get("residency")).lower()
    res = db_row.get("permit_allotment_2026_res", "")
    nr = db_row.get("permit_allotment_2026_nr", "")
    total = db_row.get("permit_allotment_2026_total", "")
    if residency.startswith("non"):
        return nr or total
    if residency.startswith("res"):
        return res or total
    return total or res or nr


def update_value(row: dict[str, str], field: str, value: str) -> tuple[bool, str, str]:
    before = clean(row.get(field))
    after = clean(value)
    if before == after:
        return False, before, after
    row[field] = after
    return True, before, after


def backup_file(path: Path, stamp: str) -> Path:
    rel = path.relative_to(ROOT)
    dest = BACKUP_ROOT / f"research_feeder_sync_{stamp}" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def ensure_real_file(target: dict[str, Any]) -> str:
    path: Path = target["path"]
    if not is_lfs_pointer(path):
        return "REAL_LOCAL_FILE"
    if not target.get("allow_lfs_replacement"):
        return "LFS_POINTER_BLOCKED"
    replacement: Path | None = target.get("replacement")
    if not replacement or not replacement.exists() or is_lfs_pointer(replacement):
        return "LFS_POINTER_NO_VALID_REPLACEMENT"
    shutil.copy2(replacement, path)
    return f"REPLACED_LFS_POINTER_FROM::{replacement}"


def sync_target(target: dict[str, Any], db: dict[str, dict[str, str]], stamp: str) -> dict[str, Any]:
    path: Path = target["path"]
    real_status = ensure_real_file(target)
    if real_status.startswith("LFS_POINTER"):
        return {
            "label": target["label"],
            "path": str(path.relative_to(ROOT)),
            "status": real_status,
            "rows": 0,
            "matched_rows": 0,
            "changed_rows": 0,
            "changed_cells": 0,
            "added_columns": [],
            "backup": "",
            "audit_rows": [],
        }

    fieldnames, rows = read_csv(path)
    added_columns: list[str] = []
    for field, _ in SYNC_FIELDS + SOURCE_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
            added_columns.append(field)
    if target.get("public_permits"):
        for field in ("public_permits_2026", "public_permits_2026_source"):
            if field not in fieldnames:
                fieldnames.append(field)
                added_columns.append(field)

    backup = backup_file(path, stamp)
    audit_rows: list[dict[str, Any]] = []
    changed_rows = 0
    changed_cells = 0
    matched_rows = 0
    source_extra_codes: set[str] = set()

    for index, row in enumerate(rows, start=2):
        code = clean(row.get("hunt_code") or row.get("huntCode") or row.get("code")).upper()
        if not code:
            continue
        db_row = db.get(code)
        if not db_row:
            source_extra_codes.add(code)
            continue
        matched_rows += 1
        row_changed = False
        for target_field, db_field in SYNC_FIELDS:
            value = normalize_number(db_row.get(db_field, ""))
            if not value:
                continue
            changed, before, after = update_value(row, target_field, value)
            if changed:
                row_changed = True
                changed_cells += 1
                audit_rows.append(
                    {
                        "feeder": target["label"],
                        "row_number": index,
                        "hunt_code": code,
                        "field": target_field,
                        "before": before,
                        "after": after,
                        "db_source_field": db_field,
                        "action": "UPDATED_FROM_DATABASE",
                    }
                )
        for target_field, db_field in SOURCE_FIELDS:
            value = db_row.get(db_field, "")
            if target_field == "permits_2026_source" and (
                db_row.get("permit_allotment_2026_res")
                or db_row.get("permit_allotment_2026_nr")
                or db_row.get("permit_allotment_2026_total")
            ):
                value = SOURCE_LABEL_2026
            if not value:
                continue
            changed, before, after = update_value(row, target_field, value)
            if changed:
                row_changed = True
                changed_cells += 1
                audit_rows.append(
                    {
                        "feeder": target["label"],
                        "row_number": index,
                        "hunt_code": code,
                        "field": target_field,
                        "before": before,
                        "after": after,
                        "db_source_field": db_field,
                        "action": "UPDATED_SOURCE_FROM_DATABASE",
                    }
                )
        if target.get("public_permits"):
            public_value = public_permit_for(row, db_row)
            if public_value:
                for field, value in (
                    ("public_permits_2026", public_value),
                    ("public_permits_2026_source", SOURCE_LABEL_2026),
                ):
                    changed, before, after = update_value(row, field, value)
                    if changed:
                        row_changed = True
                        changed_cells += 1
                        audit_rows.append(
                            {
                                "feeder": target["label"],
                                "row_number": index,
                                "hunt_code": code,
                                "field": field,
                                "before": before,
                                "after": after,
                                "db_source_field": "permit_allotment_2026_*",
                                "action": "UPDATED_PUBLIC_PERMIT_FROM_DATABASE",
                            }
                        )
        if row_changed:
            changed_rows += 1

    write_csv(path, fieldnames, rows)
    return {
        "label": target["label"],
        "path": str(path.relative_to(ROOT)),
        "status": real_status,
        "rows": len(rows),
        "matched_rows": matched_rows,
        "changed_rows": changed_rows,
        "changed_cells": changed_cells,
        "added_columns": added_columns,
        "extra_codes_not_in_database": len(source_extra_codes),
        "backup": str(backup.relative_to(ROOT)),
        "audit_rows": audit_rows,
    }


def write_audit(rows: list[dict[str, Any]]) -> None:
    fieldnames = ["feeder", "row_number", "hunt_code", "field", "before", "after", "db_source_field", "action"]
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    db = load_database()
    results = []
    audit_rows: list[dict[str, Any]] = []
    for target in TARGETS:
        result = sync_target(target, db, stamp)
        audit_rows.extend(result.pop("audit_rows"))
        results.append(result)
    write_audit(audit_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_rows": len(db),
        "source_label_2026": SOURCE_LABEL_2026,
        "audit_csv": str(AUDIT_OUT.relative_to(ROOT)),
        "targets": results,
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    doc = [
        "# Research Feeder Permit Sync From DATABASE",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Synced the four Research feeder surfaces against cleaned `DATABASE.csv` permit fields. This pass did not change draw odds or probability math.",
        "",
        "## Results",
        "",
        "| Feeder | Rows | Matched rows | Changed rows | Changed cells | Added columns | Status |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for result in results:
        doc.append(
            f"| `{result['label']}` | {result['rows']} | {result['matched_rows']} | {result['changed_rows']} | {result['changed_cells']} | {', '.join(result['added_columns']) or 'none'} | {result['status']} |"
        )
    doc.extend(
        [
            "",
            "## Notes",
            "",
            "- `processed_data/hunt_master_enriched.csv` was replaced from the real local Cloudfare copy only because the repo copy was a Git LFS pointer.",
            "- Existing machine fields were preserved for runtime compatibility.",
            "- `permits_2026_*` in feeder files now mirrors current `DATABASE.csv` 2026 allotment values and is labeled as the 2026 draw-results/current-permit field for 2027 model use.",
            "",
            "## Outputs",
            "",
            f"- Audit CSV: `{AUDIT_OUT.relative_to(ROOT)}`",
            f"- Summary JSON: `{SUMMARY_OUT.relative_to(ROOT)}`",
        ]
    )
    DOC_OUT.write_text("\n".join(doc) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
