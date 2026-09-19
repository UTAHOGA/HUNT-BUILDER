from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "processed_data" / "ml_draw_predictions_v1.csv"
SUMMARY = ROOT / "processed_data" / "mixed_predictive_engine_2026_summary.json"
SPORTSMAN = ROOT / "processed_data" / "sportsman_permit_predictions_v1.csv"


def rows() -> list[dict[str, str]]:
    with ML.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sportsman_rows() -> list[dict[str, str]]:
    with SPORTSMAN.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_public_materialization_has_certified_contract_and_no_duplicate_keys() -> None:
    data = rows()
    required = {
        "prediction_certification_design",
        "prediction_certification_status",
        "prediction_publication_status",
        "prediction_certification_registry_id",
        "certified_p_draw",
    }
    assert required.issubset(data[0])

    # Raw and presentation-ready probability fields belong to isolated candidate
    # evidence, not to the certified-only public materialization.
    forbidden = {
        "p_draw",
        "p_draw_mean",
        "p_draw_low",
        "p_draw_high",
        "display_odds_text",
        "p_sportsman_draw",
    }
    assert forbidden.isdisjoint(data[0])

    keys = [(r["hunt_code"], r["residency"], r["points"], r["draw_pool"]) for r in data]
    assert len(keys) == len(set(keys))
    assert json.loads(SUMMARY.read_text(encoding="utf-8"))["duplicate_key_count"] == 0


def test_summary_reports_release_guardrails() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["probability_field_guardrail_result"] == "PASS"
    assert summary["quota_guardrail_result"] == "PASS"
    assert summary["special_permit_guardrail_result"] == "PASS"
    assert summary["harvest_audit_blocker_count"] == 0


def test_only_certified_rows_publish_certified_probability() -> None:
    data = rows()
    published = [row for row in data if row["certified_p_draw"]]
    assert published
    assert all(row["prediction_certification_status"] == "CERTIFIED" for row in published)
    assert all(row["prediction_publication_status"] == "CERTIFIED_PROBABILITY" for row in published)
    assert all(0 <= float(row["certified_p_draw"]) <= 1 for row in published)

    withheld = [row for row in data if row["prediction_certification_status"] != "CERTIFIED"]
    assert withheld
    assert all(row["certified_p_draw"] == "" for row in withheld)
    assert all(row["prediction_publication_status"].endswith("PROBABILITY_WITHHELD") for row in withheld)


def test_only_the_four_certified_core_designs_are_publishable() -> None:
    data = rows()
    expected = {
        "BONUS_LE_BIG_GAME",
        "BONUS_OIL_BIG_GAME",
        "BONUS_PLE_BIG_GAME",
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    }
    published_designs = {
        row["prediction_certification_design"]
        for row in data
        if row["certified_p_draw"]
    }
    assert published_designs == expected

    noncertified_families = {
        "PREFERENCE_DEDICATED_HUNTER_DEER",
        "SPORTSMAN_RANDOM_ONLY",
        "YOUTH_GENERAL_ANY_BULL_ELK",
    }
    for row in data:
        if row["prediction_certification_design"] in noncertified_families:
            assert row["certified_p_draw"] == ""


def test_sportsman_rows_remain_separate_and_unpublished() -> None:
    merged_sportsman = [row for row in rows() if row["algorithm_status"] == "MODELED_SPORTSMAN_DRAW"]
    assert merged_sportsman
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in merged_sportsman)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in merged_sportsman)
    assert all(row["residency"] == "Resident" for row in merged_sportsman)
    assert all(row["certified_p_draw"] == "" for row in merged_sportsman)

    sportsman = [row for row in sportsman_rows() if row["algorithm_status"] == "MODELED_SPORTSMAN_DRAW"]
    assert sportsman
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in sportsman)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in sportsman)


def test_db1502_uses_published_residency_split_and_certified_probability() -> None:
    db1502 = [row for row in rows() if row["hunt_code"] == "DB1502"]
    assert db1502
    assert {row["permits_2026_total"] for row in db1502} == {"1160"}
    assert {row["permits_2026_res"] for row in db1502} == {"876"}
    assert {row["permits_2026_nr"] for row in db1502} == {"42"}
    assert {row["public_permits_2026"] for row in db1502} == {"1160"}
    assert all("OFFICIAL_EXPLICIT_RESIDENCY_SPLIT" in row["reason_codes"] for row in db1502)
    assert all(row["prediction_certification_status"] == "CERTIFIED" for row in db1502)
    assert all(row["certified_p_draw"] for row in db1502)


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
    assert all(row["certified_p_draw"] == "" for row in el3002)
    assert all(row["p_draw_mean"] == "" for row in el3002)
    assert all(row["display_odds_text"] == "" for row in el3002)
    official_rows = [row for row in el3002 if "LADDER_MAX_POINT_EXTENSION" not in row["reason_codes"]]
    assert official_rows
    assert all("NO_PUBLISHED_PERMIT_AUTHORITY" in row["reason_codes"] for row in official_rows)
    assert all("NO_PUBLISHED_QUOTA_RATIO_SKIPPED" in row["reason_codes"] for row in official_rows)
