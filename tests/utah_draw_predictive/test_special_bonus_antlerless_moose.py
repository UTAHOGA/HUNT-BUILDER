from engine.utah_draw_predictive.special_bonus import build_phase6_bonus_special_predictions


def test_antlerless_moose_uses_bonus_fields_when_modeled() -> None:
    truth_rows = [
        {
            "hunt_code": "MA1005",
            "hunt_name": "Morgan-South Rich",
            "species": "Moose",
            "sex_type": "Antlerless",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "antlerless_moose",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "8",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
        {
            "hunt_code": "MA1005",
            "hunt_name": "Morgan-South Rich",
            "species": "Moose",
            "sex_type": "Antlerless",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "antlerless_moose",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "6",
            "bonus_permits": "0",
            "regular_permits": "1",
            "total_permits": "1",
        },
    ]
    db_rows = [
        {
            "hunt_code": "MA1005",
            "hunt_name": "Morgan-South Rich",
            "species": "Moose",
            "sex_type": "Antlerless",
            "hunt_type": "Limited Entry",
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
    modeled = [row for row in rows if row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE" and row["bonus_special_valid"] == "TRUE"]
    assert modeled
    assert all(row["p_bonus_pool"] != "" for row in modeled)
    assert all(row["p_preference_draw"] == "" for row in modeled)
