import csv
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase12_bear_coverage_matches_subtype_outputs() -> None:
    coverage = json.loads(Path(str(_repo_root() / "processed_data/draw_system_coverage_report.json")).read_text(encoding="utf-8"))
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_predictions_v1.csv")))
    phase12 = coverage["phase12_bear"]

    modeled = [row for row in rows if row.get("algorithm_status") == "MODELED_BONUS"]
    pending = [row for row in rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]
    harvest_objective = [row for row in rows if row.get("bear_draw_subtype") == "HARVEST_OBJECTIVE_AVAILABILITY"]
    unlimited = [row for row in rows if row.get("bear_draw_subtype") == "UNLIMITED_PURSUIT_PERMIT"]

    assert phase12["bear_draw_modeled_bonus_rows"] == len(modeled)
    assert phase12["bear_draw_pending_rows"] == len(pending)
    assert phase12["bear_harvest_objective_rows"] == len(harvest_objective)
    assert phase12["bear_unlimited_pursuit_rows"] == len(unlimited)
    assert phase12["bear_rows_with_p_draw"] == sum(1 for row in rows if (row.get("p_draw") or "").strip())
    assert phase12["br1001_classified_as_harvest_objective_availability"] is True
    assert phase12["br1001_modeled_as_draw_odds"] is False
    assert phase12["br1007_and_br1018_classified_as_unlimited_pursuit_permit"] is True
    assert phase12["br1007_and_br1018_modeled_as_draw_odds"] is False
