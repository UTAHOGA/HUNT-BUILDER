from engine.utah_draw_predictive.bear import (
    RESTRICTED_BEAR_PURSUIT,
    classify_bear_subtype,
    is_supported_bear_bonus_row,
)


def test_public_restricted_pursuit_bear_rows_can_be_modeled_bonus() -> None:
    for hunt_code in {"BR1008", "BR1009", "BR1010", "BR1011", "BR1012", "BR1013", "BR1015", "BR1016", "BR1017"}:
        row = {
            "hunt_code": hunt_code,
            "hunt_name": "Black Bear Restricted Pursuit",
            "species": "Black Bear",
            "hunt_type": "Pursuit",
            "weapon": "Pursuit Only",
            "year": "2026",
        }
        assert classify_bear_subtype(row) == RESTRICTED_BEAR_PURSUIT
        assert is_supported_bear_bonus_row(row)
