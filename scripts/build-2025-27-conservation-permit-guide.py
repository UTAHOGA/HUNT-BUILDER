from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
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
CROSSWALK = ROOT / "data" / "conservation-permit-hunt-table-2025-27.json"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OFFICIAL = (
    ROOT
    / "public"
    / "hard-copy"
    / "conservation-permits"
    / "2025-2027"
    / "2025-27_conservation_permits.pdf"
)
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
OUTPUT = (
    ROOT
    / "output"
    / "pdf"
    / "conservation-permits"
    / "Utah_2025-27_Conservation_Permit_Guide_UOGA.pdf"
)
PUBLIC = OFFICIAL.parent / OUTPUT.name

DWR_PROGRAM_URL = "https://wildlife.utah.gov/conservationpermits"
DWR_BIDS_URL = "https://wildlife.utah.gov/pdf/conservation-permits/2025_conservation_permit_bids.pdf"

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

SPECIES_ORDER = [
    "Antlerless Elk",
    "Bear",
    "Bison",
    "Deer",
    "Desert Bighorn Sheep",
    "Elk",
    "Moose",
    "Mountain Goat",
    "Pronghorn",
    "Rocky Mountain Bighorn Sheep",
    "Turkey",
]

CONSERVATION_ONLY_CODES = ["EA1180", "EA1270", "EA1271", "EA2041", "EA2045"]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def page_background(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        try:
            canvas.setFillAlpha(0.11)
        except AttributeError:
            pass
        canvas.drawImage(str(TOPO), 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False, mask="auto")
        try:
            canvas.setFillAlpha(1)
        except AttributeError:
            pass
    canvas.setFillColor(DARK)
    canvas.rect(0, PAGE_H - 0.35 * inch, PAGE_W, 0.35 * inch, fill=1, stroke=0)
    canvas.setFillColor(ORANGE)
    canvas.rect(0, PAGE_H - 0.39 * inch, PAGE_W, 0.04 * inch, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(0.42 * inch, 0.21 * inch, "UOGA Hunt Library | 2025-27 Utah Conservation Permits")
    canvas.drawRightString(PAGE_W - 0.42 * inch, 0.21 * inch, f"Page {doc.page}")
    canvas.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=ORANGE, spaceAfter=7),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=DARK, spaceAfter=8),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5, leading=15, textColor=MUTED, spaceAfter=10),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=DARK, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.8, textColor=TEXT, spaceAfter=7),
        "body_bold": ParagraphStyle("body_bold", fontName="Helvetica-Bold", fontSize=9, leading=12.8, textColor=TEXT, spaceAfter=5),
        "callout": ParagraphStyle("callout", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=GREEN, alignment=TA_CENTER),
        "note": ParagraphStyle("note", fontName="Helvetica", fontSize=7.4, leading=9.8, textColor=MUTED, spaceAfter=4),
        "stat": ParagraphStyle("stat", fontName="Helvetica-Bold", fontSize=24, leading=27, textColor=ORANGE, alignment=TA_CENTER),
        "stat_label": ParagraphStyle("stat_label", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=DARK, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=6.8, leading=8.1, textColor=TEXT),
        "cell_bold": ParagraphStyle("cell_bold", fontName="Helvetica-Bold", fontSize=6.8, leading=8.1, textColor=TEXT),
        "cell_center": ParagraphStyle("cell_center", fontName="Helvetica", fontSize=6.8, leading=8.1, textColor=TEXT, alignment=TA_CENTER),
        "header": ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=6.5, leading=7.8, textColor=colors.white, alignment=TA_CENTER),
        "step": ParagraphStyle("step", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=DARK, spaceAfter=4),
        "step_number": ParagraphStyle("step_number", fontName="Helvetica-Bold", fontSize=25, leading=28, textColor=ORANGE, alignment=TA_CENTER),
    }


def load_sources() -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    records = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != 271:
        raise RuntimeError(f"Expected 271 conservation crosswalk records, found {len(records) if isinstance(records, list) else 'non-list'}")
    with DATABASE.open(encoding="utf-8-sig", newline="") as handle:
        database_rows = list(csv.DictReader(handle))
    database = {clean(row.get("hunt_code")).upper(): row for row in database_rows if clean(row.get("hunt_code"))}
    if len(database) < 1800:
        raise RuntimeError(f"DATABASE hunt-code coverage is unexpectedly low: {len(database)}")
    return records, database


def conservation_summary(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    grouped: dict[str, dict[str, object]] = defaultdict(lambda: {"permits": 0, "records": 0, "codes": set()})
    repeated_assignments = 0
    for record in records:
        species = clean(record.get("sourceSpecies")) or clean(record.get("species"))
        grouped[species]["permits"] = int(grouped[species]["permits"]) + int(record.get("permitCount") or 0)
        grouped[species]["records"] = int(grouped[species]["records"]) + 1
        codes = {clean(code).upper() for code in record.get("sourceHuntCodes", []) if clean(code)}
        grouped[species]["codes"].update(codes)
        repeated_assignments += int(record.get("permitCount") or 0) * len(codes)
    rows = [
        {
            "species": species,
            "permits": int(grouped[species]["permits"]),
            "records": int(grouped[species]["records"]),
            "codes": len(grouped[species]["codes"]),
        }
        for species in SPECIES_ORDER
    ]
    if sum(int(row["permits"]) for row in rows) != 336:
        raise RuntimeError("Conservation permit total changed from 336")
    if sum(int(row["records"]) for row in rows) != 271:
        raise RuntimeError("Conservation area/condition record total changed from 271")
    if len(set().union(*(grouped[species]["codes"] for species in SPECIES_ORDER))) != 418:
        raise RuntimeError("Conservation covered-code total changed from 418")
    if repeated_assignments != 1454:
        raise RuntimeError(f"Repeated display assignment total changed from 1,454 to {repeated_assignments:,}")
    return rows, repeated_assignments


def stat_cards(s: dict[str, ParagraphStyle]) -> Table:
    data = [
        [p("336", s["stat"]), p("$8.17M", s["stat"]), p("2025-27", s["stat"])],
        [p("UNDUPLICATED PERMITS EACH YEAR", s["stat_label"]), p("OFFICIAL LISTED TOTAL VALUE", s["stat_label"]), p("MULTI-YEAR ALLOCATION CYCLE", s["stat_label"])],
    ]
    table = Table(data, colWidths=[3.0 * inch, 3.0 * inch, 3.0 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 1.1, ORANGE),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, GRID),
        ("TOPPADDING", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
    ]))
    return table


def species_table(summary: list[dict[str, object]], s: dict[str, ParagraphStyle]) -> Table:
    data = [[p(value, s["header"]) for value in (
        "Species", "Annual permits", "Area / condition records", "Hunt codes showing coverage"
    )]]
    for row in summary:
        data.append([
            p(row["species"], s["cell_bold"]),
            p(f"{row['permits']:,}", s["cell_center"]),
            p(f"{row['records']:,}", s["cell_center"]),
            p(f"{row['codes']:,}", s["cell_center"]),
        ])
    data.append([p("TOTAL", s["cell_bold"]), p("336", s["cell_bold"]), p("271", s["cell_bold"]), p("418 unique", s["cell_bold"])])
    table = Table(data, colWidths=[3.0 * inch, 1.55 * inch, 1.85 * inch, 1.95 * inch])
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def conservation_only_table(database: dict[str, dict[str, str]], s: dict[str, ParagraphStyle]) -> Table:
    data = [[p(value, s["header"]) for value in (
        "Hunt code", "2026 Hunt Planner name", "Species", "Weapon", "Public-draw quota", "Conservation permits"
    )]]
    for code in CONSERVATION_ONLY_CODES:
        row = database.get(code)
        if not row:
            raise RuntimeError(f"Missing conservation-only hunt code {code}")
        conservation = clean(row.get("conservation_permits_2026_total"))
        public_total = clean(row.get("permit_allotment_2026_total")) or clean(row.get("permits_2026_total"))
        if conservation != "4" or public_total:
            raise RuntimeError(f"{code} expected four conservation permits and no public-draw quota")
        data.append([
            p(code, s["cell_bold"]),
            p(row.get("hunt_name"), s["cell"]),
            p("Antlerless Elk", s["cell"]),
            p(row.get("weapon"), s["cell"]),
            p("Not published", s["cell_center"]),
            p("4", s["cell_center"]),
        ])
    data.append([p("TOTAL", s["cell_bold"]), "", "", "", p("Not additive", s["cell_bold"]), p("20", s["cell_bold"])])
    table = Table(data, colWidths=[0.8 * inch, 2.3 * inch, 1.15 * inch, 1.5 * inch, 1.2 * inch, 1.25 * inch])
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("SPAN", (0, -1), (3, -1)),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def concept_table(s: dict[str, ParagraphStyle]) -> Table:
    data = [
        [p("PUBLIC-DRAW PERMITS", s["body_bold"]), p("CONSERVATION PERMITS", s["body_bold"]), p("HUNTERS AFIELD", s["body_bold"])],
        [
            p("Permits offered through an applicable public drawing. Use the published resident, nonresident, and total quota fields.", s["note"]),
            p("Special permits allocated through approved conservation organizations. Keep them separate from public-draw quota.", s["note"]),
            p("People reported as actually hunting. Use the official harvest report; do not infer this number from permits issued.", s["note"]),
        ],
    ]
    table = Table(data, colWidths=[3.0 * inch, 3.0 * inch, 3.0 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TAN),
        ("BACKGROUND", (0, 1), (-1, 1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.8, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def reading_steps(s: dict[str, ParagraphStyle]) -> Table:
    rows = [
        ("1", "Start here: Conservation Permits Explained", "Read the annual totals, species breakdown, and non-additive warning before comparing hunt codes."),
        ("2", "View Official Source", "Open the official DWR 2025-27 working list for the individual species, area, condition, value, and organization rows."),
        ("3", "Open the 2026 comprehensive register", "Use the 60-page hunt-code register when you need exact public quota, EXPO subset, or conservation coverage by hunt code."),
    ]
    data = []
    for number, title, body in rows:
        data.append([
            p(number, s["step_number"]),
            [p(title, s["step"]), p(body, s["body"])],
        ])
    table = Table(data, colWidths=[0.8 * inch, 8.2 * inch])
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.9, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]
    table.setStyle(TableStyle(commands))
    return table


def build_pdf(records: list[dict[str, object]], database: dict[str, dict[str, str]]) -> None:
    summary, repeated_assignments = conservation_summary(records)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    story: list[object] = [
        Spacer(1, 0.15 * inch),
        p("UOGA HUNT LIBRARY | PUBLIC REFERENCE GUIDE", s["eyebrow"]),
        p("2025-27 Utah Conservation Permits Explained", s["title"]),
        p(
            "A readable guide to Utah's multi-year conservation permit allocation: what the official list contains, how those permits relate to hunt codes, and which numbers must remain separate.",
            s["subtitle"],
        ),
        stat_cards(s),
        Spacer(1, 0.15 * inch),
        Table([[p("ONE PERMIT MAY COVER MULTIPLE COMPATIBLE HUNT CODES - DO NOT ADD REPEATED COVERAGE", s["callout"]) ]], colWidths=[9.0 * inch], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("BOX", (0, 0), (-1, -1), 1.2, ORANGE),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ])),
        Spacer(1, 0.12 * inch),
        p(
            "The official DWR working list contains 336 conservation permits for each year of the 2025-27 cycle. The reviewed UOGA crosswalk groups those individual rows into 271 species/area/condition records and identifies 418 hunt codes that show compatible coverage.",
            s["body"],
        ),
        p(
            "This is an allocation guide, not a public-draw odds report and not a hunter-participation report. Conservation permits remain a separate special-permit overlay unless an official source explicitly identifies a public-draw quota.",
            s["body"],
        ),
        PageBreak(),
        p("Annual conservation allocation by species", s["section"]),
        p(
            "Annual permits are counted once. Area/condition records consolidate identical allocation descriptions. Hunt-code coverage is a search aid showing where those permits may apply.",
            s["body"],
        ),
        species_table(summary, s),
        Spacer(1, 0.12 * inch),
        p(
            f"Non-additive warning: the crosswalk displays {repeated_assignments:,} permit-to-code assignments because some permits cover several hunt codes. The official program total remains 336 annual permits - not {repeated_assignments:,} permits.",
            s["body_bold"],
        ),
        p(
            "The official list's dollar amount is the total listed value of the permit allocation. It is not a forecast of hunter participation, harvest, or public-draw demand.",
            s["note"],
        ),
        PageBreak(),
        p("Five conservation-only antlerless elk hunt codes", s["section"]),
        p(
            "The current 2026 Hunt Planner identifies these five conservation hunts. Each has four conservation permits from the 2025-27 allocation, for 20 unduplicated antlerless elk conservation permits. Their public-draw quota remains blank because these are conservation-only records.",
            s["body"],
        ),
        conservation_only_table(database, s),
        Spacer(1, 0.16 * inch),
        concept_table(s),
        Spacer(1, 0.11 * inch),
        p(
            "Do not merge conservation permits into resident/nonresident public-draw totals. Do not convert issued or auctioned permits into hunters afield. The official harvest report remains authoritative for participation and harvest.",
            s["note"],
        ),
        PageBreak(),
        p("How to use the Conservation Permits folder", s["section"]),
        p(
            "The library presents the documents in the order a public user should read them: explanation first, official evidence second, detailed hunt-code lookup third.",
            s["body"],
        ),
        reading_steps(s),
        Spacer(1, 0.15 * inch),
        Table([[p("336 UNDUPLICATED ANNUAL PERMITS", s["callout"]), p("1,454 REPEATED CODE ASSIGNMENTS", s["callout"]) ]], colWidths=[4.5 * inch, 4.5 * inch], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("BOX", (0, 0), (-1, -1), 1.1, ORANGE),
            ("INNERGRID", (0, 0), (-1, -1), 0.6, ORANGE),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])),
        Spacer(1, 0.12 * inch),
        p(
            f"Official program: {DWR_PROGRAM_URL} | 2025 successful-bids report: {DWR_BIDS_URL}",
            s["note"],
        ),
        p(
            "Source authority: Utah DWR 2025-27 Multi-Year Conservation Permit working list (336 permits; total listed value $8,165,414.25), current 2026 Hunt Planner hunt identities, and the reviewed UOGA conservation permit-to-hunt-code crosswalk. The official source document remains available immediately after this guide in the library.",
            s["note"],
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=PAGE_SIZE,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.42 * inch,
        title="2025-27 Utah Conservation Permits Explained",
        author="Utah Outfitters and Guides Association",
        subject="Public guide to Utah's 2025-27 conservation permit allocation and hunt-code coverage",
    )
    doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
    shutil.copy2(OUTPUT, PUBLIC)


def validate_pdf() -> None:
    if not OFFICIAL.exists():
        raise RuntimeError(f"Official source is missing: {OFFICIAL}")
    official_reader = PdfReader(str(OFFICIAL))
    official_text = " ".join("\n".join(page.extract_text() or "" for page in official_reader.pages).split())
    if len(official_reader.pages) != 6 or "Total value issued" not in official_text or "8,165,414.25" not in official_text:
        raise RuntimeError("Official DWR conservation working list validation failed")

    reader = PdfReader(str(OUTPUT))
    if reader.is_encrypted or len(reader.pages) != 4:
        raise RuntimeError(f"Expected a four-page conservation guide, found {len(reader.pages)}")
    text = " ".join("\n".join(page.extract_text() or "" for page in reader.pages).split())
    for marker in (
        "2025-27 Utah Conservation Permits Explained",
        "336 UNDUPLICATED ANNUAL PERMITS",
        "1,454 REPEATED CODE ASSIGNMENTS",
        "EA1180",
        "EA1270",
        "EA1271",
        "EA2041",
        "EA2045",
        "View Official Source",
        "Open the 2026 comprehensive register",
    ):
        if marker not in text:
            raise RuntimeError(f"Missing conservation guide PDF marker: {marker}")
    if OUTPUT.read_bytes() != PUBLIC.read_bytes():
        raise RuntimeError("Conservation guide output/public copies differ")


def main() -> int:
    records, database = load_sources()
    build_pdf(records, database)
    validate_pdf()
    print(f"OUTPUT={OUTPUT}")
    print(f"PUBLIC={PUBLIC}")
    print("PAGES=4")
    print("ANNUAL_PERMITS=336")
    print("AREA_CONDITION_RECORDS=271")
    print("COVERED_HUNT_CODES=418")
    print("REPEATED_CODE_ASSIGNMENTS=1454")
    print("CONSERVATION_ONLY_ANTLERLESS_CODES=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
