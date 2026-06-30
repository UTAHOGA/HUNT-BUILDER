"""Target-year-aware permit accessors for Utah draw predictive engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PermitValue:
    value: int
    field: str
    used_2026_alias: bool = False


def _clean(value: object) -> str:
    return str(value or "").strip()


def _to_int(value: object) -> int:
    text = _clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _alias_documents_forecast_year(row: Mapping[str, object], forecast_year: int) -> bool:
    year_text = str(forecast_year)
    for key in (
        "permits_2026_alias_forecast_year",
        "permits_2026_alias_from_year",
        "permit_alias_forecast_year",
        "target_permits_alias_year",
    ):
        if _clean(row.get(key)) == year_text:
            return True
    for key in (
        "permits_2026_source",
        "quota_2026_source",
        "target_permits_source",
        "source_column_mapping",
        "reason_codes",
    ):
        text = _clean(row.get(key)).lower()
        if "alias" in text and year_text in text:
            return True
    return False


def _candidate_fields(forecast_year: int, lane: str, source_year: int | None = None) -> list[str]:
    year = str(forecast_year)
    source = str(source_year) if source_year is not None else ""
    if lane == "total":
        return [
            "target_permits_total",
            f"permits_{year}_total",
            f"quota_{year}_total",
            f"public_permits_{year}",
            *(
                [f"permits_{source}_total", f"quota_{source}_total", f"public_permits_{source}"]
                if source and source != year
                else []
            ),
        ]
    if lane == "res":
        return [
            "target_permits_res",
            f"permits_{year}_res",
            *([f"permits_{source}_res"] if source and source != year else []),
        ]
    if lane == "nr":
        return [
            "target_permits_nr",
            f"permits_{year}_nr",
            *([f"permits_{source}_nr"] if source and source != year else []),
        ]
    raise ValueError(f"Unsupported permit lane: {lane}")


def target_permit_value(row: Mapping[str, object], forecast_year: int, lane: str, source_year: int | None = None) -> PermitValue:
    for field in _candidate_fields(forecast_year, lane, source_year):
        value = _to_int(row.get(field))
        if value > 0:
            return PermitValue(value=value, field=field)

    if lane == "total":
        alias_fields = ("permits_2026_total", "quota_2026_total", "public_permits_2026")
    elif lane == "res":
        alias_fields = ("permits_2026_res",)
    elif lane == "nr":
        alias_fields = ("permits_2026_nr",)
    else:
        alias_fields = ()

    allow_alias = forecast_year == 2026 or _alias_documents_forecast_year(row, forecast_year)
    if allow_alias:
        for field in alias_fields:
            value = _to_int(row.get(field))
            if value > 0:
                return PermitValue(value=value, field=field, used_2026_alias=True)

    return PermitValue(value=0, field="")


def target_permit_total(row: Mapping[str, object], forecast_year: int, source_year: int | None = None) -> PermitValue:
    return target_permit_value(row, forecast_year, "total", source_year=source_year)


def target_permit_for_residency(
    row: Mapping[str, object],
    forecast_year: int,
    residency: str,
    source_year: int | None = None,
) -> PermitValue:
    lane = "nr" if _clean(residency).lower().startswith("non") else "res"
    return target_permit_value(row, forecast_year, lane, source_year=source_year)
