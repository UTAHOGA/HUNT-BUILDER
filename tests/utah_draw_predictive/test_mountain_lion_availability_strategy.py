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


def test_mountain_lion_rows_are_modeled_as_availability() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/mountain_lion_availability_predictions_v1.csv")))
    assert rows
    assert all(row.get("draw_system_type") == "MOUNTAIN_LION_DRAW" for row in rows)
    assert all(row.get("algorithm_status") == "MODELED_AVAILABILITY" for row in rows)
    assert all((row.get("permit_availability_type") or "").strip() == "UNLIMITED_OTC_STATEWIDE_REPORTING_UNIT" for row in rows)
    assert all((row.get("permit_type") or "").strip() == "Statewide OTC Cougar Permit" for row in rows)
    assert all((row.get("permit_status") or "").strip() == "AVAILABLE" for row in rows)
    assert all((row.get("availability_status") or "").strip() == "AVAILABLE YEAR-ROUND" for row in rows)
    assert all((row.get("season_status") or "").strip() == "YEAR_ROUND_OPEN" for row in rows)
    assert all((row.get("rule_status") or "").strip() == "STATEWIDE_OTC_YEAR_ROUND" for row in rows)
    assert all((row.get("unit_status") or "").strip() == "OPEN" for row in rows)
    assert all((row.get("season_start") or "").strip() == "2026-01-01" for row in rows)
    assert all((row.get("season_end") or "").strip() == "2026-12-31" for row in rows)
