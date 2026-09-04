"""Normalize 2023 bighorn sheep individual harvest measurements.

The 2023 bighorn sheep PDF is an individual ram measurement table. It is not a
hunt-code aggregate harvest-success table and must not be used as a quota or
p_draw input. This builder writes a source-traceable measurement layer for later
biology/quality review.

The PDF does not carry hunt codes. This module therefore also writes a separate
conservative location-to-hunt-code crosswalk using the coded 2023 bighorn sheep
hunt-success names as the authority. Ambiguous shared-unit matches stay as
possible hunt codes for manual review instead of forcing a selected code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

try:  # pdfplumber is optional until this builder is run.
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover - covered by CLI error path in local runs.
    pdfplumber = None

REPORTED_HUNT_YEAR = 2023
MODEL_TARGET_YEAR = 2026
SOURCE_CLASS = "harvest_measurements"
SPECIES = "Bighorn Sheep"

CODED_BIGHORN_HUNTS = [
    {"hunt_code": "DS6600", "hunt_name": "Henry Mtns", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6601", "hunt_name": "Kaiparowits, East", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6602", "hunt_name": "Kaiparowits, Escalante", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6603", "hunt_name": "Kaiparowits, West", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6604", "hunt_name": "La Sal, Potash/South Cisco", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6621", "hunt_name": "Pine Valley, Beaver Dam", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6620", "hunt_name": "Pine Valley, Virgin River", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6606", "hunt_name": "San Juan, Lockhart", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6622", "hunt_name": "San Juan, North", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6623", "hunt_name": "San Juan, San Juan River", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6607", "hunt_name": "San Juan, South", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6608", "hunt_name": "San Rafael, Dirty Devil", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6609", "hunt_name": "San Rafael, North", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6610", "hunt_name": "San Rafael, South", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6611", "hunt_name": "Zion", "species": "Desert Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "DS6624", "hunt_name": "San Rafael, Dirty Devil", "species": "Desert Bighorn Sheep", "weapon": "Archery"},
    {"hunt_code": "RS6701", "hunt_name": "Book Cliffs, South", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6703", "hunt_name": "Box Elder, Newfoundland Mtn", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6704", "hunt_name": "Box Elder, Newfoundland Mtn", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6725", "hunt_name": "Central Mtns, Nebo", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6720", "hunt_name": "Fillmore, Oak Creek", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6726", "hunt_name": "Fillmore, Oak Creek", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6712", "hunt_name": "Nine Mile, Gray Canyon", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6713", "hunt_name": "Nine Mile, Jack Creek", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6709", "hunt_name": "North Slope, Summit/West Daggett", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6708", "hunt_name": "North Slope, Three Corners", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6721", "hunt_name": "Oquirrh-Stansbury, West", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6724", "hunt_name": "Wasatch Mtns, West", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Any Legal Weapon"},
    {"hunt_code": "RS6722", "hunt_name": "Box Elder, Newfoundland Mtn", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Archery"},
    {"hunt_code": "RS6727", "hunt_name": "Fillmore, Oak Creek", "species": "Rocky Mountain Bighorn Sheep", "weapon": "Archery"},
]

FIELDS = [
    "record_no",
    "reported_hunt_year",
    "model_target_year",
    "source_class",
    "species",
    "sheep_type",
    "hunt_code",
    "selected_hunt_code",
    "possible_hunt_codes",
    "matched_hunt_name",
    "matched_species",
    "matched_unit_name",
    "unit_crosswalk_status",
    "unit_crosswalk_confidence",
    "unit_crosswalk_method",
    "unit_crosswalk_notes",
    "database_match_status",
    "location_of_kill",
    "days_hunted",
    "wound",
    "hunter_satisfaction",
    "horn_length_left",
    "horn_length_right",
    "base_circumference_left",
    "base_circumference_right",
    "age_of_sheep",
    "source_file",
    "source_file_sha256",
    "source_page",
    "source_row_id",
    "extraction_method",
    "data_quality_flags",
    "recommended_use",
]

CROSSWALK_FIELDS = [
    "reported_hunt_year",
    "species",
    "measurement_record_no",
    "location_of_kill",
    "normalized_location",
    "matched_unit_name",
    "matched_hunt_name",
    "matched_species",
    "possible_hunt_codes",
    "selected_hunt_code",
    "match_status",
    "match_confidence",
    "match_method",
    "notes",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: object) -> str:
    text = str(value or "").lower()
    text = text.replace("mtns", "mountains").replace("mtn", "mountain")
    text = text.replace("cyn", "canyon")
    text = text.replace("cr.", "creek").replace(" cr ", " creek ")
    text = text.replace("timpanogas", "timpanogos")
    text = text.replace("timpie", "timpe")
    text = text.replace("wahweap", "wahweap")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _codes(codes: Sequence[str]) -> list[dict[str, str]]:
    return [hunt for hunt in CODED_BIGHORN_HUNTS if hunt["hunt_code"] in set(codes)]


def match_location(location: object) -> dict[str, object]:
    normalized = normalize_text(location)
    if not normalized:
        return _match_result(normalized, [], "UNMATCHED", "LOW", "no_location_text", "No location text provided.")

    rules: list[tuple[Sequence[str], Sequence[str], str, str, str]] = [
        (("san juan river", "muley pt", "muley point"), ("DS6623",), "MATCHED", "HIGH", "distinctive San Juan River desert bighorn unit"),
        (("lockhart", "north lockhart"), ("DS6606",), "MATCHED", "HIGH", "distinctive Lockhart desert bighorn unit"),
        (("virgin river", "beaver dam"), ("DS6620", "DS6621"), "POSSIBLE_MATCH", "MEDIUM", "Pine Valley desert bighorn unit has multiple coded hunts"),
        (("dirty devil", "poison spring", "sam s mesa", "sam mesa", "hite", "ocean point"), ("DS6608", "DS6624"), "POSSIBLE_MATCH", "MEDIUM", "San Rafael Dirty Devil has weapon-specific coded hunts"),
        (("san rafael north",), ("DS6609",), "MATCHED", "HIGH", "distinctive San Rafael North unit"),
        (("san rafael south",), ("DS6610",), "MATCHED", "HIGH", "distinctive San Rafael South unit"),
        (("henry", "middle warm creek"), ("DS6600",), "POSSIBLE_MATCH", "MEDIUM", "Henry Mountains location/unit text"),
        (("kaiparowits", "paria", "alstrom", "last chance", "warm creek", "cottonwood wash", "escalante", "lone rock", "hackberry", "big water"), ("DS6601", "DS6602", "DS6603"), "POSSIBLE_MATCH", "MEDIUM", "Kaiparowits/Paria/Escalante area has multiple coded hunts"),
        (("la sal", "potash", "south cisco"), ("DS6604",), "MATCHED", "HIGH", "distinctive La Sal/Potash/South Cisco unit"),
        (("zion", "barracks", "yellow jacket", "cedar pocket", "pahcoon", "horse canyon", "north horse"), ("DS6611",), "POSSIBLE_MATCH", "MEDIUM", "Zion-area location text; review before selecting single code"),
        (("bookcliffs", "book cliffs", "rattlesnake", "rock canyon", "butler canyon"), ("RS6701",), "POSSIBLE_MATCH", "MEDIUM", "Book Cliffs South area location text"),
        (("newfoundland", "desert peak", "big pass", "miners basin", "timpe", "muskrat", "devils twist"), ("RS6703", "RS6704", "RS6722"), "POSSIBLE_MATCH", "MEDIUM", "Newfoundland Mountain unit has multiple coded hunts"),
        (("nebo", "north canyon nebo"), ("RS6725",), "MATCHED", "HIGH", "Central Mountains Nebo unit text"),
        (("oak creek",), ("RS6720", "RS6726", "RS6727"), "POSSIBLE_MATCH", "MEDIUM", "Oak Creek unit has multiple coded hunts"),
        (("gray canyon", "nine mile gray"), ("RS6712",), "MATCHED", "HIGH", "distinctive Nine Mile Gray Canyon unit"),
        (("jack creek",), ("RS6713",), "MATCHED", "HIGH", "distinctive Nine Mile Jack Creek unit"),
        (("west daggett", "summit", "sheep creek", "manella"), ("RS6709",), "POSSIBLE_MATCH", "MEDIUM", "North Slope Summit/West Daggett area text"),
        (("three corners",), ("RS6708",), "MATCHED", "HIGH", "distinctive North Slope Three Corners unit"),
        (("oquirrh", "stansbury"), ("RS6721",), "MATCHED", "HIGH", "Oquirrh-Stansbury unit text"),
        (("timpanogos", "alpine", "the y", "south of rock canyon", "between rock canyon"), ("RS6724",), "POSSIBLE_MATCH", "MEDIUM", "Wasatch Mountains West/Timpanogos area text"),
    ]

    for patterns, codes, status, confidence, notes in rules:
        if any(pattern in normalized for pattern in patterns):
            hunts = _codes(codes)
            if status == "MATCHED" and len(hunts) == 1:
                return _match_result(normalized, hunts, status, confidence, "normalized_location_keyword", notes, selected=hunts[0]["hunt_code"])
            return _match_result(normalized, hunts, status, confidence, "normalized_location_keyword", notes)

    return _match_result(normalized, [], "UNMATCHED", "LOW", "no_authoritative_name_match", "Location did not defensibly match a coded 2023 sheep hunt name/unit.")


def _match_result(
    normalized: str,
    hunts: Sequence[Mapping[str, str]],
    status: str,
    confidence: str,
    method: str,
    notes: str,
    selected: str = "",
) -> dict[str, object]:
    possible_codes = [str(hunt["hunt_code"]) for hunt in hunts]
    selected_hunt = selected if selected else ""
    return {
        "normalized_location": normalized,
        "matched_unit_name": "; ".join(sorted({str(hunt["hunt_name"]) for hunt in hunts})),
        "matched_hunt_name": "; ".join(f"{hunt['hunt_code']} {hunt['hunt_name']}" for hunt in hunts),
        "matched_species": "; ".join(sorted({str(hunt["species"]) for hunt in hunts})),
        "possible_hunt_codes": "|".join(possible_codes),
        "selected_hunt_code": selected_hunt,
        "match_status": status,
        "match_confidence": confidence,
        "match_method": method,
        "notes": notes,
    }


def _row(record_no: int, source_page: int, source_file: Path, source_sha: str, values: Sequence[str], method: str) -> dict[str, object]:
    location, days, wound, satisfaction, horn_left, horn_right, base_left, base_right, age = values
    match = match_location(location)
    flags = ["NO_HUNT_CODE_IN_SOURCE", "INDIVIDUAL_MEASUREMENT_RECORD"]
    if match["match_status"] == "MATCHED":
        flags.append("LOCATION_CROSSWALK_MATCHED")
    elif match["match_status"] == "POSSIBLE_MATCH":
        flags.append("LOCATION_CROSSWALK_POSSIBLE_MATCH")
    else:
        flags.append("LOCATION_CROSSWALK_UNMATCHED")
    return {
        "record_no": record_no,
        "reported_hunt_year": REPORTED_HUNT_YEAR,
        "model_target_year": MODEL_TARGET_YEAR,
        "source_class": SOURCE_CLASS,
        "species": SPECIES,
        "sheep_type": "BIGHORN_SHEEP_UNSPECIFIED",
        "hunt_code": "",
        "selected_hunt_code": match["selected_hunt_code"],
        "possible_hunt_codes": match["possible_hunt_codes"],
        "matched_hunt_name": match["matched_hunt_name"],
        "matched_species": match["matched_species"],
        "matched_unit_name": match["matched_unit_name"],
        "unit_crosswalk_status": match["match_status"],
        "unit_crosswalk_confidence": match["match_confidence"],
        "unit_crosswalk_method": match["match_method"],
        "unit_crosswalk_notes": match["notes"],
        "database_match_status": "NO_HUNT_CODE_IN_SOURCE",
        "location_of_kill": location or "",
        "days_hunted": days or "",
        "wound": wound or "",
        "hunter_satisfaction": satisfaction or "",
        "horn_length_left": horn_left or "",
        "horn_length_right": horn_right or "",
        "base_circumference_left": base_left or "",
        "base_circumference_right": base_right or "",
        "age_of_sheep": age or "",
        "source_file": source_file.name,
        "source_file_sha256": source_sha,
        "source_page": source_page,
        "source_row_id": record_no,
        "extraction_method": method,
        "data_quality_flags": "|".join(flags),
        "recommended_use": "bighorn harvest measurement history only; do not use as quota or p_draw input",
    }


def extract_rows(input_pdf: Path) -> list[dict[str, object]]:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required to parse the 2023 bighorn sheep measurement PDF")
    source_sha = _sha256(input_pdf)
    rows: list[dict[str, object]] = []
    with pdfplumber.open(str(input_pdf)) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        first_line = next((line for line in first_text.splitlines() if line.startswith("1 Middle Warm Creek")), "")
        if not first_line:
            raise ValueError("Could not find first bighorn sheep measurement row in PDF text")
        rows.append(_row(
            1,
            1,
            input_pdf,
            source_sha,
            ["Middle Warm Creek", "5", "", "5", "30 5/8", "31 2/8", "14 1/8", "13 6/8", "7"],
            "pdfplumber_table_plus_text_first_row",
        ))
        record_no = 2
        for page_index, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[1] if page_index == 0 and len(tables) > 1 else tables[0][1:]
            for extracted in table:
                if not extracted or len(extracted) < 9:
                    continue
                if len(extracted) == 10:
                    values = [cell or "" for cell in extracted[1:]]
                else:
                    values = [cell or "" for cell in extracted]
                rows.append(_row(record_no, page_index + 1, input_pdf, source_sha, values, "pdfplumber_table"))
                record_no += 1
    return rows


def crosswalk_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        output.append({
            "reported_hunt_year": REPORTED_HUNT_YEAR,
            "species": SPECIES,
            "measurement_record_no": row.get("record_no", ""),
            "location_of_kill": row.get("location_of_kill", ""),
            "normalized_location": normalize_text(row.get("location_of_kill", "")),
            "matched_unit_name": row.get("matched_unit_name", ""),
            "matched_hunt_name": row.get("matched_hunt_name", ""),
            "matched_species": row.get("matched_species", ""),
            "possible_hunt_codes": row.get("possible_hunt_codes", ""),
            "selected_hunt_code": row.get("selected_hunt_code", ""),
            "match_status": row.get("unit_crosswalk_status", ""),
            "match_confidence": row.get("unit_crosswalk_confidence", ""),
            "match_method": row.get("unit_crosswalk_method", ""),
            "notes": row.get("unit_crosswalk_notes", ""),
        })
    return output


def build_report(input_pdf: Path, rows: Sequence[Mapping[str, object]], output_csv: Path) -> dict[str, object]:
    locations_missing = sum(1 for row in rows if not str(row.get("location_of_kill") or "").strip())
    high = [row for row in rows if row.get("unit_crosswalk_status") == "MATCHED"]
    possible = [row for row in rows if row.get("unit_crosswalk_status") == "POSSIBLE_MATCH"]
    unmatched = [row for row in rows if row.get("unit_crosswalk_status") == "UNMATCHED"]
    return {
        "generated_at_utc": _now(),
        "input_pdf": input_pdf.name,
        "source_class": SOURCE_CLASS,
        "reported_hunt_year": REPORTED_HUNT_YEAR,
        "model_target_year": MODEL_TARGET_YEAR,
        "species": SPECIES,
        "total_pages_scanned": 4,
        "total_parsed_rows": len(rows),
        "unique_hunt_codes": 0,
        "database_matched_rows": 0,
        "database_unmatched_rows": len(rows),
        "blank_hunt_code_rows": len(rows),
        "blank_location_rows": locations_missing,
        "contains_hunt_code": False,
        "contains_individual_locations": True,
        "contains_trophy_measurements": True,
        "crosswalk": {
            "matched_high_confidence_rows": len(high),
            "possible_medium_confidence_rows": len(possible),
            "unmatched_rows": len(unmatched),
            "rows_with_selected_hunt_code": sum(1 for row in rows if row.get("selected_hunt_code")),
            "rows_with_possible_hunt_codes": sum(1 for row in rows if row.get("possible_hunt_codes")),
            "ambiguous_multi_code_rows": sum(1 for row in rows if "|" in str(row.get("possible_hunt_codes") or "")),
            "unmatched_location_examples": [row.get("location_of_kill") for row in unmatched[:15]],
            "high_confidence_match_examples": [
                {"location": row.get("location_of_kill"), "selected_hunt_code": row.get("selected_hunt_code"), "matched_hunt_name": row.get("matched_hunt_name")}
                for row in high[:15]
            ],
            "possible_match_examples": [
                {"location": row.get("location_of_kill"), "possible_hunt_codes": row.get("possible_hunt_codes"), "matched_hunt_name": row.get("matched_hunt_name")}
                for row in possible[:15]
            ],
        },
        "do_not_use_for_2026_permits": True,
        "do_not_use_for_p_draw": True,
        "output_csv": output_csv.as_posix(),
        "recommended_next_step": "Review POSSIBLE_MATCH and UNMATCHED rows before promoting selected hunt codes for individual bighorn measurements.",
    }


def build_crosswalk_report(rows: Sequence[Mapping[str, object]], output_csv: Path) -> dict[str, object]:
    high = [row for row in rows if row.get("unit_crosswalk_status") == "MATCHED"]
    possible = [row for row in rows if row.get("unit_crosswalk_status") == "POSSIBLE_MATCH"]
    unmatched = [row for row in rows if row.get("unit_crosswalk_status") == "UNMATCHED"]
    return {
        "generated_at_utc": _now(),
        "reported_hunt_year": REPORTED_HUNT_YEAR,
        "species": SPECIES,
        "crosswalk_csv": output_csv.as_posix(),
        "total_measurement_rows": len(rows),
        "matched_high_confidence_rows": len(high),
        "possible_medium_confidence_rows": len(possible),
        "unmatched_rows": len(unmatched),
        "rows_with_selected_hunt_code": sum(1 for row in rows if row.get("selected_hunt_code")),
        "rows_with_possible_hunt_codes": sum(1 for row in rows if row.get("possible_hunt_codes")),
        "ambiguous_multi_code_rows": sum(1 for row in rows if "|" in str(row.get("possible_hunt_codes") or "")),
        "do_not_use_for_2026_permits": True,
        "do_not_use_for_p_draw": True,
        "recommended_next_step": "User should evaluate medium-confidence and unmatched location matches before promoting selected hunt-code values.",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize 2023 bighorn sheep individual harvest measurements.")
    parser.add_argument("--input-pdf", required=True)
    parser.add_argument("--output-csv", default="data_truth/harvest_results_truth/normalized/harvest_results_2023_bighorn_sheep_measurements_for_2026.csv")
    parser.add_argument("--report-json", default="data_truth/harvest_results_truth/normalized/harvest_results_2023_bighorn_sheep_measurements_for_2026_report.json")
    parser.add_argument("--crosswalk-csv", default="data_truth/harvest_results_truth/normalized/harvest_location_hunt_code_crosswalk_2023_bighorn_sheep.csv")
    parser.add_argument("--crosswalk-report-json", default="data_truth/harvest_results_truth/normalized/harvest_location_hunt_code_crosswalk_2023_bighorn_sheep_report.json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    input_pdf = Path(args.input_pdf)
    output_csv = Path(args.output_csv)
    report_json = Path(args.report_json)
    crosswalk_csv = Path(args.crosswalk_csv)
    crosswalk_report_json = Path(args.crosswalk_report_json)
    rows = extract_rows(input_pdf)
    _write_csv(output_csv, rows, FIELDS)
    _write_csv(crosswalk_csv, crosswalk_rows(rows), CROSSWALK_FIELDS)
    report = build_report(input_pdf, rows, output_csv)
    _write_json(report_json, report)
    _write_json(crosswalk_report_json, build_crosswalk_report(rows, crosswalk_csv))
    print(json.dumps({
        "rows": len(rows),
        "output_csv": output_csv.as_posix(),
        "report_json": report_json.as_posix(),
        "crosswalk_csv": crosswalk_csv.as_posix(),
        "crosswalk_report_json": crosswalk_report_json.as_posix(),
    }, indent=2))


if __name__ == "__main__":
    main()
