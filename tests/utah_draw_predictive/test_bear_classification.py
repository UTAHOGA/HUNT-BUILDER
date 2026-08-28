from engine.utah_draw_predictive.classifier import classify_draw_system_type, resolve_algorithm_status
from engine.utah_draw_predictive.bear import (
    BEAR_HISTORICAL_CODE_SUCCESSORS_2026,
    BEAR_HISTORY_CODE_ALIASES_2026,
    LIMITED_ENTRY_BEAR_HUNT,
    RESTRICTED_BEAR_PURSUIT,
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
