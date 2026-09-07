from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGE_DATABASE = ROOT / "data_model" / "harvest_quality" / "harvest_results_2025_for_2026_age_database.csv"
SOURCE_ROWS = ROOT / "data_model" / "harvest_quality" / "harvest_results_2025_age_rows_from_2026_tables.csv"
EXPANDED_ROWS = ROOT / "data_model" / "harvest_quality" / "harvest_results_2025_age_rows_hunt_code_expanded.csv"
SUMMARY = ROOT / "data_model" / "harvest_quality" / "harvest_results_2025_for_2026_age_database_summary.json"
GLOBAL_AGE = ROOT / "data_model" / "harvest_quality" / "harvest_average_age_global_merge_database.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def by_code(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    return next(row for row in rows if row["hunt_code"] == code)


def test_official_2026_tables_normalize_expected_source_and_hunt_code_counts() -> None:
    source_rows = read_rows(SOURCE_ROWS)
    age_rows = read_rows(AGE_DATABASE)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert len(source_rows) == 67
    assert len(age_rows) == 222
    assert summary["age_source_rows_by_species"] == {"Pronghorn": 29, "Elk": 26, "Moose": 12}
    assert summary["hunt_code_rows_by_species"] == {"Elk": 143, "Pronghorn": 66, "Moose": 13}
    assert summary["annual_2025_age_nonblank"] == 220
    assert summary["reported_2023_2025_average_nonblank"] == 222
    assert summary["unmatched_source_units"] == [
        {"species": "Pronghorn", "source_unit_name": "Morgan-South Rich"}
    ]


def test_sample_annual_and_reported_three_year_ages_match_dwr_tables() -> None:
    rows = read_rows(AGE_DATABASE)
    samples = {
        "EB3006": ("5.8", "6.0", "2", "5"),
        "PB5025": ("3.8", "4.3", "1", "2"),
        "MB6012": ("5.6", "5.3", "1", "2"),
        "MB6003": ("3.8", "3.9", "1", "2"),
    }
    for code, (annual, reported, age_page, crosswalk_page) in samples.items():
        row = by_code(rows, code)
        assert row["average_harvest_age"] == annual
        assert row["average_harvest_age_3yr"] == reported
        assert row["age_source_page"] == age_page
        assert row["crosswalk_source_page"] == crosswalk_page
        assert row["crosswalk_confidence"] == "high"
        assert row["age_mapping_status"] == "official_2026_age_unit_to_same_file_hunt_number_table"


def test_reported_average_is_retained_when_dwr_has_no_2025_annual_age() -> None:
    rows = read_rows(AGE_DATABASE)
    assert (by_code(rows, "EB3044")["average_harvest_age"], by_code(rows, "EB3044")["average_harvest_age_3yr"]) == (
        "",
        "9.0",
    )
    assert (by_code(rows, "PB5034")["average_harvest_age"], by_code(rows, "PB5034")["average_harvest_age_3yr"]) == (
        "",
        "5.0",
    )


def test_crosswalk_is_same_file_hunt_number_evidence_and_never_boundary_id() -> None:
    rows = read_rows(AGE_DATABASE)
    assert "boundary_id" not in rows[0]
    assert all(row["age_source_file"] for row in rows)
    assert all(row["age_source_sha256"] for row in rows)
    assert all(row["crosswalk_source_hunt_name"] for row in rows)
    assert all(row["crosswalk_source_page"] for row in rows)

    expanded = read_rows(EXPANDED_ROWS)
    unmatched = [row for row in expanded if not row["hunt_code"]]
    assert [(row["species"], row["source_unit_name"]) for row in unmatched] == [
        ("Pronghorn", "Morgan-South Rich")
    ]


def test_global_history_contains_all_official_2025_age_rows() -> None:
    rows = [row for row in read_rows(GLOBAL_AGE) if row["reported_hunt_year"] == "2025"]
    assert len(rows) == 222
    assert sum(bool(row["average_harvest_age"]) for row in rows) == 220
    assert sum(bool(row["average_harvest_age_3yr"]) for row in rows) == 222
    assert {row["species"] for row in rows} == {"Elk", "Pronghorn", "Moose"}
    assert all(row["age_source_url"].startswith("https://wildlife.utah.gov/") for row in rows)
    assert all(len(row["age_source_sha256"]) == 64 for row in rows)
