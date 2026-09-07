#!/usr/bin/env python3
"""Create UOGA-styled PDF reports from retained official 2026 UtahDraws rows.

The source values remain Utah DWR/UtahDraws results. The PDFs are local
reproductions whose layout and branding are provided by UOGA/HUNT-BUILDER.
Every source row must pass explicit 2026 license-year and non-historical
checks before any PDF is written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (
    ROOT
    / "pipeline/RAW/hunt_unit_database/2026/json/draw_results"
    / "utahdraws_2026_20260902/utahdraws_2026"
)
SOURCE_DIR = SOURCE_ROOT / "csv"
SUPPLEMENT = SOURCE_ROOT / "json/draw_odds_supplement_data.json"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "output/pdf/2026_utahdraws_uoga_approved_white_cream_topo_youth_residency_fixed_20260902"
)
DEFAULT_LOGO = Path("P:/pictures/Imported from B Backup/UOGA LOGO CIRCLE 2.png")
DEFAULT_TOPO = ROOT / "assets/logos/tan-topo.png"
DEFAULT_DARK_HEADER_TOPO = ROOT / "assets/backgrounds/wild-eyez-dark-brown-topoDARK.png"
DEFAULT_BIGHORN_ICON = Path("P:/bighorn sheep vector.png")
DEFAULT_BEAR_ICON = Path("C:/Users/tyler/DOWNLOADS/black bear vector.png")
DEFAULT_MOOSE_ICON = Path("C:/Users/tyler/DOWNLOADS/moose vector.png")
MANIFEST_NAME = "2026_uoga_draw_results_pdf_manifest.json"
EXPECTED_PACKAGE_COUNT = 29
EXCLUDED_ARCHIVED_PRIOR_YEAR_CODES = {"EA1281"}
MAX_POINT_ROWS_PER_PAGE = 28
YOUTH_DISPLAY_RESIDENCIES = ["Resident", "Nonresident"]
SPORTSMAN_SECTIONS_PER_PAGE = 2
COMPACT_STANDARD_MAX_POINT_ROWS = 10
COMPACT_STANDARD_SECTIONS_PER_PAGE = 2


FAMILY_CONFIG = {
    "antlerless": {
        "title": "2026 Utah Antlerless Draw Results",
        "filename": "2026_uoga_antlerless_draw_results_corrected.pdf",
        "prefix": "2026_antlerless_",
    },
    "big_game": {
        "title": "2026 Utah Big Game Draw Results",
        "filename": "2026_uoga_big_game_draw_results.pdf",
        "prefix": "2026_big_game_",
    },
    "black_bear": {
        "title": "2026 Utah Black Bear Draw Results",
        "filename": "2026_uoga_black_bear_draw_results.pdf",
        "prefix": "2026_black_bear_",
    },
    "turkey": {
        "title": "2026 Utah Turkey Draw Results",
        "filename": "2026_uoga_turkey_draw_results.pdf",
        "prefix": "2026_turkey_",
    },
    "sportsman": {
        "title": "2026 Utah Sportsman Draw Results",
        "filename": "2026_uoga_sportsman_draw_results.pdf",
        "prefix": "2026_sportsman_",
    },
}


# Colors sampled from the current uoga.org site on September 2, 2026.
UOGA_BLACK = colors.HexColor("#000000")
UOGA_BROWN = colors.HexColor("#59270B")
UOGA_DARK_BROWN = colors.HexColor("#3E1C00")
UOGA_CREAM = colors.HexColor("#F4EBD7")
UOGA_FOREST = colors.HexColor("#003314")
UOGA_OFF_WHITE = colors.HexColor("#FBFAF7")
UOGA_TAN = colors.HexColor("#9A8669")
TOPO_CREAM = colors.HexColor("#F6EBD7")
TOPO_OPACITY = 0.12
TEXT = colors.HexColor("#1F1F1F")
MUTED = colors.HexColor("#55514A")
GRID = colors.HexColor("#7A766C")


BUILTIN_SPECIES_ICON_PATHS = {
    "bison": ROOT / "assets/library-icons/bison.png",
    "cougar": ROOT / "assets/library-icons/cougar.png",
    "deer": ROOT / "assets/library-icons/mule_deer.png",
    "elk": ROOT / "assets/library-icons/elk.png",
    "mountain_goat": ROOT / "assets/library-icons/mountain_goat.png",
    "pronghorn": ROOT / "assets/library-icons/pronghorn.png",
    "turkey": ROOT / "assets/library-icons/turkey.png",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def integer(value: object) -> int:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    return int(float(text))


def point_text(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    number = float(text)
    return str(int(number)) if number.is_integer() else str(number)


def ascii_text(value: object) -> str:
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
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text.encode("cp1252", errors="replace").decode("cp1252")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_reader(image: Image.Image) -> ImageReader:
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return ImageReader(stream)


def monochrome_watermark(path: Path) -> ImageReader:
    with Image.open(path) as opened:
        source = opened.convert("RGBA")
    alpha = source.getchannel("A").point(lambda value: round(value * 0.085))
    tinted = Image.new("RGBA", source.size, (89, 39, 11, 0))
    tinted.putalpha(alpha)
    return image_reader(tinted)


def species_art_key(species: str) -> str | None:
    value = clean(species).lower()
    for needle, key in (
        ("turkey", "turkey"),
        ("black bear", "bear"),
        ("bear", "bear"),
        ("bighorn", "bighorn"),
        ("mountain goat", "mountain_goat"),
        ("pronghorn", "pronghorn"),
        ("moose", "moose"),
        ("bison", "bison"),
        ("two doe", "deer"),
        ("deer", "deer"),
        ("elk", "elk"),
        ("cougar", "cougar"),
        ("lion", "cougar"),
    ):
        if needle in value:
            return key
    return None


def load_species_art(
    paths: dict[str, Path],
) -> tuple[
    dict[str, tuple[ImageReader, ImageReader]],
    dict[str, dict[str, str]],
]:
    art: dict[str, tuple[ImageReader, ImageReader]] = {}
    manifest: dict[str, dict[str, str]] = {}
    for key, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{key} species artwork not found: {path}")
        with Image.open(path) as opened:
            if "A" not in opened.getbands():
                raise RuntimeError(
                    f"{key} species artwork must retain a transparent background: {path}"
                )
        art[key] = (ImageReader(str(path)), monochrome_watermark(path))
        manifest[key] = {"source_path": str(path), "sha256": sha256(path)}
    return art, manifest


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def dwr_ratio(applicants: int, successful: int) -> str:
    if applicants <= 0 or successful <= 0:
        return "N/A"
    return f"1 in {applicants / successful:.1f}"


def empty_display_result() -> dict[str, str]:
    """Return a display-only zero row for a residency omitted by UtahDraws.

    The retained 2026 endpoint suppresses some zero-activity youth residency
    rows. Historical DWR youth PDFs still printed both residency panels with
    zeroes and N/A, so the PDF restores that presentation without creating a
    canonical source row.
    """
    return {
        "eligible": "0",
        "max_bonus": "0",
        "regular": "0",
        "total": "0",
        "ratio": "N/A",
    }


def source_files() -> list[Path]:
    files = [
        path
        for path in SOURCE_DIR.glob("2026_*.csv")
        if path.name != "2026_allowed_draw_odds_all_flat_rows.csv"
    ]
    return sorted(files)


def family_for(path: Path) -> str:
    matches = [
        family
        for family, config in FAMILY_CONFIG.items()
        if path.name.startswith(str(config["prefix"]))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Unmapped 2026 result package: {path.name}")
    return matches[0]


def validate_sources() -> tuple[dict[str, list[dict[str, str]]], dict[str, object]]:
    files = source_files()
    if len(files) != EXPECTED_PACKAGE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_PACKAGE_COUNT} retained 2026 packages; found {len(files)}"
        )

    supplement = json.loads(SUPPLEMENT.read_text(encoding="utf-8-sig"))
    descriptors = supplement["Data"]["DrawNameAvailableLicenseYears"]
    if any(int(item["LicenseYear"]) != 2026 for item in descriptors):
        raise RuntimeError("UtahDraws package metadata contains a non-2026 license year")
    descriptor_ids = {str(item["MasterHuntTypeID"]) for item in descriptors}

    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    package_rows: dict[str, int] = {}
    package_hashes: dict[str, str] = {}
    license_year_counts: Counter[int] = Counter()
    season_start_year_counts: Counter[int] = Counter()
    historical_values: Counter[str] = Counter()
    source_codes: Counter[str] = Counter()
    source_identities: set[tuple[str, str, str, str, str]] = set()

    for path in files:
        family = family_for(path)
        rows = read_csv(path)
        if not rows:
            raise RuntimeError(f"Source package has no rows: {path.name}")
        expected_source_json = path.with_suffix(".json").name
        for row_number, row in enumerate(rows, start=2):
            source_json = clean(row.get("source_json_file"))
            if source_json != expected_source_json:
                raise RuntimeError(
                    f"{path.name}:{row_number} source file mismatch: {source_json}"
                )
            if clean(row.get("MasterHuntTypeID")) not in descriptor_ids:
                raise RuntimeError(
                    f"{path.name}:{row_number} is absent from 2026 package metadata"
                )
            historical = clean(row.get("IsHistoricalData"))
            historical_values[historical] += 1
            if historical.lower() != "false":
                raise RuntimeError(
                    f"{path.name}:{row_number} is historical rather than 2026 actual data"
                )
            code = clean(row.get("HuntCode")).upper()
            if code in EXCLUDED_ARCHIVED_PRIOR_YEAR_CODES:
                raise RuntimeError(
                    f"Archived prior-year hunt {code} appeared in a 2026 result package"
                )
            source_codes[code] += 1
            seasons_text = clean(row.get("SeasonWeapons"))
            if seasons_text:
                try:
                    seasons = json.loads(seasons_text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"{path.name}:{row_number} has invalid SeasonWeapons JSON"
                    ) from exc
                for season in seasons:
                    year = int(season["LicenseYear"])
                    license_year_counts[year] += 1
                    if year != 2026:
                        raise RuntimeError(
                            f"{path.name}:{row_number} contains LicenseYear={year}"
                        )
                    start_year = int(clean(season.get("SeasonStartDate"))[:4])
                    season_start_year_counts[start_year] += 1
                    if start_year < 2026:
                        raise RuntimeError(
                            f"{path.name}:{row_number} contains a prior-year season start: "
                            f"{season.get('SeasonStartDate')}"
                        )
            identity = (
                path.name,
                clean(row.get("HuntID")),
                clean(row.get("residency_label")),
                clean(row.get("IsYouth")).lower(),
                point_text(row.get("Point")),
            )
            if identity in source_identities:
                raise RuntimeError(f"Duplicate source point identity: {identity}")
            source_identities.add(identity)
            row["_source_csv"] = path.name
            row["_family"] = family
            by_family[family].append(row)
        package_rows[path.name] = len(rows)
        package_hashes[path.name] = sha256(path)

    if set(by_family) != set(FAMILY_CONFIG):
        raise RuntimeError(
            f"Expected report families {sorted(FAMILY_CONFIG)}; found {sorted(by_family)}"
        )
    validation = {
        "source_package_count": len(files),
        "source_row_count": sum(package_rows.values()),
        "source_hunt_code_count": len(source_codes),
        "package_row_counts": package_rows,
        "source_sha256": package_hashes,
        "season_license_year_counts": dict(sorted(license_year_counts.items())),
        "season_start_year_counts": dict(sorted(season_start_year_counts.items())),
        "calendar_2025_season_start_count": season_start_year_counts[2025],
        "is_historical_data_counts": dict(sorted(historical_values.items())),
        "archived_prior_year_codes_excluded": sorted(EXCLUDED_ARCHIVED_PRIOR_YEAR_CODES),
        "archived_prior_year_code_matches": {
            code: source_codes[code] for code in sorted(EXCLUDED_ARCHIVED_PRIOR_YEAR_CODES)
        },
        "year_guard": (
            "Every retained row is IsHistoricalData=False; every populated "
            "SeasonWeapons LicenseYear is 2026; no season starts in 2025; "
            "EA1281 is absent. Calendar-year 2027 starts remain valid where "
            "the official record assigns LicenseYear 2026."
        ),
    }
    return dict(by_family), validation


def season_summary(row: dict[str, str]) -> str:
    raw = clean(row.get("SeasonWeapons"))
    if not raw:
        return "Season information not published in this result row"
    seasons = json.loads(raw)
    descriptions = []
    for season in seasons:
        start = clean(season.get("SeasonStartDate"))[:10]
        end = clean(season.get("SeasonEndDate"))[:10]
        weapon = clean(season.get("WeaponName")) or "Unspecified weapon"
        descriptions.append(f"{weapon}: {start} to {end}")
    return "; ".join(descriptions)


@dataclass
class Section:
    source_csv: str
    hunt_id: str
    hunt_code: str
    hunt_name: str
    hunt_category: str
    species: str
    is_youth: bool
    seasons: str
    residencies: list[str]
    point_rows: list[dict[str, dict[str, str]]]
    totals: dict[str, dict[str, str]]


def build_sections(rows: list[dict[str, str]]) -> list[Section]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                clean(row.get("_source_csv")),
                clean(row.get("HuntID")),
                clean(row.get("IsYouth")).lower(),
            )
        ].append(row)

    sections: list[Section] = []
    for (source_csv, hunt_id, youth_text), group in grouped.items():
        first = group[0]
        source_residencies = sorted(
            {clean(row.get("residency_label")) for row in group},
            key=lambda value: (value.lower() != "resident", value.lower()),
        )
        if not 1 <= len(source_residencies) <= 2:
            raise RuntimeError(
                f"{source_csv} HuntID {hunt_id} has unsupported residencies: "
                f"{source_residencies}"
            )
        is_youth = youth_text == "true"
        # DWR's published tables show the complete point ladder in each
        # residency panel. UtahDraws may omit a zero-activity residency/rung
        # combination, which otherwise creates misleading blank cells when
        # the two panels are placed side by side. Restore the DWR display form
        # (0 / 0 / 0 / 0 / N/A) in the PDF only; retained source rows and
        # canonical truth stay intact.
        residencies = (
            list(YOUTH_DISPLAY_RESIDENCIES) if is_youth else source_residencies
        )
        by_point: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
        for row in group:
            point = point_text(row.get("Point"))
            residency = clean(row.get("residency_label"))
            applicants = integer(row.get("ParticipantCount"))
            successful = integer(row.get("SuccessfulCount"))
            by_point[point][residency] = {
                "eligible": str(applicants),
                "max_bonus": str(integer(row.get("SuccessfulByMaxPointRoundCount"))),
                "regular": str(integer(row.get("SuccessfulByRegularRoundCount"))),
                "total": str(successful),
                "ratio": dwr_ratio(applicants, successful),
            }
        points = sorted(
            by_point,
            key=lambda value: float(value) if value else -1,
            reverse=True,
        )
        for point in points:
            for residency in residencies:
                by_point[point].setdefault(residency, empty_display_result())
        point_rows = [
            {"points": {"value": point}, **by_point[point]} for point in points
        ]
        totals: dict[str, dict[str, str]] = {}
        for residency in residencies:
            residency_rows = [
                row[residency] for row in point_rows if residency in row
            ]
            applicants = sum(integer(row["eligible"]) for row in residency_rows)
            successful = sum(integer(row["total"]) for row in residency_rows)
            totals[residency] = {
                "eligible": str(applicants),
                "max_bonus": str(sum(integer(row["max_bonus"]) for row in residency_rows)),
                "regular": str(sum(integer(row["regular"]) for row in residency_rows)),
                "total": str(successful),
                "ratio": dwr_ratio(applicants, successful),
            }
        sections.append(
            Section(
                source_csv=source_csv,
                hunt_id=hunt_id,
                hunt_code=clean(first.get("HuntCode")),
                hunt_name=clean(first.get("HuntName")),
                hunt_category=clean(first.get("HuntCategoryName")),
                species=clean(first.get("SpeciesSubtypeName")),
                is_youth=is_youth,
                seasons=season_summary(first),
                residencies=residencies,
                point_rows=point_rows,
                totals=totals,
            )
        )
    sections.sort(
        key=lambda section: (
            section.source_csv,
            section.hunt_code,
            section.is_youth,
            section.hunt_id,
        )
    )
    return sections


def fit_font(text: str, font: str, max_size: float, min_size: float, width: float) -> float:
    size = max_size
    while size > min_size and stringWidth(ascii_text(text), font, size) > width:
        size -= 0.25
    return size


def draw_centered(
    pdf: canvas.Canvas,
    value: object,
    left: float,
    right: float,
    y: float,
    font: str,
    size: float,
    color: colors.Color = TEXT,
) -> None:
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawCentredString((left + right) / 2, y, ascii_text(value))


def draw_page(
    pdf: canvas.Canvas,
    logo: ImageReader,
    topo: ImageReader,
    header_topo: ImageReader,
    art: tuple[ImageReader, ImageReader] | None,
    title: str,
    section: Section,
    page_rows: list[dict[str, dict[str, str]]],
    include_totals: bool,
    page_number: int,
    total_pages: int,
    part_number: int,
    part_count: int,
) -> None:
    width, height = landscape(letter)
    margin = 27
    header_height = 58
    logo_size = 46
    # Match the existing Hunt Library permit reports: a warm cream page with
    # the retained tan topographic artwork at a subtle 12% opacity. Keep the
    # header and every table cell opaque so titles and official values remain
    # as crisp and readable as the approved white-and-cream version.
    pdf.setFillColor(TOPO_CREAM)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.saveState()
    pdf.setFillAlpha(TOPO_OPACITY)
    pdf.drawImage(
        topo,
        0,
        0,
        width=width,
        height=height,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.restoreState()
    pdf.drawImage(
        header_topo,
        0,
        height - header_height - 4,
        width=width,
        height=header_height + 4,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.drawImage(
        logo,
        margin,
        height - 52,
        width=logo_size,
        height=logo_size,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )
    title_x = margin + logo_size + 12
    pdf.setFillColor(UOGA_CREAM)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, height - 24, ascii_text(title))
    pdf.setFont("Helvetica", 7.4)
    pdf.drawString(
        title_x,
        height - 39,
        "Official Utah DWR / UtahDraws values - UOGA-styled local reproduction",
    )

    if art is not None:
        header_art, _ = art
        art_left = width - 126
        pdf.drawImage(
            header_art,
            art_left,
            height - header_height + 5,
            width=99,
            height=header_height - 10,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        page_number_right = art_left - 10
    else:
        page_number_right = width - margin
    pdf.setFillColor(UOGA_CREAM)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(
        page_number_right,
        height - 22,
        f"Page {page_number} of {total_pages}",
    )
    pdf.rect(0, height - header_height - 4, width, 4, stroke=0, fill=1)

    table_left = margin
    table_right = width - margin
    table_width = table_right - table_left
    heading_y = height - 80
    hunt_line = f"Hunt: {section.hunt_code} {section.hunt_name}"
    hunt_size = fit_font(hunt_line, "Helvetica-Bold", 11, 7, table_width)
    pdf.setFont("Helvetica-Bold", hunt_size)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.drawString(table_left, heading_y, ascii_text(hunt_line))
    scope = "Youth" if section.is_youth else "Adult"
    part = f" - Part {part_number} of {part_count}" if part_count > 1 else ""
    descriptor = f"{section.hunt_category} | {section.species} | {scope}{part}"
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.drawString(table_left, heading_y - 14, ascii_text(descriptor))
    # Keep the season/weapon/date on the left immediately below the draw
    # design. It follows the reading order of the DWR report: hunt identity,
    # draw scope, then season details before the applicant ladders.
    season_size = fit_font(section.seasons, "Helvetica", 7.2, 5.8, table_width)
    pdf.setFont("Helvetica", season_size)
    pdf.drawString(table_left, heading_y - 28, ascii_text(section.seasons))

    table_top = height - 128
    table_bottom = 49
    group_header_height = 19
    column_header_height = 25
    body_count = len(page_rows) + (1 if include_totals else 0)
    body_height = table_top - table_bottom - group_header_height - column_header_height
    row_height = min(17.0, body_height / max(1, body_count))
    if row_height < 11:
        raise RuntimeError(f"Page table does not fit for {section.hunt_code}")

    block_gap = 8 if len(section.residencies) == 2 else 0
    block_width = (table_width - block_gap) / len(section.residencies)
    column_fractions = (0.10, 0.22, 0.16, 0.16, 0.16, 0.20)
    headers = ("Points", "Eligible", "Max / Bonus", "Regular", "Total", "Success Ratio")
    display_rows = list(page_rows)
    if include_totals:
        display_rows.append({"points": {"value": "Totals"}, **section.totals})
    body_top = table_top - group_header_height - column_header_height
    body_bottom = body_top - body_count * row_height

    # Match the approved proof: cream surrounds each white table and a
    # dark-brown keyline gives it crisp definition on the all-white page.
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
            # Every report page declares its audience above the tables. Repeat
            # it here so a youth page cannot be mistaken for the adult draw
            # merely because the side-by-side residency panels are viewed in
            # isolation or quoted outside the PDF.
            f"{'Youth' if section.is_youth else 'Adult'} {residency} Applicants",
            left,
            right,
            table_top - group_header_height + 5.5,
            "Helvetica-Bold",
            9,
            UOGA_CREAM,
        )
        x = left
        for fraction, header in zip(column_fractions, headers):
            next_x = x + block_width * fraction
            pdf.setFillColor(UOGA_CREAM)
            pdf.rect(x, table_top - group_header_height - column_header_height, next_x - x, column_header_height, stroke=0, fill=1)
            words = header.split(" ")
            if len(words) <= 1:
                draw_centered(pdf, header, x, next_x, table_top - 34, "Helvetica-Bold", 7.4)
            else:
                split = len(words) // 2
                draw_centered(pdf, " ".join(words[:split]), x, next_x, table_top - 29, "Helvetica-Bold", 7.0)
                draw_centered(pdf, " ".join(words[split:]), x, next_x, table_top - 38, "Helvetica-Bold", 7.0)
            x = next_x

    # Draw every row fill before the watermark so the art remains beneath all
    # point values and grid lines.
    for row_index, row in enumerate(display_rows):
        row_bottom = body_top - (row_index + 1) * row_height
        is_total = row["points"]["value"] == "Totals"
        fill = UOGA_CREAM if is_total else (UOGA_OFF_WHITE if row_index % 2 else colors.white)
        for block_index in range(len(section.residencies)):
            left = table_left + block_index * (block_width + block_gap)
            pdf.setFillColor(fill)
            pdf.rect(left, row_bottom, block_width, row_height, stroke=0, fill=1)

    if art is not None:
        _, watermark = art
        for block_index in range(len(section.residencies)):
            left = table_left + block_index * (block_width + block_gap)
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

    fields = ("eligible", "max_bonus", "regular", "total", "ratio")
    for row_index, row in enumerate(display_rows):
        row_bottom = body_top - (row_index + 1) * row_height
        is_total = row["points"]["value"] == "Totals"
        font = "Helvetica-Bold" if is_total else "Helvetica"
        size = max(6.5, min(8.0, row_height * 0.46))
        for block_index, residency in enumerate(section.residencies):
            left = table_left + block_index * (block_width + block_gap)
            values = [row["points"]["value"]]
            values.extend(row.get(residency, {}).get(field, "") for field in fields)
            x = left
            for fraction, value in zip(column_fractions, values):
                next_x = x + block_width * fraction
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

    for block_index in range(len(section.residencies)):
        left = table_left + block_index * (block_width + block_gap)
        right = left + block_width
        x_positions = [left]
        x = left
        for fraction in column_fractions:
            x += block_width * fraction
            x_positions.append(x)
        pdf.setStrokeColor(GRID)
        pdf.setLineWidth(0.45)
        for x in x_positions:
            pdf.line(x, body_bottom, x, table_top - group_header_height)
        pdf.rect(left, body_bottom, block_width, table_top - body_bottom, stroke=1, fill=0)
        pdf.line(left, body_top, right, body_top)
        for index in range(body_count + 1):
            y = body_top - index * row_height
            pdf.line(left, y, right, y)

    pdf.setFont("Helvetica", 6.6)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.drawString(
        margin,
        28,
        "Source: Utah DWR official 2026 UtahDraws results, retrieved September 2, 2026.",
    )
    pdf.drawRightString(
        width - margin,
        28,
        "2026-only guard passed; no historical rows imported. UOGA is not the source agency.",
    )

    # Match the four-point dark-brown divider below the header around all four
    # page edges. A two-point inset keeps the full stroke printable.
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


def draw_sportsman_page(
    pdf: canvas.Canvas,
    logo: ImageReader,
    topo: ImageReader,
    header_topo: ImageReader,
    species_art: dict[str, tuple[ImageReader, ImageReader]],
    title: str,
    sections: list[Section],
    page_number: int,
    total_pages: int,
) -> None:
    """Draw three compact Sportsman hunt results, one after another.

    Sportsman has one resident result row per hunt. A dedicated stacked layout
    keeps the source result and its total together, rather than leaving nine
    mostly empty full-size report pages.
    """
    width, height = landscape(letter)
    margin = 27
    header_height = 58
    logo_size = 46
    pdf.setFillColor(TOPO_CREAM)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.saveState()
    pdf.setFillAlpha(TOPO_OPACITY)
    pdf.drawImage(topo, 0, 0, width=width, height=height, preserveAspectRatio=False, mask="auto")
    pdf.restoreState()
    pdf.drawImage(
        header_topo,
        0,
        height - header_height - 4,
        width=width,
        height=header_height + 4,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.drawImage(logo, margin, height - 52, width=logo_size, height=logo_size, preserveAspectRatio=True, anchor="c", mask="auto")
    title_x = margin + logo_size + 12
    pdf.setFillColor(UOGA_CREAM)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, height - 24, ascii_text(title))
    pdf.setFont("Helvetica", 7.4)
    pdf.drawString(title_x, height - 39, "Official Utah DWR / UtahDraws values - UOGA-styled local reproduction")
    pdf.setFillColor(UOGA_CREAM)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(width - margin, height - 22, f"Page {page_number} of {total_pages}")
    pdf.rect(0, height - header_height - 4, width, 4, stroke=0, fill=1)

    content_top = height - 83
    content_bottom = 48
    gap = 9
    card_height = (content_top - content_bottom - gap * (len(sections) - 1)) / len(sections)
    headers = ("Points", "Eligible", "Max / Bonus", "Regular", "Total", "Success Ratio")
    column_fractions = (0.10, 0.22, 0.16, 0.16, 0.16, 0.20)

    for index, section in enumerate(sections):
        card_top = content_top - index * (card_height + gap)
        card_bottom = card_top - card_height
        card_left = margin
        card_right = width - margin
        card_width = card_right - card_left
        hunt_line = f"Hunt: {section.hunt_code} {section.hunt_name}"
        pdf.setFont("Helvetica-Bold", fit_font(hunt_line, "Helvetica-Bold", 9.4, 7, card_width - 72))
        pdf.setFillColor(UOGA_DARK_BROWN)
        pdf.drawString(card_left, card_top - 13, ascii_text(hunt_line))
        descriptor = f"{section.hunt_category} | {section.species} | Adult"
        pdf.setFont("Helvetica", 6.7)
        pdf.drawString(card_left, card_top - 25, ascii_text(descriptor))
        season_size = fit_font(section.seasons, "Helvetica", 6.1, 5.2, card_width - 72)
        pdf.setFont("Helvetica", season_size)
        pdf.drawString(card_left, card_top - 36, ascii_text(section.seasons))

        art_key = species_art_key(section.species)
        art = species_art.get(art_key) if art_key else None
        if art is not None:
            header_art, _ = art
            pdf.drawImage(header_art, card_right - 58, card_top - 40, width=54, height=39, preserveAspectRatio=True, anchor="c", mask="auto")

        table_top = card_top - 46
        table_bottom = card_bottom + 5
        group_header_height = 14
        column_header_height = 19
        display_rows = list(section.point_rows) + [{"points": {"value": "Totals"}, **section.totals}]
        body_count = len(display_rows)
        body_top = table_top - group_header_height - column_header_height
        row_height = (body_top - table_bottom) / body_count
        if row_height < 9:
            raise RuntimeError(f"Sportsman card does not fit for {section.hunt_code}")

        pdf.setFillColor(UOGA_CREAM)
        pdf.setStrokeColor(UOGA_DARK_BROWN)
        pdf.setLineWidth(1.0)
        pdf.roundRect(card_left - 3, table_bottom - 3, card_width + 6, table_top - table_bottom + 6, 3, stroke=1, fill=1)
        pdf.setFillColor(UOGA_DARK_BROWN)
        pdf.rect(card_left, table_top - group_header_height, card_width, group_header_height, stroke=0, fill=1)
        draw_centered(pdf, "Resident Applicants", card_left, card_right, table_top - group_header_height + 4.1, "Helvetica-Bold", 8, UOGA_CREAM)

        x = card_left
        for fraction, header in zip(column_fractions, headers):
            next_x = x + card_width * fraction
            pdf.setFillColor(UOGA_CREAM)
            pdf.rect(x, table_top - group_header_height - column_header_height, next_x - x, column_header_height, stroke=0, fill=1)
            words = header.split(" ")
            if len(words) <= 1:
                draw_centered(pdf, header, x, next_x, table_top - 27, "Helvetica-Bold", 6.3)
            else:
                split = len(words) // 2
                draw_centered(pdf, " ".join(words[:split]), x, next_x, table_top - 23, "Helvetica-Bold", 5.9)
                draw_centered(pdf, " ".join(words[split:]), x, next_x, table_top - 30, "Helvetica-Bold", 5.9)
            x = next_x

        fields = ("eligible", "max_bonus", "regular", "total", "ratio")
        for row_index, row in enumerate(display_rows):
            row_bottom = body_top - (row_index + 1) * row_height
            is_total = row["points"]["value"] == "Totals"
            pdf.setFillColor(UOGA_CREAM if is_total else (UOGA_OFF_WHITE if row_index % 2 else colors.white))
            pdf.rect(card_left, row_bottom, card_width, row_height, stroke=0, fill=1)
            values = [row["points"]["value"]]
            values.extend(row.get("Resident", {}).get(field, "") for field in fields)
            x = card_left
            font = "Helvetica-Bold" if is_total else "Helvetica"
            size = max(5.8, min(7.2, row_height * 0.42))
            for fraction, value in zip(column_fractions, values):
                next_x = x + card_width * fraction
                draw_centered(pdf, value, x, next_x, row_bottom + (row_height - size) / 2 + 1.0, font, size)
                x = next_x

        x_positions = [card_left]
        x = card_left
        for fraction in column_fractions:
            x += card_width * fraction
            x_positions.append(x)
        pdf.setStrokeColor(GRID)
        pdf.setLineWidth(0.4)
        for grid_x in x_positions:
            pdf.line(grid_x, table_bottom, grid_x, table_top - group_header_height)
        pdf.rect(card_left, table_bottom, card_width, table_top - table_bottom, stroke=1, fill=0)
        pdf.line(card_left, body_top, card_right, body_top)
        for row_index in range(body_count + 1):
            y = body_top - row_index * row_height
            pdf.line(card_left, y, card_right, y)

    pdf.setFont("Helvetica", 6.6)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.drawString(margin, 28, "Source: Utah DWR official 2026 UtahDraws results, retrieved September 2, 2026.")
    pdf.drawRightString(width - margin, 28, "2026-only guard passed; no historical rows imported. UOGA is not the source agency.")
    pdf.setStrokeColor(UOGA_DARK_BROWN)
    pdf.setLineWidth(4)
    pdf.rect(2, 2, width - 4, height - 4, stroke=1, fill=0)
    pdf.showPage()


def draw_compact_standard_page(
    pdf: canvas.Canvas,
    logo: ImageReader,
    topo: ImageReader,
    header_topo: ImageReader,
    species_art: dict[str, tuple[ImageReader, ImageReader]],
    title: str,
    sections: list[Section],
    page_number: int,
    total_pages: int,
) -> None:
    """Draw two short normal-draw hunt ladders without wasting a full page."""
    width, height = landscape(letter)
    margin = 27
    header_height = 58
    logo_size = 46
    pdf.setFillColor(TOPO_CREAM)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.saveState()
    pdf.setFillAlpha(TOPO_OPACITY)
    pdf.drawImage(topo, 0, 0, width=width, height=height, preserveAspectRatio=False, mask="auto")
    pdf.restoreState()
    pdf.drawImage(header_topo, 0, height - header_height - 4, width=width, height=header_height + 4, preserveAspectRatio=False, mask="auto")
    pdf.drawImage(logo, margin, height - 52, width=logo_size, height=logo_size, preserveAspectRatio=True, anchor="c", mask="auto")
    title_x = margin + logo_size + 12
    pdf.setFillColor(UOGA_CREAM)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, height - 24, ascii_text(title))
    pdf.setFont("Helvetica", 7.4)
    pdf.drawString(title_x, height - 39, "Official Utah DWR / UtahDraws values - UOGA-styled local reproduction")
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(width - margin, height - 22, f"Page {page_number} of {total_pages}")
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.rect(0, height - header_height - 4, width, 4, stroke=0, fill=1)

    content_top = height - 83
    content_bottom = 48
    gap = 9
    card_height = (content_top - content_bottom - gap * (len(sections) - 1)) / len(sections)
    headers = ("Points", "Eligible", "Max / Bonus", "Regular", "Total", "Success Ratio")
    column_fractions = (0.10, 0.22, 0.16, 0.16, 0.16, 0.20)

    for index, section in enumerate(sections):
        card_top = content_top - index * (card_height + gap)
        card_bottom = card_top - card_height
        card_left = margin
        card_right = width - margin
        card_width = card_right - card_left
        hunt_line = f"Hunt: {section.hunt_code} {section.hunt_name}"
        pdf.setFillColor(UOGA_DARK_BROWN)
        pdf.setFont("Helvetica-Bold", fit_font(hunt_line, "Helvetica-Bold", 9.4, 7, card_width - 72))
        pdf.drawString(card_left, card_top - 13, ascii_text(hunt_line))
        scope = "Youth" if section.is_youth else "Adult"
        descriptor = f"{section.hunt_category} | {section.species} | {scope}"
        pdf.setFont("Helvetica", 6.7)
        pdf.drawString(card_left, card_top - 25, ascii_text(descriptor))
        pdf.setFont("Helvetica", fit_font(section.seasons, "Helvetica", 6.1, 5.2, card_width - 72))
        pdf.drawString(card_left, card_top - 36, ascii_text(section.seasons))
        art_key = species_art_key(section.species)
        art = species_art.get(art_key) if art_key else None
        if art is not None:
            header_art, _ = art
            pdf.drawImage(header_art, card_right - 58, card_top - 40, width=54, height=39, preserveAspectRatio=True, anchor="c", mask="auto")

        table_top = card_top - 46
        table_bottom = card_bottom + 5
        group_header_height = 14
        column_header_height = 19
        display_rows = list(section.point_rows) + [{"points": {"value": "Totals"}, **section.totals}]
        body_count = len(display_rows)
        body_top = table_top - group_header_height - column_header_height
        row_height = (body_top - table_bottom) / body_count
        if row_height < 9:
            raise RuntimeError(f"Compact page does not fit for {section.hunt_code}")
        block_gap = 6 if len(section.residencies) == 2 else 0
        block_width = (card_width - block_gap) / len(section.residencies)

        for block_index in range(len(section.residencies)):
            left = card_left + block_index * (block_width + block_gap)
            pdf.setFillColor(UOGA_CREAM)
            pdf.setStrokeColor(UOGA_DARK_BROWN)
            pdf.setLineWidth(1.0)
            pdf.roundRect(left - 3, table_bottom - 3, block_width + 6, table_top - table_bottom + 6, 3, stroke=1, fill=1)

        for block_index, residency in enumerate(section.residencies):
            left = card_left + block_index * (block_width + block_gap)
            right = left + block_width
            pdf.setFillColor(UOGA_DARK_BROWN)
            pdf.rect(left, table_top - group_header_height, block_width, group_header_height, stroke=0, fill=1)
            draw_centered(pdf, f"{scope} {residency} Applicants", left, right, table_top - group_header_height + 4.1, "Helvetica-Bold", 7.4, UOGA_CREAM)
            x = left
            for fraction, header in zip(column_fractions, headers):
                next_x = x + block_width * fraction
                pdf.setFillColor(UOGA_CREAM)
                pdf.rect(x, table_top - group_header_height - column_header_height, next_x - x, column_header_height, stroke=0, fill=1)
                words = header.split(" ")
                if len(words) <= 1:
                    draw_centered(pdf, header, x, next_x, table_top - 27, "Helvetica-Bold", 6.1)
                else:
                    split = len(words) // 2
                    draw_centered(pdf, " ".join(words[:split]), x, next_x, table_top - 23, "Helvetica-Bold", 5.7)
                    draw_centered(pdf, " ".join(words[split:]), x, next_x, table_top - 30, "Helvetica-Bold", 5.7)
                x = next_x

        fields = ("eligible", "max_bonus", "regular", "total", "ratio")
        for row_index, row in enumerate(display_rows):
            row_bottom = body_top - (row_index + 1) * row_height
            is_total = row["points"]["value"] == "Totals"
            fill = UOGA_CREAM if is_total else (UOGA_OFF_WHITE if row_index % 2 else colors.white)
            for block_index, residency in enumerate(section.residencies):
                left = card_left + block_index * (block_width + block_gap)
                pdf.setFillColor(fill)
                pdf.rect(left, row_bottom, block_width, row_height, stroke=0, fill=1)
                values = [row["points"]["value"]]
                values.extend(row.get(residency, {}).get(field, "") for field in fields)
                x = left
                font = "Helvetica-Bold" if is_total else "Helvetica"
                size = max(5.6, min(6.9, row_height * 0.42))
                for fraction, value in zip(column_fractions, values):
                    next_x = x + block_width * fraction
                    draw_centered(pdf, value, x, next_x, row_bottom + (row_height - size) / 2 + 1.0, font, size)
                    x = next_x

        for block_index in range(len(section.residencies)):
            left = card_left + block_index * (block_width + block_gap)
            right = left + block_width
            x_positions = [left]
            x = left
            for fraction in column_fractions:
                x += block_width * fraction
                x_positions.append(x)
            pdf.setStrokeColor(GRID)
            pdf.setLineWidth(0.4)
            for grid_x in x_positions:
                pdf.line(grid_x, table_bottom, grid_x, table_top - group_header_height)
            pdf.rect(left, table_bottom, block_width, table_top - table_bottom, stroke=1, fill=0)
            pdf.line(left, body_top, right, body_top)
            for row_index in range(body_count + 1):
                y = body_top - row_index * row_height
                pdf.line(left, y, right, y)

    pdf.setFont("Helvetica", 6.6)
    pdf.setFillColor(UOGA_DARK_BROWN)
    pdf.drawString(margin, 28, "Source: Utah DWR official 2026 UtahDraws results, retrieved September 2, 2026.")
    pdf.drawRightString(width - margin, 28, "2026-only guard passed; no historical rows imported. UOGA is not the source agency.")
    pdf.setStrokeColor(UOGA_DARK_BROWN)
    pdf.setLineWidth(4)
    pdf.rect(2, 2, width - 4, height - 4, stroke=1, fill=0)
    pdf.showPage()


def page_plan(sections: list[Section]) -> list[tuple[Section, list[dict[str, dict[str, str]]], bool, int, int]]:
    plan = []
    for section in sections:
        chunks = [
            section.point_rows[index : index + MAX_POINT_ROWS_PER_PAGE]
            for index in range(0, len(section.point_rows), MAX_POINT_ROWS_PER_PAGE)
        ] or [[]]
        for index, chunk in enumerate(chunks, start=1):
            plan.append((section, chunk, index == len(chunks), index, len(chunks)))
    return plan


def standard_render_plan(
    sections: list[Section],
) -> list[tuple[str, object]]:
    """Pair adjacent short ladders; preserve full pages for longer ladders."""
    section_pages = page_plan(sections)
    plan: list[tuple[str, object]] = []
    index = 0
    while index < len(section_pages):
        current = section_pages[index]
        current_short = current[4] == 1 and len(current[1]) <= COMPACT_STANDARD_MAX_POINT_ROWS
        if current_short and index + 1 < len(section_pages):
            following = section_pages[index + 1]
            following_short = following[4] == 1 and len(following[1]) <= COMPACT_STANDARD_MAX_POINT_ROWS
            if following_short:
                plan.append(("compact", [current[0], following[0]]))
                index += COMPACT_STANDARD_SECTIONS_PER_PAGE
                continue
        plan.append(("standard", current))
        index += 1
    return plan


def build_pdf(
    path: Path,
    title: str,
    rows: list[dict[str, str]],
    logo: ImageReader,
    topo: ImageReader,
    header_topo: ImageReader,
    species_art: dict[str, tuple[ImageReader, ImageReader]],
    compact_sportsman: bool = False,
) -> dict[str, object]:
    sections = build_sections(rows)
    if compact_sportsman:
        pages = [
            sections[index : index + SPORTSMAN_SECTIONS_PER_PAGE]
            for index in range(0, len(sections), SPORTSMAN_SECTIONS_PER_PAGE)
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(path), pagesize=landscape(letter), pageCompression=1)
        pdf.setTitle(ascii_text(title))
        pdf.setAuthor("UOGA / HUNT-BUILDER")
        pdf.setSubject("Official 2026 Utah DWR UtahDraws values in a UOGA-styled local PDF reproduction")
        for page_number, page_sections in enumerate(pages, start=1):
            draw_sportsman_page(pdf, logo, topo, header_topo, species_art, title, page_sections, page_number, len(pages))
        pdf.save()
        return {
            "source_rows": len(rows),
            "hunt_sections": len(sections),
            "pages": len(pages),
            "layout": f"compact_stacked_{SPORTSMAN_SECTIONS_PER_PAGE}_hunts_per_page",
        }
    render_pages = standard_render_plan(sections)
    art_page_counts: Counter[str] = Counter()
    missing_art_page_counts: Counter[str] = Counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=landscape(letter), pageCompression=1)
    pdf.setTitle(ascii_text(title))
    pdf.setAuthor("UOGA / HUNT-BUILDER")
    pdf.setSubject("Official 2026 Utah DWR UtahDraws values in a UOGA-styled local PDF reproduction")
    for page_number, (kind, payload) in enumerate(render_pages, start=1):
        page_sections = payload if kind == "compact" else [payload[0]]
        for section in page_sections:
            art_key = species_art_key(section.species)
            if art_key in species_art:
                art_page_counts[art_key] += 1
            else:
                missing_art_page_counts[art_key or "unmapped"] += 1
        if kind == "compact":
            draw_compact_standard_page(
                pdf, logo, topo, header_topo, species_art, title, payload,
                page_number, len(render_pages),
            )
            continue
        section, page_rows, totals, part, part_count = payload
        art_key = species_art_key(section.species)
        draw_page(
            pdf, logo, topo, header_topo, species_art.get(art_key) if art_key else None,
            title, section, page_rows, totals, page_number, len(render_pages), part, part_count,
        )
    pdf.save()
    return {
        "source_rows": len(rows),
        "hunt_sections": len(sections),
        "pages": len(render_pages),
        "species_art_page_counts": dict(sorted(art_page_counts.items())),
        "missing_species_art_page_counts": dict(
            sorted(missing_art_page_counts.items())
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--family", choices=sorted(FAMILY_CONFIG))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--logo", type=Path, default=DEFAULT_LOGO)
    parser.add_argument("--topo", type=Path, default=DEFAULT_TOPO)
    parser.add_argument("--dark-header-topo", type=Path, default=DEFAULT_DARK_HEADER_TOPO)
    parser.add_argument("--bighorn-icon", type=Path, default=DEFAULT_BIGHORN_ICON)
    parser.add_argument("--bear-icon", type=Path, default=DEFAULT_BEAR_ICON)
    parser.add_argument("--moose-icon", type=Path, default=DEFAULT_MOOSE_ICON)
    args = parser.parse_args()

    by_family, validation = validate_sources()
    payload: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Utah DWR official 2026 UtahDraws online results",
        "branding": "UOGA-styled local reproduction",
        "uoga_palette": {
            "black": "#000000",
            "brown": "#59270B",
            "dark_brown": "#3E1C00",
            "cream": "#F4EBD7",
            "forest": "#003314",
            "off_white": "#FBFAF7",
            "tan": "#9A8669",
        },
        "validation": validation,
        "outputs": {},
    }
    if args.validate_only:
        print(json.dumps(payload, indent=2))
        return

    if not args.logo.is_file():
        raise FileNotFoundError(f"UOGA logo not found: {args.logo}")
    if not args.topo.is_file():
        raise FileNotFoundError(f"Tan topographic background not found: {args.topo}")
    if not args.dark_header_topo.is_file():
        raise FileNotFoundError(
            f"Dark header topographic background not found: {args.dark_header_topo}"
        )
    with Image.open(args.logo) as image:
        if "A" not in image.getbands():
            raise RuntimeError("UOGA logo must retain its transparent background")
    logo = ImageReader(str(args.logo))
    topo = ImageReader(str(args.topo))
    header_topo = ImageReader(str(args.dark_header_topo))
    art_paths = dict(BUILTIN_SPECIES_ICON_PATHS)
    art_paths["bighorn"] = args.bighorn_icon
    if args.bear_icon is not None:
        art_paths["bear"] = args.bear_icon
    if args.moose_icon is not None:
        art_paths["moose"] = args.moose_icon
    species_art, species_art_manifest = load_species_art(art_paths)
    payload["species_art"] = {
        "available": species_art_manifest,
        "not_supplied": [
            key for key in ("bear", "moose") if key not in species_art
        ],
        "treatment": (
            "Full-strength transparent art in the white header and an 8.5% "
            "warm-brown watermark behind each applicant point table."
        ),
    }
    payload["header_background"] = {
        "source_path": str(args.dark_header_topo),
        "sha256": sha256(args.dark_header_topo),
        "treatment": (
            "Dark-brown topographic banner behind the UOGA mark, report title, "
            "source subtitle, and page number, with cream header text."
        ),
    }
    payload["terrain_background"] = {
        "source_path": str(args.topo),
        "sha256": sha256(args.topo),
        "base_color": "#F6EBD7",
        "opacity": TOPO_OPACITY,
        "treatment": (
            "The same light-brown topographic background used by the existing "
            "UOGA Hunt Library permit reports, with an opaque white header and "
            "opaque white-and-cream applicant tables for readability."
        ),
    }
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, object] = {}
    selected_families = [args.family] if args.family else list(FAMILY_CONFIG)
    for family in selected_families:
        config = FAMILY_CONFIG[family]
        path = output_dir / str(config["filename"])
        if path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing output; use a new directory: {path}"
            )
        stats = build_pdf(
            path,
            str(config["title"]),
            by_family[family],
            logo,
            topo,
            header_topo,
            species_art,
            compact_sportsman=family == "sportsman",
        )
        outputs[family] = {
            "path": path.relative_to(ROOT).as_posix(),
            **stats,
            "sha256": sha256(path),
        }
    payload["logo"] = {
        "source_path": str(args.logo),
        "sha256": sha256(args.logo),
    }
    payload["outputs"] = outputs
    manifest = output_dir / MANIFEST_NAME
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
