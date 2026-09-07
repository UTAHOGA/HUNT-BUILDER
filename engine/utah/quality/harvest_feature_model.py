"""Harvest quality feature helpers for Utah hunt prediction context.

These helpers intentionally produce quality and demand-signal features only.
They must not be used as public draw odds or quota/allotment sources.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from engine.utah.quality.harvest_identity import harvest_identity_compatible


BLANK_TOKENS = {"", "-", "--", "---", "–", "—", "na", "n/a", "none", "null"}


def clean_numeric(value: object) -> float | None:
    """Convert source values to float while preserving blanks/dashes as None."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in BLANK_TOKENS:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def safe_rate(numerator: object, denominator: object) -> float | None:
    numerator_value = clean_numeric(numerator)
    denominator_value = clean_numeric(denominator)
    if numerator_value is None or denominator_value in (None, 0):
        return None
    return numerator_value / denominator_value


def success_rate_check(row: dict[str, object]) -> dict[str, object]:
    harvest = clean_numeric(row.get("harvest_total") or row.get("harvest"))
    hunters = clean_numeric(row.get("hunters_afield"))
    reported = clean_numeric(row.get("percent_success"))
    if harvest is None or hunters in (None, 0) or reported is None:
        return {"status": "NOT_CHECKED", "expected_success_pct": None, "reason_code": "SOURCE_DOES_NOT_REPORT_FIELD"}
    expected = 100.0 * harvest / hunters
    conflict = abs(expected - reported) > 1.0
    return {
        "status": "CONFLICT" if conflict else "OK",
        "expected_success_pct": expected,
        "reported_percent_success": reported,
        "difference": abs(expected - reported),
        "reason_code": "SUCCESS_RATE_MATH_CONFLICT" if conflict else "",
    }


def rolling_mean(values: Iterable[object], years: int = 3) -> tuple[float | None, list[str]]:
    cleaned = [value for value in (clean_numeric(value) for value in values) if value is not None]
    recent = cleaned[-years:]
    if not recent:
        return None, ["NO_HISTORY"]
    if len(recent) == 1:
        return recent[0], ["SPARSE_HISTORY"]
    return mean(recent), []


def trend_delta(recent: object, prior: object) -> float | None:
    recent_value = clean_numeric(recent)
    prior_value = clean_numeric(prior)
    if recent_value is None or prior_value is None:
        return None
    return recent_value - prior_value


def trend_direction(delta: object, tolerance: float) -> str:
    delta_value = clean_numeric(delta)
    if delta_value is None:
        return "UNKNOWN"
    if delta_value > tolerance:
        return "INCREASING"
    if delta_value < -tolerance:
        return "DECREASING"
    return "FLAT"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def normalize_percent(value: object) -> float | None:
    number = clean_numeric(value)
    if number is None:
        return None
    return clamp(number)


def normalize_scale(value: object, scale_max: float) -> float | None:
    number = clean_numeric(value)
    if number is None or scale_max <= 0:
        return None
    return clamp((number / scale_max) * 100.0)


def normalize_inverse_effort(value: object) -> float | None:
    number = clean_numeric(value)
    if number is None:
        return None
    # Lower effort is usually better. Twelve days is treated as high effort pressure.
    return clamp(100.0 - ((number / 12.0) * 100.0))


def normalize_stability(delta: object, recent: object) -> float | None:
    delta_value = clean_numeric(delta)
    recent_value = clean_numeric(recent)
    if delta_value is None or recent_value in (None, 0):
        return None
    return clamp(100.0 - min(100.0, abs(delta_value) / max(abs(recent_value), 1.0) * 100.0))


def weighted_index(components: list[tuple[float, float | None]], reason_codes: list[str]) -> float | None:
    usable = [(weight, value) for weight, value in components if value is not None]
    if not usable:
        reason_codes.append("NO_USABLE_QUALITY_COMPONENTS")
        return None
    if len(usable) < len(components):
        reason_codes.append("QUALITY_INDEX_COMPONENT_REWEIGHTED")
    total_weight = sum(weight for weight, _ in usable)
    return clamp(sum((weight / total_weight) * value for weight, value in usable))


def harvest_quality_index(row: dict[str, object]) -> tuple[float | None, list[str]]:
    reason_codes: list[str] = []
    components = [
        (0.35, normalize_percent(row.get("harvest_success_recent") or row.get("percent_success"))),
        (0.20, normalize_scale(row.get("hunter_satisfaction_recent") or row.get("hunter_satisfaction"), 5.0)),
        (0.15, normalize_scale(row.get("average_age_recent") or row.get("average_age"), 10.0)),
        (0.10, normalize_percent(row.get("population_signal_recent"))),
        (0.10, normalize_stability(row.get("harvest_success_delta_1yr"), row.get("harvest_success_recent"))),
        (0.10, normalize_inverse_effort(row.get("hunter_effort_days_recent") or row.get("average_days"))),
    ]
    return weighted_index(components, reason_codes), reason_codes


def demand_pressure_signal(row: dict[str, object]) -> tuple[float | None, str, list[str]]:
    reason_codes: list[str] = []
    quality = clean_numeric(row.get("harvest_quality_index"))
    if quality is None:
        quality, quality_reasons = harvest_quality_index(row)
        reason_codes.extend(quality_reasons)
    success_delta = clean_numeric(row.get("harvest_success_delta_1yr"))
    age_delta = clean_numeric(row.get("average_age_delta_1yr"))
    satisfaction_delta = clean_numeric(row.get("hunter_satisfaction_delta_1yr"))
    effort_delta = clean_numeric(row.get("hunter_effort_days_delta_1yr"))
    components = [
        (0.40, quality),
        (0.20, clamp(50.0 + (success_delta or 0.0) * 5.0) if success_delta is not None else None),
        (0.15, clamp(50.0 + (age_delta or 0.0) * 20.0) if age_delta is not None else None),
        (0.15, clamp(50.0 + (satisfaction_delta or 0.0) * 20.0) if satisfaction_delta is not None else None),
        (0.10, clamp(50.0 - (effort_delta or 0.0) * 10.0) if effort_delta is not None else None),
    ]
    signal = weighted_index(components, reason_codes)
    if signal is None:
        return None, "UNKNOWN_DEMAND_SIGNAL", reason_codes
    if signal < 35:
        category = "LOW_DEMAND_SIGNAL"
    elif signal < 65:
        category = "MODERATE_DEMAND_SIGNAL"
    else:
        category = "HIGH_DEMAND_SIGNAL"
    return signal, category, reason_codes


def point_creep_quality_adjustment(row: dict[str, object]) -> float:
    signal = clean_numeric(row.get("demand_pressure_signal"))
    if signal is None:
        signal, _, _ = demand_pressure_signal(row)
    if signal is None:
        return 0.0
    if signal >= 75:
        return 0.25
    if signal >= 65:
        return 0.10
    if signal <= 25:
        return -0.10
    return 0.0


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def unit_key(hunt_name: object) -> str:
    text = str(hunt_name or "")
    return normalize_text(text.split(",", 1)[0])


@dataclass(frozen=True)
class FallbackSelection:
    rows: list[dict[str, str]]
    match_method: str
    data_quality_grade: str
    reason_codes: list[str]


def grade_for_match(match_method: str, year_count: int) -> str:
    if match_method == "EXACT_HUNT_CODE_HISTORY":
        if year_count >= 3:
            return "A"
        if year_count == 2:
            return "B"
        if year_count == 1:
            return "C"
    if match_method in {"SAME_HUNT_NAME_SPECIES_HISTORY", "UNIT_SPECIES_HISTORY"}:
        return "C" if year_count >= 2 else "D"
    return "F"


def fallback_feature_selection(
    hunt_code: str,
    species: str,
    hunt_name: str,
    target_year: int,
    history_rows: list[dict[str, str]] | None = None,
) -> FallbackSelection:
    rows = history_rows or []
    cutoff = int(target_year) - 1
    usable = [
        row
        for row in rows
        if clean_numeric(row.get("reported_hunt_year")) is not None
        and int(clean_numeric(row.get("reported_hunt_year")) or 0) <= cutoff
    ]
    species_norm = normalize_text(species)
    name_norm = normalize_text(hunt_name)
    unit_norm = unit_key(hunt_name)

    same_code = [row for row in usable if row.get("hunt_code") == hunt_code]
    target = {"hunt_code": hunt_code, "species": species, "hunt_name": hunt_name}
    candidates = [row for row in same_code if harvest_identity_compatible(row, target)]
    method = "EXACT_HUNT_CODE_HISTORY"
    reasons: list[str] = []
    if same_code and not candidates:
        reasons.append("HUNT_CODE_NAME_OR_SPECIES_MISMATCH_REJECTED")
    if not candidates and species_norm and name_norm:
        candidates = [
            row
            for row in usable
            if normalize_text(row.get("species")) == species_norm and normalize_text(row.get("hunt_name")) == name_norm
        ]
        method = "SAME_HUNT_NAME_SPECIES_HISTORY"
        reasons.append("FALLBACK_BY_HUNT_NAME_SPECIES")
    if not candidates and species_norm and unit_norm:
        candidates = [
            row
            for row in usable
            if normalize_text(row.get("species")) == species_norm and unit_key(row.get("hunt_name")) == unit_norm
        ]
        method = "UNIT_SPECIES_HISTORY"
        reasons.append("FALLBACK_BY_UNIT_SPECIES")
    if not candidates:
        return FallbackSelection(
            [],
            "NO_HARVEST_HISTORY",
            "F",
            reasons + ["NO_USABLE_HARVEST_HISTORY", "SPECIES_WIDE_FALLBACK_PROHIBITED"],
        )

    by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        year = int(clean_numeric(row.get("reported_hunt_year")) or 0)
        by_year[year].append(row)
    recent_years = sorted(by_year)[-3:]
    selected = [row for year in recent_years for row in by_year[year]]
    grade = grade_for_match(method, len(recent_years))
    if len(recent_years) < 3:
        reasons.append("SPARSE_HISTORY")
    return FallbackSelection(selected, method, grade, reasons)
