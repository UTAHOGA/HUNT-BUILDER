import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/extract_legacy_black_bear_residency_ladders.py"
OUTPUT = ROOT / "data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders.csv"
SUMMARY = ROOT / "data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders_summary.json"


def test_legacy_bear_pdf_residency_ladders_reconcile_to_canonical_totals() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    with OUTPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["parity_status"] == "PASS_FOR_CANONICAL_COVERED_YEARS_2019_2022"
    assert summary["canonical_freeze_status"] == "2018_BEAR_SCOPE_PENDING"
    assert summary["canonical_keys_missing_from_pdf"] == []
    assert summary["value_mismatches"] == []
    for year in ("2019", "2020", "2021", "2022"):
        assert summary["per_year"][year]["status"] == "PASS"
    assert summary["per_year"]["2018"]["status"] == "OFFICIAL_PDF_EXTRACTED_CANONICAL_BEAR_SCOPE_NOT_FROZEN"
    assert {row["reported_draw_year"] for row in rows} == {"2018", "2019", "2020", "2021", "2022"}
    assert {row["residency"] for row in rows} == {"Resident", "Nonresident"}

    br7003 = [row for row in rows if row["reported_draw_year"] == "2021" and row["hunt_code"] == "BR7003"]
    assert len(br7003) == 40
    assert next(row for row in br7003 if row["residency"] == "Resident" and row["points"] == "7")["eligible_applicants"] == "3"
    assert next(row for row in br7003 if row["residency"] == "Nonresident" and row["points"] == "5")["total_permits"] == "1"
