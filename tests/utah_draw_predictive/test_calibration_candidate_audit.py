import csv
from pathlib import Path

from engine.utah_draw_predictive.calibration_candidate_audit import (
    RAW_METHOD,
    ScoreRow,
    apply_method,
    decide_family,
    run_audit,
)


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _simple_run(tmp_path: Path, *, rows_per_year: int = 12) -> tuple[Path, Path]:
    run_root = tmp_path / "full_every_year_prediction_run_test"
    truth_rows: list[dict[str, object]] = []
    pred_fields = [
        "source_year",
        "target_year",
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "p_draw",
        "family",
    ]
    truth_fields = [
        "source_year",
        "target_year",
        "hunt_code",
        "residency",
        "point_value",
        "draw_system_type",
        "actual_p",
        "_calibration_policy",
    ]
    for source_year, target_year in ((2020, 2021), (2021, 2022), (2022, 2023)):
        pred_rows = []
        for idx in range(rows_per_year):
            code = f"DA{1000 + idx:04d}"
            point = idx % 6
            actual = 0.35 + (idx % 5) * 0.03
            pred = max(0.0, actual - 0.10)
            pred_rows.append(
                {
                    "source_year": source_year,
                    "target_year": target_year,
                    "hunt_code": code,
                    "residency": "Resident",
                    "points": point,
                    "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                    "p_draw": f"{pred:.6f}",
                    "family": "preference_antlerless_deer",
                }
            )
            truth_rows.append(
                {
                    "source_year": source_year,
                    "target_year": target_year,
                    "hunt_code": code,
                    "residency": "Resident",
                    "point_value": point,
                    "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                    "actual_p": f"{actual:.6f}",
                    "_calibration_policy": "CALIBRATION_SAFE",
                }
            )
        _write_csv(run_root / f"source_{source_year}_target_{target_year}" / "family_predictions.csv", pred_rows, pred_fields)
    truth_path = tmp_path / "truth.csv"
    _write_csv(truth_path, truth_rows, truth_fields)
    return run_root, truth_path


def test_audit_command_runs_without_writing_production_files(tmp_path):
    run_root, truth_path = _simple_run(tmp_path)
    before = _read_text(run_root / "source_2022_target_2023" / "family_predictions.csv")

    status = run_audit(None, run_root, truth_path, tmp_path / "audit")

    after = _read_text(run_root / "source_2022_target_2023" / "family_predictions.csv")
    assert status["CALIBRATION_CANDIDATE_AUDIT_COMPLETE"] is True
    assert status["production_calibration_applied"] is False
    assert status["repo_files_modified"] == 0
    assert before == after


def test_family_with_improved_metrics_but_failed_zero_preservation_is_blocked():
    rows = [
        ScoreRow(2021, 2020, f"DA{idx:04d}", "Resident", str(idx), "PREFERENCE_ANTLERLESS_DEER", 0.4, 0.3, "pred.csv")
        for idx in range(120)
    ]
    methods = [
        {
            "method": RAW_METHOD,
            "mae": 0.10,
            "rmse": 0.10,
            "bias": -0.10,
            "heldout_years": 3,
            "total_test_rows": 120,
            "years_mae_improved": 0,
            "max_year_mae_worsening": 0,
            "delta_mae_positive_is_better": 0,
            "delta_rmse_positive_is_better": 0,
            "delta_abs_bias_positive_is_better": 0,
        },
        {
            "method": "ZERO_PRESERVING_LINEAR_RECALIBRATION",
            "mae": 0.05,
            "rmse": 0.08,
            "bias": -0.02,
            "heldout_years": 3,
            "total_test_rows": 120,
            "years_mae_improved": 3,
            "max_year_mae_worsening": 0,
            "delta_mae_positive_is_better": 0.05,
            "delta_rmse_positive_is_better": 0.02,
            "delta_abs_bias_positive_is_better": 0.08,
        },
    ]

    decision = decide_family("PREFERENCE_ANTLERLESS_DEER", rows, methods, False, True)

    assert decision["decision"] == "BLOCKED_STRUCTURAL_ZERO_FAILURE"


def test_family_with_improved_bias_but_worse_mae_is_do_not_calibrate():
    rows = [
        ScoreRow(2021 + (idx % 3), 2020, f"DB{idx:04d}", "Resident", str(idx), "PREFERENCE_GENERAL_SEASON_BUCK_DEER", 0.4, 0.3, "pred.csv")
        for idx in range(120)
    ]
    methods = [
        {"method": RAW_METHOD, "mae": 0.10, "rmse": 0.10, "bias": -0.10},
        {
            "method": "ADDITIVE_BIAS_CORRECTION",
            "mae": 0.12,
            "rmse": 0.11,
            "bias": -0.02,
            "heldout_years": 3,
            "total_test_rows": 120,
            "years_mae_improved": 1,
            "max_year_mae_worsening": 0.04,
            "delta_mae_positive_is_better": -0.02,
            "delta_rmse_positive_is_better": -0.01,
            "delta_abs_bias_positive_is_better": 0.08,
        },
    ]

    decision = decide_family("PREFERENCE_GENERAL_SEASON_BUCK_DEER", rows, methods, False, False)

    assert decision["decision"] == "DO_NOT_CALIBRATE"


def test_family_with_fewer_than_minimum_rows_is_not_enough_score_history():
    rows = [
        ScoreRow(2021 + (idx % 3), 2020, f"DA{idx:04d}", "Resident", str(idx), "PREFERENCE_ANTLERLESS_DEER", 0.4, 0.3, "pred.csv")
        for idx in range(20)
    ]

    decision = decide_family("PREFERENCE_ANTLERLESS_DEER", rows, [], False, False)

    assert decision["decision"] == "NOT_ENOUGH_SCORE_HISTORY"


def test_antlerless_deer_zero_preserving_method_preserves_raw_zero():
    train = [
        ScoreRow(2020, 2019, "DA1000", "Resident", "0", "PREFERENCE_ANTLERLESS_DEER", 0.0, 0.0, "pred.csv"),
        ScoreRow(2020, 2019, "DA1001", "Resident", "1", "PREFERENCE_ANTLERLESS_DEER", 0.6, 0.5, "pred.csv"),
        ScoreRow(2020, 2019, "DA1002", "Resident", "2", "PREFERENCE_ANTLERLESS_DEER", 0.8, 0.7, "pred.csv"),
    ]
    test = [ScoreRow(2021, 2020, "DA1003", "Resident", "0", "PREFERENCE_ANTLERLESS_DEER", 0.2, 0.0, "pred.csv")]

    scored = apply_method("ZERO_PRESERVING_LINEAR_RECALIBRATION", train, test)

    assert scored == [(0.2, 0.0)]


def test_general_season_buck_deer_is_not_calibrated_from_current_evidence():
    rows = [
        ScoreRow(2021 + (idx % 3), 2020, f"DB{idx:04d}", "Resident", str(idx), "PREFERENCE_GENERAL_SEASON_BUCK_DEER", 0.4, 0.3, "pred.csv")
        for idx in range(120)
    ]
    methods = [
        {"method": RAW_METHOD, "mae": 0.10, "rmse": 0.10, "bias": 0.01},
        {
            "method": "HALF_ADDITIVE_BIAS_CORRECTION",
            "mae": 0.101,
            "rmse": 0.10,
            "bias": 0.005,
            "heldout_years": 3,
            "total_test_rows": 120,
            "years_mae_improved": 1,
            "max_year_mae_worsening": 0.02,
            "delta_mae_positive_is_better": -0.001,
            "delta_rmse_positive_is_better": 0,
            "delta_abs_bias_positive_is_better": 0.005,
        },
    ]

    decision = decide_family("PREFERENCE_GENERAL_SEASON_BUCK_DEER", rows, methods, False, False)

    assert decision["decision"] == "DO_NOT_CALIBRATE"


def test_output_json_says_production_calibration_applied_false(tmp_path):
    run_root, truth_path = _simple_run(tmp_path)
    audit_dir = tmp_path / "audit"

    run_audit(None, run_root, truth_path, audit_dir)

    assert '"production_calibration_applied": false' in _read_text(audit_dir / "calibration_candidate_audit_status.json")


def test_no_p_draw_overwrite_occurs(tmp_path):
    run_root, truth_path = _simple_run(tmp_path)
    prediction_file = run_root / "source_2020_target_2021" / "family_predictions.csv"
    before = _read_text(prediction_file)

    run_audit(None, run_root, truth_path, tmp_path / "audit")

    assert _read_text(prediction_file) == before
