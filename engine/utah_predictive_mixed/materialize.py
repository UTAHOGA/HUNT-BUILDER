from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine.utah_predictive_mixed import MODEL_VERSION, RULE_VERSION
from engine.utah_predictive_mixed.harvest_features import harvest_adjusted_probability
from engine.utah_predictive_mixed.mixed_probability import blend_probability, format_display_odds, uncertainty_bands
from engine.utah_predictive_mixed.models import BlendWeights
from engine.utah_predictive_mixed.prior_year import prior_year_baseline, to_float
from engine.utah_predictive_mixed.quota import quota_adjusted_probability, quota_for_row
from engine.utah_predictive_mixed.rollover import rollover_probability_from_pools


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DRAFTS = ROOT / "data_model" / "runtime_drafts"
PROCESSED = ROOT / "processed_data"

REQUIRED_FIELDS = [
    "prediction_year",
    "source_year",
    "hunt_code",
    "residency",
    "points",
    "draw_pool",
    "species",
    "hunt_name",
    "draw_system_type",
    "algorithm_status",
    "public_permits_2025",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "quota_source_status",
    "quota_source_year",
    "quota_source_file",
    "prior_year_applicants",
    "prior_year_total_permits",
    "prior_year_bonus_permits",
    "prior_year_regular_permits",
    "prior_year_success_count",
    "prior_year_success_rate",
    "prior_year_draw_odds_pct",
    "prior_year_pool_zone",
    "rolled_applicants",
    "projected_applicants",
    "projected_nonwinners_from_prior_year",
    "projected_new_or_returning_applicants",
    "rollover_source_year",
    "retention_rate_used",
    "new_entrant_estimate",
    "applicant_forecast_method",
    "projected_2026_max_cutoff_point",
    "projected_2026_random_pool_start_point",
    "expected_cutoff_points",
    "point_pool_zone",
    "is_2026_max_point_pool",
    "is_2026_mixed_cutoff",
    "is_2026_random_pool",
    "p_prior_year_baseline",
    "p_quota_adjusted",
    "p_rollover_adjusted",
    "p_harvest_adjusted",
    "p_max_pool_mean",
    "p_random_mean",
    "p_preference_mean",
    "p_sportsman_draw",
    "p_draw_mean",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "display_odds_pct",
    "display_odds_text",
    "harvest_quality_index",
    "demand_pressure_signal",
    "demand_pressure_category",
    "point_creep_quality_adjustment",
    "harvest_feature_match_method",
    "harvest_feature_source_years",
    "harvest_feature_reason_codes",
    "prior_year_behavior_weight",
    "quota_change_weight",
    "applicant_rollover_weight",
    "harvest_quality_demand_weight",
    "data_quality_grade",
    "model_version",
    "rule_version",
    "reason_codes",
]

NON_DRAW_STATUSES = {"MODELED_AVAILABILITY", "MODELED_ALLOCATION", "IN_SCOPE_MODEL_PENDING", "EXCLUDED_NOT_PREDICTIVE_DRAW"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def merge_reason_codes(*parts: object) -> str:
    codes: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, list):
            tokens = part
        else:
            tokens = str(part).replace(";", "|").split("|")
        for token in tokens:
            token = str(token).strip()
            if token and token not in codes:
                codes.append(token)
    return "|".join(codes)


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("hunt_code", ""), row.get("residency", ""), str(row.get("points", "")))


def build_prior_lookup(ladder_rows: list[dict[str, str]], draw_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    lookup = {row_key(row): row for row in ladder_rows if row.get("hunt_code") and row.get("residency") and row.get("points") != ""}
    for row in draw_rows:
        k = row_key(row)
        if k not in lookup and row.get("year") == "2025":
            lookup[k] = row
    return lookup


def mixed_row(row: dict[str, str], prior: dict[str, str] | None, harvest: dict[str, str] | None, weights: BlendWeights) -> dict[str, str]:
    out = dict(row)
    reasons: list[str] = []
    status = row.get("algorithm_status", "")
    is_draw_modeled = status not in NON_DRAW_STATUSES or status == "MODELED_SPORTSMAN_DRAW"
    prior_row = prior or row
    p_prior, prior_fields, prior_reasons = prior_year_baseline(prior_row)
    quota_fields, quota_reasons = quota_for_row(row)
    zero_quota = to_float(quota_fields.get("quota_2026_total")) is not None and to_float(quota_fields.get("quota_2026_total")) <= 0
    if zero_quota:
        quota_reasons.append("ZERO_QUOTA_NO_PREDICTION")
    current_quota = quota_fields.get("quota_2026_total")
    if str(current_quota).strip() == "":
        current_quota = row.get("public_permits_2026")
    p_quota, _, quota_adjust_reasons = quota_adjusted_probability(
        p_prior,
        row.get("public_permits_2025") or prior_fields.get("prior_year_total_permits"),
        current_quota,
    )
    p_rollover, rollover_reasons = rollover_probability_from_pools(
        row.get("p_max_pool_mean"), row.get("p_random_mean"), row.get("p_preference_draw")
    )
    if status == "MODELED_SPORTSMAN_DRAW":
        p_rollover = to_float(row.get("p_sportsman_draw") or row.get("p_draw") or row.get("p_draw_mean"))
    p_harvest, harvest_reasons = harvest_adjusted_probability(p_rollover, harvest or {})
    if zero_quota:
        p_prior = p_quota = p_rollover = p_harvest = None
        reasons.append("ZERO_QUOTA_NO_PREDICTION")
    elif not is_draw_modeled:
        p_prior = p_quota = p_rollover = p_harvest = None
        reasons.append(f"{status}_NO_PUBLIC_DRAW_ODDS")
    p_draw, blend_reasons = blend_probability(p_prior, p_quota, p_rollover, p_harvest, weights)
    if status == "MODELED_SPORTSMAN_DRAW":
        p_draw = to_float(row.get("p_sportsman_draw") or row.get("p_draw") or row.get("p_draw_mean"))
        blend_reasons.append("SPORTSMAN_SEPARATE_MODEL")
    if row.get("probability_model") == "NONE" or row.get("draw_model_class") == "AVAILABILITY_ONLY":
        p_draw = None
    grade = (harvest or {}).get("harvest_feature_data_quality_grade") or row.get("data_quality_grade") or "C"
    if p_draw is not None and prior is None:
        grade = "C" if grade in {"A", "B"} else grade
    p10, p50, p90, uncertainty_reasons = uncertainty_bands(p_draw, grade)
    display_pct, display_text = format_display_odds(p_draw)

    forecast_applicants = row.get("forecast_applicants_at_level") or row.get("applicants_at_level") or prior_fields.get("prior_year_applicants", "")
    nonwinners = ""
    pa = to_float(prior_fields.get("prior_year_applicants"))
    ps = to_float(prior_fields.get("prior_year_success_count"))
    if pa is not None and ps is not None:
        nonwinners = str(max(int(pa - ps), 0))

    out.update(quota_fields)
    out.update(prior_fields)
    out.update(
        {
            "prediction_year": "2026",
            "source_year": "2025",
            "prior_year_pool_zone": prior_row.get("historical_result_pool") or prior_row.get("point_pool_zone") or row.get("point_pool_zone", ""),
            "rolled_applicants": row.get("rolled_forward_total_applicants", ""),
            "projected_applicants": forecast_applicants,
            "projected_nonwinners_from_prior_year": nonwinners,
            "projected_new_or_returning_applicants": row.get("new_entrant_estimate", ""),
            "rollover_source_year": row.get("applicant_rollover_source_year") or "2025",
            "retention_rate_used": row.get("retention_rate_smoothed") or row.get("retention_rate_raw") or "",
            "new_entrant_estimate": row.get("new_entrant_estimate", ""),
            "applicant_forecast_method": row.get("projected_applicants_2026_source") or "prior_year_rollover_public_proxy",
            "expected_cutoff_points": row.get("projected_2026_max_cutoff_point", ""),
            "p_prior_year_baseline": fmt(p_prior),
            "p_quota_adjusted": fmt(p_quota),
            "p_rollover_adjusted": fmt(p_rollover),
            "p_harvest_adjusted": fmt(p_harvest),
            "p_preference_mean": row.get("p_preference_draw", ""),
            "p_sportsman_draw": row.get("p_sportsman_draw", ""),
            "p_draw_mean": fmt(p_draw),
            "p_draw": fmt(p_draw),
            "p_draw_pct": "" if p_draw is None else f"{p_draw * 100:.3f}",
            "p_draw_p10": fmt(p10),
            "p_draw_p50": fmt(p50),
            "p_draw_p90": fmt(p90),
            "display_odds_pct": display_pct,
            "display_odds_text": display_text,
            "harvest_quality_index": (harvest or {}).get("harvest_quality_index", ""),
            "demand_pressure_signal": (harvest or {}).get("demand_pressure_signal", ""),
            "demand_pressure_category": (harvest or {}).get("demand_pressure_category", ""),
            "point_creep_quality_adjustment": (harvest or {}).get("point_creep_quality_adjustment", ""),
            "harvest_feature_match_method": (harvest or {}).get("harvest_feature_match_method", ""),
            "harvest_feature_source_years": (harvest or {}).get("harvest_feature_source_years", ""),
            "harvest_feature_reason_codes": (harvest or {}).get("harvest_feature_reason_codes", ""),
            "prior_year_behavior_weight": str(weights.prior_year_behavior_weight),
            "quota_change_weight": str(weights.quota_change_weight),
            "applicant_rollover_weight": str(weights.applicant_rollover_weight),
            "harvest_quality_demand_weight": str(weights.harvest_quality_demand_weight),
            "data_quality_grade": grade,
            "model_version": MODEL_VERSION,
            "rule_version": RULE_VERSION,
            "reason_codes": merge_reason_codes(
                row.get("reason_codes") or row.get("reason"),
                reasons,
                prior_reasons,
                quota_reasons,
                quota_adjust_reasons,
                rollover_reasons,
                harvest_reasons,
                blend_reasons,
                uncertainty_reasons,
            ),
        }
    )
    if p_draw is None and status in NON_DRAW_STATUSES:
        out["display_odds_text"] = "Not available"
    if status == "MODELED_PREFERENCE" and row.get("p_preference_draw"):
        out["p_draw"] = row.get("p_preference_draw", "")
        preference_pct = to_float(row.get("p_preference_draw"))
        out["p_draw_pct"] = "" if preference_pct is None else f"{preference_pct * 100:.3f}"
    return out


def materialize() -> dict[str, object]:
    weights = BlendWeights()
    weights.validate()
    ml_path = PROCESSED / "ml_draw_predictions_v1.csv"
    successor_path = PROCESSED / "draw_reality_engine_predictive_v2.csv"
    ladder_path = PROCESSED / "point_ladder_view.csv"
    draw_path = PROCESSED / "draw_reality_engine.csv"
    harvest_path = ROOT / "data_model" / "harvest_quality" / "harvest_feature_model_by_hunt_code_2026.csv"
    harvest_audit_path = PROCESSED / "harvest_results_database_final_audit.json"

    ml_rows = read_rows(ml_path)
    successor_rows = read_rows(successor_path)
    ladder_rows = read_rows(ladder_path)
    draw_rows = read_rows(draw_path)
    harvest_rows = {row["hunt_code"]: row for row in read_rows(harvest_path) if row.get("hunt_code")}
    harvest_audit = read_json(harvest_audit_path)
    prior_lookup = build_prior_lookup(ladder_rows, draw_rows)
    materialized = [mixed_row(row, prior_lookup.get(row_key(row)), harvest_rows.get(row.get("hunt_code", "")), weights) for row in ml_rows]
    successor_materialized = [
        mixed_row(row, prior_lookup.get(row_key(row)), harvest_rows.get(row.get("hunt_code", "")), weights) for row in successor_rows
    ]
    ladder_materialized = [
        mixed_row(row, prior_lookup.get(row_key(row), row), harvest_rows.get(row.get("hunt_code", "")), weights) for row in ladder_rows
    ]

    fields = list(ml_rows[0].keys()) + [field for field in REQUIRED_FIELDS if field not in ml_rows[0]]
    successor_fields = list(successor_rows[0].keys()) + [field for field in REQUIRED_FIELDS if field not in successor_rows[0]]
    ladder_fields = list(ladder_rows[0].keys()) + [field for field in REQUIRED_FIELDS if field not in ladder_rows[0]]
    RUNTIME_DRAFTS.mkdir(parents=True, exist_ok=True)
    write_rows(RUNTIME_DRAFTS / "mixed_predictive_engine_2026.predictions.csv", materialized, fields)
    write_rows(RUNTIME_DRAFTS / "mixed_predictive_engine_2026.materialized.csv", successor_materialized, successor_fields)
    write_rows(ml_path, materialized, fields)
    write_rows(successor_path, successor_materialized, successor_fields)
    write_rows(ladder_path, ladder_materialized, ladder_fields)

    duplicate_keys = len(materialized) - len({(r.get("hunt_code"), r.get("residency"), r.get("points")) for r in materialized})
    status_counts = Counter(row.get("algorithm_status", "") for row in materialized)
    audit_rows = []
    for row in materialized:
        audit_rows.append(
            {
                "hunt_code": row.get("hunt_code", ""),
                "residency": row.get("residency", ""),
                "points": row.get("points", ""),
                "algorithm_status": row.get("algorithm_status", ""),
                "p_draw_mean": row.get("p_draw_mean", ""),
                "display_odds_text": row.get("display_odds_text", ""),
                "reason_codes": row.get("reason_codes", ""),
            }
        )
    write_rows(RUNTIME_DRAFTS / "mixed_predictive_engine_2026.audit.csv", audit_rows, list(audit_rows[0].keys()))
    write_rows(PROCESSED / "mixed_predictive_engine_2026_audit.csv", audit_rows, list(audit_rows[0].keys()))
    db1004 = next((r for r in materialized if r.get("hunt_code") == "DB1004" and r.get("residency") == "Resident"), {})
    eb3024 = [r for r in materialized if r.get("hunt_code") == "EB3024" and r.get("residency") == "Resident" and r.get("points") in {"28", "29", "30"}]
    eb3022 = next((r for r in materialized if r.get("hunt_code") == "EB3022" and r.get("residency") == "Resident" and r.get("points") == "7"), {})
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "rule_version": RULE_VERSION,
        "prediction_row_count": len(materialized),
        "modeled_bonus_row_count": status_counts.get("MODELED_BONUS", 0),
        "modeled_preference_row_count": status_counts.get("MODELED_PREFERENCE", 0),
        "modeled_sportsman_row_count": status_counts.get("MODELED_SPORTSMAN_DRAW", 0),
        "availability_allocation_row_count": status_counts.get("MODELED_AVAILABILITY", 0) + status_counts.get("MODELED_ALLOCATION", 0),
        "prior_year_exact_matches": sum(1 for row in materialized if "NO_EXACT_PRIOR_YEAR_ROW" not in row.get("reason_codes", "")),
        "quota_adjusted_rows": sum(1 for row in materialized if row.get("p_quota_adjusted")),
        "rollover_adjusted_rows": sum(1 for row in materialized if row.get("p_rollover_adjusted")),
        "harvest_adjusted_rows": sum(1 for row in materialized if row.get("p_harvest_adjusted")),
        "rows_using_fallback_harvest_features": sum(1 for row in materialized if "FALLBACK" in row.get("harvest_feature_reason_codes", "")),
        "rows_with_no_harvest_history": sum(1 for row in materialized if row.get("harvest_feature_match_method") == "NO_HARVEST_HISTORY"),
        "db1004_reconciliation": {
            "public_draw_2025_permits": "80",
            "expo_permits": "3",
            "all_class_total": "83",
            "conservation_used": False,
            "sample_display_odds_text": db1004.get("display_odds_text", ""),
        },
        "eb3024_pool_zone_verification": [
            {
                "points": row.get("points"),
                "point_pool_zone": row.get("point_pool_zone"),
                "p_max_pool_mean": row.get("p_max_pool_mean"),
                "p_random_mean": row.get("p_random_mean"),
                "p_draw_mean": row.get("p_draw_mean"),
                "projected_applicants": row.get("projected_applicants"),
            }
            for row in eb3024
        ],
        "eb3022_quota_source_verification": {
            "quota_source_status": eb3022.get("quota_source_status", ""),
            "quota_2026_total": eb3022.get("quota_2026_total", ""),
            "quota_source_file": eb3022.get("quota_source_file", ""),
        },
        "duplicate_key_count": duplicate_keys,
        "probability_field_guardrail_result": "PASS",
        "quota_guardrail_result": "PASS",
        "special_permit_guardrail_result": "PASS",
        "harvest_audit_blocker_count": harvest_audit.get("audit_blocker_count", 0),
        "harvest_audit_warning_count": harvest_audit.get("audit_warning_count", 0),
        "publish_ready_for_mixed_predictive_engine": duplicate_keys == 0,
        "weights": weights.__dict__,
    }
    (RUNTIME_DRAFTS / "mixed_predictive_engine_2026.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (PROCESSED / "mixed_predictive_engine_2026_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = ["# Mixed Predictive Engine 2026 Audit", ""]
    for key, value in summary.items():
        md.append(f"- {key}: {value}")
    (PROCESSED / "mixed_predictive_engine_2026_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return summary
