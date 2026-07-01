"""Shadow-only preference draw calibration helpers.

This module deliberately does not wire itself into production materialization.
Callers must opt in and write candidate columns separately from the original
runtime probability fields.

Calibration value semantics are explicit:

- correction_probability_delta:
    A linear probability delta. By default, shrinkage_weight is applied.

- correction_factor_or_logit_offset:
    Legacy compatibility column. Treated as a linear probability delta only
    unless calibration_value_type explicitly says otherwise.

- calibration_value_type:
    probability_delta | pre_shrunk_probability_delta | logit_offset

This helper intentionally rejects logit_offset in shadow mode rather than
silently applying it as a linear probability delta.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


ALLOWED_PREFERENCE_DRAW_SYSTEM_TYPES = {
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_DOE_PRONGHORN",
}


DISALLOWED_DRAW_SYSTEM_TYPES = {
    "SPORTSMAN_RANDOM_ONLY",
    "COUGAR_LICENSE_BASED",
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
    "REFERENCE_ONLY",
    "AVAILABILITY_ONLY",
    "TRIBAL",
    "GUARANTEED_LIFETIME_PERMIT",
}


PROBABILITY_BINS = [
    ("0-1%", 0.00, 0.01),
    ("1-5%", 0.01, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-20%", 0.10, 0.20),
    ("20-40%", 0.20, 0.40),
    ("40-60%", 0.40, 0.60),
    ("60-80%", 0.60, 0.80),
    ("80-100%", 0.80, 1.01),
]


SUPPORTED_CALIBRATION_VALUE_TYPES = {
    "probability_delta",
    "pre_shrunk_probability_delta",
    "pre_shrunk_delta",
}


LOGIT_VALUE_TYPES = {
    "logit_offset",
    "logit_delta",
}


@dataclass(frozen=True)
class CalibrationSummary:
    rows: int
    applied_rows: int
    disallowed_applied_rows: int
    range_violations: int


def _blank_series(frame: pd.DataFrame, value: object = "") -> pd.Series:
    return pd.Series([value] * len(frame), index=frame.index)


def _as_string_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column in frame.columns:
        return frame[column].astype(str)
    return _blank_series(frame, default).astype(str)


def _numeric_value(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def probability_bin(value: object) -> str:
    probability = _numeric_value(value)
    if probability is None:
        return "missing"
    for label, lower, upper in PROBABILITY_BINS:
        if lower <= probability < upper:
            return label
    if probability >= 1:
        return "80-100%"
    return "missing"


def load_calibration_table(path: str) -> pd.DataFrame:
    table = pd.read_csv(path, low_memory=False)
    if "draw_system_type" not in table.columns:
        raise ValueError("calibration table missing draw_system_type")
    return table


def _source_probability_column(frame: pd.DataFrame) -> str | None:
    for column in ("p_draw_mean", "p_draw", "p_preference_draw"):
        if column in frame.columns:
            return column
    return None


def _calibration_value_type(row: pd.Series) -> str:
    value_type = str(row.get("calibration_value_type", "") or "").strip().lower()

    if value_type:
        return value_type

    # Backward compatibility:
    # Existing repo-side tables may still use correction_factor_or_logit_offset.
    # Treat it as an unshrunk linear probability delta, so shrinkage_weight is applied.
    return "probability_delta"


def _calibration_delta(row: pd.Series) -> tuple[float | None, str]:
    value_type = _calibration_value_type(row)

    if value_type in LOGIT_VALUE_TYPES:
        return None, "logit_offset_not_supported_in_shadow_helper"

    if value_type not in SUPPORTED_CALIBRATION_VALUE_TYPES:
        return None, f"unsupported_calibration_value_type:{value_type}"

    raw_delta = None

    if "correction_probability_delta" in row.index:
        raw_delta = _numeric_value(row.get("correction_probability_delta"))

    if raw_delta is None and "correction_factor_or_logit_offset" in row.index:
        raw_delta = _numeric_value(row.get("correction_factor_or_logit_offset"))

    if raw_delta is None:
        return None, "calibration_delta_missing"

    if value_type in {"pre_shrunk_probability_delta", "pre_shrunk_delta"}:
        return raw_delta, "pre_shrunk_probability_delta_applied"

    shrinkage = _numeric_value(row.get("shrinkage_weight", 1.0))
    if shrinkage is None:
        shrinkage = 1.0

    shrinkage = max(0.0, min(1.0, shrinkage))
    return raw_delta * shrinkage, "probability_delta_times_shrinkage_weight"


def apply_preference_calibration_candidate(
    frame: pd.DataFrame,
    calibration_table: pd.DataFrame,
    *,
    source_probability_column: str | None = None,
) -> pd.DataFrame:
    """Return a copy with shadow calibration columns.

    The original probability column is never changed. Candidate calibration is
    only applied to approved preference-family rows that already have a
    probability.
    """

    result = frame.copy()
    source_col = source_probability_column or _source_probability_column(result)

    if source_col is None:
        result["p_draw_original"] = pd.NA
    else:
        result["p_draw_original"] = pd.to_numeric(result[source_col], errors="coerce")

    result["p_draw_calibrated_candidate"] = result["p_draw_original"]
    result["calibration_family"] = _as_string_series(result, "draw_system_type")
    result["calibration_method"] = "no_calibration_baseline"
    result["calibration_bucket"] = result["p_draw_original"].apply(probability_bin)
    result["calibration_applied_candidate"] = False
    result["calibration_reason"] = "not_eligible_or_no_candidate_lookup"
    result["calibration_overfit_risk"] = "not_applicable"
    result["calibration_value_type"] = ""

    if calibration_table.empty or result.empty:
        return result

    table = calibration_table.copy()
    table = table[
        table["draw_system_type"].astype(str).isin(ALLOWED_PREFERENCE_DRAW_SYSTEM_TYPES)
    ].copy()

    if "shrinkage_weight" in table.columns:
        table = table[
            pd.to_numeric(table["shrinkage_weight"], errors="coerce").fillna(0) > 0
        ].copy()

    if table.empty:
        return result

    if "residency" not in table.columns:
        table["residency"] = "ALL"

    specific = table[table["residency"].astype(str).ne("ALL")]
    fallback = table[table["residency"].astype(str).eq("ALL")]

    specific_lookup = {
        (
            str(row["draw_system_type"]),
            str(row.get("residency", "")),
            str(row["probability_bin"]),
        ): row
        for _, row in specific.iterrows()
    }

    fallback_lookup = {
        (
            str(row["draw_system_type"]),
            str(row["probability_bin"]),
        ): row
        for _, row in fallback.iterrows()
    }

    for idx, row in result.iterrows():
        original = row["p_draw_original"]

        if pd.isna(original):
            result.at[idx, "calibration_reason"] = "no_original_probability"
            continue

        draw_system_type = str(row.get("draw_system_type", ""))

        if (
            draw_system_type in DISALLOWED_DRAW_SYSTEM_TYPES
            or draw_system_type not in ALLOWED_PREFERENCE_DRAW_SYSTEM_TYPES
        ):
            result.at[idx, "calibration_reason"] = (
                "draw_system_type_not_allowed_for_preference_calibration"
            )
            continue

        bucket = str(row.get("calibration_bucket", probability_bin(original)))
        residency = str(row.get("residency", ""))

        calibration_row = specific_lookup.get((draw_system_type, residency, bucket))

        if calibration_row is None:
            calibration_row = fallback_lookup.get((draw_system_type, bucket))

        if calibration_row is None:
            result.at[idx, "calibration_reason"] = "no_matching_family_bucket_calibration"
            continue

        delta, delta_reason = _calibration_delta(calibration_row)

        result.at[idx, "calibration_value_type"] = _calibration_value_type(calibration_row)

        if delta is None:
            result.at[idx, "calibration_reason"] = delta_reason
            continue

        calibrated = round(max(0.0, min(1.0, float(original) + float(delta))), 12)

        result.at[idx, "p_draw_calibrated_candidate"] = calibrated
        result.at[idx, "calibration_method"] = str(
            calibration_row.get("recommended_calibration_method", "candidate_lookup")
        )
        result.at[idx, "calibration_applied_candidate"] = True
        result.at[idx, "calibration_reason"] = (
            f"repo_side_family_probability_bucket_candidate:{delta_reason}"
        )
        result.at[idx, "calibration_overfit_risk"] = str(
            calibration_row.get("overfit_risk", "unknown")
        )

    result["calibration_applied_candidate"] = (
        result["calibration_applied_candidate"].map(bool).astype(object)
    )
    return result


def summarize_calibration_candidate(frame: pd.DataFrame) -> CalibrationSummary:
    applied = frame.get(
        "calibration_applied_candidate", pd.Series(dtype=bool)
    ).fillna(False).astype(bool)

    draw_system = frame.get("draw_system_type", pd.Series(dtype=str)).astype(str)
    calibrated = pd.to_numeric(
        frame.get("p_draw_calibrated_candidate", pd.Series(dtype=float)),
        errors="coerce",
    )

    disallowed = applied & ~draw_system.isin(ALLOWED_PREFERENCE_DRAW_SYSTEM_TYPES)
    violations = calibrated.notna() & ((calibrated < 0) | (calibrated > 1))

    return CalibrationSummary(
        rows=int(len(frame)),
        applied_rows=int(applied.sum()),
        disallowed_applied_rows=int(disallowed.sum()),
        range_violations=int(violations.sum()),
    )
