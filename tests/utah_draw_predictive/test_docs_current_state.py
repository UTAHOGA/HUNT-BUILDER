from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_docs_current_state_reflects_completed_and_pending_phases() -> None:
    text = (REPO / "docs" / "utah_draw_system_scope.md").read_text(encoding="utf-8")

    for phrase in (
        "Formula and routing contract:",
        "## Target Scope",
        "## Out Of Scope",
        "## Classifier Values",
        "## Algorithm Status Values",
        "## Current Bonus Engine Usage",
        "## Categories Requiring Preference Or Other Strategy",
    ):
        assert phrase in text

    for draw_system_type in (
        "`BONUS_OIL_BIG_GAME`",
        "`BONUS_LE_BIG_GAME`",
        "`BONUS_PLE_BIG_GAME`",
        "`PREFERENCE_GENERAL_SEASON_BUCK_DEER`",
        "`PREFERENCE_DEDICATED_HUNTER_DEER`",
        "`PREFERENCE_ANTLERLESS_DEER`",
        "`PREFERENCE_ANTLERLESS_ELK`",
        "`PREFERENCE_DOE_PRONGHORN`",
        "`SPORTSMAN_PERMIT`",
        "`PRIVATE_LANDS_ONLY_ANTLERLESS_ELK`",
        "`YOUTH_DRAW_ONLY_ELK`",
        "`YOUTH_OTC_OR_AVAILABILITY`",
    ):
        assert draw_system_type in text

    assert "These categories must not use the OIL/LE/PLE bonus algorithm:" in text
    assert "`OUT_OF_SCOPE_NON_TARGET` rows stay in coverage and audit artifacts" in text
