#!/usr/bin/env python3
"""Build one UOGA-styled elk page proving the proposed species-art treatment."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from build_2026_utahdraws_uoga_pdfs import (
    DEFAULT_LOGO,
    GRID,
    MUTED,
    ROOT,
    TEXT,
    UOGA_BLACK,
    UOGA_BROWN,
    UOGA_CREAM,
    UOGA_DARK_BROWN,
    UOGA_FOREST,
    UOGA_OFF_WHITE,
    UOGA_TAN,
    ascii_text,
    build_sections,
    draw_centered,
    fit_font,
    validate_sources,
)


ELK_ICON = ROOT / "assets/library-icons/elk.png"
OUTPUT = ROOT / "output/pdf/2026_utahdraws_uoga_mockups/2026_uoga_elk_all_white_cream_table_frame_sample.pdf"


def image_reader(image: Image.Image) -> ImageReader:
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return ImageReader(stream)


def monochrome_watermark(path: Path) -> ImageReader:
    source = Image.open(path).convert("RGBA")
    alpha = source.getchannel("A").point(lambda value: round(value * 0.085))
    tinted = Image.new("RGBA", source.size, (89, 39, 11, 0))
    tinted.putalpha(alpha)
    return image_reader(tinted)


def draw_sample() -> None:
    by_family, _ = validate_sources()
    sections = build_sections(by_family["big_game"])
    section = next(
        item for item in sections if item.hunt_code == "EB3067" and not item.is_youth
    )
    if len(section.point_rows) > 28:
        raise RuntimeError("Selected sample no longer fits on one page")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing sample: {OUTPUT}")
    pdf = canvas.Canvas(str(OUTPUT), pagesize=landscape(letter), pageCompression=1)
    pdf.setTitle("2026 UOGA Elk Species Art Design Proof")
    pdf.setAuthor("UOGA / HUNT-BUILDER")
    width, height = landscape(letter)
    margin = 27
    header_height = 58
    uoga_logo = ImageReader(str(DEFAULT_LOGO))
    watermark = monochrome_watermark(ELK_ICON)
    elk_header = ImageReader(str(ELK_ICON))
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.rect(0, height - header_height, width, header_height, stroke=0, fill=1)
    pdf.drawImage(
        uoga_logo,
        margin,
        height - 52,
        width=46,
        height=46,
        preserveAspectRatio=True,
        mask="auto",
    )
    title_x = margin + 58
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, height - 24, "2026 Utah Big Game Draw Results")
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica", 7.4)
    pdf.drawString(
        title_x,
        height - 39,
        "Official Utah DWR / UtahDraws values - UOGA-styled local reproduction",
    )

    art_left = width - 126
    art_bottom = height - header_height + 5
    art_width = 99
    art_height = header_height - 10
    pdf.drawImage(
        elk_header,
        art_left,
        art_bottom,
        width=art_width,
        height=art_height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(art_left - 10, height - 22, "ALL-WHITE / CREAM FRAME DESIGN PROOF")
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.rect(0, height - header_height - 4, width, 4, stroke=0, fill=1)

    table_left = margin
    table_right = width - margin
    table_width = table_right - table_left
    heading_y = height - 80
    hunt_line = f"Hunt: {section.hunt_code} {section.hunt_name}"
    size = fit_font(hunt_line, "Helvetica-Bold", 11, 7, table_width)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica-Bold", size)
    pdf.drawString(table_left, heading_y, ascii_text(hunt_line))
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        table_left,
        heading_y - 14,
        ascii_text(f"{section.hunt_category} | {section.species} | Adult"),
    )
    season_size = fit_font(section.seasons, "Helvetica", 7.2, 5.8, table_width * 0.58)
    pdf.setFont("Helvetica", season_size)
    pdf.drawRightString(table_right, heading_y - 14, ascii_text(section.seasons))

    table_top = height - 114
    table_bottom = 49
    group_header_height = 19
    column_header_height = 25
    display_rows = [
        *section.point_rows,
        {"points": {"value": "Totals"}, **section.totals},
    ]
    row_height = min(
        17.0,
        (table_top - table_bottom - group_header_height - column_header_height)
        / len(display_rows),
    )
    block_gap = 8
    block_width = (table_width - block_gap) / 2
    fractions = (0.10, 0.22, 0.16, 0.16, 0.16, 0.20)
    headers = ("Points", "Eligible", "Max / Bonus", "Regular", "Total", "Success Ratio")
    body_top = table_top - group_header_height - column_header_height
    body_bottom = body_top - len(display_rows) * row_height

    # The same cream used for the column-description row now surrounds each
    # table, replacing the earlier tan matte on the all-white page.
    for block_index in range(len(section.residencies)):
        left = table_left + block_index * (block_width + block_gap)
        pdf.setFillColor(UOGA_CREAM)
        pdf.setStrokeColor(UOGA_DARK_BROWN)
        pdf.setLineWidth(1.2)
        pdf.roundRect(
            left - 4,
            body_bottom - 4,
            block_width + 8,
            table_top - body_bottom + 8,
            4,
            stroke=1,
            fill=1,
        )

    for block_index, residency in enumerate(section.residencies):
        left = table_left + block_index * (block_width + block_gap)
        right = left + block_width
        pdf.setFillColor(UOGA_DARK_BROWN)
        pdf.rect(left, table_top - group_header_height, block_width, group_header_height, stroke=0, fill=1)
        draw_centered(
            pdf,
            f"{residency} Applicants",
            left,
            right,
            table_top - group_header_height + 5.5,
            "Helvetica-Bold",
            9,
            UOGA_CREAM,
        )
        x = left
        for fraction, header in zip(fractions, headers):
            next_x = x + block_width * fraction
            pdf.setFillColor(UOGA_CREAM)
            pdf.rect(x, body_top, next_x - x, column_header_height, stroke=0, fill=1)
            words = header.split(" ")
            if len(words) == 1:
                draw_centered(pdf, header, x, next_x, table_top - 34, "Helvetica-Bold", 7.4)
            else:
                split = len(words) // 2
                draw_centered(pdf, " ".join(words[:split]), x, next_x, table_top - 29, "Helvetica-Bold", 7.0)
                draw_centered(pdf, " ".join(words[split:]), x, next_x, table_top - 38, "Helvetica-Bold", 7.0)
            x = next_x

        for row_index, row in enumerate(display_rows):
            row_bottom = body_top - (row_index + 1) * row_height
            is_total = row["points"]["value"] == "Totals"
            pdf.setFillColor(
                UOGA_CREAM if is_total else (UOGA_OFF_WHITE if row_index % 2 else colors.white)
            )
            pdf.rect(left, row_bottom, block_width, row_height, stroke=0, fill=1)

        # The lightly colored art is laid over the row fills but beneath all
        # grid lines and values, which makes it read as a true table watermark.
        mark_width = block_width * 0.58
        mark_height = (body_top - body_bottom) * 0.50
        pdf.drawImage(
            watermark,
            left + (block_width - mark_width) / 2,
            body_bottom + ((body_top - body_bottom) - mark_height) / 2,
            width=mark_width,
            height=mark_height,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )

        for row_index, row in enumerate(display_rows):
            row_bottom = body_top - (row_index + 1) * row_height
            is_total = row["points"]["value"] == "Totals"
            font = "Helvetica-Bold" if is_total else "Helvetica"
            text_size = max(6.5, min(8.0, row_height * 0.46))
            values = [row["points"]["value"]]
            fields = ("eligible", "max_bonus", "regular", "total", "ratio")
            values.extend(row.get(residency, {}).get(field, "") for field in fields)
            x = left
            for fraction, value in zip(fractions, values):
                next_x = x + block_width * fraction
                draw_centered(
                    pdf,
                    value,
                    x,
                    next_x,
                    row_bottom + (row_height - text_size) / 2 + 1.6,
                    font,
                    text_size,
                )
                x = next_x

        x_positions = [left]
        x = left
        for fraction in fractions:
            x += block_width * fraction
            x_positions.append(x)
        pdf.setStrokeColor(GRID)
        pdf.setLineWidth(0.45)
        for x in x_positions:
            pdf.line(x, body_bottom, x, table_top - group_header_height)
        pdf.rect(left, body_bottom, block_width, table_top - body_bottom, stroke=1, fill=0)
        pdf.line(left, body_top, right, body_top)
        for row_index in range(len(display_rows) + 1):
            y = body_top - row_index * row_height
            pdf.line(left, y, right, y)

    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.setFont("Helvetica", 6.6)
    pdf.drawString(
        margin,
        28,
        "Source: Utah DWR official 2026 UtahDraws results, retrieved September 2, 2026.",
    )
    pdf.drawRightString(
        width - margin,
        28,
        "Visual proof only - existing report set has not been replaced.",
    )

    # Match the four-point dark-brown divider below the header around all four
    # outer page edges. The two-point inset keeps the full stroke printable.
    page_keyline_inset = 2
    pdf.setStrokeColor(UOGA_DARK_BROWN)
    pdf.setLineWidth(4)
    pdf.rect(
        page_keyline_inset,
        page_keyline_inset,
        width - (page_keyline_inset * 2),
        height - (page_keyline_inset * 2),
        stroke=1,
        fill=0,
    )
    pdf.showPage()
    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    draw_sample()
