"""Audit source-only Bear false guarantees against their held-out ladders.

This is deliberately an evidence report, not an engine or truth-data writer.
It joins the frozen forecast, held-out official point ladder, and scored result
for every Bear row forecast at 100 percent that did not draw at 100 percent.
Public aggregate ladders cannot identify individual hunt-switchers; the report
therefore records observable target stack pressure instead of claiming an
individual-level arrival history.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping


EPSILON = 0.000001


def text(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float:
    try:
        return float(text(value).replace(",", ""))
    except ValueError:
        return 0.0


def point_key(value: object) -> str:
    raw = text(value)
    if not raw:
        return ""
    try:
        numeric = float(raw)
    except ValueError:
        return raw
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def lane_key(row: Mapping[str, object]) -> tuple[str, str]:
    return (text(row.get("hunt_code")), text(row.get("residency")).casefold())


def score_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    hunt_code, residency = lane_key(row)
    return (hunt_code, residency, point_key(row.get("points")))


def is_point_row(row: Mapping[str, object]) -> bool:
    return text(row.get("row_type") or row.get("record_type")).upper() in {
        "POINT_ROW",
        "POINT_LEVEL_DRAW_RESULT",
    }


def permit_total(row: Mapping[str, object]) -> float:
    return number(row.get("bonus_permits")) + number(row.get("regular_permits"))


def target_lane_stats(lane_rows: Iterable[Mapping[str, object]], rung: float) -> dict[str, object]:
    point_rows = [row for row in lane_rows if is_point_row(row)]
    source_values_present = any(
        text(row.get(field))
        for row in point_rows
        for field in ("eligible_applicants", "bonus_permits", "regular_permits")
    )
    at_rung = [row for row in point_rows if point_key(row.get("points")) == point_key(rung)]
    at_or_above = [row for row in point_rows if number(row.get("points")) >= rung]
    return {
        "target_ladder_available": "TRUE" if source_values_present else "FALSE",
        "target_eligible_at_rung": sum(number(row.get("eligible_applicants")) for row in at_rung),
        "target_successful_at_rung": sum(permit_total(row) for row in at_rung),
        "target_eligible_at_or_above_rung": sum(number(row.get("eligible_applicants")) for row in at_or_above),
        "target_successful_at_or_above_rung": sum(permit_total(row) for row in at_or_above),
        "target_lane_bonus_permits": sum(number(row.get("bonus_permits")) for row in point_rows),
        "target_lane_regular_permits": sum(number(row.get("regular_permits")) for row in point_rows),
    }


def permit_alignment(predicted: float, target: float, target_available: str) -> str:
    if target_available != "TRUE":
        return "TARGET_LADDER_UNAVAILABLE"
    if abs(predicted - target) < EPSILON:
        return "MATCHED"
    return "TARGET_HIGHER" if target > predicted else "TARGET_LOWER"


def report(run_dir: Path, out_dir: Path) -> dict[str, object]:
    result_rows: list[dict[str, object]] = []
    fold_pattern = re.compile(r"^(?P<source>\d{4})_to_(?P<target>\d{4})$")
    fold_dirs = sorted(
        (path for path in run_dir.iterdir() if path.is_dir() and fold_pattern.match(path.name)),
        key=lambda path: path.name,
    )
    if not fold_dirs:
        raise ValueError(f"No YYYY_to_YYYY fold directories found under {run_dir}")

    for fold_dir in fold_dirs:
        match = fold_pattern.match(fold_dir.name)
        assert match
        source_year = match.group("source")
        target_year = match.group("target")
        comparison = rows(fold_dir / "comparison_phase" / "draw_line_aware_actual_ladder_scoring_rows.csv")
        prediction_path = fold_dir / "prediction_phase" / "predictions" / f"{source_year}_{target_year}_bonus_bear.csv"
        predictions = {score_key(row): row for row in rows(prediction_path)}
        actual_path = fold_dir / "scoring_projection" / f"{target_year}_frozen_actual_residency_scoring_projection.csv"
        actual_by_lane: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows(actual_path):
            actual_by_lane[lane_key(row)].append(row)

        for score in comparison:
            if text(score.get("family_actual")) != "bonus_bear":
                continue
            if text(score.get("scoring_decision")) != "score_probability":
                continue
            if number(score.get("predicted_probability")) < 1.0 - EPSILON:
                continue
            if number(score.get("actual_probability")) >= 1.0 - EPSILON:
                continue
            prediction = predictions.get(score_key(score))
            if prediction is None:
                raise ValueError(f"False guarantee lacks frozen forecast row: {fold_dir.name} {score_key(score)}")
            rung = number(score.get("points"))
            stats = target_lane_stats(actual_by_lane[lane_key(score)], rung)
            forecast_bonus = number(prediction.get("max_point_permits_2026"))
            forecast_regular = number(prediction.get("random_permits_2026"))
            forecast_total = forecast_bonus + forecast_regular
            forecast_above = number(prediction.get("applicants_above"))
            forecast_at_rung = number(prediction.get("applicants_at_level"))
            forecast_stack = forecast_above + forecast_at_rung
            target_total = number(stats["target_lane_bonus_permits"]) + number(stats["target_lane_regular_permits"])
            target_stack = number(stats["target_eligible_at_or_above_rung"])
            target_successful_stack = number(stats["target_successful_at_or_above_rung"])
            result_rows.append(
                {
                    "fold": fold_dir.name,
                    "source_draw_year": source_year,
                    "target_draw_year": target_year,
                    "hunt_code": text(score.get("hunt_code")),
                    "residency": text(score.get("residency")),
                    "points": point_key(score.get("points")),
                    "actual_probability": text(score.get("actual_probability")),
                    "predicted_probability": text(score.get("predicted_probability")),
                    "absolute_error": text(score.get("absolute_error")),
                    "point_relation_to_draw_line": text(score.get("point_relation_to_draw_line")),
                    "target_mixed_cutoff_point": text(score.get("mixed_cutoff_point")),
                    "target_lowest_guaranteed_stack_point": text(score.get("lowest_guaranteed_stack_point")),
                    "target_top_applicant_point": text(score.get("top_applicant_point")),
                    "target_actual_eligible_at_rung": text(score.get("actual_eligible_applicants")),
                    "forecast_applicants_above": forecast_above,
                    "forecast_applicants_at_rung": forecast_at_rung,
                    "forecast_applicants_at_or_above_rung": forecast_stack,
                    "forecast_max_permits": forecast_bonus,
                    "forecast_regular_permits": forecast_regular,
                    "forecast_total_permits": forecast_total,
                    "target_ladder_available": stats["target_ladder_available"],
                    "target_eligible_at_rung": stats["target_eligible_at_rung"],
                    "target_successful_at_rung": stats["target_successful_at_rung"],
                    "target_eligible_at_or_above_rung": target_stack,
                    "target_successful_at_or_above_rung": target_successful_stack,
                    "target_unselected_at_or_above_rung": target_stack - target_successful_stack,
                    "target_stack_excess_over_forecast": target_stack - forecast_stack,
                    "target_lane_bonus_permits": stats["target_lane_bonus_permits"],
                    "target_lane_regular_permits": stats["target_lane_regular_permits"],
                    "target_lane_total_permits": target_total,
                    "permit_alignment": permit_alignment(
                        forecast_total,
                        target_total,
                        str(stats["target_ladder_available"]),
                    ),
                    "bear_cohort_evidence_scope": text(prediction.get("bear_cohort_evidence_scope")),
                    "bear_cohort_reapply_rate": text(prediction.get("bear_cohort_reapply_rate")),
                    "bear_cohort_arrival_mean": text(prediction.get("bear_cohort_arrival_count")),
                    "bear_cohort_exact_unsuccessful": text(prediction.get("bear_cohort_exact_unsuccessful")),
                    "bear_cohort_exact_transitions": text(prediction.get("bear_cohort_exact_transitions")),
                    "source_pdf": text(next(iter(actual_by_lane[lane_key(score)]), {}).get("source_pdf")),
                    "source_pdf_page": text(next(iter(actual_by_lane[lane_key(score)]), {}).get("pdf_page")),
                    "interpretation": (
                        "Aggregate-ladder evidence only: target stack pressure is observable; "
                        "individual returning, new-entry, and hunt-switch identities are not."
                    ),
                }
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "bear_false_guarantee_ladder_audit.csv"
    columns = list(result_rows[0]) if result_rows else []
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result_rows)

    relation_counts = Counter(text(row["point_relation_to_draw_line"]) for row in result_rows)
    residency_counts = Counter(text(row["residency"]) for row in result_rows)
    permit_counts = Counter(text(row["permit_alignment"]) for row in result_rows)
    matched_quota_rows = [row for row in result_rows if row["permit_alignment"] == "MATCHED"]
    by_fold = {
        fold: sum(1 for row in result_rows if row["fold"] == fold)
        for fold in sorted({text(row["fold"]) for row in result_rows})
    }
    summary = {
        "run_dir": str(run_dir),
        "scope": "Frozen source-only Bear false guarantees; no truth, engine, runtime, or release file changed.",
        "false_guarantee_rows": len(result_rows),
        "by_fold": by_fold,
        "by_target_point_relation": dict(sorted(relation_counts.items())),
        "by_residency": dict(sorted(residency_counts.items())),
        "by_target_permit_alignment": dict(sorted(permit_counts.items())),
        "matched_quota_stack_excess": {
            "rows": len(matched_quota_rows),
            "mean_target_stack_excess_over_forecast": (
                sum(number(row["target_stack_excess_over_forecast"]) for row in matched_quota_rows)
                / len(matched_quota_rows)
                if matched_quota_rows
                else None
            ),
            "rows_with_positive_target_stack_excess": sum(
                number(row["target_stack_excess_over_forecast"]) > 0 for row in matched_quota_rows
            ),
        },
        "interpretation": (
            "A matched target permit total excludes a simple permit-total drift explanation for that row. "
            "It does not identify individual arrival or switching behavior; only DWR person-level transition data could do that."
        ),
        "row_audit": str(output),
    }
    summary_path = out_dir / "bear_false_guarantee_ladder_audit_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(report(args.run_dir, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
