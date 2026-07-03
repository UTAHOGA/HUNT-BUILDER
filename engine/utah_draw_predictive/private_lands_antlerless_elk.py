"""Private-lands-only antlerless elk OTC capped-quota helpers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import (
    ALGORITHM_STATUS_MODELED_AVAILABILITY,
    StrategySpec,
    TARGET_SCOPE_TARGET,
)


REPO = Path(__file__).resolve().parents[2]
PRIVATE_LANDS_SOURCE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "2026 Permits" / "elk antlerless private lands.csv"

MODEL_STRATEGY_NAME = "private_lands_antlerless_elk_otc_capped_quota_phase14"
RULE_VERSION = "utah_private_lands_antlerless_elk_otc_capped_permits_v1.2.0"
DRAW_SYSTEM_TYPE = "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"
ACQUISITION_METHOD = "OTC_CAPPED_PRIVATE_LANDS_PERMITS"

PRIVATE_LANDS_TOKENS = (
    "private lands only",
    "private land only",
    "private-land-only",
    "private lands antlerless elk",
    "private land antlerless elk",
    "antlerless elk private lands only",
    " plo ",
)

STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.private_lands_antlerless_elk",
        algorithm_status=ALGORITHM_STATUS_MODELED_AVAILABILITY,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Private-lands-only antlerless elk is an O.T.C. capped-permit stream, not preference or bonus draw odds.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    ),
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _to_int(value: object) -> int:
    text = _clean(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "NOTES", "notes", "source_file")
    )


def _has_private_lands_draw_marker(row: Mapping[str, object]) -> bool:
    return any(
        _clean(row.get(key)).upper() == DRAW_SYSTEM_TYPE
        for key in ("draw_system_type", "draw_2026_system_type")
    )


def is_private_lands_antlerless_elk_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    is_antlerless_elk = (
        "elk" in text
        and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "cow", "cow only"})
    )
    if is_antlerless_elk and _has_private_lands_draw_marker(row):
        return True
    return (
        is_antlerless_elk
        and any(token in f" {text} " for token in PRIVATE_LANDS_TOKENS)
    )


def is_modeled_private_lands_antlerless_elk_row(row: Mapping[str, object]) -> bool:
    return (
        _clean(row.get("draw_system_type")) == DRAW_SYSTEM_TYPE
        and _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean_lower(row.get("private_lands_allocation_valid")) in {"1", "true", "yes", "y"}
    )


def build_private_lands_antlerless_elk_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    source_rows: dict[str, dict[str, str]] = {}
    if PRIVATE_LANDS_SOURCE_PATH.exists():
        with PRIVATE_LANDS_SOURCE_PATH.open(encoding="utf-8-sig", newline="") as handle:
            import csv

            for row in csv.DictReader(handle):
                hunt_code = _clean(row.get("hunt_code")).upper()
                if hunt_code:
                    source_rows[hunt_code] = {
                        "hunt_name": _clean(row.get("hunt_name")),
                        "season_dates": _clean(row.get("season")),
                        "permits_total": _clean(row.get("permits_2026_total")),
                        "source_file": str(PRIVATE_LANDS_SOURCE_PATH.relative_to(REPO)),
                    }

    truth_by_code: dict[str, dict[str, str]] = {}
    source_files: set[str] = set()
    for row in truth_rows:
        if not is_private_lands_antlerless_elk_row(row):
            continue
        hunt_code = _clean(row.get("hunt_code")).upper()
        if not hunt_code:
            continue
        truth_by_code.setdefault(
            hunt_code,
            {
                "season_dates": _clean(row.get("season")),
                "unit": _clean(row.get("unit")) or _clean(row.get("hunt_name")),
                "source_file": _clean(row.get("source_file")),
            },
        )
        if _clean(row.get("source_file")):
            source_files.add(_clean(row.get("source_file")))

    rows: list[dict[str, object]] = []
    data_quality_counter: Counter[str] = Counter()
    reviewed_rows: list[dict[str, object]] = []

    for db_row in db_rows:
        if not is_private_lands_antlerless_elk_row(db_row):
            continue
        reviewed_rows.append(dict(db_row))
        hunt_code = _clean(db_row.get("hunt_code")).upper()
        if not hunt_code:
            continue
        source_meta = source_rows.get(hunt_code, {})
        permits_allotted = _to_int(source_meta.get("permits_total")) or _to_int(db_row.get("permits_2026_total"))
        truth_meta = truth_by_code.get(hunt_code, {})
        season_dates = _clean(truth_meta.get("season_dates")) or _clean(db_row.get("season"))
        if _clean(source_meta.get("season_dates")):
            season_dates = _clean(source_meta.get("season_dates"))
        unit = _clean(truth_meta.get("unit")) or _clean(source_meta.get("hunt_name")) or _clean(db_row.get("hunt_name"))
        source_file = _clean(source_meta.get("source_file")) or _clean(truth_meta.get("source_file")) or "DATABASE.csv"
        source_files.add(source_file)

        algorithm_status = "MODELED_AVAILABILITY" if permits_allotted > 0 else "IN_SCOPE_MODEL_PENDING"
        capped_permit_status = "OTC CAPPED PERMITS KNOWN / REMAINING UNKNOWN" if permits_allotted > 0 else "SOURCE MISSING"
        allocation_status = capped_permit_status
        availability_status = capped_permit_status
        season_status = "SEASON DATES PRESENT" if season_dates else "SEASON DATES MISSING"
        data_quality_flags = []
        if permits_allotted > 0:
            data_quality_flags.extend(["REMAINING_PERMIT_STATUS_UNKNOWN", "OTC_CAPPED_QUOTA_NOT_RESIDENCY_SPLIT"])
            if not season_dates:
                data_quality_flags.append("SEASON_DATES_MISSING")
        else:
            data_quality_flags.append("SOURCE_MISSING")
        for flag in data_quality_flags:
            data_quality_counter[flag] += 1

        for residency in ("Resident", "Nonresident"):
            rows.append(
                {
                    "model_version": MODEL_VERSION,
                    "rule_version": RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": _clean(db_row.get("hunt_name")),
                    "species": _clean(db_row.get("species")),
                    "sex_type": _clean(db_row.get("sex_type")),
                    "hunt_type": _clean(db_row.get("hunt_type")),
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
                    "algorithm_status": algorithm_status,
                    "weapon": _clean(db_row.get("weapon")),
                    "draw_system_type": DRAW_SYSTEM_TYPE,
                    "draw_design": "Capped Permits",
                    "acquisition_method": ACQUISITION_METHOD,
                    "private_lands_allocation_valid": "TRUE" if permits_allotted > 0 else "FALSE",
                    "private_lands_allocation_note": allocation_status,
                    "private_lands_capped_permit_valid": "TRUE" if permits_allotted > 0 else "FALSE",
                    "private_lands_capped_permit_note": capped_permit_status,
                    "capped_permit_count": str(permits_allotted) if permits_allotted > 0 else "",
                    "permits_allotted": str(permits_allotted) if permits_allotted > 0 else "",
                    "permits_remaining": "",
                    "permits_sold": "",
                    "permits_sold_or_used": "",
                    "allocation_status": allocation_status,
                    "capped_permit_status": capped_permit_status,
                    "availability_status": availability_status,
                    "p_availability": "",
                    "availability_pct": "",
                    "sellout_risk": "",
                    "closure_risk": "",
                    "sale_date": "",
                    "unit": unit,
                    "season_dates": season_dates,
                    "season_status": season_status,
                    "private_land_only_flag": "TRUE",
                    "data_quality_flags": "|".join(data_quality_flags),
                    "p_draw": "",
                    "p_draw_pct": "",
                    "p_bonus_pool": "",
                    "p_bonus_pool_pct": "",
                    "p_random_pool": "",
                    "p_random_pool_pct": "",
                    "p_preference_draw": "",
                }
            )

    modeled_rows = [row for row in rows if _clean(row.get("private_lands_allocation_valid")) == "TRUE"]
    pending_rows = [row for row in rows if _clean(row.get("private_lands_allocation_valid")) != "TRUE"]
    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_private_lands_antlerless_elk_rows_reviewed": len(reviewed_rows),
        "active_predictive_row_count": len(rows),
        "otc_capped_permit_row_count": len(modeled_rows),
        "modeled_allocation_row_count": len(modeled_rows),
        "pending_allocation_row_count": len(pending_rows),
        "pending_capped_permit_row_count": len(pending_rows),
        "excluded_row_count": 0,
        "hunt_code_count": len({row.get("hunt_code", "") for row in rows if _clean(row.get("hunt_code"))}),
        "unit_count": len({row.get("unit", "") for row in rows if _clean(row.get("unit"))}),
        "rows_by_algorithm_status": {
            "MODELED_AVAILABILITY": len(modeled_rows),
            "IN_SCOPE_MODEL_PENDING": len(pending_rows),
            "EXCLUDED_NOT_PREDICTIVE_DRAW": 0,
        },
        "classification": "OTC_CAPPED_PRIVATE_LANDS_PERMITS",
        "draw_design": "Capped Permits",
        "acquisition_method": ACQUISITION_METHOD,
        "permits_allotted_non_null_count": sum(1 for row in rows if _clean(row.get("permits_allotted"))),
        "permits_remaining_non_null_count": sum(1 for row in rows if _clean(row.get("permits_remaining"))),
        "p_availability_non_null_count": sum(1 for row in rows if _clean(row.get("p_availability"))),
        "availability_pct_non_null_count": sum(1 for row in rows if _clean(row.get("availability_pct"))),
        "sellout_risk_non_null_count": sum(1 for row in rows if _clean(row.get("sellout_risk"))),
        "p_draw_non_null_count": 0,
        "p_draw_pct_non_null_count": 0,
        "p_bonus_pool_non_null_count": 0,
        "p_random_pool_non_null_count": 0,
        "p_preference_draw_non_null_count": 0,
        "rows_with_availability_pct_outside_range": 0,
        "duplicate_key_count": len(rows) - len({(row.get("hunt_code", ""), row.get("residency", ""), row.get("points", "")) for row in rows}),
        "source_files_used": sorted(source_files),
        "data_quality_flags_summary": dict(sorted(data_quality_counter.items())),
    }
    return rows, report
