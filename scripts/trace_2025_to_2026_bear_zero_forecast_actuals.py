#!/usr/bin/env python3
"""Trace 2025→2026 Bear zero-forecast/positive-actual scoring rows.

This is a read-only diagnostic.  It distinguishes an actual Bear-engine
forecast from the source-backed roll-forward fallback before attributing a
zero probability to cohort behavior.  The fallback is deliberately not a
simulated Bear probability and therefore must not be treated as one.
"""

from __future__ import annotations

import csv
import json
import argparse
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
DEFAULT_AUDIT_ROOT = ROOT / "audits" / "historical_adjacent_bear_year_resolution_repair_20260902" / "2025_to_2026"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: object) -> float:
    try:
        return float(str(value or "").strip())
    except ValueError:
        return 0.0


def source_lane_counts(row: dict[str, str] | None, residency: str) -> dict[str, int] | None:
    """Read the verified 2025 residency lane from its combined canonical row."""

    if row is None:
        return None
    prefix = "resident" if residency == "Resident" else "nonresident"
    eligible = number(row.get(f"{prefix}_eligible_applicants"))
    bonus = number(row.get(f"{prefix}_bonus_permits"))
    regular = number(row.get(f"{prefix}_regular_permits"))
    total = number(row.get(f"{prefix}_total_permits"))
    return {
        "eligible_applicants": int(eligible),
        "bonus_permits": int(bonus),
        "regular_permits": int(regular),
        "total_permits": int(total),
        "unsuccessful_applicants": max(0, int(eligible - bonus - regular)),
    }


def trace_category(
    forecast: dict[str, str] | None,
    target_points: int,
    prior_lane: dict[str, int] | None,
) -> tuple[str, str]:
    """Return one of the four approved diagnostic categories and evidence."""

    if forecast is None:
        return "HUNT_CODE_OR_SUBTYPE_TRANSITION", "No matching Bear forecast identity was emitted."

    if forecast.get("model_strategy") != "bear_bonus_phase8":
        return (
            "RESIDENCY_SOURCE_POOL_MISMATCH",
            "The score used a source-backed roll-forward fallback, not a Bear-engine probability; the verified 2025 residency ladder was unavailable to the engine.",
        )

    history_code = (forecast.get("history_hunt_code") or "").strip().upper()
    hunt_code = (forecast.get("hunt_code") or "").strip().upper()
    if history_code and history_code != hunt_code:
        return "HUNT_CODE_OR_SUBTYPE_TRANSITION", "The engine used an explicit historical hunt-code alias."

    flags = set((forecast.get("data_quality_flags") or "").split("|"))
    if "TOTAL_SCOPE_HISTORY_USED_FOR_RESIDENCY" in flags:
        return (
            "RESIDENCY_SOURCE_POOL_MISMATCH",
            "The Bear engine had only combined-residency history and could not establish a lane-specific applicant stack.",
        )

    if target_points == 0:
        return "UNSUPPORTED_NEW_ENTRANT", "A point-zero entrant has no prior point rung to carry forward."
    if prior_lane is None:
        return "UNSUPPORTED_NEW_ENTRANT", "The official 2025 source ladder has no same-code residency lane at the required prior point rung."
    if prior_lane["unsuccessful_applicants"] == 0:
        return (
            "UNSUPPORTED_NEW_ENTRANT",
            "The official prior-point lane had no unsuccessful applicants to carry forward; a 2026 applicant at this point is a new/returning condition not proven by the source ladder.",
        )
    return (
        "MISSING_HISTORICAL_RUNG_CARRY_FORWARD",
        "The verified 2025 prior-point residency lane had unsuccessful applicants, but the Bear engine emitted zero probability at their carried-forward target rung.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=DEFAULT_AUDIT_ROOT,
        help="fold root that contains prediction_phase and comparison_phase",
    )
    args = parser.parse_args()
    audit_root = args.audit_root.resolve()
    rowlevel = audit_root / "comparison_phase" / "draw_line_aware_prediction_vs_actual_rowlevel.csv"
    forecast_path = audit_root / "prediction_phase" / "family_predictions.csv"
    output = audit_root / "comparison_phase" / "zero_forecast_positive_actual_trace.csv"
    summary_path = audit_root / "comparison_phase" / "zero_forecast_positive_actual_trace_summary.json"

    rowlevel_rows = read_csv(rowlevel)
    forecast_rows = [
        row
        for row in read_csv(forecast_path)
        if row.get("family") == "bonus_bear" and (row.get("p_draw") or "").strip()
    ]
    # Prefer the actual Bear engine over its intentionally separate source
    # fallback when both records share an identity.
    forecasts: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in forecast_rows:
        key = (row.get("hunt_code", ""), row.get("residency", ""), row.get("points", ""))
        previous = forecasts.get(key)
        if previous is None or row.get("model_strategy") == "bear_bonus_phase8":
            forecasts[key] = row

    canonical_bear_rows = [
        row
        for row in read_csv(CANONICAL)
        if row.get("record_type") == "point_level_draw_result" and (row.get("hunt_code") or "").startswith("BR")
    ]
    canonical_by_key = {
        (row.get("hunt_code", ""), row.get("points", "")): row
        for row in canonical_bear_rows
        if row.get("metric_scope") == "total"
    }
    verified_2025_lane_rows = sum(
        1 for row in canonical_bear_rows if row.get("qa_status") == "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL"
    )

    traced: list[dict[str, str]] = []
    for actual in rowlevel_rows:
        if actual.get("scoring_decision") != "score_probability":
            continue
        if number(actual.get("predicted_probability")) > 0 or number(actual.get("actual_probability")) <= 0:
            continue
        key = (actual.get("hunt_code", ""), actual.get("residency", ""), actual.get("points", ""))
        forecast = forecasts.get(key)
        target_points = int(number(actual.get("points")))
        prior_points = target_points - 1 if target_points > 0 else None
        prior_source = None if prior_points is None else canonical_by_key.get((actual.get("hunt_code", ""), str(prior_points)))
        prior_lane = source_lane_counts(prior_source, actual.get("residency", ""))
        category, evidence = trace_category(forecast, target_points, prior_lane)
        traced.append(
            {
                "hunt_code": actual.get("hunt_code", ""),
                "residency": actual.get("residency", ""),
                "points": actual.get("points", ""),
                "predicted_probability": actual.get("predicted_probability", ""),
                "actual_probability": actual.get("actual_probability", ""),
                "actual_eligible_applicants": actual.get("actual_eligible_applicants", ""),
                "point_relation_to_draw_line": actual.get("point_relation_to_draw_line", ""),
                "classification": category,
                "classification_evidence": evidence,
                "forecast_model_strategy": "" if forecast is None else forecast.get("model_strategy", ""),
                "forecast_algorithm_status": "" if forecast is None else forecast.get("algorithm_status", ""),
                "history_hunt_code": "" if forecast is None else forecast.get("history_hunt_code", ""),
                "bear_draw_subtype": "" if forecast is None else forecast.get("bear_draw_subtype", ""),
                "forecast_data_quality_flags": "" if forecast is None else forecast.get("data_quality_flags", ""),
                "source_prior_points": "" if prior_points is None else str(prior_points),
                "source_prior_eligible_applicants": "" if prior_lane is None else str(prior_lane["eligible_applicants"]),
                "source_prior_bonus_permits": "" if prior_lane is None else str(prior_lane["bonus_permits"]),
                "source_prior_regular_permits": "" if prior_lane is None else str(prior_lane["regular_permits"]),
                "source_prior_total_permits": "" if prior_lane is None else str(prior_lane["total_permits"]),
                "source_prior_unsuccessful_applicants": "" if prior_lane is None else str(prior_lane["unsuccessful_applicants"]),
            }
        )

    fieldnames = list(traced[0]) if traced else ["classification"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(traced)

    unique_keys = {(row["hunt_code"], row["residency"], row["points"]) for row in traced}
    summary = {
        "purpose": "read_only_2025_to_2026_bear_zero_forecast_positive_actual_trace",
        "audit_root": str(audit_root.relative_to(ROOT)).replace("\\", "/"),
        "input_row_occurrences": len(traced),
        "unique_score_keys": len(unique_keys),
        "duplicate_score_occurrences": len(traced) - len(unique_keys),
        "classification_counts": dict(sorted(Counter(row["classification"] for row in traced).items())),
        "canonical_2025_bear_point_rows": len(canonical_bear_rows),
        "canonical_2025_verified_pdf_residency_lane_rows": verified_2025_lane_rows,
        "conclusion": "The output classifies source-only evidence; it does not alter canonical truth, probabilities, runtime artifacts, or deployment state.",
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
