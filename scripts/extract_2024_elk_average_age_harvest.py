#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root

import pandas as pd
import pdfplumber

YEARS = [str(y) for y in range(2015, 2025)]
OBJECTIVE_RE = re.compile(r"^\d+(?:\.\d+)?[–-]\d+(?:\.\d+)?$")
NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def clean_line(line: str) -> str:
    return " ".join((line or "").split()).strip()


def is_missing(value: str) -> bool:
    return value in {"—", "-", "--", "—*", "*", "**", ""}


def to_float_or_none(value: str):
    value = (value or "").strip()
    if is_missing(value):
        return None
    if NUM_RE.match(value):
        return float(value)
    return None


def parse_row(line: str):
    tokens = line.split()
    if len(tokens) < 14:
        return None

    # Find objective token (e.g., 5.5–6.0)
    objective_idx = None
    for i, tok in enumerate(tokens):
        if OBJECTIVE_RE.match(tok):
            objective_idx = i
            break

    if objective_idx is None or objective_idx < 2:
        return None

    unit = tokens[0]
    unit_name = " ".join(tokens[1:objective_idx]).strip()
    objective = tokens[objective_idx]
    tail = tokens[objective_idx + 1 :]

    # Expect 10 year values + 3-year average
    if len(tail) < 11:
        return None

    tail = tail[:11]
    year_vals = tail[:10]
    avg_3_year = tail[10]

    row = {
        "unit": unit,
        "unit_name": unit_name,
        "objective_age_range": objective,
        "hunt_code": "",  # user maps later if needed
    }
    for i, year in enumerate(YEARS):
        row[f"avg_age_{year}"] = to_float_or_none(year_vals[i])
    row["avg_age_3_year_average"] = to_float_or_none(avg_3_year)
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Extract 2024 elk average age harvest table to draft CSV/XLSX outputs."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(_repo_root() / "pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/2024 ELK AVERAGE AGE HARVEST.pdf"),
    )
    parser.add_argument(
        "--out-dir",
        default=r"pipeline\RAW\hunt_unit_database\2025\formatted_tables\elk_average_age_2024_extract",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF: {pdf_path}")

    rows = []
    raw_lines = []
    title = ""

    with pdfplumber.open(str(pdf_path)) as doc:
        page = doc.pages[0]
        text = page.extract_text() or ""
        lines = [clean_line(ln) for ln in text.splitlines() if clean_line(ln)]
        if lines:
            title = lines[0]
        for ln in lines:
            raw_lines.append({"raw_line": ln})
            # Skip headers/notes
            if (
                ln.lower().startswith("average age of harvested")
                or ln.lower().startswith("3-year")
                or ln.lower().startswith("unit unit name objective")
            ):
                continue
            parsed = parse_row(ln)
            if parsed:
                parsed["table_title"] = title
                parsed["source_file"] = str(pdf_path)
                parsed["source_page"] = 1
                rows.append(parsed)

    if not rows:
        raise RuntimeError("No table rows parsed from PDF.")

    df = pd.DataFrame(rows)
    raw_df = pd.DataFrame(raw_lines)

    csv_path = out_dir / "ELK_AVERAGE_AGE_HARVEST_2024.csv"
    xlsx_path = out_dir / "ELK_AVERAGE_AGE_HARVEST_2024.xlsx"
    raw_csv_path = out_dir / "ELK_AVERAGE_AGE_HARVEST_2024_raw_lines.csv"
    manifest_json = out_dir / "elk_average_age_2024_extract_manifest.json"
    manifest_csv = out_dir / "elk_average_age_2024_extract_manifest.csv"
    report_txt = out_dir / "elk_average_age_2024_extract_report.txt"

    df.to_csv(csv_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    raw_df.to_csv(raw_csv_path, index=False, encoding="utf-8")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="elk_avg_age")
        raw_df.to_excel(writer, index=False, sheet_name="raw_lines")

    manifest = [
        {
            "source_pdf": str(pdf_path),
            "table_title": title,
            "rows_parsed": int(len(df)),
            "columns": int(len(df.columns)),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "csv_file": str(csv_path),
            "xlsx_file": str(xlsx_path),
            "raw_lines_file": str(raw_csv_path),
        }
    ]
    pd.DataFrame(manifest).to_csv(manifest_csv, index=False, encoding="utf-8")
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report_txt.write_text(
        "\n".join(
            [
                "2024 ELK AVERAGE AGE HARVEST extraction report",
                "===========================================",
                f"source_pdf: {pdf_path}",
                f"rows_parsed: {len(df)}",
                f"csv_file: {csv_path}",
                f"xlsx_file: {xlsx_path}",
                f"raw_lines_file: {raw_csv_path}",
                f"manifest_json: {manifest_json}",
                f"manifest_csv: {manifest_csv}",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "source_pdf": str(pdf_path),
                "out_dir": str(out_dir),
                "rows_parsed": int(len(df)),
                "csv_file": str(csv_path),
                "xlsx_file": str(xlsx_path),
                "raw_lines_file": str(raw_csv_path),
                "manifest_json": str(manifest_json),
                "manifest_csv": str(manifest_csv),
                "report_txt": str(report_txt),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
