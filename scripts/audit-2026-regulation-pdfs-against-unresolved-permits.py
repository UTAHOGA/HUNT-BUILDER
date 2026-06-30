#!/usr/bin/env python3
"""Search 2026 regulation PDFs for remaining unresolved current permit hunt codes."""

from __future__ import annotations

import csv
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

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
UNRESOLVED = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_crosswalk_hunts_upload_rule.csv"
OUT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
AUDIT_CSV = OUT_DIR / "regulation_2026_unresolved_code_presence_audit.csv"
SUMMARY_JSON = OUT_DIR / "regulation_2026_unresolved_code_presence_summary.json"

PDFS = [
    Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Big Game Application.pdf")),
    Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2026/pdf/regulations/antlerless_guidebook.pdf")),
    Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2026/pdf/regulations/2026 Bear Cougar Furbearer Guidebook.pdf")),
]

OUTPUT_COLUMNS = [
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "split_bucket",
    "recommended_action",
    "source_support_count",
    "hanumber_res",
    "hanumber_nr",
    "hanumber_total",
    "hunttable_res",
    "hunttable_nr",
    "hunttable_total",
    "utahdraws_res",
    "utahdraws_nr",
    "utahdraws_total",
    "database_res_reference",
    "database_nr_reference",
    "database_total_reference",
    "recommended_res",
    "recommended_nr",
    "recommended_total",
    "winner_source",
    "conflicting_sources",
    "database_alignment",
    "regulation_presence_status",
    "matched_pdf_count",
    "matched_pdfs",
    "matched_pages",
    "snippet",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def extract_pdf_pages(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return pages


def make_snippet(text: str, code: str, radius: int = 120) -> str:
    match = re.search(re.escape(code), text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def main() -> int:
    rows = read_csv(UNRESOLVED)
    pdf_pages = {path.name: extract_pdf_pages(path) for path in PDFS}

    audit_rows: list[dict[str, str]] = []
    for row in rows:
        code = row.get("hunt_code", "")
        matched_pdfs: list[str] = []
        matched_pages: list[str] = []
        snippets: list[str] = []

        if code:
            code_pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", flags=re.IGNORECASE)
            for pdf_name, pages in pdf_pages.items():
                page_hits: list[str] = []
                for idx, text in enumerate(pages, start=1):
                    if code_pattern.search(text):
                        page_hits.append(str(idx))
                        if len(snippets) < 2:
                            snippets.append(f"{pdf_name} p.{idx}: {make_snippet(text, code)}")
                if page_hits:
                    matched_pdfs.append(pdf_name)
                    matched_pages.append(f"{pdf_name}:{'|'.join(page_hits)}")

        status = "REGULATION_CODE_PRESENT" if matched_pdfs else "NOT_FOUND_IN_THESE_REGULATION_PDFS"
        notes = (
            "Code string appears in one or more 2026 regulation PDFs; use as code-presence evidence only, not permit-value truth."
            if matched_pdfs
            else "Code string was not found in the three supplied 2026 regulation PDFs."
        )
        audit_rows.append(
            {
                "hunt_code": code,
                "hunt_name": row.get("hunt_name", ""),
                "species": row.get("species", ""),
                "sex_type": row.get("sex_type", ""),
                "weapon": row.get("weapon", ""),
                "hunt_type": row.get("hunt_type", ""),
                "split_bucket": row.get("split_bucket", ""),
                "recommended_action": row.get("recommended_action", ""),
                "source_support_count": row.get("source_support_count", ""),
                "hanumber_res": row.get("hanumber_res", ""),
                "hanumber_nr": row.get("hanumber_nr", ""),
                "hanumber_total": row.get("hanumber_total", ""),
                "hunttable_res": row.get("hunttable_res", ""),
                "hunttable_nr": row.get("hunttable_nr", ""),
                "hunttable_total": row.get("hunttable_total", ""),
                "utahdraws_res": row.get("utahdraws_res", ""),
                "utahdraws_nr": row.get("utahdraws_nr", ""),
                "utahdraws_total": row.get("utahdraws_total", ""),
                "database_res_reference": row.get("database_res_reference", ""),
                "database_nr_reference": row.get("database_nr_reference", ""),
                "database_total_reference": row.get("database_total_reference", ""),
                "recommended_res": row.get("recommended_res", ""),
                "recommended_nr": row.get("recommended_nr", ""),
                "recommended_total": row.get("recommended_total", ""),
                "winner_source": row.get("winner_source", ""),
                "conflicting_sources": row.get("conflicting_sources", ""),
                "database_alignment": row.get("database_alignment", ""),
                "regulation_presence_status": status,
                "matched_pdf_count": str(len(matched_pdfs)),
                "matched_pdfs": "|".join(matched_pdfs),
                "matched_pages": "; ".join(matched_pages),
                "snippet": " || ".join(snippets),
                "notes": notes,
            }
        )

    write_csv(AUDIT_CSV, audit_rows, OUTPUT_COLUMNS)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "unresolved_input": UNRESOLVED.relative_to(ROOT).as_posix(),
        "pdfs_searched": [str(path) for path in PDFS],
        "row_counts": {
            "input_unresolved_rows": len(rows),
            "audit_rows": len(audit_rows),
            "code_present_rows": sum(1 for row in audit_rows if row["regulation_presence_status"] == "REGULATION_CODE_PRESENT"),
            "code_not_found_rows": sum(1 for row in audit_rows if row["regulation_presence_status"] != "REGULATION_CODE_PRESENT"),
        },
        "presence_by_species": {
            species: dict(Counter(row["regulation_presence_status"] for row in audit_rows if row["species"] == species))
            for species in sorted({row["species"] for row in audit_rows})
        },
        "presence_by_split_bucket": {
            bucket: dict(Counter(row["regulation_presence_status"] for row in audit_rows if row["split_bucket"] == bucket))
            for bucket in sorted({row["split_bucket"] for row in audit_rows})
        },
        "outputs": {
            "audit_csv": AUDIT_CSV.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "Regulation guidebook hits are code-presence evidence only.",
            "No DATABASE.csv values were modified.",
        ],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
