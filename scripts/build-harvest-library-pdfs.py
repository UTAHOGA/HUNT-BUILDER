from __future__ import annotations

import csv
import hashlib
import io
import re
import shutil
import statistics
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = (
    ROOT
    / "data_model"
    / "harvest_quality"
    / "source_package_bundles"
    / "HUNTS_harvest_truth_and_overlay_packages_for_codex"
)
HARVEST_2024_ZIP = BUNDLE_DIR / "harvest_results_2024_for_2025_database.zip"
HARVEST_2025_ZIP = BUNDLE_DIR / "harvest_results_2025_for_2026_database.zip"
ELK_AGE_ZIP = BUNDLE_DIR / "harvest_results_2024_for_2025_elk_age_supplement.zip"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
UOGA_LOGO = ROOT / "assets" / "logos" / "UOGA-LOGO-CIRCLE.png"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"

OUTPUT_DIR = ROOT / "output" / "pdf" / "harvest-results"
PUBLIC_DIR = ROOT / "public" / "hard-copy" / "harvest-data"
OUTPUT_2024 = OUTPUT_DIR / "Utah_2024_Harvest_Results_UOGA.pdf"
OUTPUT_2025 = OUTPUT_DIR / "Utah_2025_Harvest_Results_UOGA.pdf"
PUBLIC_2024 = PUBLIC_DIR / "2024" / OUTPUT_2024.name
PUBLIC_2025 = PUBLIC_DIR / "2025" / OUTPUT_2025.name

DWR_REPORTS_URL = "https://wildlife.utah.gov/hunting/reports"
DWR_HARVEST_DASHBOARD_URL = "https://wildlife.utah.gov/biggame/reports"
DWR_2024_BIG_GAME_URL = "https://wildlife.utah.gov/pdf/annual-reports/big-game/24_bg_report.pdf"
DWR_DASHBOARD_ACCESSED = "2026-08-28"

PAGE_SIZE = landscape(letter)
PAGE_W, PAGE_H = PAGE_SIZE
CREAM = colors.HexColor("#F6EBD7")
DARK = colors.HexColor("#2B1708")
ORANGE = colors.HexColor("#F07800")
TAN = colors.HexColor("#E8CDA0")
PALE = colors.HexColor("#FFF9ED")
ALT = colors.HexColor("#F1E2C8")
GRID = colors.HexColor("#8D714B")
TEXT = colors.HexColor("#24180F")
MUTED = colors.HexColor("#5C4A39")
GREEN = colors.HexColor("#2F6B3C")
RED = colors.HexColor("#9D2B21")

SPECIES_ORDER = {
    "Elk": 1,
    "Mule Deer": 2,
    "Deer": 2,
    "Antlerless Elk": 3,
    "Antlerless Deer": 4,
    "Pronghorn": 5,
    "Black Bear": 6,
    "Moose": 7,
    "Bison": 8,
    "Desert Bighorn Sheep": 9,
    "Rocky Mountain Bighorn Sheep": 10,
    "Mountain Goat": 11,
}


# Hunt rows published after the 2026-03-06 preliminary package. These were
# transcribed from the official DWR harvest dashboards on 2026-08-28. Tuple
# fields: species, hunt code, hunt name, hunt type, weapon, sex, permits,
# hunters afield, harvest.
DWR_2025_ADDITIONS = [
    ("Deer", "LO1629", "Boulder/Kaiparowits", "General Season Landowner", "Rifle Restricted", "Male Only", "1", "", ""),
    ("Deer", "MIT001", "", "Mitigation", "Hunters/Fee", "Female Only", "512", "474", "345"),
    ("Deer", "MIT011", "", "Mitigation", "Landowners/Free", "Female Only", "2800", "1858", "957"),
    ("Elk", "EA1258", "La Sal", "Antlerless", "Any Legal Weapon", "Female Only", "1", "", ""),
    ("Elk", "EL3015", "Panguitch Lake", "Limited Entry Landowner", "Archery", "Male Only", "2", "", ""),
    ("Elk", "EL3032", "Cache, Meadowville", "Limited Entry Landowner", "Early Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "EL3042", "Fillmore, Pahvant", "Limited Entry Landowner", "Early Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "EL3067", "San Juan Bull Elk", "Limited Entry Landowner", "Late Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "EL3073", "Wasatch Mtns", "Limited Entry Landowner", "Late Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "EL3098", "Diamond Mtn", "Limited Entry Landowner", "Muzzleloader", "Male Only", "", "", ""),
    ("Elk", "EL3162", "Book Cliffs, Bitter Creek/East", "Limited Entry Landowner", "Early Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "EL3163", "Book Cliffs, Bitter Creek/East", "Limited Entry Landowner", "Late Any Legal Weapon", "Male Only", "1", "", ""),
    ("Elk", "LO0011", "Diamond Mtn Landowner Association", "Limited Entry Landowner", "Archery", "Male Only", "1", "", ""),
    ("Elk", "LO0012", "Diamond Mtn Landowner Association", "Limited Entry Landowner", "Early Any Legal Weapon", "Male Only", "12", "12", "12"),
    ("Elk", "LO0013", "Diamond Mtn Landowner Association", "Limited Entry Landowner", "Mid Any Legal Weapon", "Male Only", "9", "9", "9"),
    ("Elk", "LO0014", "Diamond Mtn Landowner Association", "Limited Entry Landowner", "Muzzleloader", "Male Only", "5", "5", "5"),
    ("Elk", "LO0015", "Diamond Mtn Landowner Association", "Limited Entry Landowner", "Late Any Legal Weapon", "Male Only", "2", "2", "0"),
    ("Elk", "MIT001", "", "Mitigation", "Hunters/Fee", "Female Only", "1695", "1572", "639"),
    ("Elk", "MIT011", "", "Mitigation", "Landowners/Free", "Female Only", "1773", "1316", "509"),
    ("Pronghorn", "MIT001", "", "Mitigation", "Hunters/Fee", "Female Only", "374", "343", "191"),
    ("Pronghorn", "MIT011", "", "Mitigation", "Landowners/Free", "Female Only", "510", "330", "143"),
]

EXPECTED_2025_SPECIES_COUNTS = {
    "Bison": 18,
    "Deer": 421,
    "Desert Bighorn Sheep": 25,
    "Elk": 471,
    "Moose": 43,
    "Mountain Goat": 18,
    "Pronghorn": 124,
    "Rocky Mountain Bighorn Sheep": 21,
}


# Direct transcription of the Utah DWR 2024 Big Game Annual Report tables on
# PDF pages 37-38 (printed pages 34-35). Values are postseason bucks per 100 does.
DEER_RATIO_ROWS = [
    ("General - public", "22", "Beaver", "18-20", "17", "20", "21", "19"),
    ("General - public", "25C/26", "Boulder/Kaiparowits", "18-20", "24", "31", "25", "27"),
    ("General - public", "1", "Box Elder", "15-17", "26", "22", "20", "23"),
    ("General - public", "2", "Cache", "15-17", "20", "19", "19", "19"),
    ("General - public", "21", "Fillmore", "18-20", "18", "24", "22", "21"),
    ("General - public", "25A", "Fishlake", "18-20", "21", "24", "22", "23"),
    ("General - public", "7", "Kamas", "18-20", "24", "23", "15", "21"),
    ("General - public", "13A", "La Sal, La Sal Mtns", "15-17", "26", "17", "30", "24"),
    ("General - public", "16B/12", "Manti/San Rafael", "15-17", "22", "19", "19", "20"),
    ("General - public", "23", "Monroe", "18-20", "18", "21", "24", "21"),
    ("General - public", "24", "Mt Dutton", "18-20", "21", "22", "20", "21"),
    ("General - public", "16A", "Nebo", "15-17", "21", "17", "19", "19"),
    ("General - public", "11", "Nine Mile", "18-20", "16", "22", "21", "20"),
    ("General - public", "8", "North Slope, Three Corners/West Daggett", "18-20", "20", "20", "21", "20"),
    ("General - public", "18", "Oquirrh-Stansbury", "15-17", "24", "26", "26", "25"),
    ("General - public", "28", "Panguitch Lake", "18-20", "18", "23", "21", "21"),
    ("General - public", "30", "Pine Valley", "18-20", "19", "23", "23", "22"),
    ("General - public", "14A", "San Juan, Abajo Mtns", "18-20", "20", "17", "23", "20"),
    ("General - public", "20", "Southwest Desert", "18-20", "21", "22", "25", "22"),
    ("General - public", "25B", "Thousand Lakes", "18-20", "25", "19", "22", "22"),
    ("General - public", "9BD", "Vernal/Bonanza", "15-17", "20", "16", "16", "17"),
    ("General - public", "17BC", "Wasatch Mtns, East", "18-20", "26", "25", "21", "24"),
    ("General - public", "17A", "Wasatch Mtns, West", "15-17", "16", "15", "16", "16"),
    ("General - public", "19C", "West Desert, Tintic", "15-17", "*", "*", "*", "*"),
    ("General - public", "19A", "West Desert, West", "15-17", "*", "*", "*", "*"),
    ("General - public", "9A", "Yellowstone", "18-20", "21", "19", "19", "19"),
    ("General - public", "29", "Zion", "18-20", "21", "24", "22", "22"),
    ("General - private", "6", "Chalk Creek", "18-20", "28", "24", "32", "28"),
    ("General - private", "5", "East Canyon", "18-20", "24", "22", "31", "26"),
    ("General - private", "4", "Morgan-South Rich", "18-20", "29", "21", "28", "26"),
    ("General - private", "3", "Ogden", "18-20", "23", "20", "21", "21"),
    ("Limited entry", "10", "Book Cliffs", "25-35", "33", "37", "41", "37"),
    ("Limited entry", "2B", "Cache, Crawford Mtn", "25-35", "22", "22", "22", "22"),
    ("Limited entry", "9C", "Diamond Mtn", "25-35", "31", "33", "27", "30"),
    ("Limited entry", "21C", "Fillmore, Oak Creek LE", "25-35", "43", "32", "39", "38"),
    ("Limited entry", "13B", "La Sal, Dolores Triangle", "25-35", "29", "27", "28", "28"),
    ("Limited entry", "14B", "San Juan, Elk Ridge", "25-35", "34", "34", "41", "36"),
    ("Limited entry", "19B", "West Desert, Vernon", "25-35", "31", "35", "33", "33"),
    ("Premium limited entry", "15", "Henry Mtns", "40-55", "36", "55", "48", "46"),
    ("Premium limited entry", "26", "Paunsaugunt", "40-55", "42", "46", "50", "46"),
]


def clean(value: object) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2011": "-",
        "\ufffd": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


def paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def read_zip_csv(zip_path: Path, member: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as raw:
            return list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig")))


def read_database() -> list[dict[str, str]]:
    with DATABASE.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text == "*":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def display_number(value: object, decimals: int = 0) -> str:
    parsed = number(value)
    if parsed is None:
        return "-"
    if decimals:
        return f"{parsed:,.{decimals}f}"
    return f"{parsed:,.0f}"


def dashboard_2025_row(values: tuple[str, ...]) -> dict[str, str]:
    species, hunt_code, hunt_name, hunt_type, weapon, sex_type, permits, hunters, harvest = values
    hunters_value = number(hunters)
    harvest_value = number(harvest)
    success = ""
    if hunters_value:
        success = f"{(harvest_value or 0) / hunters_value * 100:.1f}"
    return {
        "reported_hunt_year": "2025",
        "model_target_year": "2026",
        "source_status": "official_dashboard_current",
        "source_file": "Utah DWR Big Game Harvest & Survey dashboard",
        "source_date": DWR_DASHBOARD_ACCESSED,
        "source_family": "official_big_game_harvest_dashboard",
        "source_row": "dashboard_hunt_code",
        "row_type": "hunt_code_harvest_result",
        "hunt_code": hunt_code,
        "species": species,
        "sex_type": sex_type,
        "hunt_name": hunt_name,
        "hunt_type": hunt_type,
        "weapon": weapon,
        "permits": permits,
        "hunters_afield": hunters,
        "harvest": harvest,
        "percent_success": success,
        "average_days_hunted": "",
        "hunter_satisfaction": "",
        "do_not_use_for_permit_quota": "True",
        "do_not_use_directly_for_p_draw": "True",
        "trend_feature_eligible": "True",
        "data_quality_flags": "OFFICIAL_DWR_DASHBOARD|HUNT_CODE_KEYED|BIG_GAME_HARVEST",
        "recommended_use": "harvest quality, demand-signal, and backcheck features only; do not use as permit quota or direct draw probability",
    }


def reconcile_2025_dashboard(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    reconciled = [dict(row) for row in rows]
    pb1000 = [row for row in reconciled if clean(row.get("hunt_code")) == "PB1000"]
    if len(pb1000) != 1:
        raise RuntimeError(f"Expected one PB1000 row for species correction, found {len(pb1000)}")
    pb1000[0]["species"] = "Pronghorn"
    pb1000[0]["data_quality_flags"] = clean(pb1000[0].get("data_quality_flags")) + "|DASHBOARD_SPECIES_CORRECTED"

    existing = {(clean(row.get("species")), clean(row.get("hunt_code"))) for row in reconciled}
    for values in DWR_2025_ADDITIONS:
        row = dashboard_2025_row(values)
        key = (row["species"], row["hunt_code"])
        if key in existing:
            raise RuntimeError(f"Dashboard addition duplicates packaged row: {key}")
        reconciled.append(row)
        existing.add(key)

    actual_counts = {species: len(species_rows) for species, species_rows in group_by_species(reconciled).items()}
    if actual_counts != EXPECTED_2025_SPECIES_COUNTS:
        raise RuntimeError(f"2025 DWR dashboard species counts differ: {actual_counts}")
    return reconciled


def objective_status(value: object, objective: object) -> str:
    parsed = number(value)
    matches = re.findall(r"\d+(?:\.\d+)?", clean(objective))
    if parsed is None or len(matches) < 2:
        return "Insufficient data"
    low, high = float(matches[0]), float(matches[1])
    if parsed < low:
        return "Below"
    if parsed > high:
        return "Above"
    return "Within"


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def planner_crosscheck(age_rows: list[dict[str, str]], database_rows: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in database_rows
        if clean(row.get("species")) == "Elk"
        and clean(row.get("current_age_3yr_average"))
        and clean(row.get("dwr_huntplanner_age_objective"))
    ]
    result: dict[str, str] = {}
    for age in age_rows:
        age_name = normalize_name(age.get("unit_name"))
        age_avg = clean(age.get("avg_age_3yr_average"))
        age_obj = clean(age.get("objective"))
        matches = []
        for row in candidates:
            if number(row.get("current_age_3yr_average")) != number(age_avg):
                continue
            if clean(row.get("dwr_huntplanner_age_objective")) != age_obj:
                continue
            planner_name = normalize_name(row.get("hunt_name"))
            name_match = age_name == planner_name or age_name in planner_name or planner_name in age_name
            if name_match:
                matches.append(row)
        result[clean(age.get("unit")) + "|" + clean(age.get("unit_name"))] = "Verified" if matches else "No exact match"
    return result


def source_rows_for_year(rows: list[dict[str, str]], year: int) -> list[dict[str, str]]:
    if year == 2024:
        return sorted(
            rows,
            key=lambda row: (
                SPECIES_ORDER.get(clean(row.get("species")), 99),
                clean(row.get("species")),
                clean(row.get("hunt_code")),
            ),
        )
    return sorted(
        rows,
        key=lambda row: (
            SPECIES_ORDER.get(clean(row.get("species")), 99),
            clean(row.get("species")),
            clean(row.get("hunt_code")),
        ),
    )


def group_by_species(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("species"))].append(row)
    return dict(
        sorted(
            grouped.items(),
            key=lambda item: (SPECIES_ORDER.get(item[0], 99), item[0]),
        )
    )


def build_styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            textColor=DARK,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=ORANGE,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15,
            textColor=DARK,
            spaceBefore=5,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.7,
            textColor=TEXT,
            spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "note",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=MUTED,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="Helvetica",
            fontSize=5.7,
            leading=6.7,
            textColor=TEXT,
        ),
        "small_bold": ParagraphStyle(
            "small_bold",
            fontName="Helvetica-Bold",
            fontSize=5.8,
            leading=6.8,
            textColor=TEXT,
        ),
        "center_small": ParagraphStyle(
            "center_small",
            fontName="Helvetica",
            fontSize=5.7,
            leading=6.7,
            textColor=TEXT,
            alignment=TA_CENTER,
        ),
    }


def page_background(canvas, doc, report_title: str, preliminary: bool) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        canvas.saveState()
        canvas.setFillAlpha(0.06)
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
    canvas.setFont("Helvetica", 7.2)
    canvas.drawString(78, PAGE_H - 44, "Utah DWR source data | U.O.G.A. Hunt Builder visitor reference")
    if preliminary:
        canvas.setFillColor(ORANGE)
        canvas.roundRect(PAGE_W - 151, PAGE_H - 46, 86, 22, 7, fill=1, stroke=0)
        canvas.setFillColor(DARK)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawCentredString(PAGE_W - 108, PAGE_H - 38, "PRELIMINARY")

    canvas.setStrokeColor(ORANGE)
    canvas.setLineWidth(1)
    canvas.line(28, 28, PAGE_W - 28, 28)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(31, 17, "Harvest history and management context only - not permit quota or draw probability.")
    canvas.drawRightString(PAGE_W - 31, 17, f"Page {doc.page}")
    canvas.restoreState()


def standard_table(data: list[list[object]], widths: list[float], font_size: float = 6.1) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), font_size),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), font_size - 0.25),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, ALT]),
                ("GRID", (0, 0), (-1, -1), 0.28, GRID),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.4),
                ("TOPPADDING", (0, 0), (-1, -1), 2.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
            ]
        )
    )
    return table


def summary_table(rows: list[dict[str, str]], year: int, styles: dict[str, ParagraphStyle]) -> Table:
    grouped = group_by_species(rows)
    data: list[list[object]] = [["Species", "Hunt rows", "Hunters afield", "Harvest", "Median success"]]
    for species, species_rows in grouped.items():
        hunter_values = [number(row.get("hunters_afield")) for row in species_rows]
        harvest_key = "harvest_total" if year == 2024 else "harvest"
        harvest_values = [number(row.get(harvest_key)) for row in species_rows]
        success_values = [number(row.get("percent_success")) for row in species_rows]
        data.append(
            [
                paragraph(species, styles["small_bold"]),
                f"{len(species_rows):,}",
                f"{sum(value for value in hunter_values if value is not None):,.0f}",
                f"{sum(value for value in harvest_values if value is not None):,.0f}",
                f"{statistics.median(value for value in success_values if value is not None):.1f}%",
            ]
        )
    return standard_table(data, [2.05 * inch, 0.8 * inch, 1.05 * inch, 0.9 * inch, 1.05 * inch], 7)


def elk_age_table(
    age_rows: list[dict[str, str]],
    planner_matches: dict[str, str],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data: list[list[object]] = [
        ["Unit", "Management unit", "2024 avg age", "3-year avg", "Age objective", "2024 status", "3-year status", "Hunt Planner"]
    ]
    for row in age_rows:
        key = clean(row.get("unit")) + "|" + clean(row.get("unit_name"))
        data.append(
            [
                clean(row.get("unit")),
                paragraph(row.get("unit_name"), styles["small"]),
                display_number(row.get("avg_age_2024"), 1),
                display_number(row.get("avg_age_3yr_average"), 1),
                clean(row.get("objective")),
                objective_status(row.get("avg_age_2024"), row.get("objective")),
                objective_status(row.get("avg_age_3yr_average"), row.get("objective")),
                planner_matches.get(key, "No exact match"),
            ]
        )
    table = standard_table(
        data,
        [0.58 * inch, 2.15 * inch, 0.72 * inch, 0.68 * inch, 0.72 * inch, 0.74 * inch, 0.76 * inch, 0.82 * inch],
        6.1,
    )
    table.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 1.6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
            ]
        )
    )
    for row_index, row in enumerate(data[1:], start=1):
        for col_index in (5, 6):
            status = clean(row[col_index])
            color = GREEN if status in {"Within", "Above"} else RED if status == "Below" else MUTED
            table.setStyle(TableStyle([("TEXTCOLOR", (col_index, row_index), (col_index, row_index), color), ("FONTNAME", (col_index, row_index), (col_index, row_index), "Helvetica-Bold")]))
    return table


def deer_ratio_table(styles: dict[str, ParagraphStyle]) -> Table:
    data: list[list[object]] = [["Class", "Unit", "Management unit", "Objective", "2022", "2023", "2024", "3-year avg", "Status"]]
    for category, unit, name, objective, y2022, y2023, y2024, average in DEER_RATIO_ROWS:
        data.append(
            [
                paragraph(category, styles["small"]),
                unit,
                paragraph(name, styles["small"]),
                objective,
                y2022,
                y2023,
                y2024,
                average,
                objective_status(average, objective),
            ]
        )
    table = standard_table(
        data,
        [1.05 * inch, 0.54 * inch, 2.25 * inch, 0.66 * inch, 0.45 * inch, 0.45 * inch, 0.45 * inch, 0.62 * inch, 0.82 * inch],
        5.9,
    )
    for row_index, row in enumerate(data[1:], start=1):
        status = clean(row[8])
        color = GREEN if status in {"Within", "Above"} else RED if status == "Below" else MUTED
        table.setStyle(TableStyle([("TEXTCOLOR", (8, row_index), (8, row_index), color), ("FONTNAME", (8, row_index), (8, row_index), "Helvetica-Bold")]))
    return table


def hunt_results_table(rows: list[dict[str, str]], year: int, styles: dict[str, ParagraphStyle]) -> Table:
    data: list[list[object]] = []
    if year == 2024:
        data.append(["Code", "Hunt name", "Unit", "Permits", "Hunters", "Harvest", "Success", "Days", "Source"])
        for row in rows:
            source = f"{clean(row.get('source_file'))} p.{clean(row.get('source_page'))}"
            data.append(
                [
                    clean(row.get("hunt_code")),
                    paragraph(row.get("hunt_name"), styles["small"]),
                    clean(row.get("unit_context")),
                    display_number(row.get("permits")),
                    display_number(row.get("hunters_afield")),
                    display_number(row.get("harvest_total")),
                    f"{display_number(row.get('percent_success'), 1)}%" if number(row.get("percent_success")) is not None else "-",
                    display_number(row.get("average_days"), 1),
                    paragraph(source, styles["small"]),
                ]
            )
        widths = [0.58 * inch, 2.2 * inch, 0.48 * inch, 0.54 * inch, 0.58 * inch, 0.55 * inch, 0.55 * inch, 0.48 * inch, 1.75 * inch]
    else:
        data.append(["Code", "Hunt name", "Type / weapon", "Permits", "Hunters", "Harvest", "Success", "Days", "Satisfaction"])
        for row in rows:
            type_weapon = " | ".join(filter(None, [clean(row.get("hunt_type")), clean(row.get("weapon"))]))
            data.append(
                [
                    clean(row.get("hunt_code")),
                    paragraph(row.get("hunt_name"), styles["small"]),
                    paragraph(type_weapon, styles["small"]),
                    display_number(row.get("permits")),
                    display_number(row.get("hunters_afield")),
                    display_number(row.get("harvest")),
                    f"{display_number(row.get('percent_success'), 1)}%" if number(row.get("percent_success")) is not None else "-",
                    display_number(row.get("average_days_hunted"), 1),
                    display_number(row.get("hunter_satisfaction"), 1),
                ]
            )
        widths = [0.58 * inch, 2.15 * inch, 2.2 * inch, 0.54 * inch, 0.58 * inch, 0.55 * inch, 0.55 * inch, 0.48 * inch, 0.68 * inch]
    return standard_table(data, widths, 5.8)


def source_block(year: int, styles: dict[str, ParagraphStyle]) -> list[object]:
    annual_hash = sha256(HARVEST_2024_ZIP)
    database_hash = sha256(DATABASE)
    source_lines = [
        f"Utah DWR annual reports: {DWR_REPORTS_URL}",
        f"2024 Utah Big Game Annual Report: {DWR_2024_BIG_GAME_URL}",
        f"2024 verified harvest package SHA-256: {annual_hash}",
        f"2026 Hunt Planner database snapshot SHA-256: {database_hash}",
    ]
    if year == 2025:
        source_lines.insert(2, f"2025 current DWR harvest dashboards (accessed {DWR_DASHBOARD_ACCESSED}): {DWR_HARVEST_DASHBOARD_URL}")
        source_lines.insert(3, "2025 baseline source: 2026-03-06-2025-preliminary-bg-harvest.xlsx (verified packaged extract)")
        source_lines.insert(4, f"2025 baseline package SHA-256: {sha256(HARVEST_2025_ZIP)}")
        source_lines.insert(5, "Dashboard reconciliation: 21 newly published hunt rows plus PB1000 corrected from Moose to Pronghorn; 1,141 current rows total.")
    return [paragraph(line, styles["note"]) for line in source_lines]


def build_report(
    year: int,
    rows: list[dict[str, str]],
    age_rows: list[dict[str, str]],
    planner_matches: dict[str, str],
    output_path: Path,
) -> None:
    preliminary = False
    report_title = f"Utah {year} Harvest Results"
    styles = build_styles()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=PAGE_SIZE,
        leftMargin=0.46 * inch,
        rightMargin=0.46 * inch,
        topMargin=0.98 * inch,
        bottomMargin=0.48 * inch,
        title=report_title,
        author="Utah Outfitter and Guide Association (U.O.G.A.)",
        subject="Utah DWR harvest results and management context",
    )

    grouped = group_by_species(rows)
    total_harvest_key = "harvest_total" if year == 2024 else "harvest"
    total_harvest = sum(number(row.get(total_harvest_key)) or 0 for row in rows)
    total_hunters = sum(number(row.get("hunters_afield")) or 0 for row in rows)
    status_text = (
        "CURRENT UTAH DWR DASHBOARDS - accessed August 28, 2026"
        if year == 2025
        else "FINAL VERIFIED 2024 PACKAGE"
    )
    context_note = (
        "The 2025 hunt rows are reconciled to DWR's current harvest dashboards. DWR has not published a full 2025 annual age and herd-composition report, so the elk age and deer buck-to-doe tables remain the latest verified 2024 management context and are not labeled as 2025 observations."
        if year == 2025
        else "Elk quality is shown with observed 2024 average harvested age, the 2022-2024 three-year average, and the management age objective. Deer quality is shown with postseason bucks per 100 does rather than deer age."
    )

    story: list[object] = [
        Spacer(1, 0.22 * inch),
        paragraph(report_title, styles["title"]),
        paragraph(status_text, styles["subtitle"]),
        paragraph(
            f"This visitor report presents {len(rows):,} hunt-code harvest rows across {len(grouped):,} species groups. The hunt-code rows sum to {total_hunters:,.0f} hunters afield and {total_harvest:,.0f} harvested animals; annual-report statewide totals may differ because DWR projects hunt, unit, and statewide estimates separately.",
            styles["body"],
        ),
        paragraph(context_note, styles["body"]),
        paragraph(
            "These are historical harvest and management-quality references. They must not be used as current permit quotas or direct draw probabilities.",
            styles["note"],
        ),
        Spacer(1, 0.08 * inch),
        paragraph("Species summary", styles["section"]),
        summary_table(rows, year, styles),
        Spacer(1, 0.12 * inch),
        paragraph(
            "Summary totals are sums of the retained hunt-code rows. Median success is the median of the published hunt-level success rates, not a statewide weighted rate.",
            styles["note"],
        ),
        Spacer(1, 0.08 * inch),
        paragraph("Source and status notes", styles["section"]),
        *source_block(year, styles),
        PageBreak(),
        paragraph("Elk management-quality context", styles["section"]),
        paragraph(
            "Average age is the observed age of harvested limited-entry bull elk from the 2024 annual report. The three-year average and age objective are cross-checked to the current Hunt Planner database fields. Observed annual age, three-year average, and management objective remain separate metrics.",
            styles["body"],
        ),
        elk_age_table(age_rows, planner_matches, styles),
        Spacer(1, 0.08 * inch),
        paragraph(
            "Source: Utah DWR 2024 Big Game Annual Report, PDF page 102 (printed page 99), and the 2026 Hunt Planner DATABASE.csv snapshot. Status compares the metric to the unit objective band; 'Above' is context, not a permit recommendation.",
            styles["note"],
        ),
        PageBreak(),
        paragraph("Mule deer management-quality context", styles["section"]),
        paragraph(
            "Deer quality is represented by postseason bucks per 100 does. This table keeps the observed 2022, 2023, and 2024 ratios, the three-year average, and each unit's objective band together. Deer age is not substituted for the buck-to-doe measure.",
            styles["body"],
        ),
        deer_ratio_table(styles),
        Spacer(1, 0.08 * inch),
        paragraph(
            "Source: Utah DWR 2024 Big Game Annual Report, PDF pages 37-38 (printed pages 34-35). Asterisks in the source mean insufficient data.",
            styles["note"],
        ),
        PageBreak(),
        paragraph("Hunt-code harvest results", styles["section"]),
        paragraph(
            "The appendix is grouped by species and retains source-level hunt codes, hunt names, effort, harvest, and success measures. Blank source values are shown as '-'.",
            styles["body"],
        ),
    ]

    for group_index, (species, species_rows) in enumerate(grouped.items()):
        if group_index:
            story.append(PageBreak())
        story.extend(
            [
                paragraph(f"{species} - {len(species_rows):,} hunt rows", styles["section"]),
                hunt_results_table(species_rows, year, styles),
            ]
        )

    doc.build(
        story,
        onFirstPage=lambda canvas, document: page_background(canvas, document, report_title, preliminary),
        onLaterPages=lambda canvas, document: page_background(canvas, document, report_title, preliminary),
    )

    reader = PdfReader(str(output_path))
    if reader.is_encrypted or len(reader.pages) < 5:
        raise RuntimeError(f"PDF validation failed: {output_path}")


def publish_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256(source) != sha256(destination):
        raise RuntimeError(f"Published PDF hash mismatch: {destination}")


def main() -> None:
    harvest_2024 = read_zip_csv(HARVEST_2024_ZIP, "harvest_results_2024_for_2025_hunt_code_keyed.csv")
    harvest_2025 = read_zip_csv(HARVEST_2025_ZIP, "harvest_results_2025_for_2026_hunt_code_keyed.csv")
    elk_age = read_zip_csv(ELK_AGE_ZIP, "elk_average_age_limited_entry_units_2015_2024.csv")
    database_rows = read_database()

    if len(harvest_2024) != 1039:
        raise RuntimeError(f"Expected 1,039 keyed 2024 rows, found {len(harvest_2024):,}")
    if len(harvest_2025) != 1120:
        raise RuntimeError(f"Expected 1,120 packaged 2025 rows, found {len(harvest_2025):,}")
    if len(elk_age) != 26:
        raise RuntimeError(f"Expected 26 elk age rows, found {len(elk_age):,}")
    if len(DEER_RATIO_ROWS) != 40:
        raise RuntimeError(f"Expected 40 deer ratio rows, found {len(DEER_RATIO_ROWS):,}")

    planner_matches = planner_crosscheck(elk_age, database_rows)
    unmatched = [key for key, value in planner_matches.items() if value != "Verified"]
    if unmatched:
        raise RuntimeError(f"Hunt Planner age/objective cross-check failed for: {unmatched}")

    harvest_2025 = reconcile_2025_dashboard(harvest_2025)
    if len(harvest_2025) != 1141:
        raise RuntimeError(f"Expected 1,141 current 2025 dashboard rows, found {len(harvest_2025):,}")

    build_report(2024, source_rows_for_year(harvest_2024, 2024), elk_age, planner_matches, OUTPUT_2024)
    build_report(2025, source_rows_for_year(harvest_2025, 2025), elk_age, planner_matches, OUTPUT_2025)
    publish_copy(OUTPUT_2024, PUBLIC_2024)
    publish_copy(OUTPUT_2025, PUBLIC_2025)

    print(f"2024_PDF={OUTPUT_2024}")
    print(f"2025_PDF={OUTPUT_2025}")
    print(f"2024_PUBLIC={PUBLIC_2024}")
    print(f"2025_PUBLIC={PUBLIC_2025}")
    print(f"2024_SHA256={sha256(OUTPUT_2024)}")
    print(f"2025_SHA256={sha256(OUTPUT_2025)}")
    print(f"GENERATED={date.today().isoformat()}")


if __name__ == "__main__":
    main()
