import csv
from types import SimpleNamespace

from scripts.classify_historical_actual_gaps import (
    BLOCKING_ENGINE_GAP,
    SOURCE_CLASSIFIED,
    blocked_identity_decisions,
    classify_gap,
    conditional_abstention_evidence,
    initialize_crosswalk,
)


def test_zero_applicant_prior_rung_is_source_limitation_not_engine_coverage_defect():
    gap = {
        "draw_design_key": "BONUS_PLE_BIG_GAME",
        "draw_pool_key": "max_weighted_split",
        "hunt_code": "DB1008",
        "residency": "Nonresident",
        "points": "7",
    }
    key = (
        "BONUS_PLE_BIG_GAME",
        "max_weighted_split",
        "DB1008",
        "Nonresident",
        "7",
    )
    prior_point = SimpleNamespace(
        residency="Nonresident",
        actual_eligible_applicants=0.0,
        actual_drawn=0.0,
    )
    source_row = {
        "nonresident_eligible_applicants": "0",
        "nonresident_total_permits": "0",
        "source_file": "2024_L.E. DEER DRAW RESULTS.pdf",
    }

    classification, status, evidence = classify_gap(
        gap,
        exact_rows={key: [(prior_point, source_row)]},
        lanes={key[:4]},
        hunts={key[:3]},
    )

    assert classification == "SOURCE_LIMITATION_PRIOR_YEAR_EMPTY_POINT_RUNG"
    assert status == SOURCE_CLASSIFIED
    assert evidence["prior_year_eligible_applicants"] == 0.0


def test_pre_draw_identity_block_overrides_same_code_source_probability():
    gap = {
        "draw_design_key": "BONUS_OIL_BIG_GAME",
        "draw_pool_key": "max_weighted_split",
        "hunt_code": "BI6507",
        "residency": "Resident",
        "points": "22",
    }
    key = (
        "BONUS_OIL_BIG_GAME",
        "max_weighted_split",
        "BI6507",
        "Resident",
        "22",
    )
    prior_point = SimpleNamespace(
        residency="Resident",
        actual_eligible_applicants=2.0,
        actual_drawn=1.0,
    )
    source_row = {
        "resident_eligible_applicants": "2",
        "resident_total_permits": "1",
        "source_file": "18_big_game_odds_report.pdf",
    }

    without_identity, without_status, _ = classify_gap(
        gap,
        exact_rows={key: [(prior_point, source_row)]},
        lanes={key[:4]},
        hunts={key[:3]},
    )
    classification, status, evidence = classify_gap(
        gap,
        exact_rows={key: [(prior_point, source_row)]},
        lanes={key[:4]},
        hunts={key[:3]},
        blocked_identities={
            "BI6507": [
                {
                    "transition_type": "BOUNDARY_CHANGE",
                    "applicant_stack_carry_forward_allowed": "FALSE",
                    "evidence_file": "2019_biggameapp.pdf",
                    "evidence_pages": "44-45",
                }
            ]
        },
    )

    assert without_identity == "ENGINE_COVERAGE_DEFECT_SOURCE_PROBABILITY_NOT_EMITTED"
    assert without_status == BLOCKING_ENGINE_GAP
    assert classification == "SOURCE_IDENTITY_BLOCKED_PRE_DRAW_BOUNDARY_CHANGE"
    assert status == SOURCE_CLASSIFIED
    assert evidence["prior_year_identity_carry_forward_allowed"] == "FALSE"


def test_identity_source_is_blocked_only_when_no_successor_is_allowed(tmp_path):
    path = tmp_path / "crosswalk.csv"
    rows = [
        {
            "from_hunt_code": "MB6204",
            "to_hunt_code": "MB6240",
            "transition_type": "NAME_ALIAS",
            "applicant_stack_carry_forward_allowed": "TRUE",
        },
        {
            "from_hunt_code": "MB6204",
            "to_hunt_code": "MB6241",
            "transition_type": "UNRESOLVED",
            "applicant_stack_carry_forward_allowed": "FALSE",
        },
        {
            "from_hunt_code": "BI6507",
            "to_hunt_code": "BI6507",
            "transition_type": "BOUNDARY_CHANGE",
            "applicant_stack_carry_forward_allowed": "FALSE",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    blocked = blocked_identity_decisions(path)

    assert "MB6204" not in blocked
    assert [row["transition_type"] for row in blocked["BI6507"]] == ["BOUNDARY_CHANGE"]


def test_present_but_blank_probability_is_a_blocking_coverage_gap(tmp_path):
    from scripts.classify_historical_actual_gaps import MISSING_SCOREABLE_ACTUAL_DECISIONS
    from scripts.build_blind_acceptance_review import load_actual_gap_fold

    assert "do_not_score_missing_prediction_probability" in MISSING_SCOREABLE_ACTUAL_DECISIONS
    path = tmp_path / "actual_gaps.csv"
    row = {"draw_design_key": "BONUS_LE_BIG_GAME", "hunt_code": "DB1017",
           "residency": "Resident", "points": "12", "draw_pool_key": "max_weighted_split",
           "scoring_decision": "do_not_score_missing_prediction_probability"}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    gaps, _ = load_actual_gap_fold("2017_to_2018", path)
    assert len(gaps) == 1
    assert gaps[0]["is_unclassified"] is True


def test_conditional_abstention_requires_source_replay_not_just_a_status():
    initialize_crosswalk(2017, 2018)
    base = {"actual_draw_year": "2017", "year": "2017", "hunt_code": "DB1017",
            "species": "Deer", "hunt_name": "Limited Entry Buck Deer", "hunt_type": "Limited Entry",
            "draw_design": "BONUS_LE_BIG_GAME", "draw_system_type": "BONUS_LE_BIG_GAME",
            "draw_pool": "limited_entry_deer", "residency": "Resident", "record_type": "point_level_draw_result",
            "source_file": "17_bg-odds.pdf", "official_page": "10", "total_permits": "1"}
    history = [{**base, "points": "0", "eligible_applicants": "1", "bonus_permits": "1", "regular_permits": "0"},
               {**base, "points": "1", "eligible_applicants": "2", "bonus_permits": "0", "regular_permits": "1"}]
    pred = {"family": "bonus_le_big_game", "hunt_code": "DB1017", "residency": "Resident", "points": "1",
            "draw_system_type": "BONUS_LE_BIG_GAME", "draw_pool": "limited_entry_deer",
            "algorithm_status": "NOT_SCORED_CONDITIONAL_RUNG_NO_TRANSITION_EVIDENCE",
            "forecast_applicants_at_level": "0", "quota_2026_total": "2", "p_draw_mean": ""}
    key = ("BONUS_LE_BIG_GAME", "max_weighted_split", "DB1017", "Resident", "1")
    proof = conditional_abstention_evidence(history, [pred], 2017)
    assert proof[key]["source_predecessor_unsuccessful"] == 0
    assert proof[key]["source_adjacent_transition_count"] == 0
    assert conditional_abstention_evidence([], [pred], 2017) == {}
    assert conditional_abstention_evidence(history, [{**pred, "quota_2026_total": "99"}], 2017) == {}
    assert conditional_abstention_evidence(history, [{**pred, "p_draw_mean": "0.5"}], 2017) == {}
    assert conditional_abstention_evidence(history, [{**pred, "forecast_applicants_at_level": "1"}], 2017) == {}
    future = [{**r, "actual_draw_year": "2018", "year": "2018"} for r in history]
    assert conditional_abstention_evidence(history + future, [pred], 2017) == proof
    assert conditional_abstention_evidence(history + future, [pred], 2018) == {}
