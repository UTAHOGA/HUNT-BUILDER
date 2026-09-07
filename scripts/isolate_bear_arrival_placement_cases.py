#!/usr/bin/env python3
"""Split frozen Bear false guarantees into arrival, quota, and residual sets.

This is a source-only audit. It uses the limited-entry false-guarantee report
and historical canonical ladders available *before each source draw year*.
It does not change forecasts, truth, quota inputs, or the engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.bear import (
    LIMITED_ENTRY_BEAR_HUNT,
    _build_truth_ladders,
)


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float:
    try:
        return float(clean(value).replace(",", ""))
    except ValueError:
        return 0.0


def integer(value: object) -> int:
    return int(round(number(value)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def exact_transition_history(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
    *,
    hunt_code: str,
    residency: str,
    source_rung: int,
) -> list[dict[str, object]]:
    years = sorted(
        year
        for subtype, year, code, lane in ladders
        if subtype == LIMITED_ENTRY_BEAR_HUNT and code == hunt_code and lane == residency
    )
    output: list[dict[str, object]] = []
    for year in years:
        if year + 1 not in years:
            continue
        source = ladders[(LIMITED_ENTRY_BEAR_HUNT, year, hunt_code, residency)].get(source_rung, {})
        target = ladders[(LIMITED_ENTRY_BEAR_HUNT, year + 1, hunt_code, residency)].get(source_rung + 1, {})
        unsuccessful = max(0, int(source.get("eligible", 0)) - int(source.get("bonus", 0)) - int(source.get("regular", 0)))
        observed_next = max(0, int(target.get("eligible", 0)))
        supplied = min(unsuccessful, observed_next)
        output.append(
            {
                "history_source_year": year,
                "history_target_year": year + 1,
                "history_unsuccessful_cohort": unsuccessful,
                "history_target_applicants": observed_next,
                "history_residual_arrivals": max(0, observed_next - supplied),
            }
        )
    return output


def enrich_arrival_case(
    row: dict[str, str],
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> dict[str, object]:
    source_code = clean(row.get("source_hunt_code")) or clean(row["hunt_code"])
    residency = clean(row["residency"])
    source_rung = integer(row["point_rung"]) - 1
    transitions = exact_transition_history(
        ladders,
        hunt_code=source_code,
        residency=residency,
        source_rung=source_rung,
    )
    positive = [transition for transition in transitions if int(transition["history_residual_arrivals"]) > 0]
    result = dict(row)
    result.update(
        {
            "history_identity_hunt_code": source_code,
            "history_source_rung": source_rung,
            "prior_exact_transition_count": len(transitions),
            "prior_exact_positive_arrival_transition_count": len(positive),
            "prior_exact_arrival_total": sum(int(item["history_residual_arrivals"]) for item in transitions),
            "prior_exact_arrival_mean": round(
                sum(int(item["history_residual_arrivals"]) for item in transitions) / len(transitions), 6
            ) if transitions else 0.0,
            "prior_exact_arrival_transition_years": ";".join(
                f"{item['history_source_year']}->{item['history_target_year']}:{item['history_residual_arrivals']}"
                for item in transitions
            ),
            "repeatable_exact_arrival_placement": "TRUE" if len(positive) >= 2 else "FALSE",
            "repair_scope": (
                "EXACT_REPEATABLE_ARRIVAL_PLACEMENT_CANDIDATE"
                if len(positive) >= 2
                else "NO_EXACT_REPEATABILITY_DO_NOT_ADD_TARGETED_ARRIVAL"
            ),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--false-guarantee-audit", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.out_dir}")

    all_rows = read_csv(args.false_guarantee_audit)
    if len(all_rows) != 182:
        raise ValueError(f"Expected the complete 182-case limited-entry audit, found {len(all_rows)}")
    positive_stack = [row for row in all_rows if number(row.get("target_stack_excess_over_forecast")) > 0]
    quota_reduction = [
        row
        for row in all_rows
        if clean(row.get("permit_alignment")) == "TARGET_LOWER"
        # A lower target quota plus an actually smaller stack is a distinct
        # permit-reduction condition. A zero-stack row is not evidence that a
        # quota decline explains the false guarantee, so leave it for the
        # simulator-review residual rather than quietly folding it into either
        # repair population.
        and number(row.get("target_stack_excess_over_forecast")) < 0
    ]
    residual = [row for row in all_rows if row not in positive_stack and row not in quota_reduction]
    if len(positive_stack) != 130:
        raise ValueError(f"Expected 130 positive target-stack cases, found {len(positive_stack)}")
    if len(quota_reduction) != 42:
        raise ValueError(f"Expected 42 quota-reduction cases, found {len(quota_reduction)}")

    truth_rows = read_csv(args.truth)
    ladders_by_source_year: dict[int, dict[tuple[str, int, str, str], dict[int, dict[str, int]]]] = {}
    for source_year in sorted({integer(row["source_draw_year"]) for row in positive_stack}):
        source_truth = [
            truth
            for truth in truth_rows
            if integer(truth.get("actual_draw_year") or truth.get("source_year") or truth.get("year")) <= source_year
        ]
        ladders, _, _ = _build_truth_ladders(source_truth, set(range(2017, source_year + 1)))
        ladders_by_source_year[source_year] = ladders
    enriched = [
        enrich_arrival_case(row, ladders_by_source_year[integer(row["source_draw_year"])])
        for row in positive_stack
    ]
    repeatable = [row for row in enriched if row["repeatable_exact_arrival_placement"] == "TRUE"]
    not_repeatable = [row for row in enriched if row["repeatable_exact_arrival_placement"] != "TRUE"]
    quota_rows = [
        {
            **row,
            "repair_scope": "EXCLUDED_TARGET_PERMIT_REDUCTION_NOT_AN_ARRIVAL_REPAIR",
        }
        for row in quota_reduction
    ]
    residual_rows = [
        {
            **row,
            "repair_scope": "UNEXPLAINED_BY_POSITIVE_STACK_OR_TARGET_PERMIT_REDUCTION_REQUIRES_SIMULATOR_REVIEW",
        }
        for row in residual
    ]
    args.out_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.out_dir / "positive_target_stack_cases_with_exact_history.csv", enriched)
    write_csv(args.out_dir / "repeatable_exact_arrival_placement_candidates.csv", repeatable)
    write_csv(args.out_dir / "positive_stack_without_exact_repeatability.csv", not_repeatable)
    write_csv(args.out_dir / "target_permit_reduction_excluded_from_arrival_repair.csv", quota_rows)
    write_csv(args.out_dir / "residual_simulator_review_cases.csv", residual_rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "source_only_bear_arrival_placement_isolation",
        "scope": "The 182 frozen limited-entry Bear hunting false guarantees only. Restricted pursuit and non-draw Bear availability are absent by construction.",
        "positive_target_stack_cases": len(enriched),
        "repeatable_exact_arrival_placement_candidates": len(repeatable),
        "positive_stack_without_exact_repeatability": len(not_repeatable),
        "target_permit_reduction_cases_excluded_from_arrival_repair": len(quota_rows),
        "residual_cases_requiring_simulator_review": len(residual_rows),
        "repeatable_candidates_by_source_year": dict(sorted(Counter(clean(row["source_draw_year"]) for row in repeatable).items())),
        "rule": "Repeatable means at least two positive residual-arrival transitions at the exact historical hunt code, residency lane, and source point rung, available before the forecast source draw year.",
        "status": "PASS_SOURCE_ONLY_ISOLATION_COMPLETE",
    }
    (args.out_dir / "isolation_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
