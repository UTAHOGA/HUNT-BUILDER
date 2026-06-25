#!/usr/bin/env python3
"""Run canonical scorable year-to-year blind prediction audits.

This is an audit runner, not a production materializer. For target year N it
uses only current canonical/scorable truth files from years < N, freezes a
source-only baseline prediction, then compares to the target year's official
scorable truth file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO / "audits" / "prediction_blind_year_to_year"
DEFAULT_SCORABLE_PATTERN = "outputs/{year} scorable draw results.csv"
NO_LEAKAGE_RULE = "source_years_must_be_less_than_target_actual_draw_year"
MODEL_FAMILY = "CANONICAL_SCORABLE_TARGET_APPLICANT_LADDER_BLIND_BASELINE_NOT_FULL_ENGINE_EQUIVALENT"
SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "sportsman_total",
    "sportsman_total_draw_result",
}


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_code(value: Any) -> str:
    return clean(value).upper()


def normalize_residency(value: Any) -> str:
    text = clean(value).lower()
    if text in {"res", "resident"}:
        return "Resident"
    if text in {"nr", "nonresident", "non-resident", "non resident"}:
        return "Nonresident"
    if text in {"all", "both", "total"}:
        return "All"
    return clean(value)


def normalize_points(value: Any) -> str:
    text = clean(value)
    if text == "":
        return ""
    try:
        parsed = float(text)
    except ValueError:
        return text.upper() if text.upper() == "TOTAL" else text
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def normalize_draw_pool(value: Any) -> str:
    return clean(value) or "standard"


def parse_int(value: Any) -> int | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def bounded_probability(value: float | None) -> float | None:
    if value is None or math.isnan(value):
        return None
    if value > 1.0:
        value = value / 100.0
    return min(max(value, 0.0), 1.0)


def probability_from_row(row: Mapping[str, Any]) -> float | None:
    for field in ("p_draw", "success_ratio", "p_draw_probability"):
        value = bounded_probability(parse_float(row.get(field)))
        if value is not None:
            return value
    pct = parse_float(row.get("p_draw_percent")) or parse_float(row.get("p_draw_pct"))
    if pct is not None:
        return bounded_probability(pct / 100.0)
    applicants = parse_float(row.get("eligible_applicants"))
    permits = parse_float(row.get("total_permits"))
    if applicants and applicants > 0 and permits is not None:
        return bounded_probability(permits / applicants)
    return None


def applicant_count_from_row(row: Mapping[str, Any]) -> float | None:
    return parse_float(row.get("eligible_applicants"))


def permit_allotment_from_row(row: Mapping[str, Any], residency: str) -> float | None:
    if residency == "Resident":
        return (
            parse_float(row.get("permits_year_res"))
            or parse_float(row.get("permits_res"))
            or parse_float(row.get("resident_permits_available"))
        )
    if residency == "Nonresident":
        return (
            parse_float(row.get("permits_year_nr"))
            or parse_float(row.get("permits_nr"))
            or parse_float(row.get("nonresident_permits_available"))
        )
    return parse_float(row.get("permits_year_total")) or parse_float(row.get("permits_total"))


def fmt_probability(value: float | None) -> str:
    return "" if value is None else f"{value:.10f}"


def fmt_percent(value: float | None) -> str:
    return "" if value is None else f"{value * 100.0:.6f}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def scorable_path(pattern: str, year: int) -> Path:
    return (REPO / pattern.format(year=year)).resolve()


def row_year(row: Mapping[str, Any]) -> int | None:
    return parse_int(row.get("actual_draw_year")) or parse_int(row.get("year")) or parse_int(row.get("truth_year"))


def has_prefixed_data(row: Mapping[str, Any], prefix: str) -> bool:
    fields = (
        "eligible_applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
        "success_ratio",
        "p_draw",
        "p_draw_percent",
    )
    return any(clean(row.get(f"{prefix}_{field}")) != "" for field in fields)


def expand_residency_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = normalize_residency(row.get("residency"))
    if explicit:
        return [dict(row)]

    expanded: list[dict[str, Any]] = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        if not has_prefixed_data(row, prefix):
            continue
        out = dict(row)
        out["residency"] = residency
        for field in (
            "eligible_applicants",
            "bonus_permits",
            "regular_permits",
            "total_permits",
            "success_ratio",
            "p_draw",
            "p_draw_percent",
        ):
            out[field] = clean(row.get(f"{prefix}_{field}"))
        expanded.append(out)

    if expanded:
        return expanded

    if has_prefixed_data(row, "total"):
        out = dict(row)
        out["residency"] = "All"
        for field in (
            "eligible_applicants",
            "bonus_permits",
            "regular_permits",
            "total_permits",
            "success_ratio",
            "p_draw",
            "p_draw_percent",
        ):
            out[field] = clean(row.get(f"total_{field}"))
        return [out]

    return [dict(row)]


def normalized_record(row: Mapping[str, Any], source_path: Path, fallback_year: int) -> dict[str, Any] | None:
    code = norm_code(row.get("hunt_code"))
    if not code:
        return None
    record_type = clean(row.get("record_type")).lower()
    if record_type and record_type not in SCORABLE_RECORD_TYPES:
        return None
    applicant_count = applicant_count_from_row(row)
    if applicant_count is None or applicant_count <= 0:
        return None
    probability = probability_from_row(row)
    if probability is None:
        return None
    year = row_year(row) or fallback_year
    residency = normalize_residency(row.get("residency")) or "All"
    points = normalize_points(row.get("points"))
    if not points and record_type.startswith("sportsman"):
        points = "TOTAL"
    return {
        "source_path": rel(source_path),
        "year": year,
        "actual_draw_year": year,
        "model_target_year": parse_int(row.get("model_target_year")),
        "boundary_id": clean(row.get("boundary_id")),
        "hunt_code": code,
        "hunt_name": clean(row.get("hunt_name")),
        "species": clean(row.get("species")),
        "sex_type": clean(row.get("sex_type")) or clean(row.get("sex")),
        "hunt_type": clean(row.get("hunt_type")),
        "weapon": clean(row.get("weapon")),
        "season": clean(row.get("season")),
        "draw_design": clean(row.get("draw_design")),
        "hunt_class": clean(row.get("hunt_class")),
        "draw_pool": normalize_draw_pool(row.get("draw_pool")),
        "residency": residency,
        "points": points,
        "record_type": record_type,
        "eligible_applicants": applicant_count,
        "bonus_permits": parse_float(row.get("bonus_permits")),
        "regular_permits": parse_float(row.get("regular_permits")),
        "total_permits": parse_float(row.get("total_permits")),
        "p_draw": probability,
    }


def normalized_population_record(row: Mapping[str, Any], source_path: Path, fallback_year: int) -> dict[str, Any] | None:
    """Return a target-year prediction input row with outcome fields redacted.

    This intentionally does not read p_draw, success_ratio, bonus/regular drawn,
    or point-level total_permits from the target year. The target year can
    provide the applicant ladder and published permit availability only.
    """
    code = norm_code(row.get("hunt_code"))
    if not code:
        return None
    record_type = clean(row.get("record_type")).lower()
    if record_type and record_type not in SCORABLE_RECORD_TYPES:
        return None
    residency = normalize_residency(row.get("residency")) or "All"
    applicant_count = applicant_count_from_row(row)
    permit_allotment = permit_allotment_from_row(row, residency)
    points = normalize_points(row.get("points"))
    if not points and record_type.startswith("sportsman"):
        points = "TOTAL"
    if applicant_count is None or applicant_count <= 0:
        return None
    year = row_year(row) or fallback_year
    return {
        "source_path": rel(source_path),
        "year": year,
        "actual_draw_year": year,
        "model_target_year": parse_int(row.get("model_target_year")),
        "boundary_id": clean(row.get("boundary_id")),
        "hunt_code": code,
        "hunt_name": clean(row.get("hunt_name")),
        "species": clean(row.get("species")),
        "sex_type": clean(row.get("sex_type")) or clean(row.get("sex")),
        "hunt_type": clean(row.get("hunt_type")),
        "weapon": clean(row.get("weapon")),
        "season": clean(row.get("season")),
        "draw_design": clean(row.get("draw_design")),
        "hunt_class": clean(row.get("hunt_class")),
        "draw_pool": normalize_draw_pool(row.get("draw_pool")),
        "residency": residency,
        "points": points,
        "record_type": record_type,
        "eligible_applicants": applicant_count,
        "permit_allotment": permit_allotment,
        "p_draw": None,
    }


def load_scorable_year(path: Path, fallback_year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    headers, raw_rows = read_csv(path)
    out: list[dict[str, Any]] = []
    excluded = Counter()
    for raw in raw_rows:
        for expanded in expand_residency_rows(raw):
            record = normalized_record(expanded, path, fallback_year)
            if record is None:
                excluded["not_scorable_or_probability_missing"] += 1
                continue
            out.append(record)
    return out, {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "input_rows": len(raw_rows),
        "input_columns": len(headers),
        "expanded_scorable_rows": len(out),
        "excluded_expanded_rows": dict(excluded),
    }


def load_target_population_year(path: Path, fallback_year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    headers, raw_rows = read_csv(path)
    out: list[dict[str, Any]] = []
    excluded = Counter()
    for raw in raw_rows:
        for expanded in expand_residency_rows(raw):
            record = normalized_population_record(expanded, path, fallback_year)
            if record is None:
                excluded["not_prediction_population_or_missing_allowed_inputs"] += 1
                continue
            out.append(record)
    return out, {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "input_rows": len(raw_rows),
        "input_columns": len(headers),
        "expanded_prediction_population_rows": len(out),
        "excluded_expanded_rows": dict(excluded),
        "outcome_fields_redacted_for_prediction": [
            "p_draw",
            "p_draw_percent",
            "success_ratio",
            "bonus_permits",
            "regular_permits",
            "total_permits",
        ],
        "allowed_target_year_inputs": [
            "hunt_code",
            "boundary_id",
            "hunt metadata",
            "residency",
            "points",
            "eligible_applicants",
            "published permit availability fields when populated",
        ],
    }


def prediction_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        norm_code(row.get("hunt_code")),
        normalize_residency(row.get("residency")),
        normalize_points(row.get("points")),
        normalize_draw_pool(row.get("draw_pool")),
        clean(row.get("record_type")).lower(),
    )


def hunt_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        norm_code(row.get("hunt_code")),
        normalize_residency(row.get("residency")),
        normalize_draw_pool(row.get("draw_pool")),
        clean(row.get("record_type")).lower(),
    )


def species_point_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("species")),
        clean(row.get("draw_design")),
        normalize_residency(row.get("residency")),
        normalize_points(row.get("points")),
        clean(row.get("record_type")).lower(),
    )


def species_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("species")),
        clean(row.get("draw_design")),
        normalize_residency(row.get("residency")),
        clean(row.get("record_type")).lower(),
    )


def record_design_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (clean(row.get("record_type")).lower(), clean(row.get("draw_design")))


def add_value(index: dict[tuple[Any, ...], list[float]], key: tuple[Any, ...], value: float | None) -> None:
    if value is not None:
        index[key].append(value)


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def latest_rows_by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    latest: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = prediction_key(row)
        if not key[0]:
            continue
        previous = latest.get(key)
        if previous is None or int(row["year"]) >= int(previous["year"]):
            latest[key] = row
    return latest


def aggregate_population_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[prediction_key(row)].append(row)

    output: list[dict[str, Any]] = []
    for _key, values in grouped.items():
        base = dict(values[0])
        applicants = [value.get("eligible_applicants") for value in values if value.get("eligible_applicants") is not None]
        permits = [value.get("permit_allotment") for value in values if value.get("permit_allotment") is not None]
        base["eligible_applicants"] = sum(float(value) for value in applicants) if applicants else None
        base["permit_allotment"] = sum(float(value) for value in permits) if permits else None
        base["population_duplicate_rows"] = len(values)
        output.append(base)
    return output


def historical_prediction_indexes(history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_point: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    by_hunt: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    by_species_point: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    by_species: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    by_record_design: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    global_values: list[float] = []
    years_by_point: dict[tuple[Any, ...], set[int]] = defaultdict(set)

    for row in history_rows:
        probability = row.get("p_draw")
        if probability is None:
            continue
        add_value(by_point, prediction_key(row), probability)
        add_value(by_hunt, hunt_key(row), probability)
        add_value(by_species_point, species_point_key(row), probability)
        add_value(by_species, species_key(row), probability)
        add_value(by_record_design, record_design_key(row), probability)
        global_values.append(probability)
        years_by_point[prediction_key(row)].add(int(row["year"]))

    return {
        "by_point": by_point,
        "by_hunt": by_hunt,
        "by_species_point": by_species_point,
        "by_species": by_species,
        "by_record_design": by_record_design,
        "global_values": global_values,
        "years_by_point": years_by_point,
    }


def build_predictions(history_rows: list[dict[str, Any]], target_population_rows: list[dict[str, Any]], target_year: int) -> list[dict[str, Any]]:
    indexes = historical_prediction_indexes(history_rows)
    target_population = aggregate_population_rows(target_population_rows)
    predictions: list[dict[str, Any]] = []
    for row in sorted(target_population, key=prediction_key):
        candidates = (
            ("exact_hunt_residency_points_mean", indexes["by_point"].get(prediction_key(row), [])),
            ("hunt_residency_mean", indexes["by_hunt"].get(hunt_key(row), [])),
            ("species_draw_design_residency_points_mean", indexes["by_species_point"].get(species_point_key(row), [])),
            ("species_draw_design_residency_mean", indexes["by_species"].get(species_key(row), [])),
            ("record_type_draw_design_global_mean", indexes["by_record_design"].get(record_design_key(row), [])),
            ("global_mean", indexes["global_values"]),
        )
        method = ""
        predicted = None
        values: list[float] = []
        for candidate_method, candidate_values in candidates:
            predicted = mean(candidate_values)
            if predicted is not None:
                method = candidate_method
                values = list(candidate_values)
                break
        key = prediction_key(row)
        predictions.append(
            {
                "target_year": target_year,
                "training_cutoff_year": target_year - 1,
                "training_years": ";".join(str(year) for year in sorted({int(item["year"]) for item in history_rows})),
                "no_leakage_rule": NO_LEAKAGE_RULE,
                "model_family": MODEL_FAMILY,
                "prediction_method": method,
                "history_values_used": len(values),
                "history_years_for_key": ";".join(str(year) for year in sorted(indexes["years_by_point"].get(key, set()))),
                "source_latest_year": "",
                "prediction_population_source_year": row["year"],
                "prediction_population_rule": "target_year_applicant_ladder_allowed_outcome_fields_redacted",
                "source_path": row.get("source_path", ""),
                "boundary_id": row.get("boundary_id", ""),
                "hunt_code": row.get("hunt_code", ""),
                "hunt_name": row.get("hunt_name", ""),
                "species": row.get("species", ""),
                "sex_type": row.get("sex_type", ""),
                "hunt_type": row.get("hunt_type", ""),
                "weapon": row.get("weapon", ""),
                "season": row.get("season", ""),
                "draw_design": row.get("draw_design", ""),
                "hunt_class": row.get("hunt_class", ""),
                "draw_pool": row.get("draw_pool", ""),
                "residency": row.get("residency", ""),
                "points": row.get("points", ""),
                "record_type": row.get("record_type", ""),
                "source_p_draw": fmt_probability(row.get("p_draw")),
                "predicted_p_draw": fmt_probability(predicted),
                "predicted_p_draw_percent": fmt_percent(predicted),
                "source_eligible_applicants": "" if row.get("eligible_applicants") is None else row.get("eligible_applicants"),
                "source_total_permits": "",
                "target_permit_allotment_input": "" if row.get("permit_allotment") is None else row.get("permit_allotment"),
                "population_duplicate_rows": row.get("population_duplicate_rows", ""),
            }
        )
    return predictions


def aggregate_actuals(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[prediction_key(row)].append(row)

    aggregated: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for key, values in grouped.items():
        base = dict(values[0])
        probabilities = [float(value["p_draw"]) for value in values if value.get("p_draw") is not None]
        applicants = [value.get("eligible_applicants") for value in values if value.get("eligible_applicants") is not None]
        permits = [value.get("total_permits") for value in values if value.get("total_permits") is not None]
        base["actual_p_draw"] = mean(probabilities)
        base["actual_duplicate_rows"] = len(values)
        base["actual_eligible_applicants"] = sum(float(value) for value in applicants) if applicants else ""
        base["actual_total_permits"] = sum(float(value) for value in permits) if permits else ""
        aggregated[key] = base
    return aggregated


def parse_prediction_probability(row: Mapping[str, Any]) -> float | None:
    return bounded_probability(parse_float(row.get("predicted_p_draw")))


def point_bucket(points: Any) -> str:
    text = normalize_points(points)
    if text.upper() == "TOTAL":
        return "TOTAL"
    value = parse_int(text)
    if value is None:
        return "UNKNOWN"
    if value == 0:
        return "0"
    if value <= 5:
        return "1-5"
    if value <= 10:
        return "6-10"
    if value <= 15:
        return "11-15"
    return "16+"


def compare_predictions(predictions: list[dict[str, Any]], actual_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    predicted_by_key = {prediction_key(row): row for row in predictions}
    actual_by_key = aggregate_actuals(actual_rows)
    all_keys = sorted(set(predicted_by_key) | set(actual_by_key))
    rows: list[dict[str, Any]] = []
    for key in all_keys:
        pred = predicted_by_key.get(key)
        actual = actual_by_key.get(key)
        predicted_p = parse_prediction_probability(pred or {})
        actual_p = actual.get("actual_p_draw") if actual else None
        error = predicted_p - actual_p if predicted_p is not None and actual_p is not None else None
        base = pred or actual or {}
        rows.append(
            {
                "target_year": clean(base.get("target_year")) or clean(actual.get("year") if actual else ""),
                "match_status": "matched" if pred and actual else ("missing_prediction" if actual else "extra_prediction"),
                "model_family": MODEL_FAMILY,
                "prediction_method": clean(pred.get("prediction_method") if pred else ""),
                "history_values_used": clean(pred.get("history_values_used") if pred else ""),
                "history_years_for_key": clean(pred.get("history_years_for_key") if pred else ""),
                "source_latest_year": clean(pred.get("source_latest_year") if pred else ""),
                "boundary_id_predicted": clean(pred.get("boundary_id") if pred else ""),
                "boundary_id_actual": clean(actual.get("boundary_id") if actual else ""),
                "hunt_code": key[0],
                "hunt_name_predicted": clean(pred.get("hunt_name") if pred else ""),
                "hunt_name_actual": clean(actual.get("hunt_name") if actual else ""),
                "species_predicted": clean(pred.get("species") if pred else ""),
                "species_actual": clean(actual.get("species") if actual else ""),
                "draw_design_predicted": clean(pred.get("draw_design") if pred else ""),
                "draw_design_actual": clean(actual.get("draw_design") if actual else ""),
                "residency": key[1],
                "points": key[2],
                "point_bucket": point_bucket(key[2]),
                "draw_pool": key[3],
                "record_type": key[4],
                "predicted_p_draw": fmt_probability(predicted_p),
                "actual_p_draw": fmt_probability(actual_p),
                "error_predicted_minus_actual": "" if error is None else f"{error:.10f}",
                "absolute_error": "" if error is None else f"{abs(error):.10f}",
                "squared_error": "" if error is None else f"{error * error:.10f}",
                "actual_eligible_applicants": clean(actual.get("actual_eligible_applicants") if actual else ""),
                "actual_total_permits": clean(actual.get("actual_total_permits") if actual else ""),
                "actual_duplicate_rows": clean(actual.get("actual_duplicate_rows") if actual else ""),
            }
        )
    return rows


def metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    joined = []
    for row in rows:
        if clean(row.get("match_status")) != "matched":
            continue
        absolute = parse_float(row.get("absolute_error"))
        error = parse_float(row.get("error_predicted_minus_actual"))
        actual_weight = parse_float(row.get("actual_eligible_applicants"))
        if absolute is None or error is None:
            continue
        joined.append((absolute, error, actual_weight or 0.0))

    if not joined:
        return {
            "evaluated_rows": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "median_absolute_error": "",
            "within_1pp_rate": "",
            "within_5pp_rate": "",
            "within_10pp_rate": "",
            "applicant_weighted_mae": "",
        }

    absolutes = [item[0] for item in joined]
    errors = [item[1] for item in joined]
    weights = [item[2] for item in joined]
    total_weight = sum(weights)
    weighted_mae = sum(abs_err * weight for abs_err, _err, weight in joined) / total_weight if total_weight > 0 else ""
    return {
        "evaluated_rows": len(joined),
        "mae": statistics.fmean(absolutes),
        "rmse": math.sqrt(statistics.fmean([err * err for err in errors])),
        "bias": statistics.fmean(errors),
        "median_absolute_error": statistics.median(absolutes),
        "within_1pp_rate": sum(1 for value in absolutes if value <= 0.01) / len(absolutes),
        "within_5pp_rate": sum(1 for value in absolutes if value <= 0.05) / len(absolutes),
        "within_10pp_rate": sum(1 for value in absolutes if value <= 0.10) / len(absolutes),
        "applicant_weighted_mae": weighted_mae,
    }


def formatted_metrics(raw: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, float):
            out[key] = f"{value:.10f}"
        else:
            out[key] = value
    return out


def group_summary(rows: list[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[clean(row.get(field)) or "(blank)"].append(row)
    output = []
    for value, grouped_rows in sorted(groups.items()):
        match_counts = Counter(clean(row.get("match_status")) for row in grouped_rows)
        row_metrics = formatted_metrics(metrics(list(grouped_rows)))
        output.append(
            {
                "group_field": field,
                "group_value": value,
                "union_rows": len(grouped_rows),
                "matched_rows": match_counts.get("matched", 0),
                "missing_prediction_rows": match_counts.get("missing_prediction", 0),
                "extra_prediction_rows": match_counts.get("extra_prediction", 0),
                **row_metrics,
            }
        )
    return output


PREDICTION_FIELDS = [
    "target_year",
    "training_cutoff_year",
    "training_years",
    "no_leakage_rule",
    "model_family",
    "prediction_method",
    "history_values_used",
    "history_years_for_key",
    "source_latest_year",
    "prediction_population_source_year",
    "prediction_population_rule",
    "source_path",
    "boundary_id",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "weapon",
    "season",
    "draw_design",
    "hunt_class",
    "draw_pool",
    "residency",
    "points",
    "record_type",
    "source_p_draw",
    "predicted_p_draw",
    "predicted_p_draw_percent",
    "source_eligible_applicants",
    "source_total_permits",
    "target_permit_allotment_input",
    "population_duplicate_rows",
]

COMPARISON_FIELDS = [
    "target_year",
    "match_status",
    "model_family",
    "prediction_method",
    "history_values_used",
    "history_years_for_key",
    "source_latest_year",
    "boundary_id_predicted",
    "boundary_id_actual",
    "hunt_code",
    "hunt_name_predicted",
    "hunt_name_actual",
    "species_predicted",
    "species_actual",
    "draw_design_predicted",
    "draw_design_actual",
    "residency",
    "points",
    "point_bucket",
    "draw_pool",
    "record_type",
    "predicted_p_draw",
    "actual_p_draw",
    "error_predicted_minus_actual",
    "absolute_error",
    "squared_error",
    "actual_eligible_applicants",
    "actual_total_permits",
    "actual_duplicate_rows",
]

SUMMARY_FIELDS = [
    "target_year",
    "training_years",
    "actual_path",
    "prediction_path",
    "comparison_path",
    "source_files",
    "source_expanded_scorable_rows",
    "target_prediction_population_rows",
    "actual_expanded_scorable_rows",
    "prediction_rows",
    "comparison_union_rows",
    "matched_rows",
    "missing_prediction_rows",
    "extra_prediction_rows",
    "evaluated_rows",
    "mae",
    "rmse",
    "bias",
    "median_absolute_error",
    "within_1pp_rate",
    "within_5pp_rate",
    "within_10pp_rate",
    "applicant_weighted_mae",
    "model_family",
    "no_leakage_rule",
]


def run_fold(target_year: int, source_years: list[int], output_root: Path, pattern: str) -> dict[str, Any]:
    fold_dir = output_root / f"{source_years[0]}_through_{source_years[-1]}_to_{target_year}"
    source_rows: list[dict[str, Any]] = []
    source_audits = []
    for year in source_years:
        path = scorable_path(pattern, year)
        rows, audit = load_scorable_year(path, year)
        source_rows.extend(rows)
        source_audits.append(audit)

    actual_path = scorable_path(pattern, target_year)
    target_population_rows, target_population_audit = load_target_population_year(actual_path, target_year)
    actual_rows, actual_audit = load_scorable_year(actual_path, target_year)
    leaked = [row for row in source_rows if int(row["year"]) >= target_year]
    if leaked:
        raise RuntimeError(f"Leakage failure for target {target_year}: {len(leaked)} source rows have year >= target")

    predictions = build_predictions(source_rows, target_population_rows, target_year)
    comparison = compare_predictions(predictions, actual_rows)
    match_counts = Counter(row["match_status"] for row in comparison)
    row_metrics = formatted_metrics(metrics(comparison))

    prediction_path = fold_dir / "frozen_predictions.csv"
    comparison_path = fold_dir / "prediction_vs_actual_rowlevel.csv"
    summary_path = fold_dir / "summary.json"
    group_dir = fold_dir / "group_summaries"
    write_csv(prediction_path, PREDICTION_FIELDS, predictions)
    write_csv(comparison_path, COMPARISON_FIELDS, comparison)

    group_fields = [
        "draw_design_actual",
        "species_actual",
        "residency",
        "point_bucket",
        "record_type",
        "prediction_method",
        "match_status",
    ]
    for field in group_fields:
        write_csv(
            group_dir / f"by_{field}.csv",
            [
                "group_field",
                "group_value",
                "union_rows",
                "matched_rows",
                "missing_prediction_rows",
                "extra_prediction_rows",
                "evaluated_rows",
                "mae",
                "rmse",
                "bias",
                "median_absolute_error",
                "within_1pp_rate",
                "within_5pp_rate",
                "within_10pp_rate",
                "applicant_weighted_mae",
            ],
            group_summary(comparison, field),
        )

    summary = {
        "target_year": target_year,
        "training_years": source_years,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_family": MODEL_FAMILY,
        "no_leakage_rule": NO_LEAKAGE_RULE,
        "source_files": source_audits,
        "target_prediction_population_file": target_population_audit,
        "actual_file": actual_audit,
        "source_expanded_scorable_rows": len(source_rows),
        "target_prediction_population_rows": len(target_population_rows),
        "actual_expanded_scorable_rows": len(actual_rows),
        "prediction_rows": len(predictions),
        "comparison_union_rows": len(comparison),
        "matched_rows": match_counts.get("matched", 0),
        "missing_prediction_rows": match_counts.get("missing_prediction", 0),
        "extra_prediction_rows": match_counts.get("extra_prediction", 0),
        "metrics": row_metrics,
        "outputs": {
            "prediction_path": rel(prediction_path),
            "comparison_path": rel(comparison_path),
            "summary_path": rel(summary_path),
            "group_summary_dir": rel(group_dir),
        },
    }
    write_json(summary_path, summary)

    return {
        "target_year": target_year,
        "training_years": ";".join(str(year) for year in source_years),
        "actual_path": rel(actual_path),
        "prediction_path": rel(prediction_path),
        "comparison_path": rel(comparison_path),
        "source_files": ";".join(item["path"] for item in source_audits),
        "source_expanded_scorable_rows": len(source_rows),
        "target_prediction_population_rows": len(target_population_rows),
        "actual_expanded_scorable_rows": len(actual_rows),
        "prediction_rows": len(predictions),
        "comparison_union_rows": len(comparison),
        "matched_rows": match_counts.get("matched", 0),
        "missing_prediction_rows": match_counts.get("missing_prediction", 0),
        "extra_prediction_rows": match_counts.get("extra_prediction", 0),
        **row_metrics,
        "model_family": MODEL_FAMILY,
        "no_leakage_rule": NO_LEAKAGE_RULE,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--scorable-pattern", default=DEFAULT_SCORABLE_PATTERN)
    parser.add_argument(
        "--history-mode",
        choices=("cumulative", "previous-only"),
        default="cumulative",
        help="cumulative uses all promoted years before target; previous-only uses N-1 only.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        help="Run a single target year. Example: --target-year 2020 uses --start-year through 2019 unless previous-only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.end_year <= args.start_year:
        raise SystemExit("--end-year must be greater than --start-year")

    targets = [args.target_year] if args.target_year else list(range(args.start_year + 1, args.end_year + 1))
    summaries: list[dict[str, Any]] = []
    for target_year in targets:
        if target_year <= args.start_year:
            raise SystemExit("--target-year must be greater than --start-year")
        if args.history_mode == "previous-only":
            source_years = [target_year - 1]
        else:
            source_years = list(range(args.start_year, target_year))
        summaries.append(run_fold(target_year, source_years, args.output_root, args.scorable_pattern))

    rollup_path = args.output_root / "roll_forward_summary.csv"
    write_csv(rollup_path, SUMMARY_FIELDS, summaries)
    write_json(
        args.output_root / "roll_forward_manifest.json",
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "start_year": args.start_year,
            "end_year": args.end_year,
            "target_years": targets,
            "history_mode": args.history_mode,
            "model_family": MODEL_FAMILY,
            "no_leakage_rule": NO_LEAKAGE_RULE,
            "roll_forward_summary": rel(rollup_path),
        },
    )
    print(f"Wrote {rel(rollup_path)}")
    for summary in summaries:
        print(
            f"{summary['training_years']} -> {summary['target_year']}: "
            f"matched={summary['matched_rows']} missing={summary['missing_prediction_rows']} "
            f"extra={summary['extra_prediction_rows']} mae={summary['mae']}"
        )


if __name__ == "__main__":
    main()
