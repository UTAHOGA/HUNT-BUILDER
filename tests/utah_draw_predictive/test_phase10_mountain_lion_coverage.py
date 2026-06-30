import csv
import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase10_mountain_lion_coverage_matches_predictive_artifact() -> None:
    coverage = json.loads(Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8"))
    rows = _read_csv(Path(str(_repo_root() / "processed_data/mountain_lion_availability_predictions_v1.csv")))
    section = coverage["phase10_mountain_lion"]

    assert section["mountain_lion_cougar_in_scope"] is True
    assert section["mountain_lion_cougar_modeled_availability"] is True
    assert section["mountain_lion_cougar_still_pending_availability"] is False
    assert section["mountain_lion_cougar_active_predictive_row_count"] == len(rows)
    assert section["mountain_lion_cougar_hunt_code_count"] == len({row["hunt_code"] for row in rows})
    assert section["mountain_lion_cougar_unit_count"] == len({row["unit_name"] for row in rows})
    assert section["mountain_lion_cougar_p_draw_non_null_count"] == 0
    assert section["mountain_lion_cougar_p_availability_non_null_count"] == len(rows)

