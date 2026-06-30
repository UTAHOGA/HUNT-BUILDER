from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / "audits" / "full_engine_all_year_repair_20260629_032752"
CANONICAL = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
OUT_DIR = AUDIT / "runner_all_year_scoring_repair"
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
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


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


def canonical_path(source_year: str, target_year: str) -> Path:
    return CANONICAL / f"draw_results_{source_year}_for_{target_year}_canonical_yearly_draw_results.csv"


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


def probability_from_fields(row: dict[str, str], prefix: str = "") -> tuple[float | None, float]:
    applicants_field = f"{prefix}_eligible_applicants" if prefix else "eligible_applicants"
    permits_field = f"{prefix}_total_permits" if prefix else "total_permits"
    p_draw_field = f"{prefix}_p_draw" if prefix else "p_draw"
    p_pct_field = f"{prefix}_p_draw_percent" if prefix else "p_draw_percent"

    applicants = num(row.get(applicants_field)) or 0.0
    p_draw = num(row.get(p_draw_field))
    p_pct = num(row.get(p_pct_field))
    if p_draw is not None:
        return max(0.0, min(1.0, p_draw)), applicants
    if p_pct is not None:
        return max(0.0, min(1.0, p_pct / 100.0)), applicants
    permits = num(row.get(permits_field))
    if applicants > 0 and permits is not None:
        return max(0.0, min(1.0, permits / applicants)), applicants
    return None, applicants


def actual_entries(row: dict[str, str]) -> list[dict[str, str]]:
    if clean(row.get("record_type")) != "point_level_draw_result":
        return []
    family = family_for_actual(row)
    if family not in FAMILIES:
        return []
    code = clean(row.get("hunt_code")).upper()
    point = norm_point(row.get("points"))

    row_residency = norm_residency(row.get("residency"))
    if row_residency in {"Resident", "Nonresident"}:
        prob, applicants = probability_from_fields(row)
        return [
            {
                "family": family,
                "hunt_code": code,
                "residency": row_residency,
                "point": point,
                "actual_probability": "" if prob is None else f"{prob:.12g}",
                "actual_applicants": f"{applicants:.12g}",
            }
        ]

    entries = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        prob, applicants = probability_from_fields(row, prefix)
        entries.append(
            {
                "family": family,
                "hunt_code": code,
                "residency": residency,
                "point": point,
                "actual_probability": "" if prob is None else f"{prob:.12g}",
                "actual_applicants": f"{applicants:.12g}",
            }
        )
    return entries


def prediction_probability(row: dict[str, str]) -> tuple[float | None, float]:
    for field in ("p_draw_mean", "p_draw", "p_preference_draw"):
        value = num(row.get(field))
        if value is not None:
            return max(0.0, min(1.0, value)), num(row.get("applicants_at_level")) or 0.0
    pct = num(row.get("display_odds_pct")) or num(row.get("p_draw_pct"))
    if pct is not None:
        return max(0.0, min(1.0, pct / 100.0)), num(row.get("applicants_at_level")) or 0.0
    return None, num(row.get("applicants_at_level")) or 0.0


def build_actual_index(path: Path) -> dict[tuple[str, str, str, str], dict[str, str]]:
    actual_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    if not path.exists():
        return actual_by_key
    for row in read_csv(path):
        for entry in actual_entries(row):
            key = (entry["family"], entry["hunt_code"], entry["residency"], entry["point"])
            existing = actual_by_key.get(key)
            if existing is None or (num(entry["actual_applicants"]) or 0.0) > (
                num(existing.get("actual_applicants")) or 0.0
            ):
                actual_by_key[key] = entry
    return actual_by_key


def quality_status(mae: float, rmse: float, bias: float) -> str:
    if mae >= 0.50 or abs(bias) >= 0.50 or rmse >= 0.65:
        return "COMPARISON_REVIEW_REQUIRED_HIGH_ERROR_OR_BIAS"
    if mae <= 0.25 and abs(bias) <= 0.15:
        return "COMPARISON_GOOD"
    if mae <= 0.35 and abs(bias) <= 0.25:
        return "COMPARISON_ACCEPTABLE_WITH_CAUTION"
    return "COMPARISON_WEAK_REVIEW"


def main() -> int:
    joined_rows: list[dict[str, object]] = []
    family_year_counters = defaultdict(Counter)
    metrics = defaultdict(lambda: {"rows": 0, "mae": 0.0, "rmse2": 0.0, "bias": 0.0})

    for run_dir in sorted((AUDIT / "runs").glob("*")):
        if not run_dir.is_dir() or not run_dir.name.isdigit():
            continue
        target_year = run_dir.name
        source_year = str(int(target_year) - 1)
        actual_by_key = build_actual_index(canonical_path(source_year, target_year))
        for family in FAMILIES:
            pred_path = run_dir / "predictions" / f"{source_year}_{target_year}_{family}.csv"
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
                family_year = (target_year, family)
                family_year_counters[family_year]["prediction_rows"] += 1
                if scored and actual_prob is not None and pred_prob is not None:
                    error_value = pred_prob - actual_prob
                    error = f"{error_value:.12g}"
                    abs_error = f"{abs(error_value):.12g}"
                    family_year_counters[family_year]["scored_rows"] += 1
                    bucket = metrics[family_year]
                    bucket["rows"] += 1
                    bucket["mae"] += abs(error_value)
                    bucket["rmse2"] += error_value * error_value
                    bucket["bias"] += error_value
                else:
                    family_year_counters[family_year][exclusion_reason] += 1

                if actual is not None and actual_applicants <= 0 and pred_prob == 1.0:
                    family_year_counters[family_year]["false_100_zero_actual_applicant_rows_removed"] += 1

                joined_rows.append(
                    {
                        "target_year": target_year,
                        "source_year": source_year,
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

    family_year_rows: list[dict[str, object]] = []
    for key in sorted(family_year_counters, key=lambda item: (int(item[0]), item[1])):
        target_year, family = key
        counter = family_year_counters[key]
        metric = metrics[key]
        rows = metric["rows"]
        mae = metric["mae"] / rows if rows else None
        rmse = math.sqrt(metric["rmse2"] / rows) if rows else None
        bias = metric["bias"] / rows if rows else None
        family_year_rows.append(
            {
                "target_year": target_year,
                "source_year": str(int(target_year) - 1),
                "family": family,
                "prediction_rows": counter["prediction_rows"],
                "scored_rows": rows,
                "excluded_zero_actual_applicant_rows": counter["EXCLUDED_ZERO_ACTUAL_APPLICANTS"],
                "false_100_zero_actual_applicant_rows_removed": counter[
                    "false_100_zero_actual_applicant_rows_removed"
                ],
                "unmatched_prediction_rows": counter["NO_ACTUAL_JOIN"],
                "no_prediction_probability_rows": counter["NO_PREDICTION_PROBABILITY"],
                "mae": "" if mae is None else f"{mae:.12g}",
                "rmse": "" if rmse is None else f"{rmse:.12g}",
                "bias": "" if bias is None else f"{bias:.12g}",
                "comparative_quality_status": ""
                if mae is None or rmse is None or bias is None
                else quality_status(mae, rmse, bias),
            }
        )

    total_rows = sum(int(row["scored_rows"]) for row in family_year_rows)
    total_abs = sum(float(row["mae"] or 0) * int(row["scored_rows"]) for row in family_year_rows)
    total_bias = sum(float(row["bias"] or 0) * int(row["scored_rows"]) for row in family_year_rows)
    total_rmse2 = sum(float(row["error"]) ** 2 for row in joined_rows if row["scored"] == "true" and row["error"] != "")
    aggregate = {
        "scored_rows": total_rows,
        "mae": None if not total_rows else total_abs / total_rows,
        "rmse": None if not total_rows else math.sqrt(total_rmse2 / total_rows),
        "bias": None if not total_rows else total_bias / total_rows,
        "excluded_zero_actual_applicant_rows": sum(
            int(row["excluded_zero_actual_applicant_rows"]) for row in family_year_rows
        ),
        "false_100_zero_actual_applicant_rows_removed": sum(
            int(row["false_100_zero_actual_applicant_rows_removed"]) for row in family_year_rows
        ),
        "quality_counts": dict(Counter(row["comparative_quality_status"] for row in family_year_rows if row["comparative_quality_status"])),
    }

    write_csv(OUT_DIR / "runner_all_year_prediction_vs_actual_scored_rows.csv", joined_rows)
    write_csv(OUT_DIR / "runner_all_year_corrected_family_year_metrics.csv", family_year_rows)
    (OUT_DIR / "runner_all_year_corrected_summary.json").write_text(
        json.dumps(aggregate, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Runner All-Year Comparative Scoring Repair",
        "",
        "This scorer applies the zero-qualified-applicant rule to every runner target year.",
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
        "## Quality Counts",
        "",
    ]
    for status, count in aggregate["quality_counts"].items():
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            "- Rows with zero actual eligible applicants represent no applicants with that number of bonus/preference points.",
            "- Those rows reconcile to effectively zero qualified applicants at that point row.",
            "- They remain valid ladder/display rows, but they are excluded from MAE/RMSE/bias/Brier-style accuracy scoring.",
            "- This rule is applied across all target years, not only 2025.",
        ]
    )
    (OUT_DIR / "runner_all_year_scoring_repair_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Refresh the headline comparative report to point at the all-year corrected run.
    report = AUDIT / "RUNNER_COMPARATIVE_QUALITY_REPORT.md"
    high_error = [
        row
        for row in family_year_rows
        if row["comparative_quality_status"] == "COMPARISON_REVIEW_REQUIRED_HIGH_ERROR_OR_BIAS"
    ]
    report_lines = [
        "# Runner Comparative Quality Report",
        "",
        "This report evaluates comparative quality separately from structural runner acceptance. All target years now use the zero-qualified-applicant scoring rule.",
        "",
        "## Status",
        "",
        "- Structural runner streams accepted: 42",
        f"- Comparative family-year rows analyzed: {len(family_year_rows)}",
    ]
    for status, count in aggregate["quality_counts"].items():
        report_lines.append(f"- {status}: {count}")
    report_lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Corrected all scored rows: rows={aggregate['scored_rows']}, MAE={aggregate['mae']:.6f}, RMSE={aggregate['rmse']:.6f}, bias={aggregate['bias']:.6f}",
            f"- Excluded zero-actual-applicant rows: {aggregate['excluded_zero_actual_applicant_rows']}",
            f"- Removed false-100 zero-actual-applicant rows: {aggregate['false_100_zero_actual_applicant_rows_removed']}",
            "",
            "## High-Error Review Required",
            "",
        ]
    )
    if high_error:
        for row in high_error:
            report_lines.append(
                f"- {row['target_year']} {row['family']}: rows={row['scored_rows']}, MAE={row['mae']}, RMSE={row['rmse']}, bias={row['bias']}"
            )
    else:
        report_lines.append("- None after corrected all-year scoring.")
    report_lines.extend(
        [
            "",
            "## Qualified Applicant Interpretation",
            "",
            "- Rows with zero actual eligible applicants represent no applicants with that number of bonus/preference points.",
            "- Those rows reconcile to effectively zero qualified applicants at that point row.",
            "- They remain valid ladder/display/diagnostic rows, but they are not scored as prediction failures.",
            "",
            "## Output Files",
            "",
            f"- Corrected all-year quality audit: `{OUT_DIR / 'runner_all_year_corrected_family_year_metrics.csv'}`",
            f"- Corrected all-year row audit: `{OUT_DIR / 'runner_all_year_prediction_vs_actual_scored_rows.csv'}`",
            f"- All-year repair report: `{OUT_DIR / 'runner_all_year_scoring_repair_report.md'}`",
        ]
    )
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps(aggregate, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
