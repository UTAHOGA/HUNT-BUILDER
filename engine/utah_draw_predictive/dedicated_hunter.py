"""Preference predictive engine for Utah Dedicated Hunter deer."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable, Mapping
import re

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING, ALGORITHM_STATUS_MODELED_PREFERENCE, StrategySpec, TARGET_SCOPE_TARGET


MODEL_STRATEGY_NAME = "preference_dedicated_hunter_deer"
YOUTH_MODEL_STRATEGY_NAME = "preference_youth_dedicated_hunter_deer"
PREFERENCE_RULE_VERSION = "utah_preference_dedicated_hunter_deer_v1.0.0"
DEDICATED_HUNTER_POOL = "dedicated_hunter"
YOUTH_DEDICATED_HUNTER_POOL = "youth_dedicated_hunter"


STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type="PREFERENCE_DEDICATED_HUNTER_DEER",
        module_name="engine.utah_draw_predictive.dedicated_hunter",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Dedicated Hunter deer uses a preference-point model and only promotes rows with valid source history, quota, and modeled preference probabilities.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    ),
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type",
            "hunt_class",
            "weapon",
            "draw_pool",
            "source_file",
            "source_scope",
            "source_report_family",
        )
    )


def _normalized_text(row: Mapping[str, object]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _joined_text(row)).strip()


def _to_int(value: object) -> int:
    text = _clean(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _round_count(value: float) -> int:
    return max(0, int(round(value)))


def _forecast_total_permits(row: Mapping[str, object]) -> int:
    for key in (
        "permits_2026_total",
        "public_permits_2026",
        "permit_allotment_2026_total",
        "quota_2026_total",
        "permits_allotted",
    ):
        value = _to_int(row.get(key))
        if value > 0:
            return value
    return 0


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


def _is_youth_dedicated_hunter(row: Mapping[str, object]) -> bool:
    text = _normalized_text(row)
    return (
        _clean_lower(row.get("draw_pool")) == YOUTH_DEDICATED_HUNTER_POOL
        or ("youth" in text and any(token in text for token in ("dedicated hunter", "d h deer", "dh deer")))
    )


def _dedicated_hunter_lane(row: Mapping[str, object]) -> str:
    return YOUTH_DEDICATED_HUNTER_POOL if _is_youth_dedicated_hunter(row) else DEDICATED_HUNTER_POOL


def _looks_like_dedicated_hunter_deer(row: Mapping[str, object]) -> bool:
    text = _normalized_text(row)
    if "deer" not in text or "buck" not in text:
        return False
    if not any(token in text for token in ("dedicated hunter", "d h deer", "dh deer")):
        return False
    return True


def _is_supported_pool(row: Mapping[str, object]) -> bool:
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    weapon = _clean_lower(row.get("weapon"))
    text = _normalized_text(row)
    if draw_pool in {DEDICATED_HUNTER_POOL, YOUTH_DEDICATED_HUNTER_POOL, "standard", ""} and weapon == "dedicated hunter":
        return True
    return draw_pool in {DEDICATED_HUNTER_POOL, YOUTH_DEDICATED_HUNTER_POOL} or hunt_class in {
        "dedicated hunter",
        "youth dedicated hunter",
    } or any(token in text for token in ("dedicated hunter deer", "d h deer", "dh deer"))


def is_modeled_dedicated_hunter_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) in {MODEL_STRATEGY_NAME, YOUTH_MODEL_STRATEGY_NAME}
        and _clean_lower(row.get("preference_model_valid")) in {"1", "true", "yes", "y"}
    )


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[str, int, str, str], dict[int, dict[str, int]]],
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str, int], dict[str, int]],
]:
    ladders: dict[tuple[str, int, str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"eligible": 0, "drawn": 0}))
    meta: dict[tuple[str, str], dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in truth_rows:
        year = _to_int(row.get("year"))
        if year not in history_years:
            continue
        if not _looks_like_dedicated_hunter_deer(row) or not _is_supported_pool(row):
            continue

        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _clean(row.get("residency")) or "Resident"
        points = _to_int(row.get("points"))
        eligible = _to_int(row.get("eligible_applicants"))
        drawn = _to_int(row.get("total_permits")) or _to_int(row.get("preference_permits"))

        if not hunt_code:
            continue

        lane = _dedicated_hunter_lane(row)
        ladders[(lane, year, hunt_code, residency)][points]["eligible"] += eligible
        ladders[(lane, year, hunt_code, residency)][points]["drawn"] += drawn
        total_drawn_by_code_year[(lane, hunt_code, year)][residency] += drawn

        meta_key = (lane, hunt_code)
        if meta_key not in meta:
            meta[meta_key] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")) or "General Season",
                "weapon": _clean(row.get("weapon")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    keys_by_lane_code_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for lane, year, hunt_code, residency in ladders:
        keys_by_lane_code_res[(lane, hunt_code, residency)].append(year)

    for (lane, hunt_code, residency), years in keys_by_lane_code_res.items():
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(lane, prior_year, hunt_code, residency)]
            nxt = ladders[(lane, next_year, hunt_code, residency)]
            prior_zero = prior.get(0, {}).get("eligible", 0)
            next_zero = nxt.get(0, {}).get("eligible", 0)
            if prior_zero > 0:
                zero_growth_samples.append(max(0.25, min(2.0, next_zero / prior_zero)))
            for points, values in prior.items():
                unsuccessful = max(values["eligible"] - values["drawn"], 0)
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(points)
                next_count = nxt.get(points + 1, {}).get("eligible", 0)
                retention_samples[band].append(max(0.0, min(1.25, next_count / unsuccessful)))

    default_retention = {
        "0": 0.80,
        "1": 0.84,
        "2_3": 0.88,
        "4_5": 0.91,
        "6_9": 0.95,
        "10_plus": 0.97,
    }
    retention_by_band: dict[str, float] = {}
    for band, fallback in default_retention.items():
        samples = retention_samples.get(band, [])
        retention_by_band[band] = round(mean(samples), 4) if samples else fallback
    zero_growth = round(mean(zero_growth_samples), 4) if zero_growth_samples else 1.0
    return retention_by_band, zero_growth


def _preference_probability(quota: int, applicants_above: int, applicants_at_level: int) -> float:
    if quota <= 0 or applicants_at_level <= 0:
        return 0.0
    remaining = quota - applicants_above
    if remaining <= 0:
        return 0.0
    if remaining >= applicants_at_level:
        return 1.0
    return max(0.0, min(1.0, remaining / applicants_at_level))


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


def _forecast_quota_for_residency(
    lane: str,
    hunt_code: str,
    residency: str,
    forecast_total: int,
    latest_year: int,
    total_drawn_by_code_year: Mapping[tuple[str, str, int], dict[str, int]],
) -> int:
    observed = total_drawn_by_code_year.get((lane, hunt_code, latest_year), {})
    res_total = sum(int(value) for value in observed.values())
    if forecast_total <= 0:
        return 0
    if res_total <= 0:
        return forecast_total if residency == "Resident" else 0
    resident_drawn = int(observed.get("Resident", 0))
    resident_quota = max(0, min(forecast_total, round(forecast_total * (resident_drawn / max(res_total, 1)))))
    if residency == "Resident":
        return resident_quota
    return max(0, forecast_total - resident_quota)


def _forecast_applicant_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_by_band: Mapping[str, float],
    zero_growth: float,
) -> dict[int, int]:
    prior_points = sorted(int(points) for points in latest_ladder.keys())
    max_points = max(prior_points) if prior_points else 0
    tail_buffer = 4
    forecast: dict[int, int] = {}
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + tail_buffer + 1):
        unsuccessful_prior = max(
            int(latest_ladder.get(points - 1, {}).get("eligible", 0)) - int(latest_ladder.get(points - 1, {}).get("drawn", 0)),
            0,
        )
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.85)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.08
        forecast[points] = _round_count(retained + switch_proxy)

    # Preserve the zero-tail rows so the forecast keeps the same table shape as
    # the official source PDFs. Dedicated Hunter pages frequently include upper
    # point shells with zero permits that still need to survive row-key joins.
    return forecast


def build_preference_dedicated_hunter_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> list[dict[str, object]]:
    history_year_set = set(int(year) for year in history_years)
    latest_source_year = max(history_year_set)
    ladders, truth_meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows, history_year_set)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    rows: list[dict[str, object]] = []
    current_dedicated_rows = [
        row for row in db_rows
        if _looks_like_dedicated_hunter_deer(row)
        and _clean(row.get("hunt_code"))
    ]
    current_codes = {(_dedicated_hunter_lane(row), _clean(row.get("hunt_code")).upper()): row for row in current_dedicated_rows}

    years_by_key: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for lane, year, hunt_code, residency in ladders:
        years_by_key[(lane, hunt_code, residency)].append(year)

    for (lane, hunt_code), db_row in sorted(current_codes.items()):
        forecast_total = _forecast_total_permits(db_row)
        if forecast_total <= 0:
            continue

        meta = truth_meta.get((lane, hunt_code), {})
        hunt_name = _clean(db_row.get("hunt_name")) or meta.get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get("species", "Deer")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get("hunt_type", "General Season")
        weapon = _clean(db_row.get("weapon")) or meta.get("weapon", "Dedicated Hunter")
        is_youth_lane = lane == YOUTH_DEDICATED_HUNTER_POOL
        model_strategy = YOUTH_MODEL_STRATEGY_NAME if is_youth_lane else MODEL_STRATEGY_NAME
        hunt_class = "Youth Dedicated Hunter" if is_youth_lane else "Dedicated Hunter"

        for residency in ("Resident", "Nonresident"):
            available_years = sorted(year for year in set(years_by_key.get((lane, hunt_code, residency), [])) if year in history_year_set)
            if latest_source_year not in available_years:
                continue

            latest_ladder = ladders[(lane, latest_source_year, hunt_code, residency)]
            prior_total = sum(int(values["drawn"]) for values in latest_ladder.values())
            forecast_quota = _forecast_quota_for_residency(lane, hunt_code, residency, forecast_total, latest_source_year, total_drawn_by_code_year)
            if forecast_quota <= 0:
                continue

            forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
            if not forecast_ladder:
                continue

            prior_applicant_ladder = {points: int(values["eligible"]) for points, values in latest_ladder.items()}
            prior_guaranteed = _guaranteed_level(prior_applicant_ladder, prior_total)
            forecast_guaranteed = _guaranteed_level(forecast_ladder, forecast_quota)

            running_above = 0
            for points in sorted(forecast_ladder.keys(), reverse=True):
                applicants_at_level = int(forecast_ladder.get(points, 0))
                applicants_above = running_above
                probability_applicant_count = max(applicants_at_level, 1)
                probability = _preference_probability(forecast_quota, applicants_above, probability_applicant_count)
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
                        "sex_type": "Buck",
                        "hunt_type": hunt_type,
                        "hunt_class": hunt_class,
                        "residency": residency,
                        "points": str(points),
                        "draw_pool": lane,
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
                        "status": _status(probability),
                        "trend": _trend(prior_guaranteed, forecast_guaranteed),
                        "draw_outlook": _draw_outlook(probability, gap),
                        "source_years_used": ",".join(str(year) for year in available_years),
                        "source_year_count": len(available_years),
                        "latest_source_year": latest_source_year,
                        "earliest_source_year": min(available_years),
                        "source_dataset": "predictive",
                        "model_strategy": model_strategy,
                        "preference_model_valid": "TRUE",
                        "preference_model_note": (
                            f"Forecasted from {latest_source_year} {hunt_class.lower()} ladder with residency quota split and preference carry-forward."
                            if not is_youth_lane
                            else f"Forecasted from {latest_source_year} youth dedicated hunter ladder as a separate preference lane; no 20 percent youth-reserve rule applied."
                        ),
                        "weapon": weapon,
                        "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
                    }
                )
                running_above += applicants_at_level

    return rows


def pending_dedicated_hunter_row(reason: str | None = None) -> dict[str, object]:
    return {
        "draw_system_type": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "algorithm_status": ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "reason": reason or "Dedicated Hunter deer is in scope but missing valid source data, quota, or modeled preference probability.",
    }
