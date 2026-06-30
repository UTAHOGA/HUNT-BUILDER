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


def test_bear_subtype_preservation_for_sportsman_harvest_and_unlimited_rows() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/ml_draw_predictions_v1.csv")))

    br1000 = [row for row in rows if row.get("hunt_code") == "BR1000"]
    assert br1000
    assert all(row.get("draw_system_type") == "SPORTSMAN_PERMIT" for row in br1000)

    br1001 = [row for row in rows if row.get("hunt_code") == "BR1001"]
    assert br1001
    assert all(row.get("bear_draw_subtype") == "HARVEST_OBJECTIVE_AVAILABILITY" for row in br1001)
    assert all((row.get("p_draw") or "").strip() == "" for row in br1001)

    for hunt_code in {"BR1007", "BR1018"}:
        matching = [row for row in rows if row.get("hunt_code") == hunt_code]
        assert matching
        assert all(row.get("bear_draw_subtype") == "UNLIMITED_PURSUIT_PERMIT" for row in matching)
        assert all((row.get("p_draw") or "").strip() == "" for row in matching)
