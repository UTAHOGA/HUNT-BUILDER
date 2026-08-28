"""Apply selected final reviewed permit overrides to DATABASE.csv."""

from __future__ import annotations

import csv
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
CANONICAL = (
    ROOT
    / "data_truth/draw_results_truth/normalized/canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
OVERRIDES = ROOT / "processed_data/audits/reviewed_permit_value_overrides_2026.csv"
OUT_PATCH = ROOT / "processed_data/audits/final_reviewed_permit_overrides_database_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/final_reviewed_permit_overrides_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/final_reviewed_permit_overrides_database_patch_2026.md"
WEB_CANONICALS = [
    ROOT / "data/hunt-master-canonical-2026-foundation.json",
    ROOT / "data/hunt-master-canonical-2026-source-of-truth.json",
    ROOT / "data/hunt-master-canonical-2026-database-candidate.json",
    ROOT / "processed_data/hunt-master-canonical-2026-source-of-truth.json",
]


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


def backup_canonical() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = (
        ROOT
        / "processed_data/backups"
        / f"draw_results_2026_for_2027_before_final_reviewed_permit_overrides_{stamp}.csv"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CANONICAL, backup)
    return backup


def backup_web_canonical(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "processed_data/backups" / f"{path.stem}_before_final_reviewed_permit_overrides_{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def append_note(existing: str, note: str) -> str:
    return existing if note in existing else "; ".join(filter(None, (existing, note)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hunt-code",
        action="append",
        default=[],
        help="Apply only this reviewed override code. Repeat for multiple codes.",
    )
    parser.add_argument(
        "--propagate-canonical-long",
        action="store_true",
        help="Also apply the selected override to the 2026 canonical and rebuild draw_results_long.csv.",
    )
    parser.add_argument(
        "--propagate-web-canonicals",
        action="store_true",
        help="Also apply the selected override to the website-facing 2026 canonical JSON files.",
    )
    args = parser.parse_args()
    db_rows, db_fields = read_csv(DATABASE)
    canonical_rows: list[dict[str, str]] = []
    canonical_fields: list[str] = []
    canonical_by_code: dict[str, dict[str, str]] = {}
    if args.propagate_canonical_long:
        canonical_rows, canonical_fields = read_csv(CANONICAL)
        canonical_by_code = {
            clean(row.get("hunt_code")).upper(): row
            for row in canonical_rows
            if clean(row.get("actual_draw_year")) == "2026" and clean(row.get("hunt_code"))
        }
    web_canonical_rows: list[tuple[Path, list[dict[str, object]]]] = []
    if args.propagate_web_canonicals:
        for path in WEB_CANONICALS:
            if not path.exists():
                raise RuntimeError(f"Website canonical file is missing: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise RuntimeError(f"Website canonical is not a JSON row list: {path}")
            web_canonical_rows.append((path, payload))
    override_rows, _ = read_csv(OVERRIDES)
    selected_codes = {clean(value).upper() for value in args.hunt_code if clean(value)}
    if selected_codes:
        override_rows = [row for row in override_rows if clean(row.get("hunt_code")).upper() in selected_codes]
        missing = selected_codes - {clean(row.get("hunt_code")).upper() for row in override_rows}
        if missing:
            raise RuntimeError(f"Requested override code(s) not found: {sorted(missing)}")
    by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows if clean(row.get("hunt_code"))}
    backup = backup_database()
    canonical_backup = backup_canonical() if args.propagate_canonical_long else None
    web_canonical_backups = {
        path.relative_to(ROOT).as_posix(): backup_web_canonical(path).relative_to(ROOT).as_posix()
        for path, _ in web_canonical_rows
    }
    patch_rows: list[dict[str, object]] = []

    for override in override_rows:
        code = clean(override.get("hunt_code")).upper()
        if code not in by_code:
            raise RuntimeError(f"Override code missing from DATABASE.csv: {code}")
        if args.propagate_canonical_long and code not in canonical_by_code:
            raise RuntimeError(f"Override code missing from 2026 canonical yearly file: {code}")
        row = by_code[code]
        before_allotment = (
            clean(row.get("permit_allotment_2026_res")),
            clean(row.get("permit_allotment_2026_nr")),
            clean(row.get("permit_allotment_2026_total")),
        )
        before_current = (
            clean(row.get("permits_2026_res")),
            clean(row.get("permits_2026_nr")),
            clean(row.get("permits_2026_total")),
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
        row["permits_2026_res"] = after[0]
        row["permits_2026_nr"] = after[1]
        row["permits_2026_total"] = after[2]
        row["permits_2026_source"] = clean(override.get("reviewed_source"))
        row["permits_2026_draw_source"] = clean(override.get("reviewed_source"))
        if args.propagate_canonical_long:
            canonical_row = canonical_by_code[code]
            canonical_row["permits_2026_res"] = after[0]
            canonical_row["permits_2026_nr"] = after[1]
            canonical_row["permits_2026_total"] = after[2]
            canonical_row["permits_2026_source"] = clean(override.get("reviewed_source"))
            canonical_row["permits_2026_draw_source"] = clean(override.get("reviewed_source"))
            correction_note = (
                "USER_CONFIRMED_PD1056_TYPO: raw current DWR Hunt Planner snapshot was 63 / 4 / 0; "
                "reviewed DWR Planner record and official 2026 DWR Draw Odds both report 36 / 4 / 40."
            )
            existing_notes = clean(canonical_row.get("qa_notes"))
            if code == "PD1056" and correction_note not in existing_notes:
                canonical_row["qa_notes"] = "; ".join(filter(None, (existing_notes, correction_note)))
        for path, rows in web_canonical_rows:
            matches = [
                item
                for item in rows
                if clean(item.get("hunt_code") or item.get("huntCode") or item.get("code")).upper() == code
            ]
            if len(matches) != 1:
                raise RuntimeError(f"Expected one {code} row in {path}, found {len(matches)}")
            item = matches[0]
            for prefix in ("permits_2026", "permit_allotment_2026"):
                item[f"{prefix}_res"] = after[0]
                item[f"{prefix}_nr"] = after[1]
                item[f"{prefix}_total"] = after[2]
            item["permits_2026_source"] = clean(override.get("reviewed_source"))
            item["permits_2026_draw_source"] = clean(override.get("reviewed_source"))
            item["permit_allotment_2026_source"] = clean(override.get("reviewed_source"))
            item["permit_allotment_2026_source_file"] = OVERRIDES.relative_to(ROOT).as_posix()
            item["permit_allotment_2026_status"] = clean(override.get("reviewed_status"))
            item["totalPermits"] = after[2]
            item["permitsTotal"] = after[2]
            item["permit_note"] = append_note(
                clean(item.get("permit_note")),
                "PD1056 reviewed correction: raw Planner 63/4/0; reviewed Planner and DWR draw odds 36/4/40.",
            )
        patch_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "before_allotment_res": before_allotment[0],
                "before_allotment_nr": before_allotment[1],
                "before_allotment_total": before_allotment[2],
                "before_current_res": before_current[0],
                "before_current_nr": before_current[1],
                "before_current_total": before_current[2],
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

    long_rebuild: dict[str, object] | None = None
    if args.propagate_canonical_long:
        with CANONICAL.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=canonical_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(canonical_rows)
        from rebuild_draw_results_long_from_canonical_yearly import rebuild

        long_rebuild = rebuild(write=True, allow_split_row_canonical=True)
        if long_rebuild.get("blocked"):
            raise RuntimeError(f"Long-file rebuild blocked: {long_rebuild}")

    for path, rows in web_canonical_rows:
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "before_allotment_res",
        "before_allotment_nr",
        "before_allotment_total",
        "before_current_res",
        "before_current_nr",
        "before_current_total",
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
        "canonical_backup_path": canonical_backup.relative_to(ROOT).as_posix() if canonical_backup else "",
        "website_canonical_backup_paths": web_canonical_backups,
        "updated_database_rows": len(patch_rows),
        "updated_codes": [row["hunt_code"] for row in patch_rows],
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "long_rebuild": long_rebuild or {},
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_DOC.write_text(
        "\n".join(
            [
                "# Final Reviewed Permit Overrides DATABASE Patch 2026",
                "",
                "Applied selected reviewed permit overrides.",
                "",
                f"- DATABASE rows updated: `{len(patch_rows)}`",
                f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
                f"- 2026 canonical backup: `{canonical_backup.relative_to(ROOT).as_posix() if canonical_backup else ''}`",
                f"- Website canonical backups: `{len(web_canonical_backups)}`",
                f"- Long-file rebuild backup: `{(long_rebuild or {}).get('backup_path', '')}`",
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
