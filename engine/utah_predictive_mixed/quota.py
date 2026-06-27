from __future__ import annotations

import math

from engine.utah_predictive_mixed.prior_year import clamp, to_float

OFFICIAL_2026_DATABASE_FILE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"


def _first_float(*values: object) -> float | None:
    for value in values:
        parsed = to_float(value)
        if parsed is not None:
            return parsed
    return None


def is_no_published_permit_authority(row: dict[str, str]) -> bool:
    has_permits = bool(row.get("permits_2026_res") or row.get("permits_2026_nr") or row.get("permits_2026_total"))
    if has_permits:
        return False
    status_text = "|".join(
        str(row.get(field, "") or "").strip()
        for field in (
            "permits_2026_source",
            "permit_allotment_2026_source",
            "permit_allotment_2026_status",
            "permit_status",
            "permit_allocation_type",
            "data_status",
            "truth_source_status",
            "availability_status",
            "draw_2026_system_type",
            "draw_system_type",
            "reason_codes",
            "NOTES",
        )
    ).upper()
    return any(
        marker in status_text
        for marker in (
            "NO_PUBLISHED_PERMIT",
            "PERMIT_DATA_NOT_PUBLISHED",
            "NO_QUOTA_PUBLISHED",
            "NO_PUBLIC_DRAW_ODDS",
        )
    )


def quota_for_row(row: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    if is_no_published_permit_authority(row):
        return {
            "quota_2026_total": "",
            "quota_2026_max_pool": "",
            "quota_2026_random_pool": "",
            "quota_source_status": "no_published",
            "quota_source_year": "2026",
            "quota_source_file": OFFICIAL_2026_DATABASE_FILE,
        }, [
            "NO_PUBLISHED_PERMIT_AUTHORITY",
            "NO_QUOTA_PUBLISHED",
            "PUBLIC_DRAW_ODDS_EXCLUDED_NO_QUOTA",
        ]
    reasons = ["OFFICIAL_2026_QUOTA_USED"]
    has_published_permits = bool(row.get("permits_2026_res") or row.get("permits_2026_nr") or row.get("permits_2026_total"))
    if has_published_permits:
        reasons.append("DATABASE_2026_PUBLISHED_PERMITS_USED")
    residency = row.get("residency", "")
    total_only_published = bool(row.get("permits_2026_total")) and not row.get("permits_2026_res") and not row.get("permits_2026_nr")
    if residency == "Resident":
        quota = None if total_only_published else _first_float(row.get("permits_2026_res"), row.get("quota_2026_total"))
    elif residency == "Nonresident":
        quota = None if total_only_published else _first_float(row.get("permits_2026_nr"), row.get("quota_2026_total"))
    else:
        quota = _first_float(row.get("permits_2026_total"), row.get("quota_2026_total"))
    total = _first_float(row.get("permits_2026_total")) if total_only_published else quota
    if total is None:
        total = _first_float(row.get("quota_2026_total"), row.get("permits_2026_total"))
    max_pool = to_float(row.get("quota_2026_max_pool"))
    random_pool = to_float(row.get("quota_2026_random_pool"))
    if total_only_published and residency in {"Resident", "Nonresident"}:
        reasons.append("TOTAL_ONLY_PERMIT_AUTHORITY")
        reasons.append("NO_RESIDENCY_SPLIT_PUBLISHED")
        reasons.append("NO_RESIDENCY_LANE_QUOTA")
        max_pool = None
        random_pool = None
    elif quota is not None and max_pool is None:
        max_pool = math.ceil(quota * 0.50)
        random_pool = quota - max_pool
    if quota is not None and quota <= 0:
        reasons.append("ZERO_QUOTA_NONPREDICTIVE")
    if quota is None and total is not None and not row.get("permits_2026_res") and not row.get("permits_2026_nr"):
        reasons.append("TOTAL_ONLY_QUOTA")
    return {
        "quota_2026_total": "" if total is None else str(int(total)),
        "quota_2026_max_pool": "" if max_pool is None else str(int(max_pool)),
        "quota_2026_random_pool": "" if random_pool is None else str(int(random_pool)),
        "quota_source_status": "official" if has_published_permits or total is not None else (row.get("quota_source_status") or "official"),
        "quota_source_year": "2026",
        "quota_source_file": OFFICIAL_2026_DATABASE_FILE if has_published_permits or total is not None else row.get("quota_source_file", ""),
    }, reasons


def quota_adjusted_probability(
    p_prior: float | None, prior_public_permits: object, current_public_quota: object
) -> tuple[float | None, float, list[str]]:
    reasons: list[str] = []
    prior = to_float(prior_public_permits)
    current = to_float(current_public_quota)
    if prior in (None, 0) or current is None or current <= 0:
        ratio = 1.0
        reasons.append("QUOTA_RATIO_DEFAULTED")
    else:
        ratio = current / prior
    if current is not None and current <= 0:
        reasons.append("ZERO_QUOTA_NONPREDICTIVE")
    capped = min(2.0, max(0.25, ratio))
    if capped != ratio and ratio < 0.25:
        reasons.append("QUOTA_RATIO_CAPPED_LOW")
    if capped != ratio and ratio > 2.0:
        reasons.append("QUOTA_RATIO_CAPPED_HIGH")
    if ratio > 1.001:
        reasons.append("QUOTA_INCREASE")
    elif ratio < 0.999:
        reasons.append("QUOTA_DECREASE")
    else:
        reasons.append("QUOTA_UNCHANGED")
    if p_prior is None:
        return None, capped, reasons
    return clamp(p_prior * capped), capped, reasons
