"""Per-year repo-side completion and count comparison checkpoint.

This script compares locked canonical truth counts to in-repo comparable
prediction package counts for exactly one source/target year pair, then stops.
It does not export large comparables or use any external output path.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
AUDIT_ROOT = REPO_ROOT / "audits"


def latest_key_lock_dir() -> Path:
    candidates = sorted(AUDIT_ROOT.glob("year_to_year_key_correction*/YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST.md"))
    if not candidates:
        raise SystemExit("No YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST.md found. Run key correction lock first.")
    manifest = candidates[-1]
    text = manifest.read_text(encoding="utf-8", errors="replace")
    required = "TRUTH_KEY_LAYER_LOCKED_BEFORE_COMPARABLE_EXPORT = TRUE"
    if required not in text:
        raise SystemExit(f"Key lock manifest missing required statement: {manifest}")
    return manifest.parent


def read_summary_row(lock_dir: Path, source_year: int, target_year: int) -> Dict[str, str]:
    summary = lock_dir / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv"
    with summary.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("actual_draw_year") == str(source_year) and row.get("model_target_year") == str(target_year):
                return row
    raise SystemExit(f"No locked key summary row for {source_year}_for_{target_year}")


def count_csv_rows_and_hunts(path: Path) -> Dict[str, object]:
    row_count = 0
    hunt_codes: Set[str] = set()
    family_counts = Counter()
    status_counts = Counter()
    if not path.exists() or path.stat().st_size <= 10:
        return {
            "row_count": 0,
            "unique_hunt_codes": 0,
            "hunt_codes": set(),
            "family_counts": family_counts,
            "status_counts": status_counts,
        }
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                hunt_codes.add(hunt_code)
            family = (row.get("family") or row.get("engine_family") or "").strip()
            if family:
                family_counts[family] += 1
            status = (row.get("status") or row.get("prediction_status") or row.get("classification_status") or "").strip()
            if status:
                status_counts[status] += 1
    return {
        "row_count": row_count,
        "unique_hunt_codes": len(hunt_codes),
        "hunt_codes": hunt_codes,
        "family_counts": family_counts,
        "status_counts": status_counts,
    }


def read_truth_hunts(path: Path) -> Dict[str, object]:
    rows = 0
    hunt_codes: Set[str] = set()
    source_pdfs: Set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                hunt_codes.add(hunt_code)
            source_pdf = (
                row.get("source_pdf")
                or row.get("draw_source_file")
                or row.get("source_file")
                or ""
            ).strip()
            if source_pdf:
                source_pdfs.add(source_pdf)
    return {
        "row_count": rows,
        "unique_hunt_codes": len(hunt_codes),
        "hunt_codes": hunt_codes,
        "source_pdf_count": len(source_pdfs),
        "source_pdf_sample": "; ".join(sorted(source_pdfs)[:20]),
    }


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    args = parser.parse_args()

    source_year = args.source_year
    target_year = args.target_year
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = AUDIT_ROOT / f"year_to_year_database_completion_compare{timestamp}"
    output_dir = output_root / f"{source_year}_for_{target_year}"
    output_dir.mkdir(parents=True, exist_ok=False)

    lock_dir = latest_key_lock_dir()
    lock_manifest = lock_dir / "YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST.md"
    locked_summary = read_summary_row(lock_dir, source_year, target_year)

    truth_path = CANONICAL_ROOT / f"draw_results_{source_year}_for_{target_year}_canonical_yearly_draw_results.csv"
    if not truth_path.exists():
        raise SystemExit(f"Missing canonical truth file: {truth_path}")
    truth = read_truth_hunts(truth_path)

    comparable_root = AUDIT_ROOT / f"{source_year}_to_{target_year}_yearly_test"
    family_predictions = comparable_root / "family_predictions.csv"
    comparable = count_csv_rows_and_hunts(family_predictions)

    prediction_dir = comparable_root / "predictions"
    family_rows: List[Dict[str, object]] = []
    prediction_file_count = 0
    if prediction_dir.exists():
        for path in sorted(prediction_dir.glob("*.csv")):
            prediction_file_count += 1
            counts = count_csv_rows_and_hunts(path)
            family_rows.append(
                {
                    "source_year": source_year,
                    "target_year": target_year,
                    "comparable_family_file": str(path.relative_to(REPO_ROOT)),
                    "comparable_file_rows": counts["row_count"],
                    "comparable_file_unique_hunt_codes": counts["unique_hunt_codes"],
                }
            )

    family_count_file = comparable_root / "all_year_family_prediction_counts.csv"
    if family_count_file.exists():
        with family_count_file.open("r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("source_year") == str(source_year) and row.get("target_year") == str(target_year):
                    family_rows.append(
                        {
                            "source_year": source_year,
                            "target_year": target_year,
                            "comparable_family_file": row.get("output_path", ""),
                            "family": row.get("family", ""),
                            "readiness_status": row.get("readiness_status", ""),
                            "input_truth_rows": row.get("input_truth_rows", ""),
                            "current_target_rows": row.get("current_target_rows", ""),
                            "joined_source_target_rows": row.get("joined_source_target_rows", ""),
                            "prediction_rows": row.get("prediction_rows", ""),
                            "status": row.get("status", ""),
                            "blocker_if_failed": row.get("blocker_if_failed", ""),
                        }
                    )

    truth_hunts: Set[str] = truth["hunt_codes"]  # type: ignore[assignment]
    comparable_hunts: Set[str] = comparable["hunt_codes"]  # type: ignore[assignment]
    truth_only = sorted(truth_hunts - comparable_hunts)
    comparable_only = sorted(comparable_hunts - truth_hunts)
    shared = sorted(truth_hunts & comparable_hunts)

    conflict_groups = int(locked_summary.get("conflict_key_groups") or 0)
    duplicate_groups = int(locked_summary.get("duplicate_key_groups") or 0)
    if not family_predictions.exists():
        year_status = "BLOCKED_NO_REPO_COMPARABLE_PACKAGE"
    elif conflict_groups:
        year_status = "PASS_WITH_REVIEW_REQUIRED"
    else:
        year_status = "PASS_YEAR_DATABASE_COMPLETION_COMPARE"

    count_rows = [
        {
            "source_year": source_year,
            "target_year": target_year,
            "truth_canonical_path": str(truth_path.relative_to(REPO_ROOT)),
            "truth_physical_rows": truth["row_count"],
            "truth_unique_hunt_codes": truth["unique_hunt_codes"],
            "truth_source_pdf_count": truth["source_pdf_count"],
            "locked_generated_truth_key_lanes": locked_summary.get("generated_truth_key_lanes", ""),
            "locked_unique_truth_keys": locked_summary.get("unique_truth_keys", ""),
            "locked_duplicate_key_groups": duplicate_groups,
            "locked_conflict_key_groups": conflict_groups,
            "comparable_package_path": str(comparable_root.relative_to(REPO_ROOT)) if comparable_root.exists() else "",
            "comparable_family_predictions_path": str(family_predictions.relative_to(REPO_ROOT)) if family_predictions.exists() else "",
            "comparable_prediction_files": prediction_file_count,
            "comparable_rows": comparable["row_count"],
            "comparable_unique_hunt_codes": comparable["unique_hunt_codes"],
            "shared_hunt_codes": len(shared),
            "truth_only_hunt_codes": len(truth_only),
            "comparable_only_hunt_codes": len(comparable_only),
            "truth_only_hunt_code_sample": ";".join(truth_only[:50]),
            "comparable_only_hunt_code_sample": ";".join(comparable_only[:50]),
            "year_status": year_status,
        }
    ]

    counts_path = output_dir / f"YEAR_TRUTH_VS_COMPARABLE_COUNTS_{source_year}_FOR_{target_year}.csv"
    family_path = output_dir / f"YEAR_FAMILY_COMPARABLE_COUNTS_{source_year}_FOR_{target_year}.csv"
    report_path = output_dir / f"YEAR_DATABASE_COMPLETION_AND_COMPARISON_{source_year}_FOR_{target_year}.md"
    stop_path = output_dir / f"YEAR_STOP_CHECKPOINT_{source_year}_FOR_{target_year}.txt"

    write_csv(
        counts_path,
        count_rows,
        [
            "source_year",
            "target_year",
            "truth_canonical_path",
            "truth_physical_rows",
            "truth_unique_hunt_codes",
            "truth_source_pdf_count",
            "locked_generated_truth_key_lanes",
            "locked_unique_truth_keys",
            "locked_duplicate_key_groups",
            "locked_conflict_key_groups",
            "comparable_package_path",
            "comparable_family_predictions_path",
            "comparable_prediction_files",
            "comparable_rows",
            "comparable_unique_hunt_codes",
            "shared_hunt_codes",
            "truth_only_hunt_codes",
            "comparable_only_hunt_codes",
            "truth_only_hunt_code_sample",
            "comparable_only_hunt_code_sample",
            "year_status",
        ],
    )
    write_csv(
        family_path,
        family_rows,
        [
            "source_year",
            "target_year",
            "comparable_family_file",
            "comparable_file_rows",
            "comparable_file_unique_hunt_codes",
            "family",
            "readiness_status",
            "input_truth_rows",
            "current_target_rows",
            "joined_source_target_rows",
            "prediction_rows",
            "status",
            "blocker_if_failed",
        ],
    )

    report_lines = [
        f"# Year Database Completion and Comparison: {source_year}_for_{target_year}",
        "",
        f"timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"year_status: {year_status}",
        "external_comparables_status: NOT_EXPORTED_NO_EXTERNAL_PATH_USED",
        "",
        "## Boundary",
        "",
        f"Key lock manifest: {lock_manifest.relative_to(REPO_ROOT)}",
        "Repo-side comparison used canonical truth and in-repo comparable package counts only.",
        "No external comparable output path was used or inferred.",
        "No large comparable exports were created.",
        "",
        "## Counts",
        "",
        f"truth_rows: {truth['row_count']}",
        f"truth_unique_hunt_codes: {truth['unique_hunt_codes']}",
        f"truth_source_pdf_count: {truth['source_pdf_count']}",
        f"locked_generated_truth_key_lanes: {locked_summary.get('generated_truth_key_lanes', '')}",
        f"locked_unique_truth_keys: {locked_summary.get('unique_truth_keys', '')}",
        f"locked_duplicate_key_groups: {duplicate_groups}",
        f"locked_conflict_key_groups: {conflict_groups}",
        f"comparable_prediction_files: {prediction_file_count}",
        f"comparable_rows: {comparable['row_count']}",
        f"comparable_unique_hunt_codes: {comparable['unique_hunt_codes']}",
        f"shared_hunt_codes: {len(shared)}",
        f"truth_only_hunt_codes: {len(truth_only)}",
        f"comparable_only_hunt_codes: {len(comparable_only)}",
        "",
        "## Outputs",
        "",
        f"- {counts_path.relative_to(REPO_ROOT)}",
        f"- {family_path.relative_to(REPO_ROOT)}",
        f"- {stop_path.relative_to(REPO_ROOT)}",
        "",
        "STOP_AFTER_YEAR = TRUE",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    stop_text = (
        f"YEAR_DATABASE_COMPLETION_COMPARE_OUTPUT_DIR={output_dir}\n"
        f"YEAR_COMPLETED={source_year}_FOR_{target_year}\n"
        f"YEAR_STATUS={year_status}\n"
        "STOP_AFTER_YEAR=TRUE\n"
        f"NEXT_YEAR_PENDING={source_year + 1}_FOR_{target_year + 1}\n"
    )
    stop_path.write_text(stop_text, encoding="utf-8")
    print(stop_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
