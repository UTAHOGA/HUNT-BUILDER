#!/usr/bin/env python3
"""Batch-extract permit rows from 2026 current-year permit PDFs into CSV.

This script is a runtime-friendly supplement to `scripts/extract_permits.py`.
It writes:

- One extracted CSV per source PDF
- A combined audit manifest for all processed PDFs
- A combined CSV for cross-file merge work
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import importlib.util
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

ROOT = Path(__file__).resolve().parents[1]

_EXTRACT_PERMITS = ROOT / "scripts" / "extract_permits.py"
_spec = importlib.util.spec_from_file_location("extract_permits", _EXTRACT_PERMITS)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Unable to load extractor module from {_EXTRACT_PERMITS}")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
extract_many = _module.extract_many


DEFAULT_SOURCE_DIR = (
    ROOT / "pipeline/RAW/hunt_unit_database/2026/pdf/current_year_permit_numbers"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/current_year_permit_numbers"
)


@dataclass(frozen=True)
class ExtractedRow:
    source_pdf: str
    source_file: str
    source_page: int
    hunt_code: str
    hunt_name: str
    species_or_category: str
    method_or_weapon: str
    permits_2026_res: str
    permits_2026_nr: str
    permits_2026_total: str
    parse_status: str
    raw_hunt_line: str
    raw_totals_line: str


OUTPUT_FIELDNAMES = [
    "source_pdf",
    "source_file",
    "source_page",
    "hunt_code",
    "hunt_name",
    "species_or_category",
    "method_or_weapon",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "parse_status",
    "raw_hunt_line",
    "raw_totals_line",
]


def _to_str(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text if text.lower() != "none" else ""


def _to_int_str(value: object) -> str:
    text = _to_str(value).replace(",", "")
    if not text:
        return ""
    # keep nonnumeric values as-is for traceability (e.g. UNLIMITED)
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def _coerce_rows(rows: Sequence, source_pdf: str, source_file: str) -> List[ExtractedRow]:
    out: List[ExtractedRow] = []
    for row in rows:
        out.append(
            ExtractedRow(
                source_pdf=source_pdf,
                source_file=source_file,
                source_page=int(row.page_number),
                hunt_code=_to_str(row.hunt_code),
                hunt_name=_to_str(row.hunt_name),
                species_or_category=_to_str(row.species_or_category),
                method_or_weapon=_to_str(row.method_or_weapon),
                permits_2026_res=_to_int_str(row.permits_res_total),
                permits_2026_nr=_to_int_str(row.permits_nonres_total),
                permits_2026_total=_to_int_str(row.permits_total),
                parse_status="OK" if row.permits_total is not None else "MISSING_TOTAL",
                raw_hunt_line=_to_str(row.raw_hunt_line),
                raw_totals_line=_to_str(row.raw_totals_line),
            )
        )
    return out


def _slug(value: str) -> str:
    base = value.strip().lower().replace(" ", "_")
    base = re.sub(r"[^a-z0-9._-]+", "_", base)
    return re.sub(r"_+", "_", base).strip("_")


def _file_report(output_dir: Path, source_name: str, rows: List[ExtractedRow], report: dict) -> Path:
    report_out = output_dir / f"{source_name}_extraction_report.json"
    report_payload = {
        "source_file": report.get("source_file", ""),
        "source_pdf": source_name,
        "total_pages_scanned": report.get("total_pages_scanned", 0),
        "total_hunt_lines_found": report.get("total_hunt_lines_found", 0),
        "total_permit_numbers_found": report.get("total_permit_numbers_found", 0),
        "duplicate_count": report.get("duplicate_count", 0),
        "pages_with_no_extractable_text": report.get("pages_with_no_extractable_text", []),
        "pages_with_hunt_line_missing_totals": report.get("pages_with_hunt_line_missing_totals", []),
        "rows_written": len(rows),
    }
    report_out.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    return report_out


def _write_csv(path: Path, rows: Sequence[ExtractedRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate per-PDF CSV extract files for all 2026 permit PDFs"
    )
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Folder with source 2026 permit PDFs.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output folder for generated permit CSV and audit files.",
    )
    parser.add_argument(
        "--pattern",
        default="*.pdf",
        help="PDF filename glob pattern (default: *.pdf).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_dir = Path(args.source_dir)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = sorted(source_dir.glob(args.pattern))
    if not pdf_paths:
        raise SystemExit(f"No PDF files matched: {source_dir} with pattern {args.pattern}")

    combined_rows: List[ExtractedRow] = []
    manifest_rows: List[dict] = []
    file_reports: List[dict] = []

    for pdf_path in pdf_paths:
        rows, report = extract_many([pdf_path])
        extracted = _coerce_rows(rows, pdf_path.name, str(pdf_path))
        base = _slug(pdf_path.stem)
        # produce one file per source PDF
        per_file_csv = output_dir / f"{base}_permit_rows_extracted.csv"
        _write_csv(per_file_csv, extracted)

        file_report_path = _file_report(output_dir, base, extracted, report)
        manifest_rows.append(
            {
                "source_pdf": pdf_path.name,
                "source_file": str(pdf_path),
                "rows_written": str(len(extracted)),
                "total_hunt_lines_found": str(report.get("total_hunt_lines_found", 0)),
                "total_pages_scanned": str(report.get("total_pages_scanned", 0)),
                "duplicate_count": str(report.get("duplicate_count", 0)),
                "per_file_csv": str(per_file_csv.relative_to(ROOT)),
                "per_file_report": str(file_report_path.relative_to(ROOT)),
            }
        )
        file_reports.append(
            {
                "source_pdf": pdf_path.name,
                "source_file": str(pdf_path),
                "total_hunt_lines_found": report.get("total_hunt_lines_found", 0),
                "total_permit_numbers_found": report.get("total_permit_numbers_found", 0),
                "duplicate_count": report.get("duplicate_count", 0),
                "pages_with_no_extractable_text": report.get("pages_with_no_extractable_text", []),
                "pages_with_hunt_line_missing_totals": report.get("pages_with_hunt_line_missing_totals", []),
            }
        )
        combined_rows.extend(extracted)

        print(f"[{pdf_path.name}] wrote {len(extracted)} rows")

    combined_csv = output_dir / "2026_current_year_permits_all_extracted_rows.csv"
    _write_csv(combined_csv, combined_rows)
    manifest_csv = output_dir / "2026_current_year_permit_pdf_extraction_manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()) if manifest_rows else [
            "source_pdf",
            "source_file",
            "rows_written",
            "total_hunt_lines_found",
            "total_pages_scanned",
            "duplicate_count",
            "per_file_csv",
            "per_file_report",
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)

    run_report = {
        "source_dir": str(source_dir),
        "file_count": len(pdf_paths),
        "combined_rows_written": len(combined_rows),
        "per_file_reports": file_reports,
    }
    (output_dir / "2026_current_year_permit_pdf_batch_report.json").write_text(
        json.dumps(run_report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote combined CSV: {combined_csv}")
    print(f"Wrote manifest: {manifest_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
