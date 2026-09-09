from __future__ import annotations

import pytest

from scripts.build_predictive_bonus_engine_v1 import build_predictions


def _first_year_fixture() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    history = [
        {
            "hunt_code": "DB9999",
            "draw_pool": "standard",
            "residency": "Resident",
            "year": "2017",
            "points": str(points),
            "eligible_applicants": str(applicants),
            "bonus_permits": "0",
            "regular_permits": "0",
            "total_permits": "0",
        }
        for points, applicants in [(0, 30), (1, 10), (2, 5), (3, 2), (4, 1)]
    ]
    database = {
        "DB9999": {
            "hunt_code": "DB9999",
            "hunt_type": "Limited Entry Deer",
            "historical_permit_proxy": "true",
            "forecast_permits_res": "2",
            "forecast_permits_nr": "0",
            "forecast_permits_total": "2",
            "forecast_permits_source_year": "2017",
        }
    }
    return history, database


def test_simulation_mean_does_not_reuse_deterministic_guarantee() -> None:
    history, database = _first_year_fixture()
    deterministic, _ = build_predictions(history, database, 2018, 200, 7)
    simulated, _ = build_predictions(
        history,
        database,
        2018,
        200,
        7,
        central_estimate_mode="simulation_mean",
    )

    deterministic_row = next(row for row in deterministic if row["points"] == 6)
    simulated_row = next(row for row in simulated if row["points"] == 6)

    assert deterministic_row["p_draw_mean"] == ""
    assert deterministic_row["algorithm_status"] == "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG"
    assert deterministic_row["prediction_status"] == "NOT_SCORED"
    assert "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG" in deterministic_row["reason_codes"]
    assert simulated_row["p_draw_mean"] == ""
    assert simulated_row["guaranteed_probability"] == ""
    assert simulated_row["algorithm_status"] == "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG"
    assert "MONTE_CARLO_CENTRAL_ESTIMATE" in simulated_row["reason_codes"]
    assert "SOURCE_TRANSITION_UNCERTAINTY_DISCOUNT" in simulated_row["reason_codes"]
    assert "CONDITIONAL_ON_ONE_APPLICANT_AT_POINT" in simulated_row["reason_codes"]


def test_first_year_conditional_guarantee_is_unscored_without_transition_evidence() -> None:
    history = [
        {
            "hunt_code": "EB3100",
            "draw_pool": "limited_entry_elk",
            "residency": "Resident",
            "year": "2017",
            "points": str(points),
            "eligible_applicants": str(applicants),
            "bonus_permits": str(permits),
            "regular_permits": "0",
            "total_permits": str(permits),
        }
        for points, applicants, permits in [(10, 45, 44), (11, 12, 12), (12, 8, 8), (13, 3, 3)]
    ]
    database = {
        "EB3100": {
            "hunt_code": "EB3100",
            "hunt_type": "Limited Entry Elk",
            "historical_permit_proxy": "true",
            "forecast_permits_res": "146",
            "forecast_permits_nr": "15",
            "forecast_permits_total": "161",
            "forecast_permits_source_year": "2017",
        }
    }

    predictions, _ = build_predictions(
        history,
        database,
        2018,
        200,
        7,
        central_estimate_mode="simulation_mean",
    )
    row = next(item for item in predictions if item["points"] == 12)

    assert row["forecast_applicants_at_level"] == 0
    assert row["p_draw_mean"] == ""
    assert row["display_odds_pct"] == ""
    assert row["probability_applicant_count"] == ""
    assert row["algorithm_status"] == "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG"


def test_empty_upper_structural_rung_is_display_only_after_observed_transition() -> None:
    history = [
        {
            "hunt_code": "EB9998",
            "draw_pool": "limited_entry_elk",
            "residency": "Resident",
            "year": str(year),
            "points": str(points),
            "eligible_applicants": str(applicants),
            "bonus_permits": str(applicants) if year == 2021 and points == 2 else "0",
            "regular_permits": "0",
            "total_permits": str(applicants) if year == 2021 and points == 2 else "0",
        }
        for year, points, applicants in [
            (2020, 0, 4),
            (2020, 1, 3),
            (2021, 0, 5),
            (2021, 1, 4),
            (2021, 2, 2),
        ]
    ]
    database = {
        "EB9998": {
            "hunt_code": "EB9998",
            "hunt_type": "Limited Entry Elk",
            "historical_permit_proxy": "true",
            "forecast_permits_res": "10",
            "forecast_permits_nr": "0",
            "forecast_permits_total": "10",
            "forecast_permits_source_year": "2021",
        }
    }

    predictions, _ = build_predictions(history, database, 2022, 200, 7)
    active_rung = next(item for item in predictions if item["points"] == 2)
    upper_structural_rung = next(item for item in predictions if item["points"] == 3)

    assert active_rung["forecast_applicants_at_level"] > 0
    assert active_rung["prediction_status"] == "MODELED"
    assert upper_structural_rung["forecast_applicants_at_level"] == 0
    assert upper_structural_rung["p_draw_mean"] == ""
    assert upper_structural_rung["guaranteed_probability"] == ""
    assert upper_structural_rung["prediction_status"] == "NOT_SCORED"
    assert upper_structural_rung["algorithm_status"] == "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG"
    assert "NOT_SCORED_EMPTY_UPPER_STRUCTURAL_RUNG" in upper_structural_rung["reason_codes"]


def test_unknown_central_estimate_mode_is_rejected() -> None:
    history, database = _first_year_fixture()
    with pytest.raises(ValueError, match="central_estimate_mode"):
        build_predictions(history, database, 2018, 10, 7, central_estimate_mode="unknown")


def test_future_structural_clear_is_high_probability_not_a_guarantee() -> None:
    history = [
        {
            "hunt_code": "EB9997",
            "draw_pool": "limited_entry_elk",
            "residency": "Resident",
            "year": str(year),
            "points": str(points),
            "eligible_applicants": str(applicants),
            "bonus_permits": "0",
            "regular_permits": "0",
            "total_permits": "0",
        }
        for year, points, applicants in [
            (2020, 0, 6),
            (2021, 1, 6),
        ]
    ]
    database = {
        "EB9997": {
            "hunt_code": "EB9997",
            "hunt_type": "Limited Entry Elk",
            "historical_permit_proxy": "true",
            "forecast_permits_res": "20",
            "forecast_permits_nr": "0",
            "forecast_permits_total": "20",
            "forecast_permits_source_year": "2021",
        }
    }

    predictions, _ = build_predictions(history, database, 2022, 20, 7)
    active = next(row for row in predictions if row["forecast_applicants_at_level"] > 0)

    assert active["p_draw_mean"] == pytest.approx(0.99)
    assert active["p_draw_p90"] == pytest.approx(0.99)
    assert active["guaranteed_probability"] == 0.0
    assert "STRUCTURAL_MAX_POOL_CLEAR_BUT_FUTURE_DRAW_NOT_GUARANTEED" in active["reason_codes"]
