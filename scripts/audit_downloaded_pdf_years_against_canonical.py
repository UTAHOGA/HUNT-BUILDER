#!/usr/bin/env python3
"""Audit downloaded official PDF draw-result packages against canonical yearly files.

This script does not mutate canonical data. It inventories the downloaded PDF
cache by actual draw year, extracts point-row draw results with the existing
PDF parser, and compares hunt-code/residency/point keys against the current
canonical yearly CSVs.
"""

from __future__ import annotations

import csv
import argparse
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRESH = ROOT / "audits" / "2025_canonical_finalization" / "fresh_live_pulls_20260621_192945"
BIGGAME = FRESH / "older_years_biggame_odds"
BEAR_COUGAR_TURKEY = FRESH / "older_years_bear_cougar_turkey_odds"
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
OUT_DIR = ROOT / "audits" / "downloaded_pdf_year_reconciliation"
EXTRACTOR = ROOT / "scripts" / "extract_draw_reality.py"
CONSERVATION_XLSX = ROOT / "data_truth" / "conservation_permit_truth" / "2025-27 Conservation Permits.xlsx"

CANONICAL_YEARS = range(2019, 2026)
SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "sportsman_total_draw_result",
    "sportsman_total",
}
REAL_HUNT_CODE_RE = re.compile(r"^[A-Z]{2}\d{4}$")


def load_extractor():
    spec = importlib.util.spec_from_file_location("extract_draw_reality", EXTRACTOR)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load extractor: {EXTRACTOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", "\n").split())


def norm_residency(value: Any) -> str:
    text = clean(value)
    low = text.lower()
    if text == "1" or low in {"resident", "res"}:
        return "Resident"
    if text == "2" or low in {"nonresident", "non-resident", "non resident", "nr", "nonres"}:
        return "Nonresident"
    return text


def norm_point(value: Any) -> str:
    text = clean(value)
    if text == "":
        return ""
    try:
        return str(int(float(text.replace(",", ""))))
    except ValueError:
        return text


def norm_int(value: Any) -> str:
    text = clean(value).replace(",", "")
    if text == "":
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def draw_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year")) or clean(row.get("year"))


def is_real_code(code: str) -> bool:
    return bool(REAL_HUNT_CODE_RE.match(clean(code).upper()))


def skip_pdf(path: Path) -> bool:
    name = path.name.lower()
    if "point-only" in name or "point_only" in name:
        return True
    if "point_summary" in name or "point-summary" in name:
        return True
    if "purchase" in name and "draw_results" not in name:
        return True
    if "harvest" in name:
        return True
    return False


def year_from_path(path: Path) -> int | None:
    for part in reversed(path.parts):
        if re.fullmatch(r"20\d{2}", part):
            return int(part)
    match = re.search(r"(20\d{2})", path.name)
    if match:
        return int(match.group(1))
    return None


def source_pdfs_for_year(year: int) -> list[Path]:
    pdfs: list[Path] = []
    biggame_dir = BIGGAME / str(year)
    if biggame_dir.exists():
        pdfs.extend(sorted(biggame_dir.glob("*.pdf")))

    for family in ("bear", "turkey", "cougar"):
        if family == "cougar" and year < 2023:
            # Tyler called this out explicitly: do not backfill cougar before 2023.
            continue
        family_dir = BEAR_COUGAR_TURKEY / family / str(year)
        if family_dir.exists():
            pdfs.extend(sorted(family_dir.glob("*.pdf")))
    return pdfs


def canonical_path(year: int) -> Path:
    return CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def key_from_pdf_row(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        norm_residency(row.get("residency")),
        norm_point(row.get("points")),
    )


def key_from_canonical_row(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        norm_residency(row.get("residency")),
        norm_point(row.get("points")),
    )


def canonical_scorable_rows(year: int) -> list[dict[str, str]]:
    path = canonical_path(year)
    if not path.exists():
        return []
    _fields, rows = read_csv(path)
    out = []
    for row in rows:
        if draw_year(row).replace(".0", "") != str(year):
            continue
        if clean(row.get("record_type")).lower() not in SCORABLE_RECORD_TYPES:
            continue
        if not is_real_code(clean(row.get("hunt_code"))):
            continue
        out.append(row)
    return out


def conservation_codes() -> set[str]:
    if not CONSERVATION_XLSX.exists():
        return set()
    try:
        import openpyxl
    except ImportError:
        return set()

    codes: set[str] = set()
    workbook = openpyxl.load_workbook(CONSERVATION_XLSX, read_only=True, data_only=True)
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            if not row:
                continue
            for value in row[:4]:
                text = clean(value).upper()
                if is_real_code(text):
                    codes.add(text)
    return codes


def extract_year(year: int, extractor) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    for pdf in source_pdfs_for_year(year):
        if skip_pdf(pdf):
            file_rows.append(
                {
                    "year": year,
                    "source_file": pdf.name,
                    "source_path": str(pdf),
                    "status": "skipped_reference_or_purchase",
                    "rows": 0,
                    "codes": 0,
                    "code_list": "",
                }
            )
            continue
        try:
            extracted = extractor.parse_pdf(pdf, year)
            status = "ok"
        except Exception as exc:  # pragma: no cover - audit robustness
            extracted = []
            status = f"error:{type(exc).__name__}:{exc}"
        extracted = [row for row in extracted if is_real_code(row.get("hunt_code", ""))]
        codes = sorted({clean(row.get("hunt_code")).upper() for row in extracted})
        file_rows.append(
            {
                "year": year,
                "source_file": pdf.name,
                "source_path": str(pdf),
                "status": status,
                "rows": len(extracted),
                "codes": len(codes),
                "code_list": "|".join(codes),
            }
        )
        for row in extracted:
            row = dict(row)
            row["source_path"] = str(pdf)
            rows.append(row)
    return rows, file_rows


def compare_payloads(pdf_rows: list[dict[str, Any]], canonical_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    canonical_by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in canonical_rows:
        canonical_by_key[key_from_canonical_row(row)].append(row)

    mismatches: list[dict[str, Any]] = []
    pdf_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pdf_rows:
        pdf_by_key[key_from_pdf_row(row)].append(row)

    field_pairs = [
        ("eligible_applicants", "eligible_applicants"),
        ("bonus_permits", "bonus_permits"),
        ("regular_permits", "regular_permits"),
        ("total_permits", "total_permits"),
    ]

    for key, key_rows in pdf_by_key.items():
        candidates = canonical_by_key.get(key, [])
        if not candidates:
            continue

        # If any duplicate canonical candidate carries the same payload, the row
        # is reconciled. This avoids false mismatches from duplicate source docs.
        exact_candidate = None
        for pdf_row in key_rows:
            for candidate in candidates:
                if all(
                    norm_int(pdf_row.get(pdf_field)) == norm_int(candidate.get(canonical_field))
                    for pdf_field, canonical_field in field_pairs
                ):
                    exact_candidate = candidate
                    break
            if exact_candidate is not None:
                break
        if exact_candidate is not None:
            continue

        # Multiple conflicting payloads for the same PDF key usually means the
        # generic text extractor carried the prior Hunt header onto a continuation
        # page. Those rows need custom PDF handling, not canonical patching.
        unique_payloads = {
            tuple(norm_int(row.get(pdf_field)) for pdf_field, _canonical_field in field_pairs)
            for row in key_rows
        }
        if len(unique_payloads) > 1:
            continue

        pdf_row = key_rows[0]
        canonical = candidates[0]
        for pdf_field, canonical_field in field_pairs:
            pdf_value = norm_int(pdf_row.get(pdf_field))
            canonical_value = norm_int(canonical.get(canonical_field))
            if pdf_value == "":
                # Keep malformed PDF parses out of value-mismatch counts. They
                # are tracked separately as parser_blank_rows below.
                continue
            if pdf_value != canonical_value:
                mismatches.append(
                    {
                        "hunt_code": key[0],
                        "residency": key[1],
                        "points": key[2],
                        "field": canonical_field,
                        "pdf_value": pdf_value,
                        "canonical_value": canonical_value,
                        "pdf_source_file": pdf_row.get("source_file", ""),
                        "pdf_hunt_name": clean(pdf_row.get("hunt_name")),
                        "canonical_hunt_name": clean(canonical.get("hunt_name")),
                    }
                )
    return mismatches


def duplicate_pdf_key_conflicts(pdf_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    field_names = ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits")
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pdf_rows:
        by_key[key_from_pdf_row(row)].append(row)

    conflicts: list[dict[str, Any]] = []
    for key, rows in sorted(by_key.items()):
        payloads = {
            tuple(norm_int(row.get(field)) for field in field_names)
            for row in rows
        }
        if len(payloads) <= 1:
            continue
        conflicts.append(
            {
                "hunt_code": key[0],
                "residency": key[1],
                "points": key[2],
                "row_count": len(rows),
                "payload_count": len(payloads),
                "source_files": "|".join(sorted({clean(row.get("source_file")) for row in rows})),
                "pages": "|".join(sorted({clean(row.get("page_number")) for row in rows}, key=lambda v: int(v) if v.isdigit() else 999999)),
                "payloads": "|".join(",".join(payload) for payload in sorted(payloads)),
            }
        )
    return conflicts


def audit_year(year: int, extractor) -> dict[str, Any]:
    pdf_rows, file_rows = extract_year(year, extractor)
    canonical_rows = canonical_scorable_rows(year)

    pdf_keys = {key_from_pdf_row(row) for row in pdf_rows}
    canonical_keys = {key_from_canonical_row(row) for row in canonical_rows}
    pdf_codes = {key[0] for key in pdf_keys}
    canonical_codes = {key[0] for key in canonical_keys}
    pdf_only_keys = sorted(pdf_keys - canonical_keys)
    canonical_only_keys = sorted(canonical_keys - pdf_keys)
    conservation_code_set = conservation_codes() if year in {2025, 2026} else set()
    shared_conservation_canonical_only_keys = [
        key for key in canonical_only_keys if key[0] in conservation_code_set
    ]
    actionable_canonical_only_keys = [
        key for key in canonical_only_keys if key[0] not in conservation_code_set
    ]
    payload_mismatches = compare_payloads(pdf_rows, canonical_rows)
    duplicate_conflicts = duplicate_pdf_key_conflicts(pdf_rows)
    parser_blank_rows = [
        row
        for row in pdf_rows
        if any(norm_int(row.get(field)) == "" for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"))
    ]

    year_dir = OUT_DIR / str(year)
    write_csv(
        year_dir / "pdf_file_summary.csv",
        file_rows,
        ["year", "source_file", "source_path", "status", "rows", "codes", "code_list"],
    )
    write_csv(
        year_dir / "pdf_extracted_rows.csv",
        [
            {
                "source_file": row.get("source_file"),
                "page_number": row.get("page_number"),
                "hunt_code": row.get("hunt_code"),
                "hunt_name": row.get("hunt_name"),
                "residency": row.get("residency"),
                "points": row.get("points"),
                "eligible_applicants": row.get("eligible_applicants"),
                "bonus_permits": row.get("bonus_permits"),
                "regular_permits": row.get("regular_permits"),
                "total_permits": row.get("total_permits"),
                "success_ratio": row.get("success_ratio"),
            }
            for row in pdf_rows
        ],
        [
            "source_file",
            "page_number",
            "hunt_code",
            "hunt_name",
            "residency",
            "points",
            "eligible_applicants",
            "bonus_permits",
            "regular_permits",
            "total_permits",
            "success_ratio",
        ],
    )
    write_csv(
        year_dir / "pdf_only_keys.csv",
        [{"hunt_code": k[0], "residency": k[1], "points": k[2]} for k in pdf_only_keys],
        ["hunt_code", "residency", "points"],
    )
    write_csv(
        year_dir / "canonical_only_keys.csv",
        [{"hunt_code": k[0], "residency": k[1], "points": k[2]} for k in canonical_only_keys],
        ["hunt_code", "residency", "points"],
    )
    write_csv(
        year_dir / "canonical_only_shared_conservation_codes.csv",
        [
            {
                "hunt_code": key[0],
                "residency": key[1],
                "points": key[2],
                "reason": "hunt_code_reused_by_sportsman_draw_and_conservation_allocation",
            }
            for key in shared_conservation_canonical_only_keys
        ],
        ["hunt_code", "residency", "points", "reason"],
    )
    write_csv(
        year_dir / "canonical_only_actionable_keys.csv",
        [{"hunt_code": k[0], "residency": k[1], "points": k[2]} for k in actionable_canonical_only_keys],
        ["hunt_code", "residency", "points"],
    )
    write_csv(
        year_dir / "payload_mismatches.csv",
        payload_mismatches,
        [
            "hunt_code",
            "residency",
            "points",
            "field",
            "pdf_value",
            "canonical_value",
            "pdf_source_file",
            "pdf_hunt_name",
            "canonical_hunt_name",
        ],
    )
    write_csv(
        year_dir / "duplicate_pdf_key_conflicts.csv",
        duplicate_conflicts,
        ["hunt_code", "residency", "points", "row_count", "payload_count", "source_files", "pages", "payloads"],
    )
    write_csv(
        year_dir / "parser_blank_rows.csv",
        [
            {
                "source_file": row.get("source_file"),
                "page_number": row.get("page_number"),
                "hunt_code": row.get("hunt_code"),
                "hunt_name": row.get("hunt_name"),
                "residency": row.get("residency"),
                "points": row.get("points"),
                "eligible_applicants": row.get("eligible_applicants"),
                "bonus_permits": row.get("bonus_permits"),
                "regular_permits": row.get("regular_permits"),
                "total_permits": row.get("total_permits"),
            }
            for row in parser_blank_rows
        ],
        [
            "source_file",
            "page_number",
            "hunt_code",
            "hunt_name",
            "residency",
            "points",
            "eligible_applicants",
            "bonus_permits",
            "regular_permits",
            "total_permits",
        ],
    )

    summary = {
        "year": year,
        "pdf_files": len(source_pdfs_for_year(year)),
        "pdf_files_parsed": sum(1 for row in file_rows if row["status"] == "ok"),
        "pdf_rows": len(pdf_rows),
        "pdf_codes": len(pdf_codes),
        "canonical_rows": len(canonical_rows),
        "canonical_codes": len(canonical_codes),
        "pdf_only_codes": sorted(pdf_codes - canonical_codes),
        "canonical_only_codes": sorted(canonical_codes - pdf_codes),
        "pdf_only_key_count": len(pdf_only_keys),
        "canonical_only_key_count": len(canonical_only_keys),
        "canonical_only_shared_conservation_code_count": len(shared_conservation_canonical_only_keys),
        "canonical_only_actionable_key_count": len(actionable_canonical_only_keys),
        "canonical_only_actionable_codes": sorted({key[0] for key in actionable_canonical_only_keys}),
        "payload_mismatch_count": len(payload_mismatches),
        "duplicate_pdf_key_conflict_count": len(duplicate_conflicts),
        "parser_blank_row_count": len(parser_blank_rows),
        "pdf_prefix_counts": dict(Counter(code[:2] for code in pdf_codes)),
        "canonical_prefix_counts": dict(Counter(code[:2] for code in canonical_codes)),
    }
    (year_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        nargs="*",
        type=int,
        default=list(CANONICAL_YEARS),
        help="Actual draw years to audit. Defaults to 2019-2025.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extractor = load_extractor()
    summaries = [audit_year(year, extractor) for year in args.years]
    (OUT_DIR / "summary_all_years.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(
        OUT_DIR / "summary_all_years.csv",
        summaries,
        [
            "year",
            "pdf_files",
            "pdf_files_parsed",
            "pdf_rows",
            "pdf_codes",
            "canonical_rows",
            "canonical_codes",
            "pdf_only_key_count",
            "canonical_only_key_count",
            "payload_mismatch_count",
            "pdf_only_codes",
            "canonical_only_codes",
        ],
    )
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
