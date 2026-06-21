import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "engine_rebuild_from_truth" / "engine" / "prediction_outputs.csv"
TRUTH = ROOT / "data_truth" / "finalized_point_distribution.csv"
ENGINE_INPUTS = ROOT / "engine_rebuild_from_truth" / "engine" / "draw_engine_input_point_rows.csv"
OUT = ROOT / "audits" / "prediction_validation"


def clean(value):
    return "" if value is None else str(value).strip()


def norm_code(value):
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def norm_year(value):
    text = clean(value)
    return text[:-2] if text.endswith(".0") else text


def norm_residency(value):
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"r", "res", "resident"}:
        return "Resident"
    if text in {"nr", "nonres", "nonresident"}:
        return "Nonresident"
    if text in {"all", "both"}:
        return "All"
    return clean(value)


def to_float(value):
    text = clean(value).replace(",", "").replace("%", "")
    if text in {"", "N/A", "NA", "None", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value):
    number = to_float(value)
    if number is None:
        return None
    return int(number)


def join_key(row):
    return (
        norm_code(row.get("hunt_code")),
        norm_year(row.get("model_year")),
        norm_residency(row.get("residency")),
        norm_year(row.get("point_level")),
    )


def point_bucket(value):
    point = to_int(value)
    if point is None:
        return "NON_NUMERIC"
    if point <= 2:
        return "0-2"
    if point <= 5:
        return "3-5"
    if point <= 10:
        return "6-10"
    return "10+"


def species_from(row, code):
    hay = " ".join(clean(row.get(col)) for col in ("source_file", "source_namespace", "hunt_name")).upper()
    if code.startswith("BI") or "BISON" in hay:
        return "BISON"
    if code.startswith("BR") or "BEAR" in hay:
        return "BLACK_BEAR"
    if code.startswith("CG") or "COUGAR" in hay:
        return "COUGAR"
    if code.startswith("TK") or "TURKEY" in hay:
        return "TURKEY"
    if code.startswith("GO") or "GOAT" in hay:
        return "MOUNTAIN_GOAT"
    if code.startswith("DS") or "DESERT BIGHORN" in hay:
        return "DESERT_BIGHORN_SHEEP"
    if code.startswith("RS") or ("ROCKY" in hay and "SHEEP" in hay):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if code.startswith(("MB", "MA")) or "MOOSE" in hay:
        return "MOOSE"
    if code.startswith(("PB", "PD")) or "PRONGHORN" in hay:
        return "PRONGHORN"
    if code.startswith(("EB", "EA")) or "ELK" in hay:
        return "ELK"
    if code.startswith(("DB", "DA")) or "DEER" in hay:
        return "DEER"
    return "UNKNOWN"


def hunt_type_from(row, code):
    hay = " ".join(clean(row.get(col)) for col in ("source_file", "source_namespace", "hunt_name")).upper()
    if "SPORTSMAN" in hay:
        return "SPORTSMAN"
    if "ANTLERLESS" in hay or code.startswith(("DA", "EA", "MA", "PD")):
        return "ANTLERLESS"
    if "TURKEY" in hay or code.startswith("TK"):
        return "TURKEY"
    if "BEAR" in hay or code.startswith("BR"):
        return "BEAR"
    if "COUGAR" in hay or code.startswith("CG"):
        return "COUGAR"
    if "O.I.L" in hay or "ONCE-IN-A-LIFETIME" in hay or code.startswith(("BI", "GO", "MB", "DS", "RS")):
        return "O.I.L."
    if "L.E." in hay or "LIMITED" in hay or code.startswith(("DB", "EB", "PB")):
        return "L.E."
    if "G.S." in hay or "GENERAL" in hay:
        return "G.S."
    return "UNKNOWN"


def metric_seed():
    return {"n": 0, "sum_abs": 0.0, "sum_sq": 0.0, "sum_error": 0.0, "failures": 0}


def add_metric(metrics, error):
    metrics["n"] += 1
    metrics["sum_abs"] += abs(error)
    metrics["sum_sq"] += error * error
    metrics["sum_error"] += error
    if abs(error) > 0.25:
        metrics["failures"] += 1


def finish_metric(metrics):
    n = metrics["n"]
    if not n:
        return {
            "row_count": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "failure_count_abs_error_gt_0_25": 0,
            "failure_rate": "",
        }
    return {
        "row_count": n,
        "mae": metrics["sum_abs"] / n,
        "rmse": math.sqrt(metrics["sum_sq"] / n),
        "bias": metrics["sum_error"] / n,
        "failure_count_abs_error_gt_0_25": metrics["failures"],
        "failure_rate": metrics["failures"] / n,
    }


def write_rows(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_metric_file(path, dimensions, buckets):
    rows = []
    for key in sorted(buckets):
        values = key if isinstance(key, tuple) else (key,)
        row = {name: value for name, value in zip(dimensions, values)}
        row.update(finish_metric(buckets[key]))
        rows.append(row)
    write_rows(path, rows, list(dimensions) + ["row_count", "mae", "rmse", "bias", "failure_count_abs_error_gt_0_25", "failure_rate"])


def prediction_probability(row):
    probability = to_float(row.get("predicted_probability"))
    if probability is None:
        probability = to_float(row.get("p_draw"))
    if probability is None:
        percent = to_float(row.get("p_draw_percent"))
        if percent is not None:
            probability = percent / 100.0
    return probability


def load_predictions():
    counts = Counter()
    duplicate_key_counts = Counter()
    rows_by_occurrence = {}
    total_rows = 0
    missing_probability = 0
    with PREDICTIONS.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            key = join_key(row)
            occurrence = counts[key]
            counts[key] += 1
            duplicate_key_counts[key] += 1
            probability = prediction_probability(row)
            if probability is None:
                missing_probability += 1
            rows_by_occurrence[(key, occurrence)] = {
                "predicted_probability": probability,
                "prediction_source_file": clean(row.get("source_file")),
                "prediction_draw_method": clean(row.get("draw_method")),
                "prediction_output_source": clean(row.get("output_source")),
            }
    return rows_by_occurrence, total_rows, missing_probability, duplicate_key_counts


def read_truth_rows():
    rows = []
    with TRUTH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def guaranteed_thresholds(rows):
    thresholds = {}
    for row in rows:
        key = (norm_code(row.get("hunt_code")), norm_year(row.get("model_year")), norm_residency(row.get("residency")))
        point = to_int(row.get("point_level"))
        applicants = to_float(row.get("applicants"))
        success_rate = to_float(row.get("success_rate"))
        if point is None or applicants is None or applicants <= 0 or success_rate is None:
            continue
        if success_rate >= 99.999:
            prior = thresholds.get(key)
            thresholds[key] = point if prior is None else min(prior, point)
    return thresholds


def classify_truth_row(row, thresholds):
    code = norm_code(row.get("hunt_code"))
    model_year = norm_year(row.get("model_year"))
    residency = norm_residency(row.get("residency"))
    point = to_int(row.get("point_level"))
    applicants = to_float(row.get("applicants"))
    success_rate = to_float(row.get("success_rate"))
    if is_reviewed_source_anomaly(code, model_year, residency, point):
        return "SOURCE_ANOMALY_REVIEW"
    if not code or not model_year or not residency or point is None:
        return "INVALID_KEY_OR_POINT"
    if applicants is None:
        return "UNSCORABLE_MISSING_APPLICANTS"
    if applicants > 0 and success_rate is not None:
        return "SCORABLE_ACTUAL"
    if applicants > 0 and success_rate is None:
        return "UNSCORABLE_NONZERO_APPLICANTS_NO_PUBLISHED_SUCCESS_RATE"
    threshold = thresholds.get((code, model_year, residency))
    if threshold is not None and point >= threshold:
        return "ZERO_APPLICANT_GUARANTEED_ZONE"
    return "ZERO_APPLICANT_STRUCTURAL"


def is_reviewed_source_anomaly(code, model_year, residency, point):
    return code == "DS6608" and model_year == "2026" and residency == "Nonresident" and point == 32


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    predictions, prediction_rows, missing_prediction_probability_total, prediction_key_counts = load_predictions()
    truth_rows = read_truth_rows()
    thresholds = guaranteed_thresholds(truth_rows)

    truth_occurrences = Counter()
    class_counts = Counter()
    class_by_year = Counter()
    success_coverage_by_year = defaultdict(lambda: Counter())
    missing_success_by_source = Counter()
    missing_success_samples = []
    ds6608_truth_rows = []
    source_anomaly_rows = []

    overall = metric_seed()
    by_year = defaultdict(metric_seed)
    by_bucket = defaultdict(metric_seed)
    by_species = defaultdict(metric_seed)
    by_hunt_type = defaultdict(metric_seed)
    by_residency = defaultdict(metric_seed)
    grouped = defaultdict(metric_seed)

    joined_rows = 0
    missing_prediction_rows = 0
    missing_prediction_probability_rows = 0
    failure_count = 0
    full_rows = []
    failure_rows = []

    for row in truth_rows:
        key = join_key(row)
        occurrence = truth_occurrences[key]
        truth_occurrences[key] += 1
        classification = classify_truth_row(row, thresholds)
        year = norm_year(row.get("year"))
        model_year = norm_year(row.get("model_year"))
        code = key[0]
        species = clean(row.get("species")) or species_from(row, code)
        hunt_type = clean(row.get("hunt_type")) or hunt_type_from(row, code)
        bucket = point_bucket(row.get("point_level"))
        success_rate = to_float(row.get("success_rate"))
        applicants = to_float(row.get("applicants"))
        class_counts[classification] += 1
        class_by_year[(year, model_year, classification)] += 1

        if classification == "SOURCE_ANOMALY_REVIEW":
            source_anomaly_rows.append({
                "year": year,
                "model_year": model_year,
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "residency": key[2],
                "point_level": key[3],
                "applicants": clean(row.get("applicants")),
                "permits": clean(row.get("permits")),
                "raw_success_rate": clean(row.get("success_rate")),
                "raw_actual_probability": "" if success_rate is None else success_rate / 100.0,
                "reviewed_success_rate": "100",
                "reviewed_actual_probability": "1.0",
                "review_status": "CONFIRMED_SOURCE_ANOMALY_EXCLUDED_FROM_ACCURACY",
                "review_reason": "PDF success ratio says 1 in 2.0, but the same row has 1 applicant and 1 permit; Tyler confirmed this should be 1 in 1.0 / 100%.",
                "source_file": clean(row.get("source_file")),
                "source_namespace": clean(row.get("source_namespace")),
            })

        success_coverage_by_year[(year, model_year)]["rows"] += 1
        if success_rate is not None:
            success_coverage_by_year[(year, model_year)]["success_rate_rows"] += 1
        if applicants is not None and applicants > 0:
            success_coverage_by_year[(year, model_year)]["nonzero_applicant_rows"] += 1
            if success_rate is None:
                success_coverage_by_year[(year, model_year)]["nonzero_applicant_missing_success_rate_rows"] += 1
                missing_success_by_source[(year, model_year, clean(row.get("source_file")), clean(row.get("source_namespace")))] += 1
                if year in {"2021", "2022"} and len(missing_success_samples) < 250:
                    missing_success_samples.append({
                        "year": year,
                        "model_year": model_year,
                        "hunt_code": code,
                        "hunt_name": clean(row.get("hunt_name")),
                        "residency": key[2],
                        "point_level": key[3],
                        "applicants": clean(row.get("applicants")),
                        "permits": clean(row.get("permits")),
                        "success_rate": clean(row.get("success_rate")),
                        "source_file": clean(row.get("source_file")),
                        "source_namespace": clean(row.get("source_namespace")),
                        "validation_classification": classification,
                    })

        if code == "DS6608" and model_year == "2026":
            ds6608_truth_rows.append({
                "row_source": "truth",
                "year": year,
                "model_year": model_year,
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "residency": key[2],
                "point_level": key[3],
                "applicants": clean(row.get("applicants")),
                "permits": clean(row.get("permits")),
                "success_rate": clean(row.get("success_rate")),
                "validation_classification": classification,
                "source_file": clean(row.get("source_file")),
                "source_namespace": clean(row.get("source_namespace")),
            })

        if classification != "SCORABLE_ACTUAL":
            continue

        pred = predictions.get((key, occurrence))
        actual_probability = success_rate / 100.0
        output = {
            "year": year,
            "model_year": model_year,
            "hunt_code": code,
            "hunt_name": clean(row.get("hunt_name")),
            "species": species,
            "hunt_type": hunt_type,
            "residency": key[2],
            "point_level": key[3],
            "point_bucket": bucket,
            "validation_classification": classification,
            "actual_success_rate_percent": success_rate,
            "actual_probability": actual_probability,
            "duplicate_occurrence_index": occurrence,
            "join_key": "|".join(key),
            "truth_source_file": clean(row.get("source_file")),
        }
        if pred is None:
            missing_prediction_rows += 1
            output.update({
                "predicted_probability": "",
                "error": "",
                "abs_error": "",
                "squared_error": "",
                "failure_abs_error_gt_0_25": "",
                "prediction_source_file": "",
                "prediction_draw_method": "",
                "prediction_output_source": "",
                "validation_status": "MISSING_PREDICTION_ROW",
            })
            full_rows.append(output)
            continue
        if pred["predicted_probability"] is None:
            missing_prediction_probability_rows += 1
            output.update({
                "predicted_probability": "",
                "error": "",
                "abs_error": "",
                "squared_error": "",
                "failure_abs_error_gt_0_25": "",
                "prediction_source_file": pred["prediction_source_file"],
                "prediction_draw_method": pred["prediction_draw_method"],
                "prediction_output_source": pred["prediction_output_source"],
                "validation_status": "MISSING_PREDICTED_PROBABILITY",
            })
            full_rows.append(output)
            continue

        joined_rows += 1
        error = pred["predicted_probability"] - actual_probability
        add_metric(overall, error)
        add_metric(by_year[(year, model_year)], error)
        add_metric(by_bucket[bucket], error)
        add_metric(by_species[species], error)
        add_metric(by_hunt_type[hunt_type], error)
        add_metric(by_residency[key[2]], error)
        add_metric(grouped[(year, model_year, species, hunt_type, key[2], bucket)], error)
        failed = abs(error) > 0.25
        if failed:
            failure_count += 1
        output.update({
            "predicted_probability": pred["predicted_probability"],
            "error": error,
            "abs_error": abs(error),
            "squared_error": error * error,
            "failure_abs_error_gt_0_25": "TRUE" if failed else "FALSE",
            "prediction_source_file": pred["prediction_source_file"],
            "prediction_draw_method": pred["prediction_draw_method"],
            "prediction_output_source": pred["prediction_output_source"],
            "validation_status": "OK",
        })
        full_rows.append(output)
        if failed:
            failure_rows.append(output)

    full_fields = [
        "year", "model_year", "hunt_code", "hunt_name", "species", "hunt_type", "residency", "point_level",
        "point_bucket", "validation_classification", "actual_success_rate_percent", "actual_probability",
        "predicted_probability", "error", "abs_error", "squared_error", "failure_abs_error_gt_0_25",
        "duplicate_occurrence_index", "join_key", "truth_source_file", "prediction_source_file",
        "prediction_draw_method", "prediction_output_source", "validation_status",
    ]
    write_rows(OUT / "prediction_vs_actual_full.csv", full_rows, full_fields)
    write_rows(OUT / "prediction_vs_actual_failure_flags_abs_error_gt_0_25.csv", failure_rows, full_fields)

    write_metric_file(OUT / "prediction_vs_actual_by_year.csv", ("year", "model_year"), by_year)
    write_metric_file(OUT / "prediction_vs_actual_by_point_bucket.csv", ("point_bucket",), by_bucket)
    write_metric_file(OUT / "prediction_vs_actual_by_species.csv", ("species",), by_species)
    write_metric_file(OUT / "prediction_vs_actual_by_hunt_type.csv", ("hunt_type",), by_hunt_type)
    write_metric_file(OUT / "prediction_vs_actual_by_residency.csv", ("residency",), by_residency)
    write_metric_file(OUT / "prediction_vs_actual_group_analysis.csv", ("year", "model_year", "species", "hunt_type", "residency", "point_bucket"), grouped)

    classification_rows = [
        {"validation_classification": key, "row_count": value}
        for key, value in sorted(class_counts.items())
    ]
    write_rows(OUT / "truth_row_validation_classification_counts.csv", classification_rows, ["validation_classification", "row_count"])

    write_rows(
        OUT / "source_anomaly_review_rows.csv",
        source_anomaly_rows,
        [
            "year", "model_year", "hunt_code", "hunt_name", "residency", "point_level",
            "applicants", "permits", "raw_success_rate", "raw_actual_probability",
            "reviewed_success_rate", "reviewed_actual_probability", "review_status",
            "review_reason", "source_file", "source_namespace",
        ],
    )

    class_year_rows = [
        {"year": key[0], "model_year": key[1], "validation_classification": key[2], "row_count": value}
        for key, value in sorted(class_by_year.items())
    ]
    write_rows(OUT / "truth_row_validation_classification_by_year.csv", class_year_rows, ["year", "model_year", "validation_classification", "row_count"])

    coverage_rows = []
    for key, counts in sorted(success_coverage_by_year.items()):
        rows = counts["rows"]
        coverage_rows.append({
            "year": key[0],
            "model_year": key[1],
            "rows": rows,
            "success_rate_rows": counts["success_rate_rows"],
            "success_rate_coverage": counts["success_rate_rows"] / rows if rows else "",
            "nonzero_applicant_rows": counts["nonzero_applicant_rows"],
            "nonzero_applicant_missing_success_rate_rows": counts["nonzero_applicant_missing_success_rate_rows"],
        })
    write_rows(OUT / "success_rate_coverage_by_year.csv", coverage_rows, ["year", "model_year", "rows", "success_rate_rows", "success_rate_coverage", "nonzero_applicant_rows", "nonzero_applicant_missing_success_rate_rows"])

    missing_source_rows = [
        {
            "year": key[0],
            "model_year": key[1],
            "source_file": key[2],
            "source_namespace": key[3],
            "nonzero_applicant_missing_success_rate_rows": value,
        }
        for key, value in sorted(missing_success_by_source.items(), key=lambda item: (-item[1], item[0]))
    ]
    write_rows(OUT / "success_rate_missing_nonzero_applicants_by_source.csv", missing_source_rows, ["year", "model_year", "source_file", "source_namespace", "nonzero_applicant_missing_success_rate_rows"])
    write_rows(OUT / "success_rate_missing_nonzero_applicants_2021_2022_samples.csv", missing_success_samples, ["year", "model_year", "hunt_code", "hunt_name", "residency", "point_level", "applicants", "permits", "success_rate", "source_file", "source_namespace", "validation_classification"])

    ds6608_prediction_rows = []
    for (key, occurrence), pred in predictions.items():
        if key[0] == "DS6608" and key[1] == "2026":
            ds6608_prediction_rows.append({
                "row_source": "prediction",
                "model_year": key[1],
                "hunt_code": key[0],
                "residency": key[2],
                "point_level": key[3],
                "duplicate_occurrence_index": occurrence,
                "predicted_probability": pred["predicted_probability"],
                "prediction_source_file": pred["prediction_source_file"],
                "prediction_draw_method": pred["prediction_draw_method"],
                "prediction_output_source": pred["prediction_output_source"],
            })
    ds_fields = ["row_source", "year", "model_year", "hunt_code", "hunt_name", "residency", "point_level", "duplicate_occurrence_index", "applicants", "permits", "success_rate", "validation_classification", "predicted_probability", "source_file", "source_namespace", "prediction_source_file", "prediction_draw_method", "prediction_output_source"]
    write_rows(OUT / "DS6608_failure_inspection.csv", ds6608_truth_rows + ds6608_prediction_rows, ds_fields)

    ds_failure = [row for row in failure_rows if row["hunt_code"] == "DS6608"]
    write_rows(OUT / "DS6608_failure_joined_row.csv", ds_failure, full_fields)

    overall_finished = finish_metric(overall)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "prediction_file": str(PREDICTIONS.relative_to(ROOT)),
        "truth_file": str(TRUTH.relative_to(ROOT)),
        "actual_probability_source": "published truth success_rate / 100 only",
        "actual_probability_not_used": "permits/applicants was not used to create actual_probability",
        "truth_rows": len(truth_rows),
        "prediction_rows": prediction_rows,
        "truth_rows_by_classification": dict(sorted(class_counts.items())),
        "source_anomaly_review_rows_excluded_from_metrics": len(source_anomaly_rows),
        "joined_scorable_actual_rows": joined_rows,
        "missing_prediction_rows_for_scorable_actual": missing_prediction_rows,
        "missing_prediction_probability_rows_for_scorable_actual": missing_prediction_probability_rows,
        "prediction_missing_probability_total_rows": missing_prediction_probability_total,
        "requested_join_key_duplicate_groups_prediction": sum(1 for value in prediction_key_counts.values() if value > 1),
        "requested_join_key_duplicate_groups_truth": sum(1 for value in truth_occurrences.values() if value > 1),
        "effective_join_key": "hunt_code + model_year + residency + point_level + duplicate_occurrence_index",
        **overall_finished,
        "success_criteria_mae_lt_0_20": bool(overall_finished["mae"] != "" and overall_finished["mae"] < 0.20),
        "success_criteria_rmse_lt_0_30": bool(overall_finished["rmse"] != "" and overall_finished["rmse"] < 0.30),
        "success_criteria_bias_close_to_0_abs_lt_0_05": bool(overall_finished["bias"] != "" and abs(overall_finished["bias"]) < 0.05),
        "ds6608_failure_rows": len(ds_failure),
        "outputs": {
            "prediction_vs_actual_full": str((OUT / "prediction_vs_actual_full.csv").relative_to(ROOT)),
            "prediction_vs_actual_summary": str((OUT / "prediction_vs_actual_summary.csv").relative_to(ROOT)),
            "prediction_vs_actual_by_year": str((OUT / "prediction_vs_actual_by_year.csv").relative_to(ROOT)),
            "prediction_vs_actual_by_point_bucket": str((OUT / "prediction_vs_actual_by_point_bucket.csv").relative_to(ROOT)),
            "truth_row_validation_classification_counts": str((OUT / "truth_row_validation_classification_counts.csv").relative_to(ROOT)),
            "success_rate_coverage_by_year": str((OUT / "success_rate_coverage_by_year.csv").relative_to(ROOT)),
            "DS6608_failure_inspection": str((OUT / "DS6608_failure_inspection.csv").relative_to(ROOT)),
        },
    }

    report_lines = [
        "# Prediction Validation Classification Audit",
        "",
        f"Generated UTC: {summary['generated_at_utc']}",
        "",
        "## Scope",
        "",
        "- Actual probability is sourced only from published truth `success_rate / 100`.",
        "- Permit/applicant division is not used as actual probability.",
        "- Metrics include only `SCORABLE_ACTUAL` rows.",
        "- Zero-applicant rows remain ladder structure and are excluded from accuracy scoring.",
        "",
        "## Results",
        "",
        f"- Joined scorable actual rows: `{joined_rows}`",
        f"- MAE: `{overall_finished['mae']}`",
        f"- RMSE: `{overall_finished['rmse']}`",
        f"- Bias: `{overall_finished['bias']}`",
        f"- Failure rows over 0.25 absolute error: `{overall_finished['failure_count_abs_error_gt_0_25']}`",
        f"- Source anomaly review rows excluded from metrics: `{len(source_anomaly_rows)}`",
        "",
        "## Truth Row Classification",
        "",
    ]
    for name, count in sorted(class_counts.items()):
        report_lines.append(f"- `{name}`: `{count}`")
    report_lines.extend([
        "",
        "## DS6608 Finding",
        "",
        "- Failing row: `DS6608`, model year `2026`, `Nonresident`, point level `32`.",
        "- Published PDF text says `1 in 2.0`, but the same row has `1` applicant and `1` permit.",
        "- Tyler reviewed and confirmed this should be `1 in 1.0` / `100%`.",
        "- The raw PDF-derived value remains preserved in `source_anomaly_review_rows.csv`.",
        "- The row is excluded from accuracy metrics as `SOURCE_ANOMALY_REVIEW` so it does not falsely count as an engine miss.",
        "",
        "## 2021/2022 Success-Rate Coverage",
        "",
        "- 2021 has nonzero-applicant rows but zero published `success_rate` values in the current truth surface.",
        "- 2022 has 18,056 nonzero-applicant rows but only 2 rows with `success_rate`.",
        "- This is a truth-field normalization gap, not evidence that the PDFs lack outcomes.",
        "",
        "## Output Files",
        "",
    ])
    for label, path in summary["outputs"].items():
        report_lines.append(f"- `{label}`: `{path}`")
    report_lines.append("- `classification_report`: `audits/prediction_validation/PREDICTION_VALIDATION_CLASSIFICATION_REPORT.md`")
    (OUT / "PREDICTION_VALIDATION_CLASSIFICATION_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    with (OUT / "prediction_vs_actual_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = list(summary.keys())
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(summary)

    (OUT / "prediction_validation_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({
        "joined_scorable_actual_rows": joined_rows,
        "mae": overall_finished["mae"],
        "rmse": overall_finished["rmse"],
        "bias": overall_finished["bias"],
        "failure_count_abs_error_gt_0_25": overall_finished["failure_count_abs_error_gt_0_25"],
        "ds6608_failure_rows": len(ds_failure),
        "outputs_dir": str(OUT.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
