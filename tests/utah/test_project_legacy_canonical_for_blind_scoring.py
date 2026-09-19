import csv
import hashlib

from scripts.project_legacy_canonical_for_blind_scoring import (
    _single_year,
    apply_reviewed_identity_crosswalk,
    cwmu_pool_from_actual_fields,
    expand_actual,
    inspect_identity_crosswalk_contract,
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


def test_actual_premium_limited_entry_identity_is_preserved_from_official_hunt_name() -> None:
    row = {
        "record_type": "POINT_ROW",
        "hunt_code": "DB1000",
        "hunt_name": "Premium Le Archery Buck Deer - Henry Mtns - Archery",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "L.E.",
        "draw_design": "BONUS_LE_BIG_GAME",
        "draw_pool": "LIMITED_ENTRY",
        "resident_eligible_applicants": "54",
        "resident_total_permits": "1",
        "resident_p_draw": "0.0185185185",
    }

    [projected] = expand_actual([row])

    assert projected["draw_design"] == "BONUS_PLE_BIG_GAME"
    assert projected["draw_system_type"] == "BONUS_PLE_BIG_GAME"
    assert projected["hunt_class"] == "PREMIUM_LIMITED_ENTRY"
    assert projected["draw_pool"] == "MAX_WEIGHTED_SPLIT"
    assert projected["p_draw"] == "0.0185185185"


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


def test_reviewed_identity_crosswalk_carries_only_one_to_one_approved_stacks() -> None:
    rows = [
        {"hunt_code": "BR1008", "p_draw": "0.25", "official_score_key_v2": "old-key"},
        {"hunt_code": "DA1003", "p_draw": "0.50"},
        {"hunt_code": "GO6812", "p_draw": "0.75"},
    ]
    crosswalk = {
        "BR1008": [
            {
                "transition_id": "2017_BR1008_TO_2018_BR1008",
                "from_hunt_code": "BR1008",
                "to_hunt_code": "BR1008",
                "transition_type": "SAME_IDENTITY",
                "applicant_stack_carry_forward_allowed": "TRUE",
            }
        ],
        "DA1003": [
            {
                "transition_id": "2017_DA1003_TO_2018_DA1038",
                "from_hunt_code": "DA1003",
                "to_hunt_code": "DA1038",
                "transition_type": "NAME_ALIAS",
                "applicant_stack_carry_forward_allowed": "TRUE",
            }
        ],
        "GO6812": [
            {
                "transition_id": "2017_GO6812_TO_2018_SPLIT",
                "from_hunt_code": "GO6812",
                "to_hunt_code": "GO6818",
                "transition_type": "ONE_TO_MANY_SPLIT",
                "applicant_stack_carry_forward_allowed": "FALSE",
            }
        ],
    }

    projected, report = apply_reviewed_identity_crosswalk(rows, crosswalk)

    assert [row["hunt_code"] for row in projected] == ["BR1008", "DA1038"]
    assert projected[0]["official_score_key_v2"] == ""
    assert all(row["identity_crosswalk_status"] == "REVIEWED_STACK_CARRY_ALLOWED" for row in projected)
    assert report["input_prediction_rows"] == 3
    assert report["projected_prediction_rows"] == 2
    assert report["excluded_prediction_rows"] == 1
    assert report["excluded_reason_counts"] == {"BLOCKED_ONE_TO_MANY_SPLIT": 1}


def test_pre_draw_exception_crosswalk_passes_unlisted_codes_and_blocks_structural_changes() -> None:
    rows = [
        {"hunt_code": "BR1008", "p_draw": "0.25"},
        {"hunt_code": "MB6204", "p_draw": "0.50", "official_score_key_v2": "old"},
        {"hunt_code": "BR7103", "p_draw": "0.75"},
    ]
    crosswalk = {
        "MB6204": [
            {
                "transition_id": "PRE_DRAW_2018_2019_001",
                "from_hunt_code": "MB6204",
                "to_hunt_code": "MB6240",
                "transition_type": "NAME_ALIAS",
                "applicant_stack_carry_forward_allowed": "TRUE",
            }
        ],
        "BR7103": [
            {
                "transition_id": "PRE_DRAW_2018_2019_002",
                "from_hunt_code": "BR7103",
                "to_hunt_code": "BR7121",
                "transition_type": "ONE_TO_MANY_SPLIT",
                "applicant_stack_carry_forward_allowed": "FALSE",
            },
            {
                "transition_id": "PRE_DRAW_2018_2019_003",
                "from_hunt_code": "BR7103",
                "to_hunt_code": "BR7122",
                "transition_type": "ONE_TO_MANY_SPLIT",
                "applicant_stack_carry_forward_allowed": "FALSE",
            },
        ],
    }

    projected, report = apply_reviewed_identity_crosswalk(
        rows, crosswalk, unlisted_source_code_behavior="PASS_THROUGH"
    )

    assert [row["hunt_code"] for row in projected] == ["BR1008", "MB6240"]
    assert projected[0]["identity_crosswalk_status"] == "PRE_DRAW_NO_EXCEPTION_PASS_THROUGH"
    assert projected[1]["official_score_key_v2"] == ""
    assert report["passthrough_prediction_rows"] == 1
    assert report["excluded_reason_counts"] == {"BLOCKED_ONE_TO_MANY_SPLIT": 1}


def test_pre_draw_contract_requires_every_anti_leak_field(tmp_path) -> None:
    evidence = tmp_path / "2019_biggameapp.pdf"
    evidence.write_bytes(b"frozen test evidence")
    path = tmp_path / "pre_draw_hunt_identity_crosswalk_2018_to_2019.csv"
    row = {
        "from_hunt_code": "MB6204",
        "to_hunt_code": "MB6240",
        "transition_type": "NAME_ALIAS",
        "applicant_stack_carry_forward_allowed": "TRUE",
        "evidence_timing": "PRE_DRAW",
        "target_draw_results_used": "FALSE",
        "crosswalk_scope": "EXCEPTIONS_ONLY_PRE_DRAW",
        "certification_use": "ELIGIBLE_PRE_DRAW_IDENTITY_ONLY",
        "from_draw_year": "2018",
        "to_draw_year": "2019",
        "target_application_evidence_file": str(evidence),
        "target_application_evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "target_application_evidence_pages": "35",
        "target_application_evidence_excerpt": "Chimney Rock MB6240",
        "pre_draw_timing_evidence": "March 7, 2019 | May 30, 2019",
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    contract = inspect_identity_crosswalk_contract(path)

    assert contract["certification_eligible"] is True
    assert contract["unlisted_source_code_behavior"] == "PASS_THROUGH"
    assert contract["crosswalk_contract_validation_errors"] == []
