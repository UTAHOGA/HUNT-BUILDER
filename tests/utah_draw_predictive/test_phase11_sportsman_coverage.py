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


def test_phase11_sportsman_coverage_reports_modeled_source_driven_rows() -> None:
    report = json.loads(
        Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8")
    )

    summary = report["phase11_sportsman"]
    assert report["answers"]["sportsman_in_scope"] is True
    assert report["answers"]["is_sportsman_modeled"] is True
    assert summary["sportsman_in_scope"] is True
    assert summary["sportsman_modeled"] is True
    assert summary["sportsman_row_count"] == 10
    assert summary["sportsman_modeled_row_count"] == 10
    assert summary["sportsman_pending_row_count"] == 0
    assert summary["sportsman_hunt_code_count"] == 10
    assert summary["br1000_classified_as_sportsman_permit"] is True
    assert summary["db0007_classified_as_sportsman_permit"] is True
    assert summary["rs0001_classified_as_sportsman_permit"] is True
    assert summary["tk0001_classified_as_sportsman_permit"] is True
    assert summary["sportsman_rows_with_p_bonus_pool_non_null"] == 0
    assert summary["sportsman_rows_with_p_random_pool_non_null"] == 0
    assert summary["sportsman_rows_with_p_preference_draw_non_null"] == 0
