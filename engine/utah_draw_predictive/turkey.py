"""Phase 7 turkey bonus predictive helpers for proven Utah limited-entry turkey draw rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.monte_carlo import combine_probabilities, compute_bonus_pool_probability
from engine.utah_bonus_predictive.rules import MODEL_VERSION
from engine.utah_bonus_predictive.split import split_utah_bonus_permits
from . import ALGORITHM_STATUS_MODELED_BONUS, StrategySpec, TARGET_SCOPE_TARGET


MODEL_STRATEGY_NAME = "turkey_bonus_phase7"
BONUS_RULE_VERSION = "utah_turkey_bonus_v1.0.0"
TURKEY_DRAW_SYSTEM_TYPE = "BONUS_TURKEY"

EXCLUDED_TURKEY_TOKENS = (
    "spring general season",
    "general season",
    "remaining permit",
    "remaining",
    "over the counter",
    " otc",
    "sportsman",
    "conservation",
    "expo",
    "statewide permit",
    "statewide",
    "fall management",
    "private land only",
    "private land",
    "private",
)

STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=TURKEY_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.turkey",
        algorithm_status=ALGORITHM_STATUS_MODELED_BONUS,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Limited-entry turkey uses the Utah bonus model and only promotes rows with proven limited-entry public-draw source data, valid quota, and modeled bonus probabilities.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    )
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


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


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool", "draw_design", "source_file")
    )


def _is_turkey(row: Mapping[str, object]) -> bool:
    return "turkey" in _joined_text(row)


def _is_youth_turkey(row: Mapping[str, object]) -> bool:
    source_file = _clean_lower(row.get("source_file"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    # Youth must be source-classified. Current hunt-table rows can mention
    # youth dates/set-asides while still representing the adult LE hunt code.
    return draw_pool == "youth_turkey" or "youth turkey draw results" in source_file or "youth_turkey" in source_file


def _is_excluded_turkey_context(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    return any(token in text for token in EXCLUDED_TURKEY_TOKENS)


def _is_limited_entry_or_cwmu_turkey(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    hunt_type = _clean_lower(row.get("hunt_type"))
    draw_design = _clean_lower(row.get("draw_design") or row.get("hunt_class"))
    source_file = _clean_lower(row.get("source_file"))
    hunt_code = _clean(row.get("hunt_code")).upper()
    source_backed_adult_draw_result = (
        hunt_code.startswith("TK")
        and hunt_code != "TKY"
        and (
            "turkey draw results" in source_file
            or "turkey_draw_results" in source_file
            or "utahdraws live drawoddsdata: turkey" in source_file
        )
    )
    return (
        hunt_type in {"limited entry", "cwmu"}
        or "limited entry" in text
        or "cwmu" in text
        or (draw_design == "max/weighted split" and _source_proves_bonus_turkey(row))
        or source_backed_adult_draw_result
    )


def is_turkey_row(row: Mapping[str, object]) -> bool:
    return _is_turkey(row)


def is_general_season_turkey_row(row: Mapping[str, object]) -> bool:
    if not _is_turkey(row):
        return False
    text = _joined_text(row)
    return "spring general season" in text or "general season" in text or "statewide" in text


def is_remaining_turkey_row(row: Mapping[str, object]) -> bool:
    if not _is_turkey(row):
        return False
    text = _joined_text(row)
    return "remaining permit" in text or "remaining" in text or "over the counter" in text or " otc" in text


def is_nonpublic_turkey_row(row: Mapping[str, object]) -> bool:
    if not _is_turkey(row):
        return False
    text = _joined_text(row)
    return any(token in text for token in ("private land only", "private land", "private", "sportsman", "conservation", "expo", "fall management"))


def _source_proves_bonus_turkey(row: Mapping[str, object]) -> bool:
    source_file = _clean_lower(row.get("source_file"))
    if not source_file:
        return True
    return any(
        token in source_file
        for token in (
            "turkey_bonus_points_draw_results",
            "turkey bonus points",
            "turkey draw results",
            "turkey_draw_results",
            "utahdraws live drawoddsdata: turkey",
        )
    )


def _is_proven_bonus_turkey_truth_row(row: Mapping[str, object]) -> bool:
    return (
        _is_turkey(row)
        and _is_limited_entry_or_cwmu_turkey(row)
        and not _is_excluded_turkey_context(row)
        and not _is_youth_turkey(row)
        and _clean_lower(row.get("draw_pool")) in {"", "standard"}
        and _source_proves_bonus_turkey(row)
    )


def _is_modeled_turkey_db_row(row: Mapping[str, object]) -> bool:
    return (
        _is_turkey(row)
        and _is_limited_entry_or_cwmu_turkey(row)
        and not is_general_season_turkey_row(row)
        and not is_remaining_turkey_row(row)
        and not is_nonpublic_turkey_row(row)
        and not _is_youth_turkey(row)
    )


def is_supported_turkey_bonus_row(row: Mapping[str, object]) -> bool:
    return _is_modeled_turkey_db_row(row)


def is_modeled_turkey_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME.lower()
        and _clean_lower(row.get("turkey_bonus_valid")) in {"1", "true", "yes", "y"}
        and _clean(row.get("draw_system_type")) == TURKEY_DRAW_SYSTEM_TYPE
    )


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[int, str, str], dict[int, dict[str, int]]],
    dict[str, dict[str, str]],
    dict[tuple[str, int], dict[str, int]],
]:
    ladders: dict[tuple[int, str, str], dict[int, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0})
    )
    meta: dict[str, dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in truth_rows:
        year = _to_int(row.get("year") or row.get("actual_draw_year"))
        if year not in history_years or not _is_proven_bonus_turkey_truth_row(row):
            continue
        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _clean(row.get("residency")) or "Resident"
        points = _to_int(row.get("points"))
        if not hunt_code:
            continue

        eligible = _to_int(row.get("eligible_applicants"))
        bonus = _to_int(row.get("bonus_permits"))
        regular = _to_int(row.get("regular_permits"))
        total = _to_int(row.get("total_permits"))
        ladders[(year, hunt_code, residency)][points]["eligible"] += eligible
        ladders[(year, hunt_code, residency)][points]["bonus"] += bonus
        ladders[(year, hunt_code, residency)][points]["regular"] += regular
        ladders[(year, hunt_code, residency)][points]["total"] += total
        total_drawn_by_code_year[(hunt_code, year)][residency] += total

        if hunt_code not in meta:
            meta[hunt_code] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")),
                "hunt_class": _clean(row.get("hunt_class")),
                "weapon": _clean(row.get("weapon")),
                "sex_type": _clean(row.get("sex_type")),
                "source_file": _clean(row.get("source_file")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[int, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    years_by_code_res: dict[tuple[str, str], list[int]] = defaultdict(list)
    for year, hunt_code, residency in ladders:
        years_by_code_res[(hunt_code, residency)].append(year)

    for (hunt_code, residency), years in years_by_code_res.items():
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(prior_year, hunt_code, residency)]
            nxt = ladders[(next_year, hunt_code, residency)]
            prior_zero = prior.get(0, {}).get("eligible", 0)
            next_zero = nxt.get(0, {}).get("eligible", 0)
            if prior_zero > 0:
                zero_growth_samples.append(max(0.25, min(2.0, next_zero / prior_zero)))
            for points, values in prior.items():
                unsuccessful = max(values["eligible"] - values["bonus"] - values["regular"], 0)
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(points)
                next_count = nxt.get(points + 1, {}).get("eligible", 0)
                retention_samples[band].append(max(0.0, min(1.25, next_count / unsuccessful)))

    default_retention = {
        "0": 0.78,
        "1": 0.83,
        "2_3": 0.87,
        "4_5": 0.91,
        "6_9": 0.95,
        "10_plus": 0.98,
    }
    retention_by_band: dict[str, float] = {}
    for band, fallback in default_retention.items():
        samples = retention_samples.get(band, [])
        retention_by_band[band] = round(mean(samples), 4) if samples else fallback
    zero_growth = round(mean(zero_growth_samples), 4) if zero_growth_samples else 1.0
    return retention_by_band, zero_growth


def _forecast_applicant_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_by_band: Mapping[str, float],
    zero_growth: float,
) -> dict[int, int]:
    prior_points = sorted(int(points) for points in latest_ladder.keys())
    max_points = max(prior_points) if prior_points else 0
    forecast: dict[int, int] = {}
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + 2):
        prior_level = latest_ladder.get(points - 1, {})
        unsuccessful_prior = max(int(prior_level.get("eligible", 0)) - int(prior_level.get("bonus", 0)) - int(prior_level.get("regular", 0)), 0)
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.85)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.08
        forecast[points] = _round_count(retained + switch_proxy)

    while forecast and forecast.get(max(forecast.keys()), 0) == 0:
        forecast.pop(max(forecast.keys()))
    return forecast


def _weighted_random_probability(points: int, applicants_by_points: Mapping[int, int], random_permits: int) -> float:
    total_weight = 0.0
    target_weight = 0.0
    for point_level, count in applicants_by_points.items():
        weight = max(0, int(count)) * max(1, int(point_level) + 1)
        total_weight += weight
        if int(point_level) == int(points):
            target_weight += weight
    if random_permits <= 0 or total_weight <= 0 or target_weight <= 0:
        return 0.0
    share = min(1.0, max(0.0, target_weight / total_weight))
    return max(0.0, min(1.0, 1.0 - ((1.0 - share) ** max(1, random_permits))))


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


def _status(max_point_permits: int, random_permits: int, p_bonus_pool: float) -> str:
    if max_point_permits == 0 and random_permits > 0:
        return "RANDOM ONLY"
    if p_bonus_pool >= 0.999:
        return "MAX POOL"
    if p_bonus_pool > 0:
        return "ON EDGE"
    return "BEHIND"


def _draw_outlook(probability: float, pending: bool = False, excluded: bool = False) -> str:
    if excluded:
        return "NOT A DRAW"
    if pending:
        return "MODEL PENDING"
    if probability >= 0.75:
        return "GREEN LIGHT"
    if probability > 0.10:
        return "MAY DRAW IN 5-10 YEARS"
    return "RANDOM POOL RELIANCE" if probability > 0 else "POINT CREEP DEFEAT"


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


def _forecast_quota_for_residency(
    db_row: Mapping[str, object],
    hunt_code: str,
    residency: str,
    latest_year: int,
    total_drawn_by_code_year: Mapping[tuple[str, int], dict[str, int]],
) -> int:
    res_specific = _to_int(db_row.get("permit_allotment_2026_res")) or _to_int(db_row.get("permits_2026_res"))
    nr_specific = _to_int(db_row.get("permit_allotment_2026_nr")) or _to_int(db_row.get("permits_2026_nr"))
    total = _to_int(db_row.get("permit_allotment_2026_total")) or _to_int(db_row.get("permits_2026_total"))
    if res_specific or nr_specific:
        return res_specific if residency == "Resident" else nr_specific
    observed = total_drawn_by_code_year.get((hunt_code, latest_year), {})
    observed_total = sum(int(value) for value in observed.values())
    if total <= 0:
        return 0
    if observed_total <= 0:
        return total if residency == "Resident" else 0
    resident_drawn = int(observed.get("Resident", 0))
    resident_quota = max(0, min(total, round(total * (resident_drawn / max(observed_total, 1)))))
    return resident_quota if residency == "Resident" else max(0, total - resident_quota)


def _data_quality_flags(
    available_years: list[int],
    total_applicants: int,
    public_quota: int,
    max_point_permits: int,
    latest_source_file: str,
) -> list[str]:
    flags: list[str] = []
    if len(available_years) == 1:
        flags.append("MISSING_MULTIPLE_YEARS")
    if total_applicants < 5:
        flags.append("LOW_APPLICANT_COUNT")
    if public_quota == 1:
        flags.append("ONE_PERMIT_RANDOM_ONLY")
    if max_point_permits == 0 and public_quota > 0:
        flags.append("NO_MAX_POINT_POOL")
    if latest_source_file:
        flags.append("PROVEN_TURKEY_BONUS_SOURCE")
    return flags


def build_turkey_bonus_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    history_year_set = {int(year) for year in history_years}
    source_years_used_text = ",".join(str(year) for year in history_years)
    source_year_count = len(history_years)
    earliest_source_year = min(history_years)
    fallback_latest_source_year = max(history_years)
    ladders, meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows, history_year_set)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    years_by_code_res: dict[tuple[str, str], list[int]] = defaultdict(list)
    for year, hunt_code, residency in ladders:
        years_by_code_res[(hunt_code, residency)].append(year)

    rows: list[dict[str, object]] = []
    report_counts = Counter()
    data_quality_counter: Counter[str] = Counter()
    review_rows: list[dict[str, object]] = []

    for db_row in db_rows:
        if not _is_turkey(db_row):
            continue
        hunt_code = _clean(db_row.get("hunt_code")).upper()
        if not hunt_code:
            continue
        review_rows.append(dict(db_row))
        if not _is_modeled_turkey_db_row(db_row):
            continue

        hunt_name = _clean(db_row.get("hunt_name")) or meta.get(hunt_code, {}).get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get(hunt_code, {}).get("species", "")
        sex_type = _clean(db_row.get("sex_type")) or meta.get(hunt_code, {}).get("sex_type", "")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get(hunt_code, {}).get("hunt_type", "")
        weapon = _clean(db_row.get("weapon")) or meta.get(hunt_code, {}).get("weapon", "")
        hunt_class = "CWMU" if "cwmu" in _joined_text(db_row) else "Public"

        for residency in ("Resident", "Nonresident"):
            available_years = sorted(set(years_by_code_res.get((hunt_code, residency), [])))
            latest_year = available_years[-1] if available_years else fallback_latest_source_year
            latest_ladder = ladders.get((latest_year, hunt_code, residency), {}) if available_years else {}
            latest_meta_source = meta.get(hunt_code, {}).get("source_file", "")
            prior_total = sum(int(values.get("total", 0)) for values in latest_ladder.values())
            public_quota = _forecast_quota_for_residency(db_row, hunt_code, residency, latest_year, total_drawn_by_code_year)

            if not available_years or public_quota <= 0:
                row = {
                    "model_version": MODEL_VERSION,
                    "rule_version": BONUS_RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": hunt_name,
                    "species": species,
                    "sex_type": sex_type,
                    "hunt_type": hunt_type,
                    "hunt_class": hunt_class,
                    "residency": residency,
                    "points": "",
                    "draw_pool": "standard",
                    "public_permits_2025": prior_total,
                    "public_permits_2026": public_quota,
                    "p_preference_draw": "",
                    "p_bonus_pool": "",
                    "p_random_pool": "",
                    "p_draw": "",
                    "p_draw_pct": "",
                    "draw_outlook": "MODEL PENDING",
                    "source_years_used": source_years_used_text,
                    "source_year_count": source_year_count,
                    "latest_source_year": latest_year,
                    "earliest_source_year": earliest_source_year,
                    "source_dataset": "predictive",
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "turkey_bonus_valid": "FALSE",
                    "turkey_bonus_note": "Missing latest turkey source year, multiple-year history, or usable forecast quota.",
                    "weapon": weapon,
                    "draw_system_type": TURKEY_DRAW_SYSTEM_TYPE,
                    "data_quality_flags": "|".join(
                        flag
                        for flag in [
                            "MISSING_PROVEN_TURKEY_BONUS_HISTORY" if not available_years else "",
                            "MISSING_FORECAST_QUOTA" if public_quota <= 0 else "",
                        ]
                        if flag
                    ),
                }
                rows.append(row)
                report_counts["pending"] += 1
                continue

            split = split_utah_bonus_permits(public_quota)
            max_point_permits = split.maxPointPermits
            random_permits = split.randomPermits
            forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
            if not forecast_ladder:
                row = {
                    "model_version": MODEL_VERSION,
                    "rule_version": BONUS_RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": hunt_name,
                    "species": species,
                    "sex_type": sex_type,
                    "hunt_type": hunt_type,
                    "hunt_class": hunt_class,
                    "residency": residency,
                    "points": "",
                    "draw_pool": "standard",
                    "public_permits_2025": prior_total,
                    "public_permits_2026": public_quota,
                    "p_preference_draw": "",
                    "p_bonus_pool": "",
                    "p_random_pool": "",
                    "p_draw": "",
                    "p_draw_pct": "",
                    "draw_outlook": "MODEL PENDING",
                    "source_years_used": ",".join(str(year) for year in available_years),
                    "source_year_count": len(available_years),
                    "latest_source_year": latest_year,
                    "earliest_source_year": available_years[0],
                    "source_dataset": "predictive",
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "turkey_bonus_valid": "FALSE",
                    "turkey_bonus_note": "Proven turkey bonus history existed, but the forecast ladder was empty.",
                    "weapon": weapon,
                    "draw_system_type": TURKEY_DRAW_SYSTEM_TYPE,
                    "data_quality_flags": "LOW_APPLICANT_COUNT",
                }
                rows.append(row)
                report_counts["pending"] += 1
                continue

            prior_guaranteed = _guaranteed_level({points: int(values.get("eligible", 0)) for points, values in latest_ladder.items()}, prior_total)
            forecast_guaranteed = _guaranteed_level(forecast_ladder, public_quota)
            total_applicants = sum(forecast_ladder.values())
            flags = _data_quality_flags(available_years, total_applicants, public_quota, max_point_permits, latest_meta_source)
            for flag in flags:
                data_quality_counter[flag] += 1

            for points in sorted(forecast_ladder.keys(), reverse=True):
                applicants_by_points = {int(level): int(count) for level, count in forecast_ladder.items()}
                p_bonus_pool, applicants_above, applicants_at_level = compute_bonus_pool_probability(points, applicants_by_points, max_point_permits)
                p_random_pool = _weighted_random_probability(points, applicants_by_points, random_permits)
                p_draw = combine_probabilities(p_bonus_pool, p_random_pool)
                row = {
                    "model_version": MODEL_VERSION,
                    "rule_version": BONUS_RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": hunt_name,
                    "species": species,
                    "sex_type": sex_type,
                    "hunt_type": hunt_type,
                    "hunt_class": hunt_class,
                    "residency": residency,
                    "points": str(points),
                    "draw_pool": "standard",
                    "public_permits_2025": prior_total,
                    "public_permits_2026": public_quota,
                    "max_point_permits_2025": "",
                    "max_point_permits_2026": max_point_permits,
                    "random_permits_2025": "",
                    "random_permits_2026": random_permits,
                    "guaranteed_at_2025": "" if prior_guaranteed is None else str(prior_guaranteed),
                    "guaranteed_at_2026": "" if forecast_guaranteed is None else str(forecast_guaranteed),
                    "applicants_above": applicants_above,
                    "applicants_at_level": applicants_at_level,
                    "p_preference_draw": "",
                    "p_bonus_pool": f"{p_bonus_pool:.6f}",
                    "p_random_pool": f"{p_random_pool:.6f}",
                    "p_draw": f"{p_draw:.6f}",
                    "p_bonus_pool_pct": f"{p_bonus_pool * 100.0:.3f}",
                    "p_random_pool_pct": f"{p_random_pool * 100.0:.3f}",
                    "p_draw_pct": f"{p_draw * 100.0:.3f}",
                    "random_draw_odds_2026": f"{p_random_pool * 100.0:.3f}",
                    "gap": "" if forecast_guaranteed is None else str(forecast_guaranteed - points),
                    "delta_gap": "" if forecast_guaranteed is None or prior_guaranteed is None else str((forecast_guaranteed - points) - (prior_guaranteed - points)),
                    "status": _status(max_point_permits, random_permits, p_bonus_pool),
                    "trend": _trend(prior_guaranteed, forecast_guaranteed),
                    "draw_outlook": _draw_outlook(p_draw),
                    "source_years_used": ",".join(str(year) for year in available_years),
                    "source_year_count": len(available_years),
                    "latest_source_year": latest_year,
                    "earliest_source_year": available_years[0],
                    "source_dataset": "predictive",
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "turkey_bonus_valid": "TRUE",
                    "turkey_bonus_note": f"Forecasted from {latest_year} limited-entry turkey bonus ladder with Utah split rule.",
                    "weapon": weapon,
                    "draw_system_type": TURKEY_DRAW_SYSTEM_TYPE,
                    "data_quality_flags": "|".join(flags),
                }
                rows.append(row)
                report_counts["modeled"] += 1

    observed_history_rows = [row for row in truth_rows if _is_turkey(row)]
    excluded_general = sum(1 for row in review_rows if _is_turkey(row) and "general season" in _joined_text(row))
    excluded_remaining = sum(1 for row in review_rows if _is_turkey(row) and ("remaining permit" in _joined_text(row) or "remaining" in _joined_text(row)))
    excluded_non_public = sum(1 for row in review_rows if _is_turkey(row) and ("private land" in _joined_text(row) or "private" in _joined_text(row)))
    excluded_other = sum(1 for row in review_rows if _is_turkey(row) and any(token in _joined_text(row) for token in ("sportsman", "conservation", "expo")))
    unsupported_or_ambiguous = sum(
        1
        for row in review_rows
        if _is_turkey(row)
        and not _is_modeled_turkey_db_row(row)
        and "general season" not in _joined_text(row)
        and "remaining permit" not in _joined_text(row)
        and "remaining" not in _joined_text(row)
        and "private land" not in _joined_text(row)
        and "private" not in _joined_text(row)
        and not any(token in _joined_text(row) for token in ("sportsman", "conservation", "expo"))
    )

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "turkey_rows_seen_observed_history": len(observed_history_rows),
        "turkey_rows_seen_active_predictive": len(rows),
        "turkey_rows_seen_total": len(observed_history_rows) + len(rows),
        "turkey_rows_forecast_eligible": len(rows),
        "bonus_turkey_rows_active_predictive": len(rows),
        "bonus_turkey_modeled_rows": report_counts["modeled"],
        "bonus_turkey_pending_rows": report_counts["pending"],
        "bonus_turkey_modeled_hunt_codes": len({str(row.get("hunt_code", "")).strip() for row in rows if str(row.get("turkey_bonus_valid", "")).strip() == "TRUE"}),
        "general_season_turkey_excluded_rows": excluded_general,
        "remaining_turkey_excluded_or_availability_rows": excluded_remaining,
        "non_public_turkey_excluded_rows": excluded_non_public,
        "unsupported_or_ambiguous_turkey_rows": unsupported_or_ambiguous + excluded_other,
        "other_non_draw_turkey_rows": excluded_other,
        "source_years_used_non_null_count": sum(1 for row in rows if _clean(row.get("source_years_used"))),
        "data_quality_flags_summary": dict(data_quality_counter),
    }
    return rows, report
