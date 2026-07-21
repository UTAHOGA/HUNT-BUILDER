from __future__ import annotations

from engine.utah_draw_predictive.run_all_families import _suppress_youth_turkey_for_source_year
from scripts.run_full_engine_all_year_validation import _classified_reconciliation_for_row


def test_youth_turkey_is_suppressed_before_2019_program_start() -> None:
    assert _suppress_youth_turkey_for_source_year(2017) is True
    assert _suppress_youth_turkey_for_source_year(2018) is True


def test_youth_turkey_is_not_suppressed_after_2018() -> None:
    assert _suppress_youth_turkey_for_source_year(2019) is False


def test_youth_turkey_pre_2019_classification_is_not_a_clean_run_blocker() -> None:
    reconciliation = _classified_reconciliation_for_row(
        {
            "source_year": "2018",
            "target_year": "2019",
            "family": "youth_turkey",
            "blocker_if_failed": "SOURCE_NOT_AVAILABLE_NO_PROVEN_YOUTH_TURKEY_HISTORY",
        }
    )

    assert reconciliation["reconciliation_bucket"] == "PRE_PROGRAM_START_NOT_APPLICABLE"
    assert reconciliation["clean_run_blocker"] == "false"
    assert reconciliation["release_blocker"] == "false"
