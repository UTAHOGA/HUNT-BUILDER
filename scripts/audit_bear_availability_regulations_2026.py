"""Extract guidebook hunt-code inventories and compare retained Bear artifacts.

Read-only for engine/truth/production files. Outputs evidence in a new audit
directory, never repairs a saved probability or changes a coverage count.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    2024: ("2024_bear.pdf", "https://wildlife.utah.gov/guidebooks/2024_bear.pdf", 36, 42),
    2025: ("2025_bear_cougar.pdf", "https://wildlife.utah.gov/guidebooks/black-bear-and-cougar-guidebook-2025.pdf", 42, 48),
    2026: ("2026_bear_cougar_furbearer.pdf", "https://wildlife.utah.gov/guidebooks/black-bear-cougar-furbearer-guidebook.pdf", 73, 79),
}
HARVEST_PAGES = {2024: (43, 44), 2025: (48, 49), 2026: (79, 80)}


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def table_row_name(page, word):
    """Use PDF row borders, including unshaded and wrapped-name rows."""
    horizontal = [edge for edge in page.edges if edge["orientation"] == "h"]
    borders = [e for e in horizontal if e["x0"] <= word["x0"] and e["x1"] >= word["x1"]]
    above = max((e for e in borders if e["top"] <= word["top"]), key=lambda e: e["top"])
    bottom = min((e["top"] for e in borders if e["top"] >= word["bottom"]), default=word["bottom"] + 6)
    # Unshaded final rows have no bottom border; the next border may
    # belong to a different table far below. These cells are visually QA'd.
    if bottom - above["top"] > 70:
        bottom = word["bottom"] + 6
    left = min(e["x0"] for e in horizontal if abs(e["top"] - above["top"]) < 0.5 and e["x0"] >= 0)
    if bottom - above["top"] > 70 or above["x0"] <= left:
        raise ValueError(f"Unresolved table cell: page {page.page_number}/{word['text']}")
    name = " ".join((page.crop((left, above["top"], above["x0"], bottom)).extract_text() or "").split())
    if not name:
        raise ValueError(f"Missing hunt name: {word['text']}")
    return name


def table_hunt_names(page):
    return {w["text"]: table_row_name(page, w) for w in page.extract_words() if re.fullmatch(r"BR\d{4}", w["text"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists() or not args.out_dir.resolve().is_relative_to((ROOT / "audits").resolve()):
        parser.error("Choose a new output directory under audits/")
    inventories, provenance, harvest = {}, {}, {}
    for year, (name, url, first, last) in SOURCES.items():
        path = args.source_dir / name
        found = []
        group = ""
        with pdfplumber.open(path) as pdf:
            for number in range(first, last + 1):
                hunt_names = table_hunt_names(pdf.pages[number - 1])
                for line in (pdf.pages[number - 1].extract_text() or "").splitlines():
                    lower = line.lower().replace("multi-season", "multiseason")
                    for label, value in (
                        ("spring limited-entry", "SPRING"),
                        ("summer limited-entry", "SUMMER"),
                        ("fall limited-entry", "FALL"),
                        ("multiseason limited-entry", "MULTISEASON"),
                        ("limited-entry spot-and-stalk", "SPOT_AND_STALK"),
                        ("restricted pursuit limited-entry", "RESTRICTED_PURSUIT"),
                    ):
                        if lower.strip().startswith(label):
                            group = value
                    for code in re.findall(r"\bBR\d{4}\b", line):
                        if not group:
                            raise ValueError(f"Missing guidebook heading: {year}/{number}/{code}")
                        found.append({"hunt_code": code, "hunt_name": hunt_names[code],
                                      "program": group, "permit_type": "RESTRICTED_PURSUIT_DRAW" if group == "RESTRICTED_PURSUIT" else "LIMITED_ENTRY_HUNTING_DRAW", "pdf_page": number,
                                      "source_line": line})
            harvest[year] = []
            for number in HARVEST_PAGES[year]:
                page = pdf.pages[number - 1]
                words = page.extract_words()
                header = next(w for w in words if w["text"].lower() == "quota")
                for word in words:
                    if (re.fullmatch(r"\d{1,2}", word["text"])
                            and header["x0"] - 5 <= word["x0"] <= header["x1"] + 5
                            and word["top"] > header["bottom"]):
                        harvest[year].append({"hunt_code": "", "hunt_name": table_row_name(page, word),
                            "permit_type": "HARVEST_OBJECTIVE_NON_DRAW", "pdf_page": number,
                            "printed_harvest_objective_not_draw_quota": word["text"]})
        if len(found) != len({r["hunt_code"] for r in found}):
            raise ValueError(f"Duplicate hunt codes in {year} guidebook")
        inventories[year] = found
        provenance[year] = {"url": url, "sha256": sha(path), "path": str(path), "pages_checked": [first, last]}

    current = {r["hunt_code"] for r in inventories[2026]}
    previous = {r["hunt_code"] for r in inventories[2025]}
    historical = {}
    for year in range(2017, 2027):
        path = ROOT / f"data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv"
        codes = {r.get("hunt_code", "") for r in csv_rows(path) if r.get("hunt_code", "").startswith("BR")}
        historical[year] = {"sha256": sha(path), "codes": sorted(codes), "code_count": len(codes),
                            "not_listed_in_2026_guidebook": sorted(codes - current)}
    artifacts = {}
    for name in ("ml_draw_predictions_v1.csv", "bear_draw_predictions_v1.csv", "bear_predictions_v1.csv"):
        path = ROOT / "processed_data" / name
        rows = list(csv_rows(path))
        bear = [r for r in rows if r.get("hunt_code", "").startswith("BR")]
        availability = [r for r in bear if r.get("algorithm_status") == "MODELED_AVAILABILITY"]
        fields = ("hunt_code", "hunt_name", "species", "residency", "bear_draw_subtype", "algorithm_status", "p_draw", "availability_status")
        artifacts[name] = {"sha256": sha(path), "rows": len(rows), "bear_rows": len(bear),
                           "bear_status_counts": dict(Counter(r.get("algorithm_status") for r in bear)),
                           "bear_subtype_counts": dict(Counter(r.get("bear_draw_subtype") for r in bear)),
                           "availability": [{key: r.get(key) for key in fields} for r in availability],
                           "missing_2026_guidebook_codes": sorted(current - {r["hunt_code"] for r in bear})}
    database = list(csv_rows(ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"))
    db_codes = {r["hunt_code"] for r in database}
    summary = {"sources": provenance,
               "guidebook_counts": {y: dict(Counter(r["program"] for r in records)) for y, records in inventories.items()},
               "guidebook_rows": inventories,
               "harvest_objective_rows": harvest,
               "2026_codes_new_since_2025_guidebook": sorted(current - previous),
               "2025_codes_absent_from_2026_guidebook": sorted(previous - current),
               "historical_canonical": historical,
               "all_2017_2025_codes_absent_2026_guidebook": sorted(set().union(*(set(historical[y]["codes"]) for y in range(2017, 2026))) - current),
               "2026_guidebook_codes_missing_current_identity": sorted(current - db_codes),
               "artifacts": artifacts,
               "report_hashes": {name: sha(ROOT / "processed_data" / name) for name in ("bear_report.json", "draw_system_coverage_report.json")},
               "limitations": ["Absent from a guidebook is not proof of permanent retirement",
                               "Guidebook permits are inventory context, not applicant probability",
                               "BR1001/BR1007/BR1018 product IDs are not printed in these guidebook hunt tables"]}
    args.out_dir.mkdir(parents=True)
    (args.out_dir / "inventory.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for year, records in inventories.items():
        with (args.out_dir / f"guidebook_bear_codes_{year}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        with (args.out_dir / f"guidebook_bear_harvest_objective_{year}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(harvest[year][0]))
            writer.writeheader()
            writer.writerows(harvest[year])
    print(json.dumps({k: summary[k] for k in ("guidebook_counts", "2026_codes_new_since_2025_guidebook",
          "2025_codes_absent_from_2026_guidebook", "all_2017_2025_codes_absent_2026_guidebook",
          "2026_guidebook_codes_missing_current_identity")}, indent=2))


if __name__ == "__main__":
    main()
