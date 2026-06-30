import csv
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


def test_br1007_and_br1018_are_unlimited_pursuit_not_draw_odds() -> None:
    ml_rows = _read_csv(Path(str(_repo_root() / "processed_data/ml_draw_predictions_v1.csv")))
    rows = [row for row in ml_rows if row.get("hunt_code") in {"BR1007", "BR1018"}]
    assert rows
    assert all(row.get("bear_draw_subtype") == "UNLIMITED_PURSUIT_PERMIT" for row in rows)
    assert all(row.get("algorithm_status") == "MODELED_AVAILABILITY" for row in rows)
    assert all((row.get("p_draw") or "").strip() == "" for row in rows)
    assert all((row.get("p_bonus_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_random_pool") or "").strip() == "" for row in rows)
