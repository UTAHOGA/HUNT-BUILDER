#!/usr/bin/env python3
"""Audit source-only CWMU probability transition candidates.

This is a development reporter. It reads retained adjacent-year comparison
rows and the canonical-derived long truth, derives every feature from the
source year, and reports candidate accuracy. It does not write forecasts,
truth, registry, runtime, or release files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.special_bonus import _build_truth_ladders


TRUTH = REPO / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
DEFAULT_AUDIT = (
    REPO
    / "audit_output_real_final/current_truth_cwmu_parent_routing_totalsfix_eightfold_20260922_v1"
)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def metrics(values: list[tuple[float, float]]) -> dict[str, float | int]:
    errors = [abs(predicted - actual) for predicted, actual in values]
    return {
        "rows": len(values),
        "mae": mean(errors),
        "p90": percentile(errors, 0.90),
        "tail_over_25pp": sum(error > 0.25 for error in errors) / len(errors),
        "false_guarantees": sum(predicted >= 0.999999 and actual < 0.999999 for predicted, actual in values),
    }


def official_probability(cell: dict[str, int] | None, alpha: float, beta: float) -> float | None:
    if not cell:
        return None
    applicants = int(cell.get("eligible", 0))
    permits = min(applicants, int(cell.get("bonus", 0)) + int(cell.get("regular", 0)))
    if applicants <= 0:
        return None
    return max(0.0, min(1.0, (permits + alpha) / (applicants + alpha + beta)))


def cell_state(cell: dict[str, int] | None) -> str:
    if not cell or int(cell.get("eligible", 0)) <= 0:
        return "NONE"
    applicants = int(cell["eligible"])
    permits = int(cell.get("bonus", 0)) + int(cell.get("regular", 0))
    if permits <= 0:
        return "ZERO"
    if permits >= applicants:
        return "ONE"
    return "FRACTIONAL"


def clipped_relative_point(value: int) -> int:
    return max(-8, min(4, value))


def smoothed_average(values: list[float], prior: float, strength: float) -> float:
    return (sum(values) + prior * strength) / (len(values) + strength)


def build_empirical_maps(
    train: list[dict[str, object]],
) -> tuple[
    dict[tuple[object, ...], list[float]],
    dict[tuple[object, ...], list[float]],
    dict[tuple[object, ...], list[float]],
]:
    fine: dict[tuple[object, ...], list[float]] = defaultdict(list)
    coarse: dict[tuple[object, ...], list[float]] = defaultdict(list)
    exact: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for item in train:
        actual = float(item["actual"])
        fine[(item["draw_pool"], item["same_state"], item["advance_state"], item["relative_top"])].append(actual)
        coarse[(item["draw_pool"], item["same_state"], item["advance_state"])].append(actual)
        exact[(item["hunt_code"], item["draw_pool"], item["residency"], item["points"])].append(actual)
    return fine, coarse, exact


def empirical_transition_prediction(
    maps: tuple[
        dict[tuple[object, ...], list[float]],
        dict[tuple[object, ...], list[float]],
        dict[tuple[object, ...], list[float]],
    ],
    row: dict[str, object],
    *,
    exact_strength: float,
    group_strength: float,
    prior: float,
) -> float:
    # The 10% weak prior is the historical statewide CWMU point-row base rate,
    # rounded before this audit. It is deliberately non-certain and only
    # anchors sparse groups; exact-code history receives the final say.
    group_key = (
        row["draw_pool"],
        row["same_state"],
        row["advance_state"],
        row["relative_top"],
    )
    fine, coarse, exact = maps
    group_values = fine.get(group_key, [])
    if not group_values:
        coarse_key = (row["draw_pool"], row["same_state"], row["advance_state"])
        group_values = coarse.get(coarse_key, [])
    group_probability = smoothed_average(group_values, prior, group_strength)

    exact_key = (row["hunt_code"], row["draw_pool"], row["residency"], row["points"])
    exact_values = exact.get(exact_key, [])
    if exact_values:
        return smoothed_average(exact_values, group_probability, exact_strength)
    return group_probability


def combine(
    same: float | None,
    advance: float | None,
    engine: float,
    mode: str,
    advance_weight: float,
) -> float:
    if same is None and advance is None:
        return engine
    if same is None:
        return float(advance)
    if advance is None:
        return float(same)
    if mode == "minimum":
        return min(same, advance)
    if mode == "geometric":
        return math.sqrt(max(0.0, same) * max(0.0, advance))
    if mode == "harmonic":
        return 0.0 if same + advance <= 0 else 2.0 * same * advance / (same + advance)
    return (1.0 - advance_weight) * same + advance_weight * advance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--truth", type=Path, default=TRUTH)
    args = parser.parse_args()

    with args.truth.open(encoding="utf-8-sig", newline="") as handle:
        truth_rows = list(csv.DictReader(handle))
    ladders, _, _, _ = _build_truth_ladders(truth_rows, set(range(2017, 2025)))

    scored: list[dict[str, object]] = []
    for source_year in range(2017, 2025):
        path = (
            args.audit_root
            / f"{source_year}_to_{source_year + 1}"
            / "comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv"
        )
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if clean(row.get("draw_design_key")) != "BONUS_CWMU_BIG_GAME":
                    continue
                if clean(row.get("scoring_decision")) != "score_probability":
                    continue
                actual = number(row.get("actual_probability"))
                engine = number(row.get("predicted_probability"))
                points = number(row.get("points"))
                if actual is None or engine is None or points is None:
                    continue
                key = (
                    "BONUS_CWMU_BIG_GAME",
                    source_year,
                    clean(row.get("hunt_code")).upper(),
                    clean(row.get("draw_pool_key")),
                    clean(row.get("residency")),
                )
                ladder = ladders.get(key, {})
                point = int(points)
                source_top = max(
                    (level for level, cell in ladder.items() if int(cell.get("eligible", 0)) > 0),
                    default=point,
                )
                same_cell = ladder.get(point)
                advance_cell = ladder.get(point - 1) if point > 0 else ladder.get(0)
                scored.append(
                    {
                        "source_year": source_year,
                        "actual": actual,
                        "engine": engine,
                        "hunt_code": clean(row.get("hunt_code")).upper(),
                        "draw_pool": clean(row.get("draw_pool_key")),
                        "residency": clean(row.get("residency")),
                        "points": point,
                        "same_cell": same_cell,
                        "advance_cell": advance_cell,
                        "same_state": cell_state(same_cell),
                        "advance_state": cell_state(advance_cell),
                        "relative_top": clipped_relative_point(point - source_top),
                    }
                )

    results: dict[str, dict[str, float | int]] = {
        "current_engine": metrics([(float(row["engine"]), float(row["actual"])) for row in scored])
    }
    fold_metrics = {
        str(source_year): metrics(
            [
                (float(row["engine"]), float(row["actual"]))
                for row in scored
                if int(row["source_year"]) == source_year
            ]
        )
        for source_year in range(2017, 2025)
    }
    for beta in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0):
        for mode in ("minimum", "geometric", "harmonic", "blend"):
            weights = (0.25, 0.5, 0.75) if mode == "blend" else (0.5,)
            for weight in weights:
                pairs: list[tuple[float, float]] = []
                for row in scored:
                    same = official_probability(row["same_cell"], 0.5, beta)
                    advance = official_probability(row["advance_cell"], 0.5, beta)
                    predicted = combine(same, advance, float(row["engine"]), mode, weight)
                    pairs.append((predicted, float(row["actual"])))
                label = f"beta_{beta:g}_{mode}" + (f"_advance_{weight:g}" if mode == "blend" else "")
                results[label] = metrics(pairs)

    shrink_results: dict[str, dict[str, float | int]] = {}
    for weight in (0.0, 0.2, 0.4, 0.6, 0.8):
        for center in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
            label = f"engine_weight_{weight:g}_center_{center:g}"
            shrink_results[label] = metrics(
                [
                    (
                        weight * float(row["engine"]) + (1.0 - weight) * center,
                        float(row["actual"]),
                    )
                    for row in scored
                ]
            )

    passing_shape = {
        label: result
        for label, result in results.items()
        if float(result["mae"]) <= 0.10
        and float(result["p90"]) <= 0.30
        and float(result["tail_over_25pp"]) <= 0.10
        and int(result["false_guarantees"]) == 0
    }
    passing_shrink = {
        label: result
        for label, result in shrink_results.items()
        if float(result["mae"]) <= 0.10
        and float(result["p90"]) <= 0.30
        and float(result["tail_over_25pp"]) <= 0.10
        and int(result["false_guarantees"]) == 0
    }

    empirical_results: dict[str, dict[str, float | int]] = {}
    training_maps = {
        source_year: build_empirical_maps(
            [item for item in scored if int(item["source_year"]) < source_year]
        )
        for source_year in range(2017, 2025)
    }
    for prior in (0.01, 0.03, 0.05, 0.10):
      for exact_strength in (8.0, 12.0, 16.0, 24.0, 32.0, 48.0):
        for group_strength in (16.0, 24.0, 32.0, 48.0, 64.0, 96.0):
            pairs: list[tuple[float, float]] = []
            for row in scored:
                if row["same_state"] == "NONE" and row["advance_state"] == "NONE":
                    continue
                source_year = int(row["source_year"])
                maps = training_maps[source_year]
                if maps[0]:
                    predicted = empirical_transition_prediction(
                        maps,
                        row,
                        exact_strength=exact_strength,
                        group_strength=group_strength,
                        prior=prior,
                    )
                else:
                    same = official_probability(row["same_cell"], 0.5, 4.0)
                    advance = official_probability(row["advance_cell"], 0.5, 4.0)
                    predicted = combine(same, advance, prior, "minimum", 0.5)
                pairs.append((predicted, float(row["actual"])))
            label = f"prior_{prior:g}_exact_{exact_strength:g}_group_{group_strength:g}"
            empirical_results[label] = metrics(pairs)
    passing_empirical = {
        label: result
        for label, result in empirical_results.items()
        if float(result["mae"]) <= 0.10
        and float(result["p90"]) <= 0.30
        and float(result["tail_over_25pp"]) <= 0.10
        and int(result["false_guarantees"]) == 0
    }
    print(
        json.dumps(
            {
                "rows": len(scored),
                "fold_metrics": fold_metrics,
                "passing_shape": passing_shape,
                "passing_shrink": passing_shrink,
                "passing_empirical": passing_empirical,
                "all": results,
                "shrink": shrink_results,
                "empirical": empirical_results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
