from __future__ import annotations

import csv
from pathlib import Path

from engine.utah.quality.harvest_feature_model import (
    clean_numeric,
    demand_pressure_signal,
    fallback_feature_selection,
    harvest_quality_index,
    point_creep_quality_adjustment,
    rolling_mean,
    safe_rate,
    trend_delta,
    trend_direction,
)
from engine.utah.quality.materialize_harvest_feature_model import build_feature_row


ROOT = Path(__file__).resolve().parents[2]
BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
FEATURES = ROOT / "data_model" / "harvest_quality" / "harvest_feature_model_by_hunt_code_2026.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_numeric_helpers_preserve_missing_and_compute_safe_values() -> None:
    assert clean_numeric("") is None
    assert clean_numeric("–") is None
    assert clean_numeric("1,234.5") == 1234.5
    assert safe_rate(5, 10) == 0.5
    assert safe_rate(5, 0) is None
    assert rolling_mean([None, "1", "2", "3"], years=3)[0] == 2.0
    assert trend_delta(10, 7) == 3
    assert trend_direction(4, 3) == "INCREASING"


def test_harvest_quality_and_demand_signals_are_bounded() -> None:
    row = {
        "harvest_success_recent": "67",
        "hunter_satisfaction_recent": "4.1",
        "average_age_recent": "6.2",
        "harvest_success_delta_1yr": "4",
        "hunter_effort_days_recent": "3.0",
    }
    quality, quality_reasons = harvest_quality_index(row)
    row["harvest_quality_index"] = quality
    signal, category, demand_reasons = demand_pressure_signal(row)
    adjustment = point_creep_quality_adjustment(row)
    assert quality is not None and 0 <= quality <= 100
    assert signal is not None and 0 <= signal <= 100
    assert category in {"LOW_DEMAND_SIGNAL", "MODERATE_DEMAND_SIGNAL", "HIGH_DEMAND_SIGNAL"}
    assert -0.25 <= adjustment <= 0.25
    assert "QUALITY_INDEX_COMPONENT_REWEIGHTED" in quality_reasons + demand_reasons


def test_exact_hunt_code_history_produces_exact_match() -> None:
    history = rows(BEST)
    selection = fallback_feature_selection("DB1004", "Deer", "Paunsaugunt Premium", 2026, history)
    assert selection.match_method == "EXACT_HUNT_CODE_HISTORY"


def test_new_2026_hunt_without_direct_history_uses_fallback_or_no_history() -> None:
    history = rows(BEST)
    selection = fallback_feature_selection("EA1287", "Elk", "Box Elder, Grouse Creek", 2026, history)
    assert selection.match_method in {
        "SAME_HUNT_NAME_SPECIES_HISTORY",
        "UNIT_SPECIES_HISTORY",
        "NO_HARVEST_HISTORY",
    }


def test_same_code_with_wrong_name_is_not_an_exact_history_match() -> None:
    history = [
        {
            "reported_hunt_year": "2025",
            "hunt_code": "EA1270",
            "species": "Elk",
            "hunt_name": "Manti",
            "percent_success": "50",
        }
    ]
    selection = fallback_feature_selection("EA1270", "Elk", "Fishlake (Conservation)", 2026, history)

    assert selection.match_method != "EXACT_HUNT_CODE_HISTORY"
    assert "HUNT_CODE_NAME_OR_SPECIES_MISMATCH_REJECTED" in selection.reason_codes


def test_unrelated_species_history_is_not_used_as_an_age_substitute() -> None:
    history = [
        {
            "reported_hunt_year": "2025",
            "hunt_code": "EB3001",
            "species": "Elk",
            "hunt_name": "Beaver",
            "average_age": "9.6",
        }
    ]

    selection = fallback_feature_selection("EB3999", "Elk", "Cactus Ranch", 2026, history)

    assert selection.rows == []
    assert selection.match_method == "NO_HARVEST_HISTORY"
    assert selection.data_quality_grade == "F"
    assert "SPECIES_WIDE_FALLBACK_PROHIBITED" in selection.reason_codes


def test_feature_model_keeps_reported_and_computed_three_year_age_separate() -> None:
    db_row = {"hunt_code": "DB1000", "species": "Deer", "hunt_name": "Henry Mountains"}
    history = [
        {
            "reported_hunt_year": "2024",
            "hunt_code": "DB1000",
            "species": "Deer",
            "hunt_name": "Henry Mountains",
            "percent_success": "55",
        }
    ]
    age_rows = [
        {"reported_hunt_year": "2022", "hunt_code": "DB1000", "species": "Limited Entry Buck Deer", "average_harvest_age": "5.7", "average_harvest_age_3yr": "5.5"},
        {"reported_hunt_year": "2023", "hunt_code": "DB1000", "species": "Limited Entry Buck Deer", "average_harvest_age": "6.0", "average_harvest_age_3yr": "5.7"},
        {"reported_hunt_year": "2024", "hunt_code": "DB1000", "species": "Limited Entry Buck Deer", "average_harvest_age": "6.6", "average_harvest_age_3yr": "6.1"},
    ]

    feature = build_feature_row(db_row, history, 2026, age_rows)

    assert feature["average_harvest_age_recent"] == "6.6"
    assert feature["average_harvest_age_3yr_reported"] == "6.1"
    assert feature["average_harvest_age_3yr_computed"] == "6.1"
    assert feature["average_age_recent"] == feature["average_harvest_age_recent"]
    assert feature["average_age_3yr_avg"] == feature["average_harvest_age_3yr_computed"]


def test_materialized_feature_ranges_are_valid() -> None:
    feature_rows = rows(FEATURES)
    assert feature_rows
    for row in feature_rows:
        if row["harvest_quality_index"]:
            assert 0 <= float(row["harvest_quality_index"]) <= 100
        if row["demand_pressure_signal"]:
            assert 0 <= float(row["demand_pressure_signal"]) <= 100
        if row["point_creep_quality_adjustment"]:
            assert -0.25 <= float(row["point_creep_quality_adjustment"]) <= 0.25
