from __future__ import annotations

import csv
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ML_PATH = REPO / "processed_data" / "ml_draw_predictions_v1.csv"
COVERAGE_PATH = REPO / "processed_data" / "draw_system_coverage_report.json"
GPT_REVIEW_PATH = REPO / "processed_data" / "gpt_work_review_report.json"
FRONTEND_PATH = REPO / "hunt-research.js"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: object) -> str:
    return str(value or "").strip()


def _out_of_scope_rows() -> list[dict[str, str]]:
    return [row for row in _read_csv(ML_PATH) if row.get("algorithm_status") == "OUT_OF_SCOPE_NON_TARGET"]


def test_out_of_scope_non_target_rows_have_no_probability_fields() -> None:
    rows = _out_of_scope_rows()
    for field in ("p_draw", "p_draw_pct", "p_preference_draw", "p_bonus_pool", "p_random_pool"):
        assert all(_clean(row.get(field)) == "" for row in rows)


def test_out_of_scope_non_target_rows_excluded_from_normal_prediction_ui_output() -> None:
    text = FRONTEND_PATH.read_text(encoding="utf-8")
    assert "SHOW_AUDIT_ONLY_ROWS" in text
    assert "function isOutOfScopeNonTargetRow(row)" in text
    assert "Out of scope / not a target prediction category" in text
    assert "rawEngineRows.filter((row) => !isOutOfScopeNonTargetRow(row))" in text
    assert "onlyOutOfScopeRowsHidden" in text
    assert "hidden from the standard Hunt Research view" in text


def test_out_of_scope_non_target_rows_remain_visible_in_coverage_reports() -> None:
    coverage = _read_json(COVERAGE_PATH)
    gpt_review = _read_json(GPT_REVIEW_PATH)
    rows = _out_of_scope_rows()
    predictive_counts = coverage["counts_by_algorithm_status_by_source_dataset"]["active_predictive"]
    assert "OUT_OF_SCOPE_NON_TARGET" in coverage["out_of_scope_non_target_categories"]
    assert predictive_counts.get("OUT_OF_SCOPE_NON_TARGET", 0) == len(rows)
    assert gpt_review["row_counts"]["OUT_OF_SCOPE_NON_TARGET"] == len(rows)


def test_target_scope_pending_rows_are_not_incorrectly_marked_out_of_scope() -> None:
    rows = _read_csv(ML_PATH)
    assert not [
        row for row in rows
        if row.get("draw_system_type") in {
            "YOUTH_GENERAL_DEER_RESERVE",
            "YOUTH_ANTLERLESS_OR_DOE_RESERVE",
            "YOUTH_GENERAL_ANY_BULL_ELK",
            "YOUTH_OTC_OR_AVAILABILITY",
            "YOUTH_TURKEY_SET_ASIDE",
        }
        and row.get("algorithm_status") == "OUT_OF_SCOPE_NON_TARGET"
    ]
    assert not [
        row for row in rows
        if row.get("hunt_code") in {"EB3147", "EB3150", "EB3153"}
        and row.get("algorithm_status") == "OUT_OF_SCOPE_NON_TARGET"
    ]
