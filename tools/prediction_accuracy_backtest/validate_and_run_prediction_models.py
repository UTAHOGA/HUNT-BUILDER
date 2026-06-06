#!/usr/bin/env python3
"""Validate draw-truth source years and run controlled prediction materializations.

This tool is read-only with respect to production feeders. Large row-level
engine outputs are written under an ignored audit output directory; only compact
summary reports should be committed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT_DIR = Path("audits/prediction_model_runs/production_eligibility")
SOURCE_DRAW_RESULTS = Path("data_truth/draw_results_truth/normalized/draw_results_long.csv")
SOURCE_DATABASE = Path("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv")
RUNTIME_TRUTH_V2 = Path("data_model/runtime_drafts/draw_reality_engine_v2.csv")
RETROSPECTIVE_2025_INPUT = Path(
    "audits/prediction_accuracy_backtest/retrospective_outputs/2025/materialized/"
    "predictive_bonus_engine_2025.materialized.csv"
)
RUNTIME_2026_INPUT = Path("data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv")

PRODUCTION_COMPARE_FILES = [
    Path("processed_data/ml_draw_predictions_v1.csv"),
    Path("processed_data/draw_reality_engine_predictive_v2.csv"),
]

PROBABILITY_COLUMNS = [
    "p_draw",
    "p_draw_pct",
    "p_draw_percent",
    "p_draw_mean",
    "p_bonus_pool",
    "p_random_pool",
    "success_ratio",
    "random_draw_odds_2026",
    "display_odds",
]

SOURCE_SCORABLE_COLUMNS = [
    "p_draw",
    "p_draw_percent",
    "success_ratio",
    "total_drawn",
    "eligible_applicants",
]

PROFILE_FIELDS = [
    "run_label",
    "target_year",
    "file_role",
    "file_path",
    "exists",
    "row_count",
    "column_count",
    "unique_hunt_codes",
    "probability_fields",
    "probability_nonblank_fields",
    "draw_family_count",
    "draw_families",
    "duplicate_safe_key_count",
    "sha256",
]

RUN_FIELDS = [
    "target_year",
    "source_year",
    "run_label",
    "source_status",
    "engine_run_status",
    "direct_promotion_status",
    "source_rows",
    "source_unique_hunt_codes",
    "source_scorable_rows",
    "source_probability_range_failures",
    "materialized_input",
    "materialized_input_status",
    "output_dir",
    "ml_prediction_rows",
    "predictive_successor_rows",
    "production_compatibility_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Small audit report output directory.")
    parser.add_argument("--target-years", default="2025,2026", help="Comma-separated target years.")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not run materializer.")
    return parser.parse_args()


def norm(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def norm_code(value: Any) -> str:
    return norm(value).upper()


def parse_float(value: Any) -> float | None:
    text = norm(value).replace("%", "").replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
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


def validate_source_year(root: Path, source_year: int) -> dict[str, Any]:
    source_path = root / SOURCE_DRAW_RESULTS
    header, rows = read_csv_rows(source_path)
    year_rows = [row for row in rows if norm(row.get("year")) == str(source_year)]
    hunt_codes = {norm_code(row.get("hunt_code")) for row in year_rows if norm_code(row.get("hunt_code"))}
    scorable_rows = 0
    range_failures = 0
    families: Counter[str] = Counter()
    for row in year_rows:
        ratio = parse_float(row.get("success_ratio"))
        pct = parse_float(row.get("p_draw_percent"))
        drawn = parse_float(row.get("total_drawn"))
        applicants = parse_float(row.get("eligible_applicants"))
        if ratio is not None or pct is not None or (drawn is not None and applicants and applicants > 0):
            scorable_rows += 1
        if ratio is not None and not (0.0 <= ratio <= 1.0):
            range_failures += 1
        if pct is not None and not (0.0 <= pct <= 100.0):
            range_failures += 1
        family = norm(row.get("draw_type")) or norm(row.get("hunt_type")) or "(blank)"
        families[family] += 1

    missing_required_header = [field for field in ["hunt_code", "year", "residency", "points"] if field not in header]
    status = "PASS"
    blockers: list[str] = []
    if not year_rows:
        blockers.append("NO_SOURCE_ROWS_FOR_YEAR")
    if not hunt_codes:
        blockers.append("NO_HUNT_CODES_FOR_YEAR")
    if not scorable_rows:
        blockers.append("NO_SCORABLE_DRAW_RESULT_FIELDS")
    if range_failures:
        blockers.append("PROBABILITY_RANGE_FAILURES")
    if missing_required_header:
        blockers.append("MISSING_REQUIRED_HEADERS:" + ",".join(missing_required_header))
    if blockers:
        status = "BLOCKED"

    return {
        "source_file": rel(root, source_path),
        "source_year": source_year,
        "source_rows": len(year_rows),
        "source_unique_hunt_codes": len(hunt_codes),
        "source_scorable_rows": scorable_rows,
        "source_probability_range_failures": range_failures,
        "source_draw_family_count": len(families),
        "source_draw_families": dict(families.most_common()),
        "source_status": status,
        "source_blockers": blockers,
        "source_sha256": sha256(source_path),
    }


def materialized_input_for_year(root: Path, target_year: int) -> tuple[Path, str]:
    if target_year == 2025:
        return root / RETROSPECTIVE_2025_INPUT, "BASELINE_RETROSPECTIVE_MATERIALIZED_INPUT"
    if target_year == 2026:
        return root / RUNTIME_2026_INPUT, "CURRENT_RUNTIME_DRAFT_MATERIALIZED_INPUT_COPY"
    return root / f"data_model/runtime_drafts/predictive_bonus_engine_{target_year}.materialized.csv", "YEAR_SPECIFIC_RUNTIME_DRAFT_INPUT"


def prepare_runtime_input(root: Path, target_year: int, out_dir: Path) -> tuple[Path, str]:
    input_path, input_status = materialized_input_for_year(root, target_year)
    if not input_path.exists():
        raise FileNotFoundError(f"missing materialized input for {target_year}: {rel(root, input_path)}")
    if not (root / RUNTIME_TRUTH_V2).exists():
        raise FileNotFoundError(f"missing runtime truth v2 source: {RUNTIME_TRUTH_V2.as_posix()}")
    runtime_dir = out_dir / "runtime_inputs" / str(target_year)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, runtime_dir / f"predictive_bonus_engine_{target_year}.materialized.csv")
    shutil.copy2(root / RUNTIME_TRUTH_V2, runtime_dir / "draw_reality_engine_v2.csv")
    return runtime_dir, input_status


def run_controlled_materializer(root: Path, target_year: int, history_years: list[int], out_dir: Path) -> dict[str, str]:
    # Import after sys.path adjustment so the script works when invoked directly.
    sys.path.insert(0, str(root))
    from engine.utah_bonus_predictive import materialize as materialize_mod  # pylint: disable=import-outside-toplevel

    runtime_dir = out_dir / "runtime_inputs" / str(target_year)
    run_output_dir = out_dir / "engine_outputs" / f"{target_year}_from_{history_years[-1]}_validated_truth"
    run_output_dir.mkdir(parents=True, exist_ok=True)

    original_runtime_dir = materialize_mod.RUNTIME_DRAFT_DIR
    materialize_mod.RUNTIME_DRAFT_DIR = runtime_dir
    try:
        artifacts = materialize_mod.materialize_outputs(
            output_dir=run_output_dir,
            forecast_year=target_year,
            history_years=history_years,
            command_used=(
                "controlled audit run: engine.utah_bonus_predictive.materialize "
                f"--forecast-year {target_year} --history-years {','.join(map(str, history_years))} --skip-upstream"
            ),
            run_upstream=False,
        )
    finally:
        materialize_mod.RUNTIME_DRAFT_DIR = original_runtime_dir
    return {key: rel(root, Path(value)) for key, value in artifacts.items()}


def profile_csv(root: Path, path: Path, run_label: str, target_year: int, role: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "run_label": run_label,
            "target_year": target_year,
            "file_role": role,
            "file_path": rel(root, path),
            "exists": False,
            "row_count": 0,
            "column_count": 0,
            "unique_hunt_codes": 0,
            "probability_fields": "",
            "probability_nonblank_fields": "",
            "draw_family_count": 0,
            "draw_families": "",
            "duplicate_safe_key_count": 0,
            "sha256": "",
            "header": [],
            "families_set": set(),
        }
    header, rows = read_csv_rows(path)
    prob_fields = [field for field in header if field in PROBABILITY_COLUMNS or "prob" in field.lower() or "odds" in field.lower()]
    prob_nonblank = Counter()
    families: Counter[str] = Counter()
    hunt_codes: set[str] = set()
    seen_keys: set[tuple[str, str, str, str]] = set()
    duplicate_keys = 0
    for row in rows:
        code = norm_code(row.get("hunt_code"))
        if code:
            hunt_codes.add(code)
        family = norm(row.get("draw_system_type")) or norm(row.get("draw_type")) or norm(row.get("hunt_type")) or "(blank)"
        families[family] += 1
        for field in prob_fields:
            if norm(row.get(field)):
                prob_nonblank[field] += 1
        key = (
            code,
            norm(row.get("residency")),
            norm(row.get("points")),
            norm(row.get("draw_pool")),
        )
        if any(key):
            if key in seen_keys:
                duplicate_keys += 1
            else:
                seen_keys.add(key)
    return {
        "run_label": run_label,
        "target_year": target_year,
        "file_role": role,
        "file_path": rel(root, path),
        "exists": True,
        "row_count": len(rows),
        "column_count": len(header),
        "unique_hunt_codes": len(hunt_codes),
        "probability_fields": ";".join(prob_fields),
        "probability_nonblank_fields": ";".join(f"{field}:{count}" for field, count in prob_nonblank.most_common()),
        "draw_family_count": len(families),
        "draw_families": ";".join(f"{family}:{count}" for family, count in families.most_common(30)),
        "duplicate_safe_key_count": duplicate_keys,
        "sha256": sha256(path),
        "header": header,
        "families_set": set(families),
    }


def compare_to_production(candidate: dict[str, Any], production: dict[str, Any]) -> str:
    if not candidate["exists"]:
        return "candidate_missing"
    if not production["exists"]:
        return "production_reference_missing"
    missing_columns = sorted(set(production["header"]) - set(candidate["header"]))
    missing_families = sorted(set(production["families_set"]) - set(candidate["families_set"]))
    notes = []
    if missing_columns:
        notes.append(f"missing_columns={len(missing_columns)}")
    if missing_families:
        notes.append(f"missing_families={','.join(missing_families[:10])}")
    if candidate["row_count"] < production["row_count"]:
        notes.append(f"candidate_has_fewer_rows={production['row_count'] - candidate['row_count']}")
    return "PRODUCTION_COMPATIBLE" if not notes else "NOT_DIRECT_PROMOTION_ELIGIBLE:" + "|".join(notes)


def write_markdown(path: Path, summary: dict[str, Any], run_rows: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> None:
    lines = [
        "# Prediction Source Eligibility And Controlled Engine Runs",
        "",
        "This is an audit-only gate. It validates the source draw-result years, runs controlled materializations into ignored audit folders, and does not promote production files.",
        "",
        "## Summary",
        f"- Generated at: `{summary['generated_at_utc']}`",
        f"- Target years requested: `{', '.join(map(str, summary['target_years']))}`",
        f"- Runs attempted: `{summary['runs_attempted']}`",
        f"- Runs completed: `{summary['runs_completed']}`",
        f"- Direct production promotions applied: `0`",
        f"- Overall readiness: `{summary['overall_readiness']}`",
        "",
        "## Run Results",
    ]
    for row in run_rows:
        lines.extend(
            [
                "",
                f"### Target {row['target_year']}",
                f"- Source year: `{row['source_year']}`",
                f"- Source status: `{row['source_status']}`",
                f"- Source rows: `{row['source_rows']}`",
                f"- Source scorable rows: `{row['source_scorable_rows']}`",
                f"- Engine run status: `{row['engine_run_status']}`",
                f"- ML prediction rows: `{row['ml_prediction_rows']}`",
                f"- Predictive successor rows: `{row['predictive_successor_rows']}`",
                f"- Direct promotion status: `{row['direct_promotion_status']}`",
                f"- Notes: {row['production_compatibility_notes'] or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Important Interpretation",
            "- Target 2025 uses the existing no-leakage retrospective 2025 materialized input, so it is valid for audit/backtest review but is not a live production replacement.",
            "- Target 2026 uses a copy of the current 2026 runtime draft materialized input and a copy of runtime draw reality v2, so the controlled run does not mutate production draft files.",
            "- Production promotion remains blocked unless generated outputs match the active production schema and family coverage.",
            "",
            "## Outputs",
            "- `audits/prediction_model_runs/production_eligibility/production_eligibility_runs.csv`",
            "- `audits/prediction_model_runs/production_eligibility/production_eligibility_output_profiles.csv`",
            "- `audits/prediction_model_runs/production_eligibility/production_eligibility_summary.json`",
            "- Large row-level outputs: `audits/prediction_model_runs/production_eligibility/engine_outputs/` (ignored/local only)",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    target_years = [int(token.strip()) for token in args.target_years.split(",") if token.strip()]

    run_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    artifacts_by_run: dict[str, Any] = {}
    runs_completed = 0

    for target_year in target_years:
        source_year = target_year - 1
        run_label = f"{target_year}_from_{source_year}_validated_truth"
        source_validation = validate_source_year(root, source_year)
        materialized_input, input_status = materialized_input_for_year(root, target_year)
        row: dict[str, Any] = {
            "target_year": target_year,
            "source_year": source_year,
            "run_label": run_label,
            "source_status": source_validation["source_status"],
            "engine_run_status": "NOT_RUN_DRY_RUN" if args.dry_run else "PENDING",
            "direct_promotion_status": "NOT_PROMOTED_AUDIT_ONLY",
            "source_rows": source_validation["source_rows"],
            "source_unique_hunt_codes": source_validation["source_unique_hunt_codes"],
            "source_scorable_rows": source_validation["source_scorable_rows"],
            "source_probability_range_failures": source_validation["source_probability_range_failures"],
            "materialized_input": rel(root, materialized_input),
            "materialized_input_status": input_status if materialized_input.exists() else "MISSING",
            "output_dir": rel(root, out_dir / "engine_outputs" / run_label),
            "ml_prediction_rows": 0,
            "predictive_successor_rows": 0,
            "production_compatibility_notes": "",
        }
        artifacts_by_run[run_label] = {"source_validation": source_validation}

        if source_validation["source_status"] != "PASS":
            row["engine_run_status"] = "BLOCKED_SOURCE_NOT_PRODUCTION_ELIGIBLE"
            row["production_compatibility_notes"] = ";".join(source_validation["source_blockers"])
            run_rows.append(row)
            continue
        if not materialized_input.exists():
            row["engine_run_status"] = "BLOCKED_MISSING_MATERIALIZED_INPUT"
            row["production_compatibility_notes"] = f"missing {rel(root, materialized_input)}"
            run_rows.append(row)
            continue
        if args.dry_run:
            run_rows.append(row)
            continue

        try:
            prepare_runtime_input(root, target_year, out_dir)
            artifacts = run_controlled_materializer(root, target_year, [source_year], out_dir)
            artifacts_by_run[run_label]["artifacts"] = artifacts
            row["engine_run_status"] = "PASS"
            runs_completed += 1
        except Exception as exc:  # noqa: BLE001 - report exact blocker in audit output.
            row["engine_run_status"] = "FAILED"
            row["production_compatibility_notes"] = f"{type(exc).__name__}: {exc}"
            run_rows.append(row)
            continue

        ml_profile = profile_csv(root, root / artifacts["ml_predictions"], run_label, target_year, "candidate_ml_draw_predictions_v1")
        successor_profile = profile_csv(root, root / artifacts["predictive_successor"], run_label, target_year, "candidate_draw_reality_engine_predictive_v2")
        profile_rows.extend([ml_profile, successor_profile])
        row["ml_prediction_rows"] = ml_profile["row_count"]
        row["predictive_successor_rows"] = successor_profile["row_count"]

        notes: list[str] = []
        if target_year == 2026:
            prod_ml = profile_csv(root, root / PRODUCTION_COMPARE_FILES[0], "production", target_year, "production_ml_draw_predictions_v1")
            prod_successor = profile_csv(root, root / PRODUCTION_COMPARE_FILES[1], "production", target_year, "production_draw_reality_engine_predictive_v2")
            profile_rows.extend([prod_ml, prod_successor])
            ml_status = compare_to_production(ml_profile, prod_ml)
            successor_status = compare_to_production(successor_profile, prod_successor)
            notes.extend([f"ml={ml_status}", f"predictive_successor={successor_status}"])
            row["direct_promotion_status"] = (
                "PRODUCTION_ELIGIBLE_DO_NOT_AUTO_PROMOTE"
                if ml_status == "PRODUCTION_COMPATIBLE" and successor_status == "PRODUCTION_COMPATIBLE"
                else "RUN_COMPLETE_NOT_DIRECT_PROMOTION_ELIGIBLE"
            )
        else:
            row["direct_promotion_status"] = "AUDIT_BACKTEST_ELIGIBLE_NOT_LIVE_PRODUCTION_TARGET"
            notes.append("target_2025_is_historical_replay_not_current_live_surface")
        row["production_compatibility_notes"] = "; ".join(notes)
        run_rows.append(row)

    compact_profiles = [{field: row.get(field, "") for field in PROFILE_FIELDS} for row in profile_rows]
    write_csv(out_dir / "production_eligibility_runs.csv", RUN_FIELDS, run_rows)
    write_csv(out_dir / "production_eligibility_output_profiles.csv", PROFILE_FIELDS, compact_profiles)

    overall_readiness = "PASS"
    if any(row["engine_run_status"] in {"FAILED", "BLOCKED_SOURCE_NOT_PRODUCTION_ELIGIBLE", "BLOCKED_MISSING_MATERIALIZED_INPUT"} for row in run_rows):
        overall_readiness = "FAIL"
    elif any(row["direct_promotion_status"] == "RUN_COMPLETE_NOT_DIRECT_PROMOTION_ELIGIBLE" for row in run_rows):
        overall_readiness = "PASS_WITH_PROMOTION_BLOCKERS"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_years": target_years,
        "runs_attempted": len(target_years),
        "runs_completed": runs_completed,
        "overall_readiness": overall_readiness,
        "production_files_modified": False,
        "database_modified": False,
        "normalized_truth_modified": False,
        "website_or_r2_modified": False,
        "direct_promotions_applied": 0,
        "run_rows": run_rows,
        "artifacts_by_run": artifacts_by_run,
    }
    write_json(out_dir / "production_eligibility_summary.json", summary)
    write_markdown(out_dir / "PRODUCTION_ELIGIBILITY_REVIEW.md", summary, run_rows, profile_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if overall_readiness in {"PASS", "PASS_WITH_PROMOTION_BLOCKERS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
