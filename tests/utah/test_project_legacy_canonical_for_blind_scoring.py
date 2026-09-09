from scripts.project_legacy_canonical_for_blind_scoring import (
    _single_year,
    cwmu_pool_from_actual_fields,
    expand_actual,
    legacy_pool,
)


def test_actual_cwmu_pool_is_resolved_from_species_and_sex_without_changing_values() -> None:
    row = {
        "record_type": "point_level_draw_result",
        "hunt_code": "DA1050",
        "hunt_name": "Cwmu Antlerless Deer - The Rose Of Snowville",
        "species": "Deer",
        "sex_type": "Doe",
        "hunt_type": "CWMU",
        "draw_design": "MAX_WEIGHTED_SPLIT",
        "draw_pool": "cwmu_antlerless_deer_reference",
        "resident_eligible_applicants": "40",
        "resident_total_permits": "0",
        "resident_p_draw": "0",
    }

    assert cwmu_pool_from_actual_fields(row) == "cwmu_antlerless_deer"
    [projected] = expand_actual(row for row in [row])
    assert projected["draw_system_type"] == "BONUS_CWMU_BIG_GAME"
    assert projected["draw_pool"] == "cwmu_antlerless_deer"
    assert projected["eligible_applicants"] == "40"
    assert projected["p_draw"] == "0"


def test_cwmu_projection_preserves_source_derived_species_sex_pool() -> None:
    assert legacy_pool(
        {
            "family": "bonus_cwmu_big_game",
            "draw_pool": "cwmu_antlerless_deer",
            "source_file": "2018 CWMU Big Game Draw Results.pdf",
        }
    ) == "cwmu_antlerless_deer"


def test_cwmu_projection_retains_generic_filename_fallback_when_source_has_no_detail() -> None:
    assert legacy_pool(
        {
            "family": "bonus_cwmu_big_game",
            "draw_pool": "CWMU_ANTLERLESS",
            "source_file": "2018 CWMU Antlerless Draw Results.pdf",
        }
    ) == "CWMU_ANTLERLESS"


def test_projection_year_labels_are_derived_from_the_frozen_inputs() -> None:
    assert _single_year([{"source_year": "2018"}], "source_year", label="forecast source") == 2018
    assert _single_year([{"forecast_year": "2019"}], "forecast_year", "year", label="forecast draw") == 2019
    assert _single_year([{"actual_draw_year": "2019"}], "actual_draw_year", "year", label="actual draw") == 2019


def test_projection_year_labels_require_an_explicit_override_when_forecast_columns_mix_years() -> None:
    try:
        _single_year(
            [{"forecast_year": "2019"}, {"year": "2020"}],
            "forecast_year",
            "year",
            label="forecast draw",
        )
    except ValueError as error:
        assert "found [2019, 2020]" in str(error)
    else:
        raise AssertionError("mixed forecast years must not silently receive a misleading label")
