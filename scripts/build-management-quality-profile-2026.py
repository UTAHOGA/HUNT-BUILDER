#!/usr/bin/env python3
"""Build exact DWR management context and a gated Hunt Quality Profile.

The builder expands the retained 227-row Hunt Planner management-unit snapshot
only through its explicit source_hunt_codes. It does not use boundary_id or
synthetic statewide assumptions. Statewide bear, turkey, and cougar authority
is retained as framework/program context and cannot create a unit objective.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import normalize_code, normalize_text, species_family


DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
MANAGEMENT_UNITS = ROOT / "data_model" / "harvest_quality" / "huntplanner_management_units_2026.csv"
PLAN_INVENTORY = ROOT / "data_truth" / "harvest_results_truth" / "sources" / "dwr_management_plan_inventory_2026.json"
FEATURE_MODEL = ROOT / "data_model" / "harvest_quality" / "harvest_feature_model_by_hunt_code_2026.csv"
CONTEXT_OUTPUT = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
CONTEXT_CSV_OUTPUT = ROOT / "data_model" / "harvest_quality" / "hunt_management_objective_context_2026.csv"
PROFILE_OUTPUT = ROOT / "data_model" / "harvest_quality" / "hunt_quality_profile_by_hunt_code_2026.csv"
AUDIT_OUTPUT = ROOT / "processed_data" / "audits" / "hunt_management_quality_20260906" / "build_audit.json"

SCHEMA_VERSION = "HUNT_MANAGEMENT_QUALITY_DISPLAY_V1"
PROFILE_VERSION = "UOGA_HUNT_QUALITY_PROFILE_V1"

FAMILY_TO_PLAN = {
    "deer": "mule_deer",
    "elk": "elk",
    "moose": "moose",
    "pronghorn": "pronghorn",
    "bison": "bison",
    "mountain goat": "mountain_goat",
    "desert bighorn sheep": "bighorn_sheep",
    "rocky mountain bighorn sheep": "bighorn_sheep",
    "bighorn sheep": "bighorn_sheep",
    "black bear": "black_bear",
    "turkey": "wild_turkey",
}

CONTEXT_FIELDS = [
    "schema_version",
    "hunt_code",
    "species",
    "hunt_name",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "management_unit_key",
    "management_unit_name",
    "management_measure_scope",
    "management_measure_applicability",
    "management_objective_type",
    "management_objective_target",
    "management_objective_min",
    "management_objective_max",
    "management_current_value",
    "management_current_numeric",
    "management_objective_delta_from_range",
    "objective_unit",
    "management_objective_status",
    "management_direction",
    "management_objective_note",
    "age_objective",
    "current_age_3yr_average",
    "population_objective",
    "current_population_estimate",
    "bucks_per_100_does_objective",
    "current_bucks_per_100_does_3yr_average",
    "bulls_per_100_cows_objective",
    "bulls_per_100_cows_estimate",
    "management_evidence_status",
    "management_conflict_fields",
    "management_source_url",
    "management_source_retrieved_at",
    "management_source_locator",
    "plan_reference_url",
    "plan_reference_local_path",
    "plan_reference_sha256",
    "plan_reference_scope",
    "plan_reference_match_status",
    "plan_source_page",
    "context_only",
]

PROFILE_FIELDS = [
    "profile_version",
    "hunt_code",
    "species",
    "hunt_name",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "management_objective_type",
    "management_objective_status",
    "management_objective_target",
    "management_current_value",
    "objective_unit",
    "biological_quality_component",
    "harvest_success_3yr_component",
    "hunter_satisfaction_3yr_component",
    "effort_efficiency_3yr_component",
    "hunt_unit_quality_score",
    "hunt_unit_quality_label",
    "hunt_unit_quality_confidence",
    "hunt_unit_quality_score_status",
    "hunt_unit_quality_reason_codes",
    "hunt_unit_quality_comparison_scope",
    "harvest_success_recent",
    "harvest_success_3yr_avg",
    "hunter_satisfaction_recent",
    "hunter_satisfaction_3yr_avg",
    "hunter_effort_days_recent",
    "hunter_effort_days_3yr_avg",
    "harvest_recent",
    "harvest_3yr_avg",
    "hunters_afield_recent",
    "hunters_afield_3yr_avg",
    "average_harvest_age_recent",
    "average_harvest_age_3yr_reported",
    "average_harvest_age_3yr_computed",
    "harvest_feature_source_years",
    "harvest_feature_match_method",
    "harvest_feature_data_quality_grade",
    "management_source_url",
    "management_source_locator",
    "profile_disclaimer",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def display_number(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def parse_target(value: object) -> tuple[float | None, float | None]:
    """Parse one exact target or one simple range; reject multi-area values."""

    text = clean(value).replace(",", "").replace("–", "-").replace("—", "-")
    values = [float(item) for item in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)]
    if len(values) == 1:
        return values[0], values[0]
    if len(values) == 2 and re.search(r"\d\s*-\s*\d", text):
        return min(values), max(values)
    return None, None


def parse_current(value: object) -> float | None:
    text = clean(value).replace(",", "")
    values = [float(item) for item in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)]
    return values[0] if len(values) == 1 else None


def text_tokens(value: object) -> set[str]:
    ignored = {"unit", "management", "cwmu", "mountains", "mountain", "mtns", "the", "and"}
    return {token for token in normalize_text(value).split() if token not in ignored}


def plan_reference(
    management: dict[str, str],
    plans: list[dict[str, object]],
) -> tuple[dict[str, object] | None, str]:
    family = FAMILY_TO_PLAN.get(species_family(management.get("species")), "")
    candidates = [row for row in plans if row.get("species_family") == family]
    unit_candidates = [row for row in candidates if row.get("plan_scope") == "unit"]
    management_tokens = text_tokens(management.get("management_unit_name"))
    matches: list[tuple[float, dict[str, object]]] = []
    for row in unit_candidates:
        for label in row.get("unit_labels") or []:
            label_tokens = text_tokens(label)
            if not label_tokens or not management_tokens:
                continue
            overlap = len(label_tokens & management_tokens) / len(label_tokens)
            if label_tokens <= management_tokens or overlap >= 0.75:
                matches.append((overlap, row))
    if matches:
        best_score = max(score for score, _ in matches)
        best = {id(row): row for score, row in matches if score == best_score}
        if len(best) == 1:
            return next(iter(best.values())), "UNIT_PLAN_TOKEN_MATCH"
    statewide = [row for row in candidates if row.get("plan_scope") == "statewide"]
    if len(statewide) == 1:
        return statewide[0], "STATEWIDE_PLAN_REFERENCE"
    return None, "NO_UNAMBIGUOUS_PLAN_REFERENCE"


def primary_measure(management: dict[str, str], database: dict[str, str]) -> dict[str, str]:
    family = species_family(management.get("species"))
    sex = normalize_text(database.get("sex_type"))
    age_applies = (
        (family == "elk" and "bull" in sex)
        or (family == "moose" and "bull" in sex)
        or (family == "pronghorn" and "buck" in sex)
    )
    deer_composition_applies = family == "deer" and "buck" in sex

    if age_applies and clean(management.get("age_objective")):
        return {
            "type": "DWR Harvested Age Objective",
            "target": clean(management.get("age_objective")),
            "current": clean(management.get("current_age_3yr_average")),
            "unit": "years, DWR current 3-year harvested age",
            "target_field": "age_objective",
            "current_field": "current_age_3yr_average",
            "applicability": "APPLIES_TO_SELECTED_HUNT",
        }
    if deer_composition_applies and clean(management.get("bucks_per_100_does_objective")):
        return {
            "type": "DWR Buck-to-Doe Composition Objective",
            "target": clean(management.get("bucks_per_100_does_objective")),
            "current": clean(management.get("current_bucks_per_100_does_3yr_average")),
            "unit": "bucks per 100 does, DWR current 3-year average",
            "target_field": "bucks_per_100_does_objective",
            "current_field": "current_bucks_per_100_does_3yr_average",
            "applicability": "APPLIES_TO_SELECTED_HUNT",
        }
    if clean(management.get("population_objective")):
        return {
            "type": "DWR Population Objective",
            "target": clean(management.get("population_objective")),
            "current": clean(management.get("current_population_estimate")),
            "unit": "animals, as labeled by DWR",
            "target_field": "population_objective",
            "current_field": "current_population_estimate",
            "applicability": "APPLIES_TO_MANAGEMENT_UNIT",
        }
    return {
        "type": "DWR Management Context",
        "target": "",
        "current": "",
        "unit": "",
        "target_field": "",
        "current_field": "",
        "applicability": "NO_COMPARABLE_OBJECTIVE_AVAILABLE",
    }


def objective_status(
    measure: dict[str, str], management: dict[str, str]
) -> tuple[str, str, str, str, str, str]:
    target_min, target_max = parse_target(measure["target"])
    current = parse_current(measure["current"])
    conflicts = {item for item in clean(management.get("value_conflict_fields")).split("|") if item}
    relevant_conflict = measure["target_field"] in conflicts or measure["current_field"] in conflicts
    if relevant_conflict:
        return (
            "REVIEW_VALUE_CONFLICT",
            "DWR values conflict across retained Hunt Planner records",
            "",
            "",
            "",
            "Relevant DWR Hunt Planner values conflict; no comparison or score is published.",
        )
    if not measure["target"]:
        return "NO_QUANTIFIED_OBJECTIVE", "No quantified objective available", "", "", "", ""
    if target_min is None or target_max is None:
        return (
            "OBJECTIVE_PRESENT_COMPLEX_VALUE",
            "Objective loaded; exact numeric comparison unavailable",
            "",
            "",
            "",
            "The official target contains multiple areas or labels and is displayed without a computed comparison.",
        )
    if current is None:
        return (
            "OBJECTIVE_KNOWN_CURRENT_UNAVAILABLE",
            "Objective known; current value unavailable",
            display_number(target_min),
            display_number(target_max),
            "",
            "The official objective is available, but no comparable current value is present.",
        )
    if current < target_min:
        delta = current - target_min
        return (
            "BELOW_OBJECTIVE",
            "Below DWR objective",
            display_number(target_min),
            display_number(target_max),
            display_number(delta),
            f"Current value {display_number(current)} is below the DWR objective {measure['target']} {measure['unit']}.",
        )
    if current > target_max:
        delta = current - target_max
        return (
            "ABOVE_OBJECTIVE",
            "Above DWR objective",
            display_number(target_min),
            display_number(target_max),
            display_number(delta),
            f"Current value {display_number(current)} is above the DWR objective {measure['target']} {measure['unit']}.",
        )
    return (
        "MEETING_OBJECTIVE",
        "Meeting DWR objective",
        display_number(target_min),
        display_number(target_max),
        "0",
        f"Current value {display_number(current)} is within the DWR objective {measure['target']} {measure['unit']}.",
    )


def context_from_hunt_planner(
    management: dict[str, str],
    database: dict[str, str],
    plans: list[dict[str, object]],
) -> dict[str, object]:
    measure = primary_measure(management, database)
    status, direction, target_min, target_max, delta, note = objective_status(measure, management)
    plan, plan_match = plan_reference(management, plans)
    source_urls = [item for item in clean(management.get("source_urls")).split("|") if item]
    return {
        "schema_version": SCHEMA_VERSION,
        "hunt_code": normalize_code(database.get("hunt_code")),
        "species": clean(database.get("species")),
        "hunt_name": clean(database.get("hunt_name")),
        "sex_type": clean(database.get("sex_type")),
        "hunt_type": clean(database.get("hunt_type")),
        "hunt_class": clean(database.get("hunt_class")),
        "management_unit_key": clean(management.get("management_unit_key")),
        "management_unit_name": clean(management.get("management_unit_name")),
        "management_measure_scope": "DWR_HUNT_PLANNER_MANAGEMENT_UNIT",
        "management_measure_applicability": measure["applicability"],
        "management_objective_type": measure["type"],
        "management_objective_target": measure["target"],
        "management_objective_min": target_min,
        "management_objective_max": target_max,
        "management_current_value": measure["current"],
        "management_current_numeric": display_number(parse_current(measure["current"])),
        "management_objective_delta_from_range": delta,
        "objective_unit": measure["unit"],
        "management_objective_status": status,
        "management_direction": direction,
        "management_objective_note": note,
        "age_objective": clean(management.get("age_objective")),
        "current_age_3yr_average": clean(management.get("current_age_3yr_average")),
        "population_objective": clean(management.get("population_objective")),
        "current_population_estimate": clean(management.get("current_population_estimate")),
        "bucks_per_100_does_objective": clean(management.get("bucks_per_100_does_objective")),
        "current_bucks_per_100_does_3yr_average": clean(
            management.get("current_bucks_per_100_does_3yr_average")
        ),
        "bulls_per_100_cows_objective": clean(management.get("bulls_per_100_cows_objective")),
        "bulls_per_100_cows_estimate": clean(management.get("bulls_per_100_cows_estimate")),
        "management_evidence_status": clean(management.get("evidence_status")),
        "management_conflict_fields": clean(management.get("value_conflict_fields")),
        "management_source_url": source_urls[0] if source_urls else "",
        "management_source_retrieved_at": clean(management.get("source_retrieved_at")),
        "management_source_locator": "DWR Hunt Planner management statistics; web source, PDF page not applicable",
        "plan_reference_url": clean(plan.get("source_url")) if plan else "",
        "plan_reference_local_path": clean(plan.get("local_path")) if plan else "",
        "plan_reference_sha256": clean(plan.get("sha256")) if plan else "",
        "plan_reference_scope": clean(plan.get("plan_scope")) if plan else "",
        "plan_reference_match_status": plan_match,
        "plan_source_page": "Reference plan only; objective value sourced from Hunt Planner web record",
        "context_only": True,
    }


def framework_context(database: dict[str, str], inventory: dict[str, object]) -> dict[str, object] | None:
    family = species_family(database.get("species"))
    plans = inventory["plans"]
    plan = next(
        (
            row
            for row in plans
            if row.get("species_family") == FAMILY_TO_PLAN.get(family) and row.get("plan_scope") == "statewide"
        ),
        None,
    )
    base = {
        "schema_version": SCHEMA_VERSION,
        "hunt_code": normalize_code(database.get("hunt_code")),
        "species": clean(database.get("species")),
        "hunt_name": clean(database.get("hunt_name")),
        "sex_type": clean(database.get("sex_type")),
        "hunt_type": clean(database.get("hunt_type")),
        "hunt_class": clean(database.get("hunt_class")),
        "management_unit_key": "",
        "management_unit_name": "Statewide",
        "management_measure_applicability": "STATEWIDE_CONTEXT_ONLY",
        "management_objective_min": "",
        "management_objective_max": "",
        "management_current_value": "",
        "management_current_numeric": "",
        "management_objective_delta_from_range": "",
        "age_objective": "",
        "current_age_3yr_average": "",
        "population_objective": "",
        "current_population_estimate": "",
        "bucks_per_100_does_objective": "",
        "current_bucks_per_100_does_3yr_average": "",
        "bulls_per_100_cows_objective": "",
        "bulls_per_100_cows_estimate": "",
        "management_conflict_fields": "",
        "management_source_retrieved_at": clean(inventory.get("retrieved_at_utc")),
        "plan_reference_url": clean(plan.get("source_url")) if plan else "",
        "plan_reference_local_path": clean(plan.get("local_path")) if plan else "",
        "plan_reference_sha256": clean(plan.get("sha256")) if plan else "",
        "plan_reference_scope": "statewide" if plan else "",
        "plan_reference_match_status": "STATEWIDE_FRAMEWORK_REFERENCE" if plan else "",
        "context_only": True,
    }
    if family == "black bear" and plan:
        return {
            **base,
            "management_measure_scope": "DWR_STATEWIDE_STRATEGY_FRAMEWORK",
            "management_objective_type": "Black Bear Three-Year Strategy Framework",
            "management_objective_target": (
                "Adult male age 5: Light >35%, Moderate 25-35%, Liberal <25%; "
                "female harvest: Light <30%, Moderate 30-40%, Liberal 40-45%; "
                "DNA population growth: Light +10 to +20%, Moderate -10 to +10%, Liberal -10 to -20%"
            ),
            "objective_unit": "strategy-dependent three-year measures",
            "management_objective_status": "UNIT_STRATEGY_NOT_AVAILABLE",
            "management_direction": "Statewide framework; selected unit strategy unavailable",
            "management_objective_note": (
                "DWR requires the unit's selected Light, Moderate, or Liberal strategy before a band can be called the unit target."
            ),
            "management_evidence_status": "VERIFIED_STATEWIDE_PLAN_FRAMEWORK",
            "management_source_url": clean(plan.get("source_url")),
            "management_source_locator": "Official black bear plan, population-management objective table",
            "plan_source_page": "26",
        }
    if family == "turkey" and plan:
        return {
            **base,
            "management_measure_scope": "DWR_STATEWIDE_PROGRAM_OBJECTIVES",
            "management_objective_type": "Wild Turkey Statewide Program Objectives",
            "management_objective_target": (
                "Enhance 100,000 habitat acres statewide by 2029; increase turkey hunters 10% by 2029; "
                "increase wild turkey event participation 10% by 2029"
            ),
            "objective_unit": "statewide habitat acres and participation change",
            "management_objective_status": "STATEWIDE_PROGRAM_OBJECTIVE_NOT_UNIT_TARGET",
            "management_direction": "Statewide program context only",
            "management_objective_note": "These objectives do not create a hunt-unit harvest-quality target.",
            "management_evidence_status": "VERIFIED_STATEWIDE_PLAN_OBJECTIVES",
            "management_source_url": clean(plan.get("source_url")),
            "management_source_locator": "Official wild turkey plan objectives",
            "plan_source_page": "20|23",
        }
    if family == "cougar":
        cougar = inventory["cougar_program_authority"]
        current = cougar["current_program_authority"]
        return {
            **base,
            "management_measure_scope": "DWR_CURRENT_OPEN_SEASON_PROGRAM",
            "management_objective_type": "Cougar Open-Season Program Authority",
            "management_objective_target": clean(current.get("management_goal")),
            "objective_unit": "qualitative program goal; no current quantified objective",
            "management_objective_status": "NO_CURRENT_MANAGEMENT_PLAN_OR_QUANTIFIED_OBJECTIVE",
            "management_direction": "Open-season program context only",
            "management_objective_note": clean(cougar.get("research_display_guidance")),
            "management_evidence_status": clean(cougar.get("authority_status")),
            "management_source_url": clean(current.get("source_url")),
            "management_source_locator": "DWR Cougar program background; web source, PDF page not applicable",
            "plan_reference_url": "",
            "plan_reference_local_path": "",
            "plan_reference_sha256": "",
            "plan_reference_scope": "program_web_authority",
            "plan_reference_match_status": "NO_CURRENT_MANAGEMENT_PLAN_LISTED",
            "plan_source_page": "N/A - current web program authority",
        }
    return None


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def score_label(score: float) -> str:
    if score >= 85:
        return "Very strong hunt-quality profile"
    if score >= 70:
        return "Strong hunt-quality profile"
    if score >= 55:
        return "Moderate hunt-quality profile"
    return "Lower hunt-quality profile"


def build_profile(
    database: dict[str, str],
    feature: dict[str, str] | None,
    context: dict[str, object] | None,
) -> dict[str, object]:
    feature = feature or {}
    context = context or {}
    reasons: list[str] = []
    status = clean(context.get("management_objective_status"))
    current = number(context.get("management_current_numeric"))
    objective_min = number(context.get("management_objective_min"))
    success = number(feature.get("harvest_success_3yr_avg"))
    satisfaction = number(feature.get("hunter_satisfaction_3yr_avg"))
    effort = number(feature.get("hunter_effort_days_3yr_avg"))
    hunters = number(feature.get("hunters_afield_3yr_avg"))
    source_years = clean(feature.get("harvest_feature_source_years")).split("|")

    if not context:
        reasons.append("NO_VERIFIED_MANAGEMENT_CONTEXT")
    if clean(context.get("management_measure_applicability")) not in {
        "APPLIES_TO_SELECTED_HUNT",
        "APPLIES_TO_MANAGEMENT_UNIT",
    }:
        reasons.append("MANAGEMENT_MEASURE_NOT_SCORE_APPLICABLE")
    if status not in {"BELOW_OBJECTIVE", "MEETING_OBJECTIVE", "ABOVE_OBJECTIVE"}:
        reasons.append("NO_COMPARABLE_MANAGEMENT_STATUS")
    if current is None or objective_min in (None, 0):
        reasons.append("MANAGEMENT_TARGET_OR_CURRENT_NOT_NUMERIC")
    if status == "REVIEW_VALUE_CONFLICT":
        reasons.append("MANAGEMENT_VALUE_CONFLICT")
    if clean(feature.get("harvest_feature_match_method")) != "EXACT_HUNT_CODE_HISTORY":
        reasons.append("HARVEST_HISTORY_NOT_EXACT_HUNT_CODE")
    if clean(feature.get("harvest_feature_data_quality_grade")) not in {"A", "B"}:
        reasons.append("HARVEST_DATA_GRADE_BELOW_B")
    if "2025" not in source_years:
        reasons.append("HARVEST_HISTORY_NOT_CURRENT_THROUGH_2025")
    for name, value in (
        ("SUCCESS_3YR", success),
        ("SATISFACTION_3YR", satisfaction),
        ("EFFORT_3YR", effort),
        ("HUNTERS_AFIELD_3YR", hunters),
    ):
        if value is None:
            reasons.append(f"MISSING_{name}")
    if hunters is not None and hunters < 10:
        reasons.append("THREE_YEAR_HUNTERS_AFIELD_BELOW_10")

    biological = clamp((current / objective_min) * 100.0) if current is not None and objective_min else None
    success_component = clamp(success) if success is not None else None
    satisfaction_component = clamp((satisfaction / 5.0) * 100.0) if satisfaction is not None else None
    effort_component = clamp(100.0 - (effort / 12.0) * 100.0) if effort is not None else None

    publishable = not reasons
    score = None
    if publishable:
        assert biological is not None and success_component is not None
        assert satisfaction_component is not None and effort_component is not None
        score = (
            0.40 * biological
            + 0.25 * success_component
            + 0.20 * satisfaction_component
            + 0.15 * effort_component
        )
    confidence = ""
    if publishable:
        confidence = (
            "HIGH"
            if clean(feature.get("harvest_feature_data_quality_grade")) == "A" and (hunters or 0) >= 25
            else "MODERATE"
        )
    return {
        "profile_version": PROFILE_VERSION,
        "hunt_code": normalize_code(database.get("hunt_code")),
        "species": clean(database.get("species")),
        "hunt_name": clean(database.get("hunt_name")),
        "sex_type": clean(database.get("sex_type")),
        "hunt_type": clean(database.get("hunt_type")),
        "hunt_class": clean(database.get("hunt_class")),
        "management_objective_type": clean(context.get("management_objective_type")),
        "management_objective_status": status,
        "management_objective_target": clean(context.get("management_objective_target")),
        "management_current_value": clean(context.get("management_current_value")),
        "objective_unit": clean(context.get("objective_unit")),
        "biological_quality_component": display_number(biological) if publishable else "",
        "harvest_success_3yr_component": display_number(success_component) if publishable else "",
        "hunter_satisfaction_3yr_component": display_number(satisfaction_component) if publishable else "",
        "effort_efficiency_3yr_component": display_number(effort_component) if publishable else "",
        "hunt_unit_quality_score": display_number(score) if publishable else "",
        "hunt_unit_quality_label": score_label(score) if score is not None else "",
        "hunt_unit_quality_confidence": confidence,
        "hunt_unit_quality_score_status": (
            "PUBLISHABLE_EVIDENCE_THRESHOLD_MET" if publishable else "WITHHELD_EVIDENCE_THRESHOLD_NOT_MET"
        ),
        "hunt_unit_quality_reason_codes": "|".join(dict.fromkeys(reasons)),
        "hunt_unit_quality_comparison_scope": "|".join(
            [species_family(database.get("species")), clean(database.get("sex_type")), clean(database.get("hunt_class"))]
        ),
        "harvest_success_recent": clean(feature.get("harvest_success_recent")),
        "harvest_success_3yr_avg": clean(feature.get("harvest_success_3yr_avg")),
        "hunter_satisfaction_recent": clean(feature.get("hunter_satisfaction_recent")),
        "hunter_satisfaction_3yr_avg": clean(feature.get("hunter_satisfaction_3yr_avg")),
        "hunter_effort_days_recent": clean(feature.get("hunter_effort_days_recent")),
        "hunter_effort_days_3yr_avg": clean(feature.get("hunter_effort_days_3yr_avg")),
        "harvest_recent": clean(feature.get("harvest_recent")),
        "harvest_3yr_avg": clean(feature.get("harvest_3yr_avg")),
        "hunters_afield_recent": clean(feature.get("hunters_afield_recent")),
        "hunters_afield_3yr_avg": clean(feature.get("hunters_afield_3yr_avg")),
        "average_harvest_age_recent": clean(feature.get("average_harvest_age_recent")),
        "average_harvest_age_3yr_reported": clean(feature.get("average_harvest_age_3yr_reported")),
        "average_harvest_age_3yr_computed": clean(feature.get("average_harvest_age_3yr_computed")),
        "harvest_feature_source_years": clean(feature.get("harvest_feature_source_years")),
        "harvest_feature_match_method": clean(feature.get("harvest_feature_match_method")),
        "harvest_feature_data_quality_grade": clean(feature.get("harvest_feature_data_quality_grade")),
        "management_source_url": clean(context.get("management_source_url")),
        "management_source_locator": clean(context.get("management_source_locator")),
        "profile_disclaimer": (
            "U.O.G.A. display-only score; not a DWR score, not comparable across species/hunt classes, "
            "and never an odds, permit, or quota input."
        ),
    }


def main() -> int:
    database_rows = read_csv(DATABASE)
    management_rows = read_csv(MANAGEMENT_UNITS)
    feature_rows = read_csv(FEATURE_MODEL)
    inventory = read_json(PLAN_INVENTORY)
    plans = inventory["plans"]
    database_by_code = {normalize_code(row.get("hunt_code")): row for row in database_rows}
    feature_by_code = {normalize_code(row.get("hunt_code")): row for row in feature_rows}

    contexts: list[dict[str, object]] = []
    source_codes: list[str] = []
    for management in management_rows:
        for source_code in clean(management.get("source_hunt_codes")).split("|"):
            code = normalize_code(source_code)
            if not code:
                continue
            source_codes.append(code)
            database = database_by_code.get(code)
            if database is None:
                raise AssertionError(f"Hunt Planner management code missing from DATABASE.csv: {code}")
            if species_family(database.get("species")) != species_family(management.get("species")):
                raise AssertionError(
                    f"Management species mismatch for {code}: {management.get('species')} vs {database.get('species')}"
                )
            contexts.append(context_from_hunt_planner(management, database, plans))

    context_codes = {clean(row.get("hunt_code")) for row in contexts}
    for database in database_rows:
        code = normalize_code(database.get("hunt_code"))
        if code in context_codes:
            continue
        framework = framework_context(database, inventory)
        if framework is not None:
            contexts.append(framework)
            context_codes.add(code)

    duplicate_context_codes = [code for code, count in Counter(clean(row.get("hunt_code")) for row in contexts).items() if count > 1]
    if duplicate_context_codes:
        raise AssertionError(f"Duplicate management context hunt codes: {duplicate_context_codes[:10]}")
    if len(source_codes) != len(set(source_codes)):
        raise AssertionError("The Hunt Planner management snapshot contains duplicate source hunt codes.")

    contexts.sort(key=lambda row: (clean(row.get("species")), clean(row.get("hunt_code"))))
    context_by_code = {clean(row.get("hunt_code")): row for row in contexts}
    profiles = [
        build_profile(database, feature_by_code.get(normalize_code(database.get("hunt_code"))), context_by_code.get(normalize_code(database.get("hunt_code"))))
        for database in database_rows
    ]
    profiles.sort(key=lambda row: (clean(row.get("species")), clean(row.get("hunt_code"))))

    CONTEXT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    CONTEXT_OUTPUT.write_text(json.dumps(contexts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(CONTEXT_CSV_OUTPUT, contexts, CONTEXT_FIELDS)
    write_csv(PROFILE_OUTPUT, profiles, PROFILE_FIELDS)

    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "profile_version": PROFILE_VERSION,
        "source_management_unit_rows": len(management_rows),
        "source_hunt_code_references": len(source_codes),
        "source_hunt_code_references_unique": len(set(source_codes)),
        "database_rows": len(database_rows),
        "management_context_rows": len(contexts),
        "management_context_rows_by_species": dict(sorted(Counter(clean(row.get("species")) for row in contexts).items())),
        "management_status_counts": dict(
            sorted(Counter(clean(row.get("management_objective_status")) for row in contexts).items())
        ),
        "plan_reference_match_counts": dict(
            sorted(Counter(clean(row.get("plan_reference_match_status")) for row in contexts).items())
        ),
        "relevant_value_conflict_rows": sum(
            clean(row.get("management_objective_status")) == "REVIEW_VALUE_CONFLICT" for row in contexts
        ),
        "profile_rows": len(profiles),
        "published_composite_scores": sum(bool(clean(row.get("hunt_unit_quality_score"))) for row in profiles),
        "published_scores_by_species": dict(
            sorted(
                Counter(
                    clean(row.get("species"))
                    for row in profiles
                    if clean(row.get("hunt_unit_quality_score"))
                ).items()
            )
        ),
        "withheld_score_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for row in profiles
                    for reason in clean(row.get("hunt_unit_quality_reason_codes")).split("|")
                    if reason
                ).items()
            )
        ),
        "input_sha256": {
            str(DATABASE.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(DATABASE.read_bytes()).hexdigest(),
            str(MANAGEMENT_UNITS.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(MANAGEMENT_UNITS.read_bytes()).hexdigest(),
            str(PLAN_INVENTORY.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(PLAN_INVENTORY.read_bytes()).hexdigest(),
            str(FEATURE_MODEL.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(FEATURE_MODEL.read_bytes()).hexdigest(),
        },
        "output_sha256": {
            str(CONTEXT_OUTPUT.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(CONTEXT_OUTPUT.read_bytes()).hexdigest(),
            str(CONTEXT_CSV_OUTPUT.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(CONTEXT_CSV_OUTPUT.read_bytes()).hexdigest(),
            str(PROFILE_OUTPUT.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(PROFILE_OUTPUT.read_bytes()).hexdigest(),
        },
        "validations": {
            "all_hunt_planner_codes_exist_in_database": True,
            "all_hunt_planner_species_are_compatible": True,
            "duplicate_management_context_codes": 0,
            "boundary_id_used_for_identity": False,
            "synthetic_statewide_unit_targets_created": False,
            "missing_component_reweighting_allowed": False,
            "profile_changes_draw_probability_or_quota": False,
        },
    }
    AUDIT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
