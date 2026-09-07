#!/usr/bin/env python3
"""Promote retained 2026 UtahDraws antlerless results to canonical truth.

The five official UtahDraws endpoint packages were retained in the raw source
archive but omitted from the 2026 canonical formatter.  This repair preserves
the Hunt Planner permit-reference rows and adds the exact point, residency,
and adult/youth result rows needed for scoring.

The command is preview-only by default.  Pass ``--write`` to replace the 2026
canonical atomically after all source and reconciliation checks pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
RAW_DIR = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2026"
    / "json"
    / "draw_results"
    / "utahdraws_2026_20260902"
    / "utahdraws_2026"
    / "csv"
)
RAW_FILES = (
    "2026_antlerless_17_antlerless_deer.csv",
    "2026_antlerless_18_antlerless_elk.csv",
    "2026_antlerless_19_antlerless_moose.csv",
    "2026_antlerless_20_doe_pronghorn.csv",
    "2026_antlerless_21_ewe_rocky_mtn_bighorn_sheep.csv",
)
SOURCE_DATASET = "UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260902"
PARSE_METHOD = "2026_UTAHDRAWS_ANTLERLESS_TO_CANONICAL"
AUDIT_DIR = ROOT / "audits" / "2026_antlerless_actual_promotion"
FORMATTED_DIR = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "formatted_2026_antlerless"
)
SUMMARY_PATH = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "validation"
    / "draw_2026_antlerless_actual_promotion_summary.json"
)

EXPECTED_SOURCE_ROWS = 2_144
EXPECTED_SOURCE_HUNT_CODES = 153
EXPECTED_PUBLIC_DRAW_REFERENCE_CODES = 162
EXPECTED_UNMATCHED_REFERENCE_CODES = {
    "EA1180",
    "EA1220",
    "EA1221",
    "EA1258",
    "EA1270",
    "EA1271",
    "EA2000",
    "EA2041",
    "EA2045",
}


FILE_RULES = {
    "2026_antlerless_17_antlerless_deer.csv": {
        "adult_scope": "ANTLERLESS_DEER",
        "youth_scope": "YOUTH_ANTLERLESS_DEER",
        "draw_design": "PREFERENCE_ANTLERLESS_DEER",
        "adult_pool": "general_season_antlerless_deer",
        "youth_pool": "youth_antlerless_deer",
    },
    "2026_antlerless_18_antlerless_elk.csv": {
        "adult_scope": "ANTLERLESS_ELK",
        "youth_scope": "YOUTH_ANTLERLESS_ELK",
        "draw_design": "PREFERENCE_ANTLERLESS_ELK",
        "adult_pool": "general_season_antlerless_elk",
        "youth_pool": "youth_antlerless_elk",
    },
    "2026_antlerless_19_antlerless_moose.csv": {
        "adult_scope": "ANTLERLESS_MOOSE",
        "youth_scope": "YOUTH_ANTLERLESS_MOOSE",
        "draw_design": "MAX_WEIGHTED_SPLIT",
        "adult_pool": "max_weighted_split",
        "youth_pool": "max_weighted_split",
    },
    "2026_antlerless_20_doe_pronghorn.csv": {
        "adult_scope": "ANTLERLESS_PRONGHORN",
        "youth_scope": "YOUTH_ANTLERLESS_PRONGHORN",
        "draw_design": "PREFERENCE_DOE_PRONGHORN",
        "adult_pool": "general_season_doe_pronghorn",
        "youth_pool": "youth_doe_pronghorn",
    },
    "2026_antlerless_21_ewe_rocky_mtn_bighorn_sheep.csv": {
        "adult_scope": "ANTLERLESS_ROCKY_MOUNTAIN_BIGHORN_SHEEP",
        "youth_scope": "YOUTH_ANTLERLESS_ROCKY_MOUNTAIN_BIGHORN_SHEEP",
        "draw_design": "MAX_WEIGHTED_SPLIT",
        "adult_pool": "max_weighted_split",
        "youth_pool": "max_weighted_split",
    },
}


def clean(value: object) -> str:
    return str(value or "").strip()


def integer(value: object) -> int:
    text = clean(value)
    if not text:
        return 0
    return int(float(text))


def point(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    number = float(text)
    return str(int(number)) if number.is_integer() else str(number)


def decimal(value: float, places: int) -> str:
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def is_true(value: object) -> bool:
    return clean(value).lower() == "true"


def reference_group(row: dict[str, str]) -> str:
    haystack = " ".join(
        clean(row.get(field)).lower()
        for field in ("hunt_name", "hunt_type", "draw_pool", "source_file")
    )
    if "private lands only" in haystack or "private_lands_only" in haystack:
        return "PRIVATE_LANDS_ONLY_REFERENCE"
    if "cwmu" in haystack:
        return "CWMU_REFERENCE"
    return "PUBLIC_DRAW_REFERENCE"


def source_row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("HuntCode")).upper(),
        clean(row.get("residency_label")).lower(),
        point(row.get("Point")),
        clean(row.get("IsYouth")).lower(),
    )


def canonical_source_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")).lower(),
        point(row.get("points")),
        clean(row.get("source_is_youth")).lower(),
    )


def wide_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("source_is_youth")).lower(),
        point(row.get("points")),
    )


def probability_fields(applicants: int, successful: int) -> tuple[str, str]:
    # Match the active canonical convention: a no-success rung is retained as
    # counts but has blank probability fields rather than a fabricated ratio.
    if applicants <= 0 or successful <= 0:
        return "", ""
    probability = successful / applicants
    return decimal(probability, 9), decimal(probability * 100, 6)


def load_official_source_rows() -> tuple[list[dict[str, str]], dict[str, str]]:
    selected: list[dict[str, str]] = []
    hashes: dict[str, str] = {}
    for filename in RAW_FILES:
        path = RAW_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Required retained UtahDraws source is missing: {path}")
        hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
        _, rows = read_csv(path)
        for csv_data_row, row in enumerate(rows, start=1):
            if clean(row.get("HuntCategoryName")) != "Antlerless":
                continue
            selected.append(
                {
                    **row,
                    "_source_csv_file": filename,
                    "_source_csv_data_row": str(csv_data_row),
                }
            )
    return selected, hashes


def validate_source_rows(rows: list[dict[str, str]]) -> None:
    codes = {clean(row.get("HuntCode")).upper() for row in rows}
    keys = [source_row_key(row) for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_SOURCE_ROWS} official antlerless rows; found {len(rows)}"
        )
    if len(codes) != EXPECTED_SOURCE_HUNT_CODES:
        raise RuntimeError(
            f"Expected {EXPECTED_SOURCE_HUNT_CODES} official antlerless hunt codes; found {len(codes)}"
        )
    if duplicates:
        raise RuntimeError(f"Duplicate official source keys found: {duplicates[:10]}")
    invalid_counts = [
        source_row_key(row)
        for row in rows
        if integer(row.get("SuccessfulCount")) > integer(row.get("ParticipantCount"))
    ]
    if invalid_counts:
        raise RuntimeError(f"Successful applicants exceed participants: {invalid_counts[:10]}")


def build_canonical_row(
    raw: dict[str, str],
    reference: dict[str, str],
    fields: list[str],
) -> dict[str, str]:
    filename = clean(raw.get("_source_csv_file"))
    rules = FILE_RULES[filename]
    youth = is_true(raw.get("IsYouth"))
    applicants = integer(raw.get("ParticipantCount"))
    successful = integer(raw.get("SuccessfulCount"))
    bonus = integer(raw.get("SuccessfulByMaxPointRoundCount"))
    regular = integer(raw.get("SuccessfulByRegularRoundCount"))
    p_draw, p_draw_percent = probability_fields(applicants, successful)
    source_json = clean(raw.get("source_json_file"))
    raw_path = (RAW_DIR / filename).relative_to(ROOT).as_posix()

    row = {field: reference.get(field, "") for field in fields}
    row.update(
        {
            "actual_draw_year": "2026",
            "model_target_year": "2027",
            "hunt_code": clean(raw.get("HuntCode")).upper(),
            "hunt_name": clean(raw.get("HuntName")) or reference.get("hunt_name", ""),
            "raw_hunt_name": clean(raw.get("HuntName")) or reference.get("raw_hunt_name", ""),
            "points": point(raw.get("Point")),
            "residency": clean(raw.get("residency_label")),
            "row_type": "point_level_draw_result",
            "record_type": "point_level_draw_result",
            "resident_eligible_applicants": "",
            "resident_bonus_permits": "",
            "resident_regular_permits": "",
            "resident_total_permits": "",
            "resident_success_ratio": "",
            "resident_p_draw": "",
            "resident_p_draw_percent": "",
            "nonresident_eligible_applicants": "",
            "nonresident_bonus_permits": "",
            "nonresident_regular_permits": "",
            "nonresident_total_permits": "",
            "nonresident_success_ratio": "",
            "nonresident_p_draw": "",
            "nonresident_p_draw_percent": "",
            "total_eligible_applicants": "",
            "total_bonus_permits": "",
            "total_regular_permits": "",
            "total_permits": str(successful),
            "total_success_ratio": "",
            "total_p_draw": "",
            "total_p_draw_percent": "",
            "eligible_applicants": str(applicants),
            "bonus_permits": str(bonus),
            "regular_permits": str(regular),
            "success_ratio": p_draw,
            "p_draw": p_draw,
            "p_draw_percent": p_draw_percent,
            "successful_applicants": str(successful),
            "unsuccessful_applicants": str(applicants - successful),
            "source_scope": rules["youth_scope"] if youth else rules["adult_scope"],
            "source_namespace": "2026_PERMITS=2027_MODEL_LIVE_PLUS_PDF_DENSE",
            "draw_source_namespace": "2026_LIVE_PLUS_PDF_DENSE_RECONCILED",
            "source_file": (
                "UtahDraws live DrawOddsData: "
                f"Antlerless:{clean(raw.get('SpeciesSubtypeName'))}"
            ),
            "draw_source_file": source_json,
            "source_path": raw_path,
            "source_pdf": "",
            "pdf_page": "",
            "official_page": "",
            "page_kind": "POINT_ROW",
            "source_dataset": SOURCE_DATASET,
            "extraction_status": "LIVE_UTAHDRAWS_REFRESH",
            "parse_method": PARSE_METHOD,
            "qa_status": "CONFIRMED_CANONICAL_SCORABLE",
            "qa_notes": "",
            "algorithm_status": (
                "Retained official UtahDraws 2026 antlerless endpoint row; "
                "official applicant and success fields used directly."
            ),
            "notes": Path(source_json).stem,
            "source_residencies": clean(raw.get("residency_label")),
            "source_row_count": "1",
            "collapse_conflict_count": "0",
            "candidate_promotion_status": "OFFICIAL_SOURCE_PROMOTED_2026_ANTLERLESS",
            "draw_design": rules["draw_design"],
            "hunt_draw_class": rules["draw_design"],
            "draw_system_type": rules["draw_design"],
            "draw_pool": rules["youth_pool"] if youth else rules["adult_pool"],
            "draw_system_type_source": (
                "official UtahDraws PointCalculationTypeID and IsBonusPoint"
            ),
            "draw_system_type_confidence": "high",
            "metric_scope": clean(raw.get("residency_label")).lower(),
            "source_row_identifier": (
                f"utahdraws:{source_json}:hunt-id={clean(raw.get('HuntID'))}:"
                f"is-youth={clean(raw.get('IsYouth')).lower()}:"
                f"csv-data-row={clean(raw.get('_source_csv_data_row'))}"
            ),
            "source_is_youth": clean(raw.get("IsYouth")).lower(),
        }
    )
    return row


WIDE_FIELDS = [
    "actual_draw_year",
    "row_type",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "weapon",
    "season",
    "source_scope",
    "draw_design",
    "draw_pool",
    "is_youth",
    "points",
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "resident_success_ratio",
    "resident_p_draw",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "nonresident_success_ratio",
    "nonresident_p_draw",
    "total_eligible_applicants",
    "total_successful_applicants",
    "total_success_ratio",
    "total_p_draw",
    "source_dataset",
    "source_file",
    "resident_source_row_identifier",
    "nonresident_source_row_identifier",
]


def dwr_ratio_text(applicants: int, successful: int) -> str:
    if applicants <= 0 or successful <= 0:
        return "N/A"
    return f"1 in {applicants / successful:.1f}"


def build_2025_style_wide_rows(promoted_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Join resident/nonresident point rows like the legacy DWR report layout."""
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in promoted_rows:
        grouped.setdefault(wide_key(row), []).append(row)

    point_rows: list[dict[str, str]] = []
    for key, rows in grouped.items():
        if len(rows) > 2:
            raise RuntimeError(f"More than two residency rows for wide key {key}: {len(rows)}")
        first = rows[0]
        by_residency = {clean(row.get("residency")).lower(): row for row in rows}
        resident = by_residency.get("resident")
        nonresident = by_residency.get("nonresident")
        if len(by_residency) != len(rows):
            raise RuntimeError(f"Duplicate residency in wide key {key}")

        resident_applicants = integer(resident.get("eligible_applicants")) if resident else 0
        nonresident_applicants = integer(nonresident.get("eligible_applicants")) if nonresident else 0
        resident_successful = integer(resident.get("successful_applicants")) if resident else 0
        nonresident_successful = integer(nonresident.get("successful_applicants")) if nonresident else 0
        total_applicants = resident_applicants + nonresident_applicants
        total_successful = resident_successful + nonresident_successful
        total_ratio, _ = probability_fields(total_applicants, total_successful)

        def value(row: dict[str, str] | None, field: str) -> str:
            return clean(row.get(field)) if row else ""

        point_rows.append(
            {
                "actual_draw_year": "2026",
                "row_type": "POINT",
                "hunt_code": first["hunt_code"],
                "hunt_name": first["hunt_name"],
                "species": first["species"],
                "sex_type": first["sex_type"],
                "hunt_type": first["hunt_type"],
                "weapon": first["weapon"],
                "season": first["season"],
                "source_scope": first["source_scope"],
                "draw_design": first["draw_design"],
                "draw_pool": first["draw_pool"],
                "is_youth": first["source_is_youth"],
                "points": first["points"],
                "resident_eligible_applicants": value(resident, "eligible_applicants"),
                "resident_bonus_permits": value(resident, "bonus_permits"),
                "resident_regular_permits": value(resident, "regular_permits"),
                "resident_total_permits": value(resident, "total_permits"),
                "resident_success_ratio": dwr_ratio_text(
                    resident_applicants, resident_successful
                ),
                "resident_p_draw": value(resident, "p_draw"),
                "nonresident_eligible_applicants": value(nonresident, "eligible_applicants"),
                "nonresident_bonus_permits": value(nonresident, "bonus_permits"),
                "nonresident_regular_permits": value(nonresident, "regular_permits"),
                "nonresident_total_permits": value(nonresident, "total_permits"),
                "nonresident_success_ratio": dwr_ratio_text(
                    nonresident_applicants, nonresident_successful
                ),
                "nonresident_p_draw": value(nonresident, "p_draw"),
                "total_eligible_applicants": str(total_applicants),
                "total_successful_applicants": str(total_successful),
                "total_success_ratio": dwr_ratio_text(total_applicants, total_successful),
                "total_p_draw": total_ratio,
                "source_dataset": SOURCE_DATASET,
                "source_file": first["draw_source_file"],
                "resident_source_row_identifier": value(resident, "source_row_identifier"),
                "nonresident_source_row_identifier": value(nonresident, "source_row_identifier"),
            }
        )

    point_rows.sort(
        key=lambda row: (
            row["source_file"],
            row["hunt_code"],
            row["is_youth"],
            -integer(row["points"]),
        )
    )
    totals_by_hunt: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in point_rows:
        totals_by_hunt.setdefault((row["hunt_code"], row["is_youth"]), []).append(row)

    output: list[dict[str, str]] = []
    for row in point_rows:
        output.append(row)
        group = totals_by_hunt[(row["hunt_code"], row["is_youth"])]
        if row is not group[-1]:
            continue
        resident_applicants = sum(integer(item["resident_eligible_applicants"]) for item in group)
        resident_successful = sum(integer(item["resident_total_permits"]) for item in group)
        nonresident_applicants = sum(integer(item["nonresident_eligible_applicants"]) for item in group)
        nonresident_successful = sum(integer(item["nonresident_total_permits"]) for item in group)
        total_applicants = resident_applicants + nonresident_applicants
        total_successful = resident_successful + nonresident_successful
        resident_p, _ = probability_fields(resident_applicants, resident_successful)
        nonresident_p, _ = probability_fields(nonresident_applicants, nonresident_successful)
        total_p, _ = probability_fields(total_applicants, total_successful)
        total = dict(row)
        total.update(
            {
                "row_type": "TOTALS",
                "points": "Totals",
                "resident_eligible_applicants": str(resident_applicants),
                "resident_bonus_permits": str(sum(integer(item["resident_bonus_permits"]) for item in group)),
                "resident_regular_permits": str(sum(integer(item["resident_regular_permits"]) for item in group)),
                "resident_total_permits": str(resident_successful),
                "resident_success_ratio": dwr_ratio_text(resident_applicants, resident_successful),
                "resident_p_draw": resident_p,
                "nonresident_eligible_applicants": str(nonresident_applicants),
                "nonresident_bonus_permits": str(sum(integer(item["nonresident_bonus_permits"]) for item in group)),
                "nonresident_regular_permits": str(sum(integer(item["nonresident_regular_permits"]) for item in group)),
                "nonresident_total_permits": str(nonresident_successful),
                "nonresident_success_ratio": dwr_ratio_text(nonresident_applicants, nonresident_successful),
                "nonresident_p_draw": nonresident_p,
                "total_eligible_applicants": str(total_applicants),
                "total_successful_applicants": str(total_successful),
                "total_success_ratio": dwr_ratio_text(total_applicants, total_successful),
                "total_p_draw": total_p,
                "resident_source_row_identifier": "",
                "nonresident_source_row_identifier": "",
            }
        )
        output.append(total)
    return output


def build_promotion() -> dict[str, object]:
    fields, canonical_rows = read_csv(CANONICAL)
    source_rows, source_hashes = load_official_source_rows()
    validate_source_rows(source_rows)

    references = [
        row
        for row in canonical_rows
        if clean(row.get("record_type")) == "hunt_planner_permit_reference"
    ]
    reference_counts = Counter(clean(row.get("hunt_code")).upper() for row in references)
    duplicate_references = sorted(code for code, count in reference_counts.items() if count != 1)
    if duplicate_references:
        raise RuntimeError(
            "Expected exactly one Hunt Planner reference per hunt code; "
            f"violations: {duplicate_references[:10]}"
        )
    reference_by_code = {
        clean(row.get("hunt_code")).upper(): row for row in references
    }
    source_codes = {clean(row.get("HuntCode")).upper() for row in source_rows}
    missing_references = sorted(source_codes - set(reference_by_code))
    if missing_references:
        raise RuntimeError(
            "Official source hunts are missing current Hunt Planner identity: "
            f"{missing_references}"
        )

    public_references = [
        row for row in references if reference_group(row) == "PUBLIC_DRAW_REFERENCE"
    ]
    public_codes = {clean(row.get("hunt_code")).upper() for row in public_references}
    if len(public_codes) != EXPECTED_PUBLIC_DRAW_REFERENCE_CODES:
        raise RuntimeError(
            f"Expected {EXPECTED_PUBLIC_DRAW_REFERENCE_CODES} public draw references; "
            f"found {len(public_codes)}"
        )
    unexpected_source_codes = sorted(source_codes - public_codes)
    if unexpected_source_codes:
        raise RuntimeError(
            "Official antlerless result rows unexpectedly map to CWMU/PLO references: "
            f"{unexpected_source_codes}"
        )
    unmatched = sorted(public_codes - source_codes)
    if set(unmatched) != EXPECTED_UNMATCHED_REFERENCE_CODES:
        raise RuntimeError(
            "The public-reference source gap changed. Expected "
            f"{sorted(EXPECTED_UNMATCHED_REFERENCE_CODES)}; found {unmatched}"
        )

    retained_rows = [
        row for row in canonical_rows if clean(row.get("parse_method")) != PARSE_METHOD
    ]
    promoted_rows = [
        build_canonical_row(raw, reference_by_code[clean(raw.get("HuntCode")).upper()], fields)
        for raw in source_rows
    ]
    promoted_keys = [canonical_source_key(row) for row in promoted_rows]
    if len(promoted_keys) != len(set(promoted_keys)):
        raise RuntimeError("Promotion produced duplicate canonical point/residency/youth keys")

    promoted_rows.sort(
        key=lambda row: (
            clean(row.get("hunt_code")),
            clean(row.get("source_is_youth")),
            clean(row.get("residency")),
            integer(row.get("points")),
        )
    )
    output_rows = retained_rows + promoted_rows
    unmatched_details = []
    for code in unmatched:
        row = reference_by_code[code]
        permits = integer(row.get("permits_2026_total"))
        unmatched_details.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "permits_2026_res": integer(row.get("permits_2026_res")),
                "permits_2026_nr": integer(row.get("permits_2026_nr")),
                "permits_2026_total": permits,
                "permit_source": clean(row.get("permit_allotment_2026_source")),
                "permit_source_file": clean(
                    row.get("permit_allotment_2026_source_file")
                ),
                "disposition": (
                    "UNEXPECTED_POSITIVE_PERMIT_REFERENCE_REQUIRES_SOURCE_REVIEW"
                    if permits > 0
                    else "ZERO_PERMIT_OR_SPECIAL_REFERENCE_NO_POINT_RESULT_EXPECTED"
                ),
            }
        )

    return {
        "fields": fields,
        "canonical_rows_before": canonical_rows,
        "output_rows": output_rows,
        "promoted_rows": promoted_rows,
        "source_hashes": source_hashes,
        "reference_group_counts": dict(
            sorted(Counter(reference_group(row) for row in references).items())
        ),
        "public_draw_reference_codes": len(public_codes),
        "source_backed_hunt_codes": len(source_codes),
        "unmatched_reference_details": unmatched_details,
    }


def summary_payload(result: dict[str, object], write: bool) -> dict[str, object]:
    promoted_rows = result["promoted_rows"]
    assert isinstance(promoted_rows, list)
    canonical_before = result["canonical_rows_before"]
    output_rows = result["output_rows"]
    assert isinstance(canonical_before, list)
    assert isinstance(output_rows, list)
    source_scopes = Counter(clean(row.get("source_scope")) for row in promoted_rows)
    source_files = Counter(clean(row.get("draw_source_file")) for row in promoted_rows)
    positive_applicant_rows = sum(
        integer(row.get("eligible_applicants")) > 0 for row in promoted_rows
    )
    zero_applicant_rows = len(promoted_rows) - positive_applicant_rows
    wide_rows = build_2025_style_wide_rows(promoted_rows)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write": write,
        "canonical_path": CANONICAL.relative_to(ROOT).as_posix(),
        "canonical_sha256_before": sha256(CANONICAL),
        "canonical_rows_before": len(canonical_before),
        "canonical_rows_after": len(output_rows),
        "promoted_point_rows": len(promoted_rows),
        "promoted_positive_applicant_rows": positive_applicant_rows,
        "promoted_zero_applicant_rows": zero_applicant_rows,
        "formatted_2025_style_point_rows": sum(row["row_type"] == "POINT" for row in wide_rows),
        "formatted_2025_style_total_rows": sum(row["row_type"] == "TOTALS" for row in wide_rows),
        "formatted_2025_style_wide_rows": len(wide_rows),
        "source_backed_hunt_codes": result["source_backed_hunt_codes"],
        "public_draw_reference_codes": result["public_draw_reference_codes"],
        "unmatched_reference_count": len(result["unmatched_reference_details"]),
        "unmatched_reference_details": result["unmatched_reference_details"],
        "reference_group_counts": result["reference_group_counts"],
        "promoted_source_scope_counts": dict(sorted(source_scopes.items())),
        "promoted_source_file_counts": dict(sorted(source_files.items())),
        "retained_source_sha256": result["source_hashes"],
        "probability_policy": (
            "successful_applicants / eligible_applicants when both are positive; "
            "blank probability for zero-success or zero-applicant source rows"
        ),
        "reference_row_policy": (
            "All 262 current Hunt Planner permit-reference rows are preserved as non-scorable "
            "quota/identity references."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically replace the 2026 canonical after validation",
    )
    args = parser.parse_args()

    result = build_promotion()
    fields = result["fields"]
    output_rows = result["output_rows"]
    assert isinstance(fields, list)
    assert isinstance(output_rows, list)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    candidate = AUDIT_DIR / "draw_results_2026_antlerless_promoted_candidate.csv"
    write_csv(candidate, fields, output_rows)
    summary = summary_payload(result, args.write)

    wide_rows = build_2025_style_wide_rows(result["promoted_rows"])
    write_csv(
        FORMATTED_DIR / "2026_antlerless_draw_results_2025_style_wide.csv",
        WIDE_FIELDS,
        wide_rows,
    )
    for filename in RAW_FILES:
        source_json = Path(filename).with_suffix(".json").name
        species_rows = [row for row in wide_rows if row["source_file"] == source_json]
        write_csv(
            FORMATTED_DIR / filename.replace(".csv", "_2025_style_wide.csv"),
            WIDE_FIELDS,
            species_rows,
        )
    summary["formatted_output_directory"] = FORMATTED_DIR.relative_to(ROOT).as_posix()
    summary["formatted_output_files"] = [
        "2026_antlerless_draw_results_2025_style_wide.csv",
        *[filename.replace(".csv", "_2025_style_wide.csv") for filename in RAW_FILES],
    ]

    if args.write:
        backup_dir = AUDIT_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_dir / f"{CANONICAL.stem}.before_antlerless_{timestamp}.csv"
        shutil.copy2(CANONICAL, backup)
        temporary = CANONICAL.with_suffix(CANONICAL.suffix + ".tmp")
        write_csv(temporary, fields, output_rows)
        os.replace(temporary, CANONICAL)
        summary["canonical_sha256_after"] = sha256(CANONICAL)
        summary["backup_path"] = backup.relative_to(ROOT).as_posix()

    summary["candidate_path"] = candidate.relative_to(ROOT).as_posix()
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (AUDIT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
