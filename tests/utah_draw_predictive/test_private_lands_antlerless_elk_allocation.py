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


def test_private_lands_antlerless_elk_rows_are_modeled_as_otc_capped_permits() -> None:
    rows = _read_csv(Path(str(_repo_root() / "processed_data/private_lands_antlerless_elk_predictions_v1.csv")))
    assert rows
    assert all(row.get("draw_system_type") == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK" for row in rows)
    assert all(row.get("algorithm_status") == "MODELED_AVAILABILITY" for row in rows)
    assert all(row.get("draw_design") == "Capped Permits" for row in rows)
    assert all(row.get("acquisition_method") == "OTC_CAPPED_PRIVATE_LANDS_PERMITS" for row in rows)
    assert all((row.get("permits_allotted") or "").strip() != "" for row in rows)
    assert all((row.get("capped_permit_status") or "").strip() == "OTC CAPPED PERMITS KNOWN / REMAINING UNKNOWN" for row in rows)
    assert all((row.get("availability_status") or "").strip() == "OTC CAPPED PERMITS KNOWN / REMAINING UNKNOWN" for row in rows)
    assert all((row.get("season_status") or "").strip() == "SEASON DATES PRESENT" for row in rows)
    assert all((row.get("private_land_only_flag") or "").strip() == "TRUE" for row in rows)
