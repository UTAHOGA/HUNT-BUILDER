from __future__ import annotations

from scripts.audit_draw_odds_pdf_page_roles import classify_hunt_type
from scripts.build_score_key_v2_truth_comparable_from_prediction_surface import comparable_source_family


def test_pdf_audit_keeps_youth_dedicated_hunter_separate() -> None:
    assert (
        classify_hunt_type(
            "",
            "2019_PERMITS=2020_MODEL__YOUTH_D.H._DEER_DRAW_RESULTS.pdf",
            "DB1500",
        )
        == "YOUTH_DEDICATED_HUNTER_DEER"
    )


def test_score_key_source_family_keeps_youth_dedicated_hunter_separate() -> None:
    row = {
        "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "draw_pool": "youth_dedicated_hunter",
        "source_file": "2019_PERMITS=2020_MODEL__YOUTH_D.H._DEER_DRAW_RESULTS.pdf",
        "hunt_code": "DB1500",
    }

    assert comparable_source_family(row) == "YOUTH_DEDICATED_HUNTER_DEER"
