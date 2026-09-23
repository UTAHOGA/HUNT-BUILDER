from engine.utah_draw_predictive.special_bonus import (
    _build_truth_ladders,
    _split_special_bonus_permits,
    build_phase6_bonus_special_predictions,
)


def test_public_cwmu_one_permit_is_regular_weighted_random_for_both_residencies() -> None:
    for residency in ("Resident", "Nonresident"):
        split = _split_special_bonus_permits(1, residency, "BONUS_CWMU_BIG_GAME")
        assert split.maxPointPermits == 0
        assert split.randomPermits == 1
        assert split.randomOnly is True


def test_cwmu_hunt_total_row_is_not_double_counted_as_zero_point_rung() -> None:
    shared = {
        "actual_draw_year": "2024",
        "hunt_code": "DB1222",
        "hunt_name": "CWMU Buck Deer - Coldwater Ranch",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "CWMU",
        "hunt_class": "CWMU_BIG_GAME",
        "draw_pool": "CWMU_BIG_GAME",
    }
    rows = [
        {
            **shared,
            "record_type": "hunt_total_draw_result",
            "points": "",
            "resident_eligible_applicants": "62",
            "resident_bonus_permits": "1",
            "resident_regular_permits": "1",
            "resident_total_permits": "2",
        },
        {
            **shared,
            "record_type": "point_level_draw_result",
            "points": "17",
            "resident_eligible_applicants": "1",
            "resident_bonus_permits": "1",
            "resident_regular_permits": "0",
            "resident_total_permits": "1",
        },
        {
            **shared,
            "record_type": "point_level_draw_result",
            "points": "7",
            "resident_eligible_applicants": "4",
            "resident_bonus_permits": "0",
            "resident_regular_permits": "1",
            "resident_total_permits": "1",
        },
    ]

    ladders, _meta, totals, _counters = _build_truth_ladders(rows, {2024})
    ladder = ladders[("BONUS_CWMU_BIG_GAME", 2024, "DB1222", "cwmu_big_game_deer_buck", "Resident")]

    assert sum(item["eligible"] for item in ladder.values()) == 5
    assert sum(item["total"] for item in ladder.values()) == 2
    assert totals[("DB1222", "cwmu_big_game_deer_buck", 2024)]["Resident"] == 2


def test_public_cwmu_rows_are_modeled_in_their_exact_adult_pool() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1258",
            "hunt_name": "Little Red Creek CWMU",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "hunt_class": "CWMU",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "12",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
        {
            "hunt_code": "DB1258",
            "hunt_name": "Little Red Creek CWMU",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "hunt_class": "CWMU",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "10",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
        {
            "hunt_code": "DB1258",
            "hunt_name": "Little Red Creek CWMU",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "hunt_class": "CWMU",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "4",
            "bonus_permits": "1",
            "regular_permits": "0",
            "total_permits": "1",
        },
    ]
    db_rows = [
        {
            "hunt_code": "DB1258",
            "hunt_name": "Little Red Creek CWMU",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "weapon": "Any Legal Weapon",
            "permits_2026_total": "2",
            "permits_2026_res": "2",
            "permits_2026_nr": "0",
        }
    ]

    rows, report = build_phase6_bonus_special_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )

    modeled = [row for row in rows if row.get("bonus_special_valid") == "TRUE"]
    cwmu_rows = [row for row in rows if "CWMU" in row.get("hunt_name", "").upper() or row.get("hunt_type") == "CWMU"]

    assert modeled
    assert report["cwmu_public_modeled_row_count"] > 0
    assert cwmu_rows
    assert {row["draw_pool"] for row in cwmu_rows} == {"cwmu_big_game_deer_buck"}


def test_private_and_youth_cwmu_rows_are_not_public_bonus_predictions() -> None:
    truth_rows = [
        {
            "hunt_code": "EA9999",
            "hunt_name": "Private Creek CWMU Youth Antlerless Elk",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "CWMU",
            "hunt_class": "Private Landowner Voucher",
            "source_is_youth": "true",
            "year": "2025",
            "draw_pool": "CWMU_ANTLERLESS",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "10",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        }
    ]
    db_rows = [
        {
            "hunt_code": "EA9999",
            "hunt_name": "Private Creek CWMU Youth Antlerless Elk",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "CWMU",
            "hunt_class": "Private Landowner Voucher",
            "draw_pool": "cwmu_youth_antlerless_elk",
            "permits_2026_total": "1",
            "permits_2026_res": "1",
            "permits_2026_nr": "0",
        }
    ]

    rows, report = build_phase6_bonus_special_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2025],
    )

    assert rows == []
    assert report["cwmu_public_modeled_row_count"] == 0


def test_adult_cwmu_antlerless_rows_are_not_public_bonus_predictions() -> None:
    truth_rows = [
        {
            "hunt_code": "EA1129",
            "hunt_name": "CWMU Antlerless Elk - Example Ranch",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "CWMU",
            "hunt_class": "CWMU_ANTLERLESS",
            "source_is_youth": "false",
            "year": "2025",
            "draw_pool": "cwmu_antlerless_elk",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "20",
            "bonus_permits": "0",
            "regular_permits": "8",
            "total_permits": "8",
        }
    ]
    db_rows = [{**truth_rows[0], "permits_2026_total": "8", "permits_2026_res": "8", "permits_2026_nr": "0"}]

    rows, report = build_phase6_bonus_special_predictions(truth_rows, db_rows, 2026, [2025])

    assert rows == []
    assert report["cwmu_public_modeled_row_count"] == 0


def test_combined_residency_canonical_rows_use_actual_draw_year_and_explicit_lanes() -> None:
    truth_rows = []
    for points, res_apps, nr_apps, res_bonus, res_regular, nr_regular in (
        (1, 4, 1, 1, 0, 0),
        (0, 10, 2, 0, 1, 1),
    ):
        truth_rows.append(
            {
                "actual_draw_year": "2025",
                "hunt_code": "DB1258",
                "hunt_name": "CWMU Big Game Deer Buck - Little Red Creek",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "CWMU",
                "hunt_class": "CWMU_BIG_GAME",
                "draw_pool": "CWMU_BIG_GAME",
                "points": str(points),
                "resident_eligible_applicants": str(res_apps),
                "resident_bonus_permits": str(res_bonus),
                "resident_regular_permits": str(res_regular),
                "resident_total_permits": str(res_bonus + res_regular),
                "nonresident_eligible_applicants": str(nr_apps),
                "nonresident_bonus_permits": "0",
                "nonresident_regular_permits": str(nr_regular),
                "nonresident_total_permits": str(nr_regular),
            }
        )
    db_rows = [
        {
            "hunt_code": "DB1258",
            "hunt_name": "Little Red Creek",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "hunt_class": "Max/Weighted Split",
            "draw_pool": "max_weighted_split",
            "permits_2026_total": "3",
            "permits_2026_res": "2",
            "permits_2026_nr": "1",
        }
    ]

    rows, _report = build_phase6_bonus_special_predictions(truth_rows, db_rows, 2026, [2025])

    modeled = [row for row in rows if row.get("bonus_special_valid") == "TRUE"]
    assert modeled
    assert {row["residency"] for row in modeled} == {"Resident", "Nonresident"}
    assert {row["draw_pool"] for row in modeled} == {"cwmu_big_game_deer_buck"}
