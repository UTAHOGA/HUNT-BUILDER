from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "processed_data/2025_big_game_field_regulations_source_label_audit.json"
CORRECTIONS = (
    ROOT
    / "data_truth/regulations_truth/normalized/2025_big_game_field_regulations_post_publication_corrections.csv"
)
TEXT_LINES = ROOT / "data_truth/regulations_truth/normalized/2025_big_game_field_regulations_text_lines.csv"
NUMBER_TOKENS = ROOT / "data_truth/regulations_truth/normalized/2025_big_game_field_regulations_number_tokens.csv"
EXPECTED_TEXT_CHECKS = (
    ROOT / "data_truth/regulations_truth/normalized/2025_big_game_field_regulations_expected_text_checks.csv"
)


def _run_audit() -> None:
    subprocess.run([sys.executable, "scripts/audit-big-game-field-regulations-2025.py"], cwd=ROOT, check=True)


def test_2025_field_regulations_source_label_audit_passes() -> None:
    _run_audit()

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_file"] == "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf"
    assert summary["expected_title"] == "2025 Utah Big Game Field Regulations"
    assert summary["expected_source_year"] == "2025"
    assert summary["actual_sha256"] == "05a87b5babd0a22af62c993bd3fe0ba106fb18f7029ed60fc75f6babe4dbdaa7"
    assert summary["classification"] == "REGULATION_REFERENCE_ONLY"
    assert summary["modeling_guardrail"] == "DO_NOT_USE_AS_DRAW_ODDS_HARVEST_FEATURE_OR_2026_QUOTA_INPUT"
    assert summary["mislabeled_2026_manifest_items"] == 0
    assert summary["pdf_page_count"] == 68
    assert summary["text_line_count"] == 3723
    assert summary["number_token_count"] == 1483
    assert summary["token_type_counts"] == {"number_or_money": 1217, "code_citation": 141, "date": 125}
    assert summary["expected_text_check_count"] == 50
    assert summary["expected_text_check_failures"] == 0
    assert summary["audit_blocker_count"] == 0
    assert all(summary["checks"].values())


def test_2025_field_regulations_post_publication_corrections_are_captured() -> None:
    _run_audit()

    with CORRECTIONS.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 7
    assert {row["source_year"] for row in rows} == {"2025"}
    assert {row["source_title"] for row in rows} == {"2025 Utah Big Game Field Regulations"}
    assert all(row["classification"] == "REGULATION_REFERENCE_ONLY" for row in rows)
    assert any(row["guidebook_page"] == "38" and "restricted muzzleloader" in row["summary"] for row in rows)
    assert any(row["guidebook_page"] == "25-26" and "archery-hunt" in row["summary"] for row in rows)


def test_2025_field_regulations_line_and_number_audits_are_materialized() -> None:
    _run_audit()

    with TEXT_LINES.open(newline="", encoding="utf-8-sig") as handle:
        line_rows = list(csv.DictReader(handle))
    with NUMBER_TOKENS.open(newline="", encoding="utf-8-sig") as handle:
        token_rows = list(csv.DictReader(handle))
    with EXPECTED_TEXT_CHECKS.open(newline="", encoding="utf-8-sig") as handle:
        check_rows = list(csv.DictReader(handle))

    assert len(line_rows) == 3723
    assert len(token_rows) == 1483
    assert len(check_rows) == 50
    assert {row["status"] for row in check_rows} == {"PASS"}

    lines_by_page = {}
    for row in line_rows:
        lines_by_page.setdefault(row["printed_page"], []).append(row["line_text"])

    assert any("General archery buck deer Aug. 16-Sept. 12" in line for line in lines_by_page["7"])
    assert any("Application fee $10 $16 $21" in line for line in lines_by_page["9"])
    assert any("Any legal weapon Uinta Basin private lands only Aug. 1-Nov. 15" in line for line in lines_by_page["19"])
    assert any("Red Butte Research Natural Area" in line["line_text"] for line in line_rows if line["printed_page"] == "29") is False
    assert any("meets all requirements for muzzleloaders" in line for line in lines_by_page["70"])

    token_values = {row["token"] for row in token_rows}
    assert {"800-662-3337", "847411", "R657-5-48", "76-11-302", "53-5a-108"}.issubset(token_values)
