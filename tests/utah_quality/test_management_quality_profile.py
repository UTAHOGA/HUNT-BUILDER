import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTEXT = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"
PROFILE = ROOT / "data_model" / "harvest_quality" / "hunt_quality_profile_by_hunt_code_2026.csv"
PUBLIC = ROOT / "processed_data" / "public_contracts" / "hunt_application_outlook.json"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_management_context_uses_exact_current_sources() -> None:
    rows = json.loads(CONTEXT.read_text(encoding="utf-8"))
    assert len(rows) == 837
    assert len({row["hunt_code"] for row in rows}) == len(rows)
    assert all("synthetic" not in json.dumps(row).lower() for row in rows)
    db1110 = next(row for row in rows if row["hunt_code"] == "DB1110")
    assert db1110["management_objective_type"] == "DWR Buck-to-Doe Composition Objective"
    assert db1110["management_objective_target"] == "15-17"
    assert db1110["management_current_value"] == "21"
    assert db1110["objective_unit"].startswith("bucks per 100 does")
    assert db1110["management_objective_status"] == "ABOVE_OBJECTIVE"


def test_framework_only_species_never_receive_scores() -> None:
    rows = csv_rows(PROFILE)
    for row in rows:
        if row["species"] in {"Black Bear", "Turkey", "Cougar"}:
            assert row["hunt_unit_quality_score"] == ""
            assert row["hunt_unit_quality_score_status"] == "WITHHELD_EVIDENCE_THRESHOLD_NOT_MET"


def test_published_scores_have_all_fixed_components() -> None:
    rows = csv_rows(PROFILE)
    published = [row for row in rows if row["hunt_unit_quality_score"]]
    assert len(published) == 390
    for row in published:
        assert row["hunt_unit_quality_reason_codes"] == ""
        assert row["hunt_unit_quality_confidence"] in {"HIGH", "MODERATE"}
        assert all(
            row[field]
            for field in (
                "biological_quality_component",
                "harvest_success_3yr_component",
                "hunter_satisfaction_3yr_component",
                "effort_efficiency_3yr_component",
            )
        )


def test_annual_reported_and_hunt_planner_age_remain_distinct() -> None:
    rows = json.loads(PUBLIC.read_text(encoding="utf-8"))
    resident = next(row for row in rows if row["hunt_code"] == "EA1030" and row["residency"] == "Resident")
    assert resident["average_harvest_age"] == "7.7"
    assert resident["average_harvest_age_reported_year"] == "2023"
    assert resident["average_harvest_age_3yr_reported"] == "8"
    assert resident["current_age_3yr_average"] == "7.6"


def test_public_contract_keeps_score_within_display_layer() -> None:
    rows = json.loads(PUBLIC.read_text(encoding="utf-8"))
    scored = [row for row in rows if str(row.get("hunt_unit_quality_score") or "").strip()]
    assert len({row["hunt_code"] for row in scored}) == 390
    assert all(row["hunt_quality_profile_version"] == "UOGA_HUNT_QUALITY_PROFILE_V1" for row in scored)
    assert all(row["hunt_unit_quality_score_status"] == "PUBLISHABLE_EVIDENCE_THRESHOLD_MET" for row in scored)
