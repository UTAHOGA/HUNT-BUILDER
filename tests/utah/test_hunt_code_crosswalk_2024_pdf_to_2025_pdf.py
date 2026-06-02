from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-2024-to-2025-pdf-hunt-code-crosswalk.py"
SUMMARY = (
    ROOT
    / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years_summary.json"
)
CROSSWALK = (
    ROOT
    / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years.csv"
)
DROPPED = (
    ROOT
    / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_dropped_review.csv"
)


def run_crosswalk() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def _rows_by_code(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["source_hunt_code"]: row for row in csv.DictReader(handle)}


def test_crosswalk_counts_and_guardrail_are_stable() -> None:
    run_crosswalk()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["source_2024_model_target_2025_rows"] == 874
    assert summary["next_year_pdf_model_target_2026_rows"] == 296
    assert summary["database_rows"] == 1449
    assert summary["current_active_database_rows"] == 1412
    assert summary["dropped_or_review_rows"] == 13
    assert summary["status_counts"] == {
        "DROPPED_NO_CURRENT_ACTIVE_MATCH_NO_NEXT_YEAR_PDF_FAMILY": 7,
        "DROPPED_NO_NEXT_YEAR_PDF_OR_CURRENT_ACTIVE_MATCH": 6,
        "MAPPED_BY_TRUSTED_CURRENT_HISTORICAL_CROSSWALK_TO_CURRENT_ACTIVE": 3,
        "REPLACED_BY_NEXT_YEAR_OR_CURRENT_CANDIDATE": 21,
        "SAME_CODE_CURRENT_ACTIVE_NO_NEXT_YEAR_PDF_MATCH": 564,
        "SAME_CODE_IN_2025_PDF_AND_CURRENT_ACTIVE": 273,
    }
    assert "do not modify DATABASE.csv" in summary["guardrail"]


def test_crosswalk_identifies_dropped_replacements_and_same_code_reviews() -> None:
    run_crosswalk()
    rows = _rows_by_code(CROSSWALK)
    dropped_rows = _rows_by_code(DROPPED)

    assert rows["DB1082"]["crosswalk_status"] == "REPLACED_BY_NEXT_YEAR_OR_CURRENT_CANDIDATE"
    assert rows["DB1082"]["mapped_hunt_code"] == "DB1113"
    assert rows["DB1320"]["crosswalk_status"] == "SAME_CODE_IN_2025_PDF_AND_CURRENT_ACTIVE"
    assert rows["MB6200"]["crosswalk_status"] == "SAME_CODE_IN_2025_PDF_AND_CURRENT_ACTIVE"
    assert rows["DB1089"]["crosswalk_status"] == "DROPPED_NO_NEXT_YEAR_PDF_OR_CURRENT_ACTIVE_MATCH"
    assert rows["PB5313"]["crosswalk_status"] == "DROPPED_NO_CURRENT_ACTIVE_MATCH_NO_NEXT_YEAR_PDF_FAMILY"
    assert rows["DB1036"]["crosswalk_status"] == "MAPPED_BY_TRUSTED_CURRENT_HISTORICAL_CROSSWALK_TO_CURRENT_ACTIVE"
    assert rows["DB1036"]["mapped_hunt_code"] == "LD1108"
    assert rows["DB1036"]["mapped_source"] == "TRUSTED_CURRENT_TO_HISTORICAL_CROSSWALK_ACTIVE_DB"

    assert "DB1320" not in dropped_rows
    assert "DB1089" in dropped_rows
