"""Build the source-faithful 2020 harvest review package.

This lane deliberately keeps hunt observations separate from management-unit
biology.  Hunt-code rows retain the DWR Adult/Youth split instead of collapsing
shared general-season deer codes.  Age and composition evidence is stored once
per management unit so repeated weapon hunts cannot multiply it.

Nothing written by this script is permit-allocation or draw-probability truth.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import harvest_identity_compatible

YEAR = 2020
SOURCE_INDEX_URL = "https://wildlife.utah.gov/biggame/reports"
ANNUAL_INDEX_URL = "https://wildlife.utah.gov/hunting/reports"
BIG_GAME_URL = "https://wildlife.utah.gov/pdf/annual-reports/big-game/20_bg_report.pdf"
BEAR_URL = "https://wildlife.utah.gov/pdf/annual-reports/bear/20_black_bear_report.pdf"
COUGAR_URL = "https://wildlife.utah.gov/pdf/annual-reports/cougar/20_cougar_annual_report.pdf"
FURBEARER_URL = "https://wildlife.utah.gov/pdf/annual-reports/furbearer/harvest_20-21.pdf"

RAW_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "harvest_report"
LONG_SOURCE = ROOT / "data_truth" / "harvest_results_truth" / "sources" / "dwr_official_harvest_history_2017_2020_long.csv"
AGGREGATED_SOURCE = ROOT / "data_truth" / "harvest_results_truth" / "sources" / "dwr_official_harvest_history_2017_2021_normalized.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
BIG_GAME_REPORT = RAW_DIR / "bd5fef65__2020.pdf"
BEAR_REPORT = RAW_DIR / "a34306f2__bear_2020.pdf"
COUGAR_REPORT = RAW_DIR / "a7d1d7ba__cougar_2020.pdf"
FURBEARER_REPORT = RAW_DIR / "847a57a8__mixed_2020-21.pdf"

OUT_TRUTH = ROOT / "data_truth" / "harvest_results_truth" / "normalized"
OUT_VALIDATION = ROOT / "data_truth" / "harvest_results_truth" / "validation"
OUT_PDF = ROOT / "output" / "pdf" / "harvest-results" / "2020-review" / "Utah_2020_Harvest_Data_Review_UOGA.pdf"
OUT_OBSERVATIONS = OUT_TRUTH / "harvest_results_2020_observations.csv"
OUT_BIOLOGY = OUT_TRUTH / "harvest_biological_context_2020_by_unit.csv"
OUT_IDENTITY_AUDIT = OUT_VALIDATION / "harvest_2020_identity_audit.csv"
OUT_AUDIT = OUT_VALIDATION / "harvest_2020_review.json"

HUNT_PDFS = {
    "e38eeb18__General-season buck deer.pdf": "General Buck Deer",
    "0b5ca51c__Limited-entry and once-in-a-lifetime species.pdf": "Limited Entry and Once-in-a-Lifetime Big Game",
    "4275246d__Antlerless big game.pdf": "Antlerless Big Game",
}

OBSERVATION_FIELDS = [
    "reported_hunt_year",
    "model_target_year",
    "program",
    "report_category",
    "participant_class",
    "animal_class",
    "access_class",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "weapon",
    "permits",
    "hunters_afield",
    "harvest_total",
    "harvest_male",
    "harvest_female",
    "percent_success",
    "average_days",
    "hunter_satisfaction",
    "source_file",
    "source_page",
    "source_sha256",
    "source_url",
    "source_index_url",
    "source_url_scope",
    "local_cache_mtime_utc",
    "classification_basis",
    "parse_status",
    "do_not_use_for_permit_quota",
    "do_not_use_directly_for_p_draw",
]

BIOLOGY_FIELDS = [
    "reported_hunt_year",
    "species",
    "management_program",
    "management_unit_number",
    "management_unit",
    "subunit_code",
    "subunit",
    "metric",
    "metric_unit",
    "annual_observed_2020",
    "three_year_average_2018_2020",
    "management_objective_2020",
    "harvest_male",
    "harvest_female",
    "harvest_total",
    "percent_success_or_quota_filled",
    "percent_female",
    "percent_adult_male_or_female",
    "source_file",
    "source_page",
    "source_table_title",
    "source_url",
    "source_index_url",
    "source_sha256",
    "local_cache_mtime_utc",
    "deduplication_key",
    "mapping_status",
    "notes",
]


def clean(value: object) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text.replace("�", "-").replace("–", "-").replace("—", "-")


def missing_to_blank(value: object) -> str:
    text = clean(value)
    return "" if text in {"-", "--", "*", "?"} else text


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def animal_class(row: dict[str, str]) -> str:
    prefix = clean(row.get("hunt_code"))[:2].upper()
    return {
        "DB": "Buck",
        "DA": "Antlerless",
        "EB": "Bull",
        "EA": "Antlerless",
        "PB": "Buck",
        "PD": "Antlerless",
        "MB": "Bull",
        "MA": "Antlerless",
        "DS": "Ram",
        "RS": "Ram",
        "GO": "Either sex",
        "BI": "Either sex",
    }.get(prefix, clean(row.get("sex_type")) or "Not separately stated")


def classify_observation(row: dict[str, str], source_path: Path) -> dict[str, str]:
    family = clean(row.get("source_table_family"))
    hunt_type = clean(row.get("hunt_type"))
    if family == "general":
        program = "General Season"
        category = "General Buck Deer"
        participant = "Youth" if "youth" in hunt_type.lower() else "Adult"
        basis = "DWR General Season Buck Deer table; Youth is explicit and the paired standard row is classified Adult."
    elif family == "limited":
        program = "Limited Entry / Once-in-a-Lifetime"
        category = "Limited Entry and Once-in-a-Lifetime Big Game"
        participant = "Not separately stated"
        basis = "DWR limited-entry and once-in-a-lifetime table plus hunt-code species prefix."
    elif family == "antlerless":
        program = "Antlerless"
        category = "Antlerless Big Game"
        participant = "Not separately stated"
        basis = "DWR antlerless big-game table plus hunt-code species prefix."
    else:
        raise ValueError(f"Unexpected 2020 source table family: {family}")

    access = "CWMU" if hunt_type.upper() == "CWMU" else "Public / standard program"
    output = {field: "" for field in OBSERVATION_FIELDS}
    output.update({field: clean(row.get(field)) for field in OBSERVATION_FIELDS if field in row})
    output.update(
        {
            "reported_hunt_year": "2020",
            "model_target_year": "2021",
            "program": program,
            "report_category": category,
            "participant_class": participant,
            "animal_class": animal_class(row),
            "access_class": access,
            "source_sha256": sha256(source_path),
            "source_url": SOURCE_INDEX_URL,
            "source_index_url": SOURCE_INDEX_URL,
            "source_url_scope": "Official DWR dashboard/index URL; the legacy direct PDF URL was not retained in the cache manifest.",
            "local_cache_mtime_utc": cache_mtime(source_path),
            "classification_basis": basis,
            "do_not_use_for_permit_quota": "True",
            "do_not_use_directly_for_p_draw": "True",
        }
    )
    return output


def build_observations() -> list[dict[str, str]]:
    rows = [row for row in read_csv(LONG_SOURCE) if clean(row.get("reported_hunt_year")) == "2020"]
    output: list[dict[str, str]] = []
    for row in rows:
        source_path = RAW_DIR / clean(row.get("source_file"))
        if source_path.name not in HUNT_PDFS or not source_path.exists():
            raise FileNotFoundError(f"Missing classified 2020 hunt source: {source_path}")
        output.append(classify_observation(row, source_path))
    output.sort(key=lambda r: (r["program"], r["species"], r["hunt_code"], r["participant_class"], r["weapon"]))
    return output


def grouped_lines(page: pdfplumber.page.Page) -> list[tuple[float, list[dict[str, object]]]]:
    groups: list[tuple[float, list[dict[str, object]]]] = []
    for word in page.extract_words(use_text_flow=False, keep_blank_chars=False):
        top = round(float(word["top"]), 1)
        if not groups or abs(groups[-1][0] - top) > 0.65:
            groups.append((top, []))
        groups[-1][1].append(word)
    return groups


def text_in(words: list[dict[str, object]], start: float, end: float) -> str:
    selected = [word for word in words if start <= float(word["x0"]) < end]
    return clean(" ".join(str(word["text"]) for word in sorted(selected, key=lambda item: float(item["x0"]))))


def biology_row(**values: object) -> dict[str, str]:
    row = {field: "" for field in BIOLOGY_FIELDS}
    row.update({key: clean(value) for key, value in values.items()})
    source_file = row["source_file"]
    source_path = RAW_DIR / source_file
    row.update(
        {
            "reported_hunt_year": "2020",
            "source_sha256": sha256(source_path),
            "local_cache_mtime_utc": cache_mtime(source_path),
            "source_index_url": ANNUAL_INDEX_URL,
            "deduplication_key": "|".join(
                [
                    row["reported_hunt_year"],
                    row["species"],
                    row["management_program"],
                    row["management_unit_number"],
                    row["management_unit"],
                    row["subunit_code"],
                    row["subunit"],
                    row["metric"],
                ]
            ).lower(),
        }
    )
    return row


def parse_age_rows(page: pdfplumber.page.Page, *, species: str, source_page: int, title: str, goat: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for top, words in grouped_lines(page):
        if not 127.5 <= top <= 510:
            continue
        ordered = sorted(words, key=lambda item: float(item["x0"]))
        unit_number = clean(ordered[0]["text"]) if ordered else ""
        if not re.fullmatch(r"\d+(?:/\d+)?", unit_number):
            continue
        unit_name_start = float(ordered[0]["x1"]) + 0.1
        if goat:
            unit = text_in(words, unit_name_start, 225)
            subunit_code = ""
            subunit = ""
            objective = ""
            annual = text_in(words, 620, 670)
        else:
            unit = text_in(words, unit_name_start, 195)
            subunit_code = missing_to_blank(text_in(words, 195, 214))
            subunit = text_in(words, 214, 340)
            objective = missing_to_blank(text_in(words, 340, 385))
            annual = text_in(words, 645, 680)
        three_year = text_in(words, 680, 730)
        rows.append(
            biology_row(
                species=species,
                management_program="Limited Entry / Once-in-a-Lifetime",
                management_unit_number=unit_number,
                management_unit=unit,
                subunit_code=subunit_code,
                subunit=subunit,
                metric="Average age of harvested animals",
                metric_unit="years",
                annual_observed_2020=missing_to_blank(annual),
                three_year_average_2018_2020=missing_to_blank(three_year),
                management_objective_2020=objective,
                source_file=BIG_GAME_REPORT.name,
                source_page=str(source_page),
                source_table_title=title,
                source_url=BIG_GAME_URL,
                mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
                notes="One biological record per DWR management unit/subunit; weapon hunts are not duplicated.",
            )
        )
    return rows


def parse_deer_ratio_rows(page: pdfplumber.page.Page, *, source_page: int, ranges: list[tuple[float, float, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for top, words in grouped_lines(page):
        program = next((label for start, end, label in ranges if start <= top <= end), "")
        if not program:
            continue
        unit_number = text_in(words, 70, 89)
        if not re.fullmatch(r"\d+", unit_number):
            continue
        rows.append(
            biology_row(
                species="Deer",
                management_program=program,
                management_unit_number=unit_number,
                management_unit=text_in(words, 89, 170) if source_page == 45 else text_in(words, 89, 184),
                subunit_code=missing_to_blank(text_in(words, 170, 197) if source_page == 45 else text_in(words, 184, 211)),
                subunit=text_in(words, 197, 305) if source_page == 45 else text_in(words, 211, 304),
                metric="Postseason buck-to-doe ratio",
                metric_unit="bucks per 100 does",
                annual_observed_2020=missing_to_blank(text_in(words, 450, 495)),
                three_year_average_2018_2020=missing_to_blank(text_in(words, 495, 545)),
                management_objective_2020=missing_to_blank(text_in(words, 300, 350)),
                source_file=BIG_GAME_REPORT.name,
                source_page=str(source_page),
                source_table_title=f"Number of buck deer / 100 does for {program.lower()} management units / subunits, Utah 2018-2020",
                source_url=BIG_GAME_URL,
                mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
                notes="Deer biology is a composition ratio, not harvested age. One row per management unit/subunit.",
            )
        )
    return rows


def premium_deer_age_rows() -> list[dict[str, str]]:
    return [
        biology_row(
            species="Deer",
            management_program="Premium Limited Entry",
            management_unit="Henry Mtns",
            metric="Average age of harvested buck deer",
            metric_unit="years",
            annual_observed_2020="5.2",
            three_year_average_2018_2020="5.2",
            source_file=BIG_GAME_REPORT.name,
            source_page="40",
            source_table_title="Average age of harvested buck deer on premium limited-entry units, Utah 2005-2020",
            source_url=BIG_GAME_URL,
            mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
            notes="Table includes CWMU data and excludes management hunts; percent age 5+ remains in the official source but is not substituted for mean age.",
        ),
        biology_row(
            species="Deer",
            management_program="Premium Limited Entry",
            management_unit="Paunsaugunt",
            metric="Average age of harvested buck deer",
            metric_unit="years",
            annual_observed_2020="5.0",
            three_year_average_2018_2020="5.0",
            source_file=BIG_GAME_REPORT.name,
            source_page="40",
            source_table_title="Average age of harvested buck deer on premium limited-entry units, Utah 2005-2020",
            source_url=BIG_GAME_URL,
            mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
            notes="Table includes CWMU data and excludes management hunts; percent age 5+ remains in the official source but is not substituted for mean age.",
        ),
    ]


def parse_bear_rows(page: pdfplumber.page.Page) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for top, words in grouped_lines(page):
        if not 127.5 <= top <= 460:
            continue
        line = clean(" ".join(str(word["text"]) for word in sorted(words, key=lambda item: float(item["x0"]))))
        match = re.match(r"^(?P<unit>.+?)\s+(?P<quota>\d+)\s+(?P<male>\d+)\s+(?P<female>\d+)\s+(?P<total>\d+)\s+(?P<filled>\d+)\s+(?P<pctfemale>\d+|-)\s+(?P<adult>\d+|-)$", line)
        if not match:
            raise ValueError(f"Unparsed 2020 bear unit row: {line}")
        data = match.groupdict()
        rows.append(
            biology_row(
                species="Black Bear",
                management_program="Bear permit / harvest-objective",
                management_unit=data["unit"],
                metric="Unit harvest and biological composition",
                metric_unit="count / percent",
                harvest_male=data["male"],
                harvest_female=data["female"],
                harvest_total=data["total"],
                percent_success_or_quota_filled=data["filled"],
                percent_female=missing_to_blank(data["pctfemale"]),
                percent_adult_male_or_female=missing_to_blank(data["adult"]),
                source_file=BEAR_REPORT.name,
                source_page="9",
                source_table_title="Statewide black bear harvest by unit / subunit, Utah 2020",
                source_url=BEAR_URL,
                mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
                notes=f"Permits / quota: {data['quota']}. Adult percentage is adult male.",
            )
        )
    return rows


def parse_cougar_rows(pdf: pdfplumber.PDF) -> list[dict[str, str]]:
    physical: list[str] = []
    for source_page in (12, 13):
        for top, words in grouped_lines(pdf.pages[source_page - 1]):
            if 125 <= top <= 512:
                physical.append(clean(" ".join(str(word["text"]) for word in sorted(words, key=lambda item: float(item["x0"])))))
    joined: list[str] = []
    index = 0
    while index < len(physical):
        line = physical[index]
        if line == "Total 352* 468 363 214 578 49 68 37 14":
            index += 1
            continue
        if line == "Book Cliffs, Rattlesnake Canyon":
            joined.append(line + physical[index + 2] + " " + physical[index + 1])
            index += 3
            continue
        if line == "South Slope, Bonanza/Diamond":
            joined.append(line + " " + physical[index + 2] + " " + physical[index + 1])
            index += 3
            continue
        joined.append(line)
        index += 1

    rows: list[dict[str, str]] = []
    metric = r"(?:\d+|-|Unlimited)"
    pattern = re.compile(
        rf"^(?P<unit>.+?)\s+(?P<le>{metric})\s+(?P<objective>{metric})\s+(?P<male>{metric})\s+(?P<female>{metric})\s+(?P<total>{metric})\s+(?P<lefilled>{metric})\s+(?P<objfilled>{metric})\s+(?P<pctfemale>{metric})\s+(?P<adultfemale>{metric})$"
    )
    for line in joined:
        match = pattern.match(line)
        if not match:
            raise ValueError(f"Unparsed 2020 cougar unit row: {line}")
        data = match.groupdict()
        filled = missing_to_blank(data["lefilled"]) or missing_to_blank(data["objfilled"])
        rows.append(
            biology_row(
                species="Cougar",
                management_program="Limited Entry / Harvest Objective",
                management_unit=data["unit"].replace(" /Nine Mile", "/Nine Mile").replace("Diamond � 24", "Diamond").replace("Mtn/Vernal", "Mtn/Vernal"),
                metric="Unit harvest and biological composition",
                metric_unit="count / percent",
                harvest_male=missing_to_blank(data["male"]),
                harvest_female=missing_to_blank(data["female"]),
                harvest_total=missing_to_blank(data["total"]),
                percent_success_or_quota_filled=filled,
                percent_female=missing_to_blank(data["pctfemale"]),
                percent_adult_male_or_female=missing_to_blank(data["adultfemale"]),
                source_file=COUGAR_REPORT.name,
                source_page="12-13",
                source_table_title="Statewide cougar harvest statistics by hunt unit/subunit, Utah 2020",
                source_url=COUGAR_URL,
                mapping_status="unit_level_source_truth_not_expanded_to_hunt_codes",
                notes=f"Limited-entry permits: {missing_to_blank(data['le']) or 'not applicable'}; harvest objective: {missing_to_blank(data['objective']) or 'not applicable'}. Adult percentage is adult female age 5+.",
            )
        )
    return rows


def build_biology() -> list[dict[str, str]]:
    with pdfplumber.open(BIG_GAME_REPORT) as pdf:
        rows = premium_deer_age_rows()
        rows.extend(parse_deer_ratio_rows(pdf.pages[43], source_page=44, ranges=[(142, 532, "General Season Public Land")]))
        rows.extend(
            parse_deer_ratio_rows(
                pdf.pages[44],
                source_page=45,
                ranges=[
                    (142, 186, "General Season Private Land"),
                    (308, 410, "Limited Entry"),
                    (546, 562, "Premium Limited Entry"),
                ],
            )
        )
        rows.extend(
            parse_age_rows(
                pdf.pages[112],
                species="Elk",
                source_page=113,
                title="Average age of harvested bull elk on limited-entry units, Utah 2011-2020",
            )
        )
        rows.extend(
            parse_age_rows(
                pdf.pages[179],
                species="Moose",
                source_page=180,
                title="Average age of harvested bull moose, by management unit / subunit, 2011-2020",
            )
        )
        rows.extend(
            parse_age_rows(
                pdf.pages[221],
                species="Mountain Goat",
                source_page=222,
                title="Average age of harvested mountain goats, by management unit, Utah 2011-2020",
                goat=True,
            )
        )
    with pdfplumber.open(BEAR_REPORT) as pdf:
        rows.extend(parse_bear_rows(pdf.pages[8]))
    with pdfplumber.open(COUGAR_REPORT) as pdf:
        rows.extend(parse_cougar_rows(pdf))

    keys = [row["deduplication_key"] for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise RuntimeError(f"Duplicate 2020 biological unit keys: {duplicates[:5]}")
    rows.sort(key=lambda row: (row["species"], row["management_program"], row["management_unit"], row["subunit"]))
    return rows


def normalized_name(value: object) -> str:
    text = clean(value).lower().replace("mountains", "mtns").replace("mountain", "mtn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def build_identity_audit(aggregated: list[dict[str, str]]) -> list[dict[str, str]]:
    database_rows = read_csv(DATABASE)
    by_code = defaultdict(list)
    for row in database_rows:
        code = clean(row.get("hunt_code")).upper()
        if code:
            by_code[code].append(row)
    audit: list[dict[str, str]] = []
    for row in aggregated:
        code = clean(row.get("hunt_code")).upper()
        candidates = by_code.get(code, [])
        compatible = [candidate for candidate in candidates if harvest_identity_compatible(row, candidate)]
        if len(compatible) == 1:
            status = "MATCHED_EXACT_CODE_NAME_SPECIES"
            current_name = clean(compatible[0].get("hunt_name"))
        elif candidates:
            status = "CODE_PRESENT_NAME_OR_SPECIES_MISMATCH"
            current_name = " | ".join(sorted({clean(candidate.get("hunt_name")) for candidate in candidates}))
        else:
            status = "NOT_IN_2026_DATABASE"
            current_name = ""
        audit.append(
            {
                "reported_hunt_year": "2020",
                "hunt_code": code,
                "harvest_hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "current_database_hunt_name": current_name,
                "match_status": status,
                "match_keys_used": "hunt_code+hunt_name+species",
                "boundary_id_used": "False",
            }
        )
    return audit


def fmt(value: object, suffix: str = "") -> str:
    text = clean(value)
    return (text + suffix) if text else "-"


def p(text: object, style: ParagraphStyle) -> Paragraph:
    from reportlab.platypus import Paragraph

    return Paragraph(escape(clean(text)), style)


def make_table(data: list[list[object]], widths: list[float], font_size: float = 6.0) -> Table:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B1708")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF9ED"), colors.HexColor("#F1E2C8")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#8D714B")),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return result


def build_pdf(observations: list[dict[str, str]], biology: list[dict[str, str]], audit: dict[str, object]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2020", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor("#2B1708"), alignment=TA_CENTER)
    heading = ParagraphStyle("Heading2020", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#2B1708"), spaceAfter=5)
    body = ParagraphStyle("Body2020", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#24180F"), spaceAfter=6)
    note = ParagraphStyle("Note2020", parent=body, fontSize=6.8, leading=8.2, textColor=colors.HexColor("#5C4A39"))
    cell = ParagraphStyle("Cell2020", parent=body, fontSize=5.5, leading=6.2, spaceAfter=0)

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#F07800"))
        canvas.line(28, 25, landscape(letter)[0] - 28, 25)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#5C4A39"))
        canvas.drawString(30, 14, "Historical 2020 harvest context only - never current quota or direct draw probability.")
        canvas.drawRightString(landscape(letter)[0] - 30, 14, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=landscape(letter),
        leftMargin=0.36 * inch,
        rightMargin=0.36 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.42 * inch,
        title="Utah 2020 Harvest Data Review",
        author="Utah Outfitter and Guide Association (U.O.G.A.)",
    )
    story: list[object] = [
        Spacer(1, 0.18 * inch),
        p("Utah 2020 Harvest Data Review", title_style),
        p("SOURCE-FAITHFUL • CLASSIFIED • UNIT-DEDUPLICATED", ParagraphStyle("sub", parent=heading, alignment=TA_CENTER, textColor=colors.HexColor("#F07800"))),
        p(
            f"This review retains {len(observations):,} official DWR hunt observations representing {audit['unique_hunt_codes']:,} unique hunt codes. "
            f"The extra {audit['adult_youth_shared_code_count']:,} observations are the real Adult/Youth split on shared general-season deer codes; they are not duplicate errors.",
            body,
        ),
        p(
            "Hunt results and management-unit biology are separate tables. Deer uses bucks per 100 does; elk, moose, mountain goat, and premium deer use harvested-age measures where DWR reports them. "
            "Black bear and cougar unit harvest/composition remain separate from public limited-entry big-game success. Missing source values remain blank/dashes.",
            body,
        ),
        p(
            "Lineage note: direct legacy dashboard-PDF URLs were not retained by the earlier cache. The official DWR index URL, local source hash, local cache timestamp, source filename, and page are preserved. "
            "Annual-report direct URLs are preserved. Boundary ID is never used for identity matching.",
            note,
        ),
        p("2020 coverage", heading),
        make_table(
            [
                ["Measure", "Count", "Interpretation"],
                ["Hunt observations", f"{len(observations):,}", "Adult and Youth observations remain separate"],
                ["Unique hunt codes", f"{audit['unique_hunt_codes']:,}", "Canonical hunt-code coverage"],
                ["Core result rows", f"{audit['core_metric_complete_rows']:,}", "Hunters, harvest, and success all reported"],
                ["Source-declared no-data rows", f"{audit['source_no_data_rows']:,}", "Blank is retained; no zero substitution"],
                ["Unit biology rows", f"{len(biology):,}", "One row per management unit/program/metric"],
                ["2026 identity matches", f"{audit['identity_match_counts'].get('MATCHED_EXACT_CODE_NAME_SPECIES', 0):,}", "Exact code + normalized name + species"],
            ],
            [2.0 * inch, 1.0 * inch, 6.6 * inch],
            7.0,
        ),
        PageBreak(),
        p("Unit-level biological context", title_style),
        p("These rows are intentionally not expanded across weapon hunts. That prevents repeated evidence from inflating model counts or visual summaries.", note),
    ]

    by_species: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in biology:
        by_species[row["species"]].append(row)
    for species in sorted(by_species):
        story.append(p(species, heading))
        data: list[list[object]] = [["Program", "Unit / subunit", "Metric", "2020", "2018-20 avg", "Objective", "Harvest", "Composition"]]
        for row in by_species[species]:
            unit = ", ".join(filter(None, [row["management_unit"], row["subunit"]]))
            harvest = row["harvest_total"]
            composition = ""
            if row["percent_female"]:
                composition = f"{row['percent_female']}% female"
            if row["percent_adult_male_or_female"]:
                label = "adult male" if species == "Black Bear" else "adult female 5+"
                composition = (composition + "; " if composition else "") + f"{row['percent_adult_male_or_female']}% {label}"
            data.append(
                [
                    p(row["management_program"], cell),
                    p(unit, cell),
                    p(f"{row['metric']} ({row['metric_unit']})", cell),
                    fmt(row["annual_observed_2020"]),
                    fmt(row["three_year_average_2018_2020"]),
                    fmt(row["management_objective_2020"]),
                    fmt(harvest),
                    p(composition or "-", cell),
                ]
            )
        story.append(make_table(data, [1.25 * inch, 1.65 * inch, 2.0 * inch, 0.55 * inch, 0.68 * inch, 0.78 * inch, 0.52 * inch, 1.55 * inch], 5.3))
        story.append(Spacer(1, 0.12 * inch))

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[(row["program"], row["species"])].append(row)
    for (program, species), rows in sorted(grouped.items()):
        story.append(PageBreak())
        story.append(p(f"{program} — {species}", title_style))
        story.append(p(f"{len(rows):,} source observations. CWMU/public status, participant class, animal class, and weapon are distinct columns in the machine-readable file.", note))
        data: list[list[object]] = [["Code", "Hunt", "Participant", "Animal", "Access", "Weapon", "Permits", "Hunters", "Harvest", "Success", "Days", "Satisfaction"]]
        for row in rows:
            data.append(
                [
                    row["hunt_code"],
                    p(row["hunt_name"], cell),
                    row["participant_class"],
                    row["animal_class"],
                    "CWMU" if row["access_class"] == "CWMU" else "Public",
                    p(row["weapon"] or "-", cell),
                    fmt(row["permits"]),
                    fmt(row["hunters_afield"]),
                    fmt(row["harvest_total"]),
                    fmt(row["percent_success"], "%"),
                    fmt(row["average_days"]),
                    fmt(row["hunter_satisfaction"]),
                ]
            )
        story.append(make_table(data, [0.48 * inch, 2.0 * inch, 0.7 * inch, 0.62 * inch, 0.52 * inch, 0.75 * inch, 0.48 * inch, 0.48 * inch, 0.48 * inch, 0.48 * inch, 0.43 * inch, 0.58 * inch], 4.9))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(str(OUT_PDF))
    if reader.is_encrypted or len(reader.pages) < 10:
        raise RuntimeError("2020 review PDF validation failed")


def main() -> int:
    required = [LONG_SOURCE, AGGREGATED_SOURCE, DATABASE, BIG_GAME_REPORT, BEAR_REPORT, COUGAR_REPORT, FURBEARER_REPORT]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing 2020 review inputs: {missing}")

    observations = build_observations()
    aggregated = [row for row in read_csv(AGGREGATED_SOURCE) if clean(row.get("reported_hunt_year")) == "2020"]
    biology = build_biology()
    identity_rows = build_identity_audit(aggregated)
    identity_counts = Counter(row["match_status"] for row in identity_rows)
    shared_codes = Counter(row["hunt_code"] for row in observations)
    no_data = [row for row in observations if row["parse_status"] == "OFFICIAL_PDF_NO_DATA_ROW"]
    core_complete = [row for row in observations if row["hunters_afield"] and row["harvest_total"] and row["percent_success"]]

    audit: dict[str, object] = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "2020 only",
        "status": "REVIEW_BUILD_NOT_PUBLISHED",
        "observation_rows": len(observations),
        "unique_hunt_codes": len(shared_codes),
        "adult_youth_shared_code_count": sum(count - 1 for count in shared_codes.values() if count > 1),
        "adult_rows": sum(row["participant_class"] == "Adult" for row in observations),
        "youth_rows": sum(row["participant_class"] == "Youth" for row in observations),
        "cwmu_rows": sum(row["access_class"] == "CWMU" for row in observations),
        "public_or_standard_rows": sum(row["access_class"] != "CWMU" for row in observations),
        "core_metric_complete_rows": len(core_complete),
        "source_no_data_rows": len(no_data),
        "source_no_data_hunt_codes": [row["hunt_code"] for row in no_data],
        "biology_rows": len(biology),
        "biology_species_counts": dict(sorted(Counter(row["species"] for row in biology).items())),
        "identity_match_counts": dict(sorted(identity_counts.items())),
        "identity_rule": "exact normalized hunt_code plus normalized hunt_name plus species; boundary_id is never used",
        "source_files": [
            {
                "path": str((RAW_DIR / name).relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(RAW_DIR / name),
                "local_cache_mtime_utc": cache_mtime(RAW_DIR / name),
                "source_url": SOURCE_INDEX_URL,
                "source_url_scope": "official index URL; legacy direct dashboard PDF URL not retained",
            }
            for name in HUNT_PDFS
        ]
        + [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(path),
                "local_cache_mtime_utc": cache_mtime(path),
                "source_url": url,
                "source_url_scope": "official direct annual-report URL verified 2026-09-10",
            }
            for path, url in [(BIG_GAME_REPORT, BIG_GAME_URL), (BEAR_REPORT, BEAR_URL), (COUGAR_REPORT, COUGAR_URL), (FURBEARER_REPORT, FURBEARER_URL)]
        ],
        "furbearer_scope_note": "The 2020-21 furbearer annual report is retained in source inventory but is not merged with calendar-year 2020 big-game hunt-code rows because it uses a cross-year trapping-season schema.",
        "outputs": {
            "observations_csv": str(OUT_OBSERVATIONS.relative_to(ROOT)).replace("\\", "/"),
            "biology_csv": str(OUT_BIOLOGY.relative_to(ROOT)).replace("\\", "/"),
            "identity_audit_csv": str(OUT_IDENTITY_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "review_pdf": str(OUT_PDF.relative_to(ROOT)).replace("\\", "/"),
        },
        "guardrails": [
            "No 2026 permit allotment field is read as harvest truth or changed by this build.",
            "Hunt observations retain Adult and Youth as distinct rows even when DWR reuses the hunt code.",
            "CWMU rows remain separately classified from public/standard rows.",
            "Biological evidence is unit-deduplicated and is not expanded across weapon hunt codes.",
            "Deer uses bucks per 100 does; deer age is used only where DWR explicitly reports premium-unit harvested age.",
            "Annual observed values, DWR 2018-2020 averages, and 2020 objectives remain separate columns.",
            "Missing source values remain blank and are never converted to zero.",
            "Boundary ID is never used for matching.",
            "This review build does not publish, deploy, or update the public Library registry.",
        ],
    }

    write_csv(OUT_OBSERVATIONS, observations, OBSERVATION_FIELDS)
    write_csv(OUT_BIOLOGY, biology, BIOLOGY_FIELDS)
    write_csv(
        OUT_IDENTITY_AUDIT,
        identity_rows,
        ["reported_hunt_year", "hunt_code", "harvest_hunt_name", "species", "current_database_hunt_name", "match_status", "match_keys_used", "boundary_id_used"],
    )
    build_pdf(observations, biology, audit)
    audit["review_pdf_pages"] = len(PdfReader(str(OUT_PDF)).pages)
    audit["review_pdf_sha256"] = sha256(OUT_PDF)
    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
