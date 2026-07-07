import math

from engine.utah_draw_predictive.classifier import classify_draw_system_type
from engine.utah_draw_predictive.sportsman import build_sportsman_predictions


SPORTSMAN_CODES = {
    "BI1000": "Bison",
    "BR1000": "Black Bear",
    "DB0007": "Deer",
    "DS1000": "Desert Bighorn Sheep",
    "EB1000": "Elk",
    "GO1000": "Mountain Goat",
    "MB1000": "Moose",
    "PB1000": "Pronghorn",
    "RS0001": "Rocky Mountain Bighorn Sheep",
    "TK0001": "Turkey",
}


def test_sportsman_random_only_contract() -> None:
    rows, report = build_sportsman_predictions([], [], 2026, [2025])

    assert len(rows) == 10
    assert report["sportsman_code_count_guardrail"] == "PASS"
    assert report["sportsman_draw_design"] == "SPORTSMAN_RANDOM_ONLY"
    assert report["sportsman_random_only"] is True
    assert report["sportsman_split_draw"] is False
    assert report["sportsman_residency_scope"] == "RESIDENT_ONLY"
    assert report["nonresident_row_count"] == 0
    assert report["nonresident_quota_total"] == 0

    assert {row["hunt_code"] for row in rows} == set(SPORTSMAN_CODES)
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in rows)
    assert all(row["model_strategy"] == "SPORTSMAN_RANDOM_ONLY" for row in rows)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in rows)
    assert all(row["sportsman_random_only"] == "TRUE" for row in rows)
    assert all(row["sportsman_split_draw"] == "FALSE" for row in rows)
    assert all(row["sportsman_nonresident_quota"] == "0" for row in rows)
    assert all(row["p_bonus_pool"] == "" for row in rows)
    assert all(row["p_random_pool"] == "" for row in rows)
    assert all(row["p_preference_draw"] == "" for row in rows)

    for row in rows:
        applicants = int(row["sportsman_applicants"])
        permit_count = int(row["sportsman_permit_count"])
        expected = permit_count / applicants
        assert permit_count == 1
        assert math.isclose(float(row["p_sportsman_draw"]), expected, rel_tol=0, abs_tol=1e-6)
        assert math.isclose(float(row["p_draw"]), expected, rel_tol=0, abs_tol=1e-6)


def test_exact_2026_sportsman_codes_classify_only_as_sportsman_permits() -> None:
    for hunt_code, species in SPORTSMAN_CODES.items():
        row = {
            "hunt_code": hunt_code,
            "hunt_name": f"Sportsman {species}",
            "species": species,
            "hunt_type": "Statewide Permit",
            "hunt_class": "Sportsman",
            "weapon": "Any Legal Weapon",
        }

        assert classify_draw_system_type(row) == "SPORTSMAN_PERMIT"


def test_current_cougar_rows_do_not_reenter_sportsman_random_only() -> None:
    current_rows = [
        {
            "hunt_code": "CG9999",
            "hunt_name": "Cougar - Statewide",
            "species": "Cougar",
            "hunt_type": "Statewide",
            "hunt_class": "Capped Permits",
            "weapon": "Any Legal Weapon",
            "year": "2026",
        },
        {
            "hunt_code": "CG1000",
            "hunt_name": "Cougar - Statewide",
            "species": "Cougar",
            "hunt_type": "Sportsman",
            "hunt_class": "Sportsman",
            "weapon": "Any Legal Weapon",
            "year": "2026",
        },
    ]

    for row in current_rows:
        assert classify_draw_system_type(row) == "COUGAR_LICENSE_BASED"


def test_historical_cougar_sportsman_rows_remain_historical_truth_only() -> None:
    historical_row = {
        "hunt_code": "CG1000",
        "hunt_name": "Sportsman Cougar",
        "species": "Cougar",
        "hunt_type": "Sportsman",
        "hunt_class": "Sportsman",
        "weapon": "Any Legal Weapon",
        "actual_draw_year": "2022",
    }

    assert classify_draw_system_type(historical_row) == "SPORTSMAN_PERMIT"


def test_2017_sportsman_pdf_source_emits_cougar_code_for_2018_forecast() -> None:
    rows, report = build_sportsman_predictions([], [], 2018, [2017])
    by_code = {row["hunt_code"]: row for row in rows}

    assert len(rows) == 11
    assert report["sportsman_source_year"] == 2017
    assert report["sportsman_source_code_count"] == 11
    assert {"CG1000", "DB1045", "RS1000", "TK1000"} <= set(by_code)
    assert "DB0007" not in by_code

    cougar = by_code["CG1000"]
    assert cougar["sportsman_source_file"] == "2017_sportsman_odds.pdf"
    assert cougar["sportsman_applicants"] == "1240"
    assert cougar["sportsman_permit_count"] == "1"
    assert math.isclose(float(cougar["p_sportsman_draw"]), 1 / 1240, rel_tol=0, abs_tol=1e-6)
