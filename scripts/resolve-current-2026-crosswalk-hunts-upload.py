#!/usr/bin/env python3
"""Apply the uploaded HUNTS current-to-historical crosswalk to the 2026 unresolved bucket."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNRESOLVED_INPUT = (
    ROOT / "processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_crosswalk_review_rule.csv"
)
CROSSWALK_PATH = Path(
    "C:/Users/tyler/Desktop/GitHub/HUNTS/pages-dist/processed_data/current_to_historical_hunt_code_crosswalk_2026.csv"
)
RESOLVED_OUTPUT = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/resolved_crosswalk_hunts_upload_matches.csv"
REMAINING_OUTPUT = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_crosswalk_hunts_upload_rule.csv"
SUMMARY_OUTPUT = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/current_2026_permit_crosswalk_hunts_upload_resolution_summary.json"

RESOLVABLE_STATUSES = {
    "PROMOTED_EXACT_HISTORY": "RESOLVED_BY_EXACT_CODE_HISTORY_FROM_UPLOADED_CROSSWALK",
    "PROMOTED_PARALLEL_PUBLIC_UNIT_REFERENCE": "RESOLVED_BY_PARALLEL_PUBLIC_REFERENCE_FROM_UPLOADED_CROSSWALK",
    "REVIEWED_CURRENT_REFERENCE": "RESOLVED_BY_REVIEWED_CURRENT_REFERENCE_FROM_UPLOADED_CROSSWALK",
    "REVIEWED_CURRENT_REFERENCE_ONLY": "RESOLVED_BY_REVIEWED_CURRENT_REFERENCE_FROM_UPLOADED_CROSSWALK",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _pick_source_total(row: dict[str, str], key: str, fallback_keys: list[str]) -> str:
    if row.get(key):
        return row[key]
    for fallback in fallback_keys:
        if row.get(fallback):
            return row[fallback]
    return ""


def _resolved_row(row: dict[str, str], crosswalk: dict[str, str], status: str) -> dict[str, str]:
    out = dict(row)
    out["crosswalk_status"] = status
    out["uploaded_crosswalk_status"] = crosswalk.get("crosswalk_status", "")
    out["uploaded_historical_hunt_code"] = crosswalk.get("historical_hunt_code", "")
    out["uploaded_relationship_type"] = crosswalk.get("relationship_type", "")
    out["uploaded_recommended_model_behavior"] = crosswalk.get("recommended_model_behavior", "")
    out["crosswalk_source_file"] = "C:/Users/tyler/Desktop/GitHub/HUNTS/pages-dist/processed_data/current_to_historical_hunt_code_crosswalk_2026.csv"
    out["resolved_status"] = RESOLVABLE_STATUSES[status]
    out["resolved_matching_sources"] = "CURRENT_TO_HISTORICAL_CROSSWALK_FROM_HUNTS"
    out["resolved_matching_source_count"] = "1"
    out["resolved_res"] = _pick_source_total(row, "matching_res", ["recommended_res", "database_res_reference"])
    out["resolved_nr"] = _pick_source_total(row, "matching_nr", ["recommended_nr", "database_nr_reference"])
    out["resolved_total"] = _pick_source_total(row, "matching_total", ["recommended_total", "database_total_reference"])
    return out


def _remaining_row(row: dict[str, str], crosswalk: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    out["crosswalk_status"] = out.get("crosswalk_status", "")
    out["uploaded_crosswalk_status"] = crosswalk.get("crosswalk_status", "<none>")
    out["uploaded_historical_hunt_code"] = crosswalk.get("historical_hunt_code", "")
    out["uploaded_relationship_type"] = crosswalk.get("relationship_type", "")
    out["uploaded_recommended_model_behavior"] = crosswalk.get("recommended_model_behavior", "")
    out["crosswalk_source_file"] = "C:/Users/tyler/Desktop/GitHub/HUNTS/pages-dist/processed_data/current_to_historical_hunt_code_crosswalk_2026.csv"
    return out


def main() -> int:
    unresolved_rows = _read_csv(UNRESOLVED_INPUT)
    crosswalk_rows = _read_csv(CROSSWALK_PATH)
    lookup = {row.get("current_hunt_code", ""): row for row in crosswalk_rows if row.get("current_hunt_code")}

    resolved_rows: list[dict[str, str]] = []
    remaining_rows: list[dict[str, str]] = []

    for row in unresolved_rows:
        code = row.get("hunt_code", "")
        crosswalk = lookup.get(code, {})
        status = crosswalk.get("crosswalk_status", "")
        if status in RESOLVABLE_STATUSES:
            resolved_rows.append(_resolved_row(row, crosswalk, status))
        else:
            remaining_rows.append(_remaining_row(row, crosswalk))

    # Add compatibility fields if any resolved rows are present.
    base_fields = list(unresolved_rows[0].keys())
    additional_fields = [
        "uploaded_crosswalk_status",
        "uploaded_historical_hunt_code",
        "uploaded_relationship_type",
        "uploaded_recommended_model_behavior",
        "crosswalk_source_file",
        "resolved_status",
        "resolved_matching_sources",
        "resolved_matching_source_count",
        "resolved_res",
        "resolved_nr",
        "resolved_total",
    ]
    if resolved_rows:
        resolved_fields = list(dict.fromkeys(list(resolved_rows[0].keys()) + additional_fields))
    else:
        resolved_fields = list(dict.fromkeys(base_fields + additional_fields))

    remaining_fields = list(remaining_rows[0].keys()) if remaining_rows else list(unresolved_rows[0].keys()) + [
        "uploaded_crosswalk_status",
        "uploaded_historical_hunt_code",
        "uploaded_relationship_type",
        "uploaded_recommended_model_behavior",
        "crosswalk_source_file",
    ]
    remaining_fields = list(dict.fromkeys(remaining_fields))

    if len(resolved_rows) + len(remaining_rows) != len(unresolved_rows):
        raise RuntimeError(
            "Resolved and remaining row counts do not match input row count for uploaded-crosswalk pass"
        )

    _write_csv(RESOLVED_OUTPUT, resolved_rows, resolved_fields)
    _write_csv(REMAINING_OUTPUT, remaining_rows, remaining_fields)

    unresolved_status_counts = Counter(r.get("crosswalk_status", "") for r in unresolved_rows)
    uploaded_status_counts = Counter(
        (lookup.get(r.get("hunt_code", ""), {}).get("crosswalk_status", "<none>") for r in unresolved_rows)
    )
    unresolved_split = Counter(r.get("split_bucket", "unassigned") for r in remaining_rows)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_csv": str(UNRESOLVED_INPUT),
        "crosswalk_csv": str(CROSSWALK_PATH),
        "row_counts": {
            "input_rows": len(unresolved_rows),
            "resolved_rows": len(resolved_rows),
            "remaining_rows": len(remaining_rows),
        },
        "input_split_bucket_counts": dict(Counter(r.get("split_bucket", "unassigned") for r in unresolved_rows)),
        "input_crosswalk_status_counts": dict(unresolved_status_counts),
        "uploaded_crosswalk_status_counts": dict(uploaded_status_counts),
        "remaining_split_bucket_counts": dict(unresolved_split),
        "notes": [
            "No source permit values were modified.",
            "This pass uses the uploaded HUNTS crosswalk source only for deterministic resolution and audit tagging.",
        ],
        "outputs": {
            "resolved_csv": str(RESOLVED_OUTPUT.relative_to(ROOT).as_posix()),
            "remaining_csv": str(REMAINING_OUTPUT.relative_to(ROOT).as_posix()),
            "summary_json": str(SUMMARY_OUTPUT.relative_to(ROOT).as_posix()),
        },
    }
    SUMMARY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
