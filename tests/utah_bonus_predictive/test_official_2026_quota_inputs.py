from __future__ import annotations

import csv
from pathlib import Path

from engine.utah_bonus_predictive.forecast import normalize_quota_reason_codes
from scripts.build_predictive_bonus_engine_v1 import build_predictions


REPO = Path(__file__).resolve().parents[2]
OFFICIAL_QUOTA_FILE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
RAC_LE_ELK_FILE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "2026_rac_limited_entry_bull_elk_permits.csv"
HISTORY_FILE = REPO / "data_model" / "runtime_drafts" / "draw_reality_engine_v2.csv"
ML_OUTPUT = REPO / "processed_data" / "ml_draw_predictions_v1.csv"
SUCCESSOR_OUTPUT = REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv"
LADDER_OUTPUT = REPO / "processed_data" / "point_ladder_view.csv"

REQUIRED_QUOTA_FIELDS = {
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "quota_source_status",
    "quota_source_year",
    "quota_source_file",
    "projected_2026_max_cutoff_point",
    "projected_2026_random_pool_start_point",
    "is_2026_max_point_pool",
    "is_2026_mixed_cutoff",
    "is_2026_random_pool",
    "p_max_pool_mean",
    "p_random_mean",
    "p_draw_mean",
    "reason_codes",
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _headers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return set(csv.DictReader(handle).fieldnames or [])


def _db_row(hunt_code: str) -> dict[str, str]:
    return next(row for row in _rows(OFFICIAL_QUOTA_FILE) if row["hunt_code"] == hunt_code)


def _output_row(path: Path, hunt_code: str, residency: str, points: int) -> dict[str, str]:
    return next(
        row
        for row in _rows(path)
        if row["hunt_code"] == hunt_code
        and row["residency"] == residency
        and int(float(row["points"])) == points
    )


def test_official_2026_quota_source_file_exists_and_is_database_csv() -> None:
    assert OFFICIAL_QUOTA_FILE.exists()
    assert OFFICIAL_QUOTA_FILE.name == "DATABASE.csv"
    assert "permits_2026_res" in _headers(OFFICIAL_QUOTA_FILE)
    assert "permits_2026_nr" in _headers(OFFICIAL_QUOTA_FILE)
    assert "permits_2026_total" in _headers(OFFICIAL_QUOTA_FILE)
    assert RAC_LE_ELK_FILE.exists()
    assert "permits_2026_res" in _headers(RAC_LE_ELK_FILE)
    assert "permits_2026_nr" in _headers(RAC_LE_ELK_FILE)
    assert "permits_2026_total" in _headers(RAC_LE_ELK_FILE)


def test_materialized_outputs_include_official_quota_contract_fields() -> None:
    for path in (ML_OUTPUT, SUCCESSOR_OUTPUT, LADDER_OUTPUT):
        assert REQUIRED_QUOTA_FIELDS.issubset(_headers(path))


def test_eb3022_resident_prediction_uses_official_2026_quota_not_2025_result() -> None:
    db = _db_row("EB3022")
    row = _output_row(ML_OUTPUT, "EB3022", "Resident", 7)

    assert db["permits_2026_res"] == "130"
    assert row["public_permits_2025"] == "160"
    assert row["public_permits_2026"] == "130"
    assert row["quota_2026_total"] == "130"
    assert row["quota_2026_max_pool"] == "65"
    assert row["quota_2026_random_pool"] == "65"
    assert row["quota_source_status"] == "official"
    assert row["quota_source_year"] == "2026"
    assert row["quota_source_file"] == "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    assert "OFFICIAL_2026_QUOTA_USED" in row["reason_codes"]


def test_deprecated_quota_reason_codes_are_scrubbed() -> None:
    normalized = normalize_quota_reason_codes(
        "BONUS_RULE_SIMULATED|RAC_CURRENT_YEAR_ALLOTMENT_USED|DATABASE_2026_PERMITS_USED|OFFICIAL_2026_QUOTA_USED"
    )

    assert "RAC_CURRENT_YEAR_ALLOTMENT_USED" not in normalized
    assert "DATABASE_2026_PERMITS_USED" not in normalized
    assert "OFFICIAL_2026_QUOTA_USED" in normalized


def test_2026_official_quota_fields_drive_cutoff_and_probability_outputs() -> None:
    row_7 = _output_row(SUCCESSOR_OUTPUT, "EB3022", "Resident", 7)
    row_6 = _output_row(SUCCESSOR_OUTPUT, "EB3022", "Resident", 6)

    assert row_7["projected_2026_max_cutoff_point"] == "7.0"
    assert row_7["projected_2026_random_pool_start_point"] == "6"
    assert row_7["is_2026_mixed_cutoff"] == "True"
    assert row_7["quota_2026_total"] == "130"
    assert row_7["quota_2026_max_pool"] == "65"
    assert row_7["quota_2026_random_pool"] == "65"
    assert 0.0 < float(row_7["p_max_pool_mean"]) < 1.0
    assert 0.0 < float(row_7["p_random_mean"]) < 1.0
    assert 0.0 < float(row_7["p_draw_mean"]) < 1.0
    assert row_6["is_2026_random_pool"] == "True"
    assert row_6["p_max_pool_mean"] == "0.000000"
    assert 0.0 < float(row_6["p_random_mean"]) < 1.0


def test_quota_change_regression_changes_projected_probability() -> None:
    history_rows = [
        row
        for row in _rows(HISTORY_FILE)
        if row["hunt_code"] == "EB3022" and row["residency"] == "Resident"
    ]
    official_db = _db_row("EB3022")
    quota_2025_like = dict(
        official_db,
        permits_2026_res="160",
        permits_2026_nr="15",
        permits_2026_total="175",
    )
    quota_2026_official = dict(
        official_db,
        permits_2026_res="130",
        permits_2026_nr="15",
        permits_2026_total="145",
    )

    predictions_2025_quota, _ = build_predictions(
        history_rows,
        {"EB3022": quota_2025_like},
        prediction_year=2026,
        iterations=10,
        seed=2026,
    )
    predictions_2026_quota, _ = build_predictions(
        history_rows,
        {"EB3022": quota_2026_official},
        prediction_year=2026,
        iterations=10,
        seed=2026,
    )

    row_2025_quota = next(row for row in predictions_2025_quota if row["points"] == 7)
    row_2026_quota = next(row for row in predictions_2026_quota if row["points"] == 7)

    assert row_2025_quota["quota_2026_total"] == 160
    assert row_2026_quota["quota_2026_total"] == 130
    assert row_2025_quota["quota_2026_max_pool"] == 80
    assert row_2026_quota["quota_2026_max_pool"] == 65
    assert row_2025_quota["p_max_pool_mean"] != row_2026_quota["p_max_pool_mean"]
    assert row_2025_quota["p_random_mean"] != row_2026_quota["p_random_mean"]
    assert row_2025_quota["p_draw_mean"] != row_2026_quota["p_draw_mean"]


def test_historical_random_results_are_not_copied_as_2026_predictions() -> None:
    ladder_row = _output_row(LADDER_OUTPUT, "EB3024", "Resident", 12)

    assert ladder_row["display_2025_draw_results"] == "~1 in 49.0 or 2.0%"
    assert ladder_row["display_2026_random_draw"] != ladder_row["display_2025_draw_results"]
    assert ladder_row["random_draw_model_source"] == "p_random_pool"
