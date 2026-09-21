#!/usr/bin/env python3
"""Assemble validated PDF lanes and isolated Bear diagnostics, never production.

This audit calls the EXISTING Bear owner. It does not certify forecasts, promote
canonicals, infer boundary equivalence, or count six years as six tested folds.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_bear_pdf_truth_year import COUNTS, LANES, digest, dump, protected_paths

YEARS = list(range(2020, 2026))
AVAILABILITY = {"BR1001": LANES, "BR1007": ("Resident",), "BR1018": ("Nonresident",)}


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def identity(name):
    # Case/spacing equivalence only; not a boundary or fuzzy identity join.
    return re.sub(r"\s", "", name).casefold()


def transition_status(source, point):
    if point == 0:
        return "ZERO_POINT_ENTRY_REQUIRES_SEPARATE_DEMAND_EVIDENCE", ""
    if source is None:
        return "NO_TRANSITION_EVIDENCE", "Source-year prior-point row is absent; not an inferred zero."
    cohort = int(source["eligible_applicants"]) - int(source["total_permits"])
    if cohort == 0:
        return "NO_TRANSITION_EVIDENCE", "No unsuccessful source cohort at the preceding point; no individual return/arrival link is published."
    return "SOURCE_COHORT_PRESENT_NOT_PROVEN_SAME_HUNT_RETURN", "Aggregate unsuccessful count is not proof of next-year individual participation."


def assemble(root, out):
    points, totals, summaries, input_hashes, comparisons = [], [], [], {}, []
    for year in YEARS:
        run = root / (f"{year}_v2" if year == 2021 else f"{year}_v1")
        summary = json.loads((run / "summary.json").read_text())
        # A documented canonical NAME defect may not rewrite the PDF extract.
        comparison = summary["canonical_comparison"]
        if any(item["field"] != "hunt_name" for item in comparison["mismatches"]) or comparison["pdf_keys_missing_from_canonical"]:
            raise ValueError(f"Unresolved count/identity coverage mismatch in {year}")
        if not summary["source"]["matches_retained_bytes"]:
            raise ValueError(f"Official source replaced in {year}; review first")
        frozen = json.loads((run / "pdf_extract_freeze.json").read_text())
        for name, expected in frozen.items():
            if digest(run / name) != expected:
                raise ValueError(f"Frozen extraction changed: {run / name}")
            input_hashes[(run / name).relative_to(ROOT).as_posix()] = expected
        if digest(run / f"{str(year)[2:]}_drawing_odds.pdf") != summary["source"]["fresh_sha256"]:
            raise ValueError("Source snapshot changed after extraction")
        points.extend(read_rows(run / f"bear_{year}_pdf_point_lanes.csv"))
        totals.extend(read_rows(run / f"bear_{year}_pdf_printed_totals.csv"))
        summaries.append(summary)
        comparisons.extend({"year": year, **item} for item in comparison["mismatches"])

    # A lane projection sourced from the PDF, not from a canonical or DATABASE.
    for row in points:
        row.update(metric_scope=row["residency"].lower(),
                   bear_source_identity_source="RETAINED_OFFICIAL_BLACK_BEAR_PDF",
                   bear_source_identity_file=row["source_file"], qa_status="OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED")
    write_rows(out / "bear_pdf_history_2020_2025_point_lanes.csv", points)
    keyed = {(int(row["actual_draw_year"]), row["hunt_code"], row["residency"], int(row["points"])): row for row in points}
    if len(keyed) != len(points):
        raise ValueError("Duplicate point-lane keys")
    lane_groups = defaultdict(list)
    for row in points:
        lane_groups[(int(row["actual_draw_year"]), row["hunt_code"], row["residency"])].append(row)
    audit = []
    for row in totals:
        year, code, lane = int(row["actual_draw_year"]), row["hunt_code"], row["residency"]
        source_rows = lane_groups[year, code, lane]
        calculated = {field: sum(int(item[field]) for item in source_rows) for field in COUNTS}
        if any(calculated[field] != int(row[field]) for field in COUNTS):
            raise ValueError(f"Double-counting/totals mismatch at {(year, code, lane)}")
        audit.append({"hunt_code": code, "residency": lane, "year": year, "hunt_name": row["hunt_name"],
                      "draw_program": row["draw_pool"], "applicants": calculated["eligible_applicants"],
                      "permits": calculated["total_permits"], "bonus_permits": calculated["bonus_permits"],
                      "regular_permits": calculated["regular_permits"], "printed_total_applicants": row["eligible_applicants"],
                      "calculated_total_applicants": calculated["eligible_applicants"], "printed_total_permits": row["total_permits"],
                      "calculated_total_permits": calculated["total_permits"], "printed_total_match": True,
                      "source_file": row["source_file"], "pdf_hash": row["source_sha256"], "pdf_page": row["pdf_page"]})
    write_rows(out / "audit_bear_2020_2025.csv", audit)
    dump(out / "canonical_discrepancies.json", comparisons)
    dump(out / "history_freeze.json", {"inputs": input_hashes, "output_sha256": digest(out / "bear_pdf_history_2020_2025_point_lanes.csv")})

    guide_path = ROOT / "audits/bear_availability_validation_20260919/inventory_v4/inventory.json"
    guide = json.loads(guide_path.read_text())
    source = guide["sources"]["2026"]
    if digest(ROOT / source["path"]) != source["sha256"]:
        raise ValueError("2026 guidebook changed since reviewed inventory")
    current = {row["hunt_code"]: row for row in guide["guidebook_rows"]["2026"]}
    if len(current) != 99:
        raise ValueError("Unexpected reviewed guidebook code inventory")
    crosswalk_path = ROOT / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
    crosswalk = read_rows(crosswalk_path)
    names = defaultdict(dict)
    for row in totals:
        names[row["hunt_code"]][int(row["actual_draw_year"])] = row["hunt_name"]
    lineage = []
    for code in sorted(set(names) | set(current)):
        history = names[code]
        links = [row for row in crosswalk if code in (row["current_2026_code"], row["historical_2025_code"])]
        lineage.append({"hunt_code": code, "in_2026_guidebook": code in current,
                        "2026_name": current.get(code, {}).get("hunt_name", ""),
                        "2026_program": current.get(code, {}).get("permit_type", ""),
                        "first_seen_in_reviewed_window": min(history) if history else "",
                        "last_seen_in_reviewed_window": max(history) if history else "",
                        "years_present": "|".join(map(str, sorted(history))),
                        "names_by_year": json.dumps(history, sort_keys=True),
                        "historical_name_change": len({identity(name) for name in history.values()}) > 1,
                        "exact_2025_code_present": 2025 in history,
                        "code_status": "CURRENT_NO_EXACT_CODE_HISTORY" if code in current and not history else
                                       "NOT_IN_CURRENT_GUIDEBOOK_NOT_PROOF_OF_PERMANENT_RETIREMENT" if code not in current else "CURRENT_WITH_EXACT_CODE_HISTORY",
                        "crosswalk_statuses": "|".join(row["mapping_status"] for row in links),
                        "crosswalk_notes": " | ".join(row["review_note"] for row in links),
                        "automatic_stack_transfer_authorized_by_this_audit": False,
                        "identity_review": "CODE_NAME_DIAGNOSTIC_ONLY_BOUNDARY_AND_PROGRAM_TRANSITIONS_REQUIRE_REVIEW"})
    write_rows(out / "bear_code_lineage_2020_2026.csv", lineage)

    transitions = []
    for target in points:
        target_year, code, lane, point = int(target["actual_draw_year"]), target["hunt_code"], target["residency"], int(target["points"])
        if target_year == YEARS[0]:
            continue
        prior = keyed.get((target_year - 1, code, lane, point - 1)) if point > 0 else None
        status, reason = transition_status(prior, point)
        if prior and (prior["draw_pool"] != target["draw_pool"] or identity(prior["hunt_name"]) != identity(target["hunt_name"])):
            status, reason = "IDENTITY_OR_PROGRAM_CHANGE_REQUIRES_REVIEW", "No automatic applicant transfer across name/program changes."
        transitions.append({"source_year": target_year - 1, "target_year": target_year, "hunt_code": code,
                            "residency": lane, "draw_program": target["draw_pool"], "target_points": point,
                            "source_points": point - 1 if point else "", "source_applicants": prior["eligible_applicants"] if prior else "",
                            "source_awarded": prior["total_permits"] if prior else "",
                            "potential_unsuccessful_cohort": int(prior["eligible_applicants"]) - int(prior["total_permits"]) if prior else "",
                            "status": status, "reason": reason, "prediction": "",
                            "source_pdf": prior["source_file"] if prior else "", "source_page": prior["pdf_page"] if prior else "",
                            "target_pdf": target["source_file"], "target_page": target["pdf_page"],
                            "role": "POST_SOURCE_AUDIT_NOT_A_BLIND_FORECAST_OR_PERSON_LINKAGE"})
    write_rows(out / "bear_point_transition_evidence_2020_2025.csv", transitions)

    availability_history = []
    for year in YEARS:
        for code, lanes in AVAILABILITY.items():
            for lane in lanes:
                availability_history.append({"year": year, "hunt_code": code, "residency": lane,
                                             "present_in_draw_ladders": (year, code, lane) in lane_groups,
                                             "historical_catalog_status": "NOT_VERIFIED_NO_DATED_CATALOG_LOCATED",
                                             "p_draw": "", "p_availability": "",
                                             "reason": "A 2026 catalog identity cannot prove availability/closures for earlier years."})
    write_rows(out / "bear_availability_historical_evidence.csv", availability_history)

    # Current target context is intentionally loaded ONLY after the PDF history
    # is written and frozen. It is not a source of historical counts or labels.
    db_path = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    targets = [row for row in read_rows(db_path) if row["hunt_code"] in set(current) | set(AVAILABILITY)]
    if Counter(row["hunt_code"] for row in targets) != Counter({code: 1 for code in set(current) | set(AVAILABILITY)}):
        raise ValueError("Current target missing/duplicated")
    from engine.utah_draw_predictive import bear
    from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields

    enabled, reads = [True], []
    allowed_pdf = (ROOT / "pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/official_dwr_archive/black_bear/25_drawing_odds.pdf").resolve()

    def guard(event, arguments):
        if not enabled[0] or event != "open" or not isinstance(arguments[0], (str, bytes)):
            return
        path = Path(arguments[0]).resolve()
        mode, flags = arguments[1], arguments[2]
        if (mode and any(c in mode for c in "wax+")) or (flags and flags & 3 in (1, 2)):
            raise RuntimeError(f"Builder attempted a write: {path}")
        if path.suffix.lower() in {".csv", ".json", ".pdf"} and path.is_relative_to(ROOT):
            reads.append(path.relative_to(ROOT).as_posix())
            if path != allowed_pdf:
                raise RuntimeError(f"Hidden data dependency outside frozen PDF history: {path}")

    sys.addaudithook(guard)
    try:
        fresh, report = bear.build_bear_bonus_predictions(points, targets, 2026, YEARS)
    finally:
        enabled[0] = False
    fresh = [sanitize_modeled_probability_fields(dict(row)) for row in fresh]
    bear.validate_bear_availability_identity(fresh, targets)
    write_rows(out / "fresh_2026_engine_diagnostic_only.csv", fresh)
    dump(out / "fresh_2026_engine_diagnostic_report.json", report)
    availability = [row for row in fresh if row.get("algorithm_status") == "MODELED_AVAILABILITY"]
    write_rows(out / "fresh_2026_availability.csv", availability)
    if len(availability) != 4:
        raise ValueError("Fresh availability count differs from four")
    actual_lanes = {(row["hunt_code"], row["residency"]) for row in fresh if row["hunt_code"] in current}
    expected_lanes = {(code, lane) for code in current for lane in LANES}
    missing = sorted(expected_lanes - actual_lanes)
    # A coverage inventory is NOT a claim that each lane has enough evidence
    # for probability. Preserve pending/zero-allocation statuses from the owner.
    coverage = []
    for code, lane in sorted(expected_lanes):
        rows = [row for row in fresh if row["hunt_code"] == code and row["residency"] == lane]
        coverage.append({"hunt_code": code, "residency": lane, "2026_program": current[code]["permit_type"],
                         "engine_rows": len(rows), "statuses": "|".join(sorted({row.get("algorithm_status", "") for row in rows})),
                         "has_raw_probability": any(row.get("p_draw") not in (None, "") for row in rows),
                         "certified_probability": "", "publication_status": "WITHHELD_NOT_CERTIFIED"})
    write_rows(out / "current_2026_draw_lane_inventory.csv", coverage)
    prospective = []
    for row in fresh:
        code, lane = row["hunt_code"], row["residency"]
        point_text = str(row.get("points", "")).strip()
        prior = None
        if code in AVAILABILITY:
            status, reason = "MODELED_AVAILABILITY", "Non-draw product; draw probability is not applicable."
        elif 2025 not in names[code]:
            status, reason = "IDENTITY_TRANSITION_REQUIRES_REVIEW", "No exact-code 2025 ladder; existing engine aliases are not approved by this audit."
        elif not point_text.isdigit():
            status, reason = "EXCLUDED_OR_INSUFFICIENT_EVIDENCE", "Owner emitted no point-level forecast for this current lane."
        else:
            point = int(point_text)
            prior = keyed.get((2025, code, lane, point - 1)) if point else None
            status, reason = transition_status(prior, point)
            # Prior aggregate arrival evidence may exist despite a zero current
            # returning cohort. Do not claim it proves a particular returning
            # applicant, and never substitute it with a made-up probability.
            adjacent_evidence = sum(
                1 for source_year in range(2020, 2025)
                if (source_year, code, lane, point - 1) in keyed
                and (source_year + 1, code, lane, point) in keyed
                and keyed[source_year, code, lane, point - 1]["draw_pool"] == row["bear_draw_subtype"]
                and int(keyed[source_year + 1, code, lane, point]["eligible_applicants"]) > 0
            ) if point else 0
            if status == "NO_TRANSITION_EVIDENCE" and adjacent_evidence:
                status, reason = "HISTORICAL_DEMAND_EVIDENCE_ONLY_NOT_CERTIFIED", "Historical adjacent aggregate demand exists; current returning cohort does not establish a probability."
        prospective.append({"hunt_code": code, "residency": lane, "points": point_text,
                            "evidence_status": status, "reason": reason,
                            "source_applicants": prior["eligible_applicants"] if prior else "",
                            "source_awarded": prior["total_permits"] if prior else "",
                            "p_draw": "", "certified_p_draw": "",
                            "publication_status": "WITHHELD_NOT_CERTIFIED" if code not in AVAILABILITY else "AVAILABILITY_NOT_DRAW_ODDS"})
    write_rows(out / "current_2026_point_evidence_gate.csv", prospective)
    result = {"status": "PDF_HISTORY_VALIDATED_ISOLATED_DIAGNOSTIC_NOT_CERTIFIED",
              "years": YEARS, "year_summaries": summaries, "point_rows": len(points), "audit_lane_year_rows": len(audit),
              "canonical_name_mismatches": len(comparisons), "canonical_count_mismatches": 0,
              "historical_years": 6, "available_adjacent_year_comparisons": 5, "certification_folds_executed": 0,
              "2026_guidebook_codes": len(current), "2026_expected_draw_residency_lanes": len(expected_lanes),
              "2026_fresh_draw_residency_lanes": len(actual_lanes), "missing_current_draw_lanes": missing,
              "fresh_availability_rows": len(availability), "historical_availability_proven": False,
              "current_catalog_role": "2026_TARGET_CONTEXT_ONLY_AFTER_PDF_HISTORY_FREEZE",
              "current_catalog_sha256": digest(db_path), "builder_data_reads": sorted(set(reads)),
              "lineage_statuses": dict(Counter(row["code_status"] for row in lineage)),
              "transition_statuses": dict(Counter(row["status"] for row in transitions)),
              "prospective_point_evidence_statuses": dict(Counter(row["evidence_status"] for row in prospective)),
              "crosswalk_sha256": digest(crosswalk_path), "guidebook_inventory_sha256": digest(guide_path),
              "guidebook_source": source,
              "release_decision": "DO_NOT_PROMOTE", "protected_production_files_overwritten": False,
              "limitations": ["Historical catalog availability not proven for 2020-2025.",
                              "Same code/name is not proof of unchanged boundaries or of individual return.",
                              "Raw engine diagnostics retain existing model/crosswalk assumptions; no accuracy certification was run.",
                              "Six source years support baseline development, not an automatic certification pass.",
                              "2023 canonical name defects are corrected only in independent PDF-derived audit rows."]}
    dump(out / "summary.json", result)
    dump(out / "artifact_hashes.json", {path.name: digest(path) for path in sorted(out.iterdir()) if path.is_file()})
    print(json.dumps({key: value for key, value in result.items() if key not in {"year_summaries", "guidebook_source"}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year-audit-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    if not out.is_relative_to(ROOT / "audits") or out == ROOT / "audits" or out.exists():
        parser.error("Use a NEW directory below audits/; no existing evidence may be overwritten")
    before = protected_paths()
    out.mkdir(parents=True)
    dump(out / "protected_before.json", before)
    try:
        assemble(args.year_audit_root.resolve(), out)
    finally:
        after = {path: digest(ROOT / path) for path in before}
        changed = [path for path in before if before[path] != after[path]]
        dump(out / "protected_after.json", {"files": after, "changed": changed, "unchanged": len(before) - len(changed)})
        if changed:
            raise RuntimeError(f"Protected files changed: {changed}")


if __name__ == "__main__":
    main()
