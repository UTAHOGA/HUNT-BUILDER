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


def test_phase7_turkey_report_semantics_are_explicit() -> None:
    report_path = Path(str(_repo_root() / "processed_data/turkey_bonus_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    required_fields = {
        "turkey_rows_seen_total",
        "turkey_rows_seen_observed_history",
        "turkey_rows_seen_active_predictive",
        "turkey_rows_forecast_eligible",
        "bonus_turkey_rows_active_predictive",
        "bonus_turkey_modeled_rows",
        "bonus_turkey_pending_rows",
        "bonus_turkey_modeled_hunt_codes",
        "general_season_turkey_excluded_rows",
        "remaining_turkey_excluded_or_availability_rows",
        "non_public_turkey_excluded_rows",
        "unsupported_or_ambiguous_turkey_rows",
        "p_bonus_pool_non_null_count",
        "p_random_pool_non_null_count",
        "p_draw_non_null_count",
        "p_draw_pct_non_null_count",
        "p_preference_draw_non_null_count",
        "duplicate_key_count",
    }
    assert required_fields.issubset(report)
    assert "total_turkey_rows_reviewed" not in report
    assert report["turkey_rows_seen_total"] == report["turkey_rows_seen_observed_history"] + report["turkey_rows_seen_active_predictive"]
    assert report["bonus_turkey_rows_active_predictive"] == report["bonus_turkey_modeled_rows"] + report["bonus_turkey_pending_rows"]
    assert report["p_preference_draw_non_null_count"] == 0

