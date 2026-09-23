import pytest

from engine.utah_draw_predictive.sportsman import validate_sportsman_output_coverage


def row(code="BR1000", **changes):
    return {"hunt_code": code, "residency": "Resident", "points": "",
            "draw_system_type": "SPORTSMAN_PERMIT", "p_bonus_pool": "", "p_random_pool": "",
            "p_preference_draw": "", **changes}


def test_sportsman_rows_survive_combined_merge():
    expected = [row(), row("BI1000")]
    validate_sportsman_output_coverage([row("BR1001", draw_system_type="BEAR_DRAW"), *expected], expected)


@pytest.mark.parametrize("actual", [[], [row("BI1000")], [row(), row()],
                                    [row(draw_system_type="BEAR_DRAW")], [row(residency="Nonresident")],
                                    [row(points="0")], [row(points=0)], [row(p_bonus_pool=0)]])
def test_missing_wrong_duplicate_or_bonus_sportsman_rows_fail(actual):
    with pytest.raises(ValueError):
        validate_sportsman_output_coverage(actual, [row()])
