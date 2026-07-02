from engine.utah_draw_predictive.turkey import build_turkey_bonus_predictions


def test_limited_entry_turkey_rows_can_be_modeled_bonus() -> None:
    truth_rows = [
        {
            "hunt_code": "TK1003",
            "hunt_name": "Central Area",
            "species": "Turkey",
            "sex_type": "Bearded",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "preference_point",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "120",
            "bonus_permits": "0",
            "regular_permits": "4",
            "total_permits": "4",
        },
        {
            "hunt_code": "TK1003",
            "hunt_name": "Central Area",
            "species": "Turkey",
            "sex_type": "Bearded",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "preference_point",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "80",
            "bonus_permits": "6",
            "regular_permits": "2",
            "total_permits": "8",
        },
    ]
    db_rows = [
        {
            "hunt_code": "TK1003",
            "hunt_name": "Central Area",
            "species": "Turkey",
            "sex_type": "Bearded",
            "hunt_type": "Limited Entry",
            "weapon": "Any Legal Weapon",
            "permits_2026_total": "8",
        }
    ]

    rows, report = build_turkey_bonus_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )
    modeled = [row for row in rows if row["draw_system_type"] == "BONUS_TURKEY" and row["turkey_bonus_valid"] == "TRUE"]
    assert modeled
    assert report["bonus_turkey_modeled_rows"] == len(modeled)
    assert all(row["p_bonus_pool"] != "" for row in modeled)
    assert all(row["p_random_pool"] != "" for row in modeled)
    assert all(row["p_draw"] != "" for row in modeled)
    assert all(row["p_preference_draw"] == "" for row in modeled)
    assert all(row["draw_pool"] == "preference_point" for row in modeled)
