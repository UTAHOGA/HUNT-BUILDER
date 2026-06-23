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
    assert any(float(row["p_draw"]) == 1.0 for row in rows)


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
    assert structural_row["applicants_at_level"] == 1
