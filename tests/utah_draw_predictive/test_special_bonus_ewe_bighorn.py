from engine.utah_draw_predictive.special_bonus import build_phase6_bonus_special_predictions


def test_ewe_bighorn_uses_bonus_fields_when_modeled() -> None:
    truth_rows = [
        {
            "hunt_code": "RE1000",
            "hunt_name": "Box Elder, Newfoundland Mtn",
            "species": "Rocky Mountain Bighorn Sheep",
            "sex_type": "Ewe",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "ewe_bighorn",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "5",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
        {
            "hunt_code": "RE1000",
            "hunt_name": "Box Elder, Newfoundland Mtn",
            "species": "Rocky Mountain Bighorn Sheep",
            "sex_type": "Ewe",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "ewe_bighorn",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "4",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
    ]
    db_rows = [
        {
            "hunt_code": "RE1000",
            "hunt_name": "Box Elder, Newfoundland Mtn",
            "species": "Rocky Mountain Bighorn Sheep",
            "sex_type": "Ewe",
            "hunt_type": "General Season",
            "weapon": "Any Legal Weapon",
            "permits_2026_total": "1",
            "permits_2026_res": "1",
            "permits_2026_nr": "0",
        }
    ]

    rows, _ = build_phase6_bonus_special_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )
    modeled = [row for row in rows if row["draw_system_type"] == "BONUS_EWE_BIGHORN" and row["bonus_special_valid"] == "TRUE"]
    assert modeled
    assert all(row["p_bonus_pool"] != "" for row in modeled)
    assert all(row["p_preference_draw"] == "" for row in modeled)
