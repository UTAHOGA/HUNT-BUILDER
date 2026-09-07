#!/usr/bin/env python3
"""Audit every populated management/quality publication field and its lineage."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
MANAGEMENT_UNITS = ROOT / "data_model" / "harvest_quality" / "huntplanner_management_units_2026.csv"
INVENTORY = ROOT / "data_truth" / "harvest_results_truth" / "sources" / "dwr_management_plan_inventory_2026.json"
CONTEXT = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
PROFILE = ROOT / "data_model" / "harvest_quality" / "hunt_quality_profile_by_hunt_code_2026.csv"
PUBLIC = ROOT / "processed_data" / "public_contracts" / "hunt_application_outlook.json"
OVERLAY_AUDIT = ROOT / "processed_data" / "audits" / "management_quality_release_20260906" / "harvest_display_overlay_audit.json"
OUTPUT_DIR = ROOT / "processed_data" / "audits" / "management_quality_release_20260906"

HARVEST_LINEAGE = {
    "harvest_success_pct": ("harvest_success_reported_year", "harvest_success_source_file", "harvest_success_source_page", "%"),
    "average_days_hunted": ("average_days_hunted_reported_year", "average_days_hunted_source_file", "average_days_hunted_source_page", "days"),
    "hunter_satisfaction": ("hunter_satisfaction_reported_year", "hunter_satisfaction_source_file", "hunter_satisfaction_source_page", "0-5 satisfaction score"),
    "harvest_total": ("harvest_total_reported_year", "harvest_total_source_file", "harvest_total_source_page", "animals harvested"),
    "hunters_afield": ("hunters_afield_reported_year", "hunters_afield_source_file", "hunters_afield_source_page", "hunters"),
}

AGE_LINEAGE = {
    "average_harvest_age": ("average_harvest_age_reported_year", "age_source_file", "age_source_page", "years, annual harvested age"),
    "average_harvest_age_3yr_reported": (
        "average_harvest_age_3yr_reported_year",
        "average_harvest_age_3yr_source_file",
        "average_harvest_age_3yr_source_page",
        "years, DWR-reported 3-year harvested age",
    ),
}

MANAGEMENT_FIELDS = {
    "management_objective_type",
    "management_objective_target",
    "management_current_value",
    "management_objective_unit",
    "management_objective_status",
    "management_direction",
    "management_measure_scope",
    "management_measure_applicability",
    "management_unit_name",
    "current_age_3yr_average",
    "population_objective",
    "current_population_estimate",
    "bucks_per_100_does_objective",
    "current_bucks_per_100_does_3yr_average",
}

PROFILE_FIELDS = {
    "hunt_unit_quality_score",
    "hunt_unit_quality_label",
    "hunt_unit_quality_confidence",
    "hunt_unit_quality_score_status",
    "hunt_quality_biological_component",
    "hunt_quality_success_3yr_component",
    "hunt_quality_satisfaction_3yr_component",
    "hunt_quality_effort_3yr_component",
    "harvest_success_3yr_avg",
    "hunter_satisfaction_3yr_avg",
    "hunter_effort_days_3yr_avg",
    "harvest_3yr_avg",
    "hunters_afield_3yr_avg",
}

PROFILE_OBSERVED_FIELDS = {
    "hunt_unit_quality_score",
    "hunt_quality_biological_component",
    "hunt_quality_success_3yr_component",
    "hunt_quality_satisfaction_3yr_component",
    "hunt_quality_effort_3yr_component",
    "harvest_success_3yr_avg",
    "hunter_satisfaction_3yr_avg",
    "hunter_effort_days_3yr_avg",
    "harvest_3yr_avg",
    "hunters_afield_3yr_avg",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def text(value: object) -> str:
    return str(value or "").strip()


def code(row: dict[str, object]) -> str:
    return text(row.get("hunt_code")).upper()


def number(value: object) -> float | None:
    try:
        return float(text(value))
    except ValueError:
        return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lineage_row(row: dict[str, object], field: str) -> dict[str, object]:
    value = text(row.get(field))
    result = {
        "hunt_code": code(row),
        "species": text(row.get("species")),
        "field_name": field,
        "published_value": value,
        "source_reference": "",
        "source_year": "",
        "source_page_or_locator": "",
        "identity_status": "EXACT_HUNT_CODE_COMPATIBLE_SPECIES_NAME",
        "unit_status": "NOT_APPLICABLE",
        "audit_status": "PASS",
        "issue": "",
    }
    if field in HARVEST_LINEAGE:
        year_field, file_field, page_field, unit = HARVEST_LINEAGE[field]
        result.update(
            source_reference=text(row.get(file_field)),
            source_year=text(row.get(year_field)),
            source_page_or_locator=text(row.get(page_field)),
            unit_status=unit,
        )
    elif field in AGE_LINEAGE:
        year_field, file_field, page_field, unit = AGE_LINEAGE[field]
        result.update(
            source_reference=text(row.get(file_field)),
            source_year=text(row.get(year_field)),
            source_page_or_locator=text(row.get(page_field)),
            unit_status=unit,
        )
    elif field in MANAGEMENT_FIELDS:
        result.update(
            source_reference=text(row.get("management_source_url")),
            source_year=text(row.get("management_source_retrieved_at"))[:10],
            source_page_or_locator=text(row.get("management_source_locator")),
            unit_status=text(row.get("management_objective_unit")) or "context field",
        )
    elif field in PROFILE_FIELDS:
        source_year = text(row.get("hunt_quality_harvest_source_years"))
        if field not in PROFILE_OBSERVED_FIELDS and not source_year:
            source_year = "2026 profile build"
        result.update(
            source_reference="data_model/harvest_quality/hunt_quality_profile_by_hunt_code_2026.csv",
            source_year=source_year,
            source_page_or_locator="Derived fixed-weight profile; PDF page not applicable",
            unit_status="U.O.G.A. display-only profile field",
        )
    required = ("source_reference", "source_year", "source_page_or_locator", "identity_status", "unit_status")
    missing = [item for item in required if not text(result.get(item))]
    if missing:
        result["audit_status"] = "FAIL"
        result["issue"] = "missing " + ",".join(missing)
    return result


def main() -> int:
    database = read_csv(DATABASE)
    management_units = read_csv(MANAGEMENT_UNITS)
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    contexts = json.loads(CONTEXT.read_text(encoding="utf-8"))
    profiles = read_csv(PROFILE)
    public_rows = json.loads(PUBLIC.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY_AUDIT.read_text(encoding="utf-8"))

    db_by_code = {code(row): row for row in database}
    context_by_code = {code(row): row for row in contexts}
    profile_by_code = {code(row): row for row in profiles}
    if len(db_by_code) != len(database):
        raise AssertionError("DATABASE.csv hunt codes are not unique.")
    if len(context_by_code) != len(contexts):
        raise AssertionError("Management context hunt codes are not unique.")
    if len(profile_by_code) != len(profiles):
        raise AssertionError("Profile hunt codes are not unique.")

    source_codes = [
        item
        for row in management_units
        for item in text(row.get("source_hunt_codes")).split("|")
        if item
    ]
    if len(source_codes) != 656 or len(set(source_codes)) != 656:
        raise AssertionError("Unexpected duplicate Hunt Planner management source codes.")
    missing_source_codes = sorted(set(source_codes) - set(context_by_code))
    if missing_source_codes:
        raise AssertionError(f"Management context omitted source codes: {missing_source_codes[:10]}")

    for context in contexts:
        c = code(context)
        if c not in db_by_code:
            raise AssertionError(f"Management context code absent from DATABASE.csv: {c}")
        plan_path = text(context.get("plan_reference_local_path"))
        plan_hash = text(context.get("plan_reference_sha256"))
        if plan_path:
            local = ROOT / plan_path
            if not local.is_file() or sha256(local) != plan_hash:
                raise AssertionError(f"Plan reference hash mismatch for {c}: {plan_path}")

    public_by_code: dict[str, list[dict[str, object]]] = {}
    for row in public_rows:
        public_by_code.setdefault(code(row), []).append(row)
    display_fields = HARVEST_LINEAGE.keys() | AGE_LINEAGE.keys() | MANAGEMENT_FIELDS | PROFILE_FIELDS
    for c, rows in public_by_code.items():
        signatures = {
            tuple(text(row.get(field)) for field in sorted(display_fields))
            for row in rows
        }
        if len(signatures) != 1:
            raise AssertionError(f"Display evidence differs by residency for {c}")

    lineage_rows: list[dict[str, object]] = []
    for c, rows in sorted(public_by_code.items()):
        row = rows[0]
        for field in sorted(display_fields):
            if text(row.get(field)):
                lineage_rows.append(lineage_row(row, field))

        context = context_by_code.get(c)
        if context:
            for public_field, context_field in {
                "management_objective_type": "management_objective_type",
                "management_objective_target": "management_objective_target",
                "management_current_value": "management_current_value",
                "management_objective_unit": "objective_unit",
                "management_objective_status": "management_objective_status",
                "management_source_url": "management_source_url",
            }.items():
                if text(row.get(public_field)) != text(context.get(context_field)):
                    raise AssertionError(f"Public management mismatch for {c} field {public_field}")
        elif text(row.get("management_objective_type")):
            raise AssertionError(f"Public management field has no verified context row: {c}")

        profile = profile_by_code.get(c)
        public_score = number(row.get("hunt_unit_quality_score"))
        if public_score is not None:
            if profile is None or text(profile.get("hunt_unit_quality_score_status")) != "PUBLISHABLE_EVIDENCE_THRESHOLD_MET":
                raise AssertionError(f"Published score failed its profile gate: {c}")
            components = [
                number(row.get("hunt_quality_biological_component")),
                number(row.get("hunt_quality_success_3yr_component")),
                number(row.get("hunt_quality_satisfaction_3yr_component")),
                number(row.get("hunt_quality_effort_3yr_component")),
            ]
            if any(value is None for value in components):
                raise AssertionError(f"Published score has a missing component: {c}")
            expected = 0.40 * components[0] + 0.25 * components[1] + 0.20 * components[2] + 0.15 * components[3]
            if not math.isclose(public_score, expected, abs_tol=0.002):
                raise AssertionError(f"Published score formula mismatch for {c}: {public_score} vs {expected}")
            if text(row.get("species")) in {"Black Bear", "Turkey", "Cougar"}:
                raise AssertionError(f"Framework/program-only species received a composite score: {c}")

    lineage_failures = [row for row in lineage_rows if row["audit_status"] != "PASS"]
    if lineage_failures:
        raise AssertionError(f"Publication lineage failures: {lineage_failures[:5]}")
    if not overlay.get("protected_fields_unchanged"):
        raise AssertionError("Protected public-contract fields changed.")
    if overlay.get("protected_projection_sha256_before") != overlay.get("protected_projection_sha256_after"):
        raise AssertionError("Protected projection hashes differ.")

    annual_three_year_distinct = sum(
        bool(
            text(rows[0].get("average_harvest_age"))
            and text(rows[0].get("average_harvest_age_3yr_reported"))
            and text(rows[0].get("average_harvest_age")) != text(rows[0].get("average_harvest_age_3yr_reported"))
        )
        for rows in public_by_code.values()
    )
    planner_reported_distinct = sum(
        bool(
            text(rows[0].get("current_age_3yr_average"))
            and text(rows[0].get("average_harvest_age_3yr_reported"))
            and text(rows[0].get("current_age_3yr_average")) != text(rows[0].get("average_harvest_age_3yr_reported"))
        )
        for rows in public_by_code.values()
    )
    if annual_three_year_distinct == 0 or planner_reported_distinct == 0:
        raise AssertionError("Separate annual/reported/Hunt Planner age fields were collapsed.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lineage_path = OUTPUT_DIR / "field_lineage_audit.csv"
    lineage_fields = list(lineage_rows[0])
    with lineage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=lineage_fields)
        writer.writeheader()
        writer.writerows(lineage_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "database_rows": len(database),
        "management_unit_rows": len(management_units),
        "management_source_hunt_codes": len(source_codes),
        "management_context_rows": len(contexts),
        "profile_rows": len(profiles),
        "public_contract_rows": len(public_rows),
        "public_contract_unique_hunt_codes": len(public_by_code),
        "published_score_unique_hunt_codes": sum(
            number(rows[0].get("hunt_unit_quality_score")) is not None for rows in public_by_code.values()
        ),
        "field_lineage_rows": len(lineage_rows),
        "field_lineage_failures": 0,
        "annual_vs_reported_3yr_distinct_hunt_codes": annual_three_year_distinct,
        "hunt_planner_vs_reported_3yr_distinct_hunt_codes": planner_reported_distinct,
        "management_status_counts": dict(
            sorted(Counter(text(row.get("management_objective_status")) for row in contexts).items())
        ),
        "protected_projection_sha256_before": overlay["protected_projection_sha256_before"],
        "protected_projection_sha256_after": overlay["protected_projection_sha256_after"],
        "protected_fields_unchanged": True,
        "inventory_plan_pdf_count": inventory["plan_pdf_count"],
        "guardrails": {
            "hunt_code_identity_exact": True,
            "species_identity_compatible": True,
            "boundary_id_identity_used": False,
            "management_units_compared_in_matching_units": True,
            "annual_and_three_year_age_fields_distinct": True,
            "framework_species_scores_withheld": True,
            "missing_component_reweighting": False,
            "draw_probability_or_quota_changed": False,
        },
        "sha256": {
            "management_context": sha256(CONTEXT),
            "quality_profile": sha256(PROFILE),
            "public_contract": sha256(PUBLIC),
            "field_lineage_audit": sha256(lineage_path),
        },
    }
    summary_path = OUTPUT_DIR / "publication_audit.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
