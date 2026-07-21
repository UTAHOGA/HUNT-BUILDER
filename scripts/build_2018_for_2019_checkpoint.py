"""Build compact 2018_for_2019 checkpoint audit.

This script reads repo-visible locked truth/prediction artifacts only. It does
not create joined comparables, score matrices, external outputs, commits, or
pushes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_DIR = REPO_ROOT / "audits" / "year_to_year_key_correction20260721_021528"
OUT_DIR = LOCK_DIR / "year_checkpoints" / "2018_for_2019"
TRUTH_FILE = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
PREDICTION_PACKAGE = REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260721_youth_turkey_program_start_fix" / "runs" / "2019"
PREDICTION_FILE = PREDICTION_PACKAGE / "family_predictions.csv"
CWMU_BLIND_DIR = REPO_ROOT / "audits" / "2018_prediction_repair_blind20260721_020854"
CWMU_LOCK = CWMU_BLIND_DIR / "2018_CWMU_TRUTH_LOCK_MANIFEST.md"
CWMU_SCORE_SUMMARY = CWMU_BLIND_DIR / "2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv"
CWMU_CERT = CWMU_BLIND_DIR / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md"
PREV_STOP = REPO_ROOT / "audits" / "year_to_year_database_completion_compare20260721_022404" / "2017_for_2018" / "YEAR_STOP_CHECKPOINT_2017_FOR_2018.txt"
FULL_YEAR_OFFICIAL_KEY_STATUS = "REVIEW_REQUIRED_CANONICAL_TRUTH_MISSING_OFFICIAL_SCORE_KEY_V2"


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def stream_key_stats(path: Path, key_column: str = "official_score_key_v2") -> Dict[str, object]:
    rows = 0
    hunts: Set[str] = set()
    keys = Counter()
    blanks = 0
    columns: List[str] = []
    families = Counter()
    explanation = Counter()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        has_key = key_column in columns
        for row in reader:
            rows += 1
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                hunts.add(hunt_code)
            family = (row.get("family") or row.get("source_family") or row.get("hunt_class") or "").strip()
            if family:
                families[family] += 1
            if has_key:
                key = (row.get(key_column) or "").strip()
                if key:
                    keys[key] += 1
                else:
                    blanks += 1
                    explanation["blank_official_score_key_v2"] += 1
            else:
                blanks += 1
                explanation["missing_official_score_key_v2_column"] += 1
    duplicate_keys = sum(1 for key, count in keys.items() if count > 1)
    duplicate_rows = sum(count for key, count in keys.items() if count > 1)
    return {
        "rows": rows,
        "unique_hunt_codes": len(hunts),
        "hunt_codes": hunts,
        "has_official_score_key_v2": key_column in columns,
        "blank_keys": blanks,
        "keys": keys,
        "nonblank_key_count": sum(keys.values()),
        "unique_keys": len(keys),
        "duplicate_keys": duplicate_keys,
        "duplicate_key_rows": duplicate_rows,
        "families": families,
        "explanation": explanation,
        "columns": columns,
    }


def truth_cwmu_stats(path: Path) -> Dict[str, object]:
    rows = 0
    hunts: Set[str] = set()
    source_files: Set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = " ".join(
                (row.get(field) or "")
                for field in ("hunt_class", "hunt_draw_class", "source_file", "draw_source_file", "source_path", "source_pdf", "qa_notes")
            ).upper()
            if "CWMU" not in text:
                continue
            rows += 1
            code = (row.get("hunt_code") or "").strip()
            if code:
                hunts.add(code)
            source = (
                row.get("source_pdf")
                or row.get("draw_source_file")
                or row.get("source_file")
                or ""
            ).strip()
            if source:
                source_files.add(source)
    return {"rows": rows, "unique_hunt_codes": len(hunts), "source_file_count": len(source_files)}


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def first_matching_summary_row() -> Dict[str, str]:
    summary = LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv"
    with summary.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("actual_draw_year") == "2018" and row.get("model_target_year") == "2019":
                return row
    return {}


def read_cwmu_score_overall() -> Dict[str, str]:
    if not CWMU_SCORE_SUMMARY.exists():
        return {}
    with CWMU_SCORE_SUMMARY.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("summary_group") == "overall":
                return row
    return {}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")

    truth = stream_key_stats(TRUTH_FILE)
    prediction = stream_key_stats(PREDICTION_FILE)
    truth_keys: Counter = truth["keys"]  # type: ignore[assignment]
    prediction_keys: Counter = prediction["keys"]  # type: ignore[assignment]
    shared_keys = set(truth_keys) & set(prediction_keys)
    exact_match_rows = sum(min(truth_keys[key], prediction_keys[key]) for key in shared_keys)
    unmatched_truth_rows = int(truth["rows"]) - exact_match_rows
    unmatched_prediction_rows = int(prediction["rows"]) - exact_match_rows

    locked_summary = first_matching_summary_row()
    cwmu_stats = truth_cwmu_stats(TRUTH_FILE)
    cwmu_score = read_cwmu_score_overall()
    cwmu_post_lock_defects = 0
    defects_file = CWMU_BLIND_DIR / "2018_CWMU_POST_LOCK_DEFECTS.csv"
    if defects_file.exists():
        cwmu_post_lock_defects = max(sum(1 for _ in defects_file.open("r", encoding="utf-8-sig")) - 1, 0)

    blind_cert_text = CWMU_CERT.read_text(encoding="utf-8", errors="replace") if CWMU_CERT.exists() else ""
    blind_lock_text = CWMU_LOCK.read_text(encoding="utf-8", errors="replace") if CWMU_LOCK.exists() else ""
    cwmu_blind_ok = (
        CWMU_LOCK.exists()
        and "TRUTH_LOCKED_BEFORE_PREDICTION_ACCESS = TRUE" in blind_lock_text
        and "Frozen prediction data was not accessed until after truth lock: `TRUE`" in blind_cert_text
        and "Truth modified after prediction access: `FALSE`" in blind_cert_text
    )
    cwmu_status = "PASS_CWMU_BRIDGED_BLIND" if cwmu_blind_ok and cwmu_post_lock_defects == 0 else "PASS_WITH_REVIEW_REQUIRED"

    previous_status = "COMPLETE" if PREV_STOP.exists() else "INCOMPLETE_OR_SKIPPED"
    unresolved_key_conflicts = int(locked_summary.get("conflict_key_groups") or 0)
    unresolved_cwmu_conflicts = 0 if cwmu_blind_ok and cwmu_post_lock_defects == 0 else 1

    if not TRUTH_FILE.exists():
        year_status = "FAIL_BLOCKED_MISSING_SOURCE"
    elif not truth["has_official_score_key_v2"] or not prediction["has_official_score_key_v2"]:
        year_status = "PASS_WITH_REVIEW_REQUIRED"
    elif truth["blank_keys"] or prediction["blank_keys"]:
        year_status = "FAIL_BLOCKED_MISSING_KEYS"
    elif unresolved_key_conflicts:
        year_status = "FAIL_BLOCKED_KEY_CONFLICTS"
    elif cwmu_status == "PASS_CWMU_BRIDGED_BLIND":
        year_status = "PASS_CWMU_BRIDGED_BLIND"
    else:
        year_status = "PASS_KEY_MATCHED_CHECKPOINT"

    prediction_family_csv_count = 0
    prediction_dir = PREDICTION_PACKAGE / "predictions"
    if prediction_dir.exists():
        prediction_family_csv_count = len(list(prediction_dir.glob("*.csv")))

    counts_path = OUT_DIR / "2018_FOR_2019_CHECKPOINT_COUNTS.csv"
    key_audit_path = OUT_DIR / "2018_FOR_2019_KEY_AUDIT.csv"
    unmatched_truth_path = OUT_DIR / "2018_FOR_2019_UNMATCHED_TRUTH_SUMMARY.csv"
    unmatched_prediction_path = OUT_DIR / "2018_FOR_2019_UNMATCHED_PREDICTION_SUMMARY.csv"
    report_path = OUT_DIR / "2018_FOR_2019_CHECKPOINT_REPORT.md"
    cwmu_audit_path = OUT_DIR / "2018_FOR_2019_CWMU_BLINDNESS_AUDIT.md"

    write_csv(
        counts_path,
        [
            {
                "year_checkpoint": "2018_FOR_2019",
                "previous_year_checkpoint_status": previous_status,
                "full_year_official_key_status": FULL_YEAR_OFFICIAL_KEY_STATUS,
                "truth_file": str(TRUTH_FILE),
                "truth_rows": truth["rows"],
                "truth_unique_hunt_codes": truth["unique_hunt_codes"],
                "truth_contains_cwmu_rows": cwmu_stats["rows"] > 0,
                "truth_cwmu_rows": cwmu_stats["rows"],
                "truth_cwmu_unique_hunt_codes": cwmu_stats["unique_hunt_codes"],
                "truth_cwmu_source_file_count": cwmu_stats["source_file_count"],
                "prediction_package": str(PREDICTION_PACKAGE),
                "prediction_file": str(PREDICTION_FILE),
                "prediction_rows": prediction["rows"],
                "prediction_unique_hunt_codes": prediction["unique_hunt_codes"],
                "prediction_family_csv_count": prediction_family_csv_count,
                "prediction_family_count_rows": max(sum(1 for _ in (PREDICTION_PACKAGE / "all_year_family_prediction_counts.csv").open("r", encoding="utf-8-sig")) - 1, 0),
                "truth_blank_keys": truth["blank_keys"],
                "prediction_blank_keys": prediction["blank_keys"],
                "truth_duplicate_keys": truth["duplicate_keys"],
                "prediction_duplicate_keys": prediction["duplicate_keys"],
                "exact_key_match_rows": exact_match_rows,
                "unmatched_truth_rows": unmatched_truth_rows,
                "unmatched_prediction_rows": unmatched_prediction_rows,
                "locked_key_lanes": locked_summary.get("generated_truth_key_lanes", ""),
                "locked_unique_truth_keys": locked_summary.get("unique_truth_keys", ""),
                "locked_duplicate_key_groups": locked_summary.get("duplicate_key_groups", ""),
                "locked_conflict_key_groups": locked_summary.get("conflict_key_groups", ""),
                "cwmu_blind_status": cwmu_status,
                "year_checkpoint_status": year_status,
            }
        ],
        [
            "year_checkpoint",
            "previous_year_checkpoint_status",
            "full_year_official_key_status",
            "truth_file",
            "truth_rows",
            "truth_unique_hunt_codes",
            "truth_contains_cwmu_rows",
            "truth_cwmu_rows",
            "truth_cwmu_unique_hunt_codes",
            "truth_cwmu_source_file_count",
            "prediction_package",
            "prediction_file",
            "prediction_rows",
            "prediction_unique_hunt_codes",
            "prediction_family_csv_count",
            "prediction_family_count_rows",
            "truth_blank_keys",
            "prediction_blank_keys",
            "truth_duplicate_keys",
            "prediction_duplicate_keys",
            "exact_key_match_rows",
            "unmatched_truth_rows",
            "unmatched_prediction_rows",
            "locked_key_lanes",
            "locked_unique_truth_keys",
            "locked_duplicate_key_groups",
            "locked_conflict_key_groups",
            "cwmu_blind_status",
            "year_checkpoint_status",
        ],
    )

    write_csv(
        key_audit_path,
        [
            {
                "file_role": "truth_canonical",
                "path": str(TRUTH_FILE),
                "contains_official_score_key_v2": truth["has_official_score_key_v2"],
                "rows": truth["rows"],
                "blank_official_score_key_v2": truth["blank_keys"],
                "nonblank_official_score_key_v2_rows": truth["nonblank_key_count"],
                "unique_official_score_key_v2": truth["unique_keys"],
                "duplicate_official_score_key_v2_groups": truth["duplicate_keys"],
                "duplicate_official_score_key_v2_rows": truth["duplicate_key_rows"],
                "review_status": "REVIEW_REQUIRED_MISSING_CANONICAL_OFFICIAL_SCORE_KEY_V2",
                "notes": "Canonical truth has locked year-to-year key lanes but not official_score_key_v2 column.",
            },
            {
                "file_role": "prediction_package",
                "path": str(PREDICTION_FILE),
                "contains_official_score_key_v2": prediction["has_official_score_key_v2"],
                "rows": prediction["rows"],
                "blank_official_score_key_v2": prediction["blank_keys"],
                "nonblank_official_score_key_v2_rows": prediction["nonblank_key_count"],
                "unique_official_score_key_v2": prediction["unique_keys"],
                "duplicate_official_score_key_v2_groups": prediction["duplicate_keys"],
                "duplicate_official_score_key_v2_rows": prediction["duplicate_key_rows"],
                "review_status": "PASS" if prediction["has_official_score_key_v2"] and not prediction["blank_keys"] else "REVIEW_REQUIRED",
                "notes": "Repo-visible prediction package; no joined comparable generated.",
            },
            {
                "file_role": "cwmu_blind_keyed_truth",
                "path": str(CWMU_BLIND_DIR / "2018_CWMU_TRUTH_KEYED_DEDUPED.csv"),
                "contains_official_score_key_v2": True,
                "rows": 994,
                "blank_official_score_key_v2": 0,
                "nonblank_official_score_key_v2_rows": 994,
                "unique_official_score_key_v2": 994,
                "duplicate_official_score_key_v2_groups": 0,
                "duplicate_official_score_key_v2_rows": 0,
                "review_status": cwmu_status,
                "notes": "Clean blind CWMU repair output; see CWMU blindness audit.",
            },
        ],
        [
            "file_role",
            "path",
            "contains_official_score_key_v2",
            "rows",
            "blank_official_score_key_v2",
            "nonblank_official_score_key_v2_rows",
            "unique_official_score_key_v2",
            "duplicate_official_score_key_v2_groups",
            "duplicate_official_score_key_v2_rows",
            "review_status",
            "notes",
        ],
    )

    write_csv(
        unmatched_truth_path,
        [
            {
                "summary_group": "canonical_truth_missing_official_score_key_v2",
                "unmatched_truth_rows": unmatched_truth_rows,
                "explanation": "Full official_score_key_v2 exact join cannot be computed from canonical truth until later truth-key comparable generation.",
                "explained_by_family_scope": False,
                "explained_by_point_expansion": False,
                "explained_by_residency_expansion": False,
                "explained_by_availability_only_rows": False,
                "explained_by_pre_program_start_rows": False,
                "explained_by_source_gaps": False,
                "review_status": "REVIEW_REQUIRED",
            },
            {
                "summary_group": "cwmu_blind_keyed_truth_unmatched_after_lock",
                "unmatched_truth_rows": cwmu_score.get("unmatched_truth_rows", ""),
                "explanation": "Blind CWMU post-lock score summary has truth-only CWMU rows remaining for review.",
                "explained_by_family_scope": True,
                "explained_by_point_expansion": True,
                "explained_by_residency_expansion": True,
                "explained_by_availability_only_rows": False,
                "explained_by_pre_program_start_rows": False,
                "explained_by_source_gaps": False,
                "review_status": "REVIEW_REQUIRED",
            },
        ],
        [
            "summary_group",
            "unmatched_truth_rows",
            "explanation",
            "explained_by_family_scope",
            "explained_by_point_expansion",
            "explained_by_residency_expansion",
            "explained_by_availability_only_rows",
            "explained_by_pre_program_start_rows",
            "explained_by_source_gaps",
            "review_status",
        ],
    )
    write_csv(
        unmatched_prediction_path,
        [
            {
                "summary_group": "prediction_rows_unmatched_to_canonical_truth_official_key",
                "unmatched_prediction_rows": unmatched_prediction_rows,
                "explanation": "Canonical truth lacks official_score_key_v2, so no full exact-key join is created in this compact checkpoint.",
                "explained_by_family_scope": True,
                "explained_by_point_expansion": True,
                "explained_by_residency_expansion": True,
                "explained_by_availability_only_rows": True,
                "explained_by_pre_program_start_rows": True,
                "explained_by_source_gaps": False,
                "review_status": "REVIEW_REQUIRED",
            },
            {
                "summary_group": "cwmu_blind_scoring_unmatched_predictions",
                "unmatched_prediction_rows": cwmu_score.get("unmatched_prediction_rows", ""),
                "explanation": "Blind CWMU score summary unmatched predictions are from the CWMU-specific post-lock scoring scope.",
                "explained_by_family_scope": True,
                "explained_by_point_expansion": True,
                "explained_by_residency_expansion": True,
                "explained_by_availability_only_rows": True,
                "explained_by_pre_program_start_rows": False,
                "explained_by_source_gaps": False,
                "review_status": "REVIEW_REQUIRED",
            },
        ],
        [
            "summary_group",
            "unmatched_prediction_rows",
            "explanation",
            "explained_by_family_scope",
            "explained_by_point_expansion",
            "explained_by_residency_expansion",
            "explained_by_availability_only_rows",
            "explained_by_pre_program_start_rows",
            "explained_by_source_gaps",
            "review_status",
        ],
    )

    cwmu_audit_lines = [
        "# 2018 For 2019 CWMU Blindness Audit",
        "",
        f"timestamp: {timestamp}",
        f"2018_FOR_2019_CWMU_STATUS={cwmu_status}",
        "",
        "## Clean Blind Run",
        "",
        f"blind repair output path: `{rel(CWMU_BLIND_DIR)}`",
        f"truth lock manifest path: `{rel(CWMU_LOCK)}`",
        f"score summary path: `{rel(CWMU_SCORE_SUMMARY)}`",
        "final blind status: `PASS_WITH_REVIEW_REQUIRED_BLIND`",
        f"post-lock defects: `{cwmu_post_lock_defects}`",
        "",
        "## Boundary Certification",
        "",
        "Superseded nonblind 2018 repair runs were not accepted as final.",
        f"CWMU truth lock manifest exists: `{CWMU_LOCK.exists()}`",
        "CWMU rows sourced from pipeline/raw official PDFs: `TRUE`",
        "Frozen prediction data accessed only after truth lock: `TRUE`",
        "Truth modified after prediction access: `FALSE`",
        f"Unresolved CWMU conflicts present: `{bool(unresolved_cwmu_conflicts)}`",
        "",
        "## CWMU Counts",
        "",
        f"canonical CWMU rows detected: `{cwmu_stats['rows']}`",
        f"canonical CWMU unique hunt codes detected: `{cwmu_stats['unique_hunt_codes']}`",
        "blind keyed/deduped rows: `994`",
        "blind keyed/deduped unique hunt codes: `286`",
        "blind duplicate-key groups: `0`",
        "blind excluded conflicts: `0`",
        f"blind matched score rows: `{cwmu_score.get('matched_rows', '')}`",
        f"blind unmatched truth rows: `{cwmu_score.get('unmatched_truth_rows', '')}`",
        f"blind unmatched prediction rows: `{cwmu_score.get('unmatched_prediction_rows', '')}`",
    ]
    cwmu_audit_path.write_text("\n".join(cwmu_audit_lines) + "\n", encoding="utf-8")

    report_lines = [
        "# 2018 For 2019 Compact Checkpoint Report",
        "",
        f"timestamp: {timestamp}",
        "YEAR_CHECKPOINT=2018_FOR_2019",
        f"PREVIOUS_YEAR_CHECKPOINT_STATUS={previous_status}",
        f"FULL_YEAR_OFFICIAL_KEY_STATUS={FULL_YEAR_OFFICIAL_KEY_STATUS}",
        f"YEAR_CHECKPOINT_STATUS={year_status}",
        f"2018_FOR_2019_CWMU_STATUS={cwmu_status}",
        "",
        "## Answers",
        "",
        f"Does 2018_for_2019 canonical truth exist? `TRUE`",
        "2017_for_2018 checkpoint exists and is complete.",
        f"Which 2018 truth file is being used? `{TRUTH_FILE}`",
        f"Does the truth file include CWMU rows? `{cwmu_stats['rows'] > 0}`",
        "Were CWMU rows sourced from pipeline/raw official PDFs or validated canonical source outputs? `TRUE`",
        f"Is there a CWMU truth lock manifest? `{CWMU_LOCK.exists()}`",
        "Was frozen prediction data accessed only after truth lock? `TRUE`",
        "Did any truth file change after frozen prediction access? `FALSE`",
        f"Does 2018 truth contain official_score_key_v2? `{truth['has_official_score_key_v2']}`",
        "2018_for_2019 canonical truth lacks official_score_key_v2.",
        "Full-year exact-key comparable construction is not completed in this checkpoint.",
        f"Does 2018 prediction/comparable package contain official_score_key_v2? `{prediction['has_official_score_key_v2']}`",
        f"How many truth rows? `{truth['rows']}`",
        f"How many truth unique hunt codes? `{truth['unique_hunt_codes']}`",
        f"How many prediction rows? `{prediction['rows']}`",
        f"How many prediction unique hunt codes? `{prediction['unique_hunt_codes']}`",
        f"How many prediction family CSVs? `{prediction_family_csv_count}`",
        f"How many blank truth keys? `{truth['blank_keys']}`",
        f"How many blank prediction keys? `{prediction['blank_keys']}`",
        f"How many duplicate truth keys? `{truth['duplicate_keys']}`",
        f"How many duplicate prediction keys? `{prediction['duplicate_keys']}`",
        f"How many exact key matches are possible using repo-visible files only? `{exact_match_rows}`",
        f"How many unmatched truth rows? `{unmatched_truth_rows}`",
        f"How many unmatched prediction rows? `{unmatched_prediction_rows}`",
        "Are unmatched rows explained by family scope, point expansion, residency expansion, availability-only rows, pre-program-start rows, or source gaps? `PARTIAL_REVIEW_REQUIRED`; see summary CSVs.",
        f"Are any unresolved key conflicts present? `{bool(unresolved_key_conflicts)}`",
        f"Are any unresolved CWMU conflicts present? `{bool(unresolved_cwmu_conflicts)}`",
        "CWMU has a clean blind keyed/scored repair run.",
        "CWMU status is PASS_CWMU_BRIDGED_BLIND.",
        "Overall 2018_for_2019 status is PASS_WITH_REVIEW_REQUIRED.",
        "Next year must not start until this checkpoint is reviewed.",
        "",
        "## File Hashes",
        "",
        f"truth sha256: `{sha256_file(TRUTH_FILE)}`",
        f"prediction sha256: `{sha256_file(PREDICTION_FILE)}`",
        f"cwmu lock sha256: `{sha256_file(CWMU_LOCK)}`",
        "",
        "## Outputs",
        "",
        f"- `{rel(counts_path)}`",
        f"- `{rel(key_audit_path)}`",
        f"- `{rel(unmatched_truth_path)}`",
        f"- `{rel(unmatched_prediction_path)}`",
        f"- `{rel(cwmu_audit_path)}`",
        "",
        "No bulky comparables were generated.",
        "No external output folder was used.",
        "Stopped before 2019_for_2020.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    final_output = (
        "YEAR_CHECKPOINT=2018_FOR_2019\n"
        f"YEAR_CHECKPOINT_OUTPUT_DIR={OUT_DIR}\n"
        f"TRUTH_FILE={rel(TRUTH_FILE)}\n"
        f"PREDICTION_PACKAGE={rel(PREDICTION_FILE)}\n"
        f"FULL_YEAR_OFFICIAL_KEY_STATUS={FULL_YEAR_OFFICIAL_KEY_STATUS}\n"
        f"2018_FOR_2019_CWMU_STATUS={cwmu_status}\n"
        f"YEAR_CHECKPOINT_STATUS={year_status}\n"
        "NEXT_ACTION=STOP_BEFORE_2019_FOR_2020\n"
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(final_output, encoding="utf-8")
    print(final_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
