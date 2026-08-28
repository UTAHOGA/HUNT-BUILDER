from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import (
    actual_points_from_row,
    prediction_alignment_key,
)


def test_total_pool_preference_probability_row_is_actual_point():
    rows = actual_points_from_row(
        {
            "record_type": "point_row",
            "hunt_code": "EA1000",
            "draw_design": "PREFERENCE_ANTLERLESS_ELK",
            "draw_pool": "general_season_antlerless_elk",
            "points": "TOTAL",
            "metric_scope": "total",
            "eligible_applicants": "25",
            "p_draw": "0.4",
        }
    )

    assert len(rows) == 1
    assert rows[0].points == "TOTAL"
    assert rows[0].residency == "All"
    assert rows[0].actual_probability == 0.4
    assert rows[0].actual_eligible_applicants == 25


def test_turkey_preference_point_pool_can_be_draw_probability_row():
    rows = actual_points_from_row(
        {
            "record_type": "point_row",
            "hunt_code": "TK1006",
            "species": "Turkey",
            "draw_design": "BONUS_TURKEY",
            "draw_pool": "preference_point",
            "points": "0",
            "residency": "Resident",
            "resident_eligible_applicants": "10",
            "resident_p_draw": "0.2",
        }
    )

    assert len(rows) == 1
    assert rows[0].draw_design_key == "BONUS_TURKEY"
    assert rows[0].draw_pool == "preference_point"
    assert rows[0].actual_probability == 0.2


def test_reference_only_pool_still_excluded():
    rows = actual_points_from_row(
        {
            "record_type": "point_row",
            "hunt_code": "EA1000",
            "draw_design": "REFERENCE_ONLY",
            "draw_pool": "reference_only",
            "points": "0",
            "eligible_applicants": "10",
            "p_draw": "0.2",
        }
    )

    assert rows == []


def test_max_weighted_canonical_label_normalizes_to_limited_entry_engine_design():
    actual = actual_points_from_row(
        {
            "record_type": "point_row",
            "hunt_code": "DB1009",
            "species": "Deer",
            "draw_design": "MAX_WEIGHTED_SPLIT",
            "draw_pool": "max_weighted_split",
            "points": "12",
            "residency": "Resident",
            "resident_eligible_applicants": "10",
            "resident_p_draw": "0.2",
        }
    )[0]
    predicted = prediction_alignment_key(
        {
            "family": "bonus_le_big_game",
            "hunt_code": "DB1009",
            "residency": "Resident",
            "points": "12",
            "draw_design": "BONUS_LE_BIG_GAME",
            "draw_pool": "limited_entry_deer",
        }
    )

    assert actual.draw_design_key == "BONUS_LE_BIG_GAME"
    assert actual.draw_pool == "max_weighted_split"
    assert predicted[:5] == (
        "BONUS_LE_BIG_GAME",
        "max_weighted_split",
        "DB1009",
        "Resident",
        "12",
    )
