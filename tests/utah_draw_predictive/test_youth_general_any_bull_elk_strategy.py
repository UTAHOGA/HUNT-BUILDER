from engine.utah_draw_predictive.classifier import classify_draw_system_type, resolve_algorithm_status
from engine.utah_draw_predictive.youth import build_youth_predictions


def test_draw_only_youth_elk_rows_classify_to_specific_family() -> None:
    row = {
        "hunt_code": "EB1007",
        "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
        "species": "Elk",
        "sex_type": "Bull",
        "hunt_type": "General Season - Any Bull",
        "hunt_class": "Youth",
        "weapon": "Any Legal Weapon",
        "draw_pool": "standard",
        "source_file": "DATABASE.csv",
    }
    assert classify_draw_system_type(row) == "YOUTH_GENERAL_ANY_BULL_ELK"


def test_general_season_youth_elk_routes_to_availability_not_youth_draw() -> None:
    row = {
        "hunt_code": "EB1011",
        "hunt_name": "Youth General Season Bull Elk",
        "species": "Elk",
        "sex_type": "Bull",
        "hunt_type": "General Season - Youth",
        "hunt_class": "General Bull",
        "weapon": "Any Legal Weapon",
        "draw_pool": "standard",
        "source_file": "DATABASE.csv",
    }
    draw_system_type = classify_draw_system_type(row)
    assert draw_system_type == "YOUTH_OTC_OR_AVAILABILITY"
    assert resolve_algorithm_status(row, draw_system_type) == "EXCLUDED_NOT_PREDICTIVE_DRAW"


def test_youth_general_any_bull_elk_rows_forecast_from_promoted_history_lane() -> None:
    db_rows = [
        {
            "hunt_code": "EB1007",
            "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Any Bull",
            "hunt_class": "Youth",
            "weapon": "Any Legal Weapon",
            "season": "Sept 12 2026 - Sept 22 2026",
            "permits_2026_total": "750",
        },
        {
            "hunt_code": "EB1011",
            "hunt_name": "Youth General Season Bull Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Youth",
            "hunt_class": "General Bull",
            "weapon": "Any Legal Weapon",
        },
    ]
    rows, _report = build_youth_predictions([], db_rows, 2026, [2025])
    elk_rows = [row for row in rows if row.get("draw_system_type") == "YOUTH_GENERAL_ANY_BULL_ELK"]
    assert {row.get("hunt_code") for row in elk_rows} == {"EB1007"}
    assert all(row.get("algorithm_status") == "MODELED_RANDOM_ONLY" for row in elk_rows)
    assert all((row.get("p_draw") or "").strip() != "" for row in elk_rows)
    assert all((row.get("p_draw_pct") or "").strip() != "" for row in elk_rows)


def test_youth_general_any_bull_elk_uses_official_target_year_truth_when_available() -> None:
    truth_rows = [
        {
            "actual_draw_year": "2026",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "8068",
            "total_permits": "675",
            "p_draw": "0.083663857",
        },
        {
            "actual_draw_year": "2026",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Nonresident",
            "points": "0",
            "eligible_applicants": "391",
            "total_permits": "75",
            "p_draw": "0.191815857",
        },
    ]
    db_rows = [
        {
            "hunt_code": "EB1007",
            "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Any Bull",
            "hunt_class": "Youth",
            "weapon": "Any Legal Weapon",
            "season": "Sept 12 2026 - Sept 22 2026",
            "permits_2026_total": "750",
        }
    ]

    rows, _report = build_youth_predictions(truth_rows, db_rows, 2026, [2025])
    elk_rows = [row for row in rows if row.get("draw_system_type") == "YOUTH_GENERAL_ANY_BULL_ELK"]

    assert len(elk_rows) == 2
    assert {row.get("algorithm_status") for row in elk_rows} == {"MODELED_RANDOM_ONLY"}
    assert {row.get("points") for row in elk_rows} == {"0"}
    assert {row.get("display_odds_text") for row in elk_rows} == {
        "~1 in 12.0 or 8.4%",
        "~1 in 5.2 or 19.2%",
    }
    assert {row.get("youth_general_any_bull_elk_valid") for row in elk_rows} == {"TRUE"}


def test_youth_general_any_bull_elk_future_year_forecasts_from_history() -> None:
    truth_rows = [
        {
            "actual_draw_year": "2025",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "6597",
            "total_permits": "675",
            "p_draw": "0.102319236",
        },
        {
            "actual_draw_year": "2026",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "8068",
            "total_permits": "675",
            "p_draw": "0.083663857",
        },
        {
            "actual_draw_year": "2025",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Nonresident",
            "points": "0",
            "eligible_applicants": "353",
            "total_permits": "75",
            "p_draw": "0.2124645892",
        },
        {
            "actual_draw_year": "2026",
            "hunt_code": "EB1007",
            "hunt_name": "Youth Any Bull/Hunter's Choice Elk",
            "species": "Elk",
            "sex_type": "Hunter's Choice",
            "weapon": "Any Legal Weapon",
            "residency": "Nonresident",
            "points": "0",
            "eligible_applicants": "391",
            "total_permits": "75",
            "p_draw": "0.191815857",
        },
    ]
    db_rows = [
        {
            "hunt_code": "EB1007",
            "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Any Bull",
            "hunt_class": "Youth",
            "weapon": "Any Legal Weapon",
            "season": "Sept 12 2027 - Sept 22 2027",
            "permits_2026_total": "750",
        }
    ]

    rows, _report = build_youth_predictions(truth_rows, db_rows, 2027, [2025, 2026])
    elk_rows = [row for row in rows if row.get("draw_system_type") == "YOUTH_GENERAL_ANY_BULL_ELK"]

    assert {row.get("algorithm_status") for row in elk_rows} == {"MODELED_RANDOM_ONLY"}
    assert {row.get("projected_applicants_source") for row in elk_rows} == {"eb1007_damped_trend_last2_delta_25"}
    by_res = {row["residency"]: row for row in elk_rows}
    assert by_res["Resident"]["projected_applicants"] == "8436"
    assert by_res["Nonresident"]["projected_applicants"] == "400"
    assert by_res["Resident"]["public_permits_2026"] == "675"
    assert by_res["Nonresident"]["public_permits_2026"] == "75"
