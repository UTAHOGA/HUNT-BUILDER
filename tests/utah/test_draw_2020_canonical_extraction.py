from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.extract_2020_draw_results_from_pdfs import (
    YEAR_CONFIGS,
    classify,
    clean_hunt_name,
    count_backed_probability,
    metadata_from_page,
    species_for,
    split_draw_table_cells,
)
from scripts.compare_draw_canonical_candidate import (
    decimal_value,
    normalized_source_role,
    success_ratio_denominator,
)
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


def test_2018_management_buck_retains_distinct_identity_and_bonus_draw_design() -> None:
    assert classify("BIG_GAME", "DB1009", "Management Rifle Buck Deer - Henry Mtns - Any Legal Weapon") == (
        "MANAGEMENT_DEER", "Management Buck Deer", "BONUS_LE_BIG_GAME", "MODELED_BONUS"
    )


def test_2018_rotated_bear_pursuit_page_uses_the_published_hunt_name() -> None:
    class RotatedBearPursuitPage:
        blocks = [
            (356.8, 108.8, 368.0, 646.4, "0 0 0 0 0 9 0 N/A 0 0 N/A", 0, 0),
            (103.3, 545.4, 114.5, 633.2, "Book Cliffs - Pursuit", 1, 0),
            (103.3, 647.1, 114.7, 718.4, "Hunt: BR1008", 2, 0),
        ]

        def get_text(self, kind: str, sort: bool = False):
            if kind == "blocks":
                return self.blocks
            if kind == "text":
                return "\n".join(block[4] for block in self.blocks)
            raise AssertionError(kind)

    code, name = metadata_from_page(RotatedBearPursuitPage(), "BLACK_BEAR")

    assert (code, name) == ("BR1008", "Book Cliffs - Pursuit")
    assert classify("BLACK_BEAR", code, name) == (
        "RESTRICTED_BEAR_PURSUIT",
        "Bear Pursuit",
        "RESTRICTED_BEAR_PURSUIT",
        "MODELED_BONUS",
    )
    assert classify("BIG_GAME", "DB1058", "Management Rifle Cactus Buck Deer - Paunsaugunt, Cactus Buck") == (
        "CACTUS_DEER", "Cactus Buck Deer", "BONUS_LE_BIG_GAME", "MODELED_BONUS"
    )


def test_historical_cougar_source_stays_a_bonus_draw_not_current_availability() -> None:
    assert classify("COUGAR", "CG1001", "Book Cliffs, East - Any Legal Weapon") == (
        "HISTORICAL_LIMITED_ENTRY_COUGAR", "Cougar", "BONUS_HISTORICAL_COUGAR", "SOURCE_ONLY_HISTORICAL_DRAW"
    )


def test_2019_source_set_uses_draw_date_for_cougar_and_separate_youth_pools() -> None:
    source_files = {source_file: scope for source_file, scope, _ in YEAR_CONFIGS[2019]["sources"]}
    assert source_files["official_dwr_archive/cougar/2020_cougar_odds_report.pdf"] == "COUGAR"
    assert "official_dwr_archive/cougar/2019_cougar_odds_report.pdf" not in source_files
    assert source_files["official_dwr_archive/big_game/19_youth_dh_odds.pdf"] == "YOUTH_DEDICATED_HUNTER"
    assert source_files["official_dwr_archive/turkey/2019_youth_turkey_bonus_points.pdf"] == "YOUTH_TURKEY"


def test_legacy_pdf_hunt_name_does_not_absorb_the_following_report_header() -> None:
    assert clean_hunt_name(
        "Management Rifle Buck Deer - Henry Mtns - Any Legal Weapon "
        "2018 Draw 5, Big Game Bonus Point Draw Results 06/11/2018"
    ) == "Management Rifle Buck Deer - Henry Mtns - Any Legal Weapon"


def test_hunt_total_table_skips_both_printed_totals_markers() -> None:
    cells = [
        "Totals", "693", "3", "4", "7", "1 in 99.0",
        "Totals", "159", "0", "1", "1", "1 in 159.0",
    ]
    resident, nonresident = split_draw_table_cells(cells, "hunt_total_draw_result")

    assert resident == ["693", "3", "4", "7", "1 in 99.0"]
    assert nonresident == ["159", "0", "1", "1", "1 in 159.0"]


def test_legacy_split_output_names_normalize_to_parent_source_roles() -> None:
    assert normalized_source_role(
        {"source_file": "2019_PERMITS=2020_MODEL__CWMU_YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf"}
    ) == "YOUTH_ANTLERLESS"
    assert normalized_source_role(
        {"source_file": "2019_PERMITS=2020_MODEL__O.I.L._BISON_DRAW_RESULTS.pdf"}
    ) == "BIG_GAME"
    assert normalized_source_role(
        {"source_file": "official_dwr_archive/big_game/19_youth_dh_odds.pdf"}
    ) == "YOUTH_DEDICATED_HUNTER"
    assert normalized_source_role(
        {"source_file": "2019_PERMITS=2020_MODEL__CWMU_DOE_PRONGHORN_DRAW_RESULTS.pdf"}
    ) == "ANTLERLESS"


def test_comparison_normalizes_printed_number_and_success_ratio_formats() -> None:
    assert decimal_value("10,964") == decimal_value("10964")
    assert success_ratio_denominator("1 in 99.0") == success_ratio_denominator("99")
    assert success_ratio_denominator("N/A") == success_ratio_denominator("")


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
