from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from re import sub
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "normalized"
    / "harvest_quality_features_all_years_by_hunt_code.csv"
)
MANAGEMENT_CONTEXT = ROOT / "data_model" / "harvest_quality" / "hunt_management_objective_context_2026.csv"
QUALITY_PROFILE = ROOT / "data_model" / "harvest_quality" / "hunt_quality_profile_by_hunt_code_2026.csv"
OUTPUT_DIR = ROOT / "output" / "pdf" / "harvest-results"
PUBLIC_DIR = ROOT / "public" / "hard-copy" / "harvest-data"
MANIFEST = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "validation"
    / "harvest_library_reports_2023_2025.json"
)
UOGA_LOGO = ROOT / "assets" / "logos" / "UOGA-LOGO-CIRCLE.png"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
YEARS = (2023, 2024, 2025)

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
        "nav_title": ParagraphStyle(
            "nav_title", fontName="Helvetica-Bold", fontSize=18, leading=20,
            textColor=DARK, alignment=TA_CENTER, spaceAfter=3,
        ),
        "nav_subtitle": ParagraphStyle(
            "nav_subtitle", fontName="Helvetica-Bold", fontSize=9, leading=10,
            textColor=ORANGE, alignment=TA_CENTER, spaceAfter=4,
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
        "toc_species": ParagraphStyle(
            "toc_species", fontName="Helvetica-Bold", fontSize=6.8, leading=7.1,
            textColor=ORANGE, leftIndent=8, firstLineIndent=-8, spaceBefore=0.3, spaceAfter=0,
        ),
        "toc_sex": ParagraphStyle(
            "toc_sex", fontName="Helvetica", fontSize=6.2, leading=6.6,
            textColor=TEXT, leftIndent=25, firstLineIndent=-7, spaceBefore=0, spaceAfter=0,
        ),
    }


class HarvestDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph) or not hasattr(flowable, "_toc_level"):
            return
        level = int(flowable._toc_level)
        title = flowable.getPlainText()
        key = str(flowable._bookmark_name)
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)
        self.notify("TOCEntry", (level, title, self.page, key))


def toc_heading(text: str, style: ParagraphStyle, level: int, key: str) -> Paragraph:
    heading = para(text, style)
    heading._toc_level = level
    heading._bookmark_name = key
    return heading


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


def read_keyed_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    keyed: dict[str, dict[str, str]] = {}
    for row in rows:
        hunt_code = clean(row.get("hunt_code"))
        if hunt_code in keyed:
            raise RuntimeError(f"Duplicate hunt code in {path.name}: {hunt_code}")
        keyed[hunt_code] = row
    return keyed


def species_family(value: object) -> str:
    text = clean(value).lower()
    if "deer" in text:
        return "deer"
    if "elk" in text:
        return "elk"
    if "pronghorn" in text:
        return "pronghorn"
    if "moose" in text:
        return "moose"
    if "bison" in text:
        return "bison"
    if "goat" in text:
        return "goat"
    if "sheep" in text or "bighorn" in text:
        return "sheep"
    if "bear" in text:
        return "bear"
    if "turkey" in text:
        return "turkey"
    if "cougar" in text:
        return "cougar"
    return text


def compatible_context(row: dict[str, str], candidate: dict[str, str] | None) -> dict[str, str] | None:
    if not candidate:
        return None
    return candidate if species_family(row.get("species")) == species_family(candidate.get("species")) else None


def resolved_sex(row: dict[str, str], profiles: dict[str, dict[str, str]]) -> str:
    native = clean(row.get("sex_type"))
    if native:
        return native
    profile = compatible_context(row, profiles.get(clean(row.get("hunt_code"))))
    return clean(profile.get("sex_type")) if profile else "Sex not separately classified"


def species_sex_groups(
    rows: list[dict[str, str]], profiles: dict[str, dict[str, str]]
) -> list[tuple[str, list[tuple[str, list[dict[str, str]]]]]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        species = clean(row.get("species")) or "Unclassified"
        grouped[species][resolved_sex(row, profiles)].append(row)
    result: list[tuple[str, list[tuple[str, list[dict[str, str]]]]]] = []
    for species in sorted(grouped, key=lambda value: (SPECIES_ORDER.get(value, 99), value)):
        sex_groups: list[tuple[str, list[dict[str, str]]]] = []
        for sex in sorted(grouped[species]):
            sex_rows = sorted(grouped[species][sex], key=lambda row: (clean(row.get("hunt_code")), clean(row.get("hunt_name"))))
            sex_groups.append((sex, sex_rows))
        result.append((species, sex_groups))
    return result


def anchor_name(year: int, species: str, sex: str = "") -> str:
    slug = sub(r"[^a-z0-9]+", "-", f"{year}-{species}-{sex}".lower()).strip("-")
    return f"section-{slug}"


def hunt_anchor_name(year: int, hunt_code: str) -> str:
    slug = sub(r"[^a-z0-9]+", "-", f"{year}-{hunt_code}".lower()).strip("-")
    return f"hunt-{slug}"


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


def flat_species_groups(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("species")) or "Unclassified"].append(row)
    return sorted(grouped.items(), key=lambda item: (SPECIES_ORDER.get(item[0], 99), item[0]))


def summary_table(
    rows: list[dict[str, str]],
    management: dict[str, dict[str, str]],
    profiles: dict[str, dict[str, str]],
    report_styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[object]] = [["Species", "Rows", "Hunters", "Harvest", "Median success", "Median days", "Median satisfaction", "DWR objective rows", "Quality rows"]]
    for species, group in flat_species_groups(rows):
        success = [value for value in (number(row.get("percent_success")) for row in group) if value is not None]
        days = [value for value in (number(row.get("average_days")) for row in group) if value is not None]
        satisfaction = [value for value in (number(row.get("hunter_satisfaction")) for row in group) if value is not None]
        objective_rows = sum(
            bool(compatible_context(row, management.get(clean(row.get("hunt_code")))))
            and bool(clean(management[clean(row.get("hunt_code"))].get("management_objective_target")))
            for row in group
        )
        quality_rows = sum(
            clean((compatible_context(row, profiles.get(clean(row.get("hunt_code")))) or {}).get("hunt_unit_quality_score_status"))
            == "PUBLISHABLE_EVIDENCE_THRESHOLD_MET"
            for row in group
        )
        data.append(
            [
                para(species, report_styles["cell_bold"]),
                f"{len(group):,}",
                f"{sum(number(row.get('hunters_afield')) or 0 for row in group):,.0f}",
                f"{sum(number(row.get('harvest_total')) or 0 for row in group):,.0f}",
                f"{statistics.median(success):.1f}%" if success else "-",
                f"{statistics.median(days):.1f}" if days else "-",
                f"{statistics.median(satisfaction):.1f}" if satisfaction else "-",
                f"{objective_rows:,}",
                f"{quality_rows:,}",
            ]
        )
    result = table(data, [1.48 * inch, 0.45 * inch, 0.68 * inch, 0.62 * inch, 0.82 * inch, 0.67 * inch, 0.85 * inch, 0.86 * inch, 0.66 * inch], 5.6)
    result.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]))
    return result


def objective_short_name(value: object) -> str:
    text = clean(value)
    return {
        "DWR Harvested Age Objective": "Harvested age",
        "DWR Population Objective": "Population",
        "DWR Buck-to-Doe Composition Objective": "Buck:doe",
        "Black Bear Three-Year Strategy Framework": "Bear 3-year framework",
        "Wild Turkey Statewide Program Objectives": "Turkey statewide program",
        "Cougar Open-Season Program Authority": "Cougar open-season program",
    }.get(text, text or "DWR objective")


def objective_cell(context: dict[str, str] | None, report_styles: dict[str, ParagraphStyle]) -> Paragraph:
    if not context or not clean(context.get("management_objective_target")):
        return para("-", report_styles["cell"])
    target = clean(context.get("management_objective_target"))
    objective_type = objective_short_name(context.get("management_objective_type"))
    if len(target) > 105:
        return Paragraph(f"<b>{escape(objective_type)}</b><br/>See objective framework", report_styles["cell"])
    unit = clean(context.get("objective_unit"))
    current = clean(context.get("management_current_value"))
    status = clean(context.get("management_objective_status")).replace("_", " ").title()
    lines = [f"<b>{escape(objective_type)}</b>: {escape(target)}"]
    if unit:
        lines.append(escape(unit))
    if current:
        lines.append(f"Current: {escape(current)}")
    if status:
        lines.append(status)
    return Paragraph("<br/>".join(lines), report_styles["cell"])


def quality_cell(profile: dict[str, str] | None, report_styles: dict[str, ParagraphStyle]) -> Paragraph:
    if not profile or clean(profile.get("hunt_unit_quality_score_status")) != "PUBLISHABLE_EVIDENCE_THRESHOLD_MET":
        return para("-", report_styles["cell"])
    score = display(profile.get("hunt_unit_quality_score"), 1)
    label = clean(profile.get("hunt_unit_quality_label")).replace(" hunt-quality profile", "")
    confidence = clean(profile.get("hunt_unit_quality_confidence")).title()
    return Paragraph(
        f"<b>{escape(score)}/100</b><br/>{escape(label)}<br/>{escape(confidence)} confidence",
        report_styles["cell"],
    )


def objective_framework_table(
    rows: list[dict[str, str]],
    management: dict[str, dict[str, str]],
    report_styles: dict[str, ParagraphStyle],
) -> Table:
    frameworks: dict[tuple[str, str], str] = {}
    for row in rows:
        context = compatible_context(row, management.get(clean(row.get("hunt_code"))))
        if not context:
            continue
        target = clean(context.get("management_objective_target"))
        if len(target) <= 105:
            continue
        key = (objective_short_name(context.get("management_objective_type")), clean(context.get("objective_unit")))
        frameworks[key] = target
    data: list[list[object]] = [["Framework", "Utah DWR objective", "Unit of measure"]]
    for (name, unit), target in sorted(frameworks.items()):
        data.append([para(name, report_styles["cell_bold"]), para(target, report_styles["cell"]), para(unit, report_styles["cell"])])
    if len(data) == 1:
        data.append(["-", "No statewide qualitative framework applies to retained rows.", "-"])
    return table(data, [1.55 * inch, 6.15 * inch, 1.45 * inch], 6.0)


def unit_index_table(
    year: int,
    rows: list[dict[str, str]],
    profiles: dict[str, dict[str, str]],
    report_styles: dict[str, ParagraphStyle],
) -> Table:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in rows:
        species = clean(row.get("species")) or "Unclassified"
        sex = resolved_sex(row, profiles)
        unit = clean(row.get("hunt_name")) or "Hunt name not separately reported"
        grouped[(unit, species, sex)].append(clean(row.get("hunt_code")))
    data: list[list[object]] = [["Hunting unit / hunt name", "Hunt codes", "Species", "Sex", "Report section"]]
    for (unit, species, sex), codes in sorted(grouped.items(), key=lambda item: (item[0][0].lower(), item[0][1], item[0][2])):
        section_key = anchor_name(year, species, sex)
        unique_codes = sorted(set(codes))
        first_hunt_key = hunt_anchor_name(year, unique_codes[0])
        linked_codes = ", ".join(
            f'<a href="#{hunt_anchor_name(year, code)}">{escape(code)}</a>' for code in unique_codes
        )
        data.append(
            [
                Paragraph(f'<a href="#{first_hunt_key}">{escape(unit)}</a>', report_styles["cell"]),
                Paragraph(linked_codes, report_styles["cell"]),
                para(species, report_styles["cell"]),
                para(sex, report_styles["cell"]),
                Paragraph(f'<a href="#{section_key}">{escape(species)} / {escape(sex)}</a>', report_styles["cell"]),
            ]
        )
    result = table(data, [2.45 * inch, 2.15 * inch, 1.25 * inch, 1.35 * inch, 1.95 * inch], 5.8)
    result.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0)]))
    return result


def result_table(
    year: int,
    rows: list[dict[str, str]],
    management: dict[str, dict[str, str]],
    profiles: dict[str, dict[str, str]],
    report_styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[object]] = [[
        "Code", "Hunt / type / weapon", "Permits", "Hunters", "Util.", "Harvest", "Success", "Days", "Satisf.", "Annual age", "DWR 3-year age", "Utah DWR objective", "U.O.G.A. unit quality"
    ]]
    for row in rows:
        hunt_code = clean(row.get("hunt_code"))
        description = escape(clean(row.get("hunt_name")))
        context_line = " | ".join(filter(None, [clean(row.get("hunt_type")), clean(row.get("weapon"))]))
        if context_line:
            description = f"{description}<br/><font color='#5C4A39'>{escape(context_line)}</font>"
        permits = number(row.get("permits"))
        hunters = number(row.get("hunters_afield"))
        utilization = (hunters / permits * 100) if permits and hunters is not None else None
        management_row = compatible_context(row, management.get(hunt_code))
        profile_row = compatible_context(row, profiles.get(hunt_code))
        data.append(
            [
                Paragraph(
                    f'<a name="{hunt_anchor_name(year, hunt_code)}"/><b>{escape(hunt_code)}</b>',
                    report_styles["cell"],
                ),
                Paragraph(description, report_styles["cell"]),
                display(permits),
                display(hunters),
                display(utilization, 1, "%"),
                display(row.get("harvest_total")),
                display(row.get("percent_success"), 1, "%"),
                display(row.get("average_days"), 1),
                display(row.get("hunter_satisfaction"), 1),
                display(row.get("average_age"), 1),
                display(row.get("average_age_3yr_reported"), 1),
                objective_cell(management_row, report_styles),
                quality_cell(profile_row, report_styles),
            ]
        )
    return table(
        data,
        [0.46 * inch, 1.8 * inch, 0.47 * inch, 0.49 * inch, 0.45 * inch, 0.47 * inch, 0.47 * inch, 0.4 * inch, 0.45 * inch, 0.45 * inch, 0.52 * inch, 1.5 * inch, 1.55 * inch],
        4.95,
    )


def report_status(year: int) -> str:
    if year <= 2020:
        return "VERIFIED OFFICIAL DWR PDF"
    if year == 2021:
        return "VERIFIED DWR ANNUAL PACKAGE"
    if year <= 2024:
        return "VERIFIED DWR REPORT PACKAGE"
    return "CURRENT DWR DATA - 2026-09-02"


def build_report(
    year: int,
    rows: list[dict[str, str]],
    management: dict[str, dict[str, str]],
    profiles: dict[str, dict[str, str]],
    output_path: Path,
) -> dict[str, object]:
    report_styles = styles()
    title = f"Utah {year} Harvest Report"
    status = report_status(year)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = HarvestDocTemplate(
        str(output_path), pagesize=PAGE_SIZE,
        leftMargin=0.42 * inch, rightMargin=0.42 * inch,
        topMargin=0.97 * inch, bottomMargin=0.46 * inch,
        title=title, author="Utah Outfitter and Guide Association (U.O.G.A.)",
        subject="Utah DWR harvest results, management objectives, and U.O.G.A. hunt-unit quality",
    )
    groups = species_sex_groups(rows, profiles)
    annual_age_rows = sum(bool(clean(row.get("average_age"))) for row in rows)
    reported_age_rows = sum(bool(clean(row.get("average_age_3yr_reported"))) for row in rows)
    objective_rows = sum(
        bool(clean((compatible_context(row, management.get(clean(row.get("hunt_code")))) or {}).get("management_objective_target")))
        for row in rows
    )
    quality_rows = sum(
        clean((compatible_context(row, profiles.get(clean(row.get("hunt_code")))) or {}).get("hunt_unit_quality_score_status"))
        == "PUBLISHABLE_EVIDENCE_THRESHOLD_MET"
        for row in rows
    )
    toc = TableOfContents()
    toc.levelStyles = [report_styles["toc_species"], report_styles["toc_sex"]]
    story: list[object] = [
        Spacer(1, 0.2 * inch),
        para(title, report_styles["title"]),
        para(status, report_styles["subtitle"]),
        para(
            f"This report assembles {len(rows):,} Utah DWR hunt-code rows across {len(groups):,} species groups. "
            f"The retained rows sum to {sum(number(row.get('hunters_afield')) or 0 for row in rows):,.0f} hunters afield and "
            f"{sum(number(row.get('harvest_total')) or 0 for row in rows):,.0f} harvested animals. "
            "DWR statewide estimates may differ from sums of hunt-code rows because DWR projects statewide and hunt-level estimates separately.",
            report_styles["body"],
        ),
        para(
            f"Harvested age is available for {annual_age_rows:,} rows; a DWR-reported three-year harvested-age value is available for {reported_age_rows:,} rows. "
            f"A matching DWR management objective is available for {objective_rows:,} rows, and the evidence-gated U.O.G.A. Hunt Unit Quality score is publishable for {quality_rows:,} rows. "
            "A dash means the matched record does not support that measure; no value or score is inferred.",
            report_styles["body"],
        ),
        para(
            "Permit counts in this historical harvest report are source-year harvest-report fields only. They are not the current quota authority and are not used directly as draw probability.",
            report_styles["note"],
        ),
        para(
            "Compare permit utilization, harvest success, days hunted, satisfaction, harvested age, the applicable DWR objective, and the evidence-gated U.O.G.A. unit-quality profile. Summary medians are hunt-level medians, not statewide weighted estimates.",
            report_styles["note"],
        ),
        para("Species summary", report_styles["section"]),
        summary_table(rows, management, profiles, report_styles),
        PageBreak(),
        Paragraph('<a name="report-toc"/><b>TABLE OF CONTENTS</b>', report_styles["nav_title"]),
        para("SPECIES / SEX", report_styles["nav_subtitle"]),
        para(
            "Select a Species / Sex entry to jump directly to its report table. The PDF outline/bookmarks provide the same navigation in the viewer sidebar.",
            report_styles["note"],
        ),
        toc,
        PageBreak(),
        para("Utah DWR Management Objective Framework", report_styles["title"]),
        para(
            "The row-level objective column shows the applicable DWR target, unit of measure, current comparison value, and status when those values are available. Statewide qualitative frameworks are stated once below and referenced compactly in the row table.",
            report_styles["body"],
        ),
        objective_framework_table(rows, management, report_styles),
        Spacer(1, 0.12 * inch),
        para(
            "U.O.G.A. Hunt Unit Quality is a display-only 0-100 profile combining the matching biological measure, three-year harvest success, three-year satisfaction, and inverse effort. It is not a DWR score, not comparable across unlike species/hunt classes, and never changes permits or draw odds.",
            report_styles["note"],
        ),
        PageBreak(),
        Paragraph('<a name="unit-index"/><b>HUNTING UNIT INDEX</b>', report_styles["nav_title"]),
        para("UNIT NUMBER / NAME", report_styles["nav_subtitle"]),
        para(
            "Units are alphabetical. Select a unit or hunt code to jump to that exact result row, or select Species / Sex to jump to the full section.",
            report_styles["note"],
        ),
    ]
    if year == 2025:
        story.extend(
            [
                Spacer(1, 0.08 * inch),
                para(
                    f"2025 status: current DWR dashboard reconciliation through {DWR_2025_ACCESSED}, plus the preliminary big-game package and the turkey report. "
                    "The 2025 annual elk, pronghorn, and moose ages and their DWR-reported 2023-2025 averages are included.",
                    report_styles["note"],
                ),
            ]
        )
    story.append(unit_index_table(year, rows, profiles, report_styles))

    for species, sex_groups in groups:
        species_rows = sum(len(group) for _, group in sex_groups)
        first_sex = True
        for sex, group in sex_groups:
            story.append(PageBreak())
            if first_sex:
                story.append(
                    toc_heading(
                        f"{species} - {species_rows:,} hunt-code rows",
                        report_styles["section"],
                        0,
                        anchor_name(year, species),
                    )
                )
                first_sex = False
            story.extend(
                [
                    toc_heading(
                        f"{sex} - {len(group):,} rows",
                        report_styles["section"],
                        1,
                        anchor_name(year, species, sex),
                    ),
                    Paragraph(
                        '<a href="#report-toc">Back to T.O.C.</a> &nbsp; | &nbsp; '
                        '<a href="#unit-index">Hunting Unit Index</a>',
                        report_styles["note"],
                    ),
                    para(
                        "Annual harvest fields are year-specific. DWR objective/current context and the evidence-gated U.O.G.A. quality profile are current management overlays and remain blank where exact compatible evidence is unavailable.",
                        report_styles["note"],
                    ),
                    result_table(year, group, management, profiles, report_styles),
                ]
            )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="harvest-frame")
    doc.addPageTemplates(
        [
            PageTemplate(
                id="harvest-pages",
                frames=[frame],
                onPage=lambda canvas, document: page_background(canvas, document, title, status),
            )
        ]
    )
    doc.multiBuild(story)
    reader = PdfReader(str(output_path))
    if reader.is_encrypted or len(reader.pages) < 2:
        raise RuntimeError(f"PDF validation failed: {output_path}")
    return {
        "year": year,
        "rows": len(rows),
        "species_groups": len(groups),
        "annual_age_rows": annual_age_rows,
        "reported_three_year_age_rows": reported_age_rows,
        "management_objective_rows": objective_rows,
        "hunt_unit_quality_rows": quality_rows,
        "pages": len(reader.pages),
        "output_path": str(output_path.relative_to(ROOT)),
        "sha256": sha256(output_path),
        "status": status,
        "generated_date": date.today().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the three-year Utah harvest report Library set.")
    parser.add_argument(
        "--output-only",
        action="store_true",
        help="Write verified PDFs and the internal manifest without copying to public/hard-copy.",
    )
    args = parser.parse_args()
    rows_by_year = read_rows()
    management = read_keyed_csv(MANAGEMENT_CONTEXT)
    profiles = read_keyed_csv(QUALITY_PROFILE)
    reports: list[dict[str, object]] = []
    for year in YEARS:
        filename = f"Utah_{year}_Harvest_Report_UOGA.pdf"
        if year in {2024, 2025}:
            filename = f"Utah_{year}_Harvest_Results_UOGA.pdf"
        output_path = OUTPUT_DIR / filename
        report = build_report(year, rows_by_year[year], management, profiles, output_path)
        public_path = PUBLIC_DIR / str(year) / filename
        if args.output_only:
            report["public_path"] = str(public_path.relative_to(ROOT))
            report["public_copy_status"] = "OUTPUT_ONLY_NOT_COPIED"
        else:
            public_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output_path, public_path)
            if sha256(output_path) != sha256(public_path):
                raise RuntimeError(f"Published copy hash mismatch: {public_path}")
            report["public_path"] = str(public_path.relative_to(ROOT))
            report["public_copy_status"] = "HASH_MATCHED"
        reports.append(report)
        print(f"{year}_PDF={output_path}")
        print(f"{year}_ROWS={report['rows']} PAGES={report['pages']} SHA256={report['sha256']}")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": "2.0.0",
                "generated_date": date.today().isoformat(),
                "source": str(SOURCE.relative_to(ROOT)),
                "source_sha256": sha256(SOURCE),
                "management_context": str(MANAGEMENT_CONTEXT.relative_to(ROOT)),
                "management_context_sha256": sha256(MANAGEMENT_CONTEXT),
                "quality_profile": str(QUALITY_PROFILE.relative_to(ROOT)),
                "quality_profile_sha256": sha256(QUALITY_PROFILE),
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
