from __future__ import annotations

import csv
from pathlib import Path

from engine.utah_predictive_mixed.quota import quota_adjusted_probability, quota_for_row


ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "processed_data" / "ml_draw_predictions_v1.csv"


def rows() -> list[dict[str, str]]:
    with ML.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def row(hunt_code: str, residency: str, points: str) -> dict[str, str]:
    return next(r for r in rows() if r["hunt_code"] == hunt_code and r["residency"] == residency and r["points"] == points)


def test_2026_official_quota_is_used_when_present() -> None:
    eb3022 = row("EB3022", "Resident", "7")
    quota, reasons = quota_for_row(eb3022)
    assert quota["quota_source_status"] == "official"
    assert quota["quota_source_year"] == "2026"
    assert quota["quota_2026_total"] == "130"
    assert "OFFICIAL_2026_QUOTA_USED" in reasons


def test_quota_adjustment_caps_and_codes() -> None:
    p, ratio, reasons = quota_adjusted_probability(0.5, 10, 100)
    assert p == 1.0
    assert ratio == 2.0
    assert "QUOTA_RATIO_CAPPED_HIGH" in reasons


def test_zero_quota_is_preserved_as_nonpredictive() -> None:
    row = {
        "residency": "Nonresident",
        "permits_2026_nr": "0",
        "permits_2026_total": "14",
    }
    quota, reasons = quota_for_row(row)
    assert quota["quota_2026_total"] == "0"
    assert quota["quota_2026_max_pool"] == "0"
    assert quota["quota_2026_random_pool"] == "0"
    assert "ZERO_QUOTA_NONPREDICTIVE" in reasons


def test_total_only_permits_do_not_create_residency_lane_quota() -> None:
    row = {
        "residency": "Resident",
        "permits_2026_total": "1160",
    }
    quota, reasons = quota_for_row(row)
    assert quota["quota_2026_total"] == "1160"
    assert quota["quota_2026_max_pool"] == ""
    assert quota["quota_2026_random_pool"] == ""
    assert "TOTAL_ONLY_PERMIT_AUTHORITY" in reasons
    assert "NO_RESIDENCY_SPLIT_PUBLISHED" in reasons
    assert "NO_RESIDENCY_LANE_QUOTA" in reasons


def test_total_only_permits_can_remain_total_scope_without_split() -> None:
    row = {
        "residency": "",
        "permits_2026_total": "1160",
    }
    quota, reasons = quota_for_row(row)
    assert quota["quota_2026_total"] == "1160"
    assert quota["quota_2026_max_pool"] == "580"
    assert quota["quota_2026_random_pool"] == "580"
    assert "NO_RESIDENCY_LANE_QUOTA" not in reasons


def test_no_published_permits_do_not_create_quota() -> None:
    row = {
        "residency": "Resident",
        "permits_2026_source": "2026_HUNT_PLANNER_PERMIT_DATA_NOT_PUBLISHED",
        "permit_allotment_2026_status": "PRIVATE_LAND_DEER_NO_PUBLISHED_PERMIT_COUNT",
    }
    quota, reasons = quota_for_row(row)
    assert quota["quota_2026_total"] == ""
    assert quota["quota_2026_max_pool"] == ""
    assert quota["quota_2026_random_pool"] == ""
    assert quota["quota_source_status"] == "no_published"
    assert "NO_PUBLISHED_PERMIT_AUTHORITY" in reasons
    assert "PUBLIC_DRAW_ODDS_EXCLUDED_NO_QUOTA" in reasons


def test_zero_current_quota_defaults_probability_ratio() -> None:
    p, ratio, reasons = quota_adjusted_probability(0.5, 10, 0)
    assert p == 0.5
    assert ratio == 1.0
    assert "QUOTA_RATIO_DEFAULTED" in reasons
    assert "ZERO_QUOTA_NONPREDICTIVE" in reasons
