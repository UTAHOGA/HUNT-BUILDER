from engine.utah_draw_predictive.bear import (
    RESTRICTED_BEAR_PURSUIT,
    UNLIMITED_PURSUIT_PERMIT,
    classify_bear_subtype,
)


def _pursuit_row(hunt_code: str) -> dict[str, str]:
    return {
        "hunt_code": hunt_code,
        "hunt_name": "Black Bear Pursuit",
        "species": "Black Bear",
        "hunt_type": "Pursuit",
        "weapon": "Pursuit Only",
        "year": "2026",
    }


def test_bear_pursuit_rows_are_classified_by_source_not_hunt_name_only() -> None:
    for hunt_code in {"BR1008", "BR1009", "BR1010", "BR1011", "BR1012", "BR1013", "BR1015", "BR1016", "BR1017"}:
        assert classify_bear_subtype(_pursuit_row(hunt_code)) == RESTRICTED_BEAR_PURSUIT

    for hunt_code in {"BR1007", "BR1018"}:
        assert classify_bear_subtype(_pursuit_row(hunt_code)) == UNLIMITED_PURSUIT_PERMIT
