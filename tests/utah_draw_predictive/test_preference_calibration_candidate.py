import pandas as pd

from engine.utah_draw_predictive.preference_calibration import (
    apply_preference_calibration_candidate,
    summarize_calibration_candidate,
)


def test_preference_calibration_candidate_preserves_original_and_applies_shrinkage() -> None:
    rows = pd.DataFrame(
        [
            {
                "hunt_code": "DB1501",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "p_draw": 0.90,
            },
            {
                "hunt_code": "DB1770",
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "residency": "Resident",
                "p_draw": 0.84,
            },
        ]
    )

    table = pd.DataFrame(
        [
            {
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "probability_bin": "80-100%",
                "correction_probability_delta": -0.15,
                "shrinkage_weight": 0.5,
                "recommended_calibration_method": "family_residency_bucket_lookup",
                "overfit_risk": "medium",
                "calibration_value_type": "probability_delta",
            },
            {
                "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                "residency": "Resident",
                "probability_bin": "80-100%",
                "correction_probability_delta": -0.25,
                "shrinkage_weight": 0.8,
                "recommended_calibration_method": "dedicated_hunter_stronger_downward_bucket_correction",
                "overfit_risk": "high",
                "calibration_value_type": "probability_delta",
            },
        ]
    )

    calibrated = apply_preference_calibration_candidate(rows, table)

    assert list(calibrated["p_draw_original"]) == [0.90, 0.84]
    assert rows.loc[0, "p_draw"] == 0.90
    assert calibrated.loc[0, "p_draw_calibrated_candidate"] == 0.825
    assert calibrated.loc[1, "p_draw_calibrated_candidate"] == 0.64
    assert calibrated["calibration_applied_candidate"].tolist() == [True, True]
    assert calibrated["calibration_method"].tolist() == [
        "family_residency_bucket_lookup",
        "dedicated_hunter_stronger_downward_bucket_correction",
    ]


def test_preference_calibration_candidate_supports_explicit_pre_shrunk_delta() -> None:
    rows = pd.DataFrame(
        [
            {
                "hunt_code": "DB1501",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "p_draw": 0.90,
            }
        ]
    )

    table = pd.DataFrame(
        [
            {
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "probability_bin": "80-100%",
                "correction_probability_delta": -0.15,
                "shrinkage_weight": 0.5,
                "recommended_calibration_method": "pre_shrunk_lookup",
                "overfit_risk": "medium",
                "calibration_value_type": "pre_shrunk_probability_delta",
            }
        ]
    )

    calibrated = apply_preference_calibration_candidate(rows, table)

    assert calibrated.loc[0, "p_draw_original"] == 0.90
    assert calibrated.loc[0, "p_draw_calibrated_candidate"] == 0.75
    assert calibrated.loc[0, "calibration_applied_candidate"] is True


def test_preference_calibration_candidate_rejects_logit_offset_in_shadow_mode() -> None:
    rows = pd.DataFrame(
        [
            {
                "hunt_code": "DB1501",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "p_draw": 0.90,
            }
        ]
    )

    table = pd.DataFrame(
        [
            {
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "probability_bin": "80-100%",
                "correction_factor_or_logit_offset": -0.50,
                "shrinkage_weight": 1.0,
                "recommended_calibration_method": "logit_candidate",
                "overfit_risk": "high",
                "calibration_value_type": "logit_offset",
            }
        ]
    )

    calibrated = apply_preference_calibration_candidate(rows, table)

    assert calibrated.loc[0, "p_draw_original"] == 0.90
    assert calibrated.loc[0, "p_draw_calibrated_candidate"] == 0.90
    assert calibrated.loc[0, "calibration_applied_candidate"] is False
    assert "logit_offset_not_supported" in calibrated.loc[0, "calibration_reason"]


def test_preference_calibration_candidate_does_not_calibrate_disallowed_rows_or_create_probability() -> None:
    rows = pd.DataFrame(
        [
            {
                "hunt_code": "DB0007",
                "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
                "residency": "Resident",
                "p_draw": 0.0001,
            },
            {
                "hunt_code": "EA2002",
                "draw_system_type": "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
                "residency": "Resident",
                "p_draw": None,
            },
            {
                "hunt_code": "CG9999",
                "draw_system_type": "COUGAR_LICENSE_BASED",
                "residency": "Resident",
                "p_draw": None,
            },
            {
                "hunt_code": "REF1",
                "draw_system_type": "REFERENCE_ONLY",
                "residency": "Resident",
                "p_draw": None,
            },
        ]
    )

    table = pd.DataFrame(
        [
            {
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                "residency": "Resident",
                "probability_bin": "0-1%",
                "correction_probability_delta": 0.25,
                "shrinkage_weight": 0.8,
                "recommended_calibration_method": "family_residency_bucket_lookup",
                "overfit_risk": "medium",
                "calibration_value_type": "probability_delta",
            }
        ]
    )

    calibrated = apply_preference_calibration_candidate(rows, table)
    summary = summarize_calibration_candidate(calibrated)

    assert calibrated["calibration_applied_candidate"].tolist() == [False, False, False, False]
    assert calibrated.loc[0, "p_draw_calibrated_candidate"] == rows.loc[0, "p_draw"]
    assert calibrated.loc[1:, "p_draw_calibrated_candidate"].isna().all()
    assert summary.applied_rows == 0
    assert summary.disallowed_applied_rows == 0
    assert summary.range_violations == 0
