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
TABLE_TITLE_RE = re.compile(r".*elk harvest,\s*Utah 2024\.?$", re.IGNORECASE)


def clean_line(line: str) -> str:
    return " ".join((line or "").split()).strip()


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


def title_from_page(lines: list[str]) -> str:
    if not lines:
        return ""
    t = lines[0]
    if "Utah 2024" not in t and len(lines) > 1 and "Utah 2024" in lines[1]:
        t = f"{t} {lines[1]}"
    return t


def line_is_table_title(line: str) -> bool:
    return bool(TABLE_TITLE_RE.match(clean_line(line)))


def parse_meta(table_title: str) -> dict:
    t = (table_title or "").lower()
    hunt_class = "Limited Entry" if "limited-entry" in t or "limited entry" in t else ""
    hunt_type = "Limited Entry" if hunt_class else ""

    weapon = ""
    if "hamss" in t or "handgun-archery-muzzleloader-shotgun-short-walled-rifle" in t:
        weapon = "HAMSS"
    elif "multiseason" in t:
        weapon = "Multiseason"
    elif "landowner" in t:
        weapon = "Landowner"
    elif "any legal weapon" in t:
        weapon = "Any Legal Weapon"
    elif "muzzleloader" in t:
        weapon = "Muzzleloader"
    elif "archery" in t:
        weapon = "Archery"

    season = ""
    if "hamss" in t or "handgun-archery-muzzleloader-shotgun-short-walled-rifle" in t:
        season = "HAMSS"
    elif "multiseason" in t:
        season = "Multiseason"
    elif "landowner" in t:
        season = "Landowner"
    elif "september archery" in t:
        season = "September"
    elif "late archery" in t:
        season = "Late"
    elif "early any legal weapon" in t:
        season = "Early"
    elif "mid any legal weapon" in t:
        season = "Mid"
    elif "late any legal weapon" in t:
        season = "Late"
    elif "muzzleloader" in t:
        season = "Muzzleloader"
    elif "archery" in t:
        season = "Archery"

    return {
        "Sex type": "Bull",
        "Hunt type": hunt_type,
        "Weapon": weapon,
        "Season": season,
        "Hunt class": hunt_class,
    }


def split_hunt_name_and_weapon(pre_tokens: list[str]):
    if not pre_tokens:
        return "", ""
    low = [x.lower() for x in pre_tokens]
    if len(low) >= 3 and low[-3:] == ["any", "legal", "weapon"]:
        return " ".join(pre_tokens[:-3]).strip(), "Any Legal Weapon"
    if low[-1] == "archery":
        return " ".join(pre_tokens[:-1]).strip(), "Archery"
    if low[-1] == "muzzleloader":
        return " ".join(pre_tokens[:-1]).strip(), "Muzzleloader"
    if low[-1] == "hamss":
        return " ".join(pre_tokens[:-1]).strip(), "HAMSS"
    return " ".join(pre_tokens).strip(), ""


def parse_row(line: str):
    tokens = line.split()
    if len(tokens) < 7:
        return None

    code_idx = None
    hunt_code = None
    for i, tok in enumerate(tokens):
        if HUNT_CODE_RE.fullmatch(tok):
            code_idx = i
            hunt_code = tok
            break
    if code_idx is None or code_idx == 0:
        return None

    unit = tokens[0]
    after = tokens[code_idx + 1 :]
    if not after:
        return None

    first_num = None
    for i, tok in enumerate(after):
        if NUMISH_RE.match(tok):
            first_num = i
            break
    if first_num is None:
        return None

    hunt_name, row_weapon = split_hunt_name_and_weapon(after[:first_num])
    nums = [to_num_or_none(x) for x in after[first_num:]]
    if len(nums) < 5:
        return None

    return {
        "Unit": unit,
        "Hunt number": hunt_code,
        "Hunt name": hunt_name,
        "Row weapon": row_weapon,
        "Bull harvest": nums[1],
        "Permits": nums[0],
        "Hunters afield": nums[2],
        "Mean days hunted": nums[3],
        "Success rate (%)": nums[4],
    }


def load_boundary_map(crosswalk_csv: Path) -> dict[str, str]:
    if not crosswalk_csv.exists():
        return {}
    out = {}
    with crosswalk_csv.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            hc = str(r.get("hunt_code", "") or "").strip().upper()
            bid = str(r.get("boundary_id", "") or "").strip()
            if hc and bid:
                out[hc] = bid
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Extract 2024 limited-entry elk harvest table rows with required headers."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(_repo_root() / "pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/2024 LIMITED ENTRY ELK HARVEST.pdf"),
    )
    parser.add_argument(
        "--out-dir",
        default=r"pipeline\RAW\hunt_unit_database\2025\formatted_tables\limited_entry_elk_harvest_2024_extract",
    )
    parser.add_argument(
        "--crosswalk",
        default=r"processed_data\hunt_boundary_crosswalk_2026.csv",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    crosswalk_csv = Path(args.crosswalk)
    if not crosswalk_csv.is_absolute():
        crosswalk_csv = Path(__file__).resolve().parents[1] / crosswalk_csv
    boundary_map = load_boundary_map(crosswalk_csv.resolve())

    rows = []
    with pdfplumber.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc.pages, start=1):
            lines = [clean_line(x) for x in (page.extract_text() or "").splitlines()]
            lines = [x for x in lines if x]
            current_title = title_from_page(lines)
            current_meta = parse_meta(current_title)
            for ln in lines:
                if line_is_table_title(ln):
                    current_title = ln
                    current_meta = parse_meta(current_title)
                    continue
                if not HUNT_CODE_RE.search(ln):
                    continue
                parsed = parse_row(ln)
                if not parsed:
                    continue
                hc = parsed["Hunt number"].upper()
                parsed["Sex type"] = current_meta["Sex type"]
                parsed["Hunt type"] = current_meta["Hunt type"]
                parsed["Weapon"] = parsed.get("Row weapon", "") or current_meta["Weapon"]
                parsed["Season"] = current_meta["Season"]
                parsed["Hunt class"] = current_meta["Hunt class"]
                parsed["HUNT BOUNDARY"] = boundary_map.get(hc, "")
                parsed["Page title"] = current_title
                parsed["Source page"] = page_num
                parsed["Source file"] = pdf_path.name
                rows.append(parsed)

    if not rows:
        raise RuntimeError("No rows extracted.")

    seen = set()
    dedup = []
    for r in rows:
        k = (r["Source page"], r["Hunt number"], r["Hunt name"], r["Weapon"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)
    rows = dedup

    headers = [
        "Unit",
        "Hunt number",
        "Hunt name",
        "Bull harvest",
        "Permits",
        "Hunters afield",
        "Mean days hunted",
        "Success rate (%)",
        "Sex type",
        "Hunt type",
        "Weapon",
        "Season",
        "Hunt class",
        "HUNT BOUNDARY",
        "Page title",
        "Source page",
        "Source file",
    ]

    df = pd.DataFrame(rows)[headers]

    out_csv = out_dir / "LIMITED_ENTRY_ELK_HARVEST_2024_STANDARDIZED.csv"
    out_xlsx = out_dir / "LIMITED_ENTRY_ELK_HARVEST_2024_STANDARDIZED.xlsx"
    report_json = out_dir / "limited_entry_elk_harvest_2024_standardized_report.json"
    report_txt = out_dir / "limited_entry_elk_harvest_2024_standardized_report.txt"

    # If target files are open/locked, write versioned fallback files.
    try:
        df.to_csv(out_csv, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="limited_entry_elk_2024")
        used_csv = out_csv
        used_xlsx = out_xlsx
    except PermissionError:
        used_csv = out_dir / "LIMITED_ENTRY_ELK_HARVEST_2024_STANDARDIZED_UPDATED.csv"
        used_xlsx = out_dir / "LIMITED_ENTRY_ELK_HARVEST_2024_STANDARDIZED_UPDATED.xlsx"
        df.to_csv(used_csv, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
        with pd.ExcelWriter(used_xlsx, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="limited_entry_elk_2024")

    boundary_missing = int((df["HUNT BOUNDARY"].astype(str).str.strip() == "").sum())
    report = {
        "source_pdf": str(pdf_path),
        "rows_extracted": int(len(df)),
        "unique_hunt_numbers": int(df["Hunt number"].nunique()),
        "boundary_missing_rows": boundary_missing,
        "output_csv": str(used_csv),
        "output_xlsx": str(used_xlsx),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_txt.write_text(
        "\n".join(
            [
                "LIMITED ENTRY ELK HARVEST 2024 STANDARDIZED REPORT",
                "=================================================",
                f"source_pdf: {pdf_path}",
                f"rows_extracted: {len(df)}",
                f"unique_hunt_numbers: {df['Hunt number'].nunique()}",
                f"boundary_missing_rows: {boundary_missing}",
                f"output_csv: {used_csv}",
                f"output_xlsx: {used_xlsx}",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

