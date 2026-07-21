#!/usr/bin/env python3
"""Repair the 2019 EA1121 CWMU adult/youth lane metadata split.

This is a metadata-only repair. It does not change hunt codes, points,
applicant counts, success counts, probabilities, permit counts, or row counts.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET_YEAR = "2020"
HUNT_CODE = "EA1121"

INPUT_FILES = [
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv",
    REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
]

ADULT_SOURCE_FILE = "2019_PERMITS=2020_MODEL__CWMU_ANTLERLESS_ELK_DRAW_RESULTS.pdf"
ADULT_SOURCE_PATH = (
    r"pipeline\RAW\hunt_unit_database\2019\pdf\draw_odds\CWMU\ANTLERLESS CWMU"
    rf"\{ADULT_SOURCE_FILE}"
)

ADULT_METADATA = {
    "source_scope": ADULT_SOURCE_FILE,
    "source_file": ADULT_SOURCE_FILE,
    "draw_source_file": ADULT_SOURCE_FILE,
    "source_pdf": ADULT_SOURCE_FILE,
    "source_path": ADULT_SOURCE_PATH,
    "draw_design": "BONUS_CWMU_BIG_GAME",
    "draw_system_type": "BONUS_CWMU_BIG_GAME",
    "draw_pool": "cwmu_antlerless_elk",
    "hunt_class": "ANTLERLESS_ELK",
    "hunt_draw_class": "ANTLERLESS_ELK",
    "species": "Elk",
    "hunt_type": "CWMU",
    "sex_type": "Antlerless",
    "pdf_page": "131",
    "official_page": "131",
}

YOUTH_SOURCE_FILE = "2019_PERMITS=2020_MODEL__CWMU_YOUTH_ANTLERLESS_ELK_DRAW_RESULTS.pdf"
YOUTH_SOURCE_PATH = (
    r"pipeline\RAW\hunt_unit_database\2019\pdf\draw_odds\CWMU\ANTLERLESS CWMU"
    rf"\{YOUTH_SOURCE_FILE}"
)

YOUTH_METADATA = {
    "source_scope": YOUTH_SOURCE_FILE,
    "source_file": YOUTH_SOURCE_FILE,
    "draw_source_file": YOUTH_SOURCE_FILE,
    "source_pdf": YOUTH_SOURCE_FILE,
    "source_path": YOUTH_SOURCE_PATH,
    "draw_design": "BONUS_CWMU_BIG_GAME",
    "draw_system_type": "BONUS_CWMU_BIG_GAME",
    "draw_pool": "cwmu_youth_antlerless_elk",
    "hunt_class": "YOUTH_ANTLERLESS_ELK",
    "hunt_draw_class": "YOUTH_ANTLERLESS_ELK",
    "species": "Elk",
    "hunt_type": "CWMU",
    "sex_type": "Antlerless",
    "pdf_page": "123",
    "official_page": "123",
}


def target_year(row: dict[str, str]) -> str:
    return row.get("model_target_year") or row.get("target_year") or row.get("draw_year") or ""


def repair_file(path: Path, stamp: str) -> dict[str, object]:
    backup = path.with_name(f"{path.stem}.backup_ea1121_cwmu_lane_split_{stamp}{path.suffix}")
    shutil.copy2(path, backup)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    adult_changed = 0
    youth_changed = 0
    for row in rows:
        if target_year(row) != TARGET_YEAR or row.get("hunt_code") != HUNT_CODE:
            continue
        notes = row.get("qa_notes", "")
        if "rebuilt_bucket=ANTLERLESS_ELK" in notes:
            metadata = ADULT_METADATA
            adult_changed += 1
        elif "rebuilt_bucket=YOUTH_ANTLERLESS_ELK" in notes:
            metadata = YOUTH_METADATA
            youth_changed += 1
        else:
            continue
        for field, value in metadata.items():
            if field in fields:
                row[field] = value

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "path": str(path),
        "backup": str(backup),
        "rows": len(rows),
        "adult_cwmu_rows_repaired": adult_changed,
        "youth_cwmu_rows_confirmed": youth_changed,
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in INPUT_FILES:
        print(repair_file(path, stamp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
