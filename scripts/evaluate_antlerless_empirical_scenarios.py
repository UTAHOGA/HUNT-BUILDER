"""Develop a source-only empirical-scenario antlerless preference candidate.

The candidate preserves Utah preference mechanics and varies only the
following-year applicant ladder.  Each scenario is one physically adjacent
historical lane transition available before the held-out draw.  Target-year
outcomes label errors only; they never select or build a scenario.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah_draw_predictive.preference_antlerless import (  # noqa: E402
    _band_for_points,
    _build_truth_ladders,
    _preference_probability,
)


FAMILIES = {
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
}


@dataclass(frozen=True)
class TransitionScenario:
    lane_key: tuple[str, str, str, str]
    source_year: int
    rate_by_band: Mapping[str, float]
    zero_growth: float | None


def _as_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _quantile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_transition_scenarios(
    ladders: Mapping[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
) -> tuple[
    dict[tuple[str, str], list[TransitionScenario]],
    dict[tuple[str, str, str, str], list[TransitionScenario]],
]:
    """Return program/residency and exact-lane physical transition scenarios."""

    years_by_lane: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for family, year, hunt_code, draw_pool, residency in ladders:
        years_by_lane[(family, hunt_code, draw_pool, residency)].add(year)

    program: dict[tuple[str, str], list[TransitionScenario]] = defaultdict(list)
    exact: dict[tuple[str, str, str, str], list[TransitionScenario]] = defaultdict(list)
    for lane_key, years in years_by_lane.items():
        family, hunt_code, draw_pool, residency = lane_key
        for source_year in sorted(years):
            if source_year + 1 not in years:
                continue
            prior = ladders[(family, source_year, hunt_code, draw_pool, residency)]
            nxt = ladders[(family, source_year + 1, hunt_code, draw_pool, residency)]
            band_counts: dict[str, dict[str, int]] = defaultdict(
                lambda: {"next": 0, "unsuccessful": 0}
            )
            for point, values in prior.items():
                unsuccessful = max(
                    int(values.get("eligible", 0)) - int(values.get("drawn", 0)),
                    0,
                )
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(int(point))
                band_counts[band]["unsuccessful"] += unsuccessful
                band_counts[band]["next"] += max(
                    int(nxt.get(int(point) + 1, {}).get("eligible", 0)),
                    0,
                )
            rates = {
                band: counts["next"] / counts["unsuccessful"]
                for band, counts in band_counts.items()
                if counts["unsuccessful"] > 0
            }
            prior_zero = max(int(prior.get(0, {}).get("eligible", 0)), 0)
            zero_growth = (
                max(int(nxt.get(0, {}).get("eligible", 0)), 0) / prior_zero
                if prior_zero > 0
                else None
            )
            if not rates and zero_growth is None:
                continue
            scenario = TransitionScenario(lane_key, source_year, rates, zero_growth)
            program[(family, residency)].append(scenario)
            exact[lane_key].append(scenario)
    return dict(program), dict(exact)


def scenario_probability(
    *,
    source_ladder: Mapping[int, Mapping[str, int]],
    quota: int,
    point: int,
    scenarios: list[TransitionScenario],
    program_scenarios: list[TransitionScenario],
) -> tuple[float | None, dict[str, Any]]:
    if quota <= 0 or not scenarios:
        return None, {"scenario_count": 0}

    fallback_rate: dict[str, float] = {}
    for band in ("0", "1", "2_3", "4_5", "6_9", "10_plus"):
        values = [scenario.rate_by_band[band] for scenario in program_scenarios if band in scenario.rate_by_band]
        fallback_rate[band] = median(values) if values else 0.0
    zero_values = [scenario.zero_growth for scenario in program_scenarios if scenario.zero_growth is not None]
    fallback_zero = median(zero_values) if zero_values else 1.0

    max_source_point = max((int(value) for value in source_ladder), default=0)
    mechanical_probabilities: list[float] = []
    applicants_at: list[int] = []
    applicants_above: list[int] = []
    for scenario in scenarios:
        forecast: dict[int, int] = {
            0: max(
                0,
                int(
                    round(
                        int(source_ladder.get(0, {}).get("eligible", 0))
                        * (scenario.zero_growth if scenario.zero_growth is not None else fallback_zero)
                    )
                ),
            )
        }
        for target_point in range(1, max_source_point + 7):
            source_point = target_point - 1
            source = source_ladder.get(source_point, {})
            unsuccessful = max(
                int(source.get("eligible", 0)) - int(source.get("drawn", 0)),
                0,
            )
            band = _band_for_points(source_point)
            rate = scenario.rate_by_band.get(band, fallback_rate[band])
            forecast[target_point] = max(0, int(round(unsuccessful * max(rate, 0.0))))
        above = sum(count for target_point, count in forecast.items() if target_point > point)
        at = max(forecast.get(point, 0), 1)
        applicants_at.append(at)
        applicants_above.append(above)
        mechanical_probabilities.append(_preference_probability(quota, above, at))

    # Jeffreys posterior smoothing represents finite scenario uncertainty. It
    # prevents a small historical sample from being presented as a guarantee
    # without applying a family-wide probability cap.
    probability = (sum(mechanical_probabilities) + 0.5) / (len(mechanical_probabilities) + 1.0)
    return probability, {
        "scenario_count": len(mechanical_probabilities),
        "scenario_scope": "EXACT_LANE" if scenarios is not program_scenarios else "PROGRAM_RESIDENCY",
        "scenario_probability_min": min(mechanical_probabilities),
        "scenario_probability_max": max(mechanical_probabilities),
        "scenario_probability_mean_unsmoothed": sum(mechanical_probabilities) / len(mechanical_probabilities),
        "scenario_applicants_at_p10": _quantile(applicants_at, 0.10),
        "scenario_applicants_at_p50": _quantile(applicants_at, 0.50),
        "scenario_applicants_at_p90": _quantile(applicants_at, 0.90),
        "scenario_applicants_above_p10": _quantile(applicants_above, 0.10),
        "scenario_applicants_above_p50": _quantile(applicants_above, 0.50),
        "scenario_applicants_above_p90": _quantile(applicants_above, 0.90),
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [abs(_as_float(row["candidate_probability"]) - _as_float(row["actual_probability"])) for row in rows]
    ordered = sorted(errors)
    p90 = _quantile(ordered, 0.90)
    return {
        "rows": len(rows),
        "mae": sum(errors) / len(errors) if errors else None,
        "p90": p90,
        "tail_rows_over_25pp": sum(error > 0.25 for error in errors),
        "tail_rate_over_25pp": sum(error > 0.25 for error in errors) / len(errors) if errors else None,
        "false_guarantees": sum(
            _as_float(row["candidate_probability"]) >= 0.999999
            and _as_float(row["actual_probability"]) < 0.999999
            for row in rows
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-rows", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {args.out_dir}")
    args.out_dir.mkdir(parents=True)

    with args.audit_rows.open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    with args.truth.open(encoding="utf-8-sig", newline="") as handle:
        truth_rows = list(csv.DictReader(handle))
    truth_by_year: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        year = _as_int(row.get("actual_draw_year"))
        if year:
            truth_by_year[year].append(row)

    rows_by_fold: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in audit_rows:
        if row.get("draw_design") in FAMILIES:
            rows_by_fold[row["fold"]].append(row)

    candidate_rows: list[dict[str, Any]] = []
    fold_reports: dict[str, Any] = {}
    for fold, fold_rows in sorted(rows_by_fold.items()):
        source_year = _as_int(fold.split("_to_", 1)[0])
        history_rows = [
            row
            for year in range(min(truth_by_year), source_year + 1)
            for row in truth_by_year.get(year, [])
        ]
        ladders, _meta, _totals = _build_truth_ladders(
            history_rows, set(range(min(truth_by_year), source_year + 1))
        )
        program_scenarios, exact_scenarios = build_transition_scenarios(ladders)

        fold_candidates: list[dict[str, Any]] = []
        for row in fold_rows:
            family = row["draw_design"]
            hunt_code = row["hunt_code"]
            residency = row["residency"]
            point = _as_int(row["points"])
            lane_candidates = [
                (key, ladder)
                for key, ladder in ladders.items()
                if key[0] == family
                and key[1] == source_year
                and key[2] == hunt_code
                and key[4] == residency
            ]
            if len(lane_candidates) != 1:
                continue
            lane_with_year, source_ladder = lane_candidates[0]
            lane_key = (lane_with_year[0], lane_with_year[2], lane_with_year[3], lane_with_year[4])
            program = program_scenarios.get((family, residency), [])
            exact = exact_scenarios.get(lane_key, [])
            selected = exact if len(exact) >= 2 else program
            probability, evidence = scenario_probability(
                source_ladder=source_ladder,
                quota=_as_int(row["forecast_public_permits_target"]),
                point=point,
                scenarios=selected,
                program_scenarios=program,
            )
            if probability is None:
                continue
            candidate = {
                **row,
                "baseline_probability": row["predicted_probability"],
                "candidate_probability": round(probability, 10),
                "candidate_absolute_error": round(
                    abs(probability - _as_float(row["actual_probability"])), 10
                ),
                **evidence,
            }
            fold_candidates.append(candidate)
            candidate_rows.append(candidate)
        fold_reports[fold] = _metrics(fold_candidates)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        grouped[(row["draw_design"], row["residency"])].append(row)
    report = {
        "status": "DEVELOPMENT_ONLY_NOT_CERTIFICATION",
        "forecast_authority": "SOURCE_YEAR_CANONICAL_HISTORY_ONLY",
        "target_values_used_for_forecast": False,
        "candidate": "EMPIRICAL_PHYSICAL_TRANSITION_SCENARIO_MEAN_WITH_JEFFREYS_UNCERTAINTY",
        "overall": _metrics(candidate_rows),
        "by_family_residency": {
            "|".join(key): _metrics(rows) for key, rows in sorted(grouped.items())
        },
        "folds": fold_reports,
    }
    fieldnames: list[str] = []
    for row in candidate_rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with (args.out_dir / "candidate_scores.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidate_rows)
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
