"""Deterministic Utah draw simulator."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import asdict
from statistics import mean
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

from .constants import DEFAULT_PREDICTION_YEAR, MODEL_VERSION, RULE_VERSION
from .models import Application, ApplicationUnit, DrawResult, DrawState, DrawSystem, Hunt, PredictionAggregate, Quota, SimulationResult, UtahRuleConfig, normalize_residency
from .rules import can_group_fit_quota, derive_quota, get_draw_order


def _bucket_key(unit: ApplicationUnit, hunt_code: str) -> tuple[str, str, int]:
    return hunt_code, unit.residency, int(unit.effective_points)


def _group_units_by_bucket(units: Sequence[ApplicationUnit]) -> Dict[tuple[str, str, int], List[ApplicationUnit]]:
    buckets: Dict[tuple[str, str, int], List[ApplicationUnit]] = defaultdict(list)
    for unit in units:
        if not unit.valid_flag or not unit.eligible_flag:
            continue
        if not unit.hunt_choices:
            continue
        hunt_code = unit.hunt_choices[0]
        buckets[_bucket_key(unit, hunt_code)].append(unit)
    return buckets


def _select_choice(unit: ApplicationUnit, remaining_by_hunt: MutableMapping[str, int]) -> tuple[str | None, int | None]:
    for idx, choice in enumerate(unit.hunt_choices, start=1):
        remaining = int(remaining_by_hunt.get(choice, 0))
        if remaining >= unit.group_size:
            return choice, idx
    return None, None


def _tickets_for_unit(unit: ApplicationUnit, config: UtahRuleConfig) -> int:
    if unit.point_type == DrawSystem.BONUS:
        return max(1, 1 + int(unit.effective_points))
    return 1


def _weighted_draw(pool: Sequence[ApplicationUnit], rng: random.Random) -> ApplicationUnit | None:
    if not pool:
        return None
    weights = [_tickets_for_unit(unit, UtahRuleConfig.default()) for unit in pool]
    total = sum(weights)
    if total <= 0:
        return None
    choice = rng.uniform(0, total)
    upto = 0.0
    for unit, weight in zip(pool, weights):
        upto += weight
        if choice <= upto:
            return unit
    return pool[-1]


def _init_residency_buckets(quota: Quota) -> tuple[bool, dict[str, int], int]:
    separate = quota.resident_quota is not None or quota.nonresident_quota is not None
    buckets = {
        "Resident": max(int(quota.resident_quota or 0), 0),
        "Nonresident": max(int(quota.nonresident_quota or 0), 0),
    }
    total = max(int(quota.total_public_permits), 0)
    return separate, buckets, total


def _bonus_lane_round_quota(
    residency: str,
    permits: int,
    config: UtahRuleConfig,
) -> tuple[int, int]:
    """Return the max-point and random allotment for one residency lane.

    Utah's 50/50 bonus split is applied within each official residency lane,
    not across the combined hunt total.  The documented exception is a
    one-permit nonresident lane, which is issued in the random phase.
    """
    permits = max(int(permits), 0)
    residency = normalize_residency(residency)
    if residency == "Nonresident" and permits == 1:
        return 0, 1
    reserved = int(permits * config.bonus_reserved_fraction)
    if config.bonus_reserved_fraction == 0.5 and permits % 2:
        reserved += 1
    return reserved, max(permits - reserved, 0)


def _bonus_crossover_is_allowed(draw_state: DrawState, quota: Quota) -> bool:
    """Limit crossover to the exact limited-entry programs named by DWR."""
    species = str(draw_state.hunt.species or quota.species or "").strip().lower()
    eligible_species = any(name in species for name in ("deer", "elk", "pronghorn"))
    return bool(
        quota.crossover_allowed
        and draw_state.rule_config.resident_nonresident_crossover_enabled_when_allowed
        and draw_state.hunt.hunt_type == "limited_entry"
        and eligible_species
    )


def _consume_residency_quota(
    unit: ApplicationUnit,
    separate_residency: bool,
    residency_buckets: MutableMapping[str, int],
    total_remaining: dict[str, int],
    target_residency: str | None = None,
) -> str | None:
    if not separate_residency:
        if total_remaining["value"] < unit.group_size:
            return None
        total_remaining["value"] -= unit.group_size
        return "total"

    residency_key = normalize_residency(target_residency or unit.residency)
    if residency_buckets.get(residency_key, 0) >= unit.group_size:
        residency_buckets[residency_key] -= unit.group_size
        total_remaining["value"] -= unit.group_size
        return residency_key
    return None


def build_application_units(applications: Sequence[Application]) -> List[ApplicationUnit]:
    units: List[ApplicationUnit] = []
    for application in applications:
        units.append(
            ApplicationUnit(
                application_unit_id=application.application_id,
                member_application_ids=(application.application_id,),
                member_customer_ids_hashed=(application.hashed_customer_id,),
                group_id=application.group_id,
                group_size=1,
                residency=application.residency,
                species=application.species,
                hunt_choices=tuple(application.normalized_choices()),
                effective_points=max(int(application.points_before_draw), 0),
                point_type=application.point_type,
                youth_only_flag=bool(application.youth_flag),
                valid_flag=bool(application.valid_flag),
                eligible_flag=bool(application.eligible_flag),
                random_ticket_count=1 if application.point_type != DrawSystem.BONUS else max(1, 1 + int(application.points_before_draw)),
                reason_codes=tuple(),
            )
        )
    return units


def run_simulation_once(draw_state: DrawState, seed: int) -> SimulationResult:
    config = draw_state.rule_config
    quota = derive_quota(draw_state.quota, draw_state.hunt, config)
    rng = random.Random(seed)
    results: List[DrawResult] = []
    separate_residency, residency_buckets, initial_total = _init_residency_buckets(quota)
    remaining = {
        "bonus_reserved": int(quota.reserved_quota or 0),
        "bonus_random": int(quota.random_quota or 0),
        "preference": int(quota.preference_quota or quota.total_public_permits),
        "youth_reserved": int(quota.youth_reserved_quota or 0),
        "general": int(quota.total_public_permits),
    }
    total_remaining = {"value": initial_total}
    remaining_by_hunt: MutableMapping[str, int] = defaultdict(int)
    remaining_by_hunt[draw_state.hunt.hunt_code] = int(quota.total_public_permits)

    ordered_units = [unit for unit in draw_state.application_units if unit.valid_flag and unit.eligible_flag]
    draw_order = get_draw_order(draw_state.hunt.hunt_type)
    reason_codes: List[str] = []
    drawn_ids: set[str] = set()

    if draw_state.hunt.hunt_type in {"general_season", "antlerless", "youth_general"} and (quota.youth_reserved_quota or 0) > 0:
        youth_pool = [unit for unit in ordered_units if unit.youth_only_flag]
        for points in sorted({unit.effective_points for unit in youth_pool}, reverse=True):
            bucket = [unit for unit in youth_pool if unit.effective_points == points]
            rng.shuffle(bucket)
            for unit in bucket:
                if remaining["youth_reserved"] <= 0:
                    break
                if not can_group_fit_quota(unit.group_size, remaining["youth_reserved"]):
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "youth_reserved", None, 0, False, ("GROUP_SKIPPED_QUOTA_TOO_SMALL",))
                    )
                    continue
                if _consume_residency_quota(unit, separate_residency, residency_buckets, total_remaining) is None:
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "youth_reserved", None, 0, False, ("CROSSOVER_NOT_ALLOWED",))
                    )
                    continue
                remaining["youth_reserved"] -= unit.group_size
                remaining_by_hunt[draw_state.hunt.hunt_code] -= unit.group_size
                drawn_ids.add(unit.application_unit_id)
                results.append(
                    DrawResult(unit.application_unit_id, unit.member_application_ids, draw_state.hunt.hunt_code, True, "youth_reserved", 1, unit.group_size, True, ("YOUTH_RESERVED_SELECTED",))
                )

    if drawn_ids:
        ordered_units = [unit for unit in ordered_units if unit.application_unit_id not in drawn_ids]

    if draw_state.hunt.rule_system == DrawSystem.PREFERENCE:
        for points in sorted({unit.effective_points for unit in ordered_units}, reverse=True):
            bucket = [unit for unit in ordered_units if unit.effective_points == points]
            rng.shuffle(bucket)
            for unit in bucket:
                choice, choice_rank = _select_choice(unit, remaining_by_hunt)
                if choice is None:
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "none", None, 0, False, ("NO_CHOICE_WITH_AVAILABLE_QUOTA",))
                    )
                    continue
                if not can_group_fit_quota(unit.group_size, remaining_by_hunt[choice]):
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "preference", None, 0, False, ("GROUP_SKIPPED_PREFERENCE_QUOTA_TOO_SMALL",))
                    )
                    continue
                if _consume_residency_quota(unit, separate_residency, residency_buckets, total_remaining) is None:
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "preference", None, 0, False, ("CROSSOVER_NOT_ALLOWED",))
                    )
                    continue
                remaining_by_hunt[choice] -= unit.group_size
                remaining["preference"] -= unit.group_size
                results.append(
                    DrawResult(unit.application_unit_id, unit.member_application_ids, choice, True, "preference", choice_rank, unit.group_size, True, ("PREFERENCE_SELECTED", "POINTS_FORFEITED_PREFERENCE"))
                )
    else:
        reserved_pool = [unit for unit in ordered_units if unit.hunt_choices and unit.hunt_choices[0] == draw_state.hunt.hunt_code]
        if separate_residency:
            # DWR evaluates every choice inside each residency lane before any
            # eligible cross-over evaluation.  Do not share max/random counters
            # across lanes: a resident's high point total cannot consume an NR
            # permit while NR applicants still await their own round.
            lane_remaining = {
                residency: {
                    "bonus_reserved": _bonus_lane_round_quota(residency, residency_buckets[residency], config)[0],
                    "bonus_random": _bonus_lane_round_quota(residency, residency_buckets[residency], config)[1],
                }
                for residency in ("Resident", "Nonresident")
            }
            for residency in ("Resident", "Nonresident"):
                lane_pool = [unit for unit in reserved_pool if normalize_residency(unit.residency) == residency]
                for points in sorted({unit.effective_points for unit in lane_pool}, reverse=True):
                    bucket = [unit for unit in lane_pool if unit.effective_points == points]
                    rng.shuffle(bucket)
                    for unit in bucket:
                        if lane_remaining[residency]["bonus_reserved"] <= 0:
                            break
                        if not can_group_fit_quota(unit.group_size, lane_remaining[residency]["bonus_reserved"]):
                            results.append(
                                DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "reserved_bonus", None, 0, False, ("GROUP_SKIPPED_RESERVED_QUOTA_TOO_SMALL", "MAX_POOL_NOT_GUARANTEED"))
                            )
                            continue
                        if _consume_residency_quota(unit, True, residency_buckets, total_remaining, residency) is None:
                            results.append(
                                DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "reserved_bonus", None, 0, False, ("RESIDENCY_LANE_QUOTA_EXHAUSTED",))
                            )
                            continue
                        lane_remaining[residency]["bonus_reserved"] -= unit.group_size
                        remaining_by_hunt[draw_state.hunt.hunt_code] -= unit.group_size
                        drawn_ids.add(unit.application_unit_id)
                        results.append(
                            DrawResult(unit.application_unit_id, unit.member_application_ids, draw_state.hunt.hunt_code, True, "reserved_bonus", 1, unit.group_size, True, ("BONUS_RESERVED_SELECTED", f"RESIDENCY_LANE_{residency.upper()}"))
                        )

            for residency in ("Resident", "Nonresident"):
                random_pool = [
                    unit for unit in ordered_units
                    if normalize_residency(unit.residency) == residency and unit.application_unit_id not in drawn_ids
                ]
                while random_pool and lane_remaining[residency]["bonus_random"] > 0:
                    selected = _weighted_draw(random_pool, rng)
                    if selected is None:
                        break
                    random_pool = [unit for unit in random_pool if unit.application_unit_id != selected.application_unit_id]
                    choice, choice_rank = _select_choice(selected, remaining_by_hunt)
                    if choice is None:
                        results.append(
                            DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("BONUS_RANDOM_NO_CHOICE_AVAILABLE",))
                        )
                        continue
                    if not can_group_fit_quota(selected.group_size, lane_remaining[residency]["bonus_random"]):
                        results.append(
                            DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("GROUP_SKIPPED_RANDOM_QUOTA_TOO_SMALL",))
                        )
                        continue
                    if _consume_residency_quota(selected, True, residency_buckets, total_remaining, residency) is None:
                        results.append(
                            DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("RESIDENCY_LANE_QUOTA_EXHAUSTED",))
                        )
                        continue
                    lane_remaining[residency]["bonus_random"] -= selected.group_size
                    remaining_by_hunt[choice] -= selected.group_size
                    drawn_ids.add(selected.application_unit_id)
                    results.append(
                        DrawResult(selected.application_unit_id, selected.member_application_ids, choice, True, "random_bonus", choice_rank, selected.group_size, True, ("BONUS_RANDOM_SELECTED", f"RESIDENCY_LANE_{residency.upper()}", "POINTS_FORFEITED_BONUS"))
                    )

            if _bonus_crossover_is_allowed(draw_state, quota):
                crossover_pool = [unit for unit in ordered_units if unit.application_unit_id not in drawn_ids]
                while crossover_pool:
                    selected = _weighted_draw(crossover_pool, rng)
                    if selected is None:
                        break
                    crossover_pool = [unit for unit in crossover_pool if unit.application_unit_id != selected.application_unit_id]
                    target_residency = "Nonresident" if normalize_residency(selected.residency) == "Resident" else "Resident"
                    choice, choice_rank = _select_choice(selected, remaining_by_hunt)
                    if choice is None:
                        results.append(
                            DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "crossover_bonus", None, 0, False, ("BONUS_CROSSOVER_NO_CHOICE_AVAILABLE",))
                        )
                        continue
                    if _consume_residency_quota(selected, True, residency_buckets, total_remaining, target_residency) is None:
                        results.append(
                            DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "crossover_bonus", None, 0, False, ("CROSSOVER_LANE_QUOTA_EXHAUSTED",))
                        )
                        continue
                    remaining_by_hunt[choice] -= selected.group_size
                    drawn_ids.add(selected.application_unit_id)
                    results.append(
                        DrawResult(selected.application_unit_id, selected.member_application_ids, choice, True, "crossover_bonus", choice_rank, selected.group_size, True, ("BONUS_CROSSOVER_SELECTED", "CROSSOVER_AFTER_SEPARATE_RESIDENCY_EVALUATION", "POINTS_FORFEITED_BONUS"))
                    )
        else:
            for points in sorted({unit.effective_points for unit in reserved_pool}, reverse=True):
                bucket = [unit for unit in reserved_pool if unit.effective_points == points]
                rng.shuffle(bucket)
                for unit in bucket:
                    if remaining["bonus_reserved"] <= 0:
                        break
                    if not can_group_fit_quota(unit.group_size, remaining["bonus_reserved"]):
                        results.append(
                            DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "reserved_bonus", None, 0, False, ("GROUP_SKIPPED_RESERVED_QUOTA_TOO_SMALL", "MAX_POOL_NOT_GUARANTEED"))
                        )
                        continue
                    if _consume_residency_quota(unit, False, residency_buckets, total_remaining) is None:
                        results.append(
                            DrawResult(unit.application_unit_id, unit.member_application_ids, None, False, "reserved_bonus", None, 0, False, ("RESIDENCY_LANE_QUOTA_EXHAUSTED",))
                        )
                        continue
                    remaining["bonus_reserved"] -= unit.group_size
                    remaining_by_hunt[draw_state.hunt.hunt_code] -= unit.group_size
                    results.append(
                        DrawResult(unit.application_unit_id, unit.member_application_ids, draw_state.hunt.hunt_code, True, "reserved_bonus", 1, unit.group_size, True, ("BONUS_RESERVED_SELECTED",))
                    )

            random_pool = [unit for unit in ordered_units if unit.application_unit_id not in {result.application_unit_id for result in results if result.drawn_flag}]
            while random_pool and remaining["bonus_random"] > 0:
                selected = _weighted_draw(random_pool, rng)
                if selected is None:
                    break
                random_pool = [unit for unit in random_pool if unit.application_unit_id != selected.application_unit_id]
                choice, choice_rank = _select_choice(selected, remaining_by_hunt)
                if choice is None:
                    results.append(
                        DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("BONUS_RANDOM_NO_CHOICE_AVAILABLE",))
                    )
                    continue
                if not can_group_fit_quota(selected.group_size, remaining["bonus_random"]):
                    results.append(
                        DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("GROUP_SKIPPED_RANDOM_QUOTA_TOO_SMALL",))
                    )
                    continue
                if _consume_residency_quota(selected, False, residency_buckets, total_remaining) is None:
                    results.append(
                        DrawResult(selected.application_unit_id, selected.member_application_ids, None, False, "random_bonus", None, 0, False, ("RESIDENCY_LANE_QUOTA_EXHAUSTED",))
                    )
                    continue
                remaining["bonus_random"] -= selected.group_size
                remaining_by_hunt[choice] -= selected.group_size
                results.append(
                    DrawResult(selected.application_unit_id, selected.member_application_ids, choice, True, "random_bonus", choice_rank, selected.group_size, True, ("BONUS_RANDOM_SELECTED", "POINTS_FORFEITED_BONUS"))
                )

    return SimulationResult(draw_state, tuple(results), tuple(reason_codes))


def _aggregate_simulation(draw_state: DrawState, simulations: Sequence[SimulationResult]) -> List[PredictionAggregate]:
    buckets: Dict[tuple[str, str, int], Dict[str, List[float] | float]] = {}
    eligible_units = [unit for unit in draw_state.application_units if unit.valid_flag and unit.eligible_flag and unit.hunt_choices]
    by_bucket: Dict[tuple[str, str, int], List[ApplicationUnit]] = defaultdict(list)
    for unit in eligible_units:
        by_bucket[(draw_state.hunt.hunt_code, unit.residency, int(unit.effective_points))].append(unit)

    for key, units in by_bucket.items():
        buckets[key] = {
            "draws": [],
            "reserved": [],
            "random": [],
            "preference": [],
            "youth": [],
        }

    for simulation in simulations:
        result_map = {result.application_unit_id: result for result in simulation.results}
        for key, units in by_bucket.items():
            drawn = 0
            reserved = 0
            random_draw = 0
            preference = 0
            youth = 0
            for unit in units:
                result = result_map.get(unit.application_unit_id)
                if result and result.drawn_flag:
                    drawn += 1
                    if result.draw_stage == "reserved_bonus":
                        reserved += 1
                    elif result.draw_stage in {"random_bonus", "crossover_bonus"}:
                        random_draw += 1
                    elif result.draw_stage == "preference":
                        preference += 1
                    elif result.draw_stage == "youth_reserved":
                        youth += 1
            total = max(len(units), 1)
            buckets[key]["draws"].append(drawn / total)
            buckets[key]["reserved"].append(reserved / total)
            buckets[key]["random"].append(random_draw / total)
            buckets[key]["preference"].append(preference / total)
            buckets[key]["youth"].append(youth / total)

    aggregates: List[PredictionAggregate] = []
    for (hunt_code, residency, points), values in buckets.items():
        draw_rates = values["draws"]
        reserved_rates = values["reserved"]
        random_rates = values["random"]
        preference_rates = values["preference"]
        youth_rates = values["youth"]
        draw_mean = mean(draw_rates) if draw_rates else 0.0
        sorted_draws = sorted(draw_rates)
        p10 = sorted_draws[max(0, int(math.floor((len(sorted_draws) - 1) * 0.10)))] if sorted_draws else 0.0
        p50 = sorted_draws[max(0, int(math.floor((len(sorted_draws) - 1) * 0.50)))] if sorted_draws else 0.0
        p90 = sorted_draws[max(0, int(math.floor((len(sorted_draws) - 1) * 0.90)))] if sorted_draws else 0.0
        guaranteed_probability = sum(1.0 for rate in draw_rates if rate >= 1.0) / len(draw_rates) if draw_rates else 0.0
        p_reserved = mean(reserved_rates) if reserved_rates else 0.0
        p_random = mean(random_rates) if random_rates else 0.0
        p_preference = mean(preference_rates) if preference_rates else 0.0
        p_youth = mean(youth_rates) if youth_rates else 0.0
        expected_cutoff = float(points if draw_mean > 0 else 0)
        cutoff_probability = draw_mean if draw_mean > 0 else None
        if guaranteed_probability >= 0.999:
            display_odds = 100.0
        else:
            display_odds = round(draw_mean * 100.0, 3)
        reason_codes = []
        if draw_mean >= 0.999:
            reason_codes.append("MAX_POOL_NOT_GUARANTEED" if guaranteed_probability < 0.999 else "RESERVED_POOL_ALL_CLEAR")
        if draw_mean == 0.0:
            reason_codes.append("NO_QUOTA")
        aggregates.append(
            PredictionAggregate(
                draw_year=draw_state.draw_year,
                hunt_code=hunt_code,
                residency=residency,
                points=points,
                p_draw_mean=round(draw_mean, 6),
                p_draw_p10=round(p10, 6),
                p_draw_p50=round(p50, 6),
                p_draw_p90=round(p90, 6),
                p_reserved_mean=round(p_reserved, 6),
                p_random_mean=round(p_random, 6),
                p_preference_mean=round(p_preference, 6),
                p_youth_mean=round(p_youth, 6),
                expected_cutoff_points=expected_cutoff,
                cutoff_bucket_probability=cutoff_probability,
                guaranteed_probability=round(guaranteed_probability, 6),
                quota_source=draw_state.quota_source,
                applicant_pool_source=draw_state.applicant_pool_source,
                model_version=MODEL_VERSION,
                rule_version=RULE_VERSION,
                data_cutoff_date=draw_state.data_cutoff_date,
                data_quality_grade=draw_state.data_quality_grade,
                reason_codes=tuple(reason_codes),
                display_odds_pct=round(display_odds, 3),
            )
        )
    return aggregates


def run_monte_carlo(draw_state: DrawState, iterations: int = 1000, seed: int = 0) -> List[PredictionAggregate]:
    simulations = [run_simulation_once(draw_state, seed + index) for index in range(max(int(iterations), 1))]
    return _aggregate_simulation(draw_state, simulations)
