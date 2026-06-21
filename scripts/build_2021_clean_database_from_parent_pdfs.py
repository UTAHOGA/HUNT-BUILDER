import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "data_truth" / "draw_results_truth" / "rebuilt_clean" / "2021_PERMITS=2022_MODEL"
AUDIT_ROOT = ROOT / "audits" / "truth_document_audit" / "rebuild_2021_clean_from_parent_pdfs"
CURRENT_POINT_TRUTH = ROOT / "data_truth" / "finalized_point_distribution.csv"

SOURCES = [
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_bg-odds.pdf"),
        "source_file": "21_bg-odds.pdf",
        "source_scope": "BG_PARENT",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021 Antlerless Draw Results.pdf"),
        "source_file": "2021 Antlerless Draw Results.pdf",
        "source_scope": "ANTLERLESS_PARENT",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_antlerless_drawing_odds_report.pdf"),
        "source_file": "21_youth_antlerless_drawing_odds_report.pdf",
        "source_scope": "YOUTH_ANTLERLESS_PARENT",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021 Bear Draw Results.pdf"),
        "source_file": "2021 Bear Draw Results.pdf",
        "source_scope": "BEAR",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_cougar_odds_report.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__COUGAR DRAW RESULTS.pdf",
        "source_scope": "COUGAR",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_turkey_bonus_points_draw_results.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__TURKEY DRAW RESULTS.pdf",
        "source_scope": "TURKEY",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\2021_youth_turkey_draw_results.pdf"),
        "source_file": "2021_PERMITS=2022_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
        "source_scope": "YOUTH_TURKEY",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_deer_odds.pdf"),
        "source_file": "21_deer_odds.pdf",
        "source_scope": "GENERAL_SEASON_DEER",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_dh_odds.pdf"),
        "source_file": "21_dh_odds.pdf",
        "source_scope": "DEDICATED_HUNTER_DEER",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_lifetime_deer.pdf"),
        "source_file": "21_lifetime_deer.pdf",
        "source_scope": "LIFETIME_GENERAL_SEASON_DEER",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_bull_elk.pdf"),
        "source_file": "21_youth_bull_elk.pdf",
        "source_scope": "YOUTH_BULL_ELK",
        "draw_design": "BONUS_POINT",
        "point_label": "Bonus Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_deer.pdf"),
        "source_file": "21_youth_deer.pdf",
        "source_scope": "YOUTH_GENERAL_SEASON_DEER",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
    {
        "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21_youth_dh_odds.pdf"),
        "source_file": "21_youth_dh_odds.pdf",
        "source_scope": "YOUTH_DEDICATED_HUNTER_DEER",
        "draw_design": "PREFERENCE_POINT",
        "point_label": "Preference Points",
    },
]

SPORTSMAN_SOURCE = {
    "path": Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2021\Parent Files\21-22_sportsman_odds.pdf"),
    "source_file": "21-22_sportsman_odds.pdf",
    "source_scope": "SPORTSMAN",
    "draw_design": "SPORTSMAN_RANDOM_ONLY",
}

INVALID_2021_SPORTSMAN_CODES = {"CG9999"}

HUNT_RE = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+?)(?:\s+Page\s+\d+)?$", re.IGNORECASE)
PAGE_RE = re.compile(r"\bPage\s+(\d+)\b", re.IGNORECASE)
ROW_RE = re.compile(
    r"^\s*"
    r"(?P<r_points>\d+)\s+(?P<r_apps>[\d,]+)\s+(?P<r_bonus>[\d,]+)\s+(?P<r_regular>[\d,]+)\s+(?P<r_total>[\d,]+)\s+(?P<r_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s+"
    r"(?P<n_points>\d+)\s+(?P<n_apps>[\d,]+)\s+(?P<n_bonus>[\d,]+)\s+(?P<n_regular>[\d,]+)\s+(?P<n_total>[\d,]+)\s+(?P<n_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s*$",
    re.IGNORECASE,
)
TOTALS_RE = re.compile(
    r"^\s*Totals\s+(?P<r_apps>[\d,]+)\s+(?P<r_bonus>[\d,]+)\s+(?P<r_regular>[\d,]+)\s+(?P<r_total>[\d,]+)\s+(?P<r_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s+Totals\s+(?P<n_apps>[\d,]+)\s+(?P<n_bonus>[\d,]+)\s+(?P<n_regular>[\d,]+)\s+(?P<n_total>[\d,]+)\s+(?P<n_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s*$",
    re.IGNORECASE,
)


def clean(value):
    return "" if value is None else str(value).strip()


def norm_int(value):
    return clean(value).replace(",", "")


def ratio_to_success_rate(ratio):
    ratio = clean(ratio)
    if not ratio or ratio.upper() == "N/A":
        return ""
    match = re.search(r"1\s+in\s+([\d.]+)", ratio, re.IGNORECASE)
    if not match:
        return ""
    denom = float(match.group(1))
    if denom == 0:
        return ""
    return f"{100.0 / denom:.8f}".rstrip("0").rstrip(".")


def species_from_code_and_name(hunt_code, hunt_name):
    hay = f"{hunt_code} {hunt_name}".upper()
    if hunt_code.startswith("BI") or "BISON" in hay:
        return "BISON"
    if hunt_code.startswith("BR") or "BEAR" in hay:
        return "BLACK_BEAR"
    if hunt_code.startswith("CG") or "COUGAR" in hay:
        return "COUGAR"
    if hunt_code.startswith("TK") or "TURKEY" in hay:
        return "TURKEY"
    if hunt_code.startswith("GO") or "GOAT" in hay:
        return "MOUNTAIN_GOAT"
    if hunt_code.startswith("MB") or "MOOSE" in hay:
        return "MOOSE"
    if hunt_code.startswith("DS") or "DESERT BIGHORN" in hay:
        return "DESERT_BIGHORN_SHEEP"
    if hunt_code.startswith("RS") or ("ROCKY" in hay and "SHEEP" in hay):
        return "ROCKY_MOUNTAIN_BIGHORN_SHEEP"
    if hunt_code.startswith(("PB", "PD")) or "PRONGHORN" in hay:
        return "PRONGHORN"
    if hunt_code.startswith(("EB", "EA")) or "ELK" in hay:
        return "ELK"
    if hunt_code.startswith(("DB", "DA")) or "DEER" in hay:
        return "DEER"
    return "UNKNOWN"


def hunt_type_from_source(source_scope, hunt_code, hunt_name):
    if source_scope in {"ANTLERLESS_PARENT", "YOUTH_ANTLERLESS_PARENT"}:
        return "ANTLERLESS"
    if source_scope == "BEAR":
        return "BEAR"
    if source_scope == "COUGAR":
        return "COUGAR"
    if source_scope in {"TURKEY", "YOUTH_TURKEY"}:
        return "TURKEY"
    if source_scope == "SPORTSMAN":
        return "SPORTSMAN"
    if source_scope in {"GENERAL_SEASON_DEER", "YOUTH_GENERAL_SEASON_DEER", "LIFETIME_GENERAL_SEASON_DEER"}:
        return "G.S."
    if source_scope in {"DEDICATED_HUNTER_DEER", "YOUTH_DEDICATED_HUNTER_DEER"}:
        return "D.H."
    if source_scope == "YOUTH_BULL_ELK":
        return "YOUTH"
    hay = f"{hunt_code} {hunt_name}".upper()
    if hunt_code.startswith(("BI", "GO", "MB", "DS", "RS")):
        return "O.I.L."
    if "LIMITED" in hay or hunt_code.startswith(("DB", "EB", "PB")):
        return "L.E."
    return "UNKNOWN"


SPORTSMAN_RE = re.compile(
    r"^(?P<hunt_code>[A-Z]{2}\d{4})\s+(?P<hunt_name>.+?)\s+"
    r"(?P<successful_resident>[\d,]+)\s+(?P<successful_nonresident>[\d,]+)\s+"
    r"(?P<unsuccessful_resident>[\d,]+)\s+(?P<unsuccessful_nonresident>[\d,]+)\s+"
    r"(?P<total_applications>[\d,]+)\s+(?P<resident_quota>N/A|[\d,]+)\s+"
    r"(?P<nonresident_quota>N/A|[\d,]+)\s+(?P<total_quota>[\d,]+)\s+"
    r"(?P<resident_success>N/A|1\s+in\s+[\d,.]+)\s+(?P<nonresident_success>N/A|1\s+in\s+[\d,.]+)\s*$",
    re.IGNORECASE,
)


def norm_number_or_blank(value):
    text = clean(value).replace(",", "")
    return "" if text.upper() == "N/A" else text


def extract_sportsman_totals():
    source = SPORTSMAN_SOURCE
    if not source["path"].exists():
        raise FileNotFoundError(source["path"])
    rows = []
    rejected = []
    with pdfplumber.open(str(source["path"])) as pdf:
        for pdf_page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            pending_code = ""
            pending_name = ""
            pending_tail = ""
            for line in text.splitlines():
                if not line.strip():
                    continue
                if pending_code:
                    line = f"{pending_code} {pending_name} {line.strip()} {pending_tail}".strip()
                    pending_code = pending_name = pending_tail = ""
                match = SPORTSMAN_RE.match(line.strip())
                if not match:
                    split_match = re.match(r"^(?P<hunt_code>[A-Z]{2}\d{4})\s+(?P<hunt_name>Sportsman\s+(?:Desert Bighorn|Rocky Mtn))\s+(?P<tail>.+)$", line.strip(), re.IGNORECASE)
                    if split_match:
                        pending_code = split_match.group("hunt_code")
                        pending_name = split_match.group("hunt_name")
                        pending_tail = split_match.group("tail")
                    continue
                data = match.groupdict()
                hunt_code = data["hunt_code"].upper()
                if hunt_code in INVALID_2021_SPORTSMAN_CODES:
                    rejected.append(
                        {
                            "hunt_code": hunt_code,
                            "hunt_name": data["hunt_name"].strip(),
                            "source_file": source["source_file"],
                            "source_pdf_page": pdf_page_index,
                            "reason": "INVALID_PRE_2023_CG9999_FUTURE_COUGAR_TRANSITION_CODE",
                        }
                    )
                    continue
                hunt_name = data["hunt_name"].strip()
                rows.append(
                    {
                        "year": "2021",
                        "model_year": "2022",
                        "hunt_code": hunt_code,
                        "hunt_name": hunt_name,
                        "species": species_from_code_and_name(hunt_code, hunt_name),
                        "hunt_type": "SPORTSMAN",
                        "draw_design": source["draw_design"],
                        "residency": "All",
                        "applicants_total": norm_number_or_blank(data["total_applications"]),
                        "bonus_permits": "",
                        "regular_permits": "",
                        "permits_total": norm_number_or_blank(data["total_quota"]),
                        "success_ratio": data["resident_success"],
                        "success_rate": ratio_to_success_rate(data["resident_success"]),
                        "record_type": "sportsman_random_total",
                        "source_file": source["source_file"],
                        "source_scope": source["source_scope"],
                        "source_pdf_page": pdf_page_index,
                    }
                )
    return rows, rejected


def extract_rows():
    point_rows = []
    total_rows = []
    page_audit = []
    for source in SOURCES:
        if not source["path"].exists():
            raise FileNotFoundError(source["path"])
        with pdfplumber.open(str(source["path"])) as pdf:
            for pdf_page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                current_hunt_code = ""
                current_hunt_name = ""
                page_rows = 0
                for line in text.splitlines():
                    hunt_match = HUNT_RE.search(line)
                    if hunt_match:
                        current_hunt_code = hunt_match.group(1).upper()
                        current_hunt_name = hunt_match.group(2).strip()
                        continue
                    if not current_hunt_code:
                        continue
                    row_match = ROW_RE.match(line)
                    if row_match:
                        data = row_match.groupdict()
                        for prefix, residency in (("r", "Resident"), ("n", "Nonresident")):
                            points = norm_int(data[f"{prefix}_points"])
                            applicants = norm_int(data[f"{prefix}_apps"])
                            bonus_permits = norm_int(data[f"{prefix}_bonus"])
                            regular_permits = norm_int(data[f"{prefix}_regular"])
                            permits = norm_int(data[f"{prefix}_total"])
                            ratio = data[f"{prefix}_ratio"]
                            point_rows.append(
                                {
                                    "year": "2021",
                                    "model_year": "2022",
                                    "hunt_code": current_hunt_code,
                                    "hunt_name": current_hunt_name,
                                    "species": species_from_code_and_name(current_hunt_code, current_hunt_name),
                                    "hunt_type": hunt_type_from_source(source["source_scope"], current_hunt_code, current_hunt_name),
                                    "draw_design": source["draw_design"],
                                    "residency": residency,
                                    "point_level": points,
                                    "applicants": applicants,
                                    "bonus_permits": bonus_permits,
                                    "regular_permits": regular_permits,
                                    "permits": permits,
                                    "success_ratio": ratio,
                                    "success_rate": ratio_to_success_rate(ratio),
                                    "record_type": "point_level_draw_result",
                                    "source_file": source["source_file"],
                                    "source_scope": source["source_scope"],
                                    "source_pdf_page": pdf_page_index,
                                    "point_label": source["point_label"],
                                }
                            )
                            page_rows += 1
                        continue
                    totals_match = TOTALS_RE.match(line)
                    if totals_match:
                        data = totals_match.groupdict()
                        for prefix, residency in (("r", "Resident"), ("n", "Nonresident")):
                            ratio = data[f"{prefix}_ratio"]
                            total_rows.append(
                                {
                                    "year": "2021",
                                    "model_year": "2022",
                                    "hunt_code": current_hunt_code,
                                    "hunt_name": current_hunt_name,
                                    "species": species_from_code_and_name(current_hunt_code, current_hunt_name),
                                    "hunt_type": hunt_type_from_source(source["source_scope"], current_hunt_code, current_hunt_name),
                                    "draw_design": source["draw_design"],
                                    "residency": residency,
                                    "applicants_total": norm_int(data[f"{prefix}_apps"]),
                                    "bonus_permits": norm_int(data[f"{prefix}_bonus"]),
                                    "regular_permits": norm_int(data[f"{prefix}_regular"]),
                                    "permits_total": norm_int(data[f"{prefix}_total"]),
                                    "success_ratio": ratio,
                                    "success_rate": ratio_to_success_rate(ratio),
                                    "record_type": "hunt_total_draw_result",
                                    "source_file": source["source_file"],
                                    "source_scope": source["source_scope"],
                                    "source_pdf_page": pdf_page_index,
                                }
                            )
                page_audit.append(
                    {
                        "source_file": source["source_file"],
                        "pdf_page_index": pdf_page_index,
                        "has_hunt": "TRUE" if "Hunt:" in text else "FALSE",
                        "point_rows_extracted": page_rows,
                    }
                )
    return point_rows, total_rows, page_audit


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path, sheets):
    try:
        from openpyxl import Workbook
    except Exception:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    first = True
    for sheet_name, rows, fields in sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = sheet_name[:31]
        ws.append(fields)
        for row in rows:
            ws.append([row.get(field, "") for field in fields])
    wb.save(path)
    return True


def current_truth_profile(point_rows):
    current_keys = Counter()
    current_scope_rows = 0
    candidate_keys = Counter()
    for row in point_rows:
        candidate_keys[(row["hunt_code"], row["residency"], row["point_level"], row["source_file"])] += 1
    with CURRENT_POINT_TRUTH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if clean(row.get("year")) != "2021":
                continue
            if clean(row.get("source_file")) not in {source["source_file"] for source in SOURCES}:
                continue
            current_scope_rows += 1
            current_keys[(clean(row.get("hunt_code")), clean(row.get("residency")).title(), clean(row.get("point_level")), clean(row.get("source_file")))] += 1
    return {
        "current_scope_rows": current_scope_rows,
        "candidate_unique_keys": len(candidate_keys),
        "current_unique_keys": len(current_keys),
        "candidate_only_keys": sum(1 for key in candidate_keys if key not in current_keys),
        "current_only_keys": sum(1 for key in current_keys if key not in candidate_keys),
        "candidate_duplicate_key_groups": sum(1 for count in candidate_keys.values() if count > 1),
        "current_duplicate_key_groups": sum(1 for count in current_keys.values() if count > 1),
    }


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    point_rows, total_rows, page_audit = extract_rows()
    sportsman_rows, sportsman_rejected = extract_sportsman_totals()
    total_rows.extend(sportsman_rows)

    point_fields = [
        "year", "model_year", "hunt_code", "hunt_name", "species", "hunt_type", "draw_design",
        "residency", "point_level", "applicants", "bonus_permits", "regular_permits", "permits",
        "success_ratio", "success_rate", "record_type", "source_file", "source_scope",
        "source_pdf_page", "point_label",
    ]
    total_fields = [
        "year", "model_year", "hunt_code", "hunt_name", "species", "hunt_type", "draw_design",
        "residency", "applicants_total", "bonus_permits", "regular_permits", "permits_total",
        "success_ratio", "success_rate", "record_type", "source_file", "source_scope", "source_pdf_page",
    ]
    page_fields = ["source_file", "pdf_page_index", "has_hunt", "point_rows_extracted"]

    point_path = OUT_ROOT / "draw_results_2021_for_2022_CLEAN_PARENT_PDF_POINT_ROWS.csv"
    total_path = OUT_ROOT / "draw_results_2021_for_2022_CLEAN_PARENT_PDF_HUNT_TOTALS.csv"
    xlsx_path = OUT_ROOT / "draw_results_2021_for_2022_CLEAN_PARENT_PDF_DATABASE.xlsx"
    write_csv(point_path, point_rows, point_fields)
    write_csv(total_path, total_rows, total_fields)
    write_csv(AUDIT_ROOT / "2021_clean_parent_pdf_page_audit.csv", page_audit, page_fields)
    write_csv(
        AUDIT_ROOT / "2021_clean_parent_pdf_sportsman_rejected_rows.csv",
        sportsman_rejected,
        ["hunt_code", "hunt_name", "source_file", "source_pdf_page", "reason"],
    )
    xlsx_written = write_xlsx(
        xlsx_path,
        [
            ("point_rows", point_rows, point_fields),
            ("hunt_totals", total_rows, total_fields),
            ("page_audit", page_audit, page_fields),
        ],
    )

    by_source = Counter(row["source_file"] for row in point_rows)
    success_by_source = Counter(row["source_file"] for row in point_rows if row["success_rate"])
    unique_codes_by_source = defaultdict(set)
    for row in point_rows:
        unique_codes_by_source[row["source_file"]].add(row["hunt_code"])
    profile = current_truth_profile(point_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdfs": [str(source["path"]) for source in SOURCES],
        "point_rows": len(point_rows),
        "hunt_total_rows": len(total_rows),
        "sportsman_total_rows": len(sportsman_rows),
        "sportsman_rejected_rows": len(sportsman_rejected),
        "unique_hunt_codes": len({row["hunt_code"] for row in point_rows}),
        "unique_hunt_codes_including_totals": len({row["hunt_code"] for row in point_rows} | {row["hunt_code"] for row in total_rows}),
        "point_rows_with_success_rate": sum(1 for row in point_rows if row["success_rate"]),
        "point_rows_by_source_file": dict(sorted(by_source.items())),
        "point_rows_with_success_rate_by_source_file": dict(sorted(success_by_source.items())),
        "unique_hunt_codes_by_source_file": {key: len(value) for key, value in sorted(unique_codes_by_source.items())},
        "current_truth_comparison": profile,
        "outputs": {
            "point_rows_csv": str(point_path),
            "hunt_totals_csv": str(total_path),
            "xlsx": str(xlsx_path) if xlsx_written else "",
            "page_audit": str(AUDIT_ROOT / "2021_clean_parent_pdf_page_audit.csv"),
            "summary": str(AUDIT_ROOT / "2021_clean_parent_pdf_rebuild_summary.json"),
        },
    }
    (AUDIT_ROOT / "2021_clean_parent_pdf_rebuild_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# 2021 Clean Parent-PDF Rebuild",
        "",
        f"Generated UTC: {summary['generated_at_utc']}",
        "",
        "## Scope",
        "",
        "- Source-backed rebuild from supplied 2021 parent PDFs only.",
        "- No DATABASE.csv, processed_data, prediction output, or permit/applicant inference used.",
        "- `success_rate` is populated only from explicit PDF success ratio text (`1 in X`).",
        "- `N/A` rows remain blank in `success_rate` and remain structural point rows.",
        "",
        "## Counts",
        "",
        f"- Point rows: `{summary['point_rows']}`",
        f"- Hunt total rows: `{summary['hunt_total_rows']}`",
        f"- Unique hunt codes: `{summary['unique_hunt_codes']}`",
        f"- Point rows with success_rate: `{summary['point_rows_with_success_rate']}`",
        "",
        "## Outputs",
        "",
        f"- Point rows CSV: `{point_path}`",
        f"- Hunt totals CSV: `{total_path}`",
        f"- XLSX workbook: `{xlsx_path if xlsx_written else 'NOT_WRITTEN_OPENPYXL_MISSING'}`",
        f"- Summary JSON: `{AUDIT_ROOT / '2021_clean_parent_pdf_rebuild_summary.json'}`",
    ]
    (AUDIT_ROOT / "2021_CLEAN_PARENT_PDF_REBUILD_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
