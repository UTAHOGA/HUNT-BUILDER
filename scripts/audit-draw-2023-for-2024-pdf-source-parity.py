"""Verify 2023 draw-odds PDF sources used for 2024 modeling.

This is a source-anchor audit only. It checks the user-supplied 2023 PDFs from
the older HUNTS repo against the active HUNT-BUILDER copies, then records how
those PDF names appear in the uploaded 2023-for-2024 draw CSV exports and in
current normalized draw truth.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds"))
ACTIVE_SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "pdf" / "draw_odds"
ACTIVE_CSV_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "csv"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "draw_2023_for_2024_pdf_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2023_for_2024_pdf_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2023_for_2024_pdf_source_parity.md"

CSV_SOURCE_FILES = [
    "draw_results_2023_for_2024_long.csv",
    "draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv",
]


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def draw_year(row: dict[str, str]) -> str:
    return norm(row.get("year") or row.get("draw_year") or row.get("reported_draw_year") or row.get("reported_hunt_year_inferred"))


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def expected_files() -> list[Path]:
    return sorted(LEGACY_SOURCE_DIR.glob("*.pdf"), key=lambda path: path.name.lower())


def duplicate_hash_groups(paths: list[Path]) -> list[dict[str, object]]:
    by_hash: dict[str, list[str]] = {}
    for path in paths:
        by_hash.setdefault(sha256(path), []).append(path.name)
    return [
        {"sha256": key, "files": sorted(names), "file_count": len(names)}
        for key, names in sorted(by_hash.items())
        if len(names) > 1
    ]


def csv_source_label_summary(pdf_names: set[str]) -> dict[str, object]:
    output: dict[str, object] = {}
    all_labels: set[str] = set()
    for csv_name in CSV_SOURCE_FILES:
        path = ACTIVE_CSV_DIR / csv_name
        rows = read_csv_rows(path)
        counts = Counter(norm(row.get("source_file")) for row in rows)
        represented = {label for label in counts if label}
        all_labels |= represented
        output[csv_name] = {
            "row_count": len(rows),
            "source_file_count": len(represented),
            "source_file_counts": dict(counts),
            "represented_pdf_source_labels": sorted(represented),
            "represented_pdf_labels_matching_expected_set": sorted(represented & pdf_names),
            "represented_pdf_labels_not_in_expected_set": sorted(represented - pdf_names),
            "expected_pdf_labels_not_represented": sorted(pdf_names - represented),
        }
    output["combined_csv_pdf_label_coverage"] = {
        "represented_source_labels_across_csvs": sorted(all_labels),
        "represented_expected_pdf_count": len(all_labels & pdf_names),
        "expected_pdf_count": len(pdf_names),
        "expected_pdf_labels_not_represented_by_any_csv": sorted(pdf_names - all_labels),
        "csv_source_labels_not_in_expected_pdf_set": sorted(all_labels - pdf_names),
    }
    return output


def normalized_draw_truth_source_summary(pdf_names: set[str]) -> dict[str, object]:
    rows = [row for row in read_csv_rows(DRAW_LONG) if draw_year(row) == "2024"]
    counts = Counter(norm(row.get("source_file")) for row in rows)
    represented = {label for label in counts if label}
    return {
        "normalized_draw_year": "2024",
        "normalized_rows": len(rows),
        "normalized_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}),
        "normalized_source_file_count": len(represented),
        "normalized_source_file_counts": dict(counts),
        "normalized_source_labels_matching_expected_pdf_set": sorted(represented & pdf_names),
        "normalized_source_labels_not_in_expected_pdf_set": sorted(represented - pdf_names),
        "expected_pdf_labels_not_represented_in_normalized_truth": sorted(pdf_names - represented),
        "source_label_status": (
            "SOURCE_LABEL_LINEAGE_REVIEW"
            if represented and represented != (represented & pdf_names)
            else "SOURCE_LABELS_MATCH_EXPECTED_FILES"
        ),
    }


def build_markdown(summary: dict[str, object]) -> str:
    csv_coverage = summary["csv_source_label_summary"]["combined_csv_pdf_label_coverage"]
    normalized = summary["normalized_draw_truth_source_summary"]
    lines = [
        "# 2023 Draw PDF Source Parity For 2024 Modeling",
        "",
        "Compares the user-supplied 2023 draw-odds PDFs in `HUNTS` to the active `HUNT-BUILDER` copies.",
        "",
        "## Source Result",
        "",
        f"- Expected/source PDFs: {summary['expected_file_count']}",
        f"- Byte-identical active copies: {summary['byte_match_count']}",
        f"- Missing legacy PDFs: {summary['missing_legacy_source_files']}",
        f"- Missing active PDFs: {summary['missing_active_source_files']}",
        f"- Active-only PDFs: {summary['active_only_source_file_count']}",
        f"- Active duplicate hash groups: {summary['active_duplicate_hash_group_count']}",
        "",
        "## CSV Linkage",
        "",
        f"- Expected PDF labels represented by the two 2023-for-2024 CSV exports: {csv_coverage['represented_expected_pdf_count']} / {csv_coverage['expected_pdf_count']}",
        f"- CSV source labels not in expected PDF set: {len(csv_coverage['csv_source_labels_not_in_expected_pdf_set'])}",
        f"- Expected PDF labels not represented by either CSV: {len(csv_coverage['expected_pdf_labels_not_represented_by_any_csv'])}",
        "",
        "## Normalized Draw Truth Linkage",
        "",
        f"- Normalized draw-year/model-year 2024 rows: {normalized['normalized_rows']}",
        f"- Normalized draw-year/model-year 2024 hunt codes: {normalized['normalized_unique_hunt_codes']}",
        f"- Normalized source labels matching this expected PDF set: {len(normalized['normalized_source_labels_matching_expected_pdf_set'])}",
        f"- Normalized source label status: {normalized['source_label_status']}",
        "",
        "## Interpretation",
        "",
        "- The full 17-PDF 2023 source package is byte-anchored in the active repo.",
        "- The uploaded CSV exports use only part of that PDF set as direct `source_file` labels.",
        "- Current normalized 2024 draw truth uses different `24_*` source labels, so lineage needs reconciliation before promotion.",
        "- This audit does not extract PDF values, rewrite normalized draw truth, or publish runtime data.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    legacy_paths = expected_files()
    active_paths = sorted(ACTIVE_SOURCE_DIR.glob("*.pdf"), key=lambda path: path.name.lower())
    legacy_names = {path.name for path in legacy_paths}
    active_names = {path.name for path in active_paths}
    parity_rows: list[dict[str, str]] = []
    for legacy_path in legacy_paths:
        active_path = ACTIVE_SOURCE_DIR / legacy_path.name
        legacy_hash = sha256(legacy_path)
        active_hash = sha256(active_path)
        byte_match = legacy_path.exists() and active_path.exists() and legacy_hash == active_hash
        parity_rows.append(
            {
                "file_name": legacy_path.name,
                "legacy_source_path": str(legacy_path),
                "active_source_path": relative(active_path),
                "legacy_exists": "YES" if legacy_path.exists() else "NO",
                "active_exists": "YES" if active_path.exists() else "NO",
                "legacy_size_bytes": str(legacy_path.stat().st_size) if legacy_path.exists() else "",
                "active_size_bytes": str(active_path.stat().st_size) if active_path.exists() else "",
                "legacy_sha256": legacy_hash,
                "active_sha256": active_hash,
                "byte_hash_match": "YES" if byte_match else "NO",
                "status": "PASS" if byte_match else "REVIEW",
            }
        )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_draw_odds_pdf_source_parity_for_2024_modeling",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_source_dir": relative(ACTIVE_SOURCE_DIR),
        "expected_file_count": len(legacy_paths),
        "active_source_file_count": len(active_paths),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_legacy_source_files": sum(1 for row in parity_rows if row["legacy_exists"] == "NO"),
        "missing_active_source_files": sum(1 for row in parity_rows if row["active_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "active_only_source_file_count": len(active_names - legacy_names),
        "active_only_source_files": sorted(active_names - legacy_names),
        "legacy_duplicate_hash_groups": duplicate_hash_groups(legacy_paths),
        "active_duplicate_hash_groups": duplicate_hash_groups(active_paths),
        "active_duplicate_hash_group_count": len(duplicate_hash_groups(active_paths)),
        "source_draw_result_year": "2023",
        "model_target_year": "2024",
        "csv_source_label_summary": csv_source_label_summary(legacy_names),
        "normalized_draw_truth_source_summary": normalized_draw_truth_source_summary(legacy_names),
        "guardrails": [
            "Source-anchor audit only; no PDF extraction or draw truth rewrite is performed.",
            "2023 PDF sources are model-target-year 2024 source evidence.",
            "Do not promote normalized draw truth from source-label comparisons without a reconciliation step.",
            "Do not compare this historical source package to the 2026 active hunt-code universe as a completeness score.",
        ],
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(SUMMARY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }
    fields = [
        "file_name",
        "legacy_source_path",
        "active_source_path",
        "legacy_exists",
        "active_exists",
        "legacy_size_bytes",
        "active_size_bytes",
        "legacy_sha256",
        "active_sha256",
        "byte_hash_match",
        "status",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "2023 draw PDF source parity complete: "
        f"{summary['byte_match_count']}/{summary['expected_file_count']} PDFs byte-match; "
        f"normalized source label status {summary['normalized_draw_truth_source_summary']['source_label_status']}."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
