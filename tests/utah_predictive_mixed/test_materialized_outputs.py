from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "processed_data" / "ml_draw_predictions_v1.csv"
SUMMARY = ROOT / "processed_data" / "mixed_predictive_engine_2026_summary.json"
SPORTSMAN = ROOT / "processed_data" / "sportsman_permit_predictions_v1.csv"
RUNTIME_PROMOTION = ROOT / "processed_data" / "runtime_family_promotion_report.json"


def rows() -> list[dict[str, str]]:
    with ML.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sportsman_rows() -> list[dict[str, str]]:
    with SPORTSMAN.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_materialized_outputs_have_required_fields_and_no_duplicate_keys() -> None:
    data = rows()
    required = {"p_prior_year_baseline", "p_quota_adjusted", "p_rollover_adjusted", "p_harvest_adjusted", "display_odds_text"}
    assert required.issubset(data[0])
    keys = [(r["hunt_code"], r["residency"], r["points"], r["draw_pool"]) for r in data]
    assert len(keys) == len(set(keys))
    assert json.loads(SUMMARY.read_text(encoding="utf-8"))["duplicate_key_count"] == 0


def test_summary_reports_guardrails_and_accepted_harvest_warning_policy() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["probability_field_guardrail_result"] == "PASS"
    assert summary["quota_guardrail_result"] == "PASS"
    assert summary["special_permit_guardrail_result"] == "PASS"
    assert summary["harvest_audit_blocker_count"] == 0
    assert summary["harvest_audit_warning_count"] == 15529


def test_availability_and_allocation_rows_have_blank_p_draw() -> None:
    for row in rows():
        if row["algorithm_status"] in {"MODELED_AVAILABILITY", "MODELED_ALLOCATION"}:
            assert row["p_draw_mean"] == ""
            assert row["p_draw"] == ""


def test_sportsman_rows_use_sportsman_model_only() -> None:
    merged_sportsman = [row for row in rows() if row["algorithm_status"] == "MODELED_SPORTSMAN_DRAW"]
    assert merged_sportsman
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in merged_sportsman)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in merged_sportsman)
    assert all(row["residency"] == "Resident" for row in merged_sportsman)
    assert all(row["p_sportsman_draw"] == row["p_draw"] for row in merged_sportsman)
    sportsman = [row for row in sportsman_rows() if row["algorithm_status"] == "MODELED_SPORTSMAN_DRAW"]
    assert sportsman
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in sportsman)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in sportsman)


def test_approved_family_rows_are_promoted_to_runtime() -> None:
    data = rows()
    promoted = [row for row in data if row["runtime_promotion_status"] == "PROMOTED_TO_RUNTIME"]
    assert promoted
    expected_counts = {
        "SPORTSMAN_RANDOM_ONLY": 10,
        "YOUTH_GENERAL_ANY_BULL_ELK": 2,
        "PREFERENCE_DEDICATED_HUNTER_DEER": 1430,
        "BONUS_TURKEY": 240,
        "YOUTH_TURKEY_SET_ASIDE": 232,
    }
    report = json.loads(RUNTIME_PROMOTION.read_text(encoding="utf-8"))
    report_by_family = {row["runtime_promotion_family"]: row for row in report["families"]}
    assert set(report_by_family) == set(expected_counts)
    assert {row["runtime_promotion_family"] for row in promoted} == set(expected_counts)
    for family, expected_count in expected_counts.items():
        family_rows = [row for row in promoted if row["runtime_promotion_family"] == family]
        assert len(family_rows) == expected_count
        assert all(row["runtime_promotion_decision"] == "APPROVED_RUNTIME_PROMOTION_2026_06_29" for row in family_rows)
        assert all(row["runtime_promotion_source"] == report_by_family[family]["source_report"] for row in family_rows)
        assert all(row["runtime_promotion_source_report"] == report_by_family[family]["source_report"] for row in family_rows)
        keys = {(row["hunt_code"], row["residency"], row["points"], row["draw_system_type"]) for row in family_rows}
        assert len(keys) == len(family_rows)

    assert all(row["runtime_promotion_status"] == "" for row in data if row["draw_system_type"] == "BLACK_BEAR")
    assert all(row["runtime_promotion_status"] == "" for row in data if row["algorithm_status"] == "MODELED_BONUS" and row["draw_system_type"] not in {"BONUS_TURKEY", "YOUTH_TURKEY_SET_ASIDE"})

    assert report["promotion_ready"] is True
    assert report["promoted_row_count"] == sum(expected_counts.values())
    assert report["permit_source_field_contract"].startswith("NOT_REQUIRED_FOR_RUNTIME_PROMOTION")


def test_output_display_odds_use_combined_format() -> None:
    modeled = [row for row in rows() if row["p_draw_mean"] and float(row["p_draw_mean"]) > 0]
    assert modeled
    assert all(row["display_odds_text"].startswith("~1 in ") and " or " in row["display_odds_text"] for row in modeled[:100])


def test_total_only_preference_permits_do_not_render_as_residency_lane_quota() -> None:
    db1502 = [row for row in rows() if row["hunt_code"] == "DB1502"]
    assert db1502
    assert {row["permits_2026_total"] for row in db1502} == {"1160"}
    assert all(row["permits_2026_res"] == "" for row in db1502)
    assert all(row["permits_2026_nr"] == "" for row in db1502)
    assert all(row["public_permits_2026"] == "" for row in db1502)
    assert all("NO_RESIDENCY_LANE_QUOTA" in row["reason_codes"] for row in db1502)
    assert all("TOTAL_ONLY_QUOTA_RATIO_SKIPPED_NO_RESIDENCY_SPLIT" in row["reason_codes"] for row in db1502)


def test_no_published_private_land_rows_are_reference_only_in_ladder() -> None:
    with (ROOT / "processed_data" / "point_ladder_view.csv").open(newline="", encoding="utf-8-sig") as handle:
        ladder = list(csv.DictReader(handle))
    el3002 = [row for row in ladder if row["hunt_code"] == "EL3002"]
    assert el3002
    assert all(row["permits_2026_res"] == "" for row in el3002)
    assert all(row["permits_2026_nr"] == "" for row in el3002)
    assert all(row["permits_2026_total"] == "" for row in el3002)
    assert all(row["public_permits_2026"] == "" for row in el3002)
    assert all(row["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW" for row in el3002)
    assert all(row["p_draw_mean"] == "" for row in el3002)
    assert all(row["display_odds_text"] == "Not available" for row in el3002)
    assert all("NO_PUBLISHED_PERMIT_AUTHORITY" in row["reason_codes"] for row in el3002)
    assert all("NO_PUBLISHED_QUOTA_RATIO_SKIPPED" in row["reason_codes"] for row in el3002)
