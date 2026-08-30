from __future__ import annotations

import pytest

from engine.utah_draw_predictive.bear import (
    _bear_simulation_probability,
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
