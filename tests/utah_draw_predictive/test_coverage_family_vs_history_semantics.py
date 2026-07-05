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


def test_coverage_family_vs_history_semantics_are_precise() -> None:
    report_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    answers = report["answers"]

    assert "are_all_oil_big_game_categories_modeled" not in answers
    assert "are_all_le_big_game_categories_modeled" not in answers
    assert "are_all_ple_big_game_categories_modeled" not in answers

    assert answers["oil_big_game_engine_family_modeled"] is True
    assert answers["le_big_game_engine_family_modeled"] is True
    assert answers["ple_big_game_engine_family_modeled"] is True
    assert "oil_big_game_unmodeled_seen_hunt_code_count" in answers
    assert "le_big_game_unmodeled_seen_hunt_code_count" in answers
    assert "ple_big_game_unmodeled_seen_hunt_code_count" in answers

    family_semantics = report["family_modeling_semantics"]
    assert family_semantics["bonus_oil_big_game"]["active_predictive_coverage_complete"] is True
    assert family_semantics["bonus_le_big_game"]["active_predictive_coverage_complete"] is True
    assert family_semantics["bonus_ple_big_game"]["active_predictive_coverage_complete"] is True
