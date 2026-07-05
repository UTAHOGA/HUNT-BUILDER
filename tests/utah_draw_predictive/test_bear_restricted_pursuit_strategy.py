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


def test_public_restricted_pursuit_bear_rows_can_be_modeled_bonus() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_draw_predictions_v1.csv")))
    pursuit_rows = [
        row for row in rows
        if row.get("hunt_code") in {"BR1008", "BR1009", "BR1010", "BR1011", "BR1012", "BR1013", "BR1015", "BR1016", "BR1017"}
    ]
    assert pursuit_rows
    assert all(row.get("bear_draw_subtype") == "RESTRICTED_BEAR_PURSUIT" for row in pursuit_rows)
    assert any(row.get("algorithm_status") == "MODELED_BONUS" for row in pursuit_rows)
    assert all(row.get("algorithm_status") != "MODELED_AVAILABILITY" for row in pursuit_rows)
    modeled_rows = [row for row in pursuit_rows if row.get("algorithm_status") == "MODELED_BONUS"]
    assert modeled_rows
    assert all((row.get("p_draw") or "").strip() != "" for row in modeled_rows)
    assert all((row.get("p_bonus_pool") or "").strip() != "" for row in modeled_rows)
    assert all((row.get("p_random_pool") or "").strip() != "" for row in modeled_rows)
