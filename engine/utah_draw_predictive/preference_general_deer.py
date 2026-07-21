"""Preference predictive engine for Utah general-season buck deer."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import (
    ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    ALGORITHM_STATUS_MODELED_PREFERENCE,
    StrategySpec,
    TARGET_SCOPE_TARGET,
    append_reason_codes,
)
from .permit_accessors import target_permit_for_residency, target_permit_total
from .preference_ladder_normalizer import normalize_preference_ladder_rows


MODEL_STRATEGY_NAME = "preference_general_deer"
PREFERENCE_RULE_VERSION = "utah_preference_general_deer_v1.0.0"
PREFERENCE_TAIL_FLOOR = 0.001
PREFERENCE_TAIL_CEILING = 0.995
# Keep this at zero unless a future source-backed model change proves a
# probability lift improves MAE. A broad +0.35 lift overpredicted this family.
PREFERENCE_REPO_HOLDOUT_BIAS_CORRECTION = 0.0
TAIL_CALIBRATION_REASON = "PREFERENCE_TAIL_CALIBRATED_FROM_REPO_BACKTEST"


STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type="PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        module_name="engine.utah_draw_predictive.preference_general_deer",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="General-season buck deer uses a preference-point model and only promotes rows with valid source history, quota, and modeled preference probabilities.",
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


def _effective_draw_pool(row: Mapping[str, object]) -> str:
    return "adult_general_deer"


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


def _skipped_no_history_row(forecast_year: int) -> dict[str, object]:
    return {
        "family": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "forecast_year": str(forecast_year),
        "year": str(forecast_year),
        "status": "SKIPPED_NO_HISTORY",
        "blocker": "true",
        "production_ready": "false",
        "calibration_ready": "false",
        "model_strategy": MODEL_STRATEGY_NAME,
        "preference_model_valid": "FALSE",
        "reason_codes": "SKIPPED_NO_HISTORY",
        "preference_model_note": "No source history rows were available for preference general deer; no probability rows were fabricated.",
    }


def _to_float(value: object) -> float:
    text = _clean(value)
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def _to_float_optional(value: object) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


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


def _looks_like_general_buck_deer(row: Mapping[str, object]) -> bool:
    draw_system_type = _clean_lower(row.get("draw_system_type"))
    if draw_system_type in {"availability_only", "reference_only", "guaranteed_lifetime_permit"}:
        return False

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
    if "deer" not in text or "buck" not in text:
        return False
    if "general season" not in text and "management buck deer" not in text and "cactus buck" not in text:
        return False
    if any(token in text for token in ("dedicated hunter", "lifetime", "cwmu", "private land only", "private", "tribal")):
        return False
    if "youth" in text:
        return False
    return True


def _is_youth_general_deer_preference(row: Mapping[str, object]) -> bool:
    hunt_class = _clean_lower(row.get("hunt_class"))
    hunt_draw_class = _clean_lower(row.get("hunt_draw_class") or row.get("draw_class_type"))
    draw_system_type = _clean_lower(row.get("draw_system_type") or row.get("draw_design"))
    return (
        ("youth_general_deer" in hunt_class or "youth_general_deer" in hunt_draw_class)
        and draw_system_type == "preference_general_season_buck_deer"
    )


def _looks_like_standard_pool(row: Mapping[str, object]) -> bool:
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    hunt_draw_class = _clean_lower(row.get("hunt_draw_class") or row.get("draw_class_type"))
    if draw_pool not in {"", "standard", "adult_general_deer", "preference_general_season_buck_deer"}:
        return False
    if hunt_class in {"", "public", "general season"}:
        return True
    # General-season buck deer rows are often stored with schema labels such as
    # "Preference" or "GENERAL_SEASON_DEER" in the source tables. Keep those
    # rows eligible for this lane so the engine can forecast the full family.
    if "preference" in hunt_class:
        return True
    if "general season" in hunt_class or "general_season" in hunt_class:
        return True
    if "general season" in hunt_draw_class or "general_season" in hunt_draw_class:
        return True
    return False


def is_modeled_general_deer_row(row: Mapping[str, object]) -> bool:
    strategy_ok = _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME and _clean_lower(row.get("preference_model_valid")) in {
        "1",
        "true",
        "yes",
        "y",
    }
    if strategy_ok:
        return True

    # Phase bridge: some already-modeled preference rows are emitted from the
    # mixed runtime path without the dedicated strategy tag. Promote those rows
    # when a valid preference probability surface is present.
    p_draw_mean = _to_float_optional(row.get("p_draw_mean"))
    p_draw = _to_float_optional(row.get("p_draw"))
    p_draw_pct = _to_float_optional(row.get("p_draw_pct"))
    p_pref = _to_float_optional(row.get("p_preference_draw"))

    has_valid_probability = any(
        value is not None and 0.0 <= value <= 1.0
        for value in (p_draw_mean, p_draw, p_pref)
    ) or (p_draw_pct is not None and 0.0 <= p_draw_pct <= 100.0)
    if not has_valid_probability:
        return False

    # Require predictive evidence context so placeholders do not promote.
    source_years_used = _clean(row.get("source_years_used"))
    reason_codes = _clean_lower(row.get("reason_codes"))
    has_predictive_evidence = bool(source_years_used) and (
        "appliant_stack_rolled_forward" in reason_codes
        or "applicant_stack_rolled_forward" in reason_codes
        or "bonus_rule_simulated" in reason_codes
        or _clean_lower(row.get("source_dataset")) == "predictive"
    )
    return has_predictive_evidence


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[int, str, str, str], dict[int, dict[str, int]]],
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str, int], dict[str, int]],
]:
    ladders: dict[tuple[int, str, str, str], dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"eligible": 0, "drawn": 0}))
    meta: dict[tuple[str, str], dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in normalize_preference_ladder_rows(truth_rows):
        year = _to_int(row.get("year"))
        if year not in history_years:
            continue
        if not _looks_like_general_buck_deer(row) or not _looks_like_standard_pool(row):
            continue

        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _residency_lane(row)
        points = _to_int(row.get("points"))
        eligible = _to_int(row.get("eligible_applicants"))
        drawn = _to_int(row.get("drawn")) or _to_int(row.get("successful_applicants")) or _to_int(row.get("total_permits")) or _to_int(row.get("preference_permits"))

        if not hunt_code:
            continue
        draw_pool = _effective_draw_pool(row)

        ladders[(year, hunt_code, draw_pool, residency)][points]["eligible"] += eligible
        ladders[(year, hunt_code, draw_pool, residency)][points]["drawn"] += drawn
        total_drawn_by_code_year[(hunt_code, draw_pool, year)][residency] += drawn

        if (hunt_code, draw_pool) not in meta:
            meta[(hunt_code, draw_pool)] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")) or "General Season",
                "hunt_class": _clean(row.get("hunt_class")) or "Public",
                "draw_pool": draw_pool,
                "weapon": _clean(row.get("weapon")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[int, str, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    keys_by_code_pool_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for year, hunt_code, draw_pool, residency in ladders:
        keys_by_code_pool_res[(hunt_code, draw_pool, residency)].append(year)

    for (hunt_code, draw_pool, residency), years in keys_by_code_pool_res.items():
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(prior_year, hunt_code, draw_pool, residency)]
            nxt = ladders[(next_year, hunt_code, draw_pool, residency)]
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
        "0": 0.78,
        "1": 0.82,
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


def _calibrate_tail_probability(probability: float) -> tuple[float, bool]:
    calibrated = False
    if probability >= 1.0:
        base_probability = 1.0
        calibrated = True
    elif probability <= 0.0:
        base_probability = PREFERENCE_TAIL_FLOOR
        calibrated = True
    else:
        base_probability = probability

    adjusted = min(PREFERENCE_TAIL_CEILING, base_probability + PREFERENCE_REPO_HOLDOUT_BIAS_CORRECTION)
    if abs(adjusted - probability) > 0.000001:
        calibrated = True
    return adjusted, calibrated


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
    draw_pool: str,
    residency: str,
    forecast_total: int,
    latest_year: int,
    total_drawn_by_code_year: Mapping[tuple[str, str, int], dict[str, int]],
) -> int:
    if residency == "All":
        return forecast_total
    observed = total_drawn_by_code_year.get((hunt_code, draw_pool, latest_year), {})
    res_total = sum(int(value) for value in observed.values())
    if forecast_total <= 0:
        return 0
    if res_total <= 0:
        return forecast_total if residency == "Resident" else 0
    resident_drawn = int(observed.get("Resident", 0))
    nonresident_drawn = int(observed.get("Nonresident", 0))
    if residency == "Resident":
        return max(0, min(forecast_total, round(forecast_total * (resident_drawn / max(res_total, 1)))))
    resident_quota = max(0, min(forecast_total, round(forecast_total * (resident_drawn / max(res_total, 1)))))
    return max(0, forecast_total - resident_quota)


def _explicit_quota_for_residency(
    row: Mapping[str, object],
    residency: str,
    forecast_year: int,
    source_year: int | None = None,
) -> int | None:
    if residency == "All":
        permit = target_permit_total(row, forecast_year, source_year=source_year)
        return permit.value if permit.value > 0 else None
    permit = target_permit_for_residency(row, forecast_year, residency, source_year=source_year)
    return permit.value if permit.value > 0 else None


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
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.85)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.10
        forecast[points] = _round_count(retained + switch_proxy)

    # Preserve a small zero-applicant tail so sparse official upper point rows
    # remain joinable in blind scoring without using forecast-year results.
    return forecast


def _structural_point_levels(latest_ladder: Mapping[int, dict[str, int]]) -> list[int]:
    """Return official point levels from the source table, including zero rows."""
    return sorted({int(points) for points in latest_ladder.keys()})


def build_preference_general_deer_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> list[dict[str, object]]:
    truth_rows_list = list(truth_rows)
    history_year_set = _history_year_set_or_bootstrap(history_years, truth_rows_list)
    if not history_year_set:
        return [_skipped_no_history_row(forecast_year)]
    latest_source_year = max(history_year_set)
    ladders, truth_meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows_list, history_year_set)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    rows: list[dict[str, object]] = []
    current_general_rows = [
        row for row in db_rows
        if _looks_like_general_buck_deer(row)
        and _looks_like_standard_pool(row)
        and _clean(row.get("hunt_code"))
    ]
    current_codes = {
        (_clean(row.get("hunt_code")).upper(), _effective_draw_pool(row)): row
        for row in current_general_rows
    }

    years_by_key: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for year, hunt_code, draw_pool, residency in ladders:
        years_by_key[(hunt_code, draw_pool, residency)].append(year)
    max_points_by_residency: dict[str, int] = defaultdict(int)
    for (year, _hunt_code, _draw_pool, residency), ladder in ladders.items():
        if year == latest_source_year and ladder:
            max_points_by_residency[residency] = max(
                max_points_by_residency[residency],
                max(int(points) for points in ladder.keys()),
            )

    for (hunt_code, draw_pool), db_row in sorted(current_codes.items()):
        forecast_total = target_permit_total(db_row, forecast_year, source_year=latest_source_year).value
        if forecast_total <= 0:
            continue
        published_res = _clean(db_row.get(f"permits_{forecast_year}_res"))
        published_nr = _clean(db_row.get(f"permits_{forecast_year}_nr"))
        published_total = _clean(db_row.get(f"permits_{forecast_year}_total"))
        total_only_quota = bool(published_total) and not published_res and not published_nr
        total_only_reason = "NO_RESIDENCY_LANE_QUOTA|TOTAL_ONLY_QUOTA_RATIO_SKIPPED_NO_RESIDENCY_SPLIT"

        meta = truth_meta.get((hunt_code, draw_pool), {}) or truth_meta.get((hunt_code, "standard"), {})
        hunt_name = _clean(db_row.get("hunt_name")) or meta.get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get("species", "Deer")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get("hunt_type", "General Season")
        hunt_class = _clean(db_row.get("hunt_class")) or meta.get("hunt_class", "Public")
        weapon = _clean(db_row.get("weapon")) or meta.get("weapon", "")

        available_residencies = sorted(
            residency
            for code, pool, residency in years_by_key
            if code == hunt_code and pool == draw_pool
        )
        if "All" in available_residencies:
            residencies_to_model = ["All"]
        else:
            residencies_to_model = available_residencies or ["Resident", "Nonresident"]

        for residency in residencies_to_model:
            available_years = sorted(year for year in set(years_by_key.get((hunt_code, draw_pool, residency), [])) if year in history_year_set)
            explicit_quota = _explicit_quota_for_residency(db_row, residency, forecast_year, source_year=latest_source_year)
            if not available_years:
                if residency == "Nonresident" and explicit_quota is None:
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
                            "residency": _output_residency(residency),
                            "points": "0",
                            "draw_pool": draw_pool,
                            "public_permits_2025": 0,
                            "public_permits_2026": "" if total_only_quota else 0,
                            "permits_2026_res": "" if total_only_quota else published_res,
                            "permits_2026_nr": "" if total_only_quota else published_nr,
                            "permits_2026_total": published_total,
                            "max_point_permits_2025": "",
                            "max_point_permits_2026": "",
                            "random_permits_2025": "",
                            "random_permits_2026": "",
                            "guaranteed_at_2025": "",
                            "guaranteed_at_2026": "",
                            "applicants_above": 0,
                            "applicants_at_level": 0,
                            "probability_applicant_count": 1,
                            "p_preference_draw": "0.000000",
                            "p_bonus_pool": "",
                            "p_random_pool": "",
                            "p_draw": "0.000000",
                            "p_bonus_pool_pct": "",
                            "p_random_pool_pct": "",
                            "p_draw_pct": "0.000",
                            "random_draw_odds_2026": "",
                            "gap": "",
                            "delta_gap": "",
                            "status": _status(0.0),
                            "trend": "YELLOW",
                            "draw_outlook": _draw_outlook(0.0, None),
                            "source_years_used": "current_quota_seed",
                            "source_year_count": 0,
                            "latest_source_year": "",
                            "earliest_source_year": "",
                            "source_dataset": "predictive",
                            "model_strategy": MODEL_STRATEGY_NAME,
                            "preference_model_valid": "TRUE",
                            "preference_model_note": "Structural nonresident point-0 row emitted for a total-only preference hunt with no blind-history nonresident ladder; probability remains zero until source history or explicit quota exists.",
                            "reason_codes": (
                                "NO_NONRESIDENT_HISTORY_TOTAL_ONLY_STRUCTURAL_ROW|NO_EXPLICIT_NONRESIDENT_QUOTA"
                                + (f"|{total_only_reason}" if total_only_quota else "")
                            ),
                            "weapon": weapon,
                            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                        }
                    )
                continue
            code_latest_source_year = max(available_years)

            latest_ladder = ladders.get((code_latest_source_year, hunt_code, draw_pool, residency), {})
            prior_total = sum(int(values["drawn"]) for values in latest_ladder.values())
            forecast_quota = (
                explicit_quota
                if explicit_quota is not None
                else _forecast_quota_for_residency(hunt_code, draw_pool, residency, forecast_total, code_latest_source_year, total_drawn_by_code_year)
            )
            if forecast_quota <= 0:
                if residency == "Nonresident":
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
                            "residency": _output_residency(residency),
                            "points": "0",
                            "draw_pool": draw_pool,
                            "public_permits_2025": prior_total,
                            "public_permits_2026": "" if total_only_quota else 0,
                            "permits_2026_res": "" if total_only_quota else published_res,
                            "permits_2026_nr": "" if total_only_quota else published_nr,
                            "permits_2026_total": published_total,
                            "max_point_permits_2025": "",
                            "max_point_permits_2026": "",
                            "random_permits_2025": "",
                            "random_permits_2026": "",
                            "guaranteed_at_2025": "",
                            "guaranteed_at_2026": "",
                            "applicants_above": 0,
                            "applicants_at_level": 0,
                            "probability_applicant_count": 1,
                            "p_preference_draw": "0.000000",
                            "p_bonus_pool": "",
                            "p_random_pool": "",
                            "p_draw": "0.000000",
                            "p_bonus_pool_pct": "",
                            "p_random_pool_pct": "",
                            "p_draw_pct": "0.000",
                            "random_draw_odds_2026": "",
                            "gap": "",
                            "delta_gap": "",
                            "status": _status(0.0),
                            "trend": "YELLOW",
                            "draw_outlook": _draw_outlook(0.0, None),
                            "source_years_used": ",".join(str(year) for year in available_years),
                            "source_year_count": len(available_years),
                            "latest_source_year": code_latest_source_year,
                            "earliest_source_year": min(available_years),
                            "source_dataset": "predictive",
                            "model_strategy": MODEL_STRATEGY_NAME,
                            "preference_model_valid": "TRUE",
                            "preference_model_note": "Structural nonresident point-0 row emitted because blind-history quota inference produced zero nonresident permits for this total-only preference hunt.",
                            "reason_codes": (
                                "ZERO_INFERRED_NONRESIDENT_QUOTA_STRUCTURAL_ROW|NO_EXPLICIT_NONRESIDENT_QUOTA"
                                + (f"|{total_only_reason}" if total_only_quota else "")
                            ),
                            "weapon": weapon,
                            "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
                        }
                    )
                continue

            forecast_ladder = (
                _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
                if latest_ladder
                else {}
            )
            global_max_points = max_points_by_residency.get(residency, 0)
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
            points_desc = sorted(set(forecast_ladder) | set(structural_points), reverse=True)
            for points in points_desc:
                forecast_applicants_at_level = int(forecast_ladder.get(points, 0))
                is_structural_zero_point = forecast_applicants_at_level <= 0 and points in structural_points
                if forecast_applicants_at_level <= 0 and not is_structural_zero_point:
                    continue
                applicants_at_level = forecast_applicants_at_level
                applicants_above = running_above
                probability_applicant_count = max(forecast_applicants_at_level, 1)
                raw_probability = _preference_probability(forecast_quota, applicants_above, probability_applicant_count)
                probability, tail_calibrated = _calibrate_tail_probability(raw_probability)
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
                        "residency": _output_residency(residency),
                        "points": str(points),
                        "draw_pool": draw_pool,
                        "public_permits_2025": prior_total,
                        "public_permits_2026": "" if total_only_quota else forecast_quota,
                        "permits_2026_res": "" if total_only_quota else published_res,
                        "permits_2026_nr": "" if total_only_quota else published_nr,
                        "permits_2026_total": published_total,
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
                        "source_years_used": ",".join(str(year) for year in available_years) if available_years else "current_quota_seed",
                        "source_year_count": len(available_years),
                        "latest_source_year": code_latest_source_year,
                        "earliest_source_year": min(available_years) if available_years else "",
                        "source_dataset": "predictive",
                        "model_strategy": MODEL_STRATEGY_NAME,
                        "preference_model_valid": "TRUE",
                        "preference_model_note": (
                            f"Forecasted from {code_latest_source_year} standard-pool ladder with residency quota split and preference carry-forward."
                            if available_years
                            else "Seeded from explicit current-year nonresident quota where no prior nonresident ladder exists."
                        ),
                        "reason_codes": append_reason_codes(
                            total_only_reason if total_only_quota else "",
                            TAIL_CALIBRATION_REASON if tail_calibrated else "",
                        ),
                        "weapon": weapon,
                    }
                )
                if forecast_applicants_at_level > 0:
                    running_above += forecast_applicants_at_level

    return rows


def pending_general_deer_row(reason: str | None = None) -> dict[str, object]:
    return {
        "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "algorithm_status": ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "reason": reason or "General-season buck deer is in scope but missing valid source data, quota, or modeled preference probability.",
    }
