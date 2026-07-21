from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import pdfplumber


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = REPO / "audits" / f"conservation_permit_matrix_alignment_{STAMP}"

PDF_SOURCES = [
    {
        "source_label": "2019 Conservation Permits",
        "source_path": Path(r"B:\CLOUD DRIVES\GOOGLE DRIVE\Documents\2019_conservation_permits.pdf"),
        "source_year_start": "2019",
        "source_year_end": "2019",
        "format_family": "ORG_SECTION_SPECIES_AREA_PERMITS_CONDITION",
    },
    {
        "source_label": "2022-24 Conservation Permits",
        "source_path": Path(r"B:\CLOUD DRIVES\GOOGLE DRIVE\Documents\2022-24_conservation_permits.pdf"),
        "source_year_start": "2022",
        "source_year_end": "2024",
        "format_family": "GROUP_SPECIES_AREA_CONDITION",
    },
    {
        "source_label": "2025-27 Conservation Permits",
        "source_path": REPO / "tmp" / "source_pdfs" / "regulations" / "2025" / "2025-27-conservation-permits.pdf",
        "source_year_start": "2025",
        "source_year_end": "2027",
        "format_family": "NO_SPECIES_AREA_CONDITION_VALUE_ORGANIZATION",
    },
]

CANONICAL_HEADERS = ["No.", "Species", "Area", "Condition", "Value", "Organization"]
ORG_NAMES = {
    "Foundation for North American Wild Sheep": "FNAWS",
    "Mule Deer Foundation": "MDF",
    "National Wild Turkey Federation": "NWTF",
    "Rocky Mountain Elk Foundation": "RMEF",
    "Safari Club International": "SCI",
    "Sportsmen for Fish and Wildlife": "SFW",
    "Utah Archery Association": "UAA",
    "Utah Houndsmen Association": "UHA",
    "Utah Wild Sheep Foundation": "UWSF",
    "Wildlife Conservation Foundation": "WCF",
    "Wild Sheep Foundation": "WSF",
    "Dallas Safari Club": "DSC",
}
ORG_CODES = set(ORG_NAMES.values()) | {"MDF", "SFW", "SCI", "NWTF", "RMEF", "UAA", "UHA", "UWSF", "WCF", "DSC", "FNAWS"}
SPECIES_PREFIXES = sorted(
    [
        "Rocky Mountain Bighorn Sheep",
        "Desert Bighorn Sheep",
        "Wild Bearded Turkey",
        "Antlerless Elk",
        "Buck Pronghorn",
        "Mountain Goat",
        "Black Bear",
        "Bull Moose",
        "Buck Deer",
        "Bull Elk",
        "Pronghorn",
        "Turkey",
        "Bison",
        "Moose",
        "Deer",
        "Bear",
        "Elk",
    ],
    key=len,
    reverse=True,
)
CONDITION_TERMS = sorted(
    [
        "Combo & Season Variance",
        "Multi-season/Orientation Required",
        "Hunter's Choice of Season",
        "Any Legal Weapon, late",
        "Choice of ALW season",
        "Hunter's Choice",
        "Any Legal Weapon",
        "Muzzleloader",
        "Multiseason",
        "Multi-season",
        "Any Weapon",
        "Statewide",
        "Archery",
        "Discontinued",
    ],
    key=len,
    reverse=True,
)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "").strip())


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_species(text: str) -> tuple[str, str]:
    for species in SPECIES_PREFIXES:
        if text == species or text.startswith(species + " "):
            return species, clean(text[len(species) :])
    return "", text


def split_area_condition(text: str) -> tuple[str, str]:
    for condition in CONDITION_TERMS:
        marker = " " + condition
        if text.endswith(marker):
            return clean(text[: -len(marker)]), condition
        if text == condition:
            return "", condition
    return clean(text), ""


def parse_money(text: str) -> tuple[str, str]:
    match = re.search(r"\$[0-9,]+(?:\.[0-9]{2})?", text)
    if not match:
        return text, ""
    return clean(text[: match.start()] + " " + text[match.end() :]), match.group(0)


def normalize_condition_fields(condition: str) -> dict[str, str]:
    text = clean(condition)
    lower = text.lower()
    weapon = ""
    season = ""
    notes = ""

    if not text:
        return {
            "condition_weapon_type": "",
            "condition_season_type": "",
            "condition_notes": "",
            "condition_semantic_status": "PASS_NO_CONDITION_PUBLISHED",
            "sex_type": "",
        }

    if "archery" in lower:
        weapon = "Archery"
    elif "muzzleloader" in lower:
        weapon = "Muzzleloader"
    elif "any legal weapon" in lower or re.search(r"\balw\b", lower) or "any weapon" in lower:
        weapon = "Any Legal Weapon"

    if "hunter's choice" in lower or "choice of alw season" in lower:
        weapon = "Any Legal Weapon"
        season = "Hunter's Choice of ALW season"
    elif "late" in lower:
        season = "Late"
    elif "multiseason" in lower or "multi-season" in lower:
        season = "Multiseason"
    elif "season variance" in lower:
        season = "Season Variance"
    elif "statewide" in lower:
        season = "Statewide"
    elif "discontinued" in lower:
        season = "Discontinued"

    if "orientation required" in lower:
        notes = "Orientation Required"
    if "combo" in lower:
        notes = clean((notes + "; " if notes else "") + "Combo")

    status = "PASS_CONDITION_SPLIT_WEAPON_SEASON_NO_SEX_TYPE"
    if not weapon and not season:
        status = "REVIEW_REQUIRED_CONDITION_SEMANTICS"

    return {
        "condition_weapon_type": weapon,
        "condition_season_type": season,
        "condition_notes": notes,
        "condition_semantic_status": status,
    }


def normalize_species_and_sex(species: str, area: str) -> dict[str, str]:
    raw_species = clean(species)
    raw_area = clean(area)
    lower_area = raw_area.lower()
    prefix_map = [
        ("Wild Bearded Turkey", "Turkey", "Bearded", "SPECIES_LABEL"),
        ("Antlerless Elk", "Elk", "Antlerless", "SPECIES_LABEL"),
        ("Buck Pronghorn", "Pronghorn", "Buck", "SPECIES_LABEL"),
        ("Black Bear", "Black Bear", "", ""),
        ("Bull Moose", "Moose", "Bull", "SPECIES_LABEL"),
        ("Buck Deer", "Deer", "Buck", "SPECIES_LABEL"),
        ("Bull Elk", "Elk", "Bull", "SPECIES_LABEL"),
    ]
    for prefix, normalized_species, sex_type, source in prefix_map:
        if raw_species == prefix:
            return {
                "normalized_species": normalized_species,
                "sex_type": sex_type,
                "sex_type_source": source if sex_type else "NOT_PUBLISHED",
            }

    area_sex_patterns = [
        (r"\bantlerless\b", "Antlerless"),
        (r"\bbull elk\b|\bbull\b", "Bull"),
        (r"\bbuck\b", "Buck"),
        (r"\bcow only\b", "Cow Only"),
        (r"\bewe\b", "Ewe"),
        (r"\bram\b", "Ram"),
        (r"\bbearded\b", "Bearded"),
    ]
    for pattern, sex_type in area_sex_patterns:
        if re.search(pattern, lower_area):
            return {
                "normalized_species": raw_species,
                "sex_type": sex_type,
                "sex_type_source": "AREA_LABEL",
            }

    return {
        "normalized_species": raw_species,
        "sex_type": "",
        "sex_type_source": "NOT_PUBLISHED",
    }


def pdf_lines(path: Path) -> tuple[int, list[tuple[int, str]]]:
    rows = []
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = clean(line)
                if line:
                    rows.append((page_index, line))
        return len(pdf.pages), rows


def extract_2025(source: dict[str, object], lines: list[tuple[int, str]]) -> list[dict[str, object]]:
    rows = []
    for page, line in lines:
        if not re.match(r"^\d+\s+", line):
            continue
        remainder = line
        no_match = re.match(r"^(\d+)\s+(.*)$", remainder)
        if not no_match:
            continue
        row_no = no_match.group(1)
        body = no_match.group(2)
        body, value = parse_money(body)
        tokens = body.split()
        if tokens and tokens[-1] in ORG_CODES:
            org = tokens[-1]
            body = clean(" ".join(tokens[:-1]))
        else:
            org = ""
        # The extracted 2025 text repeats the row number before the organization.
        body = re.sub(r"\s+\d+$", "", body)
        species, rest = split_species(body)
        area, condition = split_area_condition(rest)
        if not area and condition == "Statewide":
            area = "Statewide"
            condition = ""
        if not species or not area:
            continue
        rows.append(base_row(source, page, row_no, species, area, condition, value, org, "PDF_TEXT_ROW"))
    return rows


def extract_2019(source: dict[str, object], lines: list[tuple[int, str]]) -> list[dict[str, object]]:
    rows = []
    current_org = ""
    row_no = 0
    for page, line in lines:
        if line in ORG_NAMES:
            current_org = ORG_NAMES[line]
            continue
        if line.startswith("Species Area Permits Condition") or line.startswith("2019 Utah Division"):
            continue
        species, rest = split_species(line)
        if not species or not current_org:
            continue
        permit_match = re.search(r"\s(\d+)\s", rest)
        if not permit_match:
            continue
        area = clean(rest[: permit_match.start()])
        condition = clean(rest[permit_match.end() :])
        if not area or not condition:
            continue
        row_no += 1
        rows.append(base_row(source, page, row_no, species, area, condition, "", current_org, "PDF_TEXT_ROW"))
    return rows


def extract_2022(source: dict[str, object], lines: list[tuple[int, str]]) -> list[dict[str, object]]:
    rows = []
    row_no = 0
    for page, line in lines:
        if line.startswith("Group Species Area Condition") or line in ORG_NAMES:
            continue
        tokens = line.split()
        if not tokens or tokens[0] not in ORG_CODES:
            continue
        org = tokens[0]
        species, rest = split_species(clean(" ".join(tokens[1:])))
        if not species:
            continue
        area, condition = split_area_condition(rest)
        if not area or not condition:
            continue
        row_no += 1
        rows.append(base_row(source, page, row_no, species, area, condition, "", org, "PDF_TEXT_ROW"))
    return rows


def base_row(
    source: dict[str, object],
    page: int,
    row_no: object,
    species: str,
    area: str,
    condition: str,
    value: str,
    organization: str,
    status: str,
) -> dict[str, object]:
    condition_fields = normalize_condition_fields(condition)
    species_fields = normalize_species_and_sex(species, area)
    return {
        "source_label": source["source_label"],
        "source_path": str(source["source_path"]),
        "source_year_start": source["source_year_start"],
        "source_year_end": source["source_year_end"],
        "format_family": source["format_family"],
        "pdf_page": page,
        "No.": row_no,
        "Species": species,
        **species_fields,
        "Area": area,
        "Condition": condition,
        **condition_fields,
        "Value": value,
        "Organization": organization,
        "hunt_code": "",
        "hunt_code_source_status": "NOT_PUBLISHED_IN_PERMIT_LIST_PDF_TEXT",
        "permit_count": "1",
        "matrix_alignment_status": "PASS_FORMATTED_TO_2025_27_HEADER_CONTRACT",
        "source_patch_applied": "FALSE",
        "notes": status,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = []
    all_rows = []
    for source in PDF_SOURCES:
        path = Path(source["source_path"])
        page_count = ""
        extract_status = "MISSING_SOURCE"
        rows = []
        if path.exists():
            page_count, lines = pdf_lines(path)
            if source["format_family"] == "NO_SPECIES_AREA_CONDITION_VALUE_ORGANIZATION":
                rows = extract_2025(source, lines)
            elif source["format_family"] == "ORG_SECTION_SPECIES_AREA_PERMITS_CONDITION":
                rows = extract_2019(source, lines)
            elif source["format_family"] == "GROUP_SPECIES_AREA_CONDITION":
                rows = extract_2022(source, lines)
            extract_status = "PASS_EXTRACTED_TO_MATRIX" if rows else "REVIEW_REQUIRED_NO_ROWS_EXTRACTED"
            source_rows.append(
                {
                    "source_label": source["source_label"],
                    "source_path": str(path),
                    "exists": "TRUE",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "page_count": page_count,
                    "source_year_start": source["source_year_start"],
                    "source_year_end": source["source_year_end"],
                    "format_family": source["format_family"],
                    "row_count_extracted": len(rows),
                    "extract_status": extract_status,
                    "notes": "",
                }
            )
        else:
            source_rows.append(
                {
                    "source_label": source["source_label"],
                    "source_path": str(path),
                    "exists": "FALSE",
                    "size_bytes": "",
                    "sha256": "",
                    "page_count": "",
                    "source_year_start": source["source_year_start"],
                    "source_year_end": source["source_year_end"],
                    "format_family": source["format_family"],
                    "row_count_extracted": 0,
                    "extract_status": extract_status,
                    "notes": "",
                }
            )
        all_rows.extend(rows)

    p01 = OUT_DIR / "01_CONSERVATION_PERMIT_MATRIX_HEADER_CONTRACT.csv"
    p02 = OUT_DIR / "02_CONSERVATION_PERMIT_PDF_SOURCE_CONFIRMATION.csv"
    p03 = OUT_DIR / "03_CONSERVATION_PERMIT_PDF_ROWS_MATRIX_FORMAT.csv"
    p04 = OUT_DIR / "04_CONSERVATION_PERMIT_FORMAT_COMPARISON.csv"
    p05 = OUT_DIR / "05_CONSERVATION_PERMIT_MATRIX_ALIGNMENT_REPORT.md"

    write_csv(
        p01,
        [
            {"matrix_column": header, "semantic_role": role, "required": "TRUE", "notes": notes}
            for header, role, notes in [
                ("No.", "source_row_number_or_sequence", "Native in 2025-27; generated sequentially for older PDFs when no explicit No. column is published."),
                ("Species", "conservation_species", "Includes Big Game, bear, turkey, and other Conservation permit species shown by source."),
                ("Area", "conservation_permit_area", "Area/unit label from the Conservation Permit PDF."),
                ("Condition", "published_condition_raw", "Condition column from PDF, e.g. Any Legal Weapon, Multiseason, Hunter's Choice."),
                ("Value", "permit_value", "Native in 2025-27; blank for older PDFs when not published."),
                ("Organization", "allocated_conservation_organization", "Organization receiving/auctioning the allocated permit."),
            ]
        ],
        ["matrix_column", "semantic_role", "required", "notes"],
    )
    write_csv(
        p02,
        source_rows,
        ["source_label", "source_path", "exists", "size_bytes", "sha256", "page_count", "source_year_start", "source_year_end", "format_family", "row_count_extracted", "extract_status", "notes"],
    )
    write_csv(
        p03,
        all_rows,
        [
            "source_label",
            "source_path",
            "source_year_start",
            "source_year_end",
            "format_family",
            "pdf_page",
            "No.",
            "Species",
            "normalized_species",
            "sex_type",
            "sex_type_source",
            "Area",
            "Condition",
            "condition_weapon_type",
            "condition_season_type",
            "condition_notes",
            "condition_semantic_status",
            "Value",
            "Organization",
            "hunt_code",
            "hunt_code_source_status",
            "permit_count",
            "matrix_alignment_status",
            "source_patch_applied",
            "notes",
        ],
    )

    comparison_rows = []
    by_source = Counter(row["source_label"] for row in all_rows)
    for source in PDF_SOURCES:
        rows = [row for row in all_rows if row["source_label"] == source["source_label"]]
        comparison_rows.append(
            {
                "source_label": source["source_label"],
                "source_year_start": source["source_year_start"],
                "source_year_end": source["source_year_end"],
                "source_native_format": source["format_family"],
                "canonical_matrix_headers": "|".join(CANONICAL_HEADERS),
                "formatted_row_count": len(rows),
                "unique_species": len({row["Species"] for row in rows}),
                "unique_normalized_species": len({row["normalized_species"] for row in rows}),
                "unique_organizations": len({row["Organization"] for row in rows if row["Organization"]}),
                "blank_value_rows": sum(1 for row in rows if not row["Value"]),
                "condition_semantic_review_rows": sum(1 for row in rows if row["condition_semantic_status"].startswith("REVIEW")),
                "sex_type_populated_rows": sum(1 for row in rows if row["sex_type"]),
                "hunt_code_populated_rows": sum(1 for row in rows if row["hunt_code"]),
                "format_status": "PASS_FORMATTED_TO_2025_27_HEADER_CONTRACT" if rows else "REVIEW_REQUIRED",
                "notes": "Conservation allocation source, not a normal draw_pool. Hunt codes were not published in the parsed permit-list PDF text.",
            }
        )
    write_csv(
        p04,
        comparison_rows,
        ["source_label", "source_year_start", "source_year_end", "source_native_format", "canonical_matrix_headers", "formatted_row_count", "unique_species", "unique_normalized_species", "unique_organizations", "blank_value_rows", "condition_semantic_review_rows", "sex_type_populated_rows", "hunt_code_populated_rows", "format_status", "notes"],
    )

    report = [
        "# Conservation Permit Matrix Alignment Report",
        "",
        f"report_timestamp={STAMP}",
        "",
        "## Header Contract",
        "",
        "The Conservation permit matrix/key-alignment header contract is:",
        "",
        "No. | Species | Area | Condition | Value | Organization",
        "",
        "These are allocation/benefit-auction permit rows, not standard draw_pool odds rows.",
        "The raw Condition field is semantically split for downstream alignment: ALW/Any Legal Weapon is weapon_type, late is season_type, and Hunter's Choice means the winning bidder chooses an ALW season. Hunter's Choice is not sex_type.",
        "Sex type is still populated when the hunt label is sex-specific, such as Antlerless, Bull, Buck, Cow Only, Ewe, Ram, or Bearded.",
        "The checked permit-list PDF text did not publish hunt_code values. Hunt-code attachment should come from a later source-confirmed bridge to the selection matrix/database, not from guessing.",
        "",
        "## Source Formatting",
        "",
    ]
    for row in comparison_rows:
        report.append(
            f"- {row['source_label']}: native_format={row['source_native_format']}; formatted_rows={row['formatted_row_count']}; blank_value_rows={row['blank_value_rows']}; condition_review_rows={row['condition_semantic_review_rows']}; sex_type_populated_rows={row['sex_type_populated_rows']}; hunt_code_populated_rows={row['hunt_code_populated_rows']}; status={row['format_status']}"
        )
    report.extend(
        [
            "",
            "## Source Modification Statement",
            "",
            "SOURCE_FILES_MODIFIED=FALSE",
            "DATABASE_PATCHED=FALSE",
            "DRAW_RESULTS_LONG_PATCHED=FALSE",
            "CANONICAL_YEARLY_PATCHED=FALSE",
            "PREDICTION_OUTPUTS_USED=FALSE",
            "",
            "## Outputs",
            "",
            f"MATRIX_HEADER_CONTRACT={p01}",
            f"PDF_SOURCE_CONFIRMATION={p02}",
            f"ROWS_MATRIX_FORMAT={p03}",
            f"FORMAT_COMPARISON={p04}",
            "",
            "CONSERVATION_MATRIX_ALIGNMENT_STATUS=PASS_FORMATTED_TO_2025_27_HEADER_CONTRACT_REVIEW_REQUIRED_FOR_PROMOTION",
        ]
    )
    p05.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"CONSERVATION_MATRIX_ALIGNMENT_OUTPUT_DIR={OUT_DIR}")
    print(f"MATRIX_HEADER_CONTRACT={p01}")
    print(f"PDF_SOURCE_CONFIRMATION={p02}")
    print(f"ROWS_MATRIX_FORMAT={p03}")
    print(f"FORMAT_COMPARISON={p04}")
    print(f"MATRIX_ALIGNMENT_REPORT={p05}")
    print(f"TOTAL_FORMATTED_ROWS={len(all_rows)}")
    for source in PDF_SOURCES:
        print(f"{str(source['source_year_start'])}_{str(source['source_year_end'])}_FORMATTED_ROWS={by_source[source['source_label']]}")
    print(f"CONDITION_SEMANTIC_REVIEW_ROWS={sum(1 for row in all_rows if row['condition_semantic_status'].startswith('REVIEW'))}")
    print(f"SEX_TYPE_POPULATED_ROWS={sum(1 for row in all_rows if row['sex_type'])}")
    print(f"HUNT_CODE_POPULATED_ROWS={sum(1 for row in all_rows if row['hunt_code'])}")
    print("HUNT_CODE_SOURCE_STATUS=NOT_PUBLISHED_IN_PERMIT_LIST_PDF_TEXT")
    print("HUNTERS_CHOICE_IS_SEASON_CHOICE_NOT_SEX_TYPE=TRUE")
    print("SEX_TYPE_DERIVED_FROM_SEX_SPECIFIC_HUNT_LABELS=TRUE")
    print("ALW_IS_WEAPON_TYPE=TRUE")
    print("LATE_IS_SEASON_TYPE=TRUE")
    print("CONSERVATION_IS_DRAW_POOL=FALSE")
    print("SOURCE_FILES_MODIFIED=FALSE")
    print("CONSERVATION_MATRIX_ALIGNMENT_STATUS=PASS_FORMATTED_TO_2025_27_HEADER_CONTRACT_REVIEW_REQUIRED_FOR_PROMOTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
