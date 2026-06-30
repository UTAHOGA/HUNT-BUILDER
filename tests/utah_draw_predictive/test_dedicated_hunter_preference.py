from engine.utah_draw_predictive.dedicated_hunter import (
    MODEL_STRATEGY_NAME,
    STRATEGY_SPECS,
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
    assert all(row["hunt_class"] == "Youth Dedicated Hunter" for row in youth_rows)
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
