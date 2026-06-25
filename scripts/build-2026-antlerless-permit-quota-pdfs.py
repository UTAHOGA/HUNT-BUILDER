from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
RAW_PDF_DIR = ROOT / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2026_PERMITS=2027_MODEL"
FAMILY_PDF_DIR = ROOT / "outputs" / "2026_PERMITS=2027_MODEL_species_family_docs" / "pdf"
AUDIT_DIR = ROOT / "audits" / "2026_live_source_comparison"
SOURCE_MAP_CSV = AUDIT_DIR / "antlerless_pdf_2026_hunt_code_sources.csv"
MANIFEST_CSV = AUDIT_DIR / "antlerless_pdf_2026_manifest.csv"
MANIFEST_JSON = AUDIT_DIR / "antlerless_pdf_2026_manifest.json"

DWR_LOGO = ROOT / "assets" / "logos" / "DWR-LOGO-SHIELD.png"
UOGA_LOGO = ROOT / "assets" / "logos" / "UOGA-LOGO-CIRCLE.png"
TOPO = ROOT / "assets" / "backgrounds" / "tan topo.png"

PAGE_SIZE = landscape(letter)
PAGE_W, PAGE_H = PAGE_SIZE
CREAM = colors.HexColor("#F7EEDC")
DARK = colors.HexColor("#2A1604")
ORANGE = colors.HexColor("#F27405")
HEADER_TAN = colors.HexColor("#F5D9A8")
GRID = colors.HexColor("#8A704F")
TEXT = colors.HexColor("#1E160F")

ANTLERLESS_GROUPS = {
    ("Deer", "Antlerless"): "ANTLERLESS DEER PERMIT NUMBERS",
    ("Elk", "Antlerless"): "ANTLERLESS ELK PERMIT NUMBERS",
    ("Moose", "Antlerless"): "ANTLERLESS MOOSE PERMIT NUMBERS",
    ("Pronghorn", "Doe"): "DOE PRONGHORN PERMIT NUMBERS",
    ("Rocky Mountain Bighorn Sheep", "Ewe"): "EWE ROCKY MTN SHEEP PERMIT NUMBERS",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def pdf_name(title: str) -> str:
    return f"2026_PERMITS=2027_MODEL__{title}.pdf"


def as_int(value: str) -> int:
    try:
        return int(float(clean(value).replace(",", "")))
    except ValueError:
        return 0


def load_permit_reference_rows() -> list[dict[str, str]]:
    with CANONICAL.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    permit_reference_rows = []
    seen_codes = set()
    for row in rows:
        if clean(row.get("record_type")) not in {"hunt_planner_permit_reference", "hunt_planner_permit_quota"}:
            continue
        key = (clean(row.get("hunt_code")), clean(row.get("species")), clean(row.get("sex_type")))
        if key in seen_codes:
            continue
        seen_codes.add(key)
        permit_reference_rows.append(row)
    return sorted(
        permit_reference_rows,
        key=lambda row: (
            clean(row.get("species")),
            clean(row.get("sex_type")),
            clean(row.get("hunt_code")),
            clean(row.get("hunt_name")),
        ),
    )


def group_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        title = ANTLERLESS_GROUPS.get((clean(row.get("species")), clean(row.get("sex_type"))))
        if not title:
            continue
        grouped[title].append(row)
    grouped["ANTLERLESS PERMIT NUMBER SUMMARY"] = rows
    return dict(grouped)


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(clean(text).replace("&", "&amp;"), style)


def draw_background(canvas, doc, title: str) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        canvas.drawImage(str(TOPO), 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")
        canvas.setFillAlpha(0.82)
        canvas.setFillColor(CREAM)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillAlpha(1)

    canvas.setStrokeColor(DARK)
    canvas.setLineWidth(2.4)
    canvas.roundRect(17, 17, PAGE_W - 34, PAGE_H - 34, 20, stroke=1, fill=0)
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.8)
    canvas.roundRect(27, 27, PAGE_W - 54, PAGE_H - 54, 17, stroke=1, fill=0)

    canvas.setFillColor(DARK)
    canvas.roundRect(32, PAGE_H - 92, PAGE_W - 64, 65, 12, stroke=0, fill=1)
    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1.8)
    canvas.roundRect(32, PAGE_H - 92, PAGE_W - 64, 65, 12, stroke=1, fill=0)

    if DWR_LOGO.exists():
        canvas.drawImage(str(DWR_LOGO), 45, PAGE_H - 86, width=50, height=50, preserveAspectRatio=True, mask="auto")
    if UOGA_LOGO.exists():
        canvas.drawImage(str(UOGA_LOGO), PAGE_W - 120, PAGE_H - 86, width=58, height=58, preserveAspectRatio=True, mask="auto")
        canvas.saveState()
        canvas.setFillAlpha(0.055)
        canvas.drawImage(str(UOGA_LOGO), PAGE_W / 2 - 150, PAGE_H / 2 - 150, width=300, height=300, mask="auto")
        canvas.restoreState()

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 54, "Utah DWR 2026 Permit Numbers")
    canvas.setFillColor(ORANGE)
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 72, "Brought to you by Utah Outfitter and Guide Assn. (U.O.G.A)")
    canvas.drawRightString(PAGE_W - 170, PAGE_H - 54, "06/22/2026")
    canvas.drawRightString(PAGE_W - 170, PAGE_H - 72, f"Page {doc.page}")

    canvas.setFillColor(TEXT)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(43, PAGE_H - 112, title.title().replace("Mtn", "Mtn."))
    canvas.setFont("Helvetica", 8.4)
    canvas.drawString(43, PAGE_H - 127, "2026 Permit Numbers | Hunt Planner | Non-scorable display/feed rows")

    canvas.setFillColor(ORANGE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawRightString(PAGE_W - 43, 30, "WILDLIFE ELEVATED")
    canvas.setFillColor(TEXT)
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(43, 30, "Source: Utah DWR Hunt Planner permit-number data. Reconstructed for UOGA Hunt Builder research.")
    canvas.restoreState()


def build_table(rows: list[dict[str, str]]) -> Table:
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=6.2, leading=7.2, textColor=TEXT)
    header = [
        "Hunt Code",
        "Hunt Name",
        "Sex",
        "Species",
        "Weapon",
        "Season Dates",
        "Boundary",
        "Res",
        "NR",
        "Total",
    ]
    data = [header]
    for row in rows:
        data.append(
            [
                clean(row.get("hunt_code")),
                para(clean(row.get("hunt_name")), small),
                para(clean(row.get("sex_type")), small),
                para(clean(row.get("species")), small),
                para(clean(row.get("weapon")), small),
                para(clean(row.get("season")), small),
                clean(row.get("boundary_id")),
                clean(row.get("permits_2026_res")),
                clean(row.get("permits_2026_nr")),
                clean(row.get("permits_2026_total")),
            ]
        )
    table = Table(
        data,
        colWidths=[0.64 * inch, 1.45 * inch, 0.66 * inch, 0.92 * inch, 1.13 * inch, 1.74 * inch, 0.55 * inch, 0.42 * inch, 0.42 * inch, 0.46 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 6.5),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 6.2),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF8EA")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF8EA"), colors.HexColor("#F4E8CF")]),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (6, 1), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_summary_cards(rows: list[dict[str, str]]) -> Table:
    totals = [
        ["Hunts", len(rows)],
        ["Resident permits", sum(as_int(row.get("permits_2026_res", "")) for row in rows)],
        ["Nonresident permits", sum(as_int(row.get("permits_2026_nr", "")) for row in rows)],
        ["Total permits", sum(as_int(row.get("permits_2026_total", "")) for row in rows)],
    ]
    table = Table(totals, colWidths=[1.35 * inch, 0.8 * inch] * 2)
    two_col = []
    for index in range(0, len(totals), 2):
        left = totals[index]
        right = totals[index + 1] if index + 1 < len(totals) else ["", ""]
        two_col.append(left + right)
    table = Table(two_col, colWidths=[1.2 * inch, 0.55 * inch, 1.35 * inch, 0.55 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HEADER_TAN),
                ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
            ]
        )
    )
    return table


def render_pdf(title: str, rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=PAGE_SIZE,
        leftMargin=0.54 * inch,
        rightMargin=0.54 * inch,
        topMargin=1.82 * inch,
        bottomMargin=0.55 * inch,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        textColor=DARK,
    )
    note_style = ParagraphStyle(
        "note",
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4D4030"),
    )
    story = [
        Paragraph("Permit-number summary by hunt code. These rows are display/feed rows and are not point-level draw odds results.", subtitle_style),
        Spacer(1, 0.07 * inch),
        build_summary_cards(rows),
        Spacer(1, 0.09 * inch),
        build_table(rows),
        Spacer(1, 0.05 * inch),
        Paragraph("Do not route these permit-reference rows through the prediction engine as applicant point ladders.", note_style),
    ]
    doc.build(story, onFirstPage=lambda c, d: draw_background(c, d, title), onLaterPages=lambda c, d: draw_background(c, d, title))


def write_manifest(manifest: list[dict[str, object]], grouped: dict[str, list[dict[str, str]]]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "title",
                "raw_pdf",
                "family_pdf",
                "hunt_count",
                "resident_permits",
                "nonresident_permits",
                "total_permits",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest)
    source_rows = []
    by_code: dict[str, list[str]] = defaultdict(list)
    for title, rows in grouped.items():
        file_name = pdf_name(title)
        for row in rows:
            by_code[clean(row.get("hunt_code"))].append(file_name)
    for code, sources in sorted(by_code.items()):
        source_rows.append(
            {
                "hunt_code": code,
                "prefix": code[:2],
                "source_count": len(sources),
                "sources": "; ".join(sorted(set(sources))),
            }
        )
    with SOURCE_MAP_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hunt_code", "prefix", "source_count", "sources"])
        writer.writeheader()
        writer.writerows(source_rows)
    MANIFEST_JSON.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "canonical": str(CANONICAL),
                "raw_pdf_dir": str(RAW_PDF_DIR),
                "family_pdf_dir": str(FAMILY_PDF_DIR),
                "manifest": manifest,
                "source_map": str(SOURCE_MAP_CSV),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    rows = load_permit_reference_rows()
    grouped = group_rows(rows)
    manifest: list[dict[str, object]] = []
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    FAMILY_PDF_DIR.mkdir(parents=True, exist_ok=True)
    for title, group in sorted(grouped.items()):
        raw_output = RAW_PDF_DIR / pdf_name(title)
        family_output = FAMILY_PDF_DIR / pdf_name(title)
        render_pdf(title, group, raw_output)
        shutil.copyfile(raw_output, family_output)
        manifest.append(
            {
                "title": title,
                "raw_pdf": str(raw_output),
                "family_pdf": str(family_output),
                "hunt_count": len(group),
                "resident_permits": sum(as_int(row.get("permits_2026_res", "")) for row in group),
                "nonresident_permits": sum(as_int(row.get("permits_2026_nr", "")) for row in group),
                "total_permits": sum(as_int(row.get("permits_2026_total", "")) for row in group),
            }
        )
    write_manifest(manifest, grouped)
    print(json.dumps({"pdfs_created": len(manifest), "rows": len(rows), "manifest": str(MANIFEST_CSV)}, indent=2))


if __name__ == "__main__":
    main()
