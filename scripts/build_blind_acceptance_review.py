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
MISSING_SCOREABLE_ACTUAL_DECISION = "missing_prediction_for_scoreable_actual_ladder_row"
THRESHOLDS = {
    "minimum_independent_following_year_folds": 2,
    "minimum_joined_rows_per_design": 400,
    "maximum_mae": 0.10,
    "maximum_p90_absolute_error": 0.30,
    "maximum_tail_error_rate_over_25pp": 0.10,
    "maximum_false_guarantee_rows": 0,
    "required_unclassified_actual_gaps": 0,
}

# `BEAR_DRAW` describes the shared Utah bonus-draw mechanics, but it is not a
# single visitor or certification population. Limited-entry bear hunting and
# restricted bear pursuit are different official programs with distinct hunt
# purposes and historical ladders. Keep their evidence separate while
# retaining the mechanical key in the scorer for structural joins.
BEAR_CERTIFICATION_DESIGNS = {
    "LIMITED_ENTRY_BEAR_HUNT": "BEAR_LIMITED_ENTRY_HUNT_BONUS",
    "RESTRICTED_BEAR_PURSUIT": "BEAR_RESTRICTED_PURSUIT_BONUS",
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


def certification_draw_design(row: dict[str, str]) -> str:
    """Return the declared certification population for a scored row.

    The scorer keeps `BEAR_DRAW` for the official structural join.
    Certification must not blend restricted-pursuit evidence into
    limited-entry Bear hunting, so every Bear score requires a subtype.
    """

    design = clean(row.get("draw_design_key"))
    if design != "BEAR_DRAW":
        return design
    subtype = clean(row.get("bear_draw_subtype"))
    return BEAR_CERTIFICATION_DESIGNS.get(subtype, "BEAR_DRAW_UNCLASSIFIED_SUBTYPE")


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
                design=certification_draw_design(row),
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


def actual_gap_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("draw_design_key")),
        clean(row.get("draw_pool_key")),
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")),
        clean(row.get("points")),
    )


def load_actual_gap_fold(fold: str, path: Path) -> tuple[list[dict[str, object]], str]:
    """Load scoreable official actuals that did not receive a prediction.

    ADR-0006 requires every non-joined official actual to be source-classified.
    A blank classification is an unclassified certification gap, even when the
    probability metrics for joined rows look favorable.
    """

    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows, ""
    classification_path = path.parent / "draw_line_aware_actual_gap_classifications.csv"
    classifications = {
        actual_gap_key(row): row
        for row in read_csv(classification_path)
    } if classification_path.exists() else {}
    for row in read_csv(path):
        if clean(row.get("scoring_decision")) != MISSING_SCOREABLE_ACTUAL_DECISION:
            continue
        sidecar = classifications.get(actual_gap_key(row), {})
        classification = clean(sidecar.get("actual_gap_classification") or row.get("actual_gap_classification") or row.get("source_classification") or row.get("unscorable_reason"))
        certification_gap_status = clean(sidecar.get("certification_gap_status"))
        is_source_classified = bool(classification) and certification_gap_status == "SOURCE_CLASSIFIED"
        rows.append(
            {
                "fold": fold,
                "draw_design": certification_draw_design(row),
                "hunt_code": clean(row.get("hunt_code")).upper(),
                "classification": classification,
                "certification_gap_status": certification_gap_status,
                "is_unclassified": not is_source_classified,
            }
        )
    return rows, str(classification_path) if classification_path.exists() else ""


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


def decision(
    folds: set[str],
    row_metrics: dict[str, object],
    unclassified_actual_gap_rows: int = 0,
) -> tuple[str, list[str]]:
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
    if unclassified_actual_gap_rows > THRESHOLDS["required_unclassified_actual_gaps"]:
        failures.append("UNCLASSIFIED_ACTUAL_GAPS")
    return ("ACCEPTED" if not failures else "NOT_ACCEPTED"), failures


def build_design_rows(
    rows: list[dict[str, object]],
    actual_gaps: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    actual_gaps = actual_gaps or []
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[clean(row["draw_design"]) or "UNCLASSIFIED"].append(row)
    gap_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in actual_gaps:
        gap_groups[clean(row["draw_design"]) or "UNCLASSIFIED"].append(row)
    out: list[dict[str, object]] = []
    for design in sorted(set(groups) | set(gap_groups)):
        group = groups.get(design, [])
        design_gaps = gap_groups.get(design, [])
        row_metrics = metrics(group)
        fold_names = {clean(row["fold"]) for row in group} | {clean(row["fold"]) for row in design_gaps}
        unclassified_gaps = sum(bool(row["is_unclassified"]) for row in design_gaps)
        classified_gaps = len(design_gaps) - unclassified_gaps
        status, failures = decision(fold_names, row_metrics, unclassified_gaps)
        out.append(
            {
                "draw_design": design,
                "independent_following_year_folds": ";".join(sorted(fold_names)),
                "fold_count": len(fold_names),
                **row_metrics,
                "classified_actual_gap_rows": classified_gaps,
                "unclassified_actual_gap_rows": unclassified_gaps,
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
    actual_gaps: list[dict[str, object]] = []
    input_folds: dict[str, str] = {}
    input_actual_gap_folds: dict[str, str] = {}
    input_actual_gap_classification_folds: dict[str, str] = {}
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
        actual_gap_path = path.parent / "draw_line_aware_actual_ladder_scoring_rows.csv"
        fold_gaps, classification_path = load_actual_gap_fold(fold, actual_gap_path)
        actual_gaps.extend(fold_gaps)
        input_actual_gap_folds[fold] = str(actual_gap_path)
        if classification_path:
            input_actual_gap_classification_folds[fold] = classification_path
    design_rows = build_design_rows(rows, actual_gaps)
    hunt_rows = build_hunt_code_rows(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "acceptance_by_draw_design.csv", design_rows)
    write_csv(args.out_dir / "hunt_code_following_year_review.csv", hunt_rows)
    write_csv(args.out_dir / "scored_rows_for_acceptance_review.csv", rows)
    overall = metrics(rows)
    overall_unclassified_gaps = sum(bool(row["is_unclassified"]) for row in actual_gaps)
    overall_status, overall_failures = decision(
        {clean(row["fold"]) for row in rows} | {clean(row["fold"]) for row in actual_gaps},
        overall,
        overall_unclassified_gaps,
    )
    manifest = {
        "purpose": "frozen_blind_following_year_acceptance_review",
        "acceptance_standard": "docs/decisions/ADR-0006-historical-blind-acceptance-thresholds.md",
        "thresholds": THRESHOLDS,
        "inputs": input_folds,
        "actual_gap_inputs": input_actual_gap_folds,
        "actual_gap_classification_inputs": input_actual_gap_classification_folds,
        "overall": {
            **overall,
            "classified_actual_gap_rows": sum(not bool(row["is_unclassified"]) for row in actual_gaps),
            "unclassified_actual_gap_rows": overall_unclassified_gaps,
            "acceptance_status": overall_status,
            "failure_reasons": overall_failures,
        },
        "design_count": len(design_rows),
        "hunt_code_review_count": len(hunt_rows),
        "policy": "A failed or insufficiently evidenced design remains blocked; no aggregate result may override a design-level false guarantee.",
    }
    (args.out_dir / "acceptance_review_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["overall"], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
