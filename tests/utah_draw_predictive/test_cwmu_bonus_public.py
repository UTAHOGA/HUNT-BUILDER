from engine.utah_draw_predictive.special_bonus import build_phase6_bonus_special_predictions


def test_cwmu_private_voucher_rows_are_preserved_without_public_bonus_odds() -> None:
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

    assert not modeled
    assert report["cwmu_public_modeled_row_count"] == 0
    assert cwmu_rows == []
