from __future__ import annotations

import csv
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "processed_data" / "mixed_predictive_engine_2026_summary.json"
OVERLAY_RAW = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages" / "2026_for_2026_conservation_overlay_truth_2026_species_corrected" / "conservation_permit_raw_336_rows_expanded_2025_2027_species_corrected.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_special_permit_overlays_do_not_enter_public_draw_odds() -> None:
    import json

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["special_permit_guardrail_result"] == "PASS"


def test_db1004_expo_reconciles_but_conservation_does_not_explain_gap() -> None:
    import json

    result = json.loads(SUMMARY.read_text(encoding="utf-8"))["db1004_reconciliation"]
    assert result["public_draw_2025_permits"] == "80"
    assert result["expo_permits"] == "3"
    assert result["all_class_total"] == "83"
    assert result["conservation_used"] is False


def test_conservation_remains_336_permits_per_year() -> None:
    if not OVERLAY_RAW.exists():
        pytest.skip("optional raw conservation source is not hydrated in this checkout")
    rows = read_csv(OVERLAY_RAW)
    assert {year: sum(1 for r in rows if r["permit_year"] == year) for year in ["2025", "2026", "2027"]} == {
        "2025": 336,
        "2026": 336,
        "2027": 336,
    }
