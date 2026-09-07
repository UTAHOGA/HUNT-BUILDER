"""Promote reviewed live DWR Hunt Planner permit numbers into DATABASE.csv.

Guardrails:
- Uses only the live permit-number snapshot produced from DWR HuntTableData.
- Shapes CWMU rows as total-only permits because DWR publishes the CWMU public
  permit count in QUOTA_RES while QUOTA is 0.
- Does not invent resident/nonresident splits for CWMU, private lands, expo,
  conservation, control, or other total-only/no-quota rows.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
LIVE_SNAPSHOT = (
    ROOT
    / "data_truth"
    / "crosswalk_truth"
    / "raw_inventory"
    / "live_dwr_hunt_planner_permit_numbers_2026.csv"
)
AUDIT_OUT = (
    ROOT
    / "data_truth"
    / "crosswalk_truth"
    / "validation"
    / "live_dwr_permit_numbers_promoted_to_DATABASE_2026.csv"
)
SUMMARY_OUT = (
    ROOT
    / "data_truth"
    / "crosswalk_truth"
    / "validation"
    / "live_dwr_permit_numbers_promoted_to_DATABASE_2026_summary.json"
)
REPORT_OUT = ROOT / "processed_data/live_dwr_permit_numbers_promoted_to_DATABASE_2026.md"

SOURCE_LABEL = "2026_LIVE_DWR_HUNT_PLANNER_HUNTTABLEDATA"
NO_QUOTA_LABEL = "2026_LIVE_DWR_HUNT_PLANNER_NO_QUOTA_PUBLISHED"
TOTAL_ONLY_TYPES = {"CWMU", "Private Lands Only", "Conservation", "Expo", "Antlerless Elk Control"}
ARCHIVED_PRIOR_YEAR_HUNT_CODES = {"EA1281"}


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


def live_shape(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    hunt_type = clean(row.get("hunt_type"))
    live_res = int_text(row.get("live_res"))
    live_nr = int_text(row.get("live_nr"))
    live_total = int_text(row.get("live_total"))
    source_url = clean(row.get("source_url"))

    if hunt_type == "CWMU":
        total = live_res if live_res not in {"", "0"} else live_total
        return "", "", total, "LIVE_DWR_CWMU_TOTAL_ONLY_FROM_QUOTA_RES", source_url

    if hunt_type in TOTAL_ONLY_TYPES:
        total = live_total or live_res
        if total in {"", "0"}:
            return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED", source_url
        return "", "", total, "LIVE_DWR_TOTAL_ONLY", source_url

    if live_total in {"", "0"} and live_res in {"", "0"} and live_nr in {"", "0"}:
        return "", "", "", "LIVE_DWR_NO_QUOTA_PUBLISHED", source_url

    return live_res, live_nr, live_total, "LIVE_DWR_RES_NR_SPLIT", source_url


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db_rows, db_fields = read_csv(DATABASE)
    live_rows, _ = read_csv(LIVE_SNAPSHOT)
    live_by_code = {
        row["hunt_code"]: row
        for row in live_rows
        if row.get("hunt_code") and row["hunt_code"] not in ARCHIVED_PRIOR_YEAR_HUNT_CODES
    }

    audit_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    changed_rows = 0
    changed_cells = 0
    missing_database: list[str] = []

    for row in db_rows:
        code = clean(row.get("hunt_code")).upper()
        live = live_by_code.get(code)
        if not live:
            continue
        new_res, new_nr, new_total, shape_status, source_url = live_shape(live)
        old_values = {
            "permits_2026_res": clean(row.get("permits_2026_res")),
            "permits_2026_nr": clean(row.get("permits_2026_nr")),
            "permits_2026_total": clean(row.get("permits_2026_total")),
            "permits_2026_source": clean(row.get("permits_2026_source")),
            "permit_allotment_2026_res": clean(row.get("permit_allotment_2026_res")),
            "permit_allotment_2026_nr": clean(row.get("permit_allotment_2026_nr")),
            "permit_allotment_2026_total": clean(row.get("permit_allotment_2026_total")),
            "permit_allotment_2026_source": clean(row.get("permit_allotment_2026_source")),
            "permit_allotment_2026_source_file": clean(row.get("permit_allotment_2026_source_file")),
            "permit_allotment_2026_status": clean(row.get("permit_allotment_2026_status")),
        }
        if shape_status == "LIVE_DWR_NO_QUOTA_PUBLISHED":
            # A blank/zero live DWR row means the Hunt Planner did not publish a
            # quota in this endpoint. Preserve reviewed database-entered values
            # such as conservation, expo, and other hard-copy sourced permits.
            status = "PRESERVED_DATABASE_VALUE_NO_LIVE_DWR_QUOTA"
            status_counts[status] += 1
            shape_counts[shape_status] += 1
            audit_rows.append(
                {
                    "snapshot_utc": timestamp,
                    "hunt_code": code,
                    "hunt_name": clean(row.get("hunt_name")),
                    "species": clean(row.get("species")),
                    "sex_type": clean(row.get("sex_type")),
                    "hunt_type": clean(row.get("hunt_type")),
                    "live_hunt_type": clean(live.get("hunt_type")),
                    "live_res": clean(live.get("live_res")),
                    "live_nr": clean(live.get("live_nr")),
                    "live_total": clean(live.get("live_total")),
                    "old_res": old_values["permits_2026_res"],
                    "old_nr": old_values["permits_2026_nr"],
                    "old_total": old_values["permits_2026_total"],
                    "new_res": old_values["permits_2026_res"],
                    "new_nr": old_values["permits_2026_nr"],
                    "new_total": old_values["permits_2026_total"],
                    "shape_status": shape_status,
                    "promotion_status": status,
                    "changed_fields": "",
                    "source_url": source_url,
                }
            )
            continue

        source_label = SOURCE_LABEL
        new_values = {
            "permits_2026_res": new_res,
            "permits_2026_nr": new_nr,
            "permits_2026_total": new_total,
            "permits_2026_source": source_label,
            "permit_allotment_2026_res": new_res,
            "permit_allotment_2026_nr": new_nr,
            "permit_allotment_2026_total": new_total,
            "permit_allotment_2026_source": source_label,
            "permit_allotment_2026_source_file": source_url,
            "permit_allotment_2026_status": shape_status,
        }
        diff_fields = [field for field, value in new_values.items() if old_values[field] != value]
        if diff_fields:
            changed_rows += 1
            changed_cells += len(diff_fields)
            for field, value in new_values.items():
                row[field] = value
            status = "UPDATED_FROM_LIVE_DWR"
        else:
            status = "UNCHANGED_ALREADY_MATCHED_LIVE_DWR"
        status_counts[status] += 1
        shape_counts[shape_status] += 1
        audit_rows.append(
            {
                "snapshot_utc": timestamp,
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "hunt_type": clean(row.get("hunt_type")),
                "live_hunt_type": clean(live.get("hunt_type")),
                "live_res": clean(live.get("live_res")),
                "live_nr": clean(live.get("live_nr")),
                "live_total": clean(live.get("live_total")),
                "old_res": old_values["permits_2026_res"],
                "old_nr": old_values["permits_2026_nr"],
                "old_total": old_values["permits_2026_total"],
                "new_res": new_res,
                "new_nr": new_nr,
                "new_total": new_total,
                "shape_status": shape_status,
                "promotion_status": status,
                "changed_fields": "|".join(diff_fields),
                "source_url": source_url,
            }
        )

    db_codes = {clean(row.get("hunt_code")).upper() for row in db_rows if row.get("hunt_code")}
    missing_database = sorted(set(live_by_code) - db_codes)

    write_csv(DATABASE, db_rows, db_fields)
    audit_fields = [
        "snapshot_utc",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "live_hunt_type",
        "live_res",
        "live_nr",
        "live_total",
        "old_res",
        "old_nr",
        "old_total",
        "new_res",
        "new_nr",
        "new_total",
        "shape_status",
        "promotion_status",
        "changed_fields",
        "source_url",
    ]
    write_csv(AUDIT_OUT, audit_rows, audit_fields)

    summary = {
        "artifact": "live_dwr_permit_numbers_promoted_to_DATABASE_2026",
        "snapshot_utc": timestamp,
        "source_snapshot": LIVE_SNAPSHOT.relative_to(ROOT).as_posix(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "live_row_count": len(live_rows),
        "excluded_archived_prior_year_codes": sorted(ARCHIVED_PRIOR_YEAR_HUNT_CODES),
        "promoted_row_count": len(audit_rows),
        "changed_rows": changed_rows,
        "changed_cells": changed_cells,
        "missing_database_count": len(missing_database),
        "missing_database_codes": missing_database,
        "promotion_status_counts": dict(sorted(status_counts.items())),
        "shape_status_counts": dict(sorted(shape_counts.items())),
        "guardrail": "CWMU live QUOTA_RES values were promoted as total-only permits_2026_total; resident/nonresident splits were not invented for total-only rows.",
        "outputs": {
            "audit_csv": AUDIT_OUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_OUT.relative_to(ROOT).as_posix(),
            "report_md": REPORT_OUT.relative_to(ROOT).as_posix(),
        },
    }
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Live DWR Permit Numbers Promoted To DATABASE 2026",
        "",
        f"- Snapshot UTC: `{timestamp}`",
        f"- Live rows: `{len(live_rows)}`",
        f"- Promoted rows: `{len(audit_rows)}`",
        f"- Changed rows: `{changed_rows}`",
        f"- Changed cells: `{changed_cells}`",
        f"- Missing DATABASE rows: `{len(missing_database)}`",
        "",
        "## Shape Counts",
        "",
    ]
    for status, count in summary["shape_status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not missing_database else 1


if __name__ == "__main__":
    raise SystemExit(main())
