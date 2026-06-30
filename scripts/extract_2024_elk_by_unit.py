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

HUNT_CODE_RE = re.compile(r"\b[A-Z]{2}\d{4}\b")
NUMISH_RE = re.compile(r"^(?:-?\d+(?:\.\d+)?|—|--|-|\*+)$")


def clean_line(line: str) -> str:
    return " ".join((line or "").split()).strip()


def extract_table_title(lines: list[str]) -> str:
    # Prefer first line containing "Utah 2024"
    for i, ln in enumerate(lines[:6]):
        if "Utah 2024" in ln or "Utah 2024." in ln:
            if i + 1 < len(lines) and "Utah 2024" not in ln and "harvest" in lines[i + 1].lower():
                return f"{ln} {lines[i + 1]}"
            return ln
    return lines[0] if lines else ""


def parse_hunt_code_row(line: str):
    tokens = line.split()
    if len(tokens) < 3:
        return None
    code_idx = None
    code_val = None
    for i, t in enumerate(tokens):
        if HUNT_CODE_RE.fullmatch(t):
            code_idx = i
            code_val = t
            break
    if code_idx is None or code_idx == 0:
        return None

    unit = tokens[0]
    after = tokens[code_idx + 1 :]
    if not after:
        return None

    first_num_idx = None
    for i, t in enumerate(after):
        if NUMISH_RE.match(t):
            first_num_idx = i
            break
    if first_num_idx is None:
        hunt_name = " ".join(after).strip()
        metrics = ""
    else:
        hunt_name = " ".join(after[:first_num_idx]).strip()
        metrics = " ".join(after[first_num_idx:]).strip()

    return {
        "unit": unit,
        "hunt_code": code_val,
        "hunt_name": hunt_name,
        "metrics_tail": metrics,
        "raw_line": line,
    }


def to_num_or_none(token: str):
    t = (token or "").strip()
    if t in {"", "—", "--", "-", "*", "**"}:
        return None
    try:
        if "." in t:
            return float(t)
        return int(t)
    except ValueError:
        return None


def to_standard_row(row: dict, boundary_map: dict[str, str]) -> dict:
    title = str(row.get("table_title", "") or "").lower()
    toks = [x for x in str(row.get("metrics_tail", "") or "").split() if x]
    nums = [to_num_or_none(x) for x in toks]
    is_antlerless = "antlerless" in title

    bull = None
    antlerless = None
    total = None
    hunters = None
    mean_days = None
    success = None

    # Common table shapes:
    # 5 tokens: permits, harvest, hunters, days, success
    # 7 tokens: bull/cow/calf/total/hunters/days/success OR cow/calf/total/permits/hunters/days/success
    if len(nums) >= 7:
        if is_antlerless:
            antlerless = nums[2] if nums[2] is not None else (
                (nums[0] or 0) + (nums[1] or 0) if nums[0] is not None or nums[1] is not None else None
            )
            total = nums[2]
            hunters = nums[4]
            mean_days = nums[5]
            success = nums[6]
        else:
            bull = nums[0]
            antlerless = (nums[1] or 0) + (nums[2] or 0) if nums[1] is not None or nums[2] is not None else None
            total = nums[3]
            hunters = nums[4]
            mean_days = nums[5]
            success = nums[6]
    elif len(nums) >= 5:
        if is_antlerless:
            antlerless = nums[1]
            total = nums[1]
        else:
            bull = nums[1]
            total = nums[1]
        hunters = nums[2]
        mean_days = nums[3]
        success = nums[4]

    hc = str(row.get("hunt_code", "") or "").strip().upper()
    return {
        "Unit": str(row.get("unit", "") or "").strip(),
        "Unit name": str(row.get("hunt_name", "") or "").strip(),
        "HUNT CODE": hc,
        "HUNT BOUNDARY": boundary_map.get(hc, ""),
        "Bull harvest": bull,
        "Antlerless harvest": antlerless,
        "Total harvest": total,
        "Hunters afield": hunters,
        "Mean days hunted": mean_days,
        "Success rate (%)": success,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract hunt-code rows from 2024 ELK BY UNIT harvest report."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(_repo_root() / "pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/2024 ELK BY UNIT 2024.pdf"),
    )
    parser.add_argument(
        "--out-dir",
        default=r"pipeline\RAW\hunt_unit_database\2025\formatted_tables\elk_by_unit_2024_extract",
    )
    parser.add_argument(
        "--crosswalk",
        default=r"processed_data\hunt_boundary_crosswalk_2026.csv",
        help="Crosswalk CSV used to map hunt_code -> boundary_id.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    crosswalk_csv = Path(args.crosswalk)
    if not crosswalk_csv.is_absolute():
        crosswalk_csv = Path(__file__).resolve().parents[1] / crosswalk_csv
    crosswalk_csv = crosswalk_csv.resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF: {pdf_path}")

    hunt_rows = []
    raw_lines = []
    pages_with_no_text = []

    with pdfplumber.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc.pages, start=1):
            text = page.extract_text() or ""
            lines = [clean_line(x) for x in text.splitlines() if clean_line(x)]
            if not lines:
                pages_with_no_text.append(page_num)
                continue
            table_title = extract_table_title(lines)
            for ln in lines:
                raw_lines.append(
                    {
                        "source_page": page_num,
                        "table_title": table_title,
                        "raw_line": ln,
                    }
                )
                if not HUNT_CODE_RE.search(ln):
                    continue
                parsed = parse_hunt_code_row(ln)
                if not parsed:
                    continue
                parsed["source_page"] = page_num
                parsed["table_title"] = table_title
                parsed["source_file"] = str(pdf_path)
                hunt_rows.append(parsed)

    if not hunt_rows:
        raise RuntimeError("No hunt-code rows parsed from PDF.")

    # De-duplicate exact repeats by page+code+line
    seen = set()
    dedup = []
    for r in hunt_rows:
        key = (r["source_page"], r["hunt_code"], r["raw_line"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    hunt_rows = dedup

    # boundary map from crosswalk
    boundary_map = {}
    if crosswalk_csv.exists():
        with crosswalk_csv.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                hc = str(r.get("hunt_code", "") or "").strip().upper()
                bid = str(r.get("boundary_id", "") or "").strip()
                if hc and bid:
                    boundary_map[hc] = bid

    rows_df = pd.DataFrame(hunt_rows)
    std_df = pd.DataFrame([to_standard_row(r, boundary_map) for r in hunt_rows])
    raw_df = pd.DataFrame(raw_lines)

    rows_csv = out_dir / "ELK_BY_UNIT_2024_hunt_rows.csv"
    rows_xlsx = out_dir / "ELK_BY_UNIT_2024_hunt_rows.xlsx"
    std_csv = out_dir / "ELK_BY_UNIT_2024_STANDARDIZED.csv"
    std_xlsx = out_dir / "ELK_BY_UNIT_2024_STANDARDIZED.xlsx"
    raw_csv = out_dir / "ELK_BY_UNIT_2024_raw_lines.csv"
    manifest_csv = out_dir / "elk_by_unit_2024_extract_manifest.csv"
    manifest_json = out_dir / "elk_by_unit_2024_extract_manifest.json"
    report_txt = out_dir / "elk_by_unit_2024_extract_report.txt"

    rows_df.to_csv(rows_csv, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    std_df.to_csv(std_csv, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    raw_df.to_csv(raw_csv, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(rows_xlsx, engine="openpyxl") as writer:
        rows_df.to_excel(writer, index=False, sheet_name="hunt_rows")
        raw_df.to_excel(writer, index=False, sheet_name="raw_lines")
    with pd.ExcelWriter(std_xlsx, engine="openpyxl") as writer:
        std_df.to_excel(writer, index=False, sheet_name="elk_by_unit_standardized")

    manifest = [
        {
            "source_pdf": str(pdf_path),
            "total_pages": int(len(set(raw_df["source_page"]))),
            "hunt_rows_parsed": int(len(rows_df)),
            "unique_hunt_codes": int(rows_df["hunt_code"].nunique()),
            "pages_with_no_text": ";".join(str(x) for x in pages_with_no_text),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "rows_csv": str(rows_csv),
            "rows_xlsx": str(rows_xlsx),
            "standardized_csv": str(std_csv),
            "standardized_xlsx": str(std_xlsx),
            "raw_csv": str(raw_csv),
        }
    ]
    pd.DataFrame(manifest).to_csv(manifest_csv, index=False, encoding="utf-8-sig")
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_txt.write_text(
        "\n".join(
            [
                "2024 ELK BY UNIT extraction report",
                "=================================",
                f"source_pdf: {pdf_path}",
                f"hunt_rows_parsed: {len(rows_df)}",
                f"unique_hunt_codes: {rows_df['hunt_code'].nunique()}",
                f"rows_csv: {rows_csv}",
                f"rows_xlsx: {rows_xlsx}",
                f"standardized_csv: {std_csv}",
                f"standardized_xlsx: {std_xlsx}",
                f"raw_csv: {raw_csv}",
                f"manifest_csv: {manifest_csv}",
                f"manifest_json: {manifest_json}",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "source_pdf": str(pdf_path),
                "out_dir": str(out_dir),
                "hunt_rows_parsed": int(len(rows_df)),
                "unique_hunt_codes": int(rows_df["hunt_code"].nunique()),
                "rows_csv": str(rows_csv),
                "rows_xlsx": str(rows_xlsx),
                "standardized_csv": str(std_csv),
                "standardized_xlsx": str(std_xlsx),
                "manifest_csv": str(manifest_csv),
                "manifest_json": str(manifest_json),
                "report_txt": str(report_txt),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
