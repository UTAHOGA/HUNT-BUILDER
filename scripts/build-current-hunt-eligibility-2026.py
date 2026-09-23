"""Project retained current-identity evidence into a website selection filter.

Never deletes catalog/history rows or treats current eligibility as certification.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "database": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    "planner": "processed_data/dwr_huntplanner_hanumber_2026.csv",
    "baseline": "processed_data/audits/database_2026_universe_count_and_delete_review.csv",
    "feeder": "processed_data/audits/database_current_identity_quota_2026_feeder_audit.csv",
}
OUTPUT = ROOT / "data/hunt-eligibility-2026.json"


def classify(row, planner, baseline, feeder):
    lifecycle = " ".join(str(row.get(key, "")) for key in (
        "permit_allotment_2026_status", "hunt_class"
    )).upper()
    retired = bool(re.search(r"HISTORICAL|RETIRED|DISCONTINUED|NOT_ACTIVE|NONCURRENT", lifecycle))
    current = planner.get("fetch_status") == "OK" and planner.get("hunt_year") == "2026"
    if retired:
        return "EVIDENCE_CONFLICT_REVIEW" if current else "HISTORICAL_REFERENCE"
    if feeder.get("quota_status", "").startswith("NONCURRENT"):
        return "NONCURRENT_REFERENCE"
    if current:
        return "CURRENT_PLANNER"
    if baseline.get("universe_status") == "ACTIVE_RECONCILIATION_ROW":
        return "RETAINED_ACTIVE_2026"
    return "REFERENCE_UNVERIFIED"


def build():
    inputs, tables = {}, {}
    for name, relative in INPUTS.items():
        path = ROOT / relative
        content = path.read_bytes()
        inputs[name] = {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        codes = [row["hunt_code"] for row in rows]
        if len(set(codes)) != len(codes) or not all(codes):
            raise ValueError(f"Ambiguous input identity: {name}")
        tables[name] = dict(zip(codes, rows))
    records = {}
    for code, row in sorted(tables["database"].items()):
        planner = tables["planner"].get(code, {})
        baseline = tables["baseline"].get(code, {})
        feeder = tables["feeder"].get(code, {})
        if not feeder or feeder.get("unresolved_current_delta") != "NO":
            raise ValueError(f"Missing or unresolved feeder evidence: {code}")
        status = classify(row, planner, baseline, feeder)
        records[code] = {
            "status": status,
            "current_selectable": status in {"CURRENT_PLANNER", "RETAINED_ACTIVE_2026"},
            "planner_year": planner.get("hunt_year", ""),
            "planner_source": planner.get("source_url", ""),
            "planner_retrieved_at": planner.get("source_retrieved_at", ""),
            "catalog_lifecycle": row.get("permit_allotment_2026_status", ""),
            "baseline_status": baseline.get("universe_status", ""),
            "successor_hunt_code": baseline.get("successor_hunt_code", ""),
        }
    current = [code for code, row in records.items() if row["current_selectable"]]
    archive = [code for code, row in records.items() if not row["current_selectable"]]
    return {
        "schema": "hunt-eligibility.v1", "year": 2026,
        "scope": "Retained official current identity and reviewed baseline; not a fresh DWR census or prediction certification",
        "inputs": inputs, "status_counts": dict(sorted(Counter(row["status"] for row in records.values()).items())),
        "current_codes": current, "historical_reference_codes": archive,
        "planner_current_codes_absent_from_catalog": sorted(
            code for code, row in tables["planner"].items()
            if row.get("hunt_year") == "2026" and row.get("fetch_status") == "OK"
            and code not in records
        ),
        "records": records,
    }


if __name__ == "__main__":
    result = build()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"current": len(result["current_codes"]), "historical_reference": len(result["historical_reference_codes"]), "statuses": result["status_counts"], "planner_codes_absent_from_catalog": result["planner_current_codes_absent_from_catalog"]}, indent=2))
