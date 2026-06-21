from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pdfplumber


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
PDF_ROOT = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2025\.pdf")
TARGET = REPO / r"data_truth\draw_results_truth\normalized\draw_results_2025_for_2026_candidate_promotion_file_records.csv"
OUT_DIR = REPO / r"audits\truth_document_audit\rebuild_2025_le_oil_from_uploaded_pdfs"
BACKUP_DIR = OUT_DIR / "backups"

SOURCE_YEAR = "2025"
MODEL_YEAR = "2026"

SOURCE_PDFS = [
    "2025_PERMITS=2026_MODEL__L.E. BUCK DEER DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__L.E. BUCK PRONGHORN DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__L.E. BULL ELK DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. BISON DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. BULL MOOSE DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. DESERT BIGHORN SHEEP DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. MTN GOAT DRAW RESULTS.pdf",
    "2025_PERMITS=2026_MODEL__O.I.L. ROCKY MTN SHEEP DRAW RESULTS.pdf",
]

COMPACT_FIELDS = [
    "source_year",
    "model_year",
    "source_scope",
    "source_pdf",
    "pdf_page",
    "hunt_code",
    "family",
    "raw_hunt_name",
    "residency",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "record_type",
    "extraction_status",
    "parse_method",
]

SCOPE_BY_FILE_TOKEN = {
    "L.E. BUCK DEER": "LIMITED_ENTRY_DEER",
    "L.E. BULL ELK": "LIMITED_ENTRY_ELK",
    "L.E. BUCK PRONGHORN": "LIMITED_ENTRY_PRONGHORN",
    "O.I.L. BISON": "OIL_BISON",
    "O.I.L. BULL MOOSE": "OIL_BULL_MOOSE",
    "O.I.L. DESERT BIGHORN SHEEP": "OIL_DESERT_BIGHORN_SHEEP",
    "O.I.L. MTN GOAT": "OIL_MTN_GOAT",
    "O.I.L. ROCKY MTN SHEEP": "OIL_ROCKY_MTN_SHEEP",
}

SPECIES_BY_SCOPE = {
    "LIMITED_ENTRY_DEER": ("Deer", "Buck", "L.E."),
    "LIMITED_ENTRY_ELK": ("Elk", "Bull", "L.E."),
    "LIMITED_ENTRY_PRONGHORN": ("Pronghorn", "Buck", "L.E."),
    "OIL_BISON": ("Bison", "Either Sex", "O.I.L."),
    "OIL_BULL_MOOSE": ("Moose", "Bull", "O.I.L."),
    "OIL_DESERT_BIGHORN_SHEEP": ("Desert Bighorn Sheep", "Ram", "O.I.L."),
    "OIL_MTN_GOAT": ("Mountain Goat", "Either Sex", "O.I.L."),
    "OIL_ROCKY_MTN_SHEEP": ("Rocky Mountain Bighorn Sheep", "Ram", "O.I.L."),
}


def clean(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u2019", "'")).strip()


def source_scope_for_pdf(name: str) -> str:
    upper = name.upper()
    for token, scope in SCOPE_BY_FILE_TOKEN.items():
        if token in upper:
            return scope
    return "UNKNOWN_REVIEW"


def parse_hunt_header(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"Hunt:\s*([A-Z]{2}\d{4})\s+(.+?)(?:\s+Page\s+\d+|\nResident Applicants|\nNonresident Applicants|\nNon-Resident Applicants|\Z)",
        text.replace("\u2019", "'"),
        re.I | re.S,
    )
    if not match:
        return None
    return match.group(1).upper(), clean(match.group(2))


def nonempty_tokens(row: list[object]) -> list[str]:
    return [clean(cell) for cell in row if clean(cell)]


def is_point(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}", value))


def parse_table_row(tokens: list[str]) -> tuple[list[str], list[str]] | None:
    if len(tokens) < 12:
        return None
    if tokens[0].lower() == "totals":
        return None
    if is_point(tokens[0]) and is_point(tokens[6]):
        return tokens[0:6], tokens[6:12]
    return None


def compact_row(scope: str, source_pdf: str, pdf_page: int, hunt_code: str, hunt_name: str, residency: str, values: list[str]) -> dict[str, str]:
    family_match = re.match(r"^[A-Z]+", hunt_code)
    return {
        "source_year": SOURCE_YEAR,
        "model_year": MODEL_YEAR,
        "source_scope": scope,
        "source_pdf": source_pdf,
        "pdf_page": str(pdf_page),
        "hunt_code": hunt_code,
        "family": family_match.group(0) if family_match else "",
        "raw_hunt_name": hunt_name,
        "residency": residency,
        "points": str(int(values[0])),
        "eligible_applicants": values[1],
        "bonus_permits": values[2],
        "regular_permits": values[3],
        "total_permits": values[4],
        "success_ratio": values[5],
        "record_type": "POINT_ROW",
        "extraction_status": "OK",
        "parse_method": "PDFPLUMBER_2025_LE_OIL_UPLOADED_PDF_KEEP_ZERO_ROWS",
    }


def extract_pdf(path: Path) -> tuple[list[dict[str, str]], list[dict[str, object]], list[dict[str, object]]]:
    scope = source_scope_for_pdf(path.name)
    rows: list[dict[str, str]] = []
    page_audit: list[dict[str, object]] = []
    rejects: list[dict[str, object]] = []
    with pdfplumber.open(path) as doc:
        for page in doc.pages:
            text = page.extract_text() or ""
            header = parse_hunt_header(text)
            tables = page.extract_tables()
            page_rows = 0
            if header and tables:
                hunt_code, hunt_name = header
                for table_index, table in enumerate(tables):
                    for row_index, table_row in enumerate(table):
                        tokens = nonempty_tokens(table_row)
                        parsed = parse_table_row(tokens)
                        if not parsed:
                            if tokens and any(is_point(token) for token in tokens):
                                rejects.append(
                                    {
                                        "source_pdf": path.name,
                                        "pdf_page": page.page_number,
                                        "table_index": table_index,
                                        "row_index": row_index,
                                        "hunt_code": hunt_code,
                                        "reason": "POINT_LIKE_ROW_NOT_STANDARD_12_TOKEN_SHAPE",
                                        "tokens": " | ".join(tokens),
                                    }
                                )
                            continue
                        resident, nonresident = parsed
                        rows.append(compact_row(scope, path.name, page.page_number, hunt_code, hunt_name, "Resident", resident))
                        rows.append(compact_row(scope, path.name, page.page_number, hunt_code, hunt_name, "Nonresident", nonresident))
                        page_rows += 2
            page_audit.append(
                {
                    "source_pdf": path.name,
                    "pdf_page": page.page_number,
                    "source_scope": scope,
                    "hunt_code": header[0] if header else "",
                    "raw_hunt_name": header[1] if header else "",
                    "tables_found": len(tables),
                    "point_rows_extracted": page_rows,
                }
            )
    return rows, page_audit, rejects


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> bool:
    try:
        from openpyxl import Workbook
    except Exception:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "rows"
    sheet.append(fieldnames)
    for row in rows:
        sheet.append([row.get(field, "") for field in fieldnames])
    workbook.save(path)
    return True


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def duplicate_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("hunt_code", ""),
        row.get("residency", ""),
        row.get("points", ""),
        row.get("record_type", row.get("record_kind", "")),
    )


def current_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("hunt_code", ""),
        row.get("residency", ""),
        row.get("points", ""),
        row.get("record_kind") or row.get("record_type") or "",
    )


def to_float_text(value: str) -> str:
    text = clean(value).replace(",", "")
    if text == "":
        return ""
    try:
        return f"{float(text):.1f}"
    except ValueError:
        return text


def percent_from_success(value: str) -> str:
    match = re.search(r"\b1\s+in\s+([0-9]+(?:\.[0-9]+)?)", value or "", re.I)
    if not match:
        return ""
    denominator = float(match.group(1))
    if denominator <= 0:
        return ""
    return f"{100.0 / denominator:.8f}"


def conform_row(compact: dict[str, str], fieldnames: list[str]) -> dict[str, str]:
    scope = compact["source_scope"]
    species, sex_type, hunt_type = SPECIES_BY_SCOPE.get(scope, ("", "", ""))
    row = {field: "" for field in fieldnames}
    values = {
        "record_kind": "POINT_ROW",
        "source_dataset": "official_2025_le_oil_pdf_rebuild",
        "reported_draw_year": SOURCE_YEAR,
        "model_target_year": MODEL_YEAR,
        "source_record_id": f"2025_LE_OIL::{compact['hunt_code']}::{compact['residency']}::{compact['points']}",
        "candidate_promotion_status": "PDF_GROUNDED_PROMOTED_CANDIDATE",
        "candidate_promotion_reason": f"Promoted from canonical uploaded 2025 PDF rebuild for {scope}; no values inferred.",
        "hunt_code": compact["hunt_code"],
        "hunt_name": compact["raw_hunt_name"],
        "raw_hunt_name": compact["raw_hunt_name"],
        "species": species,
        "sex_type": sex_type,
        "hunt_type": hunt_type,
        "hunt_class": hunt_type,
        "weapon": "Any Legal Weapon" if "Any Legal Weapon" in compact["raw_hunt_name"] else "",
        "year": SOURCE_YEAR,
        "actual_draw_year": SOURCE_YEAR,
        "draw_pool": "standard",
        "residency": compact["residency"],
        "points": compact["points"],
        "eligible_applicants": to_float_text(compact["eligible_applicants"]),
        "bonus_permits": to_float_text(compact["bonus_permits"]),
        "regular_permits": to_float_text(compact["regular_permits"]),
        "total_permits": to_float_text(compact["total_permits"]),
        "total_drawn": to_float_text(compact["total_permits"]),
        "success_ratio": compact["success_ratio"],
        "p_draw_percent": percent_from_success(compact["success_ratio"]),
        "draw_type": "Draw 5",
        "draw_method": "BONUS",
        "status": "OK",
        "source_file": compact["source_pdf"],
        "source_pdf_page": compact["pdf_page"],
        "page_number": compact["pdf_page"],
        "metadata_status": "PDF_REBUILT",
        "source_classification": scope,
        "source_report_family": scope,
        "normalized_family": "LE" if scope.startswith("LIMITED_ENTRY") else "OIL",
        "normalized_species_family": species.upper().replace(" ", "_"),
        "normalized_age_class": "ADULT",
    }
    for field, value in values.items():
        if field in row:
            row[field] = value
    return row


def promote_if_solid(candidate_rows: list[dict[str, str]], current_fields: list[str], current_rows: list[dict[str, str]], status: dict[str, object]) -> dict[str, object]:
    code_set = {row["hunt_code"] for row in candidate_rows}
    current_replaced = [row for row in current_rows if row.get("hunt_code") in code_set and (row.get("record_kind") or row.get("record_type")) == "POINT_ROW"]
    candidate_conformed = [conform_row(row, current_fields) for row in candidate_rows]
    if status["status"] != "PASS_CANDIDATE_READY_FOR_PROMOTION":
        return {
            "promoted": False,
            "reason": "candidate_status_not_pass",
            "current_replaced_rows": len(current_replaced),
            "candidate_conformed_rows": len(candidate_conformed),
        }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"draw_results_2025_for_2026_candidate_promotion_file_records.csv.backup_before_2025_le_oil_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)
    remaining = [row for row in current_rows if not (row.get("hunt_code") in code_set and (row.get("record_kind") or row.get("record_type")) == "POINT_ROW")]
    promoted = remaining + candidate_conformed
    write_csv(TARGET, promoted, current_fields)
    write_csv(OUT_DIR / "removed_2025_le_oil_rows_replaced_by_pdf_rebuild.csv", current_replaced, current_fields)
    write_csv(OUT_DIR / "promoted_2025_le_oil_pdf_rebuilt_rows.csv", candidate_conformed, current_fields)
    return {
        "promoted": True,
        "backup_path": str(backup_path),
        "current_replaced_rows": len(current_replaced),
        "candidate_conformed_rows": len(candidate_conformed),
        "final_rows": len(promoted),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, str]] = []
    page_audit: list[dict[str, object]] = []
    rejects: list[dict[str, object]] = []
    file_summary: list[dict[str, object]] = []
    for name in SOURCE_PDFS:
        path = PDF_ROOT / name
        before = len(all_rows)
        before_rejects = len(rejects)
        rows, pages, pdf_rejects = extract_pdf(path)
        all_rows.extend(rows)
        page_audit.extend(pages)
        rejects.extend(pdf_rejects)
        file_summary.append(
            {
                "source_pdf": name,
                "exists": path.exists(),
                "source_scope": source_scope_for_pdf(name),
                "rows": len(all_rows) - before,
                "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
                "rejects": len(rejects) - before_rejects,
            }
        )

    dupes = [
        {
            "hunt_code": key[0],
            "residency": key[1],
            "points": key[2],
            "record_type": key[3],
            "count": count,
        }
        for key, count in sorted(Counter(duplicate_key(row) for row in all_rows).items())
        if count > 1
    ]

    current_fields, current_rows = read_rows(TARGET)
    code_set = {row["hunt_code"] for row in all_rows}
    current_replaced = [row for row in current_rows if row.get("hunt_code") in code_set and (row.get("record_kind") or row.get("record_type")) == "POINT_ROW"]
    current_keys = {current_key(row) for row in current_replaced}
    candidate_keys = {duplicate_key(row) for row in all_rows}

    scope_rows = []
    for scope, group in sorted(defaultdict(list, {s: [r for r in all_rows if r["source_scope"] == s] for s in {r["source_scope"] for r in all_rows}}).items()):
        scope_rows.append(
            {
                "source_scope": scope,
                "rows": len(group),
                "unique_hunt_codes": len({row["hunt_code"] for row in group}),
                "min_points": min(int(row["points"]) for row in group),
                "max_points": max(int(row["points"]) for row in group),
            }
        )

    status = {
        "generated_at": datetime.now().isoformat(),
        "source_pdf_root": str(PDF_ROOT),
        "candidate_rows": len(all_rows),
        "candidate_unique_hunt_codes": len(code_set),
        "candidate_duplicate_key_groups": len(dupes),
        "candidate_blank_hunt_code_rows": sum(1 for row in all_rows if not row.get("hunt_code")),
        "current_rows_for_same_hunt_codes": len(current_replaced),
        "candidate_only_keys_vs_current_same_codes": len(candidate_keys - current_keys),
        "current_only_keys_vs_candidate_same_codes": len(current_keys - candidate_keys),
        "rejected_point_like_rows": len(rejects),
        "scope_summary": scope_rows,
        "status": "PASS_CANDIDATE_READY_FOR_PROMOTION",
    }
    if not all_rows or dupes or status["candidate_blank_hunt_code_rows"]:
        status["status"] = "REVIEW_REQUIRED"
    # A row-count collapse against existing same-code rows is a hard stop.
    if len(all_rows) + 100 < len(current_replaced):
        status["status"] = "REVIEW_REQUIRED_ROW_COUNT_DROP"

    write_csv(OUT_DIR / "draw_results_2025_for_2026_LE_OIL_UPLOADED_PDFS_CANDIDATE_NOT_APPLIED.csv", all_rows, COMPACT_FIELDS)
    write_xlsx(OUT_DIR / "draw_results_2025_for_2026_LE_OIL_UPLOADED_PDFS_CANDIDATE_NOT_APPLIED.xlsx", all_rows, COMPACT_FIELDS)
    write_csv(OUT_DIR / "2025_le_oil_uploaded_pdf_page_audit.csv", page_audit, ["source_pdf", "pdf_page", "source_scope", "hunt_code", "raw_hunt_name", "tables_found", "point_rows_extracted"])
    write_csv(OUT_DIR / "2025_le_oil_uploaded_pdf_file_summary.csv", file_summary, ["source_pdf", "exists", "source_scope", "rows", "unique_hunt_codes", "rejects"])
    write_csv(OUT_DIR / "2025_le_oil_uploaded_pdf_scope_summary.csv", scope_rows, ["source_scope", "rows", "unique_hunt_codes", "min_points", "max_points"])
    write_csv(OUT_DIR / "2025_le_oil_uploaded_pdf_duplicate_keys.csv", dupes, ["hunt_code", "residency", "points", "record_type", "count"])
    write_csv(OUT_DIR / "2025_le_oil_uploaded_pdf_rejected_point_like_rows.csv", rejects, ["source_pdf", "pdf_page", "table_index", "row_index", "hunt_code", "reason", "tokens"])

    promotion = promote_if_solid(all_rows, current_fields, current_rows, status)
    status["promotion"] = promotion
    status_path = OUT_DIR / "REBUILD_PROMOTE_2025_LE_OIL_FROM_UPLOADED_PDFS_STATUS.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    report_path = OUT_DIR / "REBUILD_PROMOTE_2025_LE_OIL_FROM_UPLOADED_PDFS_REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# 2025 LE/OIL Uploaded PDF Rebuild",
                "",
                f"- Candidate rows: {status['candidate_rows']}",
                f"- Candidate unique hunt codes: {status['candidate_unique_hunt_codes']}",
                f"- Duplicate key groups: {status['candidate_duplicate_key_groups']}",
                f"- Current same-code rows replaced: {promotion['current_replaced_rows']}",
                f"- Promotion applied: {promotion['promoted']}",
                f"- Final status: `{status['status']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
