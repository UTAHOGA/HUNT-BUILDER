#!/usr/bin/env python3
"""Overlay verified harvest, management, and quality display fields.

The live contract is the base so this release cannot accidentally promote local
prediction, permit, quota, or hunt-universe changes. Matching uses hunt code plus
compatible hunt name and species for harvest rows, and hunt code plus compatible
species for the already-crosswalked official age database. boundary_id is never
used as a source-row identity key.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import hunt_name_compatible, normalize_code, species_family


LIVE_URL = "https://json.uoga.workers.dev/processed_data/public_contracts/hunt_application_outlook.json"
HARVEST_PATH = ROOT / "data_model" / "harvest_quality" / "harvest_quality_features_all_years_by_hunt_code.csv"
AGE_PATH = ROOT / "data_model" / "harvest_quality" / "harvest_average_age_global_merge_database.csv"
MANAGEMENT_PATH = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
PROFILE_PATH = ROOT / "data_model" / "harvest_quality" / "hunt_quality_profile_by_hunt_code_2026.csv"
OUTPUT_PATH = ROOT / "processed_data" / "public_contracts" / "hunt_application_outlook.json"
AUDIT_DIR = ROOT / "processed_data" / "audits" / "management_quality_release_20260906"

HARVEST_DISPLAY_FIELDS = {
    "harvest_success_pct",
    "average_days_hunted",
    "hunter_satisfaction",
    "harvest_total",
    "hunters_afield",
    "harvest_reported_year",
    "harvest_source_file",
    "harvest_source_page",
    "harvest_success_reported_year",
    "harvest_success_source_file",
    "harvest_success_source_page",
    "average_days_hunted_reported_year",
    "average_days_hunted_source_file",
    "average_days_hunted_source_page",
    "hunter_satisfaction_reported_year",
    "hunter_satisfaction_source_file",
    "hunter_satisfaction_source_page",
    "harvest_total_reported_year",
    "harvest_total_source_file",
    "harvest_total_source_page",
    "hunters_afield_reported_year",
    "hunters_afield_source_file",
    "hunters_afield_source_page",
    "average_harvest_age",
    "average_harvest_age_reported_year",
    "average_harvest_age_3yr_reported",
    "average_harvest_age_3yr_reported_year",
    "age_source_file",
    "age_source_page",
    "age_source_table_title",
    "average_harvest_age_3yr_source_file",
    "average_harvest_age_3yr_source_page",
    "average_harvest_age_3yr_source_table_title",
    "age_crosswalk_confidence",
    "age_mapping_status",
}

MANAGEMENT_DISPLAY_FIELDS = {
    "management_objective_type",
    "management_objective_range",
    "management_objective_target",
    "management_objective_status",
    "management_direction",
    "management_objective_note",
    "management_current_value",
    "management_objective_delta_from_range",
    "management_objective_unit",
    "management_measure_scope",
    "management_measure_applicability",
    "management_unit_name",
    "management_unit_key",
    "management_evidence_status",
    "management_conflict_fields",
    "management_source_url",
    "management_source_retrieved_at",
    "management_source_locator",
    "management_plan_reference_url",
    "management_plan_reference_scope",
    "management_plan_reference_match_status",
    "management_plan_source_page",
    "current_age_3yr_average",
    "population_objective",
    "current_population_estimate",
    "bucks_per_100_does_objective",
    "current_bucks_per_100_does_3yr_average",
}

PROFILE_DISPLAY_FIELDS = {
    "hunt_quality_profile_version",
    "hunt_unit_quality_score",
    "hunt_unit_quality_label",
    "hunt_unit_quality_confidence",
    "hunt_unit_quality_score_status",
    "hunt_unit_quality_reason_codes",
    "hunt_unit_quality_comparison_scope",
    "hunt_quality_biological_component",
    "hunt_quality_success_3yr_component",
    "hunt_quality_satisfaction_3yr_component",
    "hunt_quality_effort_3yr_component",
    "harvest_success_3yr_avg",
    "hunter_satisfaction_3yr_avg",
    "hunter_effort_days_3yr_avg",
    "harvest_3yr_avg",
    "hunters_afield_3yr_avg",
    "hunt_quality_harvest_source_years",
    "hunt_quality_harvest_match_method",
    "hunt_quality_harvest_data_grade",
    "hunt_quality_disclaimer",
}

DISPLAY_FIELDS = HARVEST_DISPLAY_FIELDS | MANAGEMENT_DISPLAY_FIELDS | PROFILE_DISPLAY_FIELDS


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_live(url: str) -> list[dict[str, object]]:
    request = urllib.request.Request(
        f"{url}?v=management-quality-release-20260906-v1",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed official runtime endpoint
        payload = json.load(response)
    if not isinstance(payload, list):
        raise RuntimeError("Live public outlook contract is not a JSON row array.")
    return payload


def nonblank(value: object) -> bool:
    return bool(str(value or "").strip())


def year(row: dict[str, object]) -> int:
    try:
        return int(float(str(row.get("reported_hunt_year") or 0)))
    except ValueError:
        return 0


def compatible_harvest(source: dict[str, object], target: dict[str, object]) -> bool:
    if normalize_code(source.get("hunt_code")) != normalize_code(target.get("hunt_code")):
        return False
    if species_family(source.get("species")) != species_family(target.get("species")):
        return False
    return hunt_name_compatible(
        source.get("hunt_name") or source.get("unit_name"),
        target.get("hunt_name") or target.get("unit_name"),
    )


def latest_with_value(rows: list[dict[str, str]], field: str) -> dict[str, str] | None:
    candidates = [row for row in rows if nonblank(row.get(field))]
    return max(candidates, key=year) if candidates else None


def protected_projection(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{key: value for key, value in row.items() if key not in DISPLAY_FIELDS} for row in rows]


def digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compatible_exact(source: dict[str, object], target: dict[str, object]) -> bool:
    if normalize_code(source.get("hunt_code")) != normalize_code(target.get("hunt_code")):
        return False
    if species_family(source.get("species")) != species_family(target.get("species")):
        return False
    return hunt_name_compatible(source.get("hunt_name"), target.get("hunt_name"))


def read_management() -> list[dict[str, object]]:
    payload = json.loads(MANAGEMENT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Management context must be a JSON row array.")
    return payload


def build(base_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    harvest_rows = read_csv(HARVEST_PATH)
    age_rows = read_csv(AGE_PATH)
    management_rows = read_management()
    profile_rows = read_csv(PROFILE_PATH)
    harvest_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    age_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in harvest_rows:
        harvest_by_code[normalize_code(row.get("hunt_code"))].append(row)
    for row in age_rows:
        age_by_code[normalize_code(row.get("hunt_code"))].append(row)
    management_by_code = {normalize_code(row.get("hunt_code")): row for row in management_rows}
    profile_by_code = {normalize_code(row.get("hunt_code")): row for row in profile_rows}

    before_protected = protected_projection(base_rows)
    output: list[dict[str, object]] = []
    updated_fields: Counter[str] = Counter()
    unmatched_harvest_codes: set[str] = set()
    unmatched_age_codes: set[str] = set()

    for base in base_rows:
        row = dict(base)
        code = normalize_code(row.get("hunt_code"))
        compatible = [candidate for candidate in harvest_by_code.get(code, []) if compatible_harvest(candidate, row)]
        if not compatible:
            unmatched_harvest_codes.add(code)
        harvest_field_map = {
            "percent_success": ("harvest_success_pct", "harvest_success"),
            "average_days": ("average_days_hunted", "average_days_hunted"),
            "hunter_satisfaction": ("hunter_satisfaction", "hunter_satisfaction"),
            "harvest_total": ("harvest_total", "harvest_total"),
            "hunters_afield": ("hunters_afield", "hunters_afield"),
        }
        populated_harvest_sources: list[dict[str, str]] = []
        for source_field, (target_field, lineage_prefix) in harvest_field_map.items():
            source = latest_with_value(compatible, source_field)
            if source is None:
                row[target_field] = ""
                row[f"{lineage_prefix}_reported_year"] = ""
                row[f"{lineage_prefix}_source_file"] = ""
                row[f"{lineage_prefix}_source_page"] = ""
                continue
            value = source.get(source_field, "")
            if row.get(target_field) != value:
                updated_fields[target_field] += 1
            row[target_field] = value
            row[f"{lineage_prefix}_reported_year"] = str(year(source))
            row[f"{lineage_prefix}_source_file"] = source.get("source_file", "")
            row[f"{lineage_prefix}_source_page"] = source.get("source_page", "") or "N/A - structured source row"
            populated_harvest_sources.append(source)
        if populated_harvest_sources:
            latest_harvest_source = max(populated_harvest_sources, key=year)
            row["harvest_reported_year"] = str(year(latest_harvest_source))
            row["harvest_source_file"] = latest_harvest_source.get("source_file", "")
            row["harvest_source_page"] = latest_harvest_source.get("source_page", "") or "N/A - structured source row"
        else:
            row["harvest_reported_year"] = ""
            row["harvest_source_file"] = ""
            row["harvest_source_page"] = ""

        compatible_age = [
            candidate
            for candidate in age_by_code.get(code, [])
            if species_family(candidate.get("species")) == species_family(row.get("species"))
        ]
        if not compatible_age:
            unmatched_age_codes.add(code)
        annual = latest_with_value(compatible_age, "average_harvest_age")
        annual_lineage_complete = annual is not None and all(
            nonblank(annual.get(field)) for field in ("age_source_file", "age_source_page")
        )
        if annual is not None and annual_lineage_complete:
            if row.get("average_harvest_age") != annual.get("average_harvest_age"):
                updated_fields["average_harvest_age"] += 1
            row["average_harvest_age"] = annual.get("average_harvest_age", "")
            row["average_harvest_age_reported_year"] = str(year(annual))
            row["age_source_file"] = annual.get("age_source_file", "")
            row["age_source_page"] = annual.get("age_source_page", "")
            row["age_source_table_title"] = annual.get("age_source_table_title", "")
            row["age_crosswalk_confidence"] = annual.get("crosswalk_confidence", "")
            row["age_mapping_status"] = annual.get("age_mapping_status", "")
        else:
            for field in (
                "average_harvest_age",
                "average_harvest_age_reported_year",
                "age_source_file",
                "age_source_page",
                "age_source_table_title",
                "age_crosswalk_confidence",
                "age_mapping_status",
            ):
                row[field] = ""

        reported_three_year = latest_with_value(compatible_age, "average_harvest_age_3yr")
        reported_lineage_complete = reported_three_year is not None and all(
            nonblank(reported_three_year.get(field)) for field in ("age_source_file", "age_source_page")
        )
        if reported_three_year is not None and reported_lineage_complete:
            value = reported_three_year.get("average_harvest_age_3yr", "")
            if row.get("average_harvest_age_3yr_reported") != value:
                updated_fields["average_harvest_age_3yr_reported"] += 1
            row["average_harvest_age_3yr_reported"] = value
            row["average_harvest_age_3yr_reported_year"] = str(year(reported_three_year))
            row["average_harvest_age_3yr_source_file"] = reported_three_year.get("age_source_file", "")
            row["average_harvest_age_3yr_source_page"] = reported_three_year.get("age_source_page", "")
            row["average_harvest_age_3yr_source_table_title"] = reported_three_year.get("age_source_table_title", "")
        else:
            for field in (
                "average_harvest_age_3yr_reported",
                "average_harvest_age_3yr_reported_year",
                "average_harvest_age_3yr_source_file",
                "average_harvest_age_3yr_source_page",
                "average_harvest_age_3yr_source_table_title",
            ):
                row[field] = ""

        management = management_by_code.get(code)
        if management is not None and compatible_exact(management, row):
            management_map = {
                "management_objective_type": "management_objective_type",
                "management_objective_target": "management_objective_target",
                "management_objective_status": "management_objective_status",
                "management_direction": "management_direction",
                "management_objective_note": "management_objective_note",
                "management_current_value": "management_current_value",
                "management_objective_delta_from_range": "management_objective_delta_from_range",
                "objective_unit": "management_objective_unit",
                "management_measure_scope": "management_measure_scope",
                "management_measure_applicability": "management_measure_applicability",
                "management_unit_name": "management_unit_name",
                "management_unit_key": "management_unit_key",
                "management_evidence_status": "management_evidence_status",
                "management_conflict_fields": "management_conflict_fields",
                "management_source_url": "management_source_url",
                "management_source_retrieved_at": "management_source_retrieved_at",
                "management_source_locator": "management_source_locator",
                "plan_reference_url": "management_plan_reference_url",
                "plan_reference_scope": "management_plan_reference_scope",
                "plan_reference_match_status": "management_plan_reference_match_status",
                "plan_source_page": "management_plan_source_page",
                "current_age_3yr_average": "current_age_3yr_average",
                "population_objective": "population_objective",
                "current_population_estimate": "current_population_estimate",
                "bucks_per_100_does_objective": "bucks_per_100_does_objective",
                "current_bucks_per_100_does_3yr_average": "current_bucks_per_100_does_3yr_average",
            }
            for source_field, target_field in management_map.items():
                value = management.get(source_field, "")
                if row.get(target_field) != value:
                    updated_fields[target_field] += 1
                row[target_field] = value
            target = str(management.get("management_objective_target") or "").strip()
            unit = str(management.get("objective_unit") or "").strip()
            row["management_objective_range"] = f"{target} {unit}".strip()
        else:
            for field in MANAGEMENT_DISPLAY_FIELDS:
                row[field] = ""

        profile = profile_by_code.get(code)
        if profile is not None and compatible_exact(profile, row):
            profile_map = {
                "profile_version": "hunt_quality_profile_version",
                "hunt_unit_quality_score": "hunt_unit_quality_score",
                "hunt_unit_quality_label": "hunt_unit_quality_label",
                "hunt_unit_quality_confidence": "hunt_unit_quality_confidence",
                "hunt_unit_quality_score_status": "hunt_unit_quality_score_status",
                "hunt_unit_quality_reason_codes": "hunt_unit_quality_reason_codes",
                "hunt_unit_quality_comparison_scope": "hunt_unit_quality_comparison_scope",
                "biological_quality_component": "hunt_quality_biological_component",
                "harvest_success_3yr_component": "hunt_quality_success_3yr_component",
                "hunter_satisfaction_3yr_component": "hunt_quality_satisfaction_3yr_component",
                "effort_efficiency_3yr_component": "hunt_quality_effort_3yr_component",
                "harvest_feature_source_years": "hunt_quality_harvest_source_years",
                "harvest_feature_match_method": "hunt_quality_harvest_match_method",
                "harvest_feature_data_quality_grade": "hunt_quality_harvest_data_grade",
                "profile_disclaimer": "hunt_quality_disclaimer",
            }
            for source_field, target_field in profile_map.items():
                row[target_field] = profile.get(source_field, "")
            exact_publishable_history = (
                profile.get("harvest_feature_match_method") == "EXACT_HUNT_CODE_HISTORY"
                and profile.get("harvest_feature_data_quality_grade") in {"A", "B"}
            )
            profile_raw_map = {
                "harvest_success_3yr_avg": "harvest_success_3yr_avg",
                "hunter_satisfaction_3yr_avg": "hunter_satisfaction_3yr_avg",
                "hunter_effort_days_3yr_avg": "hunter_effort_days_3yr_avg",
                "harvest_3yr_avg": "harvest_3yr_avg",
                "hunters_afield_3yr_avg": "hunters_afield_3yr_avg",
            }
            for source_field, target_field in profile_raw_map.items():
                row[target_field] = profile.get(source_field, "") if exact_publishable_history else ""
        else:
            for field in PROFILE_DISPLAY_FIELDS:
                row[field] = ""

        output.append(row)

    after_protected = protected_projection(output)
    if len(output) != len(base_rows):
        raise AssertionError("Display overlay changed the live contract row count.")
    if before_protected != after_protected:
        raise AssertionError("Display overlay changed at least one non-harvest field.")

    protected_before_hash = digest(before_protected)
    protected_after_hash = digest(after_protected)
    coverage_fields = [
        "harvest_success_pct",
        "average_days_hunted",
        "hunter_satisfaction",
        "harvest_total",
        "hunters_afield",
        "average_harvest_age",
        "average_harvest_age_3yr_reported",
        "current_age_3yr_average",
        "management_objective_target",
        "management_current_value",
        "hunt_unit_quality_score",
        "harvest_success_3yr_avg",
        "hunter_satisfaction_3yr_avg",
        "hunter_effort_days_3yr_avg",
        "hunters_afield_3yr_avg",
    ]
    management_lineage_issues = []
    score_lineage_issues = []
    for row in output:
        if nonblank(row.get("management_objective_type")) and not all(
            nonblank(row.get(field))
            for field in ("management_source_url", "management_source_locator", "management_source_retrieved_at")
        ):
            management_lineage_issues.append(normalize_code(row.get("hunt_code")))
        if nonblank(row.get("hunt_unit_quality_score")) and not all(
            nonblank(row.get(field))
            for field in (
                "hunt_quality_profile_version",
                "hunt_quality_harvest_source_years",
                "hunt_quality_harvest_match_method",
                "hunt_quality_harvest_data_grade",
                "management_source_url",
                "management_source_locator",
            )
        ):
            score_lineage_issues.append(normalize_code(row.get("hunt_code")))
    if management_lineage_issues:
        raise AssertionError(f"Management lineage incomplete for {sorted(set(management_lineage_issues))[:10]}")
    if score_lineage_issues:
        raise AssertionError(f"Hunt-quality score lineage incomplete for {sorted(set(score_lineage_issues))[:10]}")
    return output, {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": LIVE_URL,
        "rows": len(output),
        "unique_hunt_codes": len({normalize_code(row.get("hunt_code")) for row in output}),
        "display_fields_allowed_to_change": sorted(DISPLAY_FIELDS),
        "updated_field_counts": dict(sorted(updated_fields.items())),
        "coverage_rows": {field: sum(nonblank(row.get(field)) for row in output) for field in coverage_fields},
        "coverage_unique_hunt_codes": {
            field: len({normalize_code(row.get("hunt_code")) for row in output if nonblank(row.get(field))})
            for field in coverage_fields
        },
        "unmatched_harvest_contract_codes": len(unmatched_harvest_codes - {""}),
        "unmatched_age_contract_codes": len(unmatched_age_codes - {""}),
        "management_context_source_rows": len(management_rows),
        "quality_profile_source_rows": len(profile_rows),
        "management_lineage_issue_rows": 0,
        "quality_score_lineage_issue_rows": 0,
        "published_quality_score_unique_hunt_codes": len(
            {normalize_code(row.get("hunt_code")) for row in output if nonblank(row.get("hunt_unit_quality_score"))}
        ),
        "protected_projection_sha256_before": protected_before_hash,
        "protected_projection_sha256_after": protected_after_hash,
        "protected_fields_unchanged": protected_before_hash == protected_after_hash,
        "guardrails": [
            "The current live public contract is the base.",
            "All non-harvest display fields are semantically identical before and after.",
            "Harvest matching uses hunt code plus compatible hunt name and species.",
            "Age matching uses hunt code plus compatible species from the pre-crosswalked official age database.",
            "boundary_id is never used as harvest or age identity.",
            "current_age_3yr_average is refreshed from exact DWR management context and remains separate from reported harvest age.",
            "Management values use exact Hunt Planner source hunt codes plus compatible species and hunt name.",
            "The composite score is published only when the fixed-component evidence gate is met.",
            "No missing quality-score component is reweighted.",
            "Management and quality display fields cannot alter the protected draw, permit, or quota projection.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-url", default=LIVE_URL)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--audit-dir", type=Path, default=AUDIT_DIR)
    args = parser.parse_args()

    base_rows = read_live(args.live_url)
    output, audit = build(base_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    (args.audit_dir / "live_before_public_contract.json").write_text(
        json.dumps(base_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.audit_dir / "harvest_display_overlay_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
