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

    assert deterministic_row["p_draw_mean"] == 1.0
    assert simulated_row["p_draw_mean"] < 1.0
    assert simulated_row["guaranteed_probability"] == 0.0
    assert "MONTE_CARLO_CENTRAL_ESTIMATE" in simulated_row["reason_codes"]
    assert "SOURCE_TRANSITION_UNCERTAINTY_DISCOUNT" in simulated_row["reason_codes"]
    assert "CONDITIONAL_ON_ONE_APPLICANT_AT_POINT" in simulated_row["reason_codes"]


def test_unknown_central_estimate_mode_is_rejected() -> None:
    history, database = _first_year_fixture()
    with pytest.raises(ValueError, match="central_estimate_mode"):
        build_predictions(history, database, 2018, 10, 7, central_estimate_mode="unknown")
