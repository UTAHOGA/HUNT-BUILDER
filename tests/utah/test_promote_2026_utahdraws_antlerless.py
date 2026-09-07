from __future__ import annotations

import csv
import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "promote_2026_utahdraws_antlerless_to_canonical.py"
CANONICAL = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)


def load_module():
    spec = importlib.util.spec_from_file_location("promote_2026_antlerless", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_retained_antlerless_source_builds_complete_validated_promotion() -> None:
    module = load_module()
    result = module.build_promotion()
    rows = result["promoted_rows"]

    assert len(rows) == 2_144
    assert len({row["hunt_code"] for row in rows}) == 153
    assert sum(int(row["eligible_applicants"]) > 0 for row in rows) == 1_911
    assert sum(int(row["eligible_applicants"]) == 0 for row in rows) == 233
    assert len({module.canonical_source_key(row) for row in rows}) == len(rows)
    assert all(int(row["successful_applicants"]) <= int(row["eligible_applicants"]) for row in rows)

    assert Counter(row["draw_source_file"] for row in rows) == {
        "2026_antlerless_17_antlerless_deer.json": 244,
        "2026_antlerless_18_antlerless_elk.json": 1_493,
        "2026_antlerless_19_antlerless_moose.json": 80,
        "2026_antlerless_20_doe_pronghorn.json": 313,
        "2026_antlerless_21_ewe_rocky_mtn_bighorn_sheep.json": 14,
    }


def test_promotion_preserves_adult_youth_and_draw_system_identity() -> None:
    module = load_module()
    rows = module.build_promotion()["promoted_rows"]

    expected = {
        "ANTLERLESS_DEER": ("PREFERENCE_ANTLERLESS_DEER", "general_season_antlerless_deer"),
        "YOUTH_ANTLERLESS_DEER": ("PREFERENCE_ANTLERLESS_DEER", "youth_antlerless_deer"),
        "ANTLERLESS_ELK": ("PREFERENCE_ANTLERLESS_ELK", "general_season_antlerless_elk"),
        "YOUTH_ANTLERLESS_ELK": ("PREFERENCE_ANTLERLESS_ELK", "youth_antlerless_elk"),
        "ANTLERLESS_PRONGHORN": ("PREFERENCE_DOE_PRONGHORN", "general_season_doe_pronghorn"),
        "YOUTH_ANTLERLESS_PRONGHORN": ("PREFERENCE_DOE_PRONGHORN", "youth_doe_pronghorn"),
        "ANTLERLESS_MOOSE": ("MAX_WEIGHTED_SPLIT", "max_weighted_split"),
        "ANTLERLESS_ROCKY_MOUNTAIN_BIGHORN_SHEEP": ("MAX_WEIGHTED_SPLIT", "max_weighted_split"),
    }
    assert set(row["source_scope"] for row in rows) == set(expected)
    for row in rows:
        assert (row["draw_design"], row["draw_pool"]) == expected[row["source_scope"]]
        assert row["source_is_youth"] in {"true", "false"}
        assert row["source_row_identifier"].startswith("utahdraws:")

    ewe_rows = [row for row in rows if row["hunt_code"] == "RE1000"]
    assert ewe_rows
    assert all(row["draw_design"] == "MAX_WEIGHTED_SPLIT" for row in ewe_rows)


def test_probability_is_exactly_count_backed_and_never_filled_for_empty_outcomes() -> None:
    module = load_module()
    rows = module.build_promotion()["promoted_rows"]

    for row in rows:
        applicants = int(row["eligible_applicants"])
        successful = int(row["successful_applicants"])
        if applicants > 0 and successful > 0:
            assert abs(float(row["p_draw"]) - successful / applicants) < 1e-9
            assert abs(float(row["p_draw_percent"]) - (100 * successful / applicants)) < 1e-6
            assert row["success_ratio"] == row["p_draw"]
        else:
            assert row["p_draw"] == ""
            assert row["p_draw_percent"] == ""
            assert row["success_ratio"] == ""


def test_2025_style_output_joins_residencies_and_adds_dwr_totals_rows() -> None:
    module = load_module()
    promoted = module.build_promotion()["promoted_rows"]
    rows = module.build_2025_style_wide_rows(promoted)

    assert Counter(row["row_type"] for row in rows) == {"POINT": 1_503, "TOTALS": 291}
    assert len(rows) == 1_794

    da1001_adult = [
        row for row in rows
        if row["hunt_code"] == "DA1001" and row["is_youth"] == "false"
    ]
    assert da1001_adult[-1]["row_type"] == "TOTALS"
    assert da1001_adult[-1]["resident_eligible_applicants"] == "80"
    assert da1001_adult[-1]["nonresident_eligible_applicants"] == "1"
    assert da1001_adult[-1]["total_eligible_applicants"] == "81"
    assert da1001_adult[-1]["total_successful_applicants"] == "24"
    assert da1001_adult[-1]["total_success_ratio"] == "1 in 3.4"
    assert [int(row["points"]) for row in da1001_adult[:-1]] == sorted(
        (int(row["points"]) for row in da1001_adult[:-1]), reverse=True
    )


def test_every_public_draw_reference_is_source_backed_or_explicitly_reconciled() -> None:
    module = load_module()
    result = module.build_promotion()
    details = result["unmatched_reference_details"]

    assert result["public_draw_reference_codes"] == 162
    assert result["source_backed_hunt_codes"] == 153
    assert {row["hunt_code"] for row in details} == module.EXPECTED_UNMATCHED_REFERENCE_CODES
    positive_permit_rows = [row for row in details if row["permits_2026_total"] > 0]
    assert positive_permit_rows == []
    assert result["reference_group_counts"] == {
        "CWMU_REFERENCE": 73,
        "PRIVATE_LANDS_ONLY_REFERENCE": 27,
        "PUBLIC_DRAW_REFERENCE": 162,
    }


def test_written_canonical_contains_promoted_rows_and_keeps_all_references() -> None:
    rows = read_rows(CANONICAL)
    promoted = [row for row in rows if row["parse_method"] == "2026_UTAHDRAWS_ANTLERLESS_TO_CANONICAL"]
    references = [row for row in rows if row["record_type"] == "hunt_planner_permit_reference"]

    assert len(promoted) == 2_144
    assert len({row["hunt_code"] for row in promoted}) == 153
    assert len(references) == 262
    assert all(row["hunt_code"] != "EA1281" for row in references)


def test_ea1281_is_preserved_only_in_historical_2025_truth() -> None:
    current_rows = read_rows(CANONICAL)
    historical = (
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
        / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
    )
    historical_rows = read_rows(historical)

    assert all(row["hunt_code"] != "EA1281" for row in current_rows)
    assert sum(row["hunt_code"] == "EA1281" for row in historical_rows) == 36
