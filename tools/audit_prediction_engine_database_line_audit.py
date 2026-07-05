#!/usr/bin/env python3
"""Line-by-line prediction coverage audit for DATABASE/canonical truth rows.

This audit is intentionally non-mutating. It does not run prediction engines,
rewrite truth files, or promote outputs. It builds a row-level reconciliation
package under audits/prediction_engine_database_line_audit/<timestamp>/.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = Path("audits") / "prediction_engine_database_line_audit"

DATABASE = Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
CANONICAL_GLOB = "data_truth/draw_results_truth/normalized/canonical_yearly/*.csv"
LONG_FILE = Path("data_truth/draw_results_truth/normalized/draw_results_long.csv")
LOCKED_2026_UNIVERSE = Path(
    "data_truth/hunt_code_universe_truth/locked/2026/LOCKED_2026_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv"
)

PREDICTION_SURFACES = [
    Path("processed_data/draw_reality_engine_predictive_v2.csv"),
    Path("processed_data/ml_draw_predictions_v1.csv"),
    Path("processed_data/sportsman_permit_predictions_v1.csv"),
    Path("processed_data/youth_draw_predictions_v1.csv"),
    Path("processed_data/bear_draw_predictions_v1.csv"),
    Path("processed_data/turkey_bonus_predictions_v1.csv"),
    Path("processed_data/youth_turkey_predictions_v1.csv"),
    Path("processed_data/phase6_bonus_special_predictions_v1.csv"),
    Path("processed_data/dedicated_hunter_predictions_v1.csv"),
    Path("processed_data/mountain_lion_availability_predictions_v1.csv"),
    Path("processed_data/private_lands_antlerless_elk_predictions_v1.csv"),
    Path("processed_data/private_lands_antlerless_elk_allocations_v1.csv"),
]

HOLDOUT_FAMILIES = {
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
    "PREFERENCE_PRONGHORN_DOE",
}

BONUS_POINT_PURCHASE_ONLY_CODES = {
    "BER",
    "BIS",
    "BPU",
    "DBS",
    "DEE",
    "DHL",
    "ELK",
    "GDR",
    "GOA",
    "MOO",
    "PRO",
    "RMB",
}

PROBABILITY_FIELDS = (
    "p_draw",
    "p_sportsman_draw",
    "p_availability",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "odds_2026_projected",
)

LINE_FIELDS = [
    "source_universe",
    "source_file",
    "source_row_number",
    "hunt_code",
    "hunt_name",
    "species",
    "year",
    "model_target_year",
    "draw_system_type",
    "engine_family",
    "residency",
    "point_level",
    "draw_pool",
    "boundary_id",
    "locked_primary_universe_bucket",
    "locked_scoring_bucket",
    "locked_boundary_id",
    "row_status",
    "prediction_eligibility",
    "requires_prediction",
    "prediction_final_classification",
    "match_tier",
    "matched_prediction_files",
    "matched_prediction_row_count",
    "matched_probability_field",
    "matched_probability_value",
    "probability_valid",
    "probability_issue",
    "zero_point_preserved",
    "quota_arithmetic_status",
    "duplicate_prediction_key_count",
    "truth_leakage_status",
    "audit_note",
    "operational_key",
    "hunt_code_only_match_count",
]


def clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def norm_code(value: Any) -> str:
    return re.sub(r"\s+", "", upper(value))


def norm_residency(value: Any) -> str:
    text = upper(value)
    if text in {"R", "RES", "RESIDENT"}:
        return "RESIDENT"
    if text in {"NR", "NONRES", "NON-RESIDENT", "NONRESIDENT"}:
        return "NONRESIDENT"
    return text


def norm_points(value: Any) -> str:
    text = clean(value)
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer():
        return str(int(number))
    return text


def norm_pool(value: Any) -> str:
    text = upper(value)
    return text if text else "STANDARD"


def norm_draw_system(row: dict[str, str]) -> str:
    for field in ("draw_system_type", "draw_2026_system_type", "hunt_draw_class", "draw_design", "draw_method"):
        value = upper(row.get(field))
        if value:
            return value
    return ""


def first_value(row: dict[str, str], fields: Iterable[str]) -> str:
    for field in fields:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def row_year(row: dict[str, str]) -> str:
    return first_value(row, ("forecast_year", "model_target_year", "target_year", "year", "actual_draw_year"))


def actual_year(row: dict[str, str]) -> str:
    return first_value(row, ("actual_draw_year", "year"))


def model_year(row: dict[str, str]) -> str:
    return first_value(row, ("model_target_year", "forecast_year", "target_year", "year"))


def int_or_none(value: Any) -> int | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def float_or_none(value: Any) -> float | None:
    text = clean(value).replace("%", "")
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def operational_key(row: dict[str, str], year_value: str | None = None) -> tuple[str, str, str, str, str, str]:
    return (
        clean(year_value if year_value is not None else row_year(row)),
        norm_code(row.get("hunt_code")),
        norm_draw_system(row),
        norm_residency(row.get("residency")),
        norm_points(row.get("points") or row.get("point") or row.get("point_level")),
        norm_pool(row.get("draw_pool")),
    )


def relaxed_key(row: dict[str, str], year_value: str | None = None) -> tuple[str, str, str, str]:
    return (
        clean(year_value if year_value is not None else row_year(row)),
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        norm_points(row.get("points") or row.get("point") or row.get("point_level")),
    )


def code_year_key(row: dict[str, str], year_value: str | None = None) -> tuple[str, str]:
    return (clean(year_value if year_value is not None else row_year(row)), norm_code(row.get("hunt_code")))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with (REPO / path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def iter_csv(path: Path) -> Iterable[tuple[int, dict[str, str]]]:
    with (REPO / path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            yield row_number, row


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


_LOCKED_2026_BY_CODE: dict[str, dict[str, str]] | None = None
_DATABASE_2026_BY_CODE: dict[str, dict[str, str]] | None = None


def locked_2026_by_code() -> dict[str, dict[str, str]]:
    global _LOCKED_2026_BY_CODE
    if _LOCKED_2026_BY_CODE is not None:
        return _LOCKED_2026_BY_CODE
    locked: dict[str, dict[str, str]] = {}
    full = REPO / LOCKED_2026_UNIVERSE
    if full.exists():
        with full.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = norm_code(row.get("hunt_code"))
                if code:
                    locked[code] = row
    _LOCKED_2026_BY_CODE = locked
    return locked


def locked_2026_row(code: str) -> dict[str, str]:
    return locked_2026_by_code().get(norm_code(code), {})


def database_2026_by_code() -> dict[str, dict[str, str]]:
    global _DATABASE_2026_BY_CODE
    if _DATABASE_2026_BY_CODE is not None:
        return _DATABASE_2026_BY_CODE
    database: dict[str, dict[str, str]] = {}
    full = REPO / DATABASE
    if full.exists():
        with full.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = norm_code(row.get("hunt_code"))
                if code:
                    database[code] = row
    _DATABASE_2026_BY_CODE = database
    return database


def database_2026_row(code: str) -> dict[str, str]:
    return database_2026_by_code().get(norm_code(code), {})


def classify_engine_family(row: dict[str, str]) -> str:
    draw = norm_draw_system(row)
    family = upper(row.get("engine_family") or row.get("runtime_promotion_family") or row.get("model_strategy"))
    text = " ".join(
        upper(row.get(field))
        for field in ("hunt_code", "species", "sex_type", "hunt_type", "hunt_class", "draw_pool", "draw_design", "record_type", "row_type")
    )
    combined = " ".join([draw, family, text])
    if "SPORTSMAN" in combined:
        return "SPORTSMAN_RANDOM_ONLY"
    if "YOUTH" in combined:
        return "YOUTH_RANDOM"
    if "PRIVATE_LANDS" in combined or "PRIVATE LANDS" in combined:
        return "AVAILABILITY_ONLY"
    if "COUGAR" in combined or "MOUNTAIN_LION" in combined or "MOUNTAIN LION" in combined:
        return "AVAILABILITY_ONLY"
    if "BEAR" in combined:
        return "BONUS_SPLIT_DRAW" if "LIMITED" in combined or "MAX" in combined else "AVAILABILITY_ONLY"
    if "PREFERENCE" in combined or "DEDICATED_HUNTER" in combined:
        return "PREFERENCE_DRAW"
    if "MAX_WEIGHTED" in combined or "BONUS" in combined or "OIL" in combined or "ONCE-IN-A-LIFETIME" in combined:
        return "BONUS_SPLIT_DRAW"
    if "DIRECT" in combined or "ALLOCATION" in combined or "CONSERVATION" in combined or "EXPO" in combined:
        return "DIRECT_ALLOCATION"
    if "OTC" in combined or "CAPPED" in combined or "AVAILABILITY" in combined:
        return "AVAILABILITY_ONLY"
    if "HARVEST" in combined:
        return "HARVEST_FEATURE"
    if "POINT_LADDER" in combined:
        return "POINT_LADDER"
    return "UNKNOWN"


def row_text(row: dict[str, str]) -> str:
    return " ".join(upper(value) for value in row.values() if value)


def is_holdout(row: dict[str, str]) -> bool:
    target = clean(model_year(row))
    text = row_text(row)
    if target != "2027" and "2027_MODEL" not in text and "FOR_2027" not in text:
        return False
    draw = norm_draw_system(row)
    return draw in HOLDOUT_FAMILIES or (
        "PREFERENCE" in text and ("ANTLERLESS" in text or "DOE" in text) and ("DEER" in text or "ELK" in text or "PRONGHORN" in text)
    )


def is_historical_reference(row: dict[str, str]) -> bool:
    target = int_or_none(model_year(row))
    return target is not None and target < 2026


def classify_eligibility(row: dict[str, str], source_universe: str) -> tuple[str, bool, str]:
    code = norm_code(row.get("hunt_code"))
    draw = norm_draw_system(row)
    family = classify_engine_family(row)
    text = row_text(row)
    record_type = upper(row.get("record_type") or row.get("row_type"))
    locked = locked_2026_row(code)
    database = database_2026_row(code)
    locked_scoring_bucket = upper(locked.get("scoring_bucket"))
    locked_text = row_text(locked)
    database_text = row_text(database)

    if not code:
        return "MISSING_REQUIRED_FIELDS", False, "Missing hunt_code."
    if code == "CG1000":
        return "TERMINATED_OR_CROSSWALK_ONLY", False, "CG1000 is not in the 2026 model workbook/matrix; current cougar runtime carries CG9999 only."
    if "CWMU" in locked_text and (
        "LIVE_DWR_CWMU_TOTAL_ONLY" in database_text
        or "DWR_HUNTPLANNER_CWMU" in database_text
        or "CONTACT CWMU OPERATOR" in database_text
        or "CONTACT OPERATOR" in database_text
    ):
        return (
            "CWMU_CONTACT_OPERATOR_REFERENCE_ONLY",
            False,
            "Locked universe/database identify this hunt as CWMU quota/contact-operator reference, not a point-level prediction obligation.",
        )
    if locked_scoring_bucket and locked_scoring_bucket != "CANDIDATE_MODEL_SCORABLE_REQUIRES_ENGINE_GATES":
        if locked_scoring_bucket == "MAPPED_SEARCHABLE_NOT_AUTOMATICALLY_SCORABLE":
            return "REFERENCE_ONLY", False, "Locked 2026 universe marks this code mapped/searchable, not automatically scorable."
        if locked_scoring_bucket == "BIBLE_REFERENCE_NOT_CURRENT_SCORING_AUTHORITY":
            return "REFERENCE_ONLY", False, "Locked 2026 universe marks this code as BIBLE/source reference, not current scoring authority."
        if locked_scoring_bucket == "SUPPORT_ONLY_REVIEW":
            return "REFERENCE_ONLY", False, "Locked 2026 universe marks this code support/reference only."
        return "REFERENCE_ONLY", False, f"Locked 2026 universe marks this code non-scorable: {locked_scoring_bucket}."
    if code in BONUS_POINT_PURCHASE_ONLY_CODES:
        return "BONUS_POINT_PURCHASE_ONLY", False, "Bonus point purchase-only code."
    if code.startswith("CG") and code != "CG9999" and model_year(row) == "2027":
        return "TERMINATED_OR_CROSSWALK_ONLY", False, "2027 cougar runtime carries forward CG9999 only."
    if source_universe == "DATABASE_2026" and draw in HOLDOUT_FAMILIES:
        return "UNRELEASED_2027_ANTLERLESS_HOLDOUT", False, "Current antlerless/doe row is held out until 2027 actual results are released."
    if any(token in text for token in ("NOT_ACTIVE_HISTORICAL_ONLY", "HISTORICAL_2025_ONLY_NOT_ACTIVE_2026", "RETIRED_2026_SUCCESSOR")):
        return "TERMINATED_OR_CROSSWALK_ONLY", False, "Historical/retired row is not an active prediction obligation."
    if source_universe == "DATABASE_2026" and "HISTORICAL_" in text and not clean(row.get("permits_2026_total") or row.get("permit_allotment_2026_total")):
        return "TERMINATED_OR_CROSSWALK_ONLY", False, "Historical database row with no current 2026 permits is not an active prediction obligation."
    if "DISCONTINUED_NO_SUCCESSOR" in text or "DISCONTINUED_" in text:
        return "TERMINATED_OR_CROSSWALK_ONLY", False, "Discontinued/crosswalk-only row is not an active prediction obligation."
    if "LEGACY_COMPAT_MIRROR" in text or "LEGACY_MIRROR" in text or "DERIVED_FROM_PUBLISHED_2026_PERMITS_COMPAT" in text:
        return "REFERENCE_ONLY", False, "Compatibility mirror row; not a direct prediction obligation."
    if is_holdout(row):
        return "UNRELEASED_2027_ANTLERLESS_HOLDOUT", False, "Unreleased 2027 antlerless/doe actual results are intentionally held out."
    if "CONTACT OPERATOR" in text or "CWMU_CONTACT_OPERATOR" in text:
        return "CWMU_CONTACT_OPERATOR_REFERENCE_ONLY", False, "CWMU contact-operator/reference row."
    if "BONUS POINT PURCHASE" in text or "POINT PURCHASE" in text:
        return "BONUS_POINT_PURCHASE_ONLY", False, "Bonus point purchase-only row."
    if is_historical_reference(row):
        return "REFERENCE_ONLY", False, "Historical canonical truth row; not a current runtime prediction obligation."
    if "REFERENCE_ONLY" in text or "REFERENCE ROW" in text or "NON_SCORABLE" in text or "NON-SCORABLE" in text:
        return "REFERENCE_ONLY", False, "Reference/non-scorable row."
    if "NO_PUBLISHED_PERMIT_AUTHORITY" in text or "NO_PUBLISHED_2026_PRIVATE_LAND_ELK_PERMIT_COUNT" in text:
        return "REFERENCE_ONLY", False, "No published permit authority/count; not a public prediction odds obligation."
    if any(token in text for token in ("LANDOWNER_PRIVATE_LAND_NO_PUBLISHED_PERMIT_COUNT", "PRIVATE_LAND_DEER_NO_PUBLISHED_PERMIT_COUNT", "SOURCE_CONFIRMED_NO_PUBLISHED_PERMIT_COUNT", "PERMIT_DATA_NOT_PUBLISHED")):
        return "REFERENCE_ONLY", False, "No published permit count/source; not a public prediction odds obligation."
    if "NO_QUOTA_PUBLISHED_REFERENCE_ONLY" in text:
        return "REFERENCE_ONLY", False, "No quota published reference-only row."
    if "NO_QUOTA_PUBLISHED" in text:
        return "REFERENCE_ONLY", False, "No quota published; not a probability obligation."
    if "HARVEST OBJECTIVE" in text:
        return "REFERENCE_ONLY", False, "Harvest-objective availability/reference row; not a draw-probability obligation."
    if "LIVE_DWR_TOTAL_ONLY" in text:
        return "ALLOCATION_ONLY", False, "Live DWR total-only row; not a point-level prediction obligation."
    if "LIVE_DWR_CWMU_TOTAL_ONLY" in text or "DWR_HUNTPLANNER_CWMU" in text:
        return "CWMU_CONTACT_OPERATOR_REFERENCE_ONLY", False, "CWMU quota/contact-operator style row; not a point-level prediction obligation."
    if any(token in text for token in ("CONSERVATION", "EXPO", "LANDOWNER", "LIFETIME", "GUARANTEED TAG", "GENERAL GUARANTEED")):
        return "ALLOCATION_ONLY", False, "Allocation/reference-only permit category."
    if "QUOTA" in record_type or "ALLOCATION" in record_type or "PERMIT_TOTAL" in record_type:
        return "ALLOCATION_ONLY", False, "Quota/allocation row type."
    if family == "SPORTSMAN_RANDOM_ONLY":
        return "SPORTSMAN_RANDOM_ONLY", True, "Sportsman random-only engine row."
    if source_universe == "DATABASE_2026":
        if not draw and family == "UNKNOWN":
            return "MISSING_REQUIRED_FIELDS", False, "Database row lacks draw-system classification."
        if not clean(row.get("permits_2026_total") or row.get("permit_allotment_2026_total")) and not clean(
            row.get("permits_2026_source") or row.get("permit_allotment_2026_source")
        ):
            return "MISSING_REQUIRED_FIELDS", False, "Database row lacks current 2026 permit source/total fields."
        if family in {"DIRECT_ALLOCATION", "HARVEST_FEATURE", "POINT_LADDER"}:
            return "REFERENCE_ONLY", False, f"{family} is not a public probability obligation."
        return "SCORABLE_PREDICTION_REQUIRED", True, "Current database row classified as prediction-obligated."
    if record_type and "POINT" not in record_type and "DRAW" not in record_type:
        return "REFERENCE_ONLY", False, "Canonical row is not a point-level draw-result row."
    if family == "UNKNOWN" and not draw:
        return "MISSING_REQUIRED_FIELDS", False, "Canonical row lacks draw-system classification."
    return "SCORABLE_PREDICTION_REQUIRED", True, "Canonical scorable point-level row in current runtime horizon."


def probability_info(rows: list[dict[str, str]]) -> tuple[str, str, bool, str]:
    for row in rows:
        for field in PROBABILITY_FIELDS:
            if field not in row:
                continue
            value = clean(row.get(field))
            if value == "":
                continue
            number = float_or_none(value)
            if number is None:
                return field, value, False, "NON_NUMERIC_PROBABILITY"
            if field.endswith("_pct") or number > 1:
                if 0 <= number <= 100:
                    return field, value, True, ""
            elif 0 <= number <= 1:
                return field, value, True, ""
            return field, value, False, "PROBABILITY_OUT_OF_BOUNDS"
    return "", "", False, "MISSING_PROBABILITY"


def matches_are_non_predictive_reference(rows: list[dict[str, str]]) -> bool:
    if not rows:
        return False
    reference_tokens = (
        "EXCLUDED_NOT_PREDICTIVE_DRAW",
        "REFERENCE_ONLY",
        "GUIDEBOOK_TRUTH_REFERENCE",
        "CWMU_CONSERVATION_PRIVATE_LAND_REFERENCE_ONLY",
    )
    for row in rows:
        text = row_text(row)
        if not any(token in text for token in reference_tokens):
            return False
    return True


def quota_status(row: dict[str, str]) -> str:
    candidates = [
        ("permit_allotment_2026_res", "permit_allotment_2026_nr", "permit_allotment_2026_total"),
        ("permits_2026_res", "permits_2026_nr", "permits_2026_total"),
        ("resident_total_permits", "nonresident_total_permits", "total_permits"),
    ]
    checked = False
    for res_field, nr_field, total_field in candidates:
        res = int_or_none(row.get(res_field))
        nr = int_or_none(row.get(nr_field))
        total = int_or_none(row.get(total_field))
        if res is None and nr is None and total is None:
            continue
        checked = True
        values = [value for value in (res, nr, total) if value is not None]
        if any(value < 0 for value in values):
            return "INVALID_NEGATIVE_QUOTA"
        if res is not None and nr is not None and total is not None and res + nr != total:
            return "INVALID_RES_NR_TOTAL_MISMATCH"
    return "CHECKED_OK" if checked else "NOT_APPLICABLE"


def truth_leakage_status(row: dict[str, str]) -> str:
    forecast = int_or_none(row.get("forecast_year") or row.get("year"))
    if forecast is None:
        return "NOT_APPLICABLE"
    source_years = re.findall(r"\b(20\d{2})\b", clean(row.get("source_years_used")))
    latest = int_or_none(row.get("latest_source_year"))
    source_text = upper(row.get("source_dataset") or row.get("source_file") or row.get("runtime_promotion_source"))
    if latest is not None and latest > forecast:
        return "POTENTIAL_LEAKAGE_FUTURE_SOURCE_YEAR"
    if str(forecast) in source_years and any(token in source_text for token in ("ACTUAL", "DRAW_RESULT", "TRUTH")):
        return "POTENTIAL_LEAKAGE_TARGET_ACTUAL_YEAR"
    return "NO_TARGET_ACTUAL_LEAKAGE_DETECTED"


def build_prediction_indexes() -> tuple[dict[str, Any], dict[str, Any]]:
    exact: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    relaxed: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    code_year: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    code_only: dict[str, list[dict[str, str]]] = defaultdict(list)
    duplicate_rows: list[dict[str, Any]] = []
    surface_summaries: list[dict[str, Any]] = []
    current_file_key_counts: dict[tuple[str, str, str, str, str, str], int]

    for path in PREDICTION_SURFACES:
        full = REPO / path
        if not full.exists():
            surface_summaries.append({"prediction_file": str(path), "exists": False, "row_count": 0, "hunt_codes": 0})
            continue
        current_file_key_counts = Counter()
        row_count = 0
        codes: set[str] = set()
        for row_number, row in iter_csv(path):
            row_count += 1
            code = norm_code(row.get("hunt_code"))
            if code:
                codes.add(code)
            row["_prediction_file"] = str(path)
            row["_prediction_row_number"] = str(row_number)
            key = operational_key(row)
            current_file_key_counts[key] += 1
            exact[key].append(row)
            relaxed[relaxed_key(row)].append(row)
            code_year[code_year_key(row)].append(row)
            if code:
                code_only[code].append(row)
        for key, count in current_file_key_counts.items():
            if count > 1 and any(key):
                duplicate_rows.append(
                    {
                        "prediction_file": str(path),
                        "operational_key": "|".join(key),
                        "duplicate_count": count,
                    }
                )
        surface_summaries.append(
            {
                "prediction_file": str(path),
                "exists": True,
                "row_count": row_count,
                "hunt_codes": len(codes),
                "duplicate_operational_key_groups": sum(1 for count in current_file_key_counts.values() if count > 1),
            }
        )

    return (
        {
            "exact": exact,
            "relaxed": relaxed,
            "code_year": code_year,
            "code_only": code_only,
            "duplicate_rows": duplicate_rows,
        },
        {"surface_summaries": surface_summaries},
    )


def find_prediction_match(row: dict[str, str], indexes: dict[str, Any], source_universe: str) -> tuple[str, list[dict[str, str]], str]:
    years_to_try = [model_year(row), row_year(row), actual_year(row)]
    years_to_try = [year for index, year in enumerate(years_to_try) if year and year not in years_to_try[:index]]

    for year in years_to_try:
        key = operational_key(row, year)
        rows = indexes["exact"].get(key, [])
        if rows:
            return "EXACT_OPERATIONAL_KEY", rows, "|".join(key)
    for year in years_to_try:
        key = relaxed_key(row, year)
        rows = indexes["relaxed"].get(key, [])
        if rows:
            return "RELAXED_YEAR_CODE_RESIDENCY_POINTS", rows, "|".join(key)
    for year in years_to_try:
        key = code_year_key(row, year)
        rows = indexes["code_year"].get(key, [])
        if rows:
            return "HUNT_CODE_YEAR_ONLY", rows, "|".join(key)
    code = norm_code(row.get("hunt_code"))
    if source_universe == "DATABASE_2026" and code:
        rows = indexes["code_only"].get(code, [])
        if rows:
            return "HUNT_CODE_ONLY_DATABASE_COVERAGE", rows, code
    return "NO_MATCH", [], "|".join(operational_key(row))


def final_classification(eligibility: str, requires: bool, match_tier: str, probability_valid: bool, duplicate_count: int) -> str:
    if duplicate_count > 1:
        return "PREDICTION_KEY_COLLISION"
    if not requires:
        if eligibility == "UNRELEASED_2027_ANTLERLESS_HOLDOUT":
            return "PREDICTION_HELD_OUT_UNRELEASED_ACTUALS"
        if eligibility in {"MISSING_REQUIRED_FIELDS", "NEEDS_REVIEW"}:
            return "PREDICTION_SOURCE_DATA_INCOMPLETE"
        return "PREDICTION_NOT_REQUIRED_REFERENCE_ONLY"
    if match_tier != "NO_MATCH" and probability_valid:
        return "PREDICTION_PRESENT"
    if match_tier != "NO_MATCH" and not probability_valid:
        return "PREDICTION_SOURCE_DATA_INCOMPLETE"
    if eligibility == "SCORABLE_PREDICTION_REQUIRED":
        return "PREDICTION_MISSING_BLOCKER"
    return "PREDICTION_ENGINE_FAMILY_NOT_WIRED"


def audit_row(
    row: dict[str, str],
    source_universe: str,
    source_file: str,
    row_number: int,
    indexes: dict[str, Any],
) -> dict[str, Any]:
    eligibility, requires, note = classify_eligibility(row, source_universe)
    match_tier, matches, op_key = find_prediction_match(row, indexes, source_universe)
    if requires and matches_are_non_predictive_reference(matches):
        eligibility = "REFERENCE_ONLY"
        requires = False
        note = "Matched runtime rows are explicitly marked non-predictive/reference-only."
    prob_field, prob_value, prob_valid, prob_issue = probability_info(matches)
    duplicate_count = 0
    if match_tier == "EXACT_OPERATIONAL_KEY":
        per_file_counts = Counter(clean(match.get("_prediction_file")) for match in matches)
        duplicate_count = max((count for count in per_file_counts.values()), default=0)
        if duplicate_count <= 1:
            duplicate_count = 0
    classification = final_classification(eligibility, requires, match_tier, prob_valid, duplicate_count)
    matched_files = sorted({clean(match.get("_prediction_file")) for match in matches if clean(match.get("_prediction_file"))})
    point = norm_points(row.get("points") or row.get("point") or row.get("point_level"))
    locked_row = locked_2026_row(row.get("hunt_code", ""))
    return {
        "source_universe": source_universe,
        "source_file": source_file,
        "source_row_number": row_number,
        "hunt_code": norm_code(row.get("hunt_code")),
        "hunt_name": first_value(row, ("hunt_name", "raw_hunt_name", "unit")),
        "species": first_value(row, ("species", "sportsman_species")),
        "year": actual_year(row) or row_year(row),
        "model_target_year": model_year(row),
        "draw_system_type": norm_draw_system(row),
        "engine_family": classify_engine_family(row),
        "residency": norm_residency(row.get("residency")),
        "point_level": point,
        "draw_pool": norm_pool(row.get("draw_pool")),
        "boundary_id": clean(row.get("boundary_id")),
        "locked_primary_universe_bucket": clean(locked_row.get("primary_universe_bucket")),
        "locked_scoring_bucket": clean(locked_row.get("scoring_bucket")),
        "locked_boundary_id": clean(locked_row.get("boundary_id")),
        "row_status": clean(row.get("record_type") or row.get("row_type") or row.get("algorithm_status") or row.get("permit_allotment_2026_status")),
        "prediction_eligibility": eligibility,
        "requires_prediction": str(bool(requires)).lower(),
        "prediction_final_classification": classification,
        "match_tier": match_tier,
        "matched_prediction_files": ";".join(matched_files),
        "matched_prediction_row_count": len(matches),
        "matched_probability_field": prob_field,
        "matched_probability_value": prob_value,
        "probability_valid": str(bool(prob_valid)).lower(),
        "probability_issue": "" if prob_valid else prob_issue,
        "zero_point_preserved": "true" if point == "0" and matches else "false" if point == "0" else "not_applicable",
        "quota_arithmetic_status": quota_status(row),
        "duplicate_prediction_key_count": duplicate_count,
        "truth_leakage_status": truth_leakage_status(matches[0]) if matches else "NO_MATCH",
        "audit_note": note,
        "operational_key": op_key,
        "hunt_code_only_match_count": len(indexes["code_only"].get(norm_code(row.get("hunt_code")), [])),
    }


def build_summary(
    rows: list[dict[str, Any]],
    database_codes: set[str],
    canonical_counts: list[dict[str, Any]],
    surface_summaries: list[dict[str, Any]],
    duplicate_count: int,
    output_dir: Path,
) -> dict[str, Any]:
    final_counts = Counter(row["prediction_final_classification"] for row in rows)
    eligibility_counts = Counter(row["prediction_eligibility"] for row in rows)
    required_rows = [row for row in rows if row["requires_prediction"] == "true"]
    required_missing = [row for row in required_rows if row["prediction_final_classification"] != "PREDICTION_PRESENT"]
    current_active_codes = {row["hunt_code"] for row in rows if row["source_universe"] == "DATABASE_2026" and row["hunt_code"]}
    predicted_codes = {row["hunt_code"] for row in rows if row["prediction_final_classification"] == "PREDICTION_PRESENT" and row["hunt_code"]}
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_dir": str(output_dir),
        "database_hunt_codes": len(database_codes),
        "canonical_hunt_codes_by_year": canonical_counts,
        "total_active_hunt_codes": len(current_active_codes),
        "total_line_rows": len(rows),
        "total_scorable_rows": sum(1 for row in rows if row["prediction_eligibility"] == "SCORABLE_PREDICTION_REQUIRED"),
        "total_prediction_required_rows": len(required_rows),
        "total_predicted_rows": final_counts["PREDICTION_PRESENT"],
        "total_missing_prediction_rows": final_counts["PREDICTION_MISSING_BLOCKER"],
        "total_held_out_rows": final_counts["PREDICTION_HELD_OUT_UNRELEASED_ACTUALS"],
        "total_reference_only_rows": final_counts["PREDICTION_NOT_REQUIRED_REFERENCE_ONLY"],
        "prediction_required_not_present_rows": len(required_missing),
        "prediction_required_hunt_codes": len({row["hunt_code"] for row in required_rows if row["hunt_code"]}),
        "predicted_hunt_codes": len(predicted_codes),
        "database_codes_with_prediction": len(database_codes & predicted_codes),
        "database_codes_without_prediction_or_exemption": len(
            {
                row["hunt_code"]
                for row in rows
                if row["source_universe"] == "DATABASE_2026"
                and row["prediction_final_classification"] in {"PREDICTION_MISSING_BLOCKER", "PREDICTION_SOURCE_DATA_INCOMPLETE", "PREDICTION_ENGINE_FAMILY_NOT_WIRED"}
            }
        ),
        "duplicate_prediction_key_groups": duplicate_count,
        "final_classification_counts": dict(sorted(final_counts.items())),
        "eligibility_counts": dict(sorted(eligibility_counts.items())),
        "prediction_surface_summaries": surface_summaries,
        "pass_condition": len(required_missing) == 0 and duplicate_count == 0,
        "classification": "PASS" if len(required_missing) == 0 and duplicate_count == 0 else "BLOCKED_REVIEW_REQUIRED",
    }
    return summary


def write_group_counts(path: Path, rows: list[dict[str, Any]], group_fields: list[str]) -> None:
    counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(clean(row.get(field)) for field in group_fields)
        counts[key]["total_rows"] += 1
        counts[key][clean(row.get("prediction_final_classification"))] += 1
        if row.get("requires_prediction") == "true":
            counts[key]["prediction_required_rows"] += 1
        if row.get("prediction_final_classification") == "PREDICTION_PRESENT":
            counts[key]["prediction_present_rows"] += 1
    fields = group_fields + [
        "total_rows",
        "prediction_required_rows",
        "prediction_present_rows",
        "PREDICTION_PRESENT",
        "PREDICTION_NOT_REQUIRED_REFERENCE_ONLY",
        "PREDICTION_HELD_OUT_UNRELEASED_ACTUALS",
        "PREDICTION_MISSING_BLOCKER",
        "PREDICTION_KEY_COLLISION",
        "PREDICTION_SOURCE_DATA_INCOMPLETE",
        "PREDICTION_ENGINE_FAMILY_NOT_WIRED",
    ]
    out = []
    for key, counter in sorted(counts.items()):
        row = dict(zip(group_fields, key))
        row.update({field: counter.get(field, 0) for field in fields if field not in row})
        out.append(row)
    write_csv(path, out, fields)


def main() -> int:
    global REPO
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(REPO))
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    REPO = Path(args.repo).resolve()
    output_dir = REPO / AUDIT_ROOT / args.timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    indexes, prediction_meta = build_prediction_indexes()
    database_fields, database_rows = read_csv(DATABASE)
    database_codes = {norm_code(row.get("hunt_code")) for row in database_rows if norm_code(row.get("hunt_code"))}

    line_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(database_rows, start=2):
        line_rows.append(audit_row(row, "DATABASE_2026", str(DATABASE), row_number, indexes))

    canonical_counts: list[dict[str, Any]] = []
    for path in sorted(REPO.glob(CANONICAL_GLOB)):
        rel = path.relative_to(REPO)
        row_count = 0
        codes: set[str] = set()
        years: set[str] = set()
        model_years: set[str] = set()
        for row_number, row in iter_csv(rel):
            row_count += 1
            code = norm_code(row.get("hunt_code"))
            if code:
                codes.add(code)
            if actual_year(row):
                years.add(actual_year(row))
            if model_year(row):
                model_years.add(model_year(row))
            line_rows.append(audit_row(row, "CANONICAL_YEARLY", str(rel), row_number, indexes))
        canonical_counts.append(
            {
                "source_file": str(rel),
                "rows": row_count,
                "hunt_codes": len(codes),
                "actual_years": ",".join(sorted(years)),
                "model_target_years": ",".join(sorted(model_years)),
            }
        )

    duplicate_rows = indexes["duplicate_rows"]
    summary = build_summary(
        line_rows,
        database_codes,
        canonical_counts,
        prediction_meta["surface_summaries"],
        len(duplicate_rows),
        output_dir,
    )

    write_csv(output_dir / "PREDICTION_ENGINE_DATABASE_LINE_AUDIT.csv", line_rows, LINE_FIELDS)
    write_csv(
        output_dir / "PREDICTION_MISSING_BY_HUNT_CODE.csv",
        [
            row
            for row in line_rows
            if row["prediction_final_classification"]
            in {"PREDICTION_MISSING_BLOCKER", "PREDICTION_SOURCE_DATA_INCOMPLETE", "PREDICTION_ENGINE_FAMILY_NOT_WIRED"}
        ],
        LINE_FIELDS,
    )
    write_group_counts(output_dir / "PREDICTION_COVERAGE_BY_ENGINE_FAMILY.csv", line_rows, ["engine_family"])
    write_group_counts(output_dir / "PREDICTION_COVERAGE_BY_SPECIES.csv", line_rows, ["species"])
    write_csv(
        output_dir / "PREDICTION_DUPLICATE_KEYS.csv",
        duplicate_rows,
        ["prediction_file", "operational_key", "duplicate_count"],
    )
    write_csv(
        output_dir / "PREDICTION_HOLDOUT_ROWS.csv",
        [row for row in line_rows if row["prediction_final_classification"] == "PREDICTION_HELD_OUT_UNRELEASED_ACTUALS"],
        LINE_FIELDS,
    )
    write_csv(
        output_dir / "PREDICTION_REFERENCE_ONLY_ROWS.csv",
        [row for row in line_rows if row["prediction_final_classification"] == "PREDICTION_NOT_REQUIRED_REFERENCE_ONLY"],
        LINE_FIELDS,
    )
    write_csv(
        output_dir / "PREDICTION_SURFACE_SUMMARY.csv",
        prediction_meta["surface_summaries"],
        ["prediction_file", "exists", "row_count", "hunt_codes", "duplicate_operational_key_groups"],
    )
    write_csv(
        output_dir / "CANONICAL_HUNT_CODE_COUNTS_BY_YEAR.csv",
        canonical_counts,
        ["source_file", "rows", "hunt_codes", "actual_years", "model_target_years"],
    )

    (output_dir / "PREDICTION_ENGINE_DATABASE_AUDIT_SUMMARY.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    md = [
        "# Prediction Engine Database Line Audit",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Final Classification",
        "",
        f"- Status: `{summary['classification']}`",
        f"- Pass condition met: `{summary['pass_condition']}`",
        f"- Prediction-required rows: `{summary['total_prediction_required_rows']}`",
        f"- Predicted rows: `{summary['total_predicted_rows']}`",
        f"- Missing prediction blockers: `{summary['total_missing_prediction_rows']}`",
        f"- Held-out unreleased rows: `{summary['total_held_out_rows']}`",
        f"- Reference-only rows: `{summary['total_reference_only_rows']}`",
        f"- Duplicate prediction key groups: `{summary['duplicate_prediction_key_groups']}`",
        "",
        "## Hunt-Code Counts",
        "",
        f"- Database hunt codes: `{summary['database_hunt_codes']}`",
        f"- Active database hunt codes: `{summary['total_active_hunt_codes']}`",
        f"- Prediction-required hunt codes: `{summary['prediction_required_hunt_codes']}`",
        f"- Predicted hunt codes: `{summary['predicted_hunt_codes']}`",
        f"- Database codes with prediction: `{summary['database_codes_with_prediction']}`",
        f"- Database codes without prediction or exemption: `{summary['database_codes_without_prediction_or_exemption']}`",
        "",
        "## Key Contract",
        "",
        "- `hunt_code` is the display/reference handle only.",
        "- Prediction equality uses `forecast_year|year`, `hunt_code`, `draw_system_type`, `residency`, `points`, `draw_pool(default=standard)`.",
        "- The audit records match tiers so hunt-code-only coverage is visible and not confused with exact row-key coverage.",
        "",
        "## Output Files",
        "",
        "- `PREDICTION_ENGINE_DATABASE_LINE_AUDIT.csv`",
        "- `PREDICTION_MISSING_BY_HUNT_CODE.csv`",
        "- `PREDICTION_COVERAGE_BY_ENGINE_FAMILY.csv`",
        "- `PREDICTION_COVERAGE_BY_SPECIES.csv`",
        "- `PREDICTION_DUPLICATE_KEYS.csv`",
        "- `PREDICTION_HOLDOUT_ROWS.csv`",
        "- `PREDICTION_REFERENCE_ONLY_ROWS.csv`",
        "- `PREDICTION_SURFACE_SUMMARY.csv`",
        "- `CANONICAL_HUNT_CODE_COUNTS_BY_YEAR.csv`",
        "- `PREDICTION_ENGINE_DATABASE_AUDIT_SUMMARY.json`",
    ]
    (output_dir / "PREDICTION_ENGINE_DATABASE_AUDIT_SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"AUDIT_DIR: {output_dir}")
    print(f"CLASSIFICATION: {summary['classification']}")
    print(f"PASS_CONDITION: {summary['pass_condition']}")
    print(f"PREDICTION_REQUIRED_ROWS: {summary['total_prediction_required_rows']}")
    print(f"PREDICTION_PRESENT_ROWS: {summary['total_predicted_rows']}")
    print(f"MISSING_BLOCKERS: {summary['total_missing_prediction_rows']}")
    print(f"DUPLICATE_PREDICTION_KEY_GROUPS: {summary['duplicate_prediction_key_groups']}")
    return 0 if summary["pass_condition"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
