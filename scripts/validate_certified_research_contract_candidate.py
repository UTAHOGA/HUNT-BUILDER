#!/usr/bin/env python3
"""Validate the isolated split Research-contract candidate before browser QA."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate" / "research_split_contract_candidate_2026-08-27"
PROCESSED = CANDIDATE / "processed_data"
FROZEN = ROOT / "processed_data" / "draw_reality_engine_predictive_v2.csv"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return clean(value).upper()


def residency(value: object) -> str:
    return "Nonresident" if clean(value).lower() in {"nonresident", "non-resident", "nr"} else "Resident"


def point(value: object) -> str:
    try:
        parsed = float(clean(value))
    except ValueError:
        return clean(value)
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def pool(value: object) -> str:
    return clean(value).lower() or "standard"


def key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (code(row.get("hunt_code")), residency(row.get("residency")), point(row.get("points")), pool(row.get("draw_pool")))


def group(row: dict[str, object]) -> tuple[str, str, str]:
    return key(row)[:2] + (pool(row.get("draw_pool")),)


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def js_row_fields(source: str) -> set[str]:
    fields = set(re.findall(r"\brow\?\.([A-Za-z_][A-Za-z0-9_]*)", source))
    fields.update(re.findall(r"\brow\.([A-Za-z_][A-Za-z0-9_]*)", source))
    for match in re.finditer(r"firstAvailable\(row,\s*\[(.*?)\]\)", source, flags=re.DOTALL):
        fields.update(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", match.group(1)))
    return fields


def main() -> int:
    audit_path = CANDIDATE / "candidate_build_audit.json"
    if not audit_path.exists():
        raise SystemExit("Candidate build audit is missing.")
    audit = read_json(audit_path)
    scope_audit_path = CANDIDATE / "candidate_index_scope_reconciliation.json"
    scope_audit = read_json(scope_audit_path) if scope_audit_path.exists() else None
    summary = read_json(PROCESSED / "hunt_research_2026_summary.json")
    ladder = read_json(PROCESSED / "hunt_research_2026_ladder.json")
    index = read_json(PROCESSED / "hunt_research_2026_split" / "hunt_research_2026.index.json")
    details = read_json(PROCESSED / "hunt_research_2026_split" / "hunt_research_2026.details.json")
    point_ladder, point_fields = read_csv(PROCESSED / "point_ladder_view.csv")
    frozen, _ = read_csv(FROZEN)

    failures: list[str] = []
    for label, record in audit["outputs"].items():
        actual = digest(ROOT / record["path"])
        expected = scope_audit["reconciled_index_sha256"] if label == "index" and scope_audit else record["sha256"]
        if actual != expected:
            failures.append(f"{label} hash does not match candidate audit")

    summary_groups = [group(row) for row in summary]
    if len(summary_groups) != len(set(summary_groups)):
        failures.append("summary contains duplicate hunt/residency/pool groups")
    ladder_keys = [key(row) for row in ladder]
    ladder_key_set = set(ladder_keys)
    frozen_keys = {key(row) for row in frozen}
    missing_frozen = frozen_keys - ladder_key_set
    if missing_frozen:
        failures.append(f"candidate ladder is missing {len(missing_frozen)} frozen prediction keys")
    point_keys = {key(row) for row in point_ladder}
    missing_point = frozen_keys - point_keys
    if missing_point:
        failures.append(f"candidate point ladder is missing {len(missing_point)} frozen prediction keys")

    index_codes = {code(row.get("hunt_code")) for row in index}
    current_index = read_json(ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json")
    current_index_codes = {code(row.get("hunt_code")) for row in current_index}
    if index_codes != current_index_codes:
        failures.append("candidate index does not match the declared current hunt-code universe")
    detail_map = details.get("details_by_hunt_code", {}) if isinstance(details, dict) else {}
    summary_by_code: dict[str, int] = Counter(code(row.get("hunt_code")) for row in summary if code(row.get("hunt_code")))
    missing_index = set(summary_by_code) - index_codes
    missing_details = set(summary_by_code) - set(detail_map)
    if missing_index and not scope_audit:
        failures.append(f"candidate index is missing {len(missing_index)} summary hunt codes")
    if missing_details:
        failures.append(f"candidate detail bundle is missing {len(missing_details)} summary hunt codes")
    wrong_detail_counts = [hunt for hunt, count in summary_by_code.items() if int(detail_map.get(hunt, {}).get("research_summary_row_count", -1)) != count]
    if wrong_detail_counts:
        failures.append(f"candidate detail bundle has {len(wrong_detail_counts)} incorrect summary-row counts")

    identity_fields = {"hunt_code", "residency", "points", "draw_pool"}
    if not identity_fields.issubset(set(point_fields)):
        failures.append("candidate point ladder lacks a required identity field")
    runtime_fields = js_row_fields((ROOT / "hunt-research.js").read_text(encoding="utf-8"))
    runtime_schema = set().union(*(set(row) for row in summary[:100]), *(set(row) for row in ladder[:100]))
    missing_runtime_fields = sorted(field for field in runtime_fields if field not in runtime_schema)

    result = {
        "status": "PASS" if not failures else "FAIL",
        "summary_rows": len(summary),
        "ladder_rows": len(ladder),
        "point_ladder_rows": len(point_ladder),
        "index_hunt_codes": len(index_codes),
        "declared_current_index_hunt_codes": len(current_index_codes),
        "summary_only_reference_hunt_codes": len(missing_index),
        "detail_hunt_codes": len(detail_map),
        "frozen_prediction_rows": len(frozen),
        "frozen_prediction_keys_missing_from_ladder": len(missing_frozen),
        "frozen_prediction_keys_missing_from_point_ladder": len(missing_point),
        "runtime_field_trace": {
            "fields_referenced": sorted(runtime_fields),
            "fields_missing_from_candidate_schema": missing_runtime_fields,
            "note": "Missing fields are optional fallbacks in the UI unless the browser flow demonstrates otherwise; browser QA is still required.",
        },
        "failures": failures,
    }
    output = CANDIDATE / "candidate_contract_validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"CERTIFIED_RESEARCH_CONTRACT_VALIDATION={result['status']}")
    print(f"SUMMARY_ROWS={len(summary)} LADDER_ROWS={len(ladder)} POINT_LADDER_ROWS={len(point_ladder)}")
    print(f"FROZEN_KEYS_MISSING_LADDER={len(missing_frozen)} FROZEN_KEYS_MISSING_POINT_LADDER={len(missing_point)}")
    print(f"RUNTIME_OPTIONAL_FIELD_GAPS={len(missing_runtime_fields)}")
    if failures:
        for failure in failures:
            print(f"FAILURE={failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
