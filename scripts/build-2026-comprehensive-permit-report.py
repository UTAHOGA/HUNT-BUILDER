from __future__ import annotations

import csv
import hashlib
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
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
EXPO_SOURCE = (
    ROOT
    / "data_truth"
    / "permit_overlay_truth"
    / "normalized"
    / "huntplanner_draw_expo_reconciliation_2026.csv"
)
CONSERVATION_SOURCE = ROOT / "data" / "conservation-permit-hunt-table-2025-27.json"
TOPO = ROOT / "assets" / "logos" / "tan-topo.png"
OUTPUT = (
    ROOT
    / "output"
    / "pdf"
    / "hunt-units-permits"
    / "Utah_2026_All_Hunt_Codes_and_Available_Permits_UOGA.pdf"
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
    "Black Bear",
    "Cougar",
    "Deer",
    "Desert Bighorn Sheep",
    "Elk",
    "Moose",
    "Mountain Goat",
    "Pronghorn",
    "Rocky Mountain Bighorn Sheep",
    "Turkey",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def p(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(clean(value)), style)


def numeric(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_sources() -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    all_database_rows = read_csv(DATABASE)
    if len(all_database_rows) != 1849:
        raise RuntimeError(f"Expected 1,849 DATABASE lineage rows, found {len(all_database_rows):,}")

    cougar_rows = [row for row in all_database_rows if clean(row.get("species")) == "Cougar"]
    current_cougar_rows = [row for row in cougar_rows if clean(row.get("hunt_code")).upper() == "CG9999"]
    if len(cougar_rows) != 32 or len(current_cougar_rows) != 1:
        raise RuntimeError(
            f"Expected one current statewide cougar row plus 31 historical cougar rows; found {len(current_cougar_rows)} current and {len(cougar_rows) - len(current_cougar_rows)} historical"
        )
    current_cougar = current_cougar_rows[0]
    expected_cougar = {
        "hunt_code": "CG9999",
        "species": "Cougar",
        "sex_type": "Either Sex",
        "weapon": "Any Legal Weapon",
        "hunt_type": "Statewide",
        "season": "open",
    }
    for field, expected in expected_cougar.items():
        if clean(current_cougar.get(field)).lower() != expected.lower():
            raise RuntimeError(
                f"Current statewide cougar row disagrees with the reviewed source: {field}={current_cougar.get(field)!r}, expected {expected!r}"
            )

    # DATABASE.csv retains historical cougar lineage, but the current public
    # permit register must show only the active statewide license-based row.
    database_rows = [
        row
        for row in all_database_rows
        if clean(row.get("species")) != "Cougar" or clean(row.get("hunt_code")).upper() == "CG9999"
    ]
    if len(database_rows) != 1818:
        raise RuntimeError(f"Expected 1,818 current report rows after excluding historical cougar codes, found {len(database_rows):,}")
    codes = [clean(row.get("hunt_code")).upper() for row in database_rows]
    if not all(codes) or len(codes) != len(set(codes)):
        raise RuntimeError("DATABASE hunt codes are blank or duplicated")

    expo_rows = read_csv(EXPO_SOURCE)
    expo_by_code = {clean(row["hunt_code"]).upper(): row for row in expo_rows}
    if len(expo_by_code) != 26 or sum(numeric(row["expo_total"]) or 0 for row in expo_rows) != 41:
        raise RuntimeError("Expected 26 exact EXPO codes and 41 EXPO permits")

    conservation_records = json.loads(CONSERVATION_SOURCE.read_text(encoding="utf-8"))
    if len(conservation_records) != 271:
        raise RuntimeError(f"Expected 271 conservation area-condition records, found {len(conservation_records)}")
    if sum(numeric(row.get("permitCount")) or 0 for row in conservation_records) != 336:
        raise RuntimeError("Expected 336 annual conservation permits")

    coverage: dict[str, dict[str, object]] = defaultdict(
        lambda: {"permits": 0, "records": 0, "shared_records": 0, "areas": set(), "species": set()}
    )
    for record in conservation_records:
        permit_count = numeric(record.get("permitCount")) or 0
        source_codes = sorted({clean(code).upper() for code in record.get("sourceHuntCodes", []) if clean(code)})
        if not source_codes:
            raise RuntimeError(f"Conservation record has no hunt-code coverage: {record.get('huntCode')}")
        for code in source_codes:
            entry = coverage[code]
            entry["permits"] = int(entry["permits"]) + permit_count
            entry["records"] = int(entry["records"]) + 1
            if len(source_codes) > 1:
                entry["shared_records"] = int(entry["shared_records"]) + 1
            entry["areas"].add(clean(record.get("area")))
            entry["species"].add(clean(record.get("species")))

    unknown = sorted(set(coverage) - set(codes))
    if len(unknown) != 13:
        raise RuntimeError(f"Expected 13 conservation crosswalk-only codes, found {len(unknown)}")
    if len(coverage) != 418:
        raise RuntimeError(f"Expected conservation coverage on 418 hunt codes, found {len(coverage)}")
    repeated_display_total = sum(int(entry["permits"]) for entry in coverage.values())
    if repeated_display_total != 1454:
        raise RuntimeError(f"Expected 1,454 repeated conservation display assignments, found {repeated_display_total}")

    expected_conservation_only = {
        "EA1180": 4,
        "EA1270": 4,
        "EA1271": 4,
        "EA2041": 4,
        "EA2045": 4,
    }
    for code, expected in expected_conservation_only.items():
        actual = int(coverage.get(code, {}).get("permits", 0))
        if actual != expected:
            raise RuntimeError(
                f"Expected {expected} conservation permits for {code}, found {actual}"
            )

    rows: list[dict[str, object]] = []
    for source in database_rows:
        code = clean(source.get("hunt_code")).upper()
        status = clean(source.get("permit_allotment_2026_status")) or "NO_CURRENT_2026_STATUS"
        published = numeric(source.get("permit_allotment_2026_total"))
        conservation = coverage.get(code)
        expo = expo_by_code.get(code)
        rows.append(
            {
                "hunt_code": code,
                "species": clean(source.get("species")) or "Unclassified",
                "hunt_name": "Cougar - Statewide" if code == "CG9999" else (clean(source.get("hunt_name")) or "-"),
                "hunt_type": clean(source.get("hunt_type")) or "-",
                "weapon": clean(source.get("weapon")) or "-",
                "published_total": published,
                "expo_total": numeric(expo.get("expo_total")) if expo else 0,
                "conservation_permits": int(conservation["permits"]) if conservation else 0,
                "conservation_records": int(conservation["records"]) if conservation else 0,
                "conservation_shared": bool(conservation and conservation["shared_records"]),
                "conservation_areas": sorted(conservation["areas"]) if conservation else [],
                "status": status,
            }
        )
    for code in unknown:
        conservation = coverage[code]
        species_names = sorted(conservation["species"])
        species_name = species_names[0] if len(species_names) == 1 else " / ".join(species_names)
        species_name = {"Bear": "Black Bear", "Antlerless Elk": "Elk"}.get(species_name, species_name)
        rows.append(
            {
                "hunt_code": code,
                "species": species_name,
                "hunt_name": " / ".join(sorted(conservation["areas"])) or "Conservation coverage",
                "hunt_type": "Conservation crosswalk only",
                "weapon": "-",
                "published_total": None,
                "expo_total": 0,
                "conservation_permits": int(conservation["permits"]),
                "conservation_records": int(conservation["records"]),
                "conservation_shared": bool(conservation["shared_records"]),
                "conservation_areas": sorted(conservation["areas"]),
                "status": "CONSERVATION_CODE_NOT_IN_CURRENT_DATABASE",
            }
        )
    return rows, expo_by_code


def page_background(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    if TOPO.exists():
        try:
            canvas.setFillAlpha(0.1)
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
    canvas.setFont("Helvetica", 7)
    canvas.drawString(0.38 * inch, 0.2 * inch, "Utah 2026 Complete Hunt-Code Permit Register")
    canvas.drawRightString(PAGE_W - 0.38 * inch, 0.2 * inch, f"Page {doc.page}")
    canvas.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=ORANGE, spaceAfter=7),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=DARK, spaceAfter=9),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5, leading=15, textColor=MUTED, spaceAfter=11),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=DARK, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.4, leading=12, textColor=TEXT, spaceAfter=7),
        "note": ParagraphStyle("note", fontName="Helvetica", fontSize=7.2, leading=9.5, textColor=MUTED, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=5.3, leading=6.3, textColor=TEXT),
        "cell_bold": ParagraphStyle("cell_bold", fontName="Helvetica-Bold", fontSize=5.4, leading=6.4, textColor=TEXT),
        "cell_center": ParagraphStyle("cell_center", fontName="Helvetica", fontSize=5.3, leading=6.3, textColor=TEXT, alignment=TA_CENTER),
        "header": ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=5.2, leading=6.2, textColor=colors.white, alignment=TA_CENTER),
    }


def summary_table(rows: list[dict[str, object]], s: dict[str, ParagraphStyle]) -> Table:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["species"])].append(row)
    data = [[p(value, s["header"]) for value in (
        "Species", "Codes", "Codes with numeric quota", "Published permits", "EXPO codes", "EXPO permits", "Conservation-covered codes", "Repeated conservation display"
    )]]
    for species in SPECIES_ORDER:
        species_rows = grouped.get(species, [])
        data.append([
            p(species, s["cell_bold"]),
            p(f"{len(species_rows):,}", s["cell_center"]),
            p(f"{sum(row['published_total'] is not None for row in species_rows):,}", s["cell_center"]),
            p(f"{sum(int(row['published_total'] or 0) for row in species_rows):,}", s["cell_center"]),
            p(f"{sum(int(row['expo_total']) > 0 for row in species_rows):,}", s["cell_center"]),
            p(f"{sum(int(row['expo_total']) for row in species_rows):,}", s["cell_center"]),
            p(f"{sum(int(row['conservation_permits']) > 0 for row in species_rows):,}", s["cell_center"]),
            p(f"{sum(int(row['conservation_permits']) for row in species_rows):,}", s["cell_center"]),
        ])
    data.append([
        p("TOTAL", s["cell_bold"]),
        p(f"{len(rows):,}", s["cell_bold"]),
        p(f"{sum(row['published_total'] is not None for row in rows):,}", s["cell_bold"]),
        p(f"{sum(int(row['published_total'] or 0) for row in rows):,}", s["cell_bold"]),
        p("26", s["cell_bold"]),
        p("41", s["cell_bold"]),
        p("418", s["cell_bold"]),
        p("1,454*", s["cell_bold"]),
    ])
    table = Table(data, colWidths=[1.65, 0.55, 1.12, 1.05, 0.7, 0.75, 1.2, 1.25], repeatRows=1)
    table._argW = [value * inch for value in table._argW]
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, -1), (-1, -1), TAN),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index in range(1, len(data) - 1):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
    table.setStyle(TableStyle(commands))
    return table


def status_label(row: dict[str, object]) -> str:
    published = row["published_total"]
    conservation = int(row["conservation_permits"])
    status = str(row["status"])
    if row["hunt_code"] == "CG9999":
        return "Statewide open; license required; no separate cougar permit"
    if status == "CONSERVATION_CODE_NOT_IN_CURRENT_DATABASE":
        return "Crosswalk-only; absent current DATABASE"
    if published is not None:
        replacements = {
            "RES": "resident",
            "NR": "nonresident",
            "DWR": "DWR",
            "CWMU": "CWMU",
            "RAC": "RAC",
        }
        words = []
        for word in status.split("_"):
            words.append(replacements.get(word, word.lower()))
        return " ".join(words).capitalize().replace("dwr", "DWR").replace("cwmu", "CWMU").replace("rac", "RAC")
    if "HISTORICAL" in status or "NOT_ACTIVE" in status:
        return "Not active in 2026"
    if conservation:
        if "conservation" in str(row["hunt_type"]).lower():
            return f"Conservation-only: {conservation} permit(s); no public-draw quota"
        return f"Conservation coverage: {conservation}; no numeric public quota"
    if "NO_PUBLISHED" in status or "NO_QUOTA" in status or "NOT_PUBLISHED" in status:
        return "No numeric quota published"
    return "No current numeric permit reference"


def species_table(rows: list[dict[str, object]], s: dict[str, ParagraphStyle]) -> Table:
    data = [[p(value, s["header"]) for value in (
        "Hunt code", "Hunt name", "Hunt type", "Weapon", "DWR published permits", "EXPO subset", "Conservation coverage*", "Coverage note", "2026 permit status"
    )]]
    for row in rows:
        conservation = int(row["conservation_permits"])
        coverage_note = ""
        if conservation:
            coverage_note = f"{int(row['conservation_records'])} area/condition record(s)"
            if row["conservation_shared"]:
                coverage_note += "; SHARED"
        data.append([
            p(row["hunt_code"], s["cell_bold"]),
            p(row["hunt_name"], s["cell"]),
            p(row["hunt_type"], s["cell"]),
            p(row["weapon"], s["cell"]),
            p("-" if row["published_total"] is None else f"{int(row['published_total']):,}", s["cell_center"]),
            p("-" if not row["expo_total"] else f"{int(row['expo_total']):,}", s["cell_center"]),
            p("-" if not conservation else f"{conservation:,}", s["cell_center"]),
            p(coverage_note or "-", s["cell"]),
            p(status_label(row), s["cell"]),
        ])
    widths = [0.58, 1.4, 0.92, 0.9, 0.68, 0.52, 0.72, 1.05, 1.55]
    table = Table(data, colWidths=[value * inch for value in widths], repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
    ]
    for index in range(1, len(data)):
        commands.append(("BACKGROUND", (0, index), (-1, index), PALE if index % 2 else ALT))
        if int(rows[index - 1]["conservation_permits"]):
            commands.append(("TEXTCOLOR", (6, index), (7, index), GREEN))
    table.setStyle(TableStyle(commands))
    return table


def build_pdf(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    numeric_rows = [row for row in rows if row["published_total"] is not None]
    story: list[object] = [
        Spacer(1, 0.18 * inch),
        p("UOGA HUNT LIBRARY | COMPREHENSIVE 2026 REFERENCE", s["eyebrow"]),
        p("All Hunt Codes & Available Permit Numbers", s["title"]),
        p(
            "A current 2026 permit register built from 1,818 active/reportable DATABASE rows, plus 13 conservation-crosswalk-only codes retained and explicitly flagged. Thirty-one historical cougar unit codes remain in source lineage but are excluded here because 2026 has one statewide open cougar hunt code: CG9999. Every displayed row shows its published numeric permit total or an explicit no-number/status result. Exact EXPO allocations and conservation-permit coverage are separate overlays.",
            s["subtitle"],
        ),
        p(
            f"Published numeric permit totals are present on {len(numeric_rows):,} codes. The 26 exact EXPO codes contain 41 EXPO permits already included in their Hunt Planner totals. Conservation coverage represents 336 annual 2025-27 permits across 271 area/condition records and reaches 418 eligible hunt codes.",
            s["body"],
        ),
        p(
            "*Important conservation reading rule: when one conservation permit covers several hunt codes, it is intentionally listed on every applicable code at the user's direction. The repeated conservation display therefore sums to 1,454 assignments and MUST NOT be treated as 1,454 distinct permits. The unduplicated statewide program total remains 336 annual permits.",
            s["body"],
        ),
        p(
            "DWR published permits are current hunt-code quota/availability references. EXPO is a subset only on the 26 exact reconciled codes; do not add it again. Conservation coverage is a separate special-permit overlay and is not converted into public draw quota or draw probability.",
            s["body"],
        ),
        p(
            f"Prepared {date.today().isoformat()} | DATABASE SHA-256 {sha256(DATABASE)} | Conservation crosswalk SHA-256 {sha256(CONSERVATION_SOURCE)}",
            s["note"],
        ),
        PageBreak(),
        p("Species summary", s["section"]),
        summary_table(rows, s),
        Spacer(1, 0.15 * inch),
        p("How to read the register", s["section"]),
        p(
            "DWR published permits is the current permit_allotment_2026_total field. A dash means the current source does not publish a numeric public quota for that code; it does not erase a separately documented conservation permit shown in the conservation column. The status column explains conservation-only coverage, unlimited/availability-only hunts, private-land/operator assignments, historical/inactive codes, or a missing current numeric reference. Zero is retained as zero and is different from a dash.",
            s["body"],
        ),
        p(
            "Conservation coverage is derived from the 2025-27 conservation permit list and its species-aware area-to-hunt-code crosswalk. 'SHARED' means at least one displayed conservation permit can be used on more than one listed code. This makes each row useful to a hunter researching a code, but the column cannot be summed.",
            s["body"],
        ),
        p(
            "Sources: Utah DWR Hunt Planner DATABASE snapshot; official 2026 EXPO exact-code reconciliation; Utah DWR 2025-27 Conservation Permits list and the reviewed conservation area-to-code crosswalk. Historical harvest results are not used as 2026 permit quotas.",
            s["body"],
        ),
    ]

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["species"])].append(row)
    for species in SPECIES_ORDER:
        species_rows = sorted(grouped[species], key=lambda row: str(row["hunt_code"]))
        story.extend([
            PageBreak(),
            p(f"{species} - {len(species_rows):,} hunt codes", s["section"]),
            p(
                f"{sum(row['published_total'] is not None for row in species_rows):,} codes have a numeric 2026 permit total; {sum(int(row['conservation_permits']) > 0 for row in species_rows):,} codes show conservation coverage. Conservation values marked shared are deliberately repeated and are not additive.",
                s["note"],
            ),
            species_table(species_rows, s),
        ])

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=PAGE_SIZE,
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.38 * inch,
        title="Utah 2026 All Hunt Codes and Available Permit Numbers",
        author="Utah Outfitters and Guides Association",
        subject="Complete current hunt-code permit availability with EXPO and conservation overlays",
    )
    doc.build(story, onFirstPage=page_background, onLaterPages=page_background)
    shutil.copy2(OUTPUT, PUBLIC)


def validate_pdf() -> None:
    reader = PdfReader(str(OUTPUT))
    if reader.is_encrypted or len(reader.pages) < 35:
        raise RuntimeError(f"Comprehensive permit PDF validation failed: {len(reader.pages)} pages")
    text = " ".join("\n".join(page.extract_text() or "" for page in reader.pages).split())
    for marker in (
        "All Hunt Codes & Available Permit Numbers",
        "1,818 active/reportable DATABASE rows",
        "MUST NOT be treated as 1,454 distinct permits",
        "CG9999",
        "Statewide open; license required; no separate cougar permit",
        "DB1024",
        "EA1180",
        "EA1270",
        "EA1271",
        "EA2041",
        "EA2045",
        "Conservation-only: 4 permit(s); no public-draw quota",
        "TK1016",
    ):
        if marker not in text:
            raise RuntimeError(f"Missing comprehensive permit PDF marker: {marker}")
    if sha256(OUTPUT) != sha256(PUBLIC):
        raise RuntimeError("Comprehensive permit output/public hashes differ")


def main() -> int:
    rows, _ = load_sources()
    build_pdf(rows)
    validate_pdf()
    print(f"OUTPUT={OUTPUT}")
    print(f"PUBLIC={PUBLIC}")
    print(f"ROWS={len(rows)}")
    print("SOURCE_DATABASE_LINEAGE_CODES=1849")
    print("CURRENT_REPORT_DATABASE_CODES=1818")
    print("HISTORICAL_COUGAR_CODES_EXCLUDED=31")
    print("CONSERVATION_CROSSWALK_ONLY_CODES=13")
    print(f"NUMERIC_QUOTA_CODES={sum(row['published_total'] is not None for row in rows)}")
    print("EXPO_CODES=26")
    print("EXPO_PERMITS=41")
    print("CONSERVATION_UNDUPLICATED=336")
    print("CONSERVATION_COVERED_CODES=418")
    print("CONSERVATION_REPEATED_DISPLAY=1454")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
