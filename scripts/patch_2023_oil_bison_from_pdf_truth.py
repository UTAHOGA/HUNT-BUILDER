#!/usr/bin/env python3
"""Patch 2023 O.I.L. bison rows from the official draw-results PDF.

The source PDF confirms hunt codes, hunt names, weapon, and the bison sex label
in each Hunt line. It does not contain season dates, so this script leaves
season blank.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2023\.pdf\2023_PERMITS=2024_MODEL__O.I.L. BISON DRAW RESULTS.pdf")
CANONICAL_2023 = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2023_for_2024_canonical_yearly_draw_results.csv"
LONG_PATH = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUDIT_DIR = ROOT / "pipeline" / "R2_OFFLOAD" / "incoming"
AUDIT_CSV = AUDIT_DIR / "patch_2023_oil_bison_from_pdf_truth_audit.csv"
SUMMARY_JSON = AUDIT_DIR / "patch_2023_oil_bison_from_pdf_truth_summary.json"


HUNT_LINE_RE = re.compile(
    r"Hunt:\s+(BI\d+)\s+Bison(?:\s+(Archery|Muzzleloader))?\s+\(([^)]+)\)\s+-\s+(.*?)\s+-\s+(.*?)\s+Page\s+(\d+)",
    re.IGNORECASE,
)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_sex(raw: str) -> str:
    value = raw.strip().lower().replace("’", "'")
    if "cow only" in value:
        return "Female Only"
    if "hunter" in value and "choice" in value:
        return "Either Sex"
    return raw.strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def extract_pdf_truth() -> dict[str, dict[str, str]]:
    truth: dict[str, dict[str, str]] = {}
    with pdfplumber.open(PDF_PATH) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                match = HUNT_LINE_RE.search(line)
                if not match:
                    continue
                code = match.group(1).upper()
                weapon_hint = clean(match.group(2))
                raw_sex = clean(match.group(3))
                hunt_name = clean(match.group(4))
                weapon = clean(match.group(5))
                truth[code] = {
                    "hunt_code": code,
                    "page": str(page_index),
                    "hunt_name_pdf": hunt_name,
                    "weapon_pdf": weapon_hint or weapon,
                    "sex_type_pdf_raw": raw_sex,
                    "sex_type_normalized": normalize_sex(raw_sex),
                    "raw_line": line.strip(),
                }
    return truth


def patch_rows(path: Path, truth: dict[str, dict[str, str]], actual_year_filter: str | None) -> tuple[int, list[dict[str, Any]]]:
    headers, rows = read_csv(path)
    required = {"hunt_code", "hunt_class", "draw_design", "sex_type"}
    missing = sorted(required - set(headers))
    if missing:
        raise RuntimeError(f"{path} missing required columns: {missing}")

    changed = 0
    audit_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        if actual_year_filter is not None and clean(row.get("actual_draw_year")) != actual_year_filter:
            continue
        code = clean(row.get("hunt_code")).upper()
        source = truth.get(code)
        if not source:
            continue
        updates: dict[str, str] = {}
        if clean(row.get("hunt_class")) == "" and clean(row.get("draw_design")) == "Max/Weighted Split":
            updates["hunt_class"] = "Max/Weighted Split"
        if clean(row.get("sex_type")) != source["sex_type_normalized"]:
            updates["sex_type"] = source["sex_type_normalized"]
        if not updates:
            continue

        before = {field: clean(row.get(field)) for field in updates}
        for field, value in updates.items():
            row[field] = value
        changed += 1
        audit_rows.append(
            {
                "target_file": str(path),
                "row_number": row_number,
                "actual_draw_year": clean(row.get("actual_draw_year") or row.get("year")),
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "pdf_hunt_name": source["hunt_name_pdf"],
                "weapon": clean(row.get("weapon")),
                "pdf_weapon": source["weapon_pdf"],
                "old_values": json.dumps(before, sort_keys=True),
                "new_values": json.dumps(updates, sort_keys=True),
                "pdf_page": source["page"],
                "pdf_raw_line": source["raw_line"],
            }
        )

    if changed:
        write_csv(path, headers, rows)
    return changed, audit_rows


def main() -> None:
    truth = extract_pdf_truth()
    if len(truth) != 17:
        raise RuntimeError(f"Expected 17 Hunt lines in source PDF, found {len(truth)}")

    canonical_changed, canonical_audit = patch_rows(CANONICAL_2023, truth, actual_year_filter=None)
    long_changed, long_audit = patch_rows(LONG_PATH, truth, actual_year_filter="2023")
    audit_rows = canonical_audit + long_audit
    write_csv(
        AUDIT_CSV,
        [
            "target_file",
            "row_number",
            "actual_draw_year",
            "hunt_code",
            "hunt_name",
            "pdf_hunt_name",
            "weapon",
            "pdf_weapon",
            "old_values",
            "new_values",
            "pdf_page",
            "pdf_raw_line",
        ],
        audit_rows,
    )
    summary = {
        "source_pdf": str(PDF_PATH),
        "source_hunt_codes": sorted(truth),
        "canonical_rows_changed": canonical_changed,
        "long_rows_changed": long_changed,
        "audit_csv": str(AUDIT_CSV),
        "note": "Season was not populated because the draw-results PDF does not contain season dates.",
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
