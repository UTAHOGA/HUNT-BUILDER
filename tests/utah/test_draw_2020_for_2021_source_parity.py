from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "data_truth" / "draw_results_truth" / "validation"
SUMMARY = VALIDATION / "draw_2020_for_2021_source_parity_summary.json"
PARITY_CSV = VALIDATION / "draw_2020_for_2021_source_parity.csv"
REPORT_MD = ROOT / "processed_data" / "draw_2020_for_2021_source_parity.md"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_2020_draw_source_parity_runs() -> None:
    subprocess.run([sys.executable, "scripts/audit-draw-2020-for-2021-source-parity.py"], cwd=ROOT, check=True)

    assert SUMMARY.exists()
    assert PARITY_CSV.exists()
    assert REPORT_MD.exists()


def test_2020_draw_source_pdfs_are_byte_identical_in_active_repo() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    parity_rows = rows(PARITY_CSV)

    assert summary["expected_file_count"] == 13
    assert summary["byte_match_count"] == 13
    assert summary["review_file_count"] == 0
    assert all(row["status"] == "PASS" for row in parity_rows)


def test_2020_draw_truth_native_count_is_anchored_and_source_label_is_verified() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["model_target_year"] == "2021"
    assert summary["source_draw_result_year"] == "2020"
    assert summary["draw_truth_2020_rows"] == 33069
    assert summary["draw_truth_2020_unique_hunt_codes"] == 1014
    assert summary["draw_truth_source_label_status"] == "SOURCE_LABELS_MATCH_EXPECTED_FILES"
