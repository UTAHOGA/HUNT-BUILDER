from __future__ import annotations

import csv
import json
from pathlib import Path

from engine.utah.quality.build_harvest_quality_history import run


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    _write_csv(
        repo / "processed_data/harvest-metrics-2024-bg-report.csv",
        [
            {"huntCode": "EB1001", "permits": 10, "hunters": 8, "harvest": 4, "percentSuccess": 50, "avgDays": 5.5, "avgSatisfaction": 4.2},
            {"huntCode": "DB2001", "permits": 5, "hunters": 5, "harvest": 5, "percentSuccess": 100, "avgDays": 2, "avgSatisfaction": 5},
        ],
        ["huntCode", "permits", "hunters", "harvest", "percentSuccess", "avgDays", "avgSatisfaction"],
    )
    _write_csv(
        repo / "data_model/quality/harvest_quality_2025_for_2026.csv",
        [
            {
                "reported_hunt_year": 2025,
                "model_target_year": 2026,
                "hunt_code": "EB1001",
                "hunt_name": "Example Elk",
                "species": "Elk",
                "hunters": 10,
                "harvest": 6,
                "percent_success": 60,
                "avg_days": 4,
                "satisfaction": 4.5,
                "source_file": "example-2025.pdf",
                "canonical_match_status": "DATABASE_MATCHED",
                "validation_notes": "VALID",
            }
        ],
        [
            "reported_hunt_year",
            "model_target_year",
            "hunt_code",
            "hunt_name",
            "species",
            "hunters",
            "harvest",
            "percent_success",
            "avg_days",
            "satisfaction",
            "source_file",
            "canonical_match_status",
            "validation_notes",
        ],
    )
    _write_csv(
        repo / "processed_data/hunt_master_enriched.csv",
        [
            {"hunt_code": "EB1001", "hunt_name": "Example Elk", "species": "Elk", "weapon": "Any Legal Weapon", "hunt_type": "Limited Entry"},
            {"hunt_code": "DB2001", "hunt_name": "Example Deer", "species": "Deer", "weapon": "Any Legal Weapon", "hunt_type": "Limited Entry"},
        ],
        ["hunt_code", "hunt_name", "species", "weapon", "hunt_type"],
    )
    _write_csv(
        repo / "processed_data/ml_draw_predictions_v1.csv",
        [
            {"hunt_code": "EB1001", "residency": "Resident", "points": 1, "p_draw": "0.25", "p_draw_pct": "25", "p_bonus_pool": "0.1", "p_random_pool": "0.15", "p_preference_draw": ""},
            {"hunt_code": "DB2001", "residency": "Resident", "points": 1, "p_draw": "", "p_draw_pct": "", "p_bonus_pool": "", "p_random_pool": "", "p_preference_draw": ""},
        ],
        ["hunt_code", "residency", "points", "p_draw", "p_draw_pct", "p_bonus_pool", "p_random_pool", "p_preference_draw"],
    )
    _write_csv(
        repo / "processed_data/draw_reality_engine_predictive_v2.csv",
        [
            {"hunt_code": "EB1001", "residency": "Resident", "points": 1, "p_draw": "0.25", "p_draw_pct": "25", "p_bonus_pool": "0.1", "p_random_pool": "0.15", "p_preference_draw": ""},
        ],
        ["hunt_code", "residency", "points", "p_draw", "p_draw_pct", "p_bonus_pool", "p_random_pool", "p_preference_draw"],
    )
    return repo


def test_harvest_2024_source_inventory_written(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=False)
    assert (repo / "data_truth/harvest_results_truth/harvest_2024_source_inventory.csv").exists()
    payload = json.loads((repo / "data_truth/harvest_results_truth/harvest_2024_source_inventory.json").read_text())
    assert payload["source_count"] >= 1


def test_harvest_2024_normalized_truth_written(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=False)
    out = repo / "data_truth/harvest_results_truth/normalized/harvest_results_2024_for_2026_long.csv"
    assert out.exists()
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert {row["reported_hunt_year"] for row in rows} == {"2024"}
    assert {row["model_target_year"] for row in rows} == {"2026"}
    assert {row["source_class"] for row in rows} == {"harvest_results"}


def test_harvest_2024_quality_features_written(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=False)
    rows = list(csv.DictReader((repo / "data_model/quality/harvest_quality_2024_for_2026.csv").open(newline="", encoding="utf-8")))
    assert "harvest_success_percent_2024" in rows[0]
    assert "harvest_2024" in rows[0]
    assert "harvest_average_days_2024" in rows[0]


def test_harvest_quality_history_contains_2024_and_2025(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=False)
    rows = list(csv.DictReader((repo / "data_model/quality/harvest_quality_history_for_2026.csv").open(newline="", encoding="utf-8")))
    assert {row["reported_hunt_year"] for row in rows} >= {"2024", "2025"}


def test_harvest_quality_wide_features_include_2024_2025_deltas(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=False)
    rows = list(csv.DictReader((repo / "data_model/quality/harvest_quality_2024_2025_features_for_2026.csv").open(newline="", encoding="utf-8")))
    assert "harvest_success_percent_delta_2024_to_2025" in rows[0]
    eb = next(row for row in rows if row["hunt_code"] == "EB1001")
    assert eb["harvest_success_percent_delta_2024_to_2025"] == "10"


def test_harvest_2024_not_used_as_2026_permit_quota(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=True)
    audit = json.loads((repo / "processed_data/harvest_2024_integration_audit.json").read_text())
    assert audit["harvest_2024_used_as_2026_permit_quota"] is False
    assert audit["harvest_2024_used_as_official_2026_allotment"] is False


def test_harvest_2024_probability_fields_are_preserved(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    before = list(csv.DictReader((repo / "processed_data/ml_draw_predictions_v1.csv").open(newline="", encoding="utf-8")))
    run(repo_root=repo, model_target_year=2026, update_predictive=True)
    after = list(csv.DictReader((repo / "processed_data/ml_draw_predictions_v1.csv").open(newline="", encoding="utf-8")))
    before_probs = [(r["hunt_code"], r["p_draw"], r["p_draw_pct"], r["p_bonus_pool"], r["p_random_pool"], r["p_preference_draw"]) for r in before]
    after_probs = [(r["hunt_code"], r["p_draw"], r["p_draw_pct"], r["p_bonus_pool"], r["p_random_pool"], r["p_preference_draw"]) for r in after]
    assert before_probs == after_probs
    assert "harvest_success_percent_2024" in after[0]


def test_harvest_2024_integration_audit_written(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    run(repo_root=repo, model_target_year=2026, update_predictive=True)
    assert (repo / "processed_data/harvest_2024_integration_audit.json").exists()
    assert (repo / "processed_data/harvest_2024_integration_audit.md").exists()
    audit = json.loads((repo / "processed_data/harvest_2024_integration_audit.json").read_text())
    assert audit["conclusion"] == "2024_HARVEST_DATABASE_COMPLETE_AND_INTEGRATED_AS_QUALITY_FEATURES"
    assert audit["harvest_2024_changes_p_draw"] is False
