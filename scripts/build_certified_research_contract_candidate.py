#!/usr/bin/env python3
"""Build a non-production split Research contract from the frozen forecast.

The complete R2 review snapshot supplies the existing non-draw/reference lanes.
Frozen prediction rows replace matching forecastable rows and add any new
forecast keys.  Outputs are written only to a new audit candidate directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
REVIEW_ROOT = CANDIDATE_ROOT / "r2_review_copy_2026-08-27" / "r2_snapshot" / "processed_data"
DEFAULT_OUTPUT = CANDIDATE_ROOT / "research_split_contract_candidate_2026-08-27"
FROZEN_PREDICTION = ROOT / "processed_data" / "draw_reality_engine_predictive_v2.csv"
LOCAL_INDEX = ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json"
FROZEN_SHA256 = "9e4c0f1a66678cd63df88512e45ba71d63746a6b21d7e4038fecb142f40e9d5e"

CERTIFIED_PROBABILITY_FIELDS = {
    "certified_p_draw",
    "certified_p_draw_mean",
    "certified_p_draw_pct",
}

# These fields are retained source/reference facts in the existing public
# Research contract.  A prediction refresh may use them as inputs, but it may
# not replace or backfill them on an identity that is already public.
PROTECTED_DRAW_PERMIT_QUOTA_FIELDS = {
    "dwr_result_display",
    "display_2025_draw_results",
    "odds_2025_actual",
    "total_permits",
    "bonus_permits",
    "regular_permits",
    "public_permits_2025",
    "max_point_permits_2025",
    "random_permits_2025",
    "public_permits_2026",
    "max_point_permits_2026",
    "random_permits_2026",
    "permits_2024_res",
    "permits_2024_nr",
    "permits_2024_total",
    "permits_2024_source",
    "permits_2025_res",
    "permits_2025_nr",
    "permits_2025_total",
    "permits_2025_source",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permits_2026_source",
    "permits_2026_draw_source",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permit_allotment_2026_source",
    "permit_allotment_2026_source_file",
    "permit_allotment_2026_status",
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "quota_source_status",
    "quota_source_year",
    "quota_source_file",
}

DIRECT_DETAIL_LADDER_FIELDS = {
    "hunt_code", "hunt_name", "species", "hunt_type", "hunt_class", "weapon", "sex_type",
    "unit_name", "boundary_id", "residency", "points", "draw_pool", "year", "forecast_year",
    "draw_system_type", "draw_2026_system_type", "algorithm_status", "availability_status",
    "prediction_certification_design", "prediction_certification_status",
    "prediction_publication_status", "certified_p_draw", "certified_p_draw_mean",
    "certified_p_draw_pct", "projected_draw_line_2025", "projected_draw_line_2026",
    "applicants", "eligible_applicants", "total_permits", "bonus_permits", "regular_permits",
    "public_permits_2026", "max_point_permits_2026", "random_permits_2026",
    "permits_2026_total", "permit_allotment_2026_total", "permit_allotment_2026_source",
    "quota_source_status", "point_pool_zone", "dwr_result_display", "display_2025_draw_results",
    "gap", "delta_gap", "status", "trend", "draw_outlook", "reason", "rule_status",
    "allocation_status", "data_quality_flags",
    "source_file", "truth_source_file", "pdf_page", "source_page", "truth_source_page",
    "actual_draw_year", "source_year", "prediction_certification_registry_id",
}

# A withheld percentage must not leave a future line or advice that implies
# the same unsupported prediction. Historical actuals and permit facts remain.
FUTURE_GUIDANCE_FIELDS = {
    "projected_draw_line_2026", "point_creep", "point_trend", "draw_trend",
    "trend", "draw_outlook", "gap", "delta_gap", "point_pool_zone",
    "decision_label", "recommended_action", "catch_up_guidance",
}

# Historical actual results are intentionally not included.  These fields are
# future estimates or legacy display aliases and must never reach the public
# Research contract beside the certified publication fields above.
RAW_FUTURE_PROBABILITY_FIELDS = {
    "p_draw",
    "p_draw_mean",
    "p_draw_pct",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "p_max_pool_mean",
    "p_max_pool_mean_pct",
    "p_max_pool_pct",
    "p_random_mean",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "p_bonus_pool_pct",
    "p_random_pool_pct",
    "p_prior_year_baseline",
    "p_quota_adjusted",
    "p_rollover_adjusted",
    "p_harvest_adjusted",
    "p_preference_mean",
    "p_sportsman_draw",
    "p_availability",
    "availability_pct",
    "youth_reserve_probability",
    "youth_rollover_main_draw_probability",
    "closure_risk",
    "sellout_risk",
    "sellout_or_closure_risk",
    "display_odds_pct",
    "display_odds_text",
    "display_2026_max_point_pool",
    "display_2026_random_draw",
    "odds_2026_projected",
    "max_pool_projection_2026",
    "random_draw_odds_2026",
    "random_draw_projection_2026",
    "preference_draw_odds_2026",
    "preference_projection_2026",
    "modeled_preference_probability",
    "draw_probability",
    "guaranteed_probability",
    "projected_guaranteed_probability_pct",
    "projected_random_probability_pct",
    "projected_total_probability_pct",
    "expected_cutoff_points",
    "p50",
}

LEGACY_GUARANTEE_FIELDS = {
    "guaranteed_at_2026",
    "guaranteed_line",
    "guaranteed_line_points",
    "guaranteed_marker",
    "projected_2026_max_cutoff_point",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return clean(value).upper()


def residency(value: object) -> str:
    raw = clean(value).lower().replace("-", "").replace(" ", "")
    return {"nonresident": "Nonresident", "nr": "Nonresident", "resident": "Resident", "res": "Resident", "r": "Resident"}.get(raw, "")


def point(value: object) -> str:
    raw = clean(value)
    try:
        parsed = float(raw)
    except ValueError:
        return raw
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def draw_pool(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")
    explicit_program_lanes = {
        "youth",
        "lifetime",
        "dedicated_hunter",
        "youth_dedicated_hunter",
        "youth_mature_bull",
        "youth_turkey",
    }
    return normalized if normalized in explicit_program_lanes else "standard"


def row_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (code(row.get("hunt_code")), residency(row.get("residency")), point(row.get("points")), draw_pool(row.get("draw_pool")))


def group_key(row: dict[str, object]) -> tuple[str, str, str]:
    return row_key(row)[:2] + (draw_pool(row.get("draw_pool")),)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sanitize_public_value(value: object) -> object:
    if isinstance(value, dict):
        return sanitize_public_row(value)
    if isinstance(value, list):
        return [sanitize_public_value(item) for item in value]
    return value


def sanitize_public_row(row: dict[str, object]) -> dict[str, object]:
    if any(clean(row.get(field)) for field in CERTIFIED_PROBABILITY_FIELDS) and not residency(row.get("residency")):
        raise ValueError(f"Certified probability has no explicit residency: {row.get('hunt_code')}")
    sanitized = {
        field: sanitize_public_value(value)
        for field, value in row.items()
        if field not in RAW_FUTURE_PROBABILITY_FIELDS
        and field not in LEGACY_GUARANTEE_FIELDS
    }
    status = clean(sanitized.get("prediction_certification_status"))
    if "draw_pool" in sanitized:
        sanitized["draw_pool"] = draw_pool(sanitized.get("draw_pool"))
    if status != "CERTIFIED":
        for field in CERTIFIED_PROBABILITY_FIELDS:
            sanitized[field] = ""
    if not has_certified_forecast(sanitized):
        for field in FUTURE_GUIDANCE_FIELDS:
            sanitized.pop(field, None)
    return sanitized


def has_certified_forecast(row: dict[str, object]) -> bool:
    if clean(row.get("prediction_certification_status")) != "CERTIFIED":
        return False
    for field in ("certified_p_draw_pct", "certified_p_draw_mean", "certified_p_draw"):
        if not clean(row.get(field)):
            continue
        try:
            value = float(row[field])
        except (TypeError, ValueError):
            return False
        return math.isfinite(value) and 0 <= value <= (100 if field.endswith("_pct") else 1)
    return False


def attach_source_scopes(detail: dict[str, object]) -> dict[str, object]:
    """Label the composite; never rebrand catalog references as draw truth."""
    result = dict(detail)
    previous = detail.get("source_provenance") or {}
    catalog = previous.get("current_catalog") or {
        "source_authority": detail.get("source_authority", ""),
        "source_file": detail.get("source_file", ""),
        "role": "CURRENT_HUNT_IDENTITY_AND_PERMIT_REFERENCE_ONLY",
    }
    sources = sorted({clean(row.get(field))
                      for group in ("research_summary_rows", "research_ladder_rows")
                      for row in detail.get(group, []) if isinstance(row, dict)
                      for field in ("truth_source_file", "source_file")
                      if clean(row.get(field)) and "database.csv" not in clean(row.get(field)).lower()})
    result["source_authority"] = "FIELD_SCOPED_RESEARCH_COMPOSITE"
    result["source_file_role"] = "CURRENT_HUNT_IDENTITY_AND_PERMIT_REFERENCE_ONLY"
    result["source_provenance"] = {
        "current_catalog": catalog,
        "historical_draw_results": {
            "role": "RETAINED_ROW_LINEAGE_NOT_CURRENT_CATALOG",
            "recorded_source_files": sources,
            "lineage_status": "RECORDED_ROW_SOURCES" if sources else "NOT_PRESENT_IN_THIS_PAYLOAD",
        },
        "future_predictions": {
            "role": "CERTIFIED_SELECTED_POINT_FIELDS_ONLY",
            "artifact_sha256": detail.get("candidate_frozen_prediction_sha256", ""),
        },
        "harvest_context": {"role": "SEPARATE_CONTEXT_NOT_DRAW_PROBABILITY_OR_QUOTA"},
    }
    return result


def is_harvest_context_field(field: str) -> bool:
    return any(token in field.lower() for token in (
        "harvest", "satisfaction", "days_hunted", "management_objective", "unit_quality"
    ))


def merge_row(base: dict[str, object], prediction: dict[str, str]) -> dict[str, object]:
    """Preserve non-prediction compatibility fields and overlay certified facts."""
    merged: dict[str, object] = dict(base)
    for field, value in prediction.items():
        # This is a prediction-only release. Refreshed internal harvest
        # features are not authority to publish a separate harvest update.
        if is_harvest_context_field(field):
            continue
        if field in CERTIFIED_PROBABILITY_FIELDS or field.startswith("prediction_certification_") or field == "prediction_publication_status":
            merged[field] = value
            continue
        if field in PROTECTED_DRAW_PERMIT_QUOTA_FIELDS and field in base:
            continue
        if clean(value):
            merged[field] = value
        elif field not in merged:
            merged[field] = value
    return sanitize_public_row(merged)


def clear_retained_prediction_authority(value: object) -> object:
    """A prior release is never evidence for a newly frozen forecast.

    Keep historical draw/permit fields intact, but make every published future
    probability come from an exact current candidate key, including blanks.
    """
    if isinstance(value, list):
        return [clear_retained_prediction_authority(item) for item in value]
    if isinstance(value, dict):
        out = {field: clear_retained_prediction_authority(item) for field, item in value.items()
               if field not in CERTIFIED_PROBABILITY_FIELDS
               and not field.startswith("prediction_certification_")
               and field != "prediction_publication_status"}
        return out
    return value


def protected_field_change_count(
    base_by_key: dict[tuple[str, str, str, str], dict[str, object]],
    candidate_rows: list[dict[str, object]],
) -> int:
    candidate_by_key = {row_key(row): row for row in candidate_rows}
    changes = 0
    for identity, base in base_by_key.items():
        candidate = candidate_by_key.get(identity)
        if candidate is None:
            continue
        for field in PROTECTED_DRAW_PERMIT_QUOTA_FIELDS:
            if field in base and clean(base.get(field)) != clean(candidate.get(field)):
                changes += 1
    return changes


def protected_harvest_context_change_count(base_by_key, candidate_rows) -> int:
    by_key = {row_key(row): row for row in candidate_rows}
    return sum(
        clean(value) != clean(by_key[identity].get(field))
        for identity, base in base_by_key.items() if identity in by_key
        for field, value in base.items() if is_harvest_context_field(field)
    )


def representative(rows: list[dict[str, str]], preferred_point: str = "") -> dict[str, str]:
    if preferred_point:
        for row in rows:
            if point(row.get("points")) == preferred_point:
                return row
    def sort_key(row: dict[str, str]) -> tuple[float, str]:
        raw = point(row.get("points"))
        try:
            return (float(raw), raw)
        except ValueError:
            return (float("inf"), raw)
    return sorted(rows, key=sort_key)[0]


def union_fields(rows: list[dict[str, object]], initial: list[str]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for field in initial:
        if field not in seen:
            fields.append(field)
            seen.add(field)
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    return fields


def build(
    review_root: Path = REVIEW_ROOT,
    frozen_prediction: Path = FROZEN_PREDICTION,
    output_root: Path = DEFAULT_OUTPUT,
    local_index_path: Path = LOCAL_INDEX,
    expected_prediction_sha256: str = FROZEN_SHA256,
) -> dict[str, object]:
    if output_root.exists():
        raise RuntimeError(f"Refusing to overwrite existing candidate: {output_root}")
    if not review_root.exists():
        raise RuntimeError(f"R2 review snapshot missing: {review_root}")
    prediction_sha256 = sha256(frozen_prediction)
    if expected_prediction_sha256 and prediction_sha256 != expected_prediction_sha256:
        raise RuntimeError("The prediction CSV does not match the declared frozen hash.")

    out = output_root / "processed_data"
    summary_source = review_root / "hunt_research_2026_summary.json"
    ladder_source = review_root / "hunt_research_2026_ladder.json"
    details_source = review_root / "hunt_research_2026_split" / "hunt_research_2026.details.json"
    index_source = review_root / "hunt_research_2026_split" / "hunt_research_2026.index.json"
    point_ladder_source = review_root / "point_ladder_view.csv"
    if not point_ladder_source.exists():
        point_ladder_source = frozen_prediction
    for path in (summary_source, ladder_source, details_source, index_source, point_ladder_source, frozen_prediction, local_index_path):
        if not path.exists():
            raise RuntimeError(f"Required candidate input is missing: {path}")

    forecast_rows, forecast_fields = read_csv(frozen_prediction)
    forecast_by_key = {row_key(row): row for row in forecast_rows}
    if len(forecast_by_key) != len(forecast_rows):
        raise RuntimeError("Frozen forecast contains duplicate Research contract identity keys.")
    forecast_by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in forecast_rows:
        forecast_by_group[group_key(row)].append(row)

    summary_base = clear_retained_prediction_authority(read_json(summary_source))
    ladder_base = clear_retained_prediction_authority(read_json(ladder_source))
    details_base = clear_retained_prediction_authority(read_json(details_source))
    index_base = read_json(index_source)
    local_index = read_json(local_index_path)
    point_ladder_base, point_ladder_fields = read_csv(point_ladder_source)
    point_ladder_base = clear_retained_prediction_authority(point_ladder_base)
    if not all(isinstance(value, list) for value in (summary_base, ladder_base, index_base, local_index)) or not isinstance(details_base, dict):
        raise RuntimeError("Review snapshot has an unexpected Research contract shape.")

    summary_base_by_group: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in summary_base:
        base = dict(row)
        group = group_key(base)
        existing = summary_base_by_group.setdefault(group, base)
        if existing is not base:
            for field, value in base.items():
                if not clean(existing.get(field)) and clean(value):
                    existing[field] = value

    summary_out: list[dict[str, object]] = []
    summary_groups: set[tuple[str, str, str]] = set(summary_base_by_group)
    summary_exact_overlays = 0
    summary_group_overlays = 0
    for group, base in summary_base_by_group.items():
        key = row_key(base)
        prediction = forecast_by_key.get(key)
        if prediction:
            summary_exact_overlays += 1
        elif group in forecast_by_group:
            prediction = representative(forecast_by_group[group], point(base.get("points")))
            summary_group_overlays += 1
        summary_out.append(merge_row(base, prediction) if prediction else sanitize_public_row(base))
    for group, predictions in sorted(forecast_by_group.items()):
        if group not in summary_groups:
            summary_out.append(sanitize_public_row(dict(representative(predictions))))

    ladder_base_by_key: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for row in ladder_base:
        base = dict(row)
        row_identity = row_key(base)
        existing = ladder_base_by_key.setdefault(row_identity, base)
        if existing is not base:
            for field, value in base.items():
                if not clean(existing.get(field)) and clean(value):
                    existing[field] = value
    ladder_out: list[dict[str, object]] = []
    ladder_keys: set[tuple[str, str, str, str]] = set(ladder_base_by_key)
    ladder_overlays = 0
    for row_identity, base in ladder_base_by_key.items():
        prediction = forecast_by_key.get(row_identity)
        if prediction:
            ladder_out.append(merge_row(base, prediction))
            ladder_overlays += 1
        else:
            ladder_out.append(sanitize_public_row(base))
    ladder_appends = [sanitize_public_row(dict(row)) for key, row in forecast_by_key.items() if key not in ladder_keys]
    ladder_out.extend(ladder_appends)

    point_base_by_key: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for row in point_ladder_base:
        base = dict(row)
        row_identity = row_key(base)
        existing = point_base_by_key.setdefault(row_identity, base)
        if existing is not base:
            for field, value in base.items():
                if not clean(existing.get(field)) and clean(value):
                    existing[field] = value
    point_out: list[dict[str, object]] = []
    point_keys: set[tuple[str, str, str, str]] = set(point_base_by_key)
    point_overlays = 0
    for row_identity, base in point_base_by_key.items():
        prediction = forecast_by_key.get(row_identity)
        if prediction:
            point_out.append(merge_row(base, prediction))
            point_overlays += 1
        else:
            point_out.append(sanitize_public_row(base))
    point_appends = [sanitize_public_row(dict(row)) for key, row in forecast_by_key.items() if key not in point_keys]
    point_out.extend(point_appends)
    protected_point_field_changes = protected_field_change_count(point_base_by_key, point_out)
    protected_harvest_changes = protected_harvest_context_change_count(point_base_by_key, point_out)
    if protected_harvest_changes:
        raise RuntimeError(f"Prediction-only release changed {protected_harvest_changes} retained harvest-context cells")
    if protected_point_field_changes:
        raise RuntimeError(
            "Prediction overlay changed retained draw, permit, or quota fields "
            f"on {protected_point_field_changes} existing point-ladder cells."
        )

    point_by_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in point_out:
        hunt_code = code(row.get("hunt_code"))
        if hunt_code:
            point_by_code[hunt_code].append(
                {field: row.get(field, "") for field in sorted(DIRECT_DETAIL_LADDER_FIELDS) if clean(row.get(field))}
            )

    summary_by_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in summary_out:
        if code(row.get("hunt_code")):
            summary_by_code[code(row.get("hunt_code"))].append(row)
    detail_bundle = dict(details_base)
    # Older sanitized bundles can contain publication-field placeholders beside
    # the actual hunt-code objects.  They are container metadata, not hunt
    # details, and must never be emitted as files such as
    # ``hunts/certified_p_draw.json``.
    detail_map = {
        hunt_code: dict(detail)
        for hunt_code, detail in dict(details_base.get("details_by_hunt_code") or {}).items()
        if isinstance(detail, dict)
    }
    for hunt_code, rows in summary_by_code.items():
        existing = dict(detail_map.get(hunt_code) or {})
        existing.update(
            {
                "hunt_code": hunt_code,
                "research_summary_rows": rows,
                "research_summary_row_count": len(rows),
                "research_ladder_rows": point_by_code.get(hunt_code, []),
                "candidate_source": "FROZEN_UNIFIED_FORECAST_OVERLAY",
                "candidate_frozen_prediction_sha256": prediction_sha256,
            }
        )
        detail_map[hunt_code] = existing
    sanitized_detail_map = {
        hunt_code: attach_source_scopes(sanitize_public_row(detail))
        for hunt_code, detail in detail_map.items()
    }
    detail_bundle = {
        field: sanitize_public_value(value)
        for field, value in detail_bundle.items()
        if field != "details_by_hunt_code"
        and field not in RAW_FUTURE_PROBABILITY_FIELDS
        and field not in LEGACY_GUARANTEE_FIELDS
    }
    detail_bundle.update(
        {
            "details_by_hunt_code": sanitized_detail_map,
            "bundled_hunt_count": len(sanitized_detail_map),
            "candidate_source": "FROZEN_UNIFIED_FORECAST_OVERLAY",
            "candidate_frozen_prediction_sha256": prediction_sha256,
        }
    )

    current_index_codes = {code(row.get("hunt_code")) for row in local_index if code(row.get("hunt_code"))}
    index_by_code = {
        code(row.get("hunt_code")): dict(row)
        for row in index_base
        if code(row.get("hunt_code")) in current_index_codes
    }
    for row in local_index:
        hunt_code = code(row.get("hunt_code"))
        if hunt_code:
            index_by_code[hunt_code] = {**index_by_code.get(hunt_code, {}), **dict(row)}
    for hunt_code, rows in summary_by_code.items():
        if hunt_code not in current_index_codes:
            continue
        representative_row = representative([{key: clean(value) for key, value in row.items()} for row in rows])
        index_row = index_by_code.get(hunt_code, {"hunt_code": hunt_code})
        for field in ("hunt_name", "species", "hunt_type", "hunt_class", "weapon", "sex_type", "draw_2026_system_type", "availability_status"):
            if not clean(index_row.get(field)) and clean(representative_row.get(field)):
                index_row[field] = representative_row[field]
        index_row["research_summary_row_count"] = len(rows)
        index_row["detail_path"] = f"hunts/{hunt_code}.json"
        index_by_code[hunt_code] = index_row
    index_out = [sanitize_public_row(index_by_code[hunt_code]) for hunt_code in sorted(index_by_code)]

    write_json(out / "hunt_research_2026_summary.json", summary_out)
    write_json(out / "hunt_research_2026_ladder.json", ladder_out)
    write_json(out / "hunt_research_2026_split" / "hunt_research_2026.index.json", index_out)
    write_json(out / "hunt_research_2026_split" / "hunt_research_2026.details.json", detail_bundle)
    detail_dir = out / "hunt_research_2026_split" / "hunts"
    for hunt_code, detail in sorted(sanitized_detail_map.items()):
        write_json(detail_dir / f"{hunt_code}.json", detail)
    write_csv(out / "point_ladder_view.csv", point_out, union_fields(point_out, point_ladder_fields + forecast_fields))
    def public_forecast_overlay(legacy_name: str) -> tuple[list[dict[str, object]], list[str]]:
        legacy_rows, legacy_fields = read_csv(review_root / legacy_name)
        legacy_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for legacy_row in legacy_rows:
            legacy_by_key.setdefault(row_key(legacy_row), legacy_row)
        rows = [merge_row(legacy_by_key.get(row_key(row), {}), row) for row in forecast_rows]
        fields = [
            field
            for field in union_fields(rows, legacy_fields + forecast_fields)
            if field not in RAW_FUTURE_PROBABILITY_FIELDS and field not in LEGACY_GUARANTEE_FIELDS
        ]
        return rows, fields

    public_predictive_rows, public_predictive_fields = public_forecast_overlay("draw_reality_engine_predictive_v2.csv")
    public_ml_rows, public_ml_fields = public_forecast_overlay("ml_draw_predictions_v1.csv")
    write_csv(out / "draw_reality_engine_predictive_v2.csv", public_predictive_rows, public_predictive_fields)
    write_csv(out / "ml_draw_predictions_v1.csv", public_ml_rows, public_ml_fields)

    candidate_paths = {
        "summary": out / "hunt_research_2026_summary.json",
        "ladder": out / "hunt_research_2026_ladder.json",
        "index": out / "hunt_research_2026_split" / "hunt_research_2026.index.json",
        "details": out / "hunt_research_2026_split" / "hunt_research_2026.details.json",
        "point_ladder": out / "point_ladder_view.csv",
        "predictive_runtime": out / "draw_reality_engine_predictive_v2.csv",
        "ml_predictions_runtime": out / "ml_draw_predictions_v1.csv",
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    audit = {
        "schema_version": "1.0.0",
        "generated_at_utc": timestamp,
        "mode": "LOCAL_CANDIDATE_NO_PROCESSED_DATA_OR_R2_WRITE",
        "frozen_prediction": {
            "path": str(frozen_prediction.relative_to(ROOT)).replace("\\", "/"),
            "sha256": prediction_sha256,
            "rows": len(forecast_rows),
            "fields": len(forecast_fields),
        },
        "overlay": {
            "summary_exact_overlays": summary_exact_overlays,
            "summary_group_overlays": summary_group_overlays,
            "summary_new_groups": len(summary_out) - len(summary_base_by_group),
            "summary_duplicate_public_groups_collapsed": len(summary_base) - len(summary_base_by_group),
            "ladder_exact_overlays": ladder_overlays,
            "ladder_new_rows": len(ladder_appends),
            "ladder_duplicate_public_identities_collapsed": len(ladder_base) - len(ladder_base_by_key),
            "point_ladder_exact_overlays": point_overlays,
            "point_ladder_new_rows": len(point_appends),
            "point_ladder_duplicate_public_identities_collapsed": len(point_ladder_base) - len(point_base_by_key),
            "preserved_reference_rows": len(ladder_base) - ladder_overlays,
            "current_index_hunt_codes": len(current_index_codes),
            "summary_only_historical_reference_codes": len(set(summary_by_code) - current_index_codes),
            "split_detail_files": len(detail_map),
            "split_detail_ladder_rows": sum(len(rows) for rows in point_by_code.values()),
            "probability_contract": "CERTIFIED_P_DRAW_FIELDS_ONLY",
            "protected_draw_permit_quota_field_changes": protected_point_field_changes,
            "protected_draw_permit_quota_fields_unchanged": protected_point_field_changes == 0,
            "protected_harvest_context_field_changes": protected_harvest_changes,
            "removed_raw_future_probability_fields": sorted(RAW_FUTURE_PROBABILITY_FIELDS),
            "removed_legacy_guarantee_fields": sorted(LEGACY_GUARANTEE_FIELDS),
        },
        "outputs": {
            label: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for label, path in candidate_paths.items()
        },
    }
    write_json(output_root / "candidate_build_audit.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-root", type=Path, default=REVIEW_ROOT)
    parser.add_argument("--prediction", type=Path, default=FROZEN_PREDICTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--local-index", type=Path, default=LOCAL_INDEX)
    parser.add_argument("--expected-prediction-sha256", default=FROZEN_SHA256)
    args = parser.parse_args()
    resolve = lambda path: path if path.is_absolute() else ROOT / path
    output = resolve(args.output)
    result = build(
        review_root=resolve(args.review_root),
        frozen_prediction=resolve(args.prediction),
        output_root=output,
        local_index_path=resolve(args.local_index),
        expected_prediction_sha256=args.expected_prediction_sha256,
    )
    print("CERTIFIED_RESEARCH_CONTRACT_CANDIDATE=PASS")
    print(f"OUTPUT={output.relative_to(ROOT)}")
    print(json.dumps(result["overlay"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
