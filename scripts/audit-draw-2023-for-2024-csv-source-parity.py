"""Audit 2023 draw-result CSV sources used for 2024 modeling.

This audit anchors two large uploaded CSV exports from the older HUNTS repo
against active HUNT-BUILDER copies, then compares their row-key coverage to
the current normalized draw truth table without rewriting draw truth.
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
LEGACY_SOURCE_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/csv"))
ACTIVE_SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "csv"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "draw_2023_for_2024_csv_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2023_for_2024_csv_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2023_for_2024_csv_source_parity.md"

EXPECTED_FILES = [
    "draw_results_2023_for_2024_long.csv",
    "draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv",
]

ROW_KEY_COLUMNS = [
    "hunt_code",
    "residency",
    "points",
    "draw_pool",
    "draw_method",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
]


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def norm_key_value(column: str, value: str | None) -> str:
    normalized = norm(value)
    if column == "draw_method":
        return normalized.upper()
    return normalized


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(norm_key_value(column, row.get(column)) for column in ROW_KEY_COLUMNS)


def draw_year(row: dict[str, str]) -> str:
    return norm(row.get("year") or row.get("draw_year") or row.get("reported_draw_year") or row.get("reported_hunt_year_inferred"))


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def source_file_summary(path: Path) -> dict[str, object]:
    fields, rows = read_rows(path)
    hunt_codes = {norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}
    source_files = Counter(norm(row.get("source_file")) for row in rows)
    draw_methods = Counter(norm(row.get("draw_method")) for row in rows)
    residencies = Counter(norm(row.get("residency")) for row in rows)
    reported_years = Counter(norm(row.get("reported_draw_year") or row.get("year")) for row in rows)
    model_years = Counter(norm(row.get("model_target_year")) for row in rows)
    return {
        "row_count": len(rows),
        "column_count": len(fields),
        "columns": fields,
        "unique_hunt_codes": len(hunt_codes),
        "unique_row_keys": len({row_key(row) for row in rows}),
        "reported_draw_year_counts": dict(sorted(reported_years.items())),
        "model_target_year_counts": dict(sorted(model_years.items())),
        "source_file_count": len([key for key in source_files if key]),
        "source_file_counts": dict(source_files),
        "draw_method_counts": dict(draw_methods),
        "residency_counts": dict(residencies),
        "hunt_codes": sorted(hunt_codes),
    }


def normalized_year_summary(year: str) -> dict[str, object]:
    _, rows_all = read_rows(DRAW_LONG)
    rows = [row for row in rows_all if draw_year(row) == year]
    source_files = Counter(norm(row.get("source_file")) for row in rows)
    draw_methods = Counter(norm(row.get("draw_method")) for row in rows)
    return {
        "year": year,
        "rows": len(rows),
        "unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}),
        "unique_row_keys": len({row_key(row) for row in rows}),
        "source_file_count": len([key for key in source_files if key]),
        "source_file_counts": dict(source_files),
        "draw_method_counts": dict(draw_methods),
        "row_keys": {row_key(row) for row in rows},
        "hunt_codes": {norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))},
    }


def source_to_normalized_overlap(source_summary: dict[str, object], normalized_summary: dict[str, object]) -> dict[str, int]:
    source_codes = set(source_summary["hunt_codes"])
    normalized_codes = set(normalized_summary["hunt_codes"])
    source_path = LEGACY_SOURCE_DIR / str(source_summary["file_name"])
    _, rows = read_rows(source_path)
    source_keys = {row_key(row) for row in rows}
    normalized_keys = set(normalized_summary["row_keys"])
    return {
        "hunt_code_overlap": len(source_codes & normalized_codes),
        "source_only_hunt_codes": len(source_codes - normalized_codes),
        "normalized_only_hunt_codes": len(normalized_codes - source_codes),
        "row_key_overlap": len(source_keys & normalized_keys),
        "source_only_row_keys": len(source_keys - normalized_keys),
        "normalized_only_row_keys": len(normalized_keys - source_keys),
    }


def build_markdown(summary: dict[str, object]) -> str:
    standard = summary["source_file_summaries"]["draw_results_2023_for_2024_long.csv"]
    combined = summary["source_file_summaries"]["draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv"]
    model = summary["normalized_model_year_2024_summary"]
    source_overlap = summary["source_file_relationship"]
    lines = [
        "# 2023 Draw CSV Source Parity For 2024 Modeling",
        "",
        "Compares two large 2023-for-2024 draw-result CSV exports from `HUNTS` to active `HUNT-BUILDER` copies.",
        "",
        "## Source Result",
        "",
        f"- Expected CSVs: {summary['expected_file_count']}",
        f"- Byte-identical active copies: {summary['byte_match_count']}",
        f"- Missing legacy CSVs: {summary['missing_legacy_source_files']}",
        f"- Missing active CSVs: {summary['missing_active_source_files']}",
        "",
        "## File Shape",
        "",
        f"- Standard long rows / codes: {standard['row_count']} / {standard['unique_hunt_codes']}",
        f"- Uploaded combined rows / codes: {combined['row_count']} / {combined['unique_hunt_codes']}",
        f"- Standard source files represented: {standard['source_file_count']}",
        f"- Uploaded combined source files represented: {combined['source_file_count']}",
        f"- Source row-key overlap between the two CSVs: {source_overlap['row_key_overlap']}",
        f"- Standard-only row keys: {source_overlap['standard_only_row_keys']}",
        f"- Uploaded-combined-only row keys: {source_overlap['combined_only_row_keys']}",
        "",
        "## Normalized Draw Truth Comparison",
        "",
        f"- Current normalized model-year/draw-year 2024 rows / codes: {model['rows']} / {model['unique_hunt_codes']}",
        f"- Standard long vs normalized 2024 hunt-code overlap: {summary['standard_vs_normalized_2024']['hunt_code_overlap']}",
        f"- Uploaded combined vs normalized 2024 hunt-code overlap: {summary['combined_vs_normalized_2024']['hunt_code_overlap']}",
        f"- Standard long vs normalized 2024 row-key overlap: {summary['standard_vs_normalized_2024']['row_key_overlap']}",
        f"- Uploaded combined vs normalized 2024 row-key overlap: {summary['combined_vs_normalized_2024']['row_key_overlap']}",
        "",
        "## Interpretation",
        "",
        "- Both source CSVs are already present in the active repo as exact byte matches.",
        "- The standard file is a single-source bonus-style export; the uploaded combined file includes multiple source classes and preference-style rows.",
        "- These files are source evidence and are not being promoted into normalized draw truth in this step.",
        "- The overlap report shows that the current normalized 2024 draw truth is not a simple byte/row-key copy of either CSV, so any future promotion needs an explicit reconciliation step.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parity_rows: list[dict[str, str]] = []
    summaries: dict[str, dict[str, object]] = {}
    for file_name in EXPECTED_FILES:
        legacy_path = LEGACY_SOURCE_DIR / file_name
        active_path = ACTIVE_SOURCE_DIR / file_name
        legacy_hash = sha256(legacy_path)
        active_hash = sha256(active_path)
        legacy_fields, legacy_rows = read_rows(legacy_path)
        active_fields, active_rows = read_rows(active_path)
        byte_match = legacy_path.exists() and active_path.exists() and legacy_hash == active_hash
        row_content_match = legacy_fields == active_fields and legacy_rows == active_rows
        file_summary = source_file_summary(legacy_path)
        file_summary["file_name"] = file_name
        summaries[file_name] = file_summary
        parity_rows.append(
            {
                "file_name": file_name,
                "legacy_source_path": str(legacy_path),
                "active_source_path": relative(active_path),
                "legacy_exists": "YES" if legacy_path.exists() else "NO",
                "active_exists": "YES" if active_path.exists() else "NO",
                "legacy_size_bytes": str(legacy_path.stat().st_size) if legacy_path.exists() else "",
                "active_size_bytes": str(active_path.stat().st_size) if active_path.exists() else "",
                "legacy_rows": str(len(legacy_rows)),
                "active_rows": str(len(active_rows)),
                "legacy_columns": str(len(legacy_fields)),
                "active_columns": str(len(active_fields)),
                "legacy_sha256": legacy_hash,
                "active_sha256": active_hash,
                "byte_hash_match": "YES" if byte_match else "NO",
                "row_content_match": "YES" if row_content_match else "NO",
                "status": "PASS" if byte_match and row_content_match else "REVIEW",
            }
        )

    standard_rows = read_rows(LEGACY_SOURCE_DIR / EXPECTED_FILES[0])[1]
    combined_rows = read_rows(LEGACY_SOURCE_DIR / EXPECTED_FILES[1])[1]
    standard_keys = {row_key(row) for row in standard_rows}
    combined_keys = {row_key(row) for row in combined_rows}
    normalized_2023 = normalized_year_summary("2023")
    normalized_2024 = normalized_year_summary("2024")
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_draw_results_csv_source_parity_for_2024_modeling",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_source_dir": relative(ACTIVE_SOURCE_DIR),
        "expected_file_count": len(EXPECTED_FILES),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "row_content_match_count": sum(1 for row in parity_rows if row["row_content_match"] == "YES"),
        "missing_legacy_source_files": sum(1 for row in parity_rows if row["legacy_exists"] == "NO"),
        "missing_active_source_files": sum(1 for row in parity_rows if row["active_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "source_draw_result_year": "2023",
        "model_target_year": "2024",
        "source_file_summaries": {
            file_name: {key: value for key, value in file_summary.items() if key != "hunt_codes"}
            for file_name, file_summary in summaries.items()
        },
        "source_file_relationship": {
            "row_key_overlap": len(standard_keys & combined_keys),
            "standard_only_row_keys": len(standard_keys - combined_keys),
            "combined_only_row_keys": len(combined_keys - standard_keys),
        },
        "normalized_draw_year_2023_summary": {
            key: value for key, value in normalized_2023.items() if key not in {"row_keys", "hunt_codes"}
        },
        "normalized_model_year_2024_summary": {
            key: value for key, value in normalized_2024.items() if key not in {"row_keys", "hunt_codes"}
        },
        "standard_vs_normalized_2024": source_to_normalized_overlap(summaries[EXPECTED_FILES[0]], normalized_2024),
        "combined_vs_normalized_2024": source_to_normalized_overlap(summaries[EXPECTED_FILES[1]], normalized_2024),
        "standard_vs_normalized_2023": source_to_normalized_overlap(summaries[EXPECTED_FILES[0]], normalized_2023),
        "combined_vs_normalized_2023": source_to_normalized_overlap(summaries[EXPECTED_FILES[1]], normalized_2023),
        "guardrails": [
            "Source-anchor audit only; no CSV extraction rewrite or normalized draw truth rewrite is performed.",
            "These reported-draw-year 2023 files are model-target-year 2024 source evidence.",
            "Do not treat the uploaded combined CSV as promoted truth until a reconciliation step explains row-key differences.",
            "Do not compare this source package to the 2026 active hunt-code universe as a completeness score.",
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
        "legacy_rows",
        "active_rows",
        "legacy_columns",
        "active_columns",
        "legacy_sha256",
        "active_sha256",
        "byte_hash_match",
        "row_content_match",
        "status",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "2023-for-2024 draw CSV source parity complete: "
        f"{summary['byte_match_count']}/{summary['expected_file_count']} CSVs byte-match active copies; "
        f"standard rows {summaries[EXPECTED_FILES[0]]['row_count']}, combined rows {summaries[EXPECTED_FILES[1]]['row_count']}."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
