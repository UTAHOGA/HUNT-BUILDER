"""Quota forecasting priorities and split application."""

from __future__ import annotations

from dataclasses import dataclass

from .split import UtahBonusPermitSplit, split_utah_bonus_permits


@dataclass(frozen=True)
class QuotaForecast:
    public_permits_forecast: int
    public_permits_source: str
    permit_delta_prior_to_forecast: int
    quota_confidence: float
    split: UtahBonusPermitSplit


def forecast_quota(
    prior_public_permits: int,
    official_forecast: int | None = None,
    residency: object = None,
) -> QuotaForecast:
    if official_forecast is not None:
        public = max(0, int(official_forecast))
        source = "official_forecast_quota"
        confidence = 0.95
    else:
        public = max(0, int(prior_public_permits))
        source = "prior_year_fallback"
        confidence = 0.60
    return QuotaForecast(
        public_permits_forecast=public,
        public_permits_source=source,
        permit_delta_prior_to_forecast=public - max(0, int(prior_public_permits)),
        quota_confidence=confidence,
        split=split_utah_bonus_permits(public, residency),
    )

