"""Retire PD1025 from the active 2026 permit universe."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
OUT_PATCH = ROOT / "processed_data/audits/pd1025_retirement_database_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/pd1025_retirement_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/pd1025_retirement_database_patch_2026.md"


def clean(value: object) -> str:
    return str(value or "").strip()


def main() -> int:
    with DATABASE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_pd1025_retirement_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)

    patch_rows: list[dict[str, object]] = []
    for row in rows:
        if clean(row.get("hunt_code")).upper() != "PD1025":
            continue
        before = {
            "res": clean(row.get("permit_allotment_2026_res")),
            "nr": clean(row.get("permit_allotment_2026_nr")),
            "total": clean(row.get("permit_allotment_2026_total")),
            "source": clean(row.get("permit_allotment_2026_source")),
            "status": clean(row.get("permit_allotment_2026_status")),
            "notes": clean(row.get("NOTES")),
        }
        row["permit_allotment_2026_res"] = ""
        row["permit_allotment_2026_nr"] = ""
        row["permit_allotment_2026_total"] = ""
        row["permit_allotment_2026_source"] = "USER_CONFIRMED_PD1025_RETIRED"
        row["permit_allotment_2026_source_file"] = "processed_data/audits/reviewed_retired_hunt_codes_2026.csv"
        row["permit_allotment_2026_status"] = "RETIRED_2026_SUCCESSOR_PD1050"
        row["NOTES"] = "RETIRED_2026; active successor PD1050 Cottonwood Ridge CWMU carries 6 / 0 / 6."
        patch_rows.append(
            {
                "hunt_code": "PD1025",
                "hunt_name": clean(row.get("hunt_name")),
                "before_res": before["res"],
                "before_nr": before["nr"],
                "before_total": before["total"],
                "after_res": "",
                "after_nr": "",
                "after_total": "",
                "before_status": before["status"],
                "after_status": row["permit_allotment_2026_status"],
                "before_notes": before["notes"],
                "after_notes": row["NOTES"],
            }
        )

    if len(patch_rows) != 1:
        raise RuntimeError(f"Expected exactly one PD1025 row, found {len(patch_rows)}")

    with DATABASE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    patch_fields = [
        "hunt_code",
        "hunt_name",
        "before_res",
        "before_nr",
        "before_total",
        "after_res",
        "after_nr",
        "after_total",
        "before_status",
        "after_status",
        "before_notes",
        "after_notes",
    ]
    OUT_PATCH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATCH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=patch_fields)
        writer.writeheader()
        writer.writerows(patch_rows)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "updated_database_rows": len(patch_rows),
        "retired_code": "PD1025",
        "successor_code": "PD1050",
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_DOC.write_text(
        "\n".join(
            [
                "# PD1025 Retirement Patch 2026",
                "",
                "`PD1025` was marked retired for 2026. Active successor `PD1050` already exists in DATABASE with `6 / 0 / 6`.",
                "",
                f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
                f"- Patch CSV: `{OUT_PATCH.relative_to(ROOT).as_posix()}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
