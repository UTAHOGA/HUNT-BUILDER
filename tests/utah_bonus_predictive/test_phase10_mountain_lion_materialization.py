import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase10_mountain_lion_artifacts_are_generated(tmp_path: Path) -> None:
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

    csv_path = tmp_path / "mountain_lion_availability_predictions_v1.csv"
    json_path = tmp_path / "mountain_lion_availability_report.json"
    assert csv_path.exists()
    assert json_path.exists()

    rows = _read_csv(csv_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert rows
    assert report["forecast_year"] == 2026
    assert report["total_mountain_lion_rows_produced"] == len(rows)
    assert report["p_draw_non_null_count"] == 0
    assert report["p_draw_pct_non_null_count"] == 0
    assert report["modeled_availability_row_count"] == 0
    assert report["reference_license_based_no_draw_row_count"] == len(rows)
    assert report["p_availability_non_null_count"] == 0
    assert report["availability_pct_non_null_count"] == 0
    assert {row["algorithm_status"] for row in rows} == {"REFERENCE_LICENSE_BASED_NO_DRAW"}
    assert all((row.get("p_availability") or "").strip() == "" for row in rows)
    assert all((row.get("availability_pct") or "").strip() == "" for row in rows)
