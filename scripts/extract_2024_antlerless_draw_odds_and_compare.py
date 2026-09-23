from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pdfplumber


DRAW_PDF_CANDIDATES = [
    Path(r"pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf"),
]
OUT_DIR = Path(
    r"pipeline/RAW/hunt_unit_database/2025/formatted_tables/draw_odds_results/antlerless_draw_odds_2024_extract"
)

# Active antlerless harvest extracts available in this repo run.
HARVEST_SOURCES = [
    Path(
        r"pipeline/RAW/hunt_unit_database/2025/formatted_tables/elk_antlerless_general_season_2024_extract/ELK_ANTLERLESS_GENERAL_SEASON_2024.csv"
    ),
    Path(
        r"pipeline/RAW/hunt_unit_database/2025/formatted_tables/elk_limited_antlerless_2024_extract/ELK_LIMITED_ANTLERLESS_HARVEST_2024.csv"
    ),
]

HUNT_RE = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+)")
TOTALS_RE = re.compile(
    r"Totals\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(?:1 in [\d.,]+|N/A)\s+"
    r"Totals\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(?:1 in [\d.,]+|N/A)",
    re.IGNORECASE,
)


@dataclass
class DrawOddsRow:
    source_file: str
    source_page: int
    hunt_code: str
    hunt_name: str
    species_category: str
    res_applicants: int
    res_bonus_permits: int
    res_regular_permits: int
    res_total_permits: int
    nr_applicants: int
    nr_bonus_permits: int
    nr_regular_permits: int
    nr_total_permits: int
    permits_total_draw_results: int
    raw_hunt_line: str
    raw_totals_line: str


def to_int(value: str) -> int:
    return int(str(value).replace(",", "").strip())


def parse_species_from_name(hunt_name: str) -> str:
    name = hunt_name.lower()
    if "antlerless deer" in name:
        return "Antlerless Deer"
    if "antlerless elk" in name:
        return "Antlerless Elk"
    if "doe pronghorn" in name:
        return "Doe Pronghorn"
    if "antlerless moose" in name:
        return "Antlerless Moose"
    if "ewe" in name:
        return "Ewe Bighorn"
    return "Other Antlerless"


def resolve_draw_pdf() -> Path:
    for p in DRAW_PDF_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No antlerless draw PDF found. Checked: "
        + ", ".join(str(p).replace("\\", "/") for p in DRAW_PDF_CANDIDATES)
    )


def parse_draw_pdf() -> list[DrawOddsRow]:
    draw_pdf = resolve_draw_pdf()
    rows: list[DrawOddsRow] = []
    with pdfplumber.open(draw_pdf) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if "Hunt:" not in text:
                continue
            hunt_match = HUNT_RE.search(text)
            totals_match = TOTALS_RE.search(" ".join(text.split()))
            if not hunt_match or not totals_match:
                continue

            hunt_code = hunt_match.group(1).strip().upper()
            hunt_name = hunt_match.group(2).strip()
            raw_hunt_line = f"Hunt: {hunt_code} {hunt_name}"
            raw_totals_line = totals_match.group(0)

            res_app = to_int(totals_match.group(1))
            res_bonus = to_int(totals_match.group(2))
            res_reg = to_int(totals_match.group(3))
            res_tot = to_int(totals_match.group(4))
            nr_app = to_int(totals_match.group(5))
            nr_bonus = to_int(totals_match.group(6))
            nr_reg = to_int(totals_match.group(7))
            nr_tot = to_int(totals_match.group(8))

            rows.append(
                DrawOddsRow(
                    source_file=str(draw_pdf).replace("\\", "/"),
                    source_page=page_idx,
                    hunt_code=hunt_code,
                    hunt_name=hunt_name,
                    species_category=parse_species_from_name(hunt_name),
                    res_applicants=res_app,
                    res_bonus_permits=res_bonus,
                    res_regular_permits=res_reg,
                    res_total_permits=res_tot,
                    nr_applicants=nr_app,
                    nr_bonus_permits=nr_bonus,
                    nr_regular_permits=nr_reg,
                    nr_total_permits=nr_tot,
                    permits_total_draw_results=res_tot + nr_tot,
                    raw_hunt_line=raw_hunt_line,
                    raw_totals_line=raw_totals_line,
                )
            )
    return rows


def load_harvest_antlerless_permits() -> tuple[pd.DataFrame, dict[str, list[dict[str, str]]]]:
    rows: list[dict[str, str]] = []
    for src in HARVEST_SOURCES:
        if not src.exists():
            continue
        df = pd.read_csv(src, dtype=str).fillna("")
        if "Hunt number" not in df.columns or "Permits" not in df.columns:
            continue
        for _, r in df.iterrows():
            code = str(r.get("Hunt number", "")).strip().upper()
            if not re.match(r"^[A-Z]{2}\d{4}$", code):
                continue
            rows.append(
                {
                    "source_file": str(src).replace("\\", "/"),
                    "hunt_code": code,
                    "hunt_name_harvest": str(r.get("Hunt name", "")).strip(),
                    "permits_harvest": str(r.get("Permits", "")).strip(),
                }
            )
    harvest_df = pd.DataFrame(rows)
    by_code: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        by_code.setdefault(r["hunt_code"], []).append(r)
    return harvest_df, by_code


def compare(draw_rows: list[DrawOddsRow], harvest_by_code: dict[str, list[dict[str, str]]]) -> pd.DataFrame:
    out_rows: list[dict[str, str | int]] = []
    for r in draw_rows:
        hits = harvest_by_code.get(r.hunt_code, [])
        if not hits:
            out_rows.append(
                {
                    "hunt_code": r.hunt_code,
                    "species_category": r.species_category,
                    "hunt_name_draw": r.hunt_name,
                    "draw_res_permits": r.res_total_permits,
                    "draw_nr_permits": r.nr_total_permits,
                    "draw_total_permits": r.permits_total_draw_results,
                    "harvest_permits": "",
                    "harvest_source_file": "",
                    "comparison_status": "missing_in_harvest_extracts",
                }
            )
            continue

        # Prefer exact permit match if any exists; otherwise first row.
        selected = hits[0]
        draw_total = r.permits_total_draw_results
        status = "mismatch"
        for h in hits:
            try:
                hp = int(str(h["permits_harvest"]).strip())
            except Exception:
                continue
            if hp == draw_total:
                selected = h
                status = "matched"
                break

        harvest_permits = selected.get("permits_harvest", "")
        try:
            hp_int = int(str(harvest_permits).strip())
            if status != "matched":
                status = "matched" if hp_int == draw_total else "mismatch"
        except Exception:
            status = "invalid_harvest_permits"

        out_rows.append(
            {
                "hunt_code": r.hunt_code,
                "species_category": r.species_category,
                "hunt_name_draw": r.hunt_name,
                "draw_res_permits": r.res_total_permits,
                "draw_nr_permits": r.nr_total_permits,
                "draw_total_permits": draw_total,
                "harvest_permits": harvest_permits,
                "harvest_hunt_name": selected.get("hunt_name_harvest", ""),
                "harvest_source_file": selected.get("source_file", ""),
                "comparison_status": status,
            }
        )
    return pd.DataFrame(out_rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    draw_rows = parse_draw_pdf()
    if not draw_rows:
        raise RuntimeError("No hunt rows parsed from draw odds PDF.")

    draw_df = pd.DataFrame([asdict(r) for r in draw_rows]).sort_values(["hunt_code", "source_page"])
    harvest_df, harvest_by_code = load_harvest_antlerless_permits()
    compare_df = compare(draw_rows, harvest_by_code).sort_values(["comparison_status", "hunt_code"])

    draw_csv = OUT_DIR / "ANTLERLESS_DRAW_ODDS_2024_PERMIT_TOTALS.csv"
    draw_xlsx = OUT_DIR / "ANTLERLESS_DRAW_ODDS_2024_PERMIT_TOTALS.xlsx"
    harvest_csv = OUT_DIR / "ANTLERLESS_HARVEST_PERMITS_REFERENCE_2024.csv"
    compare_csv = OUT_DIR / "ANTLERLESS_DRAW_VS_HARVEST_PERMIT_CHECK_2024.csv"
    compare_xlsx = OUT_DIR / "ANTLERLESS_DRAW_VS_HARVEST_PERMIT_CHECK_2024.xlsx"
    report_json = OUT_DIR / "antlerless_draw_vs_harvest_check_2024_report.json"

    draw_df.to_csv(draw_csv, index=False, encoding="utf-8-sig")
    draw_df.to_excel(draw_xlsx, index=False)
    harvest_df.to_csv(harvest_csv, index=False, encoding="utf-8-sig")
    compare_df.to_csv(compare_csv, index=False, encoding="utf-8-sig")
    compare_df.to_excel(compare_xlsx, index=False)

    status_counts = compare_df["comparison_status"].value_counts().to_dict()
    report = {
        "source_draw_pdf": str(resolve_draw_pdf()).replace("\\", "/"),
        "harvest_sources": [str(p).replace("\\", "/") for p in HARVEST_SOURCES if p.exists()],
        "draw_rows_parsed": int(len(draw_df)),
        "draw_unique_hunt_codes": int(draw_df["hunt_code"].nunique()),
        "draw_species_prefix_counts": (
            draw_df["hunt_code"].str[:2].value_counts().to_dict() if not draw_df.empty else {}
        ),
        "harvest_rows_loaded": int(len(harvest_df)),
        "harvest_unique_hunt_codes": int(harvest_df["hunt_code"].nunique()) if not harvest_df.empty else 0,
        "comparison_rows": int(len(compare_df)),
        "comparison_status_counts": status_counts,
    }
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote {draw_csv}")
    print(f"Wrote {draw_xlsx}")
    print(f"Wrote {harvest_csv}")
    print(f"Wrote {compare_csv}")
    print(f"Wrote {compare_xlsx}")
    print(f"Wrote {report_json}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
