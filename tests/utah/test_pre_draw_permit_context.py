from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from scripts.build_pre_draw_permit_context import (
    DEFAULT_OUTPUT,
    _reconcile_split,
    read_manifest,
)
from scripts.evaluate_antlerless_preference_development import (
    apply_pre_draw_quota_context,
    read_pre_draw_quota_context,
)


ROOT = Path(__file__).resolve().parents[2]


def rows() -> list[dict[str, str]]:
    with DEFAULT_OUTPUT.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_source_receipt_is_hash_and_page_verified() -> None:
    receipts = read_manifest()
    assert receipts
    for receipt in receipts:
        assert hashlib.sha256(receipt.path.read_bytes()).hexdigest() == receipt.sha256
        assert receipt.pages > 0


def test_context_contains_only_recommendation_crosschecks() -> None:
    data = rows()
    assert data
    assert {row["permit_year"] for row in data} == {"2024", "2025", "2026"}
    assert {row["source_timing"] for row in data} == {
        "PRE_DRAW_RECOMMENDATION_CROSSCHECK_ONLY"
    }
    assert all(row["source_path"] and row["source_page"] and row["source_sha256"] for row in data)
    assert all(row["eligible_for_probability_quota"] == "false" for row in data)
    assert not any("private" in row["family"].lower() for row in data)
    assert not any(row["hunt_code"].startswith(("MA", "RE")) for row in data)


def test_every_residency_split_reconciles_to_total() -> None:
    for row in rows():
        if row["permit_scope"] != "RESIDENCY_SPLIT":
            continue
        assert int(row["resident_permits"]) + int(row["nonresident_permits"]) == int(
            row["total_permits"]
        )


def test_known_source_rows_are_in_the_correct_cells() -> None:
    indexed = {(row["permit_year"], row["hunt_code"]): row for row in rows() if row["hunt_code"]}
    assert indexed[("2024", "EA1203")]["resident_permits"] == "4"
    assert indexed[("2024", "EA1203")]["nonresident_permits"] == "1"
    assert indexed[("2024", "EA1203")]["total_permits"] == "5"
    assert indexed[("2024", "EA1089")]["total_permits"] == "50"
    assert indexed[("2024", "DA1049")]["total_permits"] == "75"
    assert indexed[("2025", "PD1056")]["resident_permits"] == "36"
    assert indexed[("2025", "PD1056")]["nonresident_permits"] == "4"
    assert indexed[("2025", "PD1056")]["total_permits"] == "40"


def test_same_year_source_wins_when_retrospective_column_changed() -> None:
    row = next(
        row
        for row in rows()
        if row["permit_year"] == "2025"
        and row["unit_name_normalized"] == "beaver west"
        and row["family"] == "general_season_buck_deer_unit_quota"
    )
    assert row["total_permits"] == "900"
    assert row["crosscheck_status"] == (
        "OFFICIAL_RETROSPECTIVE_DIFFERENCE_RETAIN_SAME_YEAR_PRE_DRAW"
    )
    assert "2025-04-buck-deer-hunt-tables.pdf" in row["source_path"]


def test_ocr_separator_and_single_cell_damage_are_resolved_only_by_row_invariant() -> None:
    assert _reconcile_split([14, 1, 5], "EA1203")[:3] == (4, 1, 5)
    assert _reconcile_split([6, 10, 100], "EA1094")[:3] == (90, 10, 100)


def test_development_adapter_rejects_rac_recommendations() -> None:
    with pytest.raises(ValueError, match="RAC recommendations are cross-check-only"):
        read_pre_draw_quota_context(DEFAULT_OUTPUT)


def test_development_adapter_accepts_only_final_published_quota(tmp_path: Path) -> None:
    final_path = tmp_path / "final_published_quota.csv"
    with final_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "permit_year",
                "family",
                "hunt_code",
                "total_permits",
                "resident_permits",
                "nonresident_permits",
                "source_path",
                "source_page",
                "source_sha256",
                "source_timing",
                "eligible_for_probability_quota",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "permit_year": "2025",
                "family": "antlerless_elk",
                "hunt_code": "EA1089",
                "total_permits": "50",
                "resident_permits": "45",
                "nonresident_permits": "5",
                "source_path": "official/final.pdf",
                "source_page": "1",
                "source_sha256": "a" * 64,
                "source_timing": "FINAL_PUBLISHED_PRE_DRAW_QUOTA",
                "eligible_for_probability_quota": "true",
            }
        )
    context = read_pre_draw_quota_context(final_path)
    source = [
        {
            "draw_system_type": "PREFERENCE_ANTLERLESS_ELK",
            "hunt_code": "EA1089",
            "target_permits_total": "999",
            "target_permits_res": "999",
            "target_permits_nr": "0",
        }
    ]
    enriched, matched = apply_pre_draw_quota_context(
        source, target_year=2025, context=context
    )
    assert matched == 1
    assert enriched[0]["target_permits_total"] == "50"
    assert enriched[0]["target_permits_res"] == "45"
    assert enriched[0]["target_permits_nr"] == "5"
    assert enriched[0]["target_permits_source"] == (
        "OFFICIAL_FINAL_PUBLISHED_PRE_DRAW_QUOTA"
    )
    assert "draw result" not in enriched[0]["target_permits_source"].lower()
