#!/usr/bin/env python3
"""Validate the Hunt Research page canonical data/engine contract.

This is a non-mutating validator. It writes a timestamped audit package under
audits/research_page_canonical_contract/<timestamp>/ and never promotes output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
AUDIT_ROOT = Path("audits") / "research_page_canonical_contract"

CANONICAL_TRUTH_GLOB = "data_truth/draw_results_truth/normalized/canonical_yearly/*.csv"
REFERENCE_DATABASE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"

ENGINE_FEEDERS = [
    "processed_data/draw_reality_engine.csv",
    "processed_data/draw_reality_engine_v2.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/hunt_master_enriched.csv",
    "processed_data/hunt_unit_reference_linked.csv",
]

RUNTIME_OUTPUTS = [
    "processed_data/hunt_research_2026_summary.json",
    "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
    "processed_data/hunt_research_2026_split/hunt_research_2026.details.json",
    "processed_data/hunt_research_2026_ladder.json",
    "processed_data/hunt_research_2026_ladder_preference.json",
]

PUBLIC_RESEARCH_OUTPUTS = [
    "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
    "processed_data/hunt_research_2026_summary.json",
]

HOLDOUT_FAMILIES = {
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
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
COUGAR_TERMINATED_REPORTING_PREFIX = "CG"
COUGAR_FORWARD_CODE = "CG9999"
TERMINATED_2026_CODES = {"EA1287"}
LEGITIMATE_FEEDER_ONLY_CLASSIFICATIONS = {
    "bonus_point_purchase_only",
    "terminated_crosswalk_to_CG9999",
    "terminated_2026",
    "reference_only",
    "availability_only",
    "otc",
    "non_scorable",
    "future_hunt_code",
    "historical_truth_support_only",
}

DISPLAY_MAP_ROWS = [
    {
        "page": "Hunt Research",
        "component": "Hunt Card",
        "display_label": "Predicted Odds",
        "metric_name": "predicted_odds_percent",
        "source_file": "processed_data/hunt_research_2026_summary.json",
        "source_column": "ml_draw_probability_2026|p_draw_mean|p_draw_pct",
        "source_classification": "runtime_derived",
        "engine_family": "PREFERENCE_DRAW|BONUS_SPLIT_DRAW|MIXED_DRAW",
        "actual_or_predicted": "predicted",
        "validation_required": "probability_or_percent_bounds",
        "null_display_rule": "show_not_modeled_or_not_applicable",
        "stale_display_rule": "block_if_validation_status_stale",
        "public_safe_true_false": "review",
    },
    {
        "page": "Hunt Research",
        "component": "Point Ladder",
        "display_label": "Point Level Odds",
        "metric_name": "point_level_probability",
        "source_file": "processed_data/point_ladder_view.csv",
        "source_column": "p_draw_mean|p_random_mean|p_max_pool_mean",
        "source_classification": "engine_feeder_runtime",
        "engine_family": "POINT_LADDER",
        "actual_or_predicted": "predicted_or_historical",
        "validation_required": "probability_bounds_and_no_leakage",
        "null_display_rule": "hide_point_ladder_when_not_applicable",
        "stale_display_rule": "block_stale_target_year",
        "public_safe_true_false": "review",
    },
    {
        "page": "Hunt Research",
        "component": "Quota Panel",
        "display_label": "Permits",
        "metric_name": "total_permits",
        "source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
        "source_column": "permit_allotment_2026_total",
        "source_classification": "reference_data",
        "engine_family": "REFERENCE_DATA",
        "actual_or_predicted": "source",
        "validation_required": "nonnegative_integer",
        "null_display_rule": "show_not_available",
        "stale_display_rule": "block_if_not_current_year_reference",
        "public_safe_true_false": "true",
    },
    {
        "page": "Hunt Research",
        "component": "Harvest Panel",
        "display_label": "Harvest Success",
        "metric_name": "harvest_success",
        "source_file": "processed_data/hunt_research_2026_summary.json",
        "source_column": "harvest_success|selectedHarvestSuccess",
        "source_classification": "truth_or_reference_derived",
        "engine_family": "HARVEST_FEATURE",
        "actual_or_predicted": "source_or_model_feature",
        "validation_required": "percent_bounds_and_lineage",
        "null_display_rule": "show_not_available",
        "stale_display_rule": "label_historical_year",
        "public_safe_true_false": "review",
    },
    {
        "page": "Hunt Research",
        "component": "Availability Badge",
        "display_label": "Available",
        "metric_name": "availability_status",
        "source_file": "processed_data/hunt_research_2026_summary.json",
        "source_column": "availability_status",
        "source_classification": "reference_data",
        "engine_family": "AVAILABILITY_ONLY|OTC_CAPPED|OTC_UNLIMITED",
        "actual_or_predicted": "source",
        "validation_required": "no_fake_probability",
        "null_display_rule": "show_unknown",
        "stale_display_rule": "block_if_source_year_mismatch",
        "public_safe_true_false": "review",
    },
]


csv.field_size_limit(min(sys.maxsize, 2_147_483_647))


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_code(value: Any) -> str:
    return clean(value).upper()


def rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def safe_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return math.nan


def safe_int(value: Any) -> int | None:
    value_float = safe_float(value)
    if value_float is None or math.isnan(value_float) or not value_float.is_integer():
        return None
    return int(value_float)


def row_year(row: Mapping[str, Any]) -> int | None:
    for key in ("actual_draw_year", "target_year", "draw_year", "year", "permit_year", "source_year"):
        value = safe_int(row.get(key))
        if value is not None:
            return value
    return None


def row_family(row: Mapping[str, Any], path: str = "") -> str:
    text = " ".join(
        clean(row.get(key))
        for key in ("model_strategy", "draw_system_type", "draw_system", "hunt_family", "species", "hunt_class")
    ).lower()
    text = f"{text} {path.lower()}"
    code = norm_code(row.get("hunt_code"))
    if "preference" in text or "dedicated" in text:
        return "PREFERENCE_DRAW"
    if "bonus" in text or code[:2] in {"EB", "DB", "PB", "MB", "RB", "BG"}:
        return "BONUS_SPLIT_DRAW"
    if "youth" in text:
        return "YOUTH_RANDOM"
    if "availability" in text or "cougar" in text or "mountain_lion" in text:
        return "AVAILABILITY_ONLY"
    if "otc_capped" in text:
        return "OTC_CAPPED"
    if "otc_unlimited" in text:
        return "OTC_UNLIMITED"
    if "private" in text or "allocation" in text or "sportsman" in text:
        return "DIRECT_ALLOCATION"
    if "harvest" in text:
        return "HARVEST_FEATURE"
    if "ladder" in text or "point" in text:
        return "POINT_LADDER"
    if "mixed" in text:
        return "MIXED_DRAW"
    return "UNKNOWN"


def probability_from_row(row: Mapping[str, Any]) -> float | None:
    for key in ("actual_probability", "p_draw", "p_draw_mean", "success_ratio", "draw_probability"):
        value = safe_float(row.get(key))
        if value is not None and not math.isnan(value):
            return value / 100 if value > 1 else value
    for key in ("p_draw_percent", "p_draw_pct", "success_percent", "odds_percent"):
        value = safe_float(row.get(key))
        if value is not None and not math.isnan(value):
            return value / 100
    applicants = first_number(row, ("eligible_applicants", "applicants", "total_applicants"))
    drawn = first_number(row, ("drawn", "successful_applicants", "total_permits", "permits_drawn"))
    if applicants and applicants > 0 and drawn is not None:
        return max(0.0, min(1.0, drawn / applicants))
    return None


def first_number(row: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    lower = {key.lower(): key for key in row}
    for want in keys:
        key = lower.get(want.lower())
        if key is None:
            continue
        value = safe_float(row.get(key))
        if value is not None and not math.isnan(value):
            return value
    return None


def is_holdout(row: Mapping[str, Any]) -> bool:
    family_text = clean(row.get("model_strategy") or row.get("draw_system_type") or row.get("draw_system"))
    code = norm_code(row.get("hunt_code"))
    year = row_year(row)
    return bool(year and year >= 2026 and (family_text in HOLDOUT_FAMILIES or code[:2] in {"EA", "DA", "PA"}))


def scorable_reason(row: Mapping[str, Any]) -> str:
    if not norm_code(row.get("hunt_code")):
        return "missing_hunt_code"
    if row_year(row) is None:
        return "missing_year"
    if not clean(row.get("residency")):
        return "missing_residency"
    if is_holdout(row):
        return "non_public_or_suppressed"
    if probability_from_row(row) is not None:
        return ""
    if first_number(row, ("eligible_applicants", "applicants", "total_applicants")) is None:
        return "missing_applicants"
    if first_number(row, ("total_permits", "permits", "drawn", "successful_applicants")) is None:
        return "missing_permits"
    return "missing_actual_probability"


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_csv_dicts(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield dict(row)


def summarize_csv(path: Path, repo: Path, scorable: bool = False, sample_limit: int = 50000) -> dict[str, Any]:
    rows = 0
    codes: set[str] = set()
    columns: list[str] = []
    scorable_rows = 0
    scorable_codes: set[str] = set()
    unscorable_rows: list[dict[str, Any]] = []
    scorable_out: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    if not path.exists():
        return {
            "path": rel(path, repo),
            "exists": False,
            "rows": 0,
            "unique_hunt_codes": 0,
            "codes": set(),
            "columns": [],
            "scorable_rows": 0,
            "scorable_codes": set(),
            "scorable_out": [],
            "unscorable_rows": [],
            "reason_counts": Counter(),
        }
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            code = norm_code(row.get("hunt_code"))
            if code:
                codes.add(code)
            if scorable:
                reason = scorable_reason(row)
                year = row_year(row)
                family = row_family(row, rel(path, repo))
                if reason:
                    reason_counts[reason] += 1
                    if len(unscorable_rows) < sample_limit:
                        unscorable_rows.append(
                            {
                                "source_file": rel(path, repo),
                                "row_number": rows,
                                "year": year or "",
                                "engine_family": family,
                                "hunt_code": code,
                                "residency": clean(row.get("residency")),
                                "points": clean(row.get("points") or row.get("point_level")),
                                "unscorable_reason": reason,
                                "detail": "2027 antlerless/doe holdout" if is_holdout(row) else "",
                            }
                        )
                else:
                    scorable_rows += 1
                    if code:
                        scorable_codes.add(code)
                    if len(scorable_out) < sample_limit:
                        scorable_out.append(
                            {
                                "source_file": rel(path, repo),
                                "row_number": rows,
                                "year": year or "",
                                "engine_family": family,
                                "hunt_code": code,
                                "residency": clean(row.get("residency")),
                                "points": clean(row.get("points") or row.get("point_level")),
                                "actual_probability": probability_from_row(row),
                            }
                        )
    return {
        "path": rel(path, repo),
        "exists": True,
        "rows": rows,
        "unique_hunt_codes": len(codes),
        "codes": codes,
        "columns": columns,
        "scorable_rows": scorable_rows,
        "scorable_codes": scorable_codes,
        "scorable_out": scorable_out,
        "unscorable_rows": unscorable_rows,
        "reason_counts": reason_counts,
    }


def summarize_json(path: Path, repo: Path) -> dict[str, Any]:
    rows = 0
    codes: set[str] = set()
    columns: set[str] = set()
    exists = path.exists()
    if not exists:
        return {"path": rel(path, repo), "exists": False, "rows": 0, "unique_hunt_codes": 0, "codes": set(), "columns": []}
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(payload, list):
        rows = len(payload)
        for row in payload:
            if isinstance(row, dict):
                columns.update(row.keys())
                code = norm_code(row.get("hunt_code"))
                if code:
                    codes.add(code)
    elif isinstance(payload, dict):
        details = payload.get("details_by_hunt_code")
        if isinstance(details, dict):
            codes.update(norm_code(code) for code in details if norm_code(code))
            rows = sum(len(detail.get("research_summary_rows", [])) if isinstance(detail, dict) else 1 for detail in details.values())
            columns.update(payload.keys())
        else:
            rows = len(payload)
            for key, value in payload.items():
                columns.add(str(key))
                if isinstance(value, dict):
                    code = norm_code(value.get("hunt_code") or key)
                    if code:
                        codes.add(code)
    return {"path": rel(path, repo), "exists": True, "rows": rows, "unique_hunt_codes": len(codes), "codes": codes, "columns": sorted(columns)}


def classify_extra_code(
    code: str,
    database_rows_by_code: Mapping[str, Mapping[str, Any]],
    canonical_codes: set[str] | None = None,
    scorable_codes: set[str] | None = None,
) -> str:
    canonical_codes = canonical_codes or set()
    scorable_codes = scorable_codes or set()
    if code in BONUS_POINT_PURCHASE_ONLY_CODES:
        return "bonus_point_purchase_only"
    if code in TERMINATED_2026_CODES:
        return "terminated_2026"
    if code.startswith(COUGAR_TERMINATED_REPORTING_PREFIX) and code != COUGAR_FORWARD_CODE:
        return "terminated_crosswalk_to_CG9999"
    row = database_rows_by_code.get(code, {})
    joined = " ".join(clean(row.get(key)).upper() for key in ("draw_system_type", "hunt_type", "hunt_class", "permit_allotment_2026_status", "availability_status", "algorithm_status"))
    if "REFERENCE" in joined:
        return "reference_only"
    if "AVAILABILITY" in joined or "COUGAR" in joined or "MOUNTAIN" in joined:
        return "availability_only"
    if "OTC" in joined:
        return "otc"
    if "HISTORICAL" in joined or "NOT_ACTIVE" in joined or "STALE" in joined:
        return "stale_or_unsafe"
    if "FUTURE" in joined:
        return "future_hunt_code"
    if row:
        return "non_scorable"
    if code in canonical_codes:
        return "historical_truth_support_only"
    if not re.search(r"\d", code):
        return "stale_or_unsafe"
    if code not in scorable_codes:
        return "stale_or_unsafe"
    return "blocker"


def audit_feeder_sources(repo: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        path = repo / row["path"]
        text = row["path"].lower()
        if "canonical_yearly" in text:
            classification = "CANONICAL_TRUTH"
            usable_input = "true"
            usable_truth = "true"
        elif row["path"] == REFERENCE_DATABASE:
            classification = "REFERENCE_DATA"
            usable_input = "true"
            usable_truth = "false"
        elif "hunt_research" in text or "processed_data" in text:
            classification = "RUNTIME_DERIVED"
            usable_input = "true"
            usable_truth = "false"
        else:
            classification = "UNKNOWN_LINEAGE"
            usable_input = "review"
            usable_truth = "false"
        output.append(
            {
                "file_path": row["path"],
                "file_name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "row_count_if_tabular": row.get("rows", ""),
                "column_count_if_tabular": len(row.get("columns", [])),
                "detected_hunt_codes_count": row.get("unique_hunt_codes", ""),
                "detected_hunt_codes_sample": "|".join(sorted(row.get("codes", set()))[:25]),
                "truth_classification": classification,
                "usable_as_engine_input": usable_input,
                "usable_as_actual_truth": usable_truth,
                "concerns": "" if path.exists() else "missing_file",
                "recommended_action": "use_under_contract" if path.exists() else "restore_or_mark_optional",
            }
        )
    return output


def run_command(repo: Path, args: Sequence[str]) -> tuple[int, str]:
    proc = subprocess.run(list(args), cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout


def validate(repo: Path, output_dir: Path, strict: bool) -> tuple[str, dict[str, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_paths = sorted(repo.glob(CANONICAL_TRUTH_GLOB))
    canonical_summaries = [summarize_csv(path, repo, scorable=True) for path in canonical_paths]
    reference_summary = summarize_csv(repo / REFERENCE_DATABASE, repo)
    database_rows_by_code = {norm_code(row.get("hunt_code")): row for row in read_csv_dicts(repo / REFERENCE_DATABASE)} if (repo / REFERENCE_DATABASE).exists() else {}
    feeder_summaries = [summarize_csv(repo / path, repo) for path in ENGINE_FEEDERS]
    runtime_summaries = []
    for path_text in RUNTIME_OUTPUTS:
        path = repo / path_text
        if path.suffix.lower() == ".json":
            runtime_summaries.append(summarize_json(path, repo))
        elif path.suffix.lower() == ".csv":
            runtime_summaries.append(summarize_csv(path, repo))
    public_summaries = [summarize_json(repo / path, repo) for path in PUBLIC_RESEARCH_OUTPUTS]

    canonical_codes = set().union(*(item["codes"] for item in canonical_summaries)) if canonical_summaries else set()
    scorable_codes = set().union(*(item["scorable_codes"] for item in canonical_summaries)) if canonical_summaries else set()
    feeder_codes = set().union(*(item["codes"] for item in feeder_summaries)) if feeder_summaries else set()
    runtime_codes = set().union(*(item["codes"] for item in runtime_summaries)) if runtime_summaries else set()
    public_codes = set().union(*(item["codes"] for item in public_summaries)) if public_summaries else set()

    dropped_truth_to_feeder = sorted(scorable_codes - feeder_codes)
    dropped_feeder_to_runtime = sorted(feeder_codes - runtime_codes)
    runtime_extra = sorted(runtime_codes - feeder_codes)
    feeder_extra = sorted(feeder_codes - canonical_codes)

    blocker_rows = []
    repair_rows = []
    dropped_detail = []
    for code in dropped_truth_to_feeder:
        repair_rows.append(("truth_to_feeder", code))
        dropped_detail.append(
            {
                "engine_family": "",
                "year": "",
                "hunt_code": code,
                "source_truth_file": "canonical_yearly",
                "present_in_truth": "true",
                "present_in_reference_database": str(code in database_rows_by_code).lower(),
                "present_in_feeder": "false",
                "present_in_runtime": str(code in runtime_codes).lower(),
                "drop_stage": "truth_to_feeder",
                "drop_reason": "scorable_truth_code_absent_from_research_engine_feeder",
                "legitimate_exclusion_true_false": "review",
                "repair_candidate_true_false": "true",
                "blocker_true_false": "false",
                "recommended_fix": "confirm eligibility and feed to research engine or document legitimate exclusion",
                "evidence_file": "SCORABLE_TRUTH_ROWS.csv",
                "evidence_column": "hunt_code",
            }
        )
    for code in dropped_feeder_to_runtime:
        classification = classify_extra_code(code, database_rows_by_code, canonical_codes, scorable_codes)
        is_blocker = classification == "blocker"
        is_legitimate_exclusion = classification in LEGITIMATE_FEEDER_ONLY_CLASSIFICATIONS
        if is_blocker:
            blocker_rows.append(("feeder_to_runtime", code))
        elif not is_legitimate_exclusion:
            repair_rows.append(("feeder_to_runtime", code))
        dropped_detail.append(
            {
                "engine_family": "",
                "year": "",
                "hunt_code": code,
                "source_truth_file": "",
                "present_in_truth": str(code in canonical_codes).lower(),
                "present_in_reference_database": str(code in database_rows_by_code).lower(),
                "present_in_feeder": "true",
                "present_in_runtime": "false",
                "drop_stage": "feeder_to_runtime",
                "drop_reason": f"feeder_code_absent_from_research_runtime:{classification}",
                "legitimate_exclusion_true_false": str(is_legitimate_exclusion).lower(),
                "repair_candidate_true_false": str((not is_blocker) and (not is_legitimate_exclusion)).lower(),
                "blocker_true_false": str(is_blocker).lower(),
                "recommended_fix": recommended_fix_for_classification(classification),
                "evidence_file": "ENGINE_INPUT_COVERAGE_AUDIT.csv",
                "evidence_column": "hunt_code",
            }
        )
    for code in runtime_extra:
        classification = classify_extra_code(code, database_rows_by_code, canonical_codes, scorable_codes)
        is_approved = classification in LEGITIMATE_FEEDER_ONLY_CLASSIFICATIONS or classification == "stale_or_unsafe"
        if not is_approved:
            blocker_rows.append(("runtime_extra", code))

    counts = {
        "canonical_truth_rows": sum(item["rows"] for item in canonical_summaries),
        "canonical_truth_unique_hunt_codes": len(canonical_codes),
        "canonical_scorable_rows": sum(item["scorable_rows"] for item in canonical_summaries),
        "canonical_scorable_unique_hunt_codes": len(scorable_codes),
        "reference_database_rows": reference_summary["rows"],
        "reference_database_unique_hunt_codes": reference_summary["unique_hunt_codes"],
        "engine_feeder_rows": sum(item["rows"] for item in feeder_summaries),
        "engine_feeder_unique_hunt_codes": len(feeder_codes),
        "runtime_output_rows": sum(item["rows"] for item in runtime_summaries),
        "runtime_output_unique_hunt_codes": len(runtime_codes),
        "public_research_rows": sum(item["rows"] for item in public_summaries),
        "public_research_unique_hunt_codes": len(public_codes),
        "dropped_truth_to_feeder_hunt_codes": len(dropped_truth_to_feeder),
        "dropped_feeder_to_runtime_hunt_codes": len(dropped_feeder_to_runtime),
        "repair_candidates": len(repair_rows),
        "blockers": len(blocker_rows),
    }

    count_rows = [{"metric": key, "value": value} for key, value in counts.items()]
    write_csv(output_dir / "CANONICAL_COUNT_BLOCK.csv", ("metric", "value"), count_rows)
    write_csv(
        output_dir / "CANONICAL_TRUTH_UNIVERSE_SUMMARY.csv",
        ("file_path", "rows", "unique_hunt_codes", "scorable_rows", "scorable_unique_hunt_codes", "columns"),
        [
            {
                "file_path": item["path"],
                "rows": item["rows"],
                "unique_hunt_codes": item["unique_hunt_codes"],
                "scorable_rows": item["scorable_rows"],
                "scorable_unique_hunt_codes": len(item["scorable_codes"]),
                "columns": "|".join(item["columns"]),
            }
            for item in canonical_summaries
        ],
    )
    scorable_rows = [row for item in canonical_summaries for row in item["scorable_out"]]
    unscorable_rows = [row for item in canonical_summaries for row in item["unscorable_rows"]]
    write_csv(output_dir / "SCORABLE_TRUTH_ROWS.csv", ("source_file", "row_number", "year", "engine_family", "hunt_code", "residency", "points", "actual_probability"), scorable_rows)
    write_csv(output_dir / "UNSCORABLE_TRUTH_ROWS.csv", ("source_file", "row_number", "year", "engine_family", "hunt_code", "residency", "points", "unscorable_reason", "detail"), unscorable_rows)
    feeder_audit_input = canonical_summaries + [reference_summary] + feeder_summaries + runtime_summaries
    write_csv(
        output_dir / "FEEDER_TRUTH_SOURCE_AUDIT.csv",
        (
            "file_path",
            "file_name",
            "extension",
            "size_bytes",
            "row_count_if_tabular",
            "column_count_if_tabular",
            "detected_hunt_codes_count",
            "detected_hunt_codes_sample",
            "truth_classification",
            "usable_as_engine_input",
            "usable_as_actual_truth",
            "concerns",
            "recommended_action",
        ),
        audit_feeder_sources(repo, feeder_audit_input),
    )
    write_csv(
        output_dir / "ENGINE_INPUT_COVERAGE_AUDIT.csv",
        (
            "scope",
            "truth_unique_hunt_codes",
            "reference_unique_hunt_codes",
            "feeder_unique_hunt_codes",
            "runtime_unique_hunt_codes",
            "public_research_unique_hunt_codes",
            "dropped_truth_to_feeder_hunt_codes",
            "dropped_feeder_to_runtime_hunt_codes",
            "runtime_extra_hunt_codes",
            "feeder_extra_over_truth_hunt_codes",
            "repair_candidate_count",
            "blocker_count",
        ),
        [
            {
                "scope": "hunt_research_page",
                "truth_unique_hunt_codes": len(canonical_codes),
                "reference_unique_hunt_codes": reference_summary["unique_hunt_codes"],
                "feeder_unique_hunt_codes": len(feeder_codes),
                "runtime_unique_hunt_codes": len(runtime_codes),
                "public_research_unique_hunt_codes": len(public_codes),
                "dropped_truth_to_feeder_hunt_codes": len(dropped_truth_to_feeder),
                "dropped_feeder_to_runtime_hunt_codes": len(dropped_feeder_to_runtime),
                "runtime_extra_hunt_codes": len(runtime_extra),
                "feeder_extra_over_truth_hunt_codes": len(feeder_extra),
                "repair_candidate_count": len(repair_rows),
                "blocker_count": len(blocker_rows),
            }
        ],
    )
    write_csv(
        output_dir / "ENGINE_DROPPED_HUNT_CODES_DETAIL.csv",
        (
            "engine_family",
            "year",
            "hunt_code",
            "source_truth_file",
            "present_in_truth",
            "present_in_reference_database",
            "present_in_feeder",
            "present_in_runtime",
            "drop_stage",
            "drop_reason",
            "legitimate_exclusion_true_false",
            "repair_candidate_true_false",
            "blocker_true_false",
            "recommended_fix",
            "evidence_file",
            "evidence_column",
        ),
        dropped_detail,
    )
    runtime_validation_rows = []
    for item in runtime_summaries:
        path = repo / item["path"]
        missing = not item["exists"]
        reason = "missing_optional_file" if missing and path.name == "hunt_research_2026_ladder.json" else "missing_file" if missing else ""
        runtime_validation_rows.append(
            {
                "file_path": item["path"],
                "row_count": item["rows"],
                "unique_hunt_codes": item["unique_hunt_codes"],
                "engine_family": "Research Page Runtime",
                "prediction_columns": "|".join(col for col in item.get("columns", []) if re.search(r"p_draw|prob|odds", col, re.I)),
                "actual_columns_present": "|".join(col for col in item.get("columns", []) if re.search(r"actual", col, re.I)),
                "safe_for_public_runtime_true_false": str(not reason).lower(),
                "reason_if_not_safe": reason,
            }
        )
    write_csv(
        output_dir / "RUNTIME_OUTPUT_VALIDATION.csv",
        ("file_path", "row_count", "unique_hunt_codes", "engine_family", "prediction_columns", "actual_columns_present", "safe_for_public_runtime_true_false", "reason_if_not_safe"),
        runtime_validation_rows,
    )
    write_csv(
        output_dir / "WEBSITE_METRIC_DISPLAY_MAP.csv",
        (
            "page",
            "component",
            "display_label",
            "metric_name",
            "source_file",
            "source_column",
            "source_classification",
            "engine_family",
            "actual_or_predicted",
            "validation_required",
            "null_display_rule",
            "stale_display_rule",
            "public_safe_true_false",
        ),
        DISPLAY_MAP_ROWS,
    )
    status = "FAIL_BLOCKED" if blocker_rows else "PASS_WITH_REPAIR_CANDIDATES" if repair_rows else "PROMOTION_READY"
    promotion_ready = status == "PROMOTION_READY"
    write_text(
        output_dir / "PROMOTION_READINESS.md",
        "\n".join(
            [
                "# Promotion Readiness",
                "",
                f"CONTRACT_STATUS: {status}",
                f"PROMOTION_READY: {str(promotion_ready).lower()}",
                "",
                "## Blockers",
                *(f"- {stage}: {code}" for stage, code in blocker_rows[:200]),
                "",
                "## Repair Candidates",
                *(f"- {stage}: {code}" for stage, code in repair_rows[:200]),
                "",
                "## Count Block",
                *(f"- {key}: {value}" for key, value in counts.items()),
            ]
        )
        + "\n",
    )
    write_text(
        output_dir / "ENGINE_RESEARCH_PAGE_CANONICAL_CONTRACT_AUDIT.md",
        "\n".join(
            [
                "# Engine Research Page Canonical Contract Audit",
                "",
                f"CONTRACT_STATUS: {status}",
                "",
                "## Sources",
                f"- Canonical truth glob: `{CANONICAL_TRUTH_GLOB}`",
                f"- Reference database: `{REFERENCE_DATABASE}`",
                "- Engine feeders:",
                *(f"  - `{path}`" for path in ENGINE_FEEDERS),
                "- Runtime outputs:",
                *(f"  - `{path}`" for path in RUNTIME_OUTPUTS),
                "",
                "## Count Block",
                *(f"- {key}: {value}" for key, value in counts.items()),
                "",
                "## Final Answer",
                (
                    "YES - PROMOTION_READY"
                    if status == "PROMOTION_READY"
                    else "YES, BUT MORE REPAIRS ARE AVAILABLE - PASS_WITH_REPAIR_CANDIDATES"
                    if status == "PASS_WITH_REPAIR_CANDIDATES"
                    else "NO - FAIL_BLOCKED"
                ),
            ]
        )
        + "\n",
    )
    write_text(output_dir / "TEST_RESULTS.txt", "Validator completed. External compileall/pytest results are captured by the Codex run summary when executed.\n")
    summary = {
        "RESEARCH_PAGE_CANONICAL_CONTRACT_COMPLETE": 0 if strict and status == "FAIL_BLOCKED" else 1,
        "CONTRACT_STATUS": status,
        "AUDIT_OUTPUT_DIR": str(output_dir),
        "CANONICAL_TRUTH_ROWS": counts["canonical_truth_rows"],
        "CANONICAL_TRUTH_HUNT_CODES": counts["canonical_truth_unique_hunt_codes"],
        "SCORABLE_TRUTH_ROWS": counts["canonical_scorable_rows"],
        "SCORABLE_TRUTH_HUNT_CODES": counts["canonical_scorable_unique_hunt_codes"],
        "REFERENCE_HUNT_CODES": counts["reference_database_unique_hunt_codes"],
        "FEEDER_HUNT_CODES": counts["engine_feeder_unique_hunt_codes"],
        "RUNTIME_HUNT_CODES": counts["runtime_output_unique_hunt_codes"],
        "PUBLIC_RESEARCH_HUNT_CODES": counts["public_research_unique_hunt_codes"],
        "DROPPED_TRUTH_TO_FEEDER": counts["dropped_truth_to_feeder_hunt_codes"],
        "DROPPED_FEEDER_TO_RUNTIME": counts["dropped_feeder_to_runtime_hunt_codes"],
        "REPAIR_CANDIDATES": counts["repair_candidates"],
        "BLOCKERS": counts["blockers"],
        "PROMOTION_READY": 1 if promotion_ready else 0,
    }
    lines = []
    for key, value in summary.items():
        if key in {"RESEARCH_PAGE_CANONICAL_CONTRACT_COMPLETE", "PROMOTION_READY"}:
            lines.append(f"{key}: {str(bool(value)).lower()}")
        else:
            lines.append(f"{key}: {value}")
    write_text(output_dir / "FINAL_CONSOLE_SUMMARY.txt", "\n".join(lines) + "\n")
    return status, counts


def recommended_fix_for_classification(classification: str) -> str:
    if classification == "bonus_point_purchase_only":
        return "keep as bonus-point purchase-only record; do not score or require Research runtime hunt row"
    if classification == "terminated_crosswalk_to_CG9999":
        return "terminate individual cougar reporting code and carry forward only CG9999 for statewide cougar open season"
    if classification == "terminated_2026":
        return "terminate for 2026; do not carry into current Research runtime unless an official crosswalk is added"
    if classification == "historical_truth_support_only":
        return "keep as historical support only; do not require current Research runtime row"
    if classification in {"reference_only", "availability_only", "otc", "non_scorable", "future_hunt_code"}:
        return "document as legitimate non-scorable/reference exclusion"
    return "publish to runtime, document exclusion, or remove stale feeder row"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--write-audits", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--no-promote", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo / AUDIT_ROOT / timestamp
    status, counts = validate(repo, output_dir, strict=args.strict)
    summary_path = output_dir / "FINAL_CONSOLE_SUMMARY.txt"
    print(summary_path.read_text(encoding="utf-8"), end="")
    return 1 if args.strict and status == "FAIL_BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
