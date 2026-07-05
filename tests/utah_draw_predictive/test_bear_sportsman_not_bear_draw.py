import csv
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


def test_br1000_remains_sportsman_not_bear_draw() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/ml_draw_predictions_v1.csv")))
    br1000 = [row for row in rows if row.get("hunt_code") == "BR1000"]
    assert br1000
    assert all(row.get("draw_system_type") == "SPORTSMAN_PERMIT" for row in br1000)
    assert all(row.get("algorithm_status") == "MODELED_SPORTSMAN_DRAW" for row in br1000)
    assert all((row.get("p_bonus_pool") or "").strip() == "" for row in br1000)
    assert all((row.get("p_random_pool") or "").strip() == "" for row in br1000)
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in br1000)
