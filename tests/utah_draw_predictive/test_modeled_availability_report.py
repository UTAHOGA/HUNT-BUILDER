import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
REVIEW_PATH = REPO / "processed_data" / "modeled_availability_review_report.json"
COVERAGE_PATH = REPO / "processed_data" / "draw_system_coverage_report.json"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_modeled_availability_review_report_fields_present() -> None:
    report = _read_json(REVIEW_PATH)
    required_fields = {
        "forecast_year",
        "source_years",
        "total_MODELED_AVAILABILITY_rows",
        "total_MODELED_AVAILABILITY_hunt_codes",
        "total_MODELED_AVAILABILITY_by_draw_system_type",
        "total_MODELED_AVAILABILITY_by_species",
        "total_MODELED_AVAILABILITY_by_model_strategy",
        "total_MODELED_AVAILABILITY_by_availability_status",
        "total_MODELED_AVAILABILITY_by_permit_availability_type",
        "total_MODELED_AVAILABILITY_by_reason_code",
        "mountain_lion_availability_row_count",
        "bear_availability_row_count",
        "other_availability_row_count",
        "other_availability_rows_detail",
        "p_draw_non_null_count",
        "p_draw_pct_non_null_count",
        "p_preference_draw_non_null_count",
        "p_bonus_pool_non_null_count",
        "p_random_pool_non_null_count",
        "p_availability_non_null_count",
        "availability_pct_non_null_count",
        "duplicate_key_count",
        "availability_rows_missing_reason_codes",
        "availability_rows_missing_availability_status_or_equivalent",
        "availability_rows_with_draw_probability_fields",
        "availability_rows_with_invalid_availability_range",
        "availability_rows_requiring_reclassification",
        "conclusion",
    }
    assert required_fields.issubset(report.keys())


def test_draw_system_coverage_has_modeled_availability_section() -> None:
    coverage = _read_json(COVERAGE_PATH)
    section = coverage["modeled_availability"]
    assert section["modeled_availability_total_row_count"] >= 0
    assert "COUGAR_LICENSE_BASED" not in section["modeled_availability_by_draw_system_type"]
    assert section["mountain_lion_cougar_modeled_availability_row_count"] == 0
    assert coverage["phase10_mountain_lion"]["mountain_lion_cougar_reference_license_based_no_draw"] is True
    assert section["modeled_availability_pass"] is True

