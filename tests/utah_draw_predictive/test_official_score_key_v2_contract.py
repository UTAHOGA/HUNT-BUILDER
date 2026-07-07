from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from engine.utah_draw_predictive.run_all_families import _with_run_fields
from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import main as scorer_main


REQUIRED_COLUMNS = {
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "official_score_key_v2",
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_summary(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("residency", "expected_scope", "expected_residency"),
    [
        ("", "TOTAL", ""),
        ("Resident", "RESIDENT", "Resident"),
        ("Nonresident", "NONRESIDENT", "Nonresident"),
        ("Non-Resident", "NONRESIDENT", "Nonresident"),
    ],
)
def test_family_predictions_emit_score_key_v2_columns_and_exact_key(residency: str, expected_scope: str, expected_residency: str) -> None:
    row = {
        "hunt_code": "DB0007",
        "hunt_name": "Sportsman Deer",
        "species": "Deer",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "residency": residency,
        "points": "0",
        "p_draw": "0.500000",
    }

    output = _with_run_fields([row], 2018, 2019, "sportsman")[0]

    assert REQUIRED_COLUMNS.issubset(output.keys())
    assert output["score_scope"] == expected_scope
    assert output["residency"] == expected_residency
    assert output["source_family"] == "SPORTSMAN"
    assert output["probability_metric"] == "p_draw"
    assert output["official_score_key_v2"] == "|".join(
        [
            "2019",
            "SPORTSMAN",
            "SPORTSMAN_RANDOM_ONLY",
            "random",
            "DB0007",
            expected_scope,
            expected_residency,
            "0",
            "p_draw",
        ]
    )


def test_scorer_cli_accepts_required_args_and_scores_synthetic_rows(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    base_row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
    }

    _write_csv(
        prediction_file,
        [
            {
                **base_row,
                "p_draw": "0.400000",
            }
        ],
    )
    _write_csv(
        truth_file,
        [
            {
                **base_row,
                "p_draw": "0.250000",
            }
        ],
    )

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 0

    summary = _read_summary(output_dir / "official_score_key_v2_summary.json")
    assert summary["joined_rows"] == 1
    assert summary["unmatched_prediction_rows"] == 0
    assert summary["unmatched_truth_rows"] == 0
    assert summary["calibration_applied"] is False
    assert summary["mae"] == "0.1500000000"
    assert summary["rmse"] == "0.1500000000"
    assert summary["bias"] == "0.1500000000"


def test_scorer_blocks_duplicate_prediction_keys(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
        "p_draw": "0.400000",
    }

    _write_csv(prediction_file, [row, row])
    _write_csv(truth_file, [row])

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 2


def test_scorer_blocks_duplicate_truth_keys(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
        "p_draw": "0.250000",
    }

    _write_csv(prediction_file, [row])
    _write_csv(truth_file, [row, row])

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 2
