import json
from pathlib import Path

from engine.utah_draw_predictive.classifier import build_draw_system_coverage_report


def test_draw_system_coverage_report_generation(tmp_path: Path) -> None:
    artifacts = build_draw_system_coverage_report(tmp_path, forecast_year=2026, history_years=[2021, 2022, 2023, 2024, 2025])
    csv_path = artifacts["csv"]
    json_path = artifacts["json"]
    assert csv_path.exists()
    assert json_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["forecast_year"] == 2026
    assert report["answers"]["is_general_season_buck_deer_modeled"] is True
    assert report["answers"]["is_dedicated_hunter_deer_modeled"] is True
    assert "PREFERENCE_GENERAL_SEASON_BUCK_DEER" in report["modeled_preference_categories"]
    assert "PREFERENCE_DEDICATED_HUNTER_DEER" in report["modeled_preference_categories"]
    assert "PREFERENCE_ANTLERLESS_DEER" in report["modeled_preference_categories"]
    assert "PREFERENCE_ANTLERLESS_ELK" in report["modeled_preference_categories"]
    assert "PREFERENCE_DOE_PRONGHORN" in report["modeled_preference_categories"]
    assert report["answers"]["is_bear_modeled"] is True
    assert report["answers"]["is_turkey_modeled"] is True
    assert report["answers"]["is_mountain_lion_cougar_modeled"] is True
    assert report["answers"]["oil_big_game_engine_family_modeled"] is True
    assert report["answers"]["le_big_game_engine_family_modeled"] is True
    assert report["answers"]["ple_big_game_engine_family_modeled"] is True
    assert "BONUS_TURKEY" in report["modeled_bonus_categories"]
    assert "BEAR_DRAW" in report["modeled_bonus_categories"]
    assert report["answers"]["is_cwmu_public_modeled"] is False
    assert "BONUS_CWMU_BIG_GAME" in report["modeled_bonus_categories"]
    assert "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK" in report["modeled_allocation_categories"]
    assert "MOUNTAIN_LION_DRAW" in report["modeled_availability_categories"]
    assert report["modeled_availability"]["modeled_availability_total_row_count"] >= 0
    assert report["modeled_availability"]["modeled_availability_pass"] is True
    assert "BONUS_OIL_BIG_GAME" in report["modeled_bonus_categories"]
    assert "OUT_OF_SCOPE_NON_TARGET" in report["out_of_scope_non_target_categories"]
