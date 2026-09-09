from engine.utah_draw_predictive.run_all_families import (
    _effective_draw_pool_for_family,
    _source_backed_family_for_row,
    _source_backed_probability_rows,
    _source_backed_probability_values,
)


def test_blank_display_probability_with_applicants_and_zero_success_is_exact_zero() -> None:
    values = _source_backed_probability_values(
        {
            "resident_eligible_applicants": "23",
            "resident_bonus_permits": "0",
            "resident_regular_permits": "0",
            "resident_total_permits": "0",
            "resident_p_draw": "",
            "resident_success_ratio": "N/A",
            "nonresident_eligible_applicants": "1",
            "nonresident_bonus_permits": "0",
            "nonresident_regular_permits": "0",
            "nonresident_total_permits": "0",
            "nonresident_p_draw": "",
            "nonresident_success_ratio": "N/A",
            "total_eligible_applicants": "24",
            "total_bonus_permits": "0",
            "total_regular_permits": "0",
            "total_permits": "0",
            "total_p_draw": "",
            "total_success_ratio": "N/A",
        }
    )

    assert values == [("Resident", 0.0), ("Nonresident", 0.0), ("", 0.0)]


def test_blank_success_counts_do_not_invent_zero_probability() -> None:
    values = _source_backed_probability_values(
        {
            "resident_eligible_applicants": "23",
            "resident_bonus_permits": "",
            "resident_regular_permits": "",
            "resident_total_permits": "",
            "resident_p_draw": "",
            "resident_success_ratio": "N/A",
        }
    )

    assert values == []


def test_reconciled_published_lane_counts_supply_exact_probability() -> None:
    values = _source_backed_probability_values(
        {
            "resident_eligible_applicants": "25",
            "resident_total_permits": "1",
            "nonresident_eligible_applicants": "4",
            "nonresident_total_permits": "2",
        }
    )

    assert values == [("Resident", 0.04), ("Nonresident", 0.5)]


def test_unreconciled_published_counts_do_not_supply_probability() -> None:
    values = _source_backed_probability_values(
        {
            "residency": "Resident",
            "eligible_applicants": "2",
            "successful_applicants": "",
            "total_permits": "5",
        }
    )

    assert values == []


def test_explicit_residency_row_uses_reported_zero_success_count() -> None:
    values = _source_backed_probability_values(
        {
            "residency": "Resident",
            "eligible_applicants": "18",
            "successful_applicants": "0",
            "p_draw": "",
            "success_ratio": "N/A",
        }
    )

    assert values == [("Resident", 0.0)]


def test_legacy_adult_deer_odds_filename_overrides_polluted_youth_pool_field() -> None:
    row = {
        "hunt_code": "DB1515",
        "species": "Deer",
        "sex_type": "Buck",
        "draw_pool": "youth_general_deer",
        "draw_system_type": "REFERENCE_ONLY",
        "source_file": "21_deer_odds.pdf",
    }

    assert _source_backed_family_for_row(row) == "preference_general_deer"
    assert _effective_draw_pool_for_family(row, "preference_general_deer") == "adult_general_deer"


def test_polluted_reference_only_field_does_not_block_authoritative_adult_deer_source() -> None:
    row = {
        "actual_draw_year": "2021",
        "hunt_code": "DB1515",
        "hunt_name": "Beaver",
        "species": "Deer",
        "sex_type": "Buck",
        "record_type": "point_level_draw_result",
        "points": "0",
        "draw_pool": "youth_general_deer",
        "draw_system_type": "REFERENCE_ONLY",
        "source_file": "21_deer_odds.pdf",
        "resident_eligible_applicants": "388",
        "resident_total_permits": "67",
    }

    rows = _source_backed_probability_rows([row], {}, 2021, 2022)

    assert rows["preference_general_deer"][0]["draw_pool"] == "adult_general_deer"
    assert rows["preference_general_deer"][0]["p_draw"] == "0.172680"
