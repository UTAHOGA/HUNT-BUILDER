"""Phase 6 bonus-family predictive helpers for antlerless moose and ewe bighorn.

CWMU rows are retained in database/permit reconciliation surfaces, but they do
not feed public draw-odds materialization.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.monte_carlo import combine_probabilities, compute_bonus_pool_probability
from engine.utah_bonus_predictive.rules import MODEL_VERSION
from engine.utah_bonus_predictive.split import split_utah_bonus_permits


MODEL_STRATEGY_NAME = "bonus_special_phase6"
BONUS_RULE_VERSION = "utah_bonus_special_v1.0.0"
PHASE6_DRAW_SYSTEM_TYPES = {"BONUS_CWMU_BIG_GAME", "BONUS_ANTLERLESS_MOOSE", "BONUS_EWE_BIGHORN"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _to_int(value: object) -> int:
    text = _clean(value)
    if not text:
        return 0
    text = text.replace(",", "")
    try:
        return int(float(text))
    except Exception:
        matches = re.findall(r"-?\d+(?:\.\d+)?", text)
        if not matches:
            return 0
        try:
            return int(float(matches[-1]))
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
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool")
    )


def _is_antlerless_moose(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    if "cwmu" in text or _clean_lower(row.get("hunt_type")) == "cwmu":
        return False
    return "moose" in text and ("antlerless" in text or _clean_lower(row.get("sex_type")) in {"antlerless", "cow", "cow only"})


def _is_ewe_bighorn(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    if "cwmu" in text or _clean_lower(row.get("hunt_type")) == "cwmu":
        return False
    return "bighorn" in text and ("ewe" in text or _clean_lower(row.get("sex_type")) == "ewe")


def _is_cwmu_public(row: Mapping[str, object]) -> bool:
    return False
    text = _joined_text(row)
    if "cwmu" not in text:
        return False
    if "turkey" in text:
        return False
    if _is_antlerless_moose(row) or _is_ewe_bighorn(row):
        return False
    if any(token in text for token in ("private", "landowner", "voucher", "conservation", "expo", "sportsman", "remaining permit", "over the counter", " otc", "youth")):
        return False
    hunt_type = _clean_lower(row.get("hunt_type"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    return hunt_type == "cwmu" and not any(token in hunt_class for token in ("private", "landowner", "voucher", "conservation", "expo", "sportsman")) and draw_pool in {"", "standard"}


def _classify_phase6_family(row: Mapping[str, object]) -> str | None:
    if _is_antlerless_moose(row):
        return "BONUS_ANTLERLESS_MOOSE"
    if _is_ewe_bighorn(row):
        return "BONUS_EWE_BIGHORN"
    if _is_cwmu_public(row):
        return "BONUS_CWMU_BIG_GAME"
    return None


def is_modeled_phase6_bonus_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean_lower(row.get("bonus_special_valid")) in {"1", "true", "yes", "y"}
        and _clean(row.get("draw_system_type")) in PHASE6_DRAW_SYSTEM_TYPES
    )


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[str, int, str, str], dict[int, dict[str, int]]],
    dict[str, dict[str, str]],
    dict[tuple[str, int], dict[str, int]],
    dict[str, int],
]:
    ladders: dict[tuple[str, int, str, str], dict[int, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0})
    )
    meta: dict[str, dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    private_cwmu_counter = 0

    for row in truth_rows:
        year = _to_int(row.get("year"))
        if year not in history_years:
            continue
        text = _joined_text(row)
        if "cwmu" in text and any(token in text for token in ("private", "landowner", "voucher")):
            private_cwmu_counter += 1

        draw_system_type = _classify_phase6_family(row)
        if not draw_system_type:
            continue
        if _clean_lower(row.get("draw_pool")) not in {"", "standard"}:
            continue

        hunt_code = _clean(row.get("hunt_code")).upper()
        residency = _clean(row.get("residency")) or "Resident"
        points = _to_int(row.get("points"))
        eligible = _to_int(row.get("eligible_applicants"))
        bonus = _to_int(row.get("bonus_permits"))
        regular = _to_int(row.get("regular_permits"))
        total = _to_int(row.get("total_permits"))

        if not hunt_code:
            continue

        ladders[(draw_system_type, year, hunt_code, residency)][points]["eligible"] += eligible
        ladders[(draw_system_type, year, hunt_code, residency)][points]["bonus"] += bonus
        ladders[(draw_system_type, year, hunt_code, residency)][points]["regular"] += regular
        ladders[(draw_system_type, year, hunt_code, residency)][points]["total"] += total
        total_drawn_by_code_year[(hunt_code, year)][residency] += total

        if hunt_code not in meta:
            meta[hunt_code] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")),
                "weapon": _clean(row.get("weapon")),
                "sex_type": _clean(row.get("sex_type")),
            }

    return ladders, meta, total_drawn_by_code_year, {"private_cwmu_truth_rows": private_cwmu_counter}


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    keys_by_family_code_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, residency in ladders:
        keys_by_family_code_res[(draw_system_type, hunt_code, residency)].append(year)

    for (draw_system_type, hunt_code, residency), years in keys_by_family_code_res.items():
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
    tail_buffer = 4
    forecast: dict[int, int] = {}
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + tail_buffer + 1):
        prior_level = latest_ladder.get(points - 1, {})
        unsuccessful_prior = max(int(prior_level.get("eligible", 0)) - int(prior_level.get("bonus", 0)) - int(prior_level.get("regular", 0)), 0)
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.85)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.08
        forecast[points] = _round_count(retained + switch_proxy)

    # Keep a small zero-applicant tail so blind scoring can compare official
    # point rows that appear one or more levels above the prior-year ladder.
    # These rows do not fabricate probability; they simply keep the key space
    # stable when DWR prints sparse upper point levels.
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


def _draw_outlook(probability: float, gap: int | None, pending: bool = False, excluded: bool = False) -> str:
    if excluded:
        return "NOT A PUBLIC DRAW"
    if pending:
        return "MODEL PENDING"
    if probability >= 0.75:
        return "GREEN LIGHT"
    if probability >= 0.10 or (gap is not None and gap <= 1):
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
    res_specific = _to_int(db_row.get("permits_2026_res"))
    nr_specific = _to_int(db_row.get("permits_2026_nr"))
    total = _to_int(db_row.get("permits_2026_total"))
    if res_specific or nr_specific:
        return res_specific if residency == "Resident" else nr_specific
    observed = total_drawn_by_code_year.get((hunt_code, latest_year), {})
    observed_total = sum(int(value) for value in observed.values())
    if total <= 0:
        return 0
    if observed_total <= 0:
        return total if residency == "Resident" else 0
    resident_drawn = int(observed.get("Resident", 0))
    resident_permits = max(0, min(total, round(total * (resident_drawn / max(observed_total, 1)))))
    return resident_permits if residency == "Resident" else max(0, total - resident_permits)


def _data_quality_flags(total_applicants: int, public_quota: int, max_point_permits: int, available_years: list[int]) -> list[str]:
    flags: list[str] = []
    if len(available_years) < 2:
        flags.append("MISSING_MULTIPLE_YEARS")
    if total_applicants < 5:
        flags.append("LOW_APPLICANT_COUNT")
    if public_quota == 1:
        flags.append("ONE_PERMIT_RANDOM_ONLY")
    if max_point_permits == 0 and public_quota > 0:
        flags.append("NO_MAX_POINT_POOL")
    return flags


def build_phase6_bonus_special_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    truth_rows_list = list(truth_rows)
    history_year_set = set(int(year) for year in history_years)
    latest_source_year = max(history_year_set)
    source_years_used_text = ",".join(str(year) for year in history_years)
    source_year_count = len(history_years)
    earliest_source_year = min(history_years)
    ladders, meta, total_drawn_by_code_year, source_counters = _build_truth_ladders(truth_rows_list, history_year_set)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    rows: list[dict[str, object]] = []
    report_counts = Counter()
    data_quality_counter: Counter[str] = Counter()

    current_candidates = []
    excluded_cwmu_nonpublic = 0
    for row in db_rows:
        draw_system_type = _classify_phase6_family(row)
        text = _joined_text(row)
        if "cwmu" in text and draw_system_type is None and any(token in text for token in ("private", "landowner", "voucher", "conservation", "expo", "sportsman", "remaining permit", "over the counter", " otc")):
            excluded_cwmu_nonpublic += 1
        if draw_system_type and _clean(row.get("hunt_code")):
            current_candidates.append((draw_system_type, row))

    current_rows_by_key = {(draw_system_type, _clean(row.get("hunt_code")).upper()): row for draw_system_type, row in current_candidates}
    years_by_key: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for draw_system_type, year, hunt_code, residency in ladders:
        years_by_key[(draw_system_type, hunt_code, residency)].append(year)

    for (draw_system_type, hunt_code), db_row in sorted(current_rows_by_key.items()):
        hunt_name = _clean(db_row.get("hunt_name")) or meta.get(hunt_code, {}).get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get(hunt_code, {}).get("species", "")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get(hunt_code, {}).get("hunt_type", "")
        weapon = _clean(db_row.get("weapon")) or meta.get(hunt_code, {}).get("weapon", "")
        sex_type = _clean(db_row.get("sex_type")) or meta.get(hunt_code, {}).get("sex_type", "")

        for residency in ("Resident", "Nonresident"):
            available_years = sorted(year for year in set(years_by_key.get((draw_system_type, hunt_code, residency), [])) if year in history_year_set)
            latest_year = available_years[-1] if available_years else latest_source_year
            forecast_quota = _forecast_quota_for_residency(db_row, hunt_code, residency, latest_year, total_drawn_by_code_year)
            latest_ladder = ladders.get((draw_system_type, latest_year, hunt_code, residency), {})
            prior_total = sum(int(values.get("total", 0)) for values in latest_ladder.values())

            if not available_years or forecast_quota <= 0:
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
                    "hunt_class": "CWMU" if draw_system_type == "BONUS_CWMU_BIG_GAME" else _clean(db_row.get("hunt_class")),
                    "residency": residency,
                    "points": "",
                    "draw_pool": "standard",
                    "public_permits_2025": prior_total,
                    "public_permits_2026": forecast_quota,
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
                    "bonus_special_valid": "FALSE",
                    "draw_system_type": draw_system_type,
                    "data_quality_flags": "|".join(flag for flag in ["MISSING_PRIOR_YEAR" if not available_years else "", "MISSING_FORECAST_QUOTA" if forecast_quota <= 0 else ""] if flag),
                }
                rows.append(row)
                report_counts[(draw_system_type, "IN_SCOPE_MODEL_PENDING")] += 1
                continue

            public_quota = forecast_quota
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
                    "hunt_class": "CWMU" if draw_system_type == "BONUS_CWMU_BIG_GAME" else _clean(db_row.get("hunt_class")),
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
                    "latest_source_year": latest_source_year,
                    "earliest_source_year": earliest_source_year,
                    "source_dataset": "predictive",
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "bonus_special_valid": "FALSE",
                    "draw_system_type": draw_system_type,
                    "data_quality_flags": "LOW_APPLICANT_COUNT",
                }
                rows.append(row)
                report_counts[(draw_system_type, "IN_SCOPE_MODEL_PENDING")] += 1
                continue

            prior_guaranteed = _guaranteed_level({points: int(values.get("eligible", 0)) for points, values in latest_ladder.items()}, prior_total)
            forecast_guaranteed = _guaranteed_level(forecast_ladder, public_quota)
            total_applicants = sum(forecast_ladder.values())
            flags = _data_quality_flags(total_applicants, public_quota, max_point_permits, available_years)
            if latest_year != latest_source_year:
                flags.append("MISSING_LATEST_SOURCE_YEAR")
            for flag in flags:
                data_quality_counter[flag] += 1

            for points in sorted(forecast_ladder.keys(), reverse=True):
                applicants_by_points = {int(level): int(count) for level, count in forecast_ladder.items()}
                p_bonus_pool, applicants_above, applicants_at_level = compute_bonus_pool_probability(points, applicants_by_points, max_point_permits)
                p_random_pool = _weighted_random_probability(points, applicants_by_points, random_permits)
                p_draw = combine_probabilities(p_bonus_pool, p_random_pool)
                gap = (forecast_guaranteed - points) if forecast_guaranteed is not None else None
                prior_gap = (prior_guaranteed - points) if prior_guaranteed is not None else None
                delta_gap = None if gap is None or prior_gap is None else gap - prior_gap
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
                    "hunt_class": "CWMU" if draw_system_type == "BONUS_CWMU_BIG_GAME" else _clean(db_row.get("hunt_class")),
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
                    "gap": "" if gap is None else str(gap),
                    "delta_gap": "" if delta_gap is None else str(delta_gap),
                    "status": _status(max_point_permits, random_permits, p_bonus_pool),
                    "trend": _trend(prior_guaranteed, forecast_guaranteed),
                    "draw_outlook": _draw_outlook(p_draw, gap),
                    "source_years_used": ",".join(str(year) for year in available_years),
                    "source_year_count": source_year_count,
                    "latest_source_year": latest_year,
                    "earliest_source_year": earliest_source_year,
                    "source_dataset": "predictive",
                    "model_strategy": MODEL_STRATEGY_NAME,
                    "bonus_special_valid": "TRUE",
                    "bonus_special_note": f"Forecasted from {latest_year} bonus ladder with Utah split rule.",
                    "weapon": weapon,
                    "draw_system_type": draw_system_type,
                    "data_quality_flags": "|".join(flags),
                }
                rows.append(row)
                report_counts[(draw_system_type, "MODELED_BONUS")] += 1

    phase6_rows = [row for row in rows if _clean(row.get("draw_system_type")) in PHASE6_DRAW_SYSTEM_TYPES]
    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_phase6_rows": len(phase6_rows),
        "rows_by_draw_system_type": dict(Counter(_clean(row.get("draw_system_type")) for row in phase6_rows)),
        "rows_by_algorithm_status": dict(Counter("MODELED_BONUS" if _clean(row.get("bonus_special_valid")) == "TRUE" else "IN_SCOPE_MODEL_PENDING" for row in phase6_rows)),
        "cwmu_public_modeled_row_count": report_counts[("BONUS_CWMU_BIG_GAME", "MODELED_BONUS")],
        "cwmu_public_modeled_hunt_code_count": len({row.get("hunt_code") for row in phase6_rows if row.get("draw_system_type") == "BONUS_CWMU_BIG_GAME" and _clean(row.get("bonus_special_valid")) == "TRUE"}),
        "cwmu_pending_row_count": report_counts[("BONUS_CWMU_BIG_GAME", "IN_SCOPE_MODEL_PENDING")],
        "cwmu_private_excluded_row_count": excluded_cwmu_nonpublic + source_counters.get("private_cwmu_truth_rows", 0),
        "antlerless_moose_modeled_row_count": report_counts[("BONUS_ANTLERLESS_MOOSE", "MODELED_BONUS")],
        "antlerless_moose_modeled_hunt_code_count": len({row.get("hunt_code") for row in phase6_rows if row.get("draw_system_type") == "BONUS_ANTLERLESS_MOOSE" and _clean(row.get("bonus_special_valid")) == "TRUE"}),
        "antlerless_moose_pending_row_count": report_counts[("BONUS_ANTLERLESS_MOOSE", "IN_SCOPE_MODEL_PENDING")],
        "ewe_bighorn_modeled_row_count": report_counts[("BONUS_EWE_BIGHORN", "MODELED_BONUS")],
        "ewe_bighorn_modeled_hunt_code_count": len({row.get("hunt_code") for row in phase6_rows if row.get("draw_system_type") == "BONUS_EWE_BIGHORN" and _clean(row.get("bonus_special_valid")) == "TRUE"}),
        "ewe_bighorn_pending_row_count": report_counts[("BONUS_EWE_BIGHORN", "IN_SCOPE_MODEL_PENDING")],
        "p_bonus_pool_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("p_bonus_pool"))),
        "p_random_pool_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("p_random_pool"))),
        "p_draw_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("p_draw"))),
        "p_draw_pct_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("p_draw_pct"))),
        "p_preference_draw_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("p_preference_draw"))),
        "p_draw_outside_0_1_count": sum(1 for row in phase6_rows if _clean(row.get("p_draw")) and not (0.0 <= float(_clean(row.get("p_draw"))) <= 1.0)),
        "p_draw_pct_outside_0_100_count": sum(1 for row in phase6_rows if _clean(row.get("p_draw_pct")) and not (0.0 <= float(_clean(row.get("p_draw_pct"))) <= 100.0)),
        "duplicate_key_count": len([(row.get("hunt_code"), row.get("residency"), row.get("points")) for row in phase6_rows]) - len({(row.get("hunt_code"), row.get("residency"), row.get("points")) for row in phase6_rows}),
        "source_years_used_non_null_count": sum(1 for row in phase6_rows if _clean(row.get("source_years_used"))),
        "data_quality_flags_summary": dict(data_quality_counter),
    }
    return rows, report
