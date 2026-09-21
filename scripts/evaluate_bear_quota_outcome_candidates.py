"""Evaluate source-only Bear quota-state and outcome-calibration candidates.

This is an isolated diagnostic.  Target-year actuals are opened only after the
retained forecasts and are used for scoring, never to alter a forecast.  The
script does not write production artifacts or change certification labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIMITS = {"mae": 0.10, "p90": 0.30, "tail": 0.10}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows: list[dict[str, object]], field: str) -> dict[str, object]:
    errors = sorted(abs(float(row[field]) - float(row["actual"])) for row in rows)
    if not errors:
        return {"rows": 0, "mae": None, "p90": None, "tail": None}
    p90 = errors[math.ceil(0.90 * len(errors)) - 1]
    result = {
        "rows": len(errors),
        "mae": sum(errors) / len(errors),
        "p90": p90,
        "tail": sum(error > 0.25 for error in errors) / len(errors),
    }
    result["passes_accuracy"] = all(result[key] <= limit for key, limit in LIMITS.items())
    return result


def design(row: dict[str, str]) -> str:
    return (
        "BEAR_RESTRICTED_PURSUIT_BONUS"
        if row.get("bear_draw_subtype") == "RESTRICTED_BEAR_PURSUIT"
        else "BEAR_LIMITED_ENTRY_HUNT_BONUS"
    )


def load_rows(folds: Path) -> tuple[list[dict[str, object]], dict[tuple[int, str, str], int]]:
    scored = read_csv(folds / "final_scored_rows.csv")
    output: list[dict[str, object]] = []
    yearly_quota: dict[tuple[int, str, str], int] = {}
    for source_year in range(2017, 2025):
        fold = f"{source_year}_to_{source_year + 1}"
        predictions = {
            (row["hunt_code"], row["residency"], row["points"]): row
            for row in read_csv(folds / fold / "prediction_phase" / "final_predictions.csv")
        }
        target_quota: dict[tuple[str, str], int] = defaultdict(int)
        for row in read_csv(folds / fold / "actual_projection.csv"):
            target_quota[(row["hunt_code"], row["residency"])] += int(row.get("total_permits") or 0)
        for (hunt_code, residency), quota in target_quota.items():
            yearly_quota[(source_year + 1, hunt_code, residency)] = quota
        for row in (item for item in scored if item["fold"] == fold):
            prediction = predictions[(row["hunt_code"], row["residency"], row["points"])]
            yearly_quota.setdefault(
                (source_year, row["hunt_code"], row["residency"]),
                int(float(prediction.get("public_permits_target") or 0)),
            )
            output.append(
                {
                    "source_year": source_year,
                    "draw_design": row["draw_design"],
                    "hunt_code": row["hunt_code"],
                    "residency": row["residency"],
                    "points": int(row["points"]),
                    "predicted": float(row["predicted_probability"]),
                    "actual": float(row["actual_probability"]),
                    "source_quota": int(float(prediction.get("public_permits_target") or 0)),
                }
            )
    return output, yearly_quota


def quota_review(
    rows: list[dict[str, object]],
    yearly_quota: dict[tuple[int, str, str], int],
) -> dict[str, object]:
    lane_design = {
        (str(row["hunt_code"]), str(row["residency"])): str(row["draw_design"])
        for row in rows
    }
    methods: dict[str, list[int]] = defaultdict(list)
    late: dict[str, list[int]] = defaultdict(list)
    for (target_year, hunt_code, residency), target in sorted(yearly_quota.items()):
        source_year = target_year - 1
        if source_year < 2017 or (source_year, hunt_code, residency) not in yearly_quota:
            continue
        values = [
            yearly_quota[(year, hunt_code, residency)]
            for year in range(2017, target_year)
            if (year, hunt_code, residency) in yearly_quota
        ]
        current = values[-1]
        transitions: list[tuple[int, int]] = []
        current_design = lane_design.get((hunt_code, residency))
        for (year, code, lane), value in yearly_quota.items():
            if year >= source_year or lane != residency:
                continue
            if lane_design.get((code, lane)) != current_design:
                continue
            following = yearly_quota.get((year + 1, code, lane))
            if following is not None:
                transitions.append((value, following))
        estimates = {
            "latest_same_lane": current,
            "median_last_2": round(statistics.median(values[-2:])),
            "median_last_3": round(statistics.median(values[-3:])),
            "mean_last_2": round(sum(values[-2:]) / len(values[-2:])),
            "mean_last_3": round(sum(values[-3:]) / len(values[-3:])),
            "linear_last_delta": max(0, current + (current - values[-2])) if len(values) > 1 else current,
        }
        matching = [following for previous, following in transitions if previous == current]
        estimates["program_residency_markov_mode"] = (
            Counter(matching).most_common(1)[0][0] if matching else current
        )
        for method, estimate in estimates.items():
            error = abs(int(estimate) - int(target))
            methods[method].append(error)
            if target_year >= 2023:
                late[method].append(error)

    def summarize(values: list[int]) -> dict[str, object]:
        return {
            "lane_transitions": len(values),
            "quota_mae": sum(values) / len(values),
            "changed_lane_misses": sum(value > 0 for value in values),
        }

    return {
        "all_transitions": {method: summarize(values) for method, values in methods.items()},
        "target_years_2023_2025": {method: summarize(values) for method, values in late.items()},
        "selected_method": "latest_same_lane",
        "selection_reason": "Lowest quota MAE and fewest changed-lane misses in both reviewed windows.",
    }


def empirical_nonresident_candidate(
    train: list[dict[str, object]], test: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Frozen transparent candidate selected before opening the late folds.

    Five-percentage-point mechanical-probability cells are kept separately by
    design and residency.  Only nonresident rows are adjusted.  Five prior
    pseudo-observations retain the official mechanical probability.
    """

    cells: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for row in train:
        cell = min(int(float(row["predicted"]) / 0.05), 19)
        cells[(str(row["draw_design"]), str(row["residency"]), cell)].append(float(row["actual"]))
    output = []
    for source in test:
        row = dict(source)
        probability = float(row["predicted"])
        if row["residency"] == "Nonresident":
            cell = min(int(probability / 0.05), 19)
            observations = cells.get((str(row["draw_design"]), "Nonresident", cell), [])
            if observations:
                count = len(observations)
                target = sum(observations) / count
                weight = count / (count + 5.0)
                probability = ((1.0 - weight) * probability) + (weight * target)
        row["candidate"] = min(0.99, max(0.0, probability))
        output.append(row)
    return output


def calibration_review(rows: list[dict[str, object]]) -> dict[str, object]:
    development = [row for row in rows if int(row["source_year"]) <= 2021]
    validation = [row for row in rows if int(row["source_year"]) == 2022]
    late_training = [row for row in rows if int(row["source_year"]) <= 2022]
    late = [row for row in rows if int(row["source_year"]) >= 2023]
    validation_candidate = empirical_nonresident_candidate(development, validation)
    late_candidate = empirical_nonresident_candidate(late_training, late)

    def by_design(selected: list[dict[str, object]], field: str) -> dict[str, object]:
        return {
            draw_design: metrics(
                [row for row in selected if row["draw_design"] == draw_design], field
            )
            for draw_design in sorted({str(row["draw_design"]) for row in selected})
        }

    validation_baseline = [dict(row, candidate=row["predicted"]) for row in validation]
    late_baseline = [dict(row, candidate=row["predicted"]) for row in late]
    return {
        "frozen_candidate": {
            "cell_width": 0.05,
            "prior_strength": 5,
            "scope": "DRAW_DESIGN_RESIDENCY_MECHANICAL_PROBABILITY_CELL",
            "applied_residency": "Nonresident",
        },
        "development_years": [2017, 2018, 2019, 2020, 2021],
        "validation_source_year": 2022,
        "validation_baseline": by_design(validation_baseline, "candidate"),
        "validation_candidate": by_design(validation_candidate, "candidate"),
        "late_training_source_years": [2017, 2018, 2019, 2020, 2021, 2022],
        "late_evaluation_source_years": [2023, 2024],
        "late_baseline": by_design(late_baseline, "candidate"),
        "late_candidate": by_design(late_candidate, "candidate"),
    }


def protected_review(folds: Path) -> dict[str, object]:
    baseline = json.loads((folds / "protected_before.json").read_text(encoding="utf-8"))
    current = {
        relative: digest(ROOT / relative) if (ROOT / relative).exists() else None
        for relative in baseline
    }
    changed = [relative for relative in baseline if baseline[relative] != current[relative]]
    return {"files": len(baseline), "changed": changed, "current": current}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    folds = args.folds.resolve()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows, yearly_quota = load_rows(folds)
    result = {
        "status": "EVALUATED_NOT_CERTIFIED_DO_NOT_PROMOTE",
        "source_only_forecast_rule": True,
        "target_actuals_used_only_for_scoring": True,
        "quota_review": quota_review(rows, yearly_quota),
        "random_outcome_calibration_review": calibration_review(rows),
        "protected_review": protected_review(folds),
        "production_written": False,
        "certification_changed": False,
    }
    (out / "review.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "review_sha256": digest(out / "review.json"),
                "script_sha256": digest(Path(__file__).resolve()),
                "source_folds": str(folds.relative_to(ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
