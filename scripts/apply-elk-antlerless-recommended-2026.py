"""Apply confirmed 2026 Elk Antlerless recommended permit values.

Only rows where pasted Elk Antlerless evidence exactly matches the current
recommended value and differs from DATABASE allotment are updated.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
ELK_AUDIT = ROOT / "processed_data/audits/elk_antlerless_pasted_vs_recommended_2026.csv"

OUT_PATCH = ROOT / "processed_data/audits/elk_antlerless_recommended_database_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/elk_antlerless_recommended_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/elk_antlerless_recommended_database_patch_2026.md"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup_database() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_elk_antlerless_recommended_patch_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def main() -> int:
    db_rows, db_fields = read_csv(DATABASE)
    audit_rows, _ = read_csv(ELK_AUDIT)
    backup = backup_database()

    candidates: dict[str, dict[str, str]] = {}
    duplicate_values: dict[str, set[tuple[str, str, str]]] = {}
    for row in audit_rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        if clean(row.get("pasted_vs_recommended")) != "EXACT_MATCH":
            continue
        if clean(row.get("pasted_vs_database")) != "DIFFERS":
            continue
        if not code.startswith("EA"):
            continue
        values = (
            clean(row.get("recommended_res")),
            clean(row.get("recommended_nr")),
            clean(row.get("recommended_total")),
        )
        duplicate_values.setdefault(code, set()).add(values)
        candidates[code] = row

    inconsistent_duplicates = {
        code: sorted(values)
        for code, values in duplicate_values.items()
        if len(values) > 1
    }
    if inconsistent_duplicates:
        raise RuntimeError(f"Inconsistent duplicate pasted values: {inconsistent_duplicates}")

    patch_rows: list[dict[str, object]] = []
    db_by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows if clean(row.get("hunt_code"))}
    missing_codes = sorted(set(candidates) - set(db_by_code))
    if missing_codes:
        raise RuntimeError(f"Confirmed Elk Antlerless codes missing from DATABASE.csv: {missing_codes}")

    for code, source in sorted(candidates.items()):
        db = db_by_code[code]
        before = {
            "res": clean(db.get("permit_allotment_2026_res")),
            "nr": clean(db.get("permit_allotment_2026_nr")),
            "total": clean(db.get("permit_allotment_2026_total")),
            "source": clean(db.get("permit_allotment_2026_source")),
            "source_file": clean(db.get("permit_allotment_2026_source_file")),
            "status": clean(db.get("permit_allotment_2026_status")),
        }
        after = {
            "res": clean(source.get("recommended_res")),
            "nr": clean(source.get("recommended_nr")),
            "total": clean(source.get("recommended_total")),
        }
        db["permit_allotment_2026_res"] = after["res"]
        db["permit_allotment_2026_nr"] = after["nr"]
        db["permit_allotment_2026_total"] = after["total"]
        db["permit_allotment_2026_source"] = "2026_CURRENT_RECOMMENDED_CONFIRMED_BY_ELK_ANTLERLESS_DWR_TABLE"
        db["permit_allotment_2026_source_file"] = (
            "processed_data/audits/elk_antlerless_pasted_vs_recommended_2026.csv"
        )
        db["permit_allotment_2026_status"] = "RECONCILED_2026_ELK_ANTLERLESS_RECOMMENDED_CONFIRMED"

        patch_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(db.get("hunt_name")),
                "species": clean(db.get("species")),
                "before_res": before["res"],
                "before_nr": before["nr"],
                "before_total": before["total"],
                "after_res": after["res"],
                "after_nr": after["nr"],
                "after_total": after["total"],
                "recommended_winner_source": clean(source.get("recommended_winner_source")),
                "recommended_confidence": clean(source.get("recommended_confidence")),
                "pasted_duplicate_count": clean(source.get("pasted_duplicate_count")),
                "before_source": before["source"],
                "after_source": db["permit_allotment_2026_source"],
                "before_status": before["status"],
                "after_status": db["permit_allotment_2026_status"],
                "notes": "Pasted Elk Antlerless evidence exactly matched recommended value and differed from DATABASE.",
            }
        )

    with DATABASE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=db_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(db_rows)

    fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "before_res",
        "before_nr",
        "before_total",
        "after_res",
        "after_nr",
        "after_total",
        "recommended_winner_source",
        "recommended_confidence",
        "pasted_duplicate_count",
        "before_source",
        "after_source",
        "before_status",
        "after_status",
        "notes",
    ]
    write_csv(OUT_PATCH, patch_rows, fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "source_audit": ELK_AUDIT.relative_to(ROOT).as_posix(),
        "updated_database_rows": len(patch_rows),
        "updated_codes": [row["hunt_code"] for row in patch_rows],
        "recommended_winner_source_counts": dict(sorted(Counter(row["recommended_winner_source"] for row in patch_rows).items())),
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Only Elk Antlerless rows confirmed by pasted evidence were updated.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Elk Antlerless Recommended DATABASE Patch 2026",
        "",
        "## Scope",
        "",
        "Updated only Elk Antlerless rows where pasted DWR-table evidence exactly matched the current recommended value and differed from DATABASE allotment.",
        "",
        "## Counts",
        "",
        f"- DATABASE rows updated: `{len(patch_rows)}`",
        f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
        "",
        "## Outputs",
        "",
        f"- Patch CSV: `{OUT_PATCH.relative_to(ROOT).as_posix()}`",
        f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
    ]
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
