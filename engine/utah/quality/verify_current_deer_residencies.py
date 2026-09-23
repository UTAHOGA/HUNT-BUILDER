"""Verify local deer allocation staging without authorizing publication.

Reuses the owning official quota feeder, validates both residency rows, and
keeps current Planner hunt totals separate from regular-draw allocations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
from collections import Counter
from pathlib import Path

from engine.utah.current_year_allotments import apply_official_general_deer_regular_quotas

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_rows(targets, lanes, expected, planner, year):
    """Return measured rows and failures; missing lanes never mean zero."""
    failures, review = [], []
    expected = {r["hunt_code"]: r for r in expected if r.get("target_permits_scope") == "REGULAR_DRAW_AFTER_PROGRAM_ALLOCATIONS"}
    target_counts = Counter(r["hunt_code"] for r in targets)
    if set(target_counts) != set(expected) or any(n != 1 for n in target_counts.values()):
        failures.append("TARGET_CODE_SET_OR_DUPLICATES")
    lane_counts = Counter((r["hunt_code"], r["residency"]) for r in lanes)
    keys = {(code, lane) for code in expected for lane in ("Resident", "Nonresident")}
    if set(lane_counts) != keys or any(n != 1 for n in lane_counts.values()):
        failures.append("RESIDENCY_CODE_SET_OR_DUPLICATES")
    by_lane = {(r["hunt_code"], r["residency"]): r for r in lanes}
    planner_current = [r for r in planner if r.get("hunt_year") == str(year)]
    counts = Counter(r["hunt_code"] for r in planner_current)
    by_planner = {r["hunt_code"]: r for r in planner_current}
    by_target = {r["hunt_code"]: r for r in targets}
    for code, official in sorted(expected.items()):
        target = by_target.get(code, {})
        if target != official:
            failures.append(f"TARGET_SOURCE_CELL_MISMATCH:{code}")
        values = [int(official[k]) for k in ("target_permits_res", "target_permits_nr", "target_permits_total")]
        if values[0] + values[1] != values[2]:
            failures.append(f"UNBALANCED_REGULAR_DRAW:{code}")
        for residency, allocation in zip(("Resident", "Nonresident"), values[:2]):
            lane = by_lane.get((code, residency), {})
            required = {"draw_allocation": str(allocation), "draw_allocation_total": str(values[2]),
                        "scope": official["target_permits_scope"],
                        "source_sha256": official["target_permits_source_sha256"]}
            if any(lane.get(k) != v for k, v in required.items()):
                failures.append(f"RESIDENCY_SOURCE_CELL_MISMATCH:{code}:{residency}")
        p = by_planner.get(code, {})
        total = p.get("permits_2026_total", "")
        if counts[code] != 1 or not total.isdigit():
            failures.append(f"MISSING_OR_AMBIGUOUS_PLANNER_TOTAL:{code}")
            planner_total = None
        else:
            planner_total = int(total)
        review.append({"hunt_code": code, "resident_regular": values[0],
                       "nonresident_regular": values[1], "regular_draw_allocation": values[2],
                       "planner_hunt_total": planner_total,
                       "planner_total_differs": planner_total != values[2],
                       "planner_regular_difference_status": (
                           "REFERENCE_TOTAL_DIFFERENCE_NON_BLOCKING"
                           if planner_total is not None and planner_total != values[2]
                           else "NO_DIFFERENCE" if planner_total is not None
                           else "PLANNER_REFERENCE_UNRESOLVED"
                       ),
                       "totals_are_additive": False,
                       "planner_source_url": p.get("source_url", "")})
    return review, failures


def audit(staging, planner_path, authority_path):
    report = {"data_status": "BLOCKED", "promotion_status": "BLOCKED_LOCAL_STAGING_ONLY",
              "failures": [], "promotion_blockers": [], "rows": []}
    try:
        manifest_path = staging / "official_general_deer_regular_quota_audit.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = ROOT / manifest["source"]
        database = ROOT / manifest["database_identity_source"]
        if digest(source) != manifest["sha256"] or digest(database) != manifest["database_sha256"]:
            raise ValueError("SOURCE_OR_DATABASE_CHANGED_SINCE_EXPORT")
        for name in ("current_general_deer_target_rows.csv", "current_general_deer_residency_rows.csv"):
            if digest(staging / name) != manifest["outputs"][name]["sha256"]:
                report["failures"].append(f"STAGED_HASH_MISMATCH:{name}")
        expected, official_audit = apply_official_general_deer_regular_quotas(
            read_rows(database), source, int(manifest["forecast_year"]))
        # The feeder records its supplied path spelling. Retain the export's
        # relative/absolute spelling after resolving and hash-checking above.
        for row in expected:
            if row.get("target_permits_source_sha256") == digest(source):
                row["target_permits_source"] = str(Path(manifest["source"]))
        review, failures = verify_rows(
            read_rows(staging / "current_general_deer_target_rows.csv"),
            read_rows(staging / "current_general_deer_residency_rows.csv"),
            expected, read_rows(planner_path), manifest["forecast_year"])
        report.update(rows=review, expected_hunts=official_audit["source_eligible_hunts"],
                      residency_rows=len(read_rows(staging / "current_general_deer_residency_rows.csv")),
                      planner_sha256=digest(planner_path), source_sha256=digest(source))
        report["failures"].extend(failures)
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
        approved = authority["truth_authority"]["current_hunt_and_permit_reference"]["verified_sha256"]
        report["database_hash_review"] = {"actual": digest(database), "approved": approved}
        if digest(database) != approved:
            report["promotion_blockers"].append("DATABASE_HASH_REVIEW_PENDING")
        report["data_status"] = "FAIL" if report["failures"] else "PASS"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["failures"].append(f"INPUT_VALIDATION_ERROR:{type(exc).__name__}:{exc}")
    try:
        importlib.import_module("engine.utah_bonus_predictive.materialize")
        report["bear_import_status"] = "PASS"
    except Exception as exc:
        report["bear_import_status"] = "FAIL"
        report["promotion_blockers"].append(f"BEAR_BUILD_IMPORT:{type(exc).__name__}:{exc}")
    # Passing these narrow checks cannot approve the remaining release gates.
    report["promotion_blockers"].append("LOCAL_STAGING_ONLY_NO_RELEASE_AUTHORIZATION")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--planner", type=Path, required=True)
    parser.add_argument("--authority", type=Path, default=ROOT / "governance/engine-authority.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; preserve prior audit and choose another path")
    report = audit(args.staging, args.planner, args.authority)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    return int(bool(report["failures"] or report["promotion_blockers"]))


if __name__ == "__main__":
    raise SystemExit(main())
