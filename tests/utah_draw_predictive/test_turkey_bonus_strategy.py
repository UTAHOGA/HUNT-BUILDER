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


def test_single_year_turkey_simulation_does_not_report_deterministic_certainty() -> None:
    truth_rows = [
        {
            "hunt_code": "TK9999",
            "hunt_name": "Test Turkey",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "year": "2025",
            "draw_pool": "preference_point",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "10",
            "bonus_permits": "0",
            "regular_permits": "0",
            "total_permits": "0",
            "source_file": "turkey_2025_turkey_bonus_points_draw_results.pdf",
        }
    ]
    db_rows = [
        {
            "hunt_code": "TK9999",
            "hunt_name": "Test Turkey",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "target_permits_total": "20",
            "target_permits_res": "20",
            "target_permits_nr": "0",
        }
    ]

    deterministic, _ = build_turkey_bonus_predictions(truth_rows, db_rows, 2026, [2025])
    simulated, _ = build_turkey_bonus_predictions(
        truth_rows,
        db_rows,
        2026,
        [2025],
        central_estimate_mode="simulation_mean",
        iterations=200,
        seed=7,
    )

    deterministic_row = next(row for row in deterministic if row["residency"] == "Resident" and row["points"] == "1")
    simulated_row = next(row for row in simulated if row["residency"] == "Resident" and row["points"] == "1")
    assert deterministic_row["p_draw"] == "1.000000"
    assert float(simulated_row["p_draw"]) < 1.0
    assert "TURKEY_SOURCE_TRANSITION_UNCERTAINTY_DISCOUNT" in simulated_row["reason_codes"]


def test_turkey_hunt_total_row_is_not_double_counted_as_zero_point_demand() -> None:
    point_row = {
        "hunt_code": "TK9998",
        "hunt_name": "Test Turkey",
        "species": "Turkey",
        "hunt_type": "Limited Entry",
        "hunt_class": "Public",
        "year": "2025",
        "draw_pool": "preference_point",
        "residency": "Resident",
        "points": "0",
        "eligible_applicants": "10",
        "bonus_permits": "0",
        "regular_permits": "1",
        "total_permits": "1",
        "source_file": "turkey_2025_turkey_bonus_points_draw_results.pdf",
    }
    total_row = {
        **point_row,
        "points": "",
        "record_type": "hunt_total_draw_result",
        "eligible_applicants": "10",
    }
    db_rows = [
        {
            "hunt_code": "TK9998",
            "hunt_name": "Test Turkey",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "hunt_class": "Public",
            "target_permits_total": "4",
            "target_permits_res": "4",
            "target_permits_nr": "0",
        }
    ]

    without_total, _ = build_turkey_bonus_predictions([point_row], db_rows, 2026, [2025])
    with_total, _ = build_turkey_bonus_predictions([point_row, total_row], db_rows, 2026, [2025])
    resident_without = [row for row in without_total if row["residency"] == "Resident"]
    resident_with = [row for row in with_total if row["residency"] == "Resident"]
    assert resident_with == resident_without
