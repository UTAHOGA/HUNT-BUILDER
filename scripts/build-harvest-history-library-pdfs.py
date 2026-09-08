from __future__ import annotations

import csv
import hashlib
import json
import shutil
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "normalized"
    / "harvest_quality_features_all_years_by_hunt_code.csv"
)
OUTPUT_DIR = ROOT / "output" / "pdf" / "harvest-results"
PUBLIC_DIR = ROOT / "public" / "hard-copy" / "harvest-data"
MANIFEST = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "validation"
    / "harvest_library_reports_2017_2025.json"
)
UOGA_LOGO = ROOT / "assets" / "logos" / "UOGA-LOGO-CIRCLE.png"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
YEARS = tuple(range(2017, 2026))

DWR_REPORTS_URL = "https://wildlife.utah.gov/biggame/reports"
DWR_REPORT_INDEX_URL = "https://wildlife.utah.gov/hunting/reports"
DWR_2025_ACCESSED = "2026-09-02"

PAGE_SIZE = landscape(letter)
PAGE_W, PAGE_H = PAGE_SIZE
CREAM = colors.HexColor("#F6EBD7")
DARK = colors.HexColor("#2B1708")
ORANGE = colors.HexColor("#F07800")
PALE = colors.HexColor("#FFF9ED")
ALT = colors.HexColor("#F1E2C8")
GRID = colors.HexColor("#8D714B")
TEXT = colors.HexColor("#24180F")
MUTED = colors.HexColor("#5C4A39")

SPECIES_ORDER = {
    "Elk": 1,
    "Antlerless Elk": 2,
    "Deer": 3,
    "Mule Deer": 3,
    "Antlerless Deer": 4,
    "Pronghorn": 5,
    "Moose": 6,
    "Bison": 7,
    "Mountain Goat": 8,
    "Desert Bighorn Sheep": 9,
    "Rocky Mountain Bighorn Sheep": 10,
    "Black Bear": 11,
    "Wild Turkey": 12,
}


def clean(value: object) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    for source, replacement in {
        "\u2013": "-",
        "\u2014": "-",
        "\u2011": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufffd": "-",
    }.items():
        text = text.replace(source, replacement)
    return text


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def display(value: object, decimals: int = 0, suffix: str = "") -> str:
    parsed = number(value)
    if parsed is None:
        return "-"
    if decimals == 0:
        rendered = f"{parsed:,.0f}"
    else:
        rendered = f"{parsed:,.{decimals}f}".rstrip("0").rstrip(".")
    return rendered + suffix


def para(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=22, leading=25,
            textColor=DARK, alignment=TA_CENTER, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
            textColor=ORANGE, alignment=TA_CENTER, spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "section", fontName="Helvetica-Bold", fontSize=12.5, leading=15,
            textColor=DARK, spaceBefore=4, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=8.1, leading=10.3,
            textColor=TEXT, spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "note", fontName="Helvetica", fontSize=6.8, leading=8.6,
            textColor=MUTED, spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "cell", fontName="Helvetica", fontSize=5.15, leading=6.0,
            textColor=TEXT,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold", fontName="Helvetica-Bold", fontSize=5.2, leading=6.1,
            textColor=TEXT,
        ),
    }


def read_rows() -> dict[int, list[dict[str, str]]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            year = int(row["reported_hunt_year"])
            if year in YEARS:
                grouped[year].append(row)
    missing = [year for year in YEARS if not grouped[year]]
    if missing:
        raise RuntimeError(f"Missing harvest rows for years: {missing}")
    return dict(grouped)


def species_groups(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("species")) or "Unclassified"].append(row)
    for species_rows in grouped.values():
        species_rows.sort(key=lambda row: (clean(row.get("hunt_code")), clean(row.get("hunt_name"))))
    return sorted(grouped.items(), key=lambda item: (SPECIES_ORDER.get(item[0], 99), item[0]))


def source_inventory(rows: list[dict[str, str]], prefix: str, file_field: str, page_field: str) -> tuple[dict[str, str], list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        source_file = clean(row.get(file_field))
        if source_file:
            grouped[source_file].append(row)
    mapping: dict[str, str] = {}
    inventory: list[dict[str, object]] = []
    for index, source_file in enumerate(sorted(grouped), start=1):
        source_id = f"{prefix}{index:02d}"
        mapping[source_file] = source_id
        pages = sorted({clean(row.get(page_field)) for row in grouped[source_file] if clean(row.get(page_field))})
        inventory.append(
            {
                "id": source_id,
                "file": source_file,
                "pages": ", ".join(pages) if pages else "not stated",
                "rows": len(grouped[source_file]),
            }
        )
    return mapping, inventory


def page_background(canvas, doc, report_title: str, status: str) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        canvas.saveState()
        canvas.setFillAlpha(0.055)
        canvas.drawImage(str(TOPO), 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")
        canvas.restoreState()
    canvas.setFillColor(DARK)
    canvas.rect(0, PAGE_H - 58, PAGE_W, 58, fill=1, stroke=0)
    canvas.setFillColor(ORANGE)
    canvas.rect(0, PAGE_H - 62, PAGE_W, 4, fill=1, stroke=0)
    if UOGA_LOGO.exists():
        canvas.drawImage(str(UOGA_LOGO), 24, PAGE_H - 53, width=43, height=43, preserveAspectRatio=True, mask="auto")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(78, PAGE_H - 29, report_title)
    canvas.setFont("Helvetica", 7.1)
    canvas.drawString(78, PAGE_H - 44, "Official Utah DWR harvest data | U.O.G.A. Hunt Builder visitor reference")
    canvas.setFillColor(ORANGE)
    canvas.roundRect(PAGE_W - 206, PAGE_H - 47, 141, 23, 7, fill=1, stroke=0)
    canvas.setFillColor(DARK)
    canvas.setFont("Helvetica-Bold", 7.4)
    canvas.drawCentredString(PAGE_W - 135.5, PAGE_H - 38, status[:34])
    canvas.setStrokeColor(ORANGE)
    canvas.line(28, 28, PAGE_W - 28, 28)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.4)
    canvas.drawString(31, 17, "Historical harvest and quality measures only - not current permit quota or draw probability.")
    canvas.drawRightString(PAGE_W - 31, 17, f"Page {doc.page}")
    canvas.restoreState()


def table(data: list[list[object]], widths: list[float], font_size: float = 5.7) -> Table:
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), font_size),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), font_size - 0.3),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, ALT]),
                ("GRID", (0, 0), (-1, -1), 0.28, GRID),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.0),
                ("TOPPADDING", (0, 0), (-1, -1), 1.7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.7),
            ]
        )
    )
    return result


def summary_table(rows: list[dict[str, str]], report_styles: dict[str, ParagraphStyle]) -> Table:
    data: list[list[object]] = [["Species", "Rows", "Permits", "Hunters", "Harvest", "Median success", "Age rows", "3-year age rows"]]
    for species, group in species_groups(rows):
        success = [number(row.get("percent_success")) for row in group]
        success = [value for value in success if value is not None]
        data.append(
            [
                para(species, report_styles["cell_bold"]),
                f"{len(group):,}",
                f"{sum(number(row.get('permits')) or 0 for row in group):,.0f}",
                f"{sum(number(row.get('hunters_afield')) or 0 for row in group):,.0f}",
                f"{sum(number(row.get('harvest_total')) or 0 for row in group):,.0f}",
                f"{statistics.median(success):.1f}%" if success else "-",
                f"{sum(bool(clean(row.get('average_age'))) for row in group):,}",
                f"{sum(bool(clean(row.get('average_age_3yr_reported'))) for row in group):,}",
            ]
        )
    return table(data, [1.8 * inch, 0.55 * inch, 0.75 * inch, 0.78 * inch, 0.72 * inch, 0.92 * inch, 0.68 * inch, 0.9 * inch], 6.4)


def source_table(inventory: list[dict[str, object]], report_styles: dict[str, ParagraphStyle]) -> Table:
    data: list[list[object]] = [["ID", "Official source file or table", "Source pages", "Rows"]]
    for item in inventory:
        data.append(
            [
                item["id"],
                para(item["file"], report_styles["cell"]),
                para(item["pages"], report_styles["cell"]),
                f"{int(item['rows']):,}",
            ]
        )
    return table(data, [0.5 * inch, 5.15 * inch, 2.3 * inch, 0.65 * inch], 6.1)


def result_table(
    rows: list[dict[str, str]],
    harvest_sources: dict[str, str],
    age_sources: dict[str, str],
    report_styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[object]] = [[
        "Code", "Hunt / type / weapon", "Permits", "Hunters", "Harvest", "Success", "Days", "Satisfaction", "Annual age", "DWR 3-year age", "Sources"
    ]]
    for row in rows:
        description = clean(row.get("hunt_name"))
        context = " | ".join(filter(None, [clean(row.get("hunt_type")), clean(row.get("weapon")), clean(row.get("sex_type"))]))
        if context:
            description = f"{description}<br/><font color='#5C4A39'>{escape(context)}</font>"
        harvest_file = clean(row.get("source_file"))
        age_file = clean(row.get("average_age_source_file"))
        harvest_ref = harvest_sources.get(harvest_file, "-")
        harvest_page = clean(row.get("source_page"))
        if harvest_ref != "-" and harvest_page:
            harvest_ref += f" p.{harvest_page}"
        age_ref = age_sources.get(age_file, "-")
        age_page = clean(row.get("average_age_source_page"))
        if age_ref != "-" and age_page:
            age_ref += f" p.{age_page}"
        source_ref = harvest_ref if age_ref == "-" else f"{harvest_ref}<br/>{age_ref}"
        data.append(
            [
                clean(row.get("hunt_code")),
                Paragraph(description, report_styles["cell"]),
                display(row.get("permits")),
                display(row.get("hunters_afield")),
                display(row.get("harvest_total")),
                display(row.get("percent_success"), 1, "%"),
                display(row.get("average_days"), 1),
                display(row.get("hunter_satisfaction"), 1),
                display(row.get("average_age"), 1),
                display(row.get("average_age_3yr_reported"), 1),
                Paragraph(source_ref, report_styles["cell"]),
            ]
        )
    return table(
        data,
        [0.54 * inch, 2.24 * inch, 0.52 * inch, 0.55 * inch, 0.55 * inch, 0.55 * inch, 0.46 * inch, 0.62 * inch, 0.56 * inch, 0.7 * inch, 1.37 * inch],
        5.25,
    )


def report_status(year: int) -> str:
    if year <= 2020:
        return "VERIFIED OFFICIAL DWR PDF"
    if year == 2021:
        return "VERIFIED DWR ANNUAL PACKAGE"
    if year <= 2024:
        return "VERIFIED DWR REPORT PACKAGE"
    return "CURRENT DWR DATA - 2026-09-02"


def build_report(year: int, rows: list[dict[str, str]], output_path: Path) -> dict[str, object]:
    report_styles = styles()
    title = f"Utah {year} Harvest Report"
    status = report_status(year)
    harvest_source_ids, harvest_inventory = source_inventory(rows, "H", "source_file", "source_page")
    age_source_ids, age_inventory = source_inventory(rows, "A", "average_age_source_file", "average_age_source_page")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path), pagesize=PAGE_SIZE,
        leftMargin=0.42 * inch, rightMargin=0.42 * inch,
        topMargin=0.97 * inch, bottomMargin=0.46 * inch,
        title=title, author="Utah Outfitter and Guide Association (U.O.G.A.)",
        subject="Official Utah DWR harvest results and harvested-age measures",
    )
    groups = species_groups(rows)
    annual_age_rows = sum(bool(clean(row.get("average_age"))) for row in rows)
    reported_age_rows = sum(bool(clean(row.get("average_age_3yr_reported"))) for row in rows)
    story: list[object] = [
        Spacer(1, 0.2 * inch),
        para(title, report_styles["title"]),
        para(status, report_styles["subtitle"]),
        para(
            f"This report assembles {len(rows):,} official DWR hunt-code rows across {len(groups):,} species groups. "
            f"The retained rows sum to {sum(number(row.get('hunters_afield')) or 0 for row in rows):,.0f} hunters afield and "
            f"{sum(number(row.get('harvest_total')) or 0 for row in rows):,.0f} harvested animals. "
            "DWR statewide estimates may differ from sums of hunt-code rows because DWR projects statewide and hunt-level estimates separately.",
            report_styles["body"],
        ),
        para(
            f"Harvested age is available for {annual_age_rows:,} rows; a DWR-reported three-year harvested-age value is available for {reported_age_rows:,} rows. "
            "Annual age and DWR-reported three-year age are separate fields. A blank means the official evidence does not provide that measure for the matched hunt code; no value is inferred.",
            report_styles["body"],
        ),
        para(
            "Permit counts in this historical harvest report are source-year harvest-report fields only. They are not the current quota authority and are not used directly as draw probability.",
            report_styles["note"],
        ),
        para("Species summary", report_styles["section"]),
        summary_table(rows, report_styles),
        Spacer(1, 0.08 * inch),
        para(
            "Summary totals are sums of retained hunt-code rows. Median success is the median of published hunt-level success rates, not a statewide weighted rate.",
            report_styles["note"],
        ),
        para("Official source inventory", report_styles["section"]),
        para(
            f"DWR harvest reports: {DWR_REPORTS_URL} | DWR report index: {DWR_REPORT_INDEX_URL} | Normalized source snapshot SHA-256: {sha256(SOURCE)}",
            report_styles["note"],
        ),
        source_table(harvest_inventory, report_styles),
    ]
    if age_inventory:
        story.extend(
            [
                Spacer(1, 0.08 * inch),
                para("Harvested-age source inventory", report_styles["section"]),
                source_table(age_inventory, report_styles),
            ]
        )
    if year == 2025:
        story.extend(
            [
                Spacer(1, 0.08 * inch),
                para(
                    f"2025 status: current DWR dashboard reconciliation accessed {DWR_2025_ACCESSED}, plus the official preliminary package and the official turkey report. "
                    "The 2025 annual elk, pronghorn, and moose ages and their DWR-reported 2023-2025 averages come from the DWR 2026 tables.",
                    report_styles["note"],
                ),
            ]
        )

    for species, group in groups:
        story.extend(
            [
                PageBreak(),
                para(f"{species} - {len(group):,} hunt-code rows", report_styles["section"]),
                para(
                    "Source references use H for harvest evidence and A for harvested-age evidence. Source IDs resolve to the inventories at the front of this report.",
                    report_styles["note"],
                ),
                result_table(group, harvest_source_ids, age_source_ids, report_styles),
            ]
        )

    doc.build(
        story,
        onFirstPage=lambda canvas, document: page_background(canvas, document, title, status),
        onLaterPages=lambda canvas, document: page_background(canvas, document, title, status),
    )
    reader = PdfReader(str(output_path))
    if reader.is_encrypted or len(reader.pages) < 2:
        raise RuntimeError(f"PDF validation failed: {output_path}")
    return {
        "year": year,
        "rows": len(rows),
        "species_groups": len(groups),
        "annual_age_rows": annual_age_rows,
        "reported_three_year_age_rows": reported_age_rows,
        "pages": len(reader.pages),
        "output_path": str(output_path.relative_to(ROOT)),
        "sha256": sha256(output_path),
        "status": status,
        "generated_date": date.today().isoformat(),
    }


def main() -> None:
    rows_by_year = read_rows()
    reports: list[dict[str, object]] = []
    for year in YEARS:
        filename = f"Utah_{year}_Harvest_Report_UOGA.pdf"
        if year in {2024, 2025}:
            filename = f"Utah_{year}_Harvest_Results_UOGA.pdf"
        output_path = OUTPUT_DIR / filename
        report = build_report(year, rows_by_year[year], output_path)
        public_path = PUBLIC_DIR / str(year) / filename
        public_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, public_path)
        if sha256(output_path) != sha256(public_path):
            raise RuntimeError(f"Published copy hash mismatch: {public_path}")
        report["public_path"] = str(public_path.relative_to(ROOT))
        reports.append(report)
        print(f"{year}_PDF={output_path}")
        print(f"{year}_ROWS={report['rows']} PAGES={report['pages']} SHA256={report['sha256']}")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "generated_date": date.today().isoformat(),
                "source": str(SOURCE.relative_to(ROOT)),
                "source_sha256": sha256(SOURCE),
                "reports": reports,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"MANIFEST={MANIFEST}")


if __name__ == "__main__":
    main()
