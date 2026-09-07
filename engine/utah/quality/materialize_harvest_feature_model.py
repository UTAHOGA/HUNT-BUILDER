"""Materialize harvest quality/demand features for 2026 hunt rows.

This module joins harvest-derived features as metadata only. It asserts that
draw probability and quota/allotment fields are unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine.utah.quality.harvest_feature_model import (
    clean_numeric,
    demand_pressure_signal,
    fallback_feature_selection,
    harvest_quality_index,
    point_creep_quality_adjustment,
    rolling_mean,
    trend_delta,
    trend_direction,
)
from engine.utah.quality.harvest_identity import build_identity_index, normalize_code, resolve_identity_match, species_family


ROOT = Path(__file__).resolve().parents[3]

PROTECTED_FIELDS = [
    "p_draw",
    "p_draw_mean",
    "p_random_mean",
    "p_max_pool_mean",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permit_allotment_2026_source",
    "permit_allotment_2026_source_file",
    "permit_allotment_2026_status",
    "public_permits_2026",
    "public_permits_2026_source",
]

FEATURE_FIELDS = [
    "harvest_quality_index",
    "demand_pressure_signal",
    "demand_pressure_category",
    "point_creep_quality_adjustment",
    "harvest_success_recent",
    "harvest_success_3yr_avg",
    "harvest_success_delta_1yr",
    "harvest_success_trend_direction",
    "hunter_satisfaction_recent",
    "hunter_satisfaction_3yr_avg",
    "hunter_effort_days_recent",
    "hunter_effort_days_3yr_avg",
    "harvest_recent",
    "harvest_3yr_avg",
    "hunters_afield_recent",
    "hunters_afield_3yr_avg",
    "average_harvest_age_recent",
    "average_harvest_age_3yr_reported",
    "average_harvest_age_3yr_computed",
    "average_age_recent",
    "average_age_3yr_avg",
    "percent_female_recent",
    "percent_adult_male_recent",
    "population_signal_recent",
    "pursuit_pressure_recent",
    "harvest_feature_source_years",
    "harvest_feature_match_method",
    "harvest_feature_data_quality_grade",
    "harvest_feature_reason_codes",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def values_by_year(rows: list[dict[str, str]], field: str) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for row in rows:
        year = clean_numeric(row.get("reported_hunt_year"))
        value = clean_numeric(row.get(field))
        if year is not None and value is not None:
            values.append((int(year), value))
    return sorted(values)


def recent_and_average(rows: list[dict[str, str]], field: str) -> tuple[float | None, float | None, list[str]]:
    values = values_by_year(rows, field)
    if not values:
        return None, None, ["NO_" + field.upper()]
    recent = values[-1][1]
    avg, reasons = rolling_mean([value for _, value in values], years=3)
    return recent, avg, reasons


def latest_delta(rows: list[dict[str, str]], field: str) -> float | None:
    values = values_by_year(rows, field)
    if len(values) < 2:
        return None
    return trend_delta(values[-1][1], values[-2][1])


def latest_value(rows: list[dict[str, str]], field: str) -> float | None:
    values = values_by_year(rows, field)
    return values[-1][1] if values else None


def percent_from_parts(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return 100.0 * numerator / denominator


def build_feature_row(
    db_row: dict[str, str],
    history_rows: list[dict[str, str]],
    target_year: int = 2026,
    age_rows: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    selection = fallback_feature_selection(
        db_row.get("hunt_code", ""),
        db_row.get("species", ""),
        db_row.get("hunt_name", ""),
        target_year,
        history_rows,
    )
    rows = selection.rows
    years = sorted({int(clean_numeric(row.get("reported_hunt_year")) or 0) for row in rows if clean_numeric(row.get("reported_hunt_year")) is not None})
    reason_codes = list(selection.reason_codes)

    success_recent, success_avg, success_reasons = recent_and_average(rows, "percent_success")
    satisfaction_recent, satisfaction_avg, satisfaction_reasons = recent_and_average(rows, "hunter_satisfaction")
    effort_recent, effort_avg, effort_reasons = recent_and_average(rows, "average_days")
    harvest_recent, harvest_avg, harvest_reasons = recent_and_average(rows, "harvest_total")
    hunters_recent, hunters_avg, hunters_reasons = recent_and_average(rows, "hunters_afield")
    age_recent, age_avg, age_reasons = recent_and_average(rows, "average_age")
    age_3yr_reported = latest_value(rows, "average_age_3yr_reported")
    if age_rows is not None:
        direct_age_rows = [
            row
            for row in age_rows
            if normalize_code(row.get("hunt_code")) == normalize_code(db_row.get("hunt_code"))
            and species_family(row.get("species")) == species_family(db_row.get("species"))
            and int(clean_numeric(row.get("reported_hunt_year")) or 0) < target_year
        ]
        direct_age_years = {
            int(clean_numeric(row.get("reported_hunt_year")) or 0)
            for row in direct_age_rows
            if clean_numeric(row.get("reported_hunt_year")) is not None
        }
        if direct_age_rows:
            age_recent, age_avg, age_reasons = recent_and_average(direct_age_rows, "average_harvest_age")
            age_3yr_reported = latest_value(direct_age_rows, "average_harvest_age_3yr")
            years = sorted(set(years) | {year for year in direct_age_years if year})
    reason_codes.extend(success_reasons + satisfaction_reasons + effort_reasons + harvest_reasons + hunters_reasons + age_reasons)
    if age_3yr_reported is not None:
        reason_codes.append("DWR_REPORTED_3YR_HARVEST_AGE")
    if age_avg is not None:
        reason_codes.append("COMPUTED_3YR_HARVEST_AGE")

    success_delta = latest_delta(rows, "percent_success")
    satisfaction_delta = latest_delta(rows, "hunter_satisfaction")
    effort_delta = latest_delta(rows, "average_days")
    age_delta = latest_delta(rows, "average_age")
    female_recent = values_by_year(rows, "harvest_female")
    male_recent = values_by_year(rows, "harvest_male")
    adult_male_recent = values_by_year(rows, "male_harvest")
    harvest_denominator = harvest_recent
    percent_female = percent_from_parts(female_recent[-1][1] if female_recent else None, harvest_denominator)
    percent_adult_male = percent_from_parts(
        (adult_male_recent[-1][1] if adult_male_recent else (male_recent[-1][1] if male_recent else None)),
        harvest_denominator,
    )

    feature: dict[str, object] = {
        "hunt_code": db_row.get("hunt_code", ""),
        "species": db_row.get("species", ""),
        "hunt_name": db_row.get("hunt_name", ""),
        "active_2026": "YES",
        "harvest_success_recent": success_recent,
        "harvest_success_3yr_avg": success_avg,
        "harvest_success_delta_1yr": success_delta,
        "harvest_success_trend_direction": trend_direction(success_delta, 3.0),
        "hunter_satisfaction_recent": satisfaction_recent,
        "hunter_satisfaction_3yr_avg": satisfaction_avg,
        "hunter_satisfaction_delta_1yr": satisfaction_delta,
        "hunter_effort_days_recent": effort_recent,
        "hunter_effort_days_3yr_avg": effort_avg,
        "hunter_effort_days_delta_1yr": effort_delta,
        "harvest_recent": harvest_recent,
        "harvest_3yr_avg": harvest_avg,
        "hunters_afield_recent": hunters_recent,
        "hunters_afield_3yr_avg": hunters_avg,
        "average_harvest_age_recent": age_recent,
        "average_harvest_age_3yr_reported": age_3yr_reported,
        "average_harvest_age_3yr_computed": age_avg,
        "average_age_recent": age_recent,
        "average_age_3yr_avg": age_avg,
        "average_age_delta_1yr": age_delta,
        "percent_female_recent": percent_female,
        "percent_adult_male_recent": percent_adult_male,
        "population_signal_recent": "",
        "pursuit_pressure_recent": "",
        "harvest_feature_source_years": "|".join(str(year) for year in years if year),
        "harvest_feature_match_method": selection.match_method,
        "harvest_feature_data_quality_grade": selection.data_quality_grade,
    }
    quality, quality_reasons = harvest_quality_index(feature)
    feature["harvest_quality_index"] = quality
    feature["demand_pressure_signal"], feature["demand_pressure_category"], demand_reasons = demand_pressure_signal(feature)
    feature["point_creep_quality_adjustment"] = point_creep_quality_adjustment(feature)
    reason_codes.extend(quality_reasons + demand_reasons)
    if quality is not None:
        reason_codes.append("HARVEST_QUALITY_SIGNAL_ONLY")
    reason_codes.append("DO_NOT_USE_FOR_P_DRAW")
    reason_codes.append("DO_NOT_USE_FOR_2026_QUOTA")
    feature["harvest_feature_reason_codes"] = "|".join(sorted(set(code for code in reason_codes if code)))

    output = {key: db_row.get(key, "") for key in ["hunt_code", "species", "hunt_name"]}
    for key in FEATURE_FIELDS:
        value = feature.get(key)
        if isinstance(value, float):
            output[key] = fmt(value)
        else:
            output[key] = str(value or "")
    output["active_2026"] = "YES"
    return output


def build_species_year_rows(history_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in history_rows:
        species = row.get("species", "").strip()
        year = row.get("reported_hunt_year", "").strip()
        if species and year:
            grouped[(species, year)].append(row)
    output = []
    for (species, year), rows in sorted(grouped.items()):
        success = [clean_numeric(row.get("percent_success")) for row in rows]
        harvest = [clean_numeric(row.get("harvest_total")) for row in rows]
        effort = [clean_numeric(row.get("average_days")) for row in rows]
        output.append(
            {
                "species": species,
                "reported_hunt_year": year,
                "model_target_year": str(int(year) + 1) if year.isdigit() else "",
                "hunt_code_count": str(len({row.get("hunt_code", "") for row in rows if row.get("hunt_code")})),
                "harvest_success_avg": fmt(sum(v for v in success if v is not None) / max(1, len([v for v in success if v is not None]))),
                "harvest_total_sum": fmt(sum(v for v in harvest if v is not None)),
                "average_days_avg": fmt(sum(v for v in effort if v is not None) / max(1, len([v for v in effort if v is not None]))),
            }
        )
    return output


def row_key(row: dict[str, str], index: int) -> tuple[str, str, str, str]:
    return (row.get("hunt_code", ""), row.get("residency", ""), row.get("points", ""), str(index))


def protected_snapshot(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    return {row_key(row, index): {field: row.get(field, "") for field in PROTECTED_FIELDS if field in row} for index, row in enumerate(rows)}


def assert_protected_unchanged(before: dict[tuple[str, str, str, str], dict[str, str]], rows: list[dict[str, str]]) -> None:
    after = protected_snapshot(rows)
    if before != after:
        raise AssertionError("Harvest feature materialization changed protected probability or quota fields.")


def append_features(
    rows: list[dict[str, str]],
    features_by_code: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    output = []
    for row in rows:
        merged = dict(row)
        resolution = resolve_identity_match(row, features_by_code.get(row.get("hunt_code", ""), []))
        feature = resolution.row or {}
        for field in FEATURE_FIELDS:
            merged[field] = feature.get(field, "")
        output.append(merged)
    return output


def materialize(output_dir: Path, forecast_year: int = 2026) -> dict[str, object]:
    history_path = ROOT / "data_model" / "harvest_quality" / "harvest_quality_features_all_years_by_hunt_code.csv"
    long_path = ROOT / "data_model" / "harvest_quality" / "harvest_results_all_years_long.csv"
    database_path = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
    age_path = ROOT / "data_model" / "harvest_quality" / "harvest_average_age_global_merge_database.csv"
    ml_path = ROOT / "processed_data" / "ml_draw_predictions_v1.csv"
    successor_path = ROOT / "processed_data" / "draw_reality_engine_predictive_v2.csv"

    history_rows = read_rows(history_path)
    long_rows = read_rows(long_path)
    db_rows = [row for row in read_rows(database_path) if row.get("hunt_code")]
    age_rows = read_rows(age_path)
    features = [build_feature_row(row, history_rows, forecast_year, age_rows) for row in db_rows]
    features_by_code = build_identity_index(features)
    species_year = build_species_year_rows(long_rows)

    feature_fields = ["hunt_code", "species", "hunt_name", "active_2026"] + FEATURE_FIELDS
    feature_path = ROOT / "data_model" / "harvest_quality" / "harvest_feature_model_by_hunt_code_2026.csv"
    species_path = ROOT / "data_model" / "harvest_quality" / "harvest_feature_model_by_species_year.csv"
    write_rows(feature_path, features, feature_fields)
    write_rows(species_path, species_year, list(species_year[0].keys()) if species_year else ["species"])

    ml_rows = read_rows(ml_path)
    successor_rows = read_rows(successor_path)
    ml_before = protected_snapshot(ml_rows)
    successor_before = protected_snapshot(successor_rows)
    ml_joined = append_features(ml_rows, features_by_code)
    successor_joined = append_features(successor_rows, features_by_code)
    assert_protected_unchanged(ml_before, ml_joined)
    assert_protected_unchanged(successor_before, successor_joined)

    ml_joined_path = ROOT / "data_model" / "harvest_quality" / "ml_draw_predictions_with_harvest_features.csv"
    successor_joined_path = ROOT / "data_model" / "harvest_quality" / "draw_reality_engine_predictive_with_harvest_features.csv"
    write_rows(ml_joined_path, ml_joined, list(ml_rows[0].keys()) + [field for field in FEATURE_FIELDS if field not in ml_rows[0]])
    write_rows(
        successor_joined_path,
        successor_joined,
        list(successor_rows[0].keys()) + [field for field in FEATURE_FIELDS if field not in successor_rows[0]],
    )

    method_counts = defaultdict(int)
    grade_counts = defaultdict(int)
    for row in features:
        method_counts[row["harvest_feature_match_method"]] += 1
        grade_counts[row["harvest_feature_data_quality_grade"]] += 1
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "forecast_year": forecast_year,
        "active_2026_hunt_codes": len(features),
        "harvest_quality_index_count": sum(1 for row in features if row.get("harvest_quality_index")),
        "demand_pressure_signal_count": sum(1 for row in features if row.get("demand_pressure_signal")),
        "average_harvest_age_recent_count": sum(
            1 for row in features if row.get("average_harvest_age_recent")
        ),
        "average_harvest_age_3yr_reported_count": sum(
            1 for row in features if row.get("average_harvest_age_3yr_reported")
        ),
        "average_harvest_age_3yr_computed_count": sum(
            1 for row in features if row.get("average_harvest_age_3yr_computed")
        ),
        "match_method_counts": dict(sorted(method_counts.items())),
        "data_quality_grade_counts": dict(sorted(grade_counts.items())),
        "protected_probability_and_quota_fields_unchanged": True,
        "outputs": {
            "feature_by_hunt_code": str(feature_path.relative_to(ROOT)),
            "feature_by_species_year": str(species_path.relative_to(ROOT)),
            "ml_with_features": str(ml_joined_path.relative_to(ROOT)),
            "draw_reality_with_features": str(successor_joined_path.relative_to(ROOT)),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "harvest_feature_model_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    write_rows(
        output_dir / "harvest_feature_model_audit.csv",
        [{"metric": key, "value": json.dumps(value) if isinstance(value, (dict, list)) else str(value)} for key, value in audit.items()],
        ["metric", "value"],
    )
    md = [
        "# Harvest Feature Model Audit",
        "",
        f"- active_2026_hunt_codes: {audit['active_2026_hunt_codes']}",
        f"- harvest_quality_index_count: {audit['harvest_quality_index_count']}",
        f"- demand_pressure_signal_count: {audit['demand_pressure_signal_count']}",
        f"- average_harvest_age_recent_count: {audit['average_harvest_age_recent_count']}",
        f"- average_harvest_age_3yr_reported_count: {audit['average_harvest_age_3yr_reported_count']}",
        f"- average_harvest_age_3yr_computed_count: {audit['average_harvest_age_3yr_computed_count']}",
        f"- protected_probability_and_quota_fields_unchanged: {audit['protected_probability_and_quota_fields_unchanged']}",
        f"- match_method_counts: {audit['match_method_counts']}",
    ]
    (output_dir / "harvest_feature_model_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "processed_data"))
    parser.add_argument("--forecast-year", type=int, default=2026)
    args = parser.parse_args()
    audit = materialize(Path(args.output_dir), args.forecast_year)
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
