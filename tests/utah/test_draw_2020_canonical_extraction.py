from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.extract_2020_draw_results_from_pdfs import classify, count_backed_probability, species_for
from scripts.populate_draw_probability_columns import has_material_count_backed_conflict
from engine.utah_draw_predictive.run_all_families import _cwmu_source_pool_from_fields


def test_count_backed_probability_uses_exact_counts_before_rounded_ratio() -> None:
    probability, percent = count_backed_probability("9", "8", "1 in 1.1")

    assert probability == "0.8888888889"
    assert percent == "88.88888889"


def test_zero_applicant_row_never_derives_probability_from_display_ratio() -> None:
    assert count_backed_probability("0", "1", "1 in 1.0") == ("", "")


def test_2020_antlerless_special_species_use_bonus_designs_before_pronghorn_fallback() -> None:
    assert classify("ANTLERLESS", "MA1000", "Antlerless Moose - East Canyon") == (
        "ANTLERLESS_MOOSE", "Antlerless", "BONUS_ANTLERLESS_MOOSE", "MODELED_BONUS"
    )


def test_cwmu_youth_flag_keeps_shared_antlerless_ladders_in_separate_source_pools() -> None:
    adult = {
        "species": "Elk",
        "sex_type": "Antlerless",
        "source_is_youth": "false",
    }
    youth = {**adult, "source_is_youth": "true"}

    assert _cwmu_source_pool_from_fields(adult, "CWMU_ANTLERLESS") == "cwmu_antlerless_elk"
    assert _cwmu_source_pool_from_fields(youth, "CWMU_ANTLERLESS") == "cwmu_youth_antlerless_elk"
    assert classify("ANTLERLESS", "RE1000", "Ewe Rocky Mountain Bighorn") == (
        "EWE_BIGHORN", "Ewe", "BONUS_EWE_BIGHORN", "MODELED_BONUS"
    )


def test_material_count_conflict_identifies_rounded_ratio_without_changing_source_text() -> None:
    row = {
        "row_type": "POINT_ROW",
        "resident_eligible_applicants": "254",
        "resident_total_permits": "242",
        "resident_success_ratio": "1 in 1.0",
        "resident_p_draw": "1",
    }

    assert has_material_count_backed_conflict(row, "resident")
    assert row["resident_success_ratio"] == "1 in 1.0"


def test_material_count_conflict_includes_official_sportsman_hunt_total() -> None:
    row = {
        "record_type": "sportsman_total_draw_result",
        "resident_eligible_applicants": "5806",
        "resident_total_permits": "1",
        "resident_success_ratio": "1 in 5,806.0",
        "resident_p_draw": "0.2",
    }

    assert has_material_count_backed_conflict(row, "resident")


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
    assert {row["source_is_youth"] for row in extracted} == {"false", "true"}
    assert all(row["source_is_youth"] == "true" for row in extracted if row["source_scope"].startswith("YOUTH_"))
    assert all(row["source_is_youth"] == "false" for row in extracted if not row["source_scope"].startswith("YOUTH_"))


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
    assert summary["source_pdf_count"] == 10
    assert summary["rows"] == 30338
    assert summary["unparsed_hunt_page_count"] == 0
    assert summary["duplicate_source_row_key_count"] == 0
    assert len(extracted) == 30338
    assert {row["actual_draw_year"] for row in extracted} == {"2018"}
    assert {row["model_target_year"] for row in extracted} == {"2019"}
    assert all(row["source_namespace"] == "OFFICIAL_DWR_DRAW_RESULTS_2018" for row in extracted)
    assert all(row["source_file"] and row["source_path"] and row["pdf_page"] for row in extracted)
    bear_points = [
        row
        for row in extracted
        if row["hunt_code"].startswith("BR") and row["record_type"] == "point_level_draw_result"
    ]
    assert len(bear_points) == 1820
    assert {row["source_file"] for row in bear_points} == {"official_dwr_archive/black_bear/18_drawing_odds.pdf"}


def test_2018_eb3100_resident_point_12_uses_exact_permit_applicant_probability() -> None:
    matches = [
        row
        for row in rows_2018()
        if row["hunt_code"] == "EB3100" and row["points"] == "12"
    ]

    assert len(matches) == 1
    row = matches[0]
    assert row["resident_eligible_applicants"] == "9"
    assert row["resident_total_permits"] == "8"
    assert row["resident_success_ratio"] == "1 in 1.1"
    assert row["resident_p_draw"] == "0.8888888889"
    assert row["resident_p_draw_percent"] == "88.88888889"


def test_official_hunt_code_prefix_controls_species_over_unit_name() -> None:
    """Place names such as Bear Mountain/River must not reclassify game species."""

    assert species_for("DA1001", "Antlerless Deer - Box Elder, West Bear River") == "Deer"
    assert species_for("EA1120", "CWMU Antlerless Elk - Bear Mountain") == "Elk"
    assert species_for("MB6011", "Elk Ridge Moose") == "Moose"
    assert species_for("BR7004", "Manti South/San Rafael North") == "Black Bear"


def test_2020_pdf_internal_zero_applicant_permit_conflicts_are_explicitly_quarantined() -> None:
    marker = "OFFICIAL_SOURCE_ZERO_APPLICANT_STRUCTURAL_ROW_WITH_DISPLAYED_PERMIT"
    conflicts = [
        row
        for row in rows()
        if marker in row.get("qa_notes", "")
    ]

    assert len(conflicts) == 6
    assert {row["hunt_code"] for row in conflicts} == {
        "EA1121", "MA1000", "MA1001", "MA1003", "MA1004", "MA1005"
    }
    assert all(row["points"] == "15" for row in conflicts)
    assert all(row["resident_eligible_applicants"] == "0" for row in conflicts)
    assert all(int(row["resident_total_permits"]) > 0 for row in conflicts)
    # Retain DWR's printed counts and success-ratio text, but never allow an
    # internally impossible lane to become a scoreable derived probability.
    assert all(not row["resident_p_draw"] for row in conflicts)
    assert all(not row["resident_p_draw_percent"] for row in conflicts)
