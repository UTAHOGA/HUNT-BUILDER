#!/usr/bin/env python3
"""Repair 2020 parent-source draw design metadata to split source buckets.

This is metadata-only. It does not change hunt codes, points, applicant counts,
success counts, probabilities, permit counts, or row counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET_YEAR = "2021"
SOURCE_YEAR = "2020"
CANONICAL = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
)
LONG_FILE = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_ROOT = REPO / "audits" / "source_design_alignment" / "2020_for_2021"
RAW_BASE = r"pipeline\RAW\hunt_unit_database\2020\pdf\draw_odds"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def lower(value: object) -> str:
    return clean(value).lower()


def row_target_year(row: dict[str, str]) -> str:
    return clean(row.get("model_target_year") or row.get("target_year") or row.get("draw_year"))


def row_source_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("source_year"))


def source_path(source_file: str, *parts: str) -> str:
    return "\\".join([RAW_BASE, *parts, source_file])


def common(
    *,
    source_file: str,
    draw_design: str,
    draw_pool: str,
    hunt_class: str | None = None,
    hunt_type: str | None = None,
    species: str | None = None,
    sex_type: str | None = None,
    subdir: tuple[str, ...] = (),
) -> dict[str, str]:
    metadata = {
        "source_scope": source_file,
        "source_file": source_file,
        "draw_source_file": source_file,
        "source_pdf": source_file,
        "source_path": source_path(source_file, *subdir),
        "draw_design": draw_design,
        "draw_system_type": draw_design,
        "draw_pool": draw_pool,
    }
    if hunt_class is not None:
        metadata["hunt_class"] = hunt_class
        metadata["hunt_draw_class"] = hunt_class
    if hunt_type is not None:
        metadata["hunt_type"] = hunt_type
    if species is not None:
        metadata["species"] = species
    if sex_type is not None:
        metadata["sex_type"] = sex_type
    return metadata


def cwmu_big_game_source(row: dict[str, str]) -> str:
    species = lower(row.get("species"))
    sex = lower(row.get("sex_type"))
    if "elk" in species:
        return "2020_PERMITS=2021_MODEL__L.E._ELK_DRAW_RESULTS__CWMU_BIG_GAME_ELK.pdf"
    if "pronghorn" in species:
        return "2020_PERMITS=2021_MODEL__CWMU_BIG_GAME_PRONGHORN_BUCK.pdf"
    if "moose" in species:
        return "2020_PERMITS=2021_MODEL__CWMU_BIG_GAME_MOOSE_BULL__CWMU_DEDUPED.pdf"
    if "deer" in species or "buck" in sex:
        return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__CWMU_BIG_GAME_DEER.pdf"
    return ""


def oil_source(row: dict[str, str]) -> str:
    species = lower(row.get("species"))
    if "bison" in species:
        return "2020_PERMITS=2021_MODEL__O.I.L._BISON_DRAW_RESULTS.pdf"
    if "desert" in species:
        return "2020_PERMITS=2021_MODEL__O.I.L._DESERT_BIGHORN_SHEEP.pdf"
    if "rocky" in species:
        return "2020_PERMITS=2021_MODEL__O.I.L._ROCKY_MTN_SHEEP_DRAW_RESULTS.pdf"
    if "goat" in species:
        return "2020_PERMITS=2021_MODEL__O.I.L._MTN_GOAT_DRAW_RESULTS.pdf"
    if "moose" in species:
        return "2020_PERMITS=2021_MODEL__O.I.L._BULL_MOOSE_DRAW_RESULTS__OIL_MOOSE.pdf"
    return ""


def le_deer_source(row: dict[str, str]) -> str:
    text = " ".join(lower(row.get(field)) for field in ("hunt_class", "hunt_type", "hunt_name", "raw_hunt_name"))
    if "cactus" in text:
        return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__CACTUS_DEER.pdf"
    if "hams" in text:
        return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__HAMS_DEER.pdf"
    if "management" in text:
        return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__MANAGEMENT_DEER.pdf"
    if "premium" in text:
        return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__PLE_DEER.pdf"
    return "2020_PERMITS=2021_MODEL__L.E._DEER_DRAW_RESULTS__LE_DEER.pdf"


def metadata_for(row: dict[str, str]) -> dict[str, str] | None:
    if row_target_year(row) != TARGET_YEAR or row_source_year(row) != SOURCE_YEAR:
        return None

    source_file = clean(row.get("source_file"))
    species = clean(row.get("species"))
    hunt_type = clean(row.get("hunt_type"))
    sex_type = clean(row.get("sex_type"))
    hunt_class = clean(row.get("hunt_class") or row.get("hunt_draw_class"))
    text = " ".join(lower(row.get(field)) for field in ("hunt_class", "hunt_type", "hunt_name", "raw_hunt_name", "source_file"))
    is_cwmu = "cwmu" in text

    if source_file == "20_bg-odds(2).pdf":
        if "cwmu" in text:
            source = cwmu_big_game_source(row)
            if not source:
                return None
            return common(
                source_file=source,
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="max_weighted_split",
                subdir=("CWMU", "BIG GAME CWMU"),
            )
        if "once-in-a-lifetime" in text or species in {"Moose", "Bison", "Mountain Goat", "Desert Bighorn Sheep", "Rocky Mountain Bighorn Sheep"}:
            source = oil_source(row)
            if not source:
                return None
            subdir = ("Split By Hunt Type", "OIL_MOOSE") if "OIL_MOOSE" in source else ()
            return common(source_file=source, draw_design="BONUS_OIL_BIG_GAME", draw_pool="max_weighted_split", subdir=subdir)
        if species == "Elk":
            return common(
                source_file="2020_PERMITS=2021_MODEL__L.E._ELK_DRAW_RESULTS__LE_ELK.pdf",
                draw_design="BONUS_LE_BIG_GAME",
                draw_pool="limited_entry_elk",
                subdir=("Split By Hunt Type", "LE_ELK"),
            )
        if species == "Pronghorn":
            return common(
                source_file="2020_PERMITS=2021_MODEL__L.E._PRONGHORN_DRAW_RESULTS__LE_PRONGHORN.pdf",
                draw_design="BONUS_LE_BIG_GAME",
                draw_pool="limited_entry_pronghorn",
                subdir=("Split By Hunt Type", "LE_PRONGHORN"),
            )
        if species == "Deer":
            source = le_deer_source(row)
            folder = source.rsplit("__", 1)[-1].replace(".pdf", "")
            return common(
                source_file=source,
                draw_design="BONUS_LE_BIG_GAME",
                draw_pool="limited_entry_deer",
                subdir=("Split By Hunt Type", folder),
            )

    if source_file == "20_antlerless_drawing_odds_report(1).pdf" and is_cwmu:
        if species == "Deer":
            return common(
                source_file="2020_PERMITS=2021_MODEL__CWMU_ANTLERLESS_DEER_DRAW_RESULTS.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_antlerless_deer",
                hunt_class="ANTLERLESS_DEER",
                hunt_type="CWMU",
                species="Deer",
                sex_type="Antlerless",
                subdir=("CWMU", "ANTLERLESS CWMU"),
            )
        if species == "Elk":
            return common(
                source_file="2020_PERMITS=2021_MODEL__ANTLERLESS_ELK_DRAW_RESULTS__CWMU_ANTLERLESS_ELK__CWMU_UNIQUE_PAGES.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_antlerless_elk",
                hunt_class="ANTLERLESS_ELK",
                hunt_type="CWMU",
                species="Elk",
                sex_type="Antlerless",
                subdir=("CWMU", "ANTLERLESS CWMU"),
            )
        if species == "Pronghorn":
            return common(
                source_file="2020_PERMITS=2021_MODEL__CWMU_DOE_PRONGHORN_DRAW_RESULTS.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_doe_pronghorn",
                hunt_class="ANTLERLESS_PRONGHORN",
                hunt_type="CWMU",
                species="Pronghorn",
                sex_type="Doe",
                subdir=("CWMU", "ANTLERLESS CWMU"),
            )

    if source_file == "20_youth_antlerless_drawing_odds_report(1).pdf" and is_cwmu:
        if species == "Deer":
            return common(
                source_file="2020_PERMITS=2021_MODEL__CWMU_YOUTH_ANTLERLESS_DEER_DRAW_RESULTS__CWMU_DEDUPED.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_youth_antlerless_deer",
                hunt_class="YOUTH_ANTLERLESS_DEER",
                hunt_type="CWMU",
                species="Deer",
                sex_type="Antlerless",
                subdir=("CWMU", "ANTLERLESS CWMU"),
            )
        if species == "Elk":
            return common(
                source_file="2020_PERMITS=2021_MODEL__CWMU_YOUTH_ANTLERLESS_ELK_DRAW_RESULTS__CWMU_YOUTH_ANTLERLESS_ELK__CWMU_DEDUPED.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_youth_antlerless_elk",
                hunt_class="YOUTH_ANTLERLESS_ELK",
                hunt_type="CWMU",
                species="Elk",
                sex_type="Antlerless",
                subdir=("CWMU", "ANTLERLESS CWMU", "Split By Hunt Type", "CWMU_YOUTH_ANTLERLESS_ELK"),
            )
        if species == "Pronghorn":
            return common(
                source_file="2020_PERMITS=2021_MODEL__CWMU_YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS__CWMU_DEDUPED.pdf",
                draw_design="BONUS_CWMU_BIG_GAME",
                draw_pool="cwmu_youth_doe_pronghorn",
                hunt_class="YOUTH_ANTLERLESS_PRONGHORN",
                hunt_type="CWMU",
                species="Pronghorn",
                sex_type="Doe",
                subdir=("CWMU", "ANTLERLESS CWMU"),
            )

    if source_file == "20_youth_deer(1).pdf":
        return common(
            source_file="2020_PERMITS=2021_MODEL__YOUTH_G.S._DEER_DRAW_RESULTS.pdf",
            draw_design="PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            draw_pool="youth_general_deer",
            hunt_class="YOUTH_GENERAL_SEASON_DEER",
            hunt_type="General Season",
            species="Deer",
            sex_type="Buck",
        )

    return None


def repair_file(path: Path, stamp: str, apply: bool) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    changed = []
    for line_number, row in enumerate(rows, start=2):
        metadata = metadata_for(row)
        if metadata is None:
            continue
        before = {field: clean(row.get(field)) for field in metadata if field in fields}
        if all(before[field] == value for field, value in metadata.items() if field in fields):
            continue
        changed.append(
            {
                "path": str(path),
                "line": str(line_number),
                "hunt_code": clean(row.get("hunt_code")),
                "points": clean(row.get("points")),
                "old_source_file": clean(row.get("source_file")),
                "new_source_file": metadata["source_file"],
                "old_draw_system_type": clean(row.get("draw_system_type") or row.get("draw_design")),
                "new_draw_system_type": metadata["draw_system_type"],
                "old_draw_pool": clean(row.get("draw_pool")),
                "new_draw_pool": metadata["draw_pool"],
            }
        )
        for field, value in metadata.items():
            if field in fields:
                row[field] = value

    backup = ""
    if apply and changed:
        backup_path = path.with_name(f"{path.stem}.backup_2020_parent_source_design_alignment_{stamp}{path.suffix}")
        shutil.copy2(path, backup_path)
        backup = str(backup_path)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    return {"path": str(path), "rows": len(rows), "changed_rows": len(changed), "backup": backup, "changed": changed}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-long", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = AUDIT_ROOT / f"repair_{stamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)
    files = [CANONICAL]
    if args.include_long:
        files.append(LONG_FILE)

    summaries = []
    changed = []
    for path in files:
        result = repair_file(path, stamp, args.apply)
        summaries.append({k: v for k, v in result.items() if k != "changed"})
        changed.extend(result["changed"])

    with (audit_dir / "changed_rows.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "path",
            "line",
            "hunt_code",
            "points",
            "old_source_file",
            "new_source_file",
            "old_draw_system_type",
            "new_draw_system_type",
            "old_draw_pool",
            "new_draw_pool",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(changed)
    (audit_dir / "summary.json").write_text(
        json.dumps(
            {"apply": args.apply, "include_long": args.include_long, "changed_rows": len(changed), "files": summaries},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"audit_dir": str(audit_dir), "changed_rows": len(changed)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
