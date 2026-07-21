from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]

PRIOR_GUIDEBOOK_PDF = ROOT / "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
HUNT_MASTER = ROOT / "processed_data/hunt_master_enriched.csv"
POINT_LADDER = ROOT / "processed_data/point_ladder_view.csv"
DRAW_REALITY = ROOT / "processed_data/draw_reality_engine.csv"
PREDICTIVE = ROOT / "processed_data/draw_reality_engine_predictive_v2.csv"
CURRENT_GUIDEBOOK_RECON = ROOT / "data_truth/regulations_truth/normalized/2026_turkey_guidebook_hunt_code_name_reconciliation.csv"

OUT_DIR = ROOT / "data_truth/regulations_truth/normalized"
REPORT_DIR = ROOT / "processed_data"

PRIOR_TEXT_LINES_CSV = OUT_DIR / "2025_turkey_guidebook_text_lines.csv"
PRIOR_NUMBER_TOKENS_CSV = OUT_DIR / "2025_turkey_guidebook_number_tokens.csv"
PRIOR_EXPECTED_TEXT_CHECKS_CSV = OUT_DIR / "2025_turkey_guidebook_expected_text_checks.csv"
PRIOR_HUNT_CODE_RECONCILIATION_CSV = OUT_DIR / "2025_turkey_guidebook_hunt_code_name_reconciliation.csv"
FULL_RECONCILIATION_CSV = OUT_DIR / "2026_turkey_full_hunt_code_reconciliation.csv"

PRIOR_SUMMARY = REPORT_DIR / "2025_turkey_guidebook_audit.json"
PRIOR_REPORT_MD = REPORT_DIR / "2025_turkey_guidebook_audit.md"
FULL_SUMMARY = REPORT_DIR / "2026_turkey_full_hunt_code_reconciliation_summary.json"
FULL_REPORT_MD = REPORT_DIR / "2026_turkey_full_hunt_code_reconciliation.md"
PROMOTION_DETAIL = REPORT_DIR / "2026_turkey_predictive_v2_reference_promotion.csv"
PROMOTION_SUMMARY = REPORT_DIR / "2026_turkey_predictive_v2_reference_promotion_summary.json"

PRIOR_SOURCE_PATH = "pipeline/RAW/hunt_unit_database/2024/pdf/regulations/2024_REGULATIONS__UPLAND_TURKEY.pdf"
PRIOR_EXPECTED_SHA256 = "5d6af291900a3c790c1673ad0e520d38d2ddc0ddbb2392f67426b1a45bc2e8a3"
PRIOR_EXPECTED_SIZE_BYTES = 7_607_742
PRIOR_EXPECTED_PDF_PAGES = 63

REFERENCE_MODEL_VERSION = "turkey_guidebook_reference_v1.0.0"
REFERENCE_RULE_VERSION = "utah_turkey_code_resolution_v1.0.0"
DATA_CUTOFF_DATE = "2026-05-24"

CODE_RE = re.compile(r"\b(?:TK\d{4}|TKY)\b")
DATE_TOKEN_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+"
    r"\d{1,2}(?:\s*[-]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+)?\d{1,2})?"
    r"(?:,\s*\d{4})?\b",
    re.IGNORECASE,
)
CODE_CITATION_RE = re.compile(r"\b(?:R657-\d+[a-z]?(?:-\d+)?|23A-\d+-\d+|76-\d+-\d+|50 CFR \d+\.\d+)\b")
NUMBER_TOKEN_RE = re.compile(r"\$?\b\d+(?:,\d{3})*(?:\.\d+)?%?\b|\b\d{1,2}:\d{2}\b|\bTK\d{4}\b|\bTKY\b")


@dataclass(frozen=True)
class ExpectedTextCheck:
    check_id: str
    printed_page: str
    expected_text: str
    source_note: str


@dataclass(frozen=True)
class PriorGuidebookCode:
    code: str
    guidebook_name: str
    code_type: str
    guidebook_context: str


PRIOR_EXPECTED_TEXT_CHECKS = [
    ExpectedTextCheck("guidebook_title", "3", "2024-25 UTAH UPLAND GAME AND TURKEY GUIDEBOOK", "title"),
    ExpectedTextCheck("turkey_drawing_period", "3", "CWMU in 2025, the application period runs from", "what's new"),
    ExpectedTextCheck("fall_management_harvest", "4", "Fall turkey management harvest hunt", "what's new"),
    ExpectedTextCheck("turkey_depredation_permits", "5", "Turkey depredation permits", "what's new"),
    ExpectedTextCheck("air_rifles_allowed", "5", "Air rifes allowed for specifc hunts", "what's new"),
    ExpectedTextCheck("fall_2024_permits_available", "6", "Fall 2024 management harvest permits available", "key dates"),
    ExpectedTextCheck("limited_entry_applications_available", "6", "Limited-entry applications Dec. 12, 2024", "key dates"),
    ExpectedTextCheck("spring_limited_dates", "6", "April 12-24, 2025", "season dates"),
    ExpectedTextCheck("spring_youth_dates", "6", "April 25-27, 2025", "season dates"),
    ExpectedTextCheck("spring_general_dates", "6", "April 28-May 31, 2025", "season dates"),
    ExpectedTextCheck("turkey_permit_types", "16", "Limited-entry permits (spring)", "turkey permits"),
    ExpectedTextCheck("general_season_permits", "16", "General-season permits (spring)", "turkey permits"),
    ExpectedTextCheck("conservation_permits", "16", "Conservation permits (spring)", "turkey permits"),
    ExpectedTextCheck("cwmu_permits", "16", "Cooperative Wildlife Management Unit", "turkey permits"),
    ExpectedTextCheck("management_harvest_permits", "16", "Management harvest permits (fall)", "turkey permits"),
    ExpectedTextCheck("one_spring_permit", "16", "Reminder: You may obtain one permit for", "turkey permits"),
    ExpectedTextCheck("fall_three_permits", "16", "An individual may obtain up to three fall man-", "turkey permits"),
    ExpectedTextCheck("limited_entry_youth_set_aside", "16", "Fifteen percent of Utah's turkey limited-entry", "youth turkey"),
    ExpectedTextCheck("bonus_point_tky", "19", "(TKY) on the application", "bonus point code"),
    ExpectedTextCheck("fall_management_regions", "20", "Central Region", "fall management regions"),
    ExpectedTextCheck("fall_northern_region", "20", "Northern Region", "fall management regions"),
    ExpectedTextCheck("fall_southeastern_region", "20", "Southeastern Region", "fall management regions"),
    ExpectedTextCheck("spring_general_sale", "20", "Spring general-season permits will be", "spring general"),
    ExpectedTextCheck("jan_8_results", "21", "January 8: Drawing results available", "important dates"),
    ExpectedTextCheck("march_6_remaining", "22", "March 6: Spring general-season", "important dates"),
    ExpectedTextCheck("conservation_section", "22", "Turkey conservation permits are available", "conservation permits"),
    ExpectedTextCheck("cwmu_section", "22", "Management Unit permits", "CWMU permits"),
    ExpectedTextCheck("fall_hunt_table", "38", "Wild turkey (Fall management harvest hunts)", "hunt tables"),
    ExpectedTextCheck("limited_entry_hunt_table", "39", "Wild turkey (Limited-entry hunts)", "hunt tables"),
    ExpectedTextCheck("limited_entry_codes", "39", "Areas open: Central (TK1003), Northeastern", "printed hunt codes"),
    ExpectedTextCheck("southern_limited_code", "39", "(TK1006) and Southern (TK1007)", "printed hunt codes"),
    ExpectedTextCheck("cwmu_codes", "39", "Pahvant Ensign (TK1018) and East Zion (TK1021)", "printed CWMU codes"),
    ExpectedTextCheck("spring_general_hunt_table", "39", "Wild turkey (Spring general-season hunts)", "hunt tables"),
    ExpectedTextCheck("statewide_general_area", "39", "Areas open: Statewide", "spring general"),
    ExpectedTextCheck("species_identification", "49", "The wild turkey", "species identification"),
]

PRIOR_GUIDEBOOK_CODES = [
    PriorGuidebookCode("TK1003", "Central", "hunt_code", "limited-entry area"),
    PriorGuidebookCode("TK1004", "Northeastern", "hunt_code", "limited-entry area"),
    PriorGuidebookCode("TK1005", "Northern", "hunt_code", "limited-entry area"),
    PriorGuidebookCode("TK1006", "Southeastern", "hunt_code", "limited-entry area"),
    PriorGuidebookCode("TK1007", "Southern", "hunt_code", "limited-entry area"),
    PriorGuidebookCode("TK1018", "Pahvant Ensign", "hunt_code", "CWMU area"),
    PriorGuidebookCode("TK1021", "East Zion", "hunt_code", "CWMU area"),
    PriorGuidebookCode("TKY", "Turkey bonus point", "bonus_point_code", "bonus point application code"),
]

GUIDEBOOK_BASIS_BY_CODE = {
    "TK0001": "Current database/hunt-master special statewide/sportsman turkey permit reference; not printed as a turkey guidebook hunt-table code.",
    "TK1000": "Spring general-season hunt is described as statewide in both 2024-25 and 2025-26 guidebooks, but the guidebooks do not print its database code.",
    "TK1001": "Fall management harvest Northern Region/private-land reference is described in guidebook fall-management text, but no fall-management TK code is printed.",
    "TK1012": "Conservation permits are described as spring permit types in the guidebooks; conservation area codes are database/reference rows, not printed guidebook hunt-table codes.",
    "TK1013": "Conservation permits are described as spring permit types in the guidebooks; conservation area codes are database/reference rows, not printed guidebook hunt-table codes.",
    "TK1014": "Conservation permits are described as spring permit types in the guidebooks; conservation area codes are database/reference rows, not printed guidebook hunt-table codes.",
    "TK1015": "Conservation permits are described as spring permit types in the guidebooks; conservation area codes are database/reference rows, not printed guidebook hunt-table codes.",
    "TK1016": "Conservation permits are described as spring permit types in the guidebooks; conservation area codes are database/reference rows, not printed guidebook hunt-table codes.",
    "TK1019": "Fall management harvest Southeastern Region/select-areas reference is described in guidebook fall-management text, but no fall-management TK code is printed.",
    "TK1020": "Fall management harvest Central Region/private-land reference is described in guidebook fall-management text, but no fall-management TK code is printed.",
    "TK1022": "Fall management harvest Southern Region/select-areas reference is described in the 2025-26 guidebook; it is not printed as a TK hunt-table code.",
}


def normalized(text: str) -> str:
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2022", " ")
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u00a0", " ")
    text = re.sub(r"-\s+", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rows_by_tk_code(path: Path) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = {}
    for row in read_rows(path):
        code = row.get("hunt_code", "")
        if code.startswith("TK"):
            rows.setdefault(code, []).append(row)
    return rows


def extract_prior_lines() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with pdfplumber.open(PRIOR_GUIDEBOOK_PDF) as pdf:
        for pdf_page, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line_number, line in enumerate(text.splitlines(), start=1):
                clean_line = normalized(line)
                if not clean_line:
                    continue
                printed_page_match = re.match(r"^(\d{1,2})\b", clean_line)
                rows.append(
                    {
                        "source_file": PRIOR_SOURCE_PATH,
                        "source_sha256": PRIOR_EXPECTED_SHA256,
                        "pdf_page": str(pdf_page),
                        "printed_page": printed_page_match.group(1) if printed_page_match else "",
                        "line_number": str(line_number),
                        "text": clean_line,
                    }
                )
    return rows


def build_number_tokens(text_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    token_rows: list[dict[str, str]] = []
    token_patterns = [
        ("date", DATE_TOKEN_RE),
        ("code_citation", CODE_CITATION_RE),
        ("number_money_code", NUMBER_TOKEN_RE),
    ]
    for line in text_lines:
        seen: set[tuple[str, str]] = set()
        for token_type, pattern in token_patterns:
            for match in pattern.finditer(line["text"]):
                token = match.group(0)
                key = (token_type, token)
                if key in seen:
                    continue
                seen.add(key)
                token_rows.append(
                    {
                        "source_file": line["source_file"],
                        "source_sha256": line["source_sha256"],
                        "pdf_page": line["pdf_page"],
                        "printed_page": line["printed_page"],
                        "line_number": line["line_number"],
                        "token_type": token_type,
                        "token": token,
                        "line_text": line["text"],
                    }
                )
    return token_rows


def build_expected_checks(all_text: str) -> list[dict[str, str]]:
    norm_text = normalized(all_text)
    rows: list[dict[str, str]] = []
    for check in PRIOR_EXPECTED_TEXT_CHECKS:
        expected = normalized(check.expected_text)
        rows.append(
            {
                "check_id": check.check_id,
                "printed_page": check.printed_page,
                "match_type": "contains",
                "expected_text": expected,
                "source_note": check.source_note,
                "status": "PASS" if expected in norm_text else "FAIL",
            }
        )
    return rows


def name_resolves(guidebook_name: str, database_name: str) -> bool:
    guide = normalized(guidebook_name).lower()
    database = normalized(database_name).lower()
    variants = {guide, f"{guide} area", f"{guide} cwmu"}
    return database in variants or guide in database


def build_prior_guidebook_reconciliation() -> list[dict[str, str]]:
    database_rows = rows_by_tk_code(DATABASE)
    predictive_rows = rows_by_tk_code(PREDICTIVE)
    rows: list[dict[str, str]] = []
    for guidebook_code in PRIOR_GUIDEBOOK_CODES:
        database_row = (database_rows.get(guidebook_code.code) or [{}])[0]
        predictive_row = (predictive_rows.get(guidebook_code.code) or [{}])[0]
        if guidebook_code.code_type == "bonus_point_code":
            status = "PASS_BONUS_POINT_CODE_NOT_DATABASE_HUNT"
            resolved = "true" if not database_row else "review"
        else:
            resolved = str(bool(database_row) and name_resolves(guidebook_code.guidebook_name, database_row.get("hunt_name", ""))).lower()
            status = "PASS" if resolved == "true" and predictive_row else "FAIL"
        rows.append(
            {
                "source_file": PRIOR_SOURCE_PATH,
                "source_sha256": PRIOR_EXPECTED_SHA256,
                "guidebook_code": guidebook_code.code,
                "code_type": guidebook_code.code_type,
                "guidebook_name": guidebook_code.guidebook_name,
                "guidebook_context": guidebook_code.guidebook_context,
                "database_present": str(bool(database_row)).lower(),
                "database_hunt_name": database_row.get("hunt_name", ""),
                "database_species": database_row.get("species", ""),
                "database_hunt_type": database_row.get("hunt_type", ""),
                "database_weapon": database_row.get("weapon", ""),
                "database_season": database_row.get("season", ""),
                "predictive_present": str(bool(predictive_row)).lower(),
                "predictive_hunt_name": predictive_row.get("hunt_name", ""),
                "name_resolution_status": resolved,
                "status": status,
            }
        )
    return rows


def current_guidebook_codes() -> set[str]:
    rows = read_rows(CURRENT_GUIDEBOOK_RECON)
    return {row["guidebook_code"] for row in rows if row.get("code_type") == "hunt_code" and row.get("guidebook_code", "").startswith("TK")}


def prior_guidebook_codes() -> set[str]:
    return {code.code for code in PRIOR_GUIDEBOOK_CODES if code.code_type == "hunt_code"}


def first_row(rows: dict[str, list[dict[str, str]]], code: str) -> dict[str, str]:
    return (rows.get(code) or [{}])[0]


def classify_code(code: str, database_present: bool, predictive_present: bool, printed_current: bool) -> str:
    if printed_current and database_present:
        return "GUIDEBOOK_PRINTED_CURRENT_HUNT_CODE"
    if database_present and predictive_present:
        return "CURRENT_DATABASE_PREDICTIVE_REFERENCE_NOT_PRINTED_IN_GUIDEBOOK_CODE_LIST"
    if database_present:
        return "CURRENT_DATABASE_REFERENCE_NOT_PRINTED_IN_GUIDEBOOK_CODE_LIST"
    return "HISTORICAL_OR_NON_CURRENT_TURKEY_CODE"


def reference_resolution(code: str, database_row: dict[str, str], status: str) -> str:
    if status == "GUIDEBOOK_PRINTED_CURRENT_HUNT_CODE":
        return "Printed in the current 2025-26 turkey guidebook and resolved to DATABASE."
    if code in GUIDEBOOK_BASIS_BY_CODE:
        return GUIDEBOOK_BASIS_BY_CODE[code]
    if database_row:
        return "Current DATABASE turkey reference row; not printed as a turkey guidebook hunt-table code."
    return "Not present in current DATABASE; retained only if another source surface carries it."


def build_full_reconciliation() -> list[dict[str, str]]:
    database_rows = rows_by_tk_code(DATABASE)
    hunt_master_rows = rows_by_tk_code(HUNT_MASTER)
    point_ladder_rows = rows_by_tk_code(POINT_LADDER)
    draw_reality_rows = rows_by_tk_code(DRAW_REALITY)
    predictive_rows = rows_by_tk_code(PREDICTIVE)
    current_printed = current_guidebook_codes()
    prior_printed = prior_guidebook_codes()
    all_codes = sorted(set(database_rows) | set(hunt_master_rows) | set(point_ladder_rows) | set(draw_reality_rows) | set(predictive_rows) | current_printed | prior_printed)

    rows: list[dict[str, str]] = []
    for code in all_codes:
        database_row = first_row(database_rows, code)
        predictive_row = first_row(predictive_rows, code)
        status = classify_code(code, bool(database_row), bool(predictive_row), code in current_printed)
        current_db_failure = bool(database_row) and not (
            bool(hunt_master_rows.get(code))
            and bool(point_ladder_rows.get(code))
            and bool(draw_reality_rows.get(code))
            and bool(predictive_rows.get(code))
        )
        rows.append(
            {
                "hunt_code": code,
                "hunt_name": database_row.get("hunt_name", "") or predictive_row.get("hunt_name", ""),
                "species": database_row.get("species", "") or predictive_row.get("species", ""),
                "hunt_type": database_row.get("hunt_type", "") or predictive_row.get("hunt_type", ""),
                "weapon": database_row.get("weapon", "") or predictive_row.get("weapon", ""),
                "season": database_row.get("season", "") or predictive_row.get("season_dates", ""),
                "permits_2026_total": database_row.get("permits_2026_total", "") or predictive_row.get("public_permits_2026", ""),
                "printed_in_2026_guidebook": str(code in current_printed).lower(),
                "printed_in_2025_guidebook": str(code in prior_printed).lower(),
                "database_present": str(bool(database_row)).lower(),
                "hunt_master_present": str(bool(hunt_master_rows.get(code))).lower(),
                "point_ladder_present": str(bool(point_ladder_rows.get(code))).lower(),
                "draw_reality_present": str(bool(draw_reality_rows.get(code))).lower(),
                "predictive_v2_present": str(bool(predictive_rows.get(code))).lower(),
                "code_resolution_class": status,
                "guidebook_basis": reference_resolution(code, database_row, status),
                "current_database_reconciliation_status": "FAIL" if current_db_failure else "PASS",
            }
        )
    return rows


def numeric(value: str) -> int | None:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def build_reference_row(fieldnames: list[str], database_row: dict[str, str]) -> dict[str, str]:
    row = {fieldname: "" for fieldname in fieldnames}
    total_permits = database_row.get("permits_2026_total", "")
    reason = (
        "Promoted from current 2026 DATABASE turkey reference plus 2024-25/2025-26 guidebook context; "
        "this is a non-modeled reference row and no draw-odds probability was invented."
    )
    row.update(
        {
            "year": "2026",
            "forecast_year": "2026",
            "hunt_code": database_row["hunt_code"],
            "hunt_name": database_row.get("hunt_name", ""),
            "species": database_row.get("species", "") or "Turkey",
            "sex_type": database_row.get("sex_type", ""),
            "hunt_type": database_row.get("hunt_type", ""),
            "hunt_class": "Turkey Reference",
            "residency": "Resident",
            "points": "0",
            "draw_pool": "turkey_reference",
            "source_years_used": "2025;2026",
            "source_year_count": "2",
            "latest_source_year": "2026",
            "earliest_source_year": "2025",
            "source_dataset": "2026_turkey_full_hunt_code_reconciliation",
            "model_strategy": "TURKEY_GUIDEBOOK_REFERENCE",
            "draw_system_type": "TURKEY_REFERENCE_NON_MODELED",
            "season_dates": database_row.get("season", ""),
            "weapon": database_row.get("weapon", ""),
            "algorithm_status": "TURKEY_GUIDEBOOK_REFERENCE",
            "target_scope": "TARGET",
            "modeled_by_engine": "False",
            "reason": reason,
            "model_version": REFERENCE_MODEL_VERSION,
            "rule_version": REFERENCE_RULE_VERSION,
            "public_permits_2026": total_permits,
            "quota_source_status": "official_database_reference",
            "quota_source_year": "2026",
            "quota_source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "quota_2026_total": total_permits,
            "permit_allotment_2026_res": database_row.get("permits_2026_res", ""),
            "permit_allotment_2026_nr": database_row.get("permits_2026_nr", ""),
            "permit_allotment_2026_total": total_permits,
            "permit_allotment_2026_source": "DATABASE",
            "permit_allotment_2026_source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "permit_allotment_2026_status": "official_database_reference",
            "data_cutoff_date": DATA_CUTOFF_DATE,
            "reason_codes": "TURKEY_CURRENT_DATABASE_REFERENCE|NO_PREDICTIVE_DRAW_MODEL_ROW|NO_DRAW_PROBABILITY_INVENTED",
            "status": "turkey_reference_no_draw_odds",
            "trend": "not_modeled",
            "permit_availability_type": "turkey_reference",
            "probability_model": "NONE",
            "rule_status": "turkey_reference",
            "availability_status": "turkey_reference",
            "data_quality_flags": "PROMOTED_TURKEY_REFERENCE_CODE;NO_DRAW_PROBABILITY_MODELED",
            "turkey_bonus_valid": "FALSE",
            "turkey_bonus_note": "Reference-only turkey row outside modeled limited-entry/CWMU bonus ladder.",
            "prediction_year": "2026",
            "source_year": "2026",
            "applicant_forecast_method": "not_modeled_turkey_reference",
            "display_odds_text": "Turkey reference only; odds not modeled",
            "data_quality_grade": "A",
        }
    )
    if numeric(total_permits) is None:
        row["permit_allotment_2026_total"] = ""
        row["quota_2026_total"] = ""
        row["public_permits_2026"] = ""
    return row


def promote_missing_turkey_references() -> dict[str, object]:
    predictive_rows = read_rows(PREDICTIVE)
    database_rows = {row["hunt_code"]: row for row in read_rows(DATABASE) if row.get("hunt_code", "").startswith("TK")}
    with PREDICTIVE.open(newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []

    current_database_codes = set(database_rows)
    existing_predictive_codes = {row.get("hunt_code", "") for row in predictive_rows if row.get("hunt_code", "").startswith("TK")}
    missing_codes = sorted(current_database_codes - existing_predictive_codes)

    promoted_rows = [build_reference_row(fieldnames, database_rows[code]) for code in missing_codes]
    if promoted_rows:
        predictive_rows.extend(promoted_rows)
        write_rows(PREDICTIVE, fieldnames, predictive_rows)

    final_predictive_rows = read_rows(PREDICTIVE)
    final_predictive_codes = {row.get("hunt_code", "") for row in final_predictive_rows if row.get("hunt_code", "").startswith("TK")}
    still_missing = sorted(current_database_codes - final_predictive_codes)
    reference_rows = [
        row
        for row in final_predictive_rows
        if row.get("model_version") == REFERENCE_MODEL_VERSION and row.get("hunt_code", "").startswith("TK")
    ]
    reference_codes = sorted({row["hunt_code"] for row in reference_rows})

    duplicate_keys = [
        key
        for key, count in Counter(
            (
                row.get("hunt_code", ""),
                row.get("residency", ""),
                row.get("points", ""),
                row.get("draw_pool", ""),
                row.get("model_version", ""),
            )
            for row in final_predictive_rows
        ).items()
        if count > 1
    ]

    detail_rows = [
        {
            "hunt_code": row.get("hunt_code", ""),
            "hunt_name": row.get("hunt_name", ""),
            "species": row.get("species", ""),
            "hunt_type": row.get("hunt_type", ""),
            "residency": row.get("residency", ""),
            "permits_2026_total": row.get("permit_allotment_2026_total", ""),
            "promotion_status": "PROMOTED",
            "reason": row.get("reason", ""),
        }
        for row in sorted(reference_rows, key=lambda item: item.get("hunt_code", ""))
    ]
    write_rows(
        PROMOTION_DETAIL,
        ["hunt_code", "hunt_name", "species", "hunt_type", "residency", "permits_2026_total", "promotion_status", "reason"],
        detail_rows,
    )

    summary = {
        "classification": "TURKEY_GUIDEBOOK_REFERENCE_PROMOTION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_surface": str(PREDICTIVE.relative_to(ROOT)).replace("\\", "/"),
        "current_database_turkey_code_count": len(current_database_codes),
        "initial_missing_predictive_hunt_code_count": len(missing_codes),
        "newly_promoted_hunt_code_count": len(promoted_rows),
        "promoted_reference_hunt_code_count": len(reference_codes),
        "still_missing_predictive_hunt_code_count": len(still_missing),
        "duplicate_reference_key_count": len(duplicate_keys),
        "promoted_reference_hunt_codes": reference_codes,
        "newly_promoted_hunt_codes": [row["hunt_code"] for row in promoted_rows],
        "still_missing_predictive_hunt_codes": still_missing,
        "guardrail": "Turkey reference rows promote current hunt-code coverage only; no draw odds or probability fields are invented.",
    }
    PROMOTION_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def write_prior_audit_outputs() -> dict[str, object]:
    actual_sha = sha256(PRIOR_GUIDEBOOK_PDF)
    text_lines = extract_prior_lines()
    all_text = "\n".join(row["text"] for row in text_lines)
    number_tokens = build_number_tokens(text_lines)
    expected_checks = build_expected_checks(all_text)
    reconciliation_rows = build_prior_guidebook_reconciliation()
    token_counts = Counter(row["token_type"] for row in number_tokens)

    write_rows(PRIOR_TEXT_LINES_CSV, ["source_file", "source_sha256", "pdf_page", "printed_page", "line_number", "text"], text_lines)
    write_rows(
        PRIOR_NUMBER_TOKENS_CSV,
        ["source_file", "source_sha256", "pdf_page", "printed_page", "line_number", "token_type", "token", "line_text"],
        number_tokens,
    )
    write_rows(
        PRIOR_EXPECTED_TEXT_CHECKS_CSV,
        ["check_id", "printed_page", "match_type", "expected_text", "source_note", "status"],
        expected_checks,
    )
    write_rows(
        PRIOR_HUNT_CODE_RECONCILIATION_CSV,
        [
            "source_file",
            "source_sha256",
            "guidebook_code",
            "code_type",
            "guidebook_name",
            "guidebook_context",
            "database_present",
            "database_hunt_name",
            "database_species",
            "database_hunt_type",
            "database_weapon",
            "database_season",
            "predictive_present",
            "predictive_hunt_name",
            "name_resolution_status",
            "status",
        ],
        reconciliation_rows,
    )

    failed_checks = [row for row in expected_checks if row["status"] != "PASS"]
    failed_reconciliation = [row for row in reconciliation_rows if not row["status"].startswith("PASS")]
    blockers: list[str] = []
    if actual_sha != PRIOR_EXPECTED_SHA256:
        blockers.append("source_sha256_mismatch")
    if PRIOR_GUIDEBOOK_PDF.stat().st_size != PRIOR_EXPECTED_SIZE_BYTES:
        blockers.append("source_size_mismatch")
    with pdfplumber.open(PRIOR_GUIDEBOOK_PDF) as pdf:
        page_count = len(pdf.pages)
    if page_count != PRIOR_EXPECTED_PDF_PAGES:
        blockers.append("pdf_page_count_mismatch")
    if failed_checks:
        blockers.append("expected_text_anchor_failures")
    if failed_reconciliation:
        blockers.append("hunt_code_name_reconciliation_failures")

    summary = {
        "classification": "PRIOR_YEAR_TURKEY_GUIDEBOOK_TRUTH_SOURCE_AUDIT",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdf": PRIOR_SOURCE_PATH,
        "guidebook_title": "2024-25 Utah Upland Game and Turkey Guidebook",
        "source_sha256": actual_sha,
        "expected_sha256": PRIOR_EXPECTED_SHA256,
        "source_size_bytes": PRIOR_GUIDEBOOK_PDF.stat().st_size,
        "expected_size_bytes": PRIOR_EXPECTED_SIZE_BYTES,
        "pdf_pages": page_count,
        "text_lines": len(text_lines),
        "number_tokens": len(number_tokens),
        "token_type_counts": dict(sorted(token_counts.items())),
        "expected_text_checks": len(expected_checks),
        "expected_text_anchor_failures": len(failed_checks),
        "guidebook_printed_hunt_code_count": len(prior_guidebook_codes()),
        "guidebook_bonus_point_codes": ["TKY"],
        "database_name_resolved_hunt_code_count": sum(
            1 for row in reconciliation_rows if row["code_type"] == "hunt_code" and row["name_resolution_status"] == "true"
        ),
        "hunt_code_reconciliation_failures": len(failed_reconciliation),
        "blockers": len(blockers),
        "blocker_reasons": blockers,
        "guardrail": "Prior-year turkey guidebook is regulation/reference context only; no draw odds are modeled from it.",
    }
    PRIOR_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    PRIOR_REPORT_MD.write_text(
        "\n".join(
            [
                "# 2025 Turkey Guidebook Audit",
                "",
                f"- Source PDF: `{PRIOR_SOURCE_PATH}`",
                f"- Source SHA-256: `{actual_sha}`",
                f"- PDF pages: `{page_count}`",
                f"- Extracted text lines: `{len(text_lines)}`",
                f"- Extracted number/date/code tokens: `{len(number_tokens)}`",
                f"- Expected pasted-data anchor checks: `{len(expected_checks)}`",
                f"- Anchor failures: `{len(failed_checks)}`",
                f"- Printed turkey hunt codes checked: `{len(prior_guidebook_codes())}`",
                f"- Database name-resolved printed hunt codes: `{summary['database_name_resolved_hunt_code_count']}`",
                f"- Bonus-point code handled separately: `TKY`",
                f"- Blockers: `{len(blockers)}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def write_full_reconciliation_outputs(promotion_summary: dict[str, object]) -> dict[str, object]:
    reconciliation_rows = build_full_reconciliation()
    fieldnames = [
        "hunt_code",
        "hunt_name",
        "species",
        "hunt_type",
        "weapon",
        "season",
        "permits_2026_total",
        "printed_in_2026_guidebook",
        "printed_in_2025_guidebook",
        "database_present",
        "hunt_master_present",
        "point_ladder_present",
        "draw_reality_present",
        "predictive_v2_present",
        "code_resolution_class",
        "guidebook_basis",
        "current_database_reconciliation_status",
    ]
    write_rows(FULL_RECONCILIATION_CSV, fieldnames, reconciliation_rows)

    current_database_rows = [row for row in reconciliation_rows if row["database_present"] == "true"]
    failures = [row for row in current_database_rows if row["current_database_reconciliation_status"] != "PASS"]
    printed_current = [row for row in reconciliation_rows if row["printed_in_2026_guidebook"] == "true" and row["database_present"] == "true"]
    db_not_printed = [
        row["hunt_code"]
        for row in current_database_rows
        if row["printed_in_2026_guidebook"] != "true"
    ]
    predictive_codes = [row for row in current_database_rows if row["predictive_v2_present"] == "true"]

    summary = {
        "classification": "TURKEY_FULL_HUNT_CODE_RECONCILIATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "current_database_turkey_code_count": len(current_database_rows),
        "guidebook_2026_printed_current_hunt_code_count": len(printed_current),
        "guidebook_2025_printed_hunt_code_count": len(prior_guidebook_codes()),
        "bonus_point_codes": ["TKY"],
        "current_database_codes_not_printed_in_2026_guidebook_code_list_count": len(db_not_printed),
        "current_database_codes_not_printed_in_2026_guidebook_code_list": sorted(db_not_printed),
        "current_predictive_v2_turkey_code_count": len(predictive_codes),
        "current_database_reconciliation_failure_count": len(failures),
        "current_database_reconciliation_failures": [row["hunt_code"] for row in failures],
        "promotion_summary": promotion_summary,
        "blockers": len(failures) + int(promotion_summary["still_missing_predictive_hunt_code_count"]) + int(promotion_summary["duplicate_reference_key_count"]),
        "guardrail": "Full Turkey code reconciliation resolves guidebook-printed, database-reference, and bonus-point codes without changing draw odds math.",
    }
    FULL_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    FULL_REPORT_MD.write_text(
        "\n".join(
            [
                "# 2026 Turkey Full Hunt-Code Reconciliation",
                "",
                f"- Current DATABASE TK codes: `{summary['current_database_turkey_code_count']}`",
                f"- 2026 guidebook-printed current TK hunt codes: `{summary['guidebook_2026_printed_current_hunt_code_count']}`",
                f"- 2025 guidebook-printed TK hunt codes: `{summary['guidebook_2025_printed_hunt_code_count']}`",
                f"- Current DATABASE TK codes not printed in 2026 guidebook code list: `{summary['current_database_codes_not_printed_in_2026_guidebook_code_list_count']}`",
                f"- Current predictive v2 TK code coverage: `{summary['current_predictive_v2_turkey_code_count']}`",
                f"- Reconciliation failures: `{summary['current_database_reconciliation_failure_count']}`",
                f"- Promotion still-missing count: `{promotion_summary['still_missing_predictive_hunt_code_count']}`",
                f"- Duplicate reference keys: `{promotion_summary['duplicate_reference_key_count']}`",
                f"- Blockers: `{summary['blockers']}`",
                "",
                "The database-only TK codes are resolved as current reference rows: spring OTC, fall management, conservation, or special statewide/sportsman references. They are not odds rows.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    prior_summary = write_prior_audit_outputs()
    promotion_summary = promote_missing_turkey_references()
    full_summary = write_full_reconciliation_outputs(promotion_summary)
    blockers = int(prior_summary["blockers"]) + int(full_summary["blockers"])
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
