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


def test_phase8_bear_coverage_matches_predictive_artifact() -> None:
    coverage = json.loads(Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8"))
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_draw_predictions_v1.csv")))
    phase8 = coverage["phase8_bear"]

    modeled = [row for row in rows if row.get("algorithm_status") == "MODELED_BONUS"]
    pending = [row for row in rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]
    excluded = [row for row in rows if row.get("algorithm_status") == "EXCLUDED_NOT_PREDICTIVE_DRAW"]

    assert phase8["bear_modeled"] is True
    assert phase8["bear_draw_modeled_bonus_row_count"] == len(modeled)
    assert phase8["bear_draw_in_scope_model_pending_row_count"] == len(pending)
    assert phase8["bear_draw_excluded_not_predictive_draw_row_count"] == len(excluded)
    assert phase8["limited_entry_bear_hunt_modeled"] is True
    assert phase8["restricted_bear_pursuit_modeled"] is True
