import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRUTH_ROOT = ROOT / "data_truth" / "harvest_results_truth" / "normalized"
BEST = TRUTH_ROOT / "harvest_quality_features_all_years_by_hunt_code.csv"
LONG = TRUTH_ROOT / "harvest_results_all_years_long.csv"
SOURCE_AUDIT = TRUTH_ROOT / "harvest_results_all_years_source_audit.csv"
SUMMARY = TRUTH_ROOT / "harvest_results_all_years_summary.json"
PACKAGE_MANIFEST = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages_manifest.json"
OVERLAY = ROOT / "data_model" / "permit_overlays" / "special_permit_overlay_classes_all_years.csv"


def _rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_all_years_harvest_database_outputs_exist():
    assert BEST.exists()
    assert LONG.exists()
    assert SOURCE_AUDIT.exists()
    assert SUMMARY.exists()
    assert (ROOT / "processed_data" / "harvest_quality_features_all_years_by_hunt_code.csv").exists()
    assert (ROOT / "processed_data" / "harvest_results_all_years_long.csv").exists()
    assert (ROOT / "data_model" / "harvest_quality" / "harvest_quality_features_all_years_by_hunt_code.csv").exists()
    assert (ROOT / "data_model" / "harvest_quality" / "harvest_results_all_years_long.csv").exists()
    assert OVERLAY.exists()


def test_all_years_harvest_database_has_expected_years_and_counts():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["unique_reported_hunt_years"] == [str(year) for year in range(2005, 2026)]
    assert summary["reported_hunt_year_counts"] == {
        **{str(year): 12 for year in range(2005, 2017)},
        "2017": 908,
        "2018": 936,
        "2019": 962,
        "2020": 939,
        "2021": 974,
        "2022": 1050,
        "2023": 1179,
        "2024": 1048,
        "2025": 1148,
    }
    assert summary["best_by_year_hunt_code_rows"] == 9288
    assert summary["normalized_long_rows"] == 73397
    assert summary["special_permit_overlay_class_counts"] == {
        "CONSERVATION": 77,
        "CWMU": 1429,
        "EXPO": 9,
        "SPORTSMAN": 16,
    }


def test_all_years_harvest_model_target_year_is_reported_year_plus_one():
    for row in _rows(BEST):
        assert int(row["model_target_year"]) == int(row["reported_hunt_year"]) + 1


def test_all_years_harvest_best_table_has_unique_year_hunt_identity_keys():
    rows = _rows(BEST)
    keys = [
        (
            row["reported_hunt_year"],
            row["hunt_code"],
            row["species"],
            row["hunt_name"],
            row["weapon"],
        )
        for row in rows
    ]

    assert len(keys) == len(set(keys))


def test_all_years_harvest_rows_are_not_quota_or_direct_p_draw_sources():
    for row in _rows(BEST):
        assert row["do_not_use_for_permit_quota"] == "True"
        assert row["do_not_use_directly_for_p_draw"] == "True"


def test_all_years_harvest_includes_2023_all_species_model_year_2024():
    rows = _rows(BEST)
    db1002 = [
        row
        for row in rows
        if row["reported_hunt_year"] == "2023" and row["model_target_year"] == "2024" and row["hunt_code"] == "DB1002"
    ]

    assert db1002
    assert db1002[0]["percent_success"] != ""
    assert "2023" in db1002[0]["source_file"] or "2023" in db1002[0]["source_container"]


def test_all_years_harvest_includes_2025_model_year_2026():
    rows = _rows(BEST)

    assert any(row["reported_hunt_year"] == "2025" and row["model_target_year"] == "2026" for row in rows)


def test_official_2017_2021_history_has_hunt_level_metrics_and_guardrails():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    history = summary["official_dwr_history_2017_2021"]

    assert history["rows_by_year"] == {
        "2017": 908,
        "2018": 936,
        "2019": 962,
        "2020": 939,
        "2021": 974,
    }
    assert history["metric_nonblank_by_year"]["2017"]["harvest_total"] == 897
    assert history["metric_nonblank_by_year"]["2020"]["percent_success"] == 933
    assert history["metric_nonblank_by_year"]["2021"]["harvest_total"] == 970

    repaired_rows = [row for row in _rows(BEST) if "2017" <= row["reported_hunt_year"] <= "2021"]
    assert repaired_rows
    assert all(row["do_not_use_for_permit_quota"] == "True" for row in repaired_rows)
    assert all(row["do_not_use_directly_for_p_draw"] == "True" for row in repaired_rows)

    sample_2017 = next(
        row for row in repaired_rows if row["reported_hunt_year"] == "2017" and row["hunt_code"] == "DB1000"
    )
    assert sample_2017["permits"] == "12"
    assert sample_2017["hunters_afield"] == "12"
    assert sample_2017["harvest_total"] == "11"
    assert sample_2017["percent_success"] == "91.7"

    sample_2021 = next(
        row for row in repaired_rows if row["reported_hunt_year"] == "2021" and row["hunt_code"] == "BI6503"
    )
    assert sample_2021["permits"] == "18"
    assert sample_2021["hunters_afield"] == "18"
    assert sample_2021["harvest_total"] == "15"
    assert sample_2021["percent_success"] == "81.3"


def test_current_2025_dashboard_snapshot_has_all_live_rows_and_species_counts():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    current = summary["current_2025_dashboard"]

    assert current["current_rows"] == 1141
    assert current["addition_rows"] == 21
    assert current["correction_rows"] == 1
    assert current["species_counts"] == {
        "Bison": 18,
        "Deer": 421,
        "Desert Bighorn Sheep": 25,
        "Elk": 471,
        "Moose": 43,
        "Mountain Goat": 18,
        "Pronghorn": 124,
        "Rocky Mountain Bighorn Sheep": 21,
    }


def test_official_annual_and_reported_three_year_age_are_distinct_and_provenanced():
    rows = _rows(BEST)
    sample_2017 = next(
        row for row in rows if row["reported_hunt_year"] == "2017" and row["hunt_code"] == "GO6800"
    )
    assert sample_2017["average_age"] == "3.9"
    assert sample_2017["average_age_3yr_reported"] == ""
    assert sample_2017["average_age_source_page"] == "1"
    assert sample_2017["average_age_crosswalk_confidence"] == "high"

    sample_2022 = next(
        row for row in rows if row["reported_hunt_year"] == "2022" and row["hunt_code"] == "DB1000"
    )
    assert sample_2022["average_age"] == "5.7"
    assert sample_2022["average_age_3yr_reported"] == "5.5"
    assert sample_2022["average_age_mapping_status"] == "mapped_direct_hunt_code"

    current_2025 = [row for row in rows if row["reported_hunt_year"] == "2025"]
    assert current_2025
    assert sum(bool(row["average_age"]) for row in current_2025) == 220
    assert sum(bool(row["average_age_3yr_reported"]) for row in current_2025) == 222

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["official_harvest_age"]["best_by_hunt_identity"]["reported_3yr_age_nonblank"] == 814


def test_harvest_packages_imported_without_pdf_reextraction():
    manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["unique_packages_imported"] == 14
    assert manifest["total_pdf_files"] == 0
    assert manifest["pdf_reextraction_performed"] == "NO"
    assert all(package["pdf_reextraction_performed"] == "NO" for package in manifest["packages"])
    assert all((ROOT / package["truth_extract_dir"]).exists() for package in manifest["packages"])
    assert all((ROOT / package["model_extract_dir"]).exists() for package in manifest["packages"])


def test_split_season_turkey_packages_use_ending_year():
    manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
    packages = {package["package_id"]: package for package in manifest["packages"]}

    turkey_2023_24 = packages["2024_for_2025_turkey_harvest_results_2023_24_for_2025_database"]
    turkey_2024_25 = packages["2025_for_2026_turkey_harvest_results_2024_25_for_2026_database"]

    assert turkey_2023_24["reported_hunt_year"] == "2024"
    assert turkey_2023_24["model_target_year"] == "2025"
    assert turkey_2024_25["reported_hunt_year"] == "2025"
    assert turkey_2024_25["model_target_year"] == "2026"


def test_special_permit_overlay_classes_are_reconciliation_only():
    rows = _rows(OVERLAY)

    assert rows
    assert {row["permit_overlay_class"] for row in rows} == {"CONSERVATION", "CWMU", "EXPO", "SPORTSMAN"}
    assert all(row["permit_overlay_use"] == "TOTAL_PERMIT_RECONCILIATION_ONLY" for row in rows)
    assert all(row["public_draw_odds_use"] == "NO" for row in rows)
    assert all(row["p_draw_math_use"] == "NO" for row in rows)
