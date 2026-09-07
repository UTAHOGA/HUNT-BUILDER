from __future__ import annotations

import pytest

from engine.utah_draw_predictive.bear import (
    _bear_simulation_probability,
    _build_lane_cohort_model,
    _build_source_calibrated_returning_tail_profiles,
    _build_truth_ladders,
    _condition_for_focal_bear_applicant,
    _forecast_recent_cumulative_stack_ladder,
    _forecast_lane_cohort_ladder,
    _point_purchase_counts_by_year_residency,
    _split_bear_bonus_permits,
    _sample_observed_arrival_count,
    _sample_lane_cohort_forecast_ladders,
    _sample_recent_cumulative_stack_ladders,
    _sample_bear_forecast_ladders,
    _weighted_random_probability,
)


def test_bear_random_pool_probability_is_for_one_applicant() -> None:
    probability = _weighted_random_probability(
        points=2,
        applicants_by_points={2: 2, 0: 1},
        random_permits=1,
    )

    assert probability == pytest.approx(3 / 7)


def test_bear_random_pool_excludes_max_pool_winners() -> None:
    probability = _weighted_random_probability(
        points=1,
        applicants_by_points={2: 1, 1: 2, 0: 1},
        random_permits=1,
        max_point_permits=2,
    )

    # Point 2 and one point-1 applicant receive the max-pool permits.  The
    # selected point-1 nonwinner has two tickets in a three-ticket random pool.
    assert probability == pytest.approx(2 / 3)


def test_bear_simulation_mean_does_not_reuse_deterministic_guarantee() -> None:
    sampled_ladders = [
        {5: 0, 4: 1},
        {5: 2, 4: 1},
    ]

    p_bonus, p_random, p_draw, p10, p50, p90 = _bear_simulation_probability(
        points=4,
        sampled_ladders=sampled_ladders,
        max_point_permits=1,
        random_permits=1,
    )

    assert 0.0 < p_bonus < 1.0
    assert 0.0 < p_random < 1.0
    assert 0.0 < p_draw < 1.0
    assert p10 <= p50 <= p90


def test_bear_truth_ladder_uses_actual_draw_year_when_legacy_year_is_none() -> None:
    """Canonical legacy placeholders must not erase dated official history."""

    rows = [
        {
            "year": "None",
            "actual_draw_year": "2018",
            "hunt_code": "BR7004",
            "points": "9",
            "eligible_applicants": "7",
            "bonus_permits": "0",
            "regular_permits": "0",
            "total_permits": "0",
            "resident_eligible_applicants": "7",
            "resident_bonus_permits": "0",
            "resident_regular_permits": "0",
            "resident_total_permits": "0",
            "draw_system_type": "BEAR_DRAW",
            "bear_source_classification": "TRUE_BEAR_BONUS_DRAW",
            "source_file": "official_dwr_archive/black_bear/18_drawing_odds.pdf",
        },
        {
            "year": "None",
            "actual_draw_year": "2019",
            "hunt_code": "BR7004",
            "points": "10",
            "eligible_applicants": "3",
            "bonus_permits": "3",
            "regular_permits": "0",
            "total_permits": "3",
            "resident_eligible_applicants": "3",
            "resident_bonus_permits": "3",
            "resident_regular_permits": "0",
            "resident_total_permits": "3",
            "draw_system_type": "BEAR_DRAW",
            "bear_source_classification": "TRUE_BEAR_BONUS_DRAW",
            "source_file": "official_dwr_archive/black_bear/19_drawing_odds.pdf",
        },
    ]

    ladders, _, _ = _build_truth_ladders(rows, {2018, 2019})

    assert any(key[1:3] == (2018, "BR7004") for key in ladders)
    assert any(key[1:3] == (2019, "BR7004") for key in ladders)


def test_returning_tail_profile_requires_both_historical_hunt_arrival_and_statewide_pool() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9999", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            9: {"eligible": 2, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    purchases = _point_purchase_counts_by_year_residency(
        [
            {
                "draw_year": "2018",
                "residency": "Resident",
                "points": "9",
                "point_purchase_applicants": "81",
            }
        ],
        {2018, 2019},
    )

    profiles = _build_source_calibrated_returning_tail_profiles(ladders, purchases)

    assert profiles[key] == ({9: 2},)
    assert _build_source_calibrated_returning_tail_profiles(ladders, {}) == {}


def test_returning_tail_mixture_is_sampled_not_allocated_as_a_deterministic_hunt_population() -> None:
    samples = _sample_bear_forecast_ladders(
        latest_ladder={8: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0}},
        retention_history_by_band={"6_9": (1.0,)},
        zero_growth_history=(1.0,),
        iterations=30,
        seed="returning-tail-mixture",
        returning_tail_profiles=({9: 2},),
    )

    point_nine_counts = {sample.get(9, 0) for sample in samples}
    assert point_nine_counts == {0, 2}


def test_lane_cohort_model_uses_same_lane_rung_reapplication_and_separate_arrivals() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9999", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            # Four people could have come from the prior unsuccessful cohort;
            # the other three are a measured arrival, not 175% retention.
            9: {"eligible": 7, "bonus": 0, "regular": 0, "total": 0},
        },
    }

    model = _build_lane_cohort_model(ladders)
    forecast, calibrations = _forecast_lane_cohort_ladder(
        ladders[(key[0], 2018, key[1], key[2])],
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )

    calibration = calibrations[9]
    assert calibration.reapply_rate <= 1.0
    assert calibration.arrival_count > 0.0
    assert forecast[9] > 4


def test_recent_cumulative_stack_forecast_uses_only_same_lane_demand_trends() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9993", "Resident")
    ladders = {
        (key[0], 2017, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
            9: {"eligible": 8, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
            9: {"eligible": 10, "bonus": 0, "regular": 0, "total": 0},
            10: {"eligible": 10, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    fallback, _ = _forecast_lane_cohort_ladder(
        ladders[(key[0], 2019, key[1], key[2])],
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )

    forecast, calibrations = _forecast_recent_cumulative_stack_ladder(
        ladders[(key[0], 2019, key[1], key[2])],
        model,
        fallback,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )

    calibration = calibrations[9]
    assert calibration.transition_count == 2
    assert calibration.recent_trend_delta > 0.0
    assert calibration.current_source_stack == 20
    assert sum(count for points, count in forecast.items() if points >= 9) >= calibration.forecast_target_stack
    assert calibration.forecast_target_stack > calibration.current_source_stack


def test_recent_cumulative_stack_uses_one_exact_transition_but_never_cross_hunt_fallback() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9992", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            9: {"eligible": 7, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    latest = ladders[(key[0], 2019, key[1], key[2])]
    fallback, fallback_calibrations = _forecast_lane_cohort_ladder(
        latest,
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )

    forecast, calibrations = _forecast_recent_cumulative_stack_ladder(
        latest,
        model,
        fallback,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )
    assert calibrations[9].transition_count == 1
    assert sum(count for points, count in forecast.items() if points >= 9) >= sum(
        count for points, count in fallback.items() if points >= 9
    )
    fallback_samples = _sample_lane_cohort_forecast_ladders(
        latest,
        fallback_calibrations,
        iterations=10,
        seed="one-transition-fallback",
    )
    samples = _sample_recent_cumulative_stack_ladders(
        latest,
        fallback_samples,
        calibrations,
        seed="one-transition-cumulative",
    )
    assert len(samples) == len(fallback_samples)
    assert all(
        sum(count for points, count in sample.items() if points >= 9)
        >= sum(count for points, count in fallback_sample.items() if points >= 9)
        for sample, fallback_sample in zip(samples, fallback_samples)
    )

    other_hunt_forecast, other_hunt_calibrations = _forecast_recent_cumulative_stack_ladder(
        latest,
        model,
        fallback,
        subtype=key[0],
        hunt_code="BR_NO_HISTORY",
        residency=key[2],
    )

    assert other_hunt_calibrations == {}
    assert other_hunt_forecast == fallback


def test_recent_cumulative_stack_keeps_sparse_direct_count_upper_tail() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9991", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            10: {"eligible": 1, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            10: {"eligible": 1, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    latest = ladders[(key[0], 2019, key[1], key[2])]
    fallback, fallback_calibrations = _forecast_lane_cohort_ladder(
        latest,
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )
    _, calibrations = _forecast_recent_cumulative_stack_ladder(
        latest,
        model,
        fallback,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )
    fallback_samples = _sample_lane_cohort_forecast_ladders(
        latest,
        fallback_calibrations,
        iterations=400,
        seed="sparse-direct-fallback",
    )
    samples = _sample_recent_cumulative_stack_ladders(
        latest,
        fallback_samples,
        calibrations,
        seed="sparse-direct-cumulative",
    )

    stacks = [sum(count for points, count in sample.items() if points >= 10) for sample in samples]
    assert len(set(stacks)) > 1
    assert max(stacks) > 5


def test_lane_cohort_sampling_keeps_a_thin_exact_lane_uncertain() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9998", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 8, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            9: {"eligible": 8, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    _, calibrations = _forecast_lane_cohort_ladder(
        ladders[(key[0], 2018, key[1], key[2])],
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )

    samples = _sample_lane_cohort_forecast_ladders(
        ladders[(key[0], 2018, key[1], key[2])],
        calibrations,
        iterations=60,
        seed="thin-lane-cohort",
    )

    point_nine_counts = {sample[9] for sample in samples}
    assert min(point_nine_counts) < 8
    assert max(point_nine_counts) <= 8


def test_lane_cohort_fallback_cannot_create_an_empty_upper_rung() -> None:
    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9997", "Resident")
    ladders = {
        (key[0], 2018, key[1], key[2]): {
            8: {"eligible": 4, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2019, key[1], key[2]): {
            9: {"eligible": 7, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    empty_upper = {
        9: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0},
    }

    forecast, calibrations = _forecast_lane_cohort_ladder(
        empty_upper,
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )
    samples = _sample_lane_cohort_forecast_ladders(
        empty_upper,
        calibrations,
        iterations=20,
        seed="empty-upper-rung",
    )

    assert forecast[10] == 0
    assert {sample[10] for sample in samples} == {0}


def test_exact_lane_arrival_evidence_can_populate_an_empty_upper_rung() -> None:
    """A prior exact arrival is evidence, unlike a broad fallback alone."""

    key = ("LIMITED_ENTRY_BEAR_HUNT", "BR9996", "Resident")
    ladders = {
        # This exact source rung was empty, but two applicants appeared at the
        # next rung in the following official draw. That is a measured arrival
        # residual, not a returning unsuccessful cohort.
        (key[0], 2017, key[1], key[2]): {
            9: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0},
        },
        (key[0], 2018, key[1], key[2]): {
            10: {"eligible": 2, "bonus": 0, "regular": 0, "total": 0},
        },
    }
    model = _build_lane_cohort_model(ladders)
    latest_empty_upper = {
        9: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0},
    }

    forecast, calibrations = _forecast_lane_cohort_ladder(
        latest_empty_upper,
        model,
        subtype=key[0],
        hunt_code=key[1],
        residency=key[2],
    )
    samples = _sample_lane_cohort_forecast_ladders(
        latest_empty_upper,
        calibrations,
        iterations=80,
        seed="exact-empty-upper-arrival",
    )

    assert calibrations[10].exact_transitions == 1
    assert calibrations[10].arrival_count > 0.0
    assert forecast[10] > 0
    assert 0 in {sample[10] for sample in samples}
    assert max(sample[10] for sample in samples) >= 1


def test_measured_arrival_sampling_preserves_mean_without_rounding_every_iteration() -> None:
    import random

    rng = random.Random("arrival-counts")
    samples = [_sample_observed_arrival_count(rng, 0.6) for _ in range(4_000)]

    assert 0 in samples
    assert max(samples) >= 2
    assert sum(samples) / len(samples) == pytest.approx(0.6, abs=0.05)


def test_focal_applicant_is_present_when_an_arrival_sample_is_zero() -> None:
    conditioned = _condition_for_focal_bear_applicant({9: 0, 8: 3}, 9)

    assert conditioned == {9: 1, 8: 3}


def test_bear_one_permit_lane_is_random_only_but_other_odd_pools_keep_max_extra() -> None:
    """Official Bear ladders retain a one-permit, regular-draw exception."""

    assert _split_bear_bonus_permits(1, "Resident") == (0, 1)
    assert _split_bear_bonus_permits(1, "Nonresident") == (0, 1)
    assert _split_bear_bonus_permits(3, "Resident") == (2, 1)
