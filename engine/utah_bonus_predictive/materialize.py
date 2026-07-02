"""Formal materialization CLI for Utah bonus predictive outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from engine.utah_draw_predictive import append_reason_codes
from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields
from engine.utah.current_year_allotments import apply_current_year_allotments_to_rows
from engine.utah_draw_predictive.bear import (
    BEAR_DRAW_SYSTEM_TYPE,
    CONSERVATION_OR_NON_PUBLIC,
    HARVEST_OBJECTIVE_AVAILABILITY,
    RESTRICTED_BEAR_PURSUIT,
    STATEWIDE_BEAR_PERMIT,
    UNLIMITED_PURSUIT_PERMIT,
    build_bear_draw_odds_source_audit,
    build_bear_bonus_predictions,
)
from engine.utah_draw_predictive.dedicated_hunter import build_preference_dedicated_hunter_predictions
from engine.utah_draw_predictive.mountain_lion import (
    DRAW_SYSTEM_TYPE as MOUNTAIN_LION_DRAW_SYSTEM_TYPE,
    build_mountain_lion_availability_predictions,
)
from engine.utah_draw_predictive.preference_antlerless import build_preference_antlerless_predictions
from engine.utah_draw_predictive.preference_general_deer import build_preference_general_deer_predictions
from engine.utah_draw_predictive.private_lands_antlerless_elk import (
    DRAW_SYSTEM_TYPE as PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE,
    build_private_lands_antlerless_elk_predictions,
)
from engine.utah_draw_predictive.special_bonus import PHASE6_DRAW_SYSTEM_TYPES, build_phase6_bonus_special_predictions
from engine.utah_draw_predictive.sportsman import SPORTSMAN_DRAW_SYSTEM_TYPE, build_sportsman_predictions
from engine.utah_draw_predictive.turkey import (
    TURKEY_DRAW_SYSTEM_TYPE,
    YOUTH_TURKEY_DRAW_SYSTEM_TYPE,
    build_turkey_bonus_predictions,
    build_youth_turkey_predictions,
)
from engine.utah_draw_predictive.youth import (
    YOUTH_DRAW_SYSTEM_TYPES,
    build_youth_predictions,
)

from .backtest import build_backtest_rows
from .forecast import (
    REPO,
    build_above_index,
    build_truth_indexes,
    materialize_prediction_rows,
    normalize_history_years,
    read_csv,
    run_official_forecast_build,
    write_csv,
)
from .rules import MODEL_VERSION, RULE_VERSION
from .split import split_utah_bonus_permits


TRUTH_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
RUNTIME_DRAFT_DIR = REPO / "data_model" / "runtime_drafts"
DATABASE_2026_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
TARGET_HUNT_TOKENS = (
    "once-in-a-lifetime",
    "once in a lifetime",
    "oial",
    "limited entry",
    "premium limited entry",
)

RUNTIME_PROMOTION_DECISION = "APPROVED_RUNTIME_PROMOTION_2026_06_29"
PROMOTED_RUNTIME_FAMILY_REPORTS = {
    "SPORTSMAN_RANDOM_ONLY": "sportsman_permit_report.json",
    "YOUTH_GENERAL_ANY_BULL_ELK": "youth_draw_report.json",
    "PREFERENCE_DEDICATED_HUNTER_DEER": "dedicated_hunter_report.json",
    TURKEY_DRAW_SYSTEM_TYPE: "turkey_bonus_report.json",
    YOUTH_TURKEY_DRAW_SYSTEM_TYPE: "youth_turkey_report.json",
}


def _clean_cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def expand_collapsed_truth_rows_for_engine(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Expand resident/nonresident display columns into engine-ready rows.

    Canonical and long files may keep one row with resident_* and nonresident_*
    fields. The model engines consume one residency/point row at a time, so this
    expansion is runtime-only and does not mutate the source files.
    """
    expanded_rows: list[dict[str, str]] = []
    for row in rows:
        if _clean_cell(row.get("residency")):
            out = dict(row)
            if not _clean_cell(out.get("year")) and _clean_cell(out.get("actual_draw_year")):
                out["year"] = _clean_cell(out.get("actual_draw_year"))
            if not _clean_cell(out.get("draw_pool")):
                out["draw_pool"] = "standard"
            expanded_rows.append(out)
            continue

        emitted = False
        for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            has_data = any(
                _clean_cell(row.get(f"{prefix}_{field}"))
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
            out["eligible_applicants"] = _clean_cell(row.get(f"{prefix}_eligible_applicants"))
            out["bonus_permits"] = _clean_cell(row.get(f"{prefix}_bonus_permits"))
            out["regular_permits"] = _clean_cell(row.get(f"{prefix}_regular_permits"))
            out["total_permits"] = _clean_cell(row.get(f"{prefix}_total_permits"))
            out["success_ratio"] = _clean_cell(row.get(f"{prefix}_success_ratio"))
            out["p_draw"] = _clean_cell(row.get(f"{prefix}_p_draw"))
            out["p_draw_percent"] = _clean_cell(row.get(f"{prefix}_p_draw_percent"))
            if not _clean_cell(out.get("year")) and _clean_cell(out.get("actual_draw_year")):
                out["year"] = _clean_cell(out.get("actual_draw_year"))
            if not _clean_cell(out.get("draw_pool")):
                out["draw_pool"] = "standard"
            expanded_rows.append(out)
            emitted = True

        if not emitted:
            out = dict(row)
            if not _clean_cell(out.get("year")) and _clean_cell(out.get("actual_draw_year")):
                out["year"] = _clean_cell(out.get("actual_draw_year"))
            if not _clean_cell(out.get("draw_pool")):
                out["draw_pool"] = "standard"
            expanded_rows.append(out)
    return expanded_rows


def status_from_probability(max_point_permits: int, random_permits: int, p_bonus_pool: float) -> str:
    if max_point_permits == 0 and random_permits > 0:
        return "RANDOM ONLY"
    if p_bonus_pool >= 0.999:
        return "MAX POOL"
    if p_bonus_pool > 0:
        return "ON EDGE"
    return "BEHIND"


def build_report(
    prediction_rows: list[dict[str, object]],
    forecast_year: int,
    history_years: list[int],
    source_path: Path,
    command_used: str,
) -> dict[str, object]:
    return {
        "rows": len(prediction_rows),
        "unique_hunt_codes": len({row["hunt_code"] for row in prediction_rows}),
        "years": sorted({str(row["year"]) for row in prediction_rows}),
        "forecast_year": forecast_year,
        "source_years": f"{min(history_years)}-{max(history_years)}",
        "source_years_used_nonnull": sum(1 for row in prediction_rows if str(row.get("source_years_used", "")).strip() != ""),
        "source": str(source_path.relative_to(REPO)),
        "command_used": command_used,
    }


def _nonnull(rows: list[dict[str, object]], column: str) -> int:
    return sum(1 for row in rows if str(row.get(column, "")).strip() != "")


def _duplicate_count(rows: list[dict[str, object]], fields: list[str]) -> int:
    keys = [tuple(str(row.get(field, "")).strip() for field in fields) for row in rows]
    return len(keys) - len(set(keys))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _write_phase4_antlerless_inventory(output_dir: Path, prediction_rows: list[dict[str, object]], forecast_year: int, history_years: list[int]) -> tuple[Path, Path]:
    antlerless_rows = [
        row for row in prediction_rows
        if row.get("draw_system_type") in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}
        and row.get("algorithm_status") == "MODELED_PREFERENCE"
    ]
    inventory_map: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in antlerless_rows:
        key = (
            str(row.get("draw_system_type", "")),
            str(row.get("hunt_code", "")),
            str(row.get("hunt_name", "")),
            str(row.get("species", "")),
            str(row.get("residency", "")),
        )
        item = inventory_map.setdefault(
            key,
            {
                "draw_system_type": row.get("draw_system_type", ""),
                "hunt_code": row.get("hunt_code", ""),
                "hunt_name": row.get("hunt_name", ""),
                "species": row.get("species", ""),
                "residency": row.get("residency", ""),
                "points_modeled": 0,
                "min_points": "",
                "max_points": "",
                "public_permits_2026": row.get("public_permits_2026", ""),
                "source_years_used": row.get("source_years_used", ""),
                "model_strategy": row.get("model_strategy", ""),
            },
        )
        points = int(float(str(row.get("points", "0")) or 0))
        item["points_modeled"] = int(item["points_modeled"]) + 1
        item["min_points"] = points if item["min_points"] == "" else min(int(item["min_points"]), points)
        item["max_points"] = points if item["max_points"] == "" else max(int(item["max_points"]), points)

    inventory_rows = sorted(
        inventory_map.values(),
        key=lambda row: (
            str(row.get("draw_system_type", "")),
            str(row.get("hunt_code", "")),
            str(row.get("residency", "")),
        ),
    )
    csv_path = output_dir / "phase4_antlerless_validation_inventory.csv"
    write_csv(
        csv_path,
        inventory_rows,
        [
            "draw_system_type",
            "hunt_code",
            "hunt_name",
            "species",
            "residency",
            "points_modeled",
            "min_points",
            "max_points",
            "public_permits_2026",
            "source_years_used",
            "model_strategy",
        ],
    )
    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "modeled_rows": len(antlerless_rows),
        "modeled_hunt_codes_by_type": {
            draw_system_type: len({str(row.get("hunt_code", "")) for row in antlerless_rows if row.get("draw_system_type") == draw_system_type})
            for draw_system_type in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}
        },
        "modeled_inventory_rows": len(inventory_rows),
        "modeled_inventory_residency_counts": {
            residency: sum(1 for row in inventory_rows if str(row.get("residency", "")) == residency)
            for residency in sorted({str(row.get("residency", "")) for row in inventory_rows})
        },
        "csv": _safe_relative(csv_path),
    }
    json_path = output_dir / "phase4_antlerless_validation_inventory.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_dedicated_hunter_artifacts(output_dir: Path, prediction_rows: list[dict[str, object]], forecast_year: int, history_years: list[int]) -> tuple[Path, Path]:
    dedicated_rows = [row for row in prediction_rows if row.get("draw_system_type") == "PREFERENCE_DEDICATED_HUNTER_DEER"]
    csv_path = output_dir / "dedicated_hunter_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in dedicated_rows for key in row.keys())) if dedicated_rows else [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "algorithm_status",
        "p_preference_draw",
        "p_draw",
        "p_draw_pct",
        "p_bonus_pool",
        "p_random_pool",
    ]
    write_csv(csv_path, dedicated_rows, fieldnames)

    modeled_rows = [row for row in dedicated_rows if row.get("algorithm_status") == "MODELED_PREFERENCE"]
    pending_rows = [row for row in dedicated_rows if row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"]
    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "exists": True,
        "total_rows": len(dedicated_rows),
        "modeled_preference_row_count": len(modeled_rows),
        "in_scope_model_pending_row_count": len(pending_rows),
        "modeled_hunt_code_count": len({str(row.get("hunt_code", "")) for row in modeled_rows if str(row.get("hunt_code", "")).strip()}),
        "p_preference_draw_non_null_count": _nonnull(modeled_rows, "p_preference_draw"),
        "p_draw_non_null_count": _nonnull(modeled_rows, "p_draw"),
        "p_draw_pct_non_null_count": _nonnull(modeled_rows, "p_draw_pct"),
        "p_bonus_pool_non_null_count": _nonnull(dedicated_rows, "p_bonus_pool"),
        "p_random_pool_non_null_count": _nonnull(dedicated_rows, "p_random_pool"),
        "p_draw_outside_0_1_count": sum(
            1
            for row in modeled_rows
            if str(row.get("p_draw", "")).strip()
            and not (0.0 <= float(str(row.get("p_draw", "")).strip()) <= 1.0)
        ),
        "p_draw_pct_outside_0_100_count": sum(
            1
            for row in modeled_rows
            if str(row.get("p_draw_pct", "")).strip()
            and not (0.0 <= float(str(row.get("p_draw_pct", "")).strip()) <= 100.0)
        ),
        "csv": _safe_relative(csv_path),
    }
    json_path = output_dir / "dedicated_hunter_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_phase6_bonus_special_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    phase6_report: dict[str, object],
) -> tuple[Path, Path]:
    phase6_rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() in PHASE6_DRAW_SYSTEM_TYPES]
    csv_path = output_dir / "phase6_bonus_special_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in phase6_rows for key in row.keys())) if phase6_rows else [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "algorithm_status",
        "p_bonus_pool",
        "p_random_pool",
        "p_draw",
        "p_draw_pct",
        "p_preference_draw",
    ]
    write_csv(csv_path, phase6_rows, fieldnames)
    modeled_rows = [row for row in phase6_rows if str(row.get("algorithm_status", "")).strip() == "MODELED_BONUS"]
    pending_rows = [row for row in phase6_rows if str(row.get("algorithm_status", "")).strip() == "IN_SCOPE_MODEL_PENDING"]
    cwmu_modeled_rows = [row for row in modeled_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_CWMU_BIG_GAME"]
    cwmu_pending_rows = [row for row in pending_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_CWMU_BIG_GAME"]
    antlerless_moose_modeled_rows = [row for row in modeled_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_ANTLERLESS_MOOSE"]
    antlerless_moose_pending_rows = [row for row in pending_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_ANTLERLESS_MOOSE"]
    ewe_bighorn_modeled_rows = [row for row in modeled_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_EWE_BIGHORN"]
    ewe_bighorn_pending_rows = [row for row in pending_rows if str(row.get("draw_system_type", "")).strip() == "BONUS_EWE_BIGHORN"]
    phase6_report = dict(phase6_report)
    phase6_report.update(
        {
            "total_phase6_rows": len(phase6_rows),
            "rows_by_draw_system_type": dict(
                sorted(
                    (
                        draw_system_type,
                        sum(1 for row in phase6_rows if str(row.get("draw_system_type", "")).strip() == draw_system_type),
                    )
                    for draw_system_type in sorted({str(row.get("draw_system_type", "")).strip() for row in phase6_rows if str(row.get("draw_system_type", "")).strip()})
                )
            ),
            "rows_by_algorithm_status": dict(
                sorted(
                    (
                        algorithm_status,
                        sum(1 for row in phase6_rows if str(row.get("algorithm_status", "")).strip() == algorithm_status),
                    )
                    for algorithm_status in sorted({str(row.get("algorithm_status", "")).strip() for row in phase6_rows if str(row.get("algorithm_status", "")).strip()})
                )
            ),
            "cwmu_public_modeled_row_count": len(cwmu_modeled_rows),
            "cwmu_public_modeled_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in cwmu_modeled_rows if str(row.get("hunt_code", "")).strip()}),
            "cwmu_pending_row_count": len(cwmu_pending_rows),
            "antlerless_moose_modeled_row_count": len(antlerless_moose_modeled_rows),
            "antlerless_moose_modeled_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in antlerless_moose_modeled_rows if str(row.get("hunt_code", "")).strip()}),
            "antlerless_moose_pending_row_count": len(antlerless_moose_pending_rows),
            "ewe_bighorn_modeled_row_count": len(ewe_bighorn_modeled_rows),
            "ewe_bighorn_modeled_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in ewe_bighorn_modeled_rows if str(row.get("hunt_code", "")).strip()}),
            "ewe_bighorn_pending_row_count": len(ewe_bighorn_pending_rows),
            "p_bonus_pool_non_null_count": _nonnull(phase6_rows, "p_bonus_pool"),
            "p_random_pool_non_null_count": _nonnull(phase6_rows, "p_random_pool"),
            "p_draw_non_null_count": _nonnull(phase6_rows, "p_draw"),
            "p_draw_pct_non_null_count": _nonnull(phase6_rows, "p_draw_pct"),
            "p_preference_draw_non_null_count": _nonnull(phase6_rows, "p_preference_draw"),
            "p_draw_outside_0_1_count": sum(
                1
                for row in phase6_rows
                if str(row.get("p_draw", "")).strip()
                and not (0.0 <= float(str(row.get("p_draw", "")).strip()) <= 1.0)
            ),
            "p_draw_pct_outside_0_100_count": sum(
                1
                for row in phase6_rows
                if str(row.get("p_draw_pct", "")).strip()
                and not (0.0 <= float(str(row.get("p_draw_pct", "")).strip()) <= 100.0)
            ),
            "duplicate_key_count": _duplicate_count(phase6_rows, ["hunt_code", "residency", "points"]),
            "source_years_used_non_null_count": _nonnull(phase6_rows, "source_years_used"),
        }
    )
    json_path = output_dir / "phase6_bonus_special_report.json"
    json_path.write_text(json.dumps(phase6_report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_turkey_bonus_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    turkey_report: dict[str, object],
) -> tuple[Path, Path]:
    turkey_rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() == TURKEY_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "turkey_bonus_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in turkey_rows for key in row.keys())) if turkey_rows else [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "algorithm_status",
        "p_bonus_pool",
        "p_random_pool",
        "p_draw",
        "p_draw_pct",
        "p_preference_draw",
    ]
    write_csv(csv_path, turkey_rows, fieldnames)
    modeled_rows = [row for row in turkey_rows if str(row.get("algorithm_status", "")).strip() == "MODELED_BONUS"]
    pending_rows = [row for row in turkey_rows if str(row.get("algorithm_status", "")).strip() == "IN_SCOPE_MODEL_PENDING"]
    turkey_report = dict(turkey_report)
    turkey_report.update(
        {
            "turkey_rows_seen_active_predictive": len(turkey_rows),
            "turkey_rows_seen_total": int(turkey_report.get("turkey_rows_seen_observed_history", 0)) + len(turkey_rows),
            "turkey_rows_forecast_eligible": len(turkey_rows),
            "bonus_turkey_rows_active_predictive": len(turkey_rows),
            "bonus_turkey_modeled_rows": len(modeled_rows),
            "bonus_turkey_pending_rows": len(pending_rows),
            "bonus_turkey_modeled_hunt_codes": len({str(row.get("hunt_code", "")).strip() for row in modeled_rows if str(row.get("hunt_code", "")).strip()}),
            "p_bonus_pool_non_null_count": _nonnull(turkey_rows, "p_bonus_pool"),
            "p_random_pool_non_null_count": _nonnull(turkey_rows, "p_random_pool"),
            "p_draw_non_null_count": _nonnull(turkey_rows, "p_draw"),
            "p_draw_pct_non_null_count": _nonnull(turkey_rows, "p_draw_pct"),
            "p_preference_draw_non_null_count": _nonnull(turkey_rows, "p_preference_draw"),
            "p_draw_outside_0_1_count": sum(
                1
                for row in turkey_rows
                if str(row.get("p_draw", "")).strip()
                and not (0.0 <= float(str(row.get("p_draw", "")).strip()) <= 1.0)
            ),
            "p_draw_pct_outside_0_100_count": sum(
                1
                for row in turkey_rows
                if str(row.get("p_draw_pct", "")).strip()
                and not (0.0 <= float(str(row.get("p_draw_pct", "")).strip()) <= 100.0)
            ),
            "duplicate_key_count": _duplicate_count(turkey_rows, ["hunt_code", "residency", "points"]),
            "source_years_used_non_null_count": _nonnull(turkey_rows, "source_years_used"),
        }
    )
    json_path = output_dir / "turkey_bonus_report.json"
    json_path.write_text(json.dumps(turkey_report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_youth_turkey_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    youth_turkey_report: dict[str, object],
) -> tuple[Path, Path]:
    rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() == YOUTH_TURKEY_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "youth_turkey_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys())) if rows else [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "algorithm_status",
        "draw_pool",
        "public_permits_2026",
        "p_bonus_pool",
        "p_random_pool",
        "p_draw",
        "p_draw_pct",
        "p_preference_draw",
    ]
    write_csv(csv_path, rows, fieldnames)
    modeled_rows = [row for row in rows if str(row.get("algorithm_status", "")).strip() == "MODELED_BONUS"]
    pending_rows = [row for row in rows if str(row.get("algorithm_status", "")).strip() == "IN_SCOPE_MODEL_PENDING"]
    youth_turkey_report = dict(youth_turkey_report)
    youth_turkey_report.update(
        {
            "youth_turkey_rows_seen_active_predictive": len(rows),
            "youth_turkey_rows_seen_total": int(youth_turkey_report.get("youth_turkey_rows_seen_observed_history", 0)) + len(rows),
            "youth_turkey_rows_forecast_eligible": len(rows),
            "youth_turkey_modeled_rows": len(modeled_rows),
            "youth_turkey_pending_rows": len(pending_rows),
            "youth_turkey_modeled_hunt_codes": len({str(row.get("hunt_code", "")).strip() for row in modeled_rows if str(row.get("hunt_code", "")).strip()}),
            "p_bonus_pool_non_null_count": _nonnull(rows, "p_bonus_pool"),
            "p_random_pool_non_null_count": _nonnull(rows, "p_random_pool"),
            "p_draw_non_null_count": _nonnull(rows, "p_draw"),
            "p_draw_pct_non_null_count": _nonnull(rows, "p_draw_pct"),
            "p_preference_draw_non_null_count": _nonnull(rows, "p_preference_draw"),
            "duplicate_key_count": _duplicate_count(rows, ["hunt_code", "residency", "points", "draw_system_type"]),
            "source_years_used_non_null_count": _nonnull(rows, "source_years_used"),
        }
    )
    json_path = output_dir / "youth_turkey_report.json"
    json_path.write_text(json.dumps(youth_turkey_report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_bear_bonus_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    bear_report: dict[str, object],
) -> tuple[Path, Path]:
    bear_rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() == BEAR_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "bear_draw_predictions_v1.csv"
    alias_csv_path = output_dir / "bear_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in bear_rows for key in row.keys())) if bear_rows else [
        "hunt_code",
        "residency",
        "points",
        "draw_system_type",
        "algorithm_status",
        "bear_draw_subtype",
        "p_bonus_pool",
        "p_random_pool",
        "p_draw",
        "p_draw_pct",
        "p_preference_draw",
    ]
    write_csv(csv_path, bear_rows, fieldnames)
    write_csv(alias_csv_path, bear_rows, fieldnames)
    modeled_rows = [row for row in bear_rows if str(row.get("algorithm_status", "")).strip() == "MODELED_BONUS"]
    pending_rows = [row for row in bear_rows if str(row.get("algorithm_status", "")).strip() == "IN_SCOPE_MODEL_PENDING"]
    excluded_rows = [row for row in bear_rows if str(row.get("algorithm_status", "")).strip() == "EXCLUDED_NOT_PREDICTIVE_DRAW"]
    bear_report = dict(bear_report)
    bear_report.update(
        {
            "bear_draw_active_predictive_row_count": len(bear_rows),
            "bear_draw_modeled_row_count": len(modeled_rows),
            "bear_draw_pending_row_count": len(pending_rows),
            "bear_draw_excluded_non_draw_row_count": len(excluded_rows),
            "statewide_bear_permit_row_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == STATEWIDE_BEAR_PERMIT),
            "statewide_bear_permit_modeled_row_count": sum(1 for row in modeled_rows if str(row.get("bear_draw_subtype", "")).strip() == STATEWIDE_BEAR_PERMIT),
            "statewide_bear_permit_pending_row_count": sum(1 for row in pending_rows if str(row.get("bear_draw_subtype", "")).strip() == STATEWIDE_BEAR_PERMIT),
            "statewide_bear_permit_excluded_row_count": sum(1 for row in excluded_rows if str(row.get("bear_draw_subtype", "")).strip() == STATEWIDE_BEAR_PERMIT),
            "statewide_bear_permit_p_draw_non_null_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == STATEWIDE_BEAR_PERMIT and str(row.get("p_draw", "")).strip()),
            "harvest_objective_row_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == HARVEST_OBJECTIVE_AVAILABILITY),
            "harvest_objective_p_draw_non_null_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == HARVEST_OBJECTIVE_AVAILABILITY and str(row.get("p_draw", "")).strip()),
            "harvest_objective_availability_fields_populated_count": sum(
                1
                for row in bear_rows
                if str(row.get("bear_draw_subtype", "")).strip() == HARVEST_OBJECTIVE_AVAILABILITY
                and any(str(row.get(field, "")).strip() for field in ("p_availability", "availability_pct", "harvest_objective_take_quota", "harvest_objective_status"))
            ),
            "unlimited_pursuit_permit_row_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == UNLIMITED_PURSUIT_PERMIT),
            "unlimited_pursuit_permit_p_draw_non_null_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == UNLIMITED_PURSUIT_PERMIT and str(row.get("p_draw", "")).strip()),
            "restricted_pursuit_modeled_row_count": sum(1 for row in modeled_rows if str(row.get("bear_draw_subtype", "")).strip() == RESTRICTED_BEAR_PURSUIT),
            "multiseason_limited_entry_bear_modeled_row_count": sum(1 for row in modeled_rows if "multiseason" in str(row.get("hunt_type", "")).strip().lower()),
            "spot_and_stalk_bear_modeled_row_count": sum(1 for row in modeled_rows if "spot and stalk" in str(row.get("hunt_type", "")).strip().lower()),
            "conservation_or_non_public_row_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == CONSERVATION_OR_NON_PUBLIC),
            "conservation_or_non_public_p_draw_non_null_count": sum(1 for row in bear_rows if str(row.get("bear_draw_subtype", "")).strip() == CONSERVATION_OR_NON_PUBLIC and str(row.get("p_draw", "")).strip()),
            "p_bonus_pool_non_null_count": _nonnull(bear_rows, "p_bonus_pool"),
            "p_random_pool_non_null_count": _nonnull(bear_rows, "p_random_pool"),
            "p_draw_non_null_count": _nonnull(bear_rows, "p_draw"),
            "p_draw_pct_non_null_count": _nonnull(bear_rows, "p_draw_pct"),
            "p_preference_draw_non_null_count": _nonnull(bear_rows, "p_preference_draw"),
            "duplicate_key_count": _duplicate_count(bear_rows, ["hunt_code", "residency", "points"]),
            "source_years_used_non_null_count": _nonnull(bear_rows, "source_years_used"),
        }
    )
    json_path = output_dir / "bear_draw_report.json"
    alias_json_path = output_dir / "bear_report.json"
    json_path.write_text(json.dumps(bear_report, indent=2), encoding="utf-8")
    alias_json_path.write_text(json.dumps(bear_report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_bear_draw_odds_source_audit_artifacts(
    output_dir: Path,
    audit_rows: list[dict[str, object]],
    audit_summary: dict[str, object],
) -> tuple[Path, Path]:
    csv_path = output_dir / "bear_draw_odds_source_audit.csv"
    json_path = output_dir / "bear_draw_odds_source_audit.json"
    fieldnames = list(dict.fromkeys(key for row in audit_rows for key in row.keys())) if audit_rows else [
        "hunt_code",
        "hunt_name",
        "source_year",
        "source_file",
        "appears_in_draw_odds_pdf",
        "has_point_level_bonus_rows",
        "resident_bonus_permits_total",
        "resident_regular_permits_total",
        "resident_total_permits",
        "nonresident_bonus_permits_total",
        "nonresident_regular_permits_total",
        "nonresident_total_permits",
        "source_classification",
        "engine_classification_before",
        "engine_classification_after",
        "correction_needed",
        "data_quality_flags",
    ]
    write_csv(csv_path, audit_rows, fieldnames)
    json_path.write_text(json.dumps(audit_summary, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_sportsman_artifacts(
    output_dir: Path,
    sportsman_rows: list[dict[str, object]],
    sportsman_report: dict[str, object],
) -> tuple[Path, Path]:
    sportsman_rows = [row for row in sportsman_rows if str(row.get("draw_system_type", "")).strip() == SPORTSMAN_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "sportsman_permit_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in sportsman_rows for key in row.keys())) if sportsman_rows else [
        "hunt_code",
        "residency",
        "draw_system_type",
        "algorithm_status",
        "sportsman_species",
        "sportsman_source_year",
        "sportsman_permit_count",
        "sportsman_applicants",
        "sportsman_odds_text",
        "sportsman_odds_denominator",
        "sportsman_source_file",
        "sportsman_residency_scope",
        "p_sportsman_draw",
        "p_draw",
        "p_draw_pct",
    ]
    write_csv(csv_path, sportsman_rows, fieldnames)
    json_path = output_dir / "sportsman_permit_report.json"
    json_path.write_text(json.dumps(sportsman_report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_private_lands_antlerless_elk_artifacts(
    output_dir: Path,
    private_lands_rows: list[dict[str, object]],
    report: dict[str, object],
) -> tuple[Path, Path]:
    rows = [row for row in private_lands_rows if str(row.get("draw_system_type", "")).strip() == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "private_lands_antlerless_elk_predictions_v1.csv"
    alias_csv_path = output_dir / "private_lands_antlerless_elk_allocations_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys())) if rows else [
        "hunt_code",
        "residency",
        "draw_system_type",
        "algorithm_status",
        "permits_allotted",
        "permits_remaining",
        "permits_sold_or_used",
        "allocation_status",
        "availability_status",
        "p_availability",
        "availability_pct",
        "sellout_risk",
        "season_status",
    ]
    write_csv(csv_path, rows, fieldnames)
    write_csv(alias_csv_path, rows, fieldnames)
    json_path = output_dir / "private_lands_antlerless_elk_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_mountain_lion_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    report: dict[str, object],
) -> tuple[Path, Path]:
    rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() == MOUNTAIN_LION_DRAW_SYSTEM_TYPE]
    csv_path = output_dir / "mountain_lion_availability_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys())) if rows else [
        "hunt_code",
        "residency",
        "draw_system_type",
        "algorithm_status",
        "permit_availability_type",
        "permit_type",
        "permit_status",
        "availability_status",
        "season_start",
        "season_end",
        "season_status",
        "unit_name",
        "unit_status",
        "rule_status",
        "p_availability",
        "availability_pct",
    ]
    write_csv(csv_path, rows, fieldnames)
    json_path = output_dir / "mountain_lion_availability_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _write_youth_artifacts(
    output_dir: Path,
    prediction_rows: list[dict[str, object]],
    report: dict[str, object],
) -> tuple[Path, Path]:
    rows = [row for row in prediction_rows if str(row.get("draw_system_type", "")).strip() in YOUTH_DRAW_SYSTEM_TYPES]
    csv_path = output_dir / "youth_draw_predictions_v1.csv"
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys())) if rows else [
        "hunt_code",
        "residency",
        "draw_system_type",
        "algorithm_status",
        "season_dates",
        "season_status",
        "availability_status",
        "p_draw",
        "p_draw_pct",
        "p_preference_draw",
        "p_bonus_pool",
        "p_random_pool",
    ]
    write_csv(csv_path, rows, fieldnames)
    json_path = output_dir / "youth_draw_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return csv_path, json_path


def _replace_rows_by_key(
    base_rows: list[dict[str, object]],
    replacement_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    replacement_keys = {
        (
            str(row.get("hunt_code", "")).strip(),
            str(row.get("residency", "")).strip(),
            str(row.get("points", "")).strip(),
        )
        for row in replacement_rows
    }
    filtered = [
        row
        for row in base_rows
        if (
            str(row.get("hunt_code", "")).strip(),
            str(row.get("residency", "")).strip(),
            str(row.get("points", "")).strip(),
        )
        not in replacement_keys
    ]
    filtered.extend(replacement_rows)
    return filtered


def _replace_rows_by_draw_system_type(
    base_rows: list[dict[str, object]],
    replacement_rows: list[dict[str, object]],
    draw_system_types: set[str],
) -> list[dict[str, object]]:
    filtered = [row for row in base_rows if str(row.get("draw_system_type", "")).strip() not in draw_system_types]
    filtered.extend(replacement_rows)
    return filtered


def _runtime_promotion_family(row: dict[str, object]) -> str:
    draw_system_type = str(row.get("draw_system_type", "")).strip()
    algorithm_status = str(row.get("algorithm_status", "")).strip()
    model_strategy = str(row.get("model_strategy", "")).strip()
    if draw_system_type == SPORTSMAN_DRAW_SYSTEM_TYPE and algorithm_status == "MODELED_SPORTSMAN_DRAW":
        return "SPORTSMAN_RANDOM_ONLY"
    if draw_system_type in YOUTH_DRAW_SYSTEM_TYPES and algorithm_status == "MODELED_RANDOM_ONLY":
        return "YOUTH_GENERAL_ANY_BULL_ELK"
    if draw_system_type == "PREFERENCE_DEDICATED_HUNTER_DEER" and algorithm_status == "MODELED_PREFERENCE":
        return "PREFERENCE_DEDICATED_HUNTER_DEER"
    if draw_system_type == TURKEY_DRAW_SYSTEM_TYPE and algorithm_status == "MODELED_BONUS":
        return TURKEY_DRAW_SYSTEM_TYPE
    if draw_system_type == YOUTH_TURKEY_DRAW_SYSTEM_TYPE and algorithm_status == "MODELED_BONUS":
        return YOUTH_TURKEY_DRAW_SYSTEM_TYPE
    if model_strategy == "preference_dedicated_hunter_deer" and algorithm_status == "MODELED_PREFERENCE":
        return "PREFERENCE_DEDICATED_HUNTER_DEER"
    return ""


def _apply_runtime_promotion_marks(rows: list[dict[str, object]], output_dir: Path) -> dict[str, object]:
    report_rows: list[dict[str, object]] = []
    for row in rows:
        family = _runtime_promotion_family(row)
        if not family:
            row.setdefault("runtime_promotion_family", "")
            row.setdefault("runtime_promotion_status", "")
            row.setdefault("runtime_promotion_decision", "")
            row.setdefault("runtime_promotion_source", "")
            row.setdefault("runtime_promotion_source_report", "")
            row.setdefault("runtime_promotion_note", "")
            continue
        row["runtime_promotion_family"] = family
        row["runtime_promotion_status"] = "PROMOTED_TO_RUNTIME"
        row["runtime_promotion_decision"] = RUNTIME_PROMOTION_DECISION
        source_report = output_dir / PROMOTED_RUNTIME_FAMILY_REPORTS[family]
        source_report_relative = _safe_relative(source_report)
        row["runtime_promotion_source"] = source_report_relative
        row["runtime_promotion_source_report"] = source_report_relative
        row["runtime_promotion_note"] = (
            "Family promoted after zero-pending runtime reconciliation; non-public/reference rows remain excluded."
        )

    for family, source_report_name in PROMOTED_RUNTIME_FAMILY_REPORTS.items():
        family_rows = [row for row in rows if str(row.get("runtime_promotion_family", "")).strip() == family]
        keys = {
            (
                str(row.get("hunt_code", "")).strip(),
                str(row.get("residency", "")).strip(),
                str(row.get("points", "")).strip(),
                str(row.get("draw_system_type", "")).strip(),
            )
            for row in family_rows
        }
        report_rows.append(
            {
                "runtime_promotion_family": family,
                "runtime_promotion_status": "PROMOTED_TO_RUNTIME" if family_rows else "PROMOTION_MISSING_ROWS",
                "row_count": len(family_rows),
                "hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in family_rows if str(row.get("hunt_code", "")).strip()}),
                "duplicate_runtime_key_count": len(family_rows) - len(keys),
                "source_report": _safe_relative(output_dir / source_report_name),
                "promotion_decision": RUNTIME_PROMOTION_DECISION,
            }
        )

    summary = {
        "promotion_decision": RUNTIME_PROMOTION_DECISION,
        "promoted_family_count": len(PROMOTED_RUNTIME_FAMILY_REPORTS),
        "promoted_row_count": sum(int(row["row_count"]) for row in report_rows),
        "families": report_rows,
        "promotion_ready": all(
            row["runtime_promotion_status"] == "PROMOTED_TO_RUNTIME"
            and int(row["row_count"]) > 0
            and int(row["duplicate_runtime_key_count"]) == 0
            for row in report_rows
        ),
        "excluded_from_this_promotion": [
            "MAX_WEIGHTED_SPLIT_PENDING_CHALLENGE_TEST",
            "BLACK_BEAR_PENDING_ROW_RECONCILIATION",
            "CWMU_CONSERVATION_PRIVATE_LAND_REFERENCE_ONLY",
        ],
        "runtime_promotion_columns": [
            "runtime_promotion_family",
            "runtime_promotion_status",
            "runtime_promotion_decision",
            "runtime_promotion_source",
            "runtime_promotion_source_report",
            "runtime_promotion_note",
        ],
        "permit_source_field_contract": "NOT_REQUIRED_FOR_RUNTIME_PROMOTION; permit authority is carried by permits_2026_* fields, public_permits_2026 where applicable, and reason_codes.",
    }
    return summary


def _write_runtime_promotion_artifacts(output_dir: Path, promotion_report: dict[str, object]) -> tuple[Path, Path, Path]:
    csv_path = output_dir / "runtime_family_promotion_report.csv"
    json_path = output_dir / "runtime_family_promotion_report.json"
    md_path = output_dir / "runtime_family_promotion_report.md"
    rows = list(promotion_report.get("families", []))
    write_csv(
        csv_path,
        rows,
        [
            "runtime_promotion_family",
            "runtime_promotion_status",
            "row_count",
            "hunt_code_count",
            "duplicate_runtime_key_count",
            "source_report",
            "promotion_decision",
        ],
    )
    json_path.write_text(json.dumps(promotion_report, indent=2), encoding="utf-8")
    lines = [
        "# Runtime Family Promotion Report",
        "",
        f"- promotion_decision: {promotion_report['promotion_decision']}",
        f"- promotion_ready: {promotion_report['promotion_ready']}",
        f"- promoted_family_count: {promotion_report['promoted_family_count']}",
        f"- promoted_row_count: {promotion_report['promoted_row_count']}",
        f"- permit_source_field_contract: {promotion_report['permit_source_field_contract']}",
        "",
        "| Family | Status | Rows | Hunt codes | Duplicate keys | Source report |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['runtime_promotion_family']} | {row['runtime_promotion_status']} | {row['row_count']} | "
            f"{row['hunt_code_count']} | {row['duplicate_runtime_key_count']} | {row['source_report']} |"
        )
    lines.extend(
        [
            "",
            "## Excluded From This Promotion",
            "",
            *[f"- {item}" for item in promotion_report["excluded_from_this_promotion"]],
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, json_path, md_path


def _remove_no_hunt_code_rows(rows: list[dict[str, object]], source_label: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    kept: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        if str(row.get("hunt_code", "")).strip():
            kept.append(row)
            continue
        item = dict(row)
        item["excluded_from"] = source_label
        item["excluded_row_number"] = index
        item["exclusion_reason"] = "MISSING_HUNT_CODE_NOT_ALLOWED_IN_ENGINE"
        item["reason_codes"] = append_reason_codes(item.get("reason_codes", ""), "MISSING_HUNT_CODE_NOT_ALLOWED_IN_ENGINE")
        excluded.append(item)
    return kept, excluded


def _quota_info(row: dict[str, str]) -> tuple[bool, bool]:
    raw_res = str(row.get("permits_2026_res", "")).strip()
    raw_nr = str(row.get("permits_2026_nr", "")).strip()
    raw_total = str(row.get("permits_2026_total", "")).strip()
    quota_blank = raw_res == "" and raw_nr == "" and raw_total == ""
    total = 0
    for value in (raw_res, raw_nr, raw_total):
        try:
            if value != "":
                total += int(float(value))
        except Exception:
            continue
    return quota_blank, total > 0


def _is_target_bonus_hunt(hunt_type: str) -> bool:
    value = str(hunt_type or "").strip().lower()
    return any(token in value for token in TARGET_HUNT_TOKENS)


def _build_coverage_report(
    db_rows: list[dict[str, str]],
    backtest_rows: list[dict[str, object]],
    prediction_rows: list[dict[str, object]],
    output_dir: Path,
    forecast_year: int,
) -> dict[str, object]:
    forecast_codes = {str(row["hunt_code"]).strip().upper() for row in prediction_rows if str(row.get("hunt_code", "")).strip()}
    backtest_codes = {str(row["hunt_code"]).strip().upper() for row in backtest_rows if str(row.get("hunt_code", "")).strip()}
    db_by_code: dict[str, dict[str, str]] = {}
    for row in db_rows:
        code = str(row.get("hunt_code", "")).strip().upper()
        if code and code not in db_by_code:
            db_by_code[code] = row

    coverage_rows: list[dict[str, object]] = []
    current_db_codes = set(db_by_code.keys())
    coverage_universe = sorted(forecast_codes | backtest_codes | current_db_codes)
    active_forecast_eligible_codes = 0
    forecast_label = str(forecast_year)
    forecast_eligible_field = f"forecast_eligible_{forecast_label}"
    not_active_reason = f"not_active_in_{forecast_label}"
    total_active_key = f"total_active_{forecast_label}_forecast_eligible_hunt_codes"
    count_not_active_key = f"count_excluded_not_active_in_{forecast_label}"

    reason_counts = {
        "included_forecast": 0,
        "not_OIL_LE_PLE": 0,
        not_active_reason: 0,
        "missing_forecast_quota": 0,
        "missing_required_metadata": 0,
        "hunt_code_changed_or_not_crosswalked": 0,
        "other_missing_model_input": 0,
    }

    for code in coverage_universe:
        db_row = db_by_code.get(code)
        in_forecast = code in forecast_codes
        in_backtest = code in backtest_codes
        in_current_db = db_row is not None
        hunt_type = str(db_row.get("hunt_type", "") if db_row else "")
        hunt_name = str(db_row.get("hunt_name", "") if db_row else "")
        species = str(db_row.get("species", "") if db_row else "")
        metadata_ok = bool(code and hunt_type.strip() and hunt_name.strip() and species.strip())
        is_target = _is_target_bonus_hunt(hunt_type) if db_row else False
        quota_blank, has_positive_quota = _quota_info(db_row) if db_row else (False, False)
        forecast_eligible = in_current_db and metadata_ok and is_target and not quota_blank and has_positive_quota
        if forecast_eligible:
            active_forecast_eligible_codes += 1

        if in_forecast:
            reason = "included_forecast"
        elif not in_current_db:
            reason = "hunt_code_changed_or_not_crosswalked"
        elif not metadata_ok:
            reason = "missing_required_metadata"
        elif not is_target:
            reason = "not_OIL_LE_PLE"
        elif quota_blank:
            reason = "missing_forecast_quota"
        elif not has_positive_quota:
            reason = not_active_reason
        else:
            reason = "other_missing_model_input"

        reason_counts[reason] += 1
        coverage_rows.append(
            {
                "hunt_code": code,
                "in_forecast": in_forecast,
                "in_backtest": in_backtest,
                "in_current_database": in_current_db,
                forecast_eligible_field: forecast_eligible,
                "exclusion_reason": reason,
                "hunt_type": hunt_type,
                "species": species,
                "hunt_name": hunt_name,
                "permits_2026_res": "" if not db_row else db_row.get("permits_2026_res", ""),
                "permits_2026_nr": "" if not db_row else db_row.get("permits_2026_nr", ""),
                "permits_2026_total": "" if not db_row else db_row.get("permits_2026_total", ""),
                "permit_allotment_2026_res": "" if not db_row else db_row.get("permit_allotment_2026_res", ""),
                "permit_allotment_2026_nr": "" if not db_row else db_row.get("permit_allotment_2026_nr", ""),
                "permit_allotment_2026_total": "" if not db_row else db_row.get("permit_allotment_2026_total", ""),
                "permit_allotment_2026_source": "" if not db_row else db_row.get("permit_allotment_2026_source", ""),
                "permit_allotment_2026_source_file": "" if not db_row else db_row.get("permit_allotment_2026_source_file", ""),
                "permit_allotment_2026_status": "" if not db_row else db_row.get("permit_allotment_2026_status", ""),
            }
        )

    coverage_csv_path = output_dir / "predictive_coverage_report.csv"
    write_csv(
        coverage_csv_path,
        coverage_rows,
        [
            "hunt_code",
            "in_forecast",
            "in_backtest",
            "in_current_database",
            forecast_eligible_field,
            "exclusion_reason",
            "hunt_type",
            "species",
            "hunt_name",
            "permits_2026_res",
            "permits_2026_nr",
            "permits_2026_total",
            "permit_allotment_2026_res",
            "permit_allotment_2026_nr",
            "permit_allotment_2026_total",
            "permit_allotment_2026_source",
            "permit_allotment_2026_source_file",
            "permit_allotment_2026_status",
        ],
    )

    coverage_report = {
        "total_historical_backtest_hunt_codes": len(backtest_codes),
        "total_forecast_hunt_codes": len(forecast_codes),
        total_active_key: active_forecast_eligible_codes,
        "count_excluded_not_OIL_LE_PLE": reason_counts["not_OIL_LE_PLE"],
        count_not_active_key: reason_counts[not_active_reason],
        "count_excluded_missing_forecast_quota": reason_counts["missing_forecast_quota"],
        "count_excluded_missing_required_metadata": reason_counts["missing_required_metadata"],
        "count_excluded_hunt_code_changed_or_not_crosswalked": reason_counts["hunt_code_changed_or_not_crosswalked"],
        "count_excluded_other_reason": reason_counts["other_missing_model_input"],
        "count_excluded_missing_model_input_or_not_in_predictive_draft": reason_counts["other_missing_model_input"],
        "forecast_codes_match_active_eligible_universe": len(forecast_codes) == active_forecast_eligible_codes,
        "active_eligible_codes_missing_from_forecast": max(0, active_forecast_eligible_codes - len(forecast_codes)),
        "forecast_codes_outside_active_eligible_universe": max(0, len(forecast_codes) - active_forecast_eligible_codes),
        "reason_counts": reason_counts,
        "source_csv": _safe_relative(coverage_csv_path),
    }
    coverage_json_path = output_dir / "predictive_coverage_report.json"
    coverage_json_path.write_text(json.dumps(coverage_report, indent=2), encoding="utf-8")
    return {
        "json_path": coverage_json_path,
        "csv_path": coverage_csv_path,
        "report": coverage_report,
    }


def _eb3024_regression(truth_rows: list[dict[str, str]]) -> dict[str, object]:
    permits: dict[tuple[str, str], dict[str, int]] = {}
    points: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in truth_rows:
        if str(row.get("hunt_code", "")).strip().upper() != "EB3024":
            continue
        year = str(row.get("year") or row.get("actual_draw_year") or "").strip()
        residency = str(row.get("residency", "")).strip()
        points_text = str(row.get("points", "")).strip()
        permit_key = (year, residency)
        point_key = (year, residency, points_text)
        permits.setdefault(permit_key, {"public": 0, "bonus": 0, "regular": 0})
        points.setdefault(point_key, {"eligible": 0, "bonus": 0, "regular": 0})
        permits[permit_key]["public"] += int(float(row.get("total_permits") or 0))
        permits[permit_key]["bonus"] += int(float(row.get("bonus_permits") or 0))
        permits[permit_key]["regular"] += int(float(row.get("regular_permits") or 0))
        if points_text:
            points[point_key]["eligible"] += int(float(row.get("eligible_applicants") or 0))
            points[point_key]["bonus"] += int(float(row.get("bonus_permits") or 0))
            points[point_key]["regular"] += int(float(row.get("regular_permits") or 0))

    required_permit_keys = [("2024", "Resident"), ("2025", "Resident"), ("2024", "Nonresident"), ("2025", "Nonresident")]
    required_point_keys = [("2024", "Resident", "28"), ("2025", "Resident", "29")]
    missing_permit_keys = [key for key in required_permit_keys if key not in permits]
    missing_point_keys = [key for key in required_point_keys if key not in points]
    if missing_permit_keys or missing_point_keys:
        return {
            "pass": False,
            "skipped": True,
            "reason": "EB3024 regression source rows were not present in the active truth input.",
            "missing_permit_keys": ["/".join(key) for key in missing_permit_keys],
            "missing_point_keys": ["/".join(key) for key in missing_point_keys],
            "available_permit_keys": ["/".join(key) for key in sorted(permits)],
            "available_point_keys": ["/".join(key) for key in sorted(points)],
        }

    unsuccessful_2024_28 = points[("2024", "Resident", "28")]["eligible"] - points[("2024", "Resident", "28")]["bonus"] - points[("2024", "Resident", "28")]["regular"]
    retention = points[("2025", "Resident", "29")]["eligible"] / max(1, unsuccessful_2024_28)
    return {
        "pass": (
            permits[("2024", "Resident")] == {"public": 7, "bonus": 4, "regular": 3}
            and permits[("2025", "Resident")] == {"public": 9, "bonus": 5, "regular": 4}
            and permits[("2024", "Nonresident")] == {"public": 1, "bonus": 0, "regular": 1}
            and permits[("2025", "Nonresident")] == {"public": 1, "bonus": 0, "regular": 1}
            and unsuccessful_2024_28 == 6
            and round(retention, 6) == 0.833333
        ),
        "resident_2024": permits[("2024", "Resident")],
        "resident_2025": permits[("2025", "Resident")],
        "nonresident_2024": permits[("2024", "Nonresident")],
        "nonresident_2025": permits[("2025", "Nonresident")],
        "unsuccessful_2024_28": unsuccessful_2024_28,
        "retention_2024_28_to_2025_29": round(retention, 6),
    }


def _ui_probability_checks() -> dict[str, object]:
    text = (REPO / "hunt-research.js").read_text(encoding="utf-8")
    precedence_ok = all(
        token in text
        for token in [
            "function selectDrawOddsPercent(row)",
            "display_odds_pct",
            "p_draw_mean",
            "p_bonus_pool_pct",
            "odds_2026_projected",
            "max_pool_projection_2026",
            "random_draw_odds_2026",
            "random_draw_projection_2026",
        ]
    )
    max_pool_force_absent = "if (row.status === 'MAX POOL') return 100;" not in text and 'status == "MAX POOL"' not in text
    return {
        "precedence_ok": precedence_ok,
        "max_pool_force_100_absent": max_pool_force_absent,
    }


def _anomaly_counts(prediction_rows: list[dict[str, object]], backtest_rows: list[dict[str, object]]) -> dict[str, object]:
    prediction_anomalies = {
        "p_draw_outside_0_1": 0,
        "p_draw_pct_outside_0_100": 0,
        "p_draw_pct_null": 0,
        "public_permits_gt_0_but_p_draw_null": 0,
        "status_max_pool_and_p_draw_pct_100": 0,
        "status_max_pool_and_p_draw_pct_lt_100": 0,
        "random_permits_gt_0_and_p_random_pool_0": 0,
        "duplicate_key_count": _duplicate_count(prediction_rows, ["hunt_code", "residency", "points", "draw_system_type"]),
    }
    for row in prediction_rows:
        p_draw = None
        p_draw_pct = None
        p_random_pool = None
        public_permits = 0
        random_permits = 0
        try:
            p_draw = float(str(row.get("p_draw", "")).strip()) if str(row.get("p_draw", "")).strip() != "" else None
        except Exception:
            p_draw = None
        try:
            p_draw_pct = float(str(row.get("p_draw_pct", "")).strip()) if str(row.get("p_draw_pct", "")).strip() != "" else None
        except Exception:
            p_draw_pct = None
        try:
            p_random_pool = float(str(row.get("p_random_pool", "")).strip()) if str(row.get("p_random_pool", "")).strip() != "" else None
        except Exception:
            p_random_pool = None
        try:
            public_permits = int(float(row.get("public_permits_2026") or 0))
            random_permits = int(float(row.get("random_permits_2026") or 0))
        except Exception:
            pass
        if p_draw is not None and not (0.0 <= p_draw <= 1.0):
            prediction_anomalies["p_draw_outside_0_1"] += 1
        if p_draw_pct is None:
            prediction_anomalies["p_draw_pct_null"] += 1
        elif not (0.0 <= p_draw_pct <= 100.0):
            prediction_anomalies["p_draw_pct_outside_0_100"] += 1
        if public_permits > 0 and p_draw is None:
            prediction_anomalies["public_permits_gt_0_but_p_draw_null"] += 1
        if str(row.get("status", "")).strip().upper() == "MAX POOL":
            if p_draw_pct == 100.0:
                prediction_anomalies["status_max_pool_and_p_draw_pct_100"] += 1
            if p_draw_pct is not None and p_draw_pct < 100.0:
                prediction_anomalies["status_max_pool_and_p_draw_pct_lt_100"] += 1
        if random_permits > 0 and p_random_pool == 0.0:
            prediction_anomalies["random_permits_gt_0_and_p_random_pool_0"] += 1

    backtest_anomalies = {
        "calibration_error_by_probability_bucket_null": sum(
            1 for row in backtest_rows if str(row.get("calibration_error_by_probability_bucket", "")).strip() == ""
        ),
        "brier_score_by_point_level_null": sum(1 for row in backtest_rows if str(row.get("brier_score_by_point_level", "")).strip() == ""),
        "guaranteed_at_error_null": sum(1 for row in backtest_rows if str(row.get("guaranteed_at_error", "")).strip() == ""),
        "year_transitions_tested": sorted({str(row.get("year_transition", "")).strip() for row in backtest_rows if str(row.get("year_transition", "")).strip()}),
        "distinct_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in backtest_rows if str(row.get("hunt_code", "")).strip()}),
        "distinct_residency_count": len({str(row.get("residency", "")).strip() for row in backtest_rows if str(row.get("residency", "")).strip()}),
    }
    return {
        "prediction": prediction_anomalies,
        "backtest": backtest_anomalies,
    }


def _build_manifest(
    output_dir: Path,
    command_used: str,
    forecast_year: int,
    history_years: list[int],
    prediction_rows: list[dict[str, object]],
    backtest_rows: list[dict[str, object]],
    successor_rows: list[dict[str, object]],
    coverage_report: dict[str, object],
    eb3024: dict[str, object],
    ui_checks: dict[str, object],
    runtime_truth_copy: Path,
    prediction_input: Path,
) -> Path:
    output_files = {
        "ml_draw_predictions_v1.csv": output_dir / "ml_draw_predictions_v1.csv",
        "ml_draw_predictions_v1_report.json": output_dir / "ml_draw_predictions_v1_report.json",
        "backtest_utah_bonus_draw.csv": output_dir / "backtest_utah_bonus_draw.csv",
        "backtest_utah_bonus_draw_report.json": output_dir / "backtest_utah_bonus_draw_report.json",
        "draw_reality_engine_predictive_v2.csv": output_dir / "draw_reality_engine_predictive_v2.csv",
        "draw_reality_engine_v2.csv": runtime_truth_copy,
        "predictive_coverage_report.json": output_dir / "predictive_coverage_report.json",
        "predictive_coverage_report.csv": output_dir / "predictive_coverage_report.csv",
        "dedicated_hunter_predictions_v1.csv": output_dir / "dedicated_hunter_predictions_v1.csv",
        "dedicated_hunter_report.json": output_dir / "dedicated_hunter_report.json",
        "phase4_antlerless_validation_inventory.csv": output_dir / "phase4_antlerless_validation_inventory.csv",
        "phase4_antlerless_validation_inventory.json": output_dir / "phase4_antlerless_validation_inventory.json",
        "phase6_bonus_special_predictions_v1.csv": output_dir / "phase6_bonus_special_predictions_v1.csv",
        "phase6_bonus_special_report.json": output_dir / "phase6_bonus_special_report.json",
        "turkey_bonus_predictions_v1.csv": output_dir / "turkey_bonus_predictions_v1.csv",
        "turkey_bonus_report.json": output_dir / "turkey_bonus_report.json",
        "youth_turkey_predictions_v1.csv": output_dir / "youth_turkey_predictions_v1.csv",
        "youth_turkey_report.json": output_dir / "youth_turkey_report.json",
        "bear_draw_predictions_v1.csv": output_dir / "bear_draw_predictions_v1.csv",
        "bear_draw_report.json": output_dir / "bear_draw_report.json",
        "bear_predictions_v1.csv": output_dir / "bear_predictions_v1.csv",
        "bear_report.json": output_dir / "bear_report.json",
        "bear_draw_odds_source_audit.csv": output_dir / "bear_draw_odds_source_audit.csv",
        "bear_draw_odds_source_audit.json": output_dir / "bear_draw_odds_source_audit.json",
        "sportsman_permit_predictions_v1.csv": output_dir / "sportsman_permit_predictions_v1.csv",
        "sportsman_permit_report.json": output_dir / "sportsman_permit_report.json",
        "private_lands_antlerless_elk_predictions_v1.csv": output_dir / "private_lands_antlerless_elk_predictions_v1.csv",
        "private_lands_antlerless_elk_allocations_v1.csv": output_dir / "private_lands_antlerless_elk_allocations_v1.csv",
        "private_lands_antlerless_elk_report.json": output_dir / "private_lands_antlerless_elk_report.json",
        "mountain_lion_availability_predictions_v1.csv": output_dir / "mountain_lion_availability_predictions_v1.csv",
        "mountain_lion_availability_report.json": output_dir / "mountain_lion_availability_report.json",
    }
    anomalies = _anomaly_counts(prediction_rows, backtest_rows)
    manifest = {
        "model_version": MODEL_VERSION,
        "rule_version": RULE_VERSION,
        "forecast_year": forecast_year,
        "source_years": history_years,
        "command_used": command_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_files": {name: _safe_relative(path) for name, path in output_files.items()},
        "output_row_counts": {
            "ml_draw_predictions_v1.csv": len(prediction_rows),
            "backtest_utah_bonus_draw.csv": len(backtest_rows),
            "draw_reality_engine_predictive_v2.csv": len(successor_rows),
            "draw_reality_engine_v2.csv": len(read_csv(runtime_truth_copy)),
        },
        "duplicate_key_counts": {
            "ml_draw_predictions_v1.csv": _duplicate_count(prediction_rows, ["hunt_code", "residency", "points", "draw_system_type"]),
            "draw_reality_engine_predictive_v2.csv": _duplicate_count(successor_rows, ["hunt_code", "residency", "points", "draw_system_type"]),
        },
        "p_draw_non_null_count": _nonnull(prediction_rows, "p_draw"),
        "p_draw_pct_non_null_count": _nonnull(prediction_rows, "p_draw_pct"),
        "calibration_metric_non_null_count": _nonnull(backtest_rows, "calibration_error_by_probability_bucket"),
        "EB3024_regression_result": eb3024,
        "one_permit_random_only_result": {
            "pass": split_utah_bonus_permits(1).maxPointPermits == 0 and split_utah_bonus_permits(1).randomPermits == 1,
        },
        "MAX_POOL_safety_result": {
            "pass": ui_checks["max_pool_force_100_absent"],
        },
        "UI_precedence_result": ui_checks,
        "coverage_report_summary": coverage_report,
        "anomaly_checks": anomalies,
        "source_files_used": {
            _safe_relative(TRUTH_PATH): _sha256_file(TRUTH_PATH),
            _safe_relative(DATABASE_2026_PATH): _sha256_file(DATABASE_2026_PATH),
            _safe_relative(runtime_truth_copy): _sha256_file(runtime_truth_copy),
            _safe_relative(prediction_input): _sha256_file(prediction_input),
            "hunt-research.js": _sha256_file(REPO / "hunt-research.js"),
            "config.js": _sha256_file(REPO / "config.js"),
        },
    }
    manifest_path = output_dir / "utah_bonus_predictive_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


MIXED_COMPONENT_FIELDS = (
    "p_prior_year_baseline",
    "p_quota_adjusted",
    "p_rollover_adjusted",
    "p_harvest_adjusted",
)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _canonical_probability(row: dict[str, object]) -> float | None:
    for field in ("p_draw", "p_draw_mean", "p_preference_draw", "p_sportsman_draw"):
        value = _to_float(row.get(field))
        if value is not None:
            return max(0.0, min(1.0, value))
    return None


def _format_combined_odds(probability: float | None) -> str:
    if probability is None or probability <= 0.0:
        return ""
    pct = probability * 100.0
    return f"~1 in {1.0 / probability:.1f} or {pct:.1f}%"


def _normalize_merged_surface_contract(
    rows: list[dict[str, object]],
    *,
    history_years: list[int],
) -> None:
    source_years_used = ",".join(str(year) for year in history_years)
    earliest_source_year = str(min(history_years))
    latest_source_year = str(max(history_years))
    source_year_count = str(len(history_years))
    non_probability_statuses = {
        "MODELED_AVAILABILITY",
        "MODELED_ALLOCATION",
        "IN_SCOPE_MODEL_PENDING",
        "EXCLUDED_NOT_PREDICTIVE_DRAW",
        "OUT_OF_SCOPE_NON_TARGET",
        "UNKNOWN_TARGET_NEEDS_REVIEW",
    }

    for row in rows:
        if not _clean_text(row.get("source_years_used")):
            row["source_years_used"] = source_years_used
        if not _clean_text(row.get("source_year_count")):
            row["source_year_count"] = source_year_count
        if not _clean_text(row.get("earliest_source_year")):
            row["earliest_source_year"] = earliest_source_year
        if not _clean_text(row.get("latest_source_year")):
            row["latest_source_year"] = latest_source_year

        if _clean_text(row.get("algorithm_status")) in non_probability_statuses:
            for field in MIXED_COMPONENT_FIELDS:
                row[field] = ""
            continue

        probability_value = _canonical_probability(row)
        probability = "" if probability_value is None else f"{probability_value:.6f}"
        if not probability:
            continue
        for field in MIXED_COMPONENT_FIELDS:
            if not _clean_text(row.get(field)):
                row[field] = probability
        if probability_value and probability_value > 0.0 and not _clean_text(row.get("display_odds_text")):
            row["display_odds_text"] = _format_combined_odds(probability_value)


def materialize_outputs(
    output_dir: Path,
    forecast_year: int,
    history_years: list[int],
    command_used: str,
    run_upstream: bool = True,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_paths = run_official_forecast_build(forecast_year, RUNTIME_DRAFT_DIR) if run_upstream else {
        "prediction_rows": RUNTIME_DRAFT_DIR / f"predictive_bonus_engine_{forecast_year}.predictions.csv",
        "materialized_rows": RUNTIME_DRAFT_DIR / f"predictive_bonus_engine_{forecast_year}.materialized.csv",
        "audit_rows": RUNTIME_DRAFT_DIR / f"predictive_bonus_engine_{forecast_year}.audit.csv",
    }

    truth_rows = expand_collapsed_truth_rows_for_engine(read_csv(TRUTH_PATH))
    permits, ladders, meta = build_truth_indexes(truth_rows)
    above_index = build_above_index(ladders)

    ml_input_rows = read_csv(runtime_paths["materialized_rows"])
    source_years_used = ",".join(str(year) for year in history_years)
    prediction_rows, successor_rows = materialize_prediction_rows(
        ml_rows=ml_input_rows,
        permits=permits,
        ladders=ladders,
        above_index=above_index,
        meta=meta,
        forecast_year=forecast_year,
        source_years_used=source_years_used,
        earliest_source_year=min(history_years),
        latest_source_year=max(history_years),
    )

    db_rows = apply_current_year_allotments_to_rows(read_csv(DATABASE_2026_PATH))
    preference_general_deer_rows = build_preference_general_deer_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    preference_antlerless_rows = build_preference_antlerless_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    preference_dedicated_hunter_rows = build_preference_dedicated_hunter_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    phase6_bonus_special_rows, phase6_bonus_special_report = build_phase6_bonus_special_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    turkey_bonus_rows, turkey_bonus_report = build_turkey_bonus_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    youth_turkey_rows, youth_turkey_report = build_youth_turkey_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    bear_bonus_rows, bear_bonus_report = build_bear_bonus_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    bear_draw_audit_rows, bear_draw_audit_summary = build_bear_draw_odds_source_audit(
        db_rows=db_rows,
    )
    sportsman_rows, sportsman_report = build_sportsman_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    private_lands_rows, private_lands_report = build_private_lands_antlerless_elk_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    youth_rows, youth_report = build_youth_predictions(
        truth_rows=truth_rows,
        db_rows=db_rows,
        forecast_year=forecast_year,
        history_years=history_years,
    )
    mountain_lion_rows, mountain_lion_report = build_mountain_lion_availability_predictions(
        forecast_year=forecast_year,
        history_years=history_years,
    )
    if preference_general_deer_rows:
        preference_general_deer_rows = [sanitize_modeled_probability_fields(dict(row)) for row in preference_general_deer_rows]
        prediction_rows = _replace_rows_by_key(prediction_rows, preference_general_deer_rows)
        successor_rows = _replace_rows_by_key(successor_rows, [dict(row) for row in preference_general_deer_rows])
    if preference_antlerless_rows:
        preference_antlerless_rows = [sanitize_modeled_probability_fields(dict(row)) for row in preference_antlerless_rows]
        prediction_rows = _replace_rows_by_key(prediction_rows, preference_antlerless_rows)
        successor_rows = _replace_rows_by_key(successor_rows, [dict(row) for row in preference_antlerless_rows])
    if preference_dedicated_hunter_rows:
        preference_dedicated_hunter_rows = [sanitize_modeled_probability_fields(dict(row)) for row in preference_dedicated_hunter_rows]
        prediction_rows = _replace_rows_by_key(prediction_rows, preference_dedicated_hunter_rows)
        successor_rows = _replace_rows_by_key(successor_rows, [dict(row) for row in preference_dedicated_hunter_rows])
    if phase6_bonus_special_rows:
        phase6_bonus_special_rows = [sanitize_modeled_probability_fields(dict(row)) for row in phase6_bonus_special_rows]
        prediction_rows = _replace_rows_by_key(prediction_rows, phase6_bonus_special_rows)
        successor_rows = _replace_rows_by_key(successor_rows, [dict(row) for row in phase6_bonus_special_rows])
    if turkey_bonus_rows:
        turkey_bonus_rows = [sanitize_modeled_probability_fields(dict(row)) for row in turkey_bonus_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, turkey_bonus_rows, {TURKEY_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in turkey_bonus_rows], {TURKEY_DRAW_SYSTEM_TYPE})
    if youth_turkey_rows:
        youth_turkey_rows = [sanitize_modeled_probability_fields(dict(row)) for row in youth_turkey_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, youth_turkey_rows, {YOUTH_TURKEY_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in youth_turkey_rows], {YOUTH_TURKEY_DRAW_SYSTEM_TYPE})
    if bear_bonus_rows:
        bear_bonus_rows = [sanitize_modeled_probability_fields(dict(row)) for row in bear_bonus_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, bear_bonus_rows, {BEAR_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in bear_bonus_rows], {BEAR_DRAW_SYSTEM_TYPE})
    if sportsman_rows:
        sportsman_rows = [sanitize_modeled_probability_fields(dict(row)) for row in sportsman_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, sportsman_rows, {SPORTSMAN_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in sportsman_rows], {SPORTSMAN_DRAW_SYSTEM_TYPE})
    if private_lands_rows:
        private_lands_rows = [sanitize_modeled_probability_fields(dict(row)) for row in private_lands_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, private_lands_rows, {PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in private_lands_rows], {PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE})
    if youth_rows:
        youth_rows = [sanitize_modeled_probability_fields(dict(row)) for row in youth_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, youth_rows, set(YOUTH_DRAW_SYSTEM_TYPES))
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in youth_rows], set(YOUTH_DRAW_SYSTEM_TYPES))
    if mountain_lion_rows:
        mountain_lion_rows = [sanitize_modeled_probability_fields(dict(row)) for row in mountain_lion_rows]
        prediction_rows = _replace_rows_by_draw_system_type(prediction_rows, mountain_lion_rows, {MOUNTAIN_LION_DRAW_SYSTEM_TYPE})
        successor_rows = _replace_rows_by_draw_system_type(successor_rows, [dict(row) for row in mountain_lion_rows], {MOUNTAIN_LION_DRAW_SYSTEM_TYPE})
    if preference_general_deer_rows or preference_antlerless_rows or preference_dedicated_hunter_rows or phase6_bonus_special_rows or turkey_bonus_rows or youth_turkey_rows or bear_bonus_rows or sportsman_rows or private_lands_rows or youth_rows or mountain_lion_rows:
        _normalize_merged_surface_contract(prediction_rows, history_years=history_years)
        _normalize_merged_surface_contract(successor_rows, history_years=history_years)
        prediction_rows.sort(key=lambda row: (str(row.get("hunt_code", "")), str(row.get("residency", "")), int(float(str(row.get("points", 0)) or 0)), str(row.get("draw_system_type", ""))))
        successor_rows.sort(key=lambda row: (str(row.get("hunt_code", "")), str(row.get("residency", "")), int(float(str(row.get("points", 0)) or 0)), str(row.get("draw_system_type", ""))))

    promotion_report = _apply_runtime_promotion_marks(prediction_rows, output_dir)
    _apply_runtime_promotion_marks(successor_rows, output_dir)

    prediction_fields = [
        "model_version",
        "rule_version",
        "year",
        "forecast_year",
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "hunt_class",
        "residency",
        "points",
        "draw_pool",
        "draw_design",
        "draw_method",
        "point_system",
        "public_permits_2025",
        "public_permits_2026",
        "eligible_applicants",
        "projected_applicants",
        "projected_applicants_source",
        "projected_applicants_2026",
        "projected_applicants_2026_source",
        "max_point_permits_2025",
        "max_point_permits_2026",
        "random_permits_2025",
        "random_permits_2026",
        "guaranteed_at_2025",
        "guaranteed_at_2026",
        "applicants_above",
        "applicants_at_level",
        "probability_applicant_count",
        "p_prior_year_baseline",
        "p_quota_adjusted",
        "p_rollover_adjusted",
        "p_harvest_adjusted",
        "p_draw_mean",
        "p_draw_p10",
        "p_draw_p50",
        "p_draw_p90",
        "p_max_pool_mean",
        "p_random_mean",
        "p_preference_draw",
        "p_bonus_pool",
        "p_random_pool",
        "p_draw",
        "p_bonus_pool_pct",
        "p_random_pool_pct",
        "p_draw_pct",
        "display_odds_text",
        "random_draw_odds_2026",
        "gap",
        "delta_gap",
        "status",
        "point_pool_zone",
        "trend",
        "draw_outlook",
        "quota_source_status",
        "quota_source_year",
        "quota_source_file",
        "quota_2026_total",
        "quota_2026_max_pool",
        "quota_2026_random_pool",
        "permits_2026_res",
        "permits_2026_nr",
        "permits_2026_total",
        "permit_allotment_2026_res",
        "permit_allotment_2026_nr",
        "permit_allotment_2026_total",
        "permit_allotment_2026_source",
        "permit_allotment_2026_source_file",
        "permit_allotment_2026_status",
        "projected_2026_max_cutoff_point",
        "projected_2026_random_pool_start_point",
        "is_2026_max_point_pool",
        "is_2026_mixed_cutoff",
        "is_2026_random_pool",
        "data_cutoff_date",
        "reason_codes",
        "classification_status",
        "applicant_rollover_source_year",
        "retention_rate_raw",
        "retention_rate_smoothed",
        "rollover_rule",
        "rollover_cutoff_structure",
        "rollover_mixed_cutoff_point",
        "rollover_anchor_next_point",
        "structure_retention_rate_raw",
        "structure_retention_rate_smoothed",
        "structure_retention_prior",
        "structure_retention_matched_years",
        "structure_retention_unsuccessful_total",
        "forecast_applicants_at_level",
        "forecast_applicants_above",
        "rolled_forward_total_applicants",
        "source_years_used",
        "source_year_count",
        "latest_source_year",
        "earliest_source_year",
        "source_dataset",
        "engine_family",
        "model_strategy",
        "runtime_promotion_family",
        "runtime_promotion_status",
        "runtime_promotion_decision",
        "runtime_promotion_source",
        "runtime_promotion_source_report",
        "runtime_promotion_note",
        "preference_model_valid",
        "preference_model_note",
        "bonus_special_valid",
        "bonus_special_note",
        "turkey_bonus_valid",
        "turkey_bonus_note",
        "youth_general_any_bull_elk_valid",
        "youth_general_any_bull_elk_note",
        "bear_bonus_valid",
        "bear_bonus_note",
        "sportsman_valid",
        "sportsman_model_note",
        "weapon",
        "bear_draw_subtype",
        "history_hunt_code",
        "crosswalk_status",
        "permit_availability_type",
        "acquisition_method",
        "trapping_acquisition_method",
        "public_draw_odds_eligible",
        "modeled_probability_allowed",
        "exclusion_reason",
        "permit_type",
        "permit_status",
        "availability_status",
        "availability_reason",
        "probability_model",
        "harvest_objective_unit_count",
        "harvest_objective_take_quota",
        "harvest_objective_remaining_quota",
        "harvest_objective_status",
        "p_availability",
        "availability_pct",
        "closure_risk",
        "sellout_risk",
        "sellout_or_closure_risk",
        "sportsman_species",
        "sportsman_draw_design",
        "sportsman_random_only",
        "sportsman_split_draw",
        "sportsman_resident_only",
        "sportsman_source_year",
        "sportsman_permit_count",
        "sportsman_nonresident_quota",
        "sportsman_applicants",
        "sportsman_odds_text",
        "sportsman_odds_denominator",
        "sportsman_source_file",
        "sportsman_residency_scope",
        "p_sportsman_draw",
        "private_lands_allocation_valid",
        "private_lands_allocation_note",
        "private_lands_capped_permit_valid",
        "private_lands_capped_permit_note",
        "capped_permit_count",
        "acquisition_method",
        "permits_allotted",
        "permits_remaining",
        "permits_sold",
        "permits_sold_or_used",
        "allocation_status",
        "capped_permit_status",
        "sale_date",
        "unit",
        "season_dates",
        "private_land_only_flag",
        "season_start",
        "season_end",
        "season_status",
        "unit_name",
        "unit_status",
        "closure_reason",
        "rule_status",
        "data_quality_flags",
        "draw_system_type",
        "algorithm_status",
        "target_scope",
        "modeled_by_engine",
        "reason",
        "draw_design_contract_flags",
    ]
    prediction_rows, excluded_prediction_no_code_rows = _remove_no_hunt_code_rows(prediction_rows, "ml_draw_predictions_v1")
    successor_rows, excluded_successor_no_code_rows = _remove_no_hunt_code_rows(successor_rows, "draw_reality_engine_predictive_v2")
    excluded_no_code_rows = excluded_prediction_no_code_rows + excluded_successor_no_code_rows
    excluded_no_code_fields = list(dict.fromkeys(
        ["excluded_from", "excluded_row_number", "exclusion_reason", "hunt_code", "hunt_name", "species", "draw_system_type", "algorithm_status", "model_strategy", "reason_codes"]
        + [key for row in excluded_no_code_rows for key in row.keys()]
    ))
    excluded_no_code_path = output_dir / "hunt_code_reconciliation_required_rows.csv"
    write_csv(excluded_no_code_path, excluded_no_code_rows, excluded_no_code_fields)

    ml_predictions_path = output_dir / "ml_draw_predictions_v1.csv"
    write_csv(ml_predictions_path, prediction_rows, prediction_fields)

    report = build_report(prediction_rows, forecast_year, history_years, runtime_paths["materialized_rows"], command_used)
    report["hunt_code_reconciliation_required_rows"] = len(excluded_no_code_rows)
    report["hunt_code_reconciliation_required_report"] = _safe_relative(excluded_no_code_path)
    ml_report_path = output_dir / "ml_draw_predictions_v1_report.json"
    ml_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    successor_path = output_dir / "draw_reality_engine_predictive_v2.csv"
    successor_fields = list(dict.fromkeys(key for row in successor_rows for key in row.keys())) if successor_rows else []
    write_csv(successor_path, successor_rows, successor_fields)

    dedicated_hunter_csv_path, dedicated_hunter_report_path = _write_dedicated_hunter_artifacts(output_dir, prediction_rows, forecast_year, history_years)
    phase4_inventory_csv_path, phase4_inventory_json_path = _write_phase4_antlerless_inventory(output_dir, prediction_rows, forecast_year, history_years)
    phase6_bonus_csv_path, phase6_bonus_json_path = _write_phase6_bonus_special_artifacts(output_dir, prediction_rows, phase6_bonus_special_report)
    turkey_bonus_csv_path, turkey_bonus_json_path = _write_turkey_bonus_artifacts(output_dir, prediction_rows, turkey_bonus_report)
    youth_turkey_csv_path, youth_turkey_json_path = _write_youth_turkey_artifacts(output_dir, prediction_rows, youth_turkey_report)
    bear_bonus_csv_path, bear_bonus_json_path = _write_bear_bonus_artifacts(output_dir, prediction_rows, bear_bonus_report)
    bear_draw_audit_csv_path, bear_draw_audit_json_path = _write_bear_draw_odds_source_audit_artifacts(
        output_dir,
        bear_draw_audit_rows,
        bear_draw_audit_summary,
    )
    sportsman_csv_path, sportsman_json_path = _write_sportsman_artifacts(output_dir, sportsman_rows, sportsman_report)
    private_lands_csv_path, private_lands_json_path = _write_private_lands_antlerless_elk_artifacts(output_dir, private_lands_rows, private_lands_report)
    youth_csv_path, youth_json_path = _write_youth_artifacts(output_dir, prediction_rows, youth_report)
    mountain_lion_csv_path, mountain_lion_json_path = _write_mountain_lion_artifacts(output_dir, prediction_rows, mountain_lion_report)
    promotion_csv_path, promotion_json_path, promotion_md_path = _write_runtime_promotion_artifacts(output_dir, promotion_report)

    backtest_rows = build_backtest_rows(permits, ladders, lambda public_permits: (split_utah_bonus_permits(public_permits).maxPointPermits, split_utah_bonus_permits(public_permits).randomPermits))
    backtest_fields = [
        "from_year",
        "to_year",
        "year_transition",
        "hunt_code",
        "residency",
        "mean_absolute_error_applicants_at_level",
        "mean_absolute_error_applicants_above",
        "bonus_pool_cutoff_error",
        "guaranteed_at_error",
        "quota_split_error",
        "brier_score_by_point_level",
        "calibration_error_by_probability_bucket",
    ]
    backtest_csv_path = output_dir / "backtest_utah_bonus_draw.csv"
    write_csv(backtest_csv_path, backtest_rows, backtest_fields)

    backtest_report = {
        "rows": len(backtest_rows),
        "year_transitions_tested": sorted({row["year_transition"] for row in backtest_rows}),
        "distinct_hunt_code": len({row["hunt_code"] for row in backtest_rows}),
        "distinct_residency": len({row["residency"] for row in backtest_rows}),
        "nonnull_counts": {
            "mean_absolute_error_applicants_at_level": sum(1 for row in backtest_rows if str(row["mean_absolute_error_applicants_at_level"]).strip() != ""),
            "mean_absolute_error_applicants_above": sum(1 for row in backtest_rows if str(row["mean_absolute_error_applicants_above"]).strip() != ""),
            "bonus_pool_cutoff_error": sum(1 for row in backtest_rows if str(row["bonus_pool_cutoff_error"]).strip() != ""),
            "guaranteed_at_error": sum(1 for row in backtest_rows if str(row["guaranteed_at_error"]).strip() != ""),
            "quota_split_error": sum(1 for row in backtest_rows if str(row["quota_split_error"]).strip() != ""),
            "brier_score_by_point_level": sum(1 for row in backtest_rows if str(row["brier_score_by_point_level"]).strip() != ""),
            "calibration_error_by_probability_bucket": sum(
                1 for row in backtest_rows if str(row["calibration_error_by_probability_bucket"]).strip() != ""
            ),
        },
    }
    backtest_report_path = output_dir / "backtest_utah_bonus_draw_report.json"
    backtest_report_path.write_text(json.dumps(backtest_report, indent=2), encoding="utf-8")

    runtime_truth_source = RUNTIME_DRAFT_DIR / "draw_reality_engine_v2.csv"
    runtime_truth_copy = output_dir / "draw_reality_engine_v2.csv"
    shutil.copy2(runtime_truth_source, runtime_truth_copy)

    coverage_artifacts = _build_coverage_report(db_rows, backtest_rows, prediction_rows, output_dir, forecast_year)
    eb3024 = _eb3024_regression(truth_rows)
    ui_checks = _ui_probability_checks()
    manifest_path = _build_manifest(
        output_dir=output_dir,
        command_used=command_used,
        forecast_year=forecast_year,
        history_years=history_years,
        prediction_rows=prediction_rows,
        backtest_rows=backtest_rows,
        successor_rows=successor_rows,
        coverage_report=coverage_artifacts["report"],
        eb3024=eb3024,
        ui_checks=ui_checks,
        runtime_truth_copy=runtime_truth_copy,
        prediction_input=runtime_paths["materialized_rows"],
    )

    return {
        "ml_predictions": ml_predictions_path,
        "ml_report": ml_report_path,
        "hunt_code_reconciliation_required_rows": excluded_no_code_path,
        "backtest_csv": backtest_csv_path,
        "backtest_report": backtest_report_path,
        "predictive_successor": successor_path,
        "runtime_truth_v2": runtime_truth_copy,
        "prediction_input": runtime_paths["materialized_rows"],
        "coverage_report_json": coverage_artifacts["json_path"],
        "coverage_report_csv": coverage_artifacts["csv_path"],
        "dedicated_hunter_predictions": dedicated_hunter_csv_path,
        "dedicated_hunter_report": dedicated_hunter_report_path,
        "phase4_antlerless_inventory_csv": phase4_inventory_csv_path,
        "phase4_antlerless_inventory_json": phase4_inventory_json_path,
        "phase6_bonus_special_predictions": phase6_bonus_csv_path,
        "phase6_bonus_special_report": phase6_bonus_json_path,
        "turkey_bonus_predictions": turkey_bonus_csv_path,
        "turkey_bonus_report": turkey_bonus_json_path,
        "youth_turkey_predictions": youth_turkey_csv_path,
        "youth_turkey_report": youth_turkey_json_path,
        "bear_draw_predictions": bear_bonus_csv_path,
        "bear_draw_report": bear_bonus_json_path,
        "bear_predictions": output_dir / "bear_predictions_v1.csv",
        "bear_report": output_dir / "bear_report.json",
        "bear_draw_odds_source_audit_csv": bear_draw_audit_csv_path,
        "bear_draw_odds_source_audit_json": bear_draw_audit_json_path,
        "sportsman_permit_predictions": sportsman_csv_path,
        "sportsman_permit_report": sportsman_json_path,
        "private_lands_antlerless_elk_predictions": private_lands_csv_path,
        "private_lands_antlerless_elk_allocations": output_dir / "private_lands_antlerless_elk_allocations_v1.csv",
        "private_lands_antlerless_elk_report": private_lands_json_path,
        "youth_draw_predictions": youth_csv_path,
        "youth_draw_report": youth_json_path,
        "mountain_lion_availability_predictions": mountain_lion_csv_path,
        "mountain_lion_availability_report": mountain_lion_json_path,
        "runtime_family_promotion_csv": promotion_csv_path,
        "runtime_family_promotion_json": promotion_json_path,
        "runtime_family_promotion_md": promotion_md_path,
        "manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(REPO / "processed_data"))
    parser.add_argument("--forecast-year", type=int, default=2026)
    parser.add_argument("--history-years", default="2018,2019,2020,2021,2022,2023,2024,2025")
    parser.add_argument("--skip-upstream", action="store_true")
    parser.add_argument("--model-version", default=MODEL_VERSION)
    parser.add_argument("--rule-version", default=RULE_VERSION)
    args = parser.parse_args()

    history_years = normalize_history_years(args.history_years)
    command_used = "python -m engine.utah_bonus_predictive.materialize " + " ".join(
        [
            f"--output-dir {args.output_dir}",
            f"--forecast-year {args.forecast_year}",
            f"--history-years {args.history_years}",
            "--skip-upstream" if args.skip_upstream else "",
        ]
    ).strip()
    artifacts = materialize_outputs(
        output_dir=Path(args.output_dir),
        forecast_year=args.forecast_year,
        history_years=history_years,
        command_used=command_used,
        run_upstream=not args.skip_upstream,
    )
    print(json.dumps({key: str(value) for key, value in artifacts.items()}, indent=2))


if __name__ == "__main__":
    main()
