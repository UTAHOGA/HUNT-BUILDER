#!/usr/bin/env python3
"""Audit the post-family effect of prior random/weighted winners.

The family engines already remove prior winners before rolling applicant
cohorts forward. This audit reproduces the legacy post-family blend and
compares it with the candidate rule that withholds a prior-year success-rate
baseline when a bonus-point row had a random/weighted winner.

It reads frozen prediction and official actual files and writes only to the
requested audit directory. It never changes truth, runtime, or hosted data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah_predictive_mixed.harvest_features import harvest_adjusted_probability
from engine.utah_predictive_mixed.materialize import (
    FAMILY_ENGINE_PROBABILITY_STATUSES,
    PASSTHROUGH_PROBABILITY_STATUSES,
    mixed_row,
)
from engine.utah_predictive_mixed.mixed_probability import blend_probability
from engine.utah_predictive_mixed.models import BlendWeights
from engine.utah_predictive_mixed.prior_year import prior_year_baseline, to_float
from engine.utah_predictive_mixed.quota import (
    is_no_published_permit_authority,
    quota_adjusted_probability,
    quota_for_row,
)
from engine.utah_predictive_mixed.rollover import rollover_probability_from_pools


DEFAULT_PREDICTIONS = (
    ROOT
    / "audits"
    / "prediction_release_candidates"
    / "certified_core_20260909_33875"
    / "frozen"
    / "ml_draw_predictions_v1.csv"
)
DEFAULT_ACTUAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def expand_actual_lanes(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    lanes: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        if str(row.get("draw_design", "")).strip().upper() == "REFERENCE_ONLY":
            continue
        for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            lane = {
                "hunt_code": row.get("hunt_code", ""),
                "residency": residency,
                "points": row.get("points", ""),
                "eligible_applicants": row.get(f"{prefix}_eligible_applicants", ""),
                "bonus_permits": row.get(f"{prefix}_bonus_permits", ""),
                "regular_permits": row.get(f"{prefix}_regular_permits", ""),
                "total_permits": row.get(f"{prefix}_total_permits", ""),
                "success_ratio": row.get(f"{prefix}_success_ratio", ""),
            }
            lanes[(lane["hunt_code"], lane["residency"], lane["points"])] = lane
    return lanes


def legacy_post_family_probability(
    row: dict[str, str], prior: dict[str, str], weights: BlendWeights
) -> float | None:
    """Reproduce the legacy blend before random-winner suppression."""

    p_prior, prior_fields, _ = prior_year_baseline(prior)
    quota_fields, quota_reasons = quota_for_row(row)
    total_only_no_lane_quota = "NO_RESIDENCY_LANE_QUOTA" in quota_reasons
    no_published_no_quota = "NO_PUBLISHED_PERMIT_AUTHORITY" in quota_reasons
    current_quota = "" if total_only_no_lane_quota else quota_fields.get("quota_2026_total")
    if str(current_quota or "").strip() == "" and not total_only_no_lane_quota:
        current_quota = row.get("public_permits_2026")
    if no_published_no_quota or total_only_no_lane_quota:
        p_quota = None
    else:
        p_quota, _, _ = quota_adjusted_probability(
            p_prior,
            row.get("public_permits_2025") or prior_fields.get("prior_year_total_permits"),
            current_quota,
        )

    p_rollover, _ = rollover_probability_from_pools(
        row.get("p_max_pool_mean"), row.get("p_random_mean"), row.get("p_preference_draw")
    )
    p_family = to_float(row.get("p_draw") or row.get("p_draw_mean"))
    status = row.get("algorithm_status", "")
    if p_rollover is None and status in FAMILY_ENGINE_PROBABILITY_STATUSES and p_family is not None:
        p_rollover = p_family
    if status in PASSTHROUGH_PROBABILITY_STATUSES:
        p_rollover = to_float(row.get("p_sportsman_draw") or row.get("p_draw") or row.get("p_draw_mean"))
    p_harvest, _ = harvest_adjusted_probability(p_rollover, {})
    if no_published_no_quota or is_no_published_permit_authority(row):
        p_prior = p_quota = p_rollover = p_harvest = None
    p_draw, _ = blend_probability(p_prior, p_quota, p_rollover, p_harvest, weights)
    return p_draw


def fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.9f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--actual", type=Path, default=DEFAULT_ACTUAL)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    predictions = args.predictions if args.predictions.is_absolute() else ROOT / args.predictions
    actual = args.actual if args.actual.is_absolute() else ROOT / args.actual
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    prediction_rows = read_rows(predictions)
    actual_lanes = expand_actual_lanes(read_rows(actual))
    weights = BlendWeights()
    audit_rows: list[dict[str, str]] = []
    matched_rows = 0

    for row in prediction_rows:
        prior = actual_lanes.get((row.get("hunt_code", ""), row.get("residency", ""), row.get("points", "")))
        if prior is None:
            continue
        matched_rows += 1
        corrected = mixed_row(row, prior, None, weights)
        reason_codes = corrected.get("reason_codes", "")
        if "PRIOR_RANDOM_WINNER_BASELINE_WITHHELD_FROM_CURRENT_FORECAST" not in reason_codes:
            continue
        legacy_probability = legacy_post_family_probability(row, prior, weights)
        corrected_probability = to_float(corrected.get("p_draw"))
        family_probability = to_float(row.get("p_draw") or row.get("p_draw_mean"))
        delta = None
        ratio = None
        if legacy_probability is not None and corrected_probability is not None:
            delta = legacy_probability - corrected_probability
            if corrected_probability > 0:
                ratio = legacy_probability / corrected_probability
        audit_rows.append(
            {
                "hunt_code": row.get("hunt_code", ""),
                "residency": row.get("residency", ""),
                "points": row.get("points", ""),
                "prediction_certification_design": row.get("prediction_certification_design", ""),
                "prediction_certification_status": row.get("prediction_certification_status", ""),
                "prior_year_applicants": prior.get("eligible_applicants", ""),
                "prior_year_random_weighted_winners": prior.get("regular_permits", ""),
                "family_probability": fmt(family_probability),
                "legacy_post_family_probability": fmt(legacy_probability),
                "corrected_post_family_probability": fmt(corrected_probability),
                "legacy_minus_corrected": fmt(delta),
                "legacy_to_corrected_ratio": fmt(ratio),
                "candidate_reason_code": "PRIOR_RANDOM_WINNER_BASELINE_WITHHELD_FROM_CURRENT_FORECAST",
            }
        )

    fields = list(audit_rows[0]) if audit_rows else [
        "hunt_code",
        "residency",
        "points",
        "prediction_certification_design",
        "prediction_certification_status",
        "prior_year_applicants",
        "prior_year_random_weighted_winners",
        "family_probability",
        "legacy_post_family_probability",
        "corrected_post_family_probability",
        "legacy_minus_corrected",
        "legacy_to_corrected_ratio",
        "candidate_reason_code",
    ]
    csv_path = out_dir / "random_winner_probability_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(audit_rows)

    deltas = [to_float(row["legacy_minus_corrected"]) for row in audit_rows]
    ratios = [to_float(row["legacy_to_corrected_ratio"]) for row in audit_rows]
    valid_deltas = [value for value in deltas if value is not None]
    positive_deltas = [value for value in valid_deltas if value > 0]
    valid_ratios = [value for value in ratios if value is not None]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if audit_rows else "BLOCKED_NO_AFFECTED_ROWS",
        "mode": "READ_ONLY_INPUTS_ISOLATED_AUDIT_OUTPUT",
        "prediction_rows": len(prediction_rows),
        "prediction_rows_matched_to_2025_official_lane": matched_rows,
        "affected_bonus_rows": len(audit_rows),
        "affected_certified_rows": sum(
            row["prediction_certification_status"] == "CERTIFIED" for row in audit_rows
        ),
        "affected_rows_by_residency": dict(Counter(row["residency"] for row in audit_rows)),
        "affected_rows_by_certification_status": dict(
            Counter(row["prediction_certification_status"] for row in audit_rows)
        ),
        "legacy_probability_higher_rows": sum(value > 0 for value in valid_deltas),
        "legacy_probability_lower_rows": sum(value < 0 for value in valid_deltas),
        "legacy_probability_equal_rows": sum(abs(value) <= 1e-12 for value in valid_deltas),
        "maximum_probability_inflation": max(positive_deltas, default=None),
        "median_probability_inflation_among_inflated_rows": (
            median(positive_deltas) if positive_deltas else None
        ),
        "maximum_legacy_to_corrected_ratio": max(valid_ratios, default=None),
        "corrected_probability_matches_family_probability_rows": sum(
            row["corrected_post_family_probability"] == row["family_probability"] for row in audit_rows
        ),
        "comparison_csv": str(csv_path.relative_to(ROOT)),
        "production_writes": [],
    }
    (out_dir / "random_winner_probability_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
