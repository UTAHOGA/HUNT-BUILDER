from __future__ import annotations

import csv
import json
from pathlib import Path

from engine.utah_draw_predictive.certification import (
    CERTIFIED,
    EXPERIMENTAL,
    INSUFFICIENT,
    annotate_prediction_rows,
    certification_design_for_row,
)
from scripts.build_blind_acceptance_review import build_design_rows, load_actual_gap_fold
from scripts.build_prediction_family_certification_registry import build_registry
from scripts.promote_certified_prediction_candidate import validate_certification_publication_gate


THRESHOLDS = {
    "minimum_independent_following_year_folds": 2,
    "minimum_joined_rows_per_design": 400,
    "maximum_mae": 0.10,
    "maximum_p90_absolute_error": 0.30,
    "maximum_tail_error_rate_over_25pp": 0.10,
    "maximum_false_guarantee_rows": 0,
    "required_unclassified_actual_gaps": 0,
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_acceptance_review_blocks_unclassified_scoreable_actual_gap(tmp_path: Path) -> None:
    gap_path = tmp_path / "draw_line_aware_actual_ladder_scoring_rows.csv"
    _write_csv(
        gap_path,
        [
            {
                "fold": "",
                "draw_design_key": "BONUS_OIL_BIG_GAME",
                "hunt_code": "MB1001",
                "scoring_decision": "missing_prediction_for_scoreable_actual_ladder_row",
                "actual_gap_classification": "",
            }
        ],
    )
    gaps, classification_path = load_actual_gap_fold("2023_to_2024", gap_path)
    assert classification_path == ""
    scored = [
        {
            "fold": "2022_to_2023",
            "draw_design": "BONUS_OIL_BIG_GAME",
            "absolute_error": 0.01,
            "tail_error_over_25pp": False,
            "false_guarantee": False,
        },
        {
            "fold": "2023_to_2024",
            "draw_design": "BONUS_OIL_BIG_GAME",
            "absolute_error": 0.01,
            "tail_error_over_25pp": False,
            "false_guarantee": False,
        },
    ] * 200
    result = build_design_rows(scored, gaps)[0]
    assert result["acceptance_status"] == "NOT_ACCEPTED"
    assert result["unclassified_actual_gap_rows"] == 1
    assert "UNCLASSIFIED_ACTUAL_GAPS" in result["failure_reasons"]


def test_registry_recomputes_certified_experimental_and_insufficient_statuses(tmp_path: Path) -> None:
    review = tmp_path / "review"
    review.mkdir()
    (review / "acceptance_review_manifest.json").write_text(
        json.dumps({"acceptance_standard": "ADR-0006", "thresholds": THRESHOLDS}),
        encoding="utf-8",
    )
    fields = {
        "independent_following_year_folds": "2022_to_2023;2023_to_2024",
        "fold_count": "2",
        "joined_rows": "400",
        "mae": "0.05",
        "rmse": "0.1",
        "p90_absolute_error": "0.2",
        "tail_error_rows_over_25pp": "20",
        "tail_error_rate_over_25pp": "0.05",
        "false_guarantee_rows": "0",
        "classified_actual_gap_rows": "0",
        "unclassified_actual_gap_rows": "0",
        "acceptance_status": "ACCEPTED",
        "failure_reasons": "",
    }
    _write_csv(
        review / "acceptance_by_draw_design.csv",
        [
            {"draw_design": "BONUS_OIL_BIG_GAME", **fields},
            {
                "draw_design": "BONUS_LE_BIG_GAME",
                **fields,
                "mae": "0.11",
                "acceptance_status": "NOT_ACCEPTED",
                "failure_reasons": "MAE_EXCEEDS_LIMIT",
            },
            {
                "draw_design": "YOUTH_GENERAL_ANY_BULL_ELK",
                **fields,
                "joined_rows": "16",
                "acceptance_status": "NOT_ACCEPTED",
                "failure_reasons": "INSUFFICIENT_JOINED_ROWS",
            },
        ],
    )
    registry = build_registry(review)
    assert registry["families"]["BONUS_OIL_BIG_GAME"]["certification_status"] == CERTIFIED
    assert registry["families"]["BONUS_LE_BIG_GAME"]["certification_status"] == EXPERIMENTAL
    assert registry["families"]["YOUTH_GENERAL_ANY_BULL_ELK"]["certification_status"] == INSUFFICIENT


def test_row_annotation_separates_bear_subtypes_and_withholds_uncertified_odds() -> None:
    registry = {
        "registry_id": "test-registry",
        "evidence": {"acceptance_by_draw_design": "audit/review.csv"},
        "families": {
            "BEAR_LIMITED_ENTRY_HUNT_BONUS": {
                "certification_status": EXPERIMENTAL,
                "failure_reasons": "MAE_EXCEEDS_LIMIT",
            },
            "BONUS_OIL_BIG_GAME": {
                "certification_status": CERTIFIED,
                "failure_reasons": "",
            },
        },
    }
    rows = [
        {
            "draw_system_type": "BEAR_DRAW",
            "bear_draw_subtype": "LIMITED_ENTRY_BEAR_HUNT",
            "p_draw": "0.75",
            "p_draw_pct": "75",
            "guaranteed_at_2026": "12",
        },
        {
            "draw_system_type": "BONUS_OIL_BIG_GAME",
            "p_draw_mean": "0.25",
            "display_odds_pct": "25",
            "projected_2026_max_cutoff_point": "20",
        },
    ]
    report = annotate_prediction_rows(rows, registry)
    assert certification_design_for_row(rows[0]) == "BEAR_LIMITED_ENTRY_HUNT_BONUS"
    assert rows[0]["certified_p_draw"] == ""
    assert rows[0]["projected_draw_line_2026"] == "12"
    assert rows[1]["certified_p_draw"] == "0.25"
    assert rows[1]["certified_p_draw_pct"] == "25"
    assert report["certification_status_counts"] == {CERTIFIED: 1, EXPERIMENTAL: 1}


def test_certified_design_does_not_publish_display_only_zero_placeholder() -> None:
    registry = {
        "registry_id": "test-registry",
        "evidence": {"acceptance_by_draw_design": "audit/review.csv"},
        "families": {
            "BONUS_PLE_BIG_GAME": {
                "certification_status": CERTIFIED,
                "failure_reasons": "",
            }
        },
    }
    rows = [
        {
            "draw_system_type": "BONUS_PLE_BIG_GAME",
            "status": "DISPLAY ONLY - NO FORECASTED APPLICANT COHORT",
            "p_draw": "0.000000",
            "p_draw_mean": "0.000000",
            "p_draw_pct": "0.000",
        }
    ]

    annotate_prediction_rows(rows, registry)

    assert rows[0]["prediction_certification_status"] == CERTIFIED
    assert rows[0]["certified_p_draw"] == ""
    assert rows[0]["certified_p_draw_mean"] == ""
    assert rows[0]["certified_p_draw_pct"] == ""


def test_local_promotion_gate_rejects_public_probability_on_uncertified_row(tmp_path: Path) -> None:
    path = tmp_path / "predictions.csv"
    common = {
        "prediction_certification_design": "BONUS_LE_BIG_GAME",
        "prediction_certification_status": EXPERIMENTAL,
        "prediction_publication_status": "EXPERIMENTAL_PROBABILITY_WITHHELD",
        "certified_p_draw_mean": "",
        "certified_p_draw_pct": "",
    }
    _write_csv(path, [{**common, "certified_p_draw": "0.4"}])
    result = validate_certification_publication_gate(path)
    assert result["status"] == "BLOCKED"
    assert result["unauthorized_public_probability_rows"] == 1


def test_current_registry_certifies_only_designs_that_pass_coverage_and_metric_gates() -> None:
    registry = json.loads(Path("governance/prediction-family-certification.json").read_text(encoding="utf-8"))
    expected_certified = {
        "BONUS_LE_BIG_GAME": {"fold_count": 8, "joined_rows": 49_916},
        "BONUS_OIL_BIG_GAME": {"fold_count": 8, "joined_rows": 34_330},
        "BONUS_PLE_BIG_GAME": {"fold_count": 5, "joined_rows": 1_912},
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER": {"fold_count": 8, "joined_rows": 7_783},
    }
    assert registry["certified_designs"] == list(expected_certified)
    for design, expected in expected_certified.items():
        family = registry["families"][design]
        assert family["certification_status"] == CERTIFIED
        assert family["fold_count"] == expected["fold_count"]
        assert family["joined_rows"] == expected["joined_rows"]
        assert family["mae"] < THRESHOLDS["maximum_mae"]
        assert family["p90_absolute_error"] < THRESHOLDS["maximum_p90_absolute_error"]
        assert family["tail_error_rate_over_25pp"] < THRESHOLDS["maximum_tail_error_rate_over_25pp"]
        assert family["false_guarantee_rows"] == 0
        assert family["unclassified_actual_gap_rows"] == 0
