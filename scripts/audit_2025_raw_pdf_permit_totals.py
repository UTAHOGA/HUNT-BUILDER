import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\2025\.pdf")
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
DWR_AUDIT = ROOT / "audits" / "2025_canonical_finalization" / "2025_for_2026_vs_fresh_downloads_dwr_huntboundary.csv"
OUT_DIR = ROOT / "audits" / "2025_canonical_finalization"

HUNT_HEADER_RE = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+?)(?=\s+Page\s+\d+|$)", re.IGNORECASE)
TOTALS_RE = re.compile(r"Totals\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s+1\s+in\s+[\d.]+|\s+N/A)?", re.IGNORECASE)


def clean(value):
    return " ".join(str(value or "").replace("\r", "\n").split())


def norm_int(value):
    text = clean(value)
    if text == "":
        return ""
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split_header(raw_title):
    title = clean(raw_title)
    parts = [clean(part) for part in title.split(" - ") if clean(part)]
    species_part = parts[0] if parts else title
    weapon = parts[-1] if len(parts) > 1 else ""
    hunt_name = " - ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) == 2 else "")
    return species_part, hunt_name, weapon


def extract_pdf_rows():
    import pdfplumber

    rows = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if "Hunt:" not in text or "Totals" not in text:
                        continue
                    header_match = HUNT_HEADER_RE.search(text)
                    if not header_match:
                        continue
                    totals = TOTALS_RE.findall(text)
                    code = clean(header_match.group(1)).upper()
                    raw_title = clean(header_match.group(2))
                    species_part, hunt_name, weapon = split_header(raw_title)
                    res_total = nr_total = total = ""
                    if len(totals) >= 2:
                        res_total = str(int(totals[0][3]))
                        nr_total = str(int(totals[1][3]))
                        total = str(int(res_total) + int(nr_total))
                    elif len(totals) == 1:
                        total = str(int(totals[0][3]))
                    rows.append(
                        {
                            "hunt_code": code,
                            "pdf_raw_title": raw_title,
                            "pdf_species_title": species_part,
                            "pdf_hunt_name_title": hunt_name,
                            "pdf_weapon_title": weapon,
                            "pdf_permits_res": res_total,
                            "pdf_permits_nr": nr_total,
                            "pdf_permits_total": total,
                            "pdf_page": str(page_number),
                            "source_pdf": pdf_path.name,
                        }
                    )
        except Exception as exc:
            rows.append(
                {
                    "hunt_code": "",
                    "pdf_raw_title": "",
                    "pdf_species_title": "",
                    "pdf_hunt_name_title": "",
                    "pdf_weapon_title": "",
                    "pdf_permits_res": "",
                    "pdf_permits_nr": "",
                    "pdf_permits_total": "",
                    "pdf_page": "",
                    "source_pdf": pdf_path.name,
                    "extract_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows


def canonical_permit_sets():
    rows = load_csv(CANONICAL)
    by_code = defaultdict(set)
    samples = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        item = (
            norm_int(row.get("permits_2025_res")),
            norm_int(row.get("permits_2025_nr")),
            norm_int(row.get("permits_2025_total")),
        )
        by_code[code].add(item)
        samples.setdefault(
            code,
            {
                "canonical_hunt_name": clean(row.get("hunt_name")),
                "canonical_species": clean(row.get("species")),
                "canonical_sex_type": clean(row.get("sex_type")),
                "canonical_weapon": clean(row.get("weapon")),
                "canonical_hunt_type": clean(row.get("hunt_type")),
                "canonical_draw_design": clean(row.get("draw_design")),
            },
        )
    return by_code, samples


def dwr_permit_sets():
    by_code = defaultdict(set)
    samples = {}
    if not DWR_AUDIT.exists():
        return by_code, samples
    for row in load_csv(DWR_AUDIT):
        code = clean(row.get("hunt_code")).upper()
        item = (
            norm_int(row.get("source_permits_res")),
            norm_int(row.get("source_permits_nr")),
            norm_int(row.get("source_permits_total")),
        )
        by_code[code].add(item)
        samples.setdefault(
            code,
            {
                "dwr_hunt_name": clean(row.get("source_hunt_name")),
                "dwr_species": clean(row.get("source_species")),
                "dwr_sex_type": clean(row.get("source_sex_type")),
                "dwr_weapon": clean(row.get("source_weapon")),
                "dwr_season": clean(row.get("source_season")),
                "dwr_source_file": clean(row.get("source_file")),
            },
        )
    return by_code, samples


def compare_status(pdf_set, compare_sets):
    if not compare_sets:
        return "missing"
    if pdf_set in compare_sets:
        return "matched_split"
    pdf_total = pdf_set[2]
    if pdf_total and any(item[2] == pdf_total for item in compare_sets):
        return "matched_total_only_or_split_diff"
    return "mismatch"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_rows = extract_pdf_rows()
    canonical_sets, canonical_samples = canonical_permit_sets()
    dwr_sets, dwr_samples = dwr_permit_sets()

    audit_rows = []
    for row in pdf_rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            audit_rows.append({**row, "canonical_status": "extract_error", "dwr_status": "extract_error"})
            continue
        pdf_set = (row["pdf_permits_res"], row["pdf_permits_nr"], row["pdf_permits_total"])
        can_sets = canonical_sets.get(code, set())
        live_sets = dwr_sets.get(code, set())
        audit_rows.append(
            {
                **row,
                **canonical_samples.get(code, {}),
                **dwr_samples.get(code, {}),
                "pdf_permit_set": "|".join(pdf_set),
                "canonical_permit_sets": "; ".join(sorted("|".join(item) for item in can_sets)),
                "dwr_permit_sets": "; ".join(sorted("|".join(item) for item in live_sets)),
                "canonical_status": compare_status(pdf_set, can_sets),
                "dwr_status": compare_status(pdf_set, live_sets),
            }
        )

    fields = [
        "hunt_code",
        "pdf_raw_title",
        "pdf_species_title",
        "pdf_hunt_name_title",
        "pdf_weapon_title",
        "pdf_permits_res",
        "pdf_permits_nr",
        "pdf_permits_total",
        "pdf_page",
        "source_pdf",
        "canonical_hunt_name",
        "canonical_species",
        "canonical_sex_type",
        "canonical_weapon",
        "canonical_hunt_type",
        "canonical_draw_design",
        "dwr_hunt_name",
        "dwr_species",
        "dwr_sex_type",
        "dwr_weapon",
        "dwr_season",
        "dwr_source_file",
        "pdf_permit_set",
        "canonical_permit_sets",
        "dwr_permit_sets",
        "canonical_status",
        "dwr_status",
        "extract_error",
    ]
    audit_path = OUT_DIR / "2025_raw_pdf_permit_totals_vs_canonical_and_dwr.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "pdf_dir": str(PDF_DIR),
        "pdf_files_scanned": len(list(PDF_DIR.glob("*.pdf"))),
        "pdf_hunt_rows_extracted": len([row for row in audit_rows if row.get("hunt_code")]),
        "unique_pdf_hunt_codes": len({row["hunt_code"] for row in audit_rows if row.get("hunt_code")}),
        "canonical_status_counts": dict(sorted(Counter(row.get("canonical_status") for row in audit_rows).items())),
        "dwr_status_counts": dict(sorted(Counter(row.get("dwr_status") for row in audit_rows).items())),
        "bi6505": [row for row in audit_rows if row.get("hunt_code") == "BI6505"],
        "audit_csv": str(audit_path),
    }
    summary_path = OUT_DIR / "2025_raw_pdf_permit_totals_vs_canonical_and_dwr_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
