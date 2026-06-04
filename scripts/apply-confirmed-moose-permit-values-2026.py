"""Apply user-confirmed 2026 Moose permit values to DATABASE.csv."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
OUT_PATCH = ROOT / "processed_data/audits/confirmed_moose_permit_values_database_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/confirmed_moose_permit_values_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/confirmed_moose_permit_values_database_patch_2026.md"

CONFIRMED = {
    "MA1005": ("2", "1", "3"),
    "MA1007": ("2", "0", "2"),
    "MA1008": ("2", "0", "2"),
}


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
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_confirmed_moose_permit_patch_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def main() -> int:
    rows, fields = read_csv(DATABASE)
    by_code = {clean(row.get("hunt_code")).upper(): row for row in rows if clean(row.get("hunt_code"))}
    missing = sorted(set(CONFIRMED) - set(by_code))
    if missing:
        raise RuntimeError(f"Confirmed Moose codes missing from DATABASE.csv: {missing}")

    backup = backup_database()
    patch_rows: list[dict[str, object]] = []
    for code, values in sorted(CONFIRMED.items()):
        row = by_code[code]
        before = (
            clean(row.get("permit_allotment_2026_res")),
            clean(row.get("permit_allotment_2026_nr")),
            clean(row.get("permit_allotment_2026_total")),
        )
        row["permit_allotment_2026_res"] = values[0]
        row["permit_allotment_2026_nr"] = values[1]
        row["permit_allotment_2026_total"] = values[2]
        row["permit_allotment_2026_source"] = "USER_CONFIRMED_MOOSE_RECOMMENDED_VALUES"
        row["permit_allotment_2026_source_file"] = "user message 2026-06-04"
        row["permit_allotment_2026_status"] = "RECONCILED_2026_MOOSE_RECOMMENDED_USER_CONFIRMED"
        patch_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "before_res": before[0],
                "before_nr": before[1],
                "before_total": before[2],
                "after_res": values[0],
                "after_nr": values[1],
                "after_total": values[2],
                "source": row["permit_allotment_2026_source"],
                "status": row["permit_allotment_2026_status"],
                "notes": "User confirmed Moose values match recommended values.",
            }
        )

    with DATABASE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    patch_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "before_res",
        "before_nr",
        "before_total",
        "after_res",
        "after_nr",
        "after_total",
        "source",
        "status",
        "notes",
    ]
    write_csv(OUT_PATCH, patch_rows, patch_fields)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "updated_database_rows": len(patch_rows),
        "updated_codes": list(sorted(CONFIRMED)),
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Applied only user-confirmed Moose recommended values.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_DOC.write_text(
        "\n".join(
            [
                "# Confirmed Moose Permit Values DATABASE Patch 2026",
                "",
                "Updated only user-confirmed Moose rows where the values match recommended.",
                "",
                f"- DATABASE rows updated: `{len(patch_rows)}`",
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
