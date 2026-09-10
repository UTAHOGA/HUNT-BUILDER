from __future__ import annotations

from engine.utah_predictive_mixed.rollover import rollover_applicant_stack, rollover_probability_from_pools
from engine.utah_predictive_mixed.materialize import mixed_row
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
