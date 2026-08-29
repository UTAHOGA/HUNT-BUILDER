from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import (
    actual_points_from_row,
    intentionally_blocked_copied_guarantee,
    prediction_alignment_key,
)


def test_explicit_cwmu_bonus_draw_system_beats_da_ea_db_eb_code_prefix() -> None:
    points = actual_points_from_row(
        {
            "record_type": "point_level_draw_result",
            "hunt_code": "EA1120",
            "hunt_name": "CWMU Antlerless Elk - Bear Mountain - Any Legal Weapon",
            "species": "Elk",
            "hunt_type": "CWMU",
            "draw_design": "BONUS_CWMU_BIG_GAME",
            "draw_system_type": "BONUS_CWMU_BIG_GAME",
            "draw_pool": "CWMU_ANTLERLESS",
            "points": "2",
            "resident_eligible_applicants": "10",
            "resident_p_draw": "0.2",
        }
    )

    assert len(points) == 1
    assert points[0].family == "bonus_cwmu_big_game"
    assert points[0].draw_design_key == "BONUS_CWMU_BIG_GAME"
    assert points[0].draw_pool == "cwmu_antlerless"


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


def test_table_shaped_total_metric_retains_each_official_residency_lane():
    rows = actual_points_from_row(
        {
            "record_type": "point_row",
            "hunt_code": "DB1500",
            "draw_design": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "draw_pool": "general_season_deer",
            "points": "4",
            "metric_scope": "total",
            "resident_eligible_applicants": "20",
            "resident_p_draw": "0.4",
            "nonresident_eligible_applicants": "5",
            "nonresident_p_draw": "0.2",
            "total_eligible_applicants": "25",
            "total_p_draw": "0.36",
        }
    )

    assert [row.residency for row in rows] == ["Resident", "Nonresident"]
    assert [row.actual_probability for row in rows] == [0.4, 0.2]


def test_copied_guarantee_safeguard_is_an_intentional_scoring_exclusion():
    assert intentionally_blocked_copied_guarantee(
        {
            "row": {
                "algorithm_status": "NOT_SCORED_SOURCE_ROLL_FORWARD_GUARANTEE_BLOCKED",
                "reason_codes": "SOURCE_BACKED_PUBLISHED_POINT_PROBABILITY_ROLL_FORWARD_GUARANTEE_BLOCKED",
            }
        }
    )
    assert not intentionally_blocked_copied_guarantee(
        {"row": {"algorithm_status": "MODELED_SOURCE_BACKED_ROLL_FORWARD", "reason_codes": ""}}
    )


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
