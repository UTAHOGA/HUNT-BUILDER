from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "processed_data"
ML = PROCESSED / "ml_draw_predictions_v1.csv"
SUCCESSOR = PROCESSED / "draw_reality_engine_predictive_v2.csv"
ML_WITH_FEATURES = ROOT / "data_model" / "harvest_quality" / "ml_draw_predictions_with_harvest_features.csv"
SUCCESSOR_WITH_FEATURES = ROOT / "data_model" / "harvest_quality" / "draw_reality_engine_predictive_with_harvest_features.csv"
AUDIT = PROCESSED / "harvest_feature_model_audit.json"

PROTECTED_FIELDS = [
    "p_draw",
    "p_draw_mean",
    "p_random_mean",
    "p_max_pool_mean",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permit_allotment_2026_source",
    "permit_allotment_2026_source_file",
    "permit_allotment_2026_status",
    "public_permits_2026",
    "public_permits_2026_source",
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def protected(rows_: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{field: row.get(field, "") for field in PROTECTED_FIELDS if field in row} for row in rows_]


def test_materializer_runs_and_reports_guardrails_passed() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.utah.quality.materialize_harvest_feature_model",
            "--output-dir",
            "processed_data",
            "--forecast-year",
            "2026",
        ],
        cwd=ROOT,
        check=True,
    )
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["protected_probability_and_quota_fields_unchanged"] is True
    assert audit["harvest_quality_index_count"] > 0
    assert audit["demand_pressure_signal_count"] > 0


def test_harvest_features_do_not_change_probability_fields() -> None:
    assert protected(rows(ML)) == protected(rows(ML_WITH_FEATURES))
    assert protected(rows(SUCCESSOR)) == protected(rows(SUCCESSOR_WITH_FEATURES))


def test_harvest_features_do_not_change_2026_quota_or_allotment_fields() -> None:
    ml_original = protected(rows(ML))
    ml_joined = protected(rows(ML_WITH_FEATURES))
    successor_original = protected(rows(SUCCESSOR))
    successor_joined = protected(rows(SUCCESSOR_WITH_FEATURES))
    for before, after in [(ml_original, ml_joined), (successor_original, successor_joined)]:
        for original_row, joined_row in zip(before, after):
            for field in ["quota_2026_total", "quota_2026_max_pool", "quota_2026_random_pool", "permit_allotment_2026_total", "public_permits_2026"]:
                if field in original_row:
                    assert original_row[field] == joined_row[field]


def test_harvest_permit_counts_do_not_overwrite_public_draw_permit_counts() -> None:
    joined_rows = rows(ML_WITH_FEATURES)
    assert "permits" not in joined_rows[0]
    assert "harvest_quality_index" in joined_rows[0]
    assert any(row.get("public_permits_2026") for row in joined_rows)
