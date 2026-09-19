#!/usr/bin/env python3
"""Validate the isolated split Research-contract candidate before browser QA."""

from __future__ import annotations

import argparse
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

CERTIFIED_DESIGNS = {
    "BONUS_LE_BIG_GAME",
    "BONUS_OIL_BIG_GAME",
    "BONUS_PLE_BIG_GAME",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
}
CERTIFIED_PROBABILITY_FIELDS = {
    "certified_p_draw",
    "certified_p_draw_mean",
    "certified_p_draw_pct",
}
FORBIDDEN_PUBLIC_FIELDS = {
    "p_draw", "p_draw_mean", "p_draw_pct", "p_draw_p10", "p_draw_p50", "p_draw_p90",
    "p_max_pool_mean", "p_max_pool_mean_pct", "p_max_pool_pct", "p_random_mean",
    "p_preference_draw", "p_bonus_pool", "p_random_pool", "p_bonus_pool_pct", "p_random_pool_pct",
    "p_prior_year_baseline", "p_quota_adjusted", "p_rollover_adjusted", "p_harvest_adjusted",
    "p_preference_mean", "p_sportsman_draw", "p_availability", "availability_pct",
    "youth_reserve_probability", "youth_rollover_main_draw_probability", "closure_risk",
    "sellout_risk", "sellout_or_closure_risk",
    "display_odds_pct", "display_odds_text", "display_2026_max_point_pool", "display_2026_random_draw",
    "odds_2026_projected", "max_pool_projection_2026", "random_draw_odds_2026",
    "random_draw_projection_2026", "preference_draw_odds_2026", "preference_projection_2026",
    "modeled_preference_probability", "draw_probability", "guaranteed_probability",
    "projected_guaranteed_probability_pct", "projected_random_probability_pct",
    "projected_total_probability_pct", "expected_cutoff_points", "p50", "guaranteed_at_2026", "guaranteed_line",
    "guaranteed_line_points", "guaranteed_marker",
    "projected_2026_max_cutoff_point",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return clean(value).upper()


def residency(value: object) -> str:
    raw = clean(value).lower().replace("-", "").replace(" ", "")
    return {"nonresident": "Nonresident", "nr": "Nonresident", "resident": "Resident", "res": "Resident", "r": "Resident"}.get(raw, "")


def point(value: object) -> str:
    try:
        parsed = float(clean(value))
    except ValueError:
        return clean(value)
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def pool(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")
    explicit_program_lanes = {
        "youth", "lifetime", "dedicated_hunter", "youth_dedicated_hunter",
        "youth_mature_bull", "youth_turkey",
    }
    return normalized if normalized in explicit_program_lanes else "standard"


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


def iter_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--prediction", type=Path, default=FROZEN)
    parser.add_argument("--certification-registry", type=Path, default=ROOT / "governance/prediction-family-certification.json")
    parser.add_argument(
        "--current-index",
        type=Path,
        default=ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json",
    )
    args = parser.parse_args()
    resolve = lambda path: path if path.is_absolute() else ROOT / path
    candidate = resolve(args.candidate)
    processed = candidate / "processed_data"
    frozen_path = resolve(args.prediction)
    current_index_path = resolve(args.current_index)
    registry_path = resolve(args.certification_registry)
    registry = read_json(registry_path)
    expected_certified_designs = set(registry.get("certified_designs", []))
    if not expected_certified_designs.issubset(CERTIFIED_DESIGNS):
        raise SystemExit("Registry includes designs outside the approved core scope.")

    audit_path = candidate / "candidate_build_audit.json"
    if not audit_path.exists():
        raise SystemExit("Candidate build audit is missing.")
    audit = read_json(audit_path)
    scope_audit_path = candidate / "candidate_index_scope_reconciliation.json"
    scope_audit = read_json(scope_audit_path) if scope_audit_path.exists() else None
    summary = read_json(processed / "hunt_research_2026_summary.json")
    ladder = read_json(processed / "hunt_research_2026_ladder.json")
    index = read_json(processed / "hunt_research_2026_split" / "hunt_research_2026.index.json")
    details = read_json(processed / "hunt_research_2026_split" / "hunt_research_2026.details.json")
    point_ladder, point_fields = read_csv(processed / "point_ladder_view.csv")
    public_predictions, public_prediction_fields = read_csv(processed / "ml_draw_predictions_v1.csv")
    public_predictive, public_predictive_fields = read_csv(processed / "draw_reality_engine_predictive_v2.csv")
    frozen, _ = read_csv(frozen_path)

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
    current_index = read_json(current_index_path)
    current_index_codes = {code(row.get("hunt_code")) for row in current_index}
    if index_codes != current_index_codes:
        failures.append("candidate index does not match the declared current hunt-code universe")
    detail_map = details.get("details_by_hunt_code", {}) if isinstance(details, dict) else {}
    summary_by_code: dict[str, int] = Counter(code(row.get("hunt_code")) for row in summary if code(row.get("hunt_code")))
    missing_index = set(summary_by_code) - index_codes
    missing_details = set(summary_by_code) - set(detail_map)
    declared_summary_only = int(audit.get("overlay", {}).get("summary_only_historical_reference_codes", -1))
    summary_only_scope_reconciled = len(missing_index) == declared_summary_only
    if missing_index and not scope_audit and not summary_only_scope_reconciled:
        failures.append(f"candidate index is missing {len(missing_index)} summary hunt codes")
    if missing_details:
        failures.append(f"candidate detail bundle is missing {len(missing_details)} summary hunt codes")
    wrong_detail_counts = [hunt for hunt, count in summary_by_code.items() if int(detail_map.get(hunt, {}).get("research_summary_row_count", -1)) != count]
    if wrong_detail_counts:
        failures.append(f"candidate detail bundle has {len(wrong_detail_counts)} incorrect summary-row counts")
    split_root = processed / "hunt_research_2026_split"
    missing_direct_details: list[str] = []
    mismatched_direct_details: list[str] = []
    for row in index:
        hunt_code = code(row.get("hunt_code"))
        detail_path = clean(row.get("detail_path"))
        direct_path = split_root / detail_path
        if not hunt_code or not detail_path or not direct_path.is_file():
            missing_direct_details.append(hunt_code or detail_path or "<blank>")
            continue
        if read_json(direct_path) != detail_map.get(hunt_code):
            mismatched_direct_details.append(hunt_code)
    if missing_direct_details:
        failures.append(f"candidate split index has {len(missing_direct_details)} missing direct detail files")
    if mismatched_direct_details:
        failures.append(f"candidate split index has {len(mismatched_direct_details)} direct detail files that differ from the validated bundle")

    json_documents = {"summary": summary, "ladder": ladder, "index": index, "details": details}
    forbidden_occurrences: Counter[str] = Counter()
    unauthorized_probability_rows = 0
    unauthorized_certified_design_rows = 0
    certified_designs_seen: set[str] = set()
    for document in json_documents.values():
        for row in iter_dicts(document):
            forbidden_occurrences.update(field for field in FORBIDDEN_PUBLIC_FIELDS if field in row)
            status = clean(row.get("prediction_certification_status"))
            design = clean(row.get("prediction_certification_design"))
            has_probability = any(clean(row.get(field)) for field in CERTIFIED_PROBABILITY_FIELDS)
            if status == "CERTIFIED":
                certified_designs_seen.add(design)
                if design not in CERTIFIED_DESIGNS:
                    unauthorized_certified_design_rows += 1
            elif has_probability:
                unauthorized_probability_rows += 1
    if forbidden_occurrences:
        failures.append(f"public JSON contains {sum(forbidden_occurrences.values())} forbidden raw-probability or guarantee field occurrences")
    if unauthorized_probability_rows:
        failures.append(f"public JSON contains {unauthorized_probability_rows} non-certified rows with certified probability")
    if unauthorized_certified_design_rows:
        failures.append(f"public JSON contains {unauthorized_certified_design_rows} certified rows outside the four-design allowlist")
    if certified_designs_seen != expected_certified_designs:
        failures.append(f"public JSON certified design set changed: {sorted(certified_designs_seen)}")

    point_forbidden_nonblank = sum(
        1
        for row in point_ladder
        for field in FORBIDDEN_PUBLIC_FIELDS
        if clean(row.get(field))
    )
    point_unauthorized_probability_rows = sum(
        1
        for row in point_ladder
        if clean(row.get("prediction_certification_status")) != "CERTIFIED"
        and any(clean(row.get(field)) for field in CERTIFIED_PROBABILITY_FIELDS)
    )
    if point_forbidden_nonblank:
        failures.append(f"candidate point ladder contains {point_forbidden_nonblank} nonblank forbidden future values")
    if point_unauthorized_probability_rows:
        failures.append(f"candidate point ladder contains {point_unauthorized_probability_rows} non-certified probability rows")

    forbidden_public_prediction_fields = sorted(
        (set(public_prediction_fields) | set(public_predictive_fields)) & FORBIDDEN_PUBLIC_FIELDS
    )
    public_prediction_keys = {key(row) for row in public_predictions}
    public_predictive_keys = {key(row) for row in public_predictive}
    public_prediction_leaks = sum(
        1
        for row in [*public_predictions, *public_predictive]
        if clean(row.get("prediction_certification_status")) != "CERTIFIED"
        and any(clean(row.get(field)) for field in CERTIFIED_PROBABILITY_FIELDS)
    )
    if forbidden_public_prediction_fields:
        failures.append(f"public prediction CSVs retain forbidden fields: {forbidden_public_prediction_fields}")
    if len(public_predictions) != len(frozen) or len(public_predictive) != len(frozen):
        failures.append("public prediction CSV row counts do not match the frozen materialization")
    if public_prediction_keys != frozen_keys or public_predictive_keys != frozen_keys:
        failures.append("public prediction CSV identities do not match the frozen materialization")
    if public_prediction_leaks:
        failures.append(f"public prediction CSVs contain {public_prediction_leaks} non-certified probability rows")

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
        "summary_only_reference_scope_reconciled": summary_only_scope_reconciled,
        "detail_hunt_codes": len(detail_map),
        "direct_detail_files_validated": len(index) - len(missing_direct_details),
        "missing_direct_detail_files": len(missing_direct_details),
        "mismatched_direct_detail_files": len(mismatched_direct_details),
        "frozen_prediction_rows": len(frozen),
        "frozen_prediction_keys_missing_from_ladder": len(missing_frozen),
        "frozen_prediction_keys_missing_from_point_ladder": len(missing_point),
        "publication_gate": {
            "registry_path": str(registry_path),
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "expected_certified_designs": sorted(expected_certified_designs),
            "certified_designs_seen": sorted(certified_designs_seen),
            "forbidden_json_field_occurrences": dict(sorted(forbidden_occurrences.items())),
            "unauthorized_certified_design_rows": unauthorized_certified_design_rows,
            "unauthorized_probability_rows": unauthorized_probability_rows,
            "point_ladder_nonblank_forbidden_future_values": point_forbidden_nonblank,
            "point_ladder_unauthorized_probability_rows": point_unauthorized_probability_rows,
            "public_prediction_forbidden_fields": forbidden_public_prediction_fields,
            "public_prediction_noncertified_probability_rows": public_prediction_leaks,
            "public_prediction_row_count": len(public_predictions),
            "public_predictive_row_count": len(public_predictive),
        },
        "runtime_field_trace": {
            "fields_referenced": sorted(runtime_fields),
            "fields_missing_from_candidate_schema": missing_runtime_fields,
            "note": "Missing fields are optional fallbacks in the UI unless the browser flow demonstrates otherwise; browser QA is still required.",
        },
        "failures": failures,
    }
    output = candidate / "candidate_contract_validation.json"
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
