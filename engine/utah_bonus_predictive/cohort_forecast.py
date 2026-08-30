"""Cohort roll-forward for Utah bonus ladders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


DEFAULT_RETENTION_PRIOR = 0.85
STRUCTURE_RETENTION_PRIORS = {
    "HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF": 0.8475305455097036,
    "TOP_POINT_MIXED": 0.860091743119952,
}
STRUCTURE_RETENTION_EVIDENCE_STRENGTH = 200.0

# A one-year bootstrap has no observed transition from which to estimate
# reapplication, hunt switching, or a target-year quota change.  These bounded
# priors are used only by audit simulation mode so that an unobserved
# transition cannot be reported as certain.  Runtime deterministic forecasts
# remain unchanged.
# Tuples follow random.triangular(low, high, mode) argument order.
BOOTSTRAP_RETENTION_RANGE = (0.50, 1.00, DEFAULT_RETENTION_PRIOR)
BOOTSTRAP_SWITCH_IN_SHARE_RANGE = (0.00, 1.00, 0.08)
BOOTSTRAP_QUOTA_SCALE_RANGE = (0.50, 1.50, 1.00)


@dataclass(frozen=True)
class CohortCarryForward:
    unsuccessful_at_level: int
    retention_rate_raw: float
    retention_rate_smoothed: float
    projected_retained_applicants: float
    projected_switch_in_applicants: float
    projected_switch_out_applicants: float


@dataclass(frozen=True)
class RolloverForecast:
    source_year: int
    retention_rate_raw: float
    retention_rate_smoothed: float
    rollover_rule: str
    cutoff_structure: str
    mixed_cutoff_point: int | None
    anchor_next_point: int | None
    structure_retention_rate_raw: float | None
    structure_retention_rate_smoothed: float | None
    structure_retention_prior: float | None
    structure_retention_matched_years: int
    structure_retention_unsuccessful_total: int
    total_source_applicants: int
    total_unsuccessful_source_applicants: int
    total_rolled_forward_applicants: int
    total_lower_point_additions: int
    total_projected_applicants: int
    applicants_by_points: dict[int, int]


@dataclass(frozen=True)
class CutoffStructure:
    structure: str
    top_point: int | None
    mixed_cutoff_point: int | None
    mixed_cutoff_unsuccessful: int
    guaranteed_stack_points: tuple[int, ...]


@dataclass(frozen=True)
class StructureRetentionCalibration:
    structure: str
    raw_rate: float
    smoothed_rate: float
    prior_rate: float
    matched_years: int
    unsuccessful_total: int


def compute_unsuccessful(total_eligible: int, bonus_permits: int, regular_permits: int) -> int:
    return max(0, int(total_eligible) - int(bonus_permits) - int(regular_permits))


def infer_retention_rate(unsuccessful_prior: int, observed_next: int) -> float:
    return observed_next / max(1, unsuccessful_prior)


def smooth_retention_rate(raw: float, prior: float = 0.85, strength: float = 0.35) -> float:
    smoothed = (1.0 - strength) * raw + strength * prior
    return clamp(smoothed, 0.0, 1.25)


def smooth_retention_rate_with_evidence(
    raw: float,
    *,
    prior: float,
    evidence_total: int,
    prior_strength: float = STRUCTURE_RETENTION_EVIDENCE_STRENGTH,
) -> float:
    if evidence_total <= 0:
        return clamp(prior, 0.0, 1.25)
    evidence_weight = evidence_total / (evidence_total + max(prior_strength, 1.0))
    smoothed = (evidence_weight * raw) + ((1.0 - evidence_weight) * prior)
    return clamp(smoothed, 0.0, 1.25)


def _eligible(row: Mapping[str, int]) -> int:
    return max(0, int(row.get("eligible", 0)))


def _unsuccessful(row: Mapping[str, int]) -> int:
    return compute_unsuccessful(
        int(row.get("eligible", 0)),
        int(row.get("bonus", 0)),
        int(row.get("regular", 0)),
    )


def detect_cutoff_structure(point_map: Mapping[int, Mapping[str, int]]) -> CutoffStructure:
    if not point_map:
        return CutoffStructure(
            structure="NO_POINT_HISTORY",
            top_point=None,
            mixed_cutoff_point=None,
            mixed_cutoff_unsuccessful=0,
            guaranteed_stack_points=(),
        )

    points_desc = sorted(point_map.keys(), reverse=True)
    top_point = points_desc[0] if points_desc else None
    guaranteed_stack: list[int] = []

    for points in points_desc:
        row = point_map[points]
        if _eligible(row) > 0 and _unsuccessful(row) <= 0:
            guaranteed_stack.append(points)
            continue
        break

    mixed_cutoff_point: int | None = None
    mixed_cutoff_unsuccessful = 0
    for points in points_desc:
        unsuccessful = _unsuccessful(point_map[points])
        if unsuccessful > 0:
            mixed_cutoff_point = points
            mixed_cutoff_unsuccessful = unsuccessful
            break

    if mixed_cutoff_point is None:
        structure = "ALL_APPLICANT_POINTS_GUARANTEED"
    elif mixed_cutoff_point == top_point:
        structure = "TOP_POINT_MIXED"
    elif guaranteed_stack:
        structure = "HAS_GUARANTEED_STACK_ABOVE_MIXED_CUTOFF"
    else:
        structure = "MIXED_CUTOFF_WITH_NONCONTIGUOUS_TOP_PATTERN"

    return CutoffStructure(
        structure=structure,
        top_point=top_point,
        mixed_cutoff_point=mixed_cutoff_point,
        mixed_cutoff_unsuccessful=mixed_cutoff_unsuccessful,
        guaranteed_stack_points=tuple(guaranteed_stack),
    )


def infer_group_retention_rate(point_history_by_year: Mapping[int, Mapping[int, Mapping[str, int]]]) -> tuple[float, float]:
    """Infer same-hunt reapply retention from observed unsuccessful cohorts.

    Public point-level data cannot identify individual applicants, so this treats
    the next year's point+1 cohort as the observable proxy for the prior year's
    unsuccessful cohort after reapply/attrition.
    """
    observed_next = 0
    unsuccessful_prior = 0
    years = sorted(point_history_by_year)
    for year in years:
        next_year = year + 1
        if next_year not in point_history_by_year:
            continue
        current = point_history_by_year[year]
        nxt = point_history_by_year[next_year]
        for points, row in current.items():
            unsuccessful = _unsuccessful(row)
            if unsuccessful <= 0:
                continue
            unsuccessful_prior += unsuccessful
            observed_next += _eligible(nxt.get(points + 1, {}))

    raw = infer_retention_rate(unsuccessful_prior, observed_next) if unsuccessful_prior > 0 else 0.85
    return raw, smooth_retention_rate(raw)


def has_observed_transition(
    point_history_by_year: Mapping[int, Mapping[int, Mapping[str, int]]],
) -> bool:
    """Return whether the hunt has at least one source-year transition."""
    years = {int(year) for year in point_history_by_year}
    return any(year + 1 in years for year in years)


def infer_structure_retention_rates(
    point_history_by_year: Mapping[int, Mapping[int, Mapping[str, int]]],
) -> dict[str, StructureRetentionCalibration]:
    grouped: dict[str, dict[str, int]] = {}
    years = sorted(point_history_by_year)

    for year in years:
        next_year = year + 1
        if next_year not in point_history_by_year:
            continue
        current = point_history_by_year[year]
        nxt = point_history_by_year[next_year]
        structure = detect_cutoff_structure(current)
        if structure.mixed_cutoff_point is None or structure.mixed_cutoff_unsuccessful <= 0:
            continue

        bucket = grouped.setdefault(
            structure.structure,
            {"matched_years": 0, "unsuccessful_total": 0, "observed_next_total": 0},
        )
        bucket["matched_years"] += 1
        bucket["unsuccessful_total"] += structure.mixed_cutoff_unsuccessful
        bucket["observed_next_total"] += _eligible(nxt.get(structure.mixed_cutoff_point + 1, {}))

    calibrations: dict[str, StructureRetentionCalibration] = {}
    for structure, sample in grouped.items():
        unsuccessful_total = int(sample["unsuccessful_total"])
        observed_next_total = int(sample["observed_next_total"])
        raw_rate = infer_retention_rate(unsuccessful_total, observed_next_total) if unsuccessful_total > 0 else DEFAULT_RETENTION_PRIOR
        prior_rate = STRUCTURE_RETENTION_PRIORS.get(structure, DEFAULT_RETENTION_PRIOR)
        smoothed_rate = smooth_retention_rate_with_evidence(
            raw_rate,
            prior=prior_rate,
            evidence_total=unsuccessful_total,
        )
        calibrations[structure] = StructureRetentionCalibration(
            structure=structure,
            raw_rate=raw_rate,
            smoothed_rate=smoothed_rate,
            prior_rate=prior_rate,
            matched_years=int(sample["matched_years"]),
            unsuccessful_total=unsuccessful_total,
        )
    return calibrations


def estimate_lower_point_additions(
    point_history_by_year: Mapping[int, Mapping[int, Mapping[str, int]]],
    source_year: int,
    retention_rate: float,
) -> dict[int, int]:
    """Estimate new/switch-in applicants by point level from the latest transition."""
    prior_year = source_year - 1
    if prior_year not in point_history_by_year or source_year not in point_history_by_year:
        return {}

    prior = point_history_by_year[prior_year]
    current = point_history_by_year[source_year]
    additions: dict[int, int] = {}
    candidate_points = set(current) | {point + 1 for point in prior}
    for points in candidate_points:
        observed = _eligible(current.get(points, {}))
        retained_from_prior = 0
        prior_row = prior.get(points - 1)
        if prior_row is not None:
            retained_from_prior = int(round(_unsuccessful(prior_row) * retention_rate))
        additions[points] = max(0, observed - retained_from_prior)
    return additions


def roll_forward_applicant_stack(
    point_history_by_year: Mapping[int, Mapping[int, Mapping[str, int]]],
    source_year: int,
    *,
    retention_rate: float | None = None,
) -> RolloverForecast:
    """Project the next draw year's applicant stack from source-year results.

    Winners are removed from the point stack. Unsuccessful applicants advance one
    point, adjusted by an inferred reapply/retention rate. Lower point additions
    are estimated from the most recent observed transition so the forecast does
    not simply hard-code the prior year's cutoff.
    """
    if source_year not in point_history_by_year:
        raise ValueError(f"source_year {source_year} is not present in point history")

    raw_retention, smoothed_retention = infer_group_retention_rate(point_history_by_year)
    source = point_history_by_year[source_year]
    source_structure = detect_cutoff_structure(source)
    structure_calibrations = infer_structure_retention_rates(point_history_by_year)
    structure_calibration = structure_calibrations.get(source_structure.structure)

    if retention_rate is not None:
        applied_retention = clamp(retention_rate, 0.0, 1.25)
        rollover_rule = "EXPLICIT_RETENTION_OVERRIDE"
    elif structure_calibration is not None:
        applied_retention = structure_calibration.smoothed_rate
        rollover_rule = "MIXED_CUTOFF_STRUCTURE_CALIBRATED"
    elif source_structure.structure in STRUCTURE_RETENTION_PRIORS and source_structure.mixed_cutoff_point is not None:
        applied_retention = STRUCTURE_RETENTION_PRIORS[source_structure.structure]
        rollover_rule = "MIXED_CUTOFF_STRUCTURE_PRIOR"
    else:
        applied_retention = smoothed_retention
        rollover_rule = "GROUP_WIDE_RETENTION_FALLBACK"
    additions = estimate_lower_point_additions(point_history_by_year, source_year, applied_retention)

    projected: dict[int, int] = {}
    total_unsuccessful = 0
    total_rolled = 0
    for points, row in source.items():
        unsuccessful = _unsuccessful(row)
        total_unsuccessful += unsuccessful
        retained = int(round(unsuccessful * applied_retention))
        if retained > 0:
            projected[points + 1] = projected.get(points + 1, 0) + retained
            total_rolled += retained

    for points, count in additions.items():
        if count > 0:
            projected[points] = projected.get(points, 0) + int(count)

    projected = {points: count for points, count in projected.items() if count > 0}
    return RolloverForecast(
        source_year=source_year,
        retention_rate_raw=raw_retention,
        retention_rate_smoothed=applied_retention,
        rollover_rule=rollover_rule,
        cutoff_structure=source_structure.structure,
        mixed_cutoff_point=source_structure.mixed_cutoff_point,
        anchor_next_point=None if source_structure.mixed_cutoff_point is None else source_structure.mixed_cutoff_point + 1,
        structure_retention_rate_raw=None if structure_calibration is None else structure_calibration.raw_rate,
        structure_retention_rate_smoothed=None if structure_calibration is None else structure_calibration.smoothed_rate,
        structure_retention_prior=None if structure_calibration is None else structure_calibration.prior_rate,
        structure_retention_matched_years=0 if structure_calibration is None else structure_calibration.matched_years,
        structure_retention_unsuccessful_total=0 if structure_calibration is None else structure_calibration.unsuccessful_total,
        total_source_applicants=sum(_eligible(row) for row in source.values()),
        total_unsuccessful_source_applicants=total_unsuccessful,
        total_rolled_forward_applicants=total_rolled,
        total_lower_point_additions=sum(additions.values()),
        total_projected_applicants=sum(projected.values()),
        applicants_by_points=projected,
    )

