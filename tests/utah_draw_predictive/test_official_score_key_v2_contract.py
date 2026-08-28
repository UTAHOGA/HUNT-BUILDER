from __future__ import annotations

import csv
import json
from argparse import Namespace
from pathlib import Path

import pytest

from engine.utah_draw_predictive.run_all_families import _dedupe_final_family_prediction_rows
from engine.utah_draw_predictive.run_all_families import _effective_draw_pool_for_family
from engine.utah_draw_predictive.run_all_families import _family_for_legacy_row
from engine.utah_draw_predictive.run_all_families import _with_run_fields
from engine.utah_draw_predictive.run_all_families import _finalize_prediction_output_row
from engine.utah_draw_predictive.run_all_families import _source_backed_family_for_row
from engine.utah_draw_predictive.run_all_families import _source_backed_probability_rows
from engine.utah_draw_predictive.run_all_families import _source_family_for_output_row
from scripts.build_score_key_v2_truth_comparable_from_prediction_surface import comparable_source_family
from scripts.build_score_key_v2_truth_comparable_from_prediction_surface import build as build_score_key_v2_truth_comparable
from scripts.build_score_key_v2_truth_comparable_from_prediction_surface import truth_summary_reason
from tools.prediction_accuracy_backtest.score_full_engine_draw_line_aware import (
    OfficialScoreKeyV2ValidationError,
    _validate_official_score_key_v2_rows,
    main as scorer_main,
)


REQUIRED_COLUMNS = {
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "official_score_key_v2",
}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_summary(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("residency", "expected_scope", "expected_residency"),
    [
        ("", "TOTAL", ""),
        ("Resident", "RESIDENT", "Resident"),
        ("Nonresident", "NONRESIDENT", "Nonresident"),
        ("Non-Resident", "NONRESIDENT", "Nonresident"),
    ],
)
def test_family_predictions_emit_score_key_v2_columns_and_exact_key(residency: str, expected_scope: str, expected_residency: str) -> None:
    row = {
        "hunt_code": "DB0007",
        "hunt_name": "Sportsman Deer",
        "species": "Deer",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "residency": residency,
        "points": "0",
        "p_draw": "0.500000",
    }

    output = _with_run_fields([row], 2018, 2019, "sportsman")[0]

    assert REQUIRED_COLUMNS.issubset(output.keys())
    assert output["score_scope"] == expected_scope
    assert output["residency"] == expected_residency
    assert output["source_family"] == "SPORTSMAN"
    assert output["probability_metric"] == "p_draw"
    assert output["official_score_key_v2"] == "|".join(
        [
            "2019",
            "SPORTSMAN",
            "SPORTSMAN_RANDOM_ONLY",
            "random",
            "DB0007",
            expected_scope,
            expected_residency,
            "0",
            "p_draw",
        ]
    )


def test_bonus_prediction_numeric_zero_point_survives_final_output_normalization() -> None:
    row = {
        "hunt_code": "DB1009",
        "hunt_name": "Limited Entry Deer",
        "species": "Deer",
        "hunt_type": "Limited Entry",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "draw_pool": "limited_entry_deer",
        "residency": "Resident",
        "points": 0,
        "p_draw_mean": "0.000788",
    }

    normalized = _with_run_fields([row], 2017, 2018, "bonus_le_big_game")[0]
    output = _finalize_prediction_output_row(normalized)

    assert output["points"] == "0"
    assert output["p_draw_mean"] == "0.000788"
    assert output["official_score_key_v2"].endswith("|Resident|0|p_draw")


@pytest.mark.parametrize(
    ("row", "family", "expected_source_family", "expected_key"),
    [
        (
            {
                "hunt_code": "DA1000",
                "hunt_name": "Adult antlerless deer",
                "species": "Deer",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "standard",
                "residency": "",
                "points": "0",
                "p_draw": "0.250000",
            },
            "preference_antlerless_deer",
            "ADULT_ANTLERLESS",
            "2018|ADULT_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|general_season_antlerless_deer|DA1000|TOTAL||0|p_draw",
        ),
        (
            {
                "hunt_code": "DA2000",
                "hunt_name": "Youth antlerless deer",
                "species": "Deer",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "youth_antlerless",
                "residency": "Resident",
                "points": "1",
                "p_draw": "0.125000",
            },
            "preference_antlerless_deer",
            "YOUTH_ANTLERLESS",
            "2018|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|youth_antlerless|DA2000|RESIDENT|Resident|1|p_draw",
        ),
    ],
)
def test_antlerless_rows_emit_family_specific_source_family_and_exact_key(
    row: dict[str, object],
    family: str,
    expected_source_family: str,
    expected_key: str,
) -> None:
    output = _with_run_fields([row], 2017, 2018, family)[0]

    assert output["source_family"] == expected_source_family
    assert output["official_score_key_v2"] == expected_key


def test_preference_general_deer_rows_stay_in_the_adult_lane() -> None:
    row = {
        "hunt_code": "DB1500",
        "hunt_name": "General season deer",
        "species": "Deer",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "standard",
        "residency": "Nonresident",
        "points": "20",
        "p_draw": "0.995000",
        "source_file": "18_general_deer.pdf",
    }

    output = _with_run_fields([row], 2018, 2019, "preference_general_deer")[0]

    assert output["source_family"] == "GENERAL_SEASON_DEER"
    assert output["draw_pool"] == "adult_general_deer"
    assert output["official_score_key_v2"] == "2019|GENERAL_SEASON_DEER|PREFERENCE_GENERAL_SEASON_BUCK_DEER|adult_general_deer|DB1500|NONRESIDENT|Nonresident|20|p_draw"


def test_youth_draw_rows_keep_the_youth_general_deer_lane() -> None:
    row = {
        "hunt_code": "DB1500",
        "hunt_name": "Youth general season deer",
        "species": "Deer",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "youth_general_deer",
        "residency": "Nonresident",
        "points": "20",
        "p_draw": "0.995000",
        "source_file": "18_youth_general_deer.pdf",
    }

    output = _with_run_fields([row], 2018, 2019, "youth_draw")[0]

    assert output["source_family"] == "YOUTH_GENERAL_SEASON_DEER"
    assert output["draw_pool"] == "youth_general_deer"
    assert output["official_score_key_v2"] == "2019|YOUTH_GENERAL_SEASON_DEER|PREFERENCE_GENERAL_SEASON_BUCK_DEER|youth_general_deer|DB1500|NONRESIDENT|Nonresident|20|p_draw"


def test_general_deer_routing_uses_lifetime_and_youth_source_files_to_split_lanes() -> None:
    lifetime_row = {
        "hunt_code": "DB1500",
        "hunt_name": "Lifetime general season deer",
        "species": "Deer",
        "sex_type": "Buck",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "lifetime_general_deer",
        "residency": "Resident",
        "points": "0",
        "p_draw": "0.250000",
        "source_file": "17_lifetime_general_deer.pdf",
    }
    youth_row = {
        "hunt_code": "DB1501",
        "hunt_name": "Youth general season deer",
        "species": "Deer",
        "sex_type": "Buck",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "youth_general_deer",
        "residency": "Resident",
        "points": "0",
        "p_draw": "0.500000",
        "source_file": "17_youth_general_deer.pdf",
    }

    assert _family_for_legacy_row(lifetime_row) == "preference_general_deer"
    assert _family_for_legacy_row(youth_row) == "youth_draw"
    assert _source_family_for_output_row("preference_general_deer", lifetime_row) == "LIFETIME_GENERAL_SEASON_DEER"
    assert _effective_draw_pool_for_family(lifetime_row, "preference_general_deer") == "lifetime_general_deer"
    assert _source_family_for_output_row("youth_draw", youth_row) == "YOUTH_GENERAL_SEASON_DEER"
    assert _effective_draw_pool_for_family(youth_row, "youth_draw") == "youth_general_deer"


def test_source_backed_family_uses_source_pdf_titles_for_lane_detection() -> None:
    lifetime_row = {
        "hunt_code": "DB1500",
        "hunt_name": "Lifetime general season deer",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "Lifetime",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "lifetime_general_deer",
        "source_file": "17_lifetime_general_deer.pdf",
    }
    youth_row = {
        "hunt_code": "DB1501",
        "hunt_name": "Youth general season deer",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season - Youth",
        "hunt_class": "Youth",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_pool": "youth_general_deer",
        "source_file": "17_youth_general_deer.pdf",
    }

    assert _source_backed_family_for_row(lifetime_row) == ""
    assert _source_backed_family_for_row(youth_row) == "youth_draw"


def test_source_backed_rows_do_not_promote_guaranteed_lifetime_deer_as_draw_rows() -> None:
    modeled = {
        "preference_general_deer": [
            {
                "hunt_code": "DB1500",
                "draw_pool": "adult_general_deer",
                "residency": "Resident",
                "points": "0",
            }
        ]
    }
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DB1500",
            "hunt_name": "Lifetime general season deer",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Lifetime",
            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "draw_pool": "lifetime_general_deer",
            "residency": "Resident",
            "points": "0",
            "p_draw": "0.250000",
            "source_file": "17_lifetime_general_deer.pdf",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, modeled, 2017, 2018)

    assert rows == {}


def test_source_backed_rows_do_not_promote_permit_total_summary_rows() -> None:
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DA1000",
            "hunt_name": "Antlerless deer",
            "species": "Deer",
            "sex_type": "Female",
            "hunt_type": "Limited Entry",
            "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
            "draw_pool": "preference_antlerless_deer",
            "residency": "",
            "points": "TOTAL",
            "p_draw": "0.125000",
            "source_file": "17_antlerless_points.pdf",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, {}, 2017, 2018)

    assert rows == {}


def test_pdf_bottom_total_row_is_summary_metadata_not_ladder() -> None:
    row = {
        "hunt_code": "DA1000",
        "points": "TOTAL",
        "year_permits_total": "40",
        "total_eligible_applicants": "369",
    }

    assert truth_summary_reason(row) == "PDF_BOTTOM_CUMULATIVE_TOTAL_ROW_NOT_LADDER"


def test_sportsman_total_row_is_random_draw_row_not_summary_metadata() -> None:
    row = {
        "hunt_code": "DB0007",
        "hunt_name": "Sportsman Deer",
        "hunt_type": "Sportsman",
        "record_type": "sportsman_total",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "sportsman_random_only",
        "points": "TOTAL",
        "p_draw": "0.0000907606",
    }

    assert truth_summary_reason(row) == ""


def test_sportsman_black_bear_stays_sportsman_not_bear_family() -> None:
    row = {
        "hunt_code": "BR1000",
        "hunt_name": "Sportsman Black Bear",
        "hunt_type": "Sportsman",
        "record_type": "sportsman_total",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "sportsman_random_only",
        "points": "",
    }

    assert comparable_source_family(row) == "SPORTSMAN"


def test_bear_river_antlerless_unit_does_not_become_bear_family() -> None:
    row = {
        "hunt_code": "DA1001",
        "hunt_name": "Box Elder, West Bear River",
        "species": "Deer",
        "sex_type": "Female",
        "hunt_type": "Limited Entry",
        "source_file": "17_antlerless_youth_points.pdf",
        "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
        "draw_pool": "preference_antlerless_deer",
        "points": "0",
    }

    assert comparable_source_family(row) == "YOUTH_ANTLERLESS"


def test_cwmu_draw_system_keeps_cwmu_family() -> None:
    row = {
        "source_family": "YOUTH_ANTLERLESS",
        "hunt_code": "DA1011",
        "hunt_name": "George Creek",
        "species": "Deer",
        "sex_type": "Female",
        "hunt_type": "Limited Entry",
        "source_file": "17_antlerless_youth_points.pdf",
        "draw_system_type": "BONUS_CWMU_BIG_GAME",
        "draw_pool": "bonus_cwmu_big_game",
        "points": "0",
    }

    assert comparable_source_family(row) == "CWMU_BIG_GAME"


def test_truth_comparable_uses_split_source_filename_to_avoid_2019_duplicate_keys(tmp_path: Path) -> None:
    truth_file = tmp_path / "truth.csv"
    prediction_file = tmp_path / "predictions.csv"
    output_dir = tmp_path / "truth_out"

    _write_csv(
        prediction_file,
        [
            {
                "target_year": "2020",
                "source_family": "ADULT_ANTLERLESS",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "general_season_antlerless_deer",
                "hunt_code": "DA1009",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2020|ADULT_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|general_season_antlerless_deer|DA1009|TOTAL||0|p_draw",
                "p_draw": "0.000000",
            },
            {
                "target_year": "2020",
                "source_family": "YOUTH_ANTLERLESS",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "youth_antlerless_deer",
                "hunt_code": "DA1009",
                "score_scope": "RESIDENT",
                "residency": "Resident",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2020|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|youth_antlerless_deer|DA1009|RESIDENT|Resident|0|p_draw",
                "p_draw": "0.000000",
            },
            {
                "target_year": "2020",
                "source_family": "YOUTH_ANTLERLESS",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "youth_antlerless_deer",
                "hunt_code": "DA1009",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2020|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|youth_antlerless_deer|DA1009|TOTAL||0|p_draw",
                "p_draw": "0.000000",
            },
            {
                "target_year": "2020",
                "source_family": "TURKEY",
                "draw_system_type": "BONUS_TURKEY",
                "draw_pool": "preference_point",
                "hunt_code": "TK1003",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2020|TURKEY|BONUS_TURKEY|preference_point|TK1003|TOTAL||0|p_draw",
                "p_draw": "0.000000",
            },
            {
                "target_year": "2020",
                "source_family": "TURKEY",
                "draw_system_type": "YOUTH_TURKEY_SET_ASIDE",
                "draw_pool": "youth_turkey",
                "hunt_code": "TK1003",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2020|TURKEY|YOUTH_TURKEY_SET_ASIDE|youth_turkey|TK1003|TOTAL||0|p_draw",
                "p_draw": "0.000000",
            },
        ],
    )
    _write_csv(
        truth_file,
        [
            {
                "model_target_year": "2020",
                "hunt_code": "DA1009",
                "points": "0",
                "residency": "",
                "source_file": "2019_PERMITS=2020_MODEL__ANTLERLESS_DEER_DRAW_RESULTS.pdf",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "youth_antlerless_deer",
                "qa_notes": "rebuilt_bucket=ANTLERLESS_DEER; source_group=ANTLERLESS",
                "total_p_draw": "0.125",
                "p_draw": "0.125",
            },
            {
                "model_target_year": "2020",
                "hunt_code": "DA1009",
                "points": "0",
                "residency": "",
                "source_file": "2019_PERMITS=2020_MODEL__YOUTH_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
                "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
                "draw_pool": "youth_antlerless_deer",
                "qa_notes": "rebuilt_bucket=YOUTH_ANTLERLESS_DEER; source_group=REMAINDER",
                "resident_p_draw": "0.3333333333",
                "total_p_draw": "0.375",
                "p_draw": "0.375",
            },
            {
                "model_target_year": "2020",
                "hunt_code": "TK1003",
                "points": "0",
                "residency": "",
                "source_file": "2019_PERMITS=2020_MODEL__TURKEY_DRAW_RESULTS.pdf",
                "draw_system_type": "BONUS_TURKEY",
                "draw_pool": "preference_point",
                "qa_notes": "rebuilt_bucket=TURKEY; source_group=REMAINDER",
                "p_draw": "0.027",
            },
            {
                "model_target_year": "2020",
                "hunt_code": "TK1003",
                "points": "0",
                "residency": "",
                "source_file": "2019_PERMITS=2020_MODEL__YOUTH_TURKEY_DRAW_RESULTS.pdf",
                "draw_system_type": "YOUTH_TURKEY_SET_ASIDE",
                "draw_pool": "youth_turkey",
                "qa_notes": "rebuilt_bucket=YOUTH_TURKEY; source_group=REMAINDER",
                "p_draw": "0.033",
            },
        ],
    )

    status = build_score_key_v2_truth_comparable(
        Namespace(
            truth=truth_file,
            predictions=prediction_file,
            source_year=2019,
            target_year=2020,
            output_dir=output_dir,
        )
    )

    assert status["score_key_v2_clean"] is True
    assert status["duplicate_score_key_v2_rows"] == 0

    with (output_dir / "truth_scorable_multiscope_long_score_key_v2.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    keys = {row["official_score_key_v2"] for row in rows}
    assert "2020|ADULT_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|general_season_antlerless_deer|DA1009|TOTAL||0|p_draw" in keys
    assert "2020|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|youth_antlerless_deer|DA1009|RESIDENT|Resident|0|p_draw" in keys
    assert "2020|TURKEY|BONUS_TURKEY|preference_point|TK1003|TOTAL||0|p_draw" in keys
    assert "2020|TURKEY|YOUTH_TURKEY_SET_ASIDE|youth_turkey|TK1003|TOTAL||0|p_draw" in keys

    youth_resident = next(
        row for row in rows
        if row["official_score_key_v2"] == "2020|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_DEER|youth_antlerless_deer|DA1009|RESIDENT|Resident|0|p_draw"
    )
    assert youth_resident["p_draw"] == "0.3333333333"


@pytest.mark.parametrize("points", ["", "TOTAL"])
def test_sportsman_prediction_points_normalize_to_blank_not_applicable(points: str) -> None:
    row = {
        "target_year": "2019",
        "family": "sportsman",
        "hunt_code": "DB0007",
        "hunt_name": "Sportsman Deer",
        "species": "Deer",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "sportsman_random_only",
        "residency": "Resident",
        "points": points,
        "p_draw": "0.000091",
    }

    output = _finalize_prediction_output_row(row)

    assert output["points"] == ""
    assert output["score_scope"] == "RESIDENT"
    assert output["official_score_key_v2"] == (
        "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|sportsman_random_only|DB0007|RESIDENT|Resident||p_draw"
    )


def test_source_backed_rows_emit_blank_residency_total_scope_for_numeric_points() -> None:
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DA1000",
            "hunt_name": "Antlerless deer",
            "species": "Deer",
            "sex_type": "Female",
            "hunt_type": "Limited Entry",
            "draw_system_type": "PREFERENCE_ANTLERLESS_DEER",
            "draw_pool": "preference_antlerless_deer",
            "residency": "",
            "points": "2",
            "p_draw": "0.125000",
            "source_file": "17_antlerless_points.pdf",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, {}, 2017, 2018)

    assert len(rows["preference_antlerless_deer"]) == 1
    total_row = rows["preference_antlerless_deer"][0]
    assert total_row["metric_scope"] == "total"
    assert total_row["points"] == "2"
    assert total_row["p_draw"] == "0.125000"


def test_source_backed_rows_use_split_filename_before_rebuilt_bucket_for_2019_alignment() -> None:
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "EA1073",
            "hunt_name": "Antlerless elk",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_type": "General Season",
            "hunt_class": "Youth",
            "draw_system_type": "PREFERENCE_ANTLERLESS_ELK",
            "draw_pool": "youth_antlerless_elk",
            "residency": "",
            "points": "0",
            "p_draw": "0.247312",
            "source_file": "2019_PERMITS=2020_MODEL__YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf",
            "qa_notes": "rebuilt_bucket=ANTLERLESS_ELK; source_group=ANTLERLESS",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, {}, 2019, 2020)
    finalized = _with_run_fields(rows["youth_draw"], 2019, 2020, "youth_draw")

    assert len(finalized) == 1
    row = finalized[0]
    assert row["source_family"] == "YOUTH_ANTLERLESS"
    assert row["draw_pool"] == "youth_antlerless_elk"
    assert row["official_score_key_v2"] == (
        "2020|YOUTH_ANTLERLESS|PREFERENCE_ANTLERLESS_ELK|youth_antlerless_elk|EA1073|TOTAL||0|p_draw"
    )


def test_reference_lifetime_rows_do_not_block_source_backed_youth_general_deer() -> None:
    modeled = {
        "youth_draw": [
            {
                "hunt_code": "DB1505",
                "hunt_name": "Lifetime general season deer",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "Youth",
                "draw_system_type": "REFERENCE_ONLY",
                "draw_pool": "youth_general_deer",
                "residency": "Resident",
                "points": "0",
                "source_file": "20_lifetime_deer(1).pdf",
            }
        ]
    }
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DB1505",
            "hunt_name": "Lifetime general season deer",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "Youth",
            "draw_system_type": "REFERENCE_ONLY",
            "draw_pool": "youth_general_deer",
            "residency": "",
            "points": "0",
            "p_draw": "1",
            "source_file": "20_lifetime_deer(1).pdf",
        },
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DB1505",
            "hunt_name": "Youth general season deer",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "General Season",
            "hunt_class": "YOUTH_GENERAL_SEASON_DEER",
            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            "draw_pool": "youth_general_deer",
            "residency": "",
            "points": "0",
            "p_draw": "1",
            "source_file": "2020_PERMITS=2021_MODEL__YOUTH_G.S._DEER_DRAW_RESULTS.pdf",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, modeled, 2020, 2021)
    finalized = _with_run_fields(rows["youth_draw"], 2020, 2021, "youth_draw")

    assert len(finalized) == 1
    assert finalized[0]["source_family"] == "YOUTH_GENERAL_SEASON_DEER"
    assert finalized[0]["official_score_key_v2"] == (
        "2021|YOUTH_GENERAL_SEASON_DEER|PREFERENCE_GENERAL_SEASON_BUCK_DEER|youth_general_deer|DB1505|TOTAL||0|p_draw"
    )


def test_cwmu_source_backed_rows_keep_cwmu_family_over_species_bucket() -> None:
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "DB1248",
            "hunt_name": "CWMU deer buck",
            "species": "Deer",
            "sex_type": "Buck",
            "hunt_type": "CWMU",
            "hunt_class": "CWMU",
            "draw_system_type": "BONUS_CWMU_BIG_GAME",
            "draw_pool": "max_weighted_split",
            "residency": "",
            "points": "0",
            "p_draw": "0.333333",
            "source_file": "2019_PERMITS=2020_MODEL__CWMU_BIG_GAME_DEER_BUCK.pdf",
            "qa_notes": "rebuilt_bucket=BIG_GAME_LIMITED_ENTRY_DEER; source_group=BIG_GAME",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, {}, 2019, 2020)
    finalized = _with_run_fields(rows["bonus_cwmu_big_game"], 2019, 2020, "bonus_cwmu_big_game")

    assert len(finalized) == 1
    row = finalized[0]
    assert row["source_family"] == "CWMU_BIG_GAME"
    assert row["draw_system_type"] == "BONUS_CWMU_BIG_GAME"
    assert row["draw_pool"] == "cwmu_big_game_deer_buck"
    assert row["official_score_key_v2"] == (
        "2020|CWMU_BIG_GAME|BONUS_CWMU_BIG_GAME|design_bonus_cwmu_big_game__class_cwmu__pool_cwmu_big_game_deer_buck__species_deer__hunt_cwmu__sex_buck|DB1248|TOTAL||0|p_draw"
    )


def test_source_backed_rows_keep_antlerless_moose_in_its_special_bonus_pool() -> None:
    source_rows = [
        {
            "row_type": "point_level_draw_result",
            "hunt_code": "MA1000",
            "hunt_name": "Antlerless Moose - East Canyon",
            "species": "Moose",
            "sex_type": "Female",
            "hunt_type": "Limited Entry",
            "draw_system_type": "BONUS_ANTLERLESS_MOOSE",
            "draw_pool": "bonus_antlerless_moose",
            "residency": "",
            "points": "1",
            "p_draw": "0.125000",
            "source_file": "17_antlerless_points.pdf",
        }
    ]

    rows = _source_backed_probability_rows(source_rows, {}, 2017, 2018)

    assert list(rows) == ["bonus_antlerless_moose"]
    row = rows["bonus_antlerless_moose"][0]
    assert row["family"] == "bonus_antlerless_moose"
    assert row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE"
    assert row["draw_pool"] == "bonus_antlerless_moose"
    assert row["p_draw"] == "0.125000"


def test_final_family_prediction_rows_emit_required_score_key_columns() -> None:
    row = {
        "target_year": "2018",
        "family": "sportsman",
        "hunt_code": "DB0007",
        "hunt_name": "Sportsman Deer",
        "species": "Deer",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "residency": "",
        "points": "0",
        "p_draw": "0.500000",
    }

    output = _finalize_prediction_output_row(row)

    assert REQUIRED_COLUMNS.issubset(output.keys())
    assert output["source_family"] == "SPORTSMAN"
    assert output["score_scope"] == "TOTAL"
    assert output["probability_metric"] == "p_draw"
    assert output["official_score_key_v2"] == "2018|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"


def test_scorer_cli_accepts_required_args_and_scores_synthetic_rows(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    base_row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
    }

    _write_csv(
        prediction_file,
        [
            {
                **base_row,
                "p_draw_mean": "0.400000",
            }
        ],
    )
    _write_csv(
        truth_file,
        [
            {
                **base_row,
                "p_draw": "0.250000",
            }
        ],
    )

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 0

    summary = _read_summary(output_dir / "official_score_key_v2_summary.json")
    assert summary["joined_rows"] == 1
    assert summary["unmatched_prediction_rows"] == 0
    assert summary["unmatched_truth_rows"] == 0
    assert summary["calibration_applied"] is False
    assert summary["mae"] == "0.1500000000"
    assert summary["rmse"] == "0.1500000000"
    assert summary["bias"] == "0.1500000000"


def test_scorer_cli_accepts_p_draw_normalized_truth_probability(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    base_row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
    }

    _write_csv(
        prediction_file,
        [
            {
                **base_row,
                "p_draw": "0.400000",
            }
        ],
    )
    _write_csv(
        truth_file,
        [
            {
                **base_row,
                "p_draw": "",
                "p_draw_normalized": "0.250000",
            }
        ],
    )

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 0

    summary = _read_summary(output_dir / "official_score_key_v2_summary.json")
    assert summary["joined_rows"] == 1
    assert summary["scored_rows"] == 1
    assert summary["calibration_applied"] is False
    assert summary["mae"] == "0.1500000000"
    assert summary["rmse"] == "0.1500000000"
    assert summary["bias"] == "0.1500000000"


def test_scorer_blocks_zero_score_false_pass(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    base_row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
    }

    _write_csv(prediction_file, [{**base_row, "p_draw": ""}])
    _write_csv(truth_file, [{**base_row, "p_draw": ""}])

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 2
    summary = _read_summary(output_dir / "official_score_key_v2_summary.json")
    assert summary["joined_rows"] == 1
    assert summary["scored_rows"] == 0
    assert summary["zero_score_false_pass_blocked"] is True


def test_scorer_blocks_duplicate_prediction_keys(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
        "p_draw": "0.400000",
    }

    _write_csv(prediction_file, [row, row])
    _write_csv(truth_file, [row])

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 2


def test_scorer_blocks_duplicate_truth_keys(tmp_path: Path) -> None:
    prediction_file = tmp_path / "predictions.csv"
    truth_file = tmp_path / "truth.csv"
    output_dir = tmp_path / "output"

    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    row = {
        "target_year": "2019",
        "source_family": "SPORTSMAN",
        "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
        "draw_pool": "random",
        "hunt_code": "DB0007",
        "score_scope": "TOTAL",
        "residency": "",
        "points": "0",
        "probability_metric": "p_draw",
        "official_score_key_v2": key,
        "p_draw": "0.250000",
    }

    _write_csv(prediction_file, [row])
    _write_csv(truth_file, [row, row])

    rc = scorer_main(
        [
            "--predictions",
            str(prediction_file),
            "--truth",
            str(truth_file),
            "--target-year",
            "2019",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert rc == 2


def test_duplicate_key_error_message_includes_repeated_key_sample() -> None:
    key = "2019|SPORTSMAN|SPORTSMAN_RANDOM_ONLY|random|DB0007|TOTAL||0|p_draw"
    rows = [
        {
            "official_score_key_v2": key,
        },
        {
            "official_score_key_v2": key,
        },
    ]

    with pytest.raises(OfficialScoreKeyV2ValidationError) as exc_info:
        _validate_official_score_key_v2_rows(rows, role="prediction")

    message = str(exc_info.value)
    assert "prediction duplicate official_score_key_v2 keys" in message
    assert key in message


def test_exact_duplicate_family_predictions_are_deduped() -> None:
    rows = [
        _finalize_prediction_output_row(
            {
                "target_year": "2019",
                "family": "sportsman",
                "hunt_code": "DB0007",
                "hunt_name": "Sportsman Deer",
                "species": "Deer",
                "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
                "draw_pool": "random",
                "residency": "",
                "points": "0",
                "p_draw": "0.400000",
                "source_file": "alpha.pdf",
            }
        ),
        _finalize_prediction_output_row(
            {
                "target_year": "2019.0",
                "family": "sportsman",
                "hunt_code": "DB0007",
                "hunt_name": "Sportsman Deer",
                "species": "Deer",
                "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
                "draw_pool": "random",
                "residency": "",
                "points": "0.0",
                "p_draw": "0.400000",
                "source_file": "beta.pdf",
            }
        ),
    ]

    deduped_rows, report = _dedupe_final_family_prediction_rows(rows)

    assert len(deduped_rows) == 1
    assert report["exact_duplicate_rows_dropped"] == 1
    assert report["exact_duplicate_key_count"] == 1
    assert report["conflict_key_count"] == 0


def test_conflicting_duplicate_family_predictions_are_reported() -> None:
    rows = [
        _finalize_prediction_output_row(
            {
                "target_year": "2019",
                "family": "sportsman",
                "hunt_code": "DB0007",
                "hunt_name": "Sportsman Deer",
                "species": "Deer",
                "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
                "draw_pool": "random",
                "residency": "",
                "points": "0",
                "p_draw": "0.400000",
                "source_file": "alpha.pdf",
            }
        ),
        _finalize_prediction_output_row(
            {
                "target_year": "2019",
                "family": "sportsman",
                "hunt_code": "DB0007",
                "hunt_name": "Sportsman Deer",
                "species": "Deer",
                "draw_system_type": "SPORTSMAN_RANDOM_ONLY",
                "draw_pool": "random",
                "residency": "",
                "points": "0",
                "p_draw": "0.450000",
                "source_file": "beta.pdf",
            }
        ),
    ]

    deduped_rows, report = _dedupe_final_family_prediction_rows(rows)

    assert len(deduped_rows) == 0
    assert report["conflict_key_count"] == 1
    assert report["exact_duplicate_rows_dropped"] == 0


def test_truth_comparable_drops_exact_duplicate_structural_rows(tmp_path: Path) -> None:
    truth_file = tmp_path / "truth.csv"
    prediction_file = tmp_path / "predictions.csv"
    output_dir = tmp_path / "truth_out"

    key = "2021|CWMU_BIG_GAME|BONUS_CWMU_BIG_GAME|design_bonus_cwmu_big_game__class_antlerless_elk__pool_cwmu_antlerless_elk__species_elk__hunt_cwmu__sex_antlerless|EA1121|TOTAL||15|p_draw"
    _write_csv(
        prediction_file,
        [
            {
                "target_year": "2021",
                "source_family": "CWMU_BIG_GAME",
                "draw_system_type": "BONUS_CWMU_BIG_GAME",
                "draw_pool": "design_bonus_cwmu_big_game__class_antlerless_elk__pool_cwmu_antlerless_elk__species_elk__hunt_cwmu__sex_antlerless",
                "draw_pool_key": "design_bonus_cwmu_big_game__class_antlerless_elk__pool_cwmu_antlerless_elk__species_elk__hunt_cwmu__sex_antlerless",
                "hunt_code": "EA1121",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "15",
                "probability_metric": "p_draw",
                "official_score_key_v2": key,
                "p_draw": "",
            }
        ],
    )
    truth_row = {
        "model_target_year": "2021",
        "actual_draw_year": "2020",
        "hunt_code": "EA1121",
        "points": "15",
        "residency": "",
        "source_file": "2020_PERMITS=2021_MODEL__ANTLERLESS_ELK_DRAW_RESULTS__CWMU_ANTLERLESS_ELK__CWMU_UNIQUE_PAGES.pdf",
        "draw_system_type": "BONUS_CWMU_BIG_GAME",
        "draw_pool": "cwmu_antlerless_elk",
        "hunt_class": "ANTLERLESS_ELK",
        "hunt_type": "CWMU",
        "species": "Elk",
        "sex_type": "Antlerless",
        "total_eligible_applicants": "0",
        "total_p_draw": "",
        "p_draw": "",
    }
    _write_csv(truth_file, [truth_row, truth_row])

    status = build_score_key_v2_truth_comparable(
        Namespace(
            truth=truth_file,
            predictions=prediction_file,
            source_year=2020,
            target_year=2021,
            output_dir=output_dir,
        )
    )

    assert status["score_key_v2_clean"] is True
    assert status["duplicate_score_key_v2_rows"] == 0
    assert status["exact_duplicate_score_key_v2_rows_dropped"] == 1

    with (output_dir / "truth_scorable_multiscope_long_score_key_v2.csv").open(encoding="utf-8", newline="") as handle:
        comparable_rows = list(csv.DictReader(handle))
    with (output_dir / "truth_exact_duplicate_score_key_v2_rows_dropped.csv").open(encoding="utf-8", newline="") as handle:
        dropped_rows = list(csv.DictReader(handle))

    assert len(comparable_rows) == 1
    assert len(dropped_rows) == 1
    assert comparable_rows[0]["official_score_key_v2"] == key


def test_reference_only_truth_rows_are_excluded_from_score_key_alignment(tmp_path: Path) -> None:
    truth_file = tmp_path / "truth.csv"
    prediction_file = tmp_path / "predictions.csv"
    output_dir = tmp_path / "truth_out"

    _write_csv(
        prediction_file,
        [
            {
                "target_year": "2021",
                "source_family": "OIL_BIG_GAME",
                "draw_system_type": "BONUS_OIL_BIG_GAME",
                "draw_pool": "reference_only",
                "hunt_code": "RE1000",
                "score_scope": "TOTAL",
                "residency": "",
                "points": "0",
                "probability_metric": "p_draw",
                "official_score_key_v2": "2021|OIL_BIG_GAME|BONUS_OIL_BIG_GAME|reference_only|RE1000|TOTAL||0|p_draw",
                "p_draw": "",
            }
        ],
    )
    _write_csv(
        truth_file,
        [
            {
                "model_target_year": "2021",
                "actual_draw_year": "2020",
                "hunt_code": "RE1000",
                "points": "0",
                "residency": "",
                "source_file": "20_antlerless_drawing_odds_report(1).pdf",
                "draw_system_type": "REFERENCE_ONLY",
                "draw_pool": "reference_only",
            }
        ],
    )

    status = build_score_key_v2_truth_comparable(
        Namespace(
            truth=truth_file,
            predictions=prediction_file,
            source_year=2020,
            target_year=2021,
            output_dir=output_dir,
        )
    )

    assert status["multiscope_scorable_rows"] == 0
    assert status["unmatched_truth_rows"] == 0
    assert status["excluded_reason_counts"] == {"REFERENCE_ONLY_NOT_DRAW": 1}
