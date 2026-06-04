import subprocess
import sys
from pathlib import Path

from tools.verify_prediction_engine_targeted_backfill import (
    APPROVED_FIELDS,
    CsvData,
    audit_actual_diffs,
    is_forbidden,
    norm,
    quota_arithmetic,
)


def test_approved_column_acceptance() -> None:
    assert "quota_source_year" in APPROVED_FIELDS
    assert "permit_allotment_2026_total" in APPROVED_FIELDS
    assert not is_forbidden("quota_source_year")


def test_forbidden_column_rejection() -> None:
    assert is_forbidden("p_draw_mean")
    assert is_forbidden("random_draw_odds_2026")
    assert is_forbidden("availability_status")


def test_quota_arithmetic_rejection() -> None:
    result = quota_arithmetic(
        [
            {
                "hunt_code": "EB1",
                "permits_2026_res": "10",
                "permits_2026_nr": "1",
                "permits_2026_total": "99",
            }
        ],
        ("permits_2026_res", "permits_2026_nr", "permits_2026_total"),
    )
    assert result["status"] == "FAIL"
    assert result["failures"] == 1


def test_duplicate_source_hunt_code_conflict_rejection() -> None:
    before = CsvData(
        path="feed.csv",
        header=["hunt_code", "quota_source_year"],
        rows=[{"hunt_code": "EB1", "quota_source_year": ""}],
        size_bytes=0,
        sha256="",
    )
    after = CsvData(
        path="feed.csv",
        header=["hunt_code", "quota_source_year"],
        rows=[{"hunt_code": "EB1", "quota_source_year": "2026"}],
        size_bytes=0,
        sha256="",
    )
    database = {"EB1": {"permit_allotment_2026_total": "12"}}
    database_dupes = {
        "EB1": [
            {"permit_allotment_2026_total": "12"},
            {"permit_allotment_2026_total": "13"},
        ]
    }
    _, _, _, rows = audit_actual_diffs(before, after, database, database_dupes, "DATABASE.csv")
    assert rows[0]["status"] == "FAIL"
    assert "database_duplicate_hunt_code_conflicting_source_values" in rows[0]["notes"]


def test_normalized_string_comparison() -> None:
    assert norm("12.0") == "12"
    assert norm(" 12 ") == "12"
    assert norm("12.5") == "12.5"


def test_missing_summary_handling(tmp_path: Path) -> None:
    database = tmp_path / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    database.parent.mkdir(parents=True)
    database.write_text("hunt_code,permit_allotment_2026_total\nEB1,1\n", encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "tools/verify_prediction_engine_targeted_backfill.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(tmp_path),
            "--database",
            "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "--summary",
            "missing_summary.csv",
            "--skip-remote",
            "--skip-validation-commands",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing_summary:missing_summary.csv" in result.stderr
