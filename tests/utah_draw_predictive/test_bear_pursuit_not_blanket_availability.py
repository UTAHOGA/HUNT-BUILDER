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


def test_bear_pursuit_rows_are_classified_by_source_not_hunt_name_only() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/ml_draw_predictions_v1.csv")))
    by_code = {}
    for row in rows:
        if row.get("hunt_code", "").startswith("BR10"):
            by_code.setdefault(row["hunt_code"], []).append(row)

    for hunt_code in {"BR1008", "BR1009", "BR1010", "BR1011", "BR1012", "BR1013", "BR1015", "BR1016", "BR1017"}:
        matching = by_code.get(hunt_code, [])
        assert matching
        assert all(row.get("bear_draw_subtype") == "RESTRICTED_BEAR_PURSUIT" for row in matching)
        assert all(row.get("algorithm_status") != "MODELED_AVAILABILITY" for row in matching)

    for hunt_code in {"BR1007", "BR1018"}:
        matching = by_code.get(hunt_code, [])
        assert matching
        assert all(row.get("bear_draw_subtype") == "UNLIMITED_PURSUIT_PERMIT" for row in matching)
        assert all(row.get("algorithm_status") == "MODELED_AVAILABILITY" for row in matching)
