#!/usr/bin/env python3
"""Independently reconcile current core target lanes with final predictions.

The target inventory and source canonical define expected coverage; prediction
row counts never define their own denominator. Missing comparable history is
reported explicitly and must not acquire a probability or be called complete.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah_draw_predictive.classifier import classify_draw_system_type
from engine.utah_draw_predictive.permit_accessors import target_residency_permit_allocation
from engine.utah_draw_predictive.run_all_families import _big_game_bonus_db_by_code, _big_game_bonus_kind_for_db_row, _draw_system_for_big_game_bonus_kind
from engine.utah_draw_predictive.preference_general_deer import _looks_like_general_buck_deer, _looks_like_standard_pool
from engine.utah_predictive_mixed.materialize import CORE_FINAL_PROBABILITY_DESIGNS


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(value):
    return "" if value is None else str(value).strip()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(db_rows, predictions, source_rows, forecast_year=2026, details_dir=None):
    targets = _big_game_bonus_db_by_code(db_rows)
    for row in db_rows:
        if _looks_like_general_buck_deer(row) and _looks_like_standard_pool(row):
            targets[clean(row.get("hunt_code"))] = dict(row)
    by_lane = defaultdict(list)
    failures = []
    for row in predictions:
        design = clean(row.get("draw_system_type") or row.get("prediction_certification_design"))
        if design not in CORE_FINAL_PROBABILITY_DESIGNS:
            continue
        if any(clean(row.get(k)) for k in ("p_draw", "certified_p_draw")) and clean(row.get("residency")) not in {"Resident", "Nonresident"}:
            failures.append(f"AMBIGUOUS_PREDICTION_RESIDENCY:{row.get('hunt_code')}")
        by_lane[(row.get("hunt_code"), row.get("residency"))].append(row)
    source_by_code = defaultdict(list)
    source_years_by_lane = defaultdict(set)
    for row in source_rows:
        year = clean(row.get("actual_draw_year") or row.get("year"))
        if not year.isdigit() or int(year) >= forecast_year:
            continue
        for lane, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            eligible = clean(row.get("eligible_applicants")) if row.get("residency") == lane else clean(row.get(f"{prefix}_eligible_applicants"))
            if clean(row.get("points")).isdigit() and eligible and float(eligible) > 0:
                source_years_by_lane[(row.get("hunt_code"), lane, row.get("draw_system_type") or row.get("draw_design"))].add(int(year))
        if year == str(forecast_year - 1):
            source_by_code[clean(row.get("hunt_code"))].append(row)
    inventory = []
    for code, target in sorted(targets.items()):
        design = classify_draw_system_type(target)
        if design != "PREFERENCE_GENERAL_SEASON_BUCK_DEER":
            design = _draw_system_for_big_game_bonus_kind(_big_game_bonus_kind_for_db_row(target, code))
        allocation = target_residency_permit_allocation(target, forecast_year, source_year=None, draw_system_type=design)
        for lane, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            quota = allocation.for_residency(lane) if allocation.supported else None
            selected = by_lane.get((code, lane), [])
            source_years = source_years_by_lane[(code, lane, design)]
            publishable = [r for r in selected if clean(r.get("p_draw")) and "EMPTY_UPPER_STRUCTURAL_RUNG" not in clean(r.get("reason_codes")) and clean(r.get("status")) != "DISPLAY ONLY - NO FORECASTED APPLICANT COHORT"]
            source_points = set()
            successor_points = set()
            for source in source_by_code.get(code, []):
                if clean(source.get("draw_system_type") or source.get("draw_design")) != design:
                    continue
                point = clean(source.get("points"))
                if not point.isdigit():
                    continue
                eligible = clean(source.get(f"{prefix}_eligible_applicants"))
                if clean(source.get("residency")) == lane:
                    eligible = clean(source.get("eligible_applicants"))
                if eligible and float(eligible) > 0:
                    source_points.add(int(point))
                    won = clean(source.get(f"{prefix}_total_permits"))
                    if clean(source.get("residency")) == lane:
                        won = clean(source.get("total_permits"))
                    if won and float(eligible) > float(won):
                        successor_points.add(int(point) + 1)
            historical_reference = (
                "PDF_CONFIRMED_TRUTH_ONLY_BACKFILL" in clean(target.get("NOTES"))
                and not any(clean(target.get(field)) for field in ("permits_2026_res", "permits_2026_nr", "permits_2026_total", "draw_2026_system_type"))
            )
            current_authority = any(clean(target.get(field)) for field in (
                f"permits_{forecast_year}_res", f"permits_{forecast_year}_nr", f"permits_{forecast_year}_total",
                f"permits_{forecast_year}_source", "dwr_huntplanner_hunt_year"))
            # Without a current allocation these retained inventory records
            # are not eligible forecast targets. This is not a claim that the
            # hunt was eliminated; its current eligibility is unproven.
            if not current_authority:
                historical_reference = True
            conditional_withheld = {
                int(r["points"]) for r in selected
                if clean(r.get("points")).isdigit()
                and r.get("algorithm_status") == "NOT_SCORED_CONDITIONAL_RUNG_NO_TRANSITION_EVIDENCE"
                and not clean(r.get("p_draw")) and not clean(r.get("certified_p_draw"))
                and not any(year + 1 in source_years for year in source_years)
            }
            if historical_reference:
                status = "HISTORICAL_REFERENCE_ONLY"
                if publishable:
                    failures.append(f"HISTORICAL_REFERENCE_HAS_PROBABILITY:{code}:{lane}")
            elif quota is None:
                status = "WITHHELD_NO_CURRENT_PERMIT_ALLOCATION"
                if publishable:
                    failures.append(f"UNSUPPORTED_QUOTA_HAS_PROBABILITY:{code}:{lane}")
            elif quota <= 0:
                status = "INELIGIBLE_ZERO_QUOTA"
                if publishable:
                    failures.append(f"ZERO_QUOTA_HAS_PROBABILITY:{code}:{lane}")
            elif not publishable:
                status = "WITHHELD_NO_TRANSITION_EVIDENCE" if conditional_withheld else "BLOCKED_MISSING_FORECAST" if source_points else "WITHHELD_NO_COMPARABLE_SOURCE_HISTORY"
            else:
                status = "COVERED_FORECAST"
            published_points = {int(r["points"]) for r in publishable if clean(r.get("points")).isdigit()}
            expected_points = {0} | successor_points
            missing_points = sorted(expected_points - published_points - conditional_withheld) if status == "COVERED_FORECAST" else []
            # Upper display-only rows intentionally withhold predictions. An
            # actual unsuccessful successor cohort is not display-only.
            if missing_points:
                status = "BLOCKED_MISSING_SOURCE_SUCCESSOR_POINTS"
            detail_missing = []
            if details_dir:
                path = Path(details_dir) / f"{code}.json"
                detail = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                if not path.is_file() and not historical_reference:
                    detail_missing.append("MISSING_DETAIL_FILE")
                public_rows = {clean(r.get("points")): r for r in detail.get("research_ladder_rows", []) if r.get("residency") == lane and clean(r.get("draw_pool", "standard")).lower() in {"standard", "adult_general_deer", "max_weighted_split", "general_season_deer", "limited_entry_deer", "limited_entry_elk", "limited_entry_pronghorn"}}
                for row in selected:
                    point = clean(row.get("points"))
                    public = public_rows.get(point, {})
                    expected = clean(row.get("certified_p_draw"))
                    if clean(public.get("certified_p_draw")) != expected:
                        detail_missing.append(point)
                if not publishable and any(clean(r.get("certified_p_draw")) for r in public_rows.values()):
                    detail_missing.append("UNSUPPORTED_PUBLIC_PROBABILITY")
                if detail_missing:
                    status = "BLOCKED_PUBLIC_DETAIL_MISMATCH"
            if status.startswith("BLOCKED"):
                failures.append(f"{status}:{code}:{lane}")
            inventory.append({"hunt_code": code, "hunt_name": clean(target.get("hunt_name")), "design": design,
                              "residency": lane, "quota": quota, "quota_authority": allocation.authority,
                              "source_positive_point_count": len(source_points), "forecast_point_count": len(publishable),
                              "source_years": ";".join(map(str, sorted(source_years))),
                              "forecast_points": ";".join(map(str, sorted(published_points))),
                              "certified_probabilities": {
                                  clean(r.get("points")): float(r["certified_p_draw"])
                                  for r in selected if clean(r.get("certified_p_draw"))
                              },
                              "source_verified_withheld_points": ";".join(map(str, sorted(conditional_withheld))),
                              "missing_successor_points": ";".join(map(str, missing_points)),
                              "public_detail_missing_points": ";".join(detail_missing), "coverage_status": status})
    return {
        "status": "FAIL" if failures else "PASS",
        "public_details_verified": details_dir is not None,
        "public_details_directory": str(details_dir) if details_dir is not None else None,
        "target_hunt_codes": len(targets), "target_lane_count": len(inventory),
        "coverage_status_counts": dict(Counter(r["coverage_status"] for r in inventory)),
        "complete_forecast_coverage": all(r["coverage_status"] in {"COVERED_FORECAST", "INELIGIBLE_ZERO_QUOTA", "HISTORICAL_REFERENCE_ONLY"} for r in inventory),
        "complete_eligible_accounting": not failures,
        "failures": failures, "inventory": inventory,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
    parser.add_argument("--source-truth", type=Path, default=ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv")
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--details-dir", type=Path)
    parser.add_argument("--current-deer-quota-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    targets = read_csv(args.database)
    if args.current_deer_quota_source:
        from engine.utah.current_year_allotments import apply_official_general_deer_regular_quotas
        targets, quota_audit = apply_official_general_deer_regular_quotas(targets, args.current_deer_quota_source, 2026)
    report = audit(targets, read_csv(args.prediction), read_csv(args.source_truth), details_dir=args.details_dir)
    if args.current_deer_quota_source:
        report["current_deer_regular_quota_evidence"] = quota_audit
    report["sources"] = {name: {"path": str(path), "sha256": digest(path)} for name, path in [("database", args.database), ("source_truth", args.source_truth), ("prediction", args.prediction)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report["inventory"][0]))
        writer.writeheader()
        writer.writerows(report["inventory"])
    print(json.dumps({k: v for k, v in report.items() if k not in {"inventory", "sources", "failures", "current_deer_regular_quota_evidence"}}, indent=2))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
