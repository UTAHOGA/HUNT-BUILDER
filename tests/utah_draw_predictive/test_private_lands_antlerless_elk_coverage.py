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


def test_private_lands_antlerless_elk_coverage_fields_are_present() -> None:
    report = json.loads(
        Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8")
    )
    section = report["phase14_private_lands_antlerless_elk"]

    assert section["private_lands_only_antlerless_elk_in_scope"] is True
    assert section["private_lands_only_antlerless_elk_modeled"] is True
    assert section["private_lands_only_antlerless_elk_modeled_allocation"] is True
    assert section["private_lands_only_antlerless_elk_still_pending"] is False
    assert section["private_lands_only_antlerless_elk_active_predictive_row_count"] > 0
    assert section["private_lands_only_antlerless_elk_active_predictive_hunt_code_count"] > 0
    assert section["private_lands_only_antlerless_elk_modeled_allocation_row_count"] == section["private_lands_only_antlerless_elk_active_predictive_row_count"]
    assert section["private_lands_only_antlerless_elk_pending_row_count"] == 0
    assert section["private_lands_only_antlerless_elk_excluded_row_count"] == 0
    assert section["private_lands_only_antlerless_elk_p_draw_count"] == 0
