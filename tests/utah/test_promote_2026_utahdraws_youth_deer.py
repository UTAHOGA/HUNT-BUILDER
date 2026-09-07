from __future__ import annotations

import csv
import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "promote_2026_utahdraws_youth_deer_to_canonical.py"
CANONICAL = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)


def load_module():
    spec = importlib.util.spec_from_file_location("promote_2026_youth_deer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_retained_sources_build_exact_general_and_dedicated_deer_promotion() -> None:
    module = load_module()
    result = module.build_promotion()
    rows = result["promoted_rows"]

    assert len(rows) == 2_001
    assert len({row["hunt_code"] for row in rows}) == 137
    assert Counter(row["source_scope"] for row in rows) == {
        "GENERAL_SEASON_DEER": 1_333,
        "YOUTH_GENERAL_SEASON_DEER": 389,
        "DEDICATED_HUNTER": 225,
        "YOUTH_DEDICATED_HUNTER_DEER": 54,
    }
    assert Counter(row["residency"] for row in rows) == {
        "Resident": 1_188,
        "Nonresident": 813,
    }
    assert Counter(row["source_is_youth"] for row in rows) == {
        "false": 1_558,
        "true": 443,
    }
    assert all(row["actual_draw_year"] == "2026" for row in rows)
    assert all(row["model_target_year"] == "2027" for row in rows)
    assert all(row["source_dataset"] == module.SOURCE_DATASET for row in rows)
    assert all(row["source_row_identifier"].startswith("utahdraws:") for row in rows)


def test_youth_rows_use_separate_official_draw_lanes() -> None:
    module = load_module()
    rows = module.build_promotion()["promoted_rows"]
    expected = {
        "GENERAL_SEASON_DEER": (
            "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "adult_general_deer",
        ),
        "YOUTH_GENERAL_SEASON_DEER": (
            "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "youth_general_deer",
        ),
        "DEDICATED_HUNTER": (
            "PREFERENCE_DEDICATED_HUNTER_DEER",
            "dedicated_hunter",
        ),
        "YOUTH_DEDICATED_HUNTER_DEER": (
            "PREFERENCE_DEDICATED_HUNTER_DEER",
            "youth_dedicated_hunter",
        ),
    }
    for row in rows:
        assert (row["draw_design"], row["draw_pool"]) == expected[row["source_scope"]]


def test_youth_probabilities_are_exactly_count_backed() -> None:
    module = load_module()
    rows = module.build_promotion()["promoted_rows"]
    for row in rows:
        applicants = int(row["eligible_applicants"])
        successful = int(row["successful_applicants"])
        if applicants > 0 and successful > 0:
            assert abs(float(row["p_draw"]) - successful / applicants) < 1e-9
            assert abs(float(row["p_draw_percent"]) - 100 * successful / applicants) < 1e-6
            assert row["success_ratio"] == row["p_draw"]
        else:
            assert row["p_draw"] == ""
            assert row["p_draw_percent"] == ""
            assert row["success_ratio"] == ""


def test_written_canonical_contains_youth_rows_and_preserves_references() -> None:
    rows = read_rows(CANONICAL)
    promoted = [
        row
        for row in rows
        if row["parse_method"] == "2026_UTAHDRAWS_GENERAL_AND_DEDICATED_DEER_TO_CANONICAL"
    ]
    references = [row for row in rows if row["record_type"] == "hunt_planner_permit_reference"]

    assert len(promoted) == 2_001
    assert all(row["parse_method"] != "2026_UTAHDRAWS_YOUTH_DEER_TO_CANONICAL" for row in rows)
    assert all(
        row["parse_method"] != "2026_PDF_SUCCESS_FIELD_REPAIRED_FROM_RETAINED_UTAHDRAWS"
        for row in rows
    )
    assert len(references) == 262
    assert all(row["hunt_code"] != "EA1281" for row in rows)
    assert all("2025" not in row.get("season", "") for row in promoted)
