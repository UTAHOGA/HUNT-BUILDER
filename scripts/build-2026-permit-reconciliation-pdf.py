from __future__ import annotations

import csv
import hashlib
import shutil
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
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data_truth"
    / "permit_overlay_truth"
    / "normalized"
    / "huntplanner_draw_expo_reconciliation_2026.csv"
)
UOGA_LOGO = ROOT / "assets" / "logos" / "UOGA-LOGO-CIRCLE.png"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
OUTPUT = (
    ROOT
    / "output"
    / "pdf"
    / "hunt-units-permits"
    / "Utah_2026_Hunt_Units_Permit_Reconciliation_UOGA.pdf"
)
PUBLIC = (
    ROOT
    / "public"
    / "hard-copy"
    / "hunt-units-permits"
    / "2026"
    / OUTPUT.name
)

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
    "Elk",
    "Mountain Goat",
    "Pronghorn",
    "Rocky Mountain Bighorn Sheep",
]


def clean(value: object) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def integer(value: object) -> int:
    return int(clean(value).replace(",", ""))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows() -> list[dict[str, str]]:
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 26:
        raise RuntimeError(f"Expected 26 exact-code reconciliations, found {len(rows)}")
    codes = [clean(row["hunt_code"]).upper() for row in rows]
    if len(codes) != len(set(codes)):
        raise RuntimeError("Duplicate hunt codes found in permit reconciliation source")

    for row in rows:
        for suffix in ("res", "nr", "total"):
            draw = integer(row[f"draw_{suffix}"])
            expo = integer(row[f"expo_{suffix}"])
            planner = integer(row[f"planner_{suffix}"])
            if draw + expo != planner:
                raise RuntimeError(
                    f"{row['hunt_code']} {suffix} does not balance: {draw} + {expo} != {planner}"
                )
        if clean(row["status"]) != "MATCH":
            raise RuntimeError(f"{row['hunt_code']} is not marked MATCH")

    if sum(integer(row["expo_total"]) for row in rows) != 41:
        raise RuntimeError("Expected 41 reconciled Expo permits")
    if sum(integer(row["draw_total"]) for row in rows) != 983:
        raise RuntimeError("Expected 983 public-draw permits")
    if sum(integer(row["planner_total"]) for row in rows) != 1024:
        raise RuntimeError("Expected 1,024 Hunt Planner permits")
    return rows


def page_background(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        try:
            canvas.setFillAlpha(0.12)
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
    canvas.drawString(0.45 * inch, 0.22 * inch, "Utah 2026 Hunt Units / Permit Reconciliation")
    canvas.drawRightString(PAGE_W - 0.45 * inch, 0.22 * inch, f"Page {doc.page}")
    canvas.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=ORANGE, spaceAfter=8
        ),
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=DARK, spaceAfter=12
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=12, leading=17, textColor=MUTED, spaceAfter=14
        ),
        "equation": ParagraphStyle(
            "equation", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=GREEN, alignment=TA_CENTER
        ),
        "section": ParagraphStyle(
            "section", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=DARK, spaceAfter=6
        ),
        "section_note": ParagraphStyle(
            "section_note", fontName="Helvetica", fontSize=9, leading=13, textColor=MUTED, spaceAfter=10
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9.5, leading=14, textColor=TEXT, spaceAfter=8
        ),
        "small": ParagraphStyle(
            "small", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED
        ),
        "cell": ParagraphStyle(
            "cell", fontName="Helvetica", fontSize=7.2, leading=8.6, textColor=TEXT
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold", fontName="Helvetica-Bold", fontSize=7.2, leading=8.6, textColor=TEXT
        ),
        "cell_match": ParagraphStyle(
            "cell_match", fontName="Helvetica-Bold", fontSize=7.2, leading=8.6, textColor=GREEN, alignment=TA_CENTER
        ),
        "header": ParagraphStyle(
            "header", fontName="Helvetica-Bold", fontSize=6.7, leading=8.1, textColor=colors.white, alignment=TA_CENTER
        ),
    }


def summary_table(rows: list[dict[str, str]], s: dict[str, ParagraphStyle]) -> Table:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["species"]].append(row)

    data = [[
        p("Species", s["header"]),
        p("Hunt codes", s["header"]),
        p("Public draw", s["header"]),
        p("EXPO", s["header"]),
        p("Hunt Planner", s["header"]),
        p("Balanced", s["header"]),
    ]]
    for species in SPECIES_ORDER:
        species_rows = grouped[species]
        draw = sum(integer(row["draw_total"]) for row in species_rows)
        expo = sum(integer(row["expo_total"]) for row in species_rows)
        planner = sum(integer(row["planner_total"]) for row in species_rows)
        data.append([
            p(species, s["cell_bold"]),
            p(len(species_rows), s["cell"]),
            p(f"{draw:,}", s["cell"]),
            p(f"{expo:,}", s["cell"]),
            p(f"{planner:,}", s["cell"]),
            p("YES", s["cell_match"]),
        ])
    data.append([
        p("TOTAL", s["cell_bold"]),
        p("26", s["cell_bold"]),
        p("983", s["cell_bold"]),
        p("41", s["cell_bold"]),
        p("1,024", s["cell_bold"]),
        p("26 / 26", s["cell_match"]),
    ])
    table = Table(data, colWidths=[2.4 * inch, 1.05 * inch, 1.15 * inch, 0.9 * inch, 1.2 * inch, 1.1 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, 1), (-1, -2), PALE),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.55, GRID),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def species_table(rows: list[dict[str, str]], s: dict[str, ParagraphStyle]) -> Table:
    data = [[
        p("Hunt code", s["header"]),
        p("Hunt unit", s["header"]),
        p("Weapon", s["header"]),
        p("Draw R", s["header"]),
        p("Draw NR", s["header"]),
        p("Draw total", s["header"]),
        p("EXPO R", s["header"]),
        p("EXPO NR", s["header"]),
        p("EXPO total", s["header"]),
        p("Planner total", s["header"]),
        p("Check", s["header"]),
    ]]
    for row in rows:
        data.append([
            p(row["hunt_code"], s["cell_bold"]),
            p(row["hunt_name"], s["cell"]),
            p(row["weapon"], s["cell"]),
            p(row["draw_res"], s["cell"]),
            p(row["draw_nr"], s["cell"]),
            p(row["draw_total"], s["cell_bold"]),
            p(row["expo_res"], s["cell"]),
            p(row["expo_nr"], s["cell"]),
            p(row["expo_total"], s["cell_bold"]),
            p(row["planner_total"], s["cell_bold"]),
            p("MATCH", s["cell_match"]),
        ])
    data.append([
        p("SPECIES TOTAL", s["cell_bold"]),
        "",
        "",
        p(sum(integer(row["draw_res"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["draw_nr"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["draw_total"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["expo_res"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["expo_nr"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["expo_total"]) for row in rows), s["cell_bold"]),
        p(sum(integer(row["planner_total"]) for row in rows), s["cell_bold"]),
        p(f"{len(rows)} / {len(rows)}", s["cell_match"]),
    ])
    widths = [0.72, 1.65, 1.15, 0.55, 0.58, 0.65, 0.55, 0.58, 0.65, 0.75, 0.65]
    table = Table(data, colWidths=[value * inch for value in widths], repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("ALIGN", (3, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("SPAN", (0, -1), (2, -1)),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def build_pdf(rows: list[dict[str, str]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    story: list[object] = []

    if UOGA_LOGO.exists():
        logo = Image(str(UOGA_LOGO), width=1.05 * inch, height=1.05 * inch)
        logo.hAlign = "LEFT"
        story.extend([logo, Spacer(1, 0.08 * inch)])
    story.extend([
        p("UOGA HUNT LIBRARY | VERIFIED 2026 PERMIT REFERENCE", s["eyebrow"]),
        p("2026 Hunt Units & Permit Reconciliation", s["title"]),
        p(
            "Per-species and per-hunt-code reconciliation of official public-draw permits, "
            "official EXPO permits, and the current Utah DWR Hunt Planner permit totals.",
            s["subtitle"],
        ),
        Spacer(1, 0.08 * inch),
    ])
    equation_box = Table(
        [[p("PUBLIC DRAW PERMITS + EXPO PERMITS = HUNT PLANNER TOTAL", s["equation"])]],
        colWidths=[9.25 * inch],
    )
    equation_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 1.4, ORANGE),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.extend([
        equation_box,
        Spacer(1, 0.2 * inch),
        p("26 of 26 exact-code rows balance | 41 EXPO permits | 100% reconciled", s["section"]),
        p(
            "Scope: these are the 26 official 2026 EXPO allocation hunt codes that exactly reconcile to "
            "a current Hunt Planner code and an official UtahDraws public-draw quota. The statewide EXPO "
            "series contains up to 200 permits; this document isolates the exact-code draw-plus-EXPO "
            "reconciliation set and does not recast other special-permit categories as public draw permits.",
            s["body"],
        ),
        p(
            f"Prepared {date.today().isoformat()} | Source snapshot SHA-256: {sha256(SOURCE)}",
            s["small"],
        ),
        PageBreak(),
        p("Species Summary", s["section"]),
        p(
            "Each species total below is the arithmetic sum of its listed hunt codes. Every resident, "
            "nonresident, and total column was checked independently.",
            s["section_note"],
        ),
        summary_table(rows, s),
        Spacer(1, 0.2 * inch),
        p("Authority and reading notes", s["section"]),
        p(
            "Hunt Planner total: current DWR published quota. Public draw: official UtahDraws actual "
            "draw-result quota. EXPO: official Wildlife Board allocation. R = resident; NR = nonresident. "
            "A MATCH means Draw R + EXPO R = Planner R, Draw NR + EXPO NR = Planner NR, and "
            "Draw total + EXPO total = Planner total.",
            s["body"],
        ),
        p(
            "Official sources: Utah DWR Hunt Planner hunt-code records; official UtahDraws 2026 draw-result "
            "packages; Utah Wildlife Board Sept. 18, 2025 packet, EXPO Permit Allocation tables, PDF pages 135-137.",
            s["body"],
        ),
    ])

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["species"]].append(row)
    for species in SPECIES_ORDER:
        species_rows = sorted(grouped[species], key=lambda row: row["hunt_code"])
        story.extend([
            PageBreak(),
            p(species, s["section"]),
            p(
                f"{len(species_rows)} hunt code{'s' if len(species_rows) != 1 else ''} | "
                f"{sum(integer(row['draw_total']) for row in species_rows):,} public-draw + "
                f"{sum(integer(row['expo_total']) for row in species_rows):,} EXPO = "
                f"{sum(integer(row['planner_total']) for row in species_rows):,} Hunt Planner permits",
                s["section_note"],
            ),
            species_table(species_rows, s),
        ])

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=PAGE_SIZE,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.56 * inch,
        bottomMargin=0.42 * inch,
        title="Utah 2026 Hunt Units and Permit Reconciliation",
        author="Utah Outfitters and Guides Association",
        subject="Official public draw permits plus EXPO permits reconciled to Utah DWR Hunt Planner totals",
    )
    doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
    shutil.copy2(OUTPUT, PUBLIC)


def validate_pdf() -> None:
    reader = PdfReader(str(OUTPUT))
    if len(reader.pages) != 8:
        raise RuntimeError(f"Expected 8 PDF pages, found {len(reader.pages)}")
    text = " ".join("\n".join(page.extract_text() or "" for page in reader.pages).split())
    for marker in (
        "PUBLIC DRAW PERMITS + EXPO PERMITS = HUNT PLANNER TOTAL",
        "26 of 26 exact-code rows balance",
        "BI6503",
        "DB1024",
        "EB3199",
        "PB5037",
        "RS6720",
        "26 / 26",
    ):
        if marker not in text:
            raise RuntimeError(f"Missing PDF text marker: {marker}")
    if sha256(OUTPUT) != sha256(PUBLIC):
        raise RuntimeError("Public PDF copy does not match generated output")


def main() -> int:
    rows = load_rows()
    build_pdf(rows)
    validate_pdf()
    print(f"OUTPUT={OUTPUT}")
    print(f"PUBLIC={PUBLIC}")
    print("ROWS=26")
    print("EXPO_PERMITS=41")
    print("PUBLIC_DRAW_PERMITS=983")
    print("HUNT_PLANNER_PERMITS=1024")
    print("MATCHES=26/26")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
