"""Create the locked repo-side handoff for later test-against generation.

The handoff is manifest-only plus lightweight audits. It does not generate
truth-test comparables, joined scoring files, or outputs outside this repo.
"""

from __future__ import annotations

import csv
import hashlib
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_DIR = REPO_ROOT / "audits" / "year_to_year_key_correction20260721_021528"
LOCK_MANIFEST = LOCK_DIR / "YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST.md"


PREDICTION_SELECTION = {
    2018: REPO_ROOT / "audits" / "year_by_year_blockers_and_scoring_20260707_231950" / "runs" / "2018",
    2019: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260721_youth_turkey_program_start_fix" / "runs" / "2019",
    2020: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260721_youth_turkey_program_start_fix" / "runs" / "2020",
    2021: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260721_youth_turkey_program_start_fix" / "runs" / "2021",
    2022: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2022",
    2023: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2023",
    2024: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2024",
    2025: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2025",
    2026: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2026",
    2027: REPO_ROOT / "audits" / "progressive_prediction_audit" / "20260705_090526" / "runs" / "2027",
}


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_csv_rows_fast(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("rb") as f:
        rows = sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1024 * 1024), b""))
    return max(rows - 1, 0)


def unique_hunt_codes(path: Path) -> int | None:
    if not path.exists() or path.stat().st_size <= 10:
        return 0
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "hunt_code" not in reader.fieldnames:
                return None
            codes: Set[str] = set()
            for row in reader:
                code = (row.get("hunt_code") or "").strip()
                if code:
                    codes.add(code)
            return len(codes)
    except UnicodeDecodeError:
        return None


def audit_row(
    file_role: str,
    path: Path,
    required_for: str,
    review_status: str,
    notes: str = "",
    row_count_override: int | None = None,
) -> Dict[str, object]:
    row_count = row_count_override
    hunt_count = None
    if path.suffix.lower() == ".csv":
        if row_count is None:
            row_count = count_csv_rows_fast(path)
        hunt_count = unique_hunt_codes(path)
    if hunt_count is not None:
        notes = f"{notes}; unique_hunt_codes={hunt_count}".strip("; ")
    return {
        "file_role": file_role,
        "path": rel(path),
        "file_name": path.name,
        "row_count_if_csv": "" if row_count is None else row_count,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "required_for": required_for,
        "review_status": review_status,
        "notes": notes,
    }


def read_summary() -> List[Dict[str, str]]:
    summary_path = LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv"
    with summary_path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> int:
    if not LOCK_MANIFEST.exists():
        raise SystemExit(f"Missing lock manifest: {LOCK_MANIFEST}")

    lock_text = LOCK_MANIFEST.read_text(encoding="utf-8", errors="replace")
    if "TRUTH_KEY_LAYER_LOCKED_BEFORE_COMPARABLE_EXPORT = TRUE" not in lock_text:
        raise SystemExit("Lock manifest does not certify the key layer boundary.")

    summary_rows = read_summary()
    rows: List[Dict[str, object]] = []
    timestamp = datetime.now().isoformat(timespec="seconds")

    rows.append(
        audit_row(
            "key_lock_manifest",
            LOCK_MANIFEST,
            "prove locked truth/key boundary",
            "LOCKED",
        )
    )
    rows.append(
        audit_row(
            "key_recipe",
            LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_REPORT.md",
            "document deterministic key construction",
            "LOCKED",
        )
    )
    for file_role, name, required_for in [
        ("key_recipe", "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv", "year-level truth/key counts"),
        ("duplicate_key_audit", "YEAR_TO_YEAR_DUPLICATE_KEY_AUDIT.csv", "duplicate-key review before exact-key testing"),
        ("key_conflict_review", "YEAR_TO_YEAR_KEY_CONFLICT_REVIEW.csv", "conflict review before exact-key testing"),
        ("row_count_sanity_audit", "YEAR_TO_YEAR_ROW_COUNT_SANITY_AUDIT.csv", "row-count sanity validation"),
        ("source_lineage_audit", "YEAR_TO_YEAR_SOURCE_LINEAGE_AUDIT.csv", "source lineage validation"),
        ("source_lineage_audit", "YEAR_TO_YEAR_SOURCE_PDF_LIST.json", "source PDF inventory"),
    ]:
        path = LOCK_DIR / name
        rows.append(
            audit_row(
                file_role,
                path,
                required_for,
                "REVIEW_REQUIRED" if file_role in {"duplicate_key_audit", "key_conflict_review"} else "LOCKED",
            )
        )

    for summary in summary_rows:
        truth_path = REPO_ROOT / summary["canonical_truth_path"]
        review_status = "LOCKED_PASS" if summary.get("sanity_status") == "PASS" else "LOCKED_REVIEW_REQUIRED"
        rows.append(
            audit_row(
                "locked_truth_key_file",
                truth_path,
                "generate all_year_truth_key_comparable.csv later",
                review_status,
                notes=(
                    f"actual_draw_year={summary['actual_draw_year']}; "
                    f"model_target_year={summary['model_target_year']}; "
                    f"unique_truth_keys={summary['unique_truth_keys']}; "
                    f"duplicate_key_groups={summary['duplicate_key_groups']}; "
                    f"conflict_key_groups={summary['conflict_key_groups']}"
                ),
                row_count_override=int(summary["physical_truth_rows"]),
            )
        )

    prediction_review = "REVIEW_REQUIRED_MIXED_PREDICTION_RUNS"
    selected_prediction_rows = 0
    selected_prediction_files = 0
    selected_prediction_hunts = Counter()
    for target_year, run_dir in sorted(PREDICTION_SELECTION.items()):
        family_predictions = run_dir / "family_predictions.csv"
        if family_predictions.exists():
            selected_prediction_files += 1
            row = audit_row(
                "prediction_file_for_exact_key_test",
                family_predictions,
                "generate exact-key prediction-vs-truth tests later",
                prediction_review,
                notes=f"target_year={target_year}; bulky_file_not_in_zip",
            )
            selected_prediction_rows += int(row["row_count_if_csv"] or 0)
            rows.append(row)
        for name in ("all_year_family_prediction_counts.csv", "per_family_year_prediction_counts.csv", "run_metadata.json"):
            path = run_dir / name
            if path.exists():
                rows.append(
                    audit_row(
                        "family_prediction_output",
                        path,
                        "later prediction run provenance and family row checks",
                        prediction_review,
                        notes=f"target_year={target_year}",
                    )
                )
        for path in sorted(run_dir.glob("*duplicate_official_score_key_v2*")):
            if path.is_file():
                rows.append(
                    audit_row(
                        "unmatched_diagnostic_source",
                        path,
                        "later exact-key duplicate/unmatched diagnostics",
                        "REVIEW_REQUIRED",
                        notes=f"target_year={target_year}",
                    )
                )

    required_files_path = LOCK_DIR / "YEAR_TO_YEAR_TEST_AGAINST_REQUIRED_FILES.csv"
    manifest_path = LOCK_DIR / "YEAR_TO_YEAR_TEST_AGAINST_HANDOFF_MANIFEST.md"
    spec_path = LOCK_DIR / "YEAR_TO_YEAR_TEST_AGAINST_EXPORT_SPEC.md"
    zip_path = LOCK_DIR / "YEAR_TO_YEAR_TEST_AGAINST_HANDOFF_PACKAGE.zip"

    fieldnames = [
        "file_role",
        "path",
        "file_name",
        "row_count_if_csv",
        "size_bytes",
        "sha256",
        "required_for",
        "review_status",
        "notes",
    ]
    write_csv(required_files_path, rows, fieldnames)

    status_counts = Counter(row.get("sanity_status", "") for row in summary_rows)
    duplicate_total = sum(int(row["duplicate_key_groups"]) for row in summary_rows)
    conflict_total = sum(int(row["conflict_key_groups"]) for row in summary_rows)
    excluded_total = sum(int(row["excluded_missing_or_nonnumeric_probability_lanes"]) for row in summary_rows)

    manifest_lines = [
        "# Year-to-Year Test Against Handoff Manifest",
        "",
        f"handoff_timestamp: {timestamp}",
        f"lock_manifest_path: {rel(LOCK_MANIFEST)}",
        "lock_status: LOCKED",
        "key_status: PASS_WITH_REVIEW_REQUIRED",
        "CODEX_DID_NOT_EXPORT_EXTERNAL_COMPARABLES = TRUE",
        "EXTERNAL_OUTPUT_PATH_UNKNOWN_TO_CODEX = TRUE",
        "CHATGPT_OR_USER_GENERATES_TEST_AGAINST_FILES_AFTER_HANDOFF = TRUE",
        "",
        "## Boundary",
        "",
        "This handoff contains manifests, hashes, row counts, and lightweight repo-side audits only.",
        "It does not contain generated test-against comparable outputs or bulky joined scoring files.",
        "",
        "## Locked Truth/Key Files Required",
        "",
    ]
    for summary in summary_rows:
        manifest_lines.append(
            f"- {summary['actual_draw_year']}_for_{summary['model_target_year']}: "
            f"{summary['canonical_truth_path']} | rows={summary['physical_truth_rows']} | "
            f"hunt_codes={summary['unique_hunt_codes']} | key_lanes={summary['generated_truth_key_lanes']} | "
            f"unique_keys={summary['unique_truth_keys']} | duplicate_groups={summary['duplicate_key_groups']} | "
            f"conflict_groups={summary['conflict_key_groups']} | status={summary['sanity_status']}"
        )
    manifest_lines.extend(
        [
            "",
            "## Prediction Files Required For Later Exact-Key Testing",
            "",
        ]
    )
    for target_year, run_dir in sorted(PREDICTION_SELECTION.items()):
        family_predictions = run_dir / "family_predictions.csv"
        if family_predictions.exists():
            matching = next(row for row in rows if row["path"] == rel(family_predictions))
            manifest_lines.append(
                f"- target_year={target_year}: {rel(family_predictions)} | "
                f"rows={matching['row_count_if_csv']} | size_bytes={matching['size_bytes']} | "
                f"sha256={matching['sha256']} | review_status={prediction_review}"
            )
        else:
            manifest_lines.append(f"- target_year={target_year}: MISSING family_predictions.csv in {rel(run_dir)}")
    manifest_lines.extend(
        [
            "",
            "## Review Required Flags",
            "",
            f"truth_year_status_counts: {dict(status_counts)}",
            f"duplicate_key_groups_total: {duplicate_total}",
            f"conflict_key_groups_total: {conflict_total}",
            f"excluded_missing_or_nonnumeric_probability_lane_events_total: {excluded_total}",
            f"selected_prediction_files: {selected_prediction_files}",
            f"selected_prediction_rows: {selected_prediction_rows}",
            f"prediction_selection_review_status: {prediction_review}",
            "",
            "## Required Files Manifest",
            "",
            f"- {rel(required_files_path)}",
        ]
    )
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    spec_lines = [
        "# Year-to-Year Test Against Export Specification",
        "",
        "This is a specification only. It is not an export.",
        "",
        "## Inputs",
        "",
        f"- Lock manifest: {rel(LOCK_MANIFEST)}",
        f"- Required files manifest: {rel(required_files_path)}",
        "- Use locked canonical truth/key files and the selected prediction files listed in the required files manifest.",
        "- Preserve the key recipe from the locked report and manifest.",
        "",
        "## Later Files To Generate",
        "",
        "- all_year_truth_key_comparable.csv",
        "- all_year_prediction_truth_exact_key_join.csv",
        "- all_year_score_matrix.csv",
        "- unmatched_predictions_by_year.csv",
        "- unmatched_truth_by_year.csv",
        "- family_year_score_summary.csv",
        "- species_year_score_summary.csv",
        "- residency_year_score_summary.csv",
        "- point_bucket_score_summary.csv",
        "",
        "## Later Generation Rules",
        "",
        "- Generate these files only after handoff, outside this Codex repo-side construction run.",
        "- Use exact key matching against the locked truth/key recipe.",
        "- Do not revise locked truth files while generating test-against outputs.",
        "- If defects are discovered, record defects and create a new clean lock run instead of patching locked truth in place.",
        "- Keep bulky joined prediction-vs-truth outputs out of GitHub unless separately approved.",
    ]
    spec_path.write_text("\n".join(spec_lines) + "\n", encoding="utf-8")

    zip_members = [
        LOCK_MANIFEST,
        LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_REPORT.md",
        LOCK_DIR / "YEAR_TO_YEAR_KEY_CORRECTION_SUMMARY.csv",
        LOCK_DIR / "YEAR_TO_YEAR_DUPLICATE_KEY_AUDIT.csv",
        LOCK_DIR / "YEAR_TO_YEAR_KEY_CONFLICT_REVIEW.csv",
        LOCK_DIR / "YEAR_TO_YEAR_ROW_COUNT_SANITY_AUDIT.csv",
        LOCK_DIR / "YEAR_TO_YEAR_SOURCE_LINEAGE_AUDIT.csv",
        LOCK_DIR / "YEAR_TO_YEAR_SOURCE_PDF_LIST.json",
        required_files_path,
        manifest_path,
        spec_path,
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in zip_members:
            zf.write(path, arcname=rel(path))

    print(
        f"YEAR_TO_YEAR_KEY_CORRECTION_OUTPUT_DIR={LOCK_DIR}\n"
        f"YEAR_TO_YEAR_TRUTH_KEY_LOCK_MANIFEST={LOCK_MANIFEST}\n"
        f"YEAR_TO_YEAR_TEST_AGAINST_HANDOFF_MANIFEST={manifest_path}\n"
        f"YEAR_TO_YEAR_TEST_AGAINST_REQUIRED_FILES={required_files_path}\n"
        f"YEAR_TO_YEAR_TEST_AGAINST_EXPORT_SPEC={spec_path}\n"
        f"YEAR_TO_YEAR_TEST_AGAINST_HANDOFF_PACKAGE={zip_path}\n"
        "YEAR_TO_YEAR_KEY_STATUS=PASS_WITH_REVIEW_REQUIRED\n"
        "EXTERNAL_COMPARABLES_STATUS=NOT_EXPORTED_BY_CODEX\n"
        "NEXT_ACTION=CHATGPT_OR_USER_GENERATES_TEST_AGAINST_FILES_FROM_LOCKED_HANDOFF\n",
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
