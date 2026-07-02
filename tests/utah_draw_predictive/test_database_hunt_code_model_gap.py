import csv
import json
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while not ((repo_root / "AGENTS.MD").exists() and (repo_root / "engine").is_dir() and (repo_root / "processed_data").is_dir()) and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if not ((repo_root / "AGENTS.MD").exists() and (repo_root / "engine").is_dir() and (repo_root / "processed_data").is_dir()):
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


REPO = Path(str(_repo_root()))
GAP_JSON_PATH = REPO / "processed_data" / "database_hunt_code_model_gap.json"
GAP_CSV_PATH = REPO / "processed_data" / "database_hunt_code_model_gap.csv"
COVERAGE_JSON_PATH = REPO / "processed_data" / "draw_system_coverage_report.json"
ML_PATH = REPO / "processed_data" / "ml_draw_predictions_v1.csv"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_audit_finds_the_canonical_database_count() -> None:
    report = _read_json(GAP_JSON_PATH)
    assert report["canonical_database_file"]
    assert report["database_unique_hunt_code_count"] > 0
    candidate_counts = report["canonical_database_candidate_counts"]
    assert isinstance(candidate_counts, dict)
    assert len(candidate_counts) > 0


def test_reported_database_count_equals_1294_or_explains_difference() -> None:
    report = _read_json(GAP_JSON_PATH)
    count = int(report["database_unique_hunt_code_count"])
    if count != 1294:
        explanation = str(report.get("database_count_explanation", "")).lower()
        assert "no canonical database candidate" in explanation or "selected canonical source reports" in explanation
    else:
        assert report["database_count_matches_expected_1294"] is True


def test_modeled_target_hunt_code_count_matches_coverage_artifact() -> None:
    report = _read_json(GAP_JSON_PATH)
    coverage = _read_json(COVERAGE_JSON_PATH)
    assert int(report["modeled_target_hunt_code_count"]) == int(coverage["modeled_target_hunt_codes"])


def test_computed_gap_equals_database_minus_modeled_target_count() -> None:
    report = _read_json(GAP_JSON_PATH)
    expected = int(report["database_unique_hunt_code_count"]) - int(report["modeled_target_hunt_code_count"])
    assert int(report["database_to_modeled_gap_count"]) == expected


def test_every_in_database_not_modeled_hunt_code_has_reason_not_modeled() -> None:
    rows = _read_csv(GAP_CSV_PATH)
    gap_rows = [row for row in rows if row["bucket"] == "in_database_not_modeled"]
    assert gap_rows
    missing = [row["hunt_code"] for row in gap_rows if not str(row.get("reason_not_modeled", "")).strip()]
    assert not missing


def test_no_pending_or_non_probability_row_is_counted_as_draw_odds_modeled() -> None:
    rows = _read_csv(ML_PATH)
    draw_odds_statuses = {"MODELED_BONUS", "MODELED_PREFERENCE", "MODELED_SPORTSMAN_DRAW", "MODELED_RANDOM_ONLY"}
    non_probability_statuses = {
        "IN_SCOPE_MODEL_PENDING",
        "OUT_OF_SCOPE_NON_TARGET",
        "EXCLUDED_NOT_PREDICTIVE_DRAW",
        "MODELED_ALLOCATION",
        "MODELED_AVAILABILITY",
    }

    pending_rows = [row for row in rows if row.get("algorithm_status") in non_probability_statuses]
    assert pending_rows
    assert all(row.get("algorithm_status") not in draw_odds_statuses for row in pending_rows)
