"""Apply final reviewed permit overrides for EA1176 and PD1025."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
OVERRIDES = ROOT / "processed_data/audits/reviewed_permit_value_overrides_2026.csv"
OUT_PATCH = ROOT / "processed_data/audits/final_reviewed_permit_overrides_database_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/final_reviewed_permit_overrides_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/final_reviewed_permit_overrides_database_patch_2026.md"


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
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_final_reviewed_permit_overrides_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def main() -> int:
    db_rows, db_fields = read_csv(DATABASE)
    override_rows, _ = read_csv(OVERRIDES)
    by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows if clean(row.get("hunt_code"))}
    backup = backup_database()
    patch_rows: list[dict[str, object]] = []

    for override in override_rows:
        code = clean(override.get("hunt_code")).upper()
        if code not in by_code:
            raise RuntimeError(f"Override code missing from DATABASE.csv: {code}")
        row = by_code[code]
        before = (
            clean(row.get("permit_allotment_2026_res")),
            clean(row.get("permit_allotment_2026_nr")),
            clean(row.get("permit_allotment_2026_total")),
        )
        after = (
            clean(override.get("reviewed_res")),
            clean(override.get("reviewed_nr")),
            clean(override.get("reviewed_total")),
        )
        row["permit_allotment_2026_res"] = after[0]
        row["permit_allotment_2026_nr"] = after[1]
        row["permit_allotment_2026_total"] = after[2]
        row["permit_allotment_2026_source"] = clean(override.get("reviewed_source"))
        row["permit_allotment_2026_source_file"] = OVERRIDES.relative_to(ROOT).as_posix()
        row["permit_allotment_2026_status"] = clean(override.get("reviewed_status"))
        patch_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "before_res": before[0],
                "before_nr": before[1],
                "before_total": before[2],
                "after_res": after[0],
                "after_nr": after[1],
                "after_total": after[2],
                "reviewed_source": clean(override.get("reviewed_source")),
                "reviewed_status": clean(override.get("reviewed_status")),
                "notes": clean(override.get("notes")),
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
        "reviewed_source",
        "reviewed_status",
        "notes",
    ]
    write_csv(OUT_PATCH, patch_rows, fields)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "override_source": OVERRIDES.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "updated_database_rows": len(patch_rows),
        "updated_codes": [row["hunt_code"] for row in patch_rows],
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
                "# Final Reviewed Permit Overrides DATABASE Patch 2026",
                "",
                "Applied final reviewed overrides for `EA1176` and `PD1025`.",
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
