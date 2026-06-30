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
from typing import Iterable

import pandas as pd
import pdfplumber


PDF_DEFAULT = str(_repo_root() / "pipeline/RAW/hunt_unit_database/2025/pdf/harvest_report/Pages from 24_bg_report-2.pdf")


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


def to_int(v: str | None):
    if v is None:
        return None
    s = v.strip().replace(",", "")
    if s.endswith("*"):
        s = s[:-1]
    if s in {"", "*", "**", "—"}:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def to_float(v: str | None):
    if v is None:
        return None
    s = v.strip().replace(",", "")
    if s.endswith("*"):
        s = s[:-1]
    if s in {"", "*", "**", "—"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def write_table(out_dir: Path, base: str, df: pd.DataFrame, notes: list[str] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{base}.csv"
    xlsx_path = out_dir / f"{base}.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="data")
        if notes:
            pd.DataFrame({"note": notes}).to_excel(w, index=False, sheet_name="notes")
    return str(csv_path), str(xlsx_path)


def load_pages(pdf_path: Path) -> dict[int, list[str]]:
    out = {}
    with pdfplumber.open(str(pdf_path)) as doc:
        for p in range(1, len(doc.pages) + 1):
            out[p] = clean_lines(doc.pages[p - 1].extract_text() or "")
    return out


def parse_general_or_cwmu_buck(lines: list[str], adobe_page: int, name_col: str):
    row_re = re.compile(
        r"^(?P<unit>\S+)\s+(?P<hunt>[A-Z]{2}\s?\d{4})\s+(?P<name>.+?)\s+"
        r"(?P<buck>\d+)\s+(?P<permits>\d+)\s+(?P<hunters>\d+)\s+"
        r"(?P<mean>\d+(?:\.\d+)?)\s+(?P<succ>\d+(?:\.\d+)?)$"
    )
    totals_re = re.compile(
        r"^Statewide totals\s+(?P<buck>\d+)\s+(?P<permits>\d+)\s+(?P<hunters>\d+)\s+"
        r"(?P<mean>\d+(?:\.\d+)?)\s+(?P<succ>\d+(?:\.\d+)?)$"
    )
    rows = []
    notes = []
    for ln in lines:
        m = row_re.match(ln)
        if m:
            rows.append(
                {
                    "Unit": m.group("unit"),
                    "Hunt number": m.group("hunt").replace(" ", ""),
                    name_col: m.group("name"),
                    "Buck harvest": to_int(m.group("buck")),
                    "Permits": to_int(m.group("permits")),
                    "Hunters afield": to_int(m.group("hunters")),
                    "Mean days hunted": to_float(m.group("mean")),
                    "Success rate (%)": to_float(m.group("succ")),
                    "adobe_page": adobe_page,
                }
            )
            continue
        t = totals_re.match(ln)
        if t:
            rows.append(
                {
                    "Unit": "",
                    "Hunt number": "",
                    name_col: "Statewide totals",
                    "Buck harvest": to_int(t.group("buck")),
                    "Permits": to_int(t.group("permits")),
                    "Hunters afield": to_int(t.group("hunters")),
                    "Mean days hunted": to_float(t.group("mean")),
                    "Success rate (%)": to_float(t.group("succ")),
                    "adobe_page": adobe_page,
                }
            )
            continue
        if ln.startswith("*"):
            notes.append(ln)
    return pd.DataFrame(rows), notes


def parse_cwmu_antlerless(lines: list[str], adobe_page: int):
    row_re = re.compile(
        r"^(?P<unit>\S+)\s+(?P<hunt>[A-Z]{2}\d{4}\*?)\s+(?P<name>.+?)\s+"
        r"(?P<doe>\d+)\s+(?P<fawn>\d+)\s+(?P<total>\d+)\s+(?P<permits>\d+)\s+"
        r"(?P<hunters>\d+)\s+(?P<mean>\d+(?:\.\d+)?)\s+(?P<succ>\d+(?:\.\d+)?)$"
    )
    rows, notes = [], []
    for ln in lines:
        m = row_re.match(ln)
        if m:
            rows.append(
                {
                    "Unit": m.group("unit"),
                    "Hunt number": m.group("hunt").replace("*", ""),
                    "CWMU name": m.group("name"),
                    "Doe harvest": to_int(m.group("doe")),
                    "Fawn harvest": to_int(m.group("fawn")),
                    "Total harvest": to_int(m.group("total")),
                    "Permits": to_int(m.group("permits")),
                    "Hunters afield": to_int(m.group("hunters")),
                    "Mean days hunted": to_float(m.group("mean")),
                    "Success rate (%)": to_float(m.group("succ")),
                    "adobe_page": adobe_page,
                }
            )
        elif ln.startswith("*"):
            notes.append(ln)
    return pd.DataFrame(rows), notes


def parse_fawn_100(lines: list[str], adobe_page: int):
    years = [str(y) for y in range(2015, 2025)]
    row_re = re.compile(
        r"^(?P<unit>\S+)\s+(?P<name>.+?)\s+"
        r"(?P<y2015>\S+)\s+(?P<y2016>\S+)\s+(?P<y2017>\S+)\s+(?P<y2018>\S+)\s+"
        r"(?P<y2019>\S+)\s+(?P<y2020>\S+)\s+(?P<y2021>\S+)\s+(?P<y2022>\S+)\s+"
        r"(?P<y2023>\S+)\s+(?P<y2024>\S+)$"
    )
    avg_re = re.compile(
        r"^Statewide averages\s+"
        r"(?P<y2015>\S+)\s+(?P<y2016>\S+)\s+(?P<y2017>\S+)\s+(?P<y2018>\S+)\s+"
        r"(?P<y2019>\S+)\s+(?P<y2020>\S+)\s+(?P<y2021>\S+)\s+(?P<y2022>\S+)\s+"
        r"(?P<y2023>\S+)\s+(?P<y2024>\S+)$"
    )
    rows, notes = [], []
    for ln in lines:
        m = row_re.match(ln)
        if m and re.match(r"^\d+[A-Z]*(?:/[0-9A-Z]+)?$", m.group("unit")):
            row = {"Unit": m.group("unit"), "Unit name": m.group("name"), "adobe_page": adobe_page}
            for y in years:
                row[y] = to_int(m.group(f"y{y}"))
            rows.append(row)
            continue
        a = avg_re.match(ln)
        if a:
            row = {"Unit": "", "Unit name": "Statewide averages", "adobe_page": adobe_page}
            for y in years:
                row[y] = to_int(a.group(f"y{y}"))
            rows.append(row)
            continue
        if ln.startswith("*"):
            notes.append(ln)
    return pd.DataFrame(rows), notes


def parse_survival_block(block_lines: list[str], block_type: str, adobe_page: int):
    # lines: Unit name n then rows "Name 32 0.93 ± 0.04"
    row_re = re.compile(r"^(?P<name>.+?)\s+(?P<n>\d+)\s+(?P<surv>\d+(?:\.\d+)?)\s+±\s+(?P<se>\d+(?:\.\d+)?)$")
    rows = []
    for ln in block_lines:
        m = row_re.match(ln)
        if m:
            rows.append(
                {
                    "Type": block_type,
                    "Unit name": m.group("name"),
                    "n": to_int(m.group("n")),
                    "survival": to_float(m.group("surv")),
                    "SE": to_float(m.group("se")),
                    "adobe_page": adobe_page,
                }
            )
    return pd.DataFrame(rows)


def split_page20(lines: list[str]):
    starts = []
    for i, ln in enumerate(lines):
        if ln.startswith("Adult female deer survival by management unit"):
            starts.append(("adult", i))
        if ln.startswith("Fawn female deer survival by management unit"):
            starts.append(("fawn", i))
    starts = sorted(starts, key=lambda x: x[1])
    out = []
    for idx, (typ, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
        out.append((typ, lines[start:end]))
    return out


def parse_ratio_table_rows(block_lines: list[str], adobe_page: int, title: str):
    # Unit Unit name Objective 2022 2023 2024 average
    row_re = re.compile(
        r"^(?P<unit>\S+)\s+(?P<name>.+?)\s+(?P<objective>\d+–\d+)\s+"
        r"(?P<y2022>\d+)\s+(?P<y2023>\d+)\s+(?P<y2024>\d+)\s+(?P<avg>\d+)$"
    )
    rows = []
    for ln in block_lines:
        m = row_re.match(ln)
        if m:
            rows.append(
                {
                    "Title": title,
                    "Unit": m.group("unit"),
                    "Unit name": m.group("name"),
                    "Objective": m.group("objective"),
                    "2022": to_int(m.group("y2022")),
                    "2023": to_int(m.group("y2023")),
                    "2024": to_int(m.group("y2024")),
                    "3-year average": to_int(m.group("avg")),
                    "adobe_page": adobe_page,
                }
            )
    return pd.DataFrame(rows)


def split_page22(lines: list[str]):
    starts = []
    for i, ln in enumerate(lines):
        if ln.startswith("Number of postseason buck deer per 100 does for"):
            starts.append(i)
    out = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        out.append(lines[start:end])
    return out


def parse_classification_pages_25_44(lines: list[str], adobe_page: int):
    # multiple unit tables per page
    year_re = re.compile(
        r"^(?P<year>20\d{2}[–-]\d{2})\s+(?P<n>\S+)\s+(?P<f1>\S+)\s+(?P<f2>\S+)\s+(?P<b>\S+)\s+(?P<p>\S+)$"
    )
    header_prefixes = (
        "Deer postseason classification data by management unit",
        "Fawns per",
        "Year n",
        "100 does",
        "100 adults",
    )
    sections = []
    current_unit = None
    current_rows = []
    for ln in lines:
        if ln.startswith(header_prefixes):
            continue
        if ln.startswith("Page "):
            continue
        if ln.startswith("*"):
            continue
        m = year_re.match(ln)
        if m:
            if current_unit is None:
                current_unit = "UNKNOWN_UNIT"
            current_rows.append(
                {
                    "Unit block": current_unit,
                    "Year": m.group("year"),
                    "n": to_int(m.group("n")),
                    "Fawns per 100 does": to_int(m.group("f1")),
                    "Fawns per 100 adults": to_int(m.group("f2")),
                    "Bucks per 100 does": to_int(m.group("b")),
                    "% bucks > 3 pts.": to_int(m.group("p")),
                    "adobe_page": adobe_page,
                }
            )
            continue

        # new unit title line
        if current_unit is not None and current_rows:
            sections.append((current_unit, pd.DataFrame(current_rows)))
            current_rows = []
        current_unit = ln

    if current_unit is not None and current_rows:
        sections.append((current_unit, pd.DataFrame(current_rows)))
    return sections


def generic_single_table(page_obj) -> pd.DataFrame:
    # fallback for "single table per page" pages
    tbl = page_obj.extract_table(
        table_settings={
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
        }
    )
    if not tbl:
        return pd.DataFrame(columns=["line"])
    rows = []
    max_cols = max(len(r) for r in tbl if r) if tbl else 0
    for r in tbl:
        if not r:
            continue
        cells = [(c or "").replace("\n", " ").strip() for c in r]
        if any(cells):
            cells = cells + [""] * (max_cols - len(cells))
            rows.append(cells)
    if not rows:
        return pd.DataFrame(columns=["line"])
    header = rows[0]
    cols = []
    seen = {}
    for i, h in enumerate(header):
        base = h if h else f"col_{i+1}"
        seen[base] = seen.get(base, 0) + 1
        cols.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return pd.DataFrame(rows[1:], columns=cols)


def main():
    parser = argparse.ArgumentParser(description="Final structured extraction for Pages from 24_bg_report-2.")
    parser.add_argument("pdf_path", nargs="?", default=PDF_DEFAULT)
    parser.add_argument(
        "--out-dir",
        default="pipeline/RAW/hunt_unit_database/2025/formatted_tables/pages_from_24_bg_report_2_final_extract",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    pages = load_pages(pdf_path)

    # 1) General season combined single table pages 1 + 3-5
    gs_frames, gs_notes = [], []
    for p in [1, 3, 4, 5]:
        df, notes = parse_general_or_cwmu_buck(pages[p], p, "Hunt name")
        df["table_title"] = pages[p][0] if pages[p] else ""
        gs_frames.append(df)
        gs_notes.extend([f"p{p}: {n}" for n in notes])
    gs_df = pd.concat(gs_frames, ignore_index=True)
    c, x = write_table(out_dir, "TABLE_GENERAL_SEASON_DEER_PAGES_001_003_004_005", gs_df, gs_notes)
    manifest.append({"table_id": "TABLE_GENERAL_SEASON_DEER_PAGES_001_003_004_005", "pages": "1,3,4,5", "csv": c, "xlsx": x, "rows": len(gs_df), "mode": "multi_page_single_table"})

    # 2) CWMU buck combined pages 10-12
    cwmu_buck_frames = []
    for p in [10, 11, 12]:
        df, notes = parse_general_or_cwmu_buck(pages[p], p, "CWMU name")
        cwmu_buck_frames.append(df)
    cwmu_buck_df = pd.concat(cwmu_buck_frames, ignore_index=True)
    c, x = write_table(out_dir, "TABLE_CWMU_BUCK_PAGES_010_011_012", cwmu_buck_df, None)
    manifest.append({"table_id": "TABLE_CWMU_BUCK_PAGES_010_011_012", "pages": "10,11,12", "csv": c, "xlsx": x, "rows": len(cwmu_buck_df), "mode": "multi_page_single_table"})

    # 3) CWMU antlerless page 14
    p14_df, p14_notes = parse_cwmu_antlerless(pages[14], 14)
    c, x = write_table(out_dir, "TABLE_CWMU_ANTLERLESS_PAGE_014", p14_df, p14_notes)
    manifest.append({"table_id": "TABLE_CWMU_ANTLERLESS_PAGE_014", "pages": "14", "csv": c, "xlsx": x, "rows": len(p14_df), "mode": "single_page_single_table"})

    # 4) Fawn per 100 does combined pages 23-24
    p23_df, p23_notes = parse_fawn_100(pages[23], 23)
    p24_df, p24_notes = parse_fawn_100(pages[24], 24)
    fawn_df = pd.concat([p23_df, p24_df], ignore_index=True)
    fawn_notes = [*p23_notes, *p24_notes]
    c, x = write_table(out_dir, "TABLE_POSTSEASON_FAWN_PER_100_DOES_PAGES_023_024", fawn_df, fawn_notes)
    manifest.append({"table_id": "TABLE_POSTSEASON_FAWN_PER_100_DOES_PAGES_023_024", "pages": "23,24", "csv": c, "xlsx": x, "rows": len(fawn_df), "mode": "multi_page_single_table"})

    # 5) multi-table pages 20 and 22
    for typ, block in split_page20(pages[20]):
        df = parse_survival_block(block, typ.upper(), 20)
        base = f"ADOBE_PAGE_020_TABLE_{typ.upper()}"
        c, x = write_table(out_dir, base, df, None)
        manifest.append({"table_id": base, "pages": "20", "csv": c, "xlsx": x, "rows": len(df), "mode": "multi_table_page"})

    for idx, block in enumerate(split_page22(pages[22]), start=1):
        title = block[0] if block else f"page22_table_{idx}"
        df = parse_ratio_table_rows(block, 22, title)
        base = f"ADOBE_PAGE_022_TABLE_{idx:02d}"
        c, x = write_table(out_dir, base, df, None)
        manifest.append({"table_id": base, "pages": "22", "csv": c, "xlsx": x, "rows": len(df), "mode": "multi_table_page"})

    # 6) pages 25-44 multi-table per page (unit blocks)
    for p in range(25, 45):
        sections = parse_classification_pages_25_44(pages[p], p)
        for idx, (unit_name, df) in enumerate(sections, start=1):
            safe = re.sub(r"[^A-Za-z0-9]+", "_", unit_name).strip("_")[:50].upper() or "UNIT"
            base = f"ADOBE_PAGE_{p:03d}_TABLE_{idx:02d}_{safe}"
            c, x = write_table(out_dir, base, df, None)
            manifest.append({"table_id": base, "pages": str(p), "csv": c, "xlsx": x, "rows": len(df), "mode": "multi_table_page", "unit_block": unit_name})

    # 7) all other pages single table per page (excluding already covered groups)
    covered = {1, 3, 4, 5, 10, 11, 12, 14, 20, 22, *range(23, 45)}
    with pdfplumber.open(str(pdf_path)) as doc:
        for p in range(1, len(doc.pages) + 1):
            if p in covered:
                continue
            df = generic_single_table(doc.pages[p - 1])
            base = f"ADOBE_PAGE_{p:03d}_SINGLE_TABLE"
            c, x = write_table(out_dir, base, df, None)
            manifest.append({"table_id": base, "pages": str(p), "csv": c, "xlsx": x, "rows": len(df), "mode": "single_table_page"})

    manifest_df = pd.DataFrame(manifest)
    manifest_csv = out_dir / "final_extract_manifest.csv"
    manifest_xlsx = out_dir / "final_extract_manifest.xlsx"
    manifest_json = out_dir / "final_extract_manifest.json"
    report_txt = out_dir / "final_extract_report.txt"
    manifest_df.to_csv(manifest_csv, index=False, encoding="utf-8")
    manifest_df.to_excel(manifest_xlsx, index=False)
    manifest_df.to_json(manifest_json, orient="records", indent=2, force_ascii=False)
    report_txt.write_text(
        "\n".join(
            [
                "Final extraction summary",
                "========================",
                f"source_pdf: {pdf_path}",
                f"tables_written: {len(manifest_df)}",
                "rules:",
                "- general season pages 1,3,4,5 combined single table",
                "- CWMU buck pages 10-12 combined single table",
                "- CWMU antlerless page 14 single table",
                "- fawn per 100 does pages 23-24 combined single table",
                "- pages 20,22,25-44 split as multiple tables per page",
                "- all other pages extracted as single table/page",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "source_pdf": str(pdf_path),
                "out_dir": str(out_dir),
                "tables_written": int(len(manifest_df)),
                "manifest_csv": str(manifest_csv),
                "manifest_xlsx": str(manifest_xlsx),
                "manifest_json": str(manifest_json),
                "report_txt": str(report_txt),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

