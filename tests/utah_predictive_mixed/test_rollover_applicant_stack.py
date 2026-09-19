from __future__ import annotations

from engine.utah_predictive_mixed.rollover import rollover_applicant_stack, rollover_probability_from_pools
from engine.utah_predictive_mixed.materialize import apply_database_permit_authority, mixed_row
from engine.utah_predictive_mixed.models import BlendWeights


def test_rollover_advances_unsuccessful_applicants_one_point() -> None:
    stack = rollover_applicant_stack([
        {"points": "28", "eligible_applicants": "10", "total_permits": "3"},
        {"points": "0", "eligible_applicants": "20", "total_permits": "0"},
    ])
    assert stack[29]["nonwinners"] == 7
    assert stack[29]["rolled"] > 0
    assert stack[0]["new_entrants"] == 2


def test_mixed_pool_formula_combines_max_and_random() -> None:
    p, reasons = rollover_probability_from_pools("0.30", "0.10")
    assert abs((p or 0) - 0.37) < 1e-9
    assert "ROLLOVER_ADJUSTED_PROBABILITY_USED" in reasons


def test_prior_random_winner_does_not_raise_current_family_forecast() -> None:
    row = {
        "hunt_code": "DB1001",
        "residency": "Resident",
        "points": "5",
        "algorithm_status": "MODELED_BONUS",
        "p_draw": "0.10",
        "p_draw_mean": "0.10",
        "p_max_pool_mean": "0",
        "p_random_mean": "0.10",
        "public_permits_2025": "10",
        "public_permits_2026": "10",
    }
    prior = {
        "hunt_code": "DB1001",
        "residency": "Resident",
        "points": "4",
        "eligible_applicants": "100",
        "bonus_permits": "0",
        "regular_permits": "1",
        "total_permits": "1",
        "success_ratio": "1 in 100",
    }

    result = mixed_row(row, prior, None, BlendWeights())

    assert result["prior_year_regular_permits"] == "1"
    assert result["p_prior_year_baseline"] == ""
    assert result["p_quota_adjusted"] == ""
    assert result["p_rollover_adjusted"] == "0.100000"
    assert result["p_draw"] == "0.100000"
    assert "PRIOR_RANDOM_WINNER_BASELINE_WITHHELD_FROM_CURRENT_FORECAST" in result["reason_codes"]


def test_post_mix_certification_uses_corrected_probability() -> None:
    from engine.utah_draw_predictive.certification import annotate_prediction_rows

    row = {
        "hunt_code": "DB1001",
        "residency": "Resident",
        "points": "5",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "algorithm_status": "MODELED_BONUS",
        "p_draw": "0.10",
        "p_draw_mean": "0.10",
        "p_max_pool_mean": "0",
        "p_random_mean": "0.10",
        "public_permits_2025": "10",
        "public_permits_2026": "10",
        "certified_p_draw": "0.80",
        "certified_p_draw_mean": "0.80",
        "certified_p_draw_pct": "80",
    }
    prior = {
        "hunt_code": "DB1001",
        "residency": "Resident",
        "points": "4",
        "eligible_applicants": "100",
        "bonus_permits": "0",
        "regular_permits": "1",
        "total_permits": "1",
        "success_ratio": "1 in 100",
    }
    registry = {
        "registry_id": "test-registry",
        "evidence": {"acceptance_by_draw_design": "test.csv"},
        "families": {
            "BONUS_LE_BIG_GAME": {
                "certification_status": "CERTIFIED",
                "failure_reasons": "",
            }
        },
    }

    result = mixed_row(row, prior, None, BlendWeights())
    annotate_prediction_rows([result], registry)

    assert result["p_draw"] == "0.100000"
    assert result["certified_p_draw"] == "0.100000"
    assert result["certified_p_draw_mean"] == "0.100000"


def test_current_database_context_does_not_erase_resolved_certification_family() -> None:
    rows = [
        {
            "hunt_code": "EB3022",
            "residency": "Resident",
            "draw_system_type": "BONUS_LE_BIG_GAME",
        }
    ]
    authority = {
        "EB3022": {
            "current_target_draw_system_type": "MAX_WEIGHTED_SPLIT",
            "permits_2026_res": "100",
            "permits_2026_nr": "10",
            "permits_2026_total": "110",
            "permits_2026_source": "DATABASE.csv",
        }
    }

    apply_database_permit_authority(rows, authority)

    assert rows[0]["draw_system_type"] == "BONUS_LE_BIG_GAME"
    assert rows[0]["current_target_draw_system_type"] == "MAX_WEIGHTED_SPLIT"
    assert rows[0]["public_permits_2026"] == "100"


def test_preference_success_is_not_misclassified_as_a_random_winner() -> None:
    row = {
        "hunt_code": "DB1501",
        "residency": "Resident",
        "points": "5",
        "algorithm_status": "MODELED_PREFERENCE",
        "p_preference_draw": "0.10",
        "p_draw": "0.10",
        "p_draw_mean": "0.10",
        "public_permits_2025": "10",
        "public_permits_2026": "10",
    }
    prior = {
        "hunt_code": "DB1501",
        "residency": "Resident",
        "points": "4",
        "eligible_applicants": "100",
        "bonus_permits": "0",
        "regular_permits": "1",
        "total_permits": "1",
        "success_ratio": "1 in 100",
    }

    result = mixed_row(row, prior, None, BlendWeights())

    assert result["p_prior_year_baseline"] == "0.010000"
    assert result["p_quota_adjusted"] == "0.010000"
    assert "PRIOR_RANDOM_WINNER_BASELINE_WITHHELD_FROM_CURRENT_FORECAST" not in result["reason_codes"]
