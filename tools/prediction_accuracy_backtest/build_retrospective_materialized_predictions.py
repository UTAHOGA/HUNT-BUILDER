#!/usr/bin/env python3
"""Build no-leakage retrospective prediction inputs for rolling backtests."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_BONUS_SCHEMA = Path("data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv")
REFERENCE_ML_SCHEMA = Path("processed_data/ml_draw_predictions_v1.csv")
REFERENCE_PREDICTIVE_SCHEMA = Path("processed_data/draw_reality_engine_predictive_v2.csv")
DEFAULT_OUTPUT_ROOT = Path("audits/prediction_accuracy_backtest/retrospective_outputs")
DEFAULT_HISTORY_START_YEAR = 2019

REQUIRED_METADATA_COLUMNS = [
    "target_year",
    "training_cutoff_year",
    "history_years_used",
    "no_leakage_rule",
    "source_row_years",
    "prediction_method",
]

NO_LEAKAGE_RULE = "exclude_source_draw_results_where_draw_year_gte_target_year"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_draw_sources(paths: list[Path]) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    rows: list[dict[str, str]] = []
    audits: list[dict[str, object]] = []
    for path in paths:
        headers, source_rows = read_csv(path)
        for row in source_rows:
            row.setdefault("retrospective_source_draw_results_path", str(path))
        rows.extend(source_rows)
        years = sorted({parse_year(row.get("year")) for row in source_rows if parse_year(row.get("year")) is not None})
        audits.append(
            {
                "path": str(path),
                "row_count": len(source_rows),
                "column_count": len(headers),
                "years": years,
                "exists": path.exists(),
            }
        )
    return rows, audits


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def clean(value: object) -> str:
    return str(value or "").strip()


def upper(value: object) -> str:
    return clean(value).upper()


def normalize_residency(value: object) -> str:
    lowered = clean(value).lower()
    if lowered in {"res", "resident"}:
        return "Resident"
    if lowered in {"nr", "nonresident", "non-resident", "non resident"}:
        return "Nonresident"
    if lowered in {"all", "both"}:
        return "All"
    return clean(value)


def normalize_points(value: object) -> str:
    text = clean(value)
    try:
        parsed = float(text)
    except ValueError:
        return text
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def normalize_draw_pool(value: object) -> str:
    return clean(value) or "standard"


def parse_year(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_probability(row: dict[str, str]) -> float | None:
    for field in ("p_draw_probability", "p_draw_percent", "success_ratio"):
        text = clean(row.get(field))
        if not text:
            continue
        try:
            value = float(text.replace("%", ""))
        except ValueError:
            continue
        if field == "p_draw_percent" or value > 1:
            value = value / 100.0
        return min(max(value, 0.0), 1.0)

    drawn = parse_float(row.get("total_drawn"))
    applicants = parse_float(row.get("eligible_applicants"))
    if drawn is not None and applicants and applicants > 0:
        return min(max(drawn / applicants, 0.0), 1.0)
    return None


def parse_float(value: object) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def format_probability(value: float | None, places: int = 6) -> str:
    if value is None:
        return ""
    return f"{min(max(value, 0.0), 1.0):.{places}f}"


def format_percent(value: float | None, places: int = 3) -> str:
    if value is None:
        return ""
    return f"{min(max(value * 100.0, 0.0), 100.0):.{places}f}"


def safe_mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def point_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        upper(row.get("hunt_code")),
        normalize_residency(row.get("residency")),
        normalize_points(row.get("points")),
        normalize_draw_pool(row.get("draw_pool")),
    )


def hunt_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (upper(row.get("hunt_code")), normalize_residency(row.get("residency")), normalize_draw_pool(row.get("draw_pool")))


def species_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (clean(row.get("species")), normalize_residency(row.get("residency")), normalize_draw_pool(row.get("draw_pool")))


def load_headers(root: Path) -> tuple[list[str], list[str], list[str]]:
    bonus_headers, _ = read_csv(root / REFERENCE_BONUS_SCHEMA)
    ml_headers, _ = read_csv(root / REFERENCE_ML_SCHEMA)
    predictive_headers, _ = read_csv(root / REFERENCE_PREDICTIVE_SCHEMA)
    return (
        ensure_columns(bonus_headers, REQUIRED_METADATA_COLUMNS),
        ensure_columns(ml_headers, REQUIRED_METADATA_COLUMNS),
        predictive_headers,
    )


def ensure_columns(headers: list[str], required: list[str]) -> list[str]:
    output = list(headers)
    for field in required:
        if field not in output:
            output.append(field)
    return output


def latest_metadata(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    latest: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = point_key(row)
        if not key[0]:
            continue
        current_year = parse_year(row.get("year")) or -1
        previous = latest.get(key)
        previous_year = parse_year(previous.get("year")) if previous else -1
        if previous is None or current_year >= (previous_year or -1):
            latest[key] = row
    return latest


def database_by_code(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        code = upper(row.get("hunt_code"))
        if code and code not in result:
            result[code] = row
    return result


def build_probability_indexes(history_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str, str], list[float]], dict[tuple[str, str, str], list[float]], dict[tuple[str, str, str], list[float]], list[float]]:
    by_point: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    by_hunt: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    by_species: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    global_values: list[float] = []
    for row in history_rows:
        probability = parse_probability(row)
        if probability is None:
            continue
        by_point[point_key(row)].append(probability)
        by_hunt[hunt_key(row)].append(probability)
        by_species[species_key(row)].append(probability)
        global_values.append(probability)
    return by_point, by_hunt, by_species, global_values


def choose_probability(
    row: dict[str, str],
    by_point: dict[tuple[str, str, str, str], list[float]],
    by_hunt: dict[tuple[str, str, str], list[float]],
    by_species: dict[tuple[str, str, str], list[float]],
    global_values: list[float],
) -> tuple[float | None, str]:
    point_values = by_point.get(point_key(row), [])
    if point_values:
        return safe_mean(point_values), "hunt_code_residency_points_draw_pool_average"
    hunt_values = by_hunt.get(hunt_key(row), [])
    if hunt_values:
        return safe_mean(hunt_values), "hunt_code_residency_draw_pool_average"
    species_values = by_species.get(species_key(row), [])
    if species_values:
        return safe_mean(species_values), "species_residency_draw_pool_average"
    if global_values:
        return safe_mean(global_values), "global_average"
    return None, "no_historical_probability_available"


def build_base_row(
    source_row: dict[str, str],
    database_row: dict[str, str] | None,
    target_year: int,
    history_years: list[int],
    probability: float | None,
    prediction_method: str,
    source_years: str,
) -> dict[str, str]:
    row = dict(source_row)
    db = database_row or {}
    for field in ("boundary_id", "hunt_name", "species", "sex_type", "hunt_type", "weapon", "hunt_class", "season"):
        if not clean(row.get(field)) and clean(db.get(field)):
            row[field] = db[field]

    cutoff = target_year - 1
    row.update(
        {
            "target_year": str(target_year),
            "training_cutoff_year": str(cutoff),
            "history_years_used": ";".join(str(year) for year in history_years),
            "no_leakage_rule": NO_LEAKAGE_RULE,
            "source_row_years": source_years,
            "prediction_method": prediction_method,
            "model_version": f"retrospective_{target_year}",
            "rule_version": "baseline_retrospective_v1",
            "year": str(target_year),
            "forecast_year": str(target_year),
            "prediction_year": str(target_year),
            "source_year": str(cutoff),
            "draw_pool": normalize_draw_pool(row.get("draw_pool")),
            "residency": normalize_residency(row.get("residency")),
            "points": normalize_points(row.get("points")),
            "p_draw_mean": format_probability(probability),
            "p_draw": format_probability(probability),
            "p_draw_p10": format_probability(probability),
            "p_draw_p50": format_probability(probability),
            "p_draw_p90": format_probability(probability),
            "p_random_mean": format_probability(probability),
            "p_random_pool": format_probability(probability),
            "p_draw_pct": format_percent(probability),
            "display_odds_pct": format_percent(probability),
            "display_odds_text": display_odds_text(probability),
            "algorithm_status": "BASELINE_RETROSPECTIVE",
            "model_strategy": "BASELINE_RETROSPECTIVE",
            "probability_model": "BASELINE_RETROSPECTIVE_AVERAGE",
            "source_dataset": "draw_results_truth_pre_target_history",
            "data_quality_grade": "RETROSPECTIVE_BASELINE",
            "reason_codes": f"NO_LEAKAGE_HISTORY_ONLY;{prediction_method.upper()}",
            "status": "BASELINE_RETROSPECTIVE",
            "draw_outlook": "Baseline retrospective probability generated from historical averages.",
        }
    )
    return row


def display_odds_text(probability: float | None) -> str:
    if probability is None:
        return "Not available"
    if probability >= 1:
        return "1 in 1.0 or 100.0%"
    if probability <= 0:
        return "0.0%"
    return f"1 in {1 / probability:.1f} or {probability * 100:.1f}%"


def project_row(row: dict[str, str], headers: list[str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in headers}


def build_outputs(
    target_year: int,
    history_years: list[int],
    draw_rows: list[dict[str, str]],
    database_rows: list[dict[str, str]],
    bonus_headers: list[str],
    ml_headers: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    cutoff = target_year - 1
    filtered_years = set(history_years)
    history_rows = [
        row
        for row in draw_rows
        if (year := parse_year(row.get("year"))) is not None and year < target_year and year in filtered_years
    ]
    leaked_rows = [row for row in history_rows if (parse_year(row.get("year")) or 9999) >= target_year]
    metadata = latest_metadata(history_rows)
    db_by_code = database_by_code(database_rows)
    by_point, by_hunt, by_species, global_values = build_probability_indexes(history_rows)

    base_rows: list[dict[str, str]] = []
    fallback_counts: Counter[str] = Counter()
    probability_missing = 0
    source_year_sets: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for row in history_rows:
        year = parse_year(row.get("year"))
        if year is not None:
            source_year_sets[point_key(row)].add(year)
    source_year_index = {key: ";".join(str(year) for year in sorted(years)) for key, years in source_year_sets.items()}

    for key, source_row in sorted(metadata.items()):
        probability, method = choose_probability(source_row, by_point, by_hunt, by_species, global_values)
        if probability is None:
            probability_missing += 1
        fallback_counts[method] += 1
        base = build_base_row(
            source_row,
            db_by_code.get(key[0]),
            target_year,
            history_years,
            probability,
            method,
            source_year_index.get(key, ""),
        )
        base_rows.append(base)

    materialized_rows = [project_row(row, bonus_headers) for row in base_rows]
    ml_rows = [project_row(row, ml_headers) for row in base_rows]
    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_year": target_year,
        "training_cutoff_year": cutoff,
        "history_years_requested": history_years,
        "history_years_used": sorted({parse_year(row.get("year")) for row in history_rows if parse_year(row.get("year")) is not None}),
        "no_leakage_rule": NO_LEAKAGE_RULE,
        "leaked_history_row_count": len(leaked_rows),
        "source_draw_result_rows_read": len(draw_rows),
        "history_rows_after_cutoff_filter": len(history_rows),
        "database_rows_read": len(database_rows),
        "output_row_count": len(base_rows),
        "materialized_column_count": len(bonus_headers),
        "ml_draw_prediction_column_count": len(ml_headers),
        "unique_hunt_codes": len({row.get("hunt_code", "") for row in base_rows if row.get("hunt_code", "")}),
        "unique_safe_keys": len({point_key(row) for row in base_rows if point_key(row)[0]}),
        "duplicate_safe_key_count": len(base_rows) - len({point_key(row) for row in base_rows if point_key(row)[0]}),
        "prediction_method_counts": dict(fallback_counts),
        "rows_without_probability": probability_missing,
        "model_equivalence": "BASELINE_RETROSPECTIVE_NOT_FULL_ENGINE_EQUIVALENT",
    }
    return materialized_rows, ml_rows, audit


def write_audit_csv(path: Path, audit: dict[str, object]) -> None:
    rows = [{"metric": key, "value": json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)} for key, value in audit.items()]
    write_csv(path, ["metric", "value"], rows)


def parse_year_list(value: str, target_year: int) -> list[int]:
    if value:
        years = [int(part.strip()) for part in value.split(",") if part.strip()]
    else:
        years = list(range(DEFAULT_HISTORY_START_YEAR, target_year))
    return [year for year in sorted(set(years)) if year < target_year]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument("--history-years", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--source-draw-results", default="data_truth/draw_results_truth/normalized/draw_results_long.csv")
    parser.add_argument(
        "--extra-source-draw-results",
        action="append",
        default=[],
        help="Additional normalized draw-result CSV source to union with --source-draw-results. Repeatable.",
    )
    parser.add_argument("--source-database", default="pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = REPO_ROOT
    target_year = args.target_year
    history_years = parse_year_list(args.history_years, target_year)
    if not history_years:
        raise SystemExit(f"No pre-target history years available for target year {target_year}.")

    source_draw_results = root / args.source_draw_results
    source_database = root / args.source_database
    output_root = root / args.output_dir / str(target_year) / "materialized"
    materialized_path = output_root / f"predictive_bonus_engine_{target_year}.materialized.csv"
    ml_path = output_root / "ml_draw_predictions_v1.csv"
    audit_json = output_root / "materialization_audit.json"
    audit_csv = output_root / "materialization_audit.csv"

    bonus_headers, ml_headers, predictive_headers = load_headers(root)
    draw_source_paths = [source_draw_results] + [root / source for source in args.extra_source_draw_results]
    draw_rows, draw_source_audits = read_draw_sources(draw_source_paths)
    _, database_rows = read_csv(source_database)

    materialized_rows, ml_rows, audit = build_outputs(
        target_year,
        history_years,
        draw_rows,
        database_rows,
        bonus_headers,
        ml_headers,
    )
    audit["source_draw_results"] = args.source_draw_results
    audit["extra_source_draw_results"] = args.extra_source_draw_results
    audit["source_draw_results_files"] = draw_source_audits
    audit["source_database"] = args.source_database
    audit["reference_schemas"] = {
        "predictive_bonus_engine_2026.materialized.csv": str(REFERENCE_BONUS_SCHEMA),
        "ml_draw_predictions_v1.csv": str(REFERENCE_ML_SCHEMA),
        "draw_reality_engine_predictive_v2.csv": str(REFERENCE_PREDICTIVE_SCHEMA),
        "draw_reality_engine_predictive_v2_columns": len(predictive_headers),
    }
    audit["outputs"] = {
        "predictive_bonus_engine_materialized": str(materialized_path.relative_to(root)),
        "ml_draw_predictions_v1": str(ml_path.relative_to(root)),
        "materialization_audit_json": str(audit_json.relative_to(root)),
        "materialization_audit_csv": str(audit_csv.relative_to(root)),
    }
    audit["dry_run"] = bool(args.dry_run)

    if not args.dry_run:
        write_csv(materialized_path, bonus_headers, materialized_rows)
        write_csv(ml_path, ml_headers, ml_rows)
        write_json(audit_json, audit)
        write_audit_csv(audit_csv, audit)

    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["leaked_history_row_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
