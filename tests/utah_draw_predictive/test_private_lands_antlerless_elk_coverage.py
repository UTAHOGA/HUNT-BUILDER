import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


def test_private_lands_antlerless_elk_coverage_fields_are_present() -> None:
    report = json.loads(
        Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8")
    )
    section = report["phase14_private_lands_antlerless_elk"]

    assert section["private_lands_only_antlerless_elk_in_scope"] is True
    assert section["private_lands_only_antlerless_elk_modeled"] is True
    assert section["private_lands_only_antlerless_elk_modeled_capped_permits"] is True
    assert section["private_lands_only_antlerless_elk_still_pending"] is False
    assert section["private_lands_only_antlerless_elk_active_predictive_row_count"] > 0
    assert section["private_lands_only_antlerless_elk_active_predictive_hunt_code_count"] > 0
    assert section["private_lands_only_antlerless_elk_modeled_capped_permit_row_count"] == section["private_lands_only_antlerless_elk_active_predictive_row_count"]
    assert section["private_lands_only_antlerless_elk_pending_row_count"] == 0
    assert section["private_lands_only_antlerless_elk_excluded_row_count"] == 0
    assert section["private_lands_only_antlerless_elk_p_draw_count"] == 0
