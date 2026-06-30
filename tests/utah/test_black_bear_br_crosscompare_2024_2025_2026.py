import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/crosscompare-black-bear-draw-odds-2024-2025-2026.py"
NORMALIZED_2025 = ROOT / "data_truth/draw_results_truth/normalized/black_bear_2025_draw_odds_model_target_2026_permit_totals.csv"
CROSSWALK = ROOT / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
SUMMARY = ROOT / "data_truth/crosswalk_truth/validation/black_bear_BR_2024_2025_2026_crosswalk_summary.json"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def run_script() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)


def test_black_bear_2025_draw_odds_extracts_expected_source_rows() -> None:
    run_script()
    rows = read_rows(NORMALIZED_2025)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert len(rows) == 97
    assert len({row["hunt_code"] for row in rows}) == 97
    assert summary["draw_2025_rows"] == 97
    assert summary["draw_2025_total_public_permits"] == 994
    assert summary["draw_2025_codes_missing_2024"] == ["BR7237", "BR7325"]
    assert summary["draw_2024_codes_missing_2025"] == ["BR7019"]


def test_black_bear_la_sal_codes_crosswalk_to_2026_mtns_successors() -> None:
    run_script()
    rows = {(row["historical_2025_code"], row["current_2026_code"]): row for row in read_rows(CROSSWALK)}

    assert rows[("BR7008", "BR7022")]["mapping_status"] == "HISTORICAL_CODE_RECODED_TO_CURRENT"
    assert rows[("BR7008", "BR7022")]["permits_2025_total"] == "43"
    assert rows[("BR7008", "BR7022")]["permits_2026_total"] == "43"
    assert rows[("BR7008", "BR7022")]["numeric_comparison_2025_to_2026"] == "MATCH"

    assert rows[("BR7108", "BR7127")]["mapping_status"] == "HISTORICAL_CODE_RECODED_TO_CURRENT"
    assert rows[("BR7108", "BR7127")]["permits_2025_total"] == "27"
    assert rows[("BR7108", "BR7127")]["permits_2026_total"] == "27"
    assert rows[("BR7208", "BR7239")]["mapping_status"] == "HISTORICAL_CODE_RECODED_TO_CURRENT"
    assert rows[("BR7208", "BR7239")]["permits_2025_total"] == "6"
    assert rows[("BR7208", "BR7239")]["permits_2026_total"] == "6"


def test_black_bear_br7307_code_reuse_is_preserved_not_collapsed() -> None:
    run_script()
    rows = read_rows(CROSSWALK)
    historical = next(row for row in rows if row["historical_2025_code"] == "BR7307" and row["current_2026_code"] == "BR7326")
    current_reuse = next(row for row in rows if not row["historical_2025_code"] and row["current_2026_code"] == "BR7307")

    assert historical["mapping_status"] == "HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED"
    assert historical["permits_2025_total"] == "14"
    assert historical["permits_2026_total"] == "14"
    assert historical["numeric_comparison_2025_to_2026"] == "MATCH"

    assert current_reuse["mapping_status"] == "CURRENT_CODE_REUSED_FOR_CONSERVATION_PERMIT"
    assert current_reuse["permits_2026_total"] == "4"
    assert current_reuse["permits_2026_res"] == ""
    assert current_reuse["permits_2026_nr"] == ""


def test_black_bear_current_only_and_retired_rows_are_explicit_review_evidence() -> None:
    run_script()
    rows = read_rows(CROSSWALK)
    by_current = {row["current_2026_code"]: row for row in rows if row["current_2026_code"] and not row["historical_2025_code"]}
    by_2024 = {row["historical_2024_code"]: row for row in rows if row["historical_2024_code"] and not row["historical_2025_code"]}
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert by_current["BR7021"]["mapping_status"] == "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW"
    assert by_current["BR7126"]["mapping_status"] == "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW"
    assert by_current["BR7238"]["mapping_status"] == "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW"
    assert by_current["BR7324"]["mapping_status"] == "CURRENT_CONSERVATION_NO_DRAW_SOURCE"
    assert by_2024["BR7019"]["mapping_status"] == "RETIRED_AFTER_2024_NO_2025_OR_2026_MATCH"
    assert summary["draw_2025_rows_mapped_to_current_after_crosswalk"] == 97
    assert summary["high_confidence_recode_count"] == 4
