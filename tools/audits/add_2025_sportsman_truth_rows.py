from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pdfplumber


REPO = Path(r"C:\Users\tyler\Desktop\GitHub\HUNT-BUILDER")
TARGET = REPO / "data_truth/draw_results_truth/normalized/draw_results_2025_for_2026_candidate_promotion_file_records.csv"
PDF = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2025\.pdf\2025_PERMITS=2026_MODEL__SPORTSMAN PERMITS DRAW RESULTS.pdf")
OUT_DIR = REPO / "audits/truth_document_audit/add_2025_sportsman_truth_rows"
BACKUP_DIR = OUT_DIR / "backups"


SPORTSMAN_TRAITS = {
    "BI1000": ("Bison", "Either Sex"),
    "BR1000": ("Black Bear", "Either Sex"),
    "DB0007": ("Deer", "Buck"),
    "DS1000": ("Desert Bighorn Sheep", "Ram"),
    "EB1000": ("Elk", "Bull"),
    "GO1000": ("Mountain Goat", "Either Sex"),
    "MB1000": ("Moose", "Bull"),
    "PB1000": ("Pronghorn", "Buck"),
    "RS0001": ("Rocky Mountain Bighorn Sheep", "Ram"),
    "TK0001": ("Turkey", "Bearded"),
}


def clean(value: object) -> str:
    return "" if value is None else re.sub(r"\s+", " ", str(value)).strip()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def p_draw_percent(success_ratio: str) -> str:
    match = re.search(r"\b1\s+in\s+([0-9,]+(?:\.[0-9]+)?)", success_ratio, re.I)
    if not match:
        return ""
    denominator = float(match.group(1).replace(",", ""))
    if denominator <= 0:
        return ""
    return f"{100.0 / denominator:.8f}"


def extract_sportsman_rows() -> list[dict[str, str]]:
    extracted: list[dict[str, str]] = []
    with pdfplumber.open(PDF) as doc:
        for page in doc.pages:
            text = page.extract_text() or ""
            header = re.search(r"Hunt:\s*([A-Z]{2}\d{4})\s+(.+?)(?:\nResident|\Z)", text, re.S)
            if not header:
                continue
            code = header.group(1).upper()
            hunt_name = clean(header.group(2))
            tables = page.extract_tables() or []
            resident_row = None
            for table in tables:
                for row in table:
                    tokens = [clean(cell) for cell in row if clean(cell)]
                    if len(tokens) == 6 and tokens[0] == "0" and tokens[1].replace(",", "").isdigit():
                        resident_row = tokens
                        break
                if resident_row:
                    break
            if not resident_row:
                continue
            species, sex_type = SPORTSMAN_TRAITS.get(code, ("", ""))
            extracted.append(
                {
                    "hunt_code": code,
                    "hunt_name": hunt_name,
                    "raw_hunt_name": hunt_name,
                    "species": species,
                    "sex_type": sex_type,
                    "eligible_applicants": resident_row[1].replace(",", ""),
                    "bonus_permits": resident_row[2].replace(",", ""),
                    "regular_permits": resident_row[3].replace(",", ""),
                    "total_permits": resident_row[4].replace(",", ""),
                    "success_ratio": resident_row[5],
                    "p_draw_percent": p_draw_percent(resident_row[5]),
                    "source_pdf_page": str(page.page_number),
                }
            )
    return extracted


def set_if_present(row: dict[str, str], field: str, value: str) -> None:
    if field in row:
        row[field] = value


def conform(source: dict[str, str], fields: list[str]) -> dict[str, str]:
    row = {field: "" for field in fields}
    values = {
        "record_kind": "SPORTSMAN_TOTAL",
        "source_dataset": "official_2025_sportsman_pdf_truth",
        "reported_draw_year": "2025",
        "model_target_year": "2026",
        "actual_draw_year": "2025",
        "source_record_id": f"2025_SPORTSMAN::{source['hunt_code']}",
        "candidate_promotion_status": "PDF_GROUNDED_PROMOTED_CANDIDATE",
        "candidate_promotion_reason": "Added source-backed 2025 Sportsman separate-lane total row; not an ordinary point-ladder prediction row.",
        "hunt_code": source["hunt_code"],
        "hunt_name": source["hunt_name"],
        "raw_hunt_name": source["raw_hunt_name"],
        "species": source["species"],
        "sex_type": source["sex_type"],
        "hunt_type": "Sportsman",
        "hunt_class": "Sportsman",
        "weapon": "Any Legal Weapon",
        "year": "2025",
        "draw_pool": "sportsman",
        "draw_method": "SPORTSMAN_RANDOM_ONLY",
        "residency": "Resident",
        "points": "",
        "eligible_applicants": source["eligible_applicants"],
        "bonus_permits": source["bonus_permits"],
        "regular_permits": source["regular_permits"],
        "total_permits": source["total_permits"],
        "total_drawn": source["total_permits"],
        "success_ratio": source["success_ratio"],
        "p_draw_percent": source["p_draw_percent"],
        "source_file": PDF.name,
        "source_pdf_page": source["source_pdf_page"],
        "page_number": source["source_pdf_page"],
        "pdf_page_number": source["source_pdf_page"],
        "source_report_page": source["source_pdf_page"],
        "source_family": "SPORTSMAN",
        "source_classification": "SPORTSMAN",
        "source_class": "SPORTSMAN",
        "source_report_family": "SPORTSMAN",
        "validation_status": "OK",
        "normalization_status": "SPORTSMAN_SEPARATE_LANE_ADDED_2025",
        "metadata_status": "SPORTSMAN_SEPARATE_LANE_ADDED_2025",
        "normalized_family": "SPORTSMAN_RANDOM_ONLY",
        "normalized_species_family": source["species"].upper().replace(" ", "_"),
        "normalized_age_class": "ADULT",
    }
    for field, value in values.items():
        set_if_present(row, field, value)
    return row


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields, rows = read_rows(TARGET)
    if "actual_draw_year" not in fields:
        fields.append("actual_draw_year")
    if "source_report_family" not in fields:
        fields.append("source_report_family")
    for row in rows:
        row.setdefault("actual_draw_year", "")
        row.setdefault("source_report_family", "")

    extracted = extract_sportsman_rows()
    existing_codes = {
        clean(row.get("hunt_code")).upper()
        for row in rows
        if clean(row.get("normalized_family")) == "SPORTSMAN_RANDOM_ONLY" or clean(row.get("source_classification")) == "SPORTSMAN"
    }
    to_add = [row for row in extracted if row["hunt_code"] not in existing_codes]
    conformed = [conform(row, fields) for row in to_add]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{TARGET.name}.backup_before_2025_sportsman_rows_{stamp}.csv"
    shutil.copy2(TARGET, backup_path)

    final_rows = rows + conformed
    write_csv(TARGET, final_rows, fields)
    write_csv(OUT_DIR / "2025_sportsman_pdf_extracted_rows.csv", extracted, [
        "hunt_code",
        "hunt_name",
        "raw_hunt_name",
        "species",
        "sex_type",
        "eligible_applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
        "success_ratio",
        "p_draw_percent",
        "source_pdf_page",
    ])
    write_csv(OUT_DIR / "2025_sportsman_rows_added.csv", conformed, fields)
    status = {
        "generated_at": datetime.now().isoformat(),
        "target": str(TARGET),
        "backup_path": str(backup_path),
        "rows_before": len(rows),
        "extracted_sportsman_rows": len(extracted),
        "existing_sportsman_codes": sorted(existing_codes),
        "added_sportsman_rows": len(conformed),
        "rows_after": len(final_rows),
        "added_codes": [row["hunt_code"] for row in to_add],
        "numeric_fields_changed_for_existing_rows": False,
        "status": "PASS_SPORTSMAN_ROWS_ADDED" if len(extracted) == 10 and len(final_rows) == len(rows) + len(conformed) else "REVIEW_REQUIRED",
    }
    (OUT_DIR / "ADD_2025_SPORTSMAN_TRUTH_ROWS_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
