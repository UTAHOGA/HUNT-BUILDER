#!/usr/bin/env python3
"""Patch 2022/2023 Sportsman total applicant counts from official PDFs."""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
OUTPUTS = ROOT / "outputs"
AUDIT_DIR = ROOT / "audits" / "database_alignment" / "identity_registry"

SOURCES = {
    2022: ROOT
    / "audits"
    / "2025_canonical_finalization"
    / "fresh_live_pulls_20260621_192945"
    / "older_years_biggame_odds"
    / "2022"
    / "22-23_sportsman_odds.pdf",
    2023: ROOT
    / "audits"
    / "2025_canonical_finalization"
    / "fresh_live_pulls_20260621_192945"
    / "older_years_biggame_odds"
    / "2023"
    / "23-24_sportsman_odds.pdf",
}

SPORTSMAN_LINE_RE = re.compile(
    r"^(?P<code>[A-Z]{2}\d{4})\s+Sportsman\b.*?\s+"
    r"(?P<successful_resident>\d+)\s+"
    r"(?P<successful_nonresident>\d+)\s+"
    r"(?P<unsuccessful_resident>[\d,]+)\s+"
    r"(?P<unsuccessful_nonresident>[\d,]+)\s+"
    r"(?P<total_applications>[\d,]+)\s+"
    r"(?P<resident_quota>\d+)\s+"
    r"(?P<nonresident_quota>N/A|\d+)\s+"
    r"(?P<total_quota>\d+)\s+"
    r"(?P<resident_success>1 in [\d,]+(?:\.\d+)?)\s+"
    r"(?P<nonresident_success>N/A|1 in [\d,]+(?:\.\d+)?)$",
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def parse_int(value: str) -> int:
    return int(clean(value).replace(",", ""))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def extract_pdf_rows(path: Path) -> dict[str, dict[str, str]]:
    text_parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    rows: dict[str, dict[str, str]] = {}
    for line in "\n".join(text_parts).splitlines():
        match = SPORTSMAN_LINE_RE.match(clean(line))
        if not match:
            continue
        item = match.groupdict()
        code = clean(item["code"]).upper()
        total_applications = parse_int(item["total_applications"])
        resident_quota = parse_int(item["resident_quota"])
        nonresident_quota = 0 if clean(item["nonresident_quota"]).upper() == "N/A" else parse_int(item["nonresident_quota"])
        total_quota = parse_int(item["total_quota"])
        p_draw = resident_quota / total_applications if total_applications else 0.0
        rows[code] = {
            "resident_eligible_applicants": str(total_applications),
            "resident_bonus_permits": "0",
            "resident_regular_permits": str(resident_quota),
            "resident_total_permits": str(resident_quota),
            "resident_success_ratio": clean(item["resident_success"]),
            "resident_p_draw": f"{p_draw:.12g}",
            "resident_p_draw_percent": f"{p_draw * 100:.8g}",
            "nonresident_eligible_applicants": "0",
            "nonresident_bonus_permits": "0",
            "nonresident_regular_permits": str(nonresident_quota),
            "nonresident_total_permits": str(nonresident_quota),
            "nonresident_success_ratio": "N/A",
            "nonresident_p_draw": "",
            "nonresident_p_draw_percent": "",
            "total_eligible_applicants": str(total_applications),
            "total_permits": str(total_quota),
            "total_success_ratio": clean(item["resident_success"]),
            "total_p_draw": f"{p_draw:.12g}",
            "total_p_draw_percent": f"{p_draw * 100:.8g}",
            "success_ratio": clean(item["resident_success"]),
            "p_draw": f"{p_draw:.12g}",
            "p_draw_percent": f"{p_draw * 100:.8g}",
        }
    return rows


def row_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("year"))


def is_target_row(row: dict[str, str], year: int, code: str) -> bool:
    return (
        row_year(row) == str(year)
        and clean(row.get("hunt_code")).upper() == code
        and clean(row.get("record_type") or row.get("row_type")).lower() in {"sportsman_total", "hunt_total_draw_result"}
    )


def patch_rows(
    path: Path,
    year: int,
    values_by_code: dict[str, dict[str, str]],
    source_pdf: Path,
    write: bool,
) -> list[dict[str, str]]:
    fieldnames, rows = read_csv(path)
    changes: list[dict[str, str]] = []
    source_text = str(source_pdf.relative_to(ROOT)).replace("\\", "/")
    for row_index, row in enumerate(rows, start=2):
        code = clean(row.get("hunt_code")).upper()
        values = values_by_code.get(code)
        if not values or not is_target_row(row, year, code):
            continue
        before_blank = clean(row.get("total_eligible_applicants")) == ""
        for field, value in values.items():
            if field in fieldnames:
                old = row.get(field, "")
                if old != value:
                    changes.append(
                        {
                            "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                            "year": str(year),
                            "row_number": str(row_index),
                            "hunt_code": code,
                            "field": field,
                            "old_value": old,
                            "new_value": value,
                            "source_pdf": source_text,
                        }
                    )
                    row[field] = value
        if "source_file" in fieldnames and year == 2023:
            old = row.get("source_file", "")
            if old != source_text:
                changes.append(
                    {
                        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "year": str(year),
                        "row_number": str(row_index),
                        "hunt_code": code,
                        "field": "source_file",
                        "old_value": old,
                        "new_value": source_text,
                        "source_pdf": source_text,
                    }
                )
                row["source_file"] = source_text
        if "notes" in fieldnames and before_blank:
            note = "Sportsman applicant totals patched from official Sportsman draw odds PDF; nonresidents ineligible."
            old = clean(row.get("notes"))
            if note not in old:
                row["notes"] = f"{old} | {note}".strip(" |")
    if write and changes:
        write_csv(path, fieldnames, rows)
    return changes


def output_scorable_path(year: int) -> Path:
    return OUTPUTS / f"{year} scorable draw results.csv"


def write_audit(changes: list[dict[str, str]], summary: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    changes_path = AUDIT_DIR / "sportsman_2022_2023_applicant_patch_audit.csv"
    summary_path = AUDIT_DIR / "sportsman_2022_2023_applicant_patch_summary.json"
    fields = ["file", "year", "row_number", "hunt_code", "field", "old_value", "new_value", "source_pdf"]
    with changes_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(changes)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    values_by_year = {year: extract_pdf_rows(path) for year, path in SOURCES.items()}
    all_changes: list[dict[str, str]] = []
    for year, values_by_code in values_by_year.items():
        for path in (canonical_path(year), LONG_FILE, output_scorable_path(year)):
            if path.exists():
                all_changes.extend(patch_rows(path, year, values_by_code, SOURCES[year], write=True))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdfs": {str(year): str(path.relative_to(ROOT)).replace("\\", "/") for year, path in SOURCES.items()},
        "parsed_codes": {str(year): sorted(values.keys()) for year, values in values_by_year.items()},
        "changes": len(all_changes),
        "changed_files": sorted({change["file"] for change in all_changes}),
    }
    write_audit(all_changes, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
