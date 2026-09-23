from engine.utah_draw_predictive.preference_antlerless import (
    MODEL_STRATEGY_NAME,
    STRATEGY_SPECS,
    _calibrate_tail_probability,
    _build_cohort_component_profiles,
    _build_retention_and_zero_growth,
    _build_exact_lane_transition_profiles,
    _effective_draw_pool,
    _forecast_applicant_ladder,
    _lane_transition_profile,
    _looks_like_standard_pool,
    _official_quota_for_residency,
    _target_draw_system_type,
    build_preference_antlerless_predictions,
    is_modeled_antlerless_row,
)
from engine.utah_draw_predictive.certification import has_publishable_probability_basis


def test_official_antlerless_pool_aliases_use_one_adult_identity() -> None:
    assert _effective_draw_pool(
        {"draw_pool": "ANTLERLESS_DEER"}, "PREFERENCE_ANTLERLESS_DEER"
    ) == "general_season_antlerless_deer"
    assert _effective_draw_pool(
        {"draw_pool": "ANTLERLESS_ELK"}, "PREFERENCE_ANTLERLESS_ELK"
    ) == "general_season_antlerless_elk"
    assert _effective_draw_pool(
        {"draw_pool": "DOE_PRONGHORN"}, "PREFERENCE_DOE_PRONGHORN"
    ) == "general_season_doe_pronghorn"


def test_generic_cwmu_antlerless_pool_is_species_normalized_before_routing() -> None:
    cases = (
        ("Deer", "Antlerless", "PREFERENCE_ANTLERLESS_DEER", "cwmu_antlerless_deer"),
        ("Elk", "Antlerless", "PREFERENCE_ANTLERLESS_ELK", "cwmu_antlerless_elk"),
        ("Pronghorn", "Doe", "PREFERENCE_DOE_PRONGHORN", "cwmu_doe_pronghorn"),
    )
    for species, sex_type, draw_system_type, expected_pool in cases:
        row = {
            "hunt_code": "EA1119",
            "hunt_name": f"Example CWMU {species}",
            "species": species,
            "sex_type": sex_type,
            "hunt_type": "CWMU",
            "hunt_class": "CWMU",
            "draw_design": "Preference",
            "draw_system_type": draw_system_type,
            "draw_pool": "CWMU_ANTLERLESS",
        }
        assert _effective_draw_pool(row, draw_system_type) == expected_pool
        assert _looks_like_standard_pool(row)
        row["draw_pool"] = {
            "PREFERENCE_ANTLERLESS_DEER": "ANTLERLESS_DEER",
            "PREFERENCE_ANTLERLESS_ELK": "ANTLERLESS_ELK",
            "PREFERENCE_DOE_PRONGHORN": "DOE_PRONGHORN",
        }[draw_system_type]
        assert _effective_draw_pool(row, draw_system_type) == expected_pool
        assert _looks_like_standard_pool(row)
        row["draw_design"] = "BONUS_CWMU_BIG_GAME"
        assert _looks_like_standard_pool(row)


def test_current_total_only_quota_does_not_reuse_prior_year_residency_lanes() -> None:
    row = {
        "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
        "permits_2026_total": "30",
        "permits_2025_total": "26",
        "permits_2025_res": "26",
        "permits_2025_nr": "0",
    }

    resident, resident_authority = _official_quota_for_residency(
        row,
        "Resident",
        2026,
        source_year=2025,
        draw_system_type="PREFERENCE_ANTLERLESS_DEER",
    )
    nonresident, nonresident_authority = _official_quota_for_residency(
        row,
        "Nonresident",
        2026,
        source_year=2025,
        draw_system_type="PREFERENCE_ANTLERLESS_DEER",
    )

    assert (resident, nonresident) == (27, 3)
    assert resident_authority == nonresident_authority == "OFFICIAL_10_PERCENT_TOTAL_ALLOCATION"


def test_source_transition_rate_is_not_given_a_second_switcher_increment() -> None:
    ladder = {
        0: {"eligible": 10, "drawn": 2},
        1: {"eligible": 4, "drawn": 1},
    }

    forecast = _forecast_applicant_ladder(
        ladder,
        {"0": 1.0, "1": 1.0, "2_3": 1.0, "4_5": 1.0, "6_9": 1.0, "10_plus": 1.0},
        1.0,
    )

    assert forecast[0] == 10
    assert forecast[1] == 8
    assert forecast[2] == 3


def test_transition_calibration_keeps_program_and_residency_lanes_separate() -> None:
    ladders = {
        ("PREFERENCE_ANTLERLESS_DEER", 2024, "DA1000", "general_season_antlerless_deer", "Resident"): {
            0: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2025, "DA1000", "general_season_antlerless_deer", "Resident"): {
            0: {"eligible": 10, "drawn": 0},
            1: {"eligible": 8, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2024, "DA1000", "general_season_antlerless_deer", "Nonresident"): {
            0: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2025, "DA1000", "general_season_antlerless_deer", "Nonresident"): {
            0: {"eligible": 5, "drawn": 0},
            1: {"eligible": 2, "drawn": 0},
        },
    }

    retention, zero_growth, evidence_count = _build_retention_and_zero_growth(ladders)
    resident_retention, resident_zero = _lane_transition_profile(
        "PREFERENCE_ANTLERLESS_DEER", "Resident", retention, zero_growth
    )
    nonresident_retention, nonresident_zero = _lane_transition_profile(
        "PREFERENCE_ANTLERLESS_DEER", "Nonresident", retention, zero_growth
    )

    assert resident_retention["0"] == 0.8
    assert nonresident_retention["0"] == 0.2
    assert resident_zero == 1.0
    assert nonresident_zero == 0.5
    assert evidence_count[("PREFERENCE_ANTLERLESS_DEER", "Resident")] == 1
    assert evidence_count[("PREFERENCE_ANTLERLESS_DEER", "Nonresident")] == 1


def test_transition_calibration_uses_source_backed_upper_middle_quantile() -> None:
    ladders = {}
    for year, next_count in ((2022, 1), (2023, 2), (2024, 10)):
        ladders[("PREFERENCE_DOE_PRONGHORN", year, f"PD{year}", "general_season_doe_pronghorn", "Nonresident")] = {
            0: {"eligible": 10, "drawn": 0},
        }
        ladders[("PREFERENCE_DOE_PRONGHORN", year + 1, f"PD{year}", "general_season_doe_pronghorn", "Nonresident")] = {
            0: {"eligible": 10, "drawn": 0},
            1: {"eligible": next_count, "drawn": 0},
        }

    retention, zero_growth, evidence_count = _build_retention_and_zero_growth(ladders)
    nonresident_retention, _ = _lane_transition_profile(
        "PREFERENCE_DOE_PRONGHORN", "Nonresident", retention, zero_growth
    )

    assert nonresident_retention["0"] == 0.68
    assert evidence_count[("PREFERENCE_DOE_PRONGHORN", "Nonresident")] == 3


def test_transition_calibration_does_not_truncate_measured_arrivals_at_125_percent() -> None:
    ladders = {
        ("PREFERENCE_ANTLERLESS_ELK", 2024, "EA1000", "general_season_antlerless_elk", "Resident"): {
            0: {"eligible": 10, "drawn": 9},
        },
        ("PREFERENCE_ANTLERLESS_ELK", 2025, "EA1000", "general_season_antlerless_elk", "Resident"): {
            0: {"eligible": 10, "drawn": 0},
            1: {"eligible": 3, "drawn": 0},
        },
    }

    retention, _zero_growth, _evidence_count = _build_retention_and_zero_growth(ladders)

    assert retention[("PREFERENCE_ANTLERLESS_ELK", "Resident", "0")] == 3.0


def test_arrival_pressure_is_separate_and_scoped_to_family_residency_point_band() -> None:
    ladders = {
        ("PREFERENCE_ANTLERLESS_DEER", 2022, "DA1000", "general_season_antlerless_deer", "Nonresident"): {
            2: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2023, "DA1000", "general_season_antlerless_deer", "Nonresident"): {
            3: {"eligible": 5, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2022, "DA1001", "general_season_antlerless_deer", "Nonresident"): {
            2: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2023, "DA1001", "general_season_antlerless_deer", "Nonresident"): {
            3: {"eligible": 15, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2022, "DA2000", "general_season_antlerless_deer", "Resident"): {
            2: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_DEER", 2023, "DA2000", "general_season_antlerless_deer", "Resident"): {
            3: {"eligible": 2, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_ELK", 2022, "EA1000", "general_season_antlerless_elk", "Nonresident"): {
            2: {"eligible": 10, "drawn": 0},
        },
        ("PREFERENCE_ANTLERLESS_ELK", 2023, "EA1000", "general_season_antlerless_elk", "Nonresident"): {
            3: {"eligible": 20, "drawn": 0},
        },
    }

    (
        program_return,
        program_arrival,
        program_arrival_bounds,
        _exact_return,
        _exact_arrival,
        _exact_evidence,
    ) = _build_cohort_component_profiles(ladders)

    deer_nr_key = ("PREFERENCE_ANTLERLESS_DEER", "Nonresident", "2_3")
    assert program_return[deer_nr_key] == 0.9
    assert program_arrival[deer_nr_key] == 0.3
    assert program_arrival_bounds[deer_nr_key][2] == 2
    assert program_arrival[("PREFERENCE_ANTLERLESS_DEER", "Resident", "2_3")] == 0.0
    assert program_arrival[("PREFERENCE_ANTLERLESS_ELK", "Nonresident", "2_3")] == 1.0


def test_sparse_nonresident_lane_keeps_score_but_withholds_public_certainty() -> None:
    truth_rows = [
        {
            "hunt_code": "PD1000",
            "hunt_name": "Example Unit",
            "species": "Pronghorn",
            "sex_type": "Doe",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2022",
            "draw_system_type": "PREFERENCE_DOE_PRONGHORN",
            "draw_pool": "DOE_PRONGHORN",
            "residency": "Nonresident",
            "points": "0",
            "eligible_applicants": "10",
            "regular_permits": "1",
        },
        {
            "hunt_code": "PD1000",
            "hunt_name": "Example Unit",
            "species": "Pronghorn",
            "sex_type": "Doe",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_system_type": "PREFERENCE_DOE_PRONGHORN",
            "draw_pool": "DOE_PRONGHORN",
            "residency": "Nonresident",
            "points": "1",
            "eligible_applicants": "6",
            "regular_permits": "0",
        },
    ]
    db_rows = [
        {
            **truth_rows[-1],
            "target_permits_total": "2",
            "target_permits_res": "0",
            "target_permits_nr": "2",
        }
    ]

    rows = build_preference_antlerless_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2024,
        history_years=[2022, 2023],
    )

    modeled = [row for row in rows if row["algorithm_status"] == "MODELED_PREFERENCE"]
    assert modeled
    assert all(row["p_draw"] for row in modeled)
    assert all(row["residency"] == "Nonresident" for row in modeled)
    assert all(row["residency_lane_volatility"] == "SPARSE_NONRESIDENT_1_TO_4_PERMITS" for row in modeled)
    assert all(row["probability_publication_eligible"] == "FALSE" for row in modeled)
    assert all(row["data_quality_grade"] == "D" for row in modeled)
    assert all(not has_publishable_probability_basis(row) for row in modeled)


def test_exact_hunt_lane_profile_overrides_program_rate_after_two_transitions() -> None:
    lane = ("PREFERENCE_ANTLERLESS_DEER", "DA1000", "general_season_antlerless_deer", "Nonresident")
    ladders = {
        (*lane[:1], 2022, *lane[1:]): {0: {"eligible": 10, "drawn": 0}},
        (*lane[:1], 2023, *lane[1:]): {
            0: {"eligible": 5, "drawn": 0},
            1: {"eligible": 2, "drawn": 0},
        },
        (*lane[:1], 2024, *lane[1:]): {
            0: {"eligible": 5, "drawn": 0},
            1: {"eligible": 1, "drawn": 0},
            2: {"eligible": 1, "drawn": 0},
        },
    }

    exact_retention, exact_zero = _build_exact_lane_transition_profiles(ladders)
    retention, zero = _lane_transition_profile(
        lane[0],
        lane[3],
        {(lane[0], lane[3], "0"): 0.75},
        {(lane[0], lane[3]): 1.25},
        hunt_code=lane[1],
        draw_pool=lane[2],
        exact_retention_by_lane_band=exact_retention,
        exact_zero_growth_by_lane=exact_zero,
    )

    assert retention["0"] == 0.2
    assert zero == 0.75


def test_first_source_year_is_withheld_without_adjacent_transition_evidence() -> None:
    truth_rows = [
        {
            "hunt_code": "PD1000",
            "hunt_name": "Example Unit",
            "species": "Pronghorn",
            "sex_type": "Doe",
            "hunt_type": "General Season",
            "weapon": "Any Legal Weapon",
            "year": "2017",
            "draw_system_type": "PREFERENCE_DOE_PRONGHORN",
            "draw_pool": "DOE_PRONGHORN",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "20",
            "regular_permits": "5",
        }
    ]
    db_rows = [
        {
            **truth_rows[0],
            "target_permits_total": "5",
            "target_permits_res": "5",
            "target_permits_nr": "0",
        }
    ]

    rows = build_preference_antlerless_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2018,
        history_years=[2017],
    )

    assert rows
    assert all(row["algorithm_status"] == "NO_TRANSITION_EVIDENCE" for row in rows)
    assert all(row["p_draw"] == "" for row in rows)


def test_antlerless_preference_near_certainty_remains_a_probability() -> None:
    for draw_system_type in (
        "PREFERENCE_ANTLERLESS_DEER",
        "PREFERENCE_ANTLERLESS_ELK",
        "PREFERENCE_DOE_PRONGHORN",
    ):
        assert _calibrate_tail_probability(draw_system_type, 1.0) == (0.995, True)


def test_antlerless_preference_strategies_are_promoted_to_modeled_preference() -> None:
    mapped = {spec.draw_system_type: spec for spec in STRATEGY_SPECS}
    assert mapped["PREFERENCE_ANTLERLESS_DEER"].algorithm_status == "MODELED_PREFERENCE"
    assert mapped["PREFERENCE_ANTLERLESS_ELK"].algorithm_status == "MODELED_PREFERENCE"
    assert mapped["PREFERENCE_DOE_PRONGHORN"].algorithm_status == "MODELED_PREFERENCE"
    assert "preference-point model" in mapped["PREFERENCE_ANTLERLESS_DEER"].reason


def test_public_cwmu_antlerless_row_keeps_preference_parent_design() -> None:
    row = {
        "hunt_code": "DA1011",
        "hunt_name": "George Creek CWMU",
        "species": "Deer",
        "sex_type": "Antlerless",
        "hunt_type": "CWMU",
        "hunt_class": "CWMU",
        "weapon": "Any Legal Weapon",
        "draw_design": "Preference",
        "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
    }

    assert _target_draw_system_type(row) == "PREFERENCE_ANTLERLESS_DEER"
    row["draw_system_type"] = "CWMU_PRIVATE_VOUCHER"
    assert _target_draw_system_type(row) is None


def test_build_preference_antlerless_predictions_returns_modeled_rows() -> None:
    truth_rows = [
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "40",
            "total_permits": "30",
        },
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2023",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "8",
            "total_permits": "7",
        },
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2024",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "38",
            "total_permits": "26",
        },
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2024",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "10",
            "total_permits": "8",
        },
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "36",
            "total_permits": "24",
        },
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Public",
            "weapon": "Any Legal Weapon",
            "year": "2025",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "11",
            "total_permits": "8",
        },
    ]
    db_rows = [
        {
            "hunt_code": "EA1001",
            "hunt_name": "Central Mtns",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "weapon": "Any Legal Weapon",
            "permits_2026_total": "40",
        }
    ]

    rows = build_preference_antlerless_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2026,
        history_years=[2021, 2022, 2023, 2024, 2025],
    )

    assert rows
    assert all(row["model_strategy"] == MODEL_STRATEGY_NAME for row in rows)
    assert all(row["preference_model_valid"] == "TRUE" for row in rows)
    assert all(is_modeled_antlerless_row(row) for row in rows)
    assert all(row["draw_system_type"] == "PREFERENCE_ANTLERLESS_ELK" for row in rows)
    assert any(float(row["p_draw"]) > 0.0 for row in rows)
