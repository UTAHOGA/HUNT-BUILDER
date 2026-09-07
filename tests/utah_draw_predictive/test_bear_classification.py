from engine.utah_draw_predictive.classifier import classify_draw_system_type, resolve_algorithm_status
from engine.utah_draw_predictive.bear import (
    BEAR_HISTORICAL_CODE_SUCCESSORS_2026,
    BEAR_HISTORY_CODE_ALIASES_2026,
    LIMITED_ENTRY_BEAR_HUNT,
    RESTRICTED_BEAR_PURSUIT,
    _canonical_official_bear_residency_lanes,
    _is_proven_bonus_bear_truth_row,
    classify_bear_subtype,
    is_supported_bear_bonus_row,
    official_bear_draw_odds_hunt_codes,
    official_bear_pursuit_hunt_codes,
)
from scripts.run_blind_2025_to_2026_prediction_backtest import is_current_planner_non_draw_bear


def test_bear_classification() -> None:
    row = {"hunt_type": "Limited Entry - Fall", "species": "Black Bear", "sex_type": "Either Sex"}
    assert classify_draw_system_type(row) == "BEAR_DRAW"
    assert resolve_algorithm_status(row) == "IN_SCOPE_MODEL_PENDING"


def test_restricted_pursuit_black_bear_stays_in_bear_family() -> None:
    row = {"hunt_type": "Restricted Pursuit - Summer", "species": "Black Bear", "weapon": "Pursuit Only"}
    assert classify_draw_system_type(row) == "BEAR_DRAW"
    assert resolve_algorithm_status(row) != "MODELED_BONUS"


def test_official_restricted_pursuit_bear_rows_enter_bonus_model() -> None:
    hunt_code = sorted(official_bear_pursuit_hunt_codes())[0]
    row = {
        "hunt_code": hunt_code,
        "hunt_type": "Restricted Pursuit",
        "species": "Black Bear",
        "weapon": "Pursuit Only",
        "draw_system_type": "BEAR_DRAW",
    }

    assert classify_bear_subtype(row) == RESTRICTED_BEAR_PURSUIT
    assert is_supported_bear_bonus_row(row) is True
    assert resolve_algorithm_status(row, "BEAR_DRAW") == "IN_SCOPE_MODEL_PENDING"


def test_official_bear_draw_report_overrides_ambiguous_current_planner_labels() -> None:
    pursuit_codes = {
        "BR1008",
        "BR1009",
        "BR1010",
        "BR1011",
        "BR1012",
        "BR1013",
        "BR1015",
        "BR1016",
        "BR1017",
    }
    assert pursuit_codes <= official_bear_pursuit_hunt_codes()
    assert "BR7225" in official_bear_draw_odds_hunt_codes()

    for hunt_code in pursuit_codes | {"BR7225"}:
        assert is_current_planner_non_draw_bear(
            {"hunt_code": hunt_code, "hunt_type": "O.T.C.", "weapon": "Pursuit Only"}
        ) is False


def test_bear_name_in_non_bear_hunt_does_not_false_positive() -> None:
    row = {"hunt_code": "DB1206", "hunt_name": "Bear Mountain CWMU", "species": "Deer", "sex_type": "Buck", "hunt_type": "CWMU", "hunt_class": "CWMU"}
    assert classify_draw_system_type(row) == "BONUS_CWMU_BIG_GAME"


def test_2026_lasal_dolores_bear_split_and_successor_codes_are_locked() -> None:
    assert BEAR_HISTORY_CODE_ALIASES_2026 == {
        "BR7022": "BR7008",
        "BR7127": "BR7108",
        "BR7239": "BR7208",
        "BR7326": "BR7307",
    }
    assert BEAR_HISTORICAL_CODE_SUCCESSORS_2026 == {
        "BR7008": "BR7022",
        "BR7108": "BR7127",
        "BR7208": "BR7239",
        "BR7307": "BR7326",
    }

    lasal = {
        "hunt_code": "BR7022",
        "hunt_name": "La Sal Mtns",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "hunt_class": "Max/Weighted Split",
        "weapon": "Any Legal Weapon",
    }
    dolores = {
        "hunt_code": "BR7021",
        "hunt_name": "Dolores Triangle",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "hunt_class": "Max/Weighted Split",
        "weapon": "Any Legal Weapon",
    }

    assert classify_bear_subtype(lasal) == LIMITED_ENTRY_BEAR_HUNT
    assert classify_bear_subtype(dolores) == LIMITED_ENTRY_BEAR_HUNT
    assert BEAR_HISTORY_CODE_ALIASES_2026["BR7022"] != "BR7021"


def test_retained_historical_bear_pdf_identity_restores_only_audited_lane_rows() -> None:
    legacy_lane = {
        "hunt_code": "BR7002",
        "species": "Black Bear",
        "hunt_type": "Bear",
        "draw_pool": "LIMITED_ENTRY_BEAR_HUNT",
        "source_file": "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/black_bear/18_drawing_odds.pdf",
        "qa_status": "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED",
        "bear_source_classification": "TRUE_BEAR_BONUS_DRAW",
        "bear_source_identity_source": "RETAINED_OFFICIAL_BLACK_BEAR_PDF",
        "bear_source_identity_file": "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/black_bear/18_drawing_odds.pdf",
    }
    assert classify_bear_subtype(legacy_lane) == LIMITED_ENTRY_BEAR_HUNT
    assert _is_proven_bonus_bear_truth_row(legacy_lane) is True

    unproven_copy = dict(legacy_lane)
    unproven_copy.pop("bear_source_identity_source")
    assert _is_proven_bonus_bear_truth_row(unproven_copy) is False


def test_promoted_canonical_bear_row_expands_only_verified_dwr_residency_lanes() -> None:
    canonical = {
        "hunt_code": "BR7000",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "metric_scope": "total",
        "residency": "",
        "qa_status": "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL",
        "bear_source_classification": "TRUE_BEAR_BONUS_DRAW",
        "bear_source_identity_source": "CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
        "bear_source_identity_file": "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/black_bear/20_drawing_odds.pdf",
        "resident_eligible_applicants": "7",
        "resident_bonus_permits": "2",
        "resident_regular_permits": "1",
        "resident_total_permits": "3",
        "nonresident_eligible_applicants": "2",
        "nonresident_bonus_permits": "0",
        "nonresident_regular_permits": "1",
        "nonresident_total_permits": "1",
    }

    lanes = _canonical_official_bear_residency_lanes(canonical)

    assert [(row["residency"], row["eligible_applicants"], row["total_permits"]) for row in lanes] == [
        ("Resident", "7", "3"),
        ("Nonresident", "2", "1"),
    ]
    assert _canonical_official_bear_residency_lanes(dict(canonical, qa_status="SOURCE_TABLE_PARSED")) == []


def test_accepted_reconciled_legacy_canonical_bear_row_expands_published_lanes() -> None:
    """Older canonical promotions may predate dedicated Bear PDF metadata.

    They are still safe to use only when all published resident/nonresident
    count columns are retained and recombine exactly to the combined row.
    """

    canonical = {
        "hunt_code": "BR7003",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "metric_scope": "total",
        "residency": "",
        "qa_status": "SOURCE_TABLE_PARSED",
        "candidate_promotion_status": "CONFIRMED_CANONICAL_SCORABLE",
        "source_file": "official_dwr_archive/black_bear/17_bonus_points.pdf",
        "eligible_applicants": "47",
        "bonus_permits": "1",
        "regular_permits": "1",
        "total_permits": "2",
        "resident_eligible_applicants": "40",
        "resident_bonus_permits": "1",
        "resident_regular_permits": "1",
        "resident_total_permits": "2",
        "nonresident_eligible_applicants": "7",
        "nonresident_bonus_permits": "0",
        "nonresident_regular_permits": "0",
        "nonresident_total_permits": "0",
    }

    lanes = _canonical_official_bear_residency_lanes(canonical)

    assert [(row["residency"], row["eligible_applicants"], row["total_permits"]) for row in lanes] == [
        ("Resident", "40", "2"),
        ("Nonresident", "7", "0"),
    ]
    assert _canonical_official_bear_residency_lanes(
        dict(canonical, nonresident_eligible_applicants="8")
    ) == []
    assert _canonical_official_bear_residency_lanes(
        dict(canonical, candidate_promotion_status="")
    ) == []
