from engine.utah_draw_predictive.run_all_families import (
    _drop_broad_partitioned_rows_when_source_backed,
    _prepare_big_game_bonus_history_rows,
)


def test_combined_official_big_game_row_expands_only_published_residency_lanes():
    source = {
        "actual_draw_year": "2024",
        "hunt_code": "EB3019",
        "draw_pool": "LIMITED_ENTRY",
        "points": "7",
        "residency": "",
        "eligible_applicants": "999",
        "total_permits": "999",
        "resident_eligible_applicants": "40",
        "resident_bonus_permits": "1",
        "resident_regular_permits": "2",
        "resident_total_permits": "3",
        "resident_p_draw": "0.075",
        "nonresident_eligible_applicants": "8",
        "nonresident_bonus_permits": "0",
        "nonresident_regular_permits": "1",
        "nonresident_total_permits": "1",
        "nonresident_p_draw": "0.125",
    }

    rows = _prepare_big_game_bonus_history_rows([source])

    assert [(row["residency"], row["metric_scope"]) for row in rows] == [
        ("Resident", "resident"),
        ("Nonresident", "nonresident"),
    ]
    assert [row["eligible_applicants"] for row in rows] == ["40", "8"]
    assert [row["draw_pool"] for row in rows] == ["limited_entry_elk", "limited_entry_elk"]
    assert [row["total_permits"] for row in rows] == ["3", "1"]
    assert [row["p_draw"] for row in rows] == ["0.075", "0.125"]
    assert [float(row["successful_applicants"]) for row in rows] == [3.0, 1.0]
    assert [float(row["unsuccessful_applicants"]) for row in rows] == [37.0, 7.0]


def test_existing_residency_lane_and_total_only_row_are_not_inferred_or_duplicated():
    existing_lane = {
        "year": "2023",
        "hunt_code": "DB1007",
        "species": "Deer",
        "hunt_type": "Premium Limited Entry",
        "source_file": "2023_P.L.E. DEER DRAW RESULTS.pdf",
        "residency": "Resident",
        "eligible_applicants": "12",
        "resident_eligible_applicants": "12",
    }
    total_only = {
        "actual_draw_year": "2023",
        "hunt_code": "DB1008",
        "species": "Deer",
        "hunt_type": "Premium Limited Entry",
        "source_file": "2023_P.L.E. DEER DRAW RESULTS.pdf",
        "residency": "",
        "total_eligible_applicants": "25",
        "total_permits": "2",
    }

    rows = _prepare_big_game_bonus_history_rows([existing_lane, total_only])

    assert len(rows) == 2
    assert rows[0]["residency"] == "Resident"
    assert rows[0]["eligible_applicants"] == "12"
    assert rows[1]["residency"] == ""
    assert rows[1]["total_eligible_applicants"] == "25"


def test_source_backed_precedence_drops_only_the_exact_modeled_lane():
    modeled_exact = {
        "official_score_key_v2": "2025|LE|R|EB3019|7",
        "source_family": "LE_BIG_GAME",
        "hunt_code": "EB3019",
        "model_strategy": "generic_big_game_bonus",
        "source_file": "",
    }
    modeled_other_point = dict(
        modeled_exact,
        official_score_key_v2="2025|LE|R|EB3019|8",
    )
    source_exact = dict(
        modeled_exact,
        model_strategy="bonus_le_big_game_source_backed_roll_forward",
        source_file="2024_L.E. ELK DRAW RESULTS.pdf",
    )

    rows, dropped = _drop_broad_partitioned_rows_when_source_backed(
        [modeled_exact, modeled_other_point, source_exact]
    )

    assert dropped == 1
    assert rows == [modeled_other_point, source_exact]


def test_non_big_game_row_with_reused_hunt_code_is_not_added_to_bonus_history():
    sportsman = {
        "actual_draw_year": "2017",
        "hunt_code": "DB1045",
        "hunt_name": "Sportsman Deer",
        "species": "Deer",
        "draw_pool": "SPORTSMAN_PERMIT",
        "source_file": "official_dwr_archive/big_game/2017_sportsman_odds.pdf",
        "resident_eligible_applicants": "1200",
        "resident_total_permits": "1",
    }

    assert _prepare_big_game_bonus_history_rows([sportsman]) == []
