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


def test_private_lands_antlerless_elk_rows_do_not_receive_draw_odds_fields() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/private_lands_antlerless_elk_predictions_v1.csv")))
    assert rows
    assert all((row.get("p_draw") or "").strip() == "" for row in rows)
    assert all((row.get("p_draw_pct") or "").strip() == "" for row in rows)
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in rows)
    assert all((row.get("p_bonus_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_random_pool") or "").strip() == "" for row in rows)
