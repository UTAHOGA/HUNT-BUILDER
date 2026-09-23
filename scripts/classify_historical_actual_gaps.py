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

from engine.utah_draw_predictive.run_all_families import (
    _source_backed_probability_values, _prepare_big_game_bonus_history_rows, _row_year,
)
from engine.utah_bonus_predictive.cohort_forecast import has_observed_transition, roll_forward_applicant_stack
from engine.utah_bonus_predictive.split import split_utah_bonus_permits
from scripts.build_predictive_bonus_engine_v1 import conditional_applicant_demand, deterministic_pool_probabilities
from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer


MISSING_SCOREABLE_ACTUAL_DECISION = "missing_prediction_for_scoreable_actual_ladder_row"
MISSING_SCOREABLE_ACTUAL_DECISIONS = {MISSING_SCOREABLE_ACTUAL_DECISION, "do_not_score_missing_prediction_probability"}
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


def blocked_identity_decisions(path: Path | None) -> dict[str, list[dict[str, str]]]:
    """Return source hunts whose pre-draw identity contract blocks carry-forward."""
    if path is None:
        return {}
    rows = read_csv(path)
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        source_code = clean(row.get("from_hunt_code")).upper()
        if source_code:
            by_source[source_code].append(row)
    return {
        source_code: decisions
        for source_code, decisions in by_source.items()
        if not any(
            clean(item.get("applicant_stack_carry_forward_allowed")).upper() == "TRUE"
            for item in decisions
        )
    }


def source_probability(row: Mapping[str, object], residency: str) -> float | None:
    normalized = scorer.norm_residency(residency)
    for lane, probability in _source_backed_probability_values(row):
        if scorer.norm_residency(lane or "All") == normalized:
            return probability
    return None


def conditional_abstention_evidence(history_rows, predictions, source_year):
    """Independently replay the existing source-only no-certainty safeguard.

    A status label alone is never evidence. Require the exact canonical lane,
    no observed adjacent transition, zero rolled cohort at this point, matching
    source award proxy, and the one-applicant counterfactual which triggered
    the existing abstention. No following-year outcome is used here.
    """
    histories = defaultdict(lambda: defaultdict(dict))
    lineage = defaultdict(set)
    source = [r for r in history_rows if 2017 <= (_row_year(r) or 0) <= source_year]
    for row in _prepare_big_game_bonus_history_rows(source):
        point_text = clean(row.get("points"))
        if not point_text.isdigit():
            continue
        year = _row_year(row)
        for point in scorer.actual_points_from_row(row):
            if point.residency not in {"Resident", "Nonresident"}:
                continue
            lane = point_key(point)[:4]
            values = {field: int(float(row.get(raw) or 0)) for field, raw in
                      [("eligible", "eligible_applicants"), ("bonus", "bonus_permits"),
                       ("regular", "regular_permits"), ("total", "total_permits")]}
            prior = histories[lane][year].get(int(point_text))
            if prior is not None and prior != values:
                raise ValueError(f"Conflicting source history for {lane}, {year}, {point_text}")
            histories[lane][year][int(point_text)] = values
            lineage[lane].add((clean(row.get("source_file")), clean(row.get("official_page") or row.get("pdf_page"))))
    verified = {}
    for prediction in predictions:
        if clean(prediction.get("algorithm_status")) != "NOT_SCORED_CONDITIONAL_RUNG_NO_TRANSITION_EVIDENCE":
            continue
        if any(clean(prediction.get(f)) for f in ("p_draw", "p_draw_mean", "p_draw_pct", "certified_p_draw")):
            continue
        key = scorer.prediction_alignment_key(prediction)[:5]
        if key[0] not in {"BONUS_LE_BIG_GAME", "BONUS_OIL_BIG_GAME", "BONUS_PLE_BIG_GAME"} or not key[4].isdigit():
            continue
        history = histories.get(key[:4], {})
        if not history or max(history) != source_year or has_observed_transition(history):
            continue
        rollover = roll_forward_applicant_stack(history, source_year)
        point = int(key[4])
        demand = rollover.applicants_by_points
        if demand.get(point, 0) != 0 or clean(prediction.get("forecast_applicants_at_level")) != "0":
            continue
        if not demand or point > max(demand):
            continue
        quota = sum(r["total"] for r in history[source_year].values())
        if quota <= 0 or quota != float(prediction.get("quota_2026_total") or -1):
            continue
        split = split_utah_bonus_permits(quota, key[3])
        conditional = conditional_applicant_demand(demand, point)
        probabilities = deterministic_pool_probabilities(sorted(conditional, reverse=True), conditional,
                                                         split.maxPointPermits, split.randomPermits)[0]
        if probabilities.get(point, 0) < .999:
            continue
        predecessor = history[source_year].get(point - 1, {})
        verified[key] = {
            "source_history_years_verified": ";".join(map(str, sorted(history))),
            "source_adjacent_transition_count": 0,
            "source_predecessor_point": point - 1 if point else "NO_ZERO_POINT_PREDECESSOR",
            "source_predecessor_unsuccessful": max(0, predecessor.get("eligible", 0) - predecessor.get("bonus", 0) - predecessor.get("regular", 0)),
            "replayed_forecast_applicants_at_level": 0,
            "source_award_proxy_verified": quota,
            "conditional_certainty_safeguard_replayed": "TRUE",
            "source_lane_lineage": json.dumps(sorted(lineage[key[:4]])),
        }
    return verified


def classify_gap(
    row: Mapping[str, object],
    *,
    exact_rows: Mapping[tuple[str, str, str, str, str], list[tuple[scorer.ActualPoint, dict[str, str]]]],
    lanes: set[tuple[str, str, str, str]],
    hunts: set[tuple[str, str, str]],
    source_lane_official_awards: Mapping[tuple[str, str, str, str], float] | None = None,
    blocked_identities: Mapping[str, list[dict[str, str]]] | None = None,
    verified_conditional_abstentions: Mapping[tuple, dict[str, object]] | None = None,
) -> tuple[str, str, dict[str, object]]:
    key = gap_key(row)
    identity_blocks = (blocked_identities or {}).get(key[2], [])
    if identity_blocks:
        transition_types = sorted(
            {clean(item.get("transition_type")) for item in identity_blocks if clean(item.get("transition_type"))}
        )
        return (
            "SOURCE_IDENTITY_BLOCKED_PRE_DRAW_" + "_OR_".join(transition_types or ["UNRESOLVED_CHANGE"]),
            SOURCE_CLASSIFIED,
            {
                "prior_year_identity_carry_forward_allowed": "FALSE",
                "prior_year_identity_transition_types": ";".join(transition_types),
                "prior_year_identity_evidence_file": ";".join(
                    sorted(
                        {
                            clean(item.get("target_application_evidence_file") or item.get("evidence_file"))
                            for item in identity_blocks
                            if clean(item.get("target_application_evidence_file") or item.get("evidence_file"))
                        }
                    )
                ),
                "prior_year_identity_evidence_pages": ";".join(
                    sorted(
                        {
                            clean(item.get("target_application_evidence_pages") or item.get("evidence_pages"))
                            for item in identity_blocks
                            if clean(item.get("target_application_evidence_pages") or item.get("evidence_pages"))
                        }
                    )
                ),
            },
        )
    exact = exact_rows.get(key, [])
    if exact:
        point, source_row = exact[0]
        probability = source_probability(source_row, point.residency)
        prior_eligible = float(point.actual_eligible_applicants)
        target_probability = scorer.parse_float(row.get("actual_probability"))
        if source_lane_official_awards is None:
            # Keep the helper independently testable.  Production review calls
            # pass the precomputed index above, avoiding this local scan.
            source_lane_awards_by_point = {
                source_key[4]: max(
                    [float(source_point.actual_drawn) for source_point, _ in source_values]
                    or [0.0]
                )
                for source_key, source_values in exact_rows.items()
                if source_key[:4] == key[:4]
            }
            lane_official_awards = sum(source_lane_awards_by_point.values())
        else:
            lane_official_awards = float(source_lane_official_awards.get(key[:4], 0.0))
        evidence = {
            "prior_year_probability": "" if probability is None else f"{probability:.10f}",
            "prior_year_eligible_applicants": prior_eligible,
            "prior_year_successful_applicants": point.actual_drawn,
            "source_lane_official_awards": lane_official_awards,
            "target_official_probability": "" if target_probability is None else f"{target_probability:.10f}",
            "prior_year_source_file": clean(source_row.get("source_file") or source_row.get("draw_source_file")),
            "prior_year_source_page": clean(source_row.get("official_page") or source_row.get("pdf_page")),
            "prior_year_source_row_identifier": clean(source_row.get("source_row_identifier")),
        }
        if lane_official_awards <= 0 and target_probability is not None and target_probability > 0:
            # The source-year official lane awarded no permits, while the
            # held-out following-year ladder proves that the lane became an
            # active draw.  This is a target-year official quota/program
            # transition, not a missing forecast from an active source lane.
            # The target outcome is used only to classify the scoring gap; it
            # is never supplied to the forecast.
            return (
                "TARGET_YEAR_OFFICIAL_PROGRAM_OR_QUOTA_CHANGE",
                SOURCE_CLASSIFIED,
                evidence,
            )
        if lane_official_awards <= 0 and target_probability is not None and target_probability <= 0:
            # An explicit zero-award source lane is not permission to borrow
            # the hunt total or another residency's permits.  With a zero
            # following-year result, the intentionally blank/no-probability
            # forecast is fully explained by the official zero-quota lane.
            return (
                "SOURCE_LIMITATION_PRIOR_YEAR_ZERO_AWARD_LANE",
                SOURCE_CLASSIFIED,
                evidence,
            )
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
        if probability is not None and probability <= 0:
            # A source-year observed zero with real applicants is not a
            # defensible next-year zero forecast.  The engine deliberately
            # leaves it blank; this is a documented source limitation rather
            # than a missing probability that should be fabricated.
            return (
                "SOURCE_SAFETY_BLOCKED_PRIOR_YEAR_ZERO_OUTCOME",
                SOURCE_CLASSIFIED,
                evidence,
            )
        conditional_evidence = (verified_conditional_abstentions or {}).get(key)
        if conditional_evidence:
            return (
                "SOURCE_SAFETY_NO_COHORT_AND_NO_OBSERVED_TRANSITION",
                SOURCE_CLASSIFIED,
                {**evidence, **conditional_evidence},
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


def run(
    source_truth: Path,
    actual_gaps: Path,
    output: Path,
    source_year: int,
    target_year: int,
    identity_crosswalk: Path | None = None,
    history_truth: Path | None = None,
    frozen_predictions: Path | None = None,
    reconcile_identities: bool = False,
) -> dict[str, object]:
    initialize_crosswalk(source_year, target_year)
    if reconcile_identities:
        # Match the exact-code frozen scorer. A later crosswalk cannot supply
        # source-lane evidence for a different physical historical identity.
        scorer.HUNT_CODE_CROSSWALK = {}
        scorer.ACTIVE_SCORING_HUNT_CODE_ALIASES = {}
    identity_blocks = blocked_identity_decisions(identity_crosswalk)
    if bool(history_truth) != bool(frozen_predictions):
        raise ValueError("Conditional abstention review requires both history truth and frozen predictions")
    history_rows = read_csv(history_truth) if history_truth else []
    prediction_rows = read_csv(frozen_predictions) if frozen_predictions else []
    conditional_evidence = conditional_abstention_evidence(history_rows, prediction_rows, source_year) if history_rows else {}
    preference_evidence = preference_abstention_evidence(history_rows, prediction_rows, source_year) if reconcile_identities else {}
    exact_rows: dict[tuple[str, str, str, str, str], list[tuple[scorer.ActualPoint, dict[str, str]]]] = defaultdict(list)
    lanes: set[tuple[str, str, str, str]] = set()
    hunts: set[tuple[str, str, str]] = set()

    source_rows = read_csv(source_truth)
    if reconcile_identities:
        from scripts.project_legacy_canonical_for_blind_scoring import expand_actual, source_pool_identity
        source_rows = expand_actual(source_rows)
        for item in source_rows:
            item['draw_pool'] = source_pool_identity(item, scorer.family_from_actual(item))
    for source_row in source_rows:
        for point in scorer.actual_points_from_row(source_row):
            key = point_key(point)
            exact_rows[key].append((point, source_row))
            lanes.add(key[:4])
            hunts.add(key[:3])

    # Index each lane's official awards once.  The previous per-gap scan of
    # every source point row was mathematically identical but quadratic on a
    # full statewide fold.  Distinct point keys count once; conflicting source
    # duplicates remain the responsibility of scoring-integrity validation.
    awards_by_lane_point: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(dict)
    for source_key, source_values in exact_rows.items():
        awards_by_lane_point[source_key[:4]][source_key[4]] = max(
            [float(source_point.actual_drawn) for source_point, _ in source_values] or [0.0]
        )
    source_lane_official_awards = {
        lane: sum(by_point.values()) for lane, by_point in awards_by_lane_point.items()
    }

    output_rows: list[dict[str, object]] = []
    for row in read_csv(actual_gaps):
        if clean(row.get("scoring_decision")) not in MISSING_SCOREABLE_ACTUAL_DECISIONS:
            continue
        classification, status, evidence = classify_gap(
            row,
            exact_rows=exact_rows,
            lanes=lanes,
            hunts=hunts,
            source_lane_official_awards=source_lane_official_awards,
            blocked_identities=identity_blocks,
            verified_conditional_abstentions=conditional_evidence,
        )
        replay = preference_evidence.get(gap_key(row))
        if replay and exact_rows.get(gap_key(row)) and evidence.get('prior_year_source_file'):
            classification = replay['abstention_classification']
            status = SOURCE_CLASSIFIED
            evidence.update(replay)
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
        "conditional_abstention_history_truth": str(history_truth or ""),
        "conditional_abstention_history_truth_sha256": sha256(history_truth) if history_truth else "",
        "conditional_abstention_frozen_predictions": str(frozen_predictions or ""),
        "conditional_abstention_frozen_predictions_sha256": sha256(frozen_predictions) if frozen_predictions else "",
        "source_history_maximum_year_used": source_year,
        "independently_verified_conditional_abstention_count": len(conditional_evidence),
        "actual_gaps": str(actual_gaps),
        "actual_gaps_sha256": sha256(actual_gaps),
        "identity_crosswalk": "" if identity_crosswalk is None else str(identity_crosswalk),
        "identity_crosswalk_sha256": "" if identity_crosswalk is None else sha256(identity_crosswalk),
        "blocked_identity_source_hunt_count": len(identity_blocks),
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


def preference_abstention_evidence(history_rows, predictions, source_year):
    """Recompute the existing program/residency transition gate from past truth."""
    from engine.utah_draw_predictive import preference_antlerless as antlerless, dedicated_hunter as dh
    from engine.utah_draw_predictive.run_all_families import _with_historical_target_metadata
    from scripts.project_legacy_canonical_for_blind_scoring import project_predictions, dedicated_pool
    source = [r for r in history_rows if 2017 <= (_row_year(r) or 0) <= source_year]
    years = {_row_year(r) for r in source}
    prepared = _with_historical_target_metadata(source, source_year, source_year + 1)
    counts, enrollment_totals = {}, {}
    for owner, label in ((antlerless, 'antlerless'), (dh, 'dedicated')):
        ladders, _, totals = owner._build_truth_ladders(prepared, years)
        if label == 'dedicated':
            enrollment_totals = totals
        _, _, transitions = owner._build_retention_and_zero_growth(ladders)
        counts[label] = transitions
    verified = {}
    for row in project_predictions(predictions):
        if (row.get('algorithm_status') != 'NO_TRANSITION_EVIDENCE'
                or scorer.prediction_probability(row)[0] is not None):
            continue
        family = row.get('family')
        residency = dh._residency_lane(row)
        reasons = clean(row.get('reason_codes'))
        if family == 'dedicated_hunter':
            row['draw_pool'] = dedicated_pool(row)
            lane = dh._dedicated_hunter_lane(row)
            if 'NO_THREE_YEAR_ENROLLMENT_EXPIRATION_EVIDENCE' in reasons:
                expiration_key = (lane, row['hunt_code'], source_year - 2)
                if expiration_key not in enrollment_totals:
                    verified[scorer.prediction_alignment_key(row)[:5]] = {
                        'source_history_years_verified': ','.join(map(str, sorted(years))),
                        'required_expiring_cohort_draw_year': source_year - 2,
                        'expiring_cohort_present': False,
                        'program_residency_abstention_replayed': True,
                        'abstention_classification': 'SOURCE_SAFETY_NO_THREE_YEAR_EXPIRING_ENROLLMENT_COHORT',
                    }
                continue
            count = counts['dedicated'].get((lane, residency), 0)
        elif family in {'preference_antlerless_deer', 'preference_antlerless_elk', 'preference_doe_pronghorn'}:
            count = counts['antlerless'].get((row['draw_system_type'], residency), 0)
        else:
            continue
        if count == 0 and 'NO_PROGRAM_RESIDENCY_TRANSITION_EVIDENCE' in reasons:
            verified[scorer.prediction_alignment_key(row)[:5]] = {
                'source_history_years_verified': ','.join(map(str, sorted(years))),
                'source_adjacent_transition_count': count,
                'program_residency_abstention_replayed': True,
                'abstention_classification': 'SOURCE_SAFETY_NO_PROGRAM_RESIDENCY_TRANSITION',
            }
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-truth", required=True, type=Path)
    parser.add_argument("--actual-gaps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-year", required=True, type=int)
    parser.add_argument("--target-year", required=True, type=int)
    parser.add_argument("--identity-crosswalk", type=Path)
    parser.add_argument("--history-truth", type=Path)
    parser.add_argument("--frozen-predictions", type=Path)
    args = parser.parse_args()
    manifest = run(
        args.source_truth,
        args.actual_gaps,
        args.output,
        args.source_year,
        args.target_year,
        args.identity_crosswalk,
        args.history_truth,
        args.frozen_predictions,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
