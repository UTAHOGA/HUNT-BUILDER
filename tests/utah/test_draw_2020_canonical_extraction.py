from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
)
SUMMARY = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_results_2020_for_2021_pdf_extraction_summary.json"
CANONICAL_2018 = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
)
SUMMARY_2018 = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_results_2018_for_2019_pdf_extraction_summary.json"


def rows() -> list[dict[str, str]]:
    with CANONICAL.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rows_2018() -> list[dict[str, str]]:
    with CANONICAL_2018.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def integer(value: str) -> int:
    return int((value or "0").replace(",", ""))


def test_2020_official_pdf_extraction_has_no_unparsed_hunt_pages() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["status"] == "PASS"
    assert summary["unparsed_hunt_page_count"] == 0
    assert summary["duplicate_source_row_key_count"] == 0
    assert summary["source_pdf_count"] == 13
    assert summary["rows"] == 33069


def test_2020_canonical_uses_draw_result_year_and_retains_pdf_lineage() -> None:
    extracted = rows()

    assert len(extracted) == 33069
    assert {row["actual_draw_year"] for row in extracted} == {"2020"}
    assert {row["model_target_year"] for row in extracted} == {"2021"}
    assert all(row["species"] for row in extracted)
    assert all(row["source_file"] and row["source_path"] and row["pdf_page"] for row in extracted)
    assert all(row["source_namespace"] == "OFFICIAL_DWR_DRAW_RESULTS_2020" for row in extracted)


def test_2020_public_draw_totals_are_not_residency_collapsed() -> None:
    point_rows = [row for row in rows() if row["record_type"] == "point_level_draw_result"]

    assert point_rows
    for row in point_rows:
        assert integer(row["total_eligible_applicants"]) == integer(row["resident_eligible_applicants"]) + integer(row["nonresident_eligible_applicants"])
        assert integer(row["total_permits"]) == integer(row["resident_total_permits"]) + integer(row["nonresident_total_permits"])


def test_2020_mountain_goat_is_either_sex_not_male() -> None:
    goat_rows = [row for row in rows() if row["hunt_code"].startswith("GO")]

    assert goat_rows
    assert {row["sex"] for row in goat_rows} == {"Either Sex"}
    assert {row["sex_type"] for row in goat_rows} == {"Either Sex"}


def test_2018_legacy_layout_is_canonicalized_with_complete_lineage() -> None:
    summary = json.loads(SUMMARY_2018.read_text(encoding="utf-8"))
    extracted = rows_2018()

    assert summary["status"] == "PASS"
    assert summary["source_pdf_count"] == 9
    assert summary["rows"] == 28427
    assert summary["unparsed_hunt_page_count"] == 0
    assert summary["duplicate_source_row_key_count"] == 0
    assert len(extracted) == 28427
    assert {row["actual_draw_year"] for row in extracted} == {"2018"}
    assert {row["model_target_year"] for row in extracted} == {"2019"}
    assert all(row["source_namespace"] == "OFFICIAL_DWR_DRAW_RESULTS_2018" for row in extracted)
    assert all(row["source_file"] and row["source_path"] and row["pdf_page"] for row in extracted)
