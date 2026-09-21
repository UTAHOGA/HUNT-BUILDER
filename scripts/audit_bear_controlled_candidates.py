"""Isolated Bear name repair, split review and PDF-only fold orchestration.

Uses the existing Bear owner, mixed_row, identity gate and ADR-0006 scorer.
No production write, new probability model, threshold change or certification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_bear_pdf_truth_year import digest, dump, protected_paths
from scripts.build_bear_pdf_history_audit import read_rows, write_rows

HISTORY = ROOT / "audits/prediction_release_candidates/bear_pdf_history_2020_2025_20260920"
CROSSWALKS = ROOT / "audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909/crosswalks/pre_draw_source_only"
CANONICALS = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly"
GUIDE = ROOT / "audits/bear_availability_validation_20260919/source_evidence/2026_bear_cougar_furbearer.pdf"
SCORER = ROOT / "tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py"
SCORER_SHA256 = None
RECODE = {"BR7022": "BR7008", "BR7127": "BR7108", "BR7239": "BR7208", "BR7326": "BR7307"}
SPLITS = {"BR7021", "BR7126", "BR7238"}
RESTRICTED_PURSUIT_CODES_2026 = {
    "BR1008", "BR1009", "BR1010", "BR1011", "BR1012",
    "BR1013", "BR1015", "BR1016", "BR1017",
}
REPAIRS = {
    "BR7000": ("1 in 19.0", "Beaver - Any Legal Weapon"),
    "BR7001": ("1 in 9.0", "Book Cliffs, Bitter Creek/south - Any Legal Weapon"),
    "BR7005": ("N/A", "Central Mtns, Nebo - Any Legal Weapon"),
    "BR7007": ("N/A", "Fillmore, Pahvant - Any Legal Weapon"),
    "BR7010": ("N/A", "Panguitch Lake/zion - Any Legal Weapon"),
    "BR7015": ("1 in 9.0", "South Slope, Bonanza/diamond Mtn/vernal - Any Legal Weapon"),
}


def year_dir(year):
    return HISTORY / f"{year}_{'v2' if year == 2021 else 'v1'}"


def canonical(year):
    return CANONICALS / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def new_directory(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT / "audits") or path == ROOT / "audits" or path.exists():
        raise ValueError("Use a NEW isolated directory below audits; retained evidence cannot be overwritten")
    path.mkdir(parents=True)
    return path


def pdf_lanes(year):
    if year == 2026:
        return current_canonical_lanes_2026()
    if year < 2020:
        return canonical_lanes(year)
    directory = year_dir(year)
    path = directory / f"bear_{year}_pdf_point_lanes.csv"
    freeze = json.loads((directory / "pdf_extract_freeze.json").read_text())
    if digest(path) != freeze[path.name]:
        raise ValueError(f"Frozen PDF extraction changed: {year}")
    rows = read_rows(path)
    for row in rows:
        row.update(metric_scope=row["residency"].lower(),
                   bear_source_identity_source="RETAINED_OFFICIAL_BLACK_BEAR_PDF",
                   bear_source_identity_file=row["source_file"], qa_status="OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED")
        if int(row["actual_draw_year"]) != year:
            raise ValueError("Mixed-year source extract")
    return rows


def current_canonical_lanes_2026():
    """Project the unique official UtahDraws 2026 Bear result rows for scoring.

    This function is used only after the 2025-source forecast is frozen.  It
    does not supply forecast identity, applicant demand or quota.  Program
    identity comes from the reviewed 2026 restricted-pursuit code set; every
    other BR public point ladder is limited-entry hunting. Sportsman BR1000 is
    intentionally outside these certification populations.
    """

    rows = []
    seen = set()
    for source in read_rows(canonical(2026)):
        code = source.get("hunt_code", "").upper()
        if not code.startswith("BR") or code == "BR1000":
            continue
        if source.get("record_type") != "point_level_draw_result":
            continue
        if source.get("qa_status") != "CONFIRMED_CANONICAL_SCORABLE":
            continue
        residency = source.get("residency", "")
        if residency not in {"Resident", "Nonresident"}:
            continue
        key = (code, residency, source.get("points", ""))
        if key in seen:
            raise ValueError(f"Duplicate 2026 Bear canonical scoring key: {key}")
        seen.add(key)
        program = (
            "RESTRICTED_BEAR_PURSUIT"
            if code in RESTRICTED_PURSUIT_CODES_2026
            else "LIMITED_ENTRY_BEAR_HUNT"
        )
        eligible = int(source.get("eligible_applicants") or 0)
        total = int(source.get("total_permits") or 0)
        rows.append({
            **source,
            "actual_draw_year": "2026",
            "draw_pool": program,
            "bear_draw_subtype": program,
            "bear_source_classification": (
                "BEAR_PURSUIT_BONUS_DRAW"
                if program == "RESTRICTED_BEAR_PURSUIT"
                else "TRUE_BEAR_BONUS_DRAW"
            ),
            "observed_success_fraction": f"{total / eligible:.10f}" if eligible else "",
            "metric_scope": residency.lower(),
            "bear_source_identity_source": "CANONICAL_OFFICIAL_UTAHDRAWS_2026",
            "bear_source_identity_file": source.get("source_file", ""),
            "canonical_source_file": canonical(2026).relative_to(ROOT).as_posix(),
        })
    if len(rows) != 2814:
        raise ValueError(f"Unexpected 2026 Bear canonical point-row count: {len(rows)}")
    return rows


def canonical_lanes(year):
    """Project reviewed early canonicals without inventing or merging lanes.

    The 2017-2019 PDFs use the retained canonical parser, not the later PDF
    table layout. Preserve exact source/page identity and reconcile via owner.
    """
    from engine.utah_draw_predictive import bear
    source = read_rows(canonical(year))
    ladders, _, _ = bear._build_truth_ladders(source, {year})
    rows, seen = [], set()
    for row in source:
        program = bear._canonical_bear_program(row)
        if program not in bear.MODELED_BEAR_SUBTYPES or row.get("record_type") != "point_level_draw_result":
            continue
        if int(row["actual_draw_year"]) != year or not row.get("source_file") or not row.get("pdf_page"):
            raise ValueError("Early canonical source/year/page boundary failed")
        for lane in bear._canonical_official_bear_residency_lanes(row):
            key = (program, year, row["hunt_code"], lane["residency"], int(row["points"]))
            if key in seen:
                continue  # Owner above already rejects conflicting duplicates.
            values = ladders[key[:4]][key[4]]
            seen.add(key)
            rows.append({
                "actual_draw_year": str(year), "hunt_code": row["hunt_code"], "hunt_name": row["hunt_name"],
                "species": "Black Bear", "draw_pool": program, "residency": lane["residency"],
                "points": row["points"], "record_type": "point_level_draw_result",
                "eligible_applicants": str(values["eligible"]), "bonus_permits": str(values["bonus"]),
                "regular_permits": str(values["regular"]), "total_permits": str(values["total"]),
                "observed_success_fraction": f"{values['total'] / values['eligible']:.10f}" if values["eligible"] else "",
                "metric_scope": lane["residency"].lower(), "source_file": row["source_file"],
                "pdf_page": row["pdf_page"], "source_path": row["source_path"],
                "bear_source_classification": "BEAR_PURSUIT_BONUS_DRAW" if program == bear.RESTRICTED_BEAR_PURSUIT else "TRUE_BEAR_BONUS_DRAW",
                "bear_source_identity_source": "CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
                "bear_source_identity_file": row["source_file"], "qa_status": "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED",
                "canonical_source_file": canonical(year).relative_to(ROOT).as_posix(),
            })
    if len(rows) != sum(len(points) for points in ladders.values()):
        raise ValueError("Early canonical projection lost admitted point rows")
    return rows


def protected_data():
    return {path: value for path, value in protected_paths().items() if not path.startswith("engine/")}


def prepare_name_repair(out):
    source = canonical(2023)
    payload = source.read_bytes()
    # Preserve bytes of every unaffected physical record. The canonical has no
    # embedded record newlines; reject that shape rather than reserializing it.
    lines = payload.splitlines(keepends=True)
    fields = next(csv.reader([lines[0].decode("utf-8-sig")]))
    whole_rows = read_rows(source)
    if len(lines) != len(whole_rows) + 1:
        raise ValueError("Canonical contains multiline records; explicit repair required")
    expected = json.loads((year_dir(2023) / "canonical_comparison.json").read_text())["mismatches"]
    if len(expected) != 138 or any(r["field"] != "hunt_name" for r in expected):
        raise ValueError("Mismatch inventory differs from the reviewed six-name repair")
    names = {r["key"][0]: (r["canonical"], r["pdf"]) for r in expected}
    if names != REPAIRS:
        raise ValueError(f"Reviewed PDF names differ: {names}")
    changes, rebuilt = [], [lines[0]]
    for number, (row, raw) in enumerate(zip(whole_rows, lines[1:]), 2):
        values = next(csv.reader([raw.decode("utf-8")]))
        if len(values) != len(fields) or dict(zip(fields, values)) != row:
            raise ValueError("CSV record/column ambiguity")
        code = row["hunt_code"]
        if code in names:
            old, new = names[code]
            if row["hunt_name"] != old or row["actual_draw_year"] != "2023":
                raise ValueError("Unexpected name/year in a repair target")
            values[fields.index("hunt_name")] = new
            newline = "\r\n" if raw.endswith(b"\r\n") else "\n"
            buffer = io.StringIO(newline="")
            csv.writer(buffer, lineterminator=newline).writerow(values)
            rebuilt.append(buffer.getvalue().encode("utf-8"))
            changes.append({"csv_line": number, "hunt_code": code, "points": row.get("points", ""),
                            "record_type": row.get("record_type", ""), "old_hunt_name": old, "new_hunt_name": new,
                            "source_file": row["source_file"], "pdf_page": row.get("pdf_page", "")})
        else:
            rebuilt.append(raw)
    candidate = out / source.name
    candidate.write_bytes(b"".join(rebuilt))
    repaired = read_rows(candidate)
    if len(repaired) != len(whole_rows) or len(changes) != 138:
        raise ValueError("Unexpected repair count")
    for old, new in zip(whole_rows, repaired):
        if {k: v for k, v in old.items() if k != "hunt_name"} != {k: v for k, v in new.items() if k != "hunt_name"}:
            raise ValueError("A protected/non-name field changed")
    projection = lambda rows: hashlib.sha256(json.dumps(
        [[r[field] for field in fields if field != "hunt_name"] for r in rows], ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    write_rows(out / "name_repairs.csv", changes)
    report = {"status": "PREPARED_NOT_PROMOTED", "source": str(source.relative_to(ROOT)),
              "source_sha256": digest(source), "candidate_sha256": digest(candidate), "rows": len(repaired),
              "changed_rows": len(changes), "changed_fields": ["hunt_name"],
              "changes_by_code": dict(Counter(r["hunt_code"] for r in changes)),
              "all_non_name_fields_projection_before": projection(whole_rows),
              "all_non_name_fields_projection_after": projection(repaired),
              "unaffected_records_byte_identical": all(a == b for i, (a, b) in enumerate(zip(lines, rebuilt), 1)
                                                       if i not in {r["csv_line"] for r in changes}),
              "production_canonical_written": False}
    dump(out / "name_repair_verification.json", report)
    return report


def split_review(out):
    import pdfplumber
    with pdfplumber.open(GUIDE) as pdf:
        split_text = pdf.pages[3].extract_text()
        pursuit_text = pdf.pages[9].extract_text()
    if "separating it from the La Sal Mtns" not in split_text or "both the La Sal Mtns and Dolores Triangle" not in pursuit_text:
        raise ValueError("Official split/pursuit evidence changed")
    crosswalk_path = ROOT / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
    crosswalk = {r["current_2026_code"]: r for r in read_rows(crosswalk_path) if r["current_2026_code"] in set(RECODE) | SPLITS}
    history = [r for year in range(2020, 2026) for r in pdf_lanes(year)]
    inventory_path = ROOT / "audits/bear_availability_validation_20260919/inventory_v4/inventory.json"
    inventory = json.loads(inventory_path.read_text())
    guide_rows = {r["hunt_code"]: r for r in inventory["guidebook_rows"]["2026"]}
    review = []
    for code in sorted(set(RECODE) | SPLITS):
        parent = RECODE.get(code, "")
        if crosswalk[code]["historical_2025_code"] != parent:
            raise ValueError("Crosswalk predecessor changed")
        for residency in ("Resident", "Nonresident"):
            source = [r for r in history if r["hunt_code"] == parent and r["residency"] == residency]
            years = sorted({int(r["actual_draw_year"]) for r in source})
            if parent and years != list(range(2020, 2026)):
                raise ValueError("Missing predecessor history")
            latest = [r for r in source if r["actual_draw_year"] == "2025"]
            review.append({"hunt_code": code, "residency": residency, "hunt_name": guide_rows[code]["hunt_name"],
                           "season": guide_rows[code]["program"], "historical_code": parent,
                           "historical_years": "|".join(map(str, years)),
                           "source_2025_applicants": sum(int(r["eligible_applicants"]) for r in latest) if parent else "",
                           "source_2025_awards": sum(int(r["total_permits"]) for r in latest) if parent else "",
                           "source_2025_unsuccessful": sum(int(r["eligible_applicants"])-int(r["total_permits"]) for r in latest) if parent else "",
                           "identity_disposition": "RECODED_PARENT_HISTORY_BOUNDARY_CHANGED" if parent else "NEW_SPLIT_CHILD_NO_DIRECT_HISTORY",
                           "full_stack_transfer_allowed": False, "duplicated_parent_stack_allowed": False,
                           "usable_prediction_history_start": 2026,
                           "pre_split_history_role": "REFERENCE_ONLY",
                           "eligible_pre_split_prediction_rows": 0,
                           "applicant_redistribution_evidence": "NOT_PUBLISHED_IN_RETAINED_AGGREGATE_REPORTS",
                           "p_draw": "", "certified_p_draw": "", "guidebook_page": guide_rows[code]["pdf_page"],
                           "boundary_change_page": 4, "source_pdf_sha256": digest(GUIDE)})
    write_rows(out / "la_sal_dolores_split_review.csv", review)
    dump(out / "la_sal_split_evidence.json", {"guidebook_sha256": digest(GUIDE), "crosswalk_sha256": digest(crosswalk_path),
        "current_rows": len(review), "recoded_hunt_codes": RECODE, "new_split_codes": sorted(SPLITS),
        "split_page": 4, "restricted_pursuit_page": 10, "restricted_la_sal_pursuit_remains_both_areas": True,
        "forecast_action": "POST_SPLIT_2026_FORWARD_ONLY_NO_PARENT_INHERITANCE", "production_changes": False})


def source_read_guard(allowed, out):
    """Enforce a physical source-only boundary, not a post-read year filter."""
    reads = set()
    allowed = {Path(p).resolve() for p in allowed}
    out = out.resolve()

    def hook(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            if path.is_relative_to(ROOT) and not path.is_relative_to(out) and path.suffix != ".pyc":
                raise RuntimeError(f"Forecast attempted noncandidate write: {path}")
        elif path.is_relative_to(ROOT) and path.suffix.lower() in {".csv", ".json", ".pdf", ".jsonl", ".parquet"}:
            if path not in allowed and not path.is_relative_to(out):
                raise RuntimeError(f"Forecast attempted unapproved/future data read: {path}")
            reads.add(str(path.relative_to(ROOT)))
    sys.addaudithook(hook)
    return reads, allowed


def forecast_fold(out, source_year, mode="deterministic", iterations=1, demand_mode="cohort_rollforward", returning_mode="off", history_start=2020):
    sys.dont_write_bytecode = True
    out = new_directory(out)
    if not 2017 <= history_start <= source_year <= 2025:
        raise ValueError("Reviewed source window is 2017-2025")
    years = list(range(history_start, source_year + 1))
    crosswalk_path = CROSSWALKS / f"pre_draw_hunt_identity_crosswalk_{source_year}_to_{source_year+1}.csv"
    dated_crosswalks = [CROSSWALKS/f"pre_draw_hunt_identity_crosswalk_{y}_to_{y+1}.csv" for y in years]
    allowed = [p for y in years for p in (
        (canonical(y),) if y < 2020 else
        (year_dir(y) / f"bear_{y}_pdf_point_lanes.csv", year_dir(y) / "pdf_extract_freeze.json"))]
    allowed.extend(dated_crosswalks)
    reads, allowed_set = source_read_guard(allowed, out)
    # Install before model imports as well as before explicit source loads.
    # Import-time data caches cannot silently bypass the historical boundary.
    from engine.utah_draw_predictive.bear import build_bear_bonus_predictions
    from engine.utah_draw_predictive.run_all_families import _historical_source_year_runtime_db_rows
    from engine.utah_predictive_mixed.materialize import mixed_row
    from engine.utah_predictive_mixed.models import BlendWeights
    from scripts.project_legacy_canonical_for_blind_scoring import (
        inspect_identity_crosswalk_contract, load_reviewed_identity_crosswalk, apply_reviewed_identity_crosswalk)
    cutoffs = {}
    for dated_path in dated_crosswalks:
        for row in read_rows(dated_path):
            evidence = Path(row["target_application_evidence_file"])
            allowed_set.add((evidence if evidence.is_absolute() else ROOT / evidence).resolve())
            if row["applicant_stack_carry_forward_allowed"] == "FALSE":
                code = row["to_hunt_code"] or row["from_hunt_code"]
                if code.startswith("BR") and int(row["to_draw_year"]) <= source_year:
                    cutoffs[code] = max(cutoffs.get(code, 0), int(row["to_draw_year"]))
        if not inspect_identity_crosswalk_contract(dated_path)["certification_eligible"]:
            raise ValueError(f"Invalid source-dated crosswalk: {dated_path}")
    # allowed_set is the same mutable set used by the guard.
    contract = inspect_identity_crosswalk_contract(crosswalk_path)
    if not contract["certification_eligible"]:
        raise ValueError(contract)
    decisions = load_reviewed_identity_crosswalk(crosswalk_path)
    history = [row for y in years for row in pdf_lanes(y)]
    source = [r for r in history if int(r["actual_draw_year"]) == source_year]
    targets = _historical_source_year_runtime_db_rows(source, source_year)
    representatives = {r["hunt_code"]: r for r in source}
    for target in targets:
        target["bear_history_effective_start_year"] = cutoffs.get(target["hunt_code"], 0)
        representative = representatives[target["hunt_code"]]
        for field in ("bear_source_classification", "bear_source_identity_source", "bear_source_identity_file", "qa_status", "source_file", "actual_draw_year"):
            target[field] = representative[field]
    targets, identity_report = apply_reviewed_identity_crosswalk(targets, decisions, unlisted_source_code_behavior="PASS_THROUGH")
    if any(r["identity_crosswalk_from_hunt_code"] != r["hunt_code"] for r in targets):
        raise ValueError("A new historical recode requires explicit source-ladder mapping review")
    predictions, report = build_bear_bonus_predictions(history, targets, source_year+1, years,
                                                       central_estimate_mode=mode, iterations=iterations, demand_mode=demand_mode,
                                                       returning_cohort_mode=returning_mode)
    target_by_code = {r["hunt_code"]: r for r in targets}
    prior = {(r["hunt_code"], r["residency"], r["points"]): r for r in source}
    final = []
    for row in predictions:
        row.update(family="bonus_bear", source_year=str(source_year), target_year=str(source_year+1),
                   model_target_year=str(source_year+2), draw_design="BEAR_DRAW",
                   quota_2026_total=str(row.get("public_permits_2026", "")),
                   quota_source_year=str(source_year), quota_source_file=target_by_code[row["hunt_code"]]["source_file"])
        if row["quota_source_type"] != "SOURCE_YEAR_CANONICAL_AWARDS_PROXY":
            raise ValueError("Bear owner did not retain source-year quota authority")
        # Historical calls use the same pure final entrypoint, with only the
        # exact source-year prior row; never present-day harvest or DATABASE.
        payload = {k: str(v) if v is not None else "" for k, v in row.items()}
        final.append(mixed_row(payload, prior.get((row["hunt_code"], row["residency"], str(row["points"]))),
                               None, BlendWeights(), forecast_year=source_year+1))
    write_rows(out / "family_predictions.csv", predictions)
    write_rows(out / "final_predictions.csv", final)
    write_rows(out / "source_quota_targets.csv", targets)
    dump(out / "bear_report.json", report)
    dump(out / "identity_gate.json", {**contract, **identity_report, "crosswalk_sha256": digest(crosswalk_path)})
    dump(out / "forecast_freeze.json", {
        "source_years": years, "source_year": source_year, "target_year": source_year+1,
        "history_start": history_start,
        "historical_database_csv_read_count": 0, "target_result_read_count": 0,
        "source_reads": sorted(reads), "source_hashes": {p: digest(ROOT/p) for p in sorted(reads)},
        "family_sha256": digest(out/"family_predictions.csv"), "final_sha256": digest(out/"final_predictions.csv"),
        "bear_implementation_sha256": digest(ROOT/"engine/utah_draw_predictive/bear.py"),
        "mixed_implementation_sha256": digest(ROOT/"engine/utah_predictive_mixed/materialize.py"),
        "quota_implementation_sha256": digest(ROOT/"engine/utah_predictive_mixed/quota.py"),
        "classifier_implementation_sha256": digest(ROOT/"engine/utah_draw_predictive/classifier.py"),
        "historical_adapter_implementation_sha256": digest(ROOT/"engine/utah_draw_predictive/run_all_families.py"),
        "orchestrator_sha256": digest(Path(__file__).resolve()),
        "scorer_sha256": digest(SCORER),
        "scorer_source_file": SCORER.relative_to(ROOT).as_posix(),
        "read_guard_installed_before_model_imports": True,
        "final_entrypoint": "engine.utah_predictive_mixed.materialize.mixed_row",
        "harvest_context": "NONE_HISTORICAL_FEATURE_SNAPSHOT_NOT_PROVEN",
        "central_estimate": mode, "iterations": iterations, "demand_mode": demand_mode,
        "returning_cohort_mode": returning_mode,
        "rows": len(predictions)})


def load_selected_scorer(path, expected_hash=None):
    """Execute retained exact scorer bytes with the original repo resource base.

    A concurrent working-file edit must not change an already frozen candidate.
    No source text is patched and all thresholds remain owned by the scorer.
    """
    if expected_hash and digest(path) != expected_hash:
        raise ValueError("Frozen scorer hash changed")
    logical_path = ROOT / "tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py"
    name = "_bear_exact_frozen_draw_line_scorer"
    spec = importlib.util.spec_from_file_location(name, logical_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    module.__frozen_source_file__ = str(path)
    return module


def score_fold(fold, source_year):
    scorer = load_selected_scorer(SCORER, SCORER_SHA256)
    from scripts.build_blind_acceptance_review import load_draw_line_fold, metrics, decision, MISSING_SCOREABLE_ACTUAL_DECISIONS
    prediction_dir = fold / "prediction_phase"
    freeze = json.loads((prediction_dir / "forecast_freeze.json").read_text())
    for stage in ("family", "final"):
        if digest(prediction_dir / f"{stage}_predictions.csv") != freeze[f"{stage}_sha256"]:
            raise ValueError("Frozen forecast changed before opening actuals")
    actual = pdf_lanes(source_year+1)
    for row in actual:
        row.update(p_draw=row["observed_success_fraction"], draw_design="BEAR_DRAW", family="bonus_bear",
                   bear_draw_subtype=row["draw_pool"], model_target_year=str(source_year+2))
    actual_path = fold / "actual_projection.csv"
    write_rows(actual_path, actual)
    source = pdf_lanes(source_year)
    history = [r for y in freeze["source_years"] for r in pdf_lanes(y)]
    source_lanes = defaultdict(list)
    for row in source:
        source_lanes[(row["hunt_code"], row["residency"])].append(row)
    target_lookup = {(r["hunt_code"], r["residency"], r["points"]): r for r in actual}
    crosswalk = read_rows(CROSSWALKS / f"pre_draw_hunt_identity_crosswalk_{source_year}_to_{source_year+1}.csv")
    blocked = {r["to_hunt_code"] or r["from_hunt_code"]: r for r in crosswalk
               if r.get("applicant_stack_carry_forward_allowed") == "FALSE"}
    summaries = []
    for stage in ("family", "final"):
        comparison = fold / f"{stage}_comparison"
        scorer.run(scorer.parse_args(["--predictions", str(prediction_dir/f"{stage}_predictions.csv"), "--truth", str(actual_path),
                        "--output-dir", str(comparison), "--source-year", str(source_year),
                        "--target-year", str(source_year+1), "--exact-codes-only"]))
        gaps = []
        inventory = read_rows(comparison/"draw_line_aware_actual_ladder_scoring_rows.csv")
        for row in inventory:
            # Actual-only inventory needs explicit source program identity.
            official = target_lookup.get((row["hunt_code"], row["residency"], row["points"]), {})
            row["bear_draw_subtype"] = official.get("draw_pool", row.get("bear_draw_subtype", ""))
            if row["scoring_decision"] not in MISSING_SCOREABLE_ACTUAL_DECISIONS:
                continue
            previous = source_lanes.get((row["hunt_code"], row["residency"]), [])
            reason = ""
            if row["hunt_code"] in blocked:
                reason = "PRE_DRAW_" + blocked[row["hunt_code"]]["transition_type"]
            elif not previous:
                reason = "NEW_OFFICIAL_HUNT_RESIDENCY_NO_SOURCE_LADDER"
            elif sum(int(r["total_permits"]) for r in previous) == 0:
                reason = "SOURCE_YEAR_ZERO_AWARDS_NO_POSITIVE_QUOTA_PROXY"
            elif not any(int(r["eligible_applicants"]) > 0 for r in history
                         if r["hunt_code"] == row["hunt_code"] and r["residency"] == row["residency"]
                         and int(r["points"]) in {int(row["points"]), int(row["points"])-1}):
                reason = "NO_TRANSITION_EVIDENCE"
            # Do not explain away a missed positive cohort or arbitrary blank.
            gaps.append({**row, "actual_gap_classification": reason,
                         "certification_gap_status": "SOURCE_CLASSIFIED" if reason else "UNRESOLVED",
                         "source_file": official.get("source_file", ""), "pdf_page": official.get("pdf_page", ""),
                         "source_applicants": sum(int(r["eligible_applicants"]) for r in previous),
                         "source_awards": sum(int(r["total_permits"]) for r in previous)})
        write_rows(comparison/"draw_line_aware_actual_gap_classifications.csv", gaps)
        scored = load_draw_line_fold(fold.name, comparison/"draw_line_aware_prediction_vs_actual_rowlevel.csv")
        for design in ("BEAR_LIMITED_ENTRY_HUNT_BONUS", "BEAR_RESTRICTED_PURSUIT_BONUS"):
            selected = [r for r in scored if r["draw_design"] == design]
            result = metrics(selected)
            summaries.append({"stage": stage, "design": design, **result, "fold": fold.name,
                              "unresolved_gaps": sum(r["certification_gap_status"] == "UNRESOLVED" for r in gaps)})
    dump(fold/"comparison_summary.json", summaries)
    print(json.dumps(summaries), flush=True)


def run_folds(out, source_start=2020, source_end=2024, mode="deterministic", iterations=1, demand_mode="cohort_rollforward", returning_mode="off", history_start=2020):
    from scripts.build_blind_acceptance_review import load_draw_line_fold, load_actual_gap_fold, build_design_rows, THRESHOLDS
    out = new_directory(out)
    before = protected_data()
    dump(out/"protected_before.json", before)
    for year in range(source_start, source_end+1):
        fold = out / f"{year}_to_{year+1}"
        for phase, path in (("forecast", fold/"prediction_phase"), ("score", fold)):
            subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--phase", phase,
                            "--source-year", str(year), "--out-dir", str(path), "--central-estimate", mode,
                            "--iterations", str(iterations), "--demand-mode", demand_mode,
                            "--returning-cohort-mode", returning_mode,
                            "--history-start", str(history_start),
                            *(["--scorer-snapshot", str(SCORER), "--scorer-sha256", SCORER_SHA256] if SCORER_SHA256 else [])], cwd=ROOT, check=True)
    review = {}
    for stage in ("family", "final"):
        scored, gaps = [], []
        for fold in sorted(out.glob("*_to_*")):
            comparison = fold / f"{stage}_comparison"
            scored.extend(load_draw_line_fold(fold.name, comparison/"draw_line_aware_prediction_vs_actual_rowlevel.csv"))
            actual_gaps, _ = load_actual_gap_fold(fold.name, comparison/"draw_line_aware_actual_ladder_scoring_rows.csv")
            from scripts.build_blind_acceptance_review import certification_draw_design
            classified = read_rows(comparison/"draw_line_aware_actual_gap_classifications.csv")
            designs = {r["hunt_code"]: certification_draw_design(r) for r in classified}
            for gap in actual_gaps:
                gap["draw_design"] = designs[gap["hunt_code"]]
            gaps.extend(actual_gaps)
        review[stage] = build_design_rows(scored, gaps)
        write_rows(out / f"{stage}_acceptance_by_design.csv", review[stage])
        write_rows(out / f"{stage}_scored_rows.csv", scored)
    after = protected_data()
    dump(out/"protected_after.json", {"files": after, "changed": [p for p in before if before[p] != after[p]]})
    if before != after:
        raise RuntimeError("Protected files changed")
    dump(out/"acceptance_summary.json", {"thresholds": THRESHOLDS, "results": review, "production_written": False})
    print(json.dumps(review, indent=2))


def prepare(out):
    out = new_directory(out)
    before = protected_data()
    dump(out / "protected_before.json", before)
    try:
        repair = prepare_name_repair(out)
        split_review(out)
        print(json.dumps({"repair": repair, "split_rows": 14}, indent=2))
    finally:
        after = protected_data()
        dump(out / "protected_after.json", {"files": after, "changed": [p for p in before if before[p] != after[p]]})
        if before != after:
            raise RuntimeError("Protected files changed")


def main():
    global SCORER, SCORER_SHA256
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=["prepare", "forecast", "score", "folds"], default="prepare")
    parser.add_argument("--source-year", type=int)
    parser.add_argument("--source-start", type=int, default=2020)
    parser.add_argument("--source-end", type=int, default=2024)
    parser.add_argument("--history-start", type=int, default=2020)
    parser.add_argument("--scorer-snapshot", type=Path)
    parser.add_argument("--scorer-sha256")
    parser.add_argument("--central-estimate", choices=["deterministic", "simulation_mean"], default="deterministic")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--demand-mode", choices=["cohort_rollforward", "cumulative_stack", "cumulative_transition_ensemble", "adaptive_cumulative_stack"], default="cohort_rollforward")
    parser.add_argument("--returning-cohort-mode", choices=["off", "lane_cohort_hierarchical"], default="off")
    args = parser.parse_args()
    if args.scorer_snapshot:
        SCORER = args.scorer_snapshot.resolve()
        SCORER_SHA256 = args.scorer_sha256
        if not SCORER.is_relative_to(ROOT / "audits") or not SCORER_SHA256 or digest(SCORER) != SCORER_SHA256:
            raise ValueError("Scorer snapshot must be an exact hash-pinned retained audit file")
    if args.phase == "prepare":
        prepare(args.out_dir)
    elif args.phase == "forecast":
        forecast_fold(args.out_dir, args.source_year, args.central_estimate, args.iterations, args.demand_mode, args.returning_cohort_mode, args.history_start)
    elif args.phase == "score":
        score_fold(args.out_dir, args.source_year)
    else:
        run_folds(args.out_dir, args.source_start, args.source_end, args.central_estimate, args.iterations, args.demand_mode, args.returning_cohort_mode, args.history_start)


if __name__ == "__main__":
    main()
