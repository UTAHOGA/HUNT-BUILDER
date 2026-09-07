from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2026"
    / "pdf"
    / "harvest_report"
    / "2025_age_tables_for_2026"
)
DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUT_DIR = ROOT / "data_model" / "harvest_quality"
OUT_SOURCE_ROWS = OUT_DIR / "harvest_results_2025_age_rows_from_2026_tables.csv"
OUT_EXPANDED = OUT_DIR / "harvest_results_2025_age_rows_hunt_code_expanded.csv"
OUT_DATABASE = OUT_DIR / "harvest_results_2025_for_2026_age_database.csv"
OUT_SUMMARY = OUT_DIR / "harvest_results_2025_for_2026_age_database_summary.json"

SOURCE_SPECS = {
    "Elk": {
        "file": "table-2026-04-01-bull-elk-tables.pdf",
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/table-2026-04-01-bull-elk-tables.pdf",
        "age_page": 2,
        "permit_pages": list(range(3, 10)),
        "code_prefix": "EB",
        "expected_age_rows": 26,
        "expected_table_title": "2026 LIMITED ENTRY ELK AVERAGE AGES AND OBJECTIVES",
    },
    "Pronghorn": {
        "file": "table-2026-04-01-pronghorn-tables.pdf",
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/table-2026-04-01-pronghorn-tables.pdf",
        "age_page": 1,
        "permit_pages": list(range(2, 6)),
        "code_prefix": "PB",
        "expected_age_rows": 29,
        "expected_table_title": "2026 BUCK PRONGHORN AVERAGE AGES AND OBJECTIVES",
    },
    "Moose": {
        "file": "table-2026-04-01-oilt-tables.pdf",
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/table-2026-04-01-oilt-tables.pdf",
        "age_page": 1,
        "permit_pages": [2],
        "code_prefix": "MB",
        "expected_age_rows": 12,
        "expected_table_title": "2026 MOOSE AVERAGE AGES AND OBJECTIVES",
    },
}

AGE_ROW_RE = re.compile(
    r"^(?P<unit>.+?)\s+"
    r"(?P<objective>\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\s+"
    r"(?P<y2023>\d+(?:\.\d+)?|\ufffd|\u2013|\u2014|-)\s+"
    r"(?P<y2024>\d+(?:\.\d+)?|\ufffd|\u2013|\u2014|-)\s+"
    r"(?P<y2025>\d+(?:\.\d+)?|\ufffd|\u2013|\u2014|-)\s+"
    r"(?P<avg>\d+(?:\.\d+)?|\ufffd|\u2013|\u2014|-)$"
)
CODE_RE = re.compile(r"\b(?P<code>(?:EB|PB|MB)\d{4})\b")
GROUP_HEADING_RE = re.compile(r"^(?P<unit>.+?)\s+2025 Permits\s+2026 Permits$")
NUMBER_TAIL_RE = re.compile(r"(?:\s+[\d\u2013\u2014-]+){6}\s*$")

WEAPON_PREFIXES = (
    "Archery",
    "Early Any Legal Weapon",
    "Mid Any Legal Weapon",
    "Late Any Legal Weapon",
    "Multiseason",
    "Muzzleloader",
    "Any Legal Weapon",
)
EXPLICIT_WEAPON_SUFFIXES = (
    " Late Archery",
    " HAMSS",
    " September Archery",
    " Any Legal Weapon",
)

# DWR uses a few different labels between the age page and the hunt-number pages.
# These aliases are explicit, same-document equivalences rather than fuzzy matches.
AGE_UNIT_ALIASES = {
    ("Elk", "Book Cliffs, Little Creek Roadless"): "Book Cliffs, Little Creek",
    ("Pronghorn", "Nine Mile, Anthro-Myton Bench"): "Nine Mile, Anthro",
    ("Pronghorn", "North Slope, Summit"): "North Slope, Summmit",
    ("Moose", "East Canyon, Morgan-Summit"): "East Canyon",
    ("Moose", "Wasatch Mtns/Central Mtns"): "Wasatch Mtns",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def number_or_blank(value: object) -> str:
    text = clean(value)
    if text in {"", "-", "\u2013", "\u2014", "\ufffd"}:
        return ""
    number = float(text)
    if number <= 0 or number >= 30:
        raise ValueError(f"Implausible age value: {text}")
    return f"{number:.1f}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_lines(reader: PdfReader, page_number: int) -> list[str]:
    text = reader.pages[page_number - 1].extract_text() or ""
    return [clean(line) for line in text.splitlines() if clean(line)]


def extract_age_rows(species: str, spec: dict[str, object], source_path: Path) -> list[dict[str, str]]:
    reader = PdfReader(str(source_path))
    age_page = int(spec["age_page"])
    table_title = str(spec["expected_table_title"])
    rows: list[dict[str, str]] = []
    for line in page_lines(reader, age_page):
        match = AGE_ROW_RE.fullmatch(line)
        if not match:
            continue
        values = [number_or_blank(match.group(field)) for field in ("y2023", "y2024", "y2025")]
        reported = number_or_blank(match.group("avg"))
        available = [float(value) for value in values if value]
        if not available:
            raise RuntimeError(f"No annual ages found for {species} unit {match.group('unit')}")
        computed = round(sum(available) / len(available) + 1e-9, 1)
        if not reported or abs(float(reported) - computed) > 0.05:
            raise RuntimeError(
                f"Reported 3-year age mismatch for {species} unit {match.group('unit')}: "
                f"annual={values}, reported={reported}, computed={computed:.1f}"
            )
        rows.append(
            {
                "reported_hunt_year": "2025",
                "model_target_year": "2026",
                "species": species,
                "source_unit_name": clean(match.group("unit")),
                "age_objective": clean(match.group("objective")),
                "average_harvest_age_2023": values[0],
                "average_harvest_age_2024": values[1],
                "average_harvest_age": values[2],
                "average_harvest_age_3yr": reported,
                "age_source_file": source_path.name,
                "age_source_url": str(spec["source_url"]),
                "age_source_sha256": sha256(source_path),
                "age_source_page": str(age_page),
                "age_source_table_title": table_title,
            }
        )
    expected = int(spec["expected_age_rows"])
    if len(rows) != expected:
        raise RuntimeError(f"Expected {expected} {species} age rows, parsed {len(rows)}")
    return rows


def strip_permit_numbers(line: str) -> str:
    return NUMBER_TAIL_RE.sub("", line).strip()


def extract_grouped_permits(
    species: str,
    reader: PdfReader,
    page_numbers: list[int],
    code_prefix: str,
) -> list[dict[str, str]]:
    mappings: list[dict[str, str]] = []
    current_unit = ""
    pending_name_fragments: list[str] = []
    for page_number in page_numbers:
        lines = page_lines(reader, page_number)
        for line_index, line in enumerate(lines):
            heading = GROUP_HEADING_RE.fullmatch(line)
            if heading and not line.startswith(("Weapon ", "Hunt Name ")):
                current_unit = clean(heading.group("unit"))
                # One pronghorn unit heading wraps immediately before "Daggett".
                # Join that visible source fragment before applying explicit aliases.
                if line_index > 0 and lines[line_index - 1].endswith("/West"):
                    current_unit = clean(f"{lines[line_index - 1]} {current_unit}")
                pending_name_fragments = []
                continue

            code_match = CODE_RE.search(line)
            if not code_match or not code_match.group("code").startswith(code_prefix):
                if page_number >= 8 and species == "Elk" and line not in {"Hunt", "Non"} and not any(
                    marker in line
                    for marker in (
                        "2026 LIMITED",
                        "2025 Permits",
                        "2026 Permits",
                        "Hunt Name",
                        "Number Res",
                        "Non Res",
                        "Res Total",
                        "Grand Total",
                        "Limited Entry",
                    )
                ):
                    pending_name_fragments.append(line)
                continue

            code = code_match.group("code")
            before_code = strip_permit_numbers(line[: code_match.start()])
            unit = ""
            weapon = ""
            if current_unit and before_code.startswith(WEAPON_PREFIXES):
                unit = current_unit
                weapon = before_code
            else:
                combined = clean(" ".join(pending_name_fragments + [before_code]))
                pending_name_fragments = []
                for suffix in EXPLICIT_WEAPON_SUFFIXES:
                    if combined.endswith(suffix):
                        unit = combined[: -len(suffix)].strip()
                        weapon = suffix.strip()
                        break
            if not unit:
                raise RuntimeError(f"Could not identify {species} permit unit on page {page_number}: {line}")
            mapped_unit = AGE_UNIT_ALIASES.get((species, unit), unit)
            mappings.append(
                {
                    "species": species,
                    "hunt_code": code,
                    "crosswalk_source_hunt_name": unit,
                    "crosswalk_source_weapon": weapon,
                    "crosswalk_source_page": str(page_number),
                    "source_unit_name": mapped_unit,
                }
            )
    return mappings


def extract_permit_mappings(species: str, spec: dict[str, object], source_path: Path) -> list[dict[str, str]]:
    reader = PdfReader(str(source_path))
    mappings = extract_grouped_permits(
        species,
        reader,
        [int(page) for page in spec["permit_pages"]],
        str(spec["code_prefix"]),
    )
    codes = [row["hunt_code"] for row in mappings]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise RuntimeError(f"Duplicate {species} hunt codes in permit tables: {duplicates}")
    return mappings


def validate_database_identity(mappings: list[dict[str, str]]) -> None:
    database = pd.read_csv(DATABASE_PATH, dtype=str, low_memory=False).fillna("")
    by_code = {clean(row["hunt_code"]).upper(): row for _, row in database.iterrows()}
    missing: list[str] = []
    mismatched: list[str] = []
    for mapping in mappings:
        code = mapping["hunt_code"]
        row = by_code.get(code)
        if row is None:
            missing.append(code)
            continue
        db_species = clean(row.get("species", "")).lower()
        expected = mapping["species"].lower()
        if expected not in db_species:
            mismatched.append(f"{code}:{row.get('species', '')}")
    if missing or mismatched:
        raise RuntimeError(
            "Official age-table hunt-code identity failed DATABASE.csv validation: "
            f"missing={missing}; species_mismatch={mismatched}"
        )


def expand_rows(
    age_rows: list[dict[str, str]],
    mappings: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    mappings_by_unit: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for mapping in mappings:
        mappings_by_unit[(mapping["species"], mapping["source_unit_name"])].append(mapping)

    expanded: list[dict[str, str]] = []
    database_rows: list[dict[str, str]] = []
    for age in age_rows:
        hits = sorted(
            mappings_by_unit.get((age["species"], age["source_unit_name"]), []),
            key=lambda row: row["hunt_code"],
        )
        if not hits:
            row = dict(age)
            row.update(
                {
                    "hunt_code": "",
                    "crosswalk_source_hunt_name": "",
                    "crosswalk_source_weapon": "",
                    "crosswalk_source_page": "",
                    "crosswalk_confidence": "",
                    "age_mapping_status": "no_current_hunt_code_in_2026_permit_table",
                    "notes": "Official unit age retained without inventing a hunt-code mapping.",
                }
            )
            expanded.append(row)
            continue

        for hit in hits:
            row = dict(age)
            row.update(hit)
            row.update(
                {
                    "crosswalk_confidence": "high",
                    "age_mapping_status": "official_2026_age_unit_to_same_file_hunt_number_table",
                    "age_data_available": "true",
                    "source_package": "official_2026_dwr_age_and_permit_tables",
                    "source_priority": "100",
                    "notes": "2025 annual age and DWR-reported 2023-2025 average; harvest quality context only.",
                }
            )
            expanded.append(row)
            database_rows.append(row)
    return expanded, database_rows


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Missing current hunt identity database: {DATABASE_PATH}")

    all_age_rows: list[dict[str, str]] = []
    all_mappings: list[dict[str, str]] = []
    source_hashes: dict[str, str] = {}
    source_urls: dict[str, str] = {}
    permit_mapping_counts: dict[str, int] = {}
    for species, spec in SOURCE_SPECS.items():
        source_path = SOURCE_DIR / str(spec["file"])
        if not source_path.exists():
            raise FileNotFoundError(f"Missing official DWR table: {source_path}")
        source_hashes[source_path.name] = sha256(source_path)
        source_urls[source_path.name] = str(spec["source_url"])
        age_rows = extract_age_rows(species, spec, source_path)
        mappings = extract_permit_mappings(species, spec, source_path)
        all_age_rows.extend(age_rows)
        all_mappings.extend(mappings)
        permit_mapping_counts[species] = len(mappings)

    validate_database_identity(all_mappings)
    expanded, database_rows = expand_rows(all_age_rows, all_mappings)
    database_rows.sort(key=lambda row: (row["species"], row["hunt_code"]))
    expanded.sort(key=lambda row: (row["species"], row["source_unit_name"], row.get("hunt_code", "")))

    codes = [row["hunt_code"] for row in database_rows]
    if len(codes) != len(set(codes)):
        raise RuntimeError("Duplicate hunt codes after official age-table expansion")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_age_rows).to_csv(OUT_SOURCE_ROWS, index=False, encoding="utf-8-sig")
    pd.DataFrame(expanded).to_csv(OUT_EXPANDED, index=False, encoding="utf-8-sig")
    pd.DataFrame(database_rows).to_csv(OUT_DATABASE, index=False, encoding="utf-8-sig")

    unmatched = [
        {"species": row["species"], "source_unit_name": row["source_unit_name"]}
        for row in expanded
        if not row.get("hunt_code")
    ]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reported_hunt_year": 2025,
        "model_target_year": 2026,
        "source_files_sha256": source_hashes,
        "source_urls": source_urls,
        "age_source_rows": len(all_age_rows),
        "age_source_rows_by_species": pd.DataFrame(all_age_rows)["species"].value_counts().to_dict(),
        "permit_hunt_code_mappings_by_species": permit_mapping_counts,
        "hunt_code_rows": len(database_rows),
        "hunt_code_rows_by_species": pd.DataFrame(database_rows)["species"].value_counts().to_dict(),
        "annual_2025_age_nonblank": sum(bool(row["average_harvest_age"]) for row in database_rows),
        "reported_2023_2025_average_nonblank": sum(bool(row["average_harvest_age_3yr"]) for row in database_rows),
        "unmatched_source_units": unmatched,
        "guardrails": {
            "permit_quota_authority": "NO",
            "draw_probability_authority": "NO",
            "boundary_id_used_for_matching": "NO",
            "crosswalk_basis": "same official DWR 2026 table file, age-unit page to hunt-number pages",
        },
        "outputs": {
            "source_age_rows": str(OUT_SOURCE_ROWS.relative_to(ROOT)).replace("\\", "/"),
            "expanded_age_rows": str(OUT_EXPANDED.relative_to(ROOT)).replace("\\", "/"),
            "hunt_code_age_database": str(OUT_DATABASE.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
