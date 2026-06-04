"""Apply approved 2026 permit allotment reconciliations to DATABASE.csv.

Approved scope:
- exact DATABASE/recommended matches: audit as reconciled, no numeric edit needed
- total-only matches: fill only blank split cells when the recommended split exists
- blank DATABASE with recommendation: fill available recommended values

True DATABASE-vs-recommendation disagreements are left untouched.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"

OUT_AUDIT = ROOT / "processed_data/audits/database_allotment_database_patch_2026.csv"
OUT_TRUE_DISAGREEMENTS = ROOT / "processed_data/audits/database_allotment_true_disagreements_after_patch_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/database_allotment_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/database_allotment_database_patch_2026.md"

SOURCE_FILES = {
    "HANUMBER": "processed_data/dwr_huntplanner_hanumber_2026.csv",
    "HUNTTABLE": "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv",
    "UTAHDRAWS": "processed_data/audits/dwr_2026_draw_results_vs_database_allotments.csv",
    "BUCK_DEER": "processed_data/audits/buck_deer_current_permit_source_2026_corrected.csv",
}

EXACT_MATCH = "DATABASE_MATCHES_RECOMMENDED"
TOTAL_MATCH = "DATABASE_TOTAL_MATCHES_RECOMMENDED"
BLANK_WITH_VALUE = "DATABASE_BLANK_RECOMMENDATION_HAS_VALUE"
TRUE_DISAGREE = "DATABASE_DIFFERS_FROM_RECOMMENDED"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return ""
        number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


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
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_allotment_reconciliation_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def set_source_metadata(row: dict[str, str], recon: dict[str, str], status: str) -> None:
    winner = clean(recon.get("winner_source")).upper()
    row["permit_allotment_2026_source"] = f"2026_CURRENT_PERMIT_RECONCILIATION:{winner}"
    row["permit_allotment_2026_source_file"] = SOURCE_FILES.get(winner, clean(recon.get("winner_source")))
    row["permit_allotment_2026_status"] = status


def main() -> int:
    db_rows, db_fields = read_csv(DATABASE)
    recon_rows, _ = read_csv(RECON)
    recon_by_code = {clean(row.get("hunt_code")).upper(): row for row in recon_rows if clean(row.get("hunt_code"))}
    db_codes = {clean(row.get("hunt_code")).upper() for row in db_rows if clean(row.get("hunt_code"))}

    backup = backup_database()

    audit_rows: list[dict[str, object]] = []
    true_disagreement_rows: list[dict[str, object]] = []
    action_counts: Counter[str] = Counter()
    changed_cell_count = 0

    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        recon = recon_by_code.get(code)
        if not recon:
            continue

        alignment = clean(recon.get("database_alignment"))
        db_before = {
            "res": int_text(row.get("permit_allotment_2026_res")),
            "nr": int_text(row.get("permit_allotment_2026_nr")),
            "total": int_text(row.get("permit_allotment_2026_total")),
            "source": clean(row.get("permit_allotment_2026_source")),
            "source_file": clean(row.get("permit_allotment_2026_source_file")),
            "status": clean(row.get("permit_allotment_2026_status")),
        }
        rec = {
            "res": int_text(recon.get("recommended_res")),
            "nr": int_text(recon.get("recommended_nr")),
            "total": int_text(recon.get("recommended_total")),
        }
        changed_fields: list[str] = []
        action = ""
        notes = ""

        if alignment == EXACT_MATCH:
            action = "RECONCILED_EXACT_MATCH_NO_NUMERIC_CHANGE"
            notes = "DATABASE allotment already matches recommended resident/nonresident/total values."
        elif alignment == TOTAL_MATCH:
            action = "RECONCILED_TOTAL_MATCH"
            notes = "DATABASE total already matches recommended total."
            for field, column in [
                ("res", "permit_allotment_2026_res"),
                ("nr", "permit_allotment_2026_nr"),
            ]:
                if not db_before[field] and rec[field]:
                    row[column] = rec[field]
                    changed_fields.append(column)
            if changed_fields:
                set_source_metadata(row, recon, "RECONCILED_2026_TOTAL_MATCH_SPLIT_FILLED")
                changed_fields.extend(
                    [
                        "permit_allotment_2026_source",
                        "permit_allotment_2026_source_file",
                        "permit_allotment_2026_status",
                    ]
                )
                notes += " Blank split cell(s) were filled from the recommended source."
            else:
                notes += " No split cells were safely fillable."
        elif alignment == BLANK_WITH_VALUE:
            action = "RECONCILED_DATABASE_BLANK_FILLED"
            for field, column in [
                ("res", "permit_allotment_2026_res"),
                ("nr", "permit_allotment_2026_nr"),
                ("total", "permit_allotment_2026_total"),
            ]:
                if rec[field]:
                    row[column] = rec[field]
                    changed_fields.append(column)
            if changed_fields:
                status = (
                    "RECONCILED_2026_RECOMMENDED_RES_NR_SPLIT"
                    if rec["res"] or rec["nr"]
                    else "RECONCILED_2026_RECOMMENDED_TOTAL_ONLY"
                )
                set_source_metadata(row, recon, status)
                changed_fields.extend(
                    [
                        "permit_allotment_2026_source",
                        "permit_allotment_2026_source_file",
                        "permit_allotment_2026_status",
                    ]
                )
                notes = "DATABASE allotment was blank; available recommended value(s) were populated."
            else:
                action = "NO_ACTION_RECOMMENDATION_EMPTY"
                notes = "DATABASE was blank, but no recommended numeric value was available."
        elif alignment == TRUE_DISAGREE:
            action = "LEFT_UNCHANGED_TRUE_DISAGREEMENT"
            notes = "DATABASE has a nonblank value that differs from the recommended source; left for review."
            true_disagreement_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "species": clean(row.get("species")),
                    "database_allotment_2026_res": db_before["res"],
                    "database_allotment_2026_nr": db_before["nr"],
                    "database_allotment_2026_total": db_before["total"],
                    "recommended_res": rec["res"],
                    "recommended_nr": rec["nr"],
                    "recommended_total": rec["total"],
                    "winner_source": clean(recon.get("winner_source")),
                    "confidence": clean(recon.get("confidence")),
                    "source_support_count": clean(recon.get("source_support_count")),
                    "notes": notes,
                }
            )
        else:
            continue

        db_after = {
            "res": int_text(row.get("permit_allotment_2026_res")),
            "nr": int_text(row.get("permit_allotment_2026_nr")),
            "total": int_text(row.get("permit_allotment_2026_total")),
            "source": clean(row.get("permit_allotment_2026_source")),
            "source_file": clean(row.get("permit_allotment_2026_source_file")),
            "status": clean(row.get("permit_allotment_2026_status")),
        }
        changed_cell_count += len(changed_fields)
        action_counts[action] += 1
        audit_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "database_alignment": alignment,
                "action_taken": action,
                "changed_fields": "|".join(changed_fields),
                "before_res": db_before["res"],
                "before_nr": db_before["nr"],
                "before_total": db_before["total"],
                "after_res": db_after["res"],
                "after_nr": db_after["nr"],
                "after_total": db_after["total"],
                "recommended_res": rec["res"],
                "recommended_nr": rec["nr"],
                "recommended_total": rec["total"],
                "winner_source": clean(recon.get("winner_source")),
                "confidence": clean(recon.get("confidence")),
                "source_support_count": clean(recon.get("source_support_count")),
                "before_source": db_before["source"],
                "after_source": db_after["source"],
                "before_status": db_before["status"],
                "after_status": db_after["status"],
                "notes": notes,
            }
        )

    for recon in recon_rows:
        code = clean(recon.get("hunt_code")).upper()
        if not code or code in db_codes:
            continue
        if clean(recon.get("database_alignment")) != BLANK_WITH_VALUE:
            continue

        rec = {
            "res": int_text(recon.get("recommended_res")),
            "nr": int_text(recon.get("recommended_nr")),
            "total": int_text(recon.get("recommended_total")),
        }
        if not any(rec.values()):
            continue

        new_row = {field: "" for field in db_fields}
        new_row["hunt_code"] = code
        new_row["hunt_name"] = clean(recon.get("hunt_name"))
        new_row["species"] = clean(recon.get("species"))
        new_row["sex_type"] = clean(recon.get("sex_type"))
        new_row["weapon"] = clean(recon.get("weapon"))
        new_row["hunt_type"] = clean(recon.get("hunt_type"))
        new_row["season"] = clean(recon.get("season"))
        if "NOTES" in new_row:
            new_row["NOTES"] = "Added from approved 2026 current permit reconciliation blank-DATABASE fill."
        new_row["permit_allotment_2026_res"] = rec["res"]
        new_row["permit_allotment_2026_nr"] = rec["nr"]
        new_row["permit_allotment_2026_total"] = rec["total"]
        set_source_metadata(
            new_row,
            recon,
            "RECONCILED_2026_RECOMMENDED_RES_NR_SPLIT"
            if rec["res"] or rec["nr"]
            else "RECONCILED_2026_RECOMMENDED_TOTAL_ONLY",
        )
        db_rows.append(new_row)
        db_codes.add(code)
        changed_fields = [
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "weapon",
            "hunt_type",
            "season",
            "permit_allotment_2026_res",
            "permit_allotment_2026_nr",
            "permit_allotment_2026_total",
            "permit_allotment_2026_source",
            "permit_allotment_2026_source_file",
            "permit_allotment_2026_status",
        ]
        action = "ADDED_DATABASE_ROW_FROM_BLANK_RECOMMENDATION"
        action_counts[action] += 1
        changed_cell_count += len(changed_fields)
        audit_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(recon.get("hunt_name")),
                "species": clean(recon.get("species")),
                "database_alignment": BLANK_WITH_VALUE,
                "action_taken": action,
                "changed_fields": "|".join(changed_fields),
                "before_res": "",
                "before_nr": "",
                "before_total": "",
                "after_res": rec["res"],
                "after_nr": rec["nr"],
                "after_total": rec["total"],
                "recommended_res": rec["res"],
                "recommended_nr": rec["nr"],
                "recommended_total": rec["total"],
                "winner_source": clean(recon.get("winner_source")),
                "confidence": clean(recon.get("confidence")),
                "source_support_count": clean(recon.get("source_support_count")),
                "before_source": "",
                "after_source": new_row["permit_allotment_2026_source"],
                "before_status": "",
                "after_status": new_row["permit_allotment_2026_status"],
                "notes": "Hunt code was absent from DATABASE.csv; added as an approved blank-DATABASE recommendation fill.",
            }
        )

    with DATABASE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=db_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(db_rows)

    audit_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "database_alignment",
        "action_taken",
        "changed_fields",
        "before_res",
        "before_nr",
        "before_total",
        "after_res",
        "after_nr",
        "after_total",
        "recommended_res",
        "recommended_nr",
        "recommended_total",
        "winner_source",
        "confidence",
        "source_support_count",
        "before_source",
        "after_source",
        "before_status",
        "after_status",
        "notes",
    ]
    disagreement_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "database_allotment_2026_res",
        "database_allotment_2026_nr",
        "database_allotment_2026_total",
        "recommended_res",
        "recommended_nr",
        "recommended_total",
        "winner_source",
        "confidence",
        "source_support_count",
        "notes",
    ]
    write_csv(OUT_AUDIT, sorted(audit_rows, key=lambda row: str(row["hunt_code"])), audit_fields)
    write_csv(
        OUT_TRUE_DISAGREEMENTS,
        sorted(true_disagreement_rows, key=lambda row: str(row["hunt_code"])),
        disagreement_fields,
    )

    numeric_changed_rows = [
        row for row in audit_rows if any(field in str(row["changed_fields"]).split("|") for field in [
            "permit_allotment_2026_res",
            "permit_allotment_2026_nr",
            "permit_allotment_2026_total",
        ])
    ]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "source_reconciliation_csv": RECON.relative_to(ROOT).as_posix(),
        "action_counts": dict(sorted(action_counts.items())),
        "audit_rows": len(audit_rows),
        "numeric_changed_rows": len(numeric_changed_rows),
        "changed_cell_count_including_lineage": changed_cell_count,
        "true_disagreements_left_unchanged": len(true_disagreement_rows),
        "source_meanings": {
            "allotment_numbers": "DATABASE.csv permit_allotment_2026_* fields, previously populated from live DWR Hunt Planner/HuntTable current allotment pulls where available.",
            "recommended_numbers": "Current-source reconciliation winner from HaNumber, HuntTable, Buck Deer repair source, or UtahDraws, with DATABASE used only as a comparison/reference source.",
        },
        "outputs": {
            "patch_audit_csv": OUT_AUDIT.relative_to(ROOT).as_posix(),
            "true_disagreements_csv": OUT_TRUE_DISAGREEMENTS.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Rows where DATABASE had a nonblank value differing from the recommendation were not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# DATABASE Allotment Database Patch 2026",
        "",
        "## Source Meaning",
        "",
        "- `DATABASE.csv` allotment numbers are the `permit_allotment_2026_*` fields. In the current project lineage, populated allotment rows primarily came from live DWR Hunt Planner / HuntTable current-year pulls.",
        "- Recommended numbers are the selected current-source winner from the permit reconciliation file. Source precedence is HaNumber, HuntTable, Buck Deer repaired source, then UtahDraws. DATABASE is comparison/reference only in that winner selection.",
        "",
        "## Applied Scope",
        "",
        "- Exact DATABASE/recommended matches were reconciled in the audit with no numeric DATABASE edit needed.",
        "- Total-only matches were reconciled by total. Blank resident/nonresident split cells were filled only when the recommended split was present.",
        "- Blank DATABASE allotment rows with recommended values were populated.",
        "- True nonblank DATABASE disagreements were left unchanged.",
        "",
        "## Key Counts",
        "",
    ]
    for action, count in sorted(action_counts.items()):
        lines.append(f"- `{action}`: `{count}`")
    lines.extend(
        [
            f"- Numeric rows changed: `{len(numeric_changed_rows)}`",
            f"- True disagreements left unchanged: `{len(true_disagreement_rows)}`",
            "",
            "## Outputs",
            "",
            f"- Patch audit: `{OUT_AUDIT.relative_to(ROOT).as_posix()}`",
            f"- True disagreements: `{OUT_TRUE_DISAGREEMENTS.relative_to(ROOT).as_posix()}`",
            f"- Summary: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
            f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
