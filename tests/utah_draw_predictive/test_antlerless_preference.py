from engine.utah_draw_predictive.preference_antlerless import (
    MODEL_STRATEGY_NAME,
    STRATEGY_SPECS,
    _effective_draw_pool,
    _official_quota_for_residency,
    _target_draw_system_type,
    build_preference_antlerless_predictions,
    is_modeled_antlerless_row,
)


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


def test_antlerless_preference_strategies_are_promoted_to_modeled_preference() -> None:
    mapped = {spec.draw_system_type: spec for spec in STRATEGY_SPECS}
    assert mapped["PREFERENCE_ANTLERLESS_DEER"].algorithm_status == "MODELED_PREFERENCE"
    assert mapped["PREFERENCE_ANTLERLESS_ELK"].algorithm_status == "MODELED_PREFERENCE"
    assert mapped["PREFERENCE_DOE_PRONGHORN"].algorithm_status == "MODELED_PREFERENCE"
    assert "preference-point model" in mapped["PREFERENCE_ANTLERLESS_DEER"].reason


def test_cwmu_antlerless_row_with_stale_preference_label_is_excluded() -> None:
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

    assert _target_draw_system_type(row) is None
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
