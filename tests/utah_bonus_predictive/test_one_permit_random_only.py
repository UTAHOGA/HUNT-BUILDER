from engine.utah_bonus_predictive.materialize import status_from_probability
from engine.utah_bonus_predictive.split import split_utah_bonus_permits


def test_nonresident_one_permit_is_random_only() -> None:
    split = split_utah_bonus_permits(1, "Nonresident")
    assert split.maxPointPermits == 0
    assert split.randomPermits == 1
    assert split.randomOnly is True
    assert status_from_probability(split.maxPointPermits, split.randomPermits, p_bonus_pool=0.0) == "RANDOM ONLY"

