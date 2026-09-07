from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "processed_data"
SUMMARY = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_results_all_years_summary.json"
BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
LONG = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_results_all_years_long.csv"
OVERLAY = PROCESSED / "special_permit_overlay_classes_all_years.csv"


REQUIRED_OUTPUTS = [
    PROCESSED / "harvest_results_database_final_audit.csv",
    PROCESSED / "harvest_results_database_final_audit.json",
    PROCESSED / "harvest_results_database_final_audit.md",
    PROCESSED / "harvest_results_database_key_integrity_audit.csv",
    PROCESSED / "harvest_results_database_metric_integrity_audit.csv",
    PROCESSED / "harvest_results_database_year_coverage_audit.csv",
    PROCESSED / "harvest_results_database_hunt_code_alignment_audit.csv",
    PROCESSED / "harvest_results_database_feature_readiness_audit.csv",
    PROCESSED / "harvest_results_database_modeling_contract.md",
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_audit_script_runs_and_writes_all_required_outputs() -> None:
    subprocess.run([sys.executable, "scripts/audit-harvest-results-database-final.py"], cwd=ROOT, check=True)
    for path in REQUIRED_OUTPUTS:
        assert path.exists(), path


def test_reported_and_model_target_years_are_complete() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["unique_reported_hunt_years"] == [str(year) for year in range(2005, 2026)]
    assert sorted(summary["model_target_year_counts"]) == [str(year) for year in range(2006, 2027)]


def test_harvest_database_row_counts_are_above_required_thresholds() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["normalized_long_rows"] > 25000
    assert summary["best_by_year_hunt_code_rows"] > 5000


def test_harvest_rows_are_not_quota_or_direct_draw_probability_sources() -> None:
    for path in [LONG, BEST]:
        for row in rows(path):
            assert row["do_not_use_for_permit_quota"] == "True"
            assert row["do_not_use_directly_for_p_draw"] == "True"


def test_success_rate_math_conflicts_are_reported_not_silently_ignored() -> None:
    metric_rows = rows(PROCESSED / "harvest_results_database_metric_integrity_audit.csv")
    assert any("SUCCESS_RATE_MATH_CONFLICT" in row.get("flags", "") for row in metric_rows)


def test_special_permit_overlay_rows_remain_reconciliation_only() -> None:
    overlay_rows = rows(OVERLAY)
    assert overlay_rows
    assert all(row["permit_overlay_use"] == "TOTAL_PERMIT_RECONCILIATION_ONLY" for row in overlay_rows)
    assert all(row["public_draw_odds_use"] == "NO" for row in overlay_rows)
    assert all(row["p_draw_math_use"] == "NO" for row in overlay_rows)


def test_db1004_reconciliation_public_draw_plus_expo_not_conservation() -> None:
    expo_rows = []
    expo_root = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages" / "unknown_for_unknown_expo_hunt_code_reconciliation_user_corrected"
    expo_paths = list(expo_root.glob("*.csv"))
    if not expo_paths:
        pytest.skip("Optional R2-backed raw Expo package is not hydrated locally.")
    for path in expo_paths:
        expo_rows.extend(row for row in rows(path) if row.get("selected_hunt_code") == "DB1004")
    conservation_root = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages" / "2026_for_2026_conservation_overlay_truth_2026_species_corrected"
    conservation_hits = []
    for path in conservation_root.glob("*.csv"):
        conservation_hits.extend(row for row in rows(path) if "DB1004" in "|".join(row.values()))
    assert expo_rows
    assert not conservation_hits


def test_conservation_raw_overlay_remains_336_permits_per_year_and_not_p_draw() -> None:
    raw = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages" / "2026_for_2026_conservation_overlay_truth_2026_species_corrected" / "conservation_permit_raw_336_rows_expanded_2025_2027_species_corrected.csv"
    if not raw.exists():
        pytest.skip("Optional R2-backed raw conservation package is not hydrated locally.")
    raw_rows = rows(raw)
    by_year = {}
    for year in {"2025", "2026", "2027"}:
        year_rows = [row for row in raw_rows if row["permit_year"] == year]
        by_year[year] = len(year_rows)
        assert all(row["do_not_use_directly_for_p_draw"].lower() in {"yes", "true"} for row in year_rows)
        assert all(row["do_not_merge_into_public_draw_quota"].lower() in {"yes", "true"} for row in year_rows)
    assert by_year == {"2025": 336, "2026": 336, "2027": 336}


def test_black_bear_and_antlerless_elk_species_labels_are_normalized() -> None:
    species = {row["species"] for row in rows(BEST)}
    assert "Black Bear" in species
    assert "Antlerless Elk" in species
