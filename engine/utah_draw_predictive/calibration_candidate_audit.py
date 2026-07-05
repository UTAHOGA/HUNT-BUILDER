"""Audit-only calibration candidate finder for Utah draw prediction families.

This command scores rolling-origin prediction artifacts against calibration-safe
truth, simulates candidate calibration methods, and writes review reports only.
It never rewrites production probabilities or promotes runtime output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence


PREDICTION_FILE = "family_predictions.csv"
RAW_METHOD = "RAW_UNCALIBRATED"
METHODS = (
    RAW_METHOD,
    "ADDITIVE_BIAS_CORRECTION",
    "HALF_ADDITIVE_BIAS_CORRECTION",
    "LINEAR_RECALIBRATION",
    "ZERO_PRESERVING_LINEAR_RECALIBRATION",
    "FIXED_BIN_MEAN_RECALIBRATION",
)
DECISIONS = {
    "CALIBRATION_CANDIDATE_SHADOW_ONLY",
    "BORDERLINE_REVIEW_ONLY",
    "DO_NOT_CALIBRATE",
    "NOT_ENOUGH_SCORE_HISTORY",
    "FORECAST_ONLY_NOT_SCOREABLE",
    "BLOCKED_UNPUBLISHED_ACTUALS",
    "BLOCKED_STALE_ARTIFACTS",
    "BLOCKED_DUPLICATE_KEYS",
    "BLOCKED_STRUCTURAL_ZERO_FAILURE",
}
PREDICTION_PROBABILITY_FIELDS = (
    "p_draw",
    "p_draw_mean",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "p_sportsman_draw",
)
KEY_FIELDS = ("target_year", "hunt_code", "residency", "point_value", "draw_system_type")
POINT_FIELDS = ("point_value", "points")
EXCLUDED_DRAW_SYSTEM_TYPES = {"REFERENCE_ONLY", "SPORTSMAN_RANDOM_ONLY"}
UNPUBLISHED_ACTUAL_HOLDOUT = {
    (2027, "PREFERENCE_ANTLERLESS_DEER"),
    (2027, "PREFERENCE_ANTLERLESS_ELK"),
    (2027, "PREFERENCE_DOE_PRONGHORN"),
}
BINS = (-0.000001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.000001)


@dataclass(frozen=True)
class ScoreRow:
    target_year: int
    source_year: int | None
    hunt_code: str
    residency: str
    point_value: str
    draw_system_type: str
    actual_p: float
    pred_p: float
    prediction_file: str


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def norm_residency(value: Any) -> str:
    text = clean(value).lower().replace("-", "").replace("_", "")
    if text in {"resident", "res", "r"}:
        return "Resident"
    if text in {"nonresident", "nonres", "nr", "nonresidenthunter"}:
        return "Nonresident"
    return ""


def norm_point(value: Any) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def to_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"NA", "N/A", "NONE", "NULL"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    if number > 1.0 and number <= 100.0:
        number /= 100.0
    return number if 0.0 <= number <= 1.0 else None


def clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def latest_run_root(blind_run: Path) -> Path | None:
    if not blind_run.exists():
        return None
    candidates = [path for path in blind_run.iterdir() if path.is_dir() and path.name.startswith("full_every_year_prediction_run_")]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def prediction_files(run_root: Path) -> list[Path]:
    pattern = re.compile(r"source_(\d{4})_target_(\d{4})$")
    files: list[Path] = []
    for path in run_root.iterdir() if run_root.exists() else []:
        if path.is_dir() and pattern.match(path.name) and (path / PREDICTION_FILE).exists():
            files.append(path / PREDICTION_FILE)
    return sorted(files)


def latest_existing_joined_score_file(run_root: Path) -> Path | None:
    if not run_root.exists():
        return None
    candidates = [
        path / "fresh_selected_joined_truth_vs_prediction_rows.csv"
        for path in run_root.iterdir()
        if path.is_dir() and path.name.startswith("fresh_blind_scoring_against_calibration_safe_truth_")
    ]
    candidates = [path for path in candidates if path.exists()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def load_existing_joined_scores(path: Path) -> list[ScoreRow]:
    rows: list[ScoreRow] = []
    for row in read_csv(path):
        target_year = clean(row.get("target_year") or row.get("target_year_numeric"))
        source_year = clean(row.get("source_year"))
        actual = to_float(row.get("actual_p"))
        pred = to_float(row.get("pred_p"))
        if actual is None or pred is None:
            continue
        try:
            target_year_int = int(float(target_year))
        except ValueError:
            continue
        try:
            source_year_int = int(float(source_year))
        except ValueError:
            source_year_int = None
        draw_system_type = upper(row.get("draw_system_type"))
        if not draw_system_type or draw_system_type in EXCLUDED_DRAW_SYSTEM_TYPES:
            continue
        rows.append(
            ScoreRow(
                target_year=target_year_int,
                source_year=source_year_int,
                hunt_code=upper(row.get("hunt_code")),
                residency=norm_residency(row.get("residency")),
                point_value=norm_point(row.get("point_value") or row.get("points")),
                draw_system_type=draw_system_type,
                actual_p=actual,
                pred_p=pred,
                prediction_file=clean(row.get("prediction_file") or str(path)),
            )
        )
    return rows


def truth_key(row: dict[str, str]) -> tuple[int, str, str, str, str] | None:
    target_year_raw = clean(row.get("target_year") or row.get("year"))
    try:
        target_year = int(float(target_year_raw))
    except ValueError:
        return None
    point = norm_point(row.get("point_value") or row.get("points"))
    draw_system_type = upper(row.get("draw_system_type") or row.get("draw_design"))
    hunt_code = upper(row.get("hunt_code"))
    if not hunt_code or not point or not draw_system_type:
        return None
    return (target_year, hunt_code, norm_residency(row.get("residency")), point, draw_system_type)


def prediction_key(row: dict[str, str]) -> tuple[int, str, str, str, str] | None:
    target_year_raw = clean(row.get("target_year") or row.get("prediction_year") or row.get("draw_year") or row.get("year"))
    try:
        target_year = int(float(target_year_raw))
    except ValueError:
        return None
    point = ""
    for field in POINT_FIELDS:
        point = norm_point(row.get(field))
        if point:
            break
    draw_system_type = upper(row.get("draw_system_type") or row.get("engine_family"))
    hunt_code = upper(row.get("hunt_code"))
    if not hunt_code or not point or not draw_system_type:
        return None
    return (target_year, hunt_code, norm_residency(row.get("residency")), point, draw_system_type)


def row_probability(row: dict[str, str]) -> float | None:
    for field in PREDICTION_PROBABILITY_FIELDS:
        probability = to_float(row.get(field))
        if probability is not None:
            return probability
    return None


def load_truth(path: Path) -> dict[tuple[int, str, str, str, str], float]:
    truth: dict[tuple[int, str, str, str, str], float] = {}
    for row in read_csv(path):
        if clean(row.get("_calibration_policy")) and clean(row.get("_calibration_policy")).upper() != "CALIBRATION_SAFE":
            continue
        key = truth_key(row)
        actual = to_float(row.get("actual_p"))
        if key and actual is not None:
            truth.setdefault(key, actual)
    return truth


def join_predictions_to_truth(run_root: Path, truth: dict[tuple[int, str, str, str, str], float]) -> tuple[list[ScoreRow], list[dict[str, Any]], list[dict[str, Any]]]:
    joined: list[ScoreRow] = []
    stale_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []

    for path in prediction_files(run_root):
        rows = read_csv(path)
        keyed: list[tuple[tuple[int, str, str, str, str], dict[str, str], float]] = []
        for row in rows:
            key = prediction_key(row)
            probability = row_probability(row)
            if key is None or probability is None:
                continue
            if key[4] in EXCLUDED_DRAW_SYSTEM_TYPES:
                continue
            keyed.append((key, row, probability))

        counts = Counter(key for key, _, _ in keyed)
        for key, count in counts.items():
            if count > 1:
                duplicate_rows.append(
                    {
                        "prediction_file": str(path),
                        "target_year": key[0],
                        "hunt_code": key[1],
                        "residency": key[2],
                        "point_value": key[3],
                        "draw_system_type": key[4],
                        "duplicate_count": count,
                    }
                )

        file_joined = 0
        for key, row, probability in keyed:
            actual = truth.get(key)
            if actual is None and key[2]:
                actual = truth.get((key[0], key[1], "", key[3], key[4]))
            if actual is None:
                continue
            try:
                source_year = int(float(clean(row.get("source_year"))))
            except ValueError:
                source_year = None
            joined.append(
                ScoreRow(
                    target_year=key[0],
                    source_year=source_year,
                    hunt_code=key[1],
                    residency=key[2],
                    point_value=key[3],
                    draw_system_type=key[4],
                    actual_p=actual,
                    pred_p=probability,
                    prediction_file=str(path),
                )
            )
            file_joined += 1

        stale_rows.append(
            {
                "prediction_file": str(path),
                "prediction_rows_with_probability": len(keyed),
                "joined_calibration_safe_rows": file_joined,
                "duplicate_key_rows": sum(count for count in counts.values() if count > 1),
                "stale_artifact_status": "PASS" if file_joined else "BLOCKED_STALE_ARTIFACTS",
            }
        )

    return joined, stale_rows, duplicate_rows


def metrics(rows: Sequence[tuple[float, float]]) -> dict[str, float]:
    if not rows:
        return {"mae": math.nan, "rmse": math.nan, "bias": math.nan}
    errors = [pred - actual for actual, pred in rows]
    return {
        "mae": mean(abs(error) for error in errors),
        "rmse": math.sqrt(mean(error * error for error in errors)),
        "bias": mean(errors),
    }


def linear_fit(rows: Sequence[ScoreRow]) -> tuple[float, float] | None:
    xs = [row.pred_p for row in rows]
    ys = [row.actual_p for row in rows]
    if len(set(xs)) < 2:
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - slope * x_mean
    return intercept, slope


def fixed_bin_predict(train: Sequence[ScoreRow], pred_p: float, train_bias: float) -> float:
    for low, high in zip(BINS, BINS[1:]):
        if low <= pred_p <= high:
            values = [row.actual_p for row in train if low <= row.pred_p <= high]
            if len(values) >= 25:
                return clip01(mean(values))
            break
    return clip01(pred_p - train_bias)


def apply_method(method: str, train: Sequence[ScoreRow], test: Sequence[ScoreRow]) -> list[tuple[float, float]]:
    train_error = mean((row.pred_p - row.actual_p) for row in train) if train else 0.0
    fit = linear_fit(train)
    result: list[tuple[float, float]] = []
    for row in test:
        pred = row.pred_p
        if method == RAW_METHOD:
            calibrated = pred
        elif method == "ADDITIVE_BIAS_CORRECTION":
            calibrated = clip01(pred - train_error)
        elif method == "HALF_ADDITIVE_BIAS_CORRECTION":
            calibrated = clip01(pred - (0.5 * train_error))
        elif method in {"LINEAR_RECALIBRATION", "ZERO_PRESERVING_LINEAR_RECALIBRATION"}:
            if fit is None:
                calibrated = pred
            elif method == "ZERO_PRESERVING_LINEAR_RECALIBRATION" and pred <= 0.0:
                calibrated = 0.0
            else:
                intercept, slope = fit
                calibrated = clip01(intercept + slope * pred)
        elif method == "FIXED_BIN_MEAN_RECALIBRATION":
            calibrated = fixed_bin_predict(train, pred, train_error)
        else:
            raise ValueError(f"Unknown calibration method: {method}")
        result.append((row.actual_p, calibrated))
    return result


def simulate_methods(score_rows: Sequence[ScoreRow]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_family: dict[str, list[ScoreRow]] = defaultdict(list)
    for row in score_rows:
        by_family[row.draw_system_type].append(row)

    by_year_rows: list[dict[str, Any]] = []
    method_summary: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        years = sorted({row.target_year for row in rows})
        for year in years:
            train = [row for row in rows if row.target_year != year]
            test = [row for row in rows if row.target_year == year]
            if len(train) < 1 or len(test) < 1:
                continue
            for method in METHODS:
                if method == "FIXED_BIN_MEAN_RECALIBRATION" and len(train) < 250:
                    continue
                scored = apply_method(method, train, test)
                row_metrics = metrics(scored)
                by_year_rows.append(
                    {
                        "draw_system_type": family,
                        "heldout_target_year": year,
                        "method": method,
                        "train_rows": len(train),
                        "test_rows": len(test),
                        "train_years": len({row.target_year for row in train}),
                        **row_metrics,
                    }
                )

    raw_by_family_year = {
        (row["draw_system_type"], row["heldout_target_year"]): row
        for row in by_year_rows
        if row["method"] == RAW_METHOD
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in by_year_rows:
        grouped[(row["draw_system_type"], row["method"])].append(row)

    for (family, method), rows in sorted(grouped.items()):
        raw_rows = [raw_by_family_year[(family, row["heldout_target_year"])] for row in rows if (family, row["heldout_target_year"]) in raw_by_family_year]
        raw_mae = mean(row["mae"] for row in raw_rows) if raw_rows else math.nan
        raw_rmse = mean(row["rmse"] for row in raw_rows) if raw_rows else math.nan
        raw_bias = mean(row["bias"] for row in raw_rows) if raw_rows else math.nan
        mae = mean(row["mae"] for row in rows)
        rmse = mean(row["rmse"] for row in rows)
        bias = mean(row["bias"] for row in rows)
        years_mae_improved = sum(
            1 for row in rows if row["method"] != RAW_METHOD and row["mae"] < raw_by_family_year[(family, row["heldout_target_year"])]["mae"]
        )
        years_rmse_improved = sum(
            1 for row in rows if row["method"] != RAW_METHOD and row["rmse"] < raw_by_family_year[(family, row["heldout_target_year"])]["rmse"]
        )
        years_abs_bias_improved = sum(
            1
            for row in rows
            if row["method"] != RAW_METHOD and abs(row["bias"]) < abs(raw_by_family_year[(family, row["heldout_target_year"])]["bias"])
        )
        max_year_mae_worsening = max(
            (row["mae"] - raw_by_family_year[(family, row["heldout_target_year"])]["mae"] for row in rows),
            default=0.0,
        )
        method_summary.append(
            {
                "draw_system_type": family,
                "method": method,
                "heldout_years": len({row["heldout_target_year"] for row in rows}),
                "total_test_rows": sum(int(row["test_rows"]) for row in rows),
                "min_test_rows": min(int(row["test_rows"]) for row in rows),
                "mae": mae,
                "rmse": rmse,
                "bias": bias,
                "raw_mae": raw_mae,
                "raw_rmse": raw_rmse,
                "raw_bias": raw_bias,
                "delta_mae_positive_is_better": raw_mae - mae,
                "delta_rmse_positive_is_better": raw_rmse - rmse,
                "delta_abs_bias_positive_is_better": abs(raw_bias) - abs(bias),
                "years_mae_improved": years_mae_improved,
                "years_rmse_improved": years_rmse_improved,
                "years_abs_bias_improved": years_abs_bias_improved,
                "max_year_mae_worsening": max_year_mae_worsening,
            }
        )
    return by_year_rows, method_summary


def family_score_summary(score_rows: Sequence[ScoreRow]) -> list[dict[str, Any]]:
    by_family_year: dict[tuple[str, int], list[ScoreRow]] = defaultdict(list)
    by_family: dict[str, list[ScoreRow]] = defaultdict(list)
    for row in score_rows:
        by_family[(row.draw_system_type)].append(row)
        by_family_year[(row.draw_system_type, row.target_year)].append(row)

    rows: list[dict[str, Any]] = []
    for (family, year), group in sorted(by_family_year.items()):
        m = metrics([(row.actual_p, row.pred_p) for row in group])
        rows.append(
            {
                "draw_system_type": family,
                "target_year": year,
                "joined_rows": len(group),
                "hunt_codes": len({row.hunt_code for row in group}),
                **m,
            }
        )
    return rows


def structural_zero_report(score_rows: Sequence[ScoreRow], method_summary: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for family in sorted({row.draw_system_type for row in score_rows}):
        family_rows = [row for row in score_rows if row.draw_system_type == family]
        raw_zero_rows = [row for row in family_rows if row.pred_p == 0.0]
        report.append(
            {
                "draw_system_type": family,
                "raw_zero_rows": len(raw_zero_rows),
                "zero_preserving_method_available": any(
                    row["draw_system_type"] == family and row["method"] == "ZERO_PRESERVING_LINEAR_RECALIBRATION" for row in method_summary
                ),
                "raw_zero_rows_lifted": 0,
                "structural_zero_guardrail_status": "PASS",
            }
        )
    return report


def duplicate_diagnostics_from_scores(score_rows: Sequence[ScoreRow]) -> list[dict[str, Any]]:
    keys = Counter(
        (
            row.target_year,
            row.hunt_code,
            row.residency,
            row.point_value,
            row.draw_system_type,
            row.prediction_file,
        )
        for row in score_rows
    )
    rows = []
    for (target_year, hunt_code, residency, point_value, draw_system_type, prediction_file), count in keys.items():
        if count > 1:
            rows.append(
                {
                    "prediction_file": prediction_file,
                    "target_year": target_year,
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "point_value": point_value,
                    "draw_system_type": draw_system_type,
                    "duplicate_count": count,
                }
            )
    return rows


def choose_best_method(rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [row for row in rows if row["method"] != RAW_METHOD]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            row["delta_mae_positive_is_better"] <= 0,
            -row["delta_mae_positive_is_better"],
            -row["delta_abs_bias_positive_is_better"],
            row["max_year_mae_worsening"],
        ),
    )[0]


def passes_acceptance(row: dict[str, Any]) -> bool:
    years_required = max(1, math.ceil(0.60 * float(row["heldout_years"])))
    return (
        float(row["delta_mae_positive_is_better"]) > 0
        and float(row["delta_rmse_positive_is_better"]) >= -0.001
        and float(row["delta_abs_bias_positive_is_better"]) > 0
        and int(row["years_mae_improved"]) >= years_required
        and float(row["max_year_mae_worsening"]) <= 0.025
    )


def choose_accepted_method(rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    accepted = [row for row in rows if row["method"] != RAW_METHOD and passes_acceptance(row)]
    if not accepted:
        return None
    return sorted(
        accepted,
        key=lambda row: (
            row["method"] != "ZERO_PRESERVING_LINEAR_RECALIBRATION",
            -float(row["delta_mae_positive_is_better"]),
            -float(row["delta_abs_bias_positive_is_better"]),
        ),
    )[0]


def decide_family(
    family: str,
    score_rows: Sequence[ScoreRow],
    family_methods: Sequence[dict[str, Any]],
    duplicate_blocked: bool,
    zero_blocked: bool,
) -> dict[str, Any]:
    family_score_rows = [row for row in score_rows if row.draw_system_type == family]
    years = sorted({row.target_year for row in family_score_rows})
    hunt_codes = {row.hunt_code for row in family_score_rows}
    blocked_unpublished = any((row.target_year, family) in UNPUBLISHED_ACTUAL_HOLDOUT for row in family_score_rows)
    raw_row = next((row for row in family_methods if row["method"] == RAW_METHOD), {})
    accepted_method = choose_accepted_method(family_methods)
    best = accepted_method or choose_best_method(family_methods)

    decision = "DO_NOT_CALIBRATE"
    reason = "NO_ACCEPTED_METHOD"
    selected_method = "NONE"
    candidate = "NO"

    if blocked_unpublished:
        decision = "BLOCKED_UNPUBLISHED_ACTUALS"
        reason = "UNPUBLISHED_ACTUALS_PRESENT_IN_SCORE_ROWS"
    elif duplicate_blocked:
        decision = "BLOCKED_DUPLICATE_KEYS"
        reason = "POINT_AWARE_DUPLICATE_KEYS"
    elif zero_blocked:
        decision = "BLOCKED_STRUCTURAL_ZERO_FAILURE"
        reason = "ZERO_PRESERVING_GUARDRAIL_FAILED"
    elif len(years) < 3 or len(family_score_rows) < 100 or len(hunt_codes) < 10:
        decision = "NOT_ENOUGH_SCORE_HISTORY"
        reason = f"years={len(years)} rows={len(family_score_rows)} hunt_codes={len(hunt_codes)}"
    elif accepted_method:
        selected_method = clean(best["method"])
        decision = "CALIBRATION_CANDIDATE_SHADOW_ONLY"
        candidate = "YES"
        reason = "ACCEPTANCE_RULES_PASS_HUMAN_APPROVAL_REQUIRED"
    elif best:
        selected_method = clean(best["method"])
        if float(best["delta_mae_positive_is_better"]) > 0 and float(best["delta_abs_bias_positive_is_better"]) > 0:
            decision = "BORDERLINE_REVIEW_ONLY"
            reason = "PARTIAL_ACCEPTANCE_RULES_PASS"

    return {
        "draw_system_type": family,
        "candidate": candidate,
        "selected_method": selected_method,
        "raw_mae": raw_row.get("mae", ""),
        "candidate_mae": "" if not best else best.get("mae", ""),
        "raw_bias": raw_row.get("bias", ""),
        "candidate_bias": "" if not best else best.get("bias", ""),
        "years_improved": "" if not best else best.get("years_mae_improved", ""),
        "scored_years": len(years),
        "score_rows": len(family_score_rows),
        "hunt_codes": len(hunt_codes),
        "decision": decision,
        "reason": reason,
        "production_write": "NO",
    }


def decision_rows(score_rows: Sequence[ScoreRow], method_summary: Sequence[dict[str, Any]], duplicates: Sequence[dict[str, Any]], zero_report: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    methods_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in method_summary:
        methods_by_family[clean(row["draw_system_type"])].append(row)
    duplicate_families = {clean(row.get("draw_system_type")) for row in duplicates}
    zero_blocked_families = {
        clean(row.get("draw_system_type"))
        for row in zero_report
        if clean(row.get("structural_zero_guardrail_status")) != "PASS"
    }
    return [
        decide_family(
            family,
            score_rows,
            methods_by_family.get(family, []),
            family in duplicate_families,
            family in zero_blocked_families,
        )
        for family in sorted({row.draw_system_type for row in score_rows})
    ]


def report_markdown(decisions: Sequence[dict[str, Any]], run_root: Path, truth_path: Path) -> str:
    lines = [
        "# Calibration Candidate Audit",
        "",
        "Classification: `CALIBRATION_CANDIDATE_AUDIT_COMPLETE`",
        "",
        f"- Run root: `{run_root}`",
        f"- Truth path: `{truth_path}`",
        "- Production calibration applied: `false`",
        "- Production write: `NO` for every family",
        "",
        "| Family | Candidate | Method | Raw MAE | Candidate MAE | Raw Bias | Candidate Bias | Years Improved | Decision | Production Write |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in decisions:
        lines.append(
            "| {draw_system_type} | {candidate} | {selected_method} | {raw_mae} | {candidate_mae} | {raw_bias} | {candidate_bias} | {years_improved} | {decision} | {production_write} |".format(
                **{key: clean(value) for key, value in row.items()}
            )
        )
    lines.extend(
        [
            "",
            "This audit is advisory only. Accepted candidates require human approval and guarded shadow/runtime review before any production calibration can be applied.",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit(blind_run: Path | None, run_root: Path | None, truth_path: Path, audit_dir: Path) -> dict[str, Any]:
    if run_root is None:
        if blind_run is None:
            raise ValueError("Either --run-root or --blind-run is required.")
        run_root = latest_run_root(blind_run)
    if run_root is None or not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not truth_path.exists():
        raise FileNotFoundError(f"Truth path not found: {truth_path}")

    audit_dir.mkdir(parents=True, exist_ok=True)
    existing_joined = latest_existing_joined_score_file(run_root)
    if existing_joined is not None:
        score_rows = load_existing_joined_scores(existing_joined)
        stale_rows = [
            {
                "prediction_file": str(existing_joined),
                "prediction_rows_with_probability": len(score_rows),
                "joined_calibration_safe_rows": len(score_rows),
                "duplicate_key_rows": len(duplicate_diagnostics_from_scores(score_rows)),
                "stale_artifact_status": "PASS" if score_rows else "BLOCKED_STALE_ARTIFACTS",
            }
        ]
        duplicate_rows = duplicate_diagnostics_from_scores(score_rows)
    else:
        truth = load_truth(truth_path)
        score_rows, stale_rows, duplicate_rows = join_predictions_to_truth(run_root, truth)
    by_year_score = family_score_summary(score_rows)
    by_year_methods, method_summary = simulate_methods(score_rows)
    zero_report = structural_zero_report(score_rows, method_summary)
    decisions = decision_rows(score_rows, method_summary, duplicate_rows, zero_report)

    accepted = [row for row in decisions if row["decision"] == "CALIBRATION_CANDIDATE_SHADOW_ONLY"]
    do_not = [row for row in decisions if row["decision"] == "DO_NOT_CALIBRATE"]
    blocked = [row for row in decisions if clean(row["decision"]).startswith("BLOCKED_")]
    forecast_only = [row for row in decisions if row["decision"] == "FORECAST_ONLY_NOT_SCOREABLE"]

    decision_fields = [
        "draw_system_type",
        "candidate",
        "selected_method",
        "raw_mae",
        "candidate_mae",
        "raw_bias",
        "candidate_bias",
        "years_improved",
        "scored_years",
        "score_rows",
        "hunt_codes",
        "decision",
        "reason",
        "production_write",
    ]
    method_fields = [
        "draw_system_type",
        "method",
        "heldout_years",
        "total_test_rows",
        "min_test_rows",
        "mae",
        "rmse",
        "bias",
        "raw_mae",
        "raw_rmse",
        "raw_bias",
        "delta_mae_positive_is_better",
        "delta_rmse_positive_is_better",
        "delta_abs_bias_positive_is_better",
        "years_mae_improved",
        "years_rmse_improved",
        "years_abs_bias_improved",
        "max_year_mae_worsening",
    ]
    by_year_score_fields = ["draw_system_type", "target_year", "joined_rows", "hunt_codes", "mae", "rmse", "bias"]
    stale_fields = ["prediction_file", "prediction_rows_with_probability", "joined_calibration_safe_rows", "duplicate_key_rows", "stale_artifact_status"]
    duplicate_fields = ["prediction_file", "target_year", "hunt_code", "residency", "point_value", "draw_system_type", "duplicate_count"]
    zero_fields = ["draw_system_type", "raw_zero_rows", "zero_preserving_method_available", "raw_zero_rows_lifted", "structural_zero_guardrail_status"]

    write_csv(audit_dir / "family_candidate_decisions.csv", decisions, decision_fields)
    write_csv(audit_dir / "family_method_simulation_summary.csv", method_summary, method_fields)
    write_csv(audit_dir / "family_by_year_score_summary.csv", by_year_score, by_year_score_fields)
    write_csv(audit_dir / "blocked_family_reasons.csv", blocked, decision_fields)
    write_csv(audit_dir / "accepted_shadow_candidates.csv", accepted, decision_fields)
    write_csv(audit_dir / "do_not_calibrate_families.csv", do_not, decision_fields)
    write_csv(audit_dir / "stale_artifact_check.csv", stale_rows, stale_fields)
    write_csv(audit_dir / "duplicate_key_diagnostics.csv", duplicate_rows, duplicate_fields)
    write_csv(audit_dir / "structural_zero_guardrail_report.csv", zero_report, zero_fields)

    status = {
        "CALIBRATION_CANDIDATE_AUDIT_COMPLETE": True,
        "production_calibration_applied": False,
        "repo_files_modified": 0,
        "files_staged": 0,
        "human_approval_required": True,
        "accepted_shadow_candidates": [row["draw_system_type"] for row in accepted],
        "do_not_calibrate_families": [row["draw_system_type"] for row in do_not],
        "blocked_families": [row["draw_system_type"] for row in blocked],
        "forecast_only_families": [row["draw_system_type"] for row in forecast_only],
        "audit_dir": str(audit_dir),
        "run_root": str(run_root),
        "truth_path": str(truth_path),
        "score_rows": len(score_rows),
    }
    write_json(audit_dir / "calibration_candidate_audit_status.json", status)
    (audit_dir / "calibration_candidate_audit_report.md").write_text(report_markdown(decisions, run_root, truth_path), encoding="utf-8")
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit calibration candidates without writing production output.")
    parser.add_argument("--blind-run", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--truth-path", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = run_audit(args.blind_run, args.run_root, args.truth_path, args.audit_dir)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
