#!/usr/bin/env python3
"""Repair adult/youth draw-lane metadata from rebuilt bucket authority.

The official hunt code can be shared by adult and youth reserve lanes. The
score key must keep the hunt code unchanged and separate the lanes through the
source-classified draw pool/source PDF.

This script is metadata-only. It does not change hunt codes, points, applicant
counts, success counts, probabilities, permit counts, or row counts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
AUDIT_ROOT = REPO / "audits" / "youth_lane_partitioning"

METADATA_FIELDS = {
    "source_scope",
    "source_file",
    "draw_source_file",
    "source_pdf",
    "source_path",
    "draw_design",
    "draw_system_type",
    "draw_pool",
    "hunt_class",
    "hunt_draw_class",
    "species",
    "hunt_type",
    "sex_type",
}

IGNORED_SOURCE_PARTS = {
    "parent bundles",
    "parent files",
    "duplicate active sources",
    "summary pages",
    "merged source fragments",
}


@dataclass(frozen=True)
class BucketConfig:
    draw_design: str
    draw_pool: str
    hunt_class: str
    species: str
    hunt_type: str
    sex_type: str
    include_tokens: tuple[str, ...]
    exclude_tokens: tuple[str, ...] = ()
    cwmu: bool = False


BUCKETS: dict[str, BucketConfig] = {
    "ANTLERLESS_DEER": BucketConfig(
        "PREFERENCE_ANTLERLESS_DEER",
        "general_season_antlerless_deer",
        "ANTLERLESS_DEER",
        "Deer",
        "General Season",
        "Antlerless",
        ("ANTLERLESS", "DEER"),
        ("YOUTH", "CWMU", "GS", "G_S"),
    ),
    "YOUTH_ANTLERLESS_DEER": BucketConfig(
        "PREFERENCE_ANTLERLESS_DEER",
        "youth_antlerless_deer",
        "YOUTH_ANTLERLESS_DEER",
        "Deer",
        "General Season",
        "Antlerless",
        ("YOUTH", "ANTLERLESS", "DEER"),
        ("CWMU",),
    ),
    "ANTLERLESS_ELK": BucketConfig(
        "PREFERENCE_ANTLERLESS_ELK",
        "general_season_antlerless_elk",
        "ANTLERLESS_ELK",
        "Elk",
        "General Season",
        "Antlerless",
        ("ANTLERLESS", "ELK"),
        ("YOUTH", "CWMU"),
    ),
    "YOUTH_ANTLERLESS_ELK": BucketConfig(
        "PREFERENCE_ANTLERLESS_ELK",
        "youth_antlerless_elk",
        "YOUTH_ANTLERLESS_ELK",
        "Elk",
        "General Season",
        "Antlerless",
        ("YOUTH", "ANTLERLESS", "ELK"),
        ("CWMU",),
    ),
    "ANTLERLESS_PRONGHORN": BucketConfig(
        "PREFERENCE_DOE_PRONGHORN",
        "general_season_doe_pronghorn",
        "ANTLERLESS_PRONGHORN",
        "Pronghorn",
        "General Season",
        "Doe",
        ("PRONGHORN",),
        ("YOUTH", "CWMU", "BIG_GAME"),
    ),
    "YOUTH_ANTLERLESS_PRONGHORN": BucketConfig(
        "PREFERENCE_DOE_PRONGHORN",
        "youth_doe_pronghorn",
        "YOUTH_ANTLERLESS_PRONGHORN",
        "Pronghorn",
        "General Season",
        "Doe",
        ("YOUTH", "PRONGHORN"),
        ("CWMU",),
    ),
    "GENERAL_SEASON_DEER": BucketConfig(
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "adult_general_deer",
        "GENERAL_SEASON_DEER",
        "Deer",
        "General Season",
        "Buck",
        ("G", "S", "BUCK", "DEER"),
        ("YOUTH", "LIFETIME", "ANTLERLESS", "CWMU", "LE", "PLE", "CACTUS", "HAMS", "MANAGEMENT", "D_H"),
    ),
    "YOUTH_DEER": BucketConfig(
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "youth_general_deer",
        "YOUTH_GENERAL_SEASON_DEER",
        "Deer",
        "General Season",
        "Buck",
        ("YOUTH", "G", "S", "DEER"),
        ("ANTLERLESS", "CWMU", "D_H"),
    ),
    "DEDICATED_HUNTER_DEER": BucketConfig(
        "PREFERENCE_DEDICATED_HUNTER_DEER",
        "dedicated_hunter",
        "DEDICATED_HUNTER_DEER",
        "Deer",
        "General Season",
        "Buck",
        ("D_H", "DEER"),
        ("YOUTH", "CWMU"),
    ),
    "YOUTH_DEDICATED_HUNTER_DEER": BucketConfig(
        "PREFERENCE_DEDICATED_HUNTER_DEER",
        "youth_dedicated_hunter",
        "YOUTH_DEDICATED_HUNTER_DEER",
        "Deer",
        "General Season",
        "Buck",
        ("YOUTH", "D_H", "DEER"),
        ("CWMU",),
    ),
}

CWMU_BUCKETS: dict[str, BucketConfig] = {
    "ANTLERLESS_DEER": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_antlerless_deer",
        "ANTLERLESS_DEER",
        "Deer",
        "CWMU",
        "Antlerless",
        ("CWMU", "ANTLERLESS", "DEER"),
        ("YOUTH",),
        True,
    ),
    "YOUTH_ANTLERLESS_DEER": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_youth_antlerless_deer",
        "YOUTH_ANTLERLESS_DEER",
        "Deer",
        "CWMU",
        "Antlerless",
        ("CWMU", "YOUTH", "ANTLERLESS", "DEER"),
        (),
        True,
    ),
    "ANTLERLESS_ELK": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_antlerless_elk",
        "ANTLERLESS_ELK",
        "Elk",
        "CWMU",
        "Antlerless",
        ("CWMU", "ANTLERLESS", "ELK"),
        ("YOUTH",),
        True,
    ),
    "YOUTH_ANTLERLESS_ELK": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_youth_antlerless_elk",
        "YOUTH_ANTLERLESS_ELK",
        "Elk",
        "CWMU",
        "Antlerless",
        ("CWMU", "YOUTH", "ANTLERLESS", "ELK"),
        (),
        True,
    ),
    "ANTLERLESS_PRONGHORN": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_doe_pronghorn",
        "ANTLERLESS_PRONGHORN",
        "Pronghorn",
        "CWMU",
        "Doe",
        ("CWMU", "PRONGHORN"),
        ("YOUTH", "BIG_GAME"),
        True,
    ),
    "YOUTH_ANTLERLESS_PRONGHORN": BucketConfig(
        "BONUS_CWMU_BIG_GAME",
        "cwmu_youth_doe_pronghorn",
        "YOUTH_ANTLERLESS_PRONGHORN",
        "Pronghorn",
        "CWMU",
        "Doe",
        ("CWMU", "YOUTH", "PRONGHORN"),
        (),
        True,
    ),
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def compact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")


def target_year(row: dict[str, str]) -> str:
    return clean(row.get("model_target_year") or row.get("target_year") or row.get("draw_year"))


def source_year(row: dict[str, str], path: Path) -> str:
    value = clean(row.get("actual_draw_year") or row.get("source_year"))
    if value:
        return value
    match = re.search(r"draw_results_(\d{4})_for_\d{4}_", path.name)
    return match.group(1) if match else ""


def rebuilt_bucket(row: dict[str, str]) -> str:
    for token in clean(row.get("qa_notes")).split(";"):
        name, separator, value = token.strip().partition("=")
        if separator and name.strip().lower() == "rebuilt_bucket":
            return value.strip().upper()
    return ""


def row_is_cwmu(row: dict[str, str]) -> bool:
    text = " ".join(
        clean(row.get(field))
        for field in ("source_file", "draw_source_file", "source_pdf", "source_path", "draw_pool", "hunt_type", "hunt_class")
    ).lower()
    return "cwmu" in text


@lru_cache(maxsize=None)
def active_pdf_candidates(year: str) -> tuple[Path, ...]:
    folder = RAW_ROOT / year / "pdf" / "draw_odds"
    if not folder.exists():
        return ()
    candidates = []
    for pdf in folder.rglob("*.pdf"):
        parts = {part.lower() for part in pdf.parts}
        if parts & IGNORED_SOURCE_PARTS:
            continue
        candidates.append(pdf)
    return tuple(candidates)


def token_match_score(path: Path, config: BucketConfig) -> int:
    rel = compact(path.relative_to(REPO).as_posix())
    name = compact(path.name)
    if any(token not in rel for token in config.include_tokens):
        return -1
    if any(token in rel for token in config.exclude_tokens):
        return -1
    score = 0
    for token in config.include_tokens:
        if token in name:
            score += 5
        if token in rel:
            score += 1
    if config.cwmu and "CWMU" in rel:
        score += 8
    if "SPLIT_BY_HUNT_TYPE" in rel:
        score += 4
    if "DRAW_ODDS_CWMU" in rel:
        score += 4
    if path.parent.name.upper() in {"ANTLERLESS CWMU", "BIG GAME CWMU"}:
        score += 4
    return score


@lru_cache(maxsize=None)
def choose_source(year: str, config: BucketConfig) -> Path | None:
    scored = [
        (token_match_score(path, config), path)
        for path in active_pdf_candidates(year)
    ]
    scored = [(score, path) for score, path in scored if score >= 0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], len(item[1].parts), str(item[1])))
    return scored[0][1]


def metadata_for(row: dict[str, str], path: Path, csv_path: Path) -> dict[str, str] | None:
    bucket = rebuilt_bucket(row)
    if not bucket:
        return None
    configs = CWMU_BUCKETS if row_is_cwmu(row) else BUCKETS
    config = configs.get(bucket)
    if not config:
        return None
    year = source_year(row, csv_path)
    source_pdf = choose_source(year, config)
    if source_pdf is None:
        return None
    source_file = source_pdf.name
    rel_path = str(source_pdf.relative_to(REPO)).replace("/", "\\")
    return {
        "source_scope": source_file,
        "source_file": source_file,
        "draw_source_file": source_file,
        "source_pdf": source_file,
        "source_path": rel_path,
        "draw_design": config.draw_design,
        "draw_system_type": config.draw_design,
        "draw_pool": config.draw_pool,
        "hunt_class": config.hunt_class,
        "hunt_draw_class": config.hunt_class,
        "species": config.species,
        "hunt_type": config.hunt_type,
        "sex_type": config.sex_type,
    }


def needs_repair(row: dict[str, str], metadata: dict[str, str]) -> bool:
    bucket = rebuilt_bucket(row)
    expected_lane = "youth" if bucket.startswith("YOUTH_") or bucket == "YOUTH_DEER" else "adult"
    current_text = " ".join(
        clean(row.get(field))
        for field in ("source_file", "draw_source_file", "source_pdf", "source_path", "draw_pool", "hunt_class", "hunt_draw_class")
    ).lower()
    actual_lane = "youth" if "youth" in current_text else "adult"
    if expected_lane == actual_lane:
        return False
    for field, value in metadata.items():
        if clean(row.get(field)) != value:
            return True
    return False


def iter_input_files(include_long: bool) -> Iterable[Path]:
    yield from sorted(CANONICAL_DIR.glob("*canonical_yearly_draw_results.csv"))
    if include_long and LONG_FILE.exists():
        yield LONG_FILE


def repair_file(path: Path, stamp: str, apply: bool) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    changed_rows: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []

    for line_number, row in enumerate(rows, start=2):
        bucket = rebuilt_bucket(row)
        if not bucket:
            continue
        config_source = CWMU_BUCKETS if row_is_cwmu(row) else BUCKETS
        if bucket not in config_source:
            continue
        metadata = metadata_for(row, path, path)
        if metadata is None:
            unresolved.append(
                {
                    "path": str(path),
                    "line": str(line_number),
                    "source_year": source_year(row, path),
                    "target_year": target_year(row),
                    "hunt_code": clean(row.get("hunt_code")),
                    "points": clean(row.get("points")),
                    "rebuilt_bucket": bucket,
                    "current_source_file": clean(row.get("source_file")),
                    "current_draw_pool": clean(row.get("draw_pool")),
                }
            )
            continue
        if not needs_repair(row, metadata):
            continue
        changed_rows.append(
            {
                "path": str(path),
                "line": str(line_number),
                "source_year": source_year(row, path),
                "target_year": target_year(row),
                "hunt_code": clean(row.get("hunt_code")),
                "points": clean(row.get("points")),
                "rebuilt_bucket": bucket,
                "old_source_file": clean(row.get("source_file")),
                "new_source_file": metadata["source_file"],
                "old_draw_pool": clean(row.get("draw_pool")),
                "new_draw_pool": metadata["draw_pool"],
            }
        )
        for field, value in metadata.items():
            if field in fields:
                row[field] = value

    backup = ""
    if apply and changed_rows:
        backup_path = path.with_name(f"{path.stem}.backup_youth_lane_partitioning_{stamp}{path.suffix}")
        shutil.copy2(path, backup_path)
        backup = str(backup_path)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    return {
        "path": str(path),
        "rows": len(rows),
        "changed_rows": len(changed_rows),
        "unresolved_rows": len(unresolved),
        "backup": backup,
        "changed": changed_rows,
        "unresolved": unresolved,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write repairs; default is audit-only")
    parser.add_argument("--include-long", action="store_true", help="also repair draw_results_long.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = AUDIT_ROOT / f"repair_{stamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    changed: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for path in iter_input_files(args.include_long):
        result = repair_file(path, stamp, args.apply)
        summaries.append({k: v for k, v in result.items() if k not in {"changed", "unresolved"}})
        changed.extend(result["changed"])
        unresolved.extend(result["unresolved"])

    def write_csv(name: str, rows: list[dict[str, str]], fields: list[str]) -> None:
        with (audit_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    write_csv(
        "changed_rows.csv",
        changed,
        [
            "path",
            "line",
            "source_year",
            "target_year",
            "hunt_code",
            "points",
            "rebuilt_bucket",
            "old_source_file",
            "new_source_file",
            "old_draw_pool",
            "new_draw_pool",
        ],
    )
    write_csv(
        "unresolved_rows.csv",
        unresolved,
        [
            "path",
            "line",
            "source_year",
            "target_year",
            "hunt_code",
            "points",
            "rebuilt_bucket",
            "current_source_file",
            "current_draw_pool",
        ],
    )
    (audit_dir / "summary.json").write_text(
        json.dumps(
            {
                "apply": args.apply,
                "include_long": args.include_long,
                "changed_rows": len(changed),
                "unresolved_rows": len(unresolved),
                "files": summaries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"audit_dir": str(audit_dir), "changed_rows": len(changed), "unresolved_rows": len(unresolved)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
