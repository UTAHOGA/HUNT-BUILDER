import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


def test_phase6_bonus_special_coverage_report_fields_exist() -> None:
    report_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase6 = report["phase6_bonus_special"]

    assert "cwmu_public_modeled_row_count" in phase6
    assert "cwmu_public_pending_row_count" in phase6
    assert "cwmu_private_excluded_row_count" in phase6
    assert "antlerless_moose_modeled_row_count" in phase6
    assert "ewe_bighorn_modeled_row_count" in phase6
