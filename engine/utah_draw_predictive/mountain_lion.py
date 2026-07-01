"""Phase 13 mountain lion / cougar rule-status and availability helpers."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from pypdf import PdfReader

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import (
    ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW,
    StrategySpec,
    TARGET_SCOPE_TARGET,
    append_reason_codes,
)


REPO = Path(__file__).resolve().parents[2]
COUGAR_TABLE_PATH = REPO / "data" / "cougar_hunt_table_official.json"
COUGAR_GUIDEBOOK_PATH = REPO / "processed_data" / "hard_data_exports" / "source_pdfs" / "regulations" / "2026" / "2026-bear-cougar-furbearer-guidebook.pdf"

MODEL_STRATEGY_NAME = "COUGAR_LICENSE_BASED_CLASSIFIER"
RULE_VERSION = "utah_mountain_lion_availability_v1.1.0"
DRAW_SYSTEM_TYPE = "COUGAR_LICENSE_BASED"
PERMIT_AVAILABILITY_TYPE = "HUNTING_OR_COMBINATION_LICENSE"
TRAPPING_ACQUISITION_METHOD = "HUNTING_OR_COMBINATION_LICENSE_PLUS_TRAP_REGISTRATION"

_EXCLUDED_NAME_TOKENS = ("conservation", "pursuit", "statewide", "control")
_UNIT_ALIAS_NORMALIZATIONS = {
    "La Sal": "La Sal Mtns",
    "West Desert, Mtn Ranges": "West Desert, Mountain Ranges",
    "Nebo (excludes West Face)": "Nebo (excluding West Face)",
    "Wasatch Mtns, Avintaquin-Wildcat": "Wasatch Mtns, Avintaquin/Currant Creek",
}

STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.mountain_lion",
        algorithm_status=ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Cougar is license-based availability/reference after the May 3, 2023 rule change, not draw odds.",
        modeled_by_engine=False,
        legacy_logic_present=True,
    ),
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "source_file", "NOTES", "notes")
    )


def is_mountain_lion_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    return any(token in text for token in ("mountain lion", "cougar"))


def is_modeled_mountain_lion_row(row: Mapping[str, object]) -> bool:
    return (
        _clean(row.get("draw_system_type")) == DRAW_SYSTEM_TYPE
        and _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean(row.get("unit_status")) == "OPEN"
        and _clean(row.get("permit_availability_type")) == PERMIT_AVAILABILITY_TYPE
    )


def _code_priority(code: str) -> tuple[int, int]:
    digits_text = re.sub(r"[^0-9]", "", code)
    digits = int(digits_text or "999999")
    if 1001 <= digits <= 1999:
        return (0, digits)
    if 7600 <= digits <= 7999:
        return (1, digits)
    if 1 <= digits <= 999:
        return (2, digits)
    if 7500 <= digits <= 7599:
        return (3, digits)
    return (4, digits)


def _extract_year_round_context() -> tuple[bool, list[str]]:
    source_files = []
    if COUGAR_GUIDEBOOK_PATH.exists():
        source_files.append(str(COUGAR_GUIDEBOOK_PATH.relative_to(REPO)))
        reader = PdfReader(str(COUGAR_GUIDEBOOK_PATH))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        normalized = re.sub(r"\s+", " ", text.lower())
        if (
            "residents and nonresidents may hunt or pursue cougar year-round" in normalized
            or "may hunt or pursue cougar year-round" in normalized
        ):
            return True, source_files
    return False, source_files


def _normalized_unit_name(name: str) -> str:
    return _UNIT_ALIAS_NORMALIZATIONS.get(name, name)


def _load_reporting_units() -> tuple[list[dict[str, str]], list[str]]:
    if not COUGAR_TABLE_PATH.exists():
        return [], []
    source_files = [str(COUGAR_TABLE_PATH.relative_to(REPO))]
    payload = json.loads(COUGAR_TABLE_PATH.read_text(encoding="utf-8"))
    by_unit: dict[str, set[str]] = defaultdict(set)
    for feature in payload.get("features", []):
        attributes = feature.get("attributes", {})
        hunt_code = _clean(attributes.get("HUNT_NUMBER")).upper()
        unit_name = _normalized_unit_name(_clean(attributes.get("BOUNDARY_NAME")))
        if not hunt_code.startswith("CG"):
            continue
        if not unit_name:
            continue
        if any(token in unit_name.lower() for token in _EXCLUDED_NAME_TOKENS):
            continue
        by_unit[unit_name].add(hunt_code)

    units = []
    for unit_name, codes in sorted(by_unit.items()):
        hunt_code = sorted(codes, key=_code_priority)[0]
        units.append({"hunt_code": hunt_code, "unit_name": unit_name})
    return units, source_files


def build_mountain_lion_availability_predictions(
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    data_quality_counter: Counter[str] = Counter()
    source_files_used: list[str] = []

    has_year_round_rule, guidebook_sources = _extract_year_round_context()
    reporting_units, table_sources = _load_reporting_units()
    source_files_used.extend(table_sources)
    source_files_used.extend(guidebook_sources)

    if not reporting_units:
        report = {
            "forecast_year": forecast_year,
            "source_years": history_years,
            "total_mountain_lion_cougar_rows_reviewed": 0,
            "active_predictive_cougar_rows": 0,
            "total_mountain_lion_rows_produced": 0,
            "hunt_code_count": 0,
            "cougar_hunt_code_count": 0,
            "unit_count": 0,
            "rows_by_algorithm_status": {ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW: 0},
            "modeled_availability_row_count": 0,
            "reference_license_based_no_draw_row_count": 0,
            "in_scope_model_pending_row_count": 0,
            "excluded_not_predictive_draw_row_count": 0,
            "unit_status_distribution": {},
            "season_date_coverage_distribution": {},
            "p_draw_non_null_count": 0,
            "p_draw_pct_non_null_count": 0,
            "p_preference_draw_non_null_count": 0,
            "p_bonus_pool_non_null_count": 0,
            "p_random_pool_non_null_count": 0,
            "p_availability_non_null_count": 0,
            "availability_pct_non_null_count": 0,
            "source_files_used": source_files_used,
            "data_quality_flags_summary": {"MOUNTAIN_LION_STATUS_SOURCE_MISSING": 1},
            "duplicate_key_count": 0,
        }
        return rows, report

    season_start = f"{forecast_year}-01-01" if has_year_round_rule else ""
    season_end = f"{forecast_year}-12-31" if has_year_round_rule else ""

    for unit in reporting_units:
        flags = ["STATEWIDE_OTC_RULE_STATUS", "HARVEST_REPORTING_UNIT_FROM_GEOMETRY"]
        if not has_year_round_rule:
            flags.append("MOUNTAIN_LION_STATUS_SOURCE_MISSING")
        for flag in flags:
            data_quality_counter[flag] += 1

        for residency in ("Resident", "Nonresident"):
            rows.append(
                {
                    "model_version": MODEL_VERSION,
                    "rule_version": RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": unit["hunt_code"],
                    "hunt_name": f"Cougar - Statewide OTC (Harvest Reporting: {unit['unit_name']})",
                    "species": "Cougar",
                    "sex_type": "",
                    "hunt_type": "Statewide OTC",
                    "hunt_class": "Public",
                    "residency": residency,
                    "points": "",
                    "draw_pool": "standard",
                    "source_dataset": "predictive",
                    "source_years_used": ",".join(str(year) for year in history_years),
                    "source_year_count": len(history_years),
                    "latest_source_year": max(history_years),
                    "earliest_source_year": min(history_years),
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "engine_family": "COUGAR_LICENSE_BASED_CLASSIFIER",
                    "weapon": "Any Legal Weapon",
                    "draw_system_type": DRAW_SYSTEM_TYPE,
                    "permit_availability_type": PERMIT_AVAILABILITY_TYPE,
                    "acquisition_method": "HUNTING_OR_COMBINATION_LICENSE",
                    "trapping_acquisition_method": TRAPPING_ACQUISITION_METHOD,
                    "public_draw_odds_eligible": "false",
                    "modeled_probability_allowed": "false",
                    "exclusion_reason": "license_based_no_public_draw_permit",
                    "permit_type": "License-based cougar hunting opportunity",
                    "permit_status": "AVAILABLE" if has_year_round_rule else "UNKNOWN",
                    "availability_status": "AVAILABLE YEAR-ROUND" if has_year_round_rule else "UNKNOWN",
                    "availability_reason": "Statewide OTC cougar rule-status / reporting-unit availability",
                    "probability_model": "NONE",
                    "season_start": season_start,
                    "season_end": season_end,
                    "season_status": "YEAR_ROUND_OPEN" if has_year_round_rule else "UNKNOWN",
                    "unit_name": unit["unit_name"],
                    "unit_status": "OPEN" if has_year_round_rule else "UNKNOWN",
                    "closure_reason": "",
                    "rule_status": "STATEWIDE_OTC_YEAR_ROUND" if has_year_round_rule else "RULE_STATUS_UNKNOWN",
                    "p_availability": "",
                    "availability_pct": "",
                    "closure_risk": "NONE" if has_year_round_rule else "",
                    "draw_outlook": "AVAILABLE YEAR-ROUND WITH VALID LICENSE" if has_year_round_rule else "RULE STATUS SOURCE MISSING",
                    "data_quality_flags": "|".join(flags),
                    "reason_codes": append_reason_codes(
                        "",
                        "AVAILABILITY_ONLY_NO_DRAW_PROBABILITY",
                        "COUGAR_LICENSE_BASED",
                        "LICENSE_BASED_NO_PUBLIC_DRAW_PERMIT",
                        "STATEWIDE_OTC_YEAR_ROUND" if has_year_round_rule else "RULE_STATUS_SOURCE_MISSING",
                    ),
                    "p_draw": "",
                    "p_draw_pct": "",
                    "p_bonus_pool": "",
                    "p_bonus_pool_pct": "",
                    "p_random_pool": "",
                    "p_random_pool_pct": "",
                    "p_preference_draw": "",
                }
            )

    unit_status_distribution = Counter(_clean(row.get("unit_status")) for row in rows)
    season_distribution = Counter(
        f"{_clean(row.get('season_start'))} to {_clean(row.get('season_end'))}" if _clean(row.get("season_start")) and _clean(row.get("season_end")) else "MISSING"
        for row in rows
    )

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_mountain_lion_cougar_rows_reviewed": len(rows),
        "active_predictive_cougar_rows": len(rows),
        "total_mountain_lion_rows_produced": len(rows),
        "hunt_code_count": len({row["hunt_code"] for row in rows}),
        "cougar_hunt_code_count": len({row["hunt_code"] for row in rows}),
        "unit_count": len({row["unit_name"] for row in rows}),
        "rows_by_algorithm_status": {ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW: len(rows)},
        "modeled_availability_row_count": 0,
        "reference_license_based_no_draw_row_count": len(rows),
        "in_scope_model_pending_row_count": 0,
        "excluded_not_predictive_draw_row_count": 0,
        "unit_status_distribution": dict(sorted(unit_status_distribution.items())),
        "season_date_coverage_distribution": dict(sorted(season_distribution.items())),
        "p_draw_non_null_count": 0,
        "p_draw_pct_non_null_count": 0,
        "p_preference_draw_non_null_count": 0,
        "p_bonus_pool_non_null_count": 0,
        "p_random_pool_non_null_count": 0,
        "p_availability_non_null_count": sum(1 for row in rows if _clean(row.get("p_availability"))),
        "availability_pct_non_null_count": sum(1 for row in rows if _clean(row.get("availability_pct"))),
        "source_files_used": sorted(dict.fromkeys(source_files_used)),
        "data_quality_flags_summary": dict(sorted(data_quality_counter.items())),
        "duplicate_key_count": len(rows) - len({(row["hunt_code"], row["residency"], row.get("points", "")) for row in rows}),
    }
    return rows, report
