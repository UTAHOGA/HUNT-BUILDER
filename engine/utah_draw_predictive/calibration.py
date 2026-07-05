"""Guarded shadow calibration helpers for Utah draw predictions.

This module is intentionally narrow. It exposes the approved zero-preserving
linear recalibration only for PREFERENCE_ANTLERLESS_DEER and never mutates
production probability columns by itself.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable


CALIBRATION_FAMILY = "PREFERENCE_ANTLERLESS_DEER"
CALIBRATION_METHOD = "ZERO_PRESERVING_LINEAR_RECALIBRATION"
CALIBRATION_INTERCEPT = 0.006486245502080566
CALIBRATION_SLOPE = 1.044309834481592
CALIBRATION_GUARDRAIL_VERSION = "antlerless_deer_zero_preserving_v1"
SHADOW_MODES = {"shadow", "shadow_only", "audit_shadow"}
PRODUCTION_MODES = {"production"}
CALIBRATION_MODES = SHADOW_MODES | PRODUCTION_MODES


@dataclass(frozen=True)
class ShadowCalibrationAudit:
    family: str
    enabled: bool
    mode: str
    intercept: float
    slope: float
    rows_seen: int
    rows_shadow_calibrated: int
    rows_raw_zero: int
    rows_zero_preserved: int
    rows_clipped_to_zero: int
    rows_clipped_to_one: int
    raw_mean: float | None
    shadow_mean: float | None
    mean_delta: float | None
    max_delta: float | None
    duplicate_key_rows: int
    production_applied: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "enabled": self.enabled,
            "mode": self.mode,
            "intercept": self.intercept,
            "slope": self.slope,
            "rows_seen": self.rows_seen,
            "rows_shadow_calibrated": self.rows_shadow_calibrated,
            "rows_raw_zero": self.rows_raw_zero,
            "rows_zero_preserved": self.rows_zero_preserved,
            "rows_clipped_to_zero": self.rows_clipped_to_zero,
            "rows_clipped_to_one": self.rows_clipped_to_one,
            "raw_mean": self.raw_mean,
            "shadow_mean": self.shadow_mean,
            "mean_delta": self.mean_delta,
            "max_delta": self.max_delta,
            "duplicate_key_rows": self.duplicate_key_rows,
            "production_applied": self.production_applied,
            "calibration_method": CALIBRATION_METHOD,
            "calibration_guardrail_version": CALIBRATION_GUARDRAIL_VERSION,
        }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _family(row: dict[str, Any]) -> str:
    return _clean(row.get("draw_system_type") or row.get("family")).upper()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric):
        return None
    return numeric


def _clip_probability(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def apply_family_calibration(
    row: dict[str, Any],
    p_raw: Any,
    *,
    enabled: bool = False,
    mode: str = "off",
    calibrate_family: str = CALIBRATION_FAMILY,
) -> Any:
    """Return a calibrated shadow probability or the original value.

    The calibration is zero-preserving and family-scoped. Non-target families,
    disabled calls, null probabilities, and invalid numeric values are returned
    unchanged. Structural zeroes are returned as exactly 0.0.
    """

    if not enabled:
        return p_raw
    if _clean(mode).lower() not in CALIBRATION_MODES:
        return p_raw
    if _clean(calibrate_family).upper() != CALIBRATION_FAMILY:
        return p_raw
    if _family(row) != CALIBRATION_FAMILY:
        return p_raw

    numeric = _to_float(p_raw)
    if numeric is None:
        return p_raw
    if numeric <= 0:
        return 0.0

    return _clip_probability(CALIBRATION_INTERCEPT + CALIBRATION_SLOPE * numeric)


def shadow_calibration_columns(
    row: dict[str, Any],
    p_raw: Any,
    *,
    enabled: bool = False,
    mode: str = "off",
    calibrate_family: str = CALIBRATION_FAMILY,
) -> dict[str, Any]:
    """Build optional shadow output columns without replacing p_draw."""

    if not enabled or _clean(mode).lower() not in SHADOW_MODES:
        return {}

    numeric = _to_float(p_raw)
    p_shadow = apply_family_calibration(
        row,
        p_raw,
        enabled=enabled,
        mode=mode,
        calibrate_family=calibrate_family,
    )
    shadow_numeric = _to_float(p_shadow)
    family_matches = _family(row) == CALIBRATION_FAMILY
    zero_preserved = family_matches and numeric is not None and numeric <= 0 and shadow_numeric == 0.0
    applied = family_matches and numeric is not None and numeric > 0 and shadow_numeric != numeric

    return {
        "p_draw_raw": p_raw,
        "p_draw_shadow_calibrated": p_shadow,
        "calibration_family": CALIBRATION_FAMILY if family_matches else "",
        "calibration_method": CALIBRATION_METHOD if family_matches else "",
        "calibration_applied": "true" if applied else "false",
        "calibration_zero_preserved": "true" if zero_preserved else "false",
        "calibration_intercept": CALIBRATION_INTERCEPT if family_matches else "",
        "calibration_slope": CALIBRATION_SLOPE if family_matches else "",
        "calibration_guardrail_version": CALIBRATION_GUARDRAIL_VERSION if family_matches else "",
    }


def build_shadow_calibration_audit(
    rows: Iterable[dict[str, Any]],
    *,
    enabled: bool,
    mode: str,
    probability_column: str = "p_draw",
    key_columns: tuple[str, ...] = ("draw_year", "hunt_code", "residency", "points", "draw_system_type"),
) -> ShadowCalibrationAudit:
    """Summarize a shadow calibration run.

    The audit is row-level and read-only; production_applied is always false.
    Duplicate keys are counted only for the target family and only when all
    configured key columns exist with nonblank values.
    """

    rows_seen = 0
    rows_shadow_calibrated = 0
    rows_raw_zero = 0
    rows_zero_preserved = 0
    rows_clipped_to_zero = 0
    rows_clipped_to_one = 0
    raw_values: list[float] = []
    shadow_values: list[float] = []
    deltas: list[float] = []
    keys: list[tuple[str, ...]] = []

    for row in rows:
        rows_seen += 1
        if _family(row) != CALIBRATION_FAMILY:
            continue

        raw = _to_float(row.get(probability_column))
        shadow = apply_family_calibration(row, row.get(probability_column), enabled=enabled, mode=mode)
        shadow_float = _to_float(shadow)

        if raw is None or shadow_float is None:
            continue

        raw_values.append(raw)
        shadow_values.append(shadow_float)
        delta = shadow_float - raw
        deltas.append(abs(delta))

        if raw <= 0:
            rows_raw_zero += 1
            if shadow_float == 0.0:
                rows_zero_preserved += 1
        elif shadow_float != raw:
            rows_shadow_calibrated += 1

        if shadow_float == 0.0 and raw > 0:
            rows_clipped_to_zero += 1
        if shadow_float == 1.0 and raw < 1.0:
            rows_clipped_to_one += 1

        key = tuple(_clean(row.get(column)) for column in key_columns)
        if all(key):
            keys.append(key)

    duplicate_key_rows = sum(count for count in Counter(keys).values() if count > 1)
    raw_mean = sum(raw_values) / len(raw_values) if raw_values else None
    shadow_mean = sum(shadow_values) / len(shadow_values) if shadow_values else None

    return ShadowCalibrationAudit(
        family=CALIBRATION_FAMILY,
        enabled=enabled,
        mode=mode,
        intercept=CALIBRATION_INTERCEPT,
        slope=CALIBRATION_SLOPE,
        rows_seen=rows_seen,
        rows_shadow_calibrated=rows_shadow_calibrated,
        rows_raw_zero=rows_raw_zero,
        rows_zero_preserved=rows_zero_preserved,
        rows_clipped_to_zero=rows_clipped_to_zero,
        rows_clipped_to_one=rows_clipped_to_one,
        raw_mean=raw_mean,
        shadow_mean=shadow_mean,
        mean_delta=(shadow_mean - raw_mean) if raw_mean is not None and shadow_mean is not None else None,
        max_delta=max(deltas) if deltas else None,
        duplicate_key_rows=duplicate_key_rows,
        production_applied=False,
    )
