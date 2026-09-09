#!/usr/bin/env python3
"""Source-classify non-joined official actual rows in a frozen blind fold.

The classifier does not excuse engine defects.  It distinguishes official
prior-year source limitations and the deliberate no-certainty roll-forward
safety rule from rows whose published source value should have been emitted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.run_all_families import _source_backed_probability_values
from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer


MISSING_SCOREABLE_ACTUAL_DECISION = "missing_prediction_for_scoreable_actual_ladder_row"
SOURCE_CLASSIFIED = "SOURCE_CLASSIFIED"
BLOCKING_ENGINE_GAP = "BLOCKING_ENGINE_GAP"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def initialize_crosswalk(source_year: int, target_year: int) -> None:
    scorer.HUNT_CODE_CROSSWALK = scorer.load_hunt_code_crosswalk(scorer.DEFAULT_HUNT_CODE_CROSSWALK_FILES)
    scorer.ACTIVE_SCORING_HUNT_CODE_ALIASES = dict(scorer.BASE_SCORING_HUNT_CODE_ALIASES)
    scorer.ACTIVE_SCORING_HUNT_CODE_ALIASES.update(
        scorer.YEAR_SCOPED_SCORING_HUNT_CODE_ALIASES.get((str(source_year), str(target_year)), {})
    )


def point_key(point: scorer.ActualPoint) -> tuple[str, str, str, str, str]:
    return (
        point.draw_design_key,
        point.draw_pool,
        point.hunt_code,
        point.residency,
        point.points,
    )


def gap_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("draw_design_key")),
        clean(row.get("draw_pool_key")),
        clean(row.get("hunt_code")).upper(),
        scorer.norm_residency(row.get("residency")),
        scorer.norm_points(row.get("points")),
    )


def source_probability(row: Mapping[str, object], residency: str) -> float | None:
    normalized = scorer.norm_residency(residency)
    for lane, probability in _source_backed_probability_values(row):
        if scorer.norm_residency(lane or "All") == normalized:
            return probability
    return None


def classify_gap(
    row: Mapping[str, object],
    *,
    exact_rows: Mapping[tuple[str, str, str, str, str], list[tuple[scorer.ActualPoint, dict[str, str]]]],
    lanes: set[tuple[str, str, str, str]],
    hunts: set[tuple[str, str, str]],
) -> tuple[str, str, dict[str, object]]:
    key = gap_key(row)
    exact = exact_rows.get(key, [])
    if exact:
        point, source_row = exact[0]
        probability = source_probability(source_row, point.residency)
        prior_eligible = float(point.actual_eligible_applicants)
        evidence = {
            "prior_year_probability": "" if probability is None else f"{probability:.10f}",
            "prior_year_eligible_applicants": prior_eligible,
            "prior_year_successful_applicants": point.actual_drawn,
            "prior_year_source_file": clean(source_row.get("source_file") or source_row.get("draw_source_file")),
            "prior_year_source_page": clean(source_row.get("official_page") or source_row.get("pdf_page")),
            "prior_year_source_row_identifier": clean(source_row.get("source_row_identifier")),
        }
        if prior_eligible <= 0:
            # A printed zero-applicant rung documents the source ladder's
            # structure, not an applicant probability that the forecast must
            # carry forward.  Treat a following-year applicant on that rung as
            # a source-year demand limitation, just as an absent prior rung is
            # source-classified below.
            return (
                "SOURCE_LIMITATION_PRIOR_YEAR_EMPTY_POINT_RUNG",
                SOURCE_CLASSIFIED,
                evidence,
            )
        if probability is not None and probability >= 0.999999:
            return (
                "SOURCE_SAFETY_BLOCKED_PRIOR_YEAR_CERTAINTY",
                SOURCE_CLASSIFIED,
                evidence,
            )
        if probability is not None:
            return (
                "ENGINE_COVERAGE_DEFECT_SOURCE_PROBABILITY_NOT_EMITTED",
                BLOCKING_ENGINE_GAP,
                evidence,
            )
        return (
            "SOURCE_LIMITATION_PRIOR_YEAR_POINT_PROBABILITY_UNREPORTED",
            SOURCE_CLASSIFIED,
            evidence,
        )

    design, pool, hunt, residency, _points = key
    if (design, pool, hunt, residency) in lanes:
        return (
            "SOURCE_LIMITATION_POINT_RUNG_ABSENT_IN_PRIOR_YEAR",
            SOURCE_CLASSIFIED,
            {},
        )
    if (design, pool, hunt) in hunts:
        return (
            "SOURCE_LIMITATION_RESIDENCY_LANE_ABSENT_IN_PRIOR_YEAR",
            SOURCE_CLASSIFIED,
            {},
        )
    return (
        "SOURCE_LIMITATION_HUNT_ABSENT_IN_PRIOR_YEAR",
        SOURCE_CLASSIFIED,
        {},
    )


def run(source_truth: Path, actual_gaps: Path, output: Path, source_year: int, target_year: int) -> dict[str, object]:
    initialize_crosswalk(source_year, target_year)
    exact_rows: dict[tuple[str, str, str, str, str], list[tuple[scorer.ActualPoint, dict[str, str]]]] = defaultdict(list)
    lanes: set[tuple[str, str, str, str]] = set()
    hunts: set[tuple[str, str, str]] = set()

    for source_row in read_csv(source_truth):
        for point in scorer.actual_points_from_row(source_row):
            key = point_key(point)
            exact_rows[key].append((point, source_row))
            lanes.add(key[:4])
            hunts.add(key[:3])

    output_rows: list[dict[str, object]] = []
    for row in read_csv(actual_gaps):
        if clean(row.get("scoring_decision")) != MISSING_SCOREABLE_ACTUAL_DECISION:
            continue
        classification, status, evidence = classify_gap(row, exact_rows=exact_rows, lanes=lanes, hunts=hunts)
        output_rows.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "draw_design_key": clean(row.get("draw_design_key")),
                "draw_pool_key": clean(row.get("draw_pool_key")),
                "hunt_code": clean(row.get("hunt_code")).upper(),
                "actual_original_hunt_code": clean(row.get("actual_original_hunt_code")).upper(),
                "residency": scorer.norm_residency(row.get("residency")),
                "points": scorer.norm_points(row.get("points")),
                "actual_gap_classification": classification,
                "certification_gap_status": status,
                **evidence,
            }
        )

    write_csv(output, output_rows)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "source_classify_frozen_blind_actual_gaps",
        "source_year": source_year,
        "target_year": target_year,
        "source_truth": str(source_truth),
        "source_truth_sha256": sha256(source_truth),
        "actual_gaps": str(actual_gaps),
        "actual_gaps_sha256": sha256(actual_gaps),
        "output": str(output),
        "output_sha256": sha256(output),
        "classified_rows": len(output_rows),
        "certification_gap_status_counts": dict(sorted(Counter(clean(row["certification_gap_status"]) for row in output_rows).items())),
        "classification_counts": dict(sorted(Counter(clean(row["actual_gap_classification"]) for row in output_rows).items())),
        "policy": "Only source limitations and the no-certainty safety rule are nonblocking; source-backed values omitted by the engine remain blocking.",
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-truth", required=True, type=Path)
    parser.add_argument("--actual-gaps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-year", required=True, type=int)
    parser.add_argument("--target-year", required=True, type=int)
    args = parser.parse_args()
    manifest = run(args.source_truth, args.actual_gaps, args.output, args.source_year, args.target_year)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
