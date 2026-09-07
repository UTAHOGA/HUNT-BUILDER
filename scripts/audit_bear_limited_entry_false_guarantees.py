#!/usr/bin/env python3
"""Audit frozen Bear false guarantees without changing the engine or truth.

The report deliberately keeps public limited-entry Bear hunting and restricted
Bear pursuit draw rows apart.  It only inspects an existing, source-typed
acceptance review plus its exact frozen fold artifacts.  General/unlimited
pursuit availability and harvest-objective availability are not draw odds and
are rejected from the audit population.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


EPSILON = 0.000001
LIMITED_ENTRY_DESIGN = "BEAR_LIMITED_ENTRY_HUNT_BONUS"
RESTRICTED_PURSUIT_DESIGN = "BEAR_RESTRICTED_PURSUIT_BONUS"
NON_DRAW_PURSUIT_SUBTYPES = {
    "UNLIMITED_PURSUIT_PERMIT",
    "HARVEST_OBJECTIVE_AVAILABILITY",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float:
    try:
        return float(clean(value).replace(",", ""))
    except ValueError:
        return 0.0


def point(value: object) -> str:
    raw = clean(value)
    if not raw:
        return ""
    try:
        numeric = float(raw)
    except ValueError:
        return raw
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def is_true(value: object) -> bool:
    return clean(value).casefold() == "true"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def lane_key(row: Mapping[str, object]) -> tuple[str, str]:
    return (clean(row.get("hunt_code")), clean(row.get("residency")).casefold())


def actual_ladder_stats(rows: Iterable[Mapping[str, object]], rung: float) -> dict[str, object]:
    point_rows = [
        row
        for row in rows
        if clean(row.get("row_type") or row.get("record_type")).casefold()
        in {"point_level_draw_result", "point_row"}
    ]
    at_rung = [row for row in point_rows if point(row.get("points")) == point(rung)]
    above = [row for row in point_rows if number(row.get("points")) > rung]
    at_or_above = at_rung + above
    target_total = sum(number(row.get("bonus_permits")) + number(row.get("regular_permits")) for row in point_rows)
    target_successful = sum(number(row.get("bonus_permits")) + number(row.get("regular_permits")) for row in at_or_above)
    return {
        "target_ladder_rows": len(point_rows),
        "target_applicants_at_rung": sum(number(row.get("eligible_applicants")) for row in at_rung),
        "target_successful_at_rung": sum(number(row.get("bonus_permits")) + number(row.get("regular_permits")) for row in at_rung),
        "target_applicants_above_rung": sum(number(row.get("eligible_applicants")) for row in above),
        "target_applicants_at_or_above_rung": sum(number(row.get("eligible_applicants")) for row in at_or_above),
        "target_successful_at_or_above_rung": target_successful,
        "target_unselected_at_or_above_rung": sum(number(row.get("eligible_applicants")) for row in at_or_above) - target_successful,
        "target_bonus_permits": sum(number(row.get("bonus_permits")) for row in point_rows),
        "target_regular_permits": sum(number(row.get("regular_permits")) for row in point_rows),
        "target_total_permits": target_total,
    }


def ladder_position(row: Mapping[str, object]) -> str:
    rung = number(row.get("points"))
    mixed = clean(row.get("mixed_cutoff_point"))
    guaranteed = clean(row.get("lowest_guaranteed_stack_point"))
    if mixed and abs(rung - number(mixed)) < EPSILON:
        return "TARGET_MIXED_CUTOFF"
    if guaranteed and rung >= number(guaranteed):
        return "TARGET_GUARANTEED_STACK"
    return "TARGET_RANDOM_OR_BELOW_CUTOFF"


def forecast_at_row(rows: list[dict[str, str]], line_number: object) -> dict[str, str]:
    try:
        index = int(float(clean(line_number))) - 2  # CSV header is line 1.
    except ValueError as error:
        raise ValueError(f"Invalid frozen forecast row number: {line_number!r}") from error
    if index < 0 or index >= len(rows):
        raise ValueError(f"Frozen forecast row number out of range: {line_number!r}")
    return rows[index]


def compact_group(rows: list[dict[str, object]], fields: tuple[str, ...]) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(clean(row.get(field)) for field in fields)].append(row)
    output: list[dict[str, object]] = []
    for key, members in sorted(groups.items()):
        result = {field: value for field, value in zip(fields, key)}
        result.update(
            {
                "false_guarantee_rows": len(members),
                "mean_target_stack_excess_over_forecast": round(
                    sum(number(row["target_stack_excess_over_forecast"]) for row in members) / len(members), 6
                ),
                "rows_with_target_stack_excess": sum(number(row["target_stack_excess_over_forecast"]) > 0 for row in members),
                "rows_with_zero_target_stack_excess": sum(number(row["target_stack_excess_over_forecast"]) == 0 for row in members),
                "rows_with_negative_target_stack_excess": sum(number(row["target_stack_excess_over_forecast"]) < 0 for row in members),
                "matched_target_permit_rows": sum(row["permit_alignment"] == "MATCHED" for row in members),
            }
        )
        output.append(result)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-root", type=Path, required=True, help="Source-typed eight-fold acceptance review root.")
    parser.add_argument("--baseline-root", type=Path, required=True, help="Sibling frozen artifacts root containing projections.")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    acceptance = args.review_root / "acceptance_review" / "scored_rows_for_acceptance_review.csv"
    if args.out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit directory: {args.out_dir}")
    score_rows = read_csv(acceptance)
    limited = [
        row
        for row in score_rows
        if clean(row.get("draw_design")) == LIMITED_ENTRY_DESIGN and is_true(row.get("false_guarantee"))
    ]
    pursuit = [
        row
        for row in score_rows
        if clean(row.get("draw_design")) == RESTRICTED_PURSUIT_DESIGN and is_true(row.get("false_guarantee"))
    ]
    non_draw_score_rows = [
        row
        for row in score_rows
        if clean(row.get("draw_design")) in NON_DRAW_PURSUIT_SUBTYPES
    ]
    if len(limited) != 182:
        raise ValueError(f"Expected exactly 182 limited-entry hunting false guarantees, found {len(limited)}")
    if len(pursuit) != 5:
        raise ValueError(f"Expected exactly 5 restricted-pursuit false guarantees, found {len(pursuit)}")
    if non_draw_score_rows:
        raise ValueError("Non-draw pursuit availability was found in the scoring population")

    desired = {(clean(row["fold"]), clean(row["hunt_code"]), clean(row["residency"]), point(row["points"])) for row in limited}
    enriched: list[dict[str, object]] = []
    referenced_pursuit: list[dict[str, object]] = []
    fold_names = sorted({clean(row["fold"]) for row in limited + pursuit})
    for fold in fold_names:
        source_year, target_year = fold.split("_to_")
        comparison_path = args.review_root / fold / "comparison_phase" / "draw_line_aware_prediction_vs_actual_rowlevel.csv"
        forecast_path = args.baseline_root / fold / "scoring_projection" / f"{source_year}_to_{target_year}_frozen_forecast_legacy_pool_scoring_projection.csv"
        actual_path = args.baseline_root / fold / "scoring_projection" / f"{target_year}_frozen_actual_residency_scoring_projection.csv"
        comparison_rows = read_csv(comparison_path)
        forecast_rows = read_csv(forecast_path)
        actual_by_lane: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for actual in read_csv(actual_path):
            if clean(actual.get("draw_system_type")) == "BEAR_DRAW":
                actual_by_lane[lane_key(actual)].append(actual)

        for row in comparison_rows:
            key = (fold, clean(row.get("hunt_code")), clean(row.get("residency")), point(row.get("points")))
            false_guarantee = (
                clean(row.get("family")) == "bonus_bear"
                and clean(row.get("scoring_decision")) == "score_probability"
                and number(row.get("predicted_probability")) >= 1.0 - EPSILON
                and number(row.get("actual_probability")) < 1.0 - EPSILON
            )
            if not false_guarantee:
                continue
            subtype = clean(row.get("bear_draw_subtype"))
            if subtype in NON_DRAW_PURSUIT_SUBTYPES:
                raise ValueError(f"Non-draw pursuit availability entered false-guarantee audit: {key}")
            if key not in desired:
                continue
            if subtype != "LIMITED_ENTRY_BEAR_HUNT":
                raise ValueError(f"Limited-entry acceptance row is not a limited-entry Bear hunt: {key} -> {subtype}")
            forecast = forecast_at_row(forecast_rows, row.get("prediction_row_number"))
            rung = number(row.get("points"))
            target_stats = actual_ladder_stats(actual_by_lane[lane_key(row)], rung)
            forecast_total = number(forecast.get("max_point_permits_2026")) + number(forecast.get("random_permits_2026"))
            target_total = number(target_stats["target_total_permits"])
            enrichment = {
                "fold": fold,
                "source_draw_year": source_year,
                "target_draw_year": target_year,
                "model_population": "LIMITED_ENTRY_BEAR_HUNTING_ONLY",
                "hunt_code": clean(row.get("hunt_code")),
                "source_hunt_code": clean(row.get("original_hunt_code_predicted")),
                "hunt_code_crosswalk_status": clean(row.get("hunt_code_crosswalk_status_predicted")),
                "hunt_name": clean(row.get("hunt_name_predicted")),
                "residency": clean(row.get("residency")),
                "point_rung": point(row.get("points")),
                "bear_draw_subtype": subtype,
                "bear_draw_subtype_source": clean(row.get("bear_draw_subtype_source")),
                "predicted_probability": clean(row.get("predicted_probability")),
                "actual_probability": clean(row.get("actual_probability")),
                "absolute_error": clean(row.get("absolute_error")),
                "target_ladder_position": ladder_position(row),
                "target_mixed_cutoff_point": clean(row.get("mixed_cutoff_point")),
                "target_lowest_guaranteed_stack_point": clean(row.get("lowest_guaranteed_stack_point")),
                "target_top_applicant_point": clean(row.get("top_applicant_point")),
                "target_actual_eligible_at_rung": clean(row.get("actual_eligible_applicants")),
                "forecast_applicants_at_rung": number(forecast.get("applicants_at_level")),
                "forecast_applicants_above_rung": number(forecast.get("applicants_above")),
                "forecast_applicants_at_or_above_rung": number(forecast.get("applicants_at_level")) + number(forecast.get("applicants_above")),
                "forecast_bonus_permits": number(forecast.get("max_point_permits_2026")),
                "forecast_random_permits": number(forecast.get("random_permits_2026")),
                "forecast_total_permits": forecast_total,
                **target_stats,
                "target_stack_excess_over_forecast": number(target_stats["target_applicants_at_or_above_rung"])
                - number(forecast.get("applicants_at_level"))
                - number(forecast.get("applicants_above")),
                "permit_alignment": "MATCHED" if abs(forecast_total - target_total) < EPSILON else ("TARGET_HIGHER" if target_total > forecast_total else "TARGET_LOWER"),
                "interpretation": "Aggregate target-ladder evidence only; it does not identify individual returning applicants, new entrants, or hunt-switchers.",
            }
            enriched.append(enrichment)

        for row in comparison_rows:
            if (
                clean(row.get("family")) == "bonus_bear"
                and clean(row.get("bear_draw_subtype")) == "RESTRICTED_BEAR_PURSUIT"
                and clean(row.get("scoring_decision")) == "score_probability"
                and number(row.get("predicted_probability")) >= 1.0 - EPSILON
                and number(row.get("actual_probability")) < 1.0 - EPSILON
            ):
                referenced_pursuit.append(
                    {
                        "fold": fold,
                        "source_draw_year": source_year,
                        "target_draw_year": target_year,
                        "model_population": "RESTRICTED_PURSUIT_REFERENCE_ONLY",
                        "excluded_from_limited_entry_repair": "TRUE",
                        "hunt_code": clean(row.get("hunt_code")),
                        "residency": clean(row.get("residency")),
                        "point_rung": point(row.get("points")),
                        "bear_draw_subtype": clean(row.get("bear_draw_subtype")),
                        "bear_draw_subtype_source": clean(row.get("bear_draw_subtype_source")),
                        "predicted_probability": clean(row.get("predicted_probability")),
                        "actual_probability": clean(row.get("actual_probability")),
                    }
                )

    if len(enriched) != len(limited):
        raise ValueError(f"Only enriched {len(enriched)} of {len(limited)} limited-entry false guarantees")
    if len(referenced_pursuit) != len(pursuit):
        raise ValueError(f"Expected 5 restricted-pursuit reference rows, found {len(referenced_pursuit)}")
    enriched.sort(key=lambda row: (row["fold"], row["residency"], -number(row["point_rung"]), row["hunt_code"]))
    referenced_pursuit.sort(key=lambda row: (row["fold"], row["residency"], -number(row["point_rung"]), row["hunt_code"]))

    args.out_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.out_dir / "limited_entry_hunting_false_guarantee_rows.csv", enriched)
    write_csv(args.out_dir / "restricted_pursuit_false_guarantee_reference.csv", referenced_pursuit)
    write_csv(
        args.out_dir / "by_source_year_residency_subtype_target_ladder.csv",
        compact_group(enriched, ("source_draw_year", "target_draw_year", "residency", "bear_draw_subtype", "target_ladder_position")),
    )
    write_csv(args.out_dir / "by_source_year_residency_rung_target_ladder.csv", compact_group(enriched, ("source_draw_year", "target_draw_year", "residency", "point_rung", "target_ladder_position")))
    write_csv(args.out_dir / "by_hunt_lane_target_ladder.csv", compact_group(enriched, ("hunt_code", "residency", "target_ladder_position")))
    write_csv(
        args.out_dir / "by_target_ladder_permit_alignment.csv",
        compact_group(enriched, ("target_ladder_position", "permit_alignment")),
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "read_only_limited_entry_bear_false_guarantee_audit",
        "scope": "Frozen physical adjacent-year folds only. No canonical, engine, runtime, R2, or live-site file was changed.",
        "limited_entry_hunting_false_guarantees": len(enriched),
        "restricted_pursuit_false_guarantees_reference_only": len(referenced_pursuit),
        "non_draw_pursuit_availability_score_rows": len(non_draw_score_rows),
        "non_draw_pursuit_availability_false_guarantees": 0,
        "limited_entry_subtypes": dict(Counter(clean(row["bear_draw_subtype"]) for row in enriched)),
        "by_source_year": dict(sorted(Counter(clean(row["source_draw_year"]) for row in enriched).items())),
        "by_residency": dict(sorted(Counter(clean(row["residency"]) for row in enriched).items())),
        "by_target_ladder_position": dict(sorted(Counter(clean(row["target_ladder_position"]) for row in enriched).items())),
        "by_permit_alignment": dict(sorted(Counter(clean(row["permit_alignment"]) for row in enriched).items())),
        "input_sha256": {
            "source_typed_scored_rows": sha256(acceptance),
        },
        "inputs": {
            "review_root": str(args.review_root),
            "baseline_root": str(args.baseline_root),
        },
        "interpretation": "The target ladder exposes aggregate stack pressure. It cannot prove which people returned, entered, or switched hunts. Restricted pursuit is isolated and non-draw pursuit availability is excluded from all draw-probability analysis.",
        "status": "PASS_READ_ONLY_AUDIT_COMPLETE",
    }
    (args.out_dir / "audit_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
