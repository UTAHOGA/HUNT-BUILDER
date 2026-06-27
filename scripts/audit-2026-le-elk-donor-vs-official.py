"""Extract donor L.E. elk PDFs and reconcile them against the official 2026 results PDF.

This is a source reconciliation audit only. It does not modify DATABASE.csv,
canonical rows, or prediction outputs.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: PyMuPDF / fitz") from exc

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: pypdf") from exc

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: rapidocr-onnxruntime") from exc


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2027"
OFFICIAL_PDF = SOURCE_DIR / ".pdf" / "2026_PERMITS=2027_MODEL__L.E. ELK.pdf"
DONOR_FILES = [
    SOURCE_DIR / "dwr le res elk.pdf",
    SOURCE_DIR / "elk le.pdf",
    SOURCE_DIR / "le elk nr.pdf",
    SOURCE_DIR / "le elk.pdf",
    SOURCE_DIR / "le res elk.pdf",
]
PRIMARY_DONOR_FILES = {
    "Resident": SOURCE_DIR / "le elk.pdf",
    "Nonresident": SOURCE_DIR / "le elk nr.pdf",
}

OUTPUT_DIR = ROOT / "processed_data" / "audits"
INVENTORY_CSV = OUTPUT_DIR / "2026_le_elk_donor_pdf_inventory.csv"
DONOR_SUMMARY_CSV = OUTPUT_DIR / "2026_le_elk_donor_summary.csv"
RECONCILIATION_CSV = OUTPUT_DIR / "2026_le_elk_donor_vs_official_reconciliation.csv"
SUMMARY_JSON = OUTPUT_DIR / "2026_le_elk_donor_vs_official_reconciliation.json"
REPORT_MD = OUTPUT_DIR / "2026_le_elk_donor_vs_official_reconciliation.md"

HUNT_RE = re.compile(r"Hunt:\s+(?P<hunt_code>EB\d{4})\s+(?P<hunt_name>.+?)(?:\s+Page\s+\d+)?$", re.I)
ROW_RE = re.compile(
    r"^\s*"
    r"(?P<res_points>\d+)\s+"
    r"(?P<res_applicants>\d+)\s+"
    r"(?P<res_bonus>\d+)\s+"
    r"(?P<res_regular>\d+)\s+"
    r"(?P<res_total>\d+)\s+"
    r"(?P<res_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s+"
    r"(?P<nr_points>\d+)\s+"
    r"(?P<nr_applicants>\d+)\s+"
    r"(?P<nr_bonus>\d+)\s+"
    r"(?P<nr_regular>\d+)\s+"
    r"(?P<nr_total>\d+)\s+"
    r"(?P<nr_ratio>N/A|1\s+in\s+[\d.]+)"
    r"\s*$",
    re.I,
)

DONOR_HUNT_RE = re.compile(r"\[(?P<hunt_code>EB\d{4})\]\s*-\s*(?P<rest>.+)", re.I)
TOTAL_QUOTA_RE = re.compile(r"Total\s+Quota:\s*(\d+)", re.I)
FIRST_CHOICE_PERMITS_RE = re.compile(r"1st\s*Choice\s*Permits:\s*(\d+)", re.I)
FIRST_CHOICE_APPS_RE = re.compile(r"1st\s*Choice\s*Apps:\s*(\d+)", re.I)
FIRST_CHOICE_SUCC_RE = re.compile(r"1st\s*Choice\s*Succ:\s*(N/A|[\d.]+%)", re.I)
MAX_RND_RE = re.compile(r"Max\s*Rnd:\s*(\d+)", re.I)
REG_RND_RE = re.compile(r"Reg\s*Rnd:\s*(\d+)", re.I)
WEAPON_RE = re.compile(r"(Archery|Muzzleloader|Any Legal Weapon)", re.I)


def clean_text(value: str | None) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split())


def normalize_hunt_name(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -")


def write_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_int(value: str | None) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_official_pdf(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    current_hunt_code = ""
    current_hunt_name = ""
    reader = PdfReader(str(path))
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = clean_text(raw_line)
            hunt_match = HUNT_RE.search(line)
            if hunt_match:
                current_hunt_code = hunt_match.group("hunt_code").strip()
                current_hunt_name = hunt_match.group("hunt_name").strip()
                continue
            if not current_hunt_code or line.startswith("Totals "):
                continue
            row_match = ROW_RE.match(line)
            if not row_match:
                continue
            match = row_match.groupdict()
            rows.append(
                {
                    "hunt_code": current_hunt_code,
                    "hunt_name": current_hunt_name,
                    "page_number": page_number,
                    "residency": "Resident",
                    "points": int(match["res_points"]),
                    "eligible_applicants": int(match["res_applicants"]),
                    "bonus_permits": int(match["res_bonus"]),
                    "regular_permits": int(match["res_regular"]),
                    "total_permits": int(match["res_total"]),
                }
            )
            rows.append(
                {
                    "hunt_code": current_hunt_code,
                    "hunt_name": current_hunt_name,
                    "page_number": page_number,
                    "residency": "Nonresident",
                    "points": int(match["nr_points"]),
                    "eligible_applicants": int(match["nr_applicants"]),
                    "bonus_permits": int(match["nr_bonus"]),
                    "regular_permits": int(match["nr_regular"]),
                    "total_permits": int(match["nr_total"]),
                }
            )
    return rows


def summarize_official(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["hunt_code"]), str(row["residency"]))
        bucket = grouped.setdefault(
            key,
            {
                "hunt_code": row["hunt_code"],
                "hunt_name": row["hunt_name"],
                "residency": row["residency"],
                "official_page_number": row["page_number"],
                "official_total_apps": 0,
                "official_bonus_permits": 0,
                "official_regular_permits": 0,
                "official_total_permits": 0,
            },
        )
        bucket["official_total_apps"] = int(bucket["official_total_apps"]) + int(row["eligible_applicants"])
        bucket["official_bonus_permits"] = int(bucket["official_bonus_permits"]) + int(row["bonus_permits"])
        bucket["official_regular_permits"] = int(bucket["official_regular_permits"]) + int(row["regular_permits"])
        bucket["official_total_permits"] = int(bucket["official_total_permits"]) + int(row["total_permits"])
    return sorted(grouped.values(), key=lambda item: (str(item["hunt_code"]), str(item["residency"])))


def ocr_page_text(page: fitz.Page, ocr: RapidOCR) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    result, _ = ocr(pix.tobytes("png"))
    if not result:
        return ""
    return clean_text(" ".join(line[1] for line in result))


def parse_donor_hunt_name(prefix_text: str) -> str:
    text = clean_text(prefix_text)
    text = re.split(r"\bLimited-Entry\b|\bLimited-entry\b", text, maxsplit=1, flags=re.I)[0]
    text = re.split(r"\bBull\s+Elk\b", text, maxsplit=1, flags=re.I)[0]
    return normalize_hunt_name(text)


def parse_donor_page(text: str, source_file: str, page_number: int, residency: str) -> dict[str, object] | None:
    hunt_match = DONOR_HUNT_RE.search(text)
    if not hunt_match:
        return None
    if not TOTAL_QUOTA_RE.search(text):
        return None
    hunt_code = hunt_match.group("hunt_code").upper()
    rest = hunt_match.group("rest")
    weapon_match = WEAPON_RE.search(rest)
    weapon = weapon_match.group(1) if weapon_match else ""
    hunt_name = parse_donor_hunt_name(rest)
    return {
        "source_file": source_file,
        "page_number": page_number,
        "residency": residency,
        "hunt_code": hunt_code,
        "hunt_name": hunt_name,
        "weapon": weapon,
        "donor_total_quota": to_int(TOTAL_QUOTA_RE.search(text).group(1) if TOTAL_QUOTA_RE.search(text) else ""),
        "donor_first_choice_permits": to_int(
            FIRST_CHOICE_PERMITS_RE.search(text).group(1) if FIRST_CHOICE_PERMITS_RE.search(text) else ""
        ),
        "donor_first_choice_apps": to_int(
            FIRST_CHOICE_APPS_RE.search(text).group(1) if FIRST_CHOICE_APPS_RE.search(text) else ""
        ),
        "donor_first_choice_succ": clean_text(
            FIRST_CHOICE_SUCC_RE.search(text).group(1) if FIRST_CHOICE_SUCC_RE.search(text) else ""
        ),
        "donor_max_rnd": to_int(MAX_RND_RE.search(text).group(1) if MAX_RND_RE.search(text) else ""),
        "donor_reg_rnd": to_int(REG_RND_RE.search(text).group(1) if REG_RND_RE.search(text) else ""),
        "raw_ocr_text": text,
    }


def donor_page_should_be_hunt(path: Path, page_number: int) -> bool:
    name = path.name.lower()
    if name == "le elk.pdf":
        return page_number >= 4 and page_number % 2 == 0
    if name == "le elk nr.pdf":
        return page_number >= 3 and page_number % 2 == 1
    return True


def extract_donor_summary(path: Path, residency: str, ocr: RapidOCR) -> list[dict[str, object]]:
    doc = fitz.open(str(path))
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for page_index in range(doc.page_count):
        page_number = page_index + 1
        if not donor_page_should_be_hunt(path, page_number):
            continue
        text = ocr_page_text(doc.load_page(page_index), ocr)
        parsed = parse_donor_page(text, path.name, page_number, residency)
        if not parsed:
            continue
        key = (str(parsed["hunt_code"]), int(parsed["page_number"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(parsed)
    return rows


def donor_inventory(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        exists = path.exists()
        page_count = ""
        size_bytes = ""
        if exists:
            doc = fitz.open(str(path))
            page_count = doc.page_count
            size_bytes = path.stat().st_size
        role = []
        if path == OFFICIAL_PDF:
            role.append("OFFICIAL")
        if path == PRIMARY_DONOR_FILES["Resident"]:
            role.append("PRIMARY_RESIDENT_DONOR")
        if path == PRIMARY_DONOR_FILES["Nonresident"]:
            role.append("PRIMARY_NONRESIDENT_DONOR")
        if path.name in {"le res elk.pdf", "dwr le res elk.pdf"}:
            role.append("SUPPORTING_RESIDENT_DONOR")
        if path.name == "elk le.pdf":
            role.append("ENCODING_TROUBLE_DONOR")
        rows.append(
            {
                "file_name": path.name,
                "relative_path": str(path.relative_to(ROOT)),
                "exists": "YES" if exists else "NO",
                "size_bytes": size_bytes,
                "page_count": page_count,
                "role": ";".join(role),
            }
        )
    return rows


def reconcile(
    donor_rows: list[dict[str, object]], official_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    donor_index = {(str(row["hunt_code"]), str(row["residency"])): row for row in donor_rows}
    official_index = {(str(row["hunt_code"]), str(row["residency"])): row for row in official_rows}
    keys = sorted(set(donor_index) | set(official_index))
    rows: list[dict[str, object]] = []
    for key in keys:
        donor = donor_index.get(key)
        official = official_index.get(key)
        hunt_code, residency = key
        if donor and official:
            field_checks = {
                "apps_match": donor["donor_first_choice_apps"] == official["official_total_apps"],
                "bonus_match": donor["donor_max_rnd"] == official["official_bonus_permits"],
                "regular_match": donor["donor_reg_rnd"] == official["official_regular_permits"],
                "total_match": donor["donor_total_quota"] == official["official_total_permits"],
                "first_choice_permits_match": donor["donor_first_choice_permits"] == official["official_total_permits"],
            }
            mismatch_fields = [name for name, ok in field_checks.items() if not ok]
            status = "MATCH" if not mismatch_fields else "REVIEW"
            rows.append(
                {
                    "status": status,
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "hunt_name_donor": donor["hunt_name"],
                    "hunt_name_official": official["hunt_name"],
                    "donor_source_file": donor["source_file"],
                    "donor_page_number": donor["page_number"],
                    "official_page_number": official["official_page_number"],
                    "donor_total_quota": donor["donor_total_quota"],
                    "official_total_permits": official["official_total_permits"],
                    "donor_first_choice_permits": donor["donor_first_choice_permits"],
                    "donor_first_choice_apps": donor["donor_first_choice_apps"],
                    "official_total_apps": official["official_total_apps"],
                    "donor_max_rnd": donor["donor_max_rnd"],
                    "official_bonus_permits": official["official_bonus_permits"],
                    "donor_reg_rnd": donor["donor_reg_rnd"],
                    "official_regular_permits": official["official_regular_permits"],
                    "donor_first_choice_succ": donor["donor_first_choice_succ"],
                    "mismatch_fields": ";".join(mismatch_fields),
                }
            )
            continue
        if donor and not official:
            rows.append(
                {
                    "status": "DONOR_ONLY",
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "hunt_name_donor": donor["hunt_name"],
                    "hunt_name_official": "",
                    "donor_source_file": donor["source_file"],
                    "donor_page_number": donor["page_number"],
                    "official_page_number": "",
                    "donor_total_quota": donor["donor_total_quota"],
                    "official_total_permits": "",
                    "donor_first_choice_permits": donor["donor_first_choice_permits"],
                    "donor_first_choice_apps": donor["donor_first_choice_apps"],
                    "official_total_apps": "",
                    "donor_max_rnd": donor["donor_max_rnd"],
                    "official_bonus_permits": "",
                    "donor_reg_rnd": donor["donor_reg_rnd"],
                    "official_regular_permits": "",
                    "donor_first_choice_succ": donor["donor_first_choice_succ"],
                    "mismatch_fields": "missing_official",
                }
            )
            continue
        if official and not donor:
            rows.append(
                {
                    "status": "OFFICIAL_ONLY",
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "hunt_name_donor": "",
                    "hunt_name_official": official["hunt_name"],
                    "donor_source_file": "",
                    "donor_page_number": "",
                    "official_page_number": official["official_page_number"],
                    "donor_total_quota": "",
                    "official_total_permits": official["official_total_permits"],
                    "donor_first_choice_permits": "",
                    "donor_first_choice_apps": "",
                    "official_total_apps": official["official_total_apps"],
                    "donor_max_rnd": "",
                    "official_bonus_permits": official["official_bonus_permits"],
                    "donor_reg_rnd": "",
                    "official_regular_permits": official["official_regular_permits"],
                    "donor_first_choice_succ": "",
                    "mismatch_fields": "missing_donor",
                }
            )
    return rows


def build_markdown(summary: dict[str, object], reconciliation_rows: list[dict[str, object]]) -> str:
    mismatches = [row for row in reconciliation_rows if row["status"] != "MATCH"][:20]
    lines = [
        "# 2026 L.E. Elk Donor PDF Reconciliation",
        "",
        "This audit extracts the usable donor PDFs first, then reconciles them against the official `2026_PERMITS=2027_MODEL__L.E. ELK.pdf` draw-results source.",
        "",
        "## File Handling",
        "",
        f"- Official PDF: `{summary['official_pdf']}`",
        f"- Primary resident donor: `{summary['primary_resident_donor']}`",
        f"- Primary nonresident donor: `{summary['primary_nonresident_donor']}`",
        f"- Supporting resident donor copies observed: {summary['supporting_resident_donor_count']}",
        f"- Encoding-trouble donor copies observed: {summary['encoding_trouble_donor_count']}",
        "",
        "## Coverage",
        "",
        f"- Official hunt-residency summaries: {summary['official_summary_rows']}",
        f"- Donor hunt-residency summaries: {summary['donor_summary_rows']}",
        f"- Match rows: {summary['match_rows']}",
        f"- Review rows: {summary['review_rows']}",
        f"- Donor-only rows: {summary['donor_only_rows']}",
        f"- Official-only rows: {summary['official_only_rows']}",
        "",
        "## Mismatch Fields",
        "",
    ]
    for field, count in summary["mismatch_field_counts"].items():
        lines.append(f"- {field}: {count}")
    lines.extend(["", "## First Review Rows", ""])
    if not mismatches:
        lines.append("- No mismatches detected.")
    else:
        for row in mismatches:
            lines.append(
                f"- `{row['hunt_code']}` `{row['residency']}` `{row['status']}` "
                f"mismatch=`{row['mismatch_fields']}` donor_total=`{row['donor_total_quota']}` "
                f"official_total=`{row['official_total_permits']}` donor_apps=`{row['donor_first_choice_apps']}` "
                f"official_apps=`{row['official_total_apps']}`"
            )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "This is extraction and reconciliation evidence only. It does not promote PDF values into DATABASE.csv, canonical rows, or predictive outputs.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    inventory_rows = donor_inventory([OFFICIAL_PDF, *DONOR_FILES])
    write_rows(
        INVENTORY_CSV,
        inventory_rows,
        ["file_name", "relative_path", "exists", "size_bytes", "page_count", "role"],
    )

    official_point_rows = parse_official_pdf(OFFICIAL_PDF)
    official_summary_rows = summarize_official(official_point_rows)

    ocr = RapidOCR()
    donor_rows: list[dict[str, object]] = []
    donor_rows.extend(extract_donor_summary(PRIMARY_DONOR_FILES["Resident"], "Resident", ocr))
    donor_rows.extend(extract_donor_summary(PRIMARY_DONOR_FILES["Nonresident"], "Nonresident", ocr))
    donor_rows = sorted(donor_rows, key=lambda row: (str(row["hunt_code"]), str(row["residency"])))
    write_rows(
        DONOR_SUMMARY_CSV,
        donor_rows,
        [
            "source_file",
            "page_number",
            "residency",
            "hunt_code",
            "hunt_name",
            "weapon",
            "donor_total_quota",
            "donor_first_choice_permits",
            "donor_first_choice_apps",
            "donor_first_choice_succ",
            "donor_max_rnd",
            "donor_reg_rnd",
            "raw_ocr_text",
        ],
    )

    reconciliation_rows = reconcile(donor_rows, official_summary_rows)
    write_rows(
        RECONCILIATION_CSV,
        reconciliation_rows,
        [
            "status",
            "hunt_code",
            "residency",
            "hunt_name_donor",
            "hunt_name_official",
            "donor_source_file",
            "donor_page_number",
            "official_page_number",
            "donor_total_quota",
            "official_total_permits",
            "donor_first_choice_permits",
            "donor_first_choice_apps",
            "official_total_apps",
            "donor_max_rnd",
            "official_bonus_permits",
            "donor_reg_rnd",
            "official_regular_permits",
            "donor_first_choice_succ",
            "mismatch_fields",
        ],
    )

    mismatch_counter = Counter()
    for row in reconciliation_rows:
        if row["status"] == "MATCH":
            continue
        for field in clean_text(str(row["mismatch_fields"])).split(";"):
            if field:
                mismatch_counter[field] += 1

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2026_le_elk_donor_vs_official_reconciliation",
        "official_pdf": str(OFFICIAL_PDF.relative_to(ROOT)),
        "primary_resident_donor": str(PRIMARY_DONOR_FILES["Resident"].relative_to(ROOT)),
        "primary_nonresident_donor": str(PRIMARY_DONOR_FILES["Nonresident"].relative_to(ROOT)),
        "supporting_resident_donor_count": sum(
            1 for row in inventory_rows if "SUPPORTING_RESIDENT_DONOR" in str(row["role"])
        ),
        "encoding_trouble_donor_count": sum(
            1 for row in inventory_rows if "ENCODING_TROUBLE_DONOR" in str(row["role"])
        ),
        "official_point_rows": len(official_point_rows),
        "official_summary_rows": len(official_summary_rows),
        "donor_summary_rows": len(donor_rows),
        "match_rows": sum(1 for row in reconciliation_rows if row["status"] == "MATCH"),
        "review_rows": sum(1 for row in reconciliation_rows if row["status"] == "REVIEW"),
        "donor_only_rows": sum(1 for row in reconciliation_rows if row["status"] == "DONOR_ONLY"),
        "official_only_rows": sum(1 for row in reconciliation_rows if row["status"] == "OFFICIAL_ONLY"),
        "mismatch_field_counts": dict(sorted(mismatch_counter.items())),
        "outputs": {
            "inventory_csv": str(INVENTORY_CSV.relative_to(ROOT)),
            "donor_summary_csv": str(DONOR_SUMMARY_CSV.relative_to(ROOT)),
            "reconciliation_csv": str(RECONCILIATION_CSV.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "report_md": str(REPORT_MD.relative_to(ROOT)),
        },
        "guardrail": "Extraction and reconciliation evidence only; no database, canonical, or predictive promotion is performed.",
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_markdown(summary, reconciliation_rows), encoding="utf-8")

    print(
        "2026 L.E. elk donor reconciliation complete: "
        f"{summary['match_rows']} match, {summary['review_rows']} review, "
        f"{summary['donor_only_rows']} donor-only, {summary['official_only_rows']} official-only."
    )
    return 0 if summary["review_rows"] == 0 and summary["donor_only_rows"] == 0 and summary["official_only_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
