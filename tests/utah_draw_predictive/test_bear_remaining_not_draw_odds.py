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


def test_bear_remaining_rows_do_not_receive_draw_odds() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/bear_draw_predictions_v1.csv")))
    remaining = [row for row in rows if row.get("bear_draw_subtype") == "REMAINING_PERMIT_AVAILABILITY"]
    assert all((row.get("p_draw") or "").strip() == "" for row in remaining)
    assert all((row.get("p_draw_pct") or "").strip() == "" for row in remaining)
