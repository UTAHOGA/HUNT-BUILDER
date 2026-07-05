from tools.runtime_production_gate import (
    affected_families,
    count_columns,
    full_cert_required,
    is_runtime_file,
    percent_columns,
    probability_columns,
    should_audit_prediction_keys,
)


def test_runtime_file_detection_for_research_outputs():
    assert is_runtime_file("processed_data/hunt_research_2026_summary.json")
    assert is_runtime_file("processed_data/ml_draw_predictions_v1.csv")
    assert not is_runtime_file("processed_data/conservation_permit_hunt_code_lock_2026_runtime_updates.csv")
    assert not is_runtime_file("data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv")


def test_probability_column_detection_excludes_display_odds_fields():
    fields = [
        "p_draw",
        "probability_score",
        "display_odds_text",
        "sportsman_odds_denominator",
        "hunt_odds",
        "p_random_pool_pct",
        "p_bonus_pool_pct",
        "probability_applicant_count",
    ]
    assert probability_columns(fields) == ["p_draw", "probability_score"]
    assert percent_columns(fields) == ["hunt_odds", "p_random_pool_pct", "p_bonus_pool_pct"]


def test_count_column_detection_excludes_labels_and_guard_fields():
    fields = ["total_permits", "permit_category", "missing_permits", "do_not_use_for_permit_quota", "total_success_ratio", "permit_delta_2025_to_2026"]
    assert count_columns(fields) == ["total_permits"]


def test_prediction_key_audit_only_for_keyed_prediction_outputs():
    assert should_audit_prediction_keys("processed_data/ml_draw_predictions_v1.csv", ["year", "hunt_code", "residency", "points"])
    assert not should_audit_prediction_keys("processed_data/draw_system_coverage_report.csv", ["year", "hunt_code", "residency", "points"])
    assert not should_audit_prediction_keys("data_truth/draw_results_truth/normalized/draw_results_long.csv", ["year", "hunt_code", "residency", "points"])


def test_affected_family_detection_from_path_keywords():
    families = affected_families(["engine/utah_draw_predictive/preference_antlerless.py"])
    assert "PREFERENCE_DRAW" in families


def test_full_cert_required_for_engine_and_contract_changes():
    required, reasons = full_cert_required(["engine/utah_draw_predictive/classifier.py", "contracts/foo.yaml"])
    assert required
    assert reasons
