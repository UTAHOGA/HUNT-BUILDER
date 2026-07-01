import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


def test_mountain_lion_availability_semantics_are_reported_by_family_status() -> None:
    report_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    section = report["phase10_mountain_lion"]
    assert section["mountain_lion_cougar_in_scope"] is True
    assert section["mountain_lion_cougar_modeled_availability"] is False
    assert section["mountain_lion_cougar_reference_license_based_no_draw"] is True
    assert section["mountain_lion_cougar_still_pending_availability"] is False
    assert section["mountain_lion_cougar_modeled"] is False
    assert section["mountain_lion_cougar_still_pending"] is False
    assert section["mountain_lion_cougar_strategy_status"] == "REFERENCE_LICENSE_BASED_NO_DRAW"
    assert section["mountain_lion_cougar_active_predictive_row_count"] > 0
    assert section["mountain_lion_cougar_hunt_code_count"] > 0
    assert section["mountain_lion_cougar_unit_count"] > 0
    assert section["mountain_lion_cougar_p_draw_non_null_count"] == 0
