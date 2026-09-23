"""Preference predictive engine for Utah antlerless deer, antlerless elk, and doe pronghorn."""

from __future__ import annotations

from collections import defaultdict
import re
from statistics import median
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import (
    ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    ALGORITHM_STATUS_MODELED_PREFERENCE,
    StrategySpec,
    TARGET_SCOPE_TARGET,
    append_reason_codes,
)
from .permit_accessors import target_permit_for_residency, target_permit_total, target_residency_permit_allocation
from .preference_ladder_normalizer import normalize_preference_ladder_rows


MODEL_STRATEGY_NAME = "preference_antlerless"
PREFERENCE_RULE_VERSION = "utah_preference_antlerless_v1.6.0"
NO_PRIOR_LADDER_REASON_CODE = "ANTLERLESS_CURRENT_TARGET_NO_PRIOR_LADDER_NO_PUBLIC_P_DRAW"
PREFERENCE_TAIL_FLOOR = 0.001
PREFERENCE_TAIL_CEILINGS = {
    "PREFERENCE_ANTLERLESS_DEER": 0.995,
    "PREFERENCE_ANTLERLESS_ELK": 0.995,
    "PREFERENCE_DOE_PRONGHORN": 0.995,
}
PREFERENCE_ANTLERLESS_DRAW_SYSTEM_TYPES = set(PREFERENCE_TAIL_CEILINGS)
PREFERENCE_ANTLERLESS_DRAW_POOLS = {
    "PREFERENCE_ANTLERLESS_DEER": {
        "",
        "standard",
        "antlerless_deer",
        "general_season_antlerless_deer",
        "youth_antlerless_deer",
        "cwmu_antlerless_deer",
    },
    "PREFERENCE_ANTLERLESS_ELK": {
        "",
        "standard",
        "antlerless_elk",
        "general_season_antlerless_elk",
        "youth_antlerless_elk",
        "cwmu_antlerless_elk",
    },
    "PREFERENCE_DOE_PRONGHORN": {
        "",
        "standard",
        "antlerless_pronghorn",
        "doe_pronghorn",
        "general_season_doe_pronghorn",
        "youth_doe_pronghorn",
        "cwmu_doe_pronghorn",
    },
}
TAIL_CALIBRATION_REASON = "PREFERENCE_TAIL_CALIBRATED_FROM_REPO_BACKTEST"
TRANSITION_RATE_REASON = "PREFERENCE_SOURCE_TRANSITION_RATE_INCLUDES_SWITCHING"
LANE_CALIBRATION_REASON = "PREFERENCE_PROGRAM_RESIDENCY_TRANSITION_CALIBRATION"
EXACT_LANE_CALIBRATION_REASON = "PREFERENCE_EXACT_HUNT_RESIDENCY_TRANSITION_CALIBRATION"
NO_TRANSITION_EVIDENCE_REASON = "NO_PROGRAM_RESIDENCY_TRANSITION_EVIDENCE"
TRANSITION_RATE_QUANTILE = 0.80
TRANSITION_RATE_ESTIMATE_REASON = "PREFERENCE_SOURCE_TRANSITION_EMPIRICAL_Q80"
COHORT_COMPONENT_REASON = "PREFERENCE_RETURNING_AND_ARRIVAL_COMPONENTS_SEPARATED"
ARRIVAL_PRESSURE_REASON = "PREFERENCE_SAME_FAMILY_RESIDENCY_POINT_BAND_ARRIVAL_PRESSURE"
SPARSE_NONRESIDENT_REASON = "SPARSE_NONRESIDENT_ONE_TO_FOUR_PERMIT_LANE"
SPARSE_NONRESIDENT_CERTAINTY_WITHHELD_REASON = (
    "SPARSE_NONRESIDENT_EXACT_LANE_CERTAINTY_WITHHELD"
)
SPARSE_NONRESIDENT_MAX_PERMITS = 4


STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type="PREFERENCE_ANTLERLESS_DEER",
        module_name="engine.utah_draw_predictive.preference_antlerless",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Antlerless deer uses a preference-point model and only promotes rows with valid public standard-pool history, quota, and modeled preference probabilities.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type="PREFERENCE_ANTLERLESS_ELK",
        module_name="engine.utah_draw_predictive.preference_antlerless",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Antlerless elk uses a preference-point model and only promotes rows with valid public standard-pool history, quota, and modeled preference probabilities.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type="PREFERENCE_DOE_PRONGHORN",
        module_name="engine.utah_draw_predictive.preference_antlerless",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Doe pronghorn uses a preference-point model and only promotes rows with valid public standard-pool history, quota, and modeled preference probabilities.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    ),
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _residency_lane(row: Mapping[str, object]) -> str:
    if _clean_lower(row.get("metric_scope")) == "total":
        return "All"
    return _clean(row.get("residency")) or "All"


def _output_residency(residency: str) -> str:
    return "" if residency == "All" else residency


def _identity_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_lower(value)).strip()


def _history_identity(row: Mapping[str, object]) -> tuple[str, str]:
    return (_identity_token(row.get("hunt_name")), _identity_token(row.get("weapon")))


def _to_int(value: object) -> int:
    text = _clean(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _to_int_optional(value: object) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _row_year(row: Mapping[str, object]) -> int | None:
    for key in ("actual_draw_year", "source_year", "draw_year", "year"):
        year = _to_int_optional(row.get(key))
        if year is not None:
            return year
    return None


def _history_year_set_or_bootstrap(history_years: list[int], truth_rows: list[Mapping[str, object]]) -> set[int]:
    history_year_set = {int(year) for year in history_years}
    if history_year_set:
        return history_year_set
    inferred_years = sorted({year for row in truth_rows if (year := _row_year(row)) is not None})
    return {inferred_years[-1]} if inferred_years else set()


def _skipped_no_history_rows(forecast_year: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for draw_system_type in (
        "PREFERENCE_ANTLERLESS_DEER",
        "PREFERENCE_ANTLERLESS_ELK",
        "PREFERENCE_DOE_PRONGHORN",
    ):
        rows.append(
            {
                "family": draw_system_type,
                "draw_system_type": draw_system_type,
                "forecast_year": str(forecast_year),
                "year": str(forecast_year),
                "status": "SKIPPED_NO_HISTORY",
                "blocker": "true",
                "production_ready": "false",
                "calibration_ready": "false",
                "model_strategy": MODEL_STRATEGY_NAME,
                "preference_model_valid": "FALSE",
                "reason_codes": "SKIPPED_NO_HISTORY",
                "preference_model_note": "No source history rows were available for this antlerless preference family; no probability rows were fabricated.",
            }
        )
    return rows


def _effective_draw_pool(row: Mapping[str, object], draw_system_type: str | None = None) -> str:
    draw_pool = _clean_lower(row.get("draw_pool"))
    text = " ".join(
        _clean_lower(row.get(field))
        for field in ("hunt_name", "hunt_type", "hunt_class", "draw_pool")
    )
    if "cwmu" in text:
        return {
            "PREFERENCE_ANTLERLESS_DEER": "cwmu_antlerless_deer",
            "PREFERENCE_ANTLERLESS_ELK": "cwmu_antlerless_elk",
            "PREFERENCE_DOE_PRONGHORN": "cwmu_doe_pronghorn",
        }.get(draw_system_type or _clean(row.get("draw_system_type")), draw_pool)
    canonical_pool = {
        "antlerless_deer": "general_season_antlerless_deer",
        "antlerless_elk": "general_season_antlerless_elk",
        "antlerless_pronghorn": "general_season_doe_pronghorn",
        "doe_pronghorn": "general_season_doe_pronghorn",
    }.get(draw_pool)
    if canonical_pool:
        return canonical_pool
    if draw_pool and draw_pool != "standard":
        return draw_pool
    return {
        "PREFERENCE_ANTLERLESS_DEER": "general_season_antlerless_deer",
        "PREFERENCE_ANTLERLESS_ELK": "general_season_antlerless_elk",
        "PREFERENCE_DOE_PRONGHORN": "general_season_doe_pronghorn",
    }.get(draw_system_type or _clean(row.get("draw_system_type")), "standard")


def _round_count(value: float) -> int:
    return max(0, int(round(value)))


def _empirical_quantile(values: Iterable[float], quantile: float) -> float:
    """Return a deterministic, linearly interpolated empirical quantile."""
    samples = sorted(float(value) for value in values)
    if not samples:
        raise ValueError("at least one transition sample is required")
    if len(samples) == 1:
        return samples[0]
    position = (len(samples) - 1) * max(0.0, min(1.0, quantile))
    lower = int(position)
    upper = min(lower + 1, len(samples) - 1)
    fraction = position - lower
    return samples[lower] + (samples[upper] - samples[lower]) * fraction


def _band_for_points(points: int) -> str:
    if points <= 0:
        return "0"
    if points == 1:
        return "1"
    if points <= 3:
        return "2_3"
    if points <= 5:
        return "4_5"
    if points <= 9:
        return "6_9"
    return "10_plus"


def _target_draw_system_type(row: Mapping[str, object]) -> str | None:
    # Youth set-aside ladders can reuse the adult hunt code and hunt name.
    # Their source-level flag is therefore the required identity boundary;
    # without this check the adult preference ladder silently sums adult and
    # youth applicants and awards before forecasting.  Youth remains owned by
    # the dedicated youth/source-pool route.
    source_identity = " ".join(
        _clean_lower(row.get(field))
        for field in (
            "source_file",
            "canonical_source_file",
            "original_filename",
            "source_document",
            "source_scope",
        )
    )
    if (
        _clean_lower(row.get("source_is_youth")) in {"true", "1", "yes", "y"}
        or "youth" in source_identity
    ):
        return None
    if _clean(row.get("allocation_type")).upper() in {"PRIVATE", "PRIVATE_LANDS_ONLY", "LANDOWNER", "VOUCHER"}:
        return None
    existing = _clean(row.get("draw_system_type"))
    if existing in {
        "ANTLERLESS_ELK_CONTROL",
        "AVAILABILITY_ONLY",
        "CWMU_PRIVATE_VOUCHER",
        "GUARANTEED_LIFETIME_PERMIT",
        "OTC_CAPPED",
        "OTC_UNLIMITED",
        "PRIVATE_LANDS_ONLY",
        "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
        "REFERENCE_ONLY",
        "TRIBAL",
    }:
        return None
    text = " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool")
    )
    text = " ".join(
        part for part in (
            text,
            _clean_lower(row.get("hunt_draw_class")),
            _clean_lower(row.get("draw_class_type")),
            _clean_lower(row.get("draw_design")),
        )
        if part
    )
    if any(token in text for token in ("youth", "dedicated hunter", "private land", "landowner", "voucher", "conservation", "control", "mitigation", "depredation", "sportsman", "expo")):
        return None
    # The official CWMU antlerless deer, elk, and doe-pronghorn ladders award
    # regular/preference permits (zero bonus permits across the retained
    # 2017-2025 point rows).  CWMU is an access overlay here, not a bonus-draw
    # parent.  Male CWMU big game remains in BONUS_CWMU_BIG_GAME.
    if "cwmu" in text:
        sex = _clean_lower(row.get("sex_type"))
        if "pronghorn" in text and ("doe" in text or sex in {"antlerless", "doe"}):
            return "PREFERENCE_DOE_PRONGHORN"
        if "deer" in text and ("antlerless" in text or sex in {"antlerless", "doe"}):
            return "PREFERENCE_ANTLERLESS_DEER"
        if "elk" in text and ("antlerless" in text or sex in {"antlerless", "cow", "cow only"}):
            return "PREFERENCE_ANTLERLESS_ELK"
        return None
    if existing in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}:
        return existing
    if "pronghorn" in text and ("doe" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "doe"}):
        return "PREFERENCE_DOE_PRONGHORN"
    if "deer" in text and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "doe"}):
        return "PREFERENCE_ANTLERLESS_DEER"
    if "elk" in text and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "cow", "cow only"}):
        return "PREFERENCE_ANTLERLESS_ELK"
    return None


def _looks_like_standard_pool(row: Mapping[str, object]) -> bool:
    target_draw_system_type = _target_draw_system_type(row)
    draw_system_type = _clean(row.get("draw_system_type"))
    draw_pool = _effective_draw_pool(
        row,
        target_draw_system_type or draw_system_type,
    )
    hunt_class = _clean_lower(row.get("hunt_class"))
    hunt_draw_class = _clean_lower(row.get("hunt_draw_class") or row.get("draw_class_type"))
    draw_design = _clean_lower(row.get("draw_design"))
    draw_design_system = _clean(row.get("draw_design")).upper()
    allowed_pools = PREFERENCE_ANTLERLESS_DRAW_POOLS.get(draw_system_type, {"", "standard"})
    if (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and draw_system_type in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}
        and draw_pool in allowed_pools
        and _clean_lower(row.get("preference_model_valid")) in {"1", "true", "yes", "y"}
    ):
        return True
    family_class = hunt_draw_class or hunt_class
    allowed_pools = PREFERENCE_ANTLERLESS_DRAW_POOLS.get(target_draw_system_type or draw_system_type, {"", "standard"})
    legacy_cwmu_antlerless_bonus_label = (
        "cwmu" in " ".join(
            _clean_lower(row.get(field))
            for field in ("hunt_name", "hunt_type", "hunt_class", "draw_pool")
        )
        and draw_design_system == "BONUS_CWMU_BIG_GAME"
        and target_draw_system_type in PREFERENCE_ANTLERLESS_DRAW_SYSTEM_TYPES
    )
    return (
        draw_pool in allowed_pools
        and family_class in {"", "adult", "public", "preference", "cwmu", "cwmu_antlerless", "antlerless_deer", "antlerless_elk", "doe_pronghorn"}
        and (
            draw_design in {"", "preference"}
            or draw_design_system in PREFERENCE_ANTLERLESS_DRAW_SYSTEM_TYPES
            or legacy_cwmu_antlerless_bonus_label
        )
    )


def is_modeled_antlerless_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean_lower(row.get("preference_model_valid")) in {"1", "true", "yes", "y"}
    )


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str, int], dict[str, int]],
]:
    ladders: dict[tuple[str, int, str, str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"eligible": 0, "drawn": 0}))
    meta: dict[tuple[str, str], dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in normalize_preference_ladder_rows(truth_rows):
        year = _to_int(row.get("year"))
        if year not in history_years:
            continue
        draw_system_type = _target_draw_system_type(row)
        if not draw_system_type or not _looks_like_standard_pool(row):
            continue

        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _residency_lane(row)
        points = _to_int(row.get("points"))
        eligible = _to_int(row.get("eligible_applicants"))
        # Zero regular awards are evidence, not an invitation to reuse a
        # broader total. Legacy fields apply only when the component is absent.
        drawn = next((_to_int(row.get(field)) for field in (
            "regular_permits", "drawn", "successful_applicants", "total_permits", "preference_permits"
        ) if row.get(field) is not None and str(row[field]).strip()), 0)

        if not hunt_code:
            continue
        draw_pool = _effective_draw_pool(row, draw_system_type)

        ladders[(draw_system_type, year, hunt_code, draw_pool, residency)][points]["eligible"] += eligible
        ladders[(draw_system_type, year, hunt_code, draw_pool, residency)][points]["drawn"] += drawn
        total_drawn_by_code_year[(hunt_code, draw_pool, year)][residency] += drawn

        if (hunt_code, draw_pool) not in meta:
            meta[(hunt_code, draw_pool)] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")) or "General Season",
                "hunt_class": _clean(row.get("hunt_class")) or "Public",
                "draw_pool": draw_pool,
                "weapon": _clean(row.get("weapon")),
                "sex_type": _clean(row.get("sex_type")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
) -> tuple[
    dict[tuple[str, str, str], float],
    dict[tuple[str, str], float],
    dict[tuple[str, str], int],
]:
    """Calibrate transitions inside each draw program and residency lane.

    Resident and nonresident antlerless cohorts have materially different
    transition behavior. Pooling them together overstates thin nonresident
    carry-forward and can move the projected preference cutoff several point
    levels. Keep the existing source-only transition calculation, but estimate
    it independently for each declared design and residency lane.
    """
    retention_samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    zero_growth_samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    transition_evidence_count: dict[tuple[str, str], int] = defaultdict(int)
    keys_by_type_code_pool_res: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, draw_pool, residency in ladders:
        keys_by_type_code_pool_res[(draw_system_type, hunt_code, draw_pool, residency)].append(year)

    for key, years in keys_by_type_code_pool_res.items():
        draw_system_type, hunt_code, draw_pool, residency = key
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(draw_system_type, prior_year, hunt_code, draw_pool, residency)]
            nxt = ladders[(draw_system_type, next_year, hunt_code, draw_pool, residency)]
            transition_observed = False
            prior_zero = prior.get(0, {}).get("eligible", 0)
            next_zero = nxt.get(0, {}).get("eligible", 0)
            if prior_zero > 0:
                zero_growth_samples[(draw_system_type, residency)].append(
                    max(0.25, min(2.0, next_zero / prior_zero))
                )
                transition_observed = True
            for points, values in prior.items():
                unsuccessful = max(values["eligible"] - values["drawn"], 0)
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(points)
                next_count = nxt.get(points + 1, {}).get("eligible", 0)
                # This observed transition is the complete following-year
                # point cohort divided by the prior unsuccessful cohort.  It
                # therefore includes measured same-family switching and new
                # arrivals.  Capping it at 1.25 discarded valid official
                # high-stack years and systematically understated cutoff
                # pressure.
                retention_samples[(draw_system_type, residency, band)].append(
                    max(0.0, next_count / unsuccessful)
                )
                transition_observed = True
            if transition_observed:
                transition_evidence_count[(draw_system_type, residency)] += 1

    default_retention = {
        "0": 0.76,
        "1": 0.81,
        "2_3": 0.86,
        "4_5": 0.90,
        "6_9": 0.94,
        "10_plus": 0.97,
    }
    retention_by_lane_band: dict[tuple[str, str, str], float] = {}
    zero_growth_by_lane: dict[tuple[str, str], float] = {}
    lane_keys = {
        (draw_system_type, residency)
        for draw_system_type, _year, _hunt_code, _draw_pool, residency in ladders
    }
    for draw_system_type, residency in lane_keys:
        for band, fallback in default_retention.items():
            samples = retention_samples.get((draw_system_type, residency, band), [])
            retention_by_lane_band[(draw_system_type, residency, band)] = (
                round(_empirical_quantile(samples, TRANSITION_RATE_QUANTILE), 4)
                if samples
                else fallback
            )
        samples = zero_growth_samples.get((draw_system_type, residency), [])
        zero_growth_by_lane[(draw_system_type, residency)] = round(median(samples), 4) if samples else 1.0
    return retention_by_lane_band, zero_growth_by_lane, dict(transition_evidence_count)


def _lane_transition_profile(
    draw_system_type: str,
    residency: str,
    retention_by_lane_band: Mapping[tuple[str, str, str], float],
    zero_growth_by_lane: Mapping[tuple[str, str], float],
    *,
    hunt_code: str = "",
    draw_pool: str = "",
    exact_retention_by_lane_band: Mapping[tuple[str, str, str, str, str], float] | None = None,
    exact_zero_growth_by_lane: Mapping[tuple[str, str, str, str], float] | None = None,
) -> tuple[dict[str, float], float]:
    default_retention = {
        "0": 0.76,
        "1": 0.81,
        "2_3": 0.86,
        "4_5": 0.90,
        "6_9": 0.94,
        "10_plus": 0.97,
    }
    exact_retention_by_lane_band = exact_retention_by_lane_band or {}
    exact_zero_growth_by_lane = exact_zero_growth_by_lane or {}
    retention = {}
    for band, fallback in default_retention.items():
        program_rate = retention_by_lane_band.get((draw_system_type, residency, band), fallback)
        retention[band] = exact_retention_by_lane_band.get(
            (draw_system_type, hunt_code, draw_pool, residency, band),
            program_rate,
        )
    program_zero = zero_growth_by_lane.get((draw_system_type, residency), 1.0)
    zero_growth = exact_zero_growth_by_lane.get(
        (draw_system_type, hunt_code, draw_pool, residency),
        program_zero,
    )
    return retention, zero_growth


def _build_exact_lane_transition_profiles(
    ladders: Mapping[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
) -> tuple[
    dict[tuple[str, str, str, str, str], float],
    dict[tuple[str, str, str, str], float],
]:
    """Return robust exact-hunt lane rates when at least two transitions exist."""
    # Keep source point identity until repeatability is established. A newly
    # appearing rung in one year is arrival evidence, but it is not a second
    # independent observation for every other rung in the same point band.
    transition_counts: dict[
        tuple[str, str, str, str, str, int, int], dict[str, int]
    ] = {}
    transition_years_by_point: dict[
        tuple[str, str, str, str, str, int], set[int]
    ] = defaultdict(set)
    zero_growth_samples: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    years_by_lane: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for draw_system_type, year, hunt_code, draw_pool, residency in ladders:
        years_by_lane[(draw_system_type, hunt_code, draw_pool, residency)].add(year)

    for lane_key, years in years_by_lane.items():
        draw_system_type, hunt_code, draw_pool, residency = lane_key
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(draw_system_type, prior_year, hunt_code, draw_pool, residency)]
            nxt = ladders[(draw_system_type, next_year, hunt_code, draw_pool, residency)]
            prior_zero = prior.get(0, {}).get("eligible", 0)
            if prior_zero > 0:
                next_zero = nxt.get(0, {}).get("eligible", 0)
                zero_growth_samples[lane_key].append(max(0.25, min(2.0, next_zero / prior_zero)))
            for points, values in prior.items():
                unsuccessful = max(values["eligible"] - values["drawn"], 0)
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(points)
                next_count = nxt.get(points + 1, {}).get("eligible", 0)
                point_key = (*lane_key, band, points)
                transition_counts[(*point_key, prior_year)] = {
                    "next": max(0, next_count),
                    "unsuccessful": unsuccessful,
                }
                transition_years_by_point[point_key].add(prior_year)

    # One physical lane/band/year contributes one weighted observation. Only
    # exact source rungs observed across at least two adjacent-year pairs may
    # contribute to the exact-lane override; one-off arrivals stay in the
    # broader program/residency evidence layer.
    band_year_totals: dict[
        tuple[str, str, str, str, str, int], dict[str, int]
    ] = defaultdict(lambda: {"next": 0, "unsuccessful": 0})
    for key, counts in transition_counts.items():
        draw_system_type, hunt_code, draw_pool, residency, band, points, prior_year = key
        point_key = (draw_system_type, hunt_code, draw_pool, residency, band, points)
        if len(transition_years_by_point[point_key]) < 2:
            continue
        band_year_key = (draw_system_type, hunt_code, draw_pool, residency, band, prior_year)
        band_year_totals[band_year_key]["next"] += counts["next"]
        band_year_totals[band_year_key]["unsuccessful"] += counts["unsuccessful"]

    retention_samples: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    for key, totals in band_year_totals.items():
        *lane_band, _prior_year = key
        if totals["unsuccessful"] > 0:
            retention_samples[tuple(lane_band)].append(
                totals["next"] / totals["unsuccessful"]
            )

    exact_retention = {
        key: round(_empirical_quantile(samples, TRANSITION_RATE_QUANTILE), 4)
        for key, samples in retention_samples.items()
        if len(samples) >= 2
    }
    exact_zero_growth = {
        key: round(median(samples), 4)
        for key, samples in zero_growth_samples.items()
        if len(samples) >= 2
    }
    return exact_retention, exact_zero_growth


def _build_cohort_component_profiles(
    ladders: Mapping[tuple[str, int, str, str, str], dict[int, dict[str, int]]],
) -> tuple[
    dict[tuple[str, str, str], float],
    dict[tuple[str, str, str], float],
    dict[tuple[str, str, str], tuple[float, float, int]],
    dict[tuple[str, str, str, str, int], float],
    dict[tuple[str, str, str, str, int], float],
    dict[tuple[str, str, str, str, int], int],
]:
    """Measure returning applicants separately from residual arrivals.

    ``next_count / unsuccessful`` is not a retention probability: it can be
    greater than one because the next rung includes hunt switchers and other
    arrivals. This profile keeps the returning component bounded at one and
    records only the residual above the full prior unsuccessful cohort as a
    lane-size-normalized arrival component. All observations come from
    physically adjacent source years inside the same program and residency.
    """
    program_return_samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    exact_return_samples: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)
    exact_return_years: dict[tuple[str, str, str, str, int], set[int]] = defaultdict(set)
    transition_observations: list[dict[str, object]] = []
    years_by_lane: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for draw_system_type, year, hunt_code, draw_pool, residency in ladders:
        years_by_lane[(draw_system_type, hunt_code, draw_pool, residency)].add(year)

    for lane_key, years in years_by_lane.items():
        draw_system_type, hunt_code, draw_pool, residency = lane_key
        for prior_year in sorted(years):
            if prior_year + 1 not in years:
                continue
            prior = ladders[(draw_system_type, prior_year, hunt_code, draw_pool, residency)]
            nxt = ladders[(draw_system_type, prior_year + 1, hunt_code, draw_pool, residency)]
            lane_total = sum(max(int(values.get("eligible", 0)), 0) for values in prior.values())
            max_source_point = max(
                max((int(point) for point in prior), default=0),
                max((int(point) - 1 for point in nxt if int(point) > 0), default=0),
            )
            for source_point in range(0, max_source_point + 1):
                values = prior.get(source_point, {})
                unsuccessful = max(
                    int(values.get("eligible", 0)) - int(values.get("drawn", 0)),
                    0,
                )
                next_count = max(int(nxt.get(source_point + 1, {}).get("eligible", 0)), 0)
                exact_key = (*lane_key, source_point)
                band = _band_for_points(source_point)
                if unsuccessful > 0:
                    return_rate = min(next_count, unsuccessful) / unsuccessful
                    program_return_samples[(draw_system_type, residency, band)].append(
                        return_rate
                    )
                    exact_return_samples[exact_key].append(return_rate)
                    exact_return_years[exact_key].add(prior_year)
                transition_observations.append(
                    {
                        "draw_system_type": draw_system_type,
                        "residency": residency,
                        "band": band,
                        "exact_key": exact_key,
                        "prior_year": prior_year,
                        "unsuccessful": unsuccessful,
                        "next_count": next_count,
                        "lane_total": lane_total,
                    }
                )

    program_return = {
        key: round(_empirical_quantile(samples, TRANSITION_RATE_QUANTILE), 6)
        for key, samples in program_return_samples.items()
    }
    exact_return = {
        key: round(_empirical_quantile(samples, TRANSITION_RATE_QUANTILE), 6)
        for key, samples in exact_return_samples.items()
        if len(exact_return_years[key]) >= 2
    }

    # Estimate switch-in/arrival pressure only after the same-lane returning
    # component is established. Program fallback is deliberately keyed by
    # species design, residency, and point band. A nonresident elk transition
    # can never populate a resident or pronghorn ladder, and all observations
    # precede the forecast target year.
    program_arrival_samples: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    exact_arrival_samples: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)
    exact_arrival_years: dict[tuple[str, str, str, str, int], set[int]] = defaultdict(set)
    for observation in transition_observations:
        draw_system_type = str(observation["draw_system_type"])
        residency = str(observation["residency"])
        band = str(observation["band"])
        exact_key = observation["exact_key"]
        if not isinstance(exact_key, tuple):
            continue
        unsuccessful = int(observation["unsuccessful"])
        next_count = int(observation["next_count"])
        lane_total = int(observation["lane_total"])
        return_rate = exact_return.get(
            exact_key,
            program_return.get((draw_system_type, residency, band), 0.0),
        )
        expected_returns = unsuccessful * max(0.0, min(1.0, return_rate))
        arrival_residual = max(next_count - expected_returns, 0.0)
        if lane_total <= 0:
            continue
        arrival_share = arrival_residual / lane_total
        program_key = (draw_system_type, residency, band)
        program_arrival_samples[program_key].append(arrival_share)
        exact_arrival_samples[exact_key].append(arrival_share)
        exact_arrival_years[exact_key].add(int(observation["prior_year"]))

    program_arrival = {
        key: round(median(samples), 8)
        for key, samples in program_arrival_samples.items()
    }
    program_arrival_bounds = {
        key: (
            round(_empirical_quantile(samples, 0.10), 8),
            round(_empirical_quantile(samples, 0.90), 8),
            len(samples),
        )
        for key, samples in program_arrival_samples.items()
    }
    exact_arrival = {
        key: round(median(samples), 8)
        for key, samples in exact_arrival_samples.items()
        if len(exact_arrival_years[key]) >= 2
    }
    exact_evidence_count = {
        key: len(years) for key, years in exact_arrival_years.items()
    }
    return (
        program_return,
        program_arrival,
        program_arrival_bounds,
        exact_return,
        exact_arrival,
        exact_evidence_count,
    )


def _cohort_component_profile(
    draw_system_type: str,
    hunt_code: str,
    draw_pool: str,
    residency: str,
    source_points: Iterable[int],
    program_return: Mapping[tuple[str, str, str], float],
    program_arrival: Mapping[tuple[str, str, str], float],
    program_arrival_bounds: Mapping[tuple[str, str, str], tuple[float, float, int]],
    exact_return: Mapping[tuple[str, str, str, str, int], float],
    exact_arrival: Mapping[tuple[str, str, str, str, int], float],
    exact_evidence_count: Mapping[tuple[str, str, str, str, int], int],
) -> tuple[
    dict[int, float],
    dict[int, float],
    dict[int, tuple[float, float, int]],
    set[int],
]:
    default_return = {
        "0": 0.76,
        "1": 0.81,
        "2_3": 0.86,
        "4_5": 0.90,
        "6_9": 0.94,
        "10_plus": 0.97,
    }
    return_by_point: dict[int, float] = {}
    arrival_by_point: dict[int, float] = {}
    arrival_bounds_by_point: dict[int, tuple[float, float, int]] = {}
    exact_arrival_points: set[int] = set()
    for source_point in source_points:
        exact_key = (draw_system_type, hunt_code, draw_pool, residency, source_point)
        band = _band_for_points(source_point)
        return_by_point[source_point] = exact_return.get(
            exact_key,
            program_return.get((draw_system_type, residency, band), default_return[band]),
        )
        if exact_key in exact_arrival:
            arrival_by_point[source_point] = exact_arrival[exact_key]
            exact_arrival_points.add(source_point)
        else:
            arrival_by_point[source_point] = program_arrival.get(
                (draw_system_type, residency, band),
                0.0,
            )
        arrival_bounds_by_point[source_point] = program_arrival_bounds.get(
            (draw_system_type, residency, band),
            (0.0, 0.0, 0),
        )
        if exact_evidence_count.get(exact_key, 0) >= 2:
            exact_arrival_points.add(source_point)
    return (
        return_by_point,
        arrival_by_point,
        arrival_bounds_by_point,
        exact_arrival_points,
    )


def _preference_probability(quota: int, applicants_above: int, applicants_at_level: int) -> float:
    if quota <= 0 or applicants_at_level <= 0:
        return 0.0
    remaining = quota - applicants_above
    if remaining <= 0:
        return 0.0
    if remaining >= applicants_at_level:
        return 1.0
    return max(0.0, min(1.0, remaining / applicants_at_level))


def _calibrate_tail_probability(draw_system_type: str, probability: float) -> tuple[float, bool]:
    if probability >= 1.0:
        return PREFERENCE_TAIL_CEILINGS.get(draw_system_type, 0.90), True
    if probability <= 0.0:
        return PREFERENCE_TAIL_FLOOR, True
    return probability, False


def _guaranteed_level(ladder: Mapping[int, int], quota: int) -> int | None:
    running = 0
    guaranteed: int | None = None
    for points in sorted(ladder.keys(), reverse=True):
        applicants = max(int(ladder.get(points, 0)), 0)
        if applicants <= 0:
            continue
        if running + applicants <= quota:
            guaranteed = points
            running += applicants
            continue
        break
    return guaranteed


def _trend(prior_level: int | None, forecast_level: int | None) -> str:
    if prior_level is None and forecast_level is None:
        return "YELLOW"
    if prior_level is None:
        return "GREEN"
    if forecast_level is None:
        return "RED"
    if forecast_level > prior_level:
        return "GREEN"
    if forecast_level == prior_level:
        return "YELLOW"
    return "RED"


def _draw_outlook(probability: float, gap: int | None) -> str:
    if probability >= 0.90:
        return "GREEN LIGHT"
    if probability >= 0.25:
        return "MAY DRAW IN 5-10 YEARS"
    if probability > 0:
        return "RANDOM POOL RELIANCE"
    if gap is not None and gap <= 1:
        return "MAY DRAW IN 5-10 YEARS"
    return "POINT CREEP DEFEAT"


def _status(probability: float) -> str:
    if probability >= 0.999:
        return "ABOVE CUTOFF"
    if probability > 0:
        return "ON EDGE"
    return "BEHIND"


def _official_quota_for_residency(
    row: Mapping[str, object],
    residency: str,
    forecast_year: int,
    source_year: int | None = None,
    draw_system_type: str | None = None,
) -> tuple[int | None, str]:
    target_total = target_permit_total(row, forecast_year, source_year=None).value
    allocation = target_residency_permit_allocation(
        row,
        forecast_year,
        # Historical folds declare their source-only quota proxy in the
        # target_permits_* fields. Do not fall through to permits_<source
        # year>_* here: for a current total-only hunt that would combine the
        # new total with last year's residency split and mislabel the result
        # as an explicit target-year allocation.
        source_year=None if target_total > 0 else source_year,
        draw_system_type=draw_system_type,
    )
    if not allocation.supported:
        return None, allocation.authority
    return allocation.for_residency(residency), allocation.authority


def _forecast_applicant_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_by_band: Mapping[str, float],
    zero_growth: float,
    *,
    return_by_source_point: Mapping[int, float] | None = None,
    arrival_share_by_source_point: Mapping[int, float] | None = None,
    exact_arrival_points: set[int] | None = None,
) -> dict[int, int]:
    prior_points = sorted(int(points) for points in latest_ladder.keys())
    max_points = max(prior_points) if prior_points else 0
    tail_buffer = 6
    forecast: dict[int, int] = {}
    return_by_source_point = return_by_source_point or {}
    arrival_share_by_source_point = arrival_share_by_source_point or {}
    exact_arrival_points = exact_arrival_points or set()
    source_lane_total = sum(
        max(int(values.get("eligible", 0)), 0) for values in latest_ladder.values()
    )
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + tail_buffer + 1):
        unsuccessful_prior = max(
            int(latest_ladder.get(points - 1, {}).get("eligible", 0)) - int(latest_ladder.get(points - 1, {}).get("drawn", 0)),
            0,
        )
        source_point = points - 1
        return_rate = return_by_source_point.get(
            source_point,
            retention_by_band.get(_band_for_points(source_point), 0.84),
        )
        retained = unsuccessful_prior * max(0.0, min(1.0, return_rate))
        # A broad arrival fallback may adjust a rung with a real unsuccessful
        # source cohort. It may not populate an empty upper rung; that requires
        # repeatable evidence for this exact hunt/residency/source point.
        arrival = 0.0
        if unsuccessful_prior > 0 or source_point in exact_arrival_points:
            arrival = source_lane_total * max(
                0.0, arrival_share_by_source_point.get(source_point, 0.0)
            )
        forecast[points] = _round_count(retained + arrival)

    return forecast


def _structural_point_levels(latest_ladder: Mapping[int, dict[str, int]]) -> list[int]:
    """Return official point levels from the source table, including zero rows."""
    return sorted({int(points) for points in latest_ladder.keys()})


def _current_quota_lanes(row: Mapping[str, object], forecast_year: int) -> list[tuple[str, int]]:
    total = target_permit_total(row, forecast_year).value
    res = target_permit_for_residency(row, forecast_year, "Resident").value
    nr = target_permit_for_residency(row, forecast_year, "Nonresident").value
    if res > 0 or nr > 0:
        lanes: list[tuple[str, int]] = []
        if res > 0:
            lanes.append(("Resident", res))
        if nr > 0:
            lanes.append(("Nonresident", nr))
        return lanes
    if total > 0:
        return [("All", total)]
    return []


def _pending_current_target_row(
    *,
    draw_system_type: str,
    db_row: Mapping[str, object],
    forecast_year: int,
    residency: str,
    forecast_quota: int,
    draw_pool: str,
    hunt_class: str,
) -> dict[str, object]:
    hunt_code = _clean(db_row.get("hunt_code")).upper()
    return {
        "model_version": MODEL_VERSION,
        "rule_version": PREFERENCE_RULE_VERSION,
        "year": str(forecast_year),
        "forecast_year": str(forecast_year),
        "hunt_code": hunt_code,
        "hunt_name": _clean(db_row.get("hunt_name")),
        "species": _clean(db_row.get("species")),
        "sex_type": _clean(db_row.get("sex_type")),
        "hunt_type": _clean(db_row.get("hunt_type")) or "General Season",
        "hunt_class": hunt_class,
        "residency": _output_residency(residency),
        "points": "",
        "draw_pool": draw_pool,
        "public_permits_2025": "",
        "public_permits_2026": str(forecast_quota),
        "p_preference_draw": "",
        "p_bonus_pool": "",
        "p_random_pool": "",
        "p_draw": "",
        "p_bonus_pool_pct": "",
        "p_random_pool_pct": "",
        "p_draw_pct": "",
        "status": "NO PRIOR LADDER",
        "draw_outlook": "NO PUBLIC ODDS - PRIOR LADDER PENDING",
        "source_years_used": "",
        "source_year_count": 0,
        "latest_source_year": "",
        "earliest_source_year": "",
        "source_dataset": "predictive",
        "model_strategy": MODEL_STRATEGY_NAME,
        "preference_model_valid": "FALSE",
        "preference_model_note": "Current-year antlerless target has published 2026 permit authority, but no usable prior applicant ladder or safe crosswalk. Public p_draw is intentionally blank.",
        "weapon": _clean(db_row.get("weapon")),
        "draw_system_type": draw_system_type,
        "reason_codes": append_reason_codes("", NO_PRIOR_LADDER_REASON_CODE),
        "algorithm_status": ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "target_scope": TARGET_SCOPE_TARGET,
        "modeled_by_engine": "False",
        "reason": "Current-year antlerless target has permit authority but no prior applicant ladder; do not fabricate odds from permit totals.",
    }


def build_preference_antlerless_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> list[dict[str, object]]:
    truth_rows_list = list(truth_rows)
    history_year_set = _history_year_set_or_bootstrap(history_years, truth_rows_list)
    if not history_year_set:
        return _skipped_no_history_rows(forecast_year)
    latest_source_year = max(history_year_set)
    ladders, truth_meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows_list, history_year_set)
    retention_by_lane_band, zero_growth_by_lane, transition_evidence_count = (
        _build_retention_and_zero_growth(ladders)
    )
    exact_retention_by_lane_band, exact_zero_growth_by_lane = _build_exact_lane_transition_profiles(ladders)
    (
        program_return_by_lane_band,
        program_arrival_by_lane_band,
        program_arrival_bounds_by_lane_band,
        exact_return_by_lane_point,
        exact_arrival_by_lane_point,
        exact_transition_evidence_by_lane_point,
    ) = _build_cohort_component_profiles(ladders)

    rows: list[dict[str, object]] = []
    current_target_rows = []
    for row in db_rows:
        draw_system_type = _target_draw_system_type(row)
        if draw_system_type and _looks_like_standard_pool(row) and _clean(row.get("hunt_code")):
            current_target_rows.append((draw_system_type, row))
    current_codes = {
        (draw_system_type, _clean(row.get("hunt_code")).upper(), _effective_draw_pool(row, draw_system_type)): row
        for draw_system_type, row in current_target_rows
    }
    active_current_hunt_codes = {_clean(row.get("hunt_code")).upper() for _draw_system_type, row in current_target_rows}

    years_by_key: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, draw_pool, residency in ladders:
        years_by_key[(draw_system_type, hunt_code, draw_pool, residency)].append(year)

    history_codes_by_identity: dict[tuple[str, str, tuple[str, str], str], set[str]] = defaultdict(set)
    for draw_system_type, _year, hunt_code, draw_pool, residency in ladders:
        identity = _history_identity(truth_meta.get((hunt_code, draw_pool), {}))
        if all(identity):
            history_codes_by_identity[(draw_system_type, draw_pool, identity, residency)].add(hunt_code)

    max_points_by_type_residency: dict[tuple[str, str], int] = defaultdict(int)
    for (draw_system_type, year, _hunt_code, _draw_pool, residency), ladder in ladders.items():
        if year == latest_source_year and ladder:
            max_points_by_type_residency[(draw_system_type, residency)] = max(
                max_points_by_type_residency[(draw_system_type, residency)],
                max(int(points) for points in ladder.keys()),
            )

    for (draw_system_type, hunt_code, draw_pool), db_row in sorted(current_codes.items()):
        # Current target totals and source-only fold proxies are both exposed
        # through target-year/target_permits_* fields. A prior-year permit
        # value is history, not authority for the next quota.
        forecast_total = target_permit_total(db_row, forecast_year, source_year=None).value
        if forecast_total <= 0:
            # Retrospective unit fixtures may expose only the declared
            # source-year permit proxy. Production current rows must use the
            # target-year total above whenever one exists.
            forecast_total = target_permit_total(
                db_row,
                forecast_year,
                source_year=latest_source_year,
            ).value
        if forecast_total <= 0:
            continue

        meta = truth_meta.get((hunt_code, draw_pool), {})
        hunt_name = _clean(db_row.get("hunt_name")) or meta.get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get("species", "")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get("hunt_type", "General Season")
        hunt_class = _clean(db_row.get("hunt_class")) or meta.get("hunt_class", "Public")
        weapon = _clean(db_row.get("weapon")) or meta.get("weapon", "")
        sex_type = _clean(db_row.get("sex_type")) or meta.get("sex_type", "")
        modeled_residencies: set[str] = set()

        available_residencies = sorted(
            residency
            for available_type, code, pool, residency in years_by_key
            if available_type == draw_system_type and code == hunt_code and pool == draw_pool
        )
        if "All" in available_residencies:
            residencies_to_model = ["All"]
        else:
            residencies_to_model = available_residencies or ["Resident", "Nonresident"]

        for residency in residencies_to_model:
            available_years = sorted(year for year in set(years_by_key.get((draw_system_type, hunt_code, draw_pool, residency), [])) if year in history_year_set)
            history_source_hunt_code = hunt_code
            if not available_years:
                identity = _history_identity(db_row)
                source_candidates = {
                    source_code
                    for source_code in history_codes_by_identity.get((draw_system_type, draw_pool, identity, residency), set())
                    if source_code == hunt_code or source_code not in active_current_hunt_codes
                }
                if len(source_candidates) == 1:
                    history_source_hunt_code = next(iter(source_candidates))
                    available_years = sorted(
                        year for year in set(years_by_key.get((draw_system_type, history_source_hunt_code, draw_pool, residency), [])) if year in history_year_set
                    )
            if not available_years:
                continue

            code_latest_source_year = max(available_years)
            latest_ladder = ladders[(draw_system_type, code_latest_source_year, history_source_hunt_code, draw_pool, residency)]
            prior_total = sum(int(values["drawn"]) for values in latest_ladder.values())
            official_quota, quota_authority = _official_quota_for_residency(
                db_row,
                residency,
                forecast_year,
                source_year=latest_source_year,
                draw_system_type=draw_system_type,
            )
            forecast_quota = official_quota if official_quota is not None else 0
            if forecast_quota <= 0:
                continue
            modeled_residencies.add(residency)

            if transition_evidence_count.get((draw_system_type, residency), 0) <= 0:
                for points in _structural_point_levels(latest_ladder):
                    row = _pending_current_target_row(
                        draw_system_type=draw_system_type,
                        db_row=db_row,
                        forecast_year=forecast_year,
                        residency=residency,
                        forecast_quota=forecast_quota,
                        draw_pool=draw_pool,
                        hunt_class=hunt_class,
                    )
                    row.update(
                        {
                            "points": str(points),
                            "hunt_name": hunt_name,
                            "species": species,
                            "sex_type": sex_type,
                            "hunt_type": hunt_type,
                            "weapon": weapon,
                            "public_permits_2025": prior_total,
                            "source_years_used": ",".join(str(year) for year in available_years),
                            "source_year_count": len(available_years),
                            "latest_source_year": code_latest_source_year,
                            "earliest_source_year": min(available_years),
                            "status": "NO TRANSITION EVIDENCE",
                            "draw_outlook": "INSUFFICIENT EVIDENCE",
                            "algorithm_status": "NO_TRANSITION_EVIDENCE",
                            "preference_model_note": (
                                "The official source lane exists, but no earlier physically adjacent "
                                "transition is available for this program and residency. Applicant "
                                "carry-forward is withheld rather than filled with a generic rate."
                            ),
                            "reason_codes": append_reason_codes(
                                quota_authority,
                                NO_TRANSITION_EVIDENCE_REASON,
                            ),
                        }
                    )
                    rows.append(row)
                continue

            retention_by_band, zero_growth = _lane_transition_profile(
                draw_system_type,
                residency,
                retention_by_lane_band,
                zero_growth_by_lane,
                hunt_code=history_source_hunt_code,
                draw_pool=draw_pool,
                exact_retention_by_lane_band=exact_retention_by_lane_band,
                exact_zero_growth_by_lane=exact_zero_growth_by_lane,
            )
            source_points = range(0, max((int(point) for point in latest_ladder), default=0) + 6)
            (
                return_by_source_point,
                arrival_share_by_source_point,
                arrival_bounds_by_source_point,
                exact_arrival_points,
            ) = _cohort_component_profile(
                draw_system_type,
                history_source_hunt_code,
                draw_pool,
                residency,
                source_points,
                program_return_by_lane_band,
                program_arrival_by_lane_band,
                program_arrival_bounds_by_lane_band,
                exact_return_by_lane_point,
                exact_arrival_by_lane_point,
                exact_transition_evidence_by_lane_point,
            )
            forecast_ladder = _forecast_applicant_ladder(
                latest_ladder,
                retention_by_band,
                zero_growth,
                return_by_source_point=return_by_source_point,
                arrival_share_by_source_point=arrival_share_by_source_point,
                exact_arrival_points=exact_arrival_points,
            )
            global_max_points = max_points_by_type_residency.get((draw_system_type, residency), 0)
            global_structural_points = set(range(0, global_max_points + 3))
            for structural_point in global_structural_points:
                forecast_ladder.setdefault(structural_point, 0)
            structural_points = set(_structural_point_levels(latest_ladder)) | global_structural_points
            if not forecast_ladder and not structural_points:
                continue

            prior_applicant_ladder = {points: int(values["eligible"]) for points, values in latest_ladder.items()}
            prior_guaranteed = _guaranteed_level(prior_applicant_ladder, prior_total)
            forecast_guaranteed = _guaranteed_level(forecast_ladder, forecast_quota)

            running_above = 0
            for points in sorted(set(forecast_ladder) | set(structural_points), reverse=True):
                forecast_applicants_at_level = int(forecast_ladder.get(points, 0))
                is_structural_zero_point = forecast_applicants_at_level <= 0 and points in structural_points
                if forecast_applicants_at_level <= 0 and not is_structural_zero_point:
                    continue
                applicants_at_level = forecast_applicants_at_level
                applicants_above = running_above
                probability_applicant_count = max(forecast_applicants_at_level, 1)
                raw_probability = _preference_probability(forecast_quota, applicants_above, probability_applicant_count)
                probability, tail_calibrated = _calibrate_tail_probability(
                    draw_system_type, raw_probability
                )
                source_point = max(points - 1, 0)
                sparse_nonresident_lane = (
                    residency == "Nonresident"
                    and 1 <= forecast_quota <= SPARSE_NONRESIDENT_MAX_PERMITS
                )
                exact_repeatable_transition = (
                    source_point in exact_arrival_points
                    if points > 0
                    else (
                        draw_system_type,
                        history_source_hunt_code,
                        draw_pool,
                        residency,
                    ) in exact_zero_growth_by_lane
                )
                sparse_certainty_withheld = (
                    sparse_nonresident_lane and not exact_repeatable_transition
                )
                arrival_low, arrival_high, arrival_sample_count = (
                    arrival_bounds_by_source_point.get(source_point, (0.0, 0.0, 0))
                )
                gap = (forecast_guaranteed - points) if forecast_guaranteed is not None else None
                prior_gap = (prior_guaranteed - points) if prior_guaranteed is not None else None
                delta_gap = None if gap is None or prior_gap is None else gap - prior_gap
                rows.append(
                    {
                        "model_version": MODEL_VERSION,
                        "rule_version": PREFERENCE_RULE_VERSION,
                        "year": str(forecast_year),
                        "forecast_year": str(forecast_year),
                        "hunt_code": hunt_code,
                        "hunt_name": hunt_name,
                        "species": species,
                        "sex_type": sex_type,
                        "hunt_type": hunt_type,
                        "hunt_class": hunt_class,
                        "residency": _output_residency(residency),
                        "points": str(points),
                        "draw_pool": draw_pool,
                        "public_permits_2025": prior_total,
                        "public_permits_2026": forecast_quota,
                        "max_point_permits_2025": "",
                        "max_point_permits_2026": "",
                        "random_permits_2025": "",
                        "random_permits_2026": "",
                        "guaranteed_at_2025": "" if prior_guaranteed is None else str(prior_guaranteed),
                        "guaranteed_at_2026": "" if forecast_guaranteed is None else str(forecast_guaranteed),
                        "applicants_above": applicants_above,
                        "applicants_at_level": applicants_at_level,
                        "probability_applicant_count": probability_applicant_count,
                        "p_preference_draw": f"{probability:.6f}",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": f"{probability:.6f}",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": f"{probability * 100.0:.3f}",
                        "random_draw_odds_2026": "",
                        "gap": "" if gap is None else str(gap),
                        "delta_gap": "" if delta_gap is None else str(delta_gap),
                        "status": (
                            "SPARSE LANE / UNCERTAIN"
                            if sparse_certainty_withheld and raw_probability >= 1.0
                            else _status(probability)
                        ),
                        "trend": _trend(prior_guaranteed, forecast_guaranteed),
                        "draw_outlook": (
                            "SPARSE NONRESIDENT LANE / WIDE UNCERTAINTY"
                            if sparse_certainty_withheld
                            else _draw_outlook(probability, gap)
                        ),
                        "source_years_used": ",".join(str(year) for year in available_years),
                        "source_year_count": len(available_years),
                        "latest_source_year": code_latest_source_year,
                        "earliest_source_year": min(available_years),
                        "source_dataset": "predictive",
                        "model_strategy": MODEL_STRATEGY_NAME,
                        "preference_model_valid": "TRUE",
                        "preference_model_note": (
                            f"Forecasted from {code_latest_source_year} standard-pool ladder"
                            f"{'' if history_source_hunt_code == hunt_code else f' for historical hunt code {history_source_hunt_code}'}"
                            " with residency split and preference carry-forward."
                        ),
                        "cohort_return_rate": f"{return_by_source_point.get(source_point, 0.0):.6f}",
                        "cohort_arrival_share": f"{arrival_share_by_source_point.get(source_point, 0.0):.8f}",
                        "cohort_arrival_share_p10": f"{arrival_low:.8f}",
                        "cohort_arrival_share_p90": f"{arrival_high:.8f}",
                        "cohort_arrival_transition_samples": arrival_sample_count,
                        "exact_lane_transition_evidence_count": (
                            exact_transition_evidence_by_lane_point.get(
                                (
                                    draw_system_type,
                                    history_source_hunt_code,
                                    draw_pool,
                                    residency,
                                    source_point,
                                ),
                                0,
                            )
                            if points > 0
                            else (2 if exact_repeatable_transition else 0)
                        ),
                        "residency_lane_volatility": (
                            "SPARSE_NONRESIDENT_1_TO_4_PERMITS"
                            if sparse_nonresident_lane
                            else "STANDARD"
                        ),
                        "probability_publication_eligible": (
                            "FALSE" if sparse_certainty_withheld else "TRUE"
                        ),
                        "probability_publication_withheld_reason": (
                            SPARSE_NONRESIDENT_CERTAINTY_WITHHELD_REASON
                            if sparse_certainty_withheld
                            else ""
                        ),
                        "data_quality_grade": "D" if sparse_certainty_withheld else "C",
                        "weapon": weapon,
                        "draw_system_type": draw_system_type,
                        "reason_codes": append_reason_codes(
                            quota_authority,
                            TRANSITION_RATE_REASON,
                            TRANSITION_RATE_ESTIMATE_REASON,
                            LANE_CALIBRATION_REASON,
                            EXACT_LANE_CALIBRATION_REASON,
                            COHORT_COMPONENT_REASON,
                            ARRIVAL_PRESSURE_REASON,
                            SPARSE_NONRESIDENT_REASON if sparse_nonresident_lane else "",
                            (
                                SPARSE_NONRESIDENT_CERTAINTY_WITHHELD_REASON
                                if sparse_certainty_withheld
                                else ""
                            ),
                            TAIL_CALIBRATION_REASON if tail_calibrated else "",
                        ),
                        "algorithm_status": ALGORITHM_STATUS_MODELED_PREFERENCE,
                        "modeled_by_engine": "True",
                    }
                )
                if forecast_applicants_at_level > 0:
                    running_above += forecast_applicants_at_level

        if not modeled_residencies:
            for residency, forecast_quota in _current_quota_lanes(db_row, forecast_year):
                rows.append(
                    _pending_current_target_row(
                        draw_system_type=draw_system_type,
                        db_row=db_row,
                        forecast_year=forecast_year,
                        residency=residency,
                        forecast_quota=forecast_quota,
                        draw_pool=draw_pool,
                        hunt_class=hunt_class,
                    )
                )

    return rows


def pending_antlerless_row(draw_system_type: str, reason: str | None = None) -> dict[str, object]:
    return {
        "draw_system_type": draw_system_type,
        "algorithm_status": ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "reason": reason or "Antlerless preference category is in scope but missing valid source data, quota, or modeled preference probability.",
    }
