from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
import textwrap

import pdfplumber
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


HUNT_RE = re.compile(r"Hunt:\s*([A-Z]{2}\d{4})\s+(.+?)\s+Page\s+(\d+)", re.S | re.I)
ARIAL_FONT_NAME = "Helvetica"
ARIAL_BOLD_FONT_NAME = "Helvetica-Bold"
ROOT = Path(__file__).resolve().parents[1]
SEASON_LOOKUP_CSV = ROOT / "data_truth" / "crosswalk_truth" / "raw_inventory" / "live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv"
TABLE_SIDE_MARGIN = 0.44 * inch


@dataclass
class PageBlock:
    hunt_code: str
    hunt_name: str
    source_report_page: str
    audience: str
    rows: list[list[str]]
    season_text: str


@dataclass(frozen=True)
class PacketTheme:
    name: str
    cover_bg: str
    cover_border_dark: str
    cover_border_accent: str
    cover_header_fill: str
    cover_title_text: str
    cover_accent_text: str
    cover_body_text: str
    cover_rule: str
    page_bg: str
    page_frame_dark: str
    page_frame_accent: str
    page_header_fill: str
    page_header_text: str
    page_header_accent: str
    page_title_text: str
    table_header_primary: str
    table_header_secondary: str
    table_grid: str
    table_divider: str
    table_row_a: str
    table_row_b: str
    body_text: str
    cover_watermark_opacity: float
    page_species_icon: bool
    page_frame: bool


THEMES: dict[str, PacketTheme] = {
    "dark_packet": PacketTheme(
        name="dark_packet",
        cover_bg="#F5EEDC",
        cover_border_dark="#3B210C",
        cover_border_accent="#F08A11",
        cover_header_fill="#4A2405",
        cover_title_text="#4A2D16",
        cover_accent_text="#F39A1E",
        cover_body_text="#4A2D16",
        cover_rule="#D8C3A5",
        page_bg="#F7EEDB",
        page_frame_dark="#3B210C",
        page_frame_accent="#F08A11",
        page_header_fill="#4A2405",
        page_header_text="#FFFFFF",
        page_header_accent="#F39A1E",
        page_title_text="#3A1D06",
        table_header_primary="#4A2405",
        table_header_secondary="#8A5A2B",
        table_grid="#B58A5A",
        table_divider="#4A2405",
        table_row_a="#FFF8ED",
        table_row_b="#F2E1C9",
        body_text="#2F2119",
        cover_watermark_opacity=0.09,
        page_species_icon=False,
        page_frame=True,
    ),
    "dark_packet_icon": PacketTheme(
        name="dark_packet_icon",
        cover_bg="#F5EEDC",
        cover_border_dark="#3B210C",
        cover_border_accent="#F08A11",
        cover_header_fill="#4A2405",
        cover_title_text="#4A2D16",
        cover_accent_text="#F39A1E",
        cover_body_text="#4A2D16",
        cover_rule="#D8C3A5",
        page_bg="#F7EEDB",
        page_frame_dark="#3B210C",
        page_frame_accent="#F08A11",
        page_header_fill="#4A2405",
        page_header_text="#FFFFFF",
        page_header_accent="#F39A1E",
        page_title_text="#3A1D06",
        table_header_primary="#4A2405",
        table_header_secondary="#8A5A2B",
        table_grid="#B58A5A",
        table_divider="#4A2405",
        table_row_a="#FFF8ED",
        table_row_b="#F2E1C9",
        body_text="#2F2119",
        cover_watermark_opacity=0.11,
        page_species_icon=True,
        page_frame=True,
    ),
    "bronze_field_guide": PacketTheme(
        name="bronze_field_guide",
        cover_bg="#F4E7CF",
        cover_border_dark="#5A3314",
        cover_border_accent="#C87417",
        cover_header_fill="#5B3413",
        cover_title_text="#4E2C12",
        cover_accent_text="#D68820",
        cover_body_text="#4E2C12",
        cover_rule="#C9B08E",
        page_bg="#F6ECD7",
        page_frame_dark="#5A3314",
        page_frame_accent="#C87417",
        page_header_fill="#5B3413",
        page_header_text="#FFF7EF",
        page_header_accent="#E39A31",
        page_title_text="#4C2B12",
        table_header_primary="#5B3413",
        table_header_secondary="#9A6731",
        table_grid="#B68658",
        table_divider="#5B3413",
        table_row_a="#FFF7EB",
        table_row_b="#F1DFC4",
        body_text="#332317",
        cover_watermark_opacity=0.08,
        page_species_icon=True,
        page_frame=True,
    ),
    "espresso_minimal": PacketTheme(
        name="espresso_minimal",
        cover_bg="#F8F1E6",
        cover_border_dark="#2E1B0F",
        cover_border_accent="#9D5B19",
        cover_header_fill="#2F1B10",
        cover_title_text="#352114",
        cover_accent_text="#C77B20",
        cover_body_text="#352114",
        cover_rule="#D4C3AE",
        page_bg="#FBF5EC",
        page_frame_dark="#2E1B0F",
        page_frame_accent="#9D5B19",
        page_header_fill="#2F1B10",
        page_header_text="#FFFFFF",
        page_header_accent="#C77B20",
        page_title_text="#2E1B0F",
        table_header_primary="#2F1B10",
        table_header_secondary="#765032",
        table_grid="#B59A7D",
        table_divider="#2F1B10",
        table_row_a="#FFFDF9",
        table_row_b="#F4EBDD",
        body_text="#251B16",
        cover_watermark_opacity=0.06,
        page_species_icon=False,
        page_frame=False,
    ),
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.endswith(".0") and text[:-2].replace("-", "").isdigit():
        text = text[:-2]
    return text


def season_dropdown_options(season_text: str) -> list[str]:
    season_value = clean_text(season_text) or "Season dates unavailable"
    parts = [clean_text(part) for part in season_value.split("|") if clean_text(part)]
    options = [" "]
    if len(parts) <= 1:
        if season_value not in options:
            options.append(season_value)
        return options
    for part in parts:
        if part not in options:
            options.append(part)
    return options


def ensure_arial_fonts() -> None:
    global ARIAL_FONT_NAME, ARIAL_BOLD_FONT_NAME
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular.exists() and "Arial" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Arial", str(regular)))
    if bold.exists() and "Arial-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Arial-Bold", str(bold)))
    if "Arial" in pdfmetrics.getRegisteredFontNames():
        ARIAL_FONT_NAME = "Arial"
    if "Arial-Bold" in pdfmetrics.getRegisteredFontNames():
        ARIAL_BOLD_FONT_NAME = "Arial-Bold"


def get_theme(name: str) -> PacketTheme:
    theme = THEMES.get(clean_text(name).lower())
    if not theme:
        raise ValueError(f"Unknown theme '{name}'. Valid themes: {', '.join(sorted(THEMES))}")
    return theme


def load_season_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    if not SEASON_LOOKUP_CSV.exists():
        return lookup
    with SEASON_LOOKUP_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            hunt_code = clean_text(row.get("hunt_code", "")).upper()
            season = clean_text(row.get("season", ""))
            if hunt_code and season and hunt_code not in lookup:
                lookup[hunt_code] = season
    return lookup


def audience_from_path(path: Path) -> str:
    name = path.name.lower()
    if "youth" in name:
        return "Youth"
    return "Adult"


def normalized_title(text: str) -> str:
    return clean_text(text).replace("_", " ")


def read_page_headers(pdf_path: Path, audience: str) -> list[tuple[str, str, str, int]]:
    reader = PdfReader(str(pdf_path))
    headers: list[tuple[str, str, str, int]] = []
    for pdf_page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        match = HUNT_RE.search(text)
        if not match:
            continue
        headers.append(
            (
                clean_text(match.group(1)).upper(),
                clean_text(match.group(2)),
                clean_text(match.group(3)),
                pdf_page_number,
            )
        )
    if not headers:
        raise ValueError(f"No hunt-code page headers found in {pdf_path}")
    return headers


def compress_side(cells: list[object]) -> list[str]:
    values = [clean_text(cell) for cell in cells if clean_text(cell)]
    if len(values) <= 6:
        return values + [""] * (6 - len(values))
    return values[:5] + [" ".join(values[5:])]


def parse_pdf_table_rows(pdf_path: Path, page_number: int) -> list[list[str]]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_number - 1]
        raw_table = page.extract_table()
    if not raw_table:
        raise ValueError(f"No table extracted from {pdf_path} page {page_number}")

    normalized_rows: list[list[str]] = [
        ["Resident Applicants", "", "", "", "", "", "Nonresident Applicants", "", "", "", "", ""],
        [
            "Points",
            "Bonus Eligible Applicants",
            "Bonus # Permits",
            "Regular # Permits",
            "Total # Permits",
            "Success Ratio",
            "Points",
            "Bonus Eligible Applicants",
            "Bonus # Permits",
            "Regular # Permits",
            "Total # Permits",
            "Success Ratio",
        ],
    ]

    for row in raw_table:
        cells = list(row or [])
        if not any(clean_text(cell) for cell in cells):
            continue
        left = compress_side(cells[:8])
        right = compress_side(cells[8:16])
        if not any(left) and not any(right):
            continue
        normalized_rows.append(left + right)

    if len(normalized_rows) <= 2:
        raise ValueError(f"No usable table rows extracted from {pdf_path} page {page_number}")
    return normalized_rows


def build_blocks(pdf_path: Path, xlsx_path: Path) -> list[PageBlock]:
    audience = audience_from_path(pdf_path)
    headers = read_page_headers(pdf_path, audience)
    season_lookup = load_season_lookup()
    blocks: list[PageBlock] = []
    for hunt_code, hunt_name, source_report_page, pdf_page_number in headers:
        block_rows = parse_pdf_table_rows(pdf_path, pdf_page_number)
        blocks.append(
            PageBlock(
                hunt_code=hunt_code,
                hunt_name=hunt_name,
                source_report_page=source_report_page,
                audience=audience,
                rows=block_rows,
                season_text=season_lookup.get(hunt_code, ""),
            )
        )
    return blocks


def column_widths() -> list[float]:
    proportions = [0.95, 1.10, 0.70, 0.72, 0.72, 0.86, 0.95, 1.10, 0.70, 0.72, 0.72, 0.86]
    total = sum(proportions)
    available_width = landscape(letter)[0] - (TABLE_SIDE_MARGIN * 2)
    return [available_width * value / total for value in proportions]


def build_table(rows: list[list[str]], styles, theme: PacketTheme) -> Table:
    header_style = ParagraphStyle(
        "Header",
        parent=styles["BodyText"],
        fontName=ARIAL_BOLD_FONT_NAME,
        fontSize=6.7,
        leading=7.4,
        textColor=colors.white,
        alignment=1,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=ARIAL_FONT_NAME,
        fontSize=8.0,
        leading=8.8,
        textColor=colors.HexColor(theme.body_text),
        alignment=1,
    )
    hunt_rows = []
    for row_idx, row in enumerate(rows):
        style = header_style if row_idx < 2 else body_style
        padded = row + [""] * (12 - len(row))
        hunt_rows.append([Paragraph(clean_text(value), style) for value in padded[:12]])

    table = Table(hunt_rows, colWidths=column_widths(), repeatRows=2)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(theme.table_header_primary)),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor(theme.table_header_secondary)),
                ("TEXTCOLOR", (0, 0), (-1, 1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(theme.table_grid)),
                ("ROWBACKGROUNDS", (0, 2), (-1, -1), [colors.HexColor(theme.table_row_a), colors.HexColor(theme.table_row_b)]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("SPAN", (0, 0), (5, 0)),
                ("SPAN", (6, 0), (11, 0)),
                ("LINEAFTER", (5, 0), (5, -1), 1.0, colors.HexColor(theme.table_divider)),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def draw_brand_image(cv: canvas.Canvas, image_path: Path | None, x: float, y: float, max_width: float, max_height: float) -> None:
    if not image_path or not image_path.exists():
        return
    image = ImageReader(str(image_path))
    width, height = image.getSize()
    if not width or not height:
        return
    scale = min(max_width / width, max_height / height)
    draw_width = width * scale
    draw_height = height * scale
    cv.drawImage(image, x, y - draw_height, width=draw_width, height=draw_height, mask="auto", preserveAspectRatio=True)


def draw_centered_watermark(
    cv: canvas.Canvas,
    image_path: Path | None,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    max_width_ratio: float = 0.45,
    max_height_ratio: float = 0.90,
    opacity: float = 0.25,
) -> None:
    if not image_path or not image_path.exists():
        return
    image = ImageReader(str(image_path))
    img_w, img_h = image.getSize()
    if not img_w or not img_h:
        return
    max_width = width * max_width_ratio
    max_height = height * max_height_ratio
    scale = min(max_width / img_w, max_height / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    draw_x = x + ((width - draw_w) / 2)
    draw_y = y + ((height - draw_h) / 2)
    cv.saveState()
    try:
        cv.setFillAlpha(opacity)
    except AttributeError:
        pass
    cv.drawImage(
        image,
        draw_x,
        draw_y,
        width=draw_w,
        height=draw_h,
        mask="auto",
        preserveAspectRatio=True,
    )
    cv.restoreState()


def draw_wrapped_lines(
    cv: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    *,
    font_name: str,
    font_size: float,
    leading: float,
    max_lines: int,
    color: str,
) -> None:
    cv.setFillColor(colors.HexColor(color))
    cv.setFont(font_name, font_size)
    if not text:
        return
    words = clean_text(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if pdfmetrics.stringWidth(trial, font_name, font_size) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        clipped = lines[:max_lines]
        last = clipped[-1]
        while pdfmetrics.stringWidth(last + "...", font_name, font_size) > width and last:
            last = last[:-1]
        clipped[-1] = (last + "...").rstrip(".") + "..."
        lines = clipped
    for idx, line in enumerate(lines[:max_lines]):
        cv.drawString(x, y_top - (idx * leading), line)


def draw_season_dropdown_box(
    cv: canvas.Canvas,
    theme: PacketTheme,
    x: float,
    y: float,
    width: float,
    height: float,
    season_text: str,
    dropdown_watermark: Path | None = None,
) -> None:
    shadow = colors.HexColor("#6B4A1E")
    border = colors.HexColor(theme.table_divider)
    fill = colors.HexColor("#F7C56B")
    text = colors.HexColor("#2F1B06")

    cv.setFillColor(shadow)
    cv.setStrokeColor(shadow)
    cv.setLineWidth(0.8)
    cv.rect(x + 0.04 * inch, y - 0.04 * inch, width, height, stroke=1, fill=1)

    cv.setFillColor(fill)
    cv.setStrokeColor(border)
    cv.setLineWidth(1.4)
    cv.rect(x, y, width, height, stroke=1, fill=1)

    draw_centered_watermark(
        cv,
        dropdown_watermark,
        x,
        y,
        width,
        height,
        max_width_ratio=0.34,
        max_height_ratio=0.92,
        opacity=0.25,
    )

    cv.setFillColor(text)
    cv.setFont(ARIAL_FONT_NAME, 10.2)
    cv.drawCentredString(x + (width / 2), y + 0.11 * inch, "HUNT SEASON v")


def add_season_dropdown_field(
    cv: canvas.Canvas,
    *,
    field_name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    season_text: str,
) -> None:
    field_x = x
    field_y = y
    field_w = width
    field_h = height
    options = season_dropdown_options(season_text)
    cv.acroForm.choice(
        name=field_name,
        tooltip="Hunt Season",
        value=options[0],
        options=options,
        x=field_x,
        y=field_y,
        width=field_w,
        height=field_h,
        fontName="Helvetica",
        fontSize=0.1,
        textColor=colors.transparent,
        fillColor=colors.transparent,
        borderColor=colors.transparent,
        borderWidth=0,
        borderStyle="solid",
        fieldFlags="combo",
        forceBorder=False,
    )


def draw_watermark_image(
    cv: canvas.Canvas,
    image_path: Path | None,
    page_width: float,
    page_height: float,
    *,
    max_width: float,
    max_height: float,
    opacity: float = 0.10,
    offset_y: float = 0.0,
) -> None:
    if not image_path or not image_path.exists():
        return
    image = ImageReader(str(image_path))
    width, height = image.getSize()
    if not width or not height:
        return
    scale = min(max_width / width, max_height / height)
    draw_width = width * scale
    draw_height = height * scale
    x = (page_width - draw_width) / 2
    y = ((page_height - draw_height) / 2) + offset_y
    cv.saveState()
    try:
        cv.setFillAlpha(opacity)
    except AttributeError:
        pass
    cv.drawImage(
        image,
        x,
        y,
        width=draw_width,
        height=draw_height,
        mask="auto",
        preserveAspectRatio=True,
    )
    cv.restoreState()


def derive_species_label(title: str) -> str:
    lowered = normalized_title(title).lower()
    candidates = [
        "Rocky Mountain Bighorn Sheep",
        "Desert Bighorn Sheep",
        "Black Bear",
        "Mountain Goat",
        "Pronghorn",
        "Bison",
        "Moose",
        "Turkey",
        "Elk",
        "Deer",
        "Cougar",
    ]
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate
    return normalized_title(title)


def draw_cover_page(
    cv: canvas.Canvas,
    page_width: float,
    page_height: float,
    title: str,
    species_label: str,
    brand_left: Path | None,
    brand_right: Path | None,
    species_art: Path | None,
    theme: PacketTheme,
) -> None:
    margin = 0.28 * inch
    header_height = 0.92 * inch
    cv.setFillColor(colors.HexColor(theme.cover_bg))
    cv.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    cv.setStrokeColor(colors.HexColor(theme.cover_border_dark))
    cv.setLineWidth(2.0)
    cv.roundRect(margin, margin, page_width - (margin * 2), page_height - (margin * 2), 0.24 * inch, stroke=1, fill=0)
    cv.setStrokeColor(colors.HexColor(theme.cover_border_accent))
    cv.setLineWidth(1.2)
    cv.roundRect(margin + 0.08 * inch, margin + 0.08 * inch, page_width - (margin * 2) - 0.16 * inch, page_height - (margin * 2) - 0.16 * inch, 0.20 * inch, stroke=1, fill=0)
    cv.setFillColor(colors.HexColor(theme.cover_header_fill))
    cv.roundRect(margin + 0.20 * inch, page_height - margin - header_height, page_width - (margin * 2) - 0.40 * inch, header_height, 0.18 * inch, stroke=0, fill=1)
    draw_brand_image(cv, brand_left, margin + 0.34 * inch, page_height - margin - 0.22 * inch, 0.72 * inch, 0.72 * inch)
    draw_brand_image(cv, brand_right, page_width - margin - 1.72 * inch, page_height - margin - 0.18 * inch, 1.45 * inch, 0.72 * inch)
    cv.setFillColor(colors.white)
    cv.setFont("Helvetica-Bold", 20)
    cv.drawCentredString(page_width / 2, page_height - margin - 0.34 * inch, "Utah DWR Draw Results")
    cv.setFillColor(colors.HexColor(theme.cover_accent_text))
    cv.setFont("Helvetica-Bold", 18)
    cv.drawCentredString(page_width / 2, page_height - margin - 0.62 * inch, "Brought to you by Utah Outfitter and Guide Assn. (U.O.G.A)")
    draw_watermark_image(
        cv,
        species_art,
        page_width,
        page_height,
        max_width=page_width * 0.56,
        max_height=page_height * 0.60,
        opacity=theme.cover_watermark_opacity,
        offset_y=-0.28 * inch,
    )
    cv.setFillColor(colors.HexColor(theme.cover_title_text))
    cv.setFont("Times-Bold", 24)
    cv.drawCentredString(page_width / 2, page_height - 1.72 * inch, species_label.upper())
    cv.setFont("Helvetica-Bold", 15)
    cv.drawCentredString(page_width / 2, page_height - 2.04 * inch, "Draw Results Packet")
    cv.setFont("Times-Bold", 22)
    cv.drawCentredString(page_width / 2, page_height - 2.72 * inch, normalized_title(title))
    cv.setFillColor(colors.HexColor(theme.cover_body_text))
    cv.setFont("Helvetica", 11)
    cv.drawCentredString(page_width / 2, page_height - 3.08 * inch, "Official-source formatted packet with one hunt code per page")
    cv.drawCentredString(page_width / 2, page_height - 3.30 * inch, "Resident point ladders on the left | Nonresident point ladders on the right")
    cv.setStrokeColor(colors.HexColor(theme.cover_rule))
    cv.setLineWidth(0.5)
    rule_y = page_height - 3.55 * inch
    cv.line(0.80 * inch, rule_y, page_width - 0.80 * inch, rule_y)
    cv.setFont("Helvetica", 11)
    cv.drawCentredString(page_width / 2, 1.10 * inch, "Species watermark and header art are for packet identity only")
    cv.drawCentredString(page_width / 2, 0.85 * inch, "Source tables remain preserved in the public-facing ladder layout")
    cv.setFont("Helvetica-Oblique", 10)
    cv.drawCentredString(page_width / 2, 0.55 * inch, "Formatted for public display from official source tables")
    cv.setFont("Helvetica", 8)
    cv.drawRightString(page_width - 0.42 * inch, 0.24 * inch, f"Page {cv.getPageNumber()}")
    cv.showPage()


def build_pdf(
    blocks: list[PageBlock],
    output_pdf: Path,
    title: str,
    brand_left: Path | None = None,
    brand_right: Path | None = None,
    species_art: Path | None = None,
    dropdown_watermark: Path | None = None,
    theme: PacketTheme | None = None,
    include_cover: bool = True,
) -> None:
    theme = theme or THEMES["dark_packet"]
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(letter)
    margin_x = TABLE_SIDE_MARGIN
    margin_top = 0.26 * inch
    margin_bottom = 0.30 * inch
    usable_width = page_width - (margin_x * 2)
    usable_height = page_height - margin_top - margin_bottom
    styles = getSampleStyleSheet()
    cv = canvas.Canvas(str(output_pdf), pagesize=(page_width, page_height))
    if include_cover:
        draw_cover_page(
            cv,
            page_width,
            page_height,
            title,
            derive_species_label(title),
            brand_left,
            brand_right,
            species_art,
            theme,
        )

    grouped: dict[str, list[PageBlock]] = {}
    for block in blocks:
        grouped.setdefault(block.hunt_code, []).append(block)

    for hunt_code in sorted(grouped):
        entries = grouped[hunt_code]
        current_y = page_height - margin_top
        blocks_on_current_page = 0
        code_title = f"{hunt_code}  {normalized_title(entries[0].hunt_name)}"

        def start_page():
            nonlocal current_y, blocks_on_current_page
            outer_margin = 0.28 * inch
            band_height = 0.78 * inch
            top_tan_gap = 0.24 * inch
            cv.setFillColor(colors.HexColor(theme.page_bg))
            cv.rect(0, 0, page_width, page_height, stroke=0, fill=1)
            if theme.page_frame:
                cv.setStrokeColor(colors.HexColor(theme.page_frame_dark))
                cv.setLineWidth(1.8)
                cv.roundRect(outer_margin, outer_margin, page_width - (outer_margin * 2), page_height - (outer_margin * 2), 0.22 * inch, stroke=1, fill=0)
                cv.setStrokeColor(colors.HexColor(theme.page_frame_accent))
                cv.setLineWidth(1.0)
                cv.roundRect(outer_margin + 0.07 * inch, outer_margin + 0.07 * inch, page_width - (outer_margin * 2) - 0.14 * inch, page_height - (outer_margin * 2) - 0.14 * inch, 0.18 * inch, stroke=1, fill=0)
            band_x = outer_margin + 0.16 * inch
            band_y = page_height - outer_margin - top_tan_gap - band_height
            band_w = page_width - (outer_margin * 2) - 0.32 * inch

            # recessed panel shadow + bevel
            cv.setFillColor(colors.HexColor("#2E1707"))
            cv.roundRect(band_x + 0.03 * inch, band_y - 0.04 * inch, band_w, band_height, 0.16 * inch, stroke=0, fill=1)
            cv.setFillColor(colors.HexColor(theme.page_header_fill))
            cv.roundRect(band_x, band_y, band_w, band_height, 0.16 * inch, stroke=0, fill=1)
            cv.setStrokeColor(colors.HexColor("#7A4C20"))
            cv.setLineWidth(0.7)
            cv.roundRect(band_x + 0.03 * inch, band_y + 0.03 * inch, band_w - 0.06 * inch, band_height - 0.06 * inch, 0.13 * inch, stroke=1, fill=0)
            cv.setStrokeColor(colors.HexColor("#241203"))
            cv.setLineWidth(1.0)
            cv.line(band_x + 0.14 * inch, band_y + 0.06 * inch, band_x + band_w - 0.14 * inch, band_y + 0.06 * inch)
            cv.setStrokeColor(colors.HexColor("#8F5E30"))
            cv.setLineWidth(0.8)
            cv.line(band_x + 0.14 * inch, band_y + band_height - 0.08 * inch, band_x + band_w - 0.14 * inch, band_y + band_height - 0.08 * inch)
            draw_brand_image(cv, brand_left, band_x + 0.10 * inch, page_height - outer_margin - 0.10 * inch, 0.60 * inch, 0.60 * inch)
            draw_brand_image(cv, brand_right, band_x + band_w - 1.58 * inch, page_height - outer_margin - 0.08 * inch, 1.38 * inch, 0.60 * inch)
            cv.setFillColor(colors.HexColor(theme.page_header_text))
            cv.setFont("Helvetica-Bold", 14.5)
            cv.drawCentredString(page_width / 2, band_y + 0.50 * inch, "Utah DWR Draw Results")
            cv.setFillColor(colors.HexColor(theme.page_header_accent))
            cv.setFont("Helvetica-Bold", 12.5)
            cv.drawCentredString(page_width / 2, band_y + 0.22 * inch, "Brought to you by Utah Outfitter and Guide Assn. (U.O.G.A)")
            title_y = band_y - 0.30 * inch
            cv.setFillColor(colors.HexColor(theme.page_title_text))
            season_box_w = 2.85 * inch
            season_box_h = 0.34 * inch
            season_box_x = page_width - outer_margin - 0.34 * inch - season_box_w
            season_box_y = title_y - 0.05 * inch
            draw_wrapped_lines(
                cv,
                code_title,
                outer_margin + 0.36 * inch,
                title_y + 0.02 * inch,
                season_box_x - (outer_margin + 0.52 * inch),
                font_name=ARIAL_BOLD_FONT_NAME,
                font_size=16.0,
                leading=17.0,
                max_lines=2,
                color=theme.page_title_text,
            )
            draw_season_dropdown_box(
                cv,
                theme,
                season_box_x,
                season_box_y,
                season_box_w,
                season_box_h,
                entries[0].season_text,
                dropdown_watermark,
            )
            add_season_dropdown_field(
                cv,
                field_name=f"season_dates_{entries[0].hunt_code}_{cv.getPageNumber()}",
                x=season_box_x,
                y=season_box_y,
                width=season_box_w,
                height=season_box_h,
                season_text=entries[0].season_text,
            )
            if theme.page_species_icon:
                draw_brand_image(cv, species_art, page_width - outer_margin - 1.20 * inch, page_height - outer_margin - 0.06 * inch, 0.26 * inch, 0.26 * inch)
            separator_y = season_box_y - 0.12 * inch
            cv.setStrokeColor(colors.HexColor(theme.cover_rule))
            cv.setLineWidth(0.55)
            cv.line(outer_margin + 0.24 * inch, separator_y, page_width - outer_margin - 0.24 * inch, separator_y)
            current_y = separator_y - 0.10 * inch
            blocks_on_current_page = 0

        start_page()

        for entry_index, entry in enumerate(entries):
            table = build_table(entry.rows, styles, theme)
            table_width, table_height = table.wrap(usable_width, usable_height)
            label_height = 0.0
            audience_label = ""
            if len(entries) > 1:
                audience_label = f"{entry.audience} Table"
                label_height = 0.20 * inch

            needed_height = table_height + label_height + (0.16 * inch if blocks_on_current_page else 0)
            if current_y - needed_height < margin_bottom and blocks_on_current_page > 0:
                cv.showPage()
                start_page()

            if blocks_on_current_page:
                current_y -= 0.16 * inch
            if audience_label:
                cv.setFont("Helvetica-Bold", 10)
                cv.drawString(margin_x, current_y - 0.02 * inch, audience_label)
                current_y -= label_height

            table.drawOn(cv, margin_x, current_y - table_height)
            current_y -= table_height
            blocks_on_current_page += 1

        cv.setFont("Helvetica", 8)
        cv.setFillColor(colors.HexColor(theme.page_header_accent))
        cv.drawRightString(page_width - 0.44 * inch, 0.26 * inch, f"Page {cv.getPageNumber()}")
        cv.showPage()

    cv.save()


def write_manifest(blocks: list[PageBlock], output_dir: Path, output_pdf: Path, title: str) -> None:
    rows = [
        {
            "hunt_code": block.hunt_code,
            "hunt_name": block.hunt_name,
            "source_report_page": block.source_report_page,
            "audience": block.audience,
            "table_rows": len(block.rows),
            "output_pdf": str(output_pdf),
            "title": title,
        }
        for block in blocks
    ]
    manifest_csv = output_dir / f"{output_pdf.stem}_manifest.csv"
    manifest_json = output_dir / f"{output_pdf.stem}_manifest.json"
    try:
        with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        manifest_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    except PermissionError:
        fallback_csv = output_dir / f"{output_pdf.stem}_manifest__new.csv"
        fallback_json = output_dir / f"{output_pdf.stem}_manifest__new.json"
        with fallback_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        fallback_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one-hunt-code-per-page draw-odds PDF from a source PDF and extracted workbook.")
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--source-xlsx", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-name", default="code_paged_draw_odds.pdf")
    parser.add_argument("--brand-left", type=Path)
    parser.add_argument("--brand-right", type=Path)
    parser.add_argument("--species-art", type=Path)
    parser.add_argument("--dropdown-watermark", type=Path)
    parser.add_argument("--theme", default="dark_packet")
    parser.add_argument("--no-cover", action="store_true")
    args = parser.parse_args()

    ensure_arial_fonts()
    blocks = build_blocks(args.source_pdf, args.source_xlsx)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = output_dir / args.output_name
    build_pdf(
        blocks,
        output_pdf,
        args.title,
        args.brand_left,
        args.brand_right,
        args.species_art,
        args.dropdown_watermark,
        get_theme(args.theme),
        include_cover=not args.no_cover,
    )
    write_manifest(blocks, output_dir, output_pdf, args.title)
    print(f"PDF: {output_pdf}")


if __name__ == "__main__":
    main()
