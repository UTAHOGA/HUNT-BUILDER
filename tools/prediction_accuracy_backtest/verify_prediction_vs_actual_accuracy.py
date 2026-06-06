#!/usr/bin/env python
"""Compare retrospective prediction outputs to paired actual draw-truth files.

This is an audit-only verifier. It does not modify production feeders.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Iterable


SUMMARY_FIELDS = [
    "target_year",
    "verification_target_year",
    "prediction_file",
    "prediction_kind",
    "actual_truth_file",
    "actual_draw_year",
    "actual_source_year",
    "actual_model_target_year",
    "actual_truth_status",
    "scope",
    "record_kind",
    "validation_status",
    "pairing_status",
    "pairing_confidence",
    "pairing_reason",
    "prediction_generation_method",
    "prediction_probability_field",
    "actual_probability_field",
    "probability_exact_match_rate",
    "identical_row_probability_count",
    "warning_status",
    "prediction_rows",
    "actual_rows",
    "actual_usable_rows",
    "joined_rows",
    "unmatched_prediction_rows",
    "prediction_rows_without_probability",
    "actual_rows_without_probability",
    "actual_rows_excluded_for_leakage",
    "prediction_rows_with_leakage",
    "exact_join_rows",
    "hunt_residency_points_join_rows",
    "hunt_residency_join_rows",
    "mae",
    "rmse",
    "bias",
    "median_abs_error",
    "p90_abs_error",
    "calibration_bucket_counts_json",
    "calibration_bucket_actual_mean_json",
]

PAIRING_FIELDS = [
    "target_year",
    "verification_target_year",
    "prediction_file",
    "prediction_kind",
    "actual_truth_file",
    "actual_draw_year",
    "actual_source_year",
    "actual_model_target_year",
    "actual_truth_status",
    "scope",
    "record_kind",
    "validation_status",
    "hunt_code_rollup_rows",
    "pairing_status",
    "pairing_confidence",
    "source_year_expected",
    "actual_source_rows",
    "actual_usable_rows",
    "actual_leakage_rows",
    "prediction_rows",
    "joined_rows",
    "no_leakage_status",
    "reason",
]

ROWLEVEL_FIELDS = [
    "target_year",
    "prediction_kind",
    "prediction_file",
    "prediction_row_number",
    "hunt_code",
    "residency",
    "points",
    "draw_pool",
    "prediction_probability",
    "prediction_probability_field",
    "actual_probability",
    "actual_probability_field",
    "error",
    "absolute_error",
    "join_tier",
    "actual_rows_aggregated",
    "actual_source_file",
    "actual_source_years",
    "actual_model_target_years",
    "actual_family",
    "actual_species",
    "prediction_method",
    "model_version",
    "source_row_years",
    "leakage_status",
]

GROUP_FIELDS = [
    "target_year",
    "prediction_kind",
    "group_value",
    "joined_rows",
    "mae",
    "rmse",
    "bias",
    "median_abs_error",
    "p90_abs_error",
]

CIRCULARITY_FIELDS = [
    "target_year",
    "verification_target_year",
    "prediction_file",
    "prediction_kind",
    "actual_truth_file",
    "prediction_generation_method",
    "actual_probability_field",
    "prediction_probability_field",
    "probability_exact_match_rate",
    "identical_row_probability_count",
    "joined_rows",
    "warning_status",
]

PREDICTION_CANDIDATE_COLUMNS = [
    "p_draw",
    "p_draw_mean",
    "p_draw_probability",
    "p_draw_pct",
    "display_odds_pct",
    "odds_2026_projected",
]

ACTUAL_CANDIDATE_COLUMNS = [
    "p_draw_probability",
    "p_draw_percent",
    "p_draw",
    "success_ratio",
    "success_ratio_text",
]


@dataclass(frozen=True)
class PredictionFile:
    kind: str
    relpath_template: str
    fallback_relpath_template: str | None = None

    def path_for(self, root: Path, target_year: int) -> Path:
        primary = root / self.relpath_template.format(target_year=target_year)
        if primary.exists() or self.fallback_relpath_template is None:
            return primary
        return root / self.fallback_relpath_template.format(target_year=target_year)


@dataclass(frozen=True)
class ActualSource:
    target_year: int
    relpath: str
    confidence: str
    reason: str
    hold: bool = False
    source_year_expected_override: int | None = None
    actual_draw_year: int | None = None
    actual_source_year: int | None = None
    actual_model_target_year: int | None = None
    actual_truth_status: str = ""
    scope: str = ""
    actual_rows_expected: int | None = None
    hunt_code_rollup_rows: int | None = None
    record_kind: str = ""
    validation_status: str = ""
    allow_actual_model_target_after_verification_year: bool = False

    @property
    def source_year_expected(self) -> int:
        if self.source_year_expected_override is not None:
            return self.source_year_expected_override
        return self.target_year - 1

    def path_for(self, root: Path) -> Path:
        return root / self.relpath


@dataclass
class ActualAgg:
    probability_sum: float = 0.0
    count: int = 0
    source_files: Counter = field(default_factory=Counter)
    source_years: Counter = field(default_factory=Counter)
    model_target_years: Counter = field(default_factory=Counter)
    families: Counter = field(default_factory=Counter)
    species: Counter = field(default_factory=Counter)
    probability_fields: Counter = field(default_factory=Counter)

    def add(self, row: dict[str, str], probability: float, probability_field: str) -> None:
        self.probability_sum += probability
        self.count += 1
        self.source_files[_first_nonblank(row, ["source_file", "source_dataset"], "UNKNOWN")] += 1
        self.source_years[_first_nonblank(row, ["year", "reported_draw_year"], "")] += 1
        self.model_target_years[_first_nonblank(row, ["model_target_year"], "")] += 1
        self.families[_first_nonblank(row, ["source_family", "source_classification", "source_dataset"], "UNKNOWN")] += 1
        self.species[_title(_first_nonblank(row, ["species", "database_species"], "UNKNOWN"))] += 1
        self.probability_fields[probability_field or "UNKNOWN"] += 1

    @property
    def probability(self) -> float:
        if not self.count:
            return math.nan
        return self.probability_sum / self.count

    def top(self, counter: Counter) -> str:
        return counter.most_common(1)[0][0] if counter else ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--out-dir",
        default="audits/prediction_accuracy_backtest",
        help="Audit output directory.",
    )
    parser.add_argument(
        "--target-years",
        default="2020,2021,2022,2023,2024,2025,2026",
        help="Comma-separated target years to verify.",
    )
    return parser.parse_args()


def _first_nonblank(row: dict[str, str], names: Iterable[str], default: str = "") -> str:
    for name in names:
        value = row.get(name, "")
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _title(value: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned.title() if cleaned.isupper() else cleaned


def norm_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\ufeff", "")).strip()


def norm_hunt_code(value: object) -> str:
    return norm_text(value).upper()


def norm_residency(value: object) -> str:
    cleaned = norm_text(value).lower().replace("-", "").replace("_", " ")
    if cleaned in {"r", "res", "resident"}:
        return "Resident"
    if cleaned in {"nr", "nonresident", "non resident", "nonres"}:
        return "Nonresident"
    if cleaned in {"all", "both", "resident/nonresident", "resident nonresident"}:
        return "All"
    return norm_text(value) or "UNKNOWN"


def norm_points(value: object) -> str:
    cleaned = norm_text(value)
    if cleaned == "":
        return ""
    try:
        return str(int(float(cleaned)))
    except ValueError:
        return cleaned


def norm_draw_pool(value: object) -> str:
    cleaned = norm_text(value).lower()
    if cleaned in {"", "na", "n/a", "none"}:
        return "standard"
    return cleaned


def parse_probability(value: object, column_name: str = "") -> float | None:
    text = norm_text(value)
    if text == "" or text.lower() in {"na", "n/a", "not available", "insufficient data"}:
        return None
    lowered = text.lower()
    ratio_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*in\s*(\d+(?:\.\d+)?)\s*$", lowered)
    if ratio_match:
        numerator = float(ratio_match.group(1))
        denominator = float(ratio_match.group(2))
        if denominator:
            return max(0.0, min(1.0, numerator / denominator))
    text = text.replace("%", "").replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    if "%" in norm_text(value) or "pct" in column_name.lower() or "percent" in column_name.lower():
        number /= 100.0
    elif number > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def choose_probability(row: dict[str, str], candidates: list[str]) -> tuple[float | None, str]:
    for column in candidates:
        if column in row:
            parsed = parse_probability(row.get(column), column)
            if parsed is not None:
                return parsed, column
    return None, ""


def choose_actual_probability(row: dict[str, str]) -> tuple[float | None, str]:
    parsed, column = choose_probability(row, ACTUAL_CANDIDATE_COLUMNS)
    if parsed is not None:
        return parsed, column
    total_drawn = norm_text(row.get("total_drawn", ""))
    eligible_applicants = norm_text(row.get("eligible_applicants", ""))
    if total_drawn != "" and eligible_applicants != "":
        try:
            drawn = float(total_drawn.replace(",", ""))
            eligible = float(eligible_applicants.replace(",", ""))
        except ValueError:
            return None, ""
        if eligible > 0:
            return max(0.0, min(1.0, drawn / eligible)), "total_drawn_over_eligible_applicants"
    return None, ""


def parse_years(value: str) -> list[int]:
    years: list[int] = []
    for token in re.findall(r"\d{4}", str(value or "")):
        try:
            years.append(int(token))
        except ValueError:
            pass
    return years


def row_year(row: dict[str, str]) -> int | None:
    for name in ("year", "reported_draw_year", "draw_results_year"):
        value = norm_text(row.get(name, ""))
        if value:
            try:
                return int(float(value))
            except ValueError:
                continue
    return None


def model_target_year(row: dict[str, str]) -> int | None:
    value = norm_text(row.get("model_target_year", ""))
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def prediction_leaks(row: dict[str, str], target_year: int) -> bool:
    source_years = parse_years(row.get("source_row_years", ""))
    if any(year >= target_year for year in source_years):
        return True
    for name in ("training_cutoff_year", "latest_source_year"):
        value = norm_text(row.get(name, ""))
        if value:
            try:
                if int(float(value)) >= target_year:
                    return True
            except ValueError:
                continue
    return False


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def actual_sources() -> dict[int, ActualSource]:
    return {
        2020: ActualSource(
            2020,
            "data_truth/draw_results_truth/normalized/draw_results_2019_for_2020_candidate_promotion_file_records.csv",
            "MEDIUM_EXTRA_NORMALIZED_SOURCE",
            "2019 draw-result source feeds target-year 2020; usable but older extraction has summary rows and sparse fields.",
        ),
        2021: ActualSource(
            2021,
            "data_truth/draw_results_truth/normalized/draw_results_2020_for_2021_candidate_promotion_file_records_STRICT_USABLE_PLUS_SPORTSMAN.csv",
            "HIGH_VALIDATED_STRICT_USABLE_PLUS_SPORTSMAN",
            "Validated strict usable 2020-for-2021 source with Sportsman rows included.",
        ),
        2022: ActualSource(
            2022,
            "data_truth/draw_results_truth/normalized/draw_results_2021_for_2022_candidate_promotion_file_records.csv",
            "HIGH_NORMALIZED_CANDIDATE",
            "Correct same-target actual source: 2021 draw-result year for 2022 model target.",
        ),
        2023: ActualSource(
            2023,
            "data_truth/draw_results_truth/normalized/draw_results_2022_for_2023_candidate_promotion_file_records.csv",
            "HIGH_NORMALIZED_CANDIDATE",
            "Correct same-target actual source: 2022 draw-result year for 2023 model target.",
        ),
        2024: ActualSource(
            2024,
            "data_truth/draw_results_truth/normalized/draw_results_2023_for_2024_candidate_promotion_file_records.csv",
            "HIGH_NORMALIZED_CANDIDATE",
            "Correct same-target actual source: 2023 draw-result year for 2024 model target.",
        ),
        2025: ActualSource(
            2025,
            "data_truth/draw_results_truth/normalized/draw_results_2024_for_2025_candidate_promotion_file_records.csv",
            "HIGH_NORMALIZED_CANDIDATE",
            "Correct same-target actual source: 2024 draw-result year for 2025 model target.",
        ),
        2026: ActualSource(
            2026,
            "data_truth/draw_results_truth/normalized/draw_results_2026_for_2027_candidate_promotion_file_records.csv",
            "HIGH_VALIDATED_LIMITED_2026_CANDIDATE",
            "Validated early 2026 actual draw-result truth. The file later feeds 2027 modeling, but this verifier uses actual draw year 2026 only as held-out truth for 2026 predictions.",
            source_year_expected_override=2026,
            actual_draw_year=2026,
            actual_source_year=2026,
            actual_model_target_year=2027,
            actual_truth_status="ACTUAL_2026_RELEASED_EARLY",
            scope="VALIDATED_LIMITED_CANDIDATE",
            actual_rows_expected=1096,
            hunt_code_rollup_rows=548,
            record_kind="POINT_ROW",
            validation_status="PASS",
            allow_actual_model_target_after_verification_year=True,
        ),
    }


def prediction_files() -> list[PredictionFile]:
    return [
        PredictionFile(
            "predictive_bonus_engine_materialized",
            "audits/prediction_accuracy_backtest/retrospective_outputs/{target_year}/materialized/predictive_bonus_engine_{target_year}.materialized.csv",
            "data_model/runtime_drafts/predictive_bonus_engine_{target_year}.materialized.csv",
        ),
        PredictionFile(
            "ml_draw_predictions_v1",
            "audits/prediction_accuracy_backtest/retrospective_outputs/{target_year}/materialized/ml_draw_predictions_v1.csv",
            "processed_data/ml_draw_predictions_v1.csv",
        ),
    ]


def build_actual_indexes(
    rows: list[dict[str, str]], target_year: int, actual_source: ActualSource
) -> tuple[dict[str, dict[tuple[str, ...], ActualAgg]], dict[str, int]]:
    indexes: dict[str, dict[tuple[str, ...], ActualAgg]] = {
        "hunt_residency_points_draw_pool": defaultdict(ActualAgg),
        "hunt_residency_points": defaultdict(ActualAgg),
        "hunt_residency": defaultdict(ActualAgg),
    }
    stats = Counter()
    for row in rows:
        stats["actual_rows"] += 1
        year_value = row_year(row)
        model_target = model_target_year(row)
        if year_value is not None and year_value > target_year:
            stats["actual_rows_excluded_for_leakage"] += 1
            continue
        if (
            model_target is not None
            and model_target > target_year
            and not actual_source.allow_actual_model_target_after_verification_year
        ):
            stats["actual_rows_excluded_for_leakage"] += 1
            continue
        hunt_code = norm_hunt_code(row.get("hunt_code") or row.get("candidate_hunt_code"))
        if not hunt_code:
            stats["actual_rows_without_hunt_code"] += 1
            continue
        probability, probability_field = choose_actual_probability(row)
        if probability is None:
            stats["actual_rows_without_probability"] += 1
            continue
        residency = norm_residency(row.get("residency"))
        points = norm_points(row.get("points"))
        draw_pool = norm_draw_pool(row.get("draw_pool"))
        if not points:
            stats["actual_rows_without_points"] += 1
        keys = {
            "hunt_residency_points_draw_pool": (hunt_code, residency, points, draw_pool),
            "hunt_residency_points": (hunt_code, residency, points),
            "hunt_residency": (hunt_code, residency),
        }
        for tier, key in keys.items():
            indexes[tier][key].add(row, probability, probability_field)
        stats["actual_usable_rows"] += 1
    return indexes, dict(stats)


def match_actual(
    indexes: dict[str, dict[tuple[str, ...], ActualAgg]],
    hunt_code: str,
    residency: str,
    points: str,
    draw_pool: str,
) -> tuple[str, ActualAgg | None]:
    candidates = [
        ("hunt_residency_points_draw_pool", (hunt_code, residency, points, draw_pool)),
        ("hunt_residency_points", (hunt_code, residency, points)),
        ("hunt_residency", (hunt_code, residency)),
    ]
    for tier, key in candidates:
        match = indexes[tier].get(key)
        if match:
            return tier, match
    return "unmatched", None


def metric_dict(errors: list[float]) -> dict[str, str]:
    if not errors:
        return {
            "mae": "",
            "rmse": "",
            "bias": "",
            "median_abs_error": "",
            "p90_abs_error": "",
        }
    abs_errors = sorted(abs(value) for value in errors)
    mse = sum(value * value for value in errors) / len(errors)
    p90_index = min(len(abs_errors) - 1, max(0, math.ceil(len(abs_errors) * 0.9) - 1))
    return {
        "mae": f"{sum(abs_errors) / len(abs_errors):.6f}",
        "rmse": f"{math.sqrt(mse):.6f}",
        "bias": f"{sum(errors) / len(errors):.6f}",
        "median_abs_error": f"{median(abs_errors):.6f}",
        "p90_abs_error": f"{abs_errors[p90_index]:.6f}",
    }


def source_metadata(actual_source: ActualSource) -> dict[str, object]:
    return {
        "verification_target_year": actual_source.target_year,
        "actual_draw_year": actual_source.actual_draw_year or actual_source.source_year_expected,
        "actual_source_year": actual_source.actual_source_year or actual_source.source_year_expected,
        "actual_model_target_year": actual_source.actual_model_target_year or actual_source.target_year,
        "actual_truth_status": actual_source.actual_truth_status,
        "scope": actual_source.scope,
        "record_kind": actual_source.record_kind,
        "validation_status": actual_source.validation_status,
        "hunt_code_rollup_rows": actual_source.hunt_code_rollup_rows or "",
    }


def method_summary(rows: list[dict[str, str]]) -> str:
    counter = Counter()
    for row in rows:
        method = _first_nonblank(
            row,
            ["prediction_method", "model_strategy", "model_version", "rule_version"],
            "INSUFFICIENT_METADATA",
        )
        counter[method] += 1
    if not counter:
        return "INSUFFICIENT_METADATA"
    return "; ".join(f"{name}:{count}" for name, count in counter.most_common(5))


def circular_warning_status(
    exact_rate: float | None,
    prediction_generation_method: str,
    joined_rows: int,
) -> str:
    if joined_rows <= 0 or exact_rate is None:
        return "INSUFFICIENT_METADATA"
    method_lower = prediction_generation_method.lower()
    is_baseline = (
        "baseline" in method_lower
        or "retrospective" in method_lower
        or "average" in method_lower
    )
    if exact_rate >= 0.999999:
        return "EXACT_COPY_OR_ACTUAL_DERIVED_OUTPUT"
    if exact_rate >= 0.95:
        return "POSSIBLE_CIRCULAR_COMPARISON"
    if is_baseline:
        return "BASELINE_RETROSPECTIVE_NOT_FULL_ENGINE_EQUIVALENT"
    return "OK_TRUE_FORECAST_COMPARISON"


def calibration(errors_rows: list[dict[str, str]]) -> tuple[str, str]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in errors_rows:
        predicted = parse_probability(row.get("prediction_probability"), "")
        actual = parse_probability(row.get("actual_probability"), "")
        if predicted is None or actual is None:
            continue
        bucket_start = int(min(0.9, max(0.0, predicted)) * 10) * 10
        label = f"{bucket_start:02d}-{bucket_start + 10:02d}%"
        buckets[label].append(actual)
    counts = {key: len(values) for key, values in sorted(buckets.items())}
    means = {key: round(sum(values) / len(values), 6) for key, values in sorted(buckets.items()) if values}
    return json.dumps(counts, sort_keys=True), json.dumps(means, sort_keys=True)


def point_bucket(points: str) -> str:
    try:
        value = int(float(points))
    except ValueError:
        return "unknown"
    if value <= 0:
        return "0"
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    if value <= 10:
        return "6-10"
    return "11+"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def verify_pair(
    root: Path,
    out_dir: Path,
    target_year: int,
    prediction_file: PredictionFile,
    actual_source: ActualSource,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    prediction_path = prediction_file.path_for(root, target_year)
    actual_path = actual_source.path_for(root)
    metadata = source_metadata(actual_source)
    pairing_base = {
        "target_year": target_year,
        "prediction_file": str(prediction_path.relative_to(root)) if prediction_path.exists() else str(prediction_path),
        "prediction_kind": prediction_file.kind,
        "actual_truth_file": actual_source.relpath,
        "pairing_confidence": actual_source.confidence,
        "source_year_expected": actual_source.source_year_expected,
        "reason": actual_source.reason,
        **metadata,
    }
    if actual_source.hold:
        pairing = {
            **pairing_base,
            "pairing_status": "HOLD",
            "no_leakage_status": "NOT_EVALUATED",
        }
        summary = {
            **pairing,
            "pairing_reason": actual_source.reason,
        }
        return pairing, summary, []
    if not prediction_path.exists() or not actual_path.exists():
        missing = []
        if not prediction_path.exists():
            if target_year == 2026:
                missing.append("NO_2026_PREDICTION_OUTPUT_FOUND")
            else:
                missing.append("missing_prediction_file")
        if not actual_path.exists():
            missing.append("missing_actual_truth_file")
        pairing = {
            **pairing_base,
            "pairing_status": "INSUFFICIENT_INPUT",
            "no_leakage_status": "NOT_EVALUATED",
            "reason": "; ".join(missing),
        }
        summary = {
            **pairing,
            "pairing_reason": pairing["reason"],
        }
        return pairing, summary, []

    _actual_header, actual_rows = csv_rows(actual_path)
    actual_indexes, actual_stats = build_actual_indexes(actual_rows, target_year, actual_source)
    _prediction_header, prediction_rows = csv_rows(prediction_path)
    prediction_generation_method = method_summary(prediction_rows)

    stats = Counter(actual_stats)
    stats["prediction_rows"] = len(prediction_rows)
    rowlevel: list[dict[str, object]] = []
    errors: list[float] = []
    error_rows: list[dict[str, str]] = []
    join_counts = Counter()
    prediction_probability_fields = Counter()
    actual_probability_fields = Counter()
    identical_probability_count = 0

    for row_number, row in enumerate(prediction_rows, start=2):
        hunt_code = norm_hunt_code(row.get("hunt_code") or row.get("candidate_hunt_code"))
        residency = norm_residency(row.get("residency"))
        points = norm_points(row.get("points"))
        draw_pool = norm_draw_pool(row.get("draw_pool"))
        predicted, _pred_col = choose_probability(row, PREDICTION_CANDIDATE_COLUMNS)
        if _pred_col:
            prediction_probability_fields[_pred_col] += 1
        leaks = prediction_leaks(row, target_year)
        if leaks:
            stats["prediction_rows_with_leakage"] += 1
        if predicted is None:
            stats["prediction_rows_without_probability"] += 1
        join_tier, actual = match_actual(actual_indexes, hunt_code, residency, points, draw_pool)
        if actual is None:
            stats["unmatched_prediction_rows"] += 1
            continue
        if predicted is None or leaks:
            continue
        actual_probability = actual.probability
        error = predicted - actual_probability
        if abs(error) <= 1e-12:
            identical_probability_count += 1
        errors.append(error)
        join_counts[join_tier] += 1
        actual_probability_field = actual.top(actual.probability_fields)
        if actual_probability_field:
            actual_probability_fields[actual_probability_field] += 1
        rowlevel_row = {
            "target_year": target_year,
            "prediction_kind": prediction_file.kind,
            "prediction_file": str(prediction_path.relative_to(root)),
            "prediction_row_number": row_number,
            "hunt_code": hunt_code,
            "residency": residency,
            "points": points,
            "draw_pool": draw_pool,
            "prediction_probability": f"{predicted:.8f}",
            "prediction_probability_field": _pred_col,
            "actual_probability": f"{actual_probability:.8f}",
            "actual_probability_field": actual_probability_field,
            "error": f"{error:.8f}",
            "absolute_error": f"{abs(error):.8f}",
            "join_tier": join_tier,
            "actual_rows_aggregated": actual.count,
            "actual_source_file": actual.top(actual.source_files),
            "actual_source_years": ";".join(str(key) for key in sorted(k for k in actual.source_years if k)),
            "actual_model_target_years": ";".join(str(key) for key in sorted(k for k in actual.model_target_years if k)),
            "actual_family": actual.top(actual.families),
            "actual_species": actual.top(actual.species),
            "prediction_method": row.get("prediction_method", ""),
            "model_version": row.get("model_version", ""),
            "source_row_years": row.get("source_row_years", ""),
            "leakage_status": "LEAKAGE" if leaks else "NO_LEAKAGE",
        }
        rowlevel.append(rowlevel_row)
        error_rows.append({key: str(value) for key, value in rowlevel_row.items()})

    rowlevel_name = f"prediction_vs_actual_{target_year}_{prediction_file.kind}.csv"
    rowlevel_path = out_dir / "rowlevel_verification_outputs" / rowlevel_name
    write_csv(rowlevel_path, ROWLEVEL_FIELDS, rowlevel)

    metric_values = metric_dict(errors)
    calibration_counts, calibration_means = calibration(error_rows)
    exact_rate = (identical_probability_count / len(errors)) if errors else None
    warning_status = circular_warning_status(exact_rate, prediction_generation_method, len(errors))
    prediction_probability_field = prediction_probability_fields.most_common(1)[0][0] if prediction_probability_fields else ""
    actual_probability_field = actual_probability_fields.most_common(1)[0][0] if actual_probability_fields else ""
    no_leakage_status = (
        "PASS"
        if stats.get("actual_rows_excluded_for_leakage", 0) == 0 and stats.get("prediction_rows_with_leakage", 0) == 0
        else "FAIL"
    )
    if errors:
        pairing_status = "EVALUATED"
    elif target_year == 2026 and stats.get("actual_rows", 0) and stats.get("actual_usable_rows", 0) == 0:
        pairing_status = "EVALUATED_NO_SCORABLE_ACTUAL_PROBABILITY"
    else:
        pairing_status = "INSUFFICIENT_JOINED_ROWS"
    pairing = {
        **pairing_base,
        "pairing_status": pairing_status,
        "actual_source_rows": stats.get("actual_rows", 0),
        "actual_usable_rows": stats.get("actual_usable_rows", 0),
        "actual_leakage_rows": stats.get("actual_rows_excluded_for_leakage", 0),
        "prediction_rows": stats.get("prediction_rows", 0),
        "joined_rows": len(errors),
        "no_leakage_status": no_leakage_status,
    }
    summary = {
        **pairing,
        "pairing_reason": actual_source.reason,
        "prediction_generation_method": prediction_generation_method,
        "prediction_probability_field": prediction_probability_field,
        "actual_probability_field": actual_probability_field,
        "probability_exact_match_rate": f"{exact_rate:.6f}" if exact_rate is not None else "",
        "identical_row_probability_count": identical_probability_count,
        "warning_status": warning_status,
        "actual_rows": stats.get("actual_rows", 0),
        "actual_usable_rows": stats.get("actual_usable_rows", 0),
        "joined_rows": len(errors),
        "unmatched_prediction_rows": stats.get("unmatched_prediction_rows", 0),
        "prediction_rows_without_probability": stats.get("prediction_rows_without_probability", 0),
        "actual_rows_without_probability": stats.get("actual_rows_without_probability", 0),
        "actual_rows_excluded_for_leakage": stats.get("actual_rows_excluded_for_leakage", 0),
        "prediction_rows_with_leakage": stats.get("prediction_rows_with_leakage", 0),
        "exact_join_rows": join_counts.get("hunt_residency_points_draw_pool", 0),
        "hunt_residency_points_join_rows": join_counts.get("hunt_residency_points", 0),
        "hunt_residency_join_rows": join_counts.get("hunt_residency", 0),
        "calibration_bucket_counts_json": calibration_counts,
        "calibration_bucket_actual_mean_json": calibration_means,
        **metric_values,
    }
    return pairing, summary, rowlevel


def group_metrics(
    rows: list[dict[str, object]], dimension: str
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if dimension == "family":
            value = norm_text(row.get("actual_family")) or "UNKNOWN"
        elif dimension == "species":
            value = norm_text(row.get("actual_species")) or "UNKNOWN"
        elif dimension == "residency":
            value = norm_residency(row.get("residency"))
        elif dimension == "point_bucket":
            value = point_bucket(norm_points(row.get("points")))
        else:
            value = "UNKNOWN"
        try:
            error = float(str(row.get("error", "")))
        except ValueError:
            continue
        grouped[(int(row["target_year"]), str(row["prediction_kind"]), value)].append(error)

    output: list[dict[str, object]] = []
    for (target_year, kind, value), errors in sorted(grouped.items()):
        output.append(
            {
                "target_year": target_year,
                "prediction_kind": kind,
                "group_value": value,
                "joined_rows": len(errors),
                **metric_dict(errors),
            }
        )
    return output


def markdown_report(
    out_dir: Path,
    pairing_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
    circularity_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    species_rows: list[dict[str, object]],
    residency_rows: list[dict[str, object]],
) -> None:
    evaluated = [row for row in summary_rows if str(row.get("pairing_status", "")).startswith("EVALUATED")]
    held = [row for row in pairing_rows if row.get("pairing_status") == "HOLD"]
    leakage_failures = [row for row in summary_rows if row.get("no_leakage_status") == "FAIL"]

    def top_weakness(rows: list[dict[str, object]], label: str) -> list[str]:
        scored = []
        for row in rows:
            try:
                joined = int(row.get("joined_rows", 0))
                mae = float(row.get("mae", "nan"))
            except (TypeError, ValueError):
                continue
            if joined >= 10 and math.isfinite(mae):
                scored.append((mae, joined, row))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        lines = []
        for mae, joined, row in scored[:8]:
            lines.append(
                f"- {label} `{row.get('group_value')}` target {row.get('target_year')} "
                f"{row.get('prediction_kind')}: MAE={mae:.4f}, rows={joined}"
            )
        return lines or [f"- No {label} weakness rows met the minimum joined-row threshold."]

    lines = [
        "# Prediction Engine Verification Report",
        "",
        "This audit compares retrospective prediction outputs to paired actual draw-truth sources.",
        "",
        "## Pairing Result",
        "",
        "| Target | Prediction kind | Status | Confidence | Joined rows | MAE | RMSE | Bias |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {target_year} | {prediction_kind} | {pairing_status} | {pairing_confidence} | {joined_rows} | {mae} | {rmse} | {bias} |".format(
                **{key: row.get(key, "") for key in SUMMARY_FIELDS}
            )
        )
    for row in held:
        lines.append(
            f"| {row.get('target_year')} | {row.get('prediction_kind')} | HOLD | {row.get('pairing_confidence')} | 0 |  |  |  |"
        )

    warning_counts = Counter(str(row.get("warning_status", "INSUFFICIENT_METADATA")) for row in circularity_rows)
    lines.extend(
        [
            "",
            "## Forecast Vs Reconstruction Warning Labels",
            "",
            "| Warning status | Pair count |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(warning_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "Zero-error or near-zero-error rows are retained in the metrics, but they are not presented as standalone proof of live forecast accuracy when the generation method indicates a baseline retrospective reconstruction or when probabilities exactly match actual truth.",
            "",
            "## No-Leakage Status",
            "",
            f"- Evaluated pairs: {len(evaluated)}",
            f"- Held pairs: {len(held)}",
            f"- Leakage failures: {len(leakage_failures)}",
            "- Rule: actual rows with draw-result `year >= target_year` or `model_target_year > target_year` are excluded; prediction rows with source years at or after the target year are not scored.",
            "",
            "## Biggest Weaknesses By Family",
            "",
            *top_weakness(family_rows, "family"),
            "",
            "## Biggest Weaknesses By Species",
            "",
            *top_weakness(species_rows, "species"),
            "",
            "## Biggest Weaknesses By Residency",
            "",
            *top_weakness(residency_rows, "residency"),
            "",
            "## Notes",
            "",
            "- Target 2026 is evaluated when production 2026 prediction outputs are present, using the validated limited 2026 actual truth file for evaluation only.",
            "- The 2026 actual truth file has `model_target_year=2027`; that is not treated as leakage because the verification target uses `actual_draw_year/source_year=2026`.",
            "- Row-level joins are written under an ignored folder and are not intended for GitHub commits.",
            "- Retrospective baseline rows are separated from true forecast comparisons by `27_prediction_actual_circularity_audit.csv`.",
        ]
    )
    (out_dir / "PREDICTION_ENGINE_VERIFICATION_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = [int(part.strip()) for part in args.target_years.split(",") if part.strip()]
    source_map = actual_sources()
    pairing_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    all_rowlevel_rows: list[dict[str, object]] = []

    for target_year in targets:
        actual_source = source_map[target_year]
        for prediction_file in prediction_files():
            pairing, summary, rowlevel = verify_pair(root, out_dir, target_year, prediction_file, actual_source)
            pairing_rows.append(pairing)
            if summary.get("pairing_status") != "HOLD":
                summary_rows.append(summary)
            all_rowlevel_rows.extend(rowlevel)

    family_rows = group_metrics(all_rowlevel_rows, "family")
    species_rows = group_metrics(all_rowlevel_rows, "species")
    residency_rows = group_metrics(all_rowlevel_rows, "residency")
    point_bucket_rows = group_metrics(all_rowlevel_rows, "point_bucket")
    circularity_rows = [
        {field: row.get(field, "") for field in CIRCULARITY_FIELDS}
        for row in summary_rows
    ]

    write_csv(out_dir / "20_actual_truth_pairing_plan.csv", PAIRING_FIELDS, pairing_rows)
    write_csv(out_dir / "21_prediction_vs_actual_accuracy_summary.csv", SUMMARY_FIELDS, summary_rows)
    write_csv(out_dir / "22_prediction_vs_actual_accuracy_by_family.csv", GROUP_FIELDS, family_rows)
    write_csv(out_dir / "23_prediction_vs_actual_accuracy_by_species.csv", GROUP_FIELDS, species_rows)
    write_csv(out_dir / "24_prediction_vs_actual_accuracy_by_residency.csv", GROUP_FIELDS, residency_rows)
    write_csv(out_dir / "25_prediction_vs_actual_accuracy_by_point_bucket.csv", GROUP_FIELDS, point_bucket_rows)
    write_csv(out_dir / "27_prediction_actual_circularity_audit.csv", CIRCULARITY_FIELDS, circularity_rows)
    markdown_report(out_dir, pairing_rows, summary_rows, circularity_rows, family_rows, species_rows, residency_rows)

    leakage_failures = [row for row in summary_rows if row.get("no_leakage_status") == "FAIL"]
    evaluated = [row for row in summary_rows if str(row.get("pairing_status", "")).startswith("EVALUATED")]
    print(
        json.dumps(
            {
                "evaluated_pairs": len(evaluated),
                "held_pairs": len([row for row in pairing_rows if row.get("pairing_status") == "HOLD"]),
                "leakage_failures": len(leakage_failures),
                "joined_rows": sum(int(row.get("joined_rows", 0) or 0) for row in evaluated),
                "out_dir": str(out_dir),
            },
            indent=2,
        )
    )
    return 1 if leakage_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
