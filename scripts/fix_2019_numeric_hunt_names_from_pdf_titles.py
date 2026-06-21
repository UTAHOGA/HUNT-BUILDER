import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv"
)

AUDIT_DIR = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2019_for_2020"
    / "hunt_name_numeric_cleanup"
)
BACKUPS = AUDIT_DIR / "backups"

SOURCE_PDFS = {
    "19_drawing_odds(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__BLACK BEAR DRAW RESULTS.pdf",
    "19_antlerless_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__ANTLERLESS DEER DRAW RESULTS.pdf",
    "19_youth_antlerless_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__YOUTH ANTLERLESS DEER DRAW RESULTS.pdf",
    "19_antlerless_elk_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__ANTLERLESS ELK DRAW RESULTS.pdf",
    "19_youth_antlerless_elk_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__YOUTH ANTLERLESS ELK DRAW RESULTS.pdf",
    "19_antlerless_pronghorn_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__ANTLERLESS PRONGHORN DRAW RESULTS.pdf",
    "19_youth_antlerless_pronghorn_drawing_odds_report(1).pdf": REPO
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2019_PERMITS=2020_MODEL"
    / "2019_PERMITS=2020_MODEL__YOUTH ANTLERLESS PRONGHORN DRAW RESULTS.pdf",
    "2019_turkey_bonus_points(1).pdf": REPO
    / "audits"
    / "truth_document_audit"
    / "live_dwr_bear_cougar_turkey_odds_refresh_20260618_170145"
    / "downloads"
    / "unknown_year__2019_turkey_bonus_points.pdf",
    "2019_youth_turkey_bonus_points(1).pdf": REPO
    / "audits"
    / "truth_document_audit"
    / "live_dwr_bear_cougar_turkey_odds_refresh_20260618_170145"
    / "downloads"
    / "unknown_year__2019_youth_turkey_bonus_points.pdf",
    "2020_cougar_odds_report(2).pdf": REPO
    / "audits"
    / "truth_document_audit"
    / "live_dwr_bear_cougar_turkey_odds_refresh_20260618_170145"
    / "downloads"
    / "unknown_year__2020_cougar_odds_report.pdf",
}


def clean(value):
    return "" if value is None else str(value).strip()


def is_numeric_text(value):
    return bool(re.fullmatch(r"\d+", clean(value)))


def hunt_code_from_hunt_line(text):
    match = re.search(r"\bHunt:\s*([A-Z]{2}\d{4})\b", text)
    if match:
        return match.group(1)
    return ""


def title_from_page(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    candidate_lines = []
    for line in lines:
        if line.startswith("Hunt:"):
            continue
        if line.startswith("Utah Division"):
            break
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", line):
            break
        if line.startswith("Page "):
            break
        candidate_lines.append(line)

    if not candidate_lines:
        return ""

    title = candidate_lines[0]
    title = re.sub(r"^Hunt:\s*[A-Z]{2}\d{4}\s*", "", title).strip()
    return title


def build_title_map():
    mapping = {}
    by_hunt_code = {}
    page_info_by_hunt_code = {}
    source_page_titles = defaultdict(dict)

    for source_file, pdf_path in SOURCE_PDFS.items():
        if not pdf_path.exists():
            continue

        reader = PdfReader(str(pdf_path))
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            hunt_code = hunt_code_from_hunt_line(text)
            if not hunt_code:
                continue

            title = title_from_page(text)
            if not title:
                continue

            source_page_titles[source_file][hunt_code] = {
                "title": title,
                "page_number": page_number,
                "pdf_path": str(pdf_path),
            }
            mapping[(source_file, hunt_code)] = title
            by_hunt_code.setdefault(hunt_code, title)
            page_info_by_hunt_code.setdefault(hunt_code, source_page_titles[source_file][hunt_code])

    return mapping, by_hunt_code, page_info_by_hunt_code, source_page_titles


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    title_map, title_by_hunt_code, page_info_by_hunt_code, source_page_titles = build_title_map()

    with TARGET.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    backup = BACKUPS / f"numeric_cleanup_{timestamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(TARGET.read_bytes())

    numeric_rows = 0
    changed_rows = 0
    samples = []
    counts_by_source = Counter()
    counts_by_code = Counter()

    for row in rows:
        source_file = clean(row.get("source_file"))
        hunt_code = clean(row.get("hunt_code"))
        hunt_name = clean(row.get("hunt_name"))

        if not is_numeric_text(hunt_name):
            continue

        numeric_rows += 1
        title = title_map.get((source_file, hunt_code)) or title_by_hunt_code.get(hunt_code)
        if not title:
            continue

        counts_by_source[source_file] += 1
        counts_by_code[hunt_code] += 1

        if hunt_name != title:
            row["hunt_name"] = title
            changed_rows += 1
            if len(samples) < 200:
                samples.append(
                    {
                        "source_file": source_file,
                        "hunt_code": hunt_code,
                        "old_hunt_name": hunt_name,
                        "new_hunt_name": title,
                        "page_number": (
                            source_page_titles.get(source_file, {}).get(hunt_code, {}).get("page_number")
                            or page_info_by_hunt_code.get(hunt_code, {}).get("page_number")
                        ),
                        "pdf_path": (
                            source_page_titles.get(source_file, {}).get(hunt_code, {}).get("pdf_path")
                            or page_info_by_hunt_code.get(hunt_code, {}).get("pdf_path")
                        ),
                    }
                )

    temp_target = TARGET.with_name(f"{TARGET.stem}.numeric_cleanup_{timestamp}.tmp")
    with temp_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(temp_target), str(TARGET))

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup": str(backup),
        "numeric_rows_scanned": numeric_rows,
        "rows_changed": changed_rows,
        "changed_by_source_file": dict(sorted(counts_by_source.items())),
        "changed_by_hunt_code": dict(sorted(counts_by_code.items())),
        "sample_changes": samples[:25],
        "status": "PASS" if changed_rows else "NO_CHANGES",
        "source_pdfs": {key: str(value) for key, value in SOURCE_PDFS.items()},
    }
    (AUDIT_DIR / "2019_numeric_hunt_name_cleanup_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
