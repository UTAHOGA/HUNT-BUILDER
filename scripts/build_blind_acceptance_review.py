#!/usr/bin/env python3
"""Create a design- and hunt-code-level review of frozen blind comparisons.

This is an audit reporter.  It reads existing frozen comparison outputs and
writes a separate review directory; it never changes source truth, forecasts,
runtime artifacts, or production state.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
FALSE_GUARANTEE_THRESHOLD = 0.999999
THRESHOLDS = {
    "minimum_independent_following_year_folds": 2,
    "minimum_joined_rows_per_design": 400,
    "maximum_mae": 0.10,
    "maximum_p90_absolute_error": 0.30,
    "maximum_tail_error_rate_over_25pp": 0.10,
    "maximum_false_guarantee_rows": 0,
    "required_unclassified_actual_gaps": 0,
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    materialized = list(rows)
    fields: list[str] = []
    for row in materialized:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def review_row(
    *,
    fold: str,
    design: str,
    row: dict[str, str],
    hunt_code: str,
    residency: str,
    points: str,
    species: str,
    predicted: float,
    actual: float,
) -> dict[str, object]:
    error = abs(predicted - actual)
    return {
        "fold": fold,
        "draw_design": design,
        "hunt_code": hunt_code,
        "residency": residency,
        "points": points,
        "species": species,
        "predicted_probability": predicted,
        "actual_probability": actual,
        "absolute_error": error,
        "tail_error_over_25pp": error > 0.25,
        "false_guarantee": predicted >= FALSE_GUARANTEE_THRESHOLD and actual < FALSE_GUARANTEE_THRESHOLD,
    }


def load_draw_line_fold(fold: str, path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in read_csv(path):
        if clean(row.get("scoring_decision")) != "score_probability":
            continue
        predicted = number(row.get("predicted_probability"))
        actual = number(row.get("actual_probability"))
        if predicted is None or actual is None:
            continue
        rows.append(
            review_row(
                fold=fold,
                design=clean(row.get("draw_design_key")),
                row=row,
                hunt_code=clean(row.get("hunt_code")).upper(),
                residency=clean(row.get("residency")),
                points=clean(row.get("points")),
                species=clean(row.get("actual_species")),
                predicted=predicted,
                actual=actual,
            )
        )
    return rows


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    errors = [float(row["absolute_error"]) for row in rows]
    tail = sum(bool(row["tail_error_over_25pp"]) for row in rows)
    false_guarantees = sum(bool(row["false_guarantee"]) for row in rows)
    return {
        "joined_rows": len(rows),
        "mae": sum(errors) / len(errors) if errors else None,
        "rmse": math.sqrt(sum(value * value for value in errors) / len(errors)) if errors else None,
        "p90_absolute_error": percentile(errors, 0.90),
        "tail_error_rows_over_25pp": tail,
        "tail_error_rate_over_25pp": tail / len(rows) if rows else None,
        "false_guarantee_rows": false_guarantees,
    }


def decision(folds: set[str], row_metrics: dict[str, object]) -> tuple[str, list[str]]:
    failures: list[str] = []
    if len(folds) < THRESHOLDS["minimum_independent_following_year_folds"]:
        failures.append("INSUFFICIENT_INDEPENDENT_FOLDS")
    if int(row_metrics["joined_rows"]) < THRESHOLDS["minimum_joined_rows_per_design"]:
        failures.append("INSUFFICIENT_JOINED_ROWS")
    if row_metrics["mae"] is None or float(row_metrics["mae"]) > THRESHOLDS["maximum_mae"]:
        failures.append("MAE_EXCEEDS_LIMIT")
    if row_metrics["p90_absolute_error"] is None or float(row_metrics["p90_absolute_error"]) > THRESHOLDS["maximum_p90_absolute_error"]:
        failures.append("P90_ERROR_EXCEEDS_LIMIT")
    if row_metrics["tail_error_rate_over_25pp"] is None or float(row_metrics["tail_error_rate_over_25pp"]) > THRESHOLDS["maximum_tail_error_rate_over_25pp"]:
        failures.append("TAIL_ERROR_RATE_EXCEEDS_LIMIT")
    if int(row_metrics["false_guarantee_rows"]) > THRESHOLDS["maximum_false_guarantee_rows"]:
        failures.append("FALSE_GUARANTEE")
    return ("ACCEPTED" if not failures else "NOT_ACCEPTED"), failures


def build_design_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[clean(row["draw_design"]) or "UNCLASSIFIED"].append(row)
    out: list[dict[str, object]] = []
    for design, group in sorted(groups.items()):
        row_metrics = metrics(group)
        fold_names = {clean(row["fold"]) for row in group}
        status, failures = decision(fold_names, row_metrics)
        out.append(
            {
                "draw_design": design,
                "independent_following_year_folds": ";".join(sorted(fold_names)),
                "fold_count": len(fold_names),
                **row_metrics,
                "acceptance_status": status,
                "failure_reasons": ";".join(failures),
            }
        )
    return out


def build_hunt_code_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(clean(row["draw_design"]), clean(row["hunt_code"]))].append(row)
    out: list[dict[str, object]] = []
    for (design, code), group in sorted(groups.items()):
        row_metrics = metrics(group)
        folds = {clean(row["fold"]) for row in group}
        needs_review = int(row_metrics["false_guarantee_rows"]) > 0 or int(row_metrics["tail_error_rows_over_25pp"]) > 0
        out.append(
            {
                "draw_design": design,
                "hunt_code": code,
                "species": ";".join(sorted({clean(row["species"]) for row in group if clean(row["species"])})),
                "residencies": ";".join(sorted({clean(row["residency"]) for row in group if clean(row["residency"])})),
                "following_year_folds": ";".join(sorted(folds)),
                "fold_count": len(folds),
                **row_metrics,
                "review_disposition": "REVIEW_TAIL_OR_FALSE_GUARANTEE" if needs_review else "NO_TAIL_SIGNAL",
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--fold",
        action="append",
        required=True,
        metavar="SOURCE_TO_TARGET=SCORING_ROWS_CSV",
        help="Historical adjacent-year fold only; may be supplied more than once.",
    )
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    input_folds: dict[str, str] = {}
    for value in args.fold:
        if "=" not in value:
            raise SystemExit("Each --fold must be SOURCE_TO_TARGET=SCORING_ROWS_CSV")
        fold, raw_path = value.split("=", 1)
        fold = clean(fold)
        path = Path(raw_path)
        if not fold or not path.exists():
            raise SystemExit(f"Fold name or scoring file is invalid: {value}")
        rows.extend(load_draw_line_fold(fold, path))
        input_folds[fold] = str(path)
    design_rows = build_design_rows(rows)
    hunt_rows = build_hunt_code_rows(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "acceptance_by_draw_design.csv", design_rows)
    write_csv(args.out_dir / "hunt_code_following_year_review.csv", hunt_rows)
    write_csv(args.out_dir / "scored_rows_for_acceptance_review.csv", rows)
    overall = metrics(rows)
    overall_status, overall_failures = decision({clean(row["fold"]) for row in rows}, overall)
    manifest = {
        "purpose": "frozen_blind_following_year_acceptance_review",
        "acceptance_standard": "docs/decisions/ADR-0006-historical-blind-acceptance-thresholds.md",
        "thresholds": THRESHOLDS,
        "inputs": input_folds,
        "overall": {**overall, "acceptance_status": overall_status, "failure_reasons": overall_failures},
        "design_count": len(design_rows),
        "hunt_code_review_count": len(hunt_rows),
        "policy": "A failed or insufficiently evidenced design remains blocked; no aggregate result may override a design-level false guarantee.",
    }
    (args.out_dir / "acceptance_review_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["overall"], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
