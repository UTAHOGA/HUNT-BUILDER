from __future__ import annotations

import csv
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

import pdfplumber


REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_CSV = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
PDF_PATH = Path(
    r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\.pdf\2026_PERMITS=2027_MODEL__G.S. BUCK DEER DRAW RESULTS.pdf"
)
AUDIT_CSV = REPO_ROOT / "processed_data" / "audits" / "gs_buck_deer_2026_pdf_database_patch.csv"
BACKUP_DIR = REPO_ROOT / "processed_data" / "backups"

SOURCE_LABEL = "2026_GS_BUCK_DEER_DRAW_RESULTS_PDF_TOTAL_ONLY_PREFERENCE_PERMITS"
LEGACY_MIRROR_STATUS = "LEGACY_COMPAT_MIRROR_OF_PERMITS_2026"


def clean_int(value: object) -> int:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text:
        return 0
    return int(float(text))


def extract_pdf_permits() -> dict[str, dict[str, object]]:
    extracted: dict[str, dict[str, object]] = {}
    hunt_pattern = re.compile(r"^Hunt:\s+(DB\d{4})\s+(.+)$", re.MULTILINE)

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            match = hunt_pattern.search(text)
            if not match:
                continue

            hunt_code = match.group(1).strip()
            hunt_title = match.group(2).strip()
            totals = defaultdict(int)
            table_labels: list[str] = []

            for table in page.extract_tables() or []:
                if not table or not table[0] or not table[0][0]:
                    continue
                label = str(table[0][0]).replace("\n", " ").strip()
                label_lower = label.lower()
                if label_lower.startswith("nonresident"):
                    residency = "nr"
                elif label_lower.startswith("resident"):
                    residency = "res"
                else:
                    continue

                for row in table:
                    if row and str(row[0]).strip().lower() == "totals":
                        totals[residency] += clean_int(row[4] if len(row) > 4 else "")
                        table_labels.append(label)
                        break

            if totals:
                extracted[hunt_code] = {
                    "pdf_page": page_number,
                    "pdf_hunt_title": hunt_title,
                    "pdf_res": totals["res"],
                    "pdf_nr": totals["nr"],
                    "pdf_total": totals["res"] + totals["nr"],
                    "pdf_tables_used": "; ".join(table_labels),
                }

    return extracted


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)
    if not DATABASE_CSV.exists():
        raise FileNotFoundError(DATABASE_CSV)

    pdf_permits = extract_pdf_permits()
    if not pdf_permits:
        raise RuntimeError("No DB hunt-code permit totals were extracted from the PDF.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"DATABASE_before_gs_buck_deer_pdf_patch_{timestamp}.csv"
    shutil.copy2(DATABASE_CSV, backup_path)

    with DATABASE_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    audit_rows = []
    found_codes = set()
    for row in rows:
        hunt_code = row.get("hunt_code", "").strip()
        data = pdf_permits.get(hunt_code)
        if not data:
            continue

        found_codes.add(hunt_code)
        old_res = row.get("permits_2026_res", "")
        old_nr = row.get("permits_2026_nr", "")
        old_total = row.get("permits_2026_total", "")

        # General-season preference hunts have one total permit number. The PDF
        # tables split applicants/results by residency, but the permit authority
        # for these hunts is total-only.
        new_res = ""
        new_nr = ""
        new_total = str(data["pdf_total"])
        changed = (old_res, old_nr, old_total) != (new_res, new_nr, new_total)

        row["permits_2026_res"] = new_res
        row["permits_2026_nr"] = new_nr
        row["permits_2026_total"] = new_total
        row["permits_2026_source"] = SOURCE_LABEL
        row["permits_2026_draw_source"] = PDF_PATH.name

        # Keep legacy allotment fields mirrored so runtime compatibility columns cannot drift.
        row["permit_allotment_2026_res"] = new_res
        row["permit_allotment_2026_nr"] = new_nr
        row["permit_allotment_2026_total"] = new_total
        row["permit_allotment_2026_source"] = SOURCE_LABEL
        row["permit_allotment_2026_source_file"] = PDF_PATH.name
        row["permit_allotment_2026_status"] = LEGACY_MIRROR_STATUS

        audit_rows.append(
            {
                "hunt_code": hunt_code,
                "hunt_name": row.get("hunt_name", ""),
                "weapon": row.get("weapon", ""),
                "hunt_type": row.get("hunt_type", ""),
                "hunt_class": row.get("hunt_class", ""),
                "pdf_page": data["pdf_page"],
                "pdf_hunt_title": data["pdf_hunt_title"],
                "old_res": old_res,
                "old_nr": old_nr,
                "old_total": old_total,
                "new_res": new_res,
                "new_nr": new_nr,
                "new_total": new_total,
                "changed": "YES" if changed else "NO",
                "pdf_tables_used": data["pdf_tables_used"],
            }
        )

    missing_from_database = sorted(set(pdf_permits) - found_codes)
    if missing_from_database:
        for hunt_code in missing_from_database:
            data = pdf_permits[hunt_code]
            audit_rows.append(
                {
                    "hunt_code": hunt_code,
                    "hunt_name": "",
                    "weapon": "",
                    "hunt_type": "",
                    "hunt_class": "",
                    "pdf_page": data["pdf_page"],
                    "pdf_hunt_title": data["pdf_hunt_title"],
                    "old_res": "",
                    "old_nr": "",
                    "old_total": "",
                    "new_res": data["pdf_res"],
                    "new_nr": data["pdf_nr"],
                    "new_total": data["pdf_total"],
                    "changed": "PDF_CODE_NOT_IN_DATABASE",
                    "pdf_tables_used": data["pdf_tables_used"],
                }
            )

    with DATABASE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    audit_fields = [
        "hunt_code",
        "hunt_name",
        "weapon",
        "hunt_type",
        "hunt_class",
        "pdf_page",
        "pdf_hunt_title",
        "old_res",
        "old_nr",
        "old_total",
        "new_res",
        "new_nr",
        "new_total",
        "changed",
        "pdf_tables_used",
    ]
    with AUDIT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    changed_count = sum(1 for row in audit_rows if row["changed"] == "YES")
    print(f"PDF hunt codes extracted: {len(pdf_permits)}")
    print(f"Database rows updated from PDF: {len(found_codes)}")
    print(f"Rows with numeric changes: {changed_count}")
    print(f"PDF codes missing from DATABASE: {len(missing_from_database)}")
    print(f"Backup: {backup_path}")
    print(f"Audit: {AUDIT_CSV}")


if __name__ == "__main__":
    main()
