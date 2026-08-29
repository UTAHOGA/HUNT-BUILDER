from __future__ import annotations

import csv
from pathlib import Path

from scripts.normalize_canonical_species_by_hunt_code import expected_species


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"


def test_official_hunt_code_species_vocabulary_is_canonical() -> None:
    assert expected_species("DA1001") == "Deer"
    assert expected_species("EA1120") == "Elk"
    assert expected_species("RS6704") == "Rocky Mountain Bighorn Sheep"
    assert expected_species("EB1007") == "Elk"


def test_every_recognized_canonical_hunt_code_has_matching_species_metadata() -> None:
    mismatches: list[tuple[str, str, str, str]] = []
    for path in sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                expected = expected_species(row.get("hunt_code", ""))
                observed = (row.get("species") or "").strip()
                if expected and observed != expected:
                    mismatches.append((path.name, row.get("hunt_code", ""), observed, expected))

    assert mismatches == []
