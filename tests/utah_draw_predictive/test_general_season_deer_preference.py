from engine.utah_draw_predictive.preference_general_deer import (
    MODEL_STRATEGY_NAME,
    STRATEGY_SPECS,
    build_preference_general_deer_predictions,
    is_modeled_general_deer_row,
)


def test_general_season_deer_strategy_is_promoted_to_modeled_preference() -> None:
    spec = STRATEGY_SPECS[0]
    assert spec.draw_system_type == "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
    assert spec.algorithm_status == "MODELED_PREFERENCE"
    assert "preference-point model" in spec.reason


def test_db0008_extended_archery_availability_does_not_route_to_general_deer_preference() -> None:
    rows = build_preference_general_deer_predictions(
        truth_rows=[
            {
                "hunt_code": "DB0008",
                "hunt_name": "Deer Extended Archery Only",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Public",
                "draw_design": "Preference",
                "draw_system_type": "AVAILABILITY_ONLY",
                "weapon": "Archery",
                "year": "2026",
                "draw_pool": "standard",
                "residency": "Resident",
                "points": "0",
                "eligible_applicants": "306",
                "total_permits": "2000",
            }
        ],
        db_rows=[
            {
                "hunt_code": "DB0008",
                "hunt_name": "Deer Extended Archery Only",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Capped Permits",
                "draw_system_type": "REFERENCE_ONLY",
                "weapon": "Archery",
                "permits_2027_total": "2000",
            }
        ],
        forecast_year=2027,
        history_years=[2026],
    )

    assert rows == []


def test_db17_and_db18_dedicated_hunter_do_not_route_to_general_deer_preference() -> None:
    rows = build_preference_general_deer_predictions(
        truth_rows=[
            {
                "hunt_code": "DB1770",
                "hunt_name": "Box Elder Dedicated Hunter",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "Dedicated Hunter",
                "hunt_class": "Dedicated Hunter",
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "weapon": "Dedicated Hunter",
                "year": "2025",
                "draw_pool": "dedicated_hunter",
                "residency": "Resident",
                "points": "0",
                "eligible_applicants": "25",
                "total_permits": "20",
            }
        ],
        db_rows=[
            {
                "hunt_code": "DB1770",
                "hunt_name": "Box Elder Dedicated Hunter",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "Dedicated Hunter",
                "hunt_class": "Dedicated Hunter",
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "weapon": "Dedicated Hunter",
                "permits_2026_total": "25",
            }
        ],
        forecast_year=2026,
        history_years=[2025],
    )

    assert rows == []

    db18_rows = build_preference_general_deer_predictions(
        truth_rows=[
            {
                "hunt_code": "DB1800",
                "hunt_name": "East Canyon Dedicated Hunter",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Dedicated Hunter",
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "weapon": "Any Legal Weapon",
                "year": "2026",
                "draw_pool": "dedicated_hunter",
                "residency": "Resident",
                "points": "0",
                "eligible_applicants": "25",
                "total_permits": "20",
            }
        ],
        db_rows=[
            {
                "hunt_code": "DB1800",
                "hunt_name": "East Canyon",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Dedicated Hunter",
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "weapon": "Any Legal Weapon",
                "permits_2026_total": "186",
            }
        ],
        forecast_year=2027,
        history_years=[2026],
    )

    assert db18_rows == []


def test_build_preference_general_deer_predictions_returns_modeled_rows() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2022",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "100",
            "total_permits": "80",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2022",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "10",
            "total_permits": "10",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "90",
            "total_permits": "70",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "18",
            "total_permits": "15",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "95",
            "total_permits": "75",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "16",
            "total_permits": "12",
        },
    ]
    db_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "weapon": "Archery",
            "permits_2026_total": "100",
        }
    ]

    rows = build_preference_general_deer_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )

    assert rows
    assert all(row["model_strategy"] == MODEL_STRATEGY_NAME for row in rows)
    assert all(row["preference_model_valid"] == "TRUE" for row in rows)
    assert all(is_modeled_general_deer_row(row) for row in rows)
    assert any(float(row["p_draw"]) >= 0.995 for row in rows)


def test_general_season_deer_emits_structural_zero_point_rows() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "100",
            "total_permits": "80",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "12",
            "eligible_applicants": "0",
            "total_permits": "0",
        },
    ]
    db_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "weapon": "Archery",
            "permits_2026_total": "100",
        }
    ]

    rows = build_preference_general_deer_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2025],
    )

    structural_row = next(
        row
        for row in rows
        if row["hunt_code"] == "DB1501" and row["residency"] == "Resident" and row["points"] == "12"
    )
    assert structural_row["model_strategy"] == MODEL_STRATEGY_NAME
    assert structural_row["preference_model_valid"] == "TRUE"
    assert structural_row["applicants_at_level"] == 0
    assert structural_row["probability_applicant_count"] == 1


def test_duplicate_general_deer_ladder_keys_are_aggregated_before_forecast() -> None:
    truth_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "30",
            "total_permits": "10",
        },
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Archery",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "20",
            "total_permits": "5",
        },
    ]
    db_rows = [
        {
            "hunt_code": "DB1501",
            "hunt_name": "Box Elder",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "weapon": "Archery",
            "permits_2026_total": "50",
        }
    ]

    rows = build_preference_general_deer_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2025],
    )

    point_one = next(
        row
        for row in rows
        if row["hunt_code"] == "DB1501" and row["residency"] == "Resident" and row["points"] == "1"
    )
    assert int(point_one["applicants_at_level"]) == 27
