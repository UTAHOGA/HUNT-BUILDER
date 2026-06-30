"""Anchor 2023 moose draw PDFs used for 2024 modeling.

This audit imports/validates source PDFs only. It extracts hunt-code evidence
from the PDF text, compares those codes to existing 2023-for-2024 draw CSV
rows, and links the same codes to the existing harvest-vs-draw comparison.
It does not rewrite normalized draw truth or promote permit values.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
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

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PDF_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds"))
ACTIVE_PDF_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "pdf" / "draw_odds"
ACTIVE_CSV_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "csv"
STANDARD_DRAW_CSV = ACTIVE_CSV_DIR / "draw_results_2023_for_2024_long.csv"
COMBINED_DRAW_CSV = ACTIVE_CSV_DIR / "draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv"
HARVEST_DRAW_COMPARISON = ROOT / "processed_data" / "complete_2023_harvest_vs_draw_comparison.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
SOURCE_AUDIT_CSV = VALIDATION_DIR / "draw_2023_moose_pdf_sources.csv"
CODE_AUDIT_CSV = VALIDATION_DIR / "draw_2023_moose_pdf_hunt_codes.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2023_moose_pdf_sources_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2023_moose_pdf_sources.md"

PDF_SOURCES = [
    {
        "source_file": "bull moose.pdf",
        "species": "Moose",
        "sex_type": "Male Only",
        "draw_family": "bull_moose_bonus",
        "expected_code_prefix": "MB",
        "expected_csv": "draw_results_2023_for_2024_long.csv",
        "expected_csv_source_label": "23_bg-odds.pdf",
    },
    {
        "source_file": "antlerless moose.pdf",
        "species": "Moose",
        "sex_type": "Antlerless",
        "draw_family": "antlerless_moose_bonus",
        "expected_code_prefix": "MA",
        "expected_csv": "draw_results_2023_for_2024_UPLOADED_COMBINED_long.csv",
        "expected_csv_source_label": "2023 Antlerless big game draw results.pdf",
    },
]


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pdf_text_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def code_page_rows(source: dict[str, str]) -> list[dict[str, str]]:
    active_path = ACTIVE_PDF_DIR / source["source_file"]
    pages = pdf_text_pages(active_path)
    pattern = re.compile(rf"\b{source['expected_code_prefix']}\d{{4}}\b")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, text in enumerate(pages, start=1):
        for code in pattern.findall(text):
            if code in seen:
                continue
            seen.add(code)
            title = ""
            for line in text.splitlines():
                cleaned = norm(line)
                if code in cleaned or cleaned.lower().startswith(("hunt:", "antlerless moose")):
                    title = cleaned
                    break
            output.append(
                {
                    "source_file": source["source_file"],
                    "draw_family": source["draw_family"],
                    "hunt_code": code,
                    "pdf_page": str(index),
                    "species": source["species"],
                    "sex_type": source["sex_type"],
                    "pdf_title_evidence": title,
                }
            )
    return sorted(output, key=lambda row: row["hunt_code"])


def rows_for_codes(rows: list[dict[str, str]], codes: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if norm(row.get("hunt_code")) in codes]


def comparison_by_code() -> dict[str, dict[str, str]]:
    return {
        norm(row.get("hunt_code")): row
        for row in read_rows(HARVEST_DRAW_COMPARISON)
        if norm(row.get("hunt_code"))
    }


def source_summary(
    source: dict[str, str],
    codes: set[str],
    standard_rows: list[dict[str, str]],
    combined_rows: list[dict[str, str]],
    comparison: dict[str, dict[str, str]],
) -> dict[str, str]:
    legacy_path = LEGACY_PDF_DIR / source["source_file"]
    active_path = ACTIVE_PDF_DIR / source["source_file"]
    reader = PdfReader(str(active_path))
    standard_matches = rows_for_codes(standard_rows, codes)
    combined_matches = rows_for_codes(combined_rows, codes)
    comparison_matches = [comparison[code] for code in sorted(codes) if code in comparison]
    expected_rows = standard_matches if source["expected_csv"] == STANDARD_DRAW_CSV.name else combined_matches
    expected_source_counts = Counter(norm(row.get("source_file")) for row in expected_rows)
    return {
        "source_file": source["source_file"],
        "draw_family": source["draw_family"],
        "species": source["species"],
        "sex_type": source["sex_type"],
        "legacy_pdf_path": str(legacy_path),
        "active_pdf_path": str(active_path.relative_to(ROOT)),
        "legacy_exists": "YES" if legacy_path.exists() else "NO",
        "active_exists": "YES" if active_path.exists() else "NO",
        "legacy_sha256": sha256(legacy_path),
        "active_sha256": sha256(active_path),
        "legacy_active_byte_match": "YES" if sha256(legacy_path) == sha256(active_path) else "NO",
        "pdf_page_count": str(len(reader.pages)),
        "pdf_unique_hunt_codes": str(len(codes)),
        "standard_csv_rows_matching_codes": str(len(standard_matches)),
        "standard_csv_unique_codes_matching": str(len({norm(row.get("hunt_code")) for row in standard_matches})),
        "combined_csv_rows_matching_codes": str(len(combined_matches)),
        "combined_csv_unique_codes_matching": str(len({norm(row.get("hunt_code")) for row in combined_matches})),
        "expected_csv": source["expected_csv"],
        "expected_csv_source_label": source["expected_csv_source_label"],
        "expected_csv_rows_matching_codes": str(len(expected_rows)),
        "expected_csv_unique_codes_matching": str(len({norm(row.get("hunt_code")) for row in expected_rows})),
        "expected_csv_source_label_counts_json": json.dumps(dict(sorted(expected_source_counts.items())), sort_keys=True),
        "comparison_codes_matched": str(len(comparison_matches)),
        "comparison_bucket_counts_json": json.dumps(dict(sorted(Counter(norm(row.get("comparison_bucket")) for row in comparison_matches).items())), sort_keys=True),
        "active_database_2026_counts_json": json.dumps(dict(sorted(Counter(norm(row.get("in_active_database_2026")) for row in comparison_matches).items())), sort_keys=True),
        "missing_from_expected_csv_codes": "|".join(sorted(codes - {norm(row.get("hunt_code")) for row in expected_rows})),
        "missing_from_comparison_codes": "|".join(sorted(codes - set(comparison))),
        "status": "PASS"
        if (
            legacy_path.exists()
            and active_path.exists()
            and sha256(legacy_path) == sha256(active_path)
            and len(codes) > 0
            and len({norm(row.get("hunt_code")) for row in expected_rows}) == len(codes)
            and len(comparison_matches) == len(codes)
        )
        else "REVIEW",
    }


def code_audit_rows(
    code_rows: list[dict[str, str]],
    standard_rows: list[dict[str, str]],
    combined_rows: list[dict[str, str]],
    comparison: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    standard_by_code: dict[str, list[dict[str, str]]] = {}
    combined_by_code: dict[str, list[dict[str, str]]] = {}
    for row in standard_rows:
        standard_by_code.setdefault(norm(row.get("hunt_code")), []).append(row)
    for row in combined_rows:
        combined_by_code.setdefault(norm(row.get("hunt_code")), []).append(row)

    output: list[dict[str, str]] = []
    for row in code_rows:
        code = row["hunt_code"]
        standard_matches = standard_by_code.get(code, [])
        combined_matches = combined_by_code.get(code, [])
        comp = comparison.get(code, {})
        output.append(
            {
                **row,
                "standard_csv_rows": str(len(standard_matches)),
                "standard_csv_source_files": "|".join(sorted({norm(item.get("source_file")) for item in standard_matches if norm(item.get("source_file"))})),
                "combined_csv_rows": str(len(combined_matches)),
                "combined_csv_source_files": "|".join(sorted({norm(item.get("source_file")) for item in combined_matches if norm(item.get("source_file"))})),
                "comparison_bucket": norm(comp.get("comparison_bucket")),
                "in_active_database_2026": norm(comp.get("in_active_database_2026")),
                "harvest_hunt_names": norm(comp.get("harvest_hunt_names")),
                "draw_hunt_names": norm(comp.get("draw_hunt_names")),
                "status": "PASS" if comp and (standard_matches or combined_matches) else "REVIEW",
            }
        )
    return sorted(output, key=lambda item: (item["source_file"], item["hunt_code"]))


def build_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# 2023 Moose Draw PDF Sources For 2024 Modeling",
        "",
        "Anchors standalone bull and antlerless moose draw-result PDFs from the legacy source folder into active source evidence.",
        "",
        "## Source Result",
        "",
        f"- Source PDFs checked: {summary['source_pdf_count']}",
        f"- Byte-identical active copies: {summary['byte_match_count']}",
        f"- Total PDF hunt codes: {summary['total_pdf_hunt_codes']}",
        f"- Codes matched to expected 2023-for-2024 draw CSV rows: {summary['codes_matched_to_expected_csv']}",
        f"- Codes matched to harvest/draw comparison: {summary['codes_matched_to_harvest_draw_comparison']}",
        "",
        "## Files",
        "",
    ]
    for source in summary["source_summaries"]:
        lines.extend(
            [
                f"### {source['source_file']}",
                f"- Pages: {source['pdf_page_count']}",
                f"- Hunt codes: {source['pdf_unique_hunt_codes']}",
                f"- Expected CSV: {source['expected_csv']}",
                f"- Expected CSV rows/codes matched: {source['expected_csv_rows_matching_codes']} / {source['expected_csv_unique_codes_matching']}",
                f"- Harvest/draw comparison buckets: {source['comparison_bucket_counts_json']}",
                f"- Current 2026 active flags: {source['active_database_2026_counts_json']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "- Bull moose rows are already represented in the standard big-game extraction under `23_bg-odds.pdf`.",
            "- Antlerless moose rows are represented in the uploaded combined draw extraction under `2023 Antlerless big game draw results.pdf`.",
            "- The two standalone PDFs are now active raw source evidence and cross-checked by hunt code.",
            "- This step does not rewrite normalized draw truth, harvest truth, permit numbers, runtime files, or website feeds.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    standard_rows = read_rows(STANDARD_DRAW_CSV)
    combined_rows = read_rows(COMBINED_DRAW_CSV)
    comparison = comparison_by_code()
    all_code_rows: list[dict[str, str]] = []
    source_summaries: list[dict[str, str]] = []
    for source in PDF_SOURCES:
        code_rows = code_page_rows(source)
        all_code_rows.extend(code_rows)
        codes = {row["hunt_code"] for row in code_rows}
        source_summaries.append(source_summary(source, codes, standard_rows, combined_rows, comparison))

    detailed_code_rows = code_audit_rows(all_code_rows, standard_rows, combined_rows, comparison)
    total_codes = len({row["hunt_code"] for row in all_code_rows})
    codes_matched_to_expected_csv = sum(int(row["expected_csv_unique_codes_matching"]) for row in source_summaries)
    codes_matched_to_comparison = sum(int(row["comparison_codes_matched"]) for row in source_summaries)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_moose_draw_pdf_sources_for_2024_modeling",
        "source_draw_result_year": 2023,
        "model_target_year": 2024,
        "source_pdf_count": len(PDF_SOURCES),
        "byte_match_count": sum(1 for row in source_summaries if row["legacy_active_byte_match"] == "YES"),
        "review_source_count": sum(1 for row in source_summaries if row["status"] != "PASS"),
        "total_pdf_hunt_codes": total_codes,
        "codes_matched_to_expected_csv": codes_matched_to_expected_csv,
        "codes_matched_to_harvest_draw_comparison": codes_matched_to_comparison,
        "source_summaries": source_summaries,
        "status": "PASS"
        if (
            len(PDF_SOURCES) == 2
            and sum(1 for row in source_summaries if row["status"] == "PASS") == 2
            and total_codes == 33
            and codes_matched_to_expected_csv == 33
            and codes_matched_to_comparison == 33
        )
        else "REVIEW",
    }

    source_fields = [
        "source_file",
        "draw_family",
        "species",
        "sex_type",
        "legacy_pdf_path",
        "active_pdf_path",
        "legacy_exists",
        "active_exists",
        "legacy_sha256",
        "active_sha256",
        "legacy_active_byte_match",
        "pdf_page_count",
        "pdf_unique_hunt_codes",
        "standard_csv_rows_matching_codes",
        "standard_csv_unique_codes_matching",
        "combined_csv_rows_matching_codes",
        "combined_csv_unique_codes_matching",
        "expected_csv",
        "expected_csv_source_label",
        "expected_csv_rows_matching_codes",
        "expected_csv_unique_codes_matching",
        "expected_csv_source_label_counts_json",
        "comparison_codes_matched",
        "comparison_bucket_counts_json",
        "active_database_2026_counts_json",
        "missing_from_expected_csv_codes",
        "missing_from_comparison_codes",
        "status",
    ]
    code_fields = [
        "source_file",
        "draw_family",
        "hunt_code",
        "pdf_page",
        "species",
        "sex_type",
        "pdf_title_evidence",
        "standard_csv_rows",
        "standard_csv_source_files",
        "combined_csv_rows",
        "combined_csv_source_files",
        "comparison_bucket",
        "in_active_database_2026",
        "harvest_hunt_names",
        "draw_hunt_names",
        "status",
    ]
    write_rows(SOURCE_AUDIT_CSV, source_summaries, source_fields)
    write_rows(CODE_AUDIT_CSV, detailed_code_rows, code_fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
