"""Formal orchestration helpers for Utah bonus predictive outputs."""

from __future__ import annotations

import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields

from .split import split_utah_bonus_permits


REPO = Path(__file__).resolve().parents[2]
RUNTIME_TRUTH_SCRIPT = REPO / "scripts" / "build_runtime_draw_feed_v2.py"
PREDICTIVE_BUILD_SCRIPT = REPO / "scripts" / "build_predictive_bonus_engine_v1.py"
OFFICIAL_2026_QUOTA_SOURCE_FILE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"


def to_int(value: object) -> int:
    try:
        if value is None or str(value).strip() == "":
            return 0
        return int(float(str(value).strip()))
    except Exception:
        return 0


def to_float(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip())
    except Exception:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_nonempty(*values: object) -> object:
    for value in values:
        if value is None:
            continue
        if str(value).strip():
            return value
    return ""


DEPRECATED_QUOTA_REASON_CODES = {
    "RAC_CURRENT_YEAR_ALLOTMENT_USED",
    "DATABASE_2026_PERMITS_USED",
}


def normalize_quota_reason_codes(value: object) -> str:
    seen: list[str] = []
    for raw in str(value or "").replace(";", "|").split("|"):
        code = raw.strip()
        if not code or code in DEPRECATED_QUOTA_REASON_CODES or code in seen:
            continue
        seen.append(code)
    return "|".join(seen)


def probability_component(row: dict[str, str], field: str, fallback: float | None) -> str:
    value = to_float(row.get(field))
    if value is None:
        value = fallback
    return "" if value is None else f"{value:.6f}"


def build_truth_indexes(
    truth_rows: list[dict[str, str]],
) -> tuple[
    dict[tuple[str, str, str], dict[str, int]],
    dict[tuple[str, str, str], dict[int, dict[str, int]]],
    dict[str, dict[str, str]],
]:
    permits: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"public": 0, "bonus": 0, "regular": 0})
    ladders: dict[tuple[str, str, str], dict[int, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0})
    )
    meta: dict[str, dict[str, str]] = {}
    for row in truth_rows:
        hunt_code = (row.get("hunt_code") or "").upper().strip()
        if not hunt_code:
            continue
        year = str(row.get("year") or "").strip()
        residency = (row.get("residency") or "").strip()
        points_text = (row.get("points") or "").strip()
        eligible = to_int(row.get("eligible_applicants"))
        bonus = to_int(row.get("bonus_permits"))
        regular = to_int(row.get("regular_permits"))
        total = to_int(row.get("total_permits"))

        permits[(year, hunt_code, residency)]["public"] += total
        permits[(year, hunt_code, residency)]["bonus"] += bonus
        permits[(year, hunt_code, residency)]["regular"] += regular

        if points_text.isdigit():
            points = int(points_text)
            ladders[(year, hunt_code, residency)][points]["eligible"] += eligible
            ladders[(year, hunt_code, residency)][points]["bonus"] += bonus
            ladders[(year, hunt_code, residency)][points]["regular"] += regular
            ladders[(year, hunt_code, residency)][points]["total"] += total

        if hunt_code not in meta:
            meta[hunt_code] = {
                "hunt_name": row.get("hunt_name", ""),
                "species": row.get("species", ""),
                "hunt_type": row.get("hunt_type", ""),
            }
    return permits, ladders, meta


def build_above_index(ladders: dict[tuple[str, str, str], dict[int, dict[str, int]]]) -> dict[tuple[str, str, str], dict[int, int]]:
    index: dict[tuple[str, str, str], dict[int, int]] = {}
    for key, point_map in ladders.items():
        running = 0
        above_for_points: dict[int, int] = {}
        for points in sorted(point_map.keys(), reverse=True):
            above_for_points[points] = running
            running += point_map[points]["eligible"]
        index[key] = above_for_points
    return index


def normalize_history_years(history_years: str | list[int] | list[str]) -> list[int]:
    if isinstance(history_years, str):
        tokens = [token.strip() for token in history_years.split(",") if token.strip()]
    else:
        tokens = [str(token).strip() for token in history_years if str(token).strip()]
    return [int(token) for token in tokens]


def run_official_forecast_build(prediction_year: int, out_dir: Path) -> dict[str, Path]:
    subprocess.run([sys.executable, str(RUNTIME_TRUTH_SCRIPT)], cwd=REPO, check=True)
    subprocess.run(
        [
            sys.executable,
            str(PREDICTIVE_BUILD_SCRIPT),
            "--prediction-year",
            str(prediction_year),
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO,
        check=True,
    )
    return {
        "prediction_rows": out_dir / f"predictive_bonus_engine_{prediction_year}.predictions.csv",
        "materialized_rows": out_dir / f"predictive_bonus_engine_{prediction_year}.materialized.csv",
        "audit_rows": out_dir / f"predictive_bonus_engine_{prediction_year}.audit.csv",
    }


def materialize_prediction_rows(
    ml_rows: list[dict[str, str]],
    permits: dict[tuple[str, str, str], dict[str, int]],
    ladders: dict[tuple[str, str, str], dict[int, dict[str, int]]],
    above_index: dict[tuple[str, str, str], dict[int, int]],
    meta: dict[str, dict[str, str]],
    forecast_year: int,
    source_years_used: str,
    earliest_source_year: int,
    latest_source_year: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    prediction_rows: list[dict[str, object]] = []
    successor_rows: list[dict[str, object]] = []
    source_year_count = len(source_years_used.split(",")) if source_years_used else 0
    prior_year = forecast_year - 1
    forecast_year_text = str(forecast_year)
    prior_year_text = str(prior_year)

    for row in ml_rows:
        hunt_code = (row.get("hunt_code") or "").upper().strip()
        residency = (row.get("residency") or "").strip()
        points_text = (row.get("points") or "").strip()
        if not hunt_code or not points_text.isdigit():
            continue
        points = int(points_text)

        prior = permits.get((prior_year_text, hunt_code, residency), {"public": 0, "bonus": 0, "regular": 0})
        forecast = permits.get((forecast_year_text, hunt_code, residency))
        row_quota_text = first_nonempty(row.get("quota_2026_total"), row.get("public_permits_2026"))
        row_quota_total = to_int(row_quota_text) if row_quota_text != "" else None
        public_permits_2026 = row_quota_total if row_quota_total is not None else (forecast["public"] if forecast and forecast["public"] > 0 else prior["public"])
        split = split_utah_bonus_permits(public_permits_2026)
        max_pool_text = first_nonempty(row.get("quota_2026_max_pool"))
        random_pool_text = first_nonempty(row.get("quota_2026_random_pool"))
        max_point_permits_2026 = to_int(max_pool_text) if max_pool_text != "" else split.maxPointPermits
        random_permits_2026 = to_int(random_pool_text) if random_pool_text != "" else split.randomPermits
        if forecast_year <= latest_source_year and forecast and (forecast["bonus"] > 0 or forecast["regular"] > 0):
            max_point_permits_2026 = forecast["bonus"]
            random_permits_2026 = forecast["regular"]
        projected_cutoff = row.get("projected_2026_max_cutoff_point", "")
        projected_random_start = row.get("projected_2026_random_pool_start_point", "")
        point_pool_zone = row.get("point_pool_zone", "")

        ladder_key_2026 = (forecast_year_text, hunt_code, residency)
        ladder_key_2025 = (prior_year_text, hunt_code, residency)
        # Only use forecast-year ladder rows when that year is part of the approved historical source set.
        chosen_key = ladder_key_2026 if forecast_year <= latest_source_year and ladder_key_2026 in ladders else ladder_key_2025
        forecast_applicants_at_level_text = str(row.get("forecast_applicants_at_level", "")).strip()
        forecast_applicants_above_text = str(row.get("forecast_applicants_above", "")).strip()
        applicants_at_level = to_int(forecast_applicants_at_level_text) if forecast_applicants_at_level_text else ladders.get(chosen_key, {}).get(points, {}).get("eligible", 0)
        applicants_above = to_int(forecast_applicants_above_text) if forecast_applicants_above_text else above_index.get(chosen_key, {}).get(points, 0)

        p_bonus_pool = to_float(row.get("p_bonus_pool"))
        if p_bonus_pool is None:
            p_bonus_pool = to_float(row.get("p_reserved_mean"))
        p_random_pool = to_float(row.get("p_random_pool"))
        if p_random_pool is None:
            p_random_pool = to_float(row.get("p_random_mean"))
        p_draw = to_float(row.get("p_draw"))
        if p_draw is None:
            p_draw = to_float(row.get("p_draw_mean"))
        p_draw_pct = to_float(row.get("p_draw_pct"))
        if p_draw_pct is None:
            p_draw_pct = to_float(row.get("display_odds_pct"))
        p_draw_pct_value = p_draw_pct if p_draw_pct is not None else (p_draw * 100.0 if p_draw is not None else None)
        p_prior_year_baseline = probability_component(row, "p_prior_year_baseline", p_draw)
        p_quota_adjusted = probability_component(row, "p_quota_adjusted", p_draw)
        p_rollover_adjusted = probability_component(row, "p_rollover_adjusted", p_draw)
        p_harvest_adjusted = probability_component(row, "p_harvest_adjusted", p_draw)
        status = row.get("status", "") or ("RANDOM ONLY" if max_point_permits_2026 == 0 and random_permits_2026 > 0 else "")
        reason_codes = normalize_quota_reason_codes(row.get("reason_codes", ""))
        if "OFFICIAL_2026_QUOTA_USED" not in str(reason_codes):
            reason_codes = f"{reason_codes}|OFFICIAL_2026_QUOTA_USED".strip("|")

        prediction_row = {
            "model_version": row.get("model_version", ""),
            "rule_version": row.get("rule_version", ""),
            "year": row.get("year", forecast_year_text),
            "forecast_year": row.get("year", forecast_year_text),
            "hunt_code": hunt_code,
            "hunt_name": meta.get(hunt_code, {}).get("hunt_name", ""),
            "species": meta.get(hunt_code, {}).get("species", ""),
            "hunt_type": row.get("hunt_type", "") or meta.get(hunt_code, {}).get("hunt_type", ""),
            "residency": residency,
            "points": points_text,
            "draw_pool": row.get("draw_pool", "standard"),
            "public_permits_2025": prior["public"],
            "public_permits_2026": public_permits_2026,
            "max_point_permits_2025": prior["bonus"],
            "max_point_permits_2026": max_point_permits_2026,
            "random_permits_2025": prior["regular"],
            "random_permits_2026": random_permits_2026,
            "guaranteed_at_2025": "",
            "guaranteed_at_2026": "",
            "applicants_above": applicants_above,
            "applicants_at_level": applicants_at_level,
            "p_prior_year_baseline": p_prior_year_baseline,
            "p_quota_adjusted": p_quota_adjusted,
            "p_rollover_adjusted": p_rollover_adjusted,
            "p_harvest_adjusted": p_harvest_adjusted,
            "p_draw_mean": "" if p_draw is None else f"{p_draw:.6f}",
            "p_max_pool_mean": "" if p_bonus_pool is None else f"{p_bonus_pool:.6f}",
            "p_random_mean": "" if p_random_pool is None else f"{p_random_pool:.6f}",
            "p_bonus_pool": "" if p_bonus_pool is None else f"{p_bonus_pool:.6f}",
            "p_random_pool": "" if p_random_pool is None else f"{p_random_pool:.6f}",
            "p_draw": "" if p_draw is None else f"{p_draw:.6f}",
            "p_bonus_pool_pct": "" if p_bonus_pool is None else f"{p_bonus_pool * 100.0:.3f}",
            "p_random_pool_pct": "" if p_random_pool is None else f"{p_random_pool * 100.0:.3f}",
            "p_draw_pct": "" if p_draw_pct_value is None else f"{p_draw_pct_value:.3f}",
            "random_draw_odds_2026": row.get("random_draw_odds_2026", "") or row.get("random_draw_projection_2026", ""),
            "gap": "",
            "delta_gap": "",
            "status": status,
            "trend": row.get("trend", ""),
            "draw_outlook": row.get("draw_outlook", ""),
            "point_pool_zone": point_pool_zone,
            "quota_source_status": row.get("quota_source_status", "official"),
            "quota_source_year": row.get("quota_source_year", forecast_year_text) or forecast_year_text,
            "quota_source_file": row.get("quota_source_file", OFFICIAL_2026_QUOTA_SOURCE_FILE) or OFFICIAL_2026_QUOTA_SOURCE_FILE,
            "quota_2026_total": public_permits_2026,
            "quota_2026_max_pool": max_point_permits_2026,
            "quota_2026_random_pool": random_permits_2026,
            "permit_allotment_2026_res": row.get("permit_allotment_2026_res", ""),
            "permit_allotment_2026_nr": row.get("permit_allotment_2026_nr", ""),
            "permit_allotment_2026_total": row.get("permit_allotment_2026_total", ""),
            "permit_allotment_2026_source": row.get("permit_allotment_2026_source", ""),
            "permit_allotment_2026_source_file": row.get("permit_allotment_2026_source_file", ""),
            "permit_allotment_2026_status": row.get("permit_allotment_2026_status", ""),
            "projected_2026_max_cutoff_point": projected_cutoff,
            "projected_2026_random_pool_start_point": projected_random_start,
            "is_2026_max_point_pool": row.get("is_2026_max_point_pool", str(point_pool_zone in {"max_pool_guaranteed", "max_pool_cutoff_mixed"})),
            "is_2026_mixed_cutoff": row.get("is_2026_mixed_cutoff", str(point_pool_zone == "max_pool_cutoff_mixed")),
            "is_2026_random_pool": row.get("is_2026_random_pool", str(point_pool_zone == "random_pool")),
            "data_cutoff_date": row.get("data_cutoff_date", ""),
            "reason_codes": reason_codes,
            "applicant_rollover_source_year": row.get("applicant_rollover_source_year", ""),
            "retention_rate_raw": row.get("retention_rate_raw", ""),
            "retention_rate_smoothed": row.get("retention_rate_smoothed", ""),
            "rollover_rule": row.get("rollover_rule", ""),
            "rollover_cutoff_structure": row.get("rollover_cutoff_structure", ""),
            "rollover_mixed_cutoff_point": row.get("rollover_mixed_cutoff_point", ""),
            "rollover_anchor_next_point": row.get("rollover_anchor_next_point", ""),
            "structure_retention_rate_raw": row.get("structure_retention_rate_raw", ""),
            "structure_retention_rate_smoothed": row.get("structure_retention_rate_smoothed", ""),
            "structure_retention_prior": row.get("structure_retention_prior", ""),
            "structure_retention_matched_years": row.get("structure_retention_matched_years", ""),
            "structure_retention_unsuccessful_total": row.get("structure_retention_unsuccessful_total", ""),
            "forecast_applicants_at_level": row.get("forecast_applicants_at_level", ""),
            "forecast_applicants_above": row.get("forecast_applicants_above", ""),
            "rolled_forward_total_applicants": row.get("rolled_forward_total_applicants", ""),
            "source_years_used": source_years_used,
            "source_year_count": source_year_count,
            "latest_source_year": latest_source_year,
            "earliest_source_year": earliest_source_year,
            "source_dataset": "predictive",
        }
        prediction_row = sanitize_modeled_probability_fields(prediction_row)
        prediction_rows.append(prediction_row)
        successor_rows.append(
            {
                "year": prediction_row["year"],
                "model_version": prediction_row["model_version"],
                "rule_version": prediction_row["rule_version"],
                "hunt_code": hunt_code,
                "hunt_name": prediction_row["hunt_name"],
                "species": prediction_row["species"],
                "hunt_type": prediction_row["hunt_type"],
                "residency": residency,
                "points": points_text,
                "draw_pool": prediction_row["draw_pool"],
                "public_permits_2025": prior["public"],
                "public_permits_2026": public_permits_2026,
                "max_point_permits_2025": prior["bonus"],
                "max_point_permits_2026": max_point_permits_2026,
                "random_permits_2025": prior["regular"],
                "random_permits_2026": random_permits_2026,
                "applicants_above": applicants_above,
                "applicants_at_level": applicants_at_level,
                "p_prior_year_baseline": prediction_row["p_prior_year_baseline"],
                "p_quota_adjusted": prediction_row["p_quota_adjusted"],
                "p_rollover_adjusted": prediction_row["p_rollover_adjusted"],
                "p_harvest_adjusted": prediction_row["p_harvest_adjusted"],
                "p_bonus_pool": prediction_row["p_bonus_pool"],
                "p_random_pool": prediction_row["p_random_pool"],
                "p_draw_mean": prediction_row["p_draw_mean"],
                "p_max_pool_mean": prediction_row["p_max_pool_mean"],
                "p_random_mean": prediction_row["p_random_mean"],
                "p_draw": prediction_row["p_draw"],
                "p_draw_pct": prediction_row["p_draw_pct"],
                "point_pool_zone": prediction_row["point_pool_zone"],
                "quota_source_status": prediction_row["quota_source_status"],
                "quota_source_year": prediction_row["quota_source_year"],
                "quota_source_file": prediction_row["quota_source_file"],
                "quota_2026_total": prediction_row["quota_2026_total"],
                "quota_2026_max_pool": prediction_row["quota_2026_max_pool"],
                "quota_2026_random_pool": prediction_row["quota_2026_random_pool"],
                "permit_allotment_2026_res": prediction_row["permit_allotment_2026_res"],
                "permit_allotment_2026_nr": prediction_row["permit_allotment_2026_nr"],
                "permit_allotment_2026_total": prediction_row["permit_allotment_2026_total"],
                "permit_allotment_2026_source": prediction_row["permit_allotment_2026_source"],
                "permit_allotment_2026_source_file": prediction_row["permit_allotment_2026_source_file"],
                "permit_allotment_2026_status": prediction_row["permit_allotment_2026_status"],
                "projected_2026_max_cutoff_point": prediction_row["projected_2026_max_cutoff_point"],
                "projected_2026_random_pool_start_point": prediction_row["projected_2026_random_pool_start_point"],
                "is_2026_max_point_pool": prediction_row["is_2026_max_point_pool"],
                "is_2026_mixed_cutoff": prediction_row["is_2026_mixed_cutoff"],
                "is_2026_random_pool": prediction_row["is_2026_random_pool"],
                "data_cutoff_date": prediction_row["data_cutoff_date"],
                "reason_codes": prediction_row["reason_codes"],
                "applicant_rollover_source_year": prediction_row["applicant_rollover_source_year"],
                "retention_rate_raw": prediction_row["retention_rate_raw"],
                "retention_rate_smoothed": prediction_row["retention_rate_smoothed"],
                "rollover_rule": prediction_row["rollover_rule"],
                "rollover_cutoff_structure": prediction_row["rollover_cutoff_structure"],
                "rollover_mixed_cutoff_point": prediction_row["rollover_mixed_cutoff_point"],
                "rollover_anchor_next_point": prediction_row["rollover_anchor_next_point"],
                "structure_retention_rate_raw": prediction_row["structure_retention_rate_raw"],
                "structure_retention_rate_smoothed": prediction_row["structure_retention_rate_smoothed"],
                "structure_retention_prior": prediction_row["structure_retention_prior"],
                "structure_retention_matched_years": prediction_row["structure_retention_matched_years"],
                "structure_retention_unsuccessful_total": prediction_row["structure_retention_unsuccessful_total"],
                "forecast_applicants_at_level": prediction_row["forecast_applicants_at_level"],
                "forecast_applicants_above": prediction_row["forecast_applicants_above"],
                "rolled_forward_total_applicants": prediction_row["rolled_forward_total_applicants"],
                "status": status,
                "trend": prediction_row["trend"],
                "draw_outlook": prediction_row["draw_outlook"],
                "source_years_used": source_years_used,
                "source_year_count": source_year_count,
                "latest_source_year": latest_source_year,
                "earliest_source_year": earliest_source_year,
                "draw_system_type": prediction_row["draw_system_type"],
                "algorithm_status": prediction_row["algorithm_status"],
                "target_scope": prediction_row["target_scope"],
                "modeled_by_engine": prediction_row["modeled_by_engine"],
                "reason": prediction_row["reason"],
            }
        )
    return prediction_rows, successor_rows
