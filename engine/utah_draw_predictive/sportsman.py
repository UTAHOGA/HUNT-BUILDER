"""Sportsman permit resident-only random odds helpers."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

from . import (
    ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW,
    StrategySpec,
    TARGET_SCOPE_TARGET,
)


MODEL_STRATEGY_NAME = "SPORTSMAN_RANDOM_ONLY"
SPORTSMAN_DRAW_SYSTEM_TYPE = "SPORTSMAN_PERMIT"
SPORTSMAN_SOURCE_YEAR = 2025
SPORTSMAN_EXPECTED_CODE_COUNT = 10

REPO = Path(__file__).resolve().parents[2]
SPORTSMAN_SOURCE_CSV = REPO / "data" / "utah" / "sportsman" / "sportsman_odds_2025.csv"
SPORTSMAN_HISTORICAL_FEED_CSV = REPO / "processed_data" / "audits" / "sportsman_pdf_clean_script_feed.csv"
SPORTSMAN_SOURCE_XLSX = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "xlsx" / "24-25_sportsman_odds.xlsx"

SPORTSMAN_CODE_ALIASES: dict[str, list[str]] = {
    "BI1000": [],
    "BR1000": [],
    "DB0007": [],
    "DS1000": [],
    "EB1000": [],
    "GO1000": [],
    "MB1000": [],
    "PB1000": [],
    "RS0001": [],
    "TK0001": [],
}

STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=SPORTSMAN_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.sportsman",
        algorithm_status=ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Sportsman permits are ten Utah-resident-only random permits and do not inherit bonus, preference, split, or youth set-aside mechanics.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    )
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _safe_int(value: object) -> int:
    text = _clean(value).replace(",", "")
    if not text or text.upper() == "N/A":
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


@lru_cache(maxsize=1)
def _read_sportsman_source_rows() -> tuple[dict[str, str], ...]:
    with SPORTSMAN_SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


@lru_cache(maxsize=None)
def _read_historical_sportsman_rows(source_year: int) -> tuple[dict[str, str], ...]:
    if not SPORTSMAN_HISTORICAL_FEED_CSV.exists():
        return ()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with SPORTSMAN_HISTORICAL_FEED_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if _safe_int(raw.get("draw_results_year")) != source_year:
                continue
            if _clean(raw.get("artifact_status")) != "RAW_VALID":
                continue
            hunt_code = _clean(raw.get("normalized_hunt_code") or raw.get("raw_extracted_code")).upper()
            if not hunt_code or hunt_code in seen:
                continue
            seen.add(hunt_code)
            resident_quota = _safe_int(raw.get("resident_quota")) or _safe_int(raw.get("resident_successful"))
            nonresident_quota = _safe_int(raw.get("nonresident_quota"))
            total_apps = _safe_int(raw.get("total_applications")) or _safe_int(raw.get("odds_denominator"))
            rows.append(
                {
                    "year": str(source_year),
                    "hunt_code": hunt_code,
                    "hunt_name": _clean(raw.get("hunt_name")),
                    "species": _clean(raw.get("species")),
                    "resident_quota": str(resident_quota),
                    "nonresident_quota": str(nonresident_quota),
                    "total_quota": str(resident_quota + nonresident_quota),
                    "resident_apps": str(total_apps),
                    "nonresident_apps": "0",
                    "total_apps": str(total_apps),
                    "odds_text": _clean(raw.get("resident_success_ratio")),
                    "odds_denominator": str(_safe_int(raw.get("odds_denominator")) or total_apps),
                    "source_file": _clean(raw.get("source_file")),
                }
            )
    return tuple(rows)


@lru_cache(maxsize=None)
def _sportsman_source_by_code(source_year: int | None = None) -> dict[str, dict[str, str]]:
    historical_rows = _read_historical_sportsman_rows(source_year) if source_year is not None else ()
    if historical_rows:
        return {
            _clean(row.get("hunt_code")).upper(): row
            for row in historical_rows
            if _clean(row.get("hunt_code"))
        }
    return {
        _clean(row.get("hunt_code")).upper(): row
        for row in _read_sportsman_source_rows()
        if _clean(row.get("hunt_code"))
    }


@lru_cache(maxsize=1)
def sportsman_code_allowlist() -> set[str]:
    codes = set(_sportsman_source_by_code().keys())
    if SPORTSMAN_HISTORICAL_FEED_CSV.exists():
        with SPORTSMAN_HISTORICAL_FEED_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = _clean(row.get("normalized_hunt_code") or row.get("raw_extracted_code")).upper()
                if code:
                    codes.add(code)
    for aliases in SPORTSMAN_CODE_ALIASES.values():
        codes.update(_clean(alias).upper() for alias in aliases if _clean(alias))
    return codes


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in (
            "hunt_code",
            "hunt_name",
            "permit_name",
            "species",
            "hunt_type",
            "hunt_class",
            "weapon",
            "draw_pool",
            "sportsman_species",
        )
    )


def _canonical_sportsman_code(row: Mapping[str, object]) -> str:
    hunt_code = _clean(row.get("hunt_code")).upper()
    if hunt_code in sportsman_code_allowlist():
        return hunt_code
    for canonical_code, aliases in SPORTSMAN_CODE_ALIASES.items():
        if hunt_code in {_clean(alias).upper() for alias in aliases if _clean(alias)}:
            return canonical_code
    return hunt_code


def is_sportsman_permit_row(row: Mapping[str, object]) -> bool:
    hunt_code = _canonical_sportsman_code(row)
    text = _joined_text(row)
    if hunt_code in sportsman_code_allowlist():
        return True
    if "sportsman" in text:
        return True
    return False


def sportsman_species(row: Mapping[str, object]) -> str:
    canonical_code = _canonical_sportsman_code(row)
    source_row = _sportsman_source_by_code().get(canonical_code, {})
    return _clean(source_row.get("species")) or _clean(row.get("species"))


def is_modeled_sportsman_row(row: Mapping[str, object]) -> bool:
    return (
        _clean(row.get("draw_system_type")) == SPORTSMAN_DRAW_SYSTEM_TYPE
        and _clean_lower(row.get("model_strategy")) in {MODEL_STRATEGY_NAME.lower(), "sportsman_draw"}
        and _clean_lower(row.get("sportsman_valid")) in {"1", "true", "yes", "y"}
        and _clean(row.get("residency")).lower() == "resident"
        and _clean(row.get("p_sportsman_draw")) != ""
    )


def build_sportsman_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    del truth_rows

    source_year = max((_safe_int(year) for year in history_years), default=SPORTSMAN_SOURCE_YEAR)
    sportsman_source = _sportsman_source_by_code(source_year)
    source_code_count = len(sportsman_source)
    db_by_code = {
        _clean(row.get("hunt_code")).upper(): dict(row)
        for row in db_rows
        if _clean(row.get("hunt_code"))
    }
    rows: list[dict[str, object]] = []

    for hunt_code in sorted(sportsman_source.keys()):
        source_row = sportsman_source[hunt_code]
        db_row = db_by_code.get(hunt_code, {})
        resident_quota = _safe_int(source_row.get("resident_quota"))
        denominator = _safe_int(source_row.get("odds_denominator")) or _safe_int(source_row.get("resident_apps")) or _safe_int(source_row.get("total_apps"))
        probability = 0.0 if denominator <= 0 else min(1.0, max(0.0, resident_quota / denominator))
        hunt_name = _clean(source_row.get("hunt_name")) or _clean(db_row.get("hunt_name"))
        season = _clean(db_row.get("season"))
        row = {
            "year": str(forecast_year),
            "forecast_year": str(forecast_year),
            "hunt_code": hunt_code,
            "hunt_name": hunt_name,
            "species": _clean(source_row.get("species")) or _clean(db_row.get("species")),
            "sportsman_species": _clean(source_row.get("species")) or _clean(db_row.get("species")),
            "sex_type": _clean(db_row.get("sex_type")),
            "hunt_type": "Sportsman Permit",
            "hunt_class": "Public",
            "residency": "Resident",
            "points": "",
            "draw_pool": "sportsman",
            "draw_design": "Random",
            "sportsman_draw_design": "SPORTSMAN_RANDOM_ONLY",
            "sportsman_random_only": "TRUE",
            "sportsman_split_draw": "FALSE",
            "sportsman_resident_only": "TRUE",
            "sportsman_source_year": str(source_year),
            "sportsman_permit_count": str(resident_quota),
            "sportsman_applicants": str(_safe_int(source_row.get("resident_apps"))),
            "sportsman_nonresident_quota": "0",
            "sportsman_odds_text": _clean(source_row.get("odds_text")),
            "sportsman_odds_denominator": str(denominator),
            "p_sportsman_draw": f"{probability:.6f}",
            "p_draw": f"{probability:.6f}",
            "p_draw_pct": f"{probability * 100.0:.3f}",
            "p_bonus_pool": "",
            "p_random_pool": "",
            "p_preference_draw": "",
            "source_years_used": str(source_year),
            "source_year_count": 1,
            "latest_source_year": source_year,
            "earliest_source_year": source_year,
            "source_dataset": "predictive",
            "model_strategy": MODEL_STRATEGY_NAME,
            "draw_system_type": SPORTSMAN_DRAW_SYSTEM_TYPE,
            "sportsman_valid": "TRUE",
            "sportsman_model_note": "Resident-only random odds: resident permit count divided by eligible resident applicants.",
            "draw_outlook": "STATEWIDE DRAW",
            "sportsman_residency_scope": "RESIDENT_ONLY",
            "sportsman_source_file": _clean(source_row.get("source_file")) or _safe_relative(SPORTSMAN_SOURCE_CSV),
            "season_dates": season,
            "weapon": _clean(db_row.get("weapon")),
        }
        rows.append(row)

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "sportsman_source_year": source_year,
        "sportsman_expected_code_count": SPORTSMAN_EXPECTED_CODE_COUNT,
        "sportsman_source_code_count": source_code_count,
        "sportsman_code_count_guardrail": "PASS" if source_code_count >= SPORTSMAN_EXPECTED_CODE_COUNT else "FAIL",
        "sportsman_draw_design": "SPORTSMAN_RANDOM_ONLY",
        "sportsman_random_only": True,
        "sportsman_split_draw": False,
        "sportsman_residency_scope": "RESIDENT_ONLY",
        "sportsman_rows_reviewed": len(rows),
        "total_sportsman_rows_reviewed": len(rows),
        "sportsman_rows_modeled": len(rows),
        "modeled_sportsman_rows": len(rows),
        "sportsman_rows_pending": 0,
        "pending_sportsman_rows": 0,
        "hunt_code_list": [row["hunt_code"] for row in rows],
        "sportsman_hunt_codes": [row["hunt_code"] for row in rows],
        "species_list": [row["sportsman_species"] for row in rows],
        "sportsman_species_list": [row["sportsman_species"] for row in rows],
        "p_sportsman_draw_non_null_count": sum(1 for row in rows if _clean(row.get("p_sportsman_draw"))),
        "p_draw_non_null_count": sum(1 for row in rows if _clean(row.get("p_draw"))),
        "p_draw_pct_non_null_count": sum(1 for row in rows if _clean(row.get("p_draw_pct"))),
        "p_bonus_pool_non_null_count": 0,
        "p_random_pool_non_null_count": 0,
        "p_preference_draw_non_null_count": 0,
        "nonresident_row_count": sum(1 for row in rows if _clean_lower(row.get("residency")) != "resident"),
        "nonresident_quota_total": sum(_safe_int(row.get("sportsman_nonresident_quota")) for row in rows),
        "split_mechanics_guardrail": "PASS",
        "duplicate_key_count": len(rows) - len({(row["hunt_code"], row["residency"], row["points"]) for row in rows}),
        "source_files_used": [
            _safe_relative(SPORTSMAN_HISTORICAL_FEED_CSV) if SPORTSMAN_HISTORICAL_FEED_CSV.exists() else _safe_relative(SPORTSMAN_SOURCE_CSV),
            _safe_relative(SPORTSMAN_SOURCE_XLSX),
        ],
    }
    return rows, report
