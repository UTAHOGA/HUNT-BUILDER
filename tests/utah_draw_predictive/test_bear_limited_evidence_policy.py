"""Policy-only freeze; no model scoring, source rebuild or registry writes."""
import hashlib
import json
from pathlib import Path

import pytest

from engine.utah_draw_predictive.certification import (
    annotate_prediction_rows,
    load_registry,
)
from scripts.build_blind_acceptance_review import (
    FALSE_GUARANTEE_THRESHOLD,
    THRESHOLDS,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "governance/bear-restricted-pursuit-limited-evidence.v1.json"
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_policy_and_decision_are_hash_pinned_in_authority():
    authority = json.loads((ROOT / "governance/engine-authority.json").read_text(encoding="utf-8"))
    record = authority["restricted_pursuit_limited_evidence_policy"]
    assert record["policy_id"] == POLICY["policy_id"]
    assert record["policy_path"] == POLICY_PATH.relative_to(ROOT).as_posix()
    assert record["adr"] == POLICY["adr"]
    for path_key, hash_key in (("policy_path", "policy_sha256"), ("adr", "adr_sha256")):
        assert hashlib.sha256((ROOT / record[path_key]).read_bytes()).hexdigest() == record[hash_key]
    assert "Status: Accepted" in (ROOT / record["adr"]).read_text(encoding="utf-8")
    assert not record["public_probability_authorized"]
    assert not record["production_promotion_authorized"]


def test_original_certification_and_accuracy_thresholds_are_unchanged():
    assert THRESHOLDS == {
        "minimum_independent_following_year_folds": 2,
        "minimum_joined_rows_per_design": 400,
        "maximum_mae": 0.10,
        "maximum_p90_absolute_error": 0.30,
        "maximum_tail_error_rate_over_25pp": 0.10,
        "maximum_false_guarantee_rows": 0,
        "required_unclassified_actual_gaps": 0,
    }
    assert POLICY["ordinary_minimum_joined_rows_per_design"] == THRESHOLDS["minimum_joined_rows_per_design"]
    assert POLICY["minimum_independent_following_year_folds"] == THRESHOLDS["minimum_independent_following_year_folds"]
    assert all(THRESHOLDS[key] == value for key, value in POLICY["accuracy_limits"].items())
    assert POLICY["false_guarantee_probability_threshold"] == FALSE_GUARANTEE_THRESHOLD


def test_scope_and_coverage_do_not_mix_programs_or_erase_gaps():
    assert POLICY["eligible_designs"] == ["BEAR_RESTRICTED_PURSUIT_BONUS"]
    coverage = POLICY["coverage"]
    assert coverage["complete_eligible_actual_inventory_required"]
    assert coverage["every_missing_forecast_source_classified"]
    assert coverage["blank_forecasts_count_as_gaps"]
    assert coverage["unresolved_source_or_implementation_gaps_block"]
    assert not coverage["historical_database_reads_allowed"]
    assert not coverage["target_actuals_may_influence_forecasts"]
    assert not POLICY["scoring"]["numeric_errors_may_be_reclassified_as_gaps"]


def test_cluster_policy_keeps_related_rows_together():
    uncertainty = POLICY["uncertainty"]
    assert uncertainty["primary_cluster_key"] == ["target_draw_year", "verified_hunt_identity", "program_regime"]
    assert uncertainty["keep_all_point_rows_and_residencies_together"]
    assert not uncertainty["point_rows_are_independent_samples"]
    assert uncertainty["resampling_analyses"] == ["WHOLE_HUNT_YEAR_BLOCKS", "WHOLE_HUNT_REGIME_HISTORIES", "WHOLE_DRAW_YEARS"]
    assert uncertainty["replicates_per_analysis"] == 10000
    assert uncertainty["seed_reset_for_each_analysis"] == 20260920
    assert uncertainty["interval_quantiles"] == [0.025, 0.975]
    assert not uncertainty["confidence_bound_replaces_accuracy_gate"]
    assert uncertainty["implementation_tests_required_before_scoring"]
    assert POLICY["subgroups"]["accuracy_gates_required_for"] == ["POOLED_DESIGN", "Resident", "Nonresident"]


def test_provisional_requires_all_gates_and_unseen_confirmation():
    outcome = POLICY["provisional_outcome"]
    assert outcome["label"] == "Provisionally validated—limited evidence"
    assert outcome["requires_all_accuracy_and_safeguard_gates"]
    assert not outcome["is_certified"]
    assert not outcome["is_production_registry_status"]
    assert not outcome["granted_to_existing_candidate"]
    assert POLICY["freeze"]["timestamped_candidate_manifest_before_scoring"]
    assert POLICY["freeze"]["forecast_hashes_before_opening_target_actuals"]
    assert POLICY["confirmation"]["later_genuinely_unseen_draw_required"]
    assert not POLICY["confirmation"]["retuning_on_confirmation_result_preserves_unseen_status"]
    assert not POLICY["confirmation"]["automatic_certification_after_confirmation"]


def test_hypothetical_provisional_label_cannot_publish_probability():
    row = {
        "draw_system_type": "BEAR_DRAW",
        "bear_draw_subtype": "RESTRICTED_BEAR_PURSUIT",
        "p_draw": 0.5,
        "p_draw_mean": 0.5,
        "p_draw_pct": 50,
        "certified_p_draw": 0.9,
        "certified_p_draw_mean": 0.9,
        "certified_p_draw_pct": 90,
    }
    registry = {"families": {"BEAR_RESTRICTED_PURSUIT_BONUS": {
        "certification_status": POLICY["provisional_outcome"]["status"],
    }}}
    annotate_prediction_rows([row], registry)
    assert row["p_draw"] == 0.5
    assert all(row[key] == "" for key in ("certified_p_draw", "certified_p_draw_mean", "certified_p_draw_pct"))


def test_provisional_is_not_an_accepted_production_registry_status(tmp_path):
    path = tmp_path / "hypothetical_registry.json"
    path.write_text(json.dumps({
        "schema_version": "prediction-family-certification.v1",
        "families": {"BEAR_RESTRICTED_PURSUIT_BONUS": {
            "certification_status": POLICY["provisional_outcome"]["status"],
        }},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported certification status"):
        load_registry(path)
