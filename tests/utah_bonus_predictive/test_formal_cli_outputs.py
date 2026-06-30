import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _nonnull(rows: list[dict[str, str]], column: str) -> int:
    return sum(1 for row in rows if str(row.get(column) or "").strip() != "")


def test_formal_cli_generates_populated_artifacts(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.utah_bonus_predictive.materialize",
            "--output-dir",
            str(tmp_path),
            "--forecast-year",
            "2026",
            "--history-years",
            "2021,2022,2023,2024,2025",
            "--skip-upstream",
        ],
        cwd=REPO,
        check=True,
    )

    ml_path = tmp_path / "ml_draw_predictions_v1.csv"
    bt_path = tmp_path / "backtest_utah_bonus_draw.csv"
    successor_path = tmp_path / "draw_reality_engine_predictive_v2.csv"
    runtime_truth_path = tmp_path / "draw_reality_engine_v2.csv"
    report_path = tmp_path / "ml_draw_predictions_v1_report.json"
    coverage_json_path = tmp_path / "predictive_coverage_report.json"
    coverage_csv_path = tmp_path / "predictive_coverage_report.csv"
    dedicated_hunter_csv_path = tmp_path / "dedicated_hunter_predictions_v1.csv"
    dedicated_hunter_report_path = tmp_path / "dedicated_hunter_report.json"
    phase4_inventory_csv_path = tmp_path / "phase4_antlerless_validation_inventory.csv"
    phase4_inventory_json_path = tmp_path / "phase4_antlerless_validation_inventory.json"
    phase6_csv_path = tmp_path / "phase6_bonus_special_predictions_v1.csv"
    phase6_report_path = tmp_path / "phase6_bonus_special_report.json"
    turkey_csv_path = tmp_path / "turkey_bonus_predictions_v1.csv"
    turkey_report_path = tmp_path / "turkey_bonus_report.json"
    bear_csv_path = tmp_path / "bear_draw_predictions_v1.csv"
    bear_report_path = tmp_path / "bear_draw_report.json"
    bear_audit_csv_path = tmp_path / "bear_draw_odds_source_audit.csv"
    bear_audit_json_path = tmp_path / "bear_draw_odds_source_audit.json"
    sportsman_csv_path = tmp_path / "sportsman_permit_predictions_v1.csv"
    sportsman_report_path = tmp_path / "sportsman_permit_report.json"
    private_lands_csv_path = tmp_path / "private_lands_antlerless_elk_predictions_v1.csv"
    private_lands_report_path = tmp_path / "private_lands_antlerless_elk_report.json"
    youth_csv_path = tmp_path / "youth_draw_predictions_v1.csv"
    youth_report_path = tmp_path / "youth_draw_report.json"
    mountain_lion_csv_path = tmp_path / "mountain_lion_availability_predictions_v1.csv"
    mountain_lion_report_path = tmp_path / "mountain_lion_availability_report.json"
    manifest_path = tmp_path / "utah_bonus_predictive_manifest.json"

    assert ml_path.exists()
    assert bt_path.exists()
    assert successor_path.exists()
    assert runtime_truth_path.exists()
    assert report_path.exists()
    assert coverage_json_path.exists()
    assert coverage_csv_path.exists()
    assert dedicated_hunter_csv_path.exists()
    assert dedicated_hunter_report_path.exists()
    assert phase4_inventory_csv_path.exists()
    assert phase4_inventory_json_path.exists()
    assert phase6_csv_path.exists()
    assert phase6_report_path.exists()
    assert turkey_csv_path.exists()
    assert turkey_report_path.exists()
    assert bear_csv_path.exists()
    assert bear_report_path.exists()
    assert bear_audit_csv_path.exists()
    assert bear_audit_json_path.exists()
    assert sportsman_csv_path.exists()
    assert sportsman_report_path.exists()
    assert private_lands_csv_path.exists()
    assert private_lands_report_path.exists()
    assert youth_csv_path.exists()
    assert youth_report_path.exists()
    assert mountain_lion_csv_path.exists()
    assert mountain_lion_report_path.exists()
    assert manifest_path.exists()

    ml_rows = _read_csv(ml_path)
    bt_rows = _read_csv(bt_path)
    successor_rows = _read_csv(successor_path)
    dedicated_hunter_rows = _read_csv(dedicated_hunter_csv_path)
    phase6_rows = _read_csv(phase6_csv_path)
    turkey_rows = _read_csv(turkey_csv_path)
    bear_rows = _read_csv(bear_csv_path)
    bear_audit_rows = _read_csv(bear_audit_csv_path)
    sportsman_rows = _read_csv(sportsman_csv_path)
    private_lands_rows = _read_csv(private_lands_csv_path)
    youth_rows = _read_csv(youth_csv_path)
    mountain_lion_rows = _read_csv(mountain_lion_csv_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    dedicated_hunter_report = json.loads(dedicated_hunter_report_path.read_text(encoding="utf-8"))
    phase6_report = json.loads(phase6_report_path.read_text(encoding="utf-8"))
    turkey_report = json.loads(turkey_report_path.read_text(encoding="utf-8"))
    bear_report = json.loads(bear_report_path.read_text(encoding="utf-8"))
    bear_audit_report = json.loads(bear_audit_json_path.read_text(encoding="utf-8"))
    sportsman_report = json.loads(sportsman_report_path.read_text(encoding="utf-8"))
    private_lands_report = json.loads(private_lands_report_path.read_text(encoding="utf-8"))
    youth_report = json.loads(youth_report_path.read_text(encoding="utf-8"))
    mountain_lion_report = json.loads(mountain_lion_report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert ml_rows
    assert bt_rows
    assert successor_rows
    assert report["forecast_year"] == 2026
    assert report["source_years"] == "2021-2025"
    assert coverage["total_forecast_hunt_codes"] == len({row["hunt_code"] for row in ml_rows})
    assert "count_excluded_missing_model_input_or_not_in_predictive_draft" in coverage
    assert "active_eligible_codes_missing_from_forecast" in coverage
    assert dedicated_hunter_report["exists"] is True
    assert dedicated_hunter_report["total_rows"] == len(dedicated_hunter_rows)
    assert phase6_report["forecast_year"] == 2026
    assert phase6_report["total_phase6_rows"] == len(phase6_rows)
    assert turkey_report["forecast_year"] == 2026
    assert turkey_report["bonus_turkey_rows_active_predictive"] == len(turkey_rows)
    assert bear_report["forecast_year"] == 2026
    assert bear_report["bear_draw_active_predictive_row_count"] == len(bear_rows)
    assert len(bear_audit_rows) >= bear_audit_report["bear_hunt_codes_found_in_official_draw_odds_pdf"]
    assert any(row["appears_in_draw_odds_pdf"] == "no" for row in bear_audit_rows)
    assert sportsman_report["forecast_year"] == 2026
    assert sportsman_report["sportsman_rows_reviewed"] == len(sportsman_rows)
    assert private_lands_report["forecast_year"] == 2026
    assert private_lands_report["modeled_allocation_row_count"] == len(private_lands_rows)
    assert youth_report["forecast_year"] == 2026
    assert youth_report["active_predictive_youth_row_count"] == len(youth_rows)
    assert mountain_lion_report["forecast_year"] == 2026
    assert mountain_lion_report["total_mountain_lion_rows_produced"] == len(mountain_lion_rows)
    assert manifest["forecast_year"] == 2026
    assert manifest["calibration_metric_non_null_count"] == len(bt_rows)

    modeled_bonus_rows = [row for row in ml_rows if row.get("algorithm_status") == "MODELED_BONUS"]
    modeled_preference_rows = [row for row in ml_rows if row.get("algorithm_status") == "MODELED_PREFERENCE"]
    modeled_allocation_rows = [row for row in ml_rows if row.get("algorithm_status") == "MODELED_ALLOCATION"]
    modeled_availability_rows = [row for row in ml_rows if row.get("algorithm_status") == "MODELED_AVAILABILITY"]
    modeled_sportsman_rows = [row for row in ml_rows if row.get("algorithm_status") == "MODELED_SPORTSMAN_DRAW"]
    pending_rows = [row for row in ml_rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]
    dedicated_hunter_modeled_rows = [row for row in dedicated_hunter_rows if row.get("algorithm_status") == "MODELED_PREFERENCE"]
    assert modeled_bonus_rows
    assert _nonnull(modeled_bonus_rows, "p_draw") == len(modeled_bonus_rows)
    assert _nonnull(modeled_bonus_rows, "p_draw_pct") == len(modeled_bonus_rows)
    component_fields = {
        "p_prior_year_baseline",
        "p_quota_adjusted",
        "p_rollover_adjusted",
        "p_harvest_adjusted",
    }
    assert component_fields.issubset(ml_rows[0])
    assert component_fields.issubset(successor_rows[0])
    for field in component_fields:
        assert _nonnull(modeled_bonus_rows, field) == len(modeled_bonus_rows)
    positive_modeled_bonus_rows = [row for row in modeled_bonus_rows if float(row["p_draw"]) > 0.0]
    assert positive_modeled_bonus_rows
    assert all(
        row["display_odds_text"].startswith("~1 in ") and " or " in row["display_odds_text"]
        for row in positive_modeled_bonus_rows
    )
    assert modeled_preference_rows
    assert _nonnull(modeled_preference_rows, "p_preference_draw") == len(modeled_preference_rows)
    assert _nonnull(modeled_preference_rows, "p_draw") == len(modeled_preference_rows)
    assert _nonnull(modeled_preference_rows, "p_draw_pct") == len(modeled_preference_rows)
    assert all((row.get("p_preference_draw") or "") == (row.get("p_draw") or "") for row in modeled_preference_rows)
    assert all(str(row.get("p_draw") or "").strip() == "" for row in pending_rows)
    assert all(str(row.get("p_draw_pct") or "").strip() == "" for row in pending_rows)
    for field in component_fields:
        assert all(str(row.get(field) or "").strip() == "" for row in pending_rows)
    assert _nonnull(dedicated_hunter_modeled_rows, "p_preference_draw") == len(dedicated_hunter_modeled_rows)
    assert _nonnull([row for row in turkey_rows if row.get("algorithm_status") == "MODELED_BONUS"], "p_preference_draw") == 0
    assert all((row.get("p_preference_draw") or "") == (row.get("p_draw") or "") for row in dedicated_hunter_modeled_rows)
    assert _nonnull(dedicated_hunter_rows, "p_bonus_pool") == 0
    assert _nonnull(dedicated_hunter_rows, "p_random_pool") == 0
    assert _nonnull(modeled_preference_rows, "p_bonus_pool") == 0
    assert _nonnull(modeled_preference_rows, "p_random_pool") == 0
    if modeled_allocation_rows:
        assert _nonnull(modeled_allocation_rows, "p_draw") == 0
        assert _nonnull(modeled_allocation_rows, "p_draw_pct") == 0
        assert _nonnull(modeled_allocation_rows, "p_bonus_pool") == 0
        assert _nonnull(modeled_allocation_rows, "p_random_pool") == 0
        assert _nonnull(modeled_allocation_rows, "p_preference_draw") == 0
    assert modeled_availability_rows
    assert _nonnull(modeled_availability_rows, "p_draw") == 0
    assert _nonnull(modeled_availability_rows, "p_draw_pct") == 0
    assert _nonnull(modeled_availability_rows, "p_bonus_pool") == 0
    assert _nonnull(modeled_availability_rows, "p_random_pool") == 0
    assert _nonnull(modeled_availability_rows, "p_preference_draw") == 0
    assert all(
        any(str(row.get(field) or "").strip() for field in ("p_availability", "unit_status", "harvest_objective_status", "permit_availability_type"))
        for row in modeled_availability_rows
    )
    assert modeled_sportsman_rows
    assert _nonnull(modeled_sportsman_rows, "p_sportsman_draw") == len(modeled_sportsman_rows)
    assert _nonnull(modeled_sportsman_rows, "p_draw") == len(modeled_sportsman_rows)
    assert _nonnull(modeled_sportsman_rows, "p_draw_pct") == len(modeled_sportsman_rows)
    assert _nonnull(modeled_sportsman_rows, "p_bonus_pool") == 0
    assert _nonnull(modeled_sportsman_rows, "p_random_pool") == 0
    assert _nonnull(modeled_sportsman_rows, "p_preference_draw") == 0
    assert _nonnull(ml_rows, "source_years_used") == len(ml_rows)
    assert _nonnull(bt_rows, "calibration_error_by_probability_bucket") == len(bt_rows)

    keys = [(row["hunt_code"], row["draw_system_type"], row["residency"], row["points"]) for row in successor_rows]
    assert len(keys) == len(set(keys))


def test_formal_cli_source_year_traceability_fields(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.utah_bonus_predictive.materialize",
            "--output-dir",
            str(tmp_path),
            "--forecast-year",
            "2026",
            "--history-years",
            "2021,2022,2023,2024,2025",
            "--skip-upstream",
        ],
        cwd=REPO,
        check=True,
    )
    rows = _read_csv(tmp_path / "ml_draw_predictions_v1.csv")
    assert rows
    assert all(str(row.get("source_years_used") or "").strip() for row in rows)
    assert all(str(row.get("source_year_count") or "").strip() for row in rows)
    assert all(str(row.get("earliest_source_year") or "").strip() for row in rows)
    assert all(str(row.get("latest_source_year") or "").strip() for row in rows)
    assert any(row["source_years_used"] == "2021,2022,2023,2024,2025" for row in rows)
