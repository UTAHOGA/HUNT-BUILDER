import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "finalize-draw-results-cumulative-database.py"
TRUTH_ROOT = ROOT / "data_truth" / "draw_results_truth" / "normalized"
LONG = TRUTH_ROOT / "draw_results_long.csv"
SOURCE_AUDIT = TRUTH_ROOT / "draw_results_all_years_source_audit.csv"
SUMMARY = TRUTH_ROOT / "draw_results_all_years_summary.json"
SUMMARY_MD = TRUTH_ROOT / "draw_results_all_years_summary.md"


def run_builder():
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_draw_results_cumulative_outputs_exist_and_validate():
    run_builder()

    assert LONG.exists()
    assert SOURCE_AUDIT.exists()
    assert SUMMARY.exists()
    assert SUMMARY_MD.exists()
    assert (ROOT / "processed_data" / "draw_results_all_years_source_audit.csv").exists()
    assert (ROOT / "processed_data" / "draw_results_all_years_summary.json").exists()
    assert (ROOT / "processed_data" / "draw_results_all_years_summary.md").exists()

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    # Multiple official source scopes can share a coarse hunt-point identity.
    # They remain distinct evidence.  Source-row lineage makes the actual
    # source identity unique without merging or discarding either row.
    assert summary["blocker_count"] == 0
    assert summary["blockers"] == []
    assert summary["blank_hunt_code_rows"] == 0
    assert summary["invalid_year_rows"] == 0
    assert summary["coarse_key_collision_count"] > 0
    assert summary["cross_scope_only_collision_count"] == summary["coarse_key_collision_count"]
    assert summary["source_identity_collision_count"] == 0
    assert summary["source_identity_collision_group_count"] == 0


def test_draw_results_cumulative_counts_are_locked():
    run_builder()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["normalized_long_rows"] == 309562
    assert summary["unique_draw_years"] == ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]
    assert summary["draw_year_counts"] == {
        "2018": 28427,
        "2019": 33478,
        "2020": 33069,
        "2021": 33788,
        "2022": 34876,
        "2023": 35834,
        "2024": 43175,
        "2025": 38120,
        "2026": 28795,
    }
    assert summary["model_target_year_counts"] == {
        "2019": 28427,
        "2020": 33478,
        "2021": 33069,
        "2022": 33788,
        "2023": 34876,
        "2024": 35834,
        "2025": 43175,
        "2026": 38120,
        "2027": 28795,
    }


def test_draw_results_cumulative_key_contract_and_crosswalk_presence():
    run_builder()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["coarse_key_fields"] == ["hunt_code", "year", "draw_pool", "residency", "points"]
    assert summary["source_identity_key_fields"] == [
        "hunt_code", "year", "draw_pool", "residency", "points", "source_scope", "source_file", "record_type",
        "pdf_page", "source_row_identifier",
    ]
    assert summary["active_database_hunt_codes"] == 1849
    assert summary["crosswalk_current_code_count"] == 0
    assert summary["crosswalk_current_codes_present_in_draw_rows"] == 0

    source_rows = read_rows(SOURCE_AUDIT)
    assert source_rows
    assert sum(int(row["row_count"]) for row in source_rows) == summary["normalized_long_rows"]
