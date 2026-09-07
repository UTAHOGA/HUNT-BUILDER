from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import build_identity_index, resolve_identity_match

DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
HUNT_MASTER = ROOT / "processed_data" / "hunt_master_enriched.csv"
REFERENCE = ROOT / "processed_data" / "hunt_unit_reference_linked.csv"
HARVEST_FEATURES = ROOT / "processed_data" / "harvest_quality_features_all_years_by_hunt_code.csv"

SUMMARY = ROOT / "data_truth" / "comparison_outputs" / "validation" / "hunt_research_reference_linked_2026_summary.json"
REPORT = ROOT / "processed_data" / "hunt_research_reference_linked_2026.md"

RETIRED_CODES = {
    "EA1007",
    "EA1053",
    "EA1287",
    "EA1288",
    "EA1289",
    "EA1290",
    "EA1291",
    "EA1292",
    "EA1293",
    "EA1294",
    "EA1295",
    "EA1296",
    "EA1297",
    "EA1298",
    "EA1299",
    "EA1300",
    "PD1039",
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def code(row: dict[str, str]) -> str:
    return (row.get("hunt_code") or "").strip().upper()


def clean_residency(value: str) -> str:
    return "Nonresident" if str(value or "").strip().lower() == "nonresident" else "Resident"


def is_invalid_current_code(hunt_code: str) -> bool:
    return hunt_code in RETIRED_CODES or (hunt_code.startswith("CG") and hunt_code != "CG9999")


def first_value(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return ""


def build_harvest_by_code(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    return build_identity_index(
        row for row in rows if str(row.get("model_target_year", "")).strip() == "2026"
    )


def backfill_reference_row(master_row: dict[str, str], columns: list[str], harvest_row: dict[str, str] | None) -> dict[str, str]:
    row = {column: "" for column in columns}
    for column in columns:
        if column in master_row:
            row[column] = master_row.get(column, "")

    row["residency"] = clean_residency(master_row.get("residency", ""))
    row["coverage_status"] = row.get("coverage_status") or "BACKFILLED_FROM_HUNT_MASTER"
    row["coverage_reason"] = row.get("coverage_reason") or "Missing current reference row rebuilt from hunt_master_enriched.csv."
    row["truth_source_status"] = row.get("truth_source_status") or "BACKFILLED_CURRENT_REFERENCE"
    row["reason_codes"] = row.get("reason_codes") or "REFERENCE_BACKFILL_2026"

    if harvest_row:
        row["harvest_hunters_2025"] = first_value(harvest_row, ["hunters_afield", "permits"])
        row["harvest_2025"] = first_value(harvest_row, ["harvest_total"])
        row["harvest_success_percent_2025"] = first_value(harvest_row, ["percent_success"])
        row["harvest_average_days_2025"] = first_value(harvest_row, ["average_days"])
        row["harvest_satisfaction_2025"] = first_value(harvest_row, ["hunter_satisfaction"])
    else:
        row["harvest_hunters_2025"] = first_value(master_row, ["success_hunters"])
        row["harvest_2025"] = first_value(master_row, ["success_harvest"])
        row["harvest_success_percent_2025"] = first_value(master_row, ["success_percent"])

    return row


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    database_rows, _ = read_csv(DATABASE)
    master_rows, _ = read_csv(HUNT_MASTER)
    reference_rows, reference_columns = read_csv(REFERENCE)
    harvest_rows, _ = read_csv(HARVEST_FEATURES)

    database_codes = {code(row) for row in database_rows if code(row)}
    harvest_by_code = build_harvest_by_code(harvest_rows)

    cleaned_reference = [row for row in reference_rows if code(row) in database_codes and not is_invalid_current_code(code(row))]
    cleaned_keys = {(code(row), clean_residency(row.get("residency", "")), str(row.get("draw_pool", "") or "standard").strip().lower() or "standard") for row in cleaned_reference}
    cleaned_codes = {key[0] for key in cleaned_keys}
    missing_codes = sorted(database_codes - cleaned_codes)

    master_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in master_rows:
        hunt_code = code(row)
        if hunt_code in missing_codes:
            master_by_code[hunt_code].append(row)

    backfilled_rows: list[dict[str, str]] = []
    for hunt_code in missing_codes:
        seen_keys: set[tuple[str, str, str]] = set()
        for master_row in master_by_code.get(hunt_code, []):
            key = (
                hunt_code,
                clean_residency(master_row.get("residency", "")),
                str(master_row.get("draw_pool", "") or "standard").strip().lower() or "standard",
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolution = resolve_identity_match(master_row, harvest_by_code.get(hunt_code, []))
            backfilled_rows.append(
                backfill_reference_row(
                    master_row,
                    reference_columns,
                    dict(resolution.row) if resolution.row is not None else None,
                )
            )

    output_rows = cleaned_reference + backfilled_rows
    output_rows.sort(key=lambda row: (code(row), clean_residency(row.get("residency", "")), str(row.get("draw_pool", "") or "")))
    write_csv(REFERENCE, output_rows, reference_columns)

    output_codes = {code(row) for row in output_rows if code(row)}
    harvest_populated_codes = {
        code(row)
        for row in output_rows
        if any(str(row.get(field, "")).strip() for field in [
            "harvest_hunters_2025",
            "harvest_2025",
            "harvest_success_percent_2025",
            "harvest_average_days_2025",
            "harvest_satisfaction_2025",
        ])
    }
    blockers = []
    if output_codes != database_codes:
        blockers.append("hunt_unit_reference_linked.csv code universe does not match DATABASE.csv")
    if any(is_invalid_current_code(hunt_code) for hunt_code in output_codes):
        blockers.append("hunt_unit_reference_linked.csv still contains retired or non-current cougar codes")

    summary = {
        "artifact": "hunt_research_reference_linked_2026",
        "timestamp_utc": timestamp,
        "database_unique_hunt_code_count": len(database_codes),
        "reference_row_count_before": len(reference_rows),
        "reference_unique_hunt_code_count_before": len({code(row) for row in reference_rows if code(row)}),
        "reference_row_count_after": len(output_rows),
        "reference_unique_hunt_code_count_after": len(output_codes),
        "removed_invalid_or_non_current_row_count": len(reference_rows) - len(cleaned_reference),
        "backfilled_row_count": len(backfilled_rows),
        "backfilled_unique_hunt_code_count": len({code(row) for row in backfilled_rows if code(row)}),
        "harvest_populated_unique_hunt_code_count": len(harvest_populated_codes),
        "harvest_model_2026_unique_hunt_code_count": len(set(harvest_by_code) & database_codes),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "guardrail": "Backfill uses current hunt_master_enriched rows and 2025-for-2026 harvest feature rows only; it does not change DATABASE.csv.",
    }

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    REPORT.write_text(
        "\n".join([
            "# Hunt Research Reference Linked 2026",
            "",
            f"- Timestamp UTC: `{timestamp}`",
            f"- DATABASE current hunt codes: `{len(database_codes)}`",
            f"- Reference unique codes before: `{summary['reference_unique_hunt_code_count_before']}`",
            f"- Reference unique codes after: `{summary['reference_unique_hunt_code_count_after']}`",
            f"- Backfilled rows: `{len(backfilled_rows)}`",
            f"- Harvest-populated current hunt codes: `{len(harvest_populated_codes)}`",
            f"- Blockers: `{len(blockers)}`",
        ]) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
