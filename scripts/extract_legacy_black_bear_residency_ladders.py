#!/usr/bin/env python3
"""Extract the resident/nonresident point ladders from 2018-2022 bear PDFs.

The retained official PDFs have separate resident and nonresident tables, while
the legacy canonical rows retain combined point counts.  This script creates a
separate, hash-linked validation source and proves each reconstructed page
against the combined canonical before any canonical rewrite is considered.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    2018: ROOT / "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/black_bear/18_drawing_odds.pdf",
    2019: ROOT / "pipeline/RAW/hunt_unit_database/2019/pdf/draw_odds/official_dwr_archive/black_bear/19_drawing_odds.pdf",
    2020: ROOT / "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/black_bear/20_drawing_odds.pdf",
    2021: ROOT / "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/official_dwr_archive/black_bear/21_drawing_odds.pdf",
    2022: ROOT / "pipeline/RAW/hunt_unit_database/2022/pdf/draw_odds/official_dwr_archive/black_bear/22_drawing_odds.pdf",
}
CANONICAL_DIR = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly"
OUTPUT = ROOT / "data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders.csv"
SUMMARY = ROOT / "data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders_summary.json"

FIELDS = [
    "reported_draw_year",
    "model_target_year",
    "hunt_code",
    "hunt_name",
    "residency",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "source_file",
    "source_sha256",
    "page_number",
    "source_classification",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def int_text(value: object) -> int:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else 0


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def extract_pdf(reported_year: int, source: Path) -> list[dict[str, object]]:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("pdfplumber is required to extract official bear draw PDFs.") from exc

    rows: list[dict[str, object]] = []
    source_hash = sha256(source)
    with pdfplumber.open(source) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            hunt = re.search(r"Hunt:\s*(BR\d{4})\s+(.+?)\nResident Applicants", text, re.S)
            if not hunt:
                continue
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Expected one point table on {relative(source)} page {page_number}; found {len(tables)}")
            raw_name = " ".join(hunt.group(2).split())
            hunt_name = re.sub(r"\s+-\s+.*$", "", raw_name).strip()
            subtype = "BEAR_PURSUIT_BONUS_DRAW" if "pursuit" in raw_name.lower() else "TRUE_BEAR_BONUS_DRAW"
            for cells in tables[0]:
                if len(cells) < 11:
                    continue
                # The 2018-21 tables have six columns per residency lane.  In
                # 2022, PDF extraction preserves a blank column under the
                # printed "#" header for the resident lane, moving the
                # nonresident lane from column 6 to 7.  Select positions from
                # the observed table shape; do not infer a split from totals.
                if len(cells) >= 13 and str(cells[7] or "").strip().isdigit():
                    resident = (0, 2, 3, 4, 5)
                    nonresident = (7, 8, 9, 10, 11)
                else:
                    resident = (0, 1, 2, 3, 4)
                    nonresident = (6, 7, 8, 9, 10)
                left_point = str(cells[resident[0]] or "").strip()
                right_point = str(cells[nonresident[0]] or "").strip()
                if not left_point.isdigit() or not right_point.isdigit() or left_point != right_point:
                    continue
                for residency, positions in (("Resident", resident), ("Nonresident", nonresident)):
                    rows.append(
                        {
                            "reported_draw_year": reported_year,
                            "model_target_year": reported_year + 1,
                            "hunt_code": hunt.group(1).upper(),
                            "hunt_name": hunt_name,
                            "residency": residency,
                            "points": int_text(cells[positions[0]]),
                            "eligible_applicants": int_text(cells[positions[1]]),
                            "bonus_permits": int_text(cells[positions[2]]),
                            "regular_permits": int_text(cells[positions[3]]),
                            "total_permits": int_text(cells[positions[4]]),
                            "source_file": relative(source),
                            "source_sha256": source_hash,
                            "page_number": page_number,
                            "source_classification": subtype,
                        }
                    )
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_rows(reported_year: int) -> list[dict[str, str]]:
    matches = sorted(CANONICAL_DIR.glob(f"draw_results_{reported_year}_for_{reported_year + 1}_canonical_yearly_draw_results.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one canonical for {reported_year}; found {matches}")
    return read_csv(matches[0])


def combined_keyed(rows: Iterable[dict[str, object]]) -> dict[tuple[int, str, int], dict[str, int]]:
    grouped: dict[tuple[int, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        key = (int(row["reported_draw_year"]), str(row["hunt_code"]), int(row["points"]))
        for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"):
            grouped[key][field] += int_text(row.get(field))
    return grouped


def canonical_keyed(rows: Iterable[dict[str, str]], reported_year: int) -> dict[tuple[int, str, int], dict[str, int]]:
    grouped: dict[tuple[int, str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        # Older canonical taxonomy sometimes carries the family-level species
        # label across a mixed source scope. The official BR prefix is the
        # unambiguous identity for this dedicated black-bear PDF source.
        if not str(row.get("hunt_code", "")).strip().upper().startswith("BR"):
            continue
        if str(row.get("metric_scope", "")).strip().lower() != "total":
            continue
        point_text = str(row.get("points", "")).strip()
        if not point_text.isdigit():
            continue
        key = (reported_year, str(row.get("hunt_code", "")).strip().upper(), int(point_text))
        for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"):
            grouped[key][field] += int_text(row.get(field))
    return grouped


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    extracted = [row for year, source in SOURCES.items() for row in extract_pdf(year, source)]
    if len(extracted) != len({(row["reported_draw_year"], row["hunt_code"], row["residency"], row["points"]) for row in extracted}):
        raise RuntimeError("Duplicate official bear residency/point identity found during extraction")

    reconstructed = combined_keyed(extracted)
    canonical = {
        key: value
        for year in SOURCES
        for key, value in canonical_keyed(canonical_rows(year), year).items()
    }
    missing = sorted(set(canonical) - set(reconstructed))
    extra = sorted(set(reconstructed) - set(canonical))
    mismatches = [
        {"key": key, "pdf": reconstructed[key], "canonical": canonical[key]}
        for key in sorted(set(reconstructed) & set(canonical))
        if reconstructed[key] != canonical[key]
    ]
    per_year: dict[str, dict[str, object]] = {}
    canonical_covered_years = [
        year
        for year in SOURCES
        if any(key[0] == year for key in canonical)
    ]
    for year in SOURCES:
        prefix = (year,)
        year_missing = [key for key in missing if key[:1] == prefix]
        year_extra = [key for key in extra if key[:1] == prefix]
        year_mismatches = [row for row in mismatches if row["key"][:1] == prefix]
        # If a retained PDF scope has no canonical keys yet, record the
        # source-complete scope as a canonical-freeze task.  Once promoted,
        # every year uses the same exact recombination standard.
        if year not in canonical_covered_years:
            status = "OFFICIAL_PDF_EXTRACTED_CANONICAL_BEAR_SCOPE_NOT_FROZEN"
        else:
            status = "PASS" if not year_missing and not year_extra and not year_mismatches else "FAIL"
        per_year[str(year)] = {
            "status": status,
            "reconstructed_combined_point_keys": sum(1 for key in reconstructed if key[:1] == prefix),
            "canonical_combined_point_keys": sum(1 for key in canonical if key[:1] == prefix),
            "canonical_keys_missing_from_pdf": year_missing,
            "pdf_keys_missing_from_canonical": year_extra,
            "value_mismatches": year_mismatches,
        }
    write_csv(OUTPUT, extracted)
    summary = {
        "purpose": "official_pdf_residency_ladder_reconstruction_before_canonical_promotion",
        "reported_draw_years": sorted(SOURCES),
        "source_files": {str(year): {"path": relative(path), "sha256": sha256(path)} for year, path in SOURCES.items()},
        "extracted_residency_point_rows": len(extracted),
        "distinct_hunt_codes": len({str(row["hunt_code"]) for row in extracted}),
        "reconstructed_combined_point_keys": len(reconstructed),
        "canonical_combined_point_keys": len(canonical),
        "canonical_keys_missing_from_pdf": missing,
        "pdf_keys_missing_from_canonical": extra,
        "value_mismatches": mismatches,
        "canonical_covered_years": canonical_covered_years,
        "per_year": per_year,
        "parity_status": (
            "PASS"
            if all(per_year[str(year)]["status"] == "PASS" for year in canonical_covered_years)
            else "FAIL"
        ),
        "canonical_freeze_status": "COMPLETE" if all(
            per_year[str(year)]["status"] == "PASS" for year in SOURCES
        ) else "PENDING",
        "output": relative(OUTPUT),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
