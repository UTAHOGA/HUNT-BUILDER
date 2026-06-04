"""Feeder contract for production prediction engine inputs.

This file is intentionally declarative. It describes the files consumed by the
engine modules; it does not generate or repair official source data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


FileType = Literal["csv", "json", "pdf", "python", "javascript", "xlsx", "other"]


@dataclass(frozen=True)
class FeederContract:
    group: str
    path: str
    consumer_module: str
    required: bool = True
    production_blocker: bool = True
    file_type: FileType = "csv"
    alternatives: tuple[str, ...] = ()
    primary_key: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    critical_columns: tuple[str, ...] = ()
    numeric_columns: tuple[str, ...] = ()
    probability_columns: tuple[str, ...] = ()
    percent_columns: tuple[str, ...] = ()
    nonnegative_integer_columns: tuple[str, ...] = ()
    lineage_columns: tuple[str, ...] = ()
    generated: bool = False
    notes: str = ""


ROUTING_COLUMNS = ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type")
POINT_KEY = ("hunt_code", "residency", "points")
DRAW_HISTORY_KEY = ("hunt_code", "year", "residency", "points")
CURRENT_PERMIT_COLUMNS = ("permit_allotment_2026_res", "permit_allotment_2026_nr", "permit_allotment_2026_total")
DRAW_PROBABILITY_COLUMNS = ("p_draw", "p_draw_mean", "p_draw_p10", "p_draw_p50", "p_draw_p90", "p_random_mean", "p_max_pool_mean")
SOURCE_LINEAGE_COLUMNS = ("source_file",)
RUNTIME_LINEAGE_COLUMNS = ("truth_source_file", "truth_source_status")
QUOTA_LINEAGE_COLUMNS = ("quota_source_file", "quota_source_status", "quota_source_year")


ENGINE_FEEDERS: tuple[FeederContract, ...] = (
    # 1. engine.utah.rebuild fixture feeders.
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/applications_raw.csv", "engine.utah.rebuild", primary_key=("application_id",), required_columns=("application_id", "hunt_code"), critical_columns=("application_id", "hunt_code"), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/applicants_raw.csv", "engine.utah.rebuild", primary_key=("applicant_id",), required_columns=("applicant_id",), critical_columns=("applicant_id",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/groups_raw.csv", "engine.utah.rebuild", primary_key=("group_id",), required_columns=("group_id",), critical_columns=("group_id",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/points_raw.csv", "engine.utah.rebuild", primary_key=("applicant_id", "species"), required_columns=("applicant_id", "species", "points"), critical_columns=("applicant_id", "species"), nonnegative_integer_columns=("points",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/quotas_raw.csv", "engine.utah.rebuild", primary_key=("hunt_code", "residency"), required_columns=("hunt_code", "residency", "quota"), critical_columns=("hunt_code", "residency"), nonnegative_integer_columns=("quota",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/draw_results_raw.csv", "engine.utah.rebuild", primary_key=("hunt_code", "residency", "points"), required_columns=("hunt_code", "residency", "points"), critical_columns=("hunt_code", "residency"), nonnegative_integer_columns=("points",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/hunt_metadata_raw.csv", "engine.utah.rebuild", primary_key=("hunt_code",), required_columns=ROUTING_COLUMNS, critical_columns=("hunt_code", "hunt_name", "species"), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),
    FeederContract("utah_rebuild_fixtures", "data/utah/fixtures/harvest_quality_raw.csv", "engine.utah.rebuild", primary_key=("hunt_code",), required_columns=("hunt_code",), critical_columns=("hunt_code",), percent_columns=("success_percent",), notes="Synthetic fixture rebuild input; missing fixtures block fixture rebuild only."),

    # 2. engine.utah.materialize_engine processed feeders.
    FeederContract("utah_materialize_engine", "processed_data/draw_reality_engine.csv", "engine.utah.materialize_engine", primary_key=DRAW_HISTORY_KEY, required_columns=("hunt_code", "year", "residency", "points", "success_ratio"), critical_columns=("hunt_code", "year", "residency"), numeric_columns=("success_ratio",), percent_columns=("p_draw_percent",), lineage_columns=("source_file",), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/draw_reality_view.csv", "engine.utah.materialize_engine", primary_key=DRAW_HISTORY_KEY, required_columns=("hunt_code", "year", "residency", "points"), critical_columns=("hunt_code", "year", "residency"), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/point_ladder_view.csv", "engine.utah.materialize_engine", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points", "public_permits_2026"), critical_columns=("hunt_code", "residency"), probability_columns=("p_draw_mean", "p_random_mean", "p_max_pool_mean"), nonnegative_integer_columns=("points",), lineage_columns=RUNTIME_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_materialize_engine", "processed_data/historical_trend_2025.csv", "engine.utah.materialize_engine", primary_key=("hunt_code",), required_columns=("hunt_code",), critical_columns=("hunt_code",), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/projected_bonus_draw_2026_simulated.csv", "engine.utah.materialize_engine", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points"), critical_columns=("hunt_code", "residency"), probability_columns=("p_draw", "p_draw_mean"), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/recommended_permits_2026.csv", "engine.utah.materialize_engine", primary_key=("hunt_code",), required_columns=("hunt_code",), critical_columns=("hunt_code",), nonnegative_integer_columns=("permits_2026_res", "permits_2026_nr", "permits_2026_total"), lineage_columns=("source_file",), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/hunt_master_enriched.csv", "engine.utah.materialize_engine", primary_key=POINT_KEY, required_columns=ROUTING_COLUMNS + ("residency", "points"), critical_columns=("hunt_code", "residency"), lineage_columns=RUNTIME_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_materialize_engine", "processed_data/harvest-metrics-2024-bg-report.csv", "engine.utah.materialize_engine", primary_key=("hunt_code",), required_columns=("hunt_code",), critical_columns=("hunt_code",), percent_columns=("success_percent", "harvest_success_percent"), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/harvest-metrics-2025-prelim.csv", "engine.utah.materialize_engine", primary_key=("hunt_code",), required_columns=("hunt_code",), critical_columns=("hunt_code",), percent_columns=("success_percent", "harvest_success_percent"), generated=True),
    FeederContract("utah_materialize_engine", "processed_data/hunt-master-canonical.json", "engine.utah.materialize_engine", file_type="json", alternatives=("processed_data/hunt-master-canonical-2026-source-of-truth.json",), notes="Legacy name accepted when present; 2026 source-of-truth JSON is the current alternate."),

    # 3. engine.utah_bonus_predictive.materialize production feeders.
    FeederContract("utah_bonus_predictive", "data_truth/draw_results_truth/normalized/draw_results_long.csv", "engine.utah_bonus_predictive.materialize", primary_key=DRAW_HISTORY_KEY, required_columns=("hunt_code", "year", "residency", "points", "eligible_applicants", "total_permits", "success_ratio", "source_file"), critical_columns=("hunt_code", "year", "residency"), numeric_columns=("success_ratio",), percent_columns=("p_draw_percent",), lineage_columns=SOURCE_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_bonus_predictive", "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv", "engine.utah_bonus_predictive.materialize", primary_key=("hunt_code",), required_columns=ROUTING_COLUMNS + CURRENT_PERMIT_COLUMNS, critical_columns=("hunt_code", "hunt_name", "species"), nonnegative_integer_columns=CURRENT_PERMIT_COLUMNS, lineage_columns=("permit_allotment_2026_source_file", "permit_allotment_2026_status")),
    FeederContract("utah_bonus_predictive", "scripts/build_runtime_draw_feed_v2.py", "engine.utah_bonus_predictive.materialize", file_type="python", primary_key=(), required_columns=(), critical_columns=(), notes="Code dependency invoked upstream."),
    FeederContract("utah_bonus_predictive", "scripts/build_predictive_bonus_engine_v1.py", "engine.utah_bonus_predictive.materialize", file_type="python", primary_key=(), required_columns=(), critical_columns=(), notes="Code dependency invoked upstream."),
    FeederContract("utah_bonus_predictive", "hunt-research.js", "engine.utah_bonus_predictive.materialize", file_type="javascript", primary_key=(), required_columns=(), critical_columns=(), notes="Runtime publication contract dependency."),
    FeederContract("utah_bonus_predictive", "config.js", "engine.utah_bonus_predictive.materialize", file_type="javascript", primary_key=(), required_columns=(), critical_columns=(), notes="Runtime manifest/config dependency."),
    FeederContract("utah_bonus_predictive_skip_upstream", "data_model/runtime_drafts/predictive_bonus_engine_2026.predictions.csv", "engine.utah_bonus_predictive.materialize --skip-upstream", primary_key=POINT_KEY, required=False, production_blocker=False, required_columns=("hunt_code", "residency", "points", "p_draw_mean"), critical_columns=("hunt_code", "residency"), probability_columns=DRAW_PROBABILITY_COLUMNS, generated=True),
    FeederContract("utah_bonus_predictive_skip_upstream", "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv", "engine.utah_bonus_predictive.materialize --skip-upstream", primary_key=POINT_KEY, required=False, production_blocker=False, required_columns=("hunt_code", "residency", "points", "p_draw_mean"), critical_columns=("hunt_code", "residency"), probability_columns=DRAW_PROBABILITY_COLUMNS, lineage_columns=QUOTA_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_bonus_predictive_skip_upstream", "data_model/runtime_drafts/predictive_bonus_engine_2026.audit.csv", "engine.utah_bonus_predictive.materialize --skip-upstream", primary_key=("hunt_code", "residency"), required=False, production_blocker=False, required_columns=("hunt_code", "residency", "quota_source_status"), critical_columns=("hunt_code", "residency"), lineage_columns=("quota_source_file",), generated=True),

    # 4. engine.utah_draw_predictive feeders.
    FeederContract("utah_draw_predictive", "processed_data/draw_reality_engine_v2.csv", "engine.utah_draw_predictive.classifier", primary_key=DRAW_HISTORY_KEY, required_columns=("hunt_code", "year", "residency", "points", "eligible_applicants", "source_file"), critical_columns=("hunt_code", "year", "residency"), numeric_columns=("success_ratio",), lineage_columns=SOURCE_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_draw_predictive", "processed_data/draw_reality_engine_predictive_v2.csv", "engine.utah_draw_predictive.*", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points", "draw_system_type"), critical_columns=("hunt_code", "residency"), probability_columns=("p_draw", "p_sportsman_draw"), percent_columns=("p_draw_pct",), lineage_columns=QUOTA_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_draw_predictive", "processed_data/ml_draw_predictions_v1.csv", "engine.utah_draw_predictive.*", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points", "p_draw_mean"), critical_columns=("hunt_code", "residency"), probability_columns=DRAW_PROBABILITY_COLUMNS + ("p_draw",), percent_columns=("p_draw_pct",), lineage_columns=QUOTA_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_draw_predictive", "processed_data/draw_system_coverage_report.csv", "engine.utah_draw_predictive.*", primary_key=("hunt_code", "year", "residency", "draw_system_type"), required_columns=("hunt_code", "year", "draw_system_type", "algorithm_status"), critical_columns=("hunt_code", "year", "draw_system_type"), probability_columns=("p_draw", "p_bonus_pool", "p_random_pool"), percent_columns=("p_draw_pct",), generated=True),
    FeederContract("utah_draw_predictive", "processed_data/draw_system_coverage_report.json", "engine.utah_draw_predictive.*", file_type="json"),
    FeederContract("utah_draw_predictive", "processed_data/hunt_master_enriched.csv", "engine.utah_draw_predictive.*", primary_key=POINT_KEY, required_columns=ROUTING_COLUMNS + ("residency", "points"), critical_columns=("hunt_code", "residency"), lineage_columns=RUNTIME_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_draw_predictive", "processed_data/hunt_unit_reference_linked.csv", "engine.utah_draw_predictive.*", primary_key=("hunt_code", "residency"), required_columns=("hunt_code", "residency", "hunt_name", "species"), critical_columns=("hunt_code", "residency"), lineage_columns=RUNTIME_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_draw_predictive", "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv", "engine.utah_draw_predictive.*", primary_key=("hunt_code",), required_columns=ROUTING_COLUMNS + CURRENT_PERMIT_COLUMNS, critical_columns=("hunt_code", "hunt_name", "species"), nonnegative_integer_columns=CURRENT_PERMIT_COLUMNS, lineage_columns=("permit_allotment_2026_source_file", "permit_allotment_2026_status")),
    FeederContract("utah_draw_predictive", "data/utah/sportsman/sportsman_odds_2025.csv", "engine.utah_draw_predictive.sportsman", primary_key=("hunt_code",), required_columns=("year", "hunt_code", "species", "resident_quota", "resident_apps", "odds_text", "odds_denominator"), critical_columns=("year", "hunt_code", "species"), probability_columns=(), nonnegative_integer_columns=("resident_quota", "nonresident_quota", "total_quota", "resident_apps", "nonresident_apps", "total_apps", "odds_denominator"), lineage_columns=()),
    FeederContract("utah_draw_predictive", "data/cougar_hunt_table_official.json", "engine.utah_draw_predictive.mountain_lion", file_type="json"),
    FeederContract("utah_draw_predictive", "pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/black bear.csv", "engine.utah_draw_predictive.bear", primary_key=("hunt_code",), required_columns=("hunt_code", "hunt_name", "permits_2026_total"), critical_columns=("hunt_code", "hunt_name"), nonnegative_integer_columns=("permits_2026_res", "permits_2026_nr", "permits_2026_total")),
    FeederContract("utah_draw_predictive", "pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/elk antlerless private lands.csv", "engine.utah_draw_predictive.private_lands_antlerless_elk", primary_key=("hunt_code",), required_columns=("hunt_code", "hunt_name", "permits_2026_total"), critical_columns=("hunt_code", "hunt_name"), nonnegative_integer_columns=("permits_2026_total",)),
    FeederContract("utah_draw_predictive", "pipeline/RAW/hunt_unit_database/2026/csv/2026_elk_general_anybull_youth.csv", "engine.utah_draw_predictive.youth", primary_key=("hunt_code",), required_columns=("hunt_code", "hunt_name", "permits_2026_total"), critical_columns=("hunt_code", "hunt_name"), nonnegative_integer_columns=("permits_2026_res", "permits_2026_nr", "permits_2026_total")),

    # 5. Harvest and quality feeders.
    FeederContract("harvest_quality", "data_model/quality/raw_pdf_inventory_audit.csv", "engine.utah.quality.*", primary_key=("path",), required_columns=("path",), critical_columns=("path",), generated=True),
    FeederContract("harvest_quality", "data_model/quality/promoted_quality_sources.csv", "engine.utah.quality.*", primary_key=("path",), required_columns=("path",), critical_columns=("path",), generated=True),
    FeederContract("harvest_quality", "data_model/quality/promoted_draw_sources.csv", "engine.utah.quality.*", primary_key=("path",), required_columns=("path",), critical_columns=("path",), generated=True),
    FeederContract("harvest_quality", "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv", "engine.utah.quality.materialize_harvest_feature_model", primary_key=("reported_hunt_year", "hunt_code"), required_columns=("reported_hunt_year", "model_target_year", "hunt_code", "species", "source_file"), critical_columns=("reported_hunt_year", "hunt_code"), percent_columns=("percent_success",), lineage_columns=("source_file", "source_status"), generated=True),
    FeederContract("harvest_quality", "data_model/harvest_quality/harvest_results_all_years_long.csv", "engine.utah.quality.materialize_harvest_feature_model", primary_key=("reported_hunt_year", "hunt_code", "source_file"), required_columns=("reported_hunt_year", "model_target_year", "hunt_code", "source_file"), critical_columns=("reported_hunt_year", "hunt_code"), percent_columns=("percent_success",), lineage_columns=("source_file", "source_status"), generated=True),
    FeederContract("harvest_quality", "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv", "engine.utah.quality.materialize_harvest_feature_model", primary_key=("hunt_code",), required_columns=("hunt_code", "species", "harvest_quality_index"), critical_columns=("hunt_code",), numeric_columns=("harvest_quality_index",), lineage_columns=("harvest_feature_source_years", "harvest_feature_data_quality_grade"), generated=True),
    FeederContract("harvest_quality", "processed_data/harvest_results_database_final_audit.json", "engine.utah_predictive_mixed.materialize", file_type="json"),

    # 6. engine.utah_predictive_mixed.materialize feeders.
    FeederContract("utah_predictive_mixed", "processed_data/ml_draw_predictions_v1.csv", "engine.utah_predictive_mixed.materialize", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points", "p_draw_mean"), critical_columns=("hunt_code", "residency"), probability_columns=DRAW_PROBABILITY_COLUMNS + ("p_draw",), percent_columns=("p_draw_pct",), lineage_columns=QUOTA_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_predictive_mixed", "processed_data/draw_reality_engine_predictive_v2.csv", "engine.utah_predictive_mixed.materialize", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points", "draw_system_type"), critical_columns=("hunt_code", "residency"), probability_columns=("p_draw", "p_sportsman_draw"), percent_columns=("p_draw_pct",), lineage_columns=QUOTA_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_predictive_mixed", "processed_data/point_ladder_view.csv", "engine.utah_predictive_mixed.materialize", primary_key=POINT_KEY, required_columns=("hunt_code", "residency", "points"), critical_columns=("hunt_code", "residency"), probability_columns=("p_draw_mean", "p_random_mean", "p_max_pool_mean"), lineage_columns=RUNTIME_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_predictive_mixed", "processed_data/draw_reality_engine.csv", "engine.utah_predictive_mixed.materialize", primary_key=DRAW_HISTORY_KEY, required_columns=("hunt_code", "year", "residency", "points", "source_file"), critical_columns=("hunt_code", "year", "residency"), numeric_columns=("success_ratio",), lineage_columns=SOURCE_LINEAGE_COLUMNS, generated=True),
    FeederContract("utah_predictive_mixed", "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv", "engine.utah_predictive_mixed.materialize", primary_key=("hunt_code",), required_columns=("hunt_code", "harvest_quality_index"), critical_columns=("hunt_code",), numeric_columns=("harvest_quality_index",), lineage_columns=("harvest_feature_source_years", "harvest_feature_data_quality_grade"), generated=True),
    FeederContract("utah_predictive_mixed", "processed_data/harvest_results_database_final_audit.json", "engine.utah_predictive_mixed.materialize", file_type="json"),
)


def feeders_for_group(group: str | None = None) -> tuple[FeederContract, ...]:
    if not group:
        return ENGINE_FEEDERS
    return tuple(item for item in ENGINE_FEEDERS if item.group == group)


def groups() -> tuple[str, ...]:
    return tuple(sorted({item.group for item in ENGINE_FEEDERS}))
