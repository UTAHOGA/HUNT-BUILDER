from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
DEFAULT_ROLLING_DIR = REPO / "audits" / "preference_family_rolling_audit_20260701_110319"

FAMILIES = ("bonus_turkey", "youth_turkey")
DESIRED_DRAW_SYSTEM = {
    "bonus_turkey": "BONUS_TURKEY",
    "youth_turkey": "YOUTH_TURKEY_SET_ASIDE",
}
PRED_PROB_COLS = ("p_draw_mean", "p_draw", "p_preference_draw", "p_bonus_pool", "p_random_pool")
ACTUAL_PROB_COLS = ("p_draw", "total_p_draw", "resident_p_draw", "nonresident_p_draw")

# Turkey scoring must keep adult and youth pools separate. Do not add
# diagnostic policies here that omit draw_pool; those collapse adult/youth rows
# with the same hunt code and point level.
KEY_POLICIES = {
    "turkey_pool_identity_with_residency": (
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "draw_pool",
        "weapon",
        "hunt_type",
    ),
    "turkey_pool_identity": ("hunt_code", "points", "draw_system_type", "draw_pool", "weapon", "hunt_type"),
    "turkey_pool_minimal": ("hunt_code", "points", "draw_system_type", "draw_pool"),
}


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower())


def norm_points(value: object) -> str:
    try:
        return str(int(float(clean(value))))
    except Exception:
        return norm(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: Iterable[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields or ["no_rows"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def draw_system(row: dict[str, str]) -> str:
    return clean(row.get("draw_design") or row.get("draw_system_type")).upper()


def value_for_key(row: dict[str, str], key: str) -> str:
    if key == "points":
        return norm_points(row.get("points"))
    if key == "draw_system_type":
        return norm(draw_system(row))
    if key == "draw_pool":
        return norm(row.get("draw_pool"))
    return norm(row.get(key))


def row_key(row: dict[str, str], keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value_for_key(row, key) for key in keys)


def probability(row: dict[str, str], cols: Iterable[str]) -> tuple[float | None, str]:
    for col in cols:
        text = clean(row.get(col))
        if not text or text.upper() in {"N/A", "NA", "NULL", "NONE"}:
            continue
        try:
            value = float(text.replace("%", ""))
        except Exception:
            continue
        if 1 < value <= 100:
            value /= 100
        if 0 <= value <= 1:
            return value, col
    return None, ""


def family_actual(row: dict[str, str], family: str) -> bool:
    if norm(row.get("species")) != "turkey":
        return False
    if draw_system(row) != DESIRED_DRAW_SYSTEM[family]:
        return False
    if family == "bonus_turkey" and norm(row.get("hunt_class")) == "youth":
        return False
    if family == "youth_turkey" and norm(row.get("hunt_class")) != "youth":
        return False
    return True


def expand_actual_residency_lanes(row: dict[str, str]) -> list[dict[str, str]]:
    """Convert canonical total rows with resident/nonresident probability columns to lane rows."""

    expanded: list[dict[str, str]] = []
    resident_p, _ = probability(row, ("resident_p_draw",))
    nonresident_p, _ = probability(row, ("nonresident_p_draw",))
    if resident_p is not None:
        resident_row = dict(row)
        resident_row["residency"] = "Resident"
        resident_row["p_draw"] = f"{resident_p:.12g}"
        expanded.append(resident_row)
    if nonresident_p is not None:
        nonresident_row = dict(row)
        nonresident_row["residency"] = "Nonresident"
        nonresident_row["p_draw"] = f"{nonresident_p:.12g}"
        expanded.append(nonresident_row)
    if expanded:
        return expanded

    total_p, _ = probability(row, ("total_p_draw", "p_draw"))
    if total_p is None:
        return []
    total_row = dict(row)
    if not clean(total_row.get("residency")):
        total_row["residency"] = "Total"
    total_row["p_draw"] = f"{total_p:.12g}"
    return [total_row]


def family_prediction(row: dict[str, str]) -> bool:
    predicted, _ = probability(row, PRED_PROB_COLS)
    return predicted is not None


def index_rows(rows: list[dict[str, str]], keys: tuple[str, ...], cols: Iterable[str]) -> dict[tuple[str, ...], list[tuple[float, dict[str, str], str]]]:
    out: dict[tuple[str, ...], list[tuple[float, dict[str, str], str]]] = defaultdict(list)
    for row in rows:
        predicted, probability_col = probability(row, cols)
        if predicted is None:
            continue
        out[row_key(row, keys)].append((predicted, row, probability_col))
    return out


def metrics(pairs: list[tuple[float, float]]) -> dict[str, object]:
    if not pairs:
        return {"scored_rows": 0, "mae": "", "rmse": "", "bias": "", "p90_abs_error": "", "hard_0_1_reversal_rows": 0}
    errors = [predicted - actual for predicted, actual in pairs]
    abs_errors = sorted(abs(error) for error in errors)
    return {
        "scored_rows": len(pairs),
        "mae": round(sum(abs_errors) / len(abs_errors), 8),
        "rmse": round(math.sqrt(sum(error * error for error in errors) / len(errors)), 8),
        "bias": round(sum(errors) / len(errors), 8),
        "p90_abs_error": round(abs_errors[int(0.9 * (len(abs_errors) - 1))], 8),
        "hard_0_1_reversal_rows": sum(1 for predicted, actual in pairs if (predicted == 0 and actual == 1) or (predicted == 1 and actual == 0)),
    }


def complete_key_columns(rows: list[dict[str, str]], keys: tuple[str, ...]) -> bool:
    if not rows:
        return True
    available = set(rows[0])
    for key in keys:
        if key == "draw_system_type":
            if not {"draw_design", "draw_system_type"} & available:
                return False
        elif key not in available:
            return False
    return True


def score(rolling_dir: Path, output_dir: Path) -> dict[str, object]:
    output_dir = output_dir.resolve()
    run_dirs = sorted(path for path in rolling_dir.iterdir() if path.is_dir() and re.match(r"\d{4}_to_\d{4}", path.name))
    policy_rows: list[dict[str, object]] = []
    summary_pairs: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    samples: list[dict[str, object]] = []
    skipped_policy_rows: list[dict[str, object]] = []
    canon_cache: dict[Path, list[dict[str, str]]] = {}

    for run_dir in run_dirs:
        source_year, target_year = run_dir.name.split("_to_")
        canonical_path = CANONICAL_DIR / f"draw_results_{source_year}_for_{target_year}_canonical_yearly_draw_results.csv"
        actual_all = canon_cache.setdefault(canonical_path, read_csv(canonical_path))
        pred_dir = run_dir / "predictions"
        for family in FAMILIES:
            prediction_rows = [row for row in read_csv(pred_dir / f"{source_year}_{target_year}_{family}.csv") if family_prediction(row)]
            actual_rows = [row for row in actual_all if family_actual(row, family)]
            actual_numeric_rows = [lane for row in actual_rows for lane in expand_actual_residency_lanes(row)]

            for policy, keys in KEY_POLICIES.items():
                if "draw_pool" not in keys:
                    raise RuntimeError(f"Turkey scoring policy {policy} omits draw_pool")
                if not complete_key_columns(prediction_rows, keys) or not complete_key_columns(actual_all, keys):
                    skipped_policy_rows.append(
                        {
                            "run": run_dir.name,
                            "family": family,
                            "policy": policy,
                            "key_columns": ";".join(keys),
                            "skip_reason": "missing_required_key_column",
                        }
                    )
                    continue
                prediction_index = index_rows(prediction_rows, keys, PRED_PROB_COLS)
                actual_index = index_rows(actual_numeric_rows, keys, ("p_draw",))
                pairs: list[tuple[float, float]] = []
                ambiguous_prediction_rows = 0
                ambiguous_actual_rows = 0
                no_actual_key_rows = 0
                for key, prediction_values in prediction_index.items():
                    actual_values = actual_index.get(key)
                    if not actual_values:
                        no_actual_key_rows += len(prediction_values)
                        continue
                    if len(prediction_values) != 1:
                        ambiguous_prediction_rows += len(prediction_values)
                        continue
                    if len(actual_values) != 1:
                        ambiguous_actual_rows += len(actual_values)
                        continue
                    predicted, prediction_row, prediction_col = prediction_values[0]
                    actual, _actual_row, actual_col = actual_values[0]
                    pairs.append((predicted, actual))
                    summary_pairs[(family, policy)].append((predicted, actual))
                    if len(samples) < 250:
                        samples.append(
                            {
                                "run": run_dir.name,
                                "family": family,
                                "policy": policy,
                                "key": "|".join(key),
                                "hunt_code": prediction_row.get("hunt_code", ""),
                                "points": prediction_row.get("points", ""),
                                "draw_pool": prediction_row.get("draw_pool", ""),
                                "predicted_p": predicted,
                                "prediction_col": prediction_col,
                                "actual_p": actual,
                                "actual_col": actual_col,
                                "error": round(predicted - actual, 8),
                            }
                        )
                row_metrics = metrics(pairs)
                policy_rows.append(
                    {
                        "run": run_dir.name,
                        "family": family,
                        "policy": policy,
                        "key_columns": ";".join(keys),
                        "prediction_numeric_rows": len(prediction_rows),
                        "actual_numeric_rows": len(actual_numeric_rows),
                        **row_metrics,
                        "ambiguous_prediction_rows_excluded": ambiguous_prediction_rows,
                        "ambiguous_actual_rows_excluded": ambiguous_actual_rows,
                        "no_actual_key_rows": no_actual_key_rows,
                        "unscored_prediction_rows": len(prediction_rows) - int(row_metrics["scored_rows"]),
                    }
                )

    summary_rows: list[dict[str, object]] = []
    for family in FAMILIES:
        for policy in KEY_POLICIES:
            pair_values = summary_pairs.get((family, policy), [])
            row_metrics = metrics(pair_values)
            scored_years = sum(
                1
                for row in policy_rows
                if row["family"] == family and row["policy"] == policy and int(row["scored_rows"] or 0) > 0
            )
            summary_rows.append(
                {
                    "family": family,
                    "policy": policy,
                    "scored_years": scored_years,
                    **row_metrics,
                    "candidate_decision": "review_best_policy" if int(row_metrics["scored_rows"] or 0) else "not_scoreable",
                }
            )

    write_csv(output_dir / "turkey_pool_key_policy_by_year.csv", policy_rows)
    write_csv(output_dir / "turkey_pool_key_policy_summary.csv", summary_rows)
    write_csv(output_dir / "turkey_pool_key_joined_sample.csv", samples)
    write_csv(output_dir / "turkey_pool_key_skipped_policies.csv", skipped_policy_rows)

    best_bonus = max((row for row in summary_rows if row["family"] == "bonus_turkey"), key=lambda row: int(row["scored_rows"] or 0))
    best_youth = max((row for row in summary_rows if row["family"] == "youth_turkey"), key=lambda row: int(row["scored_rows"] or 0))
    summary = {
        "turkey_pool_key_scorer_complete": True,
        "runs_reviewed": len(run_dirs),
        "families_reviewed": len(FAMILIES),
        "all_policies_require_draw_pool": all("draw_pool" in keys for keys in KEY_POLICIES.values()),
        "default_key_policy": "turkey_pool_identity_with_residency",
        "default_key_columns": ";".join(KEY_POLICIES["turkey_pool_identity_with_residency"]),
        "best_bonus_turkey_policy": best_bonus,
        "best_youth_turkey_policy": best_youth,
        "runtime_updated": False,
        "audit_dir": str(output_dir.relative_to(REPO)).replace("\\", "/"),
    }
    (output_dir / "turkey_pool_key_scorer_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Turkey Pool-Key Candidate Scorer",
        "",
        f"- turkey_pool_key_scorer_complete: `{summary['turkey_pool_key_scorer_complete']}`",
        f"- all_policies_require_draw_pool: `{summary['all_policies_require_draw_pool']}`",
        f"- default_key_columns: `{summary['default_key_columns']}`",
        f"- best_bonus_turkey_policy: `{best_bonus}`",
        f"- best_youth_turkey_policy: `{best_youth}`",
        "- runtime_updated: `False`",
    ]
    (output_dir / "TURKEY_POOL_KEY_SCORER_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Turkey candidate predictions with draw_pool-mandatory keys.")
    parser.add_argument("--rolling-dir", type=Path, default=DEFAULT_ROLLING_DIR)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    output_dir = (args.output_dir or REPO / "audits" / f"turkey_pool_key_scorer_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    summary = score(args.rolling_dir, output_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
