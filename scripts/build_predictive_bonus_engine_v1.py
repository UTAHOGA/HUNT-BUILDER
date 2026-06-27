"""Build a new Utah predictive bonus draw engine for O.I.L., L.E., and P.L.E. hunts.

Rule-first + history-calibrated Monte Carlo engine using HYBRID_ML_V1 output contract.
This script preserves legacy bridge fields while replacing deprecated MAX POOL=100 shortcuts.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Tuple

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah.materialize import materialize_rows, write_materialized_csv
from engine.utah.current_year_allotments import (
    RAC_SOURCE_LABEL,
    apply_current_year_allotments_to_rows,
    current_year_quota_for_residency,
)
from engine.utah_bonus_predictive.cohort_forecast import roll_forward_applicant_stack
from engine.utah_bonus_predictive.rules import MODEL_VERSION, RULE_VERSION
from engine.utah_bonus_predictive.split import split_utah_bonus_permits

INPUT_DRAW_V2 = REPO / "data_model" / "runtime_drafts" / "draw_reality_engine_v2.csv"
INPUT_DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
INPUT_LEGACY_ENGINE = REPO / "processed_data" / "draw_reality_engine.csv"
OFFICIAL_2026_QUOTA_SOURCE_FILE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"

OUT_DIR_DEFAULT = REPO / "data_model" / "runtime_drafts"

TARGET_TOKENS = (
    "once-in-a-lifetime",
    "once in a lifetime",
    "oial",
    "limited entry",
    "premium limited entry",
)

TRUE_PLE_HUNT_CODES = {
    "DB0009",
    "DB1000",
    "DB1001",
    "DB1002",
    "DB1003",
    "DB1004",
    "DB1005",
    "DB1006",
    "DB1007",
    "DB1008",
}


def clean(v: object) -> str:
    return "" if v is None else str(v).strip()


def to_int(v: object, default: int = 0) -> int:
    t = clean(v)
    if not t:
        return default
    try:
        return int(float(t))
    except Exception:
        return default


def to_float(v: object, default: float = 0.0) -> float:
    t = clean(v)
    if not t:
        return default
    try:
        return float(t)
    except Exception:
        return default


def read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, headers: List[str], rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def is_target_bonus_hunt(hunt_type: str) -> bool:
    h = clean(hunt_type).lower()
    return any(tok in h for tok in TARGET_TOKENS)


def normalize_bonus_hunt_type(hunt_type: str, hunt_code: str) -> str:
    h = clean(hunt_type)
    if clean(hunt_code).upper() in TRUE_PLE_HUNT_CODES:
        return "Premium Limited Entry"
    if "premium limited entry" in h.lower() and clean(hunt_code).upper() not in TRUE_PLE_HUNT_CODES:
        return "Limited Entry"
    return h


def hunt_kind_label(hunt_type: str, hunt_code: str = "") -> str:
    if clean(hunt_code).upper() in TRUE_PLE_HUNT_CODES:
        return "PLE"
    h = clean(hunt_type).lower()
    if "premium limited entry" in h and clean(hunt_code).upper() in TRUE_PLE_HUNT_CODES:
        return "PLE"
    if "once-in-a-lifetime" in h or "once in a lifetime" in h or "oial" in h:
        return "OIL"
    return "LE"


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = int(math.floor((len(vals) - 1) * p))
    idx = max(0, min(idx, len(vals) - 1))
    return vals[idx]


def growth_rate(series: List[Tuple[int, int]]) -> float:
    if len(series) < 2:
        return 0.03
    series = sorted(series)
    deltas: List[float] = []
    for i in range(1, len(series)):
        prev = max(series[i - 1][1], 1)
        curr = max(series[i][1], 0)
        deltas.append((curr - prev) / prev)
    if not deltas:
        return 0.03
    g = mean(deltas)
    return max(-0.25, min(0.25, g))


def infer_reserved_fraction(rows: List[dict]) -> float:
    fracs: List[float] = []
    for r in rows:
        b = to_float(r.get("bonus_permits"), 0.0)
        reg = to_float(r.get("regular_permits"), 0.0)
        tot = to_float(r.get("total_permits"), 0.0)
        if tot <= 0:
            continue
        if b > 0 or reg > 0:
            fracs.append(max(0.0, min(1.0, b / tot)))
    if not fracs:
        return 0.5
    return max(0.35, min(0.65, mean(fracs)))


def classify_point_pool_zone(p_reserved: float) -> str:
    if p_reserved >= 0.999:
        return "max_pool_guaranteed"
    if p_reserved > 0:
        return "max_pool_cutoff_mixed"
    return "random_pool"


def status_from_pool_zone(point_pool_zone: str, random_quota: int) -> str:
    if point_pool_zone == "max_pool_guaranteed":
        return "MAX POOL"
    if point_pool_zone == "max_pool_cutoff_mixed":
        return "MIXED CUTOFF"
    if random_quota > 0:
        return "RANDOM ONLY"
    return "BEHIND"


def simulate_iteration(points_desc: List[int], demand_by_point: Dict[int, int], reserved_quota: int, random_quota: int) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, str], float | None]:
    # Reserved (max-point-first) stage
    remaining_reserved = max(0, reserved_quota)
    p_reserved: Dict[int, float] = {p: 0.0 for p in points_desc}
    pool_zone: Dict[int, str] = {p: "random_pool" for p in points_desc}
    nonwinners: Dict[int, int] = {}
    cutoff: float | None = None

    for p in points_desc:
        n = max(0, demand_by_point.get(p, 0))
        if n <= 0:
            nonwinners[p] = 0
            continue
        if remaining_reserved <= 0:
            winners = 0
        elif remaining_reserved >= n:
            winners = n
        else:
            winners = remaining_reserved
        prob_res = winners / n if n > 0 else 0.0
        p_reserved[p] = prob_res
        pool_zone[p] = classify_point_pool_zone(prob_res)
        nonwinners[p] = n - winners
        if winners > 0:
            cutoff = float(p)
        remaining_reserved = max(0, remaining_reserved - winners)

    # Random stage (bonus tickets) on nonwinners
    total_tickets = 0.0
    tickets_by_point: Dict[int, float] = {}
    for p, n in nonwinners.items():
        t = float(max(0, p + 1) * max(0, n))
        tickets_by_point[p] = t
        total_tickets += t

    p_random: Dict[int, float] = {p: 0.0 for p in points_desc}
    if random_quota > 0 and total_tickets > 0:
        # With-replacement approximation, stable for large pools.
        draws = float(max(0, random_quota))
        for p in points_desc:
            n = nonwinners.get(p, 0)
            if n <= 0:
                continue
            ticket_share = (p + 1) / total_tickets
            p_rand = 1.0 - ((1.0 - ticket_share) ** draws)
            p_random[p] = max(0.0, min(1.0, p_rand))

    p_draw: Dict[int, float] = {}
    for p in points_desc:
        pr = p_reserved.get(p, 0.0)
        rr = p_random.get(p, 0.0)
        p_draw[p] = max(0.0, min(1.0, pr + (1.0 - pr) * rr))

    return p_draw, p_reserved, pool_zone, cutoff


def deterministic_pool_probabilities(points_desc: List[int], demand_by_point: Dict[int, int], reserved_quota: int, random_quota: int) -> Tuple[Dict[int, float], Dict[int, float], Dict[int, float], Dict[int, str], float | None]:
    remaining_reserved = max(0, reserved_quota)
    p_reserved: Dict[int, float] = {p: 0.0 for p in points_desc}
    nonwinners: Dict[int, int] = {}
    pool_zone: Dict[int, str] = {p: "random_pool" for p in points_desc}
    cutoff: float | None = None

    for p in points_desc:
        applicants = max(0, int(demand_by_point.get(p, 0)))
        if applicants <= 0:
            nonwinners[p] = 0
            continue
        winners = min(applicants, remaining_reserved)
        p_reserved[p] = winners / applicants
        pool_zone[p] = classify_point_pool_zone(p_reserved[p])
        nonwinners[p] = applicants - winners
        if winners > 0:
            cutoff = float(p)
        remaining_reserved = max(0, remaining_reserved - winners)

    total_tickets = sum(max(0, p + 1) * max(0, count) for p, count in nonwinners.items())
    p_random: Dict[int, float] = {p: 0.0 for p in points_desc}
    if random_quota > 0 and total_tickets > 0:
        for p in points_desc:
            if nonwinners.get(p, 0) <= 0:
                continue
            ticket_share = (p + 1) / total_tickets
            p_random[p] = max(0.0, min(1.0, 1.0 - ((1.0 - ticket_share) ** random_quota)))

    p_draw = {
        p: max(0.0, min(1.0, p_reserved[p] + ((1.0 - p_reserved[p]) * p_random[p])))
        for p in points_desc
    }
    return p_draw, p_reserved, p_random, pool_zone, cutoff


def build_predictions(history_rows: List[dict], db_by_code: Dict[str, dict], prediction_year: int, iterations: int, seed: int) -> Tuple[List[dict], List[dict]]:
    rng = random.Random(seed)

    # Group history at hunt+pool+residency granularity
    grouped: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    for r in history_rows:
        code = clean(r.get("hunt_code")).upper()
        draw_pool = clean(r.get("draw_pool")).lower() or "standard"
        res = clean(r.get("residency"))
        grouped[(code, draw_pool, res)].append(r)

    prediction_rows: List[dict] = []
    audit_rows: List[dict] = []

    for (code, draw_pool, residency), rows in grouped.items():
        db = db_by_code.get(code)
        if not db:
            continue

        raw_hunt_type = clean(db.get("hunt_type"))
        hunt_type = normalize_bonus_hunt_type(raw_hunt_type, code)
        kind = hunt_kind_label(raw_hunt_type, code)
        if not is_target_bonus_hunt(raw_hunt_type):
            continue

        # Published 2026 DB permit fields are the runtime quota source.
        q_res = to_int(db.get("permits_2026_res"), 0)
        q_nr = to_int(db.get("permits_2026_nr"), 0)
        q_total = to_int(db.get("permits_2026_total"), q_res + q_nr)
        residency_quota = current_year_quota_for_residency(db, residency)
        quota_source_file = OFFICIAL_2026_QUOTA_SOURCE_FILE
        quota_source_label = clean(db.get("permits_2026_source")) or "DATABASE_2026_PERMITS"
        if residency_quota <= 0:
            # Resident-only or NR-only handling: skip empty lane
            continue

        # Demand series by point and full point-level draw history.
        by_point_year: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        point_history_by_year: Dict[int, Dict[int, Dict[str, int]]] = defaultdict(dict)
        for r in rows:
            yr = to_int(r.get("year"), 0)
            pt = to_int(r.get("points"), 0)
            app = to_int(r.get("eligible_applicants"), 0)
            if yr > 0:
                by_point_year[pt].append((yr, app))
                point_history_by_year[yr][pt] = {
                    "eligible": app,
                    "bonus": to_int(r.get("bonus_permits"), 0),
                    "regular": to_int(r.get("regular_permits"), 0),
                    "total": to_int(r.get("total_permits"), 0),
                }

        source_year = max((year for year in point_history_by_year if year < prediction_year), default=0)
        if not source_year:
            continue

        rollover = roll_forward_applicant_stack(point_history_by_year, source_year)
        base_demand_by_point = dict(rollover.applicants_by_points)
        structural_points = set(by_point_year.keys())
        if structural_points:
            max_structural_point = max(structural_points)
            structural_points.update(range(max_structural_point + 1, max_structural_point + 5))
        points_desc = sorted(structural_points | set(base_demand_by_point.keys()), reverse=True)
        if not points_desc:
            continue

        split = split_utah_bonus_permits(residency_quota)
        reserved_quota = split.maxPointPermits
        random_quota = split.randomPermits
        reserved_fraction = (reserved_quota / residency_quota) if residency_quota > 0 else 0.0
        quota_source_status = "official"
        quota_source_year = prediction_year
        deterministic_draw, deterministic_reserved, deterministic_random, deterministic_zones, deterministic_cutoff = deterministic_pool_probabilities(
            points_desc,
            base_demand_by_point,
            reserved_quota,
            random_quota,
        )
        projected_random_pool_start_point = int(deterministic_cutoff) - 1 if deterministic_cutoff is not None else ""

        # Monte Carlo containers by point
        p_draw_samples: Dict[int, List[float]] = defaultdict(list)
        p_reserved_samples: Dict[int, List[float]] = defaultdict(list)
        p_random_samples: Dict[int, List[float]] = defaultdict(list)
        zone_samples: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        cutoff_samples: List[float] = []

        for _ in range(max(1, iterations)):
            demand_iter: Dict[int, int] = {}
            for p in points_desc:
                base = max(0.0, float(base_demand_by_point.get(p, 0)))
                # History-calibrated uncertainty: demand variance grows with base and volatility
                sigma = max(1.0, math.sqrt(max(base, 1.0)) * 0.25)
                sampled = int(round(max(0.0, rng.gauss(base, sigma))))
                demand_iter[p] = sampled

            p_draw_map, p_res_map, zone_map, cutoff = simulate_iteration(points_desc, demand_iter, reserved_quota, random_quota)
            if cutoff is not None:
                cutoff_samples.append(cutoff)
            for p in points_desc:
                p_draw_samples[p].append(p_draw_map.get(p, 0.0))
                p_reserved_samples[p].append(p_res_map.get(p, 0.0))
                p_random_value = 0.0
                if p_res_map.get(p, 0.0) < 0.999:
                    residual = max(0.0, 1.0 - p_res_map.get(p, 0.0))
                    if residual > 0:
                        p_random_value = max(0.0, min(1.0, (p_draw_map.get(p, 0.0) - p_res_map.get(p, 0.0)) / residual))
                p_random_samples[p].append(p_random_value)
                zone_samples[p][zone_map.get(p, "random_pool")] += 1

        expected_cutoff = round(mean(cutoff_samples), 3) if cutoff_samples else None

        # Build per-point prediction rows
        for p in points_desc:
            draws = p_draw_samples[p]
            pres = p_reserved_samples[p]
            p_draw_mean = deterministic_draw.get(p, mean(draws) if draws else 0.0)
            p10 = percentile(draws, 0.10)
            p50 = percentile(draws, 0.50)
            p90 = percentile(draws, 0.90)
            p_reserved_mean = deterministic_reserved.get(p, mean(pres) if pres else 0.0)
            p_random_mean = deterministic_random.get(p, mean(p_random_samples[p]) if p_random_samples[p] else 0.0)
            guaranteed_probability = 1.0 if p_draw_mean >= 0.999 else 0.0
            point_pool_zone = deterministic_zones.get(p) or (max(zone_samples[p].items(), key=lambda item: (item[1], item[0]))[0] if zone_samples[p] else classify_point_pool_zone(p_reserved_mean))

            reasons = [
                "BONUS_RULE_SIMULATED",
                f"HUNT_KIND_{kind}",
                f"DRAW_POOL_{draw_pool.upper()}",
                "MAX_POOL_DEPRECATED_NO_AUTO_100",
                "APPLICANT_STACK_ROLLED_FORWARD",
                "MAX_POINT_BOUNDARY_RECOMPUTED",
                "OFFICIAL_2026_QUOTA_USED",
            ]
            if quota_source_label:
                reasons.append("DATABASE_2026_PERMITS_USED")
            if guaranteed_probability >= 0.999:
                reasons.append("MODELED_100_CONFIRMED")
            if point_pool_zone == "max_pool_cutoff_mixed":
                reasons.append("MIXED_MAX_POINT_CUTOFF")
            if rollover.cutoff_structure:
                reasons.append(f"ROLLOVER_CUTOFF_STRUCTURE_{rollover.cutoff_structure}")
            if rollover.rollover_rule:
                reasons.append(rollover.rollover_rule)

            prediction_rows.append(
                {
                    "draw_year": prediction_year,
                    "hunt_code": code,
                    "residency": residency,
                    "points": p,
                    "p_draw_mean": round(p_draw_mean, 6),
                    "p_draw_p10": round(p10, 6),
                    "p_draw_p50": round(p50, 6),
                    "p_draw_p90": round(p90, 6),
                    "p_reserved_mean": round(p_reserved_mean, 6),
                    "p_random_mean": round(p_random_mean, 6),
                    "p_max_pool_mean": round(p_reserved_mean, 6),
                    "p_preference_mean": 0.0,
                    "p_youth_mean": 1.0 if draw_pool.startswith("youth") else 0.0,
                    "expected_cutoff_points": deterministic_cutoff if deterministic_cutoff is not None else expected_cutoff,
                    "cutoff_bucket_probability": round(p_draw_mean, 6),
                    "guaranteed_probability": round(guaranteed_probability, 6),
                    "point_creep_1yr": 0.0,
                    "point_creep_3yr": 0.0,
                    "quota_source": "approved_2026_residency_split",
                    "quota_source_status": quota_source_status,
                    "quota_source_year": quota_source_year,
                    "quota_source_file": quota_source_file,
                    "quota_2026_total": residency_quota,
                    "quota_2026_max_pool": reserved_quota,
                    "quota_2026_random_pool": random_quota,
                    "permit_allotment_2026_res": clean(db.get("permit_allotment_2026_res")),
                    "permit_allotment_2026_nr": clean(db.get("permit_allotment_2026_nr")),
                    "permit_allotment_2026_total": clean(db.get("permit_allotment_2026_total")),
                    "permit_allotment_2026_source": clean(db.get("permit_allotment_2026_source")),
                    "permit_allotment_2026_source_file": clean(db.get("permit_allotment_2026_source_file")),
                    "permit_allotment_2026_status": clean(db.get("permit_allotment_2026_status")),
                    "projected_2026_max_cutoff_point": deterministic_cutoff if deterministic_cutoff is not None else "",
                    "projected_2026_random_pool_start_point": projected_random_pool_start_point,
                    "is_2026_max_point_pool": point_pool_zone in {"max_pool_guaranteed", "max_pool_cutoff_mixed"},
                    "is_2026_mixed_cutoff": point_pool_zone == "max_pool_cutoff_mixed",
                    "is_2026_random_pool": point_pool_zone == "random_pool",
                    "applicant_pool_source": "public_historical_proxy",
                    "model_version": MODEL_VERSION,
                    "rule_version": RULE_VERSION,
                    "data_cutoff_date": str(date.today()),
                    "data_quality_grade": "B",
                    "reason_codes": tuple(reasons),
                    "display_odds_pct": round(p_draw_mean * 100.0, 3),
                    "status": status_from_pool_zone(point_pool_zone, random_quota),
                    "point_pool_zone": point_pool_zone,
                    "applicant_rollover_source_year": source_year,
                    "retention_rate_raw": round(rollover.retention_rate_raw, 6),
                    "retention_rate_smoothed": round(rollover.retention_rate_smoothed, 6),
                    "rollover_rule": rollover.rollover_rule,
                    "rollover_cutoff_structure": rollover.cutoff_structure,
                    "rollover_mixed_cutoff_point": rollover.mixed_cutoff_point if rollover.mixed_cutoff_point is not None else "",
                    "rollover_anchor_next_point": rollover.anchor_next_point if rollover.anchor_next_point is not None else "",
                    "structure_retention_rate_raw": "" if rollover.structure_retention_rate_raw is None else round(rollover.structure_retention_rate_raw, 6),
                    "structure_retention_rate_smoothed": "" if rollover.structure_retention_rate_smoothed is None else round(rollover.structure_retention_rate_smoothed, 6),
                    "structure_retention_prior": "" if rollover.structure_retention_prior is None else round(rollover.structure_retention_prior, 6),
                    "structure_retention_matched_years": rollover.structure_retention_matched_years,
                    "structure_retention_unsuccessful_total": rollover.structure_retention_unsuccessful_total,
                    "forecast_applicants_at_level": int(base_demand_by_point.get(p, 0)),
                    "forecast_applicants_above": sum(count for point, count in base_demand_by_point.items() if point > p),
                    "rolled_forward_total_applicants": rollover.total_projected_applicants,
                    "draw_pool": draw_pool,
                    "hunt_type": hunt_type,
                }
            )

        audit_rows.append(
            {
                "hunt_code": code,
                "hunt_type": hunt_type,
                "hunt_kind": kind,
                "draw_pool": draw_pool,
                "residency": residency,
                "prediction_year": prediction_year,
                "quota_residency": residency_quota,
                "reserved_quota": reserved_quota,
                "random_quota": random_quota,
                "quota_source_status": quota_source_status,
                "quota_source_file": quota_source_file,
                "permit_allotment_2026_source": quota_source_label,
                "reserved_fraction": round(reserved_fraction, 4),
                "applicant_rollover_source_year": source_year,
                "retention_rate_raw": round(rollover.retention_rate_raw, 6),
                "retention_rate_smoothed": round(rollover.retention_rate_smoothed, 6),
                "rollover_rule": rollover.rollover_rule,
                "rollover_cutoff_structure": rollover.cutoff_structure,
                "rollover_mixed_cutoff_point": rollover.mixed_cutoff_point if rollover.mixed_cutoff_point is not None else "",
                "rollover_anchor_next_point": rollover.anchor_next_point if rollover.anchor_next_point is not None else "",
                "structure_retention_rate_raw": "" if rollover.structure_retention_rate_raw is None else round(rollover.structure_retention_rate_raw, 6),
                "structure_retention_rate_smoothed": "" if rollover.structure_retention_rate_smoothed is None else round(rollover.structure_retention_rate_smoothed, 6),
                "structure_retention_prior": "" if rollover.structure_retention_prior is None else round(rollover.structure_retention_prior, 6),
                "structure_retention_matched_years": rollover.structure_retention_matched_years,
                "structure_retention_unsuccessful_total": rollover.structure_retention_unsuccessful_total,
                "rolled_forward_total_applicants": rollover.total_projected_applicants,
                "rolled_forward_unsuccessful_applicants": rollover.total_unsuccessful_source_applicants,
                "lower_point_additions": rollover.total_lower_point_additions,
                "points_modeled": len(points_desc),
                "expected_cutoff_points": "" if deterministic_cutoff is None else deterministic_cutoff,
                "iterations": iterations,
            }
        )

    prediction_rows.sort(key=lambda r: (r["hunt_code"], r["draw_pool"], r["residency"], int(r["points"])))
    audit_rows.sort(key=lambda r: (r["hunt_code"], r["draw_pool"], r["residency"]))
    return prediction_rows, audit_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build predictive Utah bonus draw engine for OIL/LE/PLE hunts.")
    parser.add_argument("--prediction-year", type=int, default=2026)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20260520)
    parser.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    history = read_csv(INPUT_DRAW_V2)
    db_rows = apply_current_year_allotments_to_rows(read_csv(INPUT_DATABASE))
    legacy_engine = read_csv(INPUT_LEGACY_ENGINE)

    db_by_code = {clean(r.get("hunt_code")).upper(): r for r in db_rows if clean(r.get("hunt_code"))}

    predictions, audit = build_predictions(
        history_rows=history,
        db_by_code=db_by_code,
        prediction_year=args.prediction_year,
        iterations=args.iterations,
        seed=args.seed,
    )

    # Materialize bridge-compatible rows (legacy + modeled fields)
    materialized = materialize_rows(
        predictions,
        legacy_rows=legacy_engine,
        prediction_year=args.prediction_year,
        model_version=MODEL_VERSION,
        rule_version=RULE_VERSION,
        quota_source="approved_2026_residency_split",
        applicant_pool_source="public_historical_proxy",
    )

    # Carry draw_pool/hunt_type through for downstream research filters and auditing.
    pred_index = {}
    for p in predictions:
        pred_index[(p["hunt_code"], p["residency"], int(p["points"]))] = p

    for r in materialized:
        key = (clean(r.get("hunt_code")).upper(), clean(r.get("residency")), to_int(r.get("points"), 0))
        src = pred_index.get(key, {})
        r["draw_pool"] = clean(src.get("draw_pool")) or clean(r.get("draw_pool")) or "standard"
        r["hunt_type"] = clean(src.get("hunt_type")) or clean(r.get("hunt_type"))

    predictions_path = out_dir / f"predictive_bonus_engine_{args.prediction_year}.predictions.csv"
    materialized_path = out_dir / f"predictive_bonus_engine_{args.prediction_year}.materialized.csv"
    audit_path = out_dir / f"predictive_bonus_engine_{args.prediction_year}.audit.csv"

    # Write raw predictions
    pred_headers = [
        "draw_year", "hunt_code", "hunt_type", "draw_pool", "residency", "points",
        "p_draw_mean", "p_draw_p10", "p_draw_p50", "p_draw_p90",
        "p_reserved_mean", "p_random_mean", "p_max_pool_mean", "p_preference_mean", "p_youth_mean",
        "expected_cutoff_points", "cutoff_bucket_probability", "guaranteed_probability",
        "point_creep_1yr", "point_creep_3yr", "quota_source", "applicant_pool_source",
        "quota_source_status", "quota_source_year", "quota_source_file",
        "quota_2026_total", "quota_2026_max_pool", "quota_2026_random_pool",
        "permit_allotment_2026_res", "permit_allotment_2026_nr", "permit_allotment_2026_total",
        "permit_allotment_2026_source", "permit_allotment_2026_source_file", "permit_allotment_2026_status",
        "projected_2026_max_cutoff_point", "projected_2026_random_pool_start_point",
        "is_2026_max_point_pool", "is_2026_mixed_cutoff", "is_2026_random_pool",
        "model_version", "rule_version", "data_cutoff_date", "data_quality_grade",
        "reason_codes", "display_odds_pct", "status", "point_pool_zone",
        "applicant_rollover_source_year", "retention_rate_raw", "retention_rate_smoothed",
        "rollover_rule", "rollover_cutoff_structure", "rollover_mixed_cutoff_point", "rollover_anchor_next_point",
        "structure_retention_rate_raw", "structure_retention_rate_smoothed", "structure_retention_prior",
        "structure_retention_matched_years", "structure_retention_unsuccessful_total",
        "forecast_applicants_at_level", "forecast_applicants_above", "rolled_forward_total_applicants",
    ]
    write_csv(predictions_path, pred_headers, predictions)

    # Write bridge materialized CSV (legacy+modeled)
    write_materialized_csv(materialized_path, materialized)

    # Write audit
    audit_headers = [
        "hunt_code", "hunt_type", "hunt_kind", "draw_pool", "residency", "prediction_year",
        "quota_residency", "reserved_quota", "random_quota", "quota_source_status", "quota_source_file",
        "permit_allotment_2026_source", "reserved_fraction",
        "applicant_rollover_source_year", "retention_rate_raw", "retention_rate_smoothed",
        "rollover_rule", "rollover_cutoff_structure", "rollover_mixed_cutoff_point", "rollover_anchor_next_point",
        "structure_retention_rate_raw", "structure_retention_rate_smoothed", "structure_retention_prior",
        "structure_retention_matched_years", "structure_retention_unsuccessful_total",
        "rolled_forward_total_applicants", "rolled_forward_unsuccessful_applicants", "lower_point_additions",
        "points_modeled", "expected_cutoff_points", "iterations",
    ]
    write_csv(audit_path, audit_headers, audit)

    print(f"predictions: {predictions_path}")
    print(f"materialized: {materialized_path}")
    print(f"audit: {audit_path}")
    print(f"rows_predictions: {len(predictions)}")
    print(f"rows_materialized: {len(materialized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
