from __future__ import annotations

import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "annotate_2026_draw_source_identity.py"
CANONICAL_2026 = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
CANONICAL_2025 = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
AUDIT = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_results_2026_source_identity_annotation.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_2026_source_identity_keeps_adult_youth_and_conservation_lineage() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)

    audit = read_rows(AUDIT)
    status_counts = Counter(row["status"] for row in audit)
    assert status_counts == {
        "MATCHED_TURKEY_SOURCE_ROW": 146,
        "MATCHED_TURKEY_SOURCE_ROW_COALESCED_ZERO_OUTCOME": 1,
        "EXCLUDED_BONUS_POINT_REFERENCE": 39,
        "MATCHED_CONSERVATION_SOURCE_ROW": 3,
    }

    turkey_rows = [
        row for row in read_rows(CANONICAL_2026)
        if row["source_dataset"] == "UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260618"
        and row["notes"] == "2026_turkey_03_turkey"
    ]
    assert len(turkey_rows) == 147
    assert all(row["source_row_identifier"] for row in turkey_rows)
    assert sum("coalesced-official-source-rows=" in row["source_row_identifier"] for row in turkey_rows) == 1
    assert {row["source_is_youth"] for row in turkey_rows} == {"false", "true", "ambiguous_coalesced_true_false"}

    conservation_rows = [
        row for row in read_rows(CANONICAL_2025)
        if row["source_scope"] == "BLACK_BEAR_CONSERVATION_ORGANIZATION_ALLOCATION"
    ]
    assert len(conservation_rows) == 3
    assert all(row["source_row_identifier"].startswith("conservation-permit-source-rows=") for row in conservation_rows)
