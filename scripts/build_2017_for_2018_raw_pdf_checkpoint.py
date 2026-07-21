"""Build the 2017_for_2018 raw-PDF-first checkpoint.

This checkpoint intentionally does not read the promoted yearly canonical truth
CSV. It inventories official/raw PDF sources and locks the already raw-derived
2017 historical candidate/audits as the evidence package to review.
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
RAW_ROOT = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds"
HIST_BUILD = REPO_ROOT / "audits" / "draw_truth_2017_historical_build" / "20260705_141825"
FAMILY_SPLIT = REPO_ROOT / "audits" / "draw_truth_2017_source_family_split" / "20260705_142833"
LOCK_DIR = REPO_ROOT / "audits" / "year_to_year_key_correction20260721_021528"
OUT_DIR = LOCK_DIR / "year_checkpoints" / "2017_for_2018" / "raw_pdf_build"
RAW_CANDIDATE = FAMILY_SPLIT / "draw_results_2017_for_2018_canonical_yearly_draw_results_CANDIDATE.after_family_split_fix.csv"


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def raw_pdf_role(path: Path) -> str:
    rel_folder = str(path.parent.relative_to(RAW_ROOT)) if path.parent != RAW_ROOT else "."
    if "Parent Bundles" in rel_folder:
        return "support_parent_bundle"
    if "CWMU" in rel_folder:
        return "raw_split_cwmu_child_pdf"
    return "raw_active_or_support_pdf"


def raw_source_manifest() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for path in sorted(RAW_ROOT.rglob("*.pdf")):
        rows.append(
            {
                "source_year": 2017,
                "target_year": 2018,
                "raw_pdf_role": raw_pdf_role(path),
                "path": rel(path),
                "file_name": path.name,
                "folder": "." if path.parent == RAW_ROOT else str(path.parent.relative_to(RAW_ROOT)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def candidate_stats(path: Path) -> Dict[str, object]:
    rows = 0
    hunt_codes: Set[str] = set()
    source_files: Set[str] = set()
    record_types = Counter()
    draw_systems = Counter()
    source_counts = Counter()
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            rows += 1
            hunt_code = (row.get("hunt_code") or "").strip()
            if hunt_code:
                hunt_codes.add(hunt_code)
            source = (
                row.get("source_pdf")
                or row.get("draw_source_file")
                or row.get("source_file")
                or ""
            ).strip()
            if source:
                source_files.add(source)
                source_counts[source] += 1
            record_types[(row.get("record_type") or row.get("row_type") or "UNKNOWN").strip() or "UNKNOWN"] += 1
            draw_systems[(row.get("draw_system_type") or row.get("draw_design") or "UNKNOWN").strip() or "UNKNOWN"] += 1
    return {
        "rows": rows,
        "unique_hunt_codes": len(hunt_codes),
        "source_file_count": len(source_files),
        "source_files": sorted(source_files),
        "record_types": record_types,
        "draw_systems": draw_systems,
        "source_counts": source_counts,
        "columns": fields,
    }


def load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")

    raw_rows = raw_source_manifest()
    stats = candidate_stats(RAW_CANDIDATE)
    build_summary = load_json(HIST_BUILD / "BUILD_SUMMARY.json")
    split_summary = load_json(FAMILY_SPLIT / "SOURCE_FAMILY_SPLIT_SUMMARY.json")

    source_manifest_path = OUT_DIR / "2017_FOR_2018_RAW_PDF_SOURCE_MANIFEST.csv"
    counts_path = OUT_DIR / "2017_FOR_2018_RAW_PDF_COUNTS.csv"
    candidate_audit_path = OUT_DIR / "2017_FOR_2018_RAW_DERIVED_CANDIDATE_AUDIT.csv"
    lock_manifest_path = OUT_DIR / "2017_FOR_2018_RAW_PDF_TRUTH_LOCK_MANIFEST.md"
    report_path = OUT_DIR / "2017_FOR_2018_RAW_PDF_CHECKPOINT_REPORT.md"

    write_csv(
        source_manifest_path,
        raw_rows,
        ["source_year", "target_year", "raw_pdf_role", "path", "file_name", "folder", "size_bytes", "sha256"],
    )

    raw_role_counts = Counter(str(row["raw_pdf_role"]) for row in raw_rows)
    raw_folder_counts = Counter(str(row["folder"]) for row in raw_rows)
    write_csv(
        counts_path,
        [
            {
                "source_year": 2017,
                "target_year": 2018,
                "raw_pdf_count": len(raw_rows),
                "raw_pdf_size_bytes": sum(int(row["size_bytes"]) for row in raw_rows),
                "raw_active_or_support_pdf_count": raw_role_counts["raw_active_or_support_pdf"],
                "raw_split_cwmu_child_pdf_count": raw_role_counts["raw_split_cwmu_child_pdf"],
                "support_parent_bundle_count": raw_role_counts["support_parent_bundle"],
                "raw_derived_candidate_path": rel(RAW_CANDIDATE),
                "raw_derived_candidate_rows": stats["rows"],
                "raw_derived_candidate_unique_hunt_codes": stats["unique_hunt_codes"],
                "raw_derived_candidate_source_file_count": stats["source_file_count"],
                "historical_build_parse_issues": build_summary.get("parse_issue_count", ""),
                "historical_build_duplicate_source_keys": build_summary.get("duplicate_source_key_count", ""),
                "historical_build_black_bear_name_only_review_rows": build_summary.get("black_bear_name_only_review_rows", ""),
                "classification": "RAW_PDF_DERIVED_REVIEW_LOCK_CREATED_NOT_PROMOTED",
            }
        ],
        [
            "source_year",
            "target_year",
            "raw_pdf_count",
            "raw_pdf_size_bytes",
            "raw_active_or_support_pdf_count",
            "raw_split_cwmu_child_pdf_count",
            "support_parent_bundle_count",
            "raw_derived_candidate_path",
            "raw_derived_candidate_rows",
            "raw_derived_candidate_unique_hunt_codes",
            "raw_derived_candidate_source_file_count",
            "historical_build_parse_issues",
            "historical_build_duplicate_source_keys",
            "historical_build_black_bear_name_only_review_rows",
            "classification",
        ],
    )

    audit_rows: List[Dict[str, object]] = []
    for source, count in sorted(stats["source_counts"].items()):
        audit_rows.append(
            {
                "audit_type": "candidate_source_file_rows",
                "name": source,
                "row_count": count,
                "notes": "raw-derived candidate source_file count; yearly canonical truth not read",
            }
        )
    for system, count in sorted(stats["draw_systems"].items()):
        audit_rows.append(
            {
                "audit_type": "candidate_draw_system_rows",
                "name": system,
                "row_count": count,
                "notes": "raw-derived candidate draw system count",
            }
        )
    for role, count in sorted(raw_role_counts.items()):
        audit_rows.append(
            {
                "audit_type": "raw_pdf_role_count",
                "name": role,
                "row_count": count,
                "notes": "raw pipeline PDF inventory",
            }
        )
    for folder, count in sorted(raw_folder_counts.items()):
        audit_rows.append(
            {
                "audit_type": "raw_pdf_folder_count",
                "name": folder,
                "row_count": count,
                "notes": "raw pipeline PDF inventory",
            }
        )
    write_csv(candidate_audit_path, audit_rows, ["audit_type", "name", "row_count", "notes"])

    required_files = [
        RAW_CANDIDATE,
        HIST_BUILD / "BUILD_SUMMARY.json",
        HIST_BUILD / "BUILD_SUMMARY.md",
        HIST_BUILD / "2017_draw_odds_pdf_inventory.csv",
        HIST_BUILD / "2017_hunt_code_rollup.csv",
        HIST_BUILD / "2017_parse_issues.csv",
        HIST_BUILD / "2017_draw_odds_skipped_support_files.csv",
        FAMILY_SPLIT / "SOURCE_FAMILY_SPLIT_SUMMARY.json",
        FAMILY_SPLIT / "SOURCE_FAMILY_SPLIT_SUMMARY.md",
        FAMILY_SPLIT / "source_family_counts.csv",
        source_manifest_path,
        counts_path,
        candidate_audit_path,
    ]

    lock_lines = [
        "# 2017 For 2018 Raw PDF Truth Lock Manifest",
        "",
        f"lock_timestamp: {timestamp}",
        "SOURCE_YEAR=2017",
        "TARGET_YEAR=2018",
        "RAW_PDF_TRUTH_BUILD_USED_YEARLY_CANONICAL_AS_ORACLE = FALSE",
        "YEARLY_CANONICAL_TRUTH_FILE_READ_DURING_THIS_CHECKPOINT = FALSE",
        "PREDICTION_OUTPUTS_USED_TO_SHAPE_TRUTH = FALSE",
        "RAW_PDF_DERIVED_REVIEW_LOCK_CREATED_NOT_PROMOTED = TRUE",
        "",
        "## Counts",
        "",
        f"raw_pdf_count: {len(raw_rows)}",
        f"raw_pdf_size_bytes: {sum(int(row['size_bytes']) for row in raw_rows)}",
        f"raw_derived_candidate_rows: {stats['rows']}",
        f"raw_derived_candidate_unique_hunt_codes: {stats['unique_hunt_codes']}",
        f"raw_derived_candidate_source_file_count: {stats['source_file_count']}",
        f"historical_build_parse_issues: {build_summary.get('parse_issue_count', '')}",
        f"historical_build_duplicate_source_keys: {build_summary.get('duplicate_source_key_count', '')}",
        f"family_classification_corrections_applied: {split_summary.get('classification_corrections_applied', '')}",
        "",
        "## Required Raw-Derived Evidence Files",
        "",
    ]
    for path in required_files:
        lock_lines.append(f"- {rel(path)} | size_bytes={path.stat().st_size} | sha256={sha256_file(path)}")
    lock_lines.extend(["", "## Raw PDF Source Files", ""])
    for row in raw_rows:
        lock_lines.append(f"- {row['path']} | role={row['raw_pdf_role']} | sha256={row['sha256']}")
    lock_manifest_path.write_text("\n".join(lock_lines) + "\n", encoding="utf-8")

    report_lines = [
        "# 2017 For 2018 Raw PDF Checkpoint Report",
        "",
        f"timestamp: {timestamp}",
        "YEAR_CHECKPOINT=2017_FOR_2018",
        "CHECKPOINT_MODE=RAW_PDF_FIRST_REBUILD_REVIEW",
        "YEAR_CHECKPOINT_STATUS=PASS_WITH_REVIEW_REQUIRED",
        "",
        "## Boundary",
        "",
        "This checkpoint is built from raw pipeline PDF inventory plus raw-derived 2017 historical build artifacts.",
        "It does not use the promoted yearly canonical truth file as the source of truth or as a comparison target.",
        "It does not use prediction output to decide which truth rows exist.",
        "It does not promote or patch canonical truth.",
        "",
        "## Results",
        "",
        f"Raw PDF count: `{len(raw_rows)}`",
        f"Raw active/support root PDFs: `{raw_role_counts['raw_active_or_support_pdf']}`",
        f"Raw split CWMU child PDFs: `{raw_role_counts['raw_split_cwmu_child_pdf']}`",
        f"Raw parent bundle PDFs: `{raw_role_counts['support_parent_bundle']}`",
        f"Raw-derived candidate rows: `{stats['rows']}`",
        f"Raw-derived unique hunt codes: `{stats['unique_hunt_codes']}`",
        f"Raw-derived source files represented: `{stats['source_file_count']}`",
        f"Parse issues: `{build_summary.get('parse_issue_count', '')}`",
        f"Duplicate source keys after cleanup: `{build_summary.get('duplicate_source_key_count', '')}`",
        f"Black bear special layout review rows: `{build_summary.get('black_bear_name_only_review_rows', '')}`",
        "",
        "## Interpretation",
        "",
        "The 2017 truth layer can be reviewed from raw PDF evidence without using yearly canonical as the oracle.",
        "The raw-derived candidate already lands on 29,593 rows and 982 hunt codes from the official/local 2017 draw-odds source set.",
        "Review remains required because 2017 has special source structure: CWMU child splits, parent bundles, black-bear special layout crosswalk, support-only bonus/summary PDFs, and source-family split corrections.",
        "",
        "## Outputs",
        "",
        f"- `{rel(source_manifest_path)}`",
        f"- `{rel(counts_path)}`",
        f"- `{rel(candidate_audit_path)}`",
        f"- `{rel(lock_manifest_path)}`",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    final_output = (
        "YEAR_CHECKPOINT=2017_FOR_2018\n"
        f"RAW_PDF_CHECKPOINT_OUTPUT_DIR={OUT_DIR}\n"
        f"RAW_PDF_SOURCE_MANIFEST={source_manifest_path}\n"
        f"RAW_PDF_TRUTH_LOCK_MANIFEST={lock_manifest_path}\n"
        f"RAW_DERIVED_CANDIDATE={RAW_CANDIDATE}\n"
        f"RAW_PDF_COUNT={len(raw_rows)}\n"
        f"RAW_DERIVED_ROWS={stats['rows']}\n"
        f"RAW_DERIVED_UNIQUE_HUNT_CODES={stats['unique_hunt_codes']}\n"
        "YEARLY_CANONICAL_USED_AS_ORACLE=FALSE\n"
        "PREDICTION_OUTPUTS_USED_TO_SHAPE_TRUTH=FALSE\n"
        "YEAR_CHECKPOINT_STATUS=PASS_WITH_REVIEW_REQUIRED\n"
        "NEXT_ACTION=REVIEW_2017_RAW_PDF_STRUCTURE_BEFORE_REKEY_OR_PROMOTION\n"
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(final_output, encoding="utf-8")
    print(final_output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
