"""Run Utah draw predictive families for a source-year/target-year pair."""

from __future__ import annotations

import argparse
import csv
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .dedicated_hunter import build_preference_dedicated_hunter_predictions
from .permit_accessors import target_permit_total
from .preference_antlerless import build_preference_antlerless_predictions
from .preference_general_deer import build_preference_general_deer_predictions
from .preference_ladder_normalizer import normalize_preference_ladder_rows
from .sportsman import build_sportsman_predictions


REPO = Path(__file__).resolve().parents[2]
TRUTH_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUTHORITY_PATH = REPO / "data_truth" / "crosswalk_truth" / "normalized" / "hunt_code_crosswalk_authority_2020_2026.csv"
MODELED_FAMILIES = (
    "preference_general_deer",
    "dedicated_hunter",
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
)

AUTHORITY_TO_FAMILY = {
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER": "preference_general_deer",
    "PREFERENCE_DEDICATED_HUNTER_DEER": "preference_dedicated_hunter_deer",
    "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
    "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
    "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
}
PREFERENCE_DRAW_SYSTEM_TYPES = set(AUTHORITY_TO_FAMILY)
AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES = {
    "ANTLERLESS_ELK_CONTROL",
    "AVAILABILITY_ONLY",
    "BEAR_HARVEST_OBJECTIVE",
    "BEAR_PURSUIT_ONLY",
    "BEAR_RESTRICTED_PURSUIT",
    "COUGAR_LICENSE_BASED",
    "CWMU_PRIVATE_VOUCHER",
    "FURBEARER_TAG_OR_LICENSE_ONLY",
    "GUARANTEED_LIFETIME_PERMIT",
    "OTC_CAPPED",
    "OTC_UNLIMITED",
    "PRIVATE_LANDS_ONLY",
    "PTARMIGAN_FREE_AVAILABILITY",
    "REFERENCE_ONLY",
    "TURKEY_CONTROL_VOUCHER",
    "TURKEY_CWMU",
    "TURKEY_FALL_MANAGEMENT",
}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _to_int(value: object) -> int | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _to_number(value: object) -> float:
    text = _clean(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def _best_number(row: Mapping[str, object], *fields: str) -> float:
    for field in fields:
        value = _to_number(row.get(field))
        if value > 0:
            return value
    return 0.0


def _row_year(row: Mapping[str, object]) -> int | None:
    for key in ("actual_draw_year", "source_year", "draw_year", "year"):
        value = _to_int(row.get(key))
        if value is not None:
            return value
    return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


@lru_cache(maxsize=1)
def _crosswalk_authority_by_year_code() -> dict[tuple[int, str], dict[str, str]]:
    if not AUTHORITY_PATH.exists():
        return {}

    priority = {
        "GUIDEBOOK_AUTHORITY": 0,
        "SOURCE_BACKED": 1,
        "SOURCE_BACKED_NOT_IN_LEGACY_CROSSWALK": 2,
        "AUDIT_DERIVED": 3,
    }
    authority: dict[tuple[int, str], dict[str, str]] = {}
    with AUTHORITY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            hunt_code = _clean(raw.get("hunt_code")).upper()
            draw_system_type = _clean(raw.get("draw_system_type")).upper()
            if not hunt_code or not draw_system_type:
                continue
            year = None
            for year_field in ("source_year", "actual_draw_year", "hunt_year"):
                year = _to_int(raw.get(year_field))
                if year is not None:
                    break
            if year is None:
                continue
            key = (year, hunt_code)
            current = authority.get(key)
            if current is None or priority.get(_clean(raw.get("authority_status")).upper(), 99) < priority.get(
                _clean(current.get("authority_status")).upper(),
                99,
            ):
                authority[key] = dict(raw)
    return authority


def _authority_row_for_legacy_row(row: Mapping[str, object]) -> dict[str, str] | None:
    hunt_code = _clean(row.get("hunt_code")).upper()
    year = _row_year(row)
    if not hunt_code or year is None:
        return None
    return _crosswalk_authority_by_year_code().get((year, hunt_code))


def _authority_family_for_legacy_row(row: Mapping[str, object]) -> str | None:
    authority = _authority_row_for_legacy_row(row)
    if not authority:
        return None
    draw_system_type = _clean(authority.get("draw_system_type")).upper()
    if draw_system_type in AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES:
        return ""
    return AUTHORITY_TO_FAMILY.get(draw_system_type)


def _authority_draw_system_type_for_legacy_row(row: Mapping[str, object]) -> str:
    authority = _authority_row_for_legacy_row(row)
    return _clean(authority.get("draw_system_type")).upper() if authority else ""


def _fieldnames(rows: Sequence[Mapping[str, object]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields or ["no_rows"]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _family_for_legacy_row(row: Mapping[str, object]) -> str:
    authority_family = _authority_family_for_legacy_row(row)
    if authority_family is not None:
        return authority_family

    model_strategy = _clean(row.get("model_strategy"))
    draw_system_type = _clean(row.get("draw_system_type"))
    hunt_code = _clean(row.get("hunt_code")).upper()
    if draw_system_type in {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL"}:
        return ""
    if model_strategy in {
        "preference_general_deer",
        "preference_antlerless_deer",
        "preference_antlerless_elk",
        "preference_doe_pronghorn",
        "preference_dedicated_hunter_deer",
    }:
        return model_strategy
    if model_strategy == "preference_antlerless":
        return {
            "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
            "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
            "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
        }.get(draw_system_type, "")
    if model_strategy == "preference_dedicated_hunter_deer":
        return "preference_dedicated_hunter_deer"
    if draw_system_type:
        mapped_draw_system = {
            "PREFERENCE_GENERAL_SEASON_BUCK_DEER": "preference_general_deer",
            "PREFERENCE_DEDICATED_HUNTER_DEER": "preference_dedicated_hunter_deer",
            "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
            "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
            "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
        }.get(draw_system_type, "")
        if mapped_draw_system:
            return mapped_draw_system

    hunt_class = _clean(row.get("hunt_class")).upper()
    hunt_draw_class = _clean(row.get("hunt_draw_class") or row.get("draw_class_type")).upper()
    effective_hunt_class = hunt_draw_class or hunt_class
    species = _clean(row.get("species")).lower()
    sex_type = _clean(row.get("sex_type")).lower()
    hunt_type = _clean(row.get("hunt_type")).lower()
    draw_design = _clean(row.get("draw_design")).lower()

    draw_design_system = draw_design.upper()
    is_preference = draw_design == "preference" or draw_design_system in PREFERENCE_DRAW_SYSTEM_TYPES or hunt_class == "PREFERENCE"
    if not is_preference:
        return ""
    if effective_hunt_class == "GENERAL_SEASON_DEER" and species == "deer" and hunt_code.startswith("DB") and not hunt_code.startswith(("DB17", "DB18")):
        return "preference_general_deer"
    if hunt_code.startswith(("DB15", "DB16")) and species == "deer":
        return "preference_general_deer"
    if effective_hunt_class == "DEDICATED_HUNTER_DEER" and species == "deer" and sex_type == "buck":
        return "preference_dedicated_hunter_deer"
    if effective_hunt_class == "ANTLERLESS_DEER" and species == "deer":
        return "preference_antlerless_deer"
    if effective_hunt_class == "ANTLERLESS_ELK" and species == "elk":
        return "preference_antlerless_elk"
    if effective_hunt_class == "DOE_PRONGHORN" and species == "pronghorn":
        return "preference_doe_pronghorn"
    if hunt_code.startswith("DA") and species == "deer":
        return "preference_antlerless_deer"
    if hunt_code.startswith("EA") and species == "elk":
        return "preference_antlerless_elk"
    if hunt_code.startswith("PD") and species == "pronghorn":
        return "preference_doe_pronghorn"
    if "dedicated hunter" in hunt_type and species == "deer" and sex_type == "buck":
        return "preference_dedicated_hunter_deer"
    return ""


def _family_match(row: Mapping[str, object], family: str) -> bool:
    legacy_family = _family_for_legacy_row(row)
    if family == "dedicated_hunter":
        return legacy_family == "preference_dedicated_hunter_deer"
    return legacy_family == family


def _draw_system_for_family(family: str) -> str:
    return {
        "preference_general_deer": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "preference_dedicated_hunter_deer": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "preference_antlerless_deer": "PREFERENCE_ANTLERLESS_DEER",
        "preference_antlerless_elk": "PREFERENCE_ANTLERLESS_ELK",
        "preference_doe_pronghorn": "PREFERENCE_DOE_PRONGHORN",
    }.get(family, "")


def _runner_strategy_for_family(family: str) -> str:
    if family in {"preference_antlerless_deer", "preference_antlerless_elk", "preference_doe_pronghorn"}:
        return "preference_antlerless"
    return family


def _render_odds_text(probability: float) -> str:
    if probability <= 0:
        return "No modeled chance"
    capped = min(1.0, max(0.0, probability))
    pct = capped * 100.0
    if capped >= 0.999:
        return f"~1 in 1 or {pct:.1f}%"
    denominator = 1.0 / capped
    denominator_text = f"{denominator:.1f}".rstrip("0").rstrip(".") if denominator < 10 else str(round(denominator))
    pct_text = f"{pct:.1f}".rstrip("0").rstrip(".")
    return f"~1 in {denominator_text} or {pct_text}%"


def _family_draw_system(family: str) -> str:
    if family == "dedicated_hunter":
        return "PREFERENCE_DEDICATED_HUNTER_DEER"
    return _draw_system_for_family(family)


def _aggregate_target_permits(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], dict[str, float]]:
    aggregates: dict[tuple[str, str], dict[str, float]] = {}
    seen_point_rows: set[tuple[str, str, str]] = set()
    for row in rows:
        family = _family_for_legacy_row(row)
        hunt_code = _clean(row.get("hunt_code")).upper()
        points = _clean(row.get("points"))
        if not family or not hunt_code or (family, hunt_code, points) in seen_point_rows:
            continue
        seen_point_rows.add((family, hunt_code, points))
        key = (family, hunt_code)
        aggregate = aggregates.setdefault(key, {"res": 0.0, "nr": 0.0, "total": 0.0})
        res = _best_number(row, "resident_regular_permits", "resident_total_permits")
        nr = _best_number(row, "nonresident_regular_permits", "nonresident_total_permits")
        total = _best_number(row, "total_regular_permits", "total_permits")
        aggregate["res"] += res
        aggregate["nr"] += nr
        aggregate["total"] += total if total > 0 else res + nr
    return aggregates


def _with_historical_target_metadata(
    rows: Sequence[Mapping[str, object]],
    source_year: int,
    target_year: int,
) -> list[dict[str, object]]:
    aggregates = _aggregate_target_permits(rows)
    enriched: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        family = _family_for_legacy_row(item)
        hunt_code = _clean(item.get("hunt_code")).upper()
        if not family or not hunt_code:
            authority_draw_system_type = _authority_draw_system_type_for_legacy_row(item)
            if authority_draw_system_type:
                item["draw_system_type"] = authority_draw_system_type
                item["authority_excluded_from_public_draw_odds"] = str(
                    authority_draw_system_type in AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES
                ).upper()
            enriched.append(item)
            continue

        draw_system_type = _draw_system_for_family(family)
        aggregate = aggregates.get((family, hunt_code), {})
        item["model_strategy"] = _runner_strategy_for_family(family)
        item["draw_system_type"] = draw_system_type
        item["preference_model_valid"] = "TRUE"
        item["target_permits_total"] = int(round(aggregate.get("total", 0.0)))
        item["target_permits_res"] = int(round(aggregate.get("res", 0.0)))
        item["target_permits_nr"] = int(round(aggregate.get("nr", 0.0)))
        item["target_permits_source"] = (
            f"source_year_{source_year}_split_truth_columns_for_target_{target_year}"
        )
        item["source_column_mapping"] = (
            "resident_regular_permits|resident_total_permits|"
            "nonresident_regular_permits|nonresident_total_permits|"
            "total_regular_permits|total_permits"
        )
        if family == "preference_dedicated_hunter_deer":
            item["draw_pool"] = _clean(item.get("draw_pool")) or "dedicated_hunter"
            item["weapon"] = "Any Legal Weapon"
            item["hunt_type"] = "General Season"
            item["hunt_class"] = "Dedicated Hunter"
            item["sex_type"] = "Buck"
        elif family == "preference_general_deer":
            item["draw_pool"] = "standard"
            item["hunt_type"] = "General Season"
            item["sex_type"] = "Buck"
            if not _clean(item.get("hunt_class")):
                item["hunt_class"] = "GENERAL_SEASON_DEER"
        elif family in {"preference_antlerless_deer", "preference_antlerless_elk", "preference_doe_pronghorn"}:
            item["draw_pool"] = "standard"
            item["hunt_type"] = _clean(item.get("hunt_type")) or "General Season"
            item["sex_type"] = "Doe" if family == "preference_doe_pronghorn" else "Antlerless"
        elif not _clean(item.get("draw_pool")):
            item["draw_pool"] = "standard"
        enriched.append(item)
    return enriched


def _with_run_fields(rows: Iterable[Mapping[str, object]], source_year: int, target_year: int, family: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        is_sportsman = family == "sportsman"
        item["source_year"] = source_year
        item["target_year"] = target_year
        item["prediction_year"] = target_year
        item["family"] = family
        item["engine_family"] = "SPORTSMAN_RANDOM_ONLY" if is_sportsman else family
        item["draw_system_type"] = _clean(item.get("draw_system_type")) or _family_draw_system(family)
        item["draw_design"] = _clean(item.get("draw_design")) or item["draw_system_type"]
        item["draw_method"] = _clean(item.get("draw_method")) or ("Strict random" if is_sportsman else "Preference")
        item["point_system"] = _clean(item.get("point_system")) or ("none" if is_sportsman else "preference")
        item["algorithm_status"] = _clean(item.get("algorithm_status")) or ("MODELED_SPORTSMAN_DRAW" if is_sportsman else "MODELED_PREFERENCE")
        item["prediction_status"] = _clean(item.get("prediction_status")) or "MODELED"
        item["classification_status"] = _clean(item.get("classification_status")) or ("MODELED_SPORTSMAN_DRAW" if is_sportsman else "MODELED_PREFERENCE")
        item["reason_codes"] = _clean(item.get("reason_codes")) or ("FAMILY_ENGINE_MODELED_SPORTSMAN_RANDOM_ONLY" if is_sportsman else "FAMILY_ENGINE_MODELED_PREFERENCE")
        probability = _to_number(item.get("p_draw") or item.get("p_preference_draw") or item.get("p_draw_mean"))
        item["p_draw_mean"] = _clean(item.get("p_draw_mean")) or f"{probability:.6f}"
        item["p_draw_p10"] = _clean(item.get("p_draw_p10")) or f"{probability if is_sportsman else max(0.0, probability - 0.05):.6f}"
        item["p_draw_p50"] = _clean(item.get("p_draw_p50")) or f"{probability:.6f}"
        item["p_draw_p90"] = _clean(item.get("p_draw_p90")) or f"{probability if is_sportsman else min(1.0, probability + 0.05):.6f}"
        item["display_odds_pct"] = _clean(item.get("display_odds_pct")) or f"{probability * 100.0:.3f}"
        item["display_odds_text"] = _clean(item.get("display_odds_text")) or (_clean(item.get("sportsman_odds_text")) if is_sportsman else _render_odds_text(probability))
        item["public_permits_target"] = _clean(item.get("public_permits_target")) or _clean(item.get("public_permits_2026"))
        item["public_permits_source"] = _clean(item.get("public_permits_source")) or (
            f"source_year_{source_year}_sportsman_raw_draw_results" if is_sportsman else f"source_year_{source_year}_split_truth_columns_for_target_{target_year}"
        )
        out.append(item)
    return out


def _sample_values(rows: Sequence[Mapping[str, object]], key: str, limit: int = 5) -> str:
    values: list[str] = []
    for row in rows:
        value = _clean(row.get(key))
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def _sample_columns_present(rows: Sequence[Mapping[str, object]], limit: int = 24) -> str:
    columns: list[str] = []
    for row in rows[:25]:
        for key, value in row.items():
            if key not in columns and _clean(value):
                columns.append(key)
            if len(columns) >= limit:
                return ";".join(columns)
    return ";".join(columns)


def _sample_hunt_draw_class(rows: Sequence[Mapping[str, object]], limit: int = 5) -> str:
    values: list[str] = []
    for row in rows:
        value = "|".join(
            part
            for part in (
                _clean(row.get("hunt_class")),
                _clean(row.get("draw_design")),
                _clean(row.get("hunt_type")),
                _clean(row.get("sex_type")),
            )
            if part
        )
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def _trace_row(
    source_year: int,
    target_year: int,
    family: str,
    stage: str,
    rows_before: int,
    rows_after: int,
    sample_rows: Sequence[Mapping[str, object]],
    blocker: str = "",
    notes: str = "",
) -> dict[str, object]:
    return {
        "source_year": source_year,
        "target_year": target_year,
        "family": family,
        "stage": stage,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "dropped_rows": max(rows_before - rows_after, 0),
        "blocker": blocker,
        "sample_hunt_codes": _sample_values(sample_rows, "hunt_code"),
        "sample_source_years": _sample_values(sample_rows, "source_year"),
        "sample_actual_draw_years": _sample_values(sample_rows, "actual_draw_year"),
        "sample_hunt_draw_class": _sample_hunt_draw_class(sample_rows),
        "sample_source_dataset": _sample_values(sample_rows, "source_dataset"),
        "sample_columns_present": _sample_columns_present(sample_rows),
        "notes": notes,
    }


def _family_rows(rows: Sequence[Mapping[str, object]], family: str) -> list[dict[str, object]]:
    return [dict(row) for row in rows if _family_match(row, family)]


def _normalized_family_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return normalize_preference_ladder_rows(rows)


def _permit_ok_rows(rows: Sequence[Mapping[str, object]], target_year: int, source_year: int) -> list[dict[str, object]]:
    return [dict(row) for row in rows if target_permit_total(row, target_year, source_year=source_year).value > 0]


def _joined_target_rows(
    target_rows: Sequence[Mapping[str, object]],
    normalized_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    source_codes = {_clean(row.get("hunt_code")).upper() for row in normalized_rows if _clean(row.get("hunt_code"))}
    return [dict(row) for row in target_rows if _clean(row.get("hunt_code")).upper() in source_codes]


def _prefix_family_guess(row: Mapping[str, object]) -> str:
    if _clean(row.get("draw_system_type")) in {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL"}:
        return ""
    hunt_code = _clean(row.get("hunt_code")).upper()
    species = _clean(row.get("species")).lower()
    draw_design = _clean(row.get("draw_design")).lower()
    hunt_class = _clean(row.get("hunt_class")).upper()
    if draw_design != "preference" and draw_design.upper() not in PREFERENCE_DRAW_SYSTEM_TYPES and hunt_class != "PREFERENCE":
        return ""
    if hunt_code.startswith(("DB15", "DB16")) and species == "deer":
        return "preference_general_deer"
    if hunt_code.startswith("DB17") and species == "deer":
        return "dedicated_hunter"
    if hunt_code.startswith("DA") and species == "deer":
        return "preference_antlerless_deer"
    if hunt_code.startswith("EA") and species == "elk":
        return "preference_antlerless_elk"
    if hunt_code.startswith("PD") and species == "pronghorn":
        return "preference_doe_pronghorn"
    return ""


def _census_rows(
    rows: Sequence[Mapping[str, object]],
    source_year: int,
    target_year: int,
    census_type: str,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str, str, str, str], dict[str, object]] = {}
    for row in rows:
        family = _family_for_legacy_row(row) or _prefix_family_guess(row) or "unclassified"
        key = (
            family,
            _clean(row.get("hunt_code")).upper()[:2],
            _clean(row.get("hunt_class")),
            _clean(row.get("draw_design")),
            _clean(row.get("species")),
            _clean(row.get("sex_type")),
            _clean(row.get("hunt_type")),
            _clean(row.get("source_dataset")),
        )
        item = grouped.setdefault(
            key,
            {
                "source_year": source_year,
                "target_year": target_year,
                "census_type": census_type,
                "family": family,
                "hunt_code_prefix": key[1],
                "hunt_class": key[2],
                "draw_design": key[3],
                "species": key[4],
                "sex_type": key[5],
                "hunt_type": key[6],
                "source_dataset": key[7],
                "row_count": 0,
                "sample_hunt_codes": [],
            },
        )
        item["row_count"] = int(item["row_count"]) + 1
        sample = item["sample_hunt_codes"]
        hunt_code = _clean(row.get("hunt_code")).upper()
        if hunt_code and hunt_code not in sample and len(sample) < 5:
            sample.append(hunt_code)
    out: list[dict[str, object]] = []
    for item in grouped.values():
        item = dict(item)
        item["sample_hunt_codes"] = ";".join(item["sample_hunt_codes"])
        out.append(item)
    return sorted(out, key=lambda row: (str(row["family"]), str(row["hunt_code_prefix"]), str(row["hunt_class"]), str(row["sex_type"])))


def _family_filter_diagnosis_rows(
    source_year: int,
    target_year: int,
    source_rows: Sequence[Mapping[str, object]],
    engine_rows: Sequence[Mapping[str, object]],
    family_metrics: Mapping[str, Mapping[str, object]],
    modeled: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family in MODELED_FAMILIES:
        prefix_rows = [row for row in source_rows if _prefix_family_guess(row) == family]
        mapped_rows = _family_rows(source_rows, family)
        metrics = family_metrics.get(family, {})
        prediction_rows = modeled.get(family, [])
        if prediction_rows:
            diagnosis = "PASS"
        elif prefix_rows and not mapped_rows:
            diagnosis = "LEGACY_LABEL_MAPPING_GAP"
        elif mapped_rows and not metrics.get("permit_rows"):
            diagnosis = "NO_TARGET_PERMITS"
        elif mapped_rows and not metrics.get("joined_rows"):
            diagnosis = "NO_SOURCE_TARGET_JOIN"
        else:
            diagnosis = "NO_SOURCE_FAMILY_ROWS"
        rows.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "source_rows": len(mapped_rows),
                "prefix_candidate_rows": len(prefix_rows),
                "normalized_ladder_rows": len(metrics.get("normalized_rows", [])),
                "target_rows": len(metrics.get("family_target_rows", [])),
                "permit_accessor_rows_ok": len(metrics.get("permit_rows", [])),
                "joined_source_target_rows": len(metrics.get("joined_rows", [])),
                "prediction_rows": len(prediction_rows),
                "diagnosis": diagnosis,
                "sample_prefix_hunt_codes": _sample_values(prefix_rows, "hunt_code"),
                "sample_mapped_hunt_codes": _sample_values(mapped_rows, "hunt_code"),
                "notes": (
                    "2021 source labels can encode family by hunt-code prefix while hunt_class/sex_type are generic."
                    if source_year == 2021
                    else ""
                ),
            }
        )
    return rows


def _leakage_row(source_year: int, target_year: int, family: str, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    future_year_detected = False
    current_year_authority_file_used = False
    hardcoded_2026_field_required = False
    source_years_used: set[str] = set()

    for row in rows:
        for part in _clean(row.get("source_years_used")).split(","):
            part = part.strip()
            if not part:
                continue
            source_years_used.add(part)
            year = _to_int(part)
            if year is not None and year > source_year:
                future_year_detected = True
        source_file = _clean(row.get("source_file") or row.get("quota_source_file") or row.get("permit_allotment_2026_source_file"))
        if target_year != 2026 and "2026" in source_file:
            current_year_authority_file_used = True
        if target_year != 2026 and _clean(row.get("permit_source_field")).startswith("permits_2026"):
            hardcoded_2026_field_required = True

    return {
        "source_year": source_year,
        "target_year": target_year,
        "family": family,
        "source_years_used": ";".join(sorted(source_years_used)),
        "future_year_detected": str(future_year_detected).lower(),
        "current_year_authority_file_used": str(current_year_authority_file_used).lower(),
        "hardcoded_2026_field_required": str(hardcoded_2026_field_required).lower(),
        "leakage_status": "FAIL" if future_year_detected or current_year_authority_file_used or hardcoded_2026_field_required else "PASS",
    }


def run_all_families(source_year: int, target_year: int, audit_dir: Path, truth_path: Path = TRUTH_PATH) -> dict[str, object]:
    all_truth_rows = _read_csv(truth_path)
    source_rows = [row for row in all_truth_rows if _row_year(row) == source_year]
    engine_rows = _with_historical_target_metadata(source_rows, source_year, target_year)
    history_years = [source_year]

    general_rows = _with_run_fields(
        build_preference_general_deer_predictions(engine_rows, engine_rows, target_year, history_years),
        source_year,
        target_year,
        "preference_general_deer",
    )
    antlerless_all = build_preference_antlerless_predictions(engine_rows, engine_rows, target_year, history_years)
    antlerless_deer_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_ANTLERLESS_DEER"],
        source_year,
        target_year,
        "preference_antlerless_deer",
    )
    antlerless_elk_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_ANTLERLESS_ELK"],
        source_year,
        target_year,
        "preference_antlerless_elk",
    )
    doe_pronghorn_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_DOE_PRONGHORN"],
        source_year,
        target_year,
        "preference_doe_pronghorn",
    )
    dedicated_rows = _with_run_fields(
        build_preference_dedicated_hunter_predictions(engine_rows, engine_rows, target_year, history_years),
        source_year,
        target_year,
        "dedicated_hunter",
    )
    sportsman_rows, sportsman_report = build_sportsman_predictions(engine_rows, engine_rows, target_year, history_years)
    sportsman_rows = _with_run_fields(sportsman_rows, source_year, target_year, "sportsman")

    modeled = {
        "preference_general_deer": general_rows,
        "dedicated_hunter": dedicated_rows,
        "preference_antlerless_deer": antlerless_deer_rows,
        "preference_antlerless_elk": antlerless_elk_rows,
        "preference_doe_pronghorn": doe_pronghorn_rows,
        "sportsman": sportsman_rows,
    }
    deferred_families = {
        "bonus_bear": "DEFERRED_WITH_REASON: bear target-year source selection is still under repair",
        "youth_turkey": "DEFERRED_WITH_REASON: youth turkey historical target-year runner wiring is not promoted",
        "youth_draw": "DEFERRED_WITH_REASON: youth draw historical target-year runner wiring is not promoted",
    }

    audit_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir = audit_dir / "predictions"
    counts: list[dict[str, object]] = []
    leakage: list[dict[str, object]] = []
    trace: list[dict[str, object]] = []
    all_prediction_rows: list[dict[str, object]] = []
    family_metrics: dict[str, dict[str, object]] = {}

    for family in MODELED_FAMILIES:
        family_truth_rows = _family_rows(source_rows, family)
        normalized_rows = _normalized_family_rows(family_truth_rows)
        family_target_rows = _family_rows(engine_rows, family)
        permit_rows = _permit_ok_rows(family_target_rows, target_year, source_year)
        joined_rows = _joined_target_rows(permit_rows, normalized_rows)
        prediction_rows = modeled.get(family, [])
        blocker = "" if prediction_rows else "NO_ROWS"
        family_metrics[family] = {
            "family_truth_rows": family_truth_rows,
            "normalized_rows": normalized_rows,
            "family_target_rows": family_target_rows,
            "permit_rows": permit_rows,
            "joined_rows": joined_rows,
        }
        trace.extend(
            [
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_truth_rows",
                    0,
                    len(all_truth_rows),
                    all_truth_rows,
                    notes=f"Loaded truth file {truth_path}",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_source_year_rows",
                    len(all_truth_rows),
                    len(source_rows),
                    source_rows,
                    blocker="" if source_rows else "NO_SOURCE_YEAR_ROWS",
                    notes="Uses actual_draw_year/source_year/draw_year/year fallback.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_family_truth_rows",
                    len(source_rows),
                    len(family_truth_rows),
                    family_truth_rows,
                    blocker="" if family_truth_rows else "NO_FAMILY_SOURCE_ROWS",
                    notes="Uses model_strategy/draw_system_type when present; otherwise legacy hunt_class/species/draw_design mapping.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "normalize_ladder_rows",
                    len(family_truth_rows),
                    len(normalized_rows),
                    normalized_rows,
                    blocker="" if normalized_rows else "NO_NORMALIZED_LADDER_ROWS",
                    notes="Uses split resident/nonresident eligible, permit, and p_draw columns; no eligibility default.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_target_rows",
                    0,
                    len(engine_rows),
                    engine_rows,
                    notes="Historical target rows are in-memory source rows enriched with target_permits_* from split truth columns.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_target_year_rows",
                    len(engine_rows),
                    len(engine_rows),
                    engine_rows,
                    notes="No future target-year authority required for historical validation.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_family_target_rows",
                    len(engine_rows),
                    len(family_target_rows),
                    family_target_rows,
                    blocker="" if family_target_rows else "NO_FAMILY_TARGET_ROWS",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "permit_accessor_rows_ok",
                    len(family_target_rows),
                    len(permit_rows),
                    permit_rows,
                    blocker="" if permit_rows else "NO_TARGET_PERMITS",
                    notes="Uses target_permits_* or source-year fields through target-year-aware accessor; no 2026 requirement for non-2026 targets.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "join_source_to_target",
                    len(permit_rows),
                    len(joined_rows),
                    joined_rows,
                    blocker="" if joined_rows else "NO_SOURCE_TARGET_CODE_JOIN",
                    notes="Joined by hunt_code after normalization.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "build_predictions",
                    len(joined_rows),
                    len(prediction_rows),
                    prediction_rows,
                    blocker=blocker,
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "write_family_output",
                    len(prediction_rows),
                    len(prediction_rows),
                    prediction_rows,
                    blocker=blocker,
                ),
            ]
        )

    family_metrics["sportsman"] = {
        "family_truth_rows": sportsman_rows,
        "normalized_rows": sportsman_rows,
        "family_target_rows": sportsman_rows,
        "permit_rows": sportsman_rows,
        "joined_rows": sportsman_rows,
    }
    trace.extend(
        [
            _trace_row(
                source_year,
                target_year,
                "sportsman",
                "load_historical_sportsman_source",
                0,
                len(sportsman_rows),
                sportsman_rows,
                blocker="" if sportsman_rows else "NO_SPORTSMAN_SOURCE_ROWS",
                notes=(
                    "Sportsman uses resident-only random draw results from yearly raw Sportsman sources. "
                    f"Source report: {sportsman_report.get('sportsman_source_year')}; "
                    f"source code count: {sportsman_report.get('sportsman_source_code_count')}."
                ),
            ),
            _trace_row(
                source_year,
                target_year,
                "sportsman",
                "build_random_only_predictions",
                len(sportsman_rows),
                len(sportsman_rows),
                sportsman_rows,
                blocker="" if sportsman_rows else "NO_SPORTSMAN_PREDICTIONS",
                notes="p_sportsman_draw is resident_permit_count / eligible resident applicants; nonresident quota is always 0.",
            ),
        ]
    )

    _write_csv(audit_dir / "source_truth_family_census.csv", _census_rows(source_rows, source_year, target_year, "source_truth"))
    _write_csv(audit_dir / "target_family_census.csv", _census_rows(engine_rows, source_year, target_year, "target_rows"))
    _write_csv(
        audit_dir / "family_filter_diagnosis.csv",
        _family_filter_diagnosis_rows(source_year, target_year, source_rows, engine_rows, family_metrics, modeled),
    )

    for family, rows in modeled.items():
        output_path = predictions_dir / f"{source_year}_{target_year}_{family}.csv"
        _write_csv(output_path, rows)
        all_prediction_rows.extend(rows)
        metrics = family_metrics.get(family, {})
        counts.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "readiness_status": "READY_TRUTH_AND_RAW_FILES",
                "input_truth_rows": len(metrics.get("family_truth_rows", [])),
                "current_target_rows": len(metrics.get("family_target_rows", [])),
                "normalized_ladder_rows": len(metrics.get("normalized_rows", [])),
                "permit_accessor_rows_ok": len(metrics.get("permit_rows", [])),
                "joined_source_target_rows": len(metrics.get("joined_rows", [])),
                "prediction_rows": len(rows),
                "output_path": str(output_path),
                "status": "PASS" if rows else "FAIL",
                "blocker_if_failed": "" if rows else "NO_ROWS",
            }
        )
        leakage.append(_leakage_row(source_year, target_year, family, rows))

    for family, reason in deferred_families.items():
        counts.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "readiness_status": reason.split(":", 1)[0],
                "input_truth_rows": 0,
                "current_target_rows": 0,
                "normalized_ladder_rows": "",
                "permit_accessor_rows_ok": "",
                "joined_source_target_rows": "",
                "prediction_rows": 0,
                "output_path": "",
                "status": "CLASSIFIED",
                "blocker_if_failed": reason,
            }
        )
        leakage.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "source_years_used": str(source_year),
                "future_year_detected": "false",
                "current_year_authority_file_used": "false",
                "hardcoded_2026_field_required": "false",
                "leakage_status": "CLASSIFIED",
            }
        )

    _write_csv(audit_dir / "family_predictions.csv", all_prediction_rows)
    _write_csv(audit_dir / "all_year_family_prediction_counts.csv", counts)
    _write_csv(audit_dir / "per_family_year_prediction_counts.csv", counts)
    _write_csv(audit_dir / "leakage_check.csv", leakage)
    _write_csv(audit_dir / "zero_row_drop_trace.csv", trace)

    return {
        "source_year": source_year,
        "target_year": target_year,
        "audit_dir": str(audit_dir),
        "prediction_rows": len(all_prediction_rows),
        "family_counts": {family: len(rows) for family, rows in modeled.items()},
        "classified_families": deferred_families,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run all currently wired Utah predictive families for one target year.")
    parser.add_argument("--source-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--truth-path", type=Path, default=TRUTH_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_all_families(args.source_year, args.target_year, args.audit_dir, args.truth_path)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
