from __future__ import annotations

import argparse
import csv
import json
import re
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


def clean_lines(text: str) -> list[str]:
    lines = [" ".join((ln or "").split()).strip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        if not ln:
            continue
        if re.fullmatch(r"Page\s+\d{1,3}", ln):
            continue
        if re.fullmatch(r"\d{1,3}", ln):
            continue
        out.append(ln)
    return out


def to_int(value: str | None):
    if value is None:
        return None
    v = value.strip().replace(",", "")
    if v.endswith("*"):
        v = v[:-1]
    if v in {"", "—", "*", "**"}:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def to_float(value: str | None):
    if value is None:
        return None
    v = value.strip().replace(",", "")
    if v.endswith("*"):
        v = v[:-1]
    if v in {"", "—", "*", "**"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_page(lines: list[str], page_number: int) -> tuple[str, pd.DataFrame, list[str]]:
    title = lines[0] if lines else f"Page {page_number}"
    rows = []
    notes = []

    for ln in lines:
        if ln.startswith("General-season "):
            continue
        if ln.startswith("Unit Unit name "):
            continue
        if ln.startswith("*"):
            notes.append(ln)
            continue

        if ln.startswith("Statewide totals"):
            tokens = ln.split()
            tail = tokens[-4:] if len(tokens) >= 4 else []
            if len(tail) == 4:
                rows.append(
                    {
                        "Unit": "",
                        "Unit name": "Statewide totals",
                        "Bull harvest": to_int(tail[0]),
                        "Hunters afield": to_int(tail[1]),
                        "Mean days hunted": to_float(tail[2]),
                        "Success rate (%)": to_float(tail[3]),
                        "adobe_page": page_number,
                        "table_title": title,
                    }
                )
            continue

        tokens = ln.split()
        if len(tokens) < 6:
            continue

        unit = tokens[0]
        tail = tokens[-4:]
        name = " ".join(tokens[1:-4]).strip()
        if not name:
            continue

        # Require tail to at least look numeric/placeholder.
        if not all(re.fullmatch(r"[\d.]+|—|\*{1,2}", t) for t in tail):
            continue

        rows.append(
            {
                "Unit": unit,
                "Unit name": name,
                "Bull harvest": to_int(tail[0]),
                "Hunters afield": to_int(tail[1]),
                "Mean days hunted": to_float(tail[2]),
                "Success rate (%)": to_float(tail[3]),
                "adobe_page": page_number,
                "table_title": title,
            }
        )

    return title, pd.DataFrame(rows), notes


def write_table(base: Path, df: pd.DataFrame, notes: list[str]):
    csv_path = base.with_suffix(".csv")
    xlsx_path = base.with_suffix(".xlsx")
    df.to_csv(csv_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="data")
        if notes:
            pd.DataFrame({"note": notes}).to_excel(w, index=False, sheet_name="notes")
    return str(csv_path), str(xlsx_path)


def main():
    parser = argparse.ArgumentParser(description="Extract General Season Elk tables from split 2024 elk harvest PDF.")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(_repo_root() / "pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/Pages from 24_elk_bg_report general season.pdf"),
    )
    parser.add_argument(
        "--out-dir",
        default=r"pipeline\RAW\hunt_unit_database\2025\formatted_tables\elk_general_season_2024_extract",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    all_frames = []

    with pdfplumber.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc.pages, start=1):
            lines = clean_lines(page.extract_text() or "")
            title, df, notes = parse_page(lines, page_num)
            table_id = f"ELK_GENERAL_SEASON_ADOBE_PAGE_{page_num:03d}"
            csv_file, xlsx_file = write_table(out_dir / table_id, df, notes)
            manifest.append(
                {
                    "table_id": table_id,
                    "adobe_page": page_num,
                    "title": title,
                    "rows": int(len(df)),
                    "csv_file": csv_file,
                    "xlsx_file": xlsx_file,
                    "notes_count": len(notes),
                }
            )
            all_frames.append(df)

    master_df = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    master_csv, master_xlsx = write_table(out_dir / "ELK_GENERAL_SEASON_2024_ALL_PAGES_MASTER", master_df, [])

    manifest_df = pd.DataFrame(manifest)
    manifest_csv = out_dir / "elk_general_season_extract_manifest.csv"
    manifest_xlsx = out_dir / "elk_general_season_extract_manifest.xlsx"
    manifest_json = out_dir / "elk_general_season_extract_manifest.json"
    report_txt = out_dir / "elk_general_season_extract_report.txt"
    manifest_df.to_csv(manifest_csv, index=False, encoding="utf-8")
    manifest_df.to_excel(manifest_xlsx, index=False)
    manifest_df.to_json(manifest_json, orient="records", indent=2, force_ascii=False)
    report_txt.write_text(
        "\n".join(
            [
                "General Season Elk extraction report",
                "==================================",
                f"source_pdf: {pdf_path}",
                f"pages: {len(manifest_df)}",
                f"page_tables_written: {len(manifest_df)}",
                f"master_rows: {len(master_df)}",
                f"master_csv: {master_csv}",
                f"master_xlsx: {master_xlsx}",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "source_pdf": str(pdf_path),
                "out_dir": str(out_dir),
                "page_tables": int(len(manifest_df)),
                "master_rows": int(len(master_df)),
                "manifest_csv": str(manifest_csv),
                "manifest_xlsx": str(manifest_xlsx),
                "manifest_json": str(manifest_json),
                "master_csv": str(master_csv),
                "master_xlsx": str(master_xlsx),
                "report_txt": str(report_txt),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

