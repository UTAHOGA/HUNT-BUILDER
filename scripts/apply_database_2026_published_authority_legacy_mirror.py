from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
ACTIONS = ROOT / "processed_data" / "audits" / "database_2026_published_vs_legacy_allotment_actions.csv"
BACKUP_ROOT = ROOT / "processed_data" / "backups"
AUDIT_CSV = ROOT / "processed_data" / "audits" / "database_2026_published_authority_legacy_mirror_audit.csv"
SUMMARY_JSON = ROOT / "processed_data" / "audits" / "database_2026_published_authority_legacy_mirror_summary.json"
SUMMARY_MD = ROOT / "processed_data" / "audits" / "database_2026_published_authority_legacy_mirror_summary.md"

COMPAT_SOURCE = "DERIVED_FROM_PUBLISHED_2026_PERMITS_COMPAT"
COMPAT_SOURCE_FILE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
COMPAT_STATUS = "DERIVED_FROM_PUBLISHED_2026_PERMITS_COMPAT"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup_database(stamp: str) -> Path:
    dest = BACKUP_ROOT / f"database_legacy_mirror_{stamp}" / DATABASE.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, dest)
    return dest


def load_keep_codes() -> dict[str, dict[str, str]]:
    _, rows = read_csv(ACTIONS)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if clean(row.get("mismatch_action")) != "KEEP_PUBLISHED_MIRROR_LEGACY":
            continue
        code = clean(row.get("hunt_code")).upper()
        if code:
            out[code] = row
    return out


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    keep_codes = load_keep_codes()
    fieldnames, rows = read_csv(DATABASE)
    backup = backup_database(stamp)
    audit_rows: list[dict[str, str]] = []
    touched_codes = 0
    touched_cells = 0
    family_counts: Counter[str] = Counter()

    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        action_row = keep_codes.get(code)
        if not action_row:
            continue
        touched_codes += 1
        family = clean(row.get("draw_2026_system_type")) or clean(row.get("hunt_class")) or "UNKNOWN"
        family_counts[family] += 1

        replacements = {
            "permit_allotment_2026_res": clean(row.get("permits_2026_res")),
            "permit_allotment_2026_nr": clean(row.get("permits_2026_nr")),
            "permit_allotment_2026_total": clean(row.get("permits_2026_total")),
            "permit_allotment_2026_source": COMPAT_SOURCE,
            "permit_allotment_2026_source_file": COMPAT_SOURCE_FILE,
            "permit_allotment_2026_status": COMPAT_STATUS,
        }
        for field, after in replacements.items():
            before = clean(row.get(field))
            if before == after:
                continue
            row[field] = after
            touched_cells += 1
            audit_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "family": family,
                    "field": field,
                    "before": before,
                    "after": after,
                    "action": "MIRROR_LEGACY_TO_PUBLISHED",
                }
            )

    write_csv(DATABASE, fieldnames, rows)
    write_csv(AUDIT_CSV, list(audit_rows[0].keys()) if audit_rows else ["hunt_code"], audit_rows or [{"hunt_code": ""}])

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_file": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
        "backup_file": str(backup.relative_to(ROOT)).replace("\\", "/"),
        "applied_action": "KEEP_PUBLISHED_MIRROR_LEGACY",
        "published_authority_rule": "permits_2026_res/nr/total",
        "legacy_fields_collapsed_to_published": True,
        "codes_touched": touched_codes,
        "cells_changed": touched_cells,
        "family_counts": dict(family_counts),
        "audit_csv": str(AUDIT_CSV.relative_to(ROOT)).replace("\\", "/"),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(
        "\n".join(
            [
                "# DATABASE 2026 Legacy Mirror Apply",
                "",
                f"Generated: `{summary['generated_at_utc']}`",
                "",
                "- Applied only `KEEP_PUBLISHED_MIRROR_LEGACY` rows.",
                "- Did not modify `permits_2026_res/nr/total`.",
                "- Collapsed `permit_allotment_2026_*` down to the published 2026 permit values for compatibility only.",
                "",
                f"- Codes touched: `{touched_codes}`",
                f"- Cells changed: `{touched_cells}`",
                f"- Backup: `{summary['backup_file']}`",
                f"- Audit CSV: `{summary['audit_csv']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
