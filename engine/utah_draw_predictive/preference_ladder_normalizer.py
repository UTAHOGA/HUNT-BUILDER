"""Normalize collapsed preference ladder truth rows for predictive builders."""

from __future__ import annotations

from typing import Iterable, Mapping


SHARED_FIELDS = (
    "actual_draw_year",
    "source_year",
    "year",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "hunt_draw_class",
    "draw_class_type",
    "draw_system_type",
    "draw_pool",
    "draw_design",
    "draw_method",
    "metric_scope",
    "points",
    "model_strategy",
    "preference_model_valid",
    "source_dataset",
    "source_file",
    "source_years_used",
    "reason_codes",
    "weapon",
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _has_value(value: object) -> bool:
    return _clean(value) != ""


def _lane_has_data(row: Mapping[str, object], prefix: str) -> bool:
    source_residencies = _clean(row.get("source_residencies")).lower()
    if prefix == "resident" and "resident" in source_residencies and "nonresident" not in source_residencies:
        return True
    if prefix == "nonresident" and "nonresident" in source_residencies:
        return True
    return any(
        _has_value(row.get(f"{prefix}_{field}"))
        for field in (
            "eligible_applicants",
            "regular_permits",
            "total_permits",
            "p_draw",
            "p_draw_percent",
        )
    )


def _copy_shared(row: Mapping[str, object]) -> dict[str, object]:
    out = {field: row.get(field, "") for field in SHARED_FIELDS if field in row}
    if not _clean(out.get("year")):
        out["year"] = _clean(row.get("actual_draw_year") or row.get("source_year"))
    if not _clean(out.get("actual_draw_year")):
        out["actual_draw_year"] = _clean(row.get("year") or row.get("source_year"))
    if not _clean(out.get("source_year")):
        out["source_year"] = _clean(row.get("actual_draw_year") or row.get("year"))
    if not _clean(out.get("draw_pool")):
        out["draw_pool"] = "standard"
    return out


def _metric_scope_for_residency(residency: object) -> str:
    value = _clean(residency).lower().replace("-", "").replace(" ", "")
    if value in {"resident", "res", "r"}:
        return "resident"
    if value in {"nonresident", "nonres", "nr"}:
        return "nonresident"
    return "total"


def _normalize_lane(row: Mapping[str, object], residency: str, prefix: str) -> dict[str, object]:
    drawn = row.get(f"{prefix}_regular_permits") if _has_value(row.get(f"{prefix}_regular_permits")) else row.get(f"{prefix}_total_permits")
    out = _copy_shared(row)
    out.update(
        {
            "residency": residency,
            "eligible_applicants": _clean(row.get(f"{prefix}_eligible_applicants")),
            "eligible": _clean(row.get(f"{prefix}_eligible_applicants")),
            "drawn": _clean(drawn),
            "successful_applicants": _clean(drawn),
            "regular_permits": _clean(row.get(f"{prefix}_regular_permits")),
            "total_permits": _clean(row.get(f"{prefix}_total_permits")),
            "p_draw": _clean(row.get(f"{prefix}_p_draw")),
            "p_draw_pct": _clean(row.get(f"{prefix}_p_draw_percent")),
            "p_draw_percent": _clean(row.get(f"{prefix}_p_draw_percent")),
            "metric_scope": prefix,
            "source_column_mapping": prefix,
        }
    )
    return out


def _normalize_total_fallback(row: Mapping[str, object]) -> dict[str, object]:
    drawn = row.get("total_regular_permits") if _has_value(row.get("total_regular_permits")) else row.get("total_permits")
    out = _copy_shared(row)
    out.update(
        {
            "residency": "All",
            "eligible_applicants": _clean(row.get("total_eligible_applicants")),
            "eligible": _clean(row.get("total_eligible_applicants")),
            "drawn": _clean(drawn),
            "successful_applicants": _clean(drawn),
            "regular_permits": _clean(row.get("total_regular_permits")),
            "total_permits": _clean(row.get("total_permits")),
            "p_draw": _clean(row.get("total_p_draw")),
            "p_draw_pct": _clean(row.get("total_p_draw_percent")),
            "p_draw_percent": _clean(row.get("total_p_draw_percent")),
            "metric_scope": "total",
            "source_column_mapping": "total_fallback",
        }
    )
    return out


def normalize_preference_ladder_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        if _clean(row.get("residency")) and _clean(row.get("eligible_applicants")):
            out = dict(row)
            out["metric_scope"] = _clean(out.get("metric_scope")) or _metric_scope_for_residency(out.get("residency"))
            if not _clean(out.get("eligible")):
                out["eligible"] = _clean(out.get("eligible_applicants"))
            drawn = out.get("drawn") or out.get("successful_applicants") or out.get("regular_permits") or out.get("total_permits")
            if not _clean(out.get("drawn")):
                out["drawn"] = _clean(drawn)
            if not _clean(out.get("successful_applicants")):
                out["successful_applicants"] = _clean(drawn)
            if not _clean(out.get("p_draw_pct")):
                out["p_draw_pct"] = _clean(out.get("p_draw_percent"))
            if not _clean(out.get("year")):
                out["year"] = _clean(out.get("actual_draw_year") or out.get("source_year"))
            normalized.append(out)
            continue

        emitted = False
        for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            if _lane_has_data(row, prefix):
                normalized.append(_normalize_lane(row, residency, prefix))
                emitted = True

        if not emitted and any(
            _has_value(row.get(field))
            for field in ("total_eligible_applicants", "total_regular_permits", "total_permits", "total_p_draw", "total_p_draw_percent")
        ):
            normalized.append(_normalize_total_fallback(row))

    return normalized
