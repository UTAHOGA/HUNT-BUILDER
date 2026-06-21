import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "audits"
    / "prediction_validation"
    / "year_to_year_2021_to_2022_fixed_key"
    / "prediction_2021_vs_actual_2022_fixed_key_full.csv"
)
OUT = ROOT / "audits" / "prediction_validation" / "youth_reserved_pool_tuning_2021_to_2022"

YOUTH_RESERVE_20_FAMILIES = {
    "YOUTH_GENERAL_SEASON_DEER_PREFERENCE",
    "YOUTH_ANTLERLESS_PREFERENCE",
}
YOUTH_HOLDOUT_FAMILIES = {
    "YOUTH_DEDICATED_HUNTER_DEER_PREFERENCE",
    "YOUTH_TURKEY_BONUS",
    "YOUTH_BULL_ELK_BONUS",
}


def clean(value):
    return "" if value is None else str(value).strip()


def to_float(value):
    text = clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clamp(value):
    return max(0.0, min(1.0, value))


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
        if pred is None or actual is None:
            continue
        errors.append(pred - actual)
    if not errors:
        return {
            "row_count": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "failure_count_abs_error_gt_0_25": 0,
        }
    return {
        "row_count": len(errors),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "bias": sum(errors) / len(errors),
        "failure_count_abs_error_gt_0_25": sum(1 for error in errors if abs(error) > 0.25),
    }


def point_bucket(row):
    return clean(row.get("point_bucket"))


def candidate_probability(row, candidate):
    pred = to_float(row["predicted_probability"])
    if pred is None:
        return ""
    family = clean(row.get("draw_family"))
    if family not in YOUTH_RESERVE_20_FAMILIES:
        return pred

    # Audit-only approximations of the 20% reserved youth pool behavior.
    # The exact engine fix should allocate youth permits before calculating row odds.
    if candidate == "reserve_pool_scale_0_80":
        return clamp(pred * 0.80)
    if candidate == "reserve_pool_scale_0_85":
        return clamp(pred * 0.85)
    if candidate == "reserve_pool_bias_shift_minus_0_04":
        return clamp(pred - 0.04)
    if candidate == "reserve_pool_bias_shift_minus_0_055":
        return clamp(pred - 0.055)
    if candidate == "reserve_pool_high_point_dampen":
        if point_bucket(row) in {"6-10", "10+"}:
            return clamp(pred * 0.85)
        return clamp(pred * 0.95)
    if candidate == "reserve_pool_transition_band":
        if pred >= 0.80:
            return clamp(pred * 0.90)
        if pred >= 0.35:
            return clamp(pred * 0.85)
        return clamp(pred * 0.95)
    return pred


def group_by(rows, key):
    groups = {}
    for row in rows:
        groups.setdefault(clean(row.get(key)), []).append(row)
    return groups


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_csv(INPUT)
    candidates = [
        "baseline_no_change",
        "reserve_pool_scale_0_80",
        "reserve_pool_scale_0_85",
        "reserve_pool_bias_shift_minus_0_04",
        "reserve_pool_bias_shift_minus_0_055",
        "reserve_pool_high_point_dampen",
        "reserve_pool_transition_band",
    ]

    summary_rows = []
    candidate_full = []
    for candidate in candidates:
        tuned = []
        for row in rows:
            out = dict(row)
            out["candidate"] = candidate
            out["candidate_probability"] = candidate_probability(row, candidate)
            actual = to_float(out["actual_probability"])
            pred = to_float(out["candidate_probability"])
            if pred is not None and actual is not None:
                error = pred - actual
                out["candidate_error"] = error
                out["candidate_abs_error"] = abs(error)
                out["candidate_squared_error"] = error * error
                out["candidate_failure_abs_error_gt_0_25"] = str(abs(error) > 0.25).upper()
            else:
                out["candidate_error"] = ""
                out["candidate_abs_error"] = ""
                out["candidate_squared_error"] = ""
                out["candidate_failure_abs_error_gt_0_25"] = ""
            tuned.append(out)
        candidate_full.extend(tuned)

        all_metrics = metrics(tuned, "candidate_probability")
        summary_rows.append(
            {
                "scope": "ALL_ROWS",
                "candidate": candidate,
                **all_metrics,
            }
        )
        for family, family_rows in sorted(group_by(tuned, "draw_family").items()):
            if family in YOUTH_RESERVE_20_FAMILIES or family in YOUTH_HOLDOUT_FAMILIES:
                summary_rows.append(
                    {
                        "scope": family,
                        "candidate": candidate,
                        **metrics(family_rows, "candidate_probability"),
                    }
                )

    write_csv(OUT / "youth_reserved_pool_candidate_full.csv", candidate_full, list(candidate_full[0].keys()))
    write_csv(
        OUT / "youth_reserved_pool_candidate_summary.csv",
        summary_rows,
        [
            "scope",
            "candidate",
            "row_count",
            "mae",
            "rmse",
            "bias",
            "failure_count_abs_error_gt_0_25",
        ],
    )

    best_by_scope = {}
    for row in summary_rows:
        if row["candidate"] == "baseline_no_change":
            continue
        if row["scope"] not in best_by_scope or (
            float(row["mae"]),
            float(row["rmse"]),
            abs(float(row["bias"])),
        ) < (
            float(best_by_scope[row["scope"]]["mae"]),
            float(best_by_scope[row["scope"]]["rmse"]),
            abs(float(best_by_scope[row["scope"]]["bias"])),
        ):
            best_by_scope[row["scope"]] = row

    baseline_by_scope = {row["scope"]: row for row in summary_rows if row["candidate"] == "baseline_no_change"}
    best_rows = []
    for scope, best in sorted(best_by_scope.items()):
        base = baseline_by_scope[scope]
        out = dict(best)
        out["baseline_mae"] = base["mae"]
        out["baseline_rmse"] = base["rmse"]
        out["baseline_bias"] = base["bias"]
        out["mae_delta"] = float(best["mae"]) - float(base["mae"])
        out["rmse_delta"] = float(best["rmse"]) - float(base["rmse"])
        out["bias_abs_delta"] = abs(float(best["bias"])) - abs(float(base["bias"]))
        best_rows.append(out)

    write_csv(
        OUT / "youth_reserved_pool_best_candidates.csv",
        best_rows,
        [
            "scope",
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

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(INPUT),
        "outputs_dir": str(OUT),
        "rule_basis": {
            "youth_general_deer": "20 percent youth-reserved general-season buck deer permits",
            "youth_antlerless": "20 percent youth-reserved antlerless deer/elk/doe pronghorn permits",
            "youth_turkey": "not included; separate up-to-15-percent turkey rule",
            "youth_dedicated_hunter": "not included; no 20-percent youth-reserve rule found for Dedicated Hunter",
        },
        "baseline": baseline_by_scope.get("ALL_ROWS", {}),
        "best_candidates": best_by_scope,
        "recommendation": "AUDIT_ONLY_DO_NOT_PROMOTE_ENGINE_RULE_UNTIL_MULTI_YEAR_CHECK",
    }
    (OUT / "youth_reserved_pool_tuning_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    report = [
        "# Youth Reserved Pool Tuning Audit",
        "",
        f"Generated UTC: {status['generated_at_utc']}",
        "",
        "This is an audit-only probability candidate. It does not overwrite engine outputs.",
        "",
        "The 20% rule was tested only for youth general-season deer and youth antlerless lanes.",
        "Youth Dedicated Hunter and youth turkey were intentionally left as separate lanes.",
        "",
        "## Best Candidates",
        "",
    ]
    for row in best_rows:
        report.append(
            f"- `{row['scope']}`: `{row['candidate']}` MAE `{row['baseline_mae']}` -> `{row['mae']}`, bias `{row['baseline_bias']}` -> `{row['bias']}`"
        )
    (OUT / "YOUTH_RESERVED_POOL_TUNING_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
