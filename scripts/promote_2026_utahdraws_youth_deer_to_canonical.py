#!/usr/bin/env python3
"""Promote retained 2026 general and Dedicated Hunter deer results.

The September UtahDraws archive contains separate adult and youth result
ladders inside the general-season buck deer and Dedicated Hunter packages.
The existing 2026 canonical retained PDF-derived rows but did not retain the
complete online source shape.  This repair adds those exact online rows while
leaving the PDF evidence and Hunt Planner reference rows intact.

The command is preview-only by default.  Pass ``--write`` to replace the 2026
canonical atomically after every source, identity, count, and year gate passes.
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
AUDIT_DIR = ROOT / "audits" / "2026_youth_deer_actual_promotion"
SUMMARY_PATH = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "validation"
    / "draw_2026_youth_deer_actual_promotion_summary.json"
)
SOURCE_DATASET = "UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260902"
PARSE_METHOD = "2026_UTAHDRAWS_GENERAL_AND_DEDICATED_DEER_TO_CANONICAL"
PRIOR_PARTIAL_PARSE_METHOD = "2026_UTAHDRAWS_YOUTH_DEER_TO_CANONICAL"
SUPERSEDED_PDF_REPAIR_METHOD = "2026_PDF_SUCCESS_FIELD_REPAIRED_FROM_RETAINED_UTAHDRAWS"


FILE_RULES = {
    "2026_big_game_05_general_season_buck_deer.csv": {
        "category": "General-Season",
        "expected_rows": 1722,
        "expected_hunts": 106,
        "adult_scope": "GENERAL_SEASON_DEER",
        "youth_scope": "YOUTH_GENERAL_SEASON_DEER",
        "draw_design": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "adult_pool": "adult_general_deer",
        "youth_pool": "youth_general_deer",
        "source_file_label": "UtahDraws live DrawOddsData: Big Game:General-Season Buck Deer",
    },
    "2026_big_game_32_dedicated_hunter_buck_deer.csv": {
        "category": "Dedicated Hunter",
        "expected_rows": 279,
        "expected_hunts": 31,
        "adult_scope": "DEDICATED_HUNTER",
        "youth_scope": "YOUTH_DEDICATED_HUNTER_DEER",
        "draw_design": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "adult_pool": "dedicated_hunter",
        "youth_pool": "youth_dedicated_hunter",
        "source_file_label": "UtahDraws live DrawOddsData: Big Game:Dedicated Hunter Buck Deer",
    },
}
EXPECTED_ROWS = 2001
EXPECTED_HUNTS = 137


def clean(value: object) -> str:
    return str(value or "").strip()


def integer(value: object) -> int:
    text = clean(value)
    return int(float(text)) if text else 0


def point(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    number = float(text)
    return str(int(number)) if number.is_integer() else str(number)


def decimal(value: float, places: int) -> str:
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def probability_fields(applicants: int, successful: int) -> tuple[str, str]:
    if applicants <= 0 or successful <= 0:
        return "", ""
    probability = successful / applicants
    return decimal(probability, 9), decimal(probability * 100, 6)


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


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def source_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("HuntCode")).upper(),
        clean(row.get("residency_label")).lower(),
        point(row.get("Point")),
        clean(row.get("IsYouth")).lower(),
        clean(row.get("source_json_file")),
    )


def canonical_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("residency")).lower(),
        point(row.get("points")),
        clean(row.get("source_is_youth")).lower(),
        clean(row.get("source_scope")),
    )


def load_source_rows() -> tuple[list[dict[str, str]], dict[str, str]]:
    selected: list[dict[str, str]] = []
    hashes: dict[str, str] = {}
    for filename, rules in FILE_RULES.items():
        path = RAW_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Required retained UtahDraws source is missing: {path}")
        hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
        _, rows = read_csv(path)
        family_rows: list[dict[str, str]] = []
        for csv_data_row, row in enumerate(rows, start=1):
            if clean(row.get("HuntCategoryName")) != rules["category"]:
                continue
            family_rows.append(
                {
                    **row,
                    "_source_csv_file": filename,
                    "_source_csv_data_row": str(csv_data_row),
                }
            )
        if len(family_rows) != rules["expected_rows"]:
            raise RuntimeError(
                f"{filename}: expected {rules['expected_rows']} draw rows; "
                f"found {len(family_rows)}"
            )
        if len({clean(row.get('HuntCode')).upper() for row in family_rows}) != rules["expected_hunts"]:
            raise RuntimeError(
                f"{filename}: expected {rules['expected_hunts']} hunt codes"
            )
        selected.extend(family_rows)
    return selected, hashes


def validate_source_rows(rows: list[dict[str, str]]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} deer rows; found {len(rows)}")
    if len({clean(row.get('HuntCode')).upper() for row in rows}) != EXPECTED_HUNTS:
        raise RuntimeError(f"Expected {EXPECTED_HUNTS} deer hunt codes")
    keys = [source_key(row) for row in rows]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise RuntimeError(f"Duplicate official source keys: {duplicates[:10]}")
    invalid_counts = [
        source_key(row)
        for row in rows
        if integer(row.get("SuccessfulCount")) > integer(row.get("ParticipantCount"))
    ]
    if invalid_counts:
        raise RuntimeError(f"Successful applicants exceed participants: {invalid_counts[:10]}")
    bad_year_rows = [
        source_key(row)
        for row in rows
        if clean(row.get("IsHistoricalData")).lower() != "false"
        or "2025" in clean(row.get("SeasonWeapons"))
        or (clean(row.get("SeasonWeapons")) and "2026" not in clean(row.get("SeasonWeapons")))
    ]
    if bad_year_rows:
        raise RuntimeError(f"2026-only source gate failed: {bad_year_rows[:10]}")


def reference_for_source(
    raw: dict[str, str], canonical_rows: list[dict[str, str]]
) -> dict[str, str]:
    filename = clean(raw.get("_source_csv_file"))
    code = clean(raw.get("HuntCode")).upper()
    if filename.startswith("2026_big_game_05_"):
        allowed_scopes = {"GENERAL_SEASON_DEER", "GENERAL_SEASON_DEER_EXTENDED_ARCHERY_REFERENCE"}
    else:
        allowed_scopes = {"DEDICATED_HUNTER"}
    candidates = [
        row
        for row in canonical_rows
        if clean(row.get("hunt_code")).upper() == code
        and clean(row.get("record_type")) == "point_level_draw_result"
        and clean(row.get("source_scope")) in allowed_scopes
    ]
    if not candidates:
        raise RuntimeError(f"No canonical hunt identity reference for {filename}:{code}")
    return candidates[0]


def build_row(
    raw: dict[str, str], reference: dict[str, str], fields: list[str]
) -> dict[str, str]:
    filename = clean(raw.get("_source_csv_file"))
    rules = FILE_RULES[filename]
    youth = clean(raw.get("IsYouth")).lower() == "true"
    applicants = integer(raw.get("ParticipantCount"))
    successful = integer(raw.get("SuccessfulCount"))
    bonus = integer(raw.get("SuccessfulByMaxPointRoundCount"))
    regular = integer(raw.get("SuccessfulByRegularRoundCount"))
    p_draw, p_draw_percent = probability_fields(applicants, successful)
    source_json = clean(raw.get("source_json_file"))
    source_path = (RAW_DIR / filename).relative_to(ROOT).as_posix()

    row = {field: reference.get(field, "") for field in fields}
    row.update(
        {
            "actual_draw_year": "2026",
            "model_target_year": "2027",
            "hunt_code": clean(raw.get("HuntCode")).upper(),
            "hunt_name": clean(raw.get("HuntName")) or reference.get("hunt_name", ""),
            "raw_hunt_name": clean(raw.get("HuntName")) or reference.get("raw_hunt_name", ""),
            "species": "Deer",
            "sex_type": "Buck",
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
            "source_file": rules["source_file_label"],
            "draw_source_file": source_json,
            "source_path": source_path,
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
                "Retained official UtahDraws 2026 deer endpoint row; "
                "official applicant and success fields used directly."
            ),
            "notes": Path(source_json).stem,
            "source_residencies": clean(raw.get("residency_label")),
            "source_row_count": "1",
            "collapse_conflict_count": "0",
            "candidate_promotion_status": "OFFICIAL_SOURCE_PROMOTED_2026_GS_DH_DEER",
            "draw_design": rules["draw_design"],
            "hunt_draw_class": rules["draw_design"],
            "draw_system_type": rules["draw_design"],
            "draw_pool": rules["youth_pool"] if youth else rules["adult_pool"],
            "draw_system_type_source": "official UtahDraws PointCalculationTypeID and IsBonusPoint",
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


def build_promotion() -> dict[str, object]:
    fields, canonical_rows = read_csv(CANONICAL)
    source_rows, source_hashes = load_source_rows()
    validate_source_rows(source_rows)

    retained_rows = [
        row
        for row in canonical_rows
        if clean(row.get("parse_method"))
        not in {PARSE_METHOD, PRIOR_PARTIAL_PARSE_METHOD, SUPERSEDED_PDF_REPAIR_METHOD}
    ]
    promoted_rows = [
        build_row(raw, reference_for_source(raw, retained_rows), fields)
        for raw in source_rows
    ]
    promoted_keys = [canonical_key(row) for row in promoted_rows]
    if len(promoted_keys) != len(set(promoted_keys)):
        raise RuntimeError("Promotion produced duplicate point/residency/youth/source keys")
    retained_keys = {canonical_key(row) for row in retained_rows}
    overlap = sorted(set(promoted_keys) & retained_keys)
    if overlap:
        raise RuntimeError(f"Promotion collides with existing canonical keys: {overlap[:10]}")

    promoted_rows.sort(
        key=lambda row: (
            clean(row.get("source_scope")),
            clean(row.get("hunt_code")),
            clean(row.get("residency")),
            integer(row.get("points")),
        )
    )
    return {
        "fields": fields,
        "canonical_rows_before": canonical_rows,
        "output_rows": retained_rows + promoted_rows,
        "promoted_rows": promoted_rows,
        "source_hashes": source_hashes,
    }


def summary_payload(result: dict[str, object], write: bool) -> dict[str, object]:
    canonical_before = result["canonical_rows_before"]
    output_rows = result["output_rows"]
    promoted_rows = result["promoted_rows"]
    assert isinstance(canonical_before, list)
    assert isinstance(output_rows, list)
    assert isinstance(promoted_rows, list)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "write": write,
        "canonical_path": CANONICAL.relative_to(ROOT).as_posix(),
        "canonical_sha256_before": sha256(CANONICAL),
        "canonical_rows_before": len(canonical_before),
        "canonical_rows_after": len(output_rows),
        "promoted_point_rows": len(promoted_rows),
        "promoted_hunt_codes": len({row["hunt_code"] for row in promoted_rows}),
        "promoted_source_scope_counts": dict(
            sorted(Counter(row["source_scope"] for row in promoted_rows).items())
        ),
        "promoted_residency_counts": dict(
            sorted(Counter(row["residency"] for row in promoted_rows).items())
        ),
        "retained_reference_rows": sum(
            row.get("record_type") == "hunt_planner_permit_reference"
            for row in output_rows
        ),
        "superseded_partial_or_repaired_rows_removed": len(canonical_before)
        + len(promoted_rows)
        - len(output_rows),
        "retained_source_sha256": result["source_hashes"],
        "year_guard": "IsHistoricalData=false and SeasonWeapons contains 2026 and not 2025",
        "probability_policy": (
            "successful_applicants / eligible_applicants when both are positive; "
            "blank probability otherwise"
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
    candidate = AUDIT_DIR / "draw_results_2026_youth_deer_promoted_candidate.csv"
    write_csv(candidate, fields, output_rows)
    summary = summary_payload(result, args.write)
    summary["candidate_path"] = candidate.relative_to(ROOT).as_posix()

    if args.write:
        backup_dir = AUDIT_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_dir / f"{CANONICAL.stem}.before_youth_deer_{timestamp}.csv"
        shutil.copy2(CANONICAL, backup)
        temporary = CANONICAL.with_suffix(CANONICAL.suffix + ".tmp")
        write_csv(temporary, fields, output_rows)
        os.replace(temporary, CANONICAL)
        summary["canonical_sha256_after"] = sha256(CANONICAL)
        summary["backup_path"] = backup.relative_to(ROOT).as_posix()

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (AUDIT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
