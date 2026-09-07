#!/usr/bin/env python3
"""Build 2025-style PDFs from the official 2026 UtahDraws antlerless results.

Utah DWR published these actual results through the UtahDraws online result
system.  This script joins the official resident and nonresident point rows by
hunt code and prints them side by side in the layout used by the 2025 DWR draw
odds PDF.  The values remain the official online results; only the PDF layout
is generated locally.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from promote_2026_utahdraws_antlerless_to_canonical import (
    ROOT,
    RAW_FILES,
    build_2025_style_wide_rows,
    build_promotion,
    clean,
)


OUTPUT_DIR = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2026"
    / "pdf"
    / "draw_odds"
    / "official_dwr_online_results"
)

COMBINED_FILENAME = "2026_utah_dwr_antlerless_draw_results.pdf"
SPECIES_FILENAMES = {
    "2026_antlerless_17_antlerless_deer.json": (
        "2026_utah_dwr_antlerless_deer_draw_results.pdf"
    ),
    "2026_antlerless_18_antlerless_elk.json": (
        "2026_utah_dwr_antlerless_elk_draw_results.pdf"
    ),
    "2026_antlerless_19_antlerless_moose.json": (
        "2026_utah_dwr_antlerless_moose_draw_results.pdf"
    ),
    "2026_antlerless_20_doe_pronghorn.json": (
        "2026_utah_dwr_doe_pronghorn_draw_results.pdf"
    ),
    "2026_antlerless_21_ewe_rocky_mtn_bighorn_sheep.json": (
        "2026_utah_dwr_ewe_rocky_mountain_bighorn_sheep_draw_results.pdf"
    ),
}
SPECIES_TITLES = {
    "2026_antlerless_17_antlerless_deer.json": "Antlerless Deer",
    "2026_antlerless_18_antlerless_elk.json": "Antlerless Elk",
    "2026_antlerless_19_antlerless_moose.json": "Antlerless Moose",
    "2026_antlerless_20_doe_pronghorn.json": "Doe Pronghorn",
    "2026_antlerless_21_ewe_rocky_mtn_bighorn_sheep.json": (
        "Ewe Rocky Mountain Bighorn Sheep"
    ),
}

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#DCE6F1")
LIGHT_BLUE = colors.HexColor("#EDF3F8")
GRID = colors.HexColor("#778899")
TEXT = colors.HexColor("#111111")
MUTED = colors.HexColor("#4D5966")


def ascii_text(value: object) -> str:
    """Keep the generated PDFs on the built-in Helvetica character set."""
    text = clean(value)
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def fit_text(
    pdf: canvas.Canvas,
    text: str,
    max_width: float,
    font: str = "Helvetica-Bold",
    max_size: float = 11.0,
    min_size: float = 7.0,
) -> float:
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.25
    pdf.setFont(font, size)
    return size


def draw_centered(
    pdf: canvas.Canvas,
    text: object,
    left: float,
    right: float,
    y: float,
    font: str,
    size: float,
    color: colors.Color = TEXT,
) -> None:
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawCentredString((left + right) / 2, y, ascii_text(text))


def draw_page(
    pdf: canvas.Canvas,
    rows: list[dict[str, str]],
    report_title: str,
    page_number: int,
    total_pages: int,
) -> None:
    width, height = landscape(letter)
    margin = 28
    table_left = margin
    table_right = width - margin
    table_width = table_right - table_left
    table_top = height - 93
    table_bottom = 49

    first = rows[0]
    is_youth = clean(first["is_youth"]).lower() == "true"
    section = "Youth" if is_youth else "Adult"
    hunt_line = f"Hunt: {first['hunt_code']} {first['hunt_name']}"

    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 39, width, 39, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(margin, height - 24, ascii_text(report_title))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - margin, height - 23, f"Page {page_number} of {total_pages}")

    pdf.setFillColor(TEXT)
    fit_text(pdf, ascii_text(hunt_line), table_width, max_size=11, min_size=7)
    pdf.drawString(margin, height - 57, ascii_text(hunt_line))
    pdf.setFont("Helvetica", 8.5)
    pdf.setFillColor(MUTED)
    descriptor = f"2026 Antlerless Draw - {section} applicant section"
    pdf.drawString(margin, height - 71, descriptor)
    pdf.drawRightString(width - margin, height - 71, "Actual official online results")

    # Two matched six-column applicant blocks, like the 2025 DWR report.
    half = table_width / 2
    block_gap = 8
    block_width = half - block_gap / 2
    resident_left = table_left
    resident_right = resident_left + block_width
    nonresident_left = resident_right + block_gap
    nonresident_right = table_right
    column_fractions = (0.10, 0.22, 0.16, 0.16, 0.16, 0.20)
    headers = ("Points", "Eligible", "Bonus", "Regular", "Total", "Success Ratio")

    group_header_height = 19
    column_header_height = 25
    body_count = len(rows)
    body_height = table_top - table_bottom - group_header_height - column_header_height
    row_height = min(17.0, body_height / max(1, body_count))
    if row_height < 10.5:
        raise RuntimeError(
            f"Hunt section {first['hunt_code']} has {body_count} rows and does not fit"
        )

    for left, right, label in (
        (resident_left, resident_right, "Resident Applicants"),
        (nonresident_left, nonresident_right, "Nonresident Applicants"),
    ):
        pdf.setFillColor(NAVY)
        pdf.rect(left, table_top - group_header_height, right - left, group_header_height, stroke=0, fill=1)
        draw_centered(
            pdf,
            label,
            left,
            right,
            table_top - group_header_height + 5.5,
            "Helvetica-Bold",
            9,
            colors.white,
        )
        x = left
        for fraction, header in zip(column_fractions, headers):
            next_x = x + (right - left) * fraction
            pdf.setFillColor(BLUE)
            pdf.rect(
                x,
                table_top - group_header_height - column_header_height,
                next_x - x,
                column_header_height,
                stroke=0,
                fill=1,
            )
            words = header.split(" ")
            if len(words) == 1:
                draw_centered(pdf, words[0], x, next_x, table_top - 34, "Helvetica-Bold", 7.5)
            else:
                draw_centered(pdf, words[0], x, next_x, table_top - 29, "Helvetica-Bold", 7.1)
                draw_centered(pdf, " ".join(words[1:]), x, next_x, table_top - 38, "Helvetica-Bold", 7.1)
            x = next_x

    body_top = table_top - group_header_height - column_header_height
    resident_fields = (
        "points",
        "resident_eligible_applicants",
        "resident_bonus_permits",
        "resident_regular_permits",
        "resident_total_permits",
        "resident_success_ratio",
    )
    nonresident_fields = (
        "points",
        "nonresident_eligible_applicants",
        "nonresident_bonus_permits",
        "nonresident_regular_permits",
        "nonresident_total_permits",
        "nonresident_success_ratio",
    )
    for index, row in enumerate(rows):
        row_top = body_top - index * row_height
        row_bottom = row_top - row_height
        is_total = row["row_type"] == "TOTALS"
        fill = BLUE if is_total else (LIGHT_BLUE if index % 2 else colors.white)
        font = "Helvetica-Bold" if is_total else "Helvetica"
        size = max(6.5, min(8.0, row_height * 0.46))
        for left, right, fields in (
            (resident_left, resident_right, resident_fields),
            (nonresident_left, nonresident_right, nonresident_fields),
        ):
            pdf.setFillColor(fill)
            pdf.rect(left, row_bottom, right - left, row_height, stroke=0, fill=1)
            x = left
            for fraction, field in zip(column_fractions, fields):
                next_x = x + (right - left) * fraction
                value = row[field]
                if not value and field != "points":
                    value = "0"
                draw_centered(
                    pdf,
                    value,
                    x,
                    next_x,
                    row_bottom + (row_height - size) / 2 + 1.6,
                    font,
                    size,
                )
                x = next_x

    # Draw the grid last so the table remains crisp over all row fills.
    body_bottom = body_top - body_count * row_height
    for left, right in (
        (resident_left, resident_right),
        (nonresident_left, nonresident_right),
    ):
        x_positions = [left]
        x = left
        for fraction in column_fractions:
            x += (right - left) * fraction
            x_positions.append(x)
        pdf.setStrokeColor(GRID)
        pdf.setLineWidth(0.45)
        for x in x_positions:
            pdf.line(x, body_bottom, x, table_top - group_header_height)
        pdf.rect(
            left,
            body_bottom,
            right - left,
            table_top - body_bottom,
            stroke=1,
            fill=0,
        )
        pdf.line(left, body_top, right, body_top)
        for index in range(body_count + 1):
            y = body_top - index * row_height
            pdf.line(left, y, right, y)

    pdf.setFont("Helvetica", 6.7)
    pdf.setFillColor(MUTED)
    pdf.drawString(
        margin,
        28,
        "Source: Utah DWR official 2026 online draw results (UtahDraws), retrieved September 2, 2026.",
    )
    pdf.drawRightString(
        width - margin,
        28,
        "Formatted reproduction - official result values are unchanged.",
    )
    pdf.showPage()


def grouped_sections(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["hunt_code"], row["is_youth"])].append(row)
    return list(groups.values())


def build_pdf(path: Path, rows: list[dict[str, str]], report_title: str) -> int:
    sections = grouped_sections(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=landscape(letter), pageCompression=1)
    pdf.setTitle(ascii_text(report_title))
    pdf.setAuthor("Utah Division of Wildlife Resources data; formatted by HUNT-BUILDER")
    pdf.setSubject("Actual 2026 Utah DWR online antlerless draw results")
    for page_number, section_rows in enumerate(sections, start=1):
        draw_page(pdf, section_rows, report_title, page_number, len(sections))
    pdf.save()
    return len(sections)


def main() -> None:
    result = build_promotion()
    wide_rows = build_2025_style_wide_rows(result["promoted_rows"])
    expected_source_files = {Path(name).with_suffix(".json").name for name in RAW_FILES}
    if set(SPECIES_FILENAMES) != expected_source_files:
        raise RuntimeError("PDF output mapping does not match the official source packages")
    if set(SPECIES_TITLES) != expected_source_files:
        raise RuntimeError("PDF title mapping does not match the official source packages")

    outputs: list[tuple[Path, int]] = []
    combined_path = OUTPUT_DIR / COMBINED_FILENAME
    outputs.append(
        (
            combined_path,
            build_pdf(
                combined_path,
                wide_rows,
                "2026 Utah DWR Antlerless Draw Results",
            ),
        )
    )
    for source_file, filename in SPECIES_FILENAMES.items():
        species_rows = [row for row in wide_rows if row["source_file"] == source_file]
        if not species_rows:
            raise RuntimeError(f"No official rows found for {source_file}")
        title_species = SPECIES_TITLES[source_file]
        output_path = OUTPUT_DIR / filename
        outputs.append(
            (
                output_path,
                build_pdf(
                    output_path,
                    species_rows,
                    f"2026 Utah DWR {title_species} Draw Results",
                ),
            )
        )

    print(f"Created {len(outputs)} PDF reports in {OUTPUT_DIR}")
    for path, pages in outputs:
        print(f"{path.name}: {pages} pages")


if __name__ == "__main__":
    main()
