#!/usr/bin/env python3
"""Score full-engine predictions with a draw-line-aware join.

This is an audit scorer. It does not mutate production feeders or truth files.
It first joins predictions to the actual ladder structurally, then classifies
each point relative to the PDF-derived applicant ladder and mixed-success draw
line before deciding whether the row is eligible for MAE/RMSE scoring.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_HUNT_CODE_CROSSWALK_DIR = REPO / "data_truth" / "crosswalk_truth" / "normalized"
DEFAULT_HUNT_CODE_CROSSWALK_FILES = (
    DEFAULT_HUNT_CODE_CROSSWALK_DIR / "current_to_historical_hunt_code_crosswalk_2026.csv",
    DEFAULT_HUNT_CODE_CROSSWALK_DIR / "black_bear_BR_2024_2025_2026_crosswalk.csv",
    DEFAULT_HUNT_CODE_CROSSWALK_DIR / "hunt_code_crosswalk_authority_2020_2026.csv",
)
PREDICTION_PROBABILITY_FIELDS = (
    "p_draw_mean",
    "p_draw",
    "p_preference_draw",
    "p_sportsman_draw",
    "p_availability",
)
POINT_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "sportsman_total",
    "sportsman_total_draw_result",
}
NON_PROBABILITY_DRAW_DESIGNS = {"REFERENCE_ONLY"}
NON_PROBABILITY_DRAW_POOLS = {
    "reference_only",
    "lifetime_general_deer",
    "preference_point",
}

DRAW_DESIGN_ALIASES = {
    "MAX/WEIGHTED SPLIT": "MAX_WEIGHTED_SPLIT",
    "MAX_WEIGHTED_SPLIT": "MAX_WEIGHTED_SPLIT",
    "MAX WEIGHTED SPLIT": "MAX_WEIGHTED_SPLIT",
    "PREFERENCE": "PREFERENCE",
    "RANDOM": "RANDOM",
    "SPORTSMAN RANDOM ONLY": "SPORTSMAN_RANDOM_ONLY",
    "SPORTSMAN_RANDOM_ONLY": "SPORTSMAN_RANDOM_ONLY",
    "CAPPED PERMITS": "CAPPED_PERMITS",
    "CAPPED_PERMITS": "CAPPED_PERMITS",
}

DRAW_POOL_ALIASES = {
    "": "",
    "STANDARD": "",
    "MAX_WEIGHTED_SPLIT": "max_weighted_split",
    "MAX WEIGHTED SPLIT": "max_weighted_split",
    "BLACK_BEAR": "bear_draw",
    "BLACK BEAR": "bear_draw",
    "BEAR_DRAW": "bear_draw",
    "BEAR DRAW": "bear_draw",
    "ADULT_GENERAL_DEER": "preference_general_season_buck_deer",
    "ADULT GENERAL DEER": "preference_general_season_buck_deer",
    "GENERAL_SEASON_ANTLERLESS_DEER": "preference_antlerless_deer",
    "GENERAL SEASON ANTLERLESS DEER": "preference_antlerless_deer",
    "GENERAL_SEASON_ANTLERLESS_ELK": "preference_antlerless_elk",
    "GENERAL SEASON ANTLERLESS ELK": "preference_antlerless_elk",
    "GENERAL_SEASON_DOE_PRONGHORN": "preference_doe_pronghorn",
    "GENERAL SEASON DOE PRONGHORN": "preference_doe_pronghorn",
    "DEDICATED_HUNTER": "preference_dedicated_hunter_deer",
    "DEDICATED HUNTER": "preference_dedicated_hunter_deer",
    "SPORTSMAN": "sportsman_permit",
    "SPORTSMAN_RANDOM_ONLY": "sportsman_permit",
    "SPORTSMAN RANDOM ONLY": "sportsman_permit",
    "YOUTH": "youth_general_any_bull_elk",
    "YOUTH_GENERAL_ANY_BULL_ELK": "youth_general_any_bull_elk",
    "YOUTH GENERAL ANY BULL ELK": "youth_general_any_bull_elk",
}

BASE_SCORING_HUNT_CODE_ALIASES = {
    # 2017 sportsman predictions use internal/legacy placeholders for rows
    # that later canonical truth stores under the zero-padded sportsman code.
    "RS0001": "RS1000",
    "TK0001": "TK1000",
}

YEAR_SCOPED_SCORING_HUNT_CODE_ALIASES = {
    # 2017 sportsman deer printed as DB1045 in the 2017 Sportsman Odds Report.
    # Later canonical truth uses DB0007 for Sportsman Deer, while DB1045 is also
    # a real limited-entry deer code in other years. Keep this alias scoped.
    ("2017", "2018"): {
        "DB0007": "DB1045",
    },
}


@dataclass(frozen=True)
class HuntCodeResolution:
    join_code: str
    original_code: str
    current_code: str = ""
    historical_code: str = ""
    status: str = ""
    confidence: str = ""
    source_file: str = ""


HUNT_CODE_CROSSWALK: dict[str, HuntCodeResolution] = {}
ACTIVE_SCORING_HUNT_CODE_ALIASES: dict[str, str] = dict(BASE_SCORING_HUNT_CODE_ALIASES)


@dataclass
class ActualPoint:
    family: str
    hunt_code: str
    original_hunt_code: str
    hunt_code_crosswalk_status: str
    hunt_code_crosswalk_confidence: str
    residency: str
    points: str
    draw_pool: str
    actual_probability: float | None
    actual_probability_field: str
    actual_eligible_applicants: float
    resident_eligible_applicants: float
    nonresident_eligible_applicants: float
    actual_drawn: float
    actual_unsuccessful: float
    hunt_name: str
    species: str
    draw_design: str
    draw_design_key: str
    record_type: str
    actual_draw_year: str
    model_target_year: str


@dataclass
class Ladder:
    family: str
    draw_design_key: str
    hunt_code: str
    residency: str
    original_hunt_codes: set[str] = field(default_factory=set)
    draw_pool: str = ""
    points: dict[int, ActualPoint] = field(default_factory=dict)
    non_numeric_points: dict[str, ActualPoint] = field(default_factory=dict)

    @property
    def numeric_points(self) -> list[int]:
        return sorted(self.points)

    @property
    def applicant_points(self) -> list[int]:
        return sorted(
            [point for point, row in self.points.items() if row.actual_eligible_applicants > 0],
            reverse=True,
        )

    @property
    def top_applicant_point(self) -> int | None:
        points = self.applicant_points
        return points[0] if points else None

    @property
    def guaranteed_stack_points(self) -> list[int]:
        stack: list[int] = []
        for point in self.applicant_points:
            row = self.points[point]
            if is_guaranteed(row):
                stack.append(point)
                continue
            break
        return stack

    @property
    def lowest_guaranteed_stack_point(self) -> int | None:
        stack = self.guaranteed_stack_points
        return min(stack) if stack else None

    @property
    def mixed_cutoff_point(self) -> int | None:
        for point in self.applicant_points:
            row = self.points[point]
            if row.actual_unsuccessful > 0:
                return point
        return None


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_code(value: Any) -> str:
    return clean(value).upper()


def crosswalk_status_is_usable(status: str, confidence: str) -> bool:
    status_text = clean(status).upper()
    confidence_text = clean(confidence).upper()
    if confidence_text and confidence_text not in {"HIGH", "LOCKED", "APPROVED"}:
        return False
    return status_text in {
        "HISTORICAL_CODE_RECODED_TO_CURRENT",
        "HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED",
        "EXACT_CODE_CURRENT",
    }


def split_crosswalk_codes(value: Any) -> list[str]:
    codes: list[str] = []
    for part in re.split(r"[|;,]", clean(value)):
        code = norm_code(part)
        if code and code not in codes:
            codes.append(code)
    return codes


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    output: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        output.append(path)
    return output


def crosswalk_files_from_dirs(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists() or not path.is_dir():
            continue
        files.extend(sorted(path.glob("*.csv")))
    return files


def current_to_historical_status_is_usable(row: Mapping[str, Any]) -> bool:
    confidence = clean(row.get("mapping_confidence")).upper()
    if confidence not in {"HIGH", "LOCKED", "APPROVED"}:
        return False
    if not norm_code(row.get("current_hunt_code")) or not split_crosswalk_codes(row.get("historical_hunt_code")):
        return False
    recommended = clean(row.get("recommended_model_behavior")).upper()
    relationship = clean(row.get("relationship_type")).upper()
    status = clean(row.get("crosswalk_status")).upper()
    if recommended == "USE_EXACT_HUNT_CODE_HISTORY":
        return True
    if relationship in {
        "EXACT_CODE_HISTORY",
        "PARALLEL_CONSERVATION_TO_PUBLIC_OIAL_2026",
        "HISTORICAL_CODE_RECODED_TO_CURRENT",
        "HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED",
    }:
        return True
    return status.startswith("PROMOTED_") and "REFERENCE" not in status


def authority_crosswalk_status_is_usable(row: Mapping[str, Any]) -> bool:
    confidence = clean(row.get("source_confidence")).upper()
    if confidence and confidence not in {"HIGH", "LOCKED", "APPROVED", "MEDIUM"}:
        return False
    action = clean(row.get("crosswalk_action")).upper()
    if not action or action.endswith("_EXCLUSION"):
        return False
    if not norm_code(row.get("current_hunt_code")):
        return False
    return True


def add_hunt_code_resolution(
    mapping: dict[str, HuntCodeResolution],
    alias_code: str,
    join_code: str,
    *,
    current_code: str,
    historical_code: str,
    status: str,
    confidence: str,
    source_file: Path,
) -> None:
    alias = norm_code(alias_code)
    join = norm_code(join_code)
    if not alias or not join:
        return
    existing = mapping.get(alias)
    resolution = HuntCodeResolution(
        join_code=join,
        original_code=alias,
        current_code=norm_code(current_code),
        historical_code=norm_code(historical_code),
        status=clean(status),
        confidence=clean(confidence),
        source_file=rel(source_file),
    )
    if existing is None or existing.status == "EXACT_CODE_CURRENT":
        mapping[alias] = resolution


def load_hunt_code_crosswalk(paths: Iterable[Path]) -> dict[str, HuntCodeResolution]:
    mapping: dict[str, HuntCodeResolution] = {}
    for path in paths:
        if not path.exists():
            continue
        header, rows = read_csv(path)
        header_set = set(header)
        if {"historical_2025_code", "current_2026_code", "mapping_status"}.issubset(header_set):
            for row in rows:
                status = clean(row.get("mapping_status"))
                confidence = clean(row.get("mapping_confidence"))
                if not crosswalk_status_is_usable(status, confidence):
                    continue
                current_code = norm_code(row.get("current_2026_code"))
                historical_codes = [
                    norm_code(row.get("historical_2025_code")),
                    norm_code(row.get("historical_2024_code")),
                ]
                if not current_code:
                    continue
                add_hunt_code_resolution(
                    mapping,
                    current_code,
                    current_code,
                    current_code=current_code,
                    historical_code=next((code for code in historical_codes if code), current_code),
                    status=status,
                    confidence=confidence,
                    source_file=path,
                )
                for historical_code in historical_codes:
                    if not historical_code:
                        continue
                    add_hunt_code_resolution(
                        mapping,
                        historical_code,
                        current_code,
                        current_code=current_code,
                        historical_code=historical_code,
                        status=status,
                        confidence=confidence,
                        source_file=path,
                    )
        elif {"current_hunt_code", "historical_hunt_code", "mapping_confidence"}.issubset(header_set):
            for row in rows:
                if not current_to_historical_status_is_usable(row):
                    continue
                current_code = norm_code(row.get("current_hunt_code"))
                historical_codes = split_crosswalk_codes(row.get("historical_hunt_code"))
                status = clean(row.get("relationship_type") or row.get("crosswalk_status"))
                confidence = clean(row.get("mapping_confidence"))
                add_hunt_code_resolution(
                    mapping,
                    current_code,
                    current_code,
                    current_code=current_code,
                    historical_code=historical_codes[0] if historical_codes else current_code,
                    status=status,
                    confidence=confidence,
                    source_file=path,
                )
                for historical_code in historical_codes:
                    add_hunt_code_resolution(
                        mapping,
                        historical_code,
                        current_code,
                        current_code=current_code,
                        historical_code=historical_code,
                        status=status,
                        confidence=confidence,
                        source_file=path,
                    )
        elif {"current_2026_code", "engine_history_code"}.issubset(header_set):
            for row in rows:
                current_code = norm_code(row.get("current_2026_code"))
                historical_code = norm_code(row.get("engine_history_code"))
                if not current_code or not historical_code:
                    continue
                add_hunt_code_resolution(
                    mapping,
                    historical_code,
                    current_code,
                    current_code=current_code,
                    historical_code=historical_code,
                    status=clean(row.get("engine_action")) or "ALIAS_TO_HISTORICAL_CODE",
                    confidence=clean(row.get("mapping_confidence")) or "HIGH",
                    source_file=path,
                )
                add_hunt_code_resolution(
                    mapping,
                    current_code,
                    current_code,
                    current_code=current_code,
                    historical_code=historical_code,
                    status=clean(row.get("engine_action")) or "ALIAS_TO_HISTORICAL_CODE",
                    confidence=clean(row.get("mapping_confidence")) or "HIGH",
                    source_file=path,
                )
        elif {"hunt_code", "current_hunt_code", "crosswalk_action", "source_confidence"}.issubset(header_set):
            for row in rows:
                if not authority_crosswalk_status_is_usable(row):
                    continue
                current_code = norm_code(row.get("current_hunt_code"))
                historical_codes = split_crosswalk_codes(row.get("historical_hunt_code"))
                source_code = norm_code(row.get("hunt_code"))
                if source_code and source_code != current_code:
                    historical_codes.append(source_code)
                historical_codes = list(dict.fromkeys(code for code in historical_codes if code))
                status = clean(row.get("crosswalk_action"))
                confidence = clean(row.get("source_confidence"))
                add_hunt_code_resolution(
                    mapping,
                    current_code,
                    current_code,
                    current_code=current_code,
                    historical_code=historical_codes[0] if historical_codes else current_code,
                    status=status,
                    confidence=confidence,
                    source_file=path,
                )
                for historical_code in historical_codes:
                    add_hunt_code_resolution(
                        mapping,
                        historical_code,
                        current_code,
                        current_code=current_code,
                        historical_code=historical_code,
                        status=status,
                        confidence=confidence,
                        source_file=path,
                    )
    return mapping


def resolve_hunt_code(value: Any) -> HuntCodeResolution:
    original = norm_code(value)
    if not original:
        return HuntCodeResolution(join_code="", original_code="")
    if original in ACTIVE_SCORING_HUNT_CODE_ALIASES:
        return HuntCodeResolution(
            join_code=ACTIVE_SCORING_HUNT_CODE_ALIASES[original],
            original_code=original,
            current_code=ACTIVE_SCORING_HUNT_CODE_ALIASES[original],
            historical_code=original,
            status="YEAR_SCOPED_SCORING_ALIAS_FROM_OFFICIAL_ODDS_PDF",
            confidence="HIGH",
            source_file="pipeline/RAW/hunt_unit_database/2017/pdf/draw_odds/2017_sportsman_odds.pdf",
        )
    return HUNT_CODE_CROSSWALK.get(original) or HuntCodeResolution(join_code=original, original_code=original)


def norm_residency(value: Any) -> str:
    text = clean(value).lower().replace("-", " ").replace("_", " ")
    if text in {"resident", "res", "r"}:
        return "Resident"
    if text in {"nonresident", "non resident", "nonres", "nr"}:
        return "Nonresident"
    if text in {"all", "both", "total"}:
        return "All"
    return clean(value)


def prediction_residency(row: Mapping[str, Any]) -> str:
    explicit = norm_residency(row.get("residency"))
    if explicit:
        return explicit
    if clean(row.get("metric_scope")).lower() == "total":
        return "All"
    family = family_from_prediction(row)
    draw_pool = prediction_draw_pool(row, family)
    draw_design = prediction_draw_design(row, family)
    if draw_pool == "max_weighted_split" or draw_design == "MAX_WEIGHTED_SPLIT":
        return "All"
    return ""


def norm_points(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    if text.upper() == "TOTAL":
        return "TOTAL"
    try:
        parsed = float(text)
    except ValueError:
        return text
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def norm_draw_design(value: Any) -> str:
    text = " ".join(clean(value).upper().replace("-", " ").replace("/", "/").split())
    if not text:
        return ""
    return DRAW_DESIGN_ALIASES.get(text, text.replace(" ", "_"))


def norm_draw_pool(value: Any) -> str:
    text = clean(value).upper().replace("-", " ").replace("/", " ")
    text = " ".join(text.split())
    if text in DRAW_POOL_ALIASES:
        return DRAW_POOL_ALIASES[text]
    return text.lower().replace(" ", "_")


def prediction_draw_design(row: Mapping[str, Any], family: str) -> str:
    draw_system_type = clean(row.get("draw_system_type")).upper()
    draw_pool = norm_draw_pool(row.get("draw_pool"))
    if draw_pool == "bonus_cwmu_big_game":
        return "BONUS_CWMU_BIG_GAME"
    if draw_system_type == "BEAR_DRAW":
        return "BEAR_DRAW"
    explicit = norm_draw_design(row.get("draw_design"))
    if explicit:
        return explicit
    explicit_system = norm_draw_design(draw_system_type)
    if explicit_system:
        return explicit_system
    family_design = {
        "preference_general_deer": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "dedicated_hunter": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "preference_antlerless_deer": "PREFERENCE_ANTLERLESS_DEER",
        "preference_antlerless_elk": "PREFERENCE_ANTLERLESS_ELK",
        "preference_doe_pronghorn": "PREFERENCE_DOE_PRONGHORN",
        "bonus_le_big_game": "MAX_WEIGHTED_SPLIT",
        "bonus_ple_big_game": "MAX_WEIGHTED_SPLIT",
        "bonus_oil_big_game": "MAX_WEIGHTED_SPLIT",
        "bonus_bear": "BEAR_DRAW",
        "sportsman": "SPORTSMAN_PERMIT",
    }.get(family)
    if family_design:
        return family_design
    if family == "youth_draw" or "YOUTH" in draw_system_type:
        return "YOUTH_GENERAL_ANY_BULL_ELK"
    if family.startswith("preference_") or family == "dedicated_hunter":
        return "PREFERENCE"
    if family in {"bonus_bear", "bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}:
        return "MAX_WEIGHTED_SPLIT"
    return ""


def prediction_draw_pool(row: Mapping[str, Any], family: str) -> str:
    explicit = norm_draw_pool(row.get("draw_pool"))
    if explicit:
        return explicit
    family_pool = {
        "preference_general_deer": "preference_general_season_buck_deer",
        "dedicated_hunter": "preference_dedicated_hunter_deer",
        "preference_antlerless_deer": "preference_antlerless_deer",
        "preference_antlerless_elk": "preference_antlerless_elk",
        "preference_doe_pronghorn": "preference_doe_pronghorn",
        "bonus_bear": "bear_draw",
        "bonus_le_big_game": "bonus_le_big_game",
        "bonus_ple_big_game": "bonus_ple_big_game",
        "bonus_oil_big_game": "bonus_oil_big_game",
        "bonus_turkey": "bonus_turkey",
        "cougar": "cougar_license_based",
        "sportsman": "sportsman_permit",
        "youth_draw": "youth_general_any_bull_elk",
    }.get(family)
    if family_pool:
        return family_pool
    draw_system_type = clean(row.get("draw_system_type")).upper()
    if "SPORTSMAN" in draw_system_type:
        return "sportsman_permit"
    if "YOUTH_GENERAL_ANY_BULL_ELK" in draw_system_type:
        return "youth_general_any_bull_elk"
    if "BEAR" in draw_system_type:
        return "bear_draw"
    return explicit


def point_int(value: Any) -> int | None:
    text = norm_points(value)
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def parse_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def bounded_probability(value: Any, field: str = "") -> float | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    if "%" in clean(value) or "pct" in field.lower() or "percent" in field.lower() or parsed > 1.0:
        parsed /= 100.0
    return min(max(parsed, 0.0), 1.0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        fieldnames = fieldnames or ["no_rows"]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def family_from_prediction(row: Mapping[str, Any]) -> str:
    family = clean(row.get("family"))
    if family:
        return family
    draw_system_type = clean(row.get("draw_system_type")).upper()
    hunt_code = norm_code(row.get("hunt_code"))
    draw_pool = clean(row.get("draw_pool")).lower()
    if draw_system_type == "YOUTH_GENERAL_ANY_BULL_ELK" or draw_pool == "youth":
        return "youth_draw"
    if "BEAR" in draw_system_type or hunt_code.startswith("BR"):
        return "bonus_bear"
    return ""


def family_from_actual(row: Mapping[str, Any]) -> str:
    record_type = clean(row.get("record_type") or row.get("row_type")).lower()
    hunt_code = norm_code(row.get("hunt_code"))
    draw_system_type = clean(row.get("draw_system_type")).upper()
    draw_design = clean(row.get("draw_design")).upper()
    draw_pool = clean(row.get("draw_pool")).lower()
    source_text = " ".join(
        clean(row.get(field))
        for field in (
            "source_scope",
            "source_namespace",
            "hunt_draw_class",
            "hunt_type",
            "hunt_class",
            "draw_design",
        )
    ).upper()
    species = clean(row.get("species")).lower()
    if record_type.startswith("sportsman") or "SPORTSMAN" in draw_system_type or "SPORTSMAN" in source_text:
        return "sportsman"
    if draw_design == "YOUTH_GENERAL_ANY_BULL_ELK" or draw_system_type == "YOUTH_GENERAL_ANY_BULL_ELK" or ("YOUTH" in source_text and hunt_code.startswith("EB")):
        return "youth_draw"
    if draw_design in {"BEAR_DRAW", "BONUS_BEAR"} or "BEAR" in draw_system_type or hunt_code.startswith("BR") or species == "black bear" or draw_pool in {"bear_draw", "black_bear"}:
        return "bonus_bear"
    if draw_design == "BONUS_LE_BIG_GAME" or draw_system_type == "BONUS_LE_BIG_GAME":
        return "bonus_le_big_game"
    if draw_design == "BONUS_PLE_BIG_GAME" or draw_system_type == "BONUS_PLE_BIG_GAME":
        return "bonus_ple_big_game"
    if draw_design == "BONUS_OIL_BIG_GAME" or draw_system_type == "BONUS_OIL_BIG_GAME":
        return "bonus_oil_big_game"
    if draw_design == "BONUS_TURKEY" or draw_system_type == "BONUS_TURKEY":
        return "bonus_turkey"
    if draw_design == "COUGAR_LICENSE_BASED" or draw_system_type == "COUGAR_LICENSE_BASED":
        return "cougar"
    if "DEDICATED" in source_text or hunt_code.startswith("DB17"):
        return "dedicated_hunter"
    if draw_design == "PREFERENCE_GENERAL_SEASON_BUCK_DEER" or hunt_code.startswith(("DB15", "DB16")) or "GENERAL_SEASON_BUCK_DEER" in draw_system_type or "GENERAL_SEASON_BUCK_DEER" in source_text:
        return "preference_general_deer"
    if draw_design == "PREFERENCE_ANTLERLESS_DEER" or hunt_code.startswith("DA") or "PREFERENCE_ANTLERLESS_DEER" in draw_system_type:
        return "preference_antlerless_deer"
    if draw_design == "PREFERENCE_ANTLERLESS_ELK" or hunt_code.startswith("EA") or "PREFERENCE_ANTLERLESS_ELK" in draw_system_type:
        return "preference_antlerless_elk"
    if draw_design == "PREFERENCE_DOE_PRONGHORN" or hunt_code.startswith("PD") or "PREFERENCE_DOE_PRONGHORN" in draw_system_type:
        return "preference_doe_pronghorn"
    return ""


def actual_residencies(row: Mapping[str, Any], family: str) -> list[str]:
    if family == "sportsman":
        return ["Resident"]
    explicit = norm_residency(row.get("residency"))
    if explicit in {"Resident", "Nonresident", "All"}:
        return [explicit]
    metric_scope = clean(row.get("metric_scope")).lower()
    if family != "sportsman" and metric_scope == "total":
        return ["All"]
    residencies: list[str] = []
    if clean(row.get("resident_eligible_applicants")) != "" or clean(row.get("resident_p_draw")) != "" or family == "sportsman":
        residencies.append("Resident")
    if clean(row.get("nonresident_eligible_applicants")) != "" or clean(row.get("nonresident_p_draw")) != "":
        residencies.append("Nonresident")
    if not residencies and (clean(row.get("total_eligible_applicants")) != "" or clean(row.get("total_p_draw")) != ""):
        residencies.append("All")
    return residencies


def first_number(row: Mapping[str, Any], *fields: str) -> float | None:
    for field in fields:
        value = parse_float(row.get(field))
        if value is not None:
            return value
    return None


def actual_probability_and_counts(row: Mapping[str, Any], residency: str) -> tuple[float | None, str, float, float, float]:
    prefix = {"Resident": "resident", "Nonresident": "nonresident", "All": "total"}.get(residency, "")
    applicants = parse_float(row.get(f"{prefix}_eligible_applicants")) if prefix else None
    if applicants is None:
        applicants = first_number(row, "applicants_numeric", "eligible_applicants", "total_eligible_applicants") or 0.0

    probability_fields: list[str] = []
    if prefix:
        probability_fields.extend([f"{prefix}_p_draw", f"{prefix}_p_draw_percent"])
    probability_fields.extend(["actual_p", "p_draw", "p_draw_percent", "total_p_draw", "total_p_draw_percent"])

    probability = None
    probability_field = ""
    for field in probability_fields:
        if field not in row:
            continue
        probability = bounded_probability(row.get(field), field)
        if probability is not None:
            probability_field = field
            break

    drawn = parse_float(row.get(f"{prefix}_total_permits")) if prefix else None
    if drawn is None:
        drawn = first_number(row, "successful_numeric", "successful_applicants", "total_permits")
    if drawn is None and probability is not None:
        drawn = probability * applicants
    drawn = drawn or 0.0
    unsuccessful = max(applicants - drawn, 0.0)
    return probability, probability_field, applicants, drawn, unsuccessful


def actual_points_from_row(row: Mapping[str, Any]) -> list[ActualPoint]:
    if clean(row.get("scoring_allowed")).lower() in {"false", "0", "no"}:
        return []
    record_type = clean(row.get("record_type") or row.get("row_type")).lower()
    if record_type and record_type not in POINT_RECORD_TYPES:
        return []
    family = family_from_actual(row)
    hunt_code_resolution = resolve_hunt_code(row.get("hunt_code"))
    hunt_code = hunt_code_resolution.join_code
    if not family or not hunt_code:
        return []
    draw_design_key = norm_draw_design(row.get("draw_design"))
    draw_pool = norm_draw_pool(row.get("draw_pool"))
    if draw_design_key in NON_PROBABILITY_DRAW_DESIGNS or draw_pool in NON_PROBABILITY_DRAW_POOLS:
        return []
    points = norm_points(row.get("points"))
    if family == "sportsman":
        # Sportsman is strictly random and has no bonus/preference point key.
        points = ""
    elif not points:
        points = ""
    if (not points and family != "sportsman") or (points == "TOTAL" and family != "sportsman"):
        return []
    output: list[ActualPoint] = []
    resident_applicants = parse_float(row.get("resident_eligible_applicants")) or 0.0
    nonresident_applicants = parse_float(row.get("nonresident_eligible_applicants")) or 0.0
    for residency in actual_residencies(row, family):
        probability, probability_field, applicants, drawn, unsuccessful = actual_probability_and_counts(row, residency)
        output.append(
            ActualPoint(
                family=family,
                hunt_code=hunt_code,
                original_hunt_code=hunt_code_resolution.original_code,
                hunt_code_crosswalk_status=hunt_code_resolution.status,
                hunt_code_crosswalk_confidence=hunt_code_resolution.confidence,
                residency=residency,
                points=points,
                draw_pool=draw_pool,
                actual_probability=probability,
                actual_probability_field=probability_field,
                actual_eligible_applicants=applicants,
                resident_eligible_applicants=resident_applicants,
                nonresident_eligible_applicants=nonresident_applicants,
                actual_drawn=drawn,
                actual_unsuccessful=unsuccessful,
                hunt_name=clean(row.get("hunt_name")),
                species=clean(row.get("species")),
                draw_design=clean(row.get("draw_design")),
                draw_design_key=draw_design_key,
                record_type=record_type,
                actual_draw_year=clean(row.get("actual_draw_year")),
                model_target_year=clean(row.get("model_target_year")),
            )
        )
    return output


def is_guaranteed(point: ActualPoint) -> bool:
    if point.actual_eligible_applicants <= 0:
        return False
    if point.actual_probability is not None and point.actual_probability >= 0.999999:
        return True
    return point.actual_drawn >= point.actual_eligible_applicants


def build_ladders(actual_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str, str], Ladder], Counter[str], Counter[str]]:
    ladders: dict[tuple[str, str, str, str], Ladder] = {}
    actual_draw_years: Counter[str] = Counter()
    actual_model_targets: Counter[str] = Counter()
    for row in actual_rows:
        for point in actual_points_from_row(row):
            key = (point.draw_design_key, point.draw_pool, point.hunt_code, point.residency)
            ladder = ladders.setdefault(
                key,
                Ladder(
                    family=point.family,
                    draw_design_key=point.draw_design_key,
                    hunt_code=point.hunt_code,
                    residency=point.residency,
                    original_hunt_codes={point.original_hunt_code},
                    draw_pool=point.draw_pool,
                ),
            )
            ladder.original_hunt_codes.add(point.original_hunt_code)
            numeric = point_int(point.points)
            if numeric is None:
                existing = ladder.non_numeric_points.get(point.points)
                if existing is None or point.actual_eligible_applicants > existing.actual_eligible_applicants:
                    ladder.non_numeric_points[point.points] = point
            else:
                existing = ladder.points.get(numeric)
                if existing is None or point.actual_eligible_applicants > existing.actual_eligible_applicants:
                    ladder.points[numeric] = point
            if point.actual_draw_year:
                actual_draw_years[point.actual_draw_year] += 1
            if point.model_target_year:
                actual_model_targets[point.model_target_year] += 1
    return ladders, actual_draw_years, actual_model_targets


def prediction_probability(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for field in PREDICTION_PROBABILITY_FIELDS:
        probability = bounded_probability(row.get(field), field)
        if probability is not None:
            return probability, field
    return None, ""


def prediction_alignment_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    family = family_from_prediction(row)
    draw_design = prediction_draw_design(row, family)
    draw_pool = prediction_draw_pool(row, family)
    # Sportsman is strictly random and has no bonus/preference point key.
    points = "" if family == "sportsman" else norm_points(row.get("points"))
    hunt_code = resolve_hunt_code(row.get("hunt_code")).join_code
    return (
        draw_design,
        draw_pool,
        hunt_code,
        prediction_residency(row),
        points,
        family,
    )


def actual_alignment_key(point: ActualPoint) -> tuple[str, str, str, str, str]:
    return (point.draw_design_key, point.draw_pool, point.hunt_code, point.residency, point.points)


def point_relation_to_draw_line(ladder: Ladder | None, points: str) -> tuple[str, ActualPoint | None]:
    if ladder is None:
        return "no_structural_ladder", None
    if points in ladder.non_numeric_points:
        if ladder.family == "sportsman":
            return "sportsman_random_permit_row", ladder.non_numeric_points[points]
        return "non_point_permit_summary_row", ladder.non_numeric_points[points]
    numeric = point_int(points)
    top = ladder.top_applicant_point
    mixed = ladder.mixed_cutoff_point
    guaranteed_bottom = ladder.lowest_guaranteed_stack_point
    if numeric is None:
        return "point_not_numeric", None

    actual_point = ladder.points.get(numeric)
    if actual_point is not None:
        if actual_point.actual_eligible_applicants <= 0:
            return "zero_applicant_structural_row", actual_point
        if mixed is None:
            return "all_applicant_points_guaranteed_or_no_mixed_draw_line", actual_point
        if numeric == mixed:
            return "at_mixed_draw_line", actual_point
        if guaranteed_bottom is not None and numeric >= guaranteed_bottom:
            return "above_draw_line_guaranteed_stack", actual_point
        if numeric > mixed:
            return "above_mixed_draw_line_noncontiguous", actual_point
        return "below_draw_line_random_pool", actual_point

    if top is not None and numeric > top:
        return "outside_pdf_ladder_above_top_applicant_point", None
    numeric_points = ladder.numeric_points
    if numeric_points and numeric < min(numeric_points):
        return "outside_pdf_ladder_below_min_point", None
    return "point_level_not_in_pdf_ladder_gap", None


def structural_join_status(ladder: Ladder | None) -> str:
    return "matched_draw_design_draw_pool_hunt_residency" if ladder is not None else "no_draw_design_draw_pool_hunt_residency_match"


def scoring_decision(
    ladder: Ladder | None,
    relation: str,
    actual: ActualPoint | None,
    predicted_probability: float | None,
    prediction_family: str,
) -> str:
    if not prediction_family:
        return "do_not_score_unknown_prediction_family"
    if ladder is None:
        return "do_not_score_no_structural_ladder"
    if actual is None:
        return "do_not_score_outside_pdf_ladder"
    if actual.actual_eligible_applicants <= 0:
        return "do_not_score_zero_actual_applicants"
    if actual.actual_probability is None:
        return "do_not_score_missing_actual_probability"
    if predicted_probability is None:
        return "do_not_score_missing_prediction_probability"
    if relation in {
        "at_mixed_draw_line",
        "above_draw_line_guaranteed_stack",
        "above_mixed_draw_line_noncontiguous",
        "below_draw_line_random_pool",
        "all_applicant_points_guaranteed_or_no_mixed_draw_line",
        "non_point_permit_summary_row",
        "sportsman_random_permit_row",
    }:
        return "score_probability"
    return "do_not_score_unclassified_point_relation"


def metrics(errors: list[float], weighted_abs_sum: float, weight_sum: float) -> dict[str, str]:
    if not errors:
        return {
            "mae": "",
            "rmse": "",
            "bias": "",
            "median_absolute_error": "",
            "within_1pp_rate": "",
            "within_5pp_rate": "",
            "within_10pp_rate": "",
            "applicant_weighted_mae": "",
        }
    abs_errors = sorted(abs(error) for error in errors)
    count = len(errors)
    return {
        "mae": f"{sum(abs_errors) / count:.10f}",
        "rmse": f"{math.sqrt(sum(error * error for error in errors) / count):.10f}",
        "bias": f"{sum(errors) / count:.10f}",
        "median_absolute_error": f"{abs_errors[count // 2] if count % 2 else (abs_errors[count // 2 - 1] + abs_errors[count // 2]) / 2:.10f}",
        "within_1pp_rate": f"{sum(1 for value in abs_errors if value <= 0.01) / count:.10f}",
        "within_5pp_rate": f"{sum(1 for value in abs_errors if value <= 0.05) / count:.10f}",
        "within_10pp_rate": f"{sum(1 for value in abs_errors if value <= 0.10) / count:.10f}",
        "applicant_weighted_mae": "" if weight_sum <= 0 else f"{weighted_abs_sum / weight_sum:.10f}",
    }


ROW_FIELDS = [
    "source_year",
    "target_year",
    "prediction_row_number",
    "family",
    "hunt_code",
    "original_hunt_code_predicted",
    "hunt_code_crosswalk_status_predicted",
    "hunt_name_predicted",
    "residency",
    "points",
    "draw_design_key",
    "draw_pool_key",
    "draw_pool_predicted",
    "predicted_probability",
    "prediction_probability_field",
    "actual_probability",
    "actual_probability_field",
    "actual_eligible_applicants",
    "actual_hunt_name",
    "actual_original_hunt_code",
    "actual_hunt_code_crosswalk_status",
    "actual_species",
    "actual_draw_design",
    "actual_draw_year",
    "actual_model_target_year",
    "structural_join_status",
    "point_relation_to_draw_line",
    "mixed_cutoff_point",
    "lowest_guaranteed_stack_point",
    "top_applicant_point",
    "scoring_decision",
    "error",
    "absolute_error",
    "source_years_used",
    "draw_system_type",
    "algorithm_status",
]

ACTUAL_LADDER_FIELDS = [
    "source_year",
    "target_year",
    "draw_design_key",
    "draw_pool_key",
    "hunt_code",
    "actual_original_hunt_code",
    "actual_hunt_code_crosswalk_status",
    "residency",
    "points",
    "family_actual",
    "family_predicted",
    "actual_hunt_name",
    "actual_species",
    "actual_probability",
    "actual_probability_field",
    "actual_eligible_applicants",
    "predicted_probability",
    "prediction_probability_field",
    "prediction_row_number",
    "prediction_original_hunt_code",
    "prediction_hunt_code_crosswalk_status",
    "prediction_duplicate_count",
    "structural_join_status",
    "point_relation_to_draw_line",
    "scoreability_status",
    "mixed_cutoff_point",
    "lowest_guaranteed_stack_point",
    "top_applicant_point",
    "scoring_decision",
    "error",
    "absolute_error",
]

EXTRA_PREDICTION_FIELDS = [
    "source_year",
    "target_year",
    "prediction_row_number",
    "draw_design_key",
    "draw_pool_key",
    "hunt_code",
    "original_hunt_code_predicted",
    "hunt_code_crosswalk_status_predicted",
    "residency",
    "points",
    "family",
    "hunt_name_predicted",
    "predicted_probability",
    "prediction_probability_field",
    "structural_join_status",
    "point_relation_to_draw_line",
    "scoreability_status",
    "mixed_cutoff_point",
    "lowest_guaranteed_stack_point",
    "top_applicant_point",
    "extra_prediction_status",
    "source_years_used",
    "draw_system_type",
    "algorithm_status",
]


def best_prediction_for_actual(
    prediction_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str, str, str], dict[str, Any]], Counter[tuple[str, str, str, str, str]]]:
    by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    counts: Counter[tuple[str, str, str, str, str]] = Counter()
    for row_number, row in enumerate(prediction_rows, start=2):
        draw_design, draw_pool, hunt_code, residency, points, family = prediction_alignment_key(row)
        key = (draw_design, draw_pool, hunt_code, residency, points)
        probability, probability_field = prediction_probability(row)
        hunt_code_resolution = resolve_hunt_code(row.get("hunt_code"))
        counts[key] += 1
        existing = by_key.get(key)
        candidate = {
            "row_number": row_number,
            "row": row,
            "family": family,
            "probability": probability,
            "probability_field": probability_field,
            "original_hunt_code": hunt_code_resolution.original_code,
            "hunt_code_crosswalk_status": hunt_code_resolution.status,
        }
        if existing is None:
            by_key[key] = candidate
            continue
        # Prefer a row with an actual probability; otherwise keep the first
        # stable occurrence to make duplicate handling reproducible.
        if existing["probability"] is None and probability is not None:
            by_key[key] = candidate
    return by_key, counts


def prediction_for_actual(
    actual: ActualPoint,
    predictions_by_key: Mapping[tuple[str, str, str, str, str], dict[str, Any]],
    prediction_counts: Counter[tuple[str, str, str, str, str]],
) -> tuple[dict[str, Any] | None, int]:
    exact_key = actual_alignment_key(actual)
    exact = predictions_by_key.get(exact_key)
    if exact is not None:
        return exact, prediction_counts.get(exact_key, 0)
    if actual.residency != "All":
        return None, 0

    base_key = (actual.draw_design_key, actual.draw_pool, actual.hunt_code)
    points = actual.points
    candidates: list[tuple[str, dict[str, Any], float]] = []
    for residency, applicants in (
        ("Resident", actual.resident_eligible_applicants),
        ("Nonresident", actual.nonresident_eligible_applicants),
    ):
        candidate_key = (*base_key, residency, points)
        candidate = predictions_by_key.get(candidate_key)
        if candidate is not None and candidate["probability"] is not None:
            candidates.append((residency, candidate, max(applicants, 0.0)))

    if not candidates:
        return None, 0
    if len(candidates) == 1:
        residency, candidate, _weight = candidates[0]
        output = dict(candidate)
        output["probability_field"] = f"{candidate['probability_field']}|single_{residency.lower()}_lane_for_total_scope"
        output["match_status"] = f"single_{residency.lower()}_lane_for_total_scope"
        return output, 1

    weight_sum = sum(weight for _residency, _candidate, weight in candidates)
    if weight_sum <= 0:
        probability = sum(candidate["probability"] for _residency, candidate, _weight in candidates) / len(candidates)
        match_status = "unweighted_residency_composite_for_total_scope"
    else:
        probability = sum(candidate["probability"] * weight for _residency, candidate, weight in candidates) / weight_sum
        match_status = "applicant_weighted_residency_composite_for_total_scope"

    first = candidates[0][1]
    output = dict(first)
    output["row_number"] = "+".join(str(candidate["row_number"]) for _residency, candidate, _weight in candidates)
    output["family"] = first["family"]
    output["probability"] = probability
    output["probability_field"] = match_status
    output["match_status"] = match_status
    return output, sum(prediction_counts.get((*base_key, residency, points), 0) for residency, _candidate, _weight in candidates)


def actual_ladder_rows(
    args: argparse.Namespace,
    ladders: Mapping[tuple[str, str, str, str], Ladder],
    prediction_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions_by_key, prediction_counts = best_prediction_for_actual(prediction_rows)
    rows: list[dict[str, Any]] = []
    errors_by_family: defaultdict[str, list[float]] = defaultdict(list)
    weighted_abs_by_family: defaultdict[str, float] = defaultdict(float)
    weights_by_family: defaultdict[str, float] = defaultdict(float)
    family_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for ladder in ladders.values():
        for actual in [*ladder.points.values(), *ladder.non_numeric_points.values()]:
            prediction, prediction_duplicate_count = prediction_for_actual(actual, predictions_by_key, prediction_counts)
            predicted_probability = prediction["probability"] if prediction else None
            prediction_probability_field = prediction["probability_field"] if prediction else ""
            relation, relation_actual = point_relation_to_draw_line(ladder, actual.points)
            decision = "score_probability"
            scoreability_status = "scoreable"
            if actual.actual_eligible_applicants <= 0:
                decision = "do_not_score_zero_actual_applicants"
                scoreability_status = "impossible_zero_actual_applicants"
            elif actual.actual_probability is None:
                decision = "do_not_score_missing_actual_probability"
                scoreability_status = "impossible_missing_actual_probability"
            elif prediction is None:
                decision = "missing_prediction_for_scoreable_actual_ladder_row"
                scoreability_status = "possible_missing_prediction"
            elif predicted_probability is None:
                decision = "do_not_score_missing_prediction_probability"
                scoreability_status = "possible_missing_prediction_probability"

            error = None
            family_key = actual.family or "(unknown)"
            family_counts[family_key]["actual_ladder_rows"] += 1
            family_counts[family_key][decision] += 1
            family_counts[family_key][relation] += 1
            if decision == "score_probability" and predicted_probability is not None and actual.actual_probability is not None:
                error = predicted_probability - actual.actual_probability
                errors_by_family[family_key].append(error)
                weighted_abs_by_family[family_key] += abs(error) * actual.actual_eligible_applicants
                weights_by_family[family_key] += actual.actual_eligible_applicants

            rows.append(
                {
                    "source_year": args.source_year,
                    "target_year": args.target_year,
                    "draw_design_key": actual.draw_design_key,
                    "draw_pool_key": actual.draw_pool,
                    "hunt_code": actual.hunt_code,
                    "actual_original_hunt_code": actual.original_hunt_code,
                    "actual_hunt_code_crosswalk_status": actual.hunt_code_crosswalk_status,
                    "residency": actual.residency,
                    "points": actual.points,
                    "family_actual": actual.family,
                    "family_predicted": "" if prediction is None else prediction["family"],
                    "actual_hunt_name": actual.hunt_name,
                    "actual_species": actual.species,
                    "actual_probability": "" if actual.actual_probability is None else f"{actual.actual_probability:.10f}",
                    "actual_probability_field": actual.actual_probability_field,
                    "actual_eligible_applicants": f"{actual.actual_eligible_applicants:.10g}",
                    "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.10f}",
                    "prediction_probability_field": prediction_probability_field,
                    "prediction_row_number": "" if prediction is None else prediction["row_number"],
                    "prediction_original_hunt_code": "" if prediction is None else prediction.get("original_hunt_code", ""),
                    "prediction_hunt_code_crosswalk_status": "" if prediction is None else prediction.get("hunt_code_crosswalk_status", ""),
                    "prediction_duplicate_count": prediction_duplicate_count,
                    "structural_join_status": "matched_draw_design_draw_pool_hunt_residency",
                    "point_relation_to_draw_line": relation,
                    "scoreability_status": scoreability_status,
                    "mixed_cutoff_point": "" if ladder.mixed_cutoff_point is None else ladder.mixed_cutoff_point,
                    "lowest_guaranteed_stack_point": "" if ladder.lowest_guaranteed_stack_point is None else ladder.lowest_guaranteed_stack_point,
                    "top_applicant_point": "" if ladder.top_applicant_point is None else ladder.top_applicant_point,
                    "scoring_decision": decision,
                    "error": "" if error is None else f"{error:.10f}",
                    "absolute_error": "" if error is None else f"{abs(error):.10f}",
                }
            )

    family_rows: list[dict[str, Any]] = []
    all_errors: list[float] = []
    all_weighted_abs = 0.0
    all_weights = 0.0
    for family in sorted(family_counts):
        errors = errors_by_family.get(family, [])
        all_errors.extend(errors)
        all_weighted_abs += weighted_abs_by_family.get(family, 0.0)
        all_weights += weights_by_family.get(family, 0.0)
        output = {"family": family, **family_counts[family]}
        output.update(metrics(errors, weighted_abs_by_family.get(family, 0.0), weights_by_family.get(family, 0.0)))
        family_rows.append(output)

    summary = {
        "actual_ladder_rows": len(rows),
        "actual_ladder_scored_rows": len(all_errors),
        "actual_ladder_not_scored_rows": len(rows) - len(all_errors),
        "actual_ladder_possible_rows": sum(1 for row in rows if str(row.get("scoreability_status", "")).startswith("possible_") or row.get("scoreability_status") == "scoreable"),
        "actual_ladder_possible_missing_prediction_rows": sum(1 for row in rows if row.get("scoreability_status") == "possible_missing_prediction"),
        "actual_ladder_possible_missing_prediction_probability_rows": sum(1 for row in rows if row.get("scoreability_status") == "possible_missing_prediction_probability"),
        "actual_ladder_impossible_zero_applicant_rows": sum(1 for row in rows if row.get("scoreability_status") == "impossible_zero_actual_applicants"),
        "actual_ladder_scoring_decision_counts": dict(Counter(row["scoring_decision"] for row in rows)),
        "actual_ladder_scoreability_status_counts": dict(Counter(row["scoreability_status"] for row in rows)),
        "actual_ladder_point_relation_counts": dict(Counter(row["point_relation_to_draw_line"] for row in rows)),
        "actual_ladder_family_rows": family_rows,
    }
    possible_rows = summary["actual_ladder_possible_rows"]
    summary["actual_ladder_possible_score_coverage_rate"] = "" if possible_rows == 0 else f"{len(all_errors) / possible_rows:.10f}"
    summary.update({f"actual_ladder_{key}": value for key, value in metrics(all_errors, all_weighted_abs, all_weights).items()})
    return rows, summary


def extra_prediction_rows(
    args: argparse.Namespace,
    ladders: Mapping[tuple[str, str, str, str], Ladder],
    prediction_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    actual_keys = {
        actual_alignment_key(actual)
        for ladder in ladders.values()
        for actual in [*ladder.points.values(), *ladder.non_numeric_points.values()]
    }
    extras: list[dict[str, Any]] = []
    for row_number, row in enumerate(prediction_rows, start=2):
        draw_design, draw_pool, hunt_code, residency, points, family = prediction_alignment_key(row)
        hunt_code_resolution = resolve_hunt_code(row.get("hunt_code"))
        key = (draw_design, draw_pool, hunt_code, residency, points)
        if key in actual_keys:
            continue
        ladder = ladders.get((draw_design, draw_pool, hunt_code, residency))
        relation, _actual = point_relation_to_draw_line(ladder, points)
        predicted_probability, probability_field = prediction_probability(row)
        extras.append(
            {
                "source_year": args.source_year,
                "target_year": args.target_year,
                "prediction_row_number": row_number,
                "draw_design_key": draw_design,
                "draw_pool_key": draw_pool,
                "hunt_code": hunt_code,
                "original_hunt_code_predicted": hunt_code_resolution.original_code,
                "hunt_code_crosswalk_status_predicted": hunt_code_resolution.status,
                "residency": residency,
                "points": points,
                "family": family,
                "hunt_name_predicted": clean(row.get("hunt_name")),
                "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.10f}",
                "prediction_probability_field": probability_field,
                "structural_join_status": "matched_draw_design_draw_pool_hunt_residency" if ladder else "no_draw_design_draw_pool_hunt_residency_match",
                "point_relation_to_draw_line": relation,
                "scoreability_status": "diagnostic_extra_prediction_not_actual_ladder_row",
                "mixed_cutoff_point": "" if ladder is None or ladder.mixed_cutoff_point is None else ladder.mixed_cutoff_point,
                "lowest_guaranteed_stack_point": "" if ladder is None or ladder.lowest_guaranteed_stack_point is None else ladder.lowest_guaranteed_stack_point,
                "top_applicant_point": "" if ladder is None or ladder.top_applicant_point is None else ladder.top_applicant_point,
                "extra_prediction_status": "extra_prediction_outside_pdf_ladder",
                "source_years_used": clean(row.get("source_years_used")),
                "draw_system_type": clean(row.get("draw_system_type")),
                "algorithm_status": clean(row.get("algorithm_status")),
            }
        )
    return extras


OFFICIAL_SCORE_KEY_V2_REQUIRED_COLUMNS = (
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "official_score_key_v2",
)

OFFICIAL_SCORE_KEY_V2_JOIN_FIELDS = (
    "official_score_key_v2",
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
)

OFFICIAL_SCORE_KEY_V2_OUTPUT_FIELDS = (
    "official_score_key_v2",
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "prediction_row_number",
    "truth_row_number",
    "prediction_probability_field",
    "truth_probability_field",
    "predicted_probability",
    "actual_probability",
    "error",
    "absolute_error",
    "match_status",
)


class OfficialScoreKeyV2ValidationError(RuntimeError):
    pass


def _score_scope_from_residency(value: Any) -> tuple[str, str]:
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"resident", "res", "r"}:
        return "RESIDENT", "Resident"
    if text in {"nonresident", "nonres", "nr", "n"}:
        return "NONRESIDENT", "Nonresident"
    return "TOTAL", ""


def _probability_metric_from_row(row: Mapping[str, Any]) -> str:
    explicit = clean(row.get("probability_metric")).strip()
    if explicit:
        return explicit
    for field in ("p_draw", "p_preference_draw", "p_sportsman_draw", "p_bonus_pool", "p_random_pool", "p_availability"):
        if clean(row.get(field)) != "":
            return field
    return "p_draw"


def _probability_for_official_row(row: Mapping[str, Any]) -> tuple[float | None, str]:
    metric = _probability_metric_from_row(row)
    candidate_fields = [metric, "p_draw", "actual_probability", "predicted_probability", "p_preference_draw", "p_sportsman_draw", "p_bonus_pool", "p_random_pool", "p_availability"]
    seen: set[str] = set()
    for field in candidate_fields:
        if field in seen:
            continue
        seen.add(field)
        value = bounded_probability(row.get(field), field)
        if value is not None:
            return value, field
    return None, ""


def _validate_official_score_key_v2_rows(rows: list[dict[str, str]], *, role: str) -> dict[str, dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    duplicate_counts: Counter[str] = Counter()
    for row_number, row in enumerate(rows, start=2):
        key = clean(row.get("official_score_key_v2"))
        if not key:
            raise OfficialScoreKeyV2ValidationError(f"{role} row {row_number} is missing official_score_key_v2")
        if key in keyed:
            duplicate_counts[key] += 1
            continue
        keyed[key] = {
            "row_number": row_number,
            "row": row,
            "probability": None,
            "probability_field": "",
        }
    if duplicate_counts:
        sample = "; ".join(f"{key} (+{count})" for key, count in duplicate_counts.most_common(5))
        raise OfficialScoreKeyV2ValidationError(f"{role} duplicate official_score_key_v2 keys: {len(duplicate_counts)} key(s); {sample}")
    return keyed


def _official_key_join_row(
    key: str,
    prediction_entry: dict[str, Any] | None,
    truth_entry: dict[str, Any] | None,
    *,
    target_year: int,
) -> dict[str, Any]:
    prediction_row = prediction_entry["row"] if prediction_entry else {}
    truth_row = truth_entry["row"] if truth_entry else {}
    base = prediction_row if prediction_row else truth_row
    predicted_probability, predicted_field = (None, "") if prediction_entry is None else _probability_for_official_row(prediction_row)
    actual_probability, actual_field = (None, "") if truth_entry is None else _probability_for_official_row(truth_row)
    error = None
    if predicted_probability is not None and actual_probability is not None:
        error = predicted_probability - actual_probability
    return {
        "official_score_key_v2": key,
        "target_year": clean(base.get("target_year")) or str(target_year),
        "source_family": clean(base.get("source_family")),
        "draw_system_type": clean(base.get("draw_system_type")),
        "draw_pool": clean(base.get("draw_pool")),
        "hunt_code": clean(base.get("hunt_code")).upper(),
        "score_scope": clean(base.get("score_scope")).upper(),
        "residency": clean(base.get("residency")),
        "points": clean(base.get("points")),
        "probability_metric": clean(base.get("probability_metric")),
        "prediction_row_number": "" if prediction_entry is None else prediction_entry["row_number"],
        "truth_row_number": "" if truth_entry is None else truth_entry["row_number"],
        "prediction_probability_field": predicted_field,
        "truth_probability_field": actual_field,
        "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.10f}",
        "actual_probability": "" if actual_probability is None else f"{actual_probability:.10f}",
        "error": "" if error is None else f"{error:.10f}",
        "absolute_error": "" if error is None else f"{abs(error):.10f}",
        "match_status": "matched" if prediction_entry and truth_entry else ("missing_prediction" if truth_entry else "extra_prediction"),
    }


def run_official_score_key_v2_mode(args: argparse.Namespace, prediction_rows: list[dict[str, str]], truth_rows: list[dict[str, str]]) -> dict[str, Any]:
    prediction_by_key = _validate_official_score_key_v2_rows(prediction_rows, role="prediction")
    truth_by_key = _validate_official_score_key_v2_rows(truth_rows, role="truth")

    all_keys = sorted(set(prediction_by_key) | set(truth_by_key))
    joined_rows: list[dict[str, Any]] = []
    unmatched_prediction_rows: list[dict[str, Any]] = []
    unmatched_truth_rows: list[dict[str, Any]] = []
    errors: list[float] = []

    for key in all_keys:
        prediction_entry = prediction_by_key.get(key)
        truth_entry = truth_by_key.get(key)
        row = _official_key_join_row(key, prediction_entry, truth_entry, target_year=args.target_year)
        if prediction_entry and truth_entry:
            joined_rows.append(row)
            predicted_probability = parse_float(row.get("predicted_probability"))
            actual_probability = parse_float(row.get("actual_probability"))
            if predicted_probability is not None and actual_probability is not None:
                errors.append(predicted_probability - actual_probability)
        elif prediction_entry:
            unmatched_prediction_rows.append(row)
        else:
            unmatched_truth_rows.append(row)

    if not joined_rows and all_keys:
        raise OfficialScoreKeyV2ValidationError("No matched official_score_key_v2 rows were produced")

    mae = rmse = bias = ""
    if errors:
        mae = f"{sum(abs(error) for error in errors) / len(errors):.10f}"
        rmse = f"{math.sqrt(sum(error * error for error in errors) / len(errors)):.10f}"
        bias = f"{sum(errors) / len(errors):.10f}"

    summary = {
        "scoring_mode": "official_score_key_v2",
        "target_year": args.target_year,
        "prediction_rows": len(prediction_rows),
        "truth_rows": len(truth_rows),
        "joined_rows": len(joined_rows),
        "unmatched_prediction_rows": len(unmatched_prediction_rows),
        "unmatched_truth_rows": len(unmatched_truth_rows),
        "duplicate_prediction_keys": 0,
        "duplicate_truth_keys": 0,
        "scored_rows": len(errors),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "calibration_applied": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "official_score_key_v2_joined_rows.csv", joined_rows, list(OFFICIAL_SCORE_KEY_V2_OUTPUT_FIELDS))
    write_csv(args.output_dir / "official_score_key_v2_unmatched_prediction_rows.csv", unmatched_prediction_rows, list(OFFICIAL_SCORE_KEY_V2_OUTPUT_FIELDS))
    write_csv(args.output_dir / "official_score_key_v2_unmatched_truth_rows.csv", unmatched_truth_rows, list(OFFICIAL_SCORE_KEY_V2_OUTPUT_FIELDS))
    write_json(args.output_dir / "official_score_key_v2_summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    global HUNT_CODE_CROSSWALK, ACTIVE_SCORING_HUNT_CODE_ALIASES
    crosswalk_dirs = [DEFAULT_HUNT_CODE_CROSSWALK_DIR] + list(args.hunt_code_crosswalk_dir or [])
    crosswalk_files = dedupe_paths(
        list(DEFAULT_HUNT_CODE_CROSSWALK_FILES)
        + crosswalk_files_from_dirs(crosswalk_dirs)
        + list(args.hunt_code_crosswalk_file or [])
    )
    HUNT_CODE_CROSSWALK = load_hunt_code_crosswalk(crosswalk_files)
    ACTIVE_SCORING_HUNT_CODE_ALIASES = dict(BASE_SCORING_HUNT_CODE_ALIASES)
    ACTIVE_SCORING_HUNT_CODE_ALIASES.update(
        YEAR_SCOPED_SCORING_HUNT_CODE_ALIASES.get((clean(args.source_year), clean(args.target_year)), {}) if args.source_year is not None else {}
    )
    prediction_header, prediction_rows = read_csv(args.prediction_file)
    actual_header, actual_rows = read_csv(args.truth_file)
    if args.source_year is None or ("official_score_key_v2" in prediction_header and "official_score_key_v2" in actual_header):
        return run_official_score_key_v2_mode(args, prediction_rows, actual_rows)
    ladders, actual_draw_years, actual_model_targets = build_ladders(actual_rows)

    rowlevel: list[dict[str, Any]] = []
    family_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    errors_by_family: defaultdict[str, list[float]] = defaultdict(list)
    weighted_abs_by_family: defaultdict[str, float] = defaultdict(float)
    weights_by_family: defaultdict[str, float] = defaultdict(float)

    for row_number, prediction in enumerate(prediction_rows, start=2):
        family = family_from_prediction(prediction)
        draw_design_key = prediction_draw_design(prediction, family)
        draw_pool_key = prediction_draw_pool(prediction, family)
        hunt_code_resolution = resolve_hunt_code(prediction.get("hunt_code"))
        hunt_code = hunt_code_resolution.join_code
        residency = prediction_residency(prediction)
        points = "" if family == "sportsman" else norm_points(prediction.get("points"))
        ladder = (
            ladders.get((draw_design_key, draw_pool_key, hunt_code, residency))
            if draw_design_key and draw_pool_key and hunt_code and residency
            else None
        )
        relation, actual = point_relation_to_draw_line(ladder, points)
        predicted_probability, prediction_probability_field = prediction_probability(prediction)
        decision = scoring_decision(ladder, relation, actual, predicted_probability, family)
        error = None
        if decision == "score_probability" and actual is not None and predicted_probability is not None and actual.actual_probability is not None:
            error = predicted_probability - actual.actual_probability
            errors_by_family[family].append(error)
            weight = actual.actual_eligible_applicants
            weighted_abs_by_family[family] += abs(error) * weight
            weights_by_family[family] += weight

        family_key = family or "(unknown)"
        family_counts[family_key]["prediction_rows"] += 1
        family_counts[family_key][structural_join_status(ladder)] += 1
        family_counts[family_key][relation] += 1
        family_counts[family_key][decision] += 1

        rowlevel.append(
            {
                "source_year": args.source_year,
                "target_year": args.target_year,
                "prediction_row_number": row_number,
                "family": family,
                "hunt_code": hunt_code,
                "original_hunt_code_predicted": hunt_code_resolution.original_code,
                "hunt_code_crosswalk_status_predicted": hunt_code_resolution.status,
                "hunt_name_predicted": clean(prediction.get("hunt_name")),
                "residency": residency,
                "points": points,
                "draw_design_key": draw_design_key,
                "draw_pool_key": draw_pool_key,
                "draw_pool_predicted": clean(prediction.get("draw_pool")),
                "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.10f}",
                "prediction_probability_field": prediction_probability_field,
                "actual_probability": "" if actual is None or actual.actual_probability is None else f"{actual.actual_probability:.10f}",
                "actual_probability_field": "" if actual is None else actual.actual_probability_field,
                "actual_eligible_applicants": "" if actual is None else f"{actual.actual_eligible_applicants:.10g}",
                "actual_hunt_name": "" if actual is None else actual.hunt_name,
                "actual_original_hunt_code": "" if actual is None else actual.original_hunt_code,
                "actual_hunt_code_crosswalk_status": "" if actual is None else actual.hunt_code_crosswalk_status,
                "actual_species": "" if actual is None else actual.species,
                "actual_draw_design": "" if actual is None else actual.draw_design,
                "actual_draw_year": "" if actual is None else actual.actual_draw_year,
                "actual_model_target_year": "" if actual is None else actual.model_target_year,
                "structural_join_status": "matched_draw_design_draw_pool_hunt_residency"
                if ladder is not None
                else "no_draw_design_draw_pool_hunt_residency_match",
                "point_relation_to_draw_line": relation,
                "mixed_cutoff_point": "" if ladder is None or ladder.mixed_cutoff_point is None else ladder.mixed_cutoff_point,
                "lowest_guaranteed_stack_point": "" if ladder is None or ladder.lowest_guaranteed_stack_point is None else ladder.lowest_guaranteed_stack_point,
                "top_applicant_point": "" if ladder is None or ladder.top_applicant_point is None else ladder.top_applicant_point,
                "scoring_decision": decision,
                "error": "" if error is None else f"{error:.10f}",
                "absolute_error": "" if error is None else f"{abs(error):.10f}",
                "source_years_used": clean(prediction.get("source_years_used")),
                "draw_system_type": clean(prediction.get("draw_system_type")),
                "algorithm_status": clean(prediction.get("algorithm_status")),
            }
        )

    family_rows: list[dict[str, Any]] = []
    all_errors: list[float] = []
    all_weighted_abs = 0.0
    all_weights = 0.0
    for family in sorted(family_counts):
        errors = errors_by_family.get(family, [])
        all_errors.extend(errors)
        all_weighted_abs += weighted_abs_by_family.get(family, 0.0)
        all_weights += weights_by_family.get(family, 0.0)
        output = {"family": family, **family_counts[family]}
        output.update(metrics(errors, weighted_abs_by_family.get(family, 0.0), weights_by_family.get(family, 0.0)))
        family_rows.append(output)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_type": "full_engine_draw_line_aware_score",
        "source_year": args.source_year,
        "target_year": args.target_year,
        "prediction_file": rel(args.prediction_file),
        "truth_file": rel(args.truth_file),
        "prediction_sha256": sha256(args.prediction_file),
        "truth_sha256": sha256(args.truth_file),
        "hunt_code_crosswalk_dirs": [rel(path) for path in crosswalk_dirs if path.exists()],
        "hunt_code_crosswalk_files": [rel(path) for path in crosswalk_files if path.exists()],
        "hunt_code_crosswalk_alias_count": len(HUNT_CODE_CROSSWALK),
        "prediction_rows": len(prediction_rows),
        "prediction_columns": len(prediction_header),
        "truth_rows": len(actual_rows),
        "truth_columns": len(actual_header),
        "structural_ladder_count": len(ladders),
        "actual_draw_years_indexed": dict(actual_draw_years),
        "actual_model_target_years_indexed": dict(actual_model_targets),
        "scored_rows": len(all_errors),
        "not_scored_rows": len(prediction_rows) - len(all_errors),
        "structural_join_counts": dict(Counter(row["structural_join_status"] for row in rowlevel)),
        "point_relation_counts": dict(Counter(row["point_relation_to_draw_line"] for row in rowlevel)),
        "scoring_decision_counts": dict(Counter(row["scoring_decision"] for row in rowlevel)),
        "scoring_rule": (
            "Join structurally by draw_design+draw_pool+hunt_code+residency, classify prediction points "
            "against the actual PDF-derived ladder and mixed-success draw line, and score only real PDF "
            "ladder rows with nonzero actual applicants plus predicted and actual probability."
        ),
        "family_rows": family_rows,
    }
    summary.update(metrics(all_errors, all_weighted_abs, all_weights))

    actual_rows_out, actual_summary = actual_ladder_rows(args, ladders, prediction_rows)
    extras = extra_prediction_rows(args, ladders, prediction_rows)
    summary.update(actual_summary)
    summary["all_possible_rows_scored"] = (
        summary.get("actual_ladder_possible_missing_prediction_rows", 0) == 0
        and summary.get("actual_ladder_possible_missing_prediction_probability_rows", 0) == 0
    )
    summary.update(
        {
            "extra_prediction_rows": len(extras),
            "extra_prediction_structural_join_counts": dict(Counter(row["structural_join_status"] for row in extras)),
            "extra_prediction_point_relation_counts": dict(Counter(row["point_relation_to_draw_line"] for row in extras)),
            "summary_only": bool(args.summary_only),
        }
    )

    if not args.summary_only:
        write_csv(args.output_dir / "draw_line_aware_prediction_vs_actual_rowlevel.csv", rowlevel, ROW_FIELDS)
        write_csv(args.output_dir / "draw_line_aware_prediction_vs_actual_by_family.csv", family_rows)
        write_csv(args.output_dir / "draw_line_aware_actual_ladder_scoring_rows.csv", actual_rows_out, ACTUAL_LADDER_FIELDS)
        write_csv(args.output_dir / "draw_line_aware_extra_prediction_diagnostics.csv", extras, EXTRA_PREDICTION_FIELDS)
    write_json(args.output_dir / "draw_line_aware_prediction_vs_actual_summary.json", summary)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", "--prediction-file", dest="prediction_file", type=Path, required=True)
    parser.add_argument("--truth", "--truth-file", dest="truth_file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-year", type=int)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument(
        "--hunt-code-crosswalk-file",
        type=Path,
        action="append",
        default=[],
        help="Optional additional hunt-code crosswalk CSV. Defaults load the normalized crosswalk directory.",
    )
    parser.add_argument(
        "--hunt-code-crosswalk-dir",
        type=Path,
        action="append",
        default=[],
        help="Optional additional directory of normalized hunt-code crosswalk CSVs.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Write only aggregate summary JSON. Use this for blind truth runs where row-level diagnostics must stay opaque.",
    )
    parser.add_argument(
        "--require-all-possible-scored",
        action="store_true",
        help="Exit nonzero unless every possible actual ladder row has a prediction probability.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run(args)
    except OfficialScoreKeyV2ValidationError as exc:
        print(str(exc))
        return 2

    if summary.get("scoring_mode") == "official_score_key_v2":
        print(
            json.dumps(
                {
                    "prediction_rows": summary["prediction_rows"],
                    "truth_rows": summary["truth_rows"],
                    "joined_rows": summary["joined_rows"],
                    "unmatched_prediction_rows": summary["unmatched_prediction_rows"],
                    "unmatched_truth_rows": summary["unmatched_truth_rows"],
                    "duplicate_prediction_keys": summary["duplicate_prediction_keys"],
                    "duplicate_truth_keys": summary["duplicate_truth_keys"],
                    "scored_rows": summary["scored_rows"],
                    "mae": summary["mae"],
                    "rmse": summary["rmse"],
                    "bias": summary["bias"],
                    "calibration_applied": summary["calibration_applied"],
                    "output_dir": rel(args.output_dir),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "prediction_rows": summary["prediction_rows"],
                "truth_rows": summary["truth_rows"],
                "structural_ladder_count": summary["structural_ladder_count"],
                "scored_rows": summary["scored_rows"],
                "not_scored_rows": summary["not_scored_rows"],
                "mae": summary["mae"],
                "rmse": summary["rmse"],
                "bias": summary["bias"],
                "applicant_weighted_mae": summary["applicant_weighted_mae"],
                "structural_join_counts": summary["structural_join_counts"],
                "point_relation_counts": summary["point_relation_counts"],
                "scoring_decision_counts": summary["scoring_decision_counts"],
                "actual_ladder_rows": summary["actual_ladder_rows"],
                "actual_ladder_possible_rows": summary["actual_ladder_possible_rows"],
                "actual_ladder_scored_rows": summary["actual_ladder_scored_rows"],
                "actual_ladder_possible_missing_prediction_rows": summary["actual_ladder_possible_missing_prediction_rows"],
                "actual_ladder_possible_missing_prediction_probability_rows": summary[
                    "actual_ladder_possible_missing_prediction_probability_rows"
                ],
                "actual_ladder_possible_score_coverage_rate": summary["actual_ladder_possible_score_coverage_rate"],
                "all_possible_rows_scored": summary["all_possible_rows_scored"],
                "hunt_code_crosswalk_alias_count": summary["hunt_code_crosswalk_alias_count"],
                "output_dir": rel(args.output_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.require_all_possible_scored and not summary["all_possible_rows_scored"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
