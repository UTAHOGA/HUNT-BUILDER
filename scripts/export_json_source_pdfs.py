#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = (
    ROOT
    / "audits"
    / "2025_canonical_finalization"
    / "fresh_live_pulls_20260621_192945"
)
OUT_DIR = ROOT / "outputs" / "2026_PERMITS=2027_MODEL_json_documents"

TRACKED_TERMS = [
    "bison",
    "black_bear",
    "cougar",
    "deer",
    "desert_bighorn_sheep",
    "elk",
    "moose",
    "mountain_goat",
    "pronghorn",
    "rocky_mountain_bighorn_sheep",
    "rocky_mtn_bighorn_sheep",
    "sportsman",
    "tribal",
    "turkey",
]
SKIP_TERMS = [
    "coyote",
    "goose",
    "grouse",
    "sandhill_crane",
    "sharp_tailed",
    "swan",
    "waterfowl",
    "hasetup",
]


def is_tracked_file(path: Path) -> bool:
    lower = path.name.lower()
    if path.suffix.lower() != ".json":
        return False
    if "summary" in lower or "supplement" in lower:
        return False
    if any(term in lower for term in SKIP_TERMS):
        return False
    return any(term in lower for term in TRACKED_TERMS)


def clean_name(name: str) -> str:
    name = re.sub(r"\.json$", "", name, flags=re.I)
    name = re.sub(r"^utahdraws_", "", name)
    name = re.sub(r"^dwr_huntboundary_", "huntboundary_", name)
    name = re.sub(r"[^A-Za-z0-9=._-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def source_kind(name: str) -> str:
    if name.startswith("utahdraws_"):
        return "UtahDraws draw odds"
    if name.startswith("dwr_huntboundary_"):
        return "DWR HuntBoundary metadata"
    return "Reference/audit JSON"


def data_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("Data", "data", "rows", "Results", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def hunt_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return scalar(row[key])
    return ""


def wrap(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(scalar(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def build_summary(rows: list[dict[str, Any]], source_file: str) -> list[list[str]]:
    hunt_codes = {
        hunt_value(row, "HuntCode", "HUNT_NUMBER", "hunt_code", "huntNumber")
        for row in rows
        if hunt_value(row, "HuntCode", "HUNT_NUMBER", "hunt_code", "huntNumber")
    }
    odds_rows = sum(len(row.get("OddsList") or []) for row in rows if isinstance(row.get("OddsList"), list))
    season_rows = sum(
        len(row.get("SeasonWeapons") or []) for row in rows if isinstance(row.get("SeasonWeapons"), list)
    )
    license_years = sorted(
        {
            str(item.get("LicenseYear"))
            for row in rows
            for item in (row.get("SeasonWeapons") or [])
            if isinstance(item, dict) and item.get("LicenseYear") is not None
        }
    )
    return [
        ["Source file", source_file],
        ["Source kind", source_kind(source_file)],
        ["Hunt records", str(len(rows))],
        ["Unique hunt codes", str(len(hunt_codes))],
        ["Odds/applicant rows", str(odds_rows)],
        ["Season/weapon rows", str(season_rows)],
        ["License years", ", ".join(license_years)],
        ["Use note", "Document export only. Not ingested into canonical prediction truth."],
    ]


def hunt_table(rows: list[dict[str, Any]], body_style: ParagraphStyle) -> list[list[Any]]:
    table_rows: list[list[Any]] = [
        ["Hunt Code", "Hunt Name", "Category", "Species", "Res Quota", "NR Quota", "Total Quota", "Odds Rows"]
    ]
    for row in rows[:200]:
        odds_count = len(row.get("OddsList") or []) if isinstance(row.get("OddsList"), list) else ""
        table_rows.append(
            [
                wrap(hunt_value(row, "HuntCode", "HUNT_NUMBER", "hunt_code", "huntNumber"), body_style),
                wrap(hunt_value(row, "HuntName", "HUNT_NAME", "hunt_name", "Name"), body_style),
                wrap(hunt_value(row, "HuntCategoryName", "category"), body_style),
                wrap(hunt_value(row, "SpeciesSubtypeName", "species", "SPECIES"), body_style),
                wrap(hunt_value(row, "ResidentQuotaQuantity"), body_style),
                wrap(hunt_value(row, "NonResidentQuotaQuantity"), body_style),
                wrap(hunt_value(row, "QuotaQuantity"), body_style),
                wrap(odds_count, body_style),
            ]
        )
    return table_rows


def season_table(rows: list[dict[str, Any]], body_style: ParagraphStyle) -> list[list[Any]]:
    table_rows: list[list[Any]] = [["Hunt Code", "Weapon", "Season Start", "Season End", "License Year"]]
    for row in rows:
        for item in row.get("SeasonWeapons") or []:
            if not isinstance(item, dict):
                continue
            table_rows.append(
                [
                    wrap(hunt_value(row, "HuntCode", "HUNT_NUMBER", "hunt_code", "huntNumber"), body_style),
                    wrap(item.get("WeaponName", ""), body_style),
                    wrap(item.get("SeasonStartDate", ""), body_style),
                    wrap(item.get("SeasonEndDate", ""), body_style),
                    wrap(item.get("LicenseYear", ""), body_style),
                ]
            )
            if len(table_rows) >= 150:
                return table_rows
    return table_rows


def odds_table(rows: list[dict[str, Any]], body_style: ParagraphStyle) -> list[list[Any]]:
    table_rows: list[list[Any]] = [["Hunt Code", "Residency", "Point", "Applicants", "Successful", "Regular", "Max"]]
    for row in rows:
        for item in row.get("OddsList") or []:
            if not isinstance(item, dict):
                continue
            table_rows.append(
                [
                    wrap(hunt_value(row, "HuntCode", "HUNT_NUMBER", "hunt_code", "huntNumber"), body_style),
                    wrap(item.get("ResidencyTypeID", ""), body_style),
                    wrap(item.get("Point", item.get("PreferencePoint", "")), body_style),
                    wrap(item.get("ParticipantCount", ""), body_style),
                    wrap(item.get("SuccessfulCount", ""), body_style),
                    wrap(item.get("SuccessfulByRegularRoundCount", ""), body_style),
                    wrap(item.get("SuccessfulByMaxPointRoundCount", ""), body_style),
                ]
            )
            if len(table_rows) >= 150:
                return table_rows
    return table_rows


def add_table(story: list[Any], rows: list[list[Any]], widths: list[float]) -> None:
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E3D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DED8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6FAF8")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))


def export_pdf(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data_rows(payload)
    stem = clean_name(path.name)
    pdf_path = OUT_DIR / f"{stem}.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=landscape(letter),
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title=stem,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HuntTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#163428"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#1F4E3D"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle("BodySmall", parent=styles["BodyText"], fontSize=7, leading=8)
    story: list[Any] = [
        Paragraph(stem.replace("_", " "), title_style),
        Paragraph("Document export only - not ingested into canonical prediction truth.", body_style),
        Spacer(1, 0.12 * inch),
        Paragraph("Summary", section_style),
    ]
    add_table(story, build_summary(rows, path.name), [1.8 * inch, 7.0 * inch])
    story.append(Paragraph("Hunt Records", section_style))
    add_table(story, hunt_table(rows, body_style), [0.85 * inch, 2.0 * inch, 1.4 * inch, 1.5 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.7 * inch])
    story.append(PageBreak())
    story.append(Paragraph("Season / Weapon Rows", section_style))
    add_table(story, season_table(rows, body_style), [1.0 * inch, 2.0 * inch, 1.8 * inch, 1.8 * inch, 1.0 * inch])
    story.append(Paragraph("Odds / Applicant Rows", section_style))
    add_table(story, odds_table(rows, body_style), [1.0 * inch, 0.8 * inch, 0.8 * inch, 1.0 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch])
    doc.build(story)
    return {
        "source_file": path.name,
        "pdf_path": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
        "hunt_records": len(rows),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tracked = sorted(path for path in SOURCE_DIR.glob("*.json") if is_tracked_file(path))
    generated = [export_pdf(path) for path in tracked]
    skipped = sorted(path.name for path in SOURCE_DIR.glob("*.json") if not is_tracked_file(path))
    manifest_path = OUT_DIR / "json_pdf_document_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "output_dir": str(OUT_DIR.relative_to(ROOT)).replace("\\", "/"),
                "generated_count": len(generated),
                "skipped_count": len(skipped),
                "generated": generated,
                "skipped": skipped,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"generated_count": len(generated), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
