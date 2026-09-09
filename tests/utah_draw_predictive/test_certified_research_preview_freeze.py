from __future__ import annotations

from scripts.freeze_certified_research_preview import (
    CERTIFIED_DESIGNS,
    CERTIFIED_FIELDS,
    RAW_FUTURE_PROBABILITY_FIELDS,
    preview_row,
)


def test_preview_scope_is_exactly_the_four_certified_core_designs() -> None:
    assert CERTIFIED_DESIGNS == (
        "BONUS_LE_BIG_GAME",
        "BONUS_OIL_BIG_GAME",
        "BONUS_PLE_BIG_GAME",
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    )


def test_preview_row_keeps_only_certified_future_probability_fields() -> None:
    source = {
        "hunt_code": "DB1501",
        "prediction_certification_status": "CERTIFIED",
        "prediction_certification_design": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "certified_p_draw": "0.995",
        "certified_p_draw_mean": "0.995",
        "certified_p_draw_pct": "99.5",
        "p_draw": "0.123",
        "p_draw_mean": "0.456",
        "p_draw_pct": "78.9",
        "display_odds_text": "unsupported alias",
        "actual_draw_probability": "0.75",
    }

    result = preview_row(source, "test-build")

    assert all(result[field] == source[field] for field in CERTIFIED_FIELDS)
    assert not (set(result) & RAW_FUTURE_PROBABILITY_FIELDS)
    assert result["actual_draw_probability"] == "0.75"
    assert result["preview_probability_contract"] == "CERTIFIED_P_DRAW_FIELDS_ONLY"
    assert result["preview_build_id"] == "test-build"


def test_certified_fields_can_remain_explicitly_blank_for_pending_source_rows() -> None:
    result = preview_row(
        {
            "hunt_code": "DB-PENDING",
            "prediction_certification_status": "CERTIFIED",
            "prediction_certification_design": "BONUS_LE_BIG_GAME",
            "p_draw": "",
        },
        "test-build",
    )

    assert all(field in result and result[field] == "" for field in CERTIFIED_FIELDS)


def test_display_only_zero_placeholder_is_not_a_certified_prediction() -> None:
    result = preview_row(
        {
            "hunt_code": "DB1001",
            "prediction_certification_status": "CERTIFIED",
            "prediction_certification_design": "BONUS_PLE_BIG_GAME",
            "status": "DISPLAY ONLY - NO FORECASTED APPLICANT COHORT",
            "p_draw": "0.000000",
            "p_draw_mean": "0.000000",
            "p_draw_pct": "0.000",
            "certified_p_draw": "0.000000",
            "certified_p_draw_mean": "0.000000",
            "certified_p_draw_pct": "0.000",
        },
        "test-build",
    )

    assert all(result[field] == "" for field in CERTIFIED_FIELDS)
