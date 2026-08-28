from __future__ import annotations

import importlib.util
import json
import shutil
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
HARVEST_BUILDER = ROOT / "scripts" / "build-harvest-library-pdfs.py"
CONSERVATION_SOURCE = ROOT / "data" / "conservation-permit-hunt-table-2025-27.json"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
OUTPUT = (
    ROOT
    / "output"
    / "pdf"
    / "harvest-results"
    / "Utah_2025_Permit_Utilization_and_Conservation_Supplement_UOGA.pdf"
)
PUBLIC = (
    ROOT
    / "public"
    / "hard-copy"
    / "harvest-data"
    / "2025"
    / OUTPUT.name
)

DWR_HARVEST_URL = "https://wildlife.utah.gov/biggame/reports"
DWR_REPORTING_URL = "https://wildlife.utah.gov/harvest"
DWR_CONSERVATION_URL = "https://wildlife.utah.gov/conservationpermits"
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
    "Bison",
    "Deer",
    "Desert Bighorn Sheep",
    "Elk",
    "Moose",
    "Mountain Goat",
    "Pronghorn",
    "Rocky Mountain Bighorn Sheep",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def load_harvest_module():
    spec = importlib.util.spec_from_file_location("harvest_library_builder", HARVEST_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load harvest report builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rows() -> tuple[list[dict[str, str]], object]:
    module = load_harvest_module()
    rows = module.read_zip_csv(module.HARVEST_2025_ZIP, "harvest_results_2025_for_2026_hunt_code_keyed.csv")
    rows = module.reconcile_2025_dashboard(rows)
    if len(rows) != 1141:
        raise RuntimeError(f"Expected 1,141 current 2025 dashboard rows, found {len(rows):,}")
    return rows, module


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
    canvas.drawString(0.42 * inch, 0.21 * inch, "Utah 2025 Permit Utilization / Conservation Supplement")
    canvas.drawRightString(PAGE_W - 0.42 * inch, 0.21 * inch, f"Page {doc.page}")
    canvas.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=ORANGE, spaceAfter=7),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=DARK, spaceAfter=9),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5, leading=15, textColor=MUTED, spaceAfter=10),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=DARK, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.8, leading=12.5, textColor=TEXT, spaceAfter=7),
        "callout": ParagraphStyle("callout", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=GREEN, alignment=TA_CENTER),
        "note": ParagraphStyle("note", fontName="Helvetica", fontSize=7.3, leading=9.6, textColor=MUTED, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=6.8, leading=8.1, textColor=TEXT),
        "cell_bold": ParagraphStyle("cell_bold", fontName="Helvetica-Bold", fontSize=6.8, leading=8.1, textColor=TEXT),
        "cell_center": ParagraphStyle("cell_center", fontName="Helvetica", fontSize=6.8, leading=8.1, textColor=TEXT, alignment=TA_CENTER),
        "header": ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=6.5, leading=7.8, textColor=colors.white, alignment=TA_CENTER),
        "tiny": ParagraphStyle("tiny", fontName="Helvetica", fontSize=5.35, leading=6.15, textColor=TEXT),
        "tiny_bold": ParagraphStyle("tiny_bold", fontName="Helvetica-Bold", fontSize=5.35, leading=6.15, textColor=TEXT),
        "tiny_center": ParagraphStyle("tiny_center", fontName="Helvetica", fontSize=5.35, leading=6.15, textColor=TEXT, alignment=TA_CENTER),
        "tiny_header": ParagraphStyle("tiny_header", fontName="Helvetica-Bold", fontSize=5.15, leading=5.9, textColor=colors.white, alignment=TA_CENTER),
    }


def summary_stats(rows: list[dict[str, str]], number) -> dict[str, object]:
    both = [
        row
        for row in rows
        if number(row.get("permits")) is not None and number(row.get("hunters_afield")) is not None
    ]
    return {
        "both": len(both),
        "equal": sum(number(row.get("permits")) == number(row.get("hunters_afield")) for row in both),
        "permits_gt": sum(number(row.get("permits")) > number(row.get("hunters_afield")) for row in both),
        "hunters_gt": sum(number(row.get("hunters_afield")) > number(row.get("permits")) for row in both),
        "blank_permits": sum(number(row.get("permits")) is None for row in rows),
        "blank_hunters": sum(number(row.get("hunters_afield")) is None for row in rows),
        "permits": int(sum(number(row.get("permits")) or 0 for row in rows)),
        "hunters": int(sum(number(row.get("hunters_afield")) or 0 for row in rows)),
        "harvest": int(sum(number(row.get("harvest")) or 0 for row in rows)),
    }


def species_summary(rows: list[dict[str, str]], number, s: dict[str, ParagraphStyle]) -> Table:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("species"))].append(row)
    data = [[p(value, s["header"]) for value in (
        "Species", "Hunt rows", "Permits", "Hunters afield", "Permit-hunter gap", "Afield / permits", "Harvest"
    )]]
    for species in SPECIES_ORDER:
        species_rows = grouped[species]
        permits = int(sum(number(row.get("permits")) or 0 for row in species_rows))
        hunters = int(sum(number(row.get("hunters_afield")) or 0 for row in species_rows))
        harvest = int(sum(number(row.get("harvest")) or 0 for row in species_rows))
        data.append([
            p(species, s["cell_bold"]),
            p(f"{len(species_rows):,}", s["cell_center"]),
            p(f"{permits:,}", s["cell_center"]),
            p(f"{hunters:,}", s["cell_center"]),
            p(f"{permits - hunters:,}", s["cell_center"]),
            p(f"{hunters / permits * 100:.1f}%" if permits else "-", s["cell_center"]),
            p(f"{harvest:,}", s["cell_center"]),
        ])
    permits = int(sum(number(row.get("permits")) or 0 for row in rows))
    hunters = int(sum(number(row.get("hunters_afield")) or 0 for row in rows))
    harvest = int(sum(number(row.get("harvest")) or 0 for row in rows))
    data.append([
        p("TOTAL", s["cell_bold"]), p("1,141", s["cell_bold"]), p(f"{permits:,}", s["cell_bold"]),
        p(f"{hunters:,}", s["cell_bold"]), p(f"{permits - hunters:,}", s["cell_bold"]),
        p(f"{hunters / permits * 100:.1f}%", s["cell_bold"]), p(f"{harvest:,}", s["cell_bold"])
    ])
    table = Table(data, colWidths=[2.15, 0.78, 1.0, 1.05, 1.0, 0.95, 0.9])
    table._argW = [value * inch for value in table._argW]
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def conservation_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if clean(row.get("hunt_type")).lower() == "conservation"]


def conservation_table(rows: list[dict[str, str]], number, s: dict[str, ParagraphStyle]) -> Table:
    data = [[p(value, s["tiny_header"]) for value in (
        "Species", "Hunt code", "Hunt name", "Weapon", "Permits", "Hunters afield", "Harvest", "Afield / permits", "Success"
    )]]
    for row in rows:
        permits = number(row.get("permits")) or 0
        hunters = number(row.get("hunters_afield")) or 0
        harvest = number(row.get("harvest")) or 0
        species = {
            "Desert Bighorn Sheep": "Desert Bighorn",
            "Rocky Mountain Bighorn Sheep": "Rocky Mtn Bighorn",
        }.get(clean(row.get("species")), clean(row.get("species")))
        weapon = "ALW" if clean(row.get("weapon")) == "Any Legal Weapon" else clean(row.get("weapon"))
        data.append([
            p(species, s["tiny"]),
            p(row.get("hunt_code"), s["tiny_bold"]),
            p(row.get("hunt_name"), s["tiny"]),
            p(weapon, s["tiny"]),
            p(f"{permits:,.0f}", s["tiny_center"]),
            p(f"{hunters:,.0f}", s["tiny_center"]),
            p(f"{harvest:,.0f}", s["tiny_center"]),
            p(f"{hunters / permits * 100:.1f}%" if permits else "-", s["tiny_center"]),
            p(f"{harvest / hunters * 100:.1f}%" if hunters else "-", s["tiny_center"]),
        ])
    data.append([
        p("TOTAL", s["tiny_bold"]), "", "", "",
        p("31", s["tiny_bold"]), p("28", s["tiny_bold"]), p("24", s["tiny_bold"]),
        p("90.3%", s["tiny_bold"]), p("85.7%", s["tiny_bold"])
    ])
    widths = [1.05, 0.62, 1.58, 0.95, 0.55, 0.65, 0.55, 0.75, 0.6]
    table = Table(data, colWidths=[value * inch for value in widths], repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("SPAN", (0, -1), (3, -1)),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def conservation_species_summary(s: dict[str, ParagraphStyle]) -> Table:
    records = json.loads(CONSERVATION_SOURCE.read_text(encoding="utf-8"))
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"permits": 0, "records": 0, "codes": 0})
    code_sets: dict[str, set[str]] = defaultdict(set)
    for record in records:
        species = clean(record.get("sourceSpecies")) or clean(record.get("species"))
        grouped[species]["permits"] += int(record.get("permitCount") or 0)
        grouped[species]["records"] += 1
        code_sets[species].update(clean(code).upper() for code in record.get("sourceHuntCodes", []) if clean(code))
    data = [[p(value, s["header"]) for value in (
        "Species", "Annual conservation permits", "Area/condition records", "Hunt codes showing coverage"
    )]]
    order = ["Antlerless Elk", "Bear", "Bison", "Deer", "Desert Bighorn Sheep", "Elk", "Moose", "Mountain Goat", "Pronghorn", "Rocky Mountain Bighorn Sheep", "Turkey"]
    for species in order:
        data.append([
            p(species, s["cell_bold"]),
            p(f"{grouped[species]['permits']:,}", s["cell_center"]),
            p(f"{grouped[species]['records']:,}", s["cell_center"]),
            p(f"{len(code_sets[species]):,}", s["cell_center"]),
        ])
    data.append([p("TOTAL", s["cell_bold"]), p("336", s["cell_bold"]), p("271", s["cell_bold"]), p("418 unique", s["cell_bold"])])
    table = Table(data, colWidths=[2.85, 1.65, 1.65, 1.75])
    table._argW = [value * inch for value in table._argW]
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


def build_pdf(rows: list[dict[str, str]], module) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    stats = summary_stats(rows, module.number)
    cons_rows = sorted(conservation_rows(rows), key=lambda row: (clean(row.get("species")), clean(row.get("hunt_code"))))
    if len(cons_rows) != 18:
        raise RuntimeError(f"Expected 18 official 2025 conservation-class harvest rows, found {len(cons_rows)}")
    cons_permits = int(sum(module.number(row.get("permits")) or 0 for row in cons_rows))
    cons_hunters = int(sum(module.number(row.get("hunters_afield")) or 0 for row in cons_rows))
    cons_harvest = int(sum(module.number(row.get("harvest")) or 0 for row in cons_rows))
    if (cons_permits, cons_hunters, cons_harvest) != (31, 28, 24):
        raise RuntimeError("Official conservation-class totals changed")

    story: list[object] = [
        Spacer(1, 0.18 * inch),
        p("UOGA HUNT LIBRARY | 2025 HARVEST SUPPLEMENT", s["eyebrow"]),
        p("Permit Utilization & Conservation Hunters Afield", s["title"]),
        p(
            "This supplement answers two separate questions: whether published permit counts equal hunters afield, and how conservation permits should be represented without inflating the official 2025 hunter count.",
            s["subtitle"],
        ),
        Table([[p("PERMITS ISSUED DO NOT AUTOMATICALLY EQUAL HUNTERS AFIELD", s["callout"]) ]], colWidths=[9.25 * inch], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 1.2, ORANGE),
            ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)
        ])),
        Spacer(1, 0.14 * inch),
        p(
            f"Yes, the 2025 harvest report was completed to the current DWR dashboard coverage used by the library: 1,141 hunt-code rows across eight species. On the {stats['both']:,} rows where both fields are published, permits equal hunters afield on {stats['equal']:,} rows and permits exceed hunters afield on {stats['permits_gt']:,} rows. No complete row has hunters afield greater than permits.",
            s["body"],
        ),
        p(
            f"Across all retained rows, the published columns sum to {stats['permits']:,} permits and {stats['hunters']:,} hunters afield, a difference of {stats['permits'] - stats['hunters']:,}. That is {stats['hunters'] / stats['permits'] * 100:.1f}% hunters afield per listed permit. Eleven rows have no hunters-afield value and one row has no permit value, so these sums are hunt-row references rather than a substitute for DWR statewide estimates.",
            s["body"],
        ),
        p(
            "DWR requires a harvest report from a big-game permit holder even when the permit holder did not hunt or harvest. That reporting design is why 'permit' and 'hunter afield' are different fields. Hunters afield should come from the official harvest record, not from adding issued, auctioned, or transferred permits.",
            s["body"],
        ),
        p(f"Official references: {DWR_HARVEST_URL} | {DWR_REPORTING_URL}", s["note"]),
        PageBreak(),
        p("All 2025 big-game rows by species", s["section"]),
        species_summary(rows, module.number, s),
        Spacer(1, 0.14 * inch),
        p(
            "The permit-hunter gap is not assumed to be nonparticipation in every case; dashboard values are report/survey outputs and some hunt programs are estimated differently. The correct use is to compare the two published fields, not to replace one with the other.",
            s["body"],
        ),
        p(
            f"Completeness note: {stats['blank_hunters']} of 1,141 rows have no hunters-afield value and {stats['blank_permits']} row has no permit value. The existing 2025 library report includes all 1,141 current dashboard rows. Its elk-age and deer-ratio context remains the latest verified 2024 annual management report because a complete 2025 age/ratio annual report was not available at build time.",
            s["note"],
        ),
        PageBreak(),
        p("Official 2025 conservation-class harvest rows", s["section"]),
        p(
            "These 18 rows are the only rows in the current 2025 big-game harvest set explicitly labeled Hunt Type = Conservation. They are the source-backed conservation hunters-afield value: 31 permits, 28 hunters afield, and 24 harvested animals. Do not add the full conservation allocation list to these hunter totals.",
            s["body"],
        ),
        conservation_table(cons_rows, module.number, s),
        Spacer(1, 0.12 * inch),
        p(
            "A conservation permit can be sold and issued but still not appear as an additional hunter afield on the same public hunt-code row. Some permits have their own conservation hunt code; some area/condition permits cover multiple compatible codes; and an issued permit is not proof the recipient hunted. The DWR harvest row remains authoritative for hunters afield.",
            s["note"],
        ),
        PageBreak(),
        p("Conservation auction allocation context", s["section"]),
        p(
            "The DWR 2025-27 conservation list contains 336 permits per year. The reviewed UOGA crosswalk groups them into 271 species/area/condition records and displays their coverage on 418 eligible hunt codes. Where one permit covers several hunt codes, the companion 2026 comprehensive permit register deliberately lists it on every compatible code.",
            s["body"],
        ),
        conservation_species_summary(s),
        Spacer(1, 0.12 * inch),
        p(
            "Non-additive warning: repeating a multi-code conservation permit on each compatible code creates 1,454 visible code assignments from 336 unduplicated annual permits. That repeated number is a search aid, not a permit total and not a hunters-afield total.",
            s["body"],
        ),
        p(
            "The DWR publishes both the multi-year permit list and a separate 2025 successful-bids report. The bids report identifies the organization, species, description, hunt/weapon, and winning bid. It establishes that a permit was auctioned; it does not establish that the successful bidder ultimately hunted.",
            s["body"],
        ),
        p(f"Official conservation program and bid sources: {DWR_CONSERVATION_URL} | {DWR_BIDS_URL}", s["note"]),
        p(
            "Recommended reading: use the 2025 harvest supplement for actual reported permits/hunters/harvest; use the comprehensive 2026 permit register for per-code availability and conservation coverage; use the existing Draw + EXPO reconciliation for the 26 exact codes whose public draw plus EXPO permits balance to Hunt Planner totals.",
            s["note"],
        ),
    ]

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=PAGE_SIZE,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.42 * inch,
        title="Utah 2025 Permit Utilization and Conservation Hunters Afield Supplement",
        author="Utah Outfitters and Guides Association",
        subject="Official 2025 permit, hunters-afield, harvest, and conservation permit reconciliation",
    )
    doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
    shutil.copy2(OUTPUT, PUBLIC)


def validate_pdf() -> None:
    reader = PdfReader(str(OUTPUT))
    if reader.is_encrypted or len(reader.pages) != 4:
        raise RuntimeError(f"Expected a four-page harvest supplement, found {len(reader.pages)}")
    text = " ".join("\n".join(page.extract_text() or "" for page in reader.pages).split())
    for marker in (
        "PERMITS ISSUED DO NOT AUTOMATICALLY EQUAL HUNTERS AFIELD",
        "1,141 hunt-code rows",
        "31 permits, 28 hunters afield, and 24 harvested animals",
        "1,454 visible code assignments",
        "EA2041",
        "RS1006",
    ):
        if marker not in text:
            raise RuntimeError(f"Missing harvest supplement PDF marker: {marker}")
    if OUTPUT.read_bytes() != PUBLIC.read_bytes():
        raise RuntimeError("Harvest supplement output/public copies differ")


def main() -> int:
    rows, module = load_rows()
    build_pdf(rows, module)
    validate_pdf()
    print(f"OUTPUT={OUTPUT}")
    print(f"PUBLIC={PUBLIC}")
    print("HARVEST_ROWS=1141")
    print("CONSERVATION_HARVEST_ROWS=18")
    print("CONSERVATION_PERMITS=31")
    print("CONSERVATION_HUNTERS_AFIELD=28")
    print("CONSERVATION_HARVEST=24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
