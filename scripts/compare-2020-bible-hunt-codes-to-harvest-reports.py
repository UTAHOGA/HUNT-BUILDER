from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
BIBLE_2020 = ROOT / "processed_data" / "audits" / "bible_hunt_code_year_documents" / "bible_hunt_code_year_document_2020.csv"
AUDIT_DIR = ROOT / "processed_data" / "audits" / "bible_hunt_code_year_documents"
DOC_REPORT = ROOT / "docs" / "harvest_report_2020_hunt_code_confirmation.md"

HARVEST_REPORTS = [
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "harvest_report" / "2020_le_oial_all.pdf",
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "harvest_report" / "2020_antlerless_hr.pdf",
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "harvest_report" / "General-season buck deer.pdf",
]

OUT_RAW = AUDIT_DIR / "harvest_report_2020_hunt_code_source_hits.csv"
OUT_COMPARE = AUDIT_DIR / "harvest_report_2020_hunt_code_confirmation.csv"
OUT_SUMMARY = AUDIT_DIR / "harvest_report_2020_hunt_code_confirmation_summary.json"

CODE_RE = re.compile(r"\b[A-Z]{2,3}\d{3,4}\b")

RAW_FIELDS = [
    "report_year",
    "source_class",
    "source_file",
    "source_page",
    "hunt_code",
    "prefix",
    "source_family",
    "context",
]

COMPARE_FIELDS = [
    "hunt_code",
    "prefix",
    "confirmation_status",
    "in_bible_2020",
    "in_harvest_reports",
    "bible_species",
    "bible_title",
    "bible_source_files",
    "harvest_source_files",
    "harvest_source_pages",
    "harvest_context_samples",
    "notes",
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def prefix_of(code: str) -> str:
    match = re.match(r"^([A-Z]+)", code or "")
    return match.group(1) if match else ""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_family(path: Path) -> str:
    name = path.name.lower()
    if "le_oial" in name:
        return "HARVEST_LIMITED_ENTRY_ONCE_IN_A_LIFETIME"
    if "antlerless" in name:
        return "HARVEST_ANTLERLESS"
    if "general-season buck deer" in name:
        return "HARVEST_GENERAL_SEASON_BUCK_DEER"
    return "HARVEST_REVIEW"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extract_harvest_hits() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in HARVEST_REPORTS:
        reader = PdfReader(str(path))
        family = source_family(path)
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                context = clean(line)
                if not context:
                    continue
                codes = sorted(set(CODE_RE.findall(context.upper())))
                for code in codes:
                    rows.append(
                        {
                            "report_year": "2020",
                            "source_class": "harvest_results",
                            "source_file": rel(path),
                            "source_page": str(page_number),
                            "hunt_code": code,
                            "prefix": prefix_of(code),
                            "source_family": family,
                            "context": context,
                        }
                    )
    return rows


def build_compare(raw_hits: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    bible_rows = read_csv(BIBLE_2020)
    bible_by_code = {row["comparison_hunt_code"]: row for row in bible_rows if row.get("comparison_hunt_code")}
    harvest_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw_hits:
        harvest_by_code[row["hunt_code"]].append(row)

    all_codes = sorted(set(bible_by_code) | set(harvest_by_code))
    compare_rows: list[dict[str, object]] = []
    for code in all_codes:
        in_bible = code in bible_by_code
        in_harvest = code in harvest_by_code
        if in_bible and in_harvest:
            status = "CONFIRMED_BY_2020_HARVEST_REPORT"
            notes = "Hunt code appears in both the 2020 BIBLE draw-result document and the selected 2020 harvest reports."
        elif in_bible:
            status = "BIBLE_ONLY_NOT_IN_SELECTED_HARVEST_REPORTS"
            notes = "Code appears in BIBLE 2020 but not in the three selected harvest reports; this can be expected for species/families not covered by the selected harvest PDFs."
        else:
            status = "HARVEST_ONLY_NOT_IN_BIBLE_2020"
            notes = "Code appears in selected 2020 harvest reports but not in the 2020 BIBLE draw-result document; review for draw-vs-harvest scope, extraction gap, or source-family mismatch."

        bible = bible_by_code.get(code, {})
        harvest_rows = harvest_by_code.get(code, [])
        compare_rows.append(
            {
                "hunt_code": code,
                "prefix": prefix_of(code),
                "confirmation_status": status,
                "in_bible_2020": "YES" if in_bible else "NO",
                "in_harvest_reports": "YES" if in_harvest else "NO",
                "bible_species": bible.get("species_from_prefix", ""),
                "bible_title": bible.get("best_hunt_title_or_row_text", ""),
                "bible_source_files": bible.get("source_files", ""),
                "harvest_source_files": "|".join(sorted({row["source_file"] for row in harvest_rows})),
                "harvest_source_pages": "|".join(sorted({row["source_page"] for row in harvest_rows}, key=lambda value: int(value) if value.isdigit() else 9999)),
                "harvest_context_samples": " || ".join(row["context"] for row in harvest_rows[:3]),
                "notes": notes,
            }
        )

    status_counts = Counter(row["confirmation_status"] for row in compare_rows)
    status_prefix_counts = {
        status: dict(Counter(row["prefix"] for row in compare_rows if row["confirmation_status"] == status).most_common())
        for status in sorted(status_counts)
    }
    harvest_only_codes = [
        row["hunt_code"]
        for row in compare_rows
        if row["confirmation_status"] == "HARVEST_ONLY_NOT_IN_BIBLE_2020"
    ]
    prefix_counts = Counter(row["prefix"] for row in compare_rows if row["confirmation_status"] != "BIBLE_ONLY_NOT_IN_SELECTED_HARVEST_REPORTS")
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scope": "Compare 2020 BIBLE hunt-code year document against three selected 2020 harvest reports for hunt-code confirmation only.",
        "source_bible_year_document": rel(BIBLE_2020),
        "harvest_reports": [rel(path) for path in HARVEST_REPORTS],
        "raw_harvest_code_hits": len(raw_hits),
        "unique_harvest_codes": len(harvest_by_code),
        "unique_bible_2020_codes": len(bible_by_code),
        "unique_codes_compared": len(compare_rows),
        "confirmation_status_counts": dict(status_counts),
        "confirmation_status_prefix_counts": status_prefix_counts,
        "harvest_only_codes": harvest_only_codes,
        "non_bible_only_prefix_counts": dict(prefix_counts),
        "guardrail": "Harvest reports are used here only as hunt-code existence confirmation evidence. This does not change DATABASE.csv, draw truth, permit truth, harvest values, or prediction inputs.",
        "outputs": {
            "raw_hits_csv": rel(OUT_RAW),
            "comparison_csv": rel(OUT_COMPARE),
            "summary_json": rel(OUT_SUMMARY),
            "report_md": rel(DOC_REPORT),
        },
    }
    return compare_rows, summary


def write_report(summary: dict[str, object]) -> None:
    lines = [
        "# 2020 Harvest Report Hunt-Code Confirmation",
        "",
        "## Purpose",
        "",
        "This audit compares the independent 2020 BIBLE hunt-code year document against three selected 2020 harvest reports. It confirms code existence only; it does not promote harvest, draw, or permit values.",
        "",
        "## Sources",
        "",
        f"- BIBLE year document: `{summary['source_bible_year_document']}`",
    ]
    for source in summary["harvest_reports"]:
        lines.append(f"- Harvest report: `{source}`")
    lines.extend(
        [
            "",
            "## Key Counts",
            "",
            f"- Raw harvest code hits: `{summary['raw_harvest_code_hits']}`",
            f"- Unique harvest-report codes: `{summary['unique_harvest_codes']}`",
            f"- Unique BIBLE 2020 codes: `{summary['unique_bible_2020_codes']}`",
            f"- Unique codes compared: `{summary['unique_codes_compared']}`",
            "",
            "## Confirmation Status Counts",
            "",
        ]
    )
    for key, value in sorted(summary["confirmation_status_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Prefix Counts By Status", ""])
    for status, counts in summary["confirmation_status_prefix_counts"].items():
        rendered = ", ".join(f"{prefix}={count}" for prefix, count in counts.items())
        lines.append(f"- `{status}`: {rendered}")
    lines.extend(["", "## Harvest-Only Codes", ""])
    if summary["harvest_only_codes"]:
        lines.append("These codes appear in the selected 2020 harvest reports but not in the 2020 BIBLE draw-result year document:")
        lines.append("")
        lines.append("```text")
        lines.extend(summary["harvest_only_codes"])
        lines.append("```")
    else:
        lines.append("No harvest-only codes found.")
    lines.extend(["", "## Outputs", ""])
    for value in summary["outputs"].values():
        lines.append(f"- `{value}`")
    lines.extend(["", "## Guardrail", "", summary["guardrail"]])
    DOC_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    raw_hits = extract_harvest_hits()
    compare_rows, summary = build_compare(raw_hits)
    write_csv(OUT_RAW, raw_hits, RAW_FIELDS)
    write_csv(OUT_COMPARE, compare_rows, COMPARE_FIELDS)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
