from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
SUBSET = ROOT / "data_truth" / "comparison_outputs" / "validation" / "permits_2026_draw_subset.csv"
SUMMARY = ROOT / "data_truth" / "comparison_outputs" / "validation" / "permits_2026_draw_subset_summary.json"
REPORT = ROOT / "processed_data" / "permits_2026_draw_field_promotion_report.json"
ML = ROOT / "processed_data" / "ml_draw_predictions_v1.csv"
HUNT_MASTER_DUPLICATE = ROOT / "processed_data" / "hunt_master_enriched_2026_draw_subset.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _by_code(path: Path) -> dict[str, dict[str, str]]:
    return {row["hunt_code"]: row for row in _read_csv(path) if row.get("hunt_code")}


def test_2026_draw_subset_is_built_from_engine_codes_and_database_values() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["draw_engine_hunt_code_count"] == 863
    assert summary["subset_hunt_code_count"] == 813
    assert summary["engine_codes_missing_database_count"] == 0
    assert summary["nonnumeric_database_totals_count"] == 0
    assert summary["source_field_family_counts"] == {"permits_2026": 813}
    assert (
        summary["draw_system_type_counts"].get("YOUTH_GENERAL_ANY_BULL_ELK")
        or summary["draw_system_type_counts"].get("YOUTH_DRAW_ONLY_ELK")
    ) == 1


def test_database_carries_explicit_2026_draw_subset_fields() -> None:
    rows = _by_code(DATABASE)

    assert rows["EB3022"]["permits_2026_draw_res"] == "130"
    assert rows["EB3022"]["permits_2026_draw_nr"] == "15"
    assert rows["EB3022"]["permits_2026_draw_total"] == "145"
    assert rows["EB3022"]["draw_2026_system_type"] == "BONUS_LE_BIG_GAME"

    assert rows["DB1002"]["permits_2026_draw_res"] == "1"
    assert rows["DB1002"]["permits_2026_draw_nr"] == "0"
    assert rows["DB1002"]["permits_2026_draw_total"] == "1"
    assert rows["DB1002"]["draw_2026_system_type"] == "BONUS_PLE_BIG_GAME"

    assert rows["BI6528"]["permits_2026_draw_total"] == "6"
    assert rows["BI6528"]["draw_2026_system_type"] == "BONUS_OIL_BIG_GAME"

    assert rows["EA2012"]["permits_2026_draw_res"] == ""
    assert rows["EA2012"]["permits_2026_draw_nr"] == ""
    assert rows["EA2012"]["permits_2026_draw_total"] == "400"
    assert rows["EA2012"]["draw_2026_system_type"] == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"

    assert rows["CG9999"]["permits_2026_draw_total"] == ""
    assert rows["CG9999"]["draw_2026_system_type"] == ""


def test_subset_export_matches_database_for_all_promoted_codes() -> None:
    db_rows = _by_code(DATABASE)
    subset_rows = _by_code(SUBSET)

    assert len(subset_rows) == 813
    for code, subset in subset_rows.items():
        database = db_rows[code]
        for field in (
            "permits_2026_draw_res",
            "permits_2026_draw_nr",
            "permits_2026_draw_total",
            "permits_2026_draw_source",
            "draw_2026_system_type",
        ):
            assert subset[field] == database[field]


def test_runtime_draw_surface_carries_the_2026_draw_subset_fields() -> None:
    ml_rows = [row for row in _read_csv(ML) if row.get("hunt_code") == "EB3022"]

    assert ml_rows
    assert all(row["permits_2026_draw_res"] == "130" for row in ml_rows)
    assert all(row["permits_2026_draw_nr"] == "15" for row in ml_rows)
    assert all(row["permits_2026_draw_total"] == "145" for row in ml_rows)
    assert all(row["draw_2026_system_type"] == "BONUS_LE_BIG_GAME" for row in ml_rows)


def test_hunt_master_duplicate_carries_2026_draw_subset_fields() -> None:
    rows = [row for row in _read_csv(HUNT_MASTER_DUPLICATE) if row.get("hunt_code") == "EB3022"]

    assert rows
    assert all(row["permits_2026_draw_res"] == "130" for row in rows)
    assert all(row["permits_2026_draw_nr"] == "15" for row in rows)
    assert all(row["permits_2026_draw_total"] == "145" for row in rows)
    assert all(row["draw_2026_system_type"] == "BONUS_LE_BIG_GAME" for row in rows)


def test_2026_draw_field_promotion_report_written() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["subset_hunt_code_count"] == 813
    assert report["files_written"] >= 10
    assert any(row["file"] == "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv" for row in report["promotion_results"])
    assert any(row["file"] == "processed_data/hunt_master_enriched_2026_draw_subset.csv" for row in report["promotion_results"])
