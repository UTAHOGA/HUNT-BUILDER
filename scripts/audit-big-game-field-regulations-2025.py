from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ROOT / "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf"
RAW_INVENTORY = ROOT / "data_model/quality/raw_pdf_inventory.csv"
RAW_AUDIT = ROOT / "data_model/quality/raw_pdf_inventory_audit.csv"
HARD_COPY_MANIFEST = ROOT / "processed_data/hard_data_exports/hard_copy_pdf_manifest.web.json"
CANONICAL_HARD_COPIES = ROOT / "canonical/hard-copies-2026.json"
OUT_DIR = ROOT / "data_truth/regulations_truth/normalized"
REPORT_DIR = ROOT / "processed_data"

SUMMARY = REPORT_DIR / "2025_big_game_field_regulations_source_label_audit.json"
REPORT_MD = REPORT_DIR / "2025_big_game_field_regulations_source_label_audit.md"
CORRECTIONS_CSV = OUT_DIR / "2025_big_game_field_regulations_post_publication_corrections.csv"
TEXT_LINES_CSV = OUT_DIR / "2025_big_game_field_regulations_text_lines.csv"
NUMBER_TOKENS_CSV = OUT_DIR / "2025_big_game_field_regulations_number_tokens.csv"
EXPECTED_TEXT_CHECKS_CSV = OUT_DIR / "2025_big_game_field_regulations_expected_text_checks.csv"

SOURCE_PATH = "pipeline/RAW/hunt_unit_database/2025/pdf/regulations/2025_REGULATIONS__FIELD_REGS.pdf"
EXPECTED_SHA256 = "05a87b5babd0a22af62c993bd3fe0ba106fb18f7029ed60fc75f6babe4dbdaa7"
EXPECTED_SIZE_BYTES = 3_432_415

DATE_TOKEN_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+"
    r"\d{1,2}(?:\s*[–-]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+)?\d{1,2})?"
    r"(?:,\s*\d{4})?\b",
    re.IGNORECASE,
)
CODE_CITATION_RE = re.compile(r"\b(?:R657-\d+(?:-\d+)?(?:\(\d+\))?|(?:\d{2,3}-){2}\d{1,4}|53-5a-\d+)\b")
NUMBER_TOKEN_RE = re.compile(
    r"\$?\b\d+(?:,\d{3})*(?:\.\d+)?%?\b|\b\d{1,2}:\d{2}\b|\b[A-Z]{1,3}\d{4}\b"
)


@dataclass(frozen=True)
class Correction:
    correction_type: str
    guidebook_page: str
    correction_date: str
    summary: str


@dataclass(frozen=True)
class ExpectedTextCheck:
    check_id: str
    guidebook_page: str
    match_type: str
    expected_text: str
    source_note: str


POST_PUBLICATION_CORRECTIONS = [
    Correction(
        "correction",
        "29",
        "2025-12-01",
        "Deleted Salt Lake County restriction bullet for Red Butte Research Natural Area; the area remains closed to public access.",
    ),
    Correction(
        "correction",
        "33",
        "",
        "Removed sentence stating big game may not be donated in the field to align with rule language regarding donations.",
    ),
    Correction(
        "correction",
        "38",
        "",
        "Corrected restricted muzzleloader deer dates to Sept. 24-Oct. 2, 2025 and restricted rifle deer dates to Oct. 18-26, 2025.",
    ),
    Correction(
        "update",
        "guidebook-wide",
        "2025-11-13",
        "Updated recodified Chapter 10 code citations to Chapter 11 and related Utah Code references effective May 7, 2025.",
    ),
    Correction(
        "update",
        "19",
        "",
        "Added youth Uinta Basin private-lands-only permit row and reorganized the youth-only elk permit table and footnotes.",
    ),
    Correction(
        "update",
        "70",
        "",
        "Clarified restricted muzzleloader equipment must meet Utah Admin. Rule R657-5-10(1) and (2).",
    ),
    Correction(
        "update",
        "25-26",
        "",
        "Removed inadvertently included archery-hunt field-possession restriction text from the online edition.",
    ),
]


EXPECTED_TEXT_CHECKS = [
    ExpectedTextCheck("contents_general_season_dates", "2", "contains", "7 General-season dates", "user pasted contents"),
    ExpectedTextCheck("contents_definitions", "2", "contains", "68 Definitions", "user pasted contents"),
    ExpectedTextCheck("utip_phone", "2", "contains", "Phone: 800-662-3337", "user pasted contact block"),
    ExpectedTextCheck("utip_text", "2", "contains", "Text: 847411", "user pasted contact block"),
    ExpectedTextCheck("title_2025_field_regs", "3", "contains", "This guidebook-along with the 2025", "user pasted know-the-laws block"),
    ExpectedTextCheck("whats_new_residency", "3", "contains", "Residency requirements", "user pasted what's-new block"),
    ExpectedTextCheck("whats_new_nonresident_fee", "3", "contains", "Nonresident fee increase", "user pasted what's-new block"),
    ExpectedTextCheck("restricted_weapons_four_units", "4", "contains", "Deer restricted weapons hunts on four", "user pasted what's-new block"),
    ExpectedTextCheck("wma_license_requirement", "4", "contains", "License required to access WMAs", "user pasted what's-new block"),
    ExpectedTextCheck("general_archery_deer_date", "7", "contains", "General archery buck deer Aug. 16-Sept. 12", "user pasted season dates"),
    ExpectedTextCheck("draw_only_youth_elk_date", "7", "contains", "Draw-only youth any Sept. 13-23", "user pasted season dates"),
    ExpectedTextCheck("sportsman_deer_elk_weapon_date", "8", "contains", "Deer and elk on any open unit Sept. 1, 2025-", "user pasted sportsman dates"),
    ExpectedTextCheck("sportsman_bison_date", "8", "contains", "Bison on any open unit Aug. 1, 2025-", "user pasted sportsman dates"),
    ExpectedTextCheck("license_fee_child", "9", "contains", "13 and under $11 $34 $44", "user pasted license fees"),
    ExpectedTextCheck("application_fee", "9", "contains", "Application fee $10 $16 $21", "user pasted permit fees"),
    ExpectedTextCheck("antlerless_apply_window", "14", "contains", "Starting June 4, 2025", "user pasted antlerless application dates"),
    ExpectedTextCheck("otc_july_8", "15", "contains", "JULY 8", "user pasted OTC dates"),
    ExpectedTextCheck("otc_july_29", "15", "contains", "JULY 29", "user pasted OTC dates"),
    ExpectedTextCheck("three_elk_permits", "16", "contains", "A hunter can obtain up to three elk", "user pasted elk permit rules"),
    ExpectedTextCheck("youth_elk_private_lands_row", "19", "contains", "Any legal weapon Uinta Basin private lands only Aug. 1-Nov. 15", "post-publication update pasted by user"),
    ExpectedTextCheck("youth_draw_only_row", "19", "contains", "Any legal weapon Any bull Sept. 13-Sept. 23", "user pasted youth table"),
    ExpectedTextCheck("cwd_positive_counts", "20", "contains", "342 mule deer and nine elk have tested positive", "user pasted CWD block"),
    ExpectedTextCheck("mandatory_reporting_late_deadline", "21", "contains", "Hunts ending Jan. 16 or later must have a harvest report submitted by Feb. 15", "user pasted reporting block"),
    ExpectedTextCheck("late_fee_amount", "21", "contains", "$50 late fee", "user pasted reporting block"),
    ExpectedTextCheck("muzzleloader_scope_limit", "24", "contains", "Scopes stronger than 1x power are", "user pasted weapon rules"),
    ExpectedTextCheck("muzzleloader_projectile_weights", "25", "contains", "210-grain or heavier bullet", "user pasted weapon rules"),
    ExpectedTextCheck("hamss_no_scopes", "26", "contains", "Important: On all HAMSS hunts, no", "user pasted HAMSS rules"),
    ExpectedTextCheck("restricted_archery_specs", "27", "contains", "Must be a single-stringed longbow or", "user pasted restricted weapons rules"),
    ExpectedTextCheck("loaded_firearm_recodified_codes", "27", "contains", "76-11-102, 53-5a-3, 76-11-204", "post-publication code update"),
    ExpectedTextCheck("red_butte_removed", "29", "absent", "Red Butte Research Natural Area", "post-publication correction pasted by user"),
    ExpectedTextCheck("salt_lake_county_i80_i15", "29", "contains", "Hunt buck deer or bull elk with a rifle or", "user pasted Salt Lake County block"),
    ExpectedTextCheck("town_of_alton_new", "30", "contains", "Town of Alton (new)", "user pasted special restrictions"),
    ExpectedTextCheck("trail_camera_public_land_dates", "31", "contains", "Trail cameras are prohibited on public land", "user pasted prohibited methods"),
    ExpectedTextCheck("aircraft_july_jan_dates", "32", "contains", "between July 31 and Jan.", "user pasted aircraft rules"),
    ExpectedTextCheck("donation_sentence_absent", "33", "absent", "you may not donate big game in the field", "post-publication correction pasted by user"),
    ExpectedTextCheck("bring_big_game_skulls", "34", "contains", "Skulls with antlers attached (new)", "user pasted importation update"),
    ExpectedTextCheck("wma_license_four_counties", "36", "contains", "New this year: Anyone 18 years old", "user pasted WMA license block"),
    ExpectedTextCheck("restricted_muzzleloader_correct_date", "38", "contains", "Restricted muzzleloader deer hunts", "post-publication correction pasted by user"),
    ExpectedTextCheck("restricted_rifle_correct_date", "38", "contains", "deer from Oct. 18-26, 2025", "post-publication correction pasted by user"),
    ExpectedTextCheck("hamss_elk_east_canyon_date", "45", "contains", "East Canyon (new, Dec. 20-28)", "user pasted elk HAMSS block"),
    ExpectedTextCheck("nine_mile_bison_sale_date", "49", "contains", "Permits will be available for purchase start-", "user pasted bison block"),
    ExpectedTextCheck("antlerless_hunts_heading", "52", "contains", "ANTLERLESS HUNTS", "user pasted antlerless block"),
    ExpectedTextCheck("antlerless_elk_printed_dates_rule", "53", "contains", "Important: Antlerless elk permits may be", "user pasted antlerless elk block"),
    ExpectedTextCheck("hunter_mentoring_program", "55", "contains", "The Utah Hunter Mentoring Program", "user pasted mentoring block"),
    ExpectedTextCheck("cwmu_hunt_dates", "59", "contains", "Archery hunts for buck Aug. 16-Oct. 31", "user pasted CWMU dates"),
    ExpectedTextCheck("definition_baited_area", "68", "contains", "Baited area means all land within a 50-yard", "user pasted definitions"),
    ExpectedTextCheck("definition_hamss", "69", "contains", "Handgun-archery-muzzleloader-shotgun-", "user pasted definitions"),
    ExpectedTextCheck("restricted_muzzleloader_clarification", "70", "contains", "meets all requirements for muzzleloaders", "post-publication update pasted by user"),
    ExpectedTextCheck("definition_youth", "71", "contains", "Youth means someone who is 17 years old or", "user pasted definitions"),
    ExpectedTextCheck("removed_archery_field_possession_absent", "", "absent", "You may not possess or be in control of a rifle, shotgun, airgun, muzzleloader, crossbow or draw-lock while in the field during an archery hunt", "post-publication correction pasted by user"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_manifest_items(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("library", {}).get("items", []))
    return []


def normalize_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "",
        "\u25ca": "",
        "\u2021": "",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def compact_for_match(text: str) -> str:
    return normalize_text(text).casefold()


def extract_pdf_lines(path: Path) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for pdf_page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            raw_lines = text.splitlines()
            printed_page = ""
            for candidate in raw_lines[:3]:
                cleaned = normalize_text(candidate)
                if cleaned.isdigit():
                    printed_page = cleaned
                    break
            text_line_number = 0
            for raw_line in raw_lines:
                line_text = normalize_text(raw_line)
                if not line_text:
                    continue
                text_line_number += 1
                rows.append(
                    {
                        "source_file": SOURCE_PATH,
                        "pdf_page_number": str(pdf_page_number),
                        "printed_page": printed_page,
                        "line_number_on_pdf_page": str(text_line_number),
                        "line_text": line_text,
                    }
                )
    return rows, page_count


def write_pdf_lines(rows: list[dict[str, str]]) -> None:
    with TEXT_LINES_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "source_file",
            "pdf_page_number",
            "printed_page",
            "line_number_on_pdf_page",
            "line_text",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def extract_number_tokens(line_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    token_rows: list[dict[str, str]] = []
    for row in line_rows:
        line_text = row["line_text"]
        seen: set[tuple[str, str]] = set()
        for token_type, pattern in (
            ("date", DATE_TOKEN_RE),
            ("code_citation", CODE_CITATION_RE),
            ("number_or_money", NUMBER_TOKEN_RE),
        ):
            for match in pattern.finditer(line_text):
                token = match.group(0)
                key = (token_type, token)
                if key in seen:
                    continue
                seen.add(key)
                token_rows.append(
                    {
                        "source_file": SOURCE_PATH,
                        "pdf_page_number": row["pdf_page_number"],
                        "printed_page": row["printed_page"],
                        "line_number_on_pdf_page": row["line_number_on_pdf_page"],
                        "token_type": token_type,
                        "token": token,
                        "line_text": line_text,
                    }
                )
    return token_rows


def write_number_tokens(rows: list[dict[str, str]]) -> None:
    with NUMBER_TOKENS_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "source_file",
            "pdf_page_number",
            "printed_page",
            "line_number_on_pdf_page",
            "token_type",
            "token",
            "line_text",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def find_expected_match(line_rows: list[dict[str, str]], check: ExpectedTextCheck) -> tuple[str, dict[str, str] | None]:
    scoped_rows = [row for row in line_rows if not check.guidebook_page or row["printed_page"] == check.guidebook_page]
    haystack = compact_for_match(" ".join(row["line_text"] for row in scoped_rows))
    needle = compact_for_match(check.expected_text)

    if check.match_type == "absent":
        return ("PASS" if needle not in haystack else "FAIL", None)

    if needle not in haystack:
        return "FAIL", None

    words = [word for word in needle.split() if len(word) >= 4]
    snippets = [" ".join(words[:4]), " ".join(words[:3]), words[0] if words else needle]
    for row in scoped_rows:
        line_compact = compact_for_match(row["line_text"])
        if any(snippet and snippet in line_compact for snippet in snippets):
            return "PASS", row
    return "PASS", scoped_rows[0] if scoped_rows else None


def run_expected_text_checks(line_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for check in EXPECTED_TEXT_CHECKS:
        status, matched = find_expected_match(line_rows, check)
        rows.append(
            {
                "source_file": SOURCE_PATH,
                "check_id": check.check_id,
                "guidebook_page": check.guidebook_page,
                "match_type": check.match_type,
                "expected_text": check.expected_text,
                "status": status,
                "matched_pdf_page_number": matched["pdf_page_number"] if matched else "",
                "matched_printed_page": matched["printed_page"] if matched else "",
                "matched_line_number_on_pdf_page": matched["line_number_on_pdf_page"] if matched else "",
                "matched_line_text": matched["line_text"] if matched else "",
                "source_note": check.source_note,
            }
        )
    return rows


def write_expected_text_checks(rows: list[dict[str, str]]) -> None:
    with EXPECTED_TEXT_CHECKS_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "source_file",
            "check_id",
            "guidebook_page",
            "match_type",
            "expected_text",
            "status",
            "matched_pdf_page_number",
            "matched_printed_page",
            "matched_line_number_on_pdf_page",
            "matched_line_text",
            "source_note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_corrections() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CORRECTIONS_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "source_file",
            "source_year",
            "source_title",
            "correction_type",
            "guidebook_page",
            "correction_date",
            "summary",
            "classification",
            "modeling_guardrail",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for correction in POST_PUBLICATION_CORRECTIONS:
            writer.writerow(
                {
                    "source_file": SOURCE_PATH,
                    "source_year": "2025",
                    "source_title": "2025 Utah Big Game Field Regulations",
                    "correction_type": correction.correction_type,
                    "guidebook_page": correction.guidebook_page,
                    "correction_date": correction.correction_date,
                    "summary": correction.summary,
                    "classification": "REGULATION_REFERENCE_ONLY",
                    "modeling_guardrail": "DO_NOT_USE_AS_DRAW_ODDS_HARVEST_FEATURE_OR_2026_QUOTA_INPUT",
                }
            )


def build_summary(
    line_rows: list[dict[str, str]],
    pdf_page_count: int,
    token_rows: list[dict[str, str]],
    expected_check_rows: list[dict[str, str]],
) -> dict[str, object]:
    source_exists = SOURCE_PDF.exists()
    source_hash = sha256(SOURCE_PDF) if source_exists else ""
    source_size = SOURCE_PDF.stat().st_size if source_exists else 0
    first_pages_text = " ".join(row["line_text"] for row in line_rows if int(row["pdf_page_number"]) <= 4)
    compact_text = compact_for_match(first_pages_text)

    raw_inventory_rows = [row for row in read_csv_rows(RAW_INVENTORY) if row.get("path") == SOURCE_PATH]
    raw_audit_rows = [row for row in read_csv_rows(RAW_AUDIT) if row.get("path") == SOURCE_PATH]
    manifest_items = read_manifest_items(HARD_COPY_MANIFEST)
    canonical_items = read_manifest_items(CANONICAL_HARD_COPIES)
    all_manifest_items = manifest_items + canonical_items

    field_reg_items = [
        item
        for item in all_manifest_items
        if "field" in json.dumps(item, sort_keys=True).lower()
        and "regulation" in json.dumps(item, sort_keys=True).lower()
    ]
    mislabeled_2026_items = [
        item
        for item in field_reg_items
        if "2026" in str(item.get("title", ""))
        or "/regulations/2026/" in str(item.get("href", ""))
        or "source_pdfs/regulations/2026" in str(item.get("href", ""))
    ]

    checks = {
        "source_pdf_exists": source_exists,
        "source_path_is_2025_folder": "/2025/" in SOURCE_PATH.replace("\\", "/"),
        "source_hash_matches_expected": source_hash == EXPECTED_SHA256,
        "source_size_matches_expected": source_size == EXPECTED_SIZE_BYTES,
        "text_mentions_2025_field_regulations": (
            "utah big game field regulations" in compact_text and "2025" in compact_text
        ),
        "text_does_not_identify_as_2026": "utah big game field regulations" in compact_text
        and "2026" not in compact_text[:500],
        "not_in_quality_raw_inventory": len(raw_inventory_rows) == 0,
        "not_promoted_by_quality_or_draw_audit": len(raw_audit_rows) == 0,
        "no_2026_field_regulations_manifest_label": len(mislabeled_2026_items) == 0,
    }

    status_counts = Counter("PASS" if passed else "REVIEW" for passed in checks.values())
    token_counts = Counter(row["token_type"] for row in token_rows)
    expected_failures = [row for row in expected_check_rows if row["status"] != "PASS"]
    return {
        "source_file": SOURCE_PATH,
        "expected_title": "2025 Utah Big Game Field Regulations",
        "expected_source_year": "2025",
        "actual_sha256": source_hash,
        "expected_sha256": EXPECTED_SHA256,
        "actual_size_bytes": source_size,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "classification": "REGULATION_REFERENCE_ONLY",
        "modeling_guardrail": "DO_NOT_USE_AS_DRAW_ODDS_HARVEST_FEATURE_OR_2026_QUOTA_INPUT",
        "source_inventory_status": "NOT_IN_QUALITY_RAW_INVENTORY",
        "library_export_status": "NOT_EXPORTED_TO_HUNTING_BIBLE",
        "post_publication_correction_count": len(POST_PUBLICATION_CORRECTIONS),
        "pdf_page_count": pdf_page_count,
        "text_line_count": len(line_rows),
        "number_token_count": len(token_rows),
        "token_type_counts": dict(token_counts),
        "expected_text_check_count": len(expected_check_rows),
        "expected_text_check_failures": len(expected_failures),
        "text_lines_output": str(TEXT_LINES_CSV.relative_to(ROOT)).replace("\\", "/"),
        "number_tokens_output": str(NUMBER_TOKENS_CSV.relative_to(ROOT)).replace("\\", "/"),
        "expected_text_checks_output": str(EXPECTED_TEXT_CHECKS_CSV.relative_to(ROOT)).replace("\\", "/"),
        "manifest_field_regulation_items_found": len(field_reg_items),
        "mislabeled_2026_manifest_items": len(mislabeled_2026_items),
        "checks": checks,
        "status_counts": dict(status_counts),
        "audit_blocker_count": status_counts.get("REVIEW", 0) + len(expected_failures),
    }


def write_markdown(summary: dict[str, object]) -> None:
    lines = [
        "# 2025 Big Game Field Regulations Source Label Audit",
        "",
        f"Source PDF: `{summary['source_file']}`",
        "",
        "This audit locks the file identity as 2025 field regulations only. It does not promote the file into draw odds, harvest features, quota math, or prediction math.",
        "",
        "## Summary",
        "",
        f"- Expected title: `{summary['expected_title']}`",
        f"- Expected source year: `{summary['expected_source_year']}`",
        f"- SHA-256: `{summary['actual_sha256']}`",
        f"- Library export status: `{summary['library_export_status']}`",
        f"- PDF pages: `{summary['pdf_page_count']}`",
        f"- Extracted text lines: `{summary['text_line_count']}`",
        f"- Extracted number/date/citation tokens: `{summary['number_token_count']}`",
        f"- Expected pasted-text checks: `{summary['expected_text_check_count']}`",
        f"- Expected pasted-text failures: `{summary['expected_text_check_failures']}`",
        f"- Mislabeled 2026 manifest items: `{summary['mislabeled_2026_manifest_items']}`",
        f"- Post-publication corrections captured: `{summary['post_publication_correction_count']}`",
        f"- Audit blockers: `{summary['audit_blocker_count']}`",
        "",
        "## Outputs",
        "",
        f"- Text lines: `{summary['text_lines_output']}`",
        f"- Number/date/citation tokens: `{summary['number_tokens_output']}`",
        f"- Pasted-text checks: `{summary['expected_text_checks_output']}`",
        "",
        "## Checks",
        "",
        "| check | status |",
        "|---|---:|",
    ]
    for check, passed in summary["checks"].items():
        lines.append(f"| {check} | {'PASS' if passed else 'REVIEW'} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_corrections()
    line_rows, pdf_page_count = extract_pdf_lines(SOURCE_PDF) if SOURCE_PDF.exists() else ([], 0)
    write_pdf_lines(line_rows)
    token_rows = extract_number_tokens(line_rows)
    write_number_tokens(token_rows)
    expected_check_rows = run_expected_text_checks(line_rows)
    write_expected_text_checks(expected_check_rows)
    summary = build_summary(line_rows, pdf_page_count, token_rows, expected_check_rows)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
