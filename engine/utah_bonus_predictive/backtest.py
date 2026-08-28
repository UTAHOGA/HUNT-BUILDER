"""Backtest builders for Utah bonus predictive outputs."""

from __future__ import annotations

from collections import defaultdict


def mean_absolute_error(actual: list[float], predicted: list[float]) -> float:
    if not actual or not predicted or len(actual) != len(predicted):
        return 0.0
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def brier_score(actual_binary: list[int], predicted_probability: list[float]) -> float:
    if not actual_binary or len(actual_binary) != len(predicted_probability):
        return 0.0
    return sum((y - p) ** 2 for y, p in zip(actual_binary, predicted_probability)) / len(actual_binary)


def cutoff_from_observed(points_map: dict[int, dict[str, int]], max_point_permits: int) -> int | None:
    running = 0
    cutoff = None
    for points in sorted(points_map.keys(), reverse=True):
        running += points_map[points].get("eligible", 0)
        if running <= max_point_permits:
            cutoff = points
    return cutoff


def cutoff_from_predicted(points_map: dict[int, int], max_point_permits: int) -> int | None:
    running = 0
    cutoff = None
    for points in sorted(points_map.keys(), reverse=True):
        running += points_map[points]
        if running <= max_point_permits:
            cutoff = points
    return cutoff


def probability_bucket(probability: float) -> str:
    if probability < 0.10:
        return "[0.00,0.10)"
    if probability < 0.25:
        return "[0.10,0.25)"
    if probability < 0.50:
        return "[0.25,0.50)"
    if probability < 0.75:
        return "[0.50,0.75)"
    return "[0.75,1.00]"


def calibration_error_by_bucket(point_rows: list[tuple[float, float]]) -> float | None:
    if not point_rows:
        return None
    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for predicted_probability, observed_outcome in point_rows:
        buckets[probability_bucket(predicted_probability)].append((predicted_probability, observed_outcome))
    weighted_errors: list[float] = []
    total_points = 0
    for bucket_rows in buckets.values():
        count = len(bucket_rows)
        total_points += count
        mean_predicted = sum(item[0] for item in bucket_rows) / count
        mean_observed = sum(item[1] for item in bucket_rows) / count
        weighted_errors.append(abs(mean_predicted - mean_observed) * count)
    if total_points == 0:
        return None
    return sum(weighted_errors) / total_points


def build_backtest_rows(
    permits: dict[tuple[str, str, str], dict[str, int]],
    ladders: dict[tuple[str, str, str], dict[int, dict[str, int]]],
    split_function,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    years = sorted({int(year) for (year, _, _) in permits.keys() if year.isdigit()})
    for year in years:
        next_year = year + 1
        if next_year not in years:
            continue
        pairs = {(hunt_code, residency) for (yy, hunt_code, residency) in permits.keys() if yy in {str(year), str(next_year)}}
        for hunt_code, residency in pairs:
            prior_public = permits.get((str(year), hunt_code, residency), {}).get("public", 0)
            observed = permits.get((str(next_year), hunt_code, residency), {"bonus": 0, "regular": 0})
            predicted_max, predicted_random = split_function(prior_public, residency)
            observed_max = observed["bonus"]
            observed_random = observed["regular"]

            prior_points = ladders.get((str(year), hunt_code, residency), {})
            next_points = ladders.get((str(next_year), hunt_code, residency), {})
            if not prior_points and not next_points:
                continue

            predicted_points = {
                points + 1: max(0, values["eligible"] - values["bonus"] - values["regular"])
                for points, values in prior_points.items()
            }
            all_points = sorted(set(next_points.keys()) | set(predicted_points.keys()))
            if not all_points:
                continue

            applicant_errors_at_level: list[float] = []
            applicant_errors_above: list[float] = []
            point_rows_for_calibration: list[tuple[float, float]] = []
            brier_scores: list[float] = []

            for points in all_points:
                observed_at_level = next_points.get(points, {}).get("eligible", 0)
                predicted_at_level = predicted_points.get(points, 0)
                applicant_errors_at_level.append(abs(observed_at_level - predicted_at_level))

                observed_above = sum(values.get("eligible", 0) for point_value, values in next_points.items() if point_value > points)
                predicted_above = sum(values for point_value, values in predicted_points.items() if point_value > points)
                applicant_errors_above.append(abs(observed_above - predicted_above))

                remaining_bonus = predicted_max - predicted_above
                if predicted_max <= 0 or remaining_bonus <= 0 or predicted_at_level <= 0:
                    predicted_probability = 0.0
                elif remaining_bonus >= predicted_at_level:
                    predicted_probability = 1.0
                else:
                    predicted_probability = remaining_bonus / predicted_at_level
                observed_outcome = 1.0 if next_points.get(points, {}).get("bonus", 0) > 0 else 0.0
                point_rows_for_calibration.append((predicted_probability, observed_outcome))
                brier_scores.append((predicted_probability - observed_outcome) ** 2)

            observed_cutoff = cutoff_from_observed(next_points, observed_max)
            predicted_cutoff = cutoff_from_predicted(predicted_points, predicted_max)
            calibration_error = calibration_error_by_bucket(point_rows_for_calibration)

            rows.append(
                {
                    "from_year": year,
                    "to_year": next_year,
                    "year_transition": f"{year}->{next_year}",
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "mean_absolute_error_applicants_at_level": round(sum(applicant_errors_at_level) / len(applicant_errors_at_level), 6),
                    "mean_absolute_error_applicants_above": round(sum(applicant_errors_above) / len(applicant_errors_above), 6),
                    "bonus_pool_cutoff_error": "" if observed_cutoff is None or predicted_cutoff is None else predicted_cutoff - observed_cutoff,
                    "guaranteed_at_error": "" if observed_cutoff is None or predicted_cutoff is None else predicted_cutoff - observed_cutoff,
                    "quota_split_error": abs(predicted_max - observed_max) + abs(predicted_random - observed_random),
                    "brier_score_by_point_level": round(sum(brier_scores) / len(brier_scores), 6),
                    "calibration_error_by_probability_bucket": "" if calibration_error is None else round(calibration_error, 6),
                }
            )
    return rows
