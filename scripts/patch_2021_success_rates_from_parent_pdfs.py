import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data_truth" / "finalized_point_distribution.csv"
OUT = ROOT / "audits" / "prediction_validation" / "patch_2021_success_rates_from_parent_pdfs"
BACKUP_DIR = OUT / "backups"

PDF_SOURCES = [
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_bg-odds.pdf"),
        "source_file": "21_bg-odds.pdf",
        "source_label": "2021_BIG_GAME_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021 Antlerless Draw Results.pdf"),
        "source_file": "2021 Antlerless Draw Results.pdf",
        "source_label": "2021_ANTLERLESS_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_antlerless_drawing_odds_report.pdf"),
        "source_file": "21_youth_antlerless_drawing_odds_report.pdf",
        "source_label": "2021_YOUTH_ANTLERLESS_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021 Bear Draw Results.pdf"),
        "source_file": "2021 Bear Draw Results.pdf",
        "source_label": "2021_BEAR_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_cougar_odds_report.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__COUGAR DRAW RESULTS.pdf",
        "source_label": "2021_COUGAR_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_turkey_bonus_points_draw_results.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__TURKEY DRAW RESULTS.pdf",
        "source_label": "2021_TURKEY_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_youth_turkey_draw_results.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
        "source_label": "2021_YOUTH_TURKEY_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_deer_odds.pdf"),
        "source_file": "21_deer_odds.pdf",
        "source_label": "2021_GENERAL_SEASON_DEER_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_dh_odds.pdf"),
        "source_file": "21_dh_odds.pdf",
        "source_label": "2021_DEDICATED_HUNTER_DEER_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_lifetime_deer.pdf"),
        "source_file": "21_lifetime_deer.pdf",
        "source_label": "2021_LIFETIME_GENERAL_SEASON_DEER_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_bull_elk.pdf"),
        "source_file": "21_youth_bull_elk.pdf",
        "source_label": "2021_YOUTH_BULL_ELK_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_deer.pdf"),
        "source_file": "21_youth_deer.pdf",
        "source_label": "2021_YOUTH_GENERAL_SEASON_DEER_PARENT",
    },
    {
        "pdf": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_dh_odds.pdf"),
        "source_file": "21_youth_dh_odds.pdf",
        "source_label": "2021_YOUTH_DEDICATED_HUNTER_DEER_PARENT",
    },
]

HUNT_RE = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+?)(?:\s+Page\s+\d+)?$", re.IGNORECASE)
ROW_RE = re.compile(
    r"^\s*"
    r"(?P<r_points>\d+)\s+(?P<r_apps>[\d,]+)\s+(?P<r_bonus>[\d,]+)\s+(?P<r_regular>[\d,]+)\s+(?P<r_total>[\d,]+)\s+(?P<r_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s+"
    r"(?P<n_points>\d+)\s+(?P<n_apps>[\d,]+)\s+(?P<n_bonus>[\d,]+)\s+(?P<n_regular>[\d,]+)\s+(?P<n_total>[\d,]+)\s+(?P<n_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s*$",
    re.IGNORECASE,
)


def clean(value):
    return "" if value is None else str(value).strip()


def norm_int_text(value):
    text = clean(value).replace(",", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def norm_residency(value):
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"r", "res", "resident"}:
        return "Resident"
    if text in {"nr", "nonres", "nonresident"}:
        return "Nonresident"
    return clean(value)


def ratio_to_success_rate(ratio):
    ratio = clean(ratio)
    if not ratio or ratio.upper() == "N/A":
        return ""
    match = re.search(r"1\s+in\s+([\d.]+)", ratio, re.IGNORECASE)
    if not match:
        return ""
    denominator = float(match.group(1))
    if denominator == 0:
        return ""
    return f"{100.0 / denominator:.8f}".rstrip("0").rstrip(".")


def extract_pdf_rows(source):
    rows = []
    current_hunt_code = ""
    current_hunt_name = ""
    with pdfplumber.open(str(source["pdf"])) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            for line in text.splitlines():
                hunt_match = HUNT_RE.search(line)
                if hunt_match:
                    current_hunt_code = hunt_match.group(1).upper()
                    current_hunt_name = hunt_match.group(2).strip()
                    continue
                row_match = ROW_RE.match(line)
                if not row_match or not current_hunt_code:
                    continue
                data = row_match.groupdict()
                for prefix, residency in (("r", "Resident"), ("n", "Nonresident")):
                    ratio = data[f"{prefix}_ratio"]
                    success_rate = ratio_to_success_rate(ratio)
                    rows.append(
                        {
                            "year": "2021",
                            "model_year": "2022",
                            "hunt_code": current_hunt_code,
                            "hunt_name_from_pdf": current_hunt_name,
                            "residency": residency,
                            "point_level": norm_int_text(data[f"{prefix}_points"]),
                            "pdf_applicants": norm_int_text(data[f"{prefix}_apps"]),
                            "pdf_bonus_permits": norm_int_text(data[f"{prefix}_bonus"]),
                            "pdf_regular_permits": norm_int_text(data[f"{prefix}_regular"]),
                            "pdf_permits": norm_int_text(data[f"{prefix}_total"]),
                            "pdf_success_ratio": ratio,
                            "pdf_success_rate": success_rate,
                            "pdf_page": page_index,
                            "source_file": source["source_file"],
                            "source_label": source["source_label"],
                        }
                    )
    return rows


def key_for(row):
    return (
        clean(row.get("year")),
        clean(row.get("hunt_code")).upper(),
        norm_residency(row.get("residency")),
        norm_int_text(row.get("point_level")),
        clean(row.get("source_file")),
    )


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    pdf_rows = []
    for source in PDF_SOURCES:
        if not source["pdf"].exists():
            raise FileNotFoundError(source["pdf"])
        pdf_rows.extend(extract_pdf_rows(source))

    pdf_fields = [
        "year",
        "model_year",
        "hunt_code",
        "hunt_name_from_pdf",
        "residency",
        "point_level",
        "pdf_applicants",
        "pdf_bonus_permits",
        "pdf_regular_permits",
        "pdf_permits",
        "pdf_success_ratio",
        "pdf_success_rate",
        "pdf_page",
        "source_file",
        "source_label",
    ]
    write_csv(OUT / "2021_parent_pdf_success_rate_extracted_rows.csv", pdf_rows, pdf_fields)

    pdf_by_key = defaultdict(list)
    for row in pdf_rows:
        pdf_by_key[key_for(row)].append(row)

    backup_path = BACKUP_DIR / f"finalized_point_distribution.BACKUP_BEFORE_2021_SUCCESS_RATE_PATCH_{timestamp}.csv"
    shutil.copy2(TRUTH, backup_path)

    patch_rows = []
    mismatch_rows = []
    unmatched_truth_rows = []
    duplicate_pdf_keys = []
    for key, rows in pdf_by_key.items():
        if len(rows) > 1:
            duplicate_pdf_keys.append(
                {
                    "year": key[0],
                    "hunt_code": key[1],
                    "residency": key[2],
                    "point_level": key[3],
                    "source_file": key[4],
                    "pdf_row_count": len(rows),
                }
            )

    tmp_path = TRUTH.with_suffix(".csv.tmp_2021_success_rate_patch")
    total_rows = 0
    rows_in_scope = 0
    rows_patched = 0
    rows_already_filled = 0
    rows_pdf_na = 0
    rows_no_pdf_match = 0
    rows_applicant_or_permit_mismatch = 0

    with TRUTH.open("r", encoding="utf-8-sig", newline="") as src, tmp_path.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src)
        fields = list(reader.fieldnames or [])
        writer = csv.DictWriter(dst, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row_number, row in enumerate(reader, start=2):
            total_rows += 1
            in_scope = clean(row.get("year")) == "2021" and clean(row.get("source_file")) in {s["source_file"] for s in PDF_SOURCES}
            if not in_scope:
                writer.writerow(row)
                continue
            rows_in_scope += 1
            existing = clean(row.get("success_rate"))
            if existing:
                rows_already_filled += 1
                writer.writerow(row)
                continue

            matches = pdf_by_key.get(key_for(row), [])
            if not matches:
                rows_no_pdf_match += 1
                if len(unmatched_truth_rows) < 1000:
                    unmatched_truth_rows.append(
                        {
                            "row_number": row_number,
                            "year": clean(row.get("year")),
                            "hunt_code": clean(row.get("hunt_code")),
                            "hunt_name": clean(row.get("hunt_name")),
                            "residency": clean(row.get("residency")),
                            "point_level": clean(row.get("point_level")),
                            "applicants": clean(row.get("applicants")),
                            "permits": clean(row.get("permits")),
                            "source_file": clean(row.get("source_file")),
                            "reason": "NO_MATCHING_PDF_ROW",
                        }
                    )
                writer.writerow(row)
                continue

            pdf_row = matches[0]
            if not pdf_row["pdf_success_rate"]:
                rows_pdf_na += 1
                writer.writerow(row)
                continue

            applicants_match = norm_int_text(row.get("applicants")) == pdf_row["pdf_applicants"]
            permits_match = norm_int_text(row.get("permits")) == pdf_row["pdf_permits"]
            if not (applicants_match and permits_match):
                rows_applicant_or_permit_mismatch += 1
                mismatch_rows.append(
                    {
                        "row_number": row_number,
                        "year": clean(row.get("year")),
                        "hunt_code": clean(row.get("hunt_code")),
                        "hunt_name": clean(row.get("hunt_name")),
                        "residency": clean(row.get("residency")),
                        "point_level": clean(row.get("point_level")),
                        "truth_applicants": clean(row.get("applicants")),
                        "pdf_applicants": pdf_row["pdf_applicants"],
                        "truth_permits": clean(row.get("permits")),
                        "pdf_permits": pdf_row["pdf_permits"],
                        "pdf_success_ratio": pdf_row["pdf_success_ratio"],
                        "pdf_success_rate": pdf_row["pdf_success_rate"],
                        "source_file": clean(row.get("source_file")),
                        "pdf_page": pdf_row["pdf_page"],
                    }
                )
                writer.writerow(row)
                continue

            row["success_rate"] = pdf_row["pdf_success_rate"]
            rows_patched += 1
            patch_rows.append(
                {
                    "row_number": row_number,
                    "year": clean(row.get("year")),
                    "model_year": clean(row.get("model_year")),
                    "hunt_code": clean(row.get("hunt_code")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "residency": clean(row.get("residency")),
                    "point_level": clean(row.get("point_level")),
                    "applicants": clean(row.get("applicants")),
                    "permits": clean(row.get("permits")),
                    "old_success_rate": existing,
                    "new_success_rate": pdf_row["pdf_success_rate"],
                    "pdf_success_ratio": pdf_row["pdf_success_ratio"],
                    "source_file": clean(row.get("source_file")),
                    "pdf_page": pdf_row["pdf_page"],
                }
            )
            writer.writerow(row)

    tmp_path.replace(TRUTH)

    write_csv(
        OUT / "2021_success_rate_patch_rows.csv",
        patch_rows,
        [
            "row_number",
            "year",
            "model_year",
            "hunt_code",
            "hunt_name",
            "residency",
            "point_level",
            "applicants",
            "permits",
            "old_success_rate",
            "new_success_rate",
            "pdf_success_ratio",
            "source_file",
            "pdf_page",
        ],
    )
    write_csv(
        OUT / "2021_success_rate_patch_mismatches.csv",
        mismatch_rows,
        [
            "row_number",
            "year",
            "hunt_code",
            "hunt_name",
            "residency",
            "point_level",
            "truth_applicants",
            "pdf_applicants",
            "truth_permits",
            "pdf_permits",
            "pdf_success_ratio",
            "pdf_success_rate",
            "source_file",
            "pdf_page",
        ],
    )
    write_csv(
        OUT / "2021_success_rate_patch_unmatched_truth_rows_sample.csv",
        unmatched_truth_rows,
        [
            "row_number",
            "year",
            "hunt_code",
            "hunt_name",
            "residency",
            "point_level",
            "applicants",
            "permits",
            "source_file",
            "reason",
        ],
    )
    write_csv(
        OUT / "2021_success_rate_duplicate_pdf_keys.csv",
        duplicate_pdf_keys,
        ["year", "hunt_code", "residency", "point_level", "source_file", "pdf_row_count"],
    )

    by_source = Counter(row["source_file"] for row in patch_rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "truth_file": str(TRUTH),
        "backup_path": str(backup_path),
        "pdf_sources": [str(source["pdf"]) for source in PDF_SOURCES],
        "total_truth_rows": total_rows,
        "rows_in_scope": rows_in_scope,
        "rows_patched": rows_patched,
        "rows_already_filled": rows_already_filled,
        "rows_pdf_na_left_blank": rows_pdf_na,
        "rows_no_pdf_match": rows_no_pdf_match,
        "rows_applicant_or_permit_mismatch_not_patched": rows_applicant_or_permit_mismatch,
        "duplicate_pdf_key_groups": len(duplicate_pdf_keys),
        "patch_rows_by_source_file": dict(sorted(by_source.items())),
        "outputs": {
            "extracted_pdf_rows": str(OUT / "2021_parent_pdf_success_rate_extracted_rows.csv"),
            "patch_rows": str(OUT / "2021_success_rate_patch_rows.csv"),
            "mismatches": str(OUT / "2021_success_rate_patch_mismatches.csv"),
            "unmatched_truth_sample": str(OUT / "2021_success_rate_patch_unmatched_truth_rows_sample.csv"),
            "summary": str(OUT / "2021_success_rate_patch_summary.json"),
        },
    }
    (OUT / "2021_success_rate_patch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
