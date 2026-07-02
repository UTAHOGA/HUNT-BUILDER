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


def test_mountain_lion_rows_are_reference_license_based_no_draw() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/mountain_lion_availability_predictions_v1.csv")))
    assert rows
    assert all(row.get("draw_system_type") == "COUGAR_LICENSE_BASED" for row in rows)
    assert all(row.get("algorithm_status") == "REFERENCE_LICENSE_BASED_NO_DRAW" for row in rows)
    assert all((row.get("permit_availability_type") or "").strip() == "HUNTING_OR_COMBINATION_LICENSE" for row in rows)
    assert all((row.get("acquisition_method") or "").strip() == "HUNTING_OR_COMBINATION_LICENSE" for row in rows)
    assert all(
        (row.get("trapping_acquisition_method") or "").strip()
        == "HUNTING_OR_COMBINATION_LICENSE_PLUS_TRAP_REGISTRATION"
        for row in rows
    )
    assert all((row.get("public_draw_odds_eligible") or "").strip() == "false" for row in rows)
    assert all((row.get("modeled_probability_allowed") or "").strip() == "false" for row in rows)
    assert all((row.get("exclusion_reason") or "").strip() == "license_based_no_public_draw_permit" for row in rows)
    assert all((row.get("p_draw") or "").strip() == "" for row in rows)
    assert all((row.get("p_availability") or "").strip() == "" for row in rows)
    assert all((row.get("availability_pct") or "").strip() == "" for row in rows)
    assert all((row.get("permit_type") or "").strip() == "License-based cougar hunting opportunity" for row in rows)
    assert all((row.get("permit_status") or "").strip() == "AVAILABLE" for row in rows)
    assert all((row.get("availability_status") or "").strip() == "AVAILABLE YEAR-ROUND" for row in rows)
    assert all((row.get("season_status") or "").strip() == "YEAR_ROUND_OPEN" for row in rows)
    assert all((row.get("rule_status") or "").strip() == "STATEWIDE_OTC_YEAR_ROUND" for row in rows)
    assert all((row.get("unit_status") or "").strip() == "OPEN" for row in rows)
    forecast_years = {(row.get("forecast_year") or row.get("year") or "").strip() for row in rows}
    assert len(forecast_years) == 1
    forecast_year = forecast_years.pop()
    assert forecast_year
    assert all((row.get("season_start") or "").strip() == f"{forecast_year}-01-01" for row in rows)
    assert all((row.get("season_end") or "").strip() == f"{forecast_year}-12-31" for row in rows)

