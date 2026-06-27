"""Promote comprehensive live 2026 DWR permit totals into DATABASE.csv.

This script promotes the full live DWR Hunt Planner snapshot over older RAC or
allotment-derived 2026 values wherever DWR publishes a numeric permit total.
Rows where DWR publishes no quota are preserved.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
LIVE_SNAPSHOT = ROOT / "data_truth/crosswalk_truth/raw_inventory/live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv"
AUDIT_OUT = ROOT / "data_truth/crosswalk_truth/validation/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026.csv"
SUMMARY_OUT = ROOT / "data_truth/crosswalk_truth/validation/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026_summary.json"
REPORT_OUT = ROOT / "processed_data/comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026.md"

SOURCE_LABEL = "2026_LIVE_DWR_HUNT_PLANNER_COMPREHENSIVE"
TOTAL_ONLY_TYPES = {
    "CWMU",
    "Private Lands Only",
    "Conservation",
    "Expo",
    "Antlerless Elk Control",
    "General Season - Youth",
    "Statewide",
}


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\ufeff", "")
    return "" if text in {"", "-", "nan", "None"} else text


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: clean(value) for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def live_shape(row: dict[str, str]) -> tuple[str, str, str, str]:
    hunt_type = clean(row.get("hunt_type"))
    live_res = int_text(row.get("live_res"))
    live_nr = int_text(row.get("live_nr"))
    live_total = int_text(row.get("live_total"))

    if hunt_type == "CWMU":
        total = live_res if live_res not in {"", "0"} else live_total
        return "", "", total, "LIVE_DWR_CWMU_TOTAL_ONLY_FROM_QUOTA_RES"

    if hunt_type in TOTAL_ONLY_TYPES:
        total = live_total or live_res
        if total in {"", "0"}:
            return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED"
        return "", "", total, "LIVE_DWR_TOTAL_ONLY"

    if live_total in {"", "0"} and live_res in {"", "0"} and live_nr in {"", "0"}:
        return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED"

    if live_total in {"", "0"} and (live_res not in {"", "0"} or live_nr not in {"", "0"}):
        live_total = str(int(live_res or 0) + int(live_nr or 0))

    if live_total not in {"", "0"} and live_res in {"", "0"} and live_nr in {"", "0"}:
        return "", "", live_total, "LIVE_DWR_TOTAL_ONLY"

    if live_res not in {"", "0"} and live_total and live_nr in {"", "0"} and int(live_total) > int(live_res):
        live_nr = str(int(live_total) - int(live_res))
    return live_res, live_nr, live_total, "LIVE_DWR_RES_NR_SPLIT"


def old_snapshot(row: dict[str, str]) -> dict[str, str]:
    return {
        "old_permits_2026_res": row.get("permits_2026_res", ""),
        "old_permits_2026_nr": row.get("permits_2026_nr", ""),
        "old_permits_2026_total": row.get("permits_2026_total", ""),
        "old_permits_2026_source": row.get("permits_2026_source", ""),
        "old_permit_allotment_2026_res": row.get("permit_allotment_2026_res", ""),
        "old_permit_allotment_2026_nr": row.get("permit_allotment_2026_nr", ""),
        "old_permit_allotment_2026_total": row.get("permit_allotment_2026_total", ""),
        "old_permit_allotment_2026_source": row.get("permit_allotment_2026_source", ""),
        "old_permit_allotment_2026_status": row.get("permit_allotment_2026_status", ""),
    }


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db_rows, db_fields = read_csv(DATABASE)
    live_rows, _ = read_csv(LIVE_SNAPSHOT)
    live_by_code = {row["hunt_code"]: row for row in live_rows if row.get("hunt_code")}
    db_codes = {row["hunt_code"] for row in db_rows if row.get("hunt_code")}

    audit_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    changed_rows = 0
    numeric_promoted_rows = 0
    preserved_no_quota_rows = 0

    for row in db_rows:
        code = row.get("hunt_code", "")
        live = live_by_code.get(code)
        if not live:
            continue

        new_res, new_nr, new_total, shape_status = live_shape(live)
        shape_counts[shape_status] += 1
        before = old_snapshot(row)

        if shape_status == "LIVE_DWR_NO_QUOTA_PUBLISHED":
            preserved_no_quota_rows += 1
            status = "PRESERVED_DATABASE_VALUE_NO_LIVE_DWR_QUOTA"
            changed_fields = []
        else:
            numeric_promoted_rows += 1
            new_values = {
                "permits_2026_res": new_res,
                "permits_2026_nr": new_nr,
                "permits_2026_total": new_total,
                "permits_2026_source": SOURCE_LABEL,
                "permit_allotment_2026_res": new_res,
                "permit_allotment_2026_nr": new_nr,
                "permit_allotment_2026_total": new_total,
                "permit_allotment_2026_source": SOURCE_LABEL,
                "permit_allotment_2026_source_file": live.get("source_url", ""),
                "permit_allotment_2026_status": shape_status,
            }
            changed_fields = [field for field, value in new_values.items() if row.get(field, "") != value]
            if changed_fields:
                changed_rows += 1
                row.update(new_values)
                status = "PROMOTED_LIVE_DWR_OVER_ALLOTMENT"
            else:
                status = "UNCHANGED_ALREADY_MATCHED_LIVE_DWR"
        status_counts[status] += 1

        audit_rows.append(
            {
                "snapshot_utc": timestamp,
                "hunt_code": code,
                "hunt_name": row.get("hunt_name", ""),
                "species": row.get("species", ""),
                "sex_type": row.get("sex_type", ""),
                "weapon": row.get("weapon", ""),
                "hunt_type": row.get("hunt_type", ""),
                "live_res": live.get("live_res", ""),
                "live_nr": live.get("live_nr", ""),
                "live_total": live.get("live_total", ""),
                "shaped_res": new_res,
                "shaped_nr": new_nr,
                "shaped_total": new_total,
                "shape_status": shape_status,
                "promotion_status": status,
                "changed_fields": "|".join(changed_fields),
                "source_url": live.get("source_url", ""),
                **before,
                "new_permits_2026_res": row.get("permits_2026_res", ""),
                "new_permits_2026_nr": row.get("permits_2026_nr", ""),
                "new_permits_2026_total": row.get("permits_2026_total", ""),
                "new_permits_2026_source": row.get("permits_2026_source", ""),
                "new_permit_allotment_2026_res": row.get("permit_allotment_2026_res", ""),
                "new_permit_allotment_2026_nr": row.get("permit_allotment_2026_nr", ""),
                "new_permit_allotment_2026_total": row.get("permit_allotment_2026_total", ""),
                "new_permit_allotment_2026_source": row.get("permit_allotment_2026_source", ""),
                "new_permit_allotment_2026_status": row.get("permit_allotment_2026_status", ""),
            }
        )

    missing_database = sorted(set(live_by_code) - db_codes)
    write_csv(DATABASE, db_rows, db_fields)

    audit_fields = [
        "snapshot_utc",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "live_res",
        "live_nr",
        "live_total",
        "shaped_res",
        "shaped_nr",
        "shaped_total",
        "shape_status",
        "promotion_status",
        "changed_fields",
        "source_url",
        "old_permits_2026_res",
        "old_permits_2026_nr",
        "old_permits_2026_total",
        "old_permits_2026_source",
        "old_permit_allotment_2026_res",
        "old_permit_allotment_2026_nr",
        "old_permit_allotment_2026_total",
        "old_permit_allotment_2026_source",
        "old_permit_allotment_2026_status",
        "new_permits_2026_res",
        "new_permits_2026_nr",
        "new_permits_2026_total",
        "new_permits_2026_source",
        "new_permit_allotment_2026_res",
        "new_permit_allotment_2026_nr",
        "new_permit_allotment_2026_total",
        "new_permit_allotment_2026_source",
        "new_permit_allotment_2026_status",
    ]
    write_csv(AUDIT_OUT, audit_rows, audit_fields)

    summary = {
        "artifact": "comprehensive_live_dwr_permit_totals_promoted_to_DATABASE_2026",
        "snapshot_utc": timestamp,
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "source_snapshot": LIVE_SNAPSHOT.relative_to(ROOT).as_posix(),
        "live_row_count": len(live_rows),
        "live_database_matched_row_count": len(audit_rows),
        "numeric_promoted_rows": numeric_promoted_rows,
        "preserved_no_quota_rows": preserved_no_quota_rows,
        "changed_rows": changed_rows,
        "missing_database_count": len(missing_database),
        "missing_database_codes": missing_database,
        "promotion_status_counts": dict(sorted(status_counts.items())),
        "shape_status_counts": dict(sorted(shape_counts.items())),
        "guardrail": "Live DWR numeric 2026 permit totals supersede older allotment-derived values. DWR no-quota rows preserve reviewed database-entered values.",
        "outputs": {
            "audit_csv": AUDIT_OUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_OUT.relative_to(ROOT).as_posix(),
            "report_md": REPORT_OUT.relative_to(ROOT).as_posix(),
        },
    }
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Comprehensive Live DWR Permit Totals Promoted To DATABASE 2026",
        "",
        f"- Snapshot UTC: `{timestamp}`",
        f"- Live rows: `{len(live_rows)}`",
        f"- Live/database matched rows: `{len(audit_rows)}`",
        f"- Numeric promoted rows: `{numeric_promoted_rows}`",
        f"- DWR no-quota rows preserved: `{preserved_no_quota_rows}`",
        f"- Changed rows: `{changed_rows}`",
        f"- Missing DATABASE rows: `{len(missing_database)}`",
        "",
        "## Promotion Status Counts",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Shape Status Counts", ""])
    for status, count in sorted(shape_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if missing_database else 0


if __name__ == "__main__":
    raise SystemExit(main())
