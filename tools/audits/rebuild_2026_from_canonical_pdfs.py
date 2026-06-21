import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2026\.pdf")
OUT_ROOT = REPO_ROOT / "audits" / "truth_document_audit" / "rebuild_2026_from_canonical_pdfs"

CANONICAL_PDFS = [
    "2026_PERMITS=2027_MODEL__SPORTSMAN PERMITS DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__TURKEY DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__YOUTH G.S. MATURE BULL ELK DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__BEAR DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__BEAR RESTRICTED PURSUIT DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__D.H. DEER DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__G.S. BUCK DEER DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__L.E. DEER.pdf",
    "2026_PERMITS=2027_MODEL__L.E. ELK.pdf",
    "2026_PERMITS=2027_MODEL__L.E. PRONGHORN.pdf",
    "2026_PERMITS=2027_MODEL__O.I.L. BISON.pdf",
    "2026_PERMITS=2027_MODEL__O.I.L. BULL MOOSE DRAW RESULTS.pdf",
    "2026_PERMITS=2027_MODEL__O.I.L. DESERT BIGHORN SHEEP.pdf",
    "2026_PERMITS=2027_MODEL__O.I.L. MTN GOAT.pdf",
    "2026_PERMITS=2027_MODEL__O.I.L. ROCKY MTN SHEEP.pdf",
]

POINT_PURCHASE_CODES = {
    "BER",
    "BIS",
    "BPU",
    "DBS",
    "DEE",
    "DHL",
    "ELK",
    "GDR",
    "GOA",
    "MOO",
    "PRO",
    "RMB",
    "TKY",
}

FIELDNAMES = [
    "record_kind",
    "source_dataset",
    "actual_draw_year",
    "year",
    "model_target_year",
    "source_file",
    "source_pdf_page",
    "source_report_title",
    "source_report_family",
    "hunt_code",
    "hunt_name",
    "raw_hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "weapon",
    "residency",
    "applicant_group",
    "draw_pool",
    "point_system",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "total_drawn",
    "successful_applicants",
    "success_ratio",
    "success_ratio_text",
    "p_draw",
    "p_draw_percent",
    "candidate_promotion_status",
    "candidate_promotion_reason",
]


def clean(value):
    return "" if value is None else str(value).strip()


def parse_int(value):
    text = clean(value).replace(",", "")
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def report_family_for_file(name):
    upper = name.upper()
    if "SPORTSMAN" in upper:
        return ("SPORTSMAN_RANDOM_ONLY", "Sportsman", "Sportsman", "SPORTSMAN_RANDOM_SINGLE_PERMIT", "sportsman")
    if "YOUTH G.S. MATURE BULL ELK" in upper:
        return ("YOUTH_GENERAL_SEASON_ELK", "Elk", "Youth", "PREFERENCE_POINT_ORDERED", "youth")
    if "TURKEY" in upper:
        return ("TURKEY", "Turkey", "Bearded", "BONUS_POINT", "standard")
    if "BEAR RESTRICTED PURSUIT" in upper:
        return ("BLACK_BEAR_RESTRICTED_PURSUIT", "Black Bear", "Either Sex", "BONUS_POINT", "standard")
    if "BEAR DRAW" in upper:
        return ("BLACK_BEAR", "Black Bear", "Either Sex", "BONUS_POINT", "standard")
    if "D.H. DEER" in upper:
        return ("DEDICATED_HUNTER", "Deer", "Buck", "PREFERENCE_POINT_ORDERED", "dedicated_hunter")
    if "G.S. BUCK DEER" in upper:
        return ("GENERAL_SEASON_DEER", "Deer", "Buck", "PREFERENCE_POINT_ORDERED", "standard")
    if "L.E. DEER" in upper:
        return ("LIMITED_ENTRY_DEER", "Deer", "Buck", "BONUS_POINT_MAX_RANDOM", "standard")
    if "L.E. ELK" in upper:
        return ("LIMITED_ENTRY_ELK", "Elk", "Bull", "BONUS_POINT_MAX_RANDOM", "standard")
    if "L.E. PRONGHORN" in upper:
        return ("LIMITED_ENTRY_PRONGHORN", "Pronghorn", "Buck", "BONUS_POINT_MAX_RANDOM", "standard")
    if "O.I.L. BISON" in upper:
        return ("OIL_BISON", "Bison", "Either Sex", "BONUS_POINT_MAX_RANDOM", "standard")
    if "O.I.L. BULL MOOSE" in upper:
        return ("OIL_BULL_MOOSE", "Moose", "Bull", "BONUS_POINT_MAX_RANDOM", "standard")
    if "O.I.L. DESERT BIGHORN" in upper:
        return ("OIL_DESERT_BIGHORN_SHEEP", "Desert Bighorn Sheep", "Ram", "BONUS_POINT_MAX_RANDOM", "standard")
    if "O.I.L. MTN GOAT" in upper:
        return ("OIL_MTN_GOAT", "Mountain Goat", "Either Sex", "BONUS_POINT_MAX_RANDOM", "standard")
    if "O.I.L. ROCKY MTN SHEEP" in upper:
        return ("OIL_ROCKY_MTN_SHEEP", "Rocky Mountain Bighorn Sheep", "Ram", "BONUS_POINT_MAX_RANDOM", "standard")
    return ("UNKNOWN_REVIEW", "", "", "", "standard")


def infer_hunt_identity(hunt_code, raw_name, fallback_species, fallback_sex):
    name = clean(raw_name)
    species = fallback_species
    sex_type = fallback_sex
    weapon = ""
    hunt_type = ""
    hunt_class = ""

    upper = name.upper()
    if "ANY LEGAL WEAPON" in upper:
        weapon = "Any Legal Weapon"
    elif "ARCHERY" in upper:
        weapon = "Archery"
    elif "MUZZLELOADER" in upper:
        weapon = "Muzzleloader"
    elif "RIFLE" in upper or "ALW" in upper:
        weapon = "Any Legal Weapon"

    if "BUCK DEER" in upper or hunt_code.startswith("DB") or hunt_code in {"DEE", "GDR", "DHL", "DB0007"}:
        species = "Deer"
        if not sex_type:
            sex_type = "Buck"
    elif "BULL ELK" in upper or hunt_code.startswith("EB") or hunt_code in {"ELK", "EB1000"}:
        species = "Elk"
        if not sex_type:
            sex_type = "Bull"
    elif "PRONGHORN" in upper or hunt_code.startswith("PB") or hunt_code in {"PRO", "PB1000"}:
        species = "Pronghorn"
        if not sex_type:
            sex_type = "Buck"
    elif "MOOSE" in upper or hunt_code.startswith("MB") or hunt_code in {"MOO", "MB1000"}:
        species = "Moose"
        if not sex_type:
            sex_type = "Bull"
    elif "BISON" in upper or hunt_code.startswith("BI") or hunt_code == "BIS":
        species = "Bison"
        if "COW" in upper:
            sex_type = "Cow"
        elif not sex_type:
            sex_type = "Either Sex"
    elif "DESERT BIGHORN" in upper or hunt_code.startswith("DS") or hunt_code == "DBS":
        species = "Desert Bighorn Sheep"
        if not sex_type:
            sex_type = "Ram"
    elif "ROCKY" in upper or hunt_code.startswith("RS") or hunt_code == "RMB":
        species = "Rocky Mountain Bighorn Sheep"
        if not sex_type:
            sex_type = "Ram"
    elif "GOAT" in upper or hunt_code.startswith("GO") or hunt_code == "GOA":
        species = "Mountain Goat"
        if not sex_type:
            sex_type = "Either Sex"
    elif "BEAR" in upper or hunt_code.startswith("BR") or hunt_code in {"BER", "BPU", "BR1000"}:
        species = "Black Bear"
        if not sex_type:
            sex_type = "Either Sex"
    elif "TURKEY" in upper or hunt_code.startswith("TK"):
        species = "Turkey"
        if not sex_type:
            sex_type = "Bearded"

    if "SPORTSMAN" in upper:
        hunt_type = "Sportsman"
    elif "DEDICATED HUNTER" in upper or hunt_code == "DHL":
        hunt_type = "D.H."
    elif "GENERAL" in upper or hunt_code == "GDR":
        hunt_type = "G.S."
    elif "LIMITED" in upper or re.match(r"^(DB10|EB3|PB5)", hunt_code):
        hunt_type = "L.E."
    elif hunt_code.startswith(("BI", "MB", "DS", "GO", "RS")) or hunt_code in {"BIS", "MOO", "DBS", "GOA", "RMB"}:
        hunt_type = "O.I.L."
    elif hunt_code.startswith("BR") or hunt_code in {"BER", "BPU"}:
        hunt_type = "Bear"
    elif hunt_code.startswith("TK") or hunt_code == "TKY":
        hunt_type = "Turkey"

    if "CWMU" in upper:
        hunt_class = "CWMU"
    elif "PREMIUM" in upper:
        hunt_class = "P.L.E."

    return {
        "species": species,
        "sex_type": sex_type,
        "weapon": weapon,
        "hunt_type": hunt_type,
        "hunt_class": hunt_class,
    }


def parse_ratio_text(text):
    value = clean(text)
    if not value or value.upper() == "N/A":
        return ""
    match = re.search(r"1\s+in\s+([0-9]+(?:\.[0-9]+)?)", value, re.IGNORECASE)
    if not match:
        return ""
    denominator = float(match.group(1))
    if denominator == 0:
        return ""
    return 1.0 / denominator


def rows_from_section(lines, start_idx):
    j = start_idx + 1
    while j < len(lines) and lines[j] != "Ratio":
        j += 1
    if j >= len(lines):
        return [], j
    j += 1
    parsed = []
    totals = None
    while j < len(lines):
        token = lines[j]
        if re.match(r"^(Resident|Nonresident) (Adult|Youth) Applicants$", token):
            break
        if token == "Totals":
            if j + 5 < len(lines):
                totals = {
                    "eligible": clean(lines[j + 1]),
                    "bonus_permits": clean(lines[j + 2]),
                    "regular_permits": clean(lines[j + 3]),
                    "total_permits": clean(lines[j + 4]),
                    "success_ratio_text": clean(lines[j + 5]),
                }
                j += 6
            break
        if not re.fullmatch(r"-?\d+", token):
            j += 1
            continue
        if j + 5 >= len(lines):
            break
        row = {
            "points": clean(lines[j]),
            "eligible_applicants": clean(lines[j + 1]),
            "bonus_permits": clean(lines[j + 2]),
            "regular_permits": clean(lines[j + 3]),
            "total_permits": clean(lines[j + 4]),
            "success_ratio_text": clean(lines[j + 5]),
        }
        parsed.append(row)
        j += 6
    return parsed, j


def extract_pdf(pdf_path):
    family, fallback_species, fallback_sex, draw_design, default_pool = report_family_for_file(pdf_path.name)
    reader = PdfReader(str(pdf_path))
    rows = []
    page_audit = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0] if lines else ""
        hunt_line = next((line for line in lines if line.startswith("Hunt: ")), "")
        match = re.match(r"Hunt:\s+(\S+)\s*(.*)$", hunt_line)
        if not match:
            page_audit.append({"source_file": pdf_path.name, "page": page_index, "status": "NO_HUNT_LINE", "rows": 0})
            continue
        hunt_code = match.group(1).strip()
        raw_hunt_name = match.group(2).strip()
        identity = infer_hunt_identity(hunt_code, raw_hunt_name, fallback_species, fallback_sex)
        section_count = 0
        page_rows = 0
        idx = 0
        while idx < len(lines):
            sec = re.match(r"^(Resident|Nonresident) (Adult|Youth) Applicants$", lines[idx])
            if not sec:
                idx += 1
                continue
            section_count += 1
            residency = sec.group(1)
            applicant_group = sec.group(2)
            section_rows, idx = rows_from_section(lines, idx)
            for raw in section_rows:
                eligible = parse_int(raw["eligible_applicants"])
                total_drawn = parse_int(raw["total_permits"])
                bonus = parse_int(raw["bonus_permits"])
                regular = parse_int(raw["regular_permits"])
                ratio = ""
                p_draw = ""
                p_draw_percent = ""
                if eligible is not None and total_drawn is not None and eligible > 0:
                    ratio_float = total_drawn / eligible
                    ratio = f"{ratio_float:.10f}".rstrip("0").rstrip(".")
                    p_draw = ratio
                    p_draw_percent = f"{ratio_float * 100:.6f}".rstrip("0").rstrip(".")
                elif raw["success_ratio_text"].upper() != "N/A":
                    parsed_ratio = parse_ratio_text(raw["success_ratio_text"])
                    if parsed_ratio != "":
                        ratio = f"{parsed_ratio:.10f}".rstrip("0").rstrip(".")
                        p_draw = ratio
                        p_draw_percent = f"{parsed_ratio * 100:.6f}".rstrip("0").rstrip(".")

                if hunt_code in POINT_PURCHASE_CODES:
                    record_kind = "POINT_PURCHASE_REFERENCE"
                    promotion_status = "DO_NOT_PROMOTE_TO_HUNT_CODE_SCORING"
                    promotion_reason = "Generic point-purchase family page, not a hunt-code keyed draw-result row."
                elif family == "SPORTSMAN_RANDOM_ONLY":
                    record_kind = "SPORTSMAN_TOTAL"
                    promotion_status = "SEPARATE_LANE_REVIEW"
                    promotion_reason = "Sportsman is random-only and must not route through normal bonus/preference scoring."
                else:
                    record_kind = "POINT_ROW"
                    promotion_status = "PDF_DERIVED_CANDIDATE_NOT_APPLIED"
                    promotion_reason = "Official 2026 DWR PDF point row extracted for audit."

                draw_pool = default_pool
                if applicant_group == "Youth":
                    draw_pool = f"youth_{default_pool}" if default_pool != "standard" else "youth"

                rows.append(
                    {
                        "record_kind": record_kind,
                        "source_dataset": "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS",
                        "actual_draw_year": "2026",
                        "year": "2026",
                        "model_target_year": "2027",
                        "source_file": str(pdf_path),
                        "source_pdf_page": str(page_index),
                        "source_report_title": title,
                        "source_report_family": family,
                        "hunt_code": hunt_code,
                        "hunt_name": raw_hunt_name,
                        "raw_hunt_name": raw_hunt_name,
                        "species": identity["species"],
                        "sex_type": identity["sex_type"],
                        "hunt_type": identity["hunt_type"],
                        "hunt_class": identity["hunt_class"],
                        "weapon": identity["weapon"],
                        "residency": residency,
                        "applicant_group": applicant_group,
                        "draw_pool": draw_pool,
                        "point_system": "Preference" if "Preference Point" in title or "Preference Point" in raw_hunt_name else "Bonus",
                        "points": raw["points"],
                        "eligible_applicants": raw["eligible_applicants"],
                        "bonus_permits": raw["bonus_permits"],
                        "regular_permits": raw["regular_permits"],
                        "total_permits": raw["total_permits"],
                        "total_drawn": raw["total_permits"],
                        "successful_applicants": raw["total_permits"],
                        "success_ratio": ratio,
                        "success_ratio_text": raw["success_ratio_text"],
                        "p_draw": p_draw,
                        "p_draw_percent": p_draw_percent,
                        "candidate_promotion_status": promotion_status,
                        "candidate_promotion_reason": promotion_reason,
                    }
                )
                page_rows += 1
        page_audit.append(
            {
                "source_file": pdf_path.name,
                "page": page_index,
                "hunt_code": hunt_code,
                "hunt_name": raw_hunt_name,
                "sections": section_count,
                "rows": page_rows,
                "status": "OK" if page_rows else "NO_ROWS_EXTRACTED",
            }
        )
    return rows, page_audit


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path, rows, fieldnames):
    try:
        from openpyxl import Workbook
    except Exception as exc:
        return str(exc)
    wb = Workbook()
    ws = wb.active
    ws.title = "2026_pdf_rows"
    ws.append(fieldnames)
    for row in rows:
        ws.append([row.get(field, "") for field in fieldnames])
    wb.save(path)
    return ""


def profile_existing(path):
    if not path.exists():
        return {"exists": False, "path": str(path)}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames or []
    return {
        "exists": True,
        "path": str(path),
        "rows": len(rows),
        "columns": len(fields),
        "unique_hunt_codes": len({clean(r.get("hunt_code")) for r in rows if clean(r.get("hunt_code"))}),
        "point_rows": sum(1 for r in rows if clean(r.get("record_kind")) == "POINT_ROW"),
        "sportsman_rows": sum(1 for r in rows if clean(r.get("record_kind")) in {"SPORTSMAN_TOTAL", "SPORTSMAN_RANDOM_ONLY"}),
        "scorable_rows": sum(
            1
            for r in rows
            if clean(r.get("p_draw_percent"))
            or clean(r.get("success_ratio"))
            or (clean(r.get("eligible_applicants")) and clean(r.get("total_drawn")))
        ),
    }


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    page_audit = []
    missing_sources = []
    for name in CANONICAL_PDFS:
        path = SOURCE_ROOT / name
        if not path.exists():
            missing_sources.append(str(path))
            continue
        rows, audit = extract_pdf(path)
        all_rows.extend(rows)
        page_audit.extend(audit)

    key_cols = ["actual_draw_year", "model_target_year", "hunt_code", "residency", "draw_pool", "point_system", "points", "record_kind"]
    key_counter = Counter(tuple(clean(row.get(col)) for col in key_cols) for row in all_rows)
    duplicates = [
        {"key": "|".join(key), "count": count}
        for key, count in key_counter.items()
        if count > 1
    ]
    by_source = Counter(row["source_file"] for row in all_rows)
    by_family = Counter(row["source_report_family"] for row in all_rows)
    by_kind = Counter(row["record_kind"] for row in all_rows)
    by_code = Counter(row["hunt_code"] for row in all_rows)
    zero_applicant_rows = sum(1 for row in all_rows if clean(row.get("eligible_applicants")).replace(",", "") in {"0", "0.0"})
    scorable_rows = sum(
        1
        for row in all_rows
        if clean(row.get("p_draw_percent"))
        or clean(row.get("success_ratio"))
        or (clean(row.get("eligible_applicants")) and clean(row.get("total_drawn")))
    )

    row_csv = OUT_ROOT / "2026_pdf_extracted_rows.csv"
    row_xlsx = OUT_ROOT / "2026_pdf_extracted_rows.xlsx"
    page_csv = OUT_ROOT / "2026_pdf_page_audit.csv"
    source_csv = OUT_ROOT / "2026_pdf_extraction_by_source_file.csv"
    family_csv = OUT_ROOT / "2026_pdf_extraction_by_family.csv"
    dup_csv = OUT_ROOT / "2026_pdf_duplicate_point_keys.csv"
    comparison_csv = OUT_ROOT / "2026_pdf_vs_existing_candidates_summary.csv"
    summary_json = OUT_ROOT / "2026_pdf_extraction_summary.json"
    report_md = OUT_ROOT / "2026_PDF_TRUTH_REBUILD_REPORT.md"

    write_csv(row_csv, all_rows, FIELDNAMES)
    xlsx_error = write_xlsx(row_xlsx, all_rows, FIELDNAMES)
    write_csv(page_csv, page_audit, ["source_file", "page", "hunt_code", "hunt_name", "sections", "rows", "status"])
    write_csv(
        source_csv,
        [
            {
                "source_file": source,
                "rows": count,
                "unique_hunt_codes": len({row["hunt_code"] for row in all_rows if row["source_file"] == source}),
            }
            for source, count in sorted(by_source.items())
        ],
        ["source_file", "rows", "unique_hunt_codes"],
    )
    write_csv(
        family_csv,
        [
            {
                "source_report_family": family,
                "rows": count,
                "unique_hunt_codes": len({row["hunt_code"] for row in all_rows if row["source_report_family"] == family}),
            }
            for family, count in sorted(by_family.items())
        ],
        ["source_report_family", "rows", "unique_hunt_codes"],
    )
    write_csv(dup_csv, duplicates, ["key", "count"])

    existing_paths = [
        REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2026_for_2027_candidate_promotion_file_records.csv",
        REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2026_for_2027_candidate_promotion_file_records_CANONICAL_SCORABLE_CANDIDATE.csv",
        REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2026_for_2027_candidate_promotion_file_records_SCORABLE_CANDIDATE.csv",
        REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2026_for_2027_candidate_promotion_file_records_SCORABLE_FOLDER_CANDIDATE.csv",
    ]
    profiles = [profile_existing(path) for path in existing_paths]
    comparison_rows = [
        {
            "file": "PDF_DERIVED_AUDIT_CANDIDATE",
            "path": str(row_csv),
            "rows": len(all_rows),
            "columns": len(FIELDNAMES),
            "unique_hunt_codes": len(by_code),
            "point_rows": by_kind.get("POINT_ROW", 0),
            "sportsman_rows": by_kind.get("SPORTSMAN_TOTAL", 0),
            "scorable_rows": scorable_rows,
        }
    ] + [
        {
            "file": Path(profile["path"]).name,
            "path": profile["path"],
            "rows": profile.get("rows", ""),
            "columns": profile.get("columns", ""),
            "unique_hunt_codes": profile.get("unique_hunt_codes", ""),
            "point_rows": profile.get("point_rows", ""),
            "sportsman_rows": profile.get("sportsman_rows", ""),
            "scorable_rows": profile.get("scorable_rows", ""),
        }
        for profile in profiles
    ]
    write_csv(
        comparison_csv,
        comparison_rows,
        ["file", "path", "rows", "columns", "unique_hunt_codes", "point_rows", "sportsman_rows", "scorable_rows"],
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(SOURCE_ROOT),
        "output_root": str(OUT_ROOT),
        "missing_sources": missing_sources,
        "pdf_files_expected": len(CANONICAL_PDFS),
        "pdf_files_found": len(CANONICAL_PDFS) - len(missing_sources),
        "rows": len(all_rows),
        "unique_hunt_codes": len(by_code),
        "point_rows": by_kind.get("POINT_ROW", 0),
        "point_purchase_reference_rows": by_kind.get("POINT_PURCHASE_REFERENCE", 0),
        "sportsman_rows": by_kind.get("SPORTSMAN_TOTAL", 0),
        "scorable_rows": scorable_rows,
        "zero_applicant_rows_retained": zero_applicant_rows,
        "duplicate_point_key_groups": len(duplicates),
        "record_kind_counts": dict(sorted(by_kind.items())),
        "source_report_family_counts": dict(sorted(by_family.items())),
        "outputs": {
            "rows_csv": str(row_csv),
            "rows_xlsx": str(row_xlsx) if not xlsx_error else "",
            "xlsx_error": xlsx_error,
            "page_audit_csv": str(page_csv),
            "source_summary_csv": str(source_csv),
            "family_summary_csv": str(family_csv),
            "duplicate_keys_csv": str(dup_csv),
            "comparison_csv": str(comparison_csv),
            "report_md": str(report_md),
        },
        "existing_profiles": profiles,
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report = [
        "# 2026 PDF Truth Rebuild Audit",
        "",
        "This is an audit candidate only. No normalized truth file or master draw_results_long.csv file was modified.",
        "",
        f"- Source root: `{SOURCE_ROOT}`",
        f"- PDF files found: {summary['pdf_files_found']} / {summary['pdf_files_expected']}",
        f"- Extracted rows: {summary['rows']}",
        f"- Unique hunt codes: {summary['unique_hunt_codes']}",
        f"- Point rows: {summary['point_rows']}",
        f"- Point-purchase reference rows: {summary['point_purchase_reference_rows']}",
        f"- Sportsman rows: {summary['sportsman_rows']}",
        f"- Scorable rows: {summary['scorable_rows']}",
        f"- Zero-applicant rows retained: {summary['zero_applicant_rows_retained']}",
        f"- Duplicate point-key groups: {summary['duplicate_point_key_groups']}",
        "",
        "## Decision",
        "",
        "PDF_DERIVED_CANDIDATE_CREATED_NOT_APPLIED",
        "",
        "The current active normalized 2026 file remains a 1,096-row placeholder-style file with no populated probability/applicant/drawn fields. This PDF-derived audit candidate should be reviewed against the existing UtahDraws/API scorable candidate before promotion.",
        "",
        "## Outputs",
        "",
    ]
    for label, path in summary["outputs"].items():
        if path:
            report.append(f"- {label}: `{path}`")
    report_md.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
