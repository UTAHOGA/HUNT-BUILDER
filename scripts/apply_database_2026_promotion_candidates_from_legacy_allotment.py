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
AUDIT_CSV = ROOT / "processed_data" / "audits" / "database_2026_promotion_candidates_apply_audit.csv"
SUMMARY_JSON = ROOT / "processed_data" / "audits" / "database_2026_promotion_candidates_apply_summary.json"
SUMMARY_MD = ROOT / "processed_data" / "audits" / "database_2026_promotion_candidates_apply_summary.md"

PROMOTE_ACTIONS = {
    "PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT",
    "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY",
}

PROMOTED_SOURCE_LABEL = "REVIEWED_2026_PUBLISHED_PERMIT_PROMOTION_FROM_LEGACY_COMPAT"
PROMOTED_STATUS_COMPAT = "DERIVED_FROM_PUBLISHED_2026_PERMITS_COMPAT"


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
    dest = BACKUP_ROOT / f"database_legacy_promotions_{stamp}" / DATABASE.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, dest)
    return dest


def published_missing_or_zero(row: dict[str, str]) -> bool:
    return all(clean(row.get(field)) in {"", "0"} for field in ("permits_2026_res", "permits_2026_nr", "permits_2026_total"))


def load_promotion_rows() -> dict[str, dict[str, str]]:
    _, rows = read_csv(ACTIONS)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        action = clean(row.get("mismatch_action"))
        if action not in PROMOTE_ACTIONS:
            continue
        code = clean(row.get("hunt_code")).upper()
        if code:
            out[code] = row
    return out


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    promotions = load_promotion_rows()
    fieldnames, rows = read_csv(DATABASE)
    backup = backup_database(stamp)

    audit_rows: list[dict[str, str]] = []
    action_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    codes_applied = 0
    codes_skipped = 0
    cells_changed = 0

    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        spec = promotions.get(code)
        if not spec:
            continue

        action = clean(spec.get("mismatch_action"))
        family = clean(row.get("draw_2026_system_type")) or clean(row.get("hunt_class")) or "UNKNOWN"

        if not published_missing_or_zero(row):
            codes_skipped += 1
            audit_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "family": family,
                    "action": action,
                    "result": "SKIPPED_PUBLISHED_ALREADY_POPULATED",
                    "field": "",
                    "before": "",
                    "after": "",
                }
            )
            continue

        if action == "PROMOTE_ALLOTMENT_TO_PUBLISHED_SPLIT":
            replacements = {
                "permits_2026_res": clean(row.get("permit_allotment_2026_res")),
                "permits_2026_nr": clean(row.get("permit_allotment_2026_nr")),
                "permits_2026_total": clean(row.get("permit_allotment_2026_total")),
            }
        elif action == "PROMOTE_ALLOTMENT_TO_PUBLISHED_TOTAL_ONLY":
            replacements = {
                "permits_2026_total": clean(row.get("permit_allotment_2026_total")),
            }
        else:
            continue

        legacy_source = clean(row.get("permit_allotment_2026_source"))
        promoted_source = legacy_source or PROMOTED_SOURCE_LABEL
        replacements["permits_2026_source"] = promoted_source

        # Collapse the legacy shadow to the new published values so it cannot drift back out.
        final_res = replacements.get("permits_2026_res", clean(row.get("permits_2026_res")))
        final_nr = replacements.get("permits_2026_nr", clean(row.get("permits_2026_nr")))
        final_total = replacements.get("permits_2026_total", clean(row.get("permits_2026_total")))
        replacements.update(
            {
                "permit_allotment_2026_res": final_res,
                "permit_allotment_2026_nr": final_nr,
                "permit_allotment_2026_total": final_total,
                "permit_allotment_2026_source": PROMOTED_SOURCE_LABEL,
                "permit_allotment_2026_source_file": str(ACTIONS.relative_to(ROOT)).replace("\\", "/"),
                "permit_allotment_2026_status": PROMOTED_STATUS_COMPAT,
            }
        )

        row_changed = False
        for field, after in replacements.items():
            before = clean(row.get(field))
            if before == after:
                continue
            row[field] = after
            row_changed = True
            cells_changed += 1
            audit_rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "family": family,
                    "action": action,
                    "result": "APPLIED",
                    "field": field,
                    "before": before,
                    "after": after,
                }
            )
        if row_changed:
            codes_applied += 1
            action_counts[action] += 1
            family_counts[family] += 1

    write_csv(DATABASE, fieldnames, rows)
    write_csv(AUDIT_CSV, list(audit_rows[0].keys()) if audit_rows else ["hunt_code"], audit_rows or [{"hunt_code": ""}])

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_file": str(DATABASE.relative_to(ROOT)).replace("\\", "/"),
        "backup_file": str(backup.relative_to(ROOT)).replace("\\", "/"),
        "promotion_actions_applied": dict(action_counts),
        "family_counts": dict(family_counts),
        "codes_applied": codes_applied,
        "codes_skipped_published_already_populated": codes_skipped,
        "cells_changed": cells_changed,
        "audit_csv": str(AUDIT_CSV.relative_to(ROOT)).replace("\\", "/"),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(
        "\n".join(
            [
                "# DATABASE 2026 Promotion Candidates Apply",
                "",
                f"Generated: `{summary['generated_at_utc']}`",
                "",
                "- Applied only classifier-approved promotion candidates.",
                "- Published `permits_2026_*` stayed authoritative.",
                "- Any row with already-populated published permit values was skipped.",
                "- Manual-review/CWMU rows were not touched.",
                "",
                f"- Codes applied: `{codes_applied}`",
                f"- Codes skipped because published values already existed: `{codes_skipped}`",
                f"- Cells changed: `{cells_changed}`",
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
