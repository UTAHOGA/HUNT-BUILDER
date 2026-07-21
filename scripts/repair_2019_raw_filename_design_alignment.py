#!/usr/bin/env python3
"""Repair 2019->2020 draw-result metadata from split raw PDF filenames.

This is a metadata-only repair. It does not change hunt codes, points,
residency, applicant counts, success counts, probabilities, permit counts, or
row counts.
"""

from __future__ import annotations

import csv
import re
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET_YEAR = "2020"
BASE_SOURCE_PATH = r"pipeline\RAW\hunt_unit_database\2019\pdf\draw_odds"
INPUT_FILES = [
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv",
    REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv",
]


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def source_path(source_file: str, subdir: str = "") -> str:
    parts = [BASE_SOURCE_PATH]
    if subdir:
        parts.extend(subdir.split("/"))
    parts.append(source_file)
    return "\\".join(parts)


def common(
    *,
    source_file: str,
    draw_design: str,
    draw_system_type: str,
    draw_pool: str,
    hunt_class: str,
    species: str,
    hunt_type: str,
    sex_type: str,
    subdir: str = "",
) -> dict[str, str]:
    return {
        "source_scope": source_file,
        "source_file": source_file,
        "draw_source_file": source_file,
        "source_pdf": source_file,
        "source_path": source_path(source_file, subdir),
        "draw_design": draw_design,
        "draw_system_type": draw_system_type,
        "draw_pool": draw_pool,
        "hunt_class": hunt_class,
        "hunt_draw_class": hunt_class,
        "species": species,
        "hunt_type": hunt_type,
        "sex_type": sex_type,
    }


def classify_source_file(source_file: str) -> dict[str, str] | None:
    name = compact(source_file)
    if not name.startswith("2019_permits_2020_model"):
        return None

    if "cwmu_big_game_deer_buck" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_big_game_deer_buck",
            hunt_class="BIG_GAME_LIMITED_ENTRY_DEER",
            species="Deer",
            hunt_type="CWMU",
            sex_type="Buck",
            subdir="CWMU/BIG GAME CWMU",
        )
    if "cwmu_big_game_elk_bull" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_big_game_elk_bull",
            hunt_class="BIG_GAME_LIMITED_ENTRY_ELK",
            species="Elk",
            hunt_type="CWMU",
            sex_type="Bull",
            subdir="CWMU/BIG GAME CWMU",
        )
    if "cwmu_big_game_pronghorn_buck" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_big_game_pronghorn_buck",
            hunt_class="BIG_GAME_LIMITED_ENTRY_PRONGHORN",
            species="Pronghorn",
            hunt_type="CWMU",
            sex_type="Buck",
            subdir="CWMU/BIG GAME CWMU",
        )
    if "cwmu_big_game_moose_bull" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_big_game_moose_bull",
            hunt_class="BIG_GAME_MOOSE",
            species="Moose",
            hunt_type="CWMU",
            sex_type="Bull",
            subdir="CWMU/BIG GAME CWMU",
        )

    if "cwmu_youth_antlerless_elk" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_youth_antlerless_elk",
            hunt_class="YOUTH_ANTLERLESS_ELK",
            species="Elk",
            hunt_type="CWMU",
            sex_type="Antlerless",
            subdir="CWMU/ANTLERLESS CWMU",
        )
    if "cwmu_youth_antlerless_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_youth_antlerless_deer",
            hunt_class="YOUTH_ANTLERLESS_DEER",
            species="Deer",
            hunt_type="CWMU",
            sex_type="Antlerless",
            subdir="CWMU/ANTLERLESS CWMU",
        )
    if "cwmu_youth_antlerless_pronghorn" in name or "cwmu_youth_doe_pronghorn" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_youth_doe_pronghorn",
            hunt_class="YOUTH_ANTLERLESS_PRONGHORN",
            species="Pronghorn",
            hunt_type="CWMU",
            sex_type="Doe",
            subdir="CWMU/ANTLERLESS CWMU",
        )
    if "cwmu_antlerless_elk" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_antlerless_elk",
            hunt_class="ANTLERLESS_ELK",
            species="Elk",
            hunt_type="CWMU",
            sex_type="Antlerless",
            subdir="CWMU/ANTLERLESS CWMU",
        )
    if "cwmu_antlerless_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_antlerless_deer",
            hunt_class="ANTLERLESS_DEER",
            species="Deer",
            hunt_type="CWMU",
            sex_type="Antlerless",
            subdir="CWMU/ANTLERLESS CWMU",
        )
    if "cwmu_doe_pronghorn" in name or "cwmu_antlerless_pronghorn" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_CWMU_BIG_GAME",
            draw_system_type="BONUS_CWMU_BIG_GAME",
            draw_pool="cwmu_doe_pronghorn",
            hunt_class="ANTLERLESS_PRONGHORN",
            species="Pronghorn",
            hunt_type="CWMU",
            sex_type="Doe",
            subdir="CWMU/ANTLERLESS CWMU",
        )

    if "p_l_e_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_PLE_BIG_GAME",
            draw_system_type="BONUS_PLE_BIG_GAME",
            draw_pool="premium_limited_entry_deer",
            hunt_class="BIG_GAME_PREMIUM_LIMITED_ENTRY_DEER",
            species="Deer",
            hunt_type="Premium Limited Entry",
            sex_type="Buck",
        )
    if "l_e_elk" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_LE_BIG_GAME",
            draw_system_type="BONUS_LE_BIG_GAME",
            draw_pool="limited_entry_elk",
            hunt_class="BIG_GAME_LIMITED_ENTRY_ELK",
            species="Elk",
            hunt_type="Limited Entry",
            sex_type="Bull",
        )
    if "l_e_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_LE_BIG_GAME",
            draw_system_type="BONUS_LE_BIG_GAME",
            draw_pool="limited_entry_deer",
            hunt_class="BIG_GAME_LIMITED_ENTRY_DEER",
            species="Deer",
            hunt_type="Limited Entry",
            sex_type="Buck",
        )
    if "l_e_pronghorn" in name or "l_e_proghorn" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_LE_BIG_GAME",
            draw_system_type="BONUS_LE_BIG_GAME",
            draw_pool="limited_entry_pronghorn",
            hunt_class="BIG_GAME_LIMITED_ENTRY_PRONGHORN",
            species="Pronghorn",
            hunt_type="Limited Entry",
            sex_type="Buck",
        )
    if "management_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_LE_BIG_GAME",
            draw_system_type="BONUS_LE_BIG_GAME",
            draw_pool="management_deer",
            hunt_class="BIG_GAME_MANAGEMENT_DEER",
            species="Deer",
            hunt_type="Management",
            sex_type="Buck",
        )
    if "cactus_deer" in name:
        return common(
            source_file=source_file,
            draw_design="BONUS_LE_BIG_GAME",
            draw_system_type="BONUS_LE_BIG_GAME",
            draw_pool="cactus_deer",
            hunt_class="BIG_GAME_CACTUS_DEER",
            species="Deer",
            hunt_type="Limited Entry",
            sex_type="Buck",
        )

    oil = {
        "o_i_l_bison": ("once_in_a_lifetime_bison", "BIG_GAME_BISON", "Bison", "Either Sex"),
        "o_i_l_bull_moose": ("once_in_a_lifetime_moose", "BIG_GAME_MOOSE", "Moose", "Bull"),
        "o_i_l_desert_bighorn_sheep": (
            "once_in_a_lifetime_desert_bighorn_sheep",
            "BIG_GAME_DESERT_BIGHORN_SHEEP",
            "Desert Bighorn Sheep",
            "Ram",
        ),
        "o_i_l_rocky_mountain_bighorn_sheep": (
            "once_in_a_lifetime_rocky_mountain_bighorn_sheep",
            "BIG_GAME_ROCKY_MTN_SHEEP",
            "Rocky Mountain Bighorn Sheep",
            "Ram",
        ),
        "o_i_l_mtn_goat": ("once_in_a_lifetime_mountain_goat", "BIG_GAME_MTN_GOAT", "Mountain Goat", "Either Sex"),
        "o_i_l_mountain_goat": (
            "once_in_a_lifetime_mountain_goat",
            "BIG_GAME_MTN_GOAT",
            "Mountain Goat",
            "Either Sex",
        ),
    }
    for token, (draw_pool, hunt_class, species, sex_type) in oil.items():
        if token in name:
            return common(
                source_file=source_file,
                draw_design="BONUS_OIL_BIG_GAME",
                draw_system_type="BONUS_OIL_BIG_GAME",
                draw_pool=draw_pool,
                hunt_class=hunt_class,
                species=species,
                hunt_type="Once-in-a-Lifetime",
                sex_type=sex_type,
            )

    preference = [
        ("youth_g_s_deer", "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "youth_general_deer", "YOUTH_DEER", "Deer", "General Season", "Buck"),
        ("g_s_buck_deer", "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "adult_general_deer", "GENERAL_SEASON_DEER", "Deer", "General Season", "Buck"),
        ("youth_d_h_deer", "PREFERENCE_DEDICATED_HUNTER_DEER", "youth_dedicated_hunter", "YOUTH_DEDICATED_HUNTER_DEER", "Deer", "General Season", "Buck"),
        ("d_h_deer", "PREFERENCE_DEDICATED_HUNTER_DEER", "dedicated_hunter", "DEDICATED_HUNTER_DEER", "Deer", "General Season", "Buck"),
        ("youth_antlerless_elk", "PREFERENCE_ANTLERLESS_ELK", "youth_antlerless_elk", "YOUTH_ANTLERLESS_ELK", "Elk", "General Season", "Antlerless"),
        ("youth_antlerless_deer", "PREFERENCE_ANTLERLESS_DEER", "youth_antlerless_deer", "YOUTH_ANTLERLESS_DEER", "Deer", "General Season", "Antlerless"),
        ("youth_antlerless_pronghorn", "PREFERENCE_DOE_PRONGHORN", "youth_doe_pronghorn", "YOUTH_ANTLERLESS_PRONGHORN", "Pronghorn", "General Season", "Doe"),
        ("antlerless_elk", "PREFERENCE_ANTLERLESS_ELK", "general_season_antlerless_elk", "ANTLERLESS_ELK", "Elk", "General Season", "Antlerless"),
        ("antlerless_deer", "PREFERENCE_ANTLERLESS_DEER", "general_season_antlerless_deer", "ANTLERLESS_DEER", "Deer", "General Season", "Antlerless"),
        ("doe_pronghorn", "PREFERENCE_DOE_PRONGHORN", "general_season_doe_pronghorn", "ANTLERLESS_PRONGHORN", "Pronghorn", "General Season", "Doe"),
        ("antlerless_pronghorn", "PREFERENCE_DOE_PRONGHORN", "general_season_doe_pronghorn", "ANTLERLESS_PRONGHORN", "Pronghorn", "General Season", "Doe"),
    ]
    for token, draw_design, draw_pool, hunt_class, species, hunt_type, sex_type in preference:
        if token in name:
            return common(
                source_file=source_file,
                draw_design=draw_design,
                draw_system_type=draw_design,
                draw_pool=draw_pool,
                hunt_class=hunt_class,
                species=species,
                hunt_type=hunt_type,
                sex_type=sex_type,
            )
    return None


def target_year(row: dict[str, str]) -> str:
    return row.get("model_target_year") or row.get("target_year") or row.get("draw_year") or ""


def repair_file(path: Path, stamp: str) -> dict[str, object]:
    backup = path.with_name(f"{path.stem}.backup_raw_filename_design_alignment_{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    changed = 0
    touched = 0
    for row in rows:
        if target_year(row) != TARGET_YEAR:
            continue
        source_file = row.get("source_file") or row.get("draw_source_file") or row.get("source_pdf") or ""
        metadata = classify_source_file(source_file)
        if not metadata:
            continue
        before = tuple(row.get(field, "") for field in metadata if field in fields)
        for field, value in metadata.items():
            if field in fields:
                row[field] = value
        after = tuple(row.get(field, "") for field in metadata if field in fields)
        touched += 1
        if after != before:
            changed += 1

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "path": str(path),
        "backup": str(backup),
        "rows": len(rows),
        "target_rows_touched": touched,
        "metadata_rows_changed": changed,
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in INPUT_FILES:
        result = repair_file(path, stamp)
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
