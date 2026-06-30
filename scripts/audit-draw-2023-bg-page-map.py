"""Anchor the 2023 big game draw-odds page map used for 2024 modeling.

This is a source audit only. It records the user-supplied page map for
23_bg-odds.pdf, validates the active PDF/csv extraction shape, and links the
source hunt codes to the existing 2023 harvest-vs-draw comparison.
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

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PDF = Path(
    str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/23_bg-odds.pdf")
)
ACTIVE_PDF = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "pdf" / "draw_odds" / "23_bg-odds.pdf"
SOURCE_CSV = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "csv" / "draw_results_2023_for_2024_long.csv"
HARVEST_DRAW_COMPARISON = ROOT / "processed_data" / "complete_2023_harvest_vs_draw_comparison.csv"
HARVEST_DRAW_SUMMARY = ROOT / "processed_data" / "complete_2023_harvest_vs_draw_comparison.json"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PAGE_MAP_CSV = VALIDATION_DIR / "draw_2023_bg_page_map.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2023_bg_page_map_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2023_bg_page_map.md"

USER_SUPPLIED_PAGE_MAP = [
    {
        "section_id": "USER_MASTER_SPECIES_PAGE",
        "section_label": "Master species page",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 1,
        "page_end": 1,
        "note": "User identified page 1 as the master species page.",
    },
    {
        "section_id": "USER_LIMITED_ENTRY_DEER",
        "section_label": "L.E. deer",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 2,
        "page_end": 206,
        "note": "User supplied L.E. deer page range.",
    },
    {
        "section_id": "USER_LIMITED_ENTRY_ELK",
        "section_label": "L.E. elk",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 208,
        "page_end": 365,
        "note": "User supplied L.E. elk page range.",
    },
    {
        "section_id": "USER_ANY_BULL_ELK",
        "section_label": "Any Bull Elk",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 367,
        "page_end": 434,
        "note": "User supplied Any Bull Elk page range.",
    },
    {
        "section_id": "USER_LIMITED_ENTRY_BUCK_PRONGHORN",
        "section_label": "L.E. Pronghorn Buck",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 436,
        "page_end": 567,
        "note": "User supplied L.E. Pronghorn Buck page range.",
    },
    {
        "section_id": "USER_ONCE_IN_A_LIFETIME_REMAINDER",
        "section_label": "O.I.L. remainder",
        "page_basis": "user_supplied_pdf_page",
        "page_start": 568,
        "page_end": 588,
        "note": "User identified the remaining pages as O.I.L.",
    },
]

OBSERVED_EXTRACTION_PAGE_MAP = [
    {
        "section_id": "OBSERVED_MASTER_SPECIES_PAGE",
        "section_label": "Observed master species page",
        "page_basis": "source_pdf_page",
        "page_start": 1,
        "page_end": 1,
        "note": "Physical PDF page 1 is a species summary/header page; the point-level CSV has no extracted hunt-code rows for it.",
    },
    {
        "section_id": "OBSERVED_LIMITED_ENTRY_DEER",
        "section_label": "Observed deer block",
        "page_basis": "source_pdf_page",
        "page_start": 2,
        "page_end": 191,
        "note": "Observed DB/deer rows in the current extraction.",
    },
    {
        "section_id": "OBSERVED_LIMITED_ENTRY_ELK",
        "section_label": "Observed limited-entry elk block",
        "page_basis": "source_pdf_page",
        "page_start": 192,
        "page_end": 333,
        "note": "Observed EB limited-entry elk rows in the current extraction.",
    },
    {
        "section_id": "OBSERVED_ANY_BULL_ELK_CWMU",
        "section_label": "Observed any bull/CWMU elk block",
        "page_basis": "source_pdf_page",
        "page_start": 334,
        "page_end": 403,
        "note": "Observed EB CWMU/any-bull-style elk rows in the current extraction.",
    },
    {
        "section_id": "OBSERVED_LIMITED_ENTRY_BUCK_PRONGHORN",
        "section_label": "Observed buck pronghorn block",
        "page_basis": "source_pdf_page",
        "page_start": 404,
        "page_end": 490,
        "note": "Observed PB buck pronghorn rows in the current extraction.",
    },
    {
        "section_id": "OBSERVED_ONCE_IN_A_LIFETIME",
        "section_label": "Observed O.I.L. block",
        "page_basis": "source_pdf_page",
        "page_start": 491,
        "page_end": 588,
        "note": "Observed BI/DS/GO/MB/RS O.I.L. rows in the current extraction.",
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


def page_value(row: dict[str, str], basis: str) -> int | None:
    if basis == "source_pdf_page" or basis == "user_supplied_pdf_page":
        raw = row.get("source_pdf_page")
    elif basis == "source_report_page":
        raw = row.get("source_report_page")
    else:
        raw = ""
    try:
        return int(str(raw or "").strip())
    except ValueError:
        return None


def source_rows() -> list[dict[str, str]]:
    rows = [
        row
        for row in read_rows(SOURCE_CSV)
        if norm(row.get("source_file")) == "23_bg-odds.pdf"
    ]
    return rows


def first_last_hunt_codes(rows: list[dict[str, str]], basis: str) -> tuple[str, str]:
    ordered = sorted(
        rows,
        key=lambda row: (
            page_value(row, basis) or 0,
            norm(row.get("hunt_code")),
            norm(row.get("points")),
            norm(row.get("residency")),
        ),
    )
    codes = [norm(row.get("hunt_code")) for row in ordered if norm(row.get("hunt_code"))]
    return (codes[0], codes[-1]) if codes else ("", "")


def summarize_section(section: dict[str, object], rows: list[dict[str, str]], map_type: str) -> dict[str, str]:
    basis = str(section["page_basis"])
    start = int(section["page_start"])
    end = int(section["page_end"])
    section_rows = [
        row
        for row in rows
        if (page := page_value(row, basis)) is not None and start <= page <= end
    ]
    species_counts = Counter(norm(row.get("species")) for row in section_rows)
    hunt_type_counts = Counter(norm(row.get("hunt_type")) for row in section_rows)
    hunt_codes = {norm(row.get("hunt_code")) for row in section_rows if norm(row.get("hunt_code"))}
    pdf_pages = [page_value(row, "source_pdf_page") for row in section_rows]
    report_pages = [page_value(row, "source_report_page") for row in section_rows]
    pdf_pages = [page for page in pdf_pages if page is not None]
    report_pages = [page for page in report_pages if page is not None]
    first_code, last_code = first_last_hunt_codes(section_rows, basis)
    mixed_species = len([key for key in species_counts if key]) > 1
    status = "OBSERVED_CLEAN" if not mixed_species else "MIXED_EXTRACTION_ROWS"
    if not section_rows and "MASTER" in str(section["section_id"]):
        status = "NO_HUNT_CODE_ROWS_EXPECTED"
    return {
        "page_map_type": map_type,
        "section_id": str(section["section_id"]),
        "section_label": str(section["section_label"]),
        "page_basis": basis,
        "page_start": str(start),
        "page_end": str(end),
        "extracted_rows": str(len(section_rows)),
        "unique_hunt_codes": str(len(hunt_codes)),
        "first_hunt_code": first_code,
        "last_hunt_code": last_code,
        "source_pdf_page_min": str(min(pdf_pages)) if pdf_pages else "",
        "source_pdf_page_max": str(max(pdf_pages)) if pdf_pages else "",
        "source_report_page_min": str(min(report_pages)) if report_pages else "",
        "source_report_page_max": str(max(report_pages)) if report_pages else "",
        "species_counts_json": json.dumps(dict(sorted(species_counts.items())), sort_keys=True),
        "hunt_type_counts_json": json.dumps(dict(sorted(hunt_type_counts.items())), sort_keys=True),
        "status": status,
        "note": str(section["note"]),
    }


def harvest_draw_linkage(source_hunt_codes: set[str]) -> dict[str, object]:
    comparison_rows = {
        norm(row.get("hunt_code")): row
        for row in read_rows(HARVEST_DRAW_COMPARISON)
        if norm(row.get("hunt_code"))
    }
    matched_codes = source_hunt_codes & set(comparison_rows)
    bucket_counts = Counter(norm(comparison_rows[code].get("comparison_bucket")) for code in matched_codes)
    active_counts = Counter(norm(comparison_rows[code].get("in_active_database_2026")) for code in matched_codes)
    return {
        "comparison_file": str(HARVEST_DRAW_COMPARISON.relative_to(ROOT)),
        "comparison_summary_file": str(HARVEST_DRAW_SUMMARY.relative_to(ROOT)),
        "source_hunt_codes": len(source_hunt_codes),
        "matched_comparison_hunt_codes": len(matched_codes),
        "missing_from_comparison_hunt_codes": sorted(source_hunt_codes - set(comparison_rows)),
        "comparison_bucket_counts": dict(sorted(bucket_counts.items())),
        "active_database_2026_counts": dict(sorted(active_counts.items())),
        "draw_only_hunt_codes": sorted(
            code
            for code in matched_codes
            if norm(comparison_rows[code].get("comparison_bucket")) == "draw_only"
        ),
        "not_active_database_2026_hunt_codes": sorted(
            code
            for code in matched_codes
            if norm(comparison_rows[code].get("in_active_database_2026")) != "YES"
        ),
    }


def build_markdown(summary: dict[str, object], section_rows: list[dict[str, str]]) -> str:
    observed_rows = [row for row in section_rows if row["page_map_type"] == "observed_extraction_pdf_page_map"]
    observed_table = [
        "| Section | PDF Pages | Rows | Codes | Species | Status |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in observed_rows:
        observed_table.append(
            "| {label} | {start}-{end} | {rows} | {codes} | {species} | {status} |".format(
                label=row["section_label"],
                start=row["page_start"],
                end=row["page_end"],
                rows=row["extracted_rows"],
                codes=row["unique_hunt_codes"],
                species=row["species_counts_json"],
                status=row["status"],
            )
        )
    linkage = summary["harvest_draw_comparison_linkage"]
    lines = [
        "# 2023 Big Game Draw Odds Page Map",
        "",
        "Anchors `23_bg-odds.pdf` for 2024 modeling and 2023 harvest-result comparison.",
        "",
        "## Source Result",
        "",
        f"- PDF page count: {summary['pdf_page_count']}",
        f"- Legacy/active PDF byte match: {summary['legacy_active_pdf_byte_match']}",
        f"- Extracted rows from `23_bg-odds.pdf`: {summary['source_csv_row_count']}",
        f"- Unique hunt codes in this source: {summary['source_csv_unique_hunt_codes']}",
        f"- Extracted PDF page coverage: {summary['source_pdf_page_min']}-{summary['source_pdf_page_max']}",
        "",
        "## Observed Extraction Map",
        "",
        *observed_table,
        "",
        "## Harvest Comparison Linkage",
        "",
        f"- Source hunt codes matched to comparison: {linkage['matched_comparison_hunt_codes']} / {linkage['source_hunt_codes']}",
        f"- Comparison buckets: {linkage['comparison_bucket_counts']}",
        f"- Current 2026 active-database flags: {linkage['active_database_2026_counts']}",
        f"- Draw-only source codes: {', '.join(linkage['draw_only_hunt_codes']) or 'none'}",
        "",
        "## Interpretation",
        "",
        "- The user-supplied page map is preserved in the CSV audit as source context.",
        "- The observed physical PDF extraction map is the safer machine-validation layer because every extracted row carries `source_pdf_page`.",
        "- This step does not rewrite draw truth, harvest truth, permit numbers, runtime files, or website feeds.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    rows = source_rows()
    pdf_reader = PdfReader(str(ACTIVE_PDF))
    pdf_page_count = len(pdf_reader.pages)
    source_hunt_codes = {norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}
    pdf_pages = [page_value(row, "source_pdf_page") for row in rows]
    report_pages = [page_value(row, "source_report_page") for row in rows]
    pdf_pages = [page for page in pdf_pages if page is not None]
    report_pages = [page for page in report_pages if page is not None]

    section_rows = [
        summarize_section(section, rows, "user_supplied_pdf_page_map")
        for section in USER_SUPPLIED_PAGE_MAP
    ]
    section_rows.extend(
        summarize_section(section, rows, "observed_extraction_pdf_page_map")
        for section in OBSERVED_EXTRACTION_PAGE_MAP
    )

    user_assigned_rows = sum(
        int(row["extracted_rows"])
        for row in section_rows
        if row["page_map_type"] == "user_supplied_pdf_page_map"
    )
    observed_assigned_rows = sum(
        int(row["extracted_rows"])
        for row in section_rows
        if row["page_map_type"] == "observed_extraction_pdf_page_map"
    )
    comparison_summary = json.loads(HARVEST_DRAW_SUMMARY.read_text(encoding="utf-8"))["summary"]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_big_game_draw_odds_page_map_for_2024_modeling",
        "source_file": "23_bg-odds.pdf",
        "legacy_pdf_path": str(LEGACY_PDF),
        "active_pdf_path": str(ACTIVE_PDF.relative_to(ROOT)),
        "legacy_pdf_sha256": sha256(LEGACY_PDF),
        "active_pdf_sha256": sha256(ACTIVE_PDF),
        "legacy_active_pdf_byte_match": sha256(LEGACY_PDF) == sha256(ACTIVE_PDF),
        "pdf_page_count": pdf_page_count,
        "source_csv": str(SOURCE_CSV.relative_to(ROOT)),
        "source_csv_row_count": len(rows),
        "source_csv_unique_hunt_codes": len(source_hunt_codes),
        "source_pdf_page_min": min(pdf_pages),
        "source_pdf_page_max": max(pdf_pages),
        "source_report_page_min": min(report_pages),
        "source_report_page_max": max(report_pages),
        "user_supplied_page_map_rows_assigned": user_assigned_rows,
        "observed_extraction_page_map_rows_assigned": observed_assigned_rows,
        "unassigned_rows_by_user_supplied_map": len(rows) - user_assigned_rows,
        "unassigned_rows_by_observed_map": len(rows) - observed_assigned_rows,
        "source_draw_result_year": 2023,
        "model_target_year": 2024,
        "harvest_draw_comparison_summary": {
            "complete_harvest_hunt_codes": comparison_summary["complete_harvest_hunt_codes"],
            "draw_odds_hunt_codes": comparison_summary["draw_odds_hunt_codes"],
            "both_harvest_and_draw": comparison_summary["both_harvest_and_draw"],
            "harvest_only": comparison_summary["harvest_only"],
            "draw_only": comparison_summary["draw_only"],
        },
        "harvest_draw_comparison_linkage": harvest_draw_linkage(source_hunt_codes),
        "status": "PASS"
        if (
            pdf_page_count == 588
            and len(rows) == 35960
            and len(source_hunt_codes) == 580
            and observed_assigned_rows == len(rows)
            and sha256(LEGACY_PDF) == sha256(ACTIVE_PDF)
        )
        else "REVIEW",
    }

    fields = [
        "page_map_type",
        "section_id",
        "section_label",
        "page_basis",
        "page_start",
        "page_end",
        "extracted_rows",
        "unique_hunt_codes",
        "first_hunt_code",
        "last_hunt_code",
        "source_pdf_page_min",
        "source_pdf_page_max",
        "source_report_page_min",
        "source_report_page_max",
        "species_counts_json",
        "hunt_type_counts_json",
        "status",
        "note",
    ]
    write_rows(PAGE_MAP_CSV, section_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_markdown(summary, section_rows), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
