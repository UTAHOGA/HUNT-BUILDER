import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_phase12_bear_artifacts_are_generated(tmp_path: Path) -> None:
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

    csv_path = tmp_path / "bear_predictions_v1.csv"
    json_path = tmp_path / "bear_report.json"
    assert csv_path.exists()
    assert json_path.exists()

    rows = _read_csv(csv_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    ho_rows = [row for row in rows if row.get("bear_draw_subtype") == "HARVEST_OBJECTIVE_AVAILABILITY"]
    pursuit_rows = [row for row in rows if row.get("bear_draw_subtype") == "UNLIMITED_PURSUIT_PERMIT"]
    restricted_pursuit_rows = [row for row in rows if row.get("bear_draw_subtype") == "RESTRICTED_BEAR_PURSUIT"]
    modeled_rows = [row for row in rows if row.get("algorithm_status") == "MODELED_BONUS"]

    assert rows
    assert report["forecast_year"] == 2026
    assert report["harvest_objective_row_count"] == len(ho_rows)
    assert report["unlimited_pursuit_permit_row_count"] == len(pursuit_rows)
    assert report["restricted_pursuit_modeled_row_count"] == len([row for row in restricted_pursuit_rows if row.get("algorithm_status") == "MODELED_BONUS"])
    assert report["harvest_objective_p_draw_non_null_count"] == 0
    assert report["unlimited_pursuit_permit_p_draw_non_null_count"] == 0
    assert report["p_preference_draw_non_null_count"] == 0
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in rows)
    assert all((row.get("p_draw") or "").strip() == "" for row in ho_rows)
    assert all((row.get("p_draw") or "").strip() == "" for row in pursuit_rows)
    assert any(row.get("algorithm_status") == "MODELED_BONUS" for row in restricted_pursuit_rows)
    assert all((row.get("p_bonus_pool") or "").strip() != "" for row in modeled_rows)


def test_bear_known_zero_residency_quota_preserves_canonical_zero_point(monkeypatch) -> None:
    from engine.utah_draw_predictive import bear as bear_module

    monkeypatch.setattr(bear_module, "official_bear_draw_odds_hunt_codes", lambda: set())
    monkeypatch.setattr(bear_module, "official_bear_pursuit_hunt_codes", lambda: set())

    truth_rows = [
        {
            "year": "2026",
            "hunt_code": "BR9999",
            "hunt_name": "Unit Test",
            "species": "Black Bear",
            "hunt_type": "Limited Entry",
            "weapon": "Any Legal Weapon",
            "draw_pool": "standard",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "10",
            "bonus_permits": "1",
            "regular_permits": "0",
            "total_permits": "1",
        },
        {
            "year": "2026",
            "hunt_code": "BR9999",
            "hunt_name": "Unit Test",
            "species": "Black Bear",
            "hunt_type": "Limited Entry",
            "weapon": "Any Legal Weapon",
            "draw_pool": "standard",
            "residency": "Nonresident",
            "points": "0",
            "eligible_applicants": "0",
            "bonus_permits": "0",
            "regular_permits": "0",
            "total_permits": "0",
        },
    ]
    db_rows = [
        {
            "hunt_code": "BR9999",
            "hunt_name": "Unit Test",
            "species": "Black Bear",
            "hunt_type": "Limited Entry",
            "weapon": "Any Legal Weapon",
            "hunt_class": "Public",
            "permits_2026_res": "1",
            "permits_2026_nr": "0",
            "permits_2026_total": "1",
        }
    ]

    rows, _report = bear_module.build_bear_bonus_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=2027,
        history_years=[2026],
    )

    nonresident_rows = [
        row
        for row in rows
        if row.get("hunt_code") == "BR9999" and row.get("residency") == "Nonresident"
    ]
    assert len(nonresident_rows) == 1
    assert nonresident_rows[0]["points"] == "0"
    assert nonresident_rows[0]["bear_bonus_valid"] == "FALSE"
    assert nonresident_rows[0]["p_draw"] == ""
    assert "KNOWN_ZERO_RESIDENCY_QUOTA" in nonresident_rows[0]["data_quality_flags"]
