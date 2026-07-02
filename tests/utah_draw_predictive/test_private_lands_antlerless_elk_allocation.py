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


def test_private_lands_antlerless_elk_rows_are_modeled_as_allocation() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/private_lands_antlerless_elk_predictions_v1.csv")))
    assert rows
    assert all(row.get("draw_system_type") == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK" for row in rows)
    assert all(row.get("algorithm_status") == "MODELED_ALLOCATION" for row in rows)
    assert all((row.get("permits_allotted") or "").strip() != "" for row in rows)
    assert all((row.get("allocation_status") or "").strip() == "ALLOCATION KNOWN / REMAINING UNKNOWN" for row in rows)
    assert all((row.get("availability_status") or "").strip() == "ALLOCATION KNOWN / REMAINING UNKNOWN" for row in rows)
    assert all((row.get("season_status") or "").strip() == "SEASON DATES PRESENT" for row in rows)
    assert all((row.get("private_land_only_flag") or "").strip() == "TRUE" for row in rows)
