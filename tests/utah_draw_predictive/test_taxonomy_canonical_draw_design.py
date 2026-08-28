from engine.utah_draw_predictive.taxonomy import canonical_draw_design, effective_draw_design


def test_removes_legacy_bonus_split_modifier() -> None:
    assert canonical_draw_design("BONUS_LE_BIG_GAME;MAX_WEIGHTED_SPLIT") == "BONUS_LE_BIG_GAME"


def test_removes_reference_only_modifier_when_primary_design_exists() -> None:
    assert canonical_draw_design("PREFERENCE_ANTLERLESS_ELK;REFERENCE_ONLY") == "PREFERENCE_ANTLERLESS_ELK"


def test_cwmu_bonus_overlay_routes_to_cwmu_family() -> None:
    assert canonical_draw_design("BONUS_CWMU_BIG_GAME;BONUS_OIL_BIG_GAME;MAX_WEIGHTED_SPLIT") == "BONUS_CWMU_BIG_GAME"


def test_cwmu_antlerless_row_keeps_preference_parent_design() -> None:
    assert canonical_draw_design("BONUS_CWMU_BIG_GAME;PREFERENCE_ANTLERLESS_ELK") == "PREFERENCE_ANTLERLESS_ELK"


def test_effective_design_prefers_source_facing_draw_design() -> None:
    assert effective_draw_design(
        {
            "draw_design": "BEAR_DRAW;MAX_WEIGHTED_SPLIT",
            "draw_system_type": "REFERENCE_ONLY",
        }
    ) == "BEAR_DRAW"
