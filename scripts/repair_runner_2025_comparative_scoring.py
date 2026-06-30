from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / "audits" / "full_engine_all_year_repair_20260629_032752"
TARGET_YEAR = "2025"
SOURCE_YEAR = "2024"
FAMILIES = [
    "preference_general_deer",
    "dedicated_hunter",
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_residency(value: object) -> str:
    text = clean(value).lower()
    if text in {"resident", "res"}:
        return "Resident"
    if text in {"nonresident", "non-resident", "non resident", "nr"}:
        return "Nonresident"
    return clean(value)


def norm_point(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer():
        return str(int(number))
    return text


def num(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        value_float = float(text)
    except ValueError:
        return None
    return value_float if math.isfinite(value_float) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    fields = fields or ["no_rows"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def actual_probability(row: dict[str, str], residency: str) -> tuple[float | None, float]:
    prefix = "resident" if residency == "Resident" else "nonresident"
    applicants = num(row.get(f"{prefix}_eligible_applicants")) or 0.0
    p_draw = num(row.get(f"{prefix}_p_draw"))
    p_pct = num(row.get(f"{prefix}_p_draw_percent"))
    if p_draw is not None:
        return max(0.0, min(1.0, p_draw)), applicants
    if p_pct is not None:
        return max(0.0, min(1.0, p_pct / 100.0)), applicants
    permits = num(row.get(f"{prefix}_total_permits"))
    if applicants > 0 and permits is not None:
        return max(0.0, min(1.0, permits / applicants)), applicants
    return None, applicants


def prediction_probability(row: dict[str, str]) -> tuple[float | None, float]:
    for field in ("p_draw_mean", "p_draw", "p_preference_draw"):
        value = num(row.get(field))
        if value is not None:
            return max(0.0, min(1.0, value)), num(row.get("applicants_at_level")) or 0.0
    pct = num(row.get("display_odds_pct")) or num(row.get("p_draw_pct"))
    if pct is not None:
        return max(0.0, min(1.0, pct / 100.0)), num(row.get("applicants_at_level")) or 0.0
    return None, num(row.get("applicants_at_level")) or 0.0


def family_for_actual(row: dict[str, str]) -> str:
    code = clean(row.get("hunt_code")).upper()
    source = " ".join(
        clean(row.get(field))
        for field in ("source_scope", "source_namespace", "hunt_draw_class", "hunt_type")
    ).upper()
    if "DEDICATED" in source or code.startswith("DB17"):
        return "dedicated_hunter"
    if code.startswith("DB15") or code.startswith("DB16") or "GENERAL_SEASON_BUCK_DEER" in source:
        return "preference_general_deer"
    if code.startswith("DA"):
        return "preference_antlerless_deer"
    if code.startswith("EA"):
        return "preference_antlerless_elk"
    if code.startswith("PD"):
        return "preference_doe_pronghorn"
    return ""


def main() -> int:
    canonical = (
        REPO
        / "data_truth"
        / "draw_results_truth"
        / "normalized"
        / "canonical_yearly"
        / "draw_results_2024_for_2025_canonical_yearly_draw_results.csv"
    )
    actual_rows = read_csv(canonical)

    actual_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in actual_rows:
        if clean(row.get("record_type")) != "point_level_draw_result":
            continue
        family = family_for_actual(row)
        if family not in FAMILIES:
            continue
        code = clean(row.get("hunt_code")).upper()
        point = norm_point(row.get("points"))
        for residency in ("Resident", "Nonresident"):
            prob, applicants = actual_probability(row, residency)
            key = (family, code, residency, point)
            existing = actual_by_key.get(key)
            if existing is None or applicants > (num(existing.get("actual_applicants")) or 0.0):
                actual_by_key[key] = {
                    "family": family,
                    "hunt_code": code,
                    "residency": residency,
                    "point": point,
                    "actual_probability": "" if prob is None else f"{prob:.12g}",
                    "actual_applicants": f"{applicants:.12g}",
                }

    joined_rows: list[dict[str, object]] = []
    summary = defaultdict(lambda: Counter())
    metrics = defaultdict(lambda: {"rows": 0, "mae": 0.0, "rmse2": 0.0, "bias": 0.0})

    for family in FAMILIES:
        pred_path = AUDIT / "runs" / TARGET_YEAR / "predictions" / f"{SOURCE_YEAR}_{TARGET_YEAR}_{family}.csv"
        if not pred_path.exists():
            continue
        for pred in read_csv(pred_path):
            code = clean(pred.get("hunt_code")).upper()
            residency = norm_residency(pred.get("residency"))
            point = norm_point(pred.get("points"))
            key = (family, code, residency, point)
            actual = actual_by_key.get(key)
            pred_prob, predicted_applicants = prediction_probability(pred)
            actual_prob = num(actual.get("actual_probability")) if actual else None
            actual_applicants = num(actual.get("actual_applicants")) if actual else 0.0

            exclusion_reason = ""
            if actual is None:
                exclusion_reason = "NO_ACTUAL_JOIN"
            elif actual_applicants <= 0:
                exclusion_reason = "EXCLUDED_ZERO_ACTUAL_APPLICANTS"
            elif pred_prob is None:
                exclusion_reason = "NO_PREDICTION_PROBABILITY"

            scored = not exclusion_reason
            error = ""
            abs_error = ""
            if scored and actual_prob is not None and pred_prob is not None:
                error_value = pred_prob - actual_prob
                error = f"{error_value:.12g}"
                abs_error = f"{abs(error_value):.12g}"
                bucket = metrics[family]
                bucket["rows"] += 1
                bucket["mae"] += abs(error_value)
                bucket["rmse2"] += error_value * error_value
                bucket["bias"] += error_value

            summary[family]["pred_rows"] += 1
            if scored:
                summary[family]["scored_rows"] += 1
            else:
                summary[family][exclusion_reason] += 1
            if pred_prob == 1.0 and actual_applicants <= 0:
                summary[family]["false_100_zero_actual_applicant_rows_removed"] += 1

            joined_rows.append(
                {
                    "target_year": TARGET_YEAR,
                    "source_year": SOURCE_YEAR,
                    "family": family,
                    "hunt_code": code,
                    "hunt_name": pred.get("hunt_name", ""),
                    "residency": residency,
                    "points": point,
                    "prediction_status": pred.get("prediction_status", ""),
                    "runner_status": pred.get("status", ""),
                    "predicted_probability": "" if pred_prob is None else f"{pred_prob:.12g}",
                    "actual_probability": "" if actual_prob is None else f"{actual_prob:.12g}",
                    "predicted_applicants_at_level": f"{predicted_applicants:.12g}",
                    "actual_eligible_applicants": f"{actual_applicants:.12g}",
                    "scored": str(scored).lower(),
                    "exclusion_reason": exclusion_reason,
                    "error": error,
                    "abs_error": abs_error,
                }
            )

    summary_rows: list[dict[str, object]] = []
    for family in FAMILIES:
        metric = metrics[family]
        rows = metric["rows"]
        summary_rows.append(
            {
                "target_year": TARGET_YEAR,
                "source_year": SOURCE_YEAR,
                "family": family,
                "prediction_rows": summary[family]["pred_rows"],
                "scored_rows": rows,
                "excluded_zero_actual_applicant_rows": summary[family]["EXCLUDED_ZERO_ACTUAL_APPLICANTS"],
                "false_100_zero_actual_applicant_rows_removed": summary[family][
                    "false_100_zero_actual_applicant_rows_removed"
                ],
                "unmatched_prediction_rows": summary[family]["NO_ACTUAL_JOIN"],
                "no_prediction_probability_rows": summary[family]["NO_PREDICTION_PROBABILITY"],
                "mae": "" if not rows else f"{metric['mae'] / rows:.12g}",
                "rmse": "" if not rows else f"{math.sqrt(metric['rmse2'] / rows):.12g}",
                "bias": "" if not rows else f"{metric['bias'] / rows:.12g}",
            }
        )

    out_dir = AUDIT / "runner_2025_scoring_repair"
    write_csv(out_dir / "runner_2025_prediction_vs_actual_scored_rows.csv", joined_rows)
    write_csv(out_dir / "runner_2025_corrected_family_metrics.csv", summary_rows)

    total_rows = sum(int(row["scored_rows"]) for row in summary_rows)
    total_mae = sum(float(row["mae"] or 0) * int(row["scored_rows"]) for row in summary_rows)
    total_rmse2 = 0.0
    total_bias = sum(float(row["bias"] or 0) * int(row["scored_rows"]) for row in summary_rows)
    for row in joined_rows:
        if row["scored"] == "true" and row["error"] != "":
            total_rmse2 += float(row["error"]) ** 2
    aggregate = {
        "target_year": TARGET_YEAR,
        "scored_rows": total_rows,
        "mae": None if not total_rows else total_mae / total_rows,
        "rmse": None if not total_rows else math.sqrt(total_rmse2 / total_rows),
        "bias": None if not total_rows else total_bias / total_rows,
        "excluded_zero_actual_applicant_rows": sum(
            int(row["excluded_zero_actual_applicant_rows"]) for row in summary_rows
        ),
        "false_100_zero_actual_applicant_rows_removed": sum(
            int(row["false_100_zero_actual_applicant_rows_removed"]) for row in summary_rows
        ),
    }
    (out_dir / "runner_2025_corrected_summary.json").write_text(
        json.dumps(aggregate, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Runner 2025 Comparative Scoring Repair",
        "",
        "The original 2025 comparison scored zero-applicant ladder filler rows as if they were failed predictions. "
        "This repaired scorer only evaluates rows with actual eligible applicants greater than zero.",
        "",
        "## Aggregate",
        "",
        f"- Scored rows: {aggregate['scored_rows']}",
        f"- MAE: {aggregate['mae']:.6f}" if aggregate["mae"] is not None else "- MAE: N/A",
        f"- RMSE: {aggregate['rmse']:.6f}" if aggregate["rmse"] is not None else "- RMSE: N/A",
        f"- Bias: {aggregate['bias']:.6f}" if aggregate["bias"] is not None else "- Bias: N/A",
        f"- Excluded zero-actual-applicant rows: {aggregate['excluded_zero_actual_applicant_rows']}",
        f"- Removed false-100 zero-actual-applicant rows: {aggregate['false_100_zero_actual_applicant_rows_removed']}",
        "",
        "## Family Metrics",
        "",
    ]
    for row in summary_rows:
        lines.append(
            f"- {row['family']}: rows={row['scored_rows']}, MAE={row['mae']}, RMSE={row['rmse']}, "
            f"bias={row['bias']}, excluded_zero_actual={row['excluded_zero_actual_applicant_rows']}"
        )
    lines.extend(
        [
            "",
            "## Rule",
            "",
            "- Score prediction accuracy only where target-year actual eligible applicants are greater than zero.",
            "- Keep zero-applicant ladder rows available for display/diagnostic review, but exclude them from MAE/RMSE/bias.",
            "- Do not fabricate antlerless 2027 actuals from permit/quota totals.",
        ]
    )
    (out_dir / "runner_2025_scoring_repair_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(aggregate, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
