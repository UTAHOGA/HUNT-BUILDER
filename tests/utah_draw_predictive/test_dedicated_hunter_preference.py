from engine.utah_draw_predictive.dedicated_hunter import (
    MODEL_STRATEGY_NAME,
    STRATEGY_SPECS,
    _official_quota_for_residency,
    build_preference_dedicated_hunter_predictions,
    is_modeled_dedicated_hunter_row,
)


def test_dedicated_hunter_strategy_is_promoted_to_modeled_preference() -> None:
    spec = STRATEGY_SPECS[0]
    assert spec.draw_system_type == "PREFERENCE_DEDICATED_HUNTER_DEER"
    assert spec.algorithm_status == "MODELED_PREFERENCE"
    assert "preference-point model" in spec.reason


def test_build_preference_dedicated_hunter_predictions_returns_modeled_rows() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Dedicated Hunter",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "25",
            "total_permits": "24",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Dedicated Hunter",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "2",
            "eligible_applicants": "3",
            "total_permits": "2",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": "2024",
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "20",
            "total_permits": "17",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": "2024",
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "4",
            "total_permits": "3",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": "2025",
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "18",
            "total_permits": "16",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": "2025",
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "5",
            "total_permits": "4",
        },
    ]
    db_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "weapon": "Dedicated Hunter",
            "permits_2026_total": "30",
        }
    ]

    rows = build_preference_dedicated_hunter_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )

    assert rows
    assert all(row["model_strategy"] == MODEL_STRATEGY_NAME for row in rows)
    assert all(row["preference_model_valid"] == "TRUE" for row in rows)
    assert all(is_modeled_dedicated_hunter_row(row) for row in rows)
    assert all(row["draw_pool"] == "dedicated_hunter" for row in rows)
    assert all(row["p_preference_draw"] == row["p_draw"] for row in rows)
    assert all(row["p_bonus_pool"] == "" for row in rows)
    assert all(row["p_random_pool"] == "" for row in rows)
    assert any(float(row["p_draw"]) > 0.0 for row in rows)


def test_db15_general_deer_does_not_route_to_dedicated_hunter_preference() -> None:
    rows = build_preference_dedicated_hunter_predictions(
        truth_rows=[
            {
                "hunt_code": "DB1501",
                "hunt_name": "Box Elder",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Public",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "weapon": "Archery",
                "year": "2025",
                "draw_pool": "standard",
                "residency": "Resident",
                "points": "0",
                "eligible_applicants": "50",
                "total_permits": "40",
            }
        ],
        db_rows=[
            {
                "hunt_code": "DB1501",
                "hunt_name": "Box Elder",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Public",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "weapon": "Archery",
                "permits_2026_total": "50",
            }
        ],
        forecast_year=2026,
        history_years=[2025],
    )

    assert rows == []


def test_youth_dedicated_hunter_is_separate_preference_lane() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Adult Unit",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": year,
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "20",
            "total_permits": "10",
        }
        for year in ("2024", "2025")
    ] + [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Youth Unit",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "Youth Dedicated Hunter",
            "hunt_class": "Youth Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": year,
            "draw_pool": "youth_dedicated_hunter",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "5",
            "total_permits": "1",
        }
        for year in ("2024", "2025")
    ]
    db_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Adult Unit",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "draw_pool": "dedicated_hunter",
            "permits_2026_total": "10",
        },
        {
            "hunt_code": "DB1770",
            "hunt_name": "Youth Unit",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "Youth Dedicated Hunter",
            "hunt_class": "Youth Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "draw_pool": "youth_dedicated_hunter",
            "permits_2026_total": "2",
        },
    ]

    rows = build_preference_dedicated_hunter_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2024, 2025],
    )

    assert {row["draw_pool"] for row in rows} == {"dedicated_hunter", "youth_dedicated_hunter"}
    youth_rows = [row for row in rows if row["draw_pool"] == "youth_dedicated_hunter"]
    assert youth_rows
    assert all(row["model_strategy"] == "preference_youth_dedicated_hunter_deer" for row in youth_rows)
    assert all(row["draw_pool"] == "youth_dedicated_hunter" for row in youth_rows)
    assert all(row["hunt_class"] == "Dedicated Hunter" for row in youth_rows)
    assert all(row["hunt_type"] == "General Season" for row in youth_rows)
    assert all(row["weapon"] == "Any Legal Weapon" for row in youth_rows)
    assert all(is_modeled_dedicated_hunter_row(row) for row in youth_rows)


def test_dedicated_hunter_does_not_promote_legacy_allotment_to_current_quota() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "year": year,
            "draw_pool": "dedicated_hunter",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "10",
            "total_permits": "5",
        }
        for year in ("2024", "2025")
    ]
    db_rows = [
        {
            "hunt_code": "DB1770",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Dedicated Hunter",
            "weapon": "Dedicated Hunter",
            "draw_pool": "dedicated_hunter",
            "permits_2026_total": "",
            "permit_allotment_2026_total": "12",
        }
    ]

    rows = build_preference_dedicated_hunter_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2024, 2025],
    )

    assert rows == []


def test_current_total_does_not_mix_with_prior_year_residency_winners() -> None:
    row = {
        "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "draw_pool": "dedicated_hunter",
        "hunt_class": "Dedicated Hunter",
        "permits_2026_total": "42",
        "permits_2025_res": "159",
        "permits_2025_nr": "14",
    }

    resident, resident_authority = _official_quota_for_residency(
        row, "Resident", 2026, source_year=2025
    )
    nonresident, nonresident_authority = _official_quota_for_residency(
        row, "Nonresident", 2026, source_year=2025
    )

    assert resident == 38
    assert nonresident == 4
    assert resident_authority == nonresident_authority == "OFFICIAL_10_PERCENT_TOTAL_ALLOCATION"
