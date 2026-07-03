#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pdfplumber


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FEEDER = REPO / "processed_data" / "draw_reality_engine.csv"
AUDIT_ROOT = REPO / "audits" / "feeder_blank_key_pdf_repair"

HUNT_RE = re.compile(
    r"Hunt:\s+(?P<hunt_code>[A-Z]{1,4}\d{4})\s+(?P<hunt_name>.+?)(?:\s+Page\s+(?P<report_page>\d+))?$",
    re.I,
)

ROW_RE = re.compile(
    r"^\s*"
    r"(?P<res_points>\d+)\s+"
    r"(?P<res_applicants>\d+)\s+"
    r"(?P<res_bonus>\d+)\s+"
    r"(?P<res_regular>\d+)\s+"
    r"(?P<res_total>\d+)\s+"
    r"(?P<res_ratio>N/A|1\s+in\s+[\d.]+|in\s+[\d.]+)"
    r"\s+"
    r"(?P<nr_points>\d+)\s+"
    r"(?P<nr_applicants>\d+)\s+"
    r"(?P<nr_bonus>\d+)\s+"
    r"(?P<nr_regular>\d+)\s+"
    r"(?P<nr_total>\d+)\s+"
    r"(?P<nr_ratio>N/A|1\s+in\s+[\d.]+|in\s+[\d.]+)"
    r"\s*$",
    re.I,
)


@dataclass(frozen=True)
class PdfRow:
    hunt_code: str
    hunt_name: str
    residency: str
    points: str
    eligible_applicants: str
    bonus_permits: str
    regular_permits: str
    total_permits: str
    success_ratio: str
    source_pdf_page: str
    source_report_page: str


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_source_name(value: str) -> str:
    return Path(clean(value).replace("\\", "/")).name.lower()


def normalize_ratio(value: str) -> str:
    text = clean(value)
    if text.lower().startswith("in "):
        return f"1 {text}"
    return text


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def blank_key(row: dict[str, str]) -> bool:
    return bool(clean(row.get("hunt_code"))) and (
        not clean(row.get("residency")) or clean(row.get("points")) == ""
    )


def scorable_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("year")),
        clean(row.get("residency")),
        clean(row.get("points")),
        normalize_source_name(row.get("source_file", "")),
    )


def hunt_source_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("year")),
        normalize_source_name(row.get("source_file", "")),
    )


def build_pdf_index(repo: Path) -> dict[str, list[Path]]:
    roots = [
        repo / "data_truth" / "draw_results_truth" / "raw_pdfs",
        repo / "pipeline" / "RAW",
        repo / "public" / "hard-copy",
        repo / "data",
        repo / "audits",
    ]
    index: dict[str, list[Path]] = defaultdict(list)
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.pdf"):
            index[path.name.lower()].append(path)
    return index


def resolve_pdf(repo: Path, source_file: str, pdf_index: dict[str, list[Path]]) -> Path | None:
    source = clean(source_file)
    if not source:
        return None
    direct = repo / source
    if direct.exists() and direct.suffix.lower() == ".pdf":
        return direct
    candidates = pdf_index.get(Path(source.replace("\\", "/")).name.lower(), [])
    if not candidates:
        return None

    def rank(path: Path) -> tuple[int, int, str]:
        text = str(path).lower().replace("\\", "/")
        if "/data_truth/draw_results_truth/raw_pdfs/" in text:
            bucket = 0
        elif "/pipeline/raw/" in text:
            bucket = 1
        elif "/public/hard-copy/" in text:
            bucket = 2
        elif "/data/" in text:
            bucket = 3
        else:
            bucket = 4
        return (bucket, len(text), text)

    return sorted(candidates, key=rank)[0]


def parse_pdf(pdf_path: Path) -> dict[str, list[PdfRow]]:
    rows_by_hunt: dict[str, list[PdfRow]] = defaultdict(list)
    current_code = ""
    current_name = ""
    current_report_page = ""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = clean_line(raw_line)
                hunt_match = HUNT_RE.search(line)
                if hunt_match:
                    current_code = hunt_match.group("hunt_code").upper()
                    current_name = clean(hunt_match.group("hunt_name"))
                    current_report_page = clean(hunt_match.group("report_page"))
                    continue
                if not current_code or line.startswith("Totals "):
                    continue
                row_match = ROW_RE.match(line)
                if not row_match:
                    continue
                m = row_match.groupdict()
                rows_by_hunt[current_code].append(
                    PdfRow(
                        hunt_code=current_code,
                        hunt_name=current_name,
                        residency="Resident",
                        points=clean(m["res_points"]),
                        eligible_applicants=clean(m["res_applicants"]),
                        bonus_permits=clean(m["res_bonus"]),
                        regular_permits=clean(m["res_regular"]),
                        total_permits=clean(m["res_total"]),
                        success_ratio=normalize_ratio(m["res_ratio"]),
                        source_pdf_page=str(page_num),
                        source_report_page=current_report_page,
                    )
                )
                rows_by_hunt[current_code].append(
                    PdfRow(
                        hunt_code=current_code,
                        hunt_name=current_name,
                        residency="Nonresident",
                        points=clean(m["nr_points"]),
                        eligible_applicants=clean(m["nr_applicants"]),
                        bonus_permits=clean(m["nr_bonus"]),
                        regular_permits=clean(m["nr_regular"]),
                        total_permits=clean(m["nr_total"]),
                        success_ratio=normalize_ratio(m["nr_ratio"]),
                        source_pdf_page=str(page_num),
                        source_report_page=current_report_page,
                    )
                )
    return rows_by_hunt


def repair_row(base: dict[str, str], pdf_row: PdfRow) -> dict[str, str]:
    row = dict(base)
    row["hunt_code"] = pdf_row.hunt_code
    if not clean(row.get("hunt_name")) or row.get("hunt_name") != pdf_row.hunt_name:
        row["hunt_name"] = pdf_row.hunt_name
    row["residency"] = pdf_row.residency
    row["points"] = pdf_row.points
    row["eligible_applicants"] = pdf_row.eligible_applicants
    row["bonus_permits"] = pdf_row.bonus_permits
    row["regular_permits"] = pdf_row.regular_permits
    row["total_permits"] = pdf_row.total_permits
    row["success_ratio"] = pdf_row.success_ratio
    row["source_pdf_page"] = pdf_row.source_pdf_page
    row["source_report_page"] = pdf_row.source_report_page
    row["validation_status"] = "VALID"
    notes = [
        note
        for note in clean(row.get("validation_notes")).split(";")
        if note and note not in {"RESIDENCY_BLANK", "POINTS_BLANK"}
    ]
    notes.append("PDF_REPAIRED_POINT_ROW")
    row["validation_notes"] = ";".join(dict.fromkeys(notes))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair blank feeder key rows by using local source PDFs as evidence."
    )
    parser.add_argument("--repo", default=str(REPO))
    parser.add_argument("--file", default=str(DEFAULT_FEEDER))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-audits", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    feeder = Path(args.file)
    if not feeder.is_absolute():
        feeder = repo / feeder
    feeder = feeder.resolve()

    fieldnames, rows = read_csv(feeder)
    out_dir = AUDIT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.write_audits:
        out_dir.mkdir(parents=True, exist_ok=True)

    nonblank_keys = {scorable_key(row) for row in rows if not blank_key(row)}
    nonblank_by_hunt_source: dict[tuple[str, str, str], int] = Counter(
        hunt_source_key(row) for row in rows if not blank_key(row)
    )

    pdf_index = build_pdf_index(repo)
    pdf_cache: dict[Path, dict[str, list[PdfRow]]] = {}
    repaired_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    counters = Counter()

    for line_number, row in enumerate(rows, start=2):
        if not blank_key(row):
            repaired_rows.append(row)
            counters["kept_existing_rows"] += 1
            continue

        counters["blank_key_rows"] += 1
        key = hunt_source_key(row)
        source_file = clean(row.get("source_file"))
        existing_point_rows = nonblank_by_hunt_source.get(key, 0)

        audit = {
            "line_number": str(line_number),
            "hunt_code": clean(row.get("hunt_code")).upper(),
            "year": clean(row.get("year")),
            "residency": clean(row.get("residency")),
            "points": clean(row.get("points")),
            "source_file": source_file,
            "action": "",
            "pdf_path": "",
            "replacement_rows": "0",
            "notes": "",
        }

        if existing_point_rows:
            counters["removed_summary_rows_existing_point_rows"] += 1
            audit["action"] = "removed_summary_row_existing_point_rows"
            audit["replacement_rows"] = "0"
            audit["notes"] = f"Existing point rows for hunt/year/source: {existing_point_rows}"
            audit_rows.append(audit)
            continue

        pdf_path = resolve_pdf(repo, source_file, pdf_index)
        if not pdf_path:
            counters["unresolved_pdf_not_found"] += 1
            audit["action"] = "kept_unresolved"
            audit["notes"] = "Source PDF not found locally"
            repaired_rows.append(row)
            audit_rows.append(audit)
            continue

        audit["pdf_path"] = str(pdf_path)
        if pdf_path not in pdf_cache:
            pdf_cache[pdf_path] = parse_pdf(pdf_path)
        pdf_rows = pdf_cache[pdf_path].get(clean(row.get("hunt_code")).upper(), [])
        if clean(row.get("residency")):
            pdf_rows = [pdf_row for pdf_row in pdf_rows if pdf_row.residency == clean(row.get("residency"))]
        if not pdf_rows:
            counters["unresolved_pdf_no_point_rows"] += 1
            audit["action"] = "kept_unresolved"
            audit["notes"] = "PDF found but no matching point table rows extracted"
            repaired_rows.append(row)
            audit_rows.append(audit)
            continue

        replacements = []
        for pdf_row in pdf_rows:
            candidate = repair_row(row, pdf_row)
            candidate_key = scorable_key(candidate)
            if candidate_key in nonblank_keys:
                continue
            nonblank_keys.add(candidate_key)
            replacements.append(candidate)

        if not replacements:
            counters["removed_summary_rows_pdf_rows_already_present"] += 1
            audit["action"] = "removed_summary_row_pdf_rows_already_present"
            audit["notes"] = "PDF rows matched rows already present in feeder"
            audit_rows.append(audit)
            continue

        repaired_rows.extend(replacements)
        counters["replaced_summary_rows_from_pdf"] += 1
        counters["pdf_replacement_rows_added"] += len(replacements)
        audit["action"] = "replaced_summary_row_from_pdf_point_table"
        audit["replacement_rows"] = str(len(replacements))
        audit["notes"] = "Local PDF point table extracted"
        audit_rows.append(audit)

    remaining_blank_keys = sum(1 for row in repaired_rows if blank_key(row))
    counters["output_rows"] = len(repaired_rows)
    counters["remaining_blank_key_rows"] = remaining_blank_keys

    if args.write_audits:
        write_csv(
            out_dir / "FEEDER_BLANK_KEY_PDF_REPAIR_DETAIL.csv",
            [
                "line_number",
                "hunt_code",
                "year",
                "residency",
                "points",
                "source_file",
                "action",
                "pdf_path",
                "replacement_rows",
                "notes",
            ],
            audit_rows,
        )
        write_csv(
            out_dir / "FEEDER_BLANK_KEY_PDF_REPAIR_SUMMARY.csv",
            ["metric", "value"],
            [{"metric": key, "value": value} for key, value in sorted(counters.items())],
        )

    if args.apply:
        backup_dir = out_dir if args.write_audits else AUDIT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{feeder.name}.backup_before_pdf_repair"
        shutil.copy2(feeder, backup)
        write_csv(feeder, fieldnames, repaired_rows)
        print(f"APPLIED: true")
        print(f"BACKUP: {backup}")
    else:
        print("APPLIED: false")

    print(f"FEEDER: {feeder}")
    print(f"INPUT_ROWS: {len(rows)}")
    print(f"OUTPUT_ROWS: {len(repaired_rows)}")
    print(f"BLANK_KEY_ROWS: {counters['blank_key_rows']}")
    print(f"REPLACED_SUMMARY_ROWS_FROM_PDF: {counters['replaced_summary_rows_from_pdf']}")
    print(f"PDF_REPLACEMENT_ROWS_ADDED: {counters['pdf_replacement_rows_added']}")
    print(f"REMOVED_SUMMARY_ROWS_EXISTING_POINT_ROWS: {counters['removed_summary_rows_existing_point_rows']}")
    print(f"UNRESOLVED_PDF_NOT_FOUND: {counters['unresolved_pdf_not_found']}")
    print(f"UNRESOLVED_PDF_NO_POINT_ROWS: {counters['unresolved_pdf_no_point_rows']}")
    print(f"REMAINING_BLANK_KEY_ROWS: {remaining_blank_keys}")
    if args.write_audits:
        print(f"AUDIT_OUTPUT_DIR: {out_dir}")

    return 1 if remaining_blank_keys else 0


if __name__ == "__main__":
    raise SystemExit(main())
