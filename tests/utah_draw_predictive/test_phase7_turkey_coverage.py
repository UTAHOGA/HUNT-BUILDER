import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    for candidate in [repo_root, *repo_root.parents]:
        if (
            (candidate / "AGENTS.MD").exists()
            and (candidate / "engine").is_dir()
            and (candidate / "processed_data").is_dir()
        ):
            return candidate
    raise RuntimeError("Could not locate HUNT-BUILDER repo root")


def test_phase7_turkey_coverage_report_fields_exist() -> None:
    report_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase7 = report["phase7_turkey"]

    assert "turkey_rows_seen_total" in phase7
    assert "turkey_rows_seen_active_predictive" in phase7
    assert "turkey_rows_seen_observed_history" in phase7
    assert "turkey_modeled_bonus_rows_active_predictive" in phase7
    assert "turkey_in_scope_model_pending_rows_active_predictive" in phase7
    assert "turkey_in_scope_model_pending_rows_observed_history" in phase7
    assert "general_season_turkey_excluded" in phase7
    assert "remaining_turkey_excluded_or_availability_pending" in phase7
