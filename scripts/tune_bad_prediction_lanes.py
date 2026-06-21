import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_FULL = ROOT / "audits" / "prediction_validation" / "prediction_vs_actual_full_fixed.csv"
OUT = ROOT / "audits" / "prediction_validation" / "lane_specific_tuning"

TARGET_FAMILIES = {
    "DEDICATED_HUNTER_DEER_PREFERENCE",
    "YOUTH_DEDICATED_HUNTER_DEER_PREFERENCE",
    "YOUTH_ANTLERLESS_PREFERENCE",
    "BEAR_BONUS",
    "TURKEY_BONUS",
}


def clean(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    text = clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def metrics(rows, pred_col="predicted_probability"):
    if not rows:
        return {
            "row_count": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "failure_count_abs_error_gt_0_25": 0,
        }
    errors = []
    for row in rows:
        pred = to_float(row[pred_col])
        actual = to_float(row["actual_probability"])
        error = pred - actual
        errors.append(error)
    return {
        "row_count": len(rows),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "bias": sum(errors) / len(errors),
        "failure_count_abs_error_gt_0_25": sum(1 for error in errors if abs(error) > 0.25),
    }


def apply_candidate(value, candidate):
    kind = candidate["kind"]
    if kind == "scale":
        return clamp(value * candidate["factor"])
    if kind == "bias_shift":
        return clamp(value + candidate["shift"])
    if kind == "blend_actual_rate":
        # Shrink high-confidence spikes toward the lane's historical mean actual rate.
        return clamp((value * (1.0 - candidate["blend"])) + (candidate["lane_actual_mean"] * candidate["blend"]))
    if kind == "cap":
        return clamp(min(value, candidate["cap"]))
    if kind == "floor_cap":
        return clamp(max(candidate["floor"], min(value, candidate["cap"])))
    return value


def candidate_set(rows):
    actual_mean = sum(to_float(row["actual_probability"]) for row in rows) / len(rows)
    candidates = [
        {"name": "identity_no_change", "kind": "scale", "factor": 1.0},
    ]
    for factor in (0.75, 0.85, 0.90, 0.95, 1.05, 1.10, 1.15, 1.25):
        candidates.append({"name": f"scale_{factor:g}", "kind": "scale", "factor": factor})
    for shift in (-0.05, -0.025, 0.025, 0.05):
        candidates.append({"name": f"bias_shift_{shift:+g}", "kind": "bias_shift", "shift": shift})
    for blend in (0.10, 0.20, 0.35, 0.50):
        candidates.append(
            {
                "name": f"blend_lane_actual_mean_{blend:g}",
                "kind": "blend_actual_rate",
                "blend": blend,
                "lane_actual_mean": actual_mean,
            }
        )
    for cap in (0.80, 0.90, 0.95):
        candidates.append({"name": f"cap_{cap:g}", "kind": "cap", "cap": cap})
    for floor, cap in ((0.01, 0.95), (0.02, 0.95), (0.05, 0.95)):
        candidates.append({"name": f"floor_{floor:g}_cap_{cap:g}", "kind": "floor_cap", "floor": floor, "cap": cap})
    return candidates


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = read_csv(BASE_FULL)
    target_rows = [row for row in all_rows if clean(row.get("draw_family")) in TARGET_FAMILIES]
    rows_by_family = defaultdict(list)
    for row in target_rows:
        rows_by_family[row["draw_family"]].append(row)

    summary_rows = []
    best_by_family = {}
    for family, rows in sorted(rows_by_family.items()):
        base = metrics(rows)
        family_results = []
        for candidate in candidate_set(rows):
            tuned_rows = []
            for row in rows:
                tuned = dict(row)
                tuned["candidate_probability"] = apply_candidate(to_float(row["predicted_probability"]), candidate)
                tuned_rows.append(tuned)
            result = metrics(tuned_rows, pred_col="candidate_probability")
            result.update(
                {
                    "draw_family": family,
                    "candidate": candidate["name"],
                    "baseline_mae": base["mae"],
                    "baseline_rmse": base["rmse"],
                    "baseline_bias": base["bias"],
                    "mae_delta": result["mae"] - base["mae"],
                    "rmse_delta": result["rmse"] - base["rmse"],
                    "bias_abs_delta": abs(result["bias"]) - abs(base["bias"]),
                }
            )
            family_results.append(result)
        family_results.sort(key=lambda row: (row["mae"], row["rmse"], abs(row["bias"])))
        best_by_family[family] = family_results[0]
        summary_rows.extend(family_results)

    write_csv(
        OUT / "lane_tuning_candidate_results.csv",
        summary_rows,
        [
            "draw_family",
            "candidate",
            "row_count",
            "mae",
            "rmse",
            "bias",
            "failure_count_abs_error_gt_0_25",
            "baseline_mae",
            "baseline_rmse",
            "baseline_bias",
            "mae_delta",
            "rmse_delta",
            "bias_abs_delta",
        ],
    )

    best_rows = list(best_by_family.values())
    write_csv(
        OUT / "lane_tuning_best_candidates.csv",
        best_rows,
        [
            "draw_family",
            "candidate",
            "row_count",
            "mae",
            "rmse",
            "bias",
            "failure_count_abs_error_gt_0_25",
            "baseline_mae",
            "baseline_rmse",
            "baseline_bias",
            "mae_delta",
            "rmse_delta",
            "bias_abs_delta",
        ],
    )

    tuned_full = []
    best_lookup = {row["draw_family"]: row["candidate"] for row in best_rows}
    candidates_by_name = {
        (family, candidate["name"]): candidate
        for family, rows in rows_by_family.items()
        for candidate in candidate_set(rows)
    }
    for row in all_rows:
        tuned = dict(row)
        family = clean(row.get("draw_family"))
        if family in best_lookup:
            candidate = candidates_by_name[(family, best_lookup[family])]
            tuned["candidate_probability"] = apply_candidate(to_float(row["predicted_probability"]), candidate)
            tuned["lane_tuning_candidate"] = candidate["name"]
            tuned["lane_tuning_status"] = "LANE_TUNED_CANDIDATE"
        else:
            tuned["candidate_probability"] = to_float(row["predicted_probability"])
            tuned["lane_tuning_candidate"] = "identity_no_change"
            tuned["lane_tuning_status"] = "UNCHANGED_NON_TARGET_LANE"
        actual = to_float(row["actual_probability"])
        error = tuned["candidate_probability"] - actual
        tuned["candidate_error"] = error
        tuned["candidate_abs_error"] = abs(error)
        tuned["candidate_squared_error"] = error * error
        tuned_full.append(tuned)

    write_csv(
        OUT / "prediction_validation_lane_tuned_candidate.csv",
        tuned_full,
        list(tuned_full[0].keys()),
    )

    before = metrics(all_rows)
    after = metrics(tuned_full, pred_col="candidate_probability")
    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_validation_file": str(BASE_FULL),
        "target_draw_families": sorted(TARGET_FAMILIES),
        "best_candidates": best_by_family,
        "baseline": before,
        "lane_tuned_candidate": after,
        "overall_mae_delta": after["mae"] - before["mae"],
        "overall_rmse_delta": after["rmse"] - before["rmse"],
        "overall_bias_abs_delta": abs(after["bias"]) - abs(before["bias"]),
        "recommendation": "REVIEW_CANDIDATES_ONLY_DO_NOT_PROMOTE",
        "outputs": {
            "candidate_results": str(OUT / "lane_tuning_candidate_results.csv"),
            "best_candidates": str(OUT / "lane_tuning_best_candidates.csv"),
            "lane_tuned_candidate": str(OUT / "prediction_validation_lane_tuned_candidate.csv"),
        },
    }
    (OUT / "lane_specific_tuning_summary.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    report = [
        "# Lane-Specific Tuning Audit",
        "",
        f"Generated UTC: {status['generated_at_utc']}",
        "",
        "No production prediction output was overwritten. This is an audit candidate only.",
        "",
        "## Overall",
        "",
        f"- Baseline MAE: `{before['mae']}`",
        f"- Candidate MAE: `{after['mae']}`",
        f"- Baseline RMSE: `{before['rmse']}`",
        f"- Candidate RMSE: `{after['rmse']}`",
        f"- Baseline bias: `{before['bias']}`",
        f"- Candidate bias: `{after['bias']}`",
        "",
        "## Best Candidates",
        "",
    ]
    for row in best_rows:
        report.append(
            f"- `{row['draw_family']}`: `{row['candidate']}` MAE `{row['baseline_mae']}` -> `{row['mae']}`, RMSE `{row['baseline_rmse']}` -> `{row['rmse']}`"
        )
    (OUT / "LANE_SPECIFIC_TUNING_REPORT.md").write_text("\\n".join(report) + "\\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
