#!/usr/bin/env python3
"""Build a report-year draw-results extraction from official DWR PDFs.

The official PDF archive is source evidence, not a permit allocation reference.
This extractor emits one source-faithful table row for each official point
level and hunt total, retaining the PDF file and page for every row.  It
intentionally skips point-purchase summary pages because they have no hunt
code and therefore are not public-draw outcome rows.

Run with ``--write`` to create the canonical.  A strict audit records every
Hunt page that could not be parsed instead of fabricating a result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import pymupdf


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "data_truth" / "draw_results_truth" / "validation"

YEAR_CONFIGS = {
    2017: {
        "target_year": 2018,
        "sources": [
            ("official_dwr_archive/big_game/17_big_game_odds_report.pdf", "BIG_GAME", "BONUS"),
            ("official_dwr_archive/big_game_antlerless/17_antlerless_points.pdf", "ANTLERLESS", "PREFERENCE"),
            ("official_dwr_archive/big_game/17_general_deer.pdf", "GENERAL_SEASON_DEER", "PREFERENCE"),
            ("official_dwr_archive/big_game/17_dedicated_hunter_deer.pdf", "DEDICATED_HUNTER", "PREFERENCE"),
            ("official_dwr_archive/big_game/17_lifetime_general_deer.pdf", "LIFETIME_GENERAL_SEASON_DEER", "REFERENCE"),
            ("official_dwr_archive/big_game_antlerless/17_antlerless_youth_points.pdf", "YOUTH_ANTLERLESS", "PREFERENCE"),
            ("official_dwr_archive/big_game/17_youth_any_bull_elk.pdf", "YOUTH_ANY_BULL_ELK", "RANDOM_ONLY"),
            ("official_dwr_archive/big_game/17_youth_general_deer.pdf", "YOUTH_GENERAL_SEASON_DEER", "PREFERENCE"),
            ("official_dwr_archive/turkey/2017_turkey_bonus_points_and_draw_results.pdf", "TURKEY", "BONUS"),
        ],
        "sportsman_file": "official_dwr_archive/big_game/2017_sportsman_odds.pdf",
    },
    2018: {
        "target_year": 2019,
        "sources": [
            ("18_big_game_odds_report.pdf", "BIG_GAME", "BONUS"),
            ("18_antlerless_drawing_odds_report.pdf", "ANTLERLESS", "PREFERENCE"),
            ("18_general_deer.pdf", "GENERAL_SEASON_DEER", "PREFERENCE"),
            ("18_dedicated_hunter_deer.pdf", "DEDICATED_HUNTER", "PREFERENCE"),
            ("18_lifetime_general_deer.pdf", "LIFETIME_GENERAL_SEASON_DEER", "REFERENCE"),
            ("18_youth_antlerless_drawing_odds_report.pdf", "YOUTH_ANTLERLESS", "PREFERENCE"),
            ("18_youth_any_bull_elk.pdf", "YOUTH_ANY_BULL_ELK", "RANDOM_ONLY"),
            ("18_youth_general_deer.pdf", "YOUTH_GENERAL_SEASON_DEER", "PREFERENCE"),
        ],
        "sportsman_file": "18-19_sportsman_odds.pdf",
    },
    2020: {
        "target_year": 2021,
        "sources": [
            ("20_bg-odds.pdf", "BIG_GAME", "BONUS"),
            ("20_antlerless_drawing_odds_report.pdf", "ANTLERLESS", "PREFERENCE"),
            ("20_deer_odds.pdf", "GENERAL_SEASON_DEER", "PREFERENCE"),
            ("20_dh_odds.pdf", "DEDICATED_HUNTER", "PREFERENCE"),
            ("20_lifetime_deer.pdf", "LIFETIME_GENERAL_SEASON_DEER", "REFERENCE"),
            ("20_youth_antlerless_drawing_odds_report.pdf", "YOUTH_ANTLERLESS", "PREFERENCE"),
            ("20_youth_bull_elk.pdf", "YOUTH_ANY_BULL_ELK", "RANDOM_ONLY"),
            ("20_youth_deer.pdf", "YOUTH_GENERAL_SEASON_DEER", "PREFERENCE"),
            ("20_youth_dh_odds.pdf", "YOUTH_DEDICATED_HUNTER", "PREFERENCE"),
            ("5213601e__turkey_2020_turkey_bonus_points_draw_results.pdf", "TURKEY", "BONUS"),
            ("68991b97__turkey_2020_youth_turkey_draw_results.pdf", "YOUTH_TURKEY", "BONUS"),
            ("97ffae94__black_bear_20_drawing_odds.pdf", "BLACK_BEAR", "BONUS"),
        ],
        "sportsman_file": "20-21_sportsman_odds.pdf",
    },
}

REPORT_YEAR = 2020
MODEL_TARGET_YEAR = 2021
PDF_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / str(REPORT_YEAR) / "pdf" / "draw_odds"
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
SUMMARY = VALIDATION / "draw_results_2020_for_2021_pdf_extraction_summary.json"
UNPARSED = VALIDATION / "draw_results_2020_for_2021_pdf_unparsed_hunt_pages.csv"
SOURCE_CONFIGS = YEAR_CONFIGS[REPORT_YEAR]["sources"]
SPORTSMAN_FILE = YEAR_CONFIGS[REPORT_YEAR]["sportsman_file"]


def configure_report_year(report_year: int) -> None:
    """Switch all lineage paths and labels together for a supported report year."""
    global REPORT_YEAR, MODEL_TARGET_YEAR, PDF_ROOT, CANONICAL, SUMMARY, UNPARSED, SOURCE_CONFIGS, SPORTSMAN_FILE
    config = YEAR_CONFIGS[report_year]
    REPORT_YEAR = report_year
    MODEL_TARGET_YEAR = config["target_year"]
    PDF_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / str(report_year) / "pdf" / "draw_odds"
    pair = f"{report_year}_for_{MODEL_TARGET_YEAR}"
    CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / f"draw_results_{pair}_canonical_yearly_draw_results.csv"
    SUMMARY = VALIDATION / f"draw_results_{pair}_pdf_extraction_summary.json"
    UNPARSED = VALIDATION / f"draw_results_{pair}_pdf_unparsed_hunt_pages.csv"
    SOURCE_CONFIGS = config["sources"]
    SPORTSMAN_FILE = config["sportsman_file"]


HEADER = [
    "actual_draw_year", "model_target_year", "boundary_id", "hunt_code", "hunt_name",
    "raw_hunt_name", "species", "sex", "sex_type", "hunt_type", "weapon", "season",
    "draw_design", "hunt_draw_class", "hunt_class", "points", "residency", "row_type",
    "record_type", "resident_eligible_applicants", "resident_bonus_permits",
    "resident_regular_permits", "resident_total_permits", "resident_success_ratio",
    "resident_p_draw", "resident_p_draw_percent", "nonresident_eligible_applicants",
    "nonresident_bonus_permits", "nonresident_regular_permits", "nonresident_total_permits",
    "nonresident_success_ratio", "nonresident_p_draw", "nonresident_p_draw_percent",
    "total_eligible_applicants", "total_bonus_permits", "total_regular_permits",
    "total_permits", "total_success_ratio", "total_p_draw", "total_p_draw_percent",
    "eligible_applicants", "bonus_permits", "regular_permits", "success_ratio", "p_draw",
    "p_draw_percent", "successful_applicants", "unsuccessful_applicants", "source_scope",
    "source_namespace", "draw_source_namespace", "source_file", "draw_source_file",
    "source_path", "source_pdf", "pdf_page", "official_page", "page_kind", "source_dataset",
    "extraction_status", "parse_method", "qa_status", "qa_notes", "algorithm_status", "notes",
    "source_residencies", "source_row_count", "collapse_conflict_count", "candidate_promotion_status",
    "unit", "draw_system_type", "draw_pool", "draw_system_type_source",
    "draw_system_type_confidence", "metric_scope",
]

CODE_RE = re.compile(r"\b([A-Z]{2}\d{4})\b")
HUNT_BLOCK_RE = re.compile(r"Hunt:\s*([A-Z]{2}\d{4})\s+(.+?)(?:\s+Page\s+\d+)?\s*$", re.I | re.S)
RATIO_RE = re.compile(r"1\s*in\s*([\d.]+)", re.I)
SPORTSMAN_RE = re.compile(
    r"^(?P<code>[A-Z]{2}\d{4})\s+(?P<name>.+?)\s+"
    r"(?P<successful_resident>[\d,]+)\s+(?P<successful_nonresident>[\d,]+)\s+"
    r"(?P<unsuccessful_resident>[\d,]+)\s+(?P<unsuccessful_nonresident>[\d,]+)\s+"
    r"(?P<total_applications>[\d,]+)\s+(?P<resident_quota>N/A|[\d,]+)\s+"
    r"(?P<nonresident_quota>N/A|[\d,]+)\s+(?P<total_quota>[\d,]+)\s+"
    r"(?P<resident_success>N/A|1\s+in\s+[\d,.]+)\s+(?P<nonresident_success>N/A|1\s+in\s+[\d,.]+)\s*$",
    re.I,
)


def clean(value: object) -> str:
    return "" if value is None else " ".join(str(value).strip().split())


def number(value: object) -> int | None:
    text = clean(value).replace(",", "")
    if not text or text.upper() == "N/A":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def ratio_probability(value: object) -> tuple[str, str]:
    match = RATIO_RE.search(clean(value))
    if not match:
        return "", ""
    denominator = float(match.group(1))
    if denominator <= 0:
        return "", ""
    probability = 1.0 / denominator
    return f"{probability:.10f}".rstrip("0").rstrip("."), f"{probability * 100:.8f}".rstrip("0").rstrip(".")


def combine_total(left: object, right: object) -> str:
    values = [number(left), number(right)]
    return "" if all(value is None for value in values) else str(sum(value or 0 for value in values))


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def species_for(code: str, name: str) -> str:
    text = f"{code} {name}".upper()
    if code.startswith("BI") or "BISON" in text:
        return "Bison"
    if code.startswith("BR") or "BEAR" in text:
        return "Black Bear"
    if code.startswith("CG") or "COUGAR" in text:
        return "Cougar"
    if code.startswith("TK") or "TURKEY" in text:
        return "Turkey"
    if code.startswith("GO") or "GOAT" in text:
        return "Mountain Goat"
    if code.startswith("MB") or "MOOSE" in text:
        return "Moose"
    if code.startswith("DS") or "DESERT BIGHORN" in text:
        return "Desert Bighorn Sheep"
    if code.startswith("RS") or "ROCKY" in text and "SHEEP" in text:
        return "Rocky Mountain Bighorn Sheep"
    if code.startswith(("PB", "PD")) or "PRONGHORN" in text:
        return "Pronghorn"
    if code.startswith(("EB", "EA")) or "ELK" in text:
        return "Elk"
    if code.startswith(("DB", "DA")) or "DEER" in text:
        return "Deer"
    return "Unknown"


def sex_metadata_for(code: str, name: str) -> tuple[str, str]:
    """Return a sex label only when the official code or hunt name says so."""
    text = f"{code} {name}".upper()
    if code.startswith(("DA", "PD")) or "DOE" in text:
        return "Female", "Doe"
    if code.startswith("EA") or "COW" in text or "ANTLERLESS" in text:
        return "Female", "Antlerless" if "ANTLERLESS" in text else "Cow"
    if code.startswith(("DB", "PB")) or "BUCK" in text:
        return "Male", "Buck"
    if code.startswith("EB") or "BULL" in text:
        return "Male", "Bull"
    if "EWE" in text:
        return "Female", "Ewe"
    if "RAM" in text:
        return "Male", "Ram"
    if "BEARDED" in text:
        return "Bearded", "Bearded"
    if code.startswith("GO"):
        return "Either Sex", "Either Sex"
    return "", ""


def classify(scope: str, code: str, name: str) -> tuple[str, str, str, str]:
    text = f"{code} {name}".upper()
    if scope == "SPORTSMAN":
        return "SPORTSMAN_PERMIT", "SPORTSMAN", "SPORTSMAN_RANDOM_ONLY", "SPORTSMAN_RANDOM_ONLY"
    if scope == "LIFETIME_GENERAL_SEASON_DEER":
        return "LIFETIME", "General Season", "REFERENCE_LIFETIME_PERMIT_HOLDER", "EXCLUDED_NOT_PREDICTIVE_DRAW"
    if scope == "GENERAL_SEASON_DEER":
        return "GENERAL_SEASON_DEER", "General Season", "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "MODELED_PREFERENCE"
    if scope == "DEDICATED_HUNTER":
        return "DEDICATED_HUNTER_DEER", "Dedicated Hunter", "PREFERENCE_DEDICATED_HUNTER_DEER", "MODELED_PREFERENCE"
    if scope == "YOUTH_GENERAL_SEASON_DEER":
        return "YOUTH_GENERAL_SEASON_DEER", "Youth", "YOUTH_GENERAL_DEER_RESERVE", "MODELED_PREFERENCE"
    if scope == "YOUTH_DEDICATED_HUNTER":
        return "YOUTH_DEDICATED_HUNTER_DEER", "Dedicated Hunter Youth", "PREFERENCE_DEDICATED_HUNTER_DEER", "MODELED_PREFERENCE"
    if scope == "YOUTH_ANY_BULL_ELK":
        return "YOUTH_GENERAL_ANY_BULL_ELK", "Youth", "YOUTH_GENERAL_ANY_BULL_ELK", "MODELED_RANDOM_ONLY"
    if scope == "YOUTH_TURKEY":
        return "YOUTH_TURKEY", "Youth Turkey", "YOUTH_TURKEY_SET_ASIDE", "MODELED_BONUS"
    if scope == "TURKEY":
        return "LIMITED_ENTRY_TURKEY", "Turkey", "BONUS_TURKEY", "MODELED_BONUS"
    if scope == "BLACK_BEAR":
        if "PURSUIT" in text:
            return "RESTRICTED_BEAR_PURSUIT", "Bear Pursuit", "RESTRICTED_BEAR_PURSUIT", "MODELED_BONUS"
        return "LIMITED_ENTRY_BEAR_HUNT", "Bear", "LIMITED_ENTRY_BEAR_HUNT", "MODELED_BONUS"
    if scope in {"ANTLERLESS", "YOUTH_ANTLERLESS"}:
        if "CWMU" in text:
            return "CWMU_ANTLERLESS", "CWMU", "BONUS_CWMU_BIG_GAME", "MODELED_BONUS"
        prefix = "YOUTH_" if scope == "YOUTH_ANTLERLESS" else ""
        if code.startswith(("DA", "DB")):
            return f"{prefix}ANTLERLESS_DEER", "Antlerless", "PREFERENCE_ANTLERLESS_DEER", "MODELED_PREFERENCE"
        if code.startswith(("EA", "EB")):
            return f"{prefix}ANTLERLESS_ELK", "Antlerless", "PREFERENCE_ANTLERLESS_ELK", "MODELED_PREFERENCE"
        return f"{prefix}DOE_PRONGHORN", "Antlerless", "PREFERENCE_DOE_PRONGHORN", "MODELED_PREFERENCE"
    if "CWMU" in text:
        return "CWMU_BIG_GAME", "CWMU", "BONUS_CWMU_BIG_GAME", "MODELED_BONUS"
    if code.startswith(("BI", "GO", "MB", "DS", "RS")):
        return "ONCE_IN_A_LIFETIME", "O.I.L.", "BONUS_OIL_BIG_GAME", "MODELED_BONUS"
    if code.startswith(("DB", "EB", "PB")):
        return "LIMITED_ENTRY", "L.E.", "BONUS_LE_BIG_GAME", "MODELED_BONUS"
    return "UNKNOWN", "", "UNKNOWN_TARGET", "UNKNOWN_TARGET_NEEDS_REVIEW"


def metadata_from_page(page: pymupdf.Page, scope: str) -> tuple[str, str] | None:
    blocks = page.get_text("blocks")
    for block in blocks:
        match = HUNT_BLOCK_RE.search(block[4])
        if match:
            return match.group(1).upper(), clean(match.group(2))

    # The 2018 antlerless PDFs place ``Hunt:`` and the code in one block but
    # print the hunt name as the separate first block. Retain that exact
    # geometry rather than treating the page as a missing result.
    for _, hunt_y, _, _, block_text, *_ in blocks:
        if "HUNT:" not in block_text.upper():
            continue
        codes = CODE_RE.findall(block_text)
        if len(set(codes)) != 1:
            continue
        candidates = []
        for _, candidate_y, _, _, candidate_text, *_ in blocks:
            candidate = clean(candidate_text)
            upper = candidate.upper()
            if (
                candidate
                and candidate_y <= hunt_y
                and "HUNT:" not in upper
                and "UTAH DIVISION" not in upper
                and "DRAW" not in upper
                and "PAGE" not in upper
            ):
                candidates.append((candidate_y, candidate))
        if candidates:
            return codes[0].upper(), sorted(candidates)[0][1]

    text = page.get_text("text", sort=True)
    codes = CODE_RE.findall(text)
    if len(set(codes)) != 1:
        return None
    code = codes[0].upper()
    if scope not in {"TURKEY", "YOUTH_TURKEY", "BLACK_BEAR"}:
        return None
    candidates = []
    for x0, y0, _, _, block_text, *_ in blocks:
        text = clean(block_text)
        upper = text.upper()
        if y0 < 170 and x0 > 70 and text and "HUNT" not in upper and "DRAW" not in upper and "PAGE" not in upper:
            candidates.append((y0, text))
    return code, candidates[0][1] if candidates else code


def normalized_cells(table_row: list[object]) -> list[str]:
    cells = [clean(cell).replace("N /A", "N/A") for cell in table_row if clean(cell)]
    return cells


def build_row(
    *,
    code: str,
    name: str,
    scope: str,
    source_file: str,
    page_number: int,
    cells: list[str],
    record_type: str,
) -> dict[str, str]:
    if record_type == "point_level_draw_result":
        left, right = cells[:6], cells[6:12]
        points = left[0]
        r_apps, r_bonus, r_regular, r_total, r_ratio = left[1:]
        n_apps, n_bonus, n_regular, n_total, n_ratio = right[1:]
    else:
        left, right = cells[1:6], cells[6:11]
        points = ""
        r_apps, r_bonus, r_regular, r_total, r_ratio = left
        n_apps, n_bonus, n_regular, n_total, n_ratio = right
    hunt_class, hunt_type, draw_design, algorithm_status = classify(scope, code, name)
    r_probability, r_percent = ratio_probability(r_ratio)
    n_probability, n_percent = ratio_probability(n_ratio)
    source_path = PDF_ROOT / source_file
    sex, sex_type = sex_metadata_for(code, name)
    row = {column: "" for column in HEADER}
    row.update(
        {
            "actual_draw_year": str(REPORT_YEAR), "model_target_year": str(MODEL_TARGET_YEAR), "hunt_code": code,
            "hunt_name": name, "raw_hunt_name": name, "species": species_for(code, name),
            "sex": sex, "sex_type": sex_type, "hunt_type": hunt_type, "draw_design": draw_design, "hunt_draw_class": hunt_class,
            "hunt_class": hunt_class, "points": points, "row_type": "POINT_ROW" if points else "HUNT_TOTAL",
            "record_type": record_type, "resident_eligible_applicants": r_apps,
            "resident_bonus_permits": r_bonus, "resident_regular_permits": r_regular,
            "resident_total_permits": r_total, "resident_success_ratio": r_ratio,
            "resident_p_draw": r_probability, "resident_p_draw_percent": r_percent,
            "nonresident_eligible_applicants": n_apps, "nonresident_bonus_permits": n_bonus,
            "nonresident_regular_permits": n_regular, "nonresident_total_permits": n_total,
            "nonresident_success_ratio": n_ratio, "nonresident_p_draw": n_probability,
            "nonresident_p_draw_percent": n_percent, "total_eligible_applicants": combine_total(r_apps, n_apps),
            "total_bonus_permits": combine_total(r_bonus, n_bonus), "total_regular_permits": combine_total(r_regular, n_regular),
            "total_permits": combine_total(r_total, n_total), "eligible_applicants": combine_total(r_apps, n_apps),
            "bonus_permits": combine_total(r_bonus, n_bonus), "regular_permits": combine_total(r_regular, n_regular),
            "successful_applicants": combine_total(r_total, n_total),
            "unsuccessful_applicants": str(max(0, (number(r_apps) or 0) + (number(n_apps) or 0) - (number(r_total) or 0) - (number(n_total) or 0))),
            "source_scope": scope, "source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{REPORT_YEAR}",
            "draw_source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{REPORT_YEAR}", "source_file": source_file,
            "draw_source_file": source_file, "source_path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "source_pdf": source_file, "pdf_page": str(page_number), "official_page": str(page_number),
            "page_kind": "HUNT_PAGE", "source_dataset": f"DWR_{REPORT_YEAR}_DRAW_RESULTS_PDF",
            "extraction_status": "OK", "parse_method": "PYMUPDF_FIND_TABLES",
            "qa_status": "SOURCE_TABLE_PARSED", "algorithm_status": algorithm_status,
            "source_residencies": "nonresident; resident", "source_row_count": "1",
            "collapse_conflict_count": "0", "candidate_promotion_status": "OFFICIAL_SOURCE_PARSED",
            "draw_system_type": draw_design, "draw_pool": hunt_class,
            "draw_system_type_source": f"{REPORT_YEAR}_OFFICIAL_PDF_SOURCE_SCOPE", "draw_system_type_confidence": "high",
            "metric_scope": "total",
        }
    )
    return row


def extract_hunt_tables() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    rows: list[dict[str, str]] = []
    unparsed: list[dict[str, str]] = []
    source_stats: dict[str, dict[str, int]] = {}
    for source_file, scope, _ in SOURCE_CONFIGS:
        path = PDF_ROOT / source_file
        if not path.exists():
            raise FileNotFoundError(path)
        document = pymupdf.open(path)
        stats = Counter(pages=len(document))
        for page_number, page in enumerate(document, start=1):
            metadata = metadata_from_page(page, scope)
            if metadata is None:
                continue
            stats["hunt_pages"] += 1
            code, name = metadata
            tables = page.find_tables().tables
            if len(tables) != 1:
                unparsed.append({"source_file": source_file, "pdf_page": str(page_number), "hunt_code": code, "hunt_name": name, "reason": f"expected_one_table_found_{len(tables)}"})
                continue
            parsed_on_page = 0
            for table_row in tables[0].extract():
                cells = normalized_cells(table_row)
                if len(cells) == 12 and cells[0].isdigit() and cells[6].isdigit():
                    rows.append(build_row(code=code, name=name, scope=scope, source_file=source_file, page_number=page_number, cells=cells, record_type="point_level_draw_result"))
                    parsed_on_page += 1
                elif len(cells) == 12 and cells[0].lower() == "totals" and cells[6].lower() == "totals":
                    rows.append(build_row(code=code, name=name, scope=scope, source_file=source_file, page_number=page_number, cells=cells, record_type="hunt_total_draw_result"))
                    parsed_on_page += 1
            if not parsed_on_page:
                unparsed.append({"source_file": source_file, "pdf_page": str(page_number), "hunt_code": code, "hunt_name": name, "reason": "no_standard_12_column_draw_rows"})
            else:
                stats["parsed_hunt_pages"] += 1
                stats["rows"] += parsed_on_page
        source_stats[source_file] = dict(stats)
    return rows, unparsed, source_stats


def extract_sportsman() -> list[dict[str, str]]:
    path = PDF_ROOT / SPORTSMAN_FILE
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text(x_tolerance=1, y_tolerance=3) or ""
    merged = []
    pending = ""
    for line in text.splitlines():
        line = clean(line)
        if pending:
            line = f"{pending} {line}"
            pending = ""
        if re.match(r"^[A-Z]{2}\d{4}\s+Sportsman\s+(?:Rocky Mtn|Desert Bighorn)\s*$", line, re.I):
            pending = line
            continue
        merged.append(line)
    rows = []
    for line in merged:
        match = SPORTSMAN_RE.match(line)
        if not match:
            continue
        data = match.groupdict()
        code, name = data["code"].upper(), clean(data["name"])
        row = {column: "" for column in HEADER}
        resident_apps = number(data["successful_resident"]) + number(data["unsuccessful_resident"])
        total_permits = number(data["total_quota"])
        hunt_class, hunt_type, draw_design, algorithm_status = classify("SPORTSMAN", code, name)
        sex, sex_type = sex_metadata_for(code, name)
        row.update({
            "actual_draw_year": str(REPORT_YEAR), "model_target_year": str(MODEL_TARGET_YEAR), "hunt_code": code, "hunt_name": name,
            "raw_hunt_name": name, "species": species_for(code, name), "hunt_type": hunt_type,
            "sex": sex, "sex_type": sex_type,
            "draw_design": draw_design, "hunt_draw_class": hunt_class, "hunt_class": hunt_class,
            "row_type": "HUNT_TOTAL", "record_type": "sportsman_total_draw_result",
            "resident_eligible_applicants": str(resident_apps), "resident_total_permits": str(total_permits),
            "resident_success_ratio": data["resident_success"], "resident_p_draw": ratio_probability(data["resident_success"])[0],
            "resident_p_draw_percent": ratio_probability(data["resident_success"])[1], "total_eligible_applicants": data["total_applications"],
            "total_permits": str(total_permits), "eligible_applicants": data["total_applications"], "successful_applicants": str(total_permits),
            "unsuccessful_applicants": str(max(0, number(data["total_applications"]) - total_permits)), "source_scope": "SPORTSMAN",
            "source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{REPORT_YEAR}", "draw_source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{REPORT_YEAR}",
            "source_file": SPORTSMAN_FILE, "draw_source_file": SPORTSMAN_FILE,
            "source_path": str(path.relative_to(ROOT)).replace("\\", "/"), "source_pdf": SPORTSMAN_FILE,
            "pdf_page": "1", "official_page": "1", "page_kind": "SPORTSMAN_TABLE", "source_dataset": f"DWR_{REPORT_YEAR}_SPORTSMAN_DRAW_RESULTS_PDF",
            "extraction_status": "OK", "parse_method": "PDFPLUMBER_LINEAR_TEXT", "qa_status": "SOURCE_TABLE_PARSED",
            "algorithm_status": algorithm_status, "source_residencies": "resident", "source_row_count": "1", "collapse_conflict_count": "0",
            "candidate_promotion_status": "OFFICIAL_SOURCE_PARSED", "draw_system_type": draw_design, "draw_pool": hunt_class,
            "draw_system_type_source": f"{REPORT_YEAR}_OFFICIAL_PDF_SOURCE_SCOPE", "draw_system_type_confidence": "high", "metric_scope": "total",
        })
        rows.append(row)
    if len(rows) != 11:
        raise ValueError(f"Expected 11 Sportsman rows, parsed {len(rows)}")
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-year", type=int, choices=sorted(YEAR_CONFIGS), default=2020, help="DWR report-generation year to extract.")
    parser.add_argument("--write", action="store_true", help="Write the canonical after strict parsing succeeds.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Write the extraction, summary, and unparsed-page audit to this directory. "
            "Use this for a historical audit without changing canonical or validation paths."
        ),
    )
    args = parser.parse_args()
    configure_report_year(args.report_year)
    if args.output_dir:
        global CANONICAL, SUMMARY, UNPARSED
        pair = f"{REPORT_YEAR}_for_{MODEL_TARGET_YEAR}"
        CANONICAL = args.output_dir / f"draw_results_{pair}_official_pdf_reconstructed.csv"
        SUMMARY = args.output_dir / f"draw_results_{pair}_official_pdf_reconstruction_summary.json"
        UNPARSED = args.output_dir / f"draw_results_{pair}_official_pdf_unparsed_hunt_pages.csv"
    rows, unparsed, source_stats = extract_hunt_tables()
    sportsman = extract_sportsman()
    rows.extend(sportsman)
    rows.sort(key=lambda row: (row["source_file"], int(row["pdf_page"] or 0), row["hunt_code"], row["record_type"], -int(row["points"] or -1)))
    duplicate_keys = Counter((row["hunt_code"], row["source_file"], row["pdf_page"], row["record_type"], row["points"]) for row in rows)
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    summary = {
        "artifact": f"draw_results_{REPORT_YEAR}_for_{MODEL_TARGET_YEAR}_canonical_yearly_pdf_extraction",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write": args.write,
        "source_pdf_count": len(SOURCE_CONFIGS) + 1,
        "source_sha256": {source_file: source_hash(PDF_ROOT / source_file) for source_file, _, _ in SOURCE_CONFIGS} | {SPORTSMAN_FILE: source_hash(PDF_ROOT / SPORTSMAN_FILE)},
        "source_stats": source_stats,
        "rows": len(rows),
        "point_rows": sum(row["record_type"] == "point_level_draw_result" for row in rows),
        "hunt_total_rows": sum(row["record_type"] == "hunt_total_draw_result" for row in rows),
        "sportsman_rows": len(sportsman),
        "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
        "unparsed_hunt_page_count": len(unparsed),
        "duplicate_source_row_key_count": duplicate_count,
        "canonical_path": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "status": "PASS" if not unparsed and not duplicate_count else "BLOCKED",
    }
    VALIDATION.mkdir(parents=True, exist_ok=True)
    write_csv(UNPARSED, unparsed, ["source_file", "pdf_page", "hunt_code", "hunt_name", "reason"])
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if unparsed or duplicate_count:
        print(json.dumps(summary, indent=2))
        return 1
    if args.write:
        write_csv(CANONICAL, rows, HEADER)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
