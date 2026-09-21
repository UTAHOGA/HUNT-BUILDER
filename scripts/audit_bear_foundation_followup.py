"""Read-only retained-replay reconciliation and byte-level release preflight.

Writes new isolated evidence only; never changes old forecasts or source truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_bear_controlled_candidates import canonical, new_directory, protected_data
from scripts.build_bear_pdf_history_audit import read_rows, write_rows
from scripts.audit_bear_pdf_truth_year import digest, dump
from engine.utah_draw_predictive import bear

OLD = ROOT / "audits/prediction_release_candidates/bear_program_source_repair_20260919/folds_v2"
GAPS = {"missing_prediction_for_scoreable_actual_ladder_row", "do_not_score_missing_prediction_probability"}


def reconcile(out):
    out = new_directory(out)
    before = protected_data()
    dump(out / "protected_before.json", before)
    classified, numeric, intake, freezes = [], [], [], []
    for fold in sorted(OLD.glob("*_to_*")):
        year = int(fold.name[:4])
        freeze = json.loads((fold / "prediction_phase/source_only_freeze.json").read_text())
        for path, expected in freeze["source_hashes"].items():
            if digest(ROOT / path) != expected:
                raise ValueError(f"Retained canonical changed: {path}")
        prediction_path = fold / "prediction_phase/family_predictions.csv"
        if digest(prediction_path) != freeze["forecast_sha256"]:
            raise ValueError("Retained forecast changed")
        freezes.append({"fold": fold.name, "forecast_sha256": freeze["forecast_sha256"]})
        source_rows = read_rows(canonical(year))
        ladders, _, _ = bear._build_truth_ladders(source_rows, {year})
        intake.extend({"year": year, "program": program, "residency": residency,
                       "code_count": sum(k[0] == program and k[3] == residency for k in ladders)}
                      for program in sorted(bear.MODELED_BEAR_SUBTYPES) for residency in ("Resident", "Nonresident"))
        by_code = {r["hunt_code"]: r for r in source_rows if r.get("pdf_page") and r.get("source_scope") == "BLACK_BEAR"}
        key = lambda r: (r["hunt_code"], r["residency"], r["points"])
        actuals = {key(r): r for r in read_rows(fold / "scoring_projection/bear_actual_only.csv")}
        predictions = {key(r): r for r in read_rows(prediction_path)}
        inventory = read_rows(fold / "comparison_phase/draw_line_aware_actual_ladder_scoring_rows.csv")
        for row in inventory:
            k = (row.get("actual_original_hunt_code") or row["hunt_code"], row["residency"], row["points"])
            official = actuals[k]
            program = official.get("draw_pool")
            if program not in bear.MODELED_BEAR_SUBTYPES:
                raise ValueError(f"Unknown target Bear program: {program}")
            ladder = ladders.get((program, year, k[0], k[1]), {})
            point = int(k[2])
            prior = ladder.get(point - 1, {})
            same = ladder.get(point, {})
            quota = sum(v["total"] for v in ladder.values())
            source = by_code.get(k[0], {})
            prediction_key = (row.get("prediction_original_hunt_code") or k[0], k[1], k[2])
            prediction = predictions.get(prediction_key, {})
            if row["scoring_decision"] in GAPS:
                if not ladder:
                    reason = "NO_SOURCE_YEAR_PROGRAM_RESIDENCY_LADDER"
                elif quota == 0:
                    reason = "SOURCE_YEAR_ZERO_AWARDS_PROXY"
                elif prior.get("eligible", 0) - prior.get("total", 0) <= 0 and same.get("eligible", 0) == 0:
                    reason = "NO_SOURCE_POINT_OR_UNSUCCESSFUL_PREDECESSOR"
                else:
                    reason = "ENGINE_COVERAGE_GAP_WITH_SOURCE_COHORT"
                classified.append({**row, "source_classification": reason,
                                   "resolved_by_classification": reason != "ENGINE_COVERAGE_GAP_WITH_SOURCE_COHORT",
                                   "draw_program": program, "source_awards_proxy": quota,
                                   "source_point_applicants": same.get("eligible", ""),
                                   "source_predecessor_applicants": prior.get("eligible", ""),
                                   "source_predecessor_awards": prior.get("total", ""),
                                   "source_pdf": source.get("source_file", ""), "source_page": source.get("pdf_page", ""),
                                   "source_canonical_sha256": digest(canonical(year)),
                                   "actual_pdf": official["source_file"], "actual_page": official["pdf_page"],
                                   "old_algorithm_status": prediction.get("algorithm_status", ""),
                                   "old_reason_codes": prediction.get("reason_codes", "")})
            if row["scoring_decision"] == "score_probability" and float(row["absolute_error"]) > .25:
                p = float(row["predicted_probability"])
                numeric.append({**row, "draw_program": program,
                                "empty_forecast_cell_zero": p == 0 and float(prediction.get("applicants_at_level") or 0) == 0,
                                "forecast_applicants_at_level": prediction.get("applicants_at_level", ""),
                                "forecast_at_existing_ceiling": p >= .99,
                                "retained_in_accuracy": True})
    if len(classified) != 374:
        raise ValueError(f"Expected retained 374-gap inventory, got {len(classified)}")
    write_rows(out / "old_eight_fold_374_gap_classifications.csv", classified)
    write_rows(out / "old_eight_fold_large_error_diagnostics.csv", numeric)
    latest_ladders, _, _ = bear._build_truth_ladders(read_rows(canonical(2025)), {2025})
    intake.extend({"year": 2025, "program": program, "residency": residency,
                   "code_count": sum(k[0] == program and k[3] == residency for k in latest_ladders)}
                  for program in sorted(bear.MODELED_BEAR_SUBTYPES) for residency in ("Resident", "Nonresident"))
    expected_intake = dict(zip(range(2017, 2026), (90, 91, 97, 100, 100, 96, 96, 96, 97)))
    for year, expected_count in expected_intake.items():
        for residency in ("Resident", "Nonresident"):
            if sum(r["code_count"] for r in intake if r["year"] == year and r["residency"] == residency) != expected_count:
                raise ValueError(f"Canonical intake mismatch: {year}/{residency}")
    write_rows(out / "canonical_intake_by_year_program_residency.csv", intake)
    split_crosswalk = ROOT / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
    reviewed = []
    for row in read_rows(split_crosswalk):
        if row["current_2026_code"] not in bear.BEAR_SPLIT_HISTORY_START:
            continue
        reviewed.append({**row, "effective_split_year": 2026, "use_pre_split_history": False,
                         "use_forward_from": 2026, "applicant_stack_carry_forward_allowed": False,
                         "forecast_2026_status": "NO_TRANSITION_EVIDENCE", "forecast_2026_p_draw": "",
                         "parent_actuals_role": "REFERENCE_ONLY_PRESERVED_UNDER_ORIGINAL_CODES",
                         "source_crosswalk_sha256": digest(split_crosswalk)})
    write_rows(out / "bear_split_forward_only_crosswalk.csv", reviewed)
    database = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
    raw = database.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    authority = json.loads((ROOT / "governance/engine-authority.json").read_text())
    sha = lambda value: hashlib.sha256(value).hexdigest()
    expected = authority["truth_authority"]["current_hunt_and_permit_reference"]["verified_sha256"]
    preflight = {"current_raw_sha256": sha(raw), "lf_projection_sha256": sha(lf),
                 "recorded_verified_sha256": expected, "crlf_count": raw.count(b"\r\n"),
                 "lf_only_bytes_match_recorded": sha(lf) == expected,
                 "original_unchanged": True, "validator_weakened": False,
                 "release_status": "BLOCKED_RAW_BYTES_DIFFER_NO_PRODUCTION_WRITE_AUTHORIZED"}
    if sha(lf) == expected:
        candidate = out / "DATABASE.lf.release-candidate.csv"
        candidate.write_bytes(lf)
        if read_rows(candidate) != read_rows(database):
            raise ValueError("Line-ending normalization changed parsed fields")
        preflight.update(candidate=str(candidate.relative_to(ROOT)), candidate_sha256=digest(candidate),
                         parsed_rows_and_all_fields_identical=True)
    dump(out / "database_byte_preflight.json", preflight)
    after = protected_data()
    if after != before:
        raise ValueError("Protected data changed")
    dump(out / "protected_after.json", after)
    summary = {"status": "RECONCILED_OLD_DIAGNOSTIC_NOT_CERTIFICATION", "old_gaps": len(classified),
               "gap_classifications": dict(Counter(r["source_classification"] for r in classified)),
               "numeric_large_errors_retained": len(numeric),
               "large_errors_with_empty_forecast_cell_zero": sum(r["empty_forecast_cell_zero"] for r in numeric),
               "frozen_forecasts_unchanged": freezes, "database_preflight": preflight,
               "protected_files_unchanged": len(after), "release_decision": "DO_NOT_PROMOTE"}
    dump(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    reconcile(parser.parse_args().out_dir)
