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
    / "draw_results_2020_for_2021_candidate_promotion_file_records.csv"
)
AUDIT_DIR = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2020_for_2021"
    / "hunt_name_numeric_cleanup"
)
BACKUPS = AUDIT_DIR / "backups"
SOURCE_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2020_PERMITS=2021_MODEL"

PROGRAM_PREFIXES = [
    "Antlerless Rocky Mountain Bighorn Sheep",
    "Rocky Mountain Bighorn Sheep",
    "Limited Entry Archery Buck Pronghorn",
    "Limited Entry Alw (rifle) Buck Pronghorn",
    "Limited Entry Muzzleloader Buck Pronghorn",
    "Limited Entry Buck Pronghorn",
    "Limited Entry Archery Buck Deer",
    "Limited Entry Alw (rifle) Buck Deer",
    "Limited Entry Muzzleloader Buck Deer",
    "Limited Entry Multi-season Buck Deer",
    "Limited Entry Buck Deer",
    "Limited Entry Archery Bull Elk",
    "Limited Entry Alw (rifle) Bull Elk",
    "Limited Entry Muzzleloader Bull Elk",
    "Limited Entry Multi-season Bull Elk",
    "Limited Entry Bull Elk",
    "Cwmu Buck Deer",
    "CWMU Buck Deer",
    "Cwmu Bull Elk",
    "CWMU Bull Elk",
    "Cwmu Buck Pronghorn",
    "CWMU Buck Pronghorn",
    "Dedicated Hunter",
    "General Season Buck Deer",
    "Youth General Season Buck Deer",
    "Youth Dedicated Hunter",
    "Antlerless Pronghorn",
    "Doe Pronghorn",
    "Youth Doe Pronghorn",
    "Youth Antlerless Pronghorn",
    "Antlerless Moose",
    "Cow Moose",
    "Antlerless Deer",
    "Youth Antlerless Deer",
    "Antlerless Elk",
    "Youth Antlerless Elk",
    "Cow Elk",
    "Bison",
    "Buck Pronghorn",
    "Buck Deer",
    "Bull Elk",
    "Bull Moose",
    "Mountain Goat",
    "Cougar",
    "Black Bear",
]

LEADING_PREFIXES = [
    *PROGRAM_PREFIXES,
    "Limited Entry",
    "Cwmu",
    "CWMU",
    "Youth",
    "General Season",
    "Draw-only",
    "Management",
    "Archery",
    "Muzzleloader",
    "Rifle",
    "Shotgun",
    "Any Legal Weapon",
    "Any Weapon",
    "Multi-season",
    "ALW",
]

WEAPON_SUFFIXES = {
    "Any Legal Weapon",
    "ALW",
    "Archery",
    "Muzzleloader",
    "Multi-season",
    "Mzl",
    "Muzzleloader Only",
    "Archery Only",
    "Hounds",
    "Rifle",
    "Shotgun",
    "Any Weapon",
}

OCR_FIXES = [
    (re.compile(r"\bAn y\b", re.I), "Any"),
    (re.compile(r"\bHenr y\b", re.I), "Henry"),
    (re.compile(r"\bO quirrh\b", re.I), "Oquirrh"),
    (re.compile(r"\bA rchery\b", re.I), "Archery"),
    (re.compile(r"\bLimited[- ]Entry\b", re.I), "Limited Entry"),
]

TRAILING_DESCRIPTOR_RE = re.compile(
    r"\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$",
    re.I,
)


def clean(value):
    return "" if value is None else str(value).strip()


def parse_csv(text):
    rows = []
    row = []
    field = ""
    in_quotes = False

    for i, char in enumerate(text):
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if char == '"':
            if in_quotes and next_char == '"':
                field += '"'
                continue
            in_quotes = not in_quotes
            continue

        if char == "," and not in_quotes:
            row.append(field)
            field = ""
            continue

        if (char == "\n" or char == "\r") and not in_quotes:
            if char == "\r" and next_char == "\n":
                continue
            row.append(field)
            rows.append(row)
            row = []
            field = ""
            continue

        field += char

    if field or row:
        row.append(field)
    if row:
        rows.append(row)

    header, *body = [entry for entry in rows if any(value != "" for value in entry)]
    return [dict(zip(header, values)) for values in body]


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", clean(text))


def normalize_punctuation(text):
    return re.sub(r"\s*,\s*", ", ", text).replace(" / ", "/")


def compact_text(text):
    return re.sub(r"[^a-z]", "", clean(text).lower())


def split_unit_segments(text):
    return [segment.strip() for segment in re.split(r"\s+-\s*|\s*-\s+", text) if segment.strip()]


def is_weaponish(text):
    compact = compact_text(text)
    return any(compact == compact_text(suffix) or compact.endswith(compact_text(suffix)) for suffix in WEAPON_SUFFIXES)


def is_species_lead(text):
    return bool(re.match(r"^Any\s+(?:Bull|Buck|Antlerless|Cow|Doe|Ram)\b", clean(text), flags=re.I))


def hunt_code_from_hunt_line(text):
    match = re.search(r"\bHunt:\s*([A-Z]{2}\d{4})\b", text)
    if match:
        return match.group(1)
    return ""


def title_from_page(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    for line in lines:
        if line.startswith("Hunt:"):
            return re.sub(r"^Hunt:\s*[A-Z]{1,3}\d{3,4}\s*", "", line).strip()

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


def clean_hunt_name(value, row=None):
    row = row or {}
    text = normalize_punctuation(normalize_whitespace(value))
    text = re.sub(r"^Hunt:\s*[A-Z]{1,3}\d{3,4}\s+", "", text, flags=re.I)

    for pattern, replacement in OCR_FIXES:
        text = pattern.sub(replacement, text)

    changed = True
    while changed:
        changed = False

        segments = split_unit_segments(text)
        if len(segments) >= 3 and is_weaponish(segments[-1]):
            text = " - ".join(segments[1:-1])
            changed = True
        elif len(segments) == 2 and (is_weaponish(segments[0]) or is_species_lead(segments[0])):
            text = segments[1]
            changed = True

        for prefix in LEADING_PREFIXES:
            pattern = rf"^{re.escape(prefix)}(?:\s*-\s*|\s+)?"
            new_text = re.sub(pattern, "", text, flags=re.I).strip()
            if new_text != text:
                text = new_text
                changed = True

        new_text = TRAILING_DESCRIPTOR_RE.sub("", text).strip()
        if new_text != text:
            text = new_text
            changed = True

        if clean((row or {}).get("hunt_type")).upper() == "CWMU" and re.search(r"\bCWMU\b$", text, flags=re.I):
            text = re.sub(r"\s*CWMU\s*$", "", text, flags=re.I).strip()
            changed = True

        suffix_match = re.match(r"^(.*?)(?:\s*-\s*)([^-]+?)\s*$", text)
        if suffix_match:
            head = suffix_match.group(1).strip()
            tail = suffix_match.group(2).strip()
            compact_tail = compact_text(tail)
            if any(
                compact_tail == compact_text(suffix) or compact_tail.endswith(compact_text(suffix))
                for suffix in WEAPON_SUFFIXES
            ):
                text = head
                changed = True

    return re.sub(r"\s+", " ", text).replace(", ", ", ").strip(" -")


def build_title_map():
    mapping = {}
    by_hunt_code = {}
    page_info_by_hunt_code = {}
    source_page_titles = defaultdict(dict)

    pdf_paths = sorted(SOURCE_ROOT.rglob("*.pdf"))
    for pdf_path in pdf_paths:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception:
            continue

        source_file = pdf_path.name
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            hunt_code = hunt_code_from_hunt_line(text)
            if not hunt_code:
                continue

            title = clean_hunt_name(title_from_page(text), {})
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

        if not hunt_name.isdigit():
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
        "source_root": str(SOURCE_ROOT),
    }
    (AUDIT_DIR / "2020_numeric_hunt_name_cleanup_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
