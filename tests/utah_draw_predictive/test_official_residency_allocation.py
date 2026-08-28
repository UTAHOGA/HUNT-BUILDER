from engine.utah_draw_predictive.permit_accessors import (
    OFFICIAL_10_PERCENT_TOTAL_ALLOCATION,
    OFFICIAL_EXPLICIT_RESIDENCY_SPLIT,
    UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE,
    target_residency_permit_allocation,
)


def test_explicit_residency_split_overrides_total_percentage() -> None:
    allocation = target_residency_permit_allocation(
        {
            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "permits_2026_total": "100",
            "permits_2026_res": "95",
            "permits_2026_nr": "5",
        },
        2026,
    )

    assert allocation.supported is True
    assert allocation.authority == OFFICIAL_EXPLICIT_RESIDENCY_SPLIT
    assert allocation.resident == 95
    assert allocation.nonresident == 5


def test_standard_big_game_total_uses_official_ten_percent_allocation() -> None:
    allocation = target_residency_permit_allocation(
        {
            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "permits_2026_total": "1160",
        },
        2026,
    )

    assert allocation.supported is True
    assert allocation.authority == OFFICIAL_10_PERCENT_TOTAL_ALLOCATION
    assert allocation.resident == 1044
    assert allocation.nonresident == 116


def test_ten_percent_allocation_uses_integer_half_up_rounding() -> None:
    five = target_residency_permit_allocation(
        {"draw_system_type": "PREFERENCE_ANTLERLESS_DEER", "permits_2026_total": "5"},
        2026,
    )
    fifteen = target_residency_permit_allocation(
        {"draw_system_type": "PREFERENCE_ANTLERLESS_ELK", "permits_2026_total": "15"},
        2026,
    )

    assert (five.resident, five.nonresident) == (4, 1)
    assert (fifteen.resident, fifteen.nonresident) == (13, 2)


def test_total_only_special_families_require_explicit_hunt_level_split() -> None:
    for draw_system_type in (
        "BEAR_DRAW;MAX_WEIGHTED_SPLIT",
        "BONUS_TURKEY",
        "BONUS_OIL_BIG_GAME",
        "BONUS_CWMU_BIG_GAME",
        "SPORTSMAN_RANDOM_ONLY",
        "AVAILABILITY_ONLY",
        "REFERENCE_ONLY",
    ):
        allocation = target_residency_permit_allocation(
            {"draw_system_type": draw_system_type, "permits_2026_total": "20"},
            2026,
        )

        assert allocation.supported is False
        assert allocation.authority == UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE
        assert allocation.resident == 0
        assert allocation.nonresident == 0


def test_cwmu_text_blocks_percentage_even_with_stale_preference_label() -> None:
    allocation = target_residency_permit_allocation(
        {
            "draw_system_type": "PREFERENCE_ANTLERLESS_ELK",
            "hunt_class": "CWMU Contact Operator",
            "permits_2026_total": "50",
        },
        2026,
    )

    assert allocation.supported is False
    assert allocation.authority == UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE

