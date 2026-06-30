import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase15_youth_artifacts_are_generated(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.utah_bonus_predictive.materialize",
            "--output-dir",
            str(tmp_path),
            "--forecast-year",
            "2026",
            "--history-years",
            "2021,2022,2023,2024,2025",
            "--skip-upstream",
        ],
        cwd=REPO,
        check=True,
    )

    csv_path = tmp_path / "youth_draw_predictions_v1.csv"
    json_path = tmp_path / "youth_draw_report.json"

    assert csv_path.exists()
    assert json_path.exists()

    rows = _read_csv(csv_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert report["forecast_year"] == 2026
    assert report["active_predictive_youth_row_count"] == len(rows)
    assert report["youth_general_any_bull_elk_row_count"] == 2
    assert report["modeled_random_only_row_count"] == 2
    assert report["p_draw_non_null_count"] == 2
    assert report["p_draw_pct_non_null_count"] == 2
    assert report["p_preference_draw_non_null_count"] == 0
    assert report["p_bonus_pool_non_null_count"] == 0
    assert report["p_random_pool_non_null_count"] == 0

    eb1007_rows = [row for row in rows if row["hunt_code"] == "EB1007"]
    assert len(eb1007_rows) == 2
    assert {row["draw_system_type"] for row in eb1007_rows} == {"YOUTH_GENERAL_ANY_BULL_ELK"}
    assert {row["algorithm_status"] for row in eb1007_rows} == {"MODELED_RANDOM_ONLY"}
    assert {row["draw_design"] for row in eb1007_rows} == {"Random"}
    assert {row["draw_method"] for row in eb1007_rows} == {"Strict random"}
    assert {row["point_system"] for row in eb1007_rows} == {"none"}
    assert {row["sex_type"] for row in eb1007_rows} == {"Hunter's Choice"}
    assert {row["hunt_class"] for row in eb1007_rows} == {"Youth Random"}
    assert all(row["p_draw"] == row["p_draw_mean"] for row in eb1007_rows)
    assert all(row["p_draw_p10"] == row["p_draw_mean"] for row in eb1007_rows)
    assert all(row["p_draw_p50"] == row["p_draw_mean"] for row in eb1007_rows)
    assert all(row["p_draw_p90"] == row["p_draw_mean"] for row in eb1007_rows)
    assert all(row["p_preference_draw"] == "" for row in eb1007_rows)
    assert all(row["p_bonus_pool"] == "" for row in eb1007_rows)
    assert all(row["p_random_pool"] == "" for row in eb1007_rows)


def test_phase15_youth_2027_materialization_keeps_draw_only_elk_separate(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "engine.utah_bonus_predictive.materialize",
            "--output-dir",
            str(tmp_path),
            "--forecast-year",
            "2027",
            "--history-years",
            "2021,2022,2023,2024,2025,2026",
            "--skip-upstream",
        ],
        cwd=REPO,
        check=True,
    )

    csv_path = tmp_path / "youth_draw_predictions_v1.csv"
    json_path = tmp_path / "youth_draw_report.json"

    rows = _read_csv(csv_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))

    eb1007_rows = [row for row in rows if row["hunt_code"] == "EB1007"]
    eb1011_rows = [row for row in rows if row["hunt_code"] == "EB1011"]

    assert report["forecast_year"] == 2027
    assert report["active_predictive_youth_row_count"] == 2
    assert report["youth_general_any_bull_elk_row_count"] == 2
    assert report["modeled_random_only_row_count"] == 2
    assert report["duplicate_key_count"] == 0

    assert len(eb1007_rows) == 2
    assert eb1011_rows == []
    assert {row["algorithm_status"] for row in eb1007_rows} == {"MODELED_RANDOM_ONLY"}
    assert {row["draw_system_type"] for row in eb1007_rows} == {"YOUTH_GENERAL_ANY_BULL_ELK"}
    assert all(row["p_draw"].strip() for row in eb1007_rows)
    assert all(row["p_draw"] == row["p_draw_mean"] for row in eb1007_rows)
    assert all(row["p_preference_draw"] == "" for row in eb1007_rows)
    assert all(row["p_bonus_pool"] == "" for row in eb1007_rows)
    assert all(row["p_random_pool"] == "" for row in eb1007_rows)
