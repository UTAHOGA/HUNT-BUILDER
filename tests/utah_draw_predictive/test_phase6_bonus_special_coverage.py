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


def test_phase6_bonus_special_coverage_report_fields_exist() -> None:
    report_path = Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    phase6 = report["phase6_bonus_special"]

    assert "cwmu_public_modeled_row_count" in phase6
    assert "cwmu_public_pending_row_count" in phase6
    assert "cwmu_private_excluded_row_count" in phase6
    assert "antlerless_moose_modeled_row_count" in phase6
    assert "ewe_bighorn_modeled_row_count" in phase6
