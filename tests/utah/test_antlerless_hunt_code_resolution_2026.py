from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AUDIT_SUMMARY = ROOT / "processed_data/2024_antlerless_draw_results_audit.json"
PROMOTION_SUMMARY = ROOT / "processed_data/2026_antlerless_predictive_v2_reference_promotion_summary.json"
RECONCILIATION_SUMMARY = ROOT / "processed_data/2026_antlerless_hunt_code_reconciliation_summary.json"
DRAW_ROWS = ROOT / "data_truth/draw_results_truth/extracted/2024_antlerless_draw_results_hunt_rows.csv"
RECONCILIATION = ROOT / "data_truth/draw_results_truth/validation/2026_antlerless_hunt_code_reconciliation.csv"
PREDICTIVE = ROOT / "processed_data/draw_reality_engine_predictive_v2.csv"

@pytest.fixture(scope="module")
def isolated_outputs(tmp_path_factory):
    """Exercise the real PDF without ever rewriting retained runtime artifacts."""
    folder = tmp_path_factory.mktemp("real_pdf_resolver")
    spec = importlib.util.spec_from_file_location("isolated_real_antlerless_resolver", ROOT / "scripts/resolve-antlerless-hunt-codes-2026.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # PREDICTIVE is both an input and an output; use a copy, not the live path.
    original_predictive = module.PREDICTIVE
    output_names = ("TEXT_LINES_CSV", "DRAW_ROWS_CSV", "CODE_RECONCILIATION_CSV",
                    "PROMOTION_DETAIL_CSV", "AUDIT_JSON", "AUDIT_MD", "PROMOTION_JSON",
                    "RECONCILIATION_JSON", "RECONCILIATION_MD", "PREDICTIVE")
    retained_hashes = {getattr(module, name): module.sha256(getattr(module, name))
                       for name in output_names if getattr(module, name).exists()}
    for name in output_names:
        setattr(module, name, folder / getattr(module, name).name)
    shutil.copy2(original_predictive, module.PREDICTIVE)
    assert module.main() == 0
    assert all(module.sha256(path) == digest for path, digest in retained_hashes.items())
    return module


def test_antlerless_hunt_code_resolution_runs_and_writes_outputs(isolated_outputs) -> None:
    AUDIT_SUMMARY = isolated_outputs.AUDIT_JSON
    PROMOTION_SUMMARY = isolated_outputs.PROMOTION_JSON
    RECONCILIATION_SUMMARY = isolated_outputs.RECONCILIATION_JSON
    DRAW_ROWS = isolated_outputs.DRAW_ROWS_CSV
    RECONCILIATION = isolated_outputs.CODE_RECONCILIATION_CSV

    assert AUDIT_SUMMARY.exists()
    assert PROMOTION_SUMMARY.exists()
    assert RECONCILIATION_SUMMARY.exists()
    assert DRAW_ROWS.exists()
    assert RECONCILIATION.exists()

    audit = json.loads(AUDIT_SUMMARY.read_text(encoding="utf-8"))
    assert audit["classification"] == "ANTLERLESS_DRAW_RESULTS_TRUTH_SOURCE_AUDIT"
    assert audit["source_sha256"] == "2b1b19782089732b9cacc2fd9ce00e60e1093acda6f3ed70d29e8d6e3ae83b08"
    assert audit["source_sha256"] == audit["expected_sha256"]
    assert audit["pdf_pages"] == 203
    assert audit["text_lines"] == 5491
    assert audit["draw_result_rows"] == 198
    assert audit["unique_draw_result_hunt_codes"] == 198
    assert audit["draw_result_prefix_counts"] == {"DA": 21, "EA": 158, "MA": 2, "PD": 16, "RE": 1}
    assert audit["blockers"] == 0

    reconciliation = json.loads(RECONCILIATION_SUMMARY.read_text(encoding="utf-8"))
    assert reconciliation["classification"] == "ANTLERLESS_HUNT_CODE_RECONCILIATION"
    assert reconciliation["target_prefixes"] == ["DA", "EA", "PD", "RE"]
    assert reconciliation["current_database_code_count"] == 418
    assert reconciliation["draw_results_2024_code_count"] == 196
    assert reconciliation["current_database_codes_present_in_2024_draw_results_count"] == 196
    assert reconciliation["current_database_reconciliation_failure_count"] == 0
    assert reconciliation["blockers"] == 0


def test_antlerless_reference_codes_promoted_without_modeling_odds(isolated_outputs) -> None:
    PROMOTION_SUMMARY = isolated_outputs.PROMOTION_JSON
    PREDICTIVE = isolated_outputs.PREDICTIVE
    promotion = json.loads(PROMOTION_SUMMARY.read_text(encoding="utf-8"))
    assert promotion["classification"] == "ANTLERLESS_REFERENCE_PROMOTION"
    assert promotion["target_prefixes"] == ["DA", "EA", "PD", "RE"]
    assert promotion["still_missing_predictive_hunt_code_count"] == 0
    assert promotion["duplicate_reference_key_count"] == 0

    promoted_codes = set(promotion["promoted_reference_hunt_codes"])
    assert len(promoted_codes) == promotion["promoted_reference_hunt_code_count"]
    assert promoted_codes

    with PREDICTIVE.open(newline="", encoding="utf-8-sig") as handle:
        reference_rows = [
            row
            for row in csv.DictReader(handle)
            if row["model_version"] == "antlerless_reference_v1.0.0"
            and row["hunt_code"] in promoted_codes
        ]

    assert {row["hunt_code"] for row in reference_rows} == promoted_codes
    assert {row["algorithm_status"] for row in reference_rows} == {"ANTLERLESS_REFERENCE"}
    assert {row["modeled_by_engine"] for row in reference_rows} == {"False"}
    assert {row["probability_model"] for row in reference_rows} == {"NONE"}
    assert {row["display_odds_text"] for row in reference_rows} == {"Antlerless reference only; odds not modeled"}
    assert {row["data_quality_grade"] for row in reference_rows} == {"A"}

    probability_fields = ("p_draw", "p_draw_mean", "p_draw_pct", "certified_p_draw", "certified_p_draw_mean", "certified_p_draw_pct")
    assert all(not any(row.get(field, "").strip() for field in probability_fields) for row in reference_rows)


def test_antlerless_reconciliation_distinguishes_prior_draw_and_current_reference_basis(isolated_outputs) -> None:
    RECONCILIATION = isolated_outputs.CODE_RECONCILIATION_CSV
    DRAW_ROWS = isolated_outputs.DRAW_ROWS_CSV
    with RECONCILIATION.open(newline="", encoding="utf-8-sig") as handle:
        rows = {row["hunt_code"]: row for row in csv.DictReader(handle)}
    with DRAW_ROWS.open(newline="", encoding="utf-8-sig") as handle:
        prior_draw_codes = {row["hunt_code"] for row in csv.DictReader(handle)}

    for code in ("EA1010", "EA1007", "PD1039", "RE1000"):
        in_prior_draw = code in prior_draw_codes
        assert rows[code]["present_in_2024_antlerless_draw_results"] == str(in_prior_draw).lower()
        assert rows[code]["source_basis"] == (
            "prior_2024_antlerless_draw_results"
            if in_prior_draw
            else "current_2026_database_reference_only"
        )
        assert rows[code]["current_database_reconciliation_status"] == "PASS"
