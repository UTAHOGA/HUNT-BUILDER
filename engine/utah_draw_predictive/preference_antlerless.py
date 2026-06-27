"""Preference predictive engine for Utah antlerless deer, antlerless elk, and doe pronghorn."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING, ALGORITHM_STATUS_MODELED_PREFERENCE, StrategySpec, TARGET_SCOPE_TARGET


MODEL_STRATEGY_NAME = "preference_antlerless"
PREFERENCE_RULE_VERSION = "utah_preference_antlerless_v1.0.0"


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


def _target_draw_system_type(row: Mapping[str, object]) -> str | None:
    text = " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool")
    )
    if any(token in text for token in ("youth", "cwmu", "dedicated hunter", "private land", "landowner", "conservation", "control", "mitigation", "depredation", "sportsman", "expo")):
        return None
    if "pronghorn" in text and ("doe" in text or _clean_lower(row.get("sex_type")) == "doe"):
        return "PREFERENCE_DOE_PRONGHORN"
    if "deer" in text and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "doe"}):
        return "PREFERENCE_ANTLERLESS_DEER"
    if "elk" in text and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "cow", "cow only"}):
        return "PREFERENCE_ANTLERLESS_ELK"
    return None


def _looks_like_standard_pool(row: Mapping[str, object]) -> bool:
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    return draw_pool in {"", "standard"} and hunt_class in {"", "public"}


def is_modeled_antlerless_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean_lower(row.get("preference_model_valid")) in {"1", "true", "yes", "y"}
    )


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[str, int, str, str], dict[int, dict[str, int]]],
    dict[str, dict[str, str]],
    dict[tuple[str, int], dict[str, int]],
]:
    ladders: dict[tuple[str, int, str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"eligible": 0, "drawn": 0}))
    meta: dict[str, dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in truth_rows:
        year = _to_int(row.get("year"))
        if year not in history_years:
            continue
        draw_system_type = _target_draw_system_type(row)
        if not draw_system_type or not _looks_like_standard_pool(row):
            continue

        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _clean(row.get("residency")) or "Resident"
        points = _to_int(row.get("points"))
        eligible = _to_int(row.get("eligible_applicants"))
        drawn = _to_int(row.get("total_permits")) or _to_int(row.get("preference_permits"))

        if not hunt_code:
            continue

        ladders[(draw_system_type, year, hunt_code, residency)][points]["eligible"] += eligible
        ladders[(draw_system_type, year, hunt_code, residency)][points]["drawn"] += drawn
        total_drawn_by_code_year[(hunt_code, year)][residency] += drawn

        if hunt_code not in meta:
            meta[hunt_code] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")) or "General Season",
                "weapon": _clean(row.get("weapon")),
                "sex_type": _clean(row.get("sex_type")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    keys_by_type_code_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, residency in ladders:
        keys_by_type_code_res[(draw_system_type, hunt_code, residency)].append(year)

    for key, years in keys_by_type_code_res.items():
        draw_system_type, hunt_code, residency = key
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(draw_system_type, prior_year, hunt_code, residency)]
            nxt = ladders[(draw_system_type, next_year, hunt_code, residency)]
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
        "0": 0.76,
        "1": 0.81,
        "2_3": 0.86,
        "4_5": 0.90,
        "6_9": 0.94,
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
    hunt_code: str,
    residency: str,
    forecast_total: int,
    latest_year: int,
    total_drawn_by_code_year: Mapping[tuple[str, int], dict[str, int]],
) -> int:
    observed = total_drawn_by_code_year.get((hunt_code, latest_year), {})
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
    tail_buffer = 6
    forecast: dict[int, int] = {}
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + tail_buffer + 1):
        unsuccessful_prior = max(
            int(latest_ladder.get(points - 1, {}).get("eligible", 0)) - int(latest_ladder.get(points - 1, {}).get("drawn", 0)),
            0,
        )
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.84)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.08
        forecast[points] = _round_count(retained + switch_proxy)

    return forecast


def _structural_point_levels(latest_ladder: Mapping[int, dict[str, int]]) -> list[int]:
    """Return official point levels from the source table, including zero rows."""
    return sorted({int(points) for points in latest_ladder.keys()})


def build_preference_antlerless_predictions(
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
    current_target_rows = []
    for row in db_rows:
        draw_system_type = _target_draw_system_type(row)
        if draw_system_type and _looks_like_standard_pool(row) and _clean(row.get("hunt_code")):
            current_target_rows.append((draw_system_type, row))
    current_codes = {(draw_system_type, _clean(row.get("hunt_code")).upper()): row for draw_system_type, row in current_target_rows}

    years_by_key: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, residency in ladders:
        years_by_key[(draw_system_type, hunt_code, residency)].append(year)
    max_points_by_type_residency: dict[tuple[str, str], int] = defaultdict(int)
    for (draw_system_type, year, _hunt_code, residency), ladder in ladders.items():
        if year == latest_source_year and ladder:
            max_points_by_type_residency[(draw_system_type, residency)] = max(
                max_points_by_type_residency[(draw_system_type, residency)],
                max(int(points) for points in ladder.keys()),
            )

    for (draw_system_type, hunt_code), db_row in sorted(current_codes.items()):
        forecast_total = _to_int(db_row.get("permits_2026_total"))
        if forecast_total <= 0:
            continue

        hunt_name = _clean(db_row.get("hunt_name")) or truth_meta.get(hunt_code, {}).get("hunt_name", "")
        species = _clean(db_row.get("species")) or truth_meta.get(hunt_code, {}).get("species", "")
        hunt_type = _clean(db_row.get("hunt_type")) or truth_meta.get(hunt_code, {}).get("hunt_type", "General Season")
        weapon = _clean(db_row.get("weapon")) or truth_meta.get(hunt_code, {}).get("weapon", "")
        sex_type = _clean(db_row.get("sex_type")) or truth_meta.get(hunt_code, {}).get("sex_type", "")

        for residency in ("Resident", "Nonresident"):
            available_years = sorted(year for year in set(years_by_key.get((draw_system_type, hunt_code, residency), [])) if year in history_year_set)
            if latest_source_year not in available_years or len(available_years) < 2:
                continue

            latest_ladder = ladders[(draw_system_type, latest_source_year, hunt_code, residency)]
            prior_total = sum(int(values["drawn"]) for values in latest_ladder.values())
            forecast_quota = _forecast_quota_for_residency(hunt_code, residency, forecast_total, latest_source_year, total_drawn_by_code_year)
            if forecast_quota <= 0:
                continue

            forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
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
                applicants_at_level = forecast_applicants_at_level if forecast_applicants_at_level > 0 else 1
                applicants_above = running_above
                probability = _preference_probability(forecast_quota, applicants_above, applicants_at_level)
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
                        "hunt_class": "Public",
                        "residency": residency,
                        "points": str(points),
                        "draw_pool": "standard",
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
                        "model_strategy": MODEL_STRATEGY_NAME,
                        "preference_model_valid": "TRUE",
                        "preference_model_note": f"Forecasted from {latest_source_year} standard-pool ladder with residency quota split and preference carry-forward.",
                        "weapon": weapon,
                        "draw_system_type": draw_system_type,
                    }
                )
                if forecast_applicants_at_level > 0:
                    running_above += forecast_applicants_at_level

    return rows


def pending_antlerless_row(draw_system_type: str, reason: str | None = None) -> dict[str, object]:
    return {
        "draw_system_type": draw_system_type,
        "algorithm_status": ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "reason": reason or "Antlerless preference category is in scope but missing valid source data, quota, or modeled preference probability.",
    }
