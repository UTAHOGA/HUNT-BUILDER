#!/usr/bin/env python3
"""Run a blind 2025->2026 prediction backtest.

The prediction phase is intentionally separated from the scoring phase:

1. Build a temporary draw-results truth file containing only scorable rows with
   actual_draw_year <= 2025 and a legacy `year` alias for the engine.
2. Run the existing 2026 prediction materializer against that filtered truth.
3. Hash/freeze the prediction output.
4. Only after the freeze, read 2026 actual scorable truth and score the run.

This script writes audit artifacts only. It does not mutate production feeds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


REPO = Path(__file__).resolve().parents[1]
SOURCE_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
ACTUAL_2026_CANDIDATES = [
    REPO / "outputs" / "2026 scorable draw results.csv",
    REPO / "outputs" / "2026" / "2026 scorable draw results.csv",
]
EXTERNAL_ACTUAL_2026 = next((path for path in ACTUAL_2026_CANDIDATES if path.exists()), None)
RUNTIME_DRAFT_DIR = REPO / "data_model" / "runtime_drafts"
DEFAULT_OUT_ROOT = REPO / "audits" / "prediction_blind_backtests" / "2025_to_2026"
BLACK_BEAR_CROSSWALK_2026 = REPO / "data_truth" / "crosswalk_truth" / "normalized" / "black_bear_BR_2024_2025_2026_crosswalk.csv"
CURRENT_DATABASE_2026 = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
# Use every available pre-target official draw year.  The blind filter still
# excludes 2026 actuals until the forecast is frozen.
HISTORY_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
CWMU_TURKEY_CODES = {"TK1018", "TK1021"}
SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "sportsman_total_draw_result",
    "sportsman_total",
}
EXCLUDED_ACTUAL_DRAW_SYSTEM_TYPES = {
    "RANDOM_ONLY_TARGET",
    "OTC_OR_REMAINING_TARGET",
    "YOUTH_OTC_OR_AVAILABILITY",
    "YOUTH_GENERAL_ANY_BULL_ELK",
    "YOUTH_DRAW_ONLY_ELK",
}
LEAN_TRUTH_COLUMNS = [
    "year",
    "actual_draw_year",
    "model_target_year",
    "source_scope",
    "source_file",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "draw_design",
    "hunt_class",
    "draw_pool",
    "source_is_youth",
    "residency",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
    "record_type",
]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_code(value: Any) -> str:
    return clean(value).upper()


def parse_int(value: Any) -> int | None:
    text = clean(value).replace(",", "")
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def probability_from_prediction(row: Mapping[str, Any]) -> float | None:
    for field in ("p_draw", "p_draw_mean", "p_sportsman_draw", "p_preference_draw"):
        value = parse_float(row.get(field))
        if value is not None:
            if value > 1.0:
                value = value / 100.0
            return min(max(value, 0.0), 1.0)
    pct = parse_float(row.get("p_draw_pct")) or parse_float(row.get("display_odds_pct"))
    if pct is not None:
        return min(max(pct / 100.0, 0.0), 1.0)
    return None


def probability_from_actual(row: Mapping[str, Any]) -> float | None:
    for field in ("p_draw", "success_ratio"):
        value = parse_float(row.get(field))
        if value is not None:
            if value > 1.0:
                value = value / 100.0
            return min(max(value, 0.0), 1.0)
    applicants = parse_float(row.get("eligible_applicants"))
    drawn = parse_float(row.get("total_permits"))
    if applicants and applicants > 0 and drawn is not None:
        return min(max(drawn / applicants, 0.0), 1.0)
    pct = parse_float(row.get("p_draw_percent"))
    if pct is not None:
        return min(max(pct / 100.0, 0.0), 1.0)
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(tmp, path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def draw_year(row: Mapping[str, Any]) -> int | None:
    return parse_int(row.get("actual_draw_year")) or parse_int(row.get("year"))


def is_scorable_history_row(row: Mapping[str, Any]) -> bool:
    year = draw_year(row)
    if year is None or year > 2025:
        return False
    record_type = clean(row.get("record_type")).lower()
    if record_type and record_type not in SCORABLE_RECORD_TYPES:
        return False
    if not norm_code(row.get("hunt_code")):
        return False
    return probability_from_actual(row) is not None or parse_int(row.get("eligible_applicants")) is not None


def build_or_resolve_actual_2026(out_dir: Path) -> Path:
    """Resolve official 2026 scoring truth after the prediction is frozen."""

    if EXTERNAL_ACTUAL_2026 is not None:
        return EXTERNAL_ACTUAL_2026

    _, rows = read_csv(SOURCE_LONG)
    actual_rows: list[dict[str, Any]] = []
    for source_row in rows:
        if draw_year(source_row) != 2026:
            continue
        for row in expanded_engine_rows(source_row):
            record_type = clean(row.get("record_type")).lower()
            if record_type and record_type not in SCORABLE_RECORD_TYPES:
                continue
            if not norm_code(row.get("hunt_code")) or probability_from_actual(row) is None:
                continue
            item = {field: row.get(field, "") for field in LEAN_TRUTH_COLUMNS}
            item["year"] = "2026"
            item["actual_draw_year"] = "2026"
            actual_rows.append(item)

    if not actual_rows:
        raise RuntimeError("Official draw_results_long.csv contains no scorable 2026 actual truth rows.")

    output = out_dir / "comparison_phase" / "official_2026_scorable_truth.csv"
    write_csv(output, LEAN_TRUTH_COLUMNS, actual_rows)
    return output


def expanded_engine_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return engine-ready rows, exploding collapsed resident/nonresident rows."""
    if clean(row.get("residency")):
        out = dict(row)
        residency = clean(out.get("residency")).lower().replace("-", "").replace(" ", "")
        if not clean(out.get("metric_scope")):
            if residency in {"resident", "res", "r"}:
                out["metric_scope"] = "resident"
            elif residency in {"nonresident", "nonres", "nr"}:
                out["metric_scope"] = "nonresident"
            else:
                out["metric_scope"] = "total"
        return [out]

    expanded: list[dict[str, Any]] = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        has_data = any(
            clean(row.get(f"{prefix}_{field}")) != ""
            for field in (
                "eligible_applicants",
                "bonus_permits",
                "regular_permits",
                "total_permits",
                "success_ratio",
                "p_draw",
                "p_draw_percent",
            )
        )
        if not has_data:
            continue
        out = dict(row)
        out["residency"] = residency
        out["eligible_applicants"] = clean(row.get(f"{prefix}_eligible_applicants"))
        out["bonus_permits"] = clean(row.get(f"{prefix}_bonus_permits"))
        out["regular_permits"] = clean(row.get(f"{prefix}_regular_permits"))
        out["total_permits"] = clean(row.get(f"{prefix}_total_permits"))
        out["success_ratio"] = clean(row.get(f"{prefix}_success_ratio"))
        out["p_draw"] = clean(row.get(f"{prefix}_p_draw"))
        out["p_draw_percent"] = clean(row.get(f"{prefix}_p_draw_percent"))
        out["metric_scope"] = prefix
        expanded.append(out)
    if expanded:
        return expanded
    out = dict(row)
    out["metric_scope"] = clean(out.get("metric_scope")) or "total"
    return [out]


def build_filtered_truth(out_dir: Path) -> dict[str, Any]:
    headers, rows = read_csv(SOURCE_LONG)
    output_headers = [field for field in LEAN_TRUTH_COLUMNS if field in set(headers) or field in {"year", "draw_pool", "hunt_class"}]

    kept: list[dict[str, str]] = []
    input_year_counts: Counter[int] = Counter()
    kept_year_counts: Counter[int] = Counter()
    excluded_type_counts: Counter[str] = Counter()
    expanded_input_rows = 0
    for row in rows:
        year = draw_year(row)
        if year is not None:
            input_year_counts[year] += 1
        expanded_rows = expanded_engine_rows(row)
        expanded_input_rows += len(expanded_rows)
        kept_any = False
        for expanded in expanded_rows:
            if not is_scorable_history_row(expanded):
                continue
            out = dict(expanded)
            out["year"] = str(year)
            out.setdefault("draw_pool", clean(expanded.get("draw_pool")) or "standard")
            if clean(out.get("draw_pool")) == "":
                out["draw_pool"] = "standard"
            # Do not force blank hunt_class to "Public" here. Some family
            # engines, especially public CWMU, use blank vs CWMU/private as
            # a meaningful source signal.
            out.setdefault("hunt_class", clean(expanded.get("hunt_class")))
            kept.append({field: out.get(field, "") for field in output_headers})
            kept_year_counts[year or 0] += 1
            kept_any = True
        if not kept_any and year is not None and year <= 2025:
            excluded_type_counts[clean(row.get("record_type")).lower() or "(blank)"] += 1

    path = out_dir / "inputs" / "draw_results_long_scorable_through_2025.csv"
    write_csv(path, output_headers, kept)
    return {
        "path": path,
        "input_rows": len(rows),
        "expanded_input_rows": expanded_input_rows,
        "kept_rows": len(kept),
        "input_year_counts": dict(sorted(input_year_counts.items())),
        "kept_year_counts": dict(sorted(kept_year_counts.items())),
        "excluded_pre_2026_record_type_counts": dict(excluded_type_counts.most_common()),
        "sha256": sha256(path),
    }


def prepare_runtime_inputs(out_dir: Path) -> dict[str, Any]:
    runtime_dir = out_dir / "inputs" / "runtime_drafts_2026_frozen_copy"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    files = [
        "predictive_bonus_engine_2026.predictions.csv",
        "predictive_bonus_engine_2026.materialized.csv",
        "predictive_bonus_engine_2026.audit.csv",
    ]
    copied: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for name in files:
        src = RUNTIME_DRAFT_DIR / name
        dst = runtime_dir / name
        if not src.exists():
            raise FileNotFoundError(f"Missing runtime draft input: {src}")
        shutil.copy2(src, dst)
        copied[name] = rel(dst)
        hashes[name] = sha256(dst)
    return {"path": runtime_dir, "files": copied, "sha256": hashes}


def rebuild_main_bonus_frozen_inputs(filtered_truth_path: Path, runtime_dir: Path) -> dict[str, Any]:
    """Rebuild the main OIL/LE/PLE bonus draft inside the blind sandbox.

    The production build script normally reads data_model/runtime_drafts. For a
    blind audit, patch its input path to the through-2025 filtered truth file and
    write outputs only into the audit runtime copy.
    """
    script_path = REPO / "scripts" / "build_predictive_bonus_engine_v1.py"
    spec = importlib.util.spec_from_file_location("blind_build_predictive_bonus_engine_v1", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original_input_draw = module.INPUT_DRAW_V2
    original_argv = sys.argv[:]
    module.INPUT_DRAW_V2 = filtered_truth_path
    try:
        sys.argv = [
            str(script_path),
            "--prediction-year",
            "2026",
            "--out-dir",
            str(runtime_dir),
        ]
        exit_code = module.main()
        if exit_code not in (0, None):
            raise RuntimeError(f"Blind main bonus rebuild failed with exit code {exit_code}")
    finally:
        module.INPUT_DRAW_V2 = original_input_draw
        sys.argv = original_argv

    rebuilt_files = [
        runtime_dir / "predictive_bonus_engine_2026.predictions.csv",
        runtime_dir / "predictive_bonus_engine_2026.materialized.csv",
        runtime_dir / "predictive_bonus_engine_2026.audit.csv",
    ]
    return {
        "rebuilt": True,
        "script": rel(script_path),
        "input_truth": rel(filtered_truth_path),
        "files": {path.name: rel(path) for path in rebuilt_files},
        "sha256": {path.name: sha256(path) for path in rebuilt_files if path.exists()},
    }


def run_prediction_phase(out_dir: Path, filtered_truth_path: Path, runtime_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(REPO))
    from engine.utah_bonus_predictive import materialize as materialize_mod  # pylint: disable=import-outside-toplevel

    prediction_dir = out_dir / "prediction_phase"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    # The materializer only copies this runtime file into its manifest output.
    # Use the filtered no-leak truth instead of duplicating the huge runtime draft.
    shutil.copy2(filtered_truth_path, runtime_dir / "draw_reality_engine_v2.csv")
    original_truth_path = materialize_mod.TRUTH_PATH
    original_runtime_dir = materialize_mod.RUNTIME_DRAFT_DIR
    materialize_mod.TRUTH_PATH = filtered_truth_path
    materialize_mod.RUNTIME_DRAFT_DIR = runtime_dir
    try:
        artifacts = materialize_mod.materialize_outputs(
            output_dir=prediction_dir,
            forecast_year=2026,
            history_years=HISTORY_YEARS,
            command_used=(
                "blind audit: 2025_to_2026 prediction phase; "
                "TRUTH_PATH=draw_results_long_scorable_through_2025.csv; "
                "run_upstream=False"
            ),
            run_upstream=False,
        )
    finally:
        materialize_mod.TRUTH_PATH = original_truth_path
        materialize_mod.RUNTIME_DRAFT_DIR = original_runtime_dir

    # This is the materializer's unified predictive surface.  It includes the
    # separate bear, turkey, youth, sportsman, and main big-game engines.  The
    # main-bonus-only file is a feeder and cannot certify full engine coverage.
    frozen_prediction = prediction_dir / "draw_reality_engine_predictive_v2.csv"
    return {
        "prediction_dir": prediction_dir,
        "artifacts": {key: rel(Path(value)) for key, value in artifacts.items()},
        "frozen_prediction": frozen_prediction,
        "frozen_prediction_sha256": sha256(frozen_prediction),
    }


def classify_actual_row(row: Mapping[str, Any]) -> str:
    from engine.utah_draw_predictive.classifier import classify_draw_system_type  # pylint: disable=import-outside-toplevel

    working = dict(row)
    working.setdefault("draw_pool", "standard")
    working.setdefault("hunt_class", "Public")
    if clean(working.get("draw_pool")) == "":
        working["draw_pool"] = "standard"
    if clean(working.get("hunt_class")) == "":
        working["hunt_class"] = "Public"
    return classify_draw_system_type(working)


def norm_residency(value: Any) -> str:
    lowered = clean(value).lower().replace("-", "").replace(" ", "")
    if lowered in {"res", "resident"}:
        return "Resident"
    if lowered in {"nr", "nonresident"}:
        return "Nonresident"
    return clean(value)


def norm_points(value: Any) -> str:
    parsed = parse_int(value)
    return str(parsed) if parsed is not None else clean(value)


def norm_key_points(value: Any, draw_system_type: str) -> str:
    points = norm_points(value)
    if points == "" and "SPORTSMAN" in clean(draw_system_type).upper():
        return "0"
    return points


def prediction_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    draw_system_type = clean(row.get("draw_system_type")) or "UNKNOWN"
    return (
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        norm_key_points(row.get("points"), draw_system_type),
        draw_system_type,
    )


def actual_key(row: Mapping[str, Any], draw_system_type: str) -> tuple[str, str, str, str]:
    return (
        norm_code(row.get("hunt_code")),
        norm_residency(row.get("residency")),
        norm_key_points(row.get("points"), draw_system_type),
        draw_system_type or "UNKNOWN",
    )


def build_history_code_years() -> dict[str, set[int]]:
    """Index official pre-target history by hunt code only.

    This is intentionally narrow: it uses only <=2025 truth to decide whether a
    2026 unmatched actual row had any code-level history available to the blind
    prediction phase. It does not infer from 2026 outcomes.
    """
    history: dict[str, set[int]] = defaultdict(set)
    _, rows = read_csv(SOURCE_LONG)
    for row in rows:
        year = draw_year(row)
        code = norm_code(row.get("hunt_code"))
        if code and year is not None and year <= 2025:
            history[code].add(year)
    return history


def load_current_only_bear_split_codes() -> set[str]:
    if not BLACK_BEAR_CROSSWALK_2026.exists():
        return set()
    _, rows = read_csv(BLACK_BEAR_CROSSWALK_2026)
    return {
        norm_code(row.get("current_2026_code"))
        for row in rows
        if clean(row.get("mapping_status")) == "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW"
    }


def load_current_database_by_code() -> dict[str, dict[str, str]]:
    """Load the official current Planner identity for scoped disposition checks."""
    if not CURRENT_DATABASE_2026.exists():
        return {}
    _, rows = read_csv(CURRENT_DATABASE_2026)
    return {
        norm_code(row.get("hunt_code")): row
        for row in rows
        if norm_code(row.get("hunt_code"))
    }


def is_current_planner_non_draw_bear(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        clean(row.get(field)).lower()
        for field in ("hunt_type", "hunt_class", "weapon", "draw_design", "draw_pool")
    )
    return "o.t.c" in text or "over the counter" in text or "pursuit" in text or "unlimited" in text


def disposition_for_unmatched_actual(
    row: Mapping[str, Any],
    history_code_years: Mapping[str, set[int]],
    current_only_bear_split_codes: set[str],
    current_database_by_code: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    """Classify unmatched actual rows without using 2026 results as history."""
    code = norm_code(row.get("hunt_code"))
    draw_system_type = clean(row.get("draw_system_type"))
    history_years = sorted(history_code_years.get(code, set()))

    if draw_system_type == "BONUS_CWMU_BIG_GAME" or code in CWMU_TURKEY_CODES:
        return (
            "SOURCE_VERIFIED_NO_PUBLIC_ODDS_CWMU_EXCLUDED",
            "CWMU rows have official draw-result ladders but are intentionally excluded from public probability scoring in the current production rule.",
        )
    if code in current_only_bear_split_codes:
        return (
            "SOURCE_VERIFIED_PREDICTION_GAP_CURRENT_ONLY_BEAR_SPLIT_CHILD",
            "Official bear crosswalk marks this 2026 code as a current split/addition with no prior draw row; resolve with an explicit source/crosswalk route before treating as fully modeled.",
        )
    current_planner_row = current_database_by_code.get(code)
    if draw_system_type == "BEAR_DRAW" and current_planner_row and is_current_planner_non_draw_bear(current_planner_row):
        return (
            "SOURCE_VERIFIED_CURRENT_PLANNER_NON_DRAW_BEAR",
            "The official current DWR Planner identifies this code as an OTC/pursuit or other non-draw bear design, while the time-aligned official draw-result source contains a historic public-draw ladder. This is a source-timing/design transition, not a missing probability-engine key; retain it for dated-snapshot reconciliation rather than scoring it as a forecast failure.",
        )
    if not history_years:
        return (
            "SOURCE_VERIFIED_PREDICTION_GAP_NO_EXACT_HISTORY",
            "No <=2025 exact-code draw history exists in the blind history input; resolve from raw PDF/canonical/crosswalk evidence before promoting as fully modeled.",
        )
    return (
        "UNEXPECTED_ENGINE_OR_KEY_GAP",
        f"Code has <=2025 history years {','.join(str(year) for year in history_years)} but did not join to a frozen prediction key.",
    )


def cleanup_large_temp_truth_files(out_dir: Path, keep_temp_truth: bool) -> dict[str, Any]:
    candidates = [
        out_dir / "inputs" / "draw_results_long_scorable_through_2025.csv",
        out_dir / "inputs" / "runtime_drafts_2026_frozen_copy" / "draw_reality_engine_v2.csv",
        out_dir / "prediction_phase" / "draw_reality_engine_v2.csv",
    ]
    records: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            continue
        record = {
            "path": rel(path),
            "size_bytes": file_size(path),
            "sha256": sha256(path),
            "removed": False,
        }
        if not keep_temp_truth:
            path.unlink()
            record["removed"] = True
        records.append(record)

    summary = {
        "keep_temp_truth": keep_temp_truth,
        "records": records,
        "regeneration_command": "python scripts/run_blind_2025_to_2026_prediction_backtest.py --out-dir <same-out-dir>",
        "reason": "Large copied truth/runtime inputs are hash-locked, regenerable audit intermediates and should not be retained as repo artifacts by default.",
    }
    if records:
        write_json(out_dir / "large_temp_truth_files_removed_after_run.json", summary)
    return summary


def aggregate_prediction_rows(rows: list[dict[str, Any]], key_field: str) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[key_field]].append(row)
    aggregated: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, group in grouped.items():
        probs = [row["probability"] for row in group if row.get("probability") is not None]
        if not probs:
            continue
        first = group[0]
        item = dict(first)
        item["probability"] = sum(probs) / len(probs)
        applicant_counts = [
            value
            for row in group
            if (value := parse_float(row.get("predicted_applicants"))) is not None
        ]
        if applicant_counts:
            item["predicted_applicants"] = sum(applicant_counts) / len(applicant_counts)
            item["predicted_applicants_min"] = min(applicant_counts)
            item["predicted_applicants_max"] = max(applicant_counts)
        for field in ("guaranteed_at_2025", "rollover_anchor_next_point"):
            values = [clean(row.get(field)) for row in group if clean(row.get(field))]
            if values:
                item[field] = values[0]
        item["row_count_aggregated"] = len(group)
        item["probability_min"] = min(probs)
        item["probability_max"] = max(probs)
        aggregated[key] = item
    return aggregated


def aggregate_actual_rows(rows: list[dict[str, Any]], key_field: str) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[key_field]].append(row)
    aggregated: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, group in grouped.items():
        first = dict(group[0])
        applicants = [parse_float(row.get("eligible_applicants")) for row in group]
        permits = [parse_float(row.get("total_permits")) for row in group]
        if all(value is not None for value in applicants) and all(value is not None for value in permits):
            total_applicants = sum(value or 0.0 for value in applicants)
            total_permits = sum(value or 0.0 for value in permits)
            if total_applicants > 0:
                first["probability"] = min(max(total_permits / total_applicants, 0.0), 1.0)
                first["eligible_applicants"] = str(int(total_applicants)) if total_applicants.is_integer() else f"{total_applicants:.6f}"
                first["total_permits"] = str(int(total_permits)) if total_permits.is_integer() else f"{total_permits:.6f}"
            else:
                probs = [row["probability"] for row in group if row.get("probability") is not None]
                if not probs:
                    continue
                first["probability"] = sum(probs) / len(probs)
        else:
            probs = [row["probability"] for row in group if row.get("probability") is not None]
            if not probs:
                continue
            weights = [parse_float(row.get("eligible_applicants")) or 0.0 for row in group]
            total_weight = sum(weights)
            if total_weight > 0:
                first["probability"] = sum(float(row["probability"]) * weight for row, weight in zip(group, weights)) / total_weight
            else:
                first["probability"] = sum(probs) / len(probs)
        first["row_count_aggregated"] = len(group)
        first["probability_min"] = min(row["probability"] for row in group if row.get("probability") is not None)
        first["probability_max"] = max(row["probability"] for row in group if row.get("probability") is not None)
        aggregated[key] = first
    return aggregated


def metric_summary(errors: list[float]) -> dict[str, Any]:
    if not errors:
        return {
            "joined_rows": 0,
            "mae": "",
            "rmse": "",
            "bias": "",
            "median_abs_error": "",
            "p90_abs_error": "",
            "failure_abs_error_gt_0_25": 0,
        }
    abs_errors = sorted(abs(error) for error in errors)
    p90_index = min(len(abs_errors) - 1, math.ceil(len(abs_errors) * 0.9) - 1)
    return {
        "joined_rows": len(errors),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "bias": sum(errors) / len(errors),
        "median_abs_error": median(abs_errors),
        "p90_abs_error": abs_errors[p90_index],
        "failure_abs_error_gt_0_25": sum(1 for error in errors if abs(error) > 0.25),
    }


def applicant_metric_summary(predicted_actual_pairs: list[tuple[float, float]]) -> dict[str, Any]:
    if not predicted_actual_pairs:
        return {
            "rows": 0,
            "mae_applicants": "",
            "rmse_applicants": "",
            "bias_applicants": "",
            "median_absolute_error_applicants": "",
            "weighted_absolute_percentage_error": "",
        }
    errors = [predicted - actual for predicted, actual in predicted_actual_pairs]
    actual_total = sum(actual for _, actual in predicted_actual_pairs)
    return {
        "rows": len(errors),
        "mae_applicants": sum(abs(error) for error in errors) / len(errors),
        "rmse_applicants": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "bias_applicants": sum(errors) / len(errors),
        "median_absolute_error_applicants": median(abs(error) for error in errors),
        "weighted_absolute_percentage_error": (
            sum(abs(error) for error in errors) / actual_total if actual_total > 0 else ""
        ),
    }


def actual_rows_for_year(year: int) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """Load official scorable actual rows for a historical comparison year."""

    _, source_rows = read_csv(SOURCE_LONG)
    rows: list[dict[str, Any]] = []
    for source_row in source_rows:
        if draw_year(source_row) != year:
            continue
        for row in expanded_engine_rows(source_row):
            record_type = clean(row.get("record_type")).lower()
            if record_type and record_type not in SCORABLE_RECORD_TYPES:
                continue
            applicants = parse_float(row.get("eligible_applicants"))
            probability = probability_from_actual(row)
            if applicants is not None and applicants <= 0:
                continue
            if probability is None:
                continue
            draw_system_type = classify_actual_row(row)
            if draw_system_type in EXCLUDED_ACTUAL_DRAW_SYSTEM_TYPES:
                continue
            key = actual_key(row, draw_system_type)
            if not key[0] or key[3] in {"UNKNOWN", "UNKNOWN_TARGET", "OUT_OF_SCOPE_NON_TARGET"}:
                continue
            rows.append(
                {
                    "key": key,
                    "hunt_code": key[0],
                    "residency": key[1],
                    "points": key[2],
                    "draw_system_type": key[3],
                    "species": clean(row.get("species")),
                    "hunt_name": clean(row.get("hunt_name")),
                    "probability": probability,
                    "eligible_applicants": clean(row.get("eligible_applicants")),
                    "total_permits": clean(row.get("total_permits")),
                    "record_type": clean(row.get("record_type")),
                }
            )
    return aggregate_actual_rows(rows, "key")


def just_missed_target_point(prediction: Mapping[str, Any]) -> int | None:
    draw_system_type = clean(prediction.get("draw_system_type"))
    if draw_system_type.startswith("PREFERENCE_"):
        prior_cutoff = parse_int(prediction.get("guaranteed_at_2025"))
        return None if prior_cutoff is None else prior_cutoff + 1
    if draw_system_type.startswith("BONUS_"):
        return parse_int(prediction.get("rollover_anchor_next_point"))
    return None


def compare_to_actual(out_dir: Path, frozen_prediction: Path, actual_2026: Path) -> dict[str, Any]:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    pred_headers, pred_raw = read_csv(frozen_prediction)
    actual_headers, actual_raw = read_csv(actual_2026)

    prediction_rows: list[dict[str, Any]] = []
    prediction_without_probability = 0
    for idx, row in enumerate(pred_raw, start=2):
        probability = probability_from_prediction(row)
        if probability is None:
            prediction_without_probability += 1
            continue
        key = prediction_key(row)
        if not key[0] or key[3] == "UNKNOWN":
            continue
        prediction_rows.append(
            {
                "key": key,
                "prediction_row_number": idx,
                "hunt_code": key[0],
                "residency": key[1],
                "points": key[2],
                "draw_system_type": key[3],
                "species": clean(row.get("species")),
                "hunt_name": clean(row.get("hunt_name")),
                "probability": probability,
                "predicted_applicants": next(
                    (
                        value
                        for field in (
                            "forecast_applicants_at_level",
                            "applicants_at_level",
                            "projected_applicants_2026",
                            "projected_applicants",
                        )
                        if (value := parse_float(row.get(field))) is not None
                    ),
                    None,
                ),
                "guaranteed_at_2025": clean(row.get("guaranteed_at_2025")),
                "rollover_anchor_next_point": clean(row.get("rollover_anchor_next_point")),
                "algorithm_status": clean(row.get("algorithm_status")),
                "model_strategy": clean(row.get("model_strategy")),
            }
        )

    actual_rows: list[dict[str, Any]] = []
    actual_without_probability = 0
    actual_excluded_zero_applicants = 0
    for idx, row in enumerate(actual_raw, start=2):
        probability = probability_from_actual(row)
        applicants = parse_float(row.get("eligible_applicants"))
        if applicants is not None and applicants <= 0:
            actual_excluded_zero_applicants += 1
            continue
        if probability is None:
            actual_without_probability += 1
            continue
        draw_system_type = classify_actual_row(row)
        if draw_system_type in EXCLUDED_ACTUAL_DRAW_SYSTEM_TYPES:
            continue
        key = actual_key(row, draw_system_type)
        if not key[0] or key[3] in {"UNKNOWN", "UNKNOWN_TARGET", "OUT_OF_SCOPE_NON_TARGET"}:
            continue
        actual_rows.append(
            {
                "key": key,
                "actual_row_number": idx,
                "hunt_code": key[0],
                "residency": key[1],
                "points": key[2],
                "draw_system_type": key[3],
                "species": clean(row.get("species")),
                "hunt_name": clean(row.get("hunt_name")),
                "probability": probability,
                "eligible_applicants": clean(row.get("eligible_applicants")),
                "total_permits": clean(row.get("total_permits")),
                "record_type": clean(row.get("record_type")),
            }
        )

    pred_dupes = Counter(row["key"] for row in prediction_rows)
    actual_dupes = Counter(row["key"] for row in actual_rows)
    predictions = aggregate_prediction_rows(prediction_rows, "key")
    actuals = aggregate_actual_rows(actual_rows, "key")
    actuals_2025 = actual_rows_for_year(2025)

    rowlevel: list[dict[str, Any]] = []
    errors: list[float] = []
    by_system: dict[str, list[float]] = defaultdict(list)
    by_species: dict[str, list[float]] = defaultdict(list)
    by_residency: dict[str, list[float]] = defaultdict(list)
    just_missed_rows: list[dict[str, Any]] = []
    model_applicant_pairs: list[tuple[float, float]] = []
    just_missed_model_pairs: list[tuple[float, float]] = []
    just_missed_same_level_pairs: list[tuple[float, float]] = []
    just_missed_rollforward_pairs: list[tuple[float, float]] = []
    just_missed_model_pairs_with_same_level: list[tuple[float, float]] = []
    just_missed_model_pairs_with_rollforward: list[tuple[float, float]] = []

    for key in sorted(set(predictions) & set(actuals)):
        pred = predictions[key]
        actual = actuals[key]
        error = pred["probability"] - actual["probability"]
        errors.append(error)
        by_system[key[3]].append(error)
        by_species[actual.get("species") or pred.get("species") or "UNKNOWN"].append(error)
        by_residency[key[1]].append(error)
        predicted_applicants = parse_float(pred.get("predicted_applicants"))
        actual_applicants = parse_float(actual.get("eligible_applicants"))
        point_value = parse_int(key[2])
        target_point = just_missed_target_point(pred)
        is_just_missed = point_value is not None and target_point is not None and point_value == target_point
        prior_same_level = actuals_2025.get(key)
        prior_same_level_applicants = parse_float((prior_same_level or {}).get("eligible_applicants"))
        prior_unsuccessful_applicants: float | None = None
        if point_value is not None and point_value > 0:
            prior_source_key = (key[0], key[1], str(point_value - 1), key[3])
            prior_source = actuals_2025.get(prior_source_key)
            if prior_source is not None:
                prior_eligible = parse_float(prior_source.get("eligible_applicants"))
                prior_drawn = parse_float(prior_source.get("total_permits"))
                if prior_eligible is not None and prior_drawn is not None:
                    prior_unsuccessful_applicants = max(prior_eligible - prior_drawn, 0.0)
        if predicted_applicants is not None and actual_applicants is not None:
            model_applicant_pairs.append((predicted_applicants, actual_applicants))
        if is_just_missed and predicted_applicants is not None and actual_applicants is not None:
            just_missed_model_pairs.append((predicted_applicants, actual_applicants))
            if prior_same_level_applicants is not None:
                just_missed_same_level_pairs.append((prior_same_level_applicants, actual_applicants))
                just_missed_model_pairs_with_same_level.append((predicted_applicants, actual_applicants))
            if prior_unsuccessful_applicants is not None:
                just_missed_rollforward_pairs.append((prior_unsuccessful_applicants, actual_applicants))
                just_missed_model_pairs_with_rollforward.append((predicted_applicants, actual_applicants))
            just_missed_rows.append(
                {
                    "hunt_code": key[0],
                    "residency": key[1],
                    "points": key[2],
                    "draw_system_type": key[3],
                    "species": actual.get("species") or pred.get("species"),
                    "hunt_name": actual.get("hunt_name") or pred.get("hunt_name"),
                    "just_missed_source_point_2025": point_value - 1 if point_value is not None else "",
                    "predicted_applicants_2026": f"{predicted_applicants:.6f}",
                    "actual_applicants_2026": f"{actual_applicants:.6f}",
                    "model_applicant_error": f"{predicted_applicants - actual_applicants:.6f}",
                    "prior_same_level_applicants_2025": "" if prior_same_level_applicants is None else f"{prior_same_level_applicants:.6f}",
                    "prior_unsuccessful_source_cohort_2025": "" if prior_unsuccessful_applicants is None else f"{prior_unsuccessful_applicants:.6f}",
                    "prediction_rows_aggregated": pred.get("row_count_aggregated", 1),
                }
            )
        rowlevel.append(
            {
                "hunt_code": key[0],
                "residency": key[1],
                "points": key[2],
                "draw_system_type": key[3],
                "species": actual.get("species") or pred.get("species"),
                "hunt_name": actual.get("hunt_name") or pred.get("hunt_name"),
                "predicted_probability": f"{pred['probability']:.9f}",
                "actual_probability": f"{actual['probability']:.9f}",
                "predicted_applicants": "" if predicted_applicants is None else f"{predicted_applicants:.6f}",
                "actual_applicants": "" if actual_applicants is None else f"{actual_applicants:.6f}",
                "applicant_error": "" if predicted_applicants is None or actual_applicants is None else f"{predicted_applicants - actual_applicants:.6f}",
                "just_missed_successor_cohort": "TRUE" if is_just_missed else "FALSE",
                "error": f"{error:.9f}",
                "absolute_error": f"{abs(error):.9f}",
                "prediction_rows_aggregated": pred.get("row_count_aggregated", 1),
                "actual_rows_aggregated": actual.get("row_count_aggregated", 1),
                "algorithm_status": pred.get("algorithm_status", ""),
                "model_strategy": pred.get("model_strategy", ""),
            }
        )

    unmatched_predictions = [predictions[key] for key in sorted(set(predictions) - set(actuals))]
    unmatched_actuals = [actuals[key] for key in sorted(set(actuals) - set(predictions))]
    history_code_years = build_history_code_years()
    current_only_bear_split_codes = load_current_only_bear_split_codes()
    current_database_by_code = load_current_database_by_code()
    source_verified_prediction_gaps: list[dict[str, Any]] = []
    unexpected_unmatched_actuals: list[dict[str, Any]] = []
    unmatched_disposition_counts: Counter[str] = Counter()
    for row in unmatched_actuals:
        disposition, disposition_reason = disposition_for_unmatched_actual(
            row,
            history_code_years,
            current_only_bear_split_codes,
            current_database_by_code,
        )
        annotated = dict(row)
        annotated["disposition"] = disposition
        annotated["disposition_reason"] = disposition_reason
        annotated["history_years_available"] = "|".join(str(year) for year in sorted(history_code_years.get(norm_code(row.get("hunt_code")), set())))
        unmatched_disposition_counts[disposition] += 1
        if disposition.startswith("SOURCE_VERIFIED"):
            source_verified_prediction_gaps.append(annotated)
        else:
            unexpected_unmatched_actuals.append(annotated)
    duplicate_pred_rows = [
        {
            "hunt_code": key[0],
            "residency": key[1],
            "points": key[2],
            "draw_system_type": key[3],
            "duplicate_count": count,
        }
        for key, count in sorted(pred_dupes.items())
        if count > 1
    ]
    duplicate_actual_rows = [
        {
            "hunt_code": key[0],
            "residency": key[1],
            "points": key[2],
            "draw_system_type": key[3],
            "duplicate_count": count,
        }
        for key, count in sorted(actual_dupes.items())
        if count > 1
    ]

    compare_dir = out_dir / "comparison_phase"
    write_csv(
        compare_dir / "prediction_2025_to_2026_vs_actual_2026_rowlevel.csv",
        [
            "hunt_code",
            "residency",
            "points",
            "draw_system_type",
            "species",
            "hunt_name",
            "predicted_probability",
            "actual_probability",
            "predicted_applicants",
            "actual_applicants",
            "applicant_error",
            "just_missed_successor_cohort",
            "error",
            "absolute_error",
            "prediction_rows_aggregated",
            "actual_rows_aggregated",
            "algorithm_status",
            "model_strategy",
        ],
        rowlevel,
    )
    write_csv(
        compare_dir / "just_missed_applicant_forecast_vs_2026_actual.csv",
        [
            "hunt_code",
            "residency",
            "points",
            "draw_system_type",
            "species",
            "hunt_name",
            "just_missed_source_point_2025",
            "predicted_applicants_2026",
            "actual_applicants_2026",
            "model_applicant_error",
            "prior_same_level_applicants_2025",
            "prior_unsuccessful_source_cohort_2025",
            "prediction_rows_aggregated",
        ],
        just_missed_rows,
    )
    write_csv(
        compare_dir / "unmatched_frozen_predictions.csv",
        ["hunt_code", "residency", "points", "draw_system_type", "species", "hunt_name", "probability", "algorithm_status", "model_strategy", "row_count_aggregated"],
        unmatched_predictions,
    )
    write_csv(
        compare_dir / "unmatched_2026_actuals.csv",
        ["hunt_code", "residency", "points", "draw_system_type", "species", "hunt_name", "probability", "eligible_applicants", "total_permits", "record_type", "row_count_aggregated"],
        unmatched_actuals,
    )
    unmatched_actual_disposition_fields = [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "species",
        "hunt_name",
        "probability",
        "eligible_applicants",
        "total_permits",
        "record_type",
        "row_count_aggregated",
        "disposition",
        "history_years_available",
        "disposition_reason",
    ]
    write_csv(
        compare_dir / "source_verified_prediction_gaps_2026_actuals.csv",
        unmatched_actual_disposition_fields,
        source_verified_prediction_gaps,
    )
    write_csv(
        compare_dir / "unexpected_unmatched_2026_actuals.csv",
        unmatched_actual_disposition_fields,
        unexpected_unmatched_actuals,
    )
    write_csv(
        compare_dir / "duplicate_prediction_keys.csv",
        ["hunt_code", "residency", "points", "draw_system_type", "duplicate_count"],
        duplicate_pred_rows,
    )
    write_csv(
        compare_dir / "duplicate_actual_keys.csv",
        ["hunt_code", "residency", "points", "draw_system_type", "duplicate_count"],
        duplicate_actual_rows,
    )

    grouped_rows = []
    for label, groups in (("draw_system_type", by_system), ("species", by_species), ("residency", by_residency)):
        for value, group_errors in sorted(groups.items()):
            row = {"group_type": label, "group_value": value}
            row.update(metric_summary(group_errors))
            grouped_rows.append(row)
    write_csv(
        compare_dir / "prediction_accuracy_grouped.csv",
        ["group_type", "group_value", "joined_rows", "mae", "rmse", "bias", "median_abs_error", "p90_abs_error", "failure_abs_error_gt_0_25"],
        grouped_rows,
    )

    just_missed_model_metrics = applicant_metric_summary(just_missed_model_pairs)
    just_missed_same_level_metrics = applicant_metric_summary(just_missed_same_level_pairs)
    just_missed_rollforward_metrics = applicant_metric_summary(just_missed_rollforward_pairs)

    def improvement_against(model: Mapping[str, Any], baseline: Mapping[str, Any]) -> float | str:
        model_mae = model.get("mae_applicants")
        baseline_mae = baseline.get("mae_applicants")
        if not isinstance(model_mae, (int, float)) or not isinstance(baseline_mae, (int, float)) or baseline_mae <= 0:
            return ""
        return (baseline_mae - model_mae) / baseline_mae

    summary = {
        "prediction_file": rel(frozen_prediction),
        "actual_file": rel(actual_2026),
        "prediction_rows_raw": len(pred_raw),
        "prediction_rows_with_probability": len(prediction_rows),
        "prediction_rows_without_probability": prediction_without_probability,
        "prediction_unique_keys": len(predictions),
        "actual_rows_raw": len(actual_raw),
        "actual_rows_with_probability": len(actual_rows),
        "actual_rows_without_probability": actual_without_probability,
        "actual_zero_applicant_rows_excluded": actual_excluded_zero_applicants,
        "actual_unique_keys": len(actuals),
        "joined_keys": len(rowlevel),
        "unmatched_prediction_keys": len(unmatched_predictions),
        "unmatched_actual_keys": len(unmatched_actuals),
        "source_verified_prediction_gap_actual_keys": len(source_verified_prediction_gaps),
        "unexpected_unmatched_actual_keys": len(unexpected_unmatched_actuals),
        "unmatched_actual_disposition_counts": dict(sorted(unmatched_disposition_counts.items())),
        "duplicate_prediction_key_groups": len(duplicate_pred_rows),
        "duplicate_actual_key_groups": len(duplicate_actual_rows),
        "join_key": "hunt_code + residency + points + draw_system_type",
        "overall_metrics": metric_summary(errors),
        "applicant_forecast_metrics": applicant_metric_summary(model_applicant_pairs),
        "just_missed_applicant_forecast": {
            "definition": "The 2026 successor point immediately above the 2025 preference cutoff, or the bonus engine's declared rollover anchor next point.",
            "model": just_missed_model_metrics,
            "prior_same_point_baseline": just_missed_same_level_metrics,
            "pure_prior_unsuccessful_rollforward_baseline": just_missed_rollforward_metrics,
            "paired_model_for_prior_same_point_rows": applicant_metric_summary(just_missed_model_pairs_with_same_level),
            "paired_model_for_pure_rollforward_rows": applicant_metric_summary(just_missed_model_pairs_with_rollforward),
            "model_mae_improvement_vs_prior_same_point": improvement_against(
                applicant_metric_summary(just_missed_model_pairs_with_same_level),
                just_missed_same_level_metrics,
            ),
            "model_mae_improvement_vs_pure_prior_unsuccessful_rollforward": improvement_against(
                applicant_metric_summary(just_missed_model_pairs_with_rollforward),
                just_missed_rollforward_metrics,
            ),
        },
        "outputs": {
            "rowlevel": rel(compare_dir / "prediction_2025_to_2026_vs_actual_2026_rowlevel.csv"),
            "grouped": rel(compare_dir / "prediction_accuracy_grouped.csv"),
            "unmatched_predictions": rel(compare_dir / "unmatched_frozen_predictions.csv"),
            "unmatched_actuals": rel(compare_dir / "unmatched_2026_actuals.csv"),
            "source_verified_prediction_gaps": rel(compare_dir / "source_verified_prediction_gaps_2026_actuals.csv"),
            "unexpected_unmatched_actuals": rel(compare_dir / "unexpected_unmatched_2026_actuals.csv"),
            "duplicate_prediction_keys": rel(compare_dir / "duplicate_prediction_keys.csv"),
            "duplicate_actual_keys": rel(compare_dir / "duplicate_actual_keys.csv"),
            "just_missed_applicant_forecast": rel(compare_dir / "just_missed_applicant_forecast_vs_2026_actual.csv"),
        },
    }
    write_json(compare_dir / "comparison_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--skip-prediction", action="store_true", help="Only rescore an existing frozen prediction in --out-dir.")
    parser.add_argument("--rebuild-main-bonus", action="store_true", help="Rebuild the main OIL/LE/PLE bonus draft from the filtered through-2025 truth inside --out-dir before freezing predictions.")
    parser.add_argument("--keep-temp-truth", action="store_true", help="Keep large copied truth/runtime input files for debugging.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_started = datetime.now(timezone.utc).isoformat()

    if args.skip_prediction:
        frozen_prediction = out_dir / "prediction_phase" / "draw_reality_engine_predictive_v2.csv"
        if not frozen_prediction.exists():
            raise FileNotFoundError(f"Missing frozen prediction file: {frozen_prediction}")
        prediction_info = {
            "prediction_dir": frozen_prediction.parent,
            "frozen_prediction": frozen_prediction,
            "frozen_prediction_sha256": sha256(frozen_prediction),
            "skipped_prediction_phase": True,
        }
        filtered_info: dict[str, Any] = {}
        runtime_info: dict[str, Any] = {}
    else:
        filtered_info = build_filtered_truth(out_dir)
        runtime_info = prepare_runtime_inputs(out_dir)
        if args.rebuild_main_bonus:
            runtime_info["main_bonus_rebuild"] = rebuild_main_bonus_frozen_inputs(filtered_info["path"], runtime_info["path"])
        prediction_info = run_prediction_phase(out_dir, filtered_info["path"], runtime_info["path"])

    actual_2026 = build_or_resolve_actual_2026(out_dir)
    locked_manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_started_utc": run_started,
        "purpose": "blind_2025_to_2026_prediction_backtest",
        "no_leakage_rule": "prediction phase uses scorable actual_draw_year <= 2025 only; 2026 actual file read only after prediction hash is recorded",
        "history_years": HISTORY_YEARS,
        "prediction_target_year": 2026,
        "filtered_truth_input": {
            **{key: value for key, value in filtered_info.items() if key != "path"},
            "path": rel(filtered_info["path"]) if filtered_info else "",
        },
        "runtime_input_copy": {
            **{key: value for key, value in runtime_info.items() if key != "path"},
            "path": rel(runtime_info["path"]) if runtime_info else "",
        },
        "frozen_prediction": {
            "path": rel(prediction_info["frozen_prediction"]),
            "sha256": prediction_info["frozen_prediction_sha256"],
        },
        "actual_2026_reserved_for_scoring_only": {
            "path": rel(actual_2026),
            "sha256": sha256(actual_2026),
        },
    }
    write_json(out_dir / "locked_prediction_manifest.json", locked_manifest)

    comparison_summary = compare_to_actual(out_dir, prediction_info["frozen_prediction"], actual_2026)
    cleanup_summary = cleanup_large_temp_truth_files(out_dir, args.keep_temp_truth)
    final_summary = {
        "locked_prediction_manifest": rel(out_dir / "locked_prediction_manifest.json"),
        "comparison_summary": rel(out_dir / "comparison_phase" / "comparison_summary.json"),
        "frozen_prediction_sha256": prediction_info["frozen_prediction_sha256"],
        "large_temp_truth_cleanup": cleanup_summary,
        "comparison": comparison_summary,
    }
    write_json(out_dir / "blind_backtest_summary.json", final_summary)
    print(json.dumps(final_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
