"""Reconcile 2026 L.E. elk donor/live draw data into DATABASE.csv.

This patch uses the normalized UtahDraws DrawOddsData rows for the same source
family as the donor PDFs (`2026_PERMITS=2027_MODEL__L.E. ELK.pdf`,
`le elk.pdf`, `le elk nr.pdf`). It updates only database fields that the donor
source can safely authoritatively backfill or correct for the current 2026 elk
draw package.
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
DRAW_RESULTS_LONG = ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"

OUT_PATCH = ROOT / "processed_data/audits/2026_le_elk_donor_database_patch.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/2026_le_elk_donor_database_patch_summary.json"
OUT_DOC = ROOT / "processed_data/audits/2026_le_elk_donor_database_patch.md"

LE_SOURCE_FILE = "UtahDraws live DrawOddsData: Big Game:Limited-Entry"
CWMU_SOURCE_FILE = "UtahDraws live DrawOddsData: Big Game:CWMU"
SOURCE_LABEL = "2026_DONOR_LE_ELK_UTAHDRAWS_DRAWDATA"


def clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\ufeff", "").strip().split())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: clean(value) for key, value in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup_database() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_2026_le_elk_donor_patch_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def load_donor_truth() -> dict[str, dict[str, dict[str, str]]]:
    rows, _ = read_csv(DRAW_RESULTS_LONG)
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        if clean(row.get("actual_draw_year")) != "2026":
            continue
        if clean(row.get("species")) != "Elk":
            continue
        code = clean(row.get("hunt_code")).upper()
        if not code.startswith("EB"):
            continue
        source_file = clean(row.get("source_file"))
        if source_file not in {LE_SOURCE_FILE, CWMU_SOURCE_FILE}:
            continue
        source_group = "CWMU" if source_file == CWMU_SOURCE_FILE else "LE"
        key = (code, source_group)
        bucket = grouped.setdefault(
            key,
            {
                "hunt_name": set(),
                "weapon": set(),
                "draw_design": set(),
                "hunt_type": set(),
                "res": 0,
                "nr": 0,
                "source_file": source_file,
            },
        )
        bucket["hunt_name"].add(clean(row.get("hunt_name")))
        bucket["weapon"].add(clean(row.get("weapon")))
        bucket["draw_design"].add(clean(row.get("draw_design")))
        bucket["hunt_type"].add(clean(row.get("hunt_type")))
        if clean(row.get("residency")) == "Resident":
            bucket["res"] = int(bucket["res"]) + int(int_text(row.get("total_permits") or row.get("total_drawn") or "0") or "0")
        elif clean(row.get("residency")) == "Nonresident":
            bucket["nr"] = int(bucket["nr"]) + int(int_text(row.get("total_permits") or row.get("total_drawn") or "0") or "0")
    truth: dict[str, dict[str, dict[str, str]]] = {}
    for (code, source_group), bucket in grouped.items():
        hunt_name = sorted(value for value in bucket["hunt_name"] if value)
        weapon = sorted(value for value in bucket["weapon"] if value)
        draw_design = sorted(value for value in bucket["draw_design"] if value)
        hunt_type = sorted(value for value in bucket["hunt_type"] if value)
        if len(hunt_name) != 1 or len(weapon) != 1 or len(draw_design) != 1 or len(hunt_type) != 1:
            raise RuntimeError(f"Ambiguous donor truth for {code} {source_group}")
        truth.setdefault(code, {})[source_group] = {
            "hunt_name": hunt_name[0],
            "weapon": weapon[0],
            "draw_design": draw_design[0],
            "hunt_type": hunt_type[0],
            "permits_2026_res": str(bucket["res"]),
            "permits_2026_nr": str(bucket["nr"]),
            "permits_2026_total": str(int(bucket["res"]) + int(bucket["nr"])),
            "source_file": str(bucket["source_file"]),
        }
    return truth


def main() -> int:
    donor_truth = load_donor_truth()
    db_rows, db_fields = read_csv(DATABASE)
    db_by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows if clean(row.get("hunt_code"))}
    missing_codes = sorted(set(donor_truth) - set(db_by_code))
    if missing_codes:
        raise RuntimeError(f"Donor/live elk codes missing from DATABASE.csv: {missing_codes[:20]}")

    backup = backup_database()
    patch_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()

    for code, variants in sorted(donor_truth.items()):
        row = db_by_code[code]
        source_group = "CWMU" if clean(row.get("hunt_type")) == "CWMU" and "CWMU" in variants else "LE"
        if source_group not in variants:
            source_group = sorted(variants.keys())[0]
        source = variants[source_group]
        before_name = clean(row.get("hunt_name"))
        before_weapon = clean(row.get("weapon"))
        before_draw_design = clean(row.get("hunt_class"))
        before_hunt_type = clean(row.get("hunt_type"))
        before_res = clean(row.get("permits_2026_res"))
        before_nr = clean(row.get("permits_2026_nr"))
        before_total = clean(row.get("permits_2026_total"))

        changed_fields: list[str] = []
        notes: list[str] = []

        if before_name != source["hunt_name"]:
            row["hunt_name"] = source["hunt_name"]
            changed_fields.append("hunt_name")
            notes.append("Updated current database hunt name to donor/live draw truth.")

        if before_weapon != source["weapon"]:
            row["weapon"] = source["weapon"]
            changed_fields.append("weapon")
            notes.append("Backfilled blank/conflicting weapon from donor/live draw truth.")

        if before_draw_design != source["draw_design"]:
            row["hunt_class"] = source["draw_design"]
            changed_fields.append("hunt_class")
            notes.append("Aligned draw design to donor/live draw truth.")

        permit_notes: list[str] = []
        if before_res != source["permits_2026_res"]:
            permit_notes.append("resident")
        if before_nr != source["permits_2026_nr"]:
            permit_notes.append("nonresident")
        if before_total != source["permits_2026_total"]:
            permit_notes.append("total")

        if permit_notes:
            row["permits_2026_res"] = source["permits_2026_res"]
            row["permits_2026_nr"] = source["permits_2026_nr"]
            row["permits_2026_total"] = source["permits_2026_total"]
            row["permits_2026_source"] = source["source_file"]
            row["permits_2026_draw_source"] = source["source_file"]
            changed_fields.extend(
                ["permits_2026_res", "permits_2026_nr", "permits_2026_total", "permits_2026_source", "permits_2026_draw_source"]
            )
            notes.append(f"Promoted donor/live permit truth over DB for {', '.join(permit_notes)} fields.")
        else:
            notes.append("Permit totals already matched donor/live truth; no permit overwrite needed.")

        if before_hunt_type != source["hunt_type"]:
            notes.append(
                f"Donor/live package labels hunt_type `{source['hunt_type']}`, but DB hunt_type `{before_hunt_type}` was retained."
            )

        status = "UPDATED" if changed_fields else "UNCHANGED"
        status_counts[status] += 1
        patch_rows.append(
            {
                "hunt_code": code,
                "source_group": source_group,
                "source_file": source["source_file"],
                "before_hunt_name": before_name,
                "after_hunt_name": clean(row.get("hunt_name")),
                "before_weapon_type": before_weapon,
                "after_weapon_type": clean(row.get("weapon")),
                "before_hunt_type": before_hunt_type,
                "donor_live_hunt_type": source["hunt_type"],
                "before_hunt_class": before_draw_design,
                "after_hunt_class": clean(row.get("hunt_class")),
                "before_permits_2026_res": before_res,
                "after_permits_2026_res": clean(row.get("permits_2026_res")),
                "before_permits_2026_nr": before_nr,
                "after_permits_2026_nr": clean(row.get("permits_2026_nr")),
                "before_permits_2026_total": before_total,
                "after_permits_2026_total": clean(row.get("permits_2026_total")),
                "changed_fields": "|".join(changed_fields),
                "status": status,
                "source_label": SOURCE_LABEL,
                "notes": " ".join(notes),
            }
        )

    write_csv(DATABASE, db_rows, db_fields)

    patch_fields = [
        "hunt_code",
        "source_group",
        "source_file",
        "before_hunt_name",
        "after_hunt_name",
        "before_weapon_type",
        "after_weapon_type",
        "before_hunt_type",
        "donor_live_hunt_type",
        "before_hunt_class",
        "after_hunt_class",
        "before_permits_2026_res",
        "after_permits_2026_res",
        "before_permits_2026_nr",
        "after_permits_2026_nr",
        "before_permits_2026_total",
        "after_permits_2026_total",
        "changed_fields",
        "status",
        "source_label",
        "notes",
    ]
    write_csv(OUT_PATCH, patch_rows, patch_fields)

    changed_rows = [row for row in patch_rows if row["status"] == "UPDATED"]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "donor_equivalent_source_files": [LE_SOURCE_FILE, CWMU_SOURCE_FILE],
        "source_label": SOURCE_LABEL,
        "donor_truth_hunt_code_count": len(donor_truth),
        "updated_database_rows": len(changed_rows),
        "unchanged_database_rows": len(patch_rows) - len(changed_rows),
        "weapon_type_updates": sum("weapon" in row["changed_fields"].split("|") for row in patch_rows),
        "hunt_name_updates": sum("hunt_name" in row["changed_fields"].split("|") for row in patch_rows),
        "hunt_class_updates": sum("hunt_class" in row["changed_fields"].split("|") for row in patch_rows),
        "permit_value_updates": sum(
            any(field in row["changed_fields"].split("|") for field in ["permits_2026_res", "permits_2026_nr", "permits_2026_total"])
            for row in patch_rows
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Retained existing DB hunt_type taxonomy where donor/live package labels all rows as limited-entry package members.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_DOC.write_text(
        "\n".join(
            [
                "# 2026 L.E. Elk Donor Reconciliation To DATABASE",
                "",
                "Applied donor-equivalent UtahDraws DrawOddsData truth for the 2026 elk limited-entry package into `DATABASE.csv`.",
                "",
                f"- Donor-equivalent hunt codes: `{summary['donor_truth_hunt_code_count']}`",
                f"- Updated rows: `{summary['updated_database_rows']}`",
                f"- Weapon updates: `{summary['weapon_type_updates']}`",
                f"- Hunt name updates: `{summary['hunt_name_updates']}`",
                f"- Permit value updates: `{summary['permit_value_updates']}`",
                f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
                "",
                "Guardrail: retained existing DB `hunt_type` taxonomy where the donor/live package groups both public and CWMU elk under the same limited-entry draw source.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
