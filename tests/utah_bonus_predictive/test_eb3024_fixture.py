from engine.utah_bonus_predictive.cohort_forecast import (
    STRUCTURE_RETENTION_PRIORS,
    compute_unsuccessful,
    detect_cutoff_structure,
    infer_retention_rate,
    roll_forward_applicant_stack,
    smooth_retention_rate_with_evidence,
)
from engine.utah_bonus_predictive.monte_carlo import compute_bonus_pool_probability
from scripts.build_predictive_bonus_engine_v1 import conditional_applicant_demand, deterministic_pool_probabilities


def test_eb3024_2024_resident_bonus_pool() -> None:
    # 2024 resident fixture.
    applicants = {29: 1, 28: 9}
    p29, above29, _ = compute_bonus_pool_probability(29, applicants, max_point_permits=4)
    p28, above28, _ = compute_bonus_pool_probability(28, applicants, max_point_permits=4)
    assert above29 == 0
    assert p29 == 1.0
    assert above28 == 1
    assert round(p28, 6) == 0.333333
    assert compute_unsuccessful(9, 3, 0) == 6


def test_eb3024_2025_resident_bonus_pool_and_retention() -> None:
    applicants = {30: 1, 29: 5}
    p30, above30, _ = compute_bonus_pool_probability(30, applicants, max_point_permits=5)
    p29, above29, _ = compute_bonus_pool_probability(29, applicants, max_point_permits=5)
    assert above30 == 0
    assert p30 == 1.0
    assert above29 == 1
    assert round(p29, 6) == 0.8
    assert round(infer_retention_rate(6, 5), 6) == 0.833333


def test_eb3024_rolls_unsuccessful_2025_applicants_into_2026_stack() -> None:
    history = {
        2024: {
            28: {"eligible": 9, "bonus": 3, "regular": 0},
            29: {"eligible": 1, "bonus": 1, "regular": 0},
        },
        2025: {
            28: {"eligible": 21, "bonus": 0, "regular": 0},
            29: {"eligible": 5, "bonus": 4, "regular": 0},
            30: {"eligible": 1, "bonus": 1, "regular": 0},
        },
    }
    rollover = roll_forward_applicant_stack(history, 2025, retention_rate=1.0)
    assert rollover.applicants_by_points.get(31, 0) == 0
    assert rollover.applicants_by_points[30] == 2
    assert rollover.applicants_by_points[29] == 21


def test_eb3024_2026_mixed_cutoff_probability_after_rollover() -> None:
    applicants = {30: 2, 29: 21, 28: 12}
    p_draw, p_max, p_random, zones, cutoff = deterministic_pool_probabilities(
        points_desc=sorted(applicants, reverse=True),
        demand_by_point=applicants,
        reserved_quota=5,
        random_quota=4,
    )
    assert cutoff == 29.0
    assert p_max[30] == 1.0
    assert zones[30] == "max_pool_guaranteed"
    assert round(p_max[29], 6) == round(3 / 21, 6)
    assert zones[29] == "max_pool_cutoff_mixed"
    assert zones[28] == "random_pool"
    assert p_draw[29] == p_max[29] + ((1 - p_max[29]) * p_random[29])


def test_zero_forecast_rung_is_modeled_for_one_real_applicant() -> None:
    # A visitor at 30 points remains an applicant even when the roll-forward
    # stack forecasts no one at that exact rung.  The prior 29-point group is
    # fully awarded from the ten max-point permits, so the 30-point applicant
    # must be evaluated as guaranteed rather than as a zero-probability blank.
    forecast = {29: 7, 28: 77, 27: 90}
    conditioned = conditional_applicant_demand(forecast, 30)
    p_draw, p_max, p_random, zones, cutoff = deterministic_pool_probabilities(
        points_desc=[30, 29, 28, 27],
        demand_by_point=conditioned,
        reserved_quota=10,
        random_quota=9,
    )

    assert forecast.get(30, 0) == 0
    assert conditioned[30] == 1
    assert p_max[30] == 1.0
    assert p_random[30] == 0.0
    assert p_draw[30] == 1.0
    assert zones[30] == "max_pool_guaranteed"
    assert cutoff == 28.0


def test_detect_cutoff_structure_marks_guaranteed_stack_above_mixed_cutoff() -> None:
    point_map = {
        30: {"eligible": 1, "bonus": 1, "regular": 0},
        29: {"eligible": 5, "bonus": 4, "regular": 0},
        28: {"eligible": 21, "bonus": 0, "regular": 0},
    }
    structure = detect_cutoff_structure(point_map)
    assert structure.structure == "HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF"
    assert structure.top_point == 30
    assert structure.mixed_cutoff_point == 29
    assert structure.mixed_cutoff_unsuccessful == 1
    assert structure.guaranteed_stack_points == (30,)


def test_roll_forward_uses_structure_calibrated_retention_when_available() -> None:
    history = {
        2023: {
            30: {"eligible": 2, "bonus": 2, "regular": 0},
            29: {"eligible": 100, "bonus": 40, "regular": 0},
            28: {"eligible": 60, "bonus": 0, "regular": 0},
        },
        2024: {
            31: {"eligible": 2, "bonus": 2, "regular": 0},
            30: {"eligible": 50, "bonus": 40, "regular": 0},
            29: {"eligible": 80, "bonus": 0, "regular": 0},
        },
    }
    rollover = roll_forward_applicant_stack(history, 2024)
    expected = smooth_retention_rate_with_evidence(
        50 / 60,
        prior=STRUCTURE_RETENTION_PRIORS["HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF"],
        evidence_total=60,
    )

    assert rollover.rollover_rule == "MIXED_CUTOFF_STRUCTURE_CALIBRATED"
    assert rollover.cutoff_structure == "HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF"
    assert rollover.mixed_cutoff_point == 30
    assert rollover.anchor_next_point == 31
    assert round(rollover.structure_retention_rate_raw or 0.0, 6) == round(50 / 60, 6)
    assert round(rollover.structure_retention_rate_smoothed or 0.0, 6) == round(expected, 6)
    assert round(rollover.retention_rate_smoothed, 6) == round(expected, 6)

