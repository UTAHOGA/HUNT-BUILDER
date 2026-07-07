from pathlib import Path

from engine.utah_draw_predictive.run_all_families import _family_prediction_status
from tools.certify_engine_prediction_truth import write_summary


def test_youth_turkey_empty_rows_are_no_rows_not_classified() -> None:
    status, blocker = _family_prediction_status(
        "youth_turkey",
        [],
        {"youth_turkey_rows_seen_observed_history": 0},
    )

    assert status == "FAIL"
    assert blocker == "NO_ROWS"


def test_certifier_rejects_classified_rows_without_special_exemption(tmp_path: Path) -> None:
    repo = tmp_path
    output_dir = tmp_path / "cert"
    progressive_dir = tmp_path / "progressive"
    counts_rows = [
        {
            "source_year": 2018,
            "target_year": 2019,
            "family": "youth_turkey",
            "status": "CLASSIFIED",
            "blocker_if_failed": "SOURCE_NOT_AVAILABLE_NO_PROVEN_YOUTH_TURKEY_HISTORY",
        }
    ]

    summary = write_summary(
        repo,
        output_dir,
        progressive_dir,
        [2019],
        counts_rows,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    assert summary["pass_condition"] is False
    assert summary["classification"] == "ENGINE_CERTIFIED_PREDICTION_TRUTH_BLOCKED"
    assert summary["classified_family_year_rows"] == 1
