"""Target-year-aware permit accessors for Utah draw predictive engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PermitValue:
    value: int
    field: str
    used_2026_alias: bool = False


@dataclass(frozen=True)
class ResidencyPermitAllocation:
    """Official target-year permit allocation for resident and nonresident lanes.

    ``supported`` is false when a row has only a total permit count but its
    draw family does not have a hunt-level percentage rule that can safely be
    applied.  Callers must treat that state as a blocker, not as permission to
    reuse a historical winner-share split.
    """

    total: int
    resident: int
    nonresident: int
    authority: str
    supported: bool
    source_fields: tuple[str, ...] = ()

    def for_residency(self, residency: str) -> int:
        lane = _clean(residency).lower()
        if lane in {"", "all", "total"}:
            return self.total
        if lane.startswith("non"):
            return self.nonresident
        return self.resident


OFFICIAL_EXPLICIT_RESIDENCY_SPLIT = "OFFICIAL_EXPLICIT_RESIDENCY_SPLIT"
OFFICIAL_10_PERCENT_TOTAL_ALLOCATION = "OFFICIAL_10_PERCENT_TOTAL_ALLOCATION"
UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE = "UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE"
MISSING_TARGET_PERMIT_ALLOCATION = "MISSING_TARGET_PERMIT_ALLOCATION"

# Utah's standard public big-game preference lanes use the published total
# allotment with a 10 percent nonresident allocation.  Families whose permits
# are concentrated across hunts or separately published (notably OIL, bear,
# turkey, CWMU and reference/availability rows) are intentionally absent.
STANDARD_BIG_GAME_TEN_PERCENT_TYPES = frozenset(
    {
        "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "PREFERENCE_DEDICATED_HUNTER_DEER",
        "PREFERENCE_ANTLERLESS_DEER",
        "PREFERENCE_ANTLERLESS_ELK",
        "PREFERENCE_DOE_PRONGHORN",
    }
)


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


def _present_target_permit_value(
    row: Mapping[str, object],
    forecast_year: int,
    lane: str,
    source_year: int | None = None,
) -> tuple[bool, PermitValue]:
    """Return the first declared field, preserving an official zero value."""

    for field in _candidate_fields(forecast_year, lane, source_year):
        if _clean(row.get(field)):
            return True, PermitValue(value=_to_int(row.get(field)), field=field)

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
            if _clean(row.get(field)):
                return True, PermitValue(value=_to_int(row.get(field)), field=field, used_2026_alias=True)

    return False, PermitValue(value=0, field="")


def _draw_system_tokens(row: Mapping[str, object], draw_system_type: str | None = None) -> set[str]:
    text = _clean(draw_system_type or row.get("draw_system_type") or row.get("draw_design")).upper()
    return {token.strip() for token in text.split(";") if token.strip()}


def _uses_standard_big_game_ten_percent_rule(
    row: Mapping[str, object],
    draw_system_type: str | None = None,
) -> bool:
    draw_system_tokens = _draw_system_tokens(row, draw_system_type=draw_system_type)
    if len(draw_system_tokens) != 1 or not draw_system_tokens.intersection(STANDARD_BIG_GAME_TEN_PERCENT_TYPES):
        return False

    joined = " ".join(
        _clean(row.get(field)).lower()
        for field in ("hunt_name", "hunt_type", "hunt_class", "draw_pool", "source_type", "record_type")
    )
    return not any(
        marker in joined
        for marker in (
            "cwmu",
            "conservation",
            "expo",
            "sportsman",
            "landowner",
            "private voucher",
            "contact operator",
            "reference",
            "availability",
            "over the counter",
        )
    )


def target_residency_permit_allocation(
    row: Mapping[str, object],
    forecast_year: int,
    source_year: int | None = None,
    draw_system_type: str | None = None,
) -> ResidencyPermitAllocation:
    """Resolve target permits using official fields and source-backed rules.

    Precedence is explicit resident/nonresident fields, then an approved
    standard-big-game 90/10 split from the official total.  Historical draw
    results are deliberately not accepted by this accessor.
    """

    total_present, total_value = _present_target_permit_value(row, forecast_year, "total", source_year)
    res_present, res_value = _present_target_permit_value(row, forecast_year, "res", source_year)
    nr_present, nr_value = _present_target_permit_value(row, forecast_year, "nr", source_year)

    if res_present or nr_present:
        resident = max(res_value.value, 0) if res_present else 0
        nonresident = max(nr_value.value, 0) if nr_present else 0
        total = max(total_value.value, 0) if total_present else resident + nonresident
        if total_present and res_present and not nr_present:
            nonresident = max(total - resident, 0)
        elif total_present and nr_present and not res_present:
            resident = max(total - nonresident, 0)
        elif not total_present:
            total = resident + nonresident
        fields = tuple(
            value.field
            for present, value in ((total_present, total_value), (res_present, res_value), (nr_present, nr_value))
            if present and value.field
        )
        return ResidencyPermitAllocation(
            total=total,
            resident=resident,
            nonresident=nonresident,
            authority=OFFICIAL_EXPLICIT_RESIDENCY_SPLIT,
            supported=True,
            source_fields=fields,
        )

    total = max(total_value.value, 0) if total_present else 0
    if total_present and total > 0 and _uses_standard_big_game_ten_percent_rule(
        row,
        draw_system_type=draw_system_type,
    ):
        # Integer half-up rounding: 5 -> 1, 15 -> 2.  Avoid Python's bankers
        # rounding because permit allocations are discrete counts.
        nonresident = (total + 5) // 10
        return ResidencyPermitAllocation(
            total=total,
            resident=total - nonresident,
            nonresident=nonresident,
            authority=OFFICIAL_10_PERCENT_TOTAL_ALLOCATION,
            supported=True,
            source_fields=(total_value.field,),
        )

    if total_present:
        return ResidencyPermitAllocation(
            total=total,
            resident=0,
            nonresident=0,
            authority=UNSUPPORTED_TOTAL_ONLY_RESIDENCY_RULE,
            supported=False,
            source_fields=(total_value.field,),
        )

    return ResidencyPermitAllocation(
        total=0,
        resident=0,
        nonresident=0,
        authority=MISSING_TARGET_PERMIT_ALLOCATION,
        supported=False,
    )
