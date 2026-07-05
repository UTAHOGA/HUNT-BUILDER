import pytest

from engine.utah_draw_predictive.calibration import apply_family_calibration
from engine.utah_draw_predictive.run_all_families import _apply_antlerless_deer_production_calibration


def test_default_off_returns_raw_probability():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    assert apply_family_calibration(row, 0.5) == 0.5


def test_family_guardrail_leaves_general_deer_unchanged():
    row = {"draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER"}

    assert apply_family_calibration(row, 0.5, enabled=True, mode="shadow") == 0.5


def test_zero_preserving_guardrail_returns_exact_zero():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    assert apply_family_calibration(row, 0.0, enabled=True, mode="shadow") == 0.0


def test_positive_antlerless_deer_value_is_shadow_calibrated():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    calibrated = apply_family_calibration(row, 0.855, enabled=True, mode="shadow")

    assert calibrated == pytest.approx(0.8993711539838417)


def test_positive_antlerless_deer_value_is_production_calibrated():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    calibrated = apply_family_calibration(row, 0.855, enabled=True, mode="production")

    assert calibrated == pytest.approx(0.8993711539838417)


def test_unknown_mode_returns_raw_probability():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    assert apply_family_calibration(row, 0.855, enabled=True, mode="experimental") == 0.855


def test_calibration_clips_at_one():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    assert apply_family_calibration(row, 1.0, enabled=True, mode="shadow") == 1.0


def test_null_probability_remains_null():
    row = {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER"}

    assert apply_family_calibration(row, None, enabled=True, mode="shadow") is None


def test_production_calibration_updates_probability_columns_for_target_family_only():
    rows = [
        {
            "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
            "p_draw": "0.855000",
            "p_preference_draw": "0.855000",
        },
        {
            "draw_system_type": "PREFERENCE_ANTLERLESS_ELK",
            "p_draw": "0.855000",
            "p_preference_draw": "0.855000",
        },
        {
            "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
            "p_draw": "0.000000",
            "p_preference_draw": "0.000000",
        },
    ]

    calibrated = _apply_antlerless_deer_production_calibration(
        rows,
        enabled=True,
        mode="production",
    )

    assert calibrated[0]["p_draw"] == "0.899371"
    assert calibrated[0]["p_preference_draw"] == "0.899371"
    assert calibrated[0]["p_draw_mean"] == "0.899371"
    assert calibrated[0]["p_draw_pct"] == "89.937"
    assert calibrated[0]["calibration_applied"] == "true"
    assert calibrated[1]["p_draw"] == "0.855000"
    assert calibrated[1]["calibration_applied"] == "false"
    assert calibrated[2]["p_draw"] == "0.000000"
    assert calibrated[2]["calibration_zero_preserved"] == "true"
