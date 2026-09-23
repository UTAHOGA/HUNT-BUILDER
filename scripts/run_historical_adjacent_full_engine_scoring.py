#!/usr/bin/env python3
"""Run source-only adjacent-year full-engine historical scoring folds.

Each fold generates the forecast from official truth at or before the source
year, writes it to an isolated audit directory, then scores it against the
following year's frozen canonical. No runtime, canonical, or hosted artifact
is modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TRUTH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"


def run(command: list[str]) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=REPO, check=True)


def canonical_actual(physical_draw_year: int) -> Path:
    """Return the canonical published for the physical target draw year.

    Canonical filenames use ``draw_results_<actual draw year>_for_<next model
    year>``.  A source year N forecast must therefore compare to the N+1
    actual file, whose score-key model year is N+2.
    """
    matches = sorted(CANONICAL_DIR.glob(f"draw_results_{physical_draw_year}_for_{physical_draw_year + 1}_canonical_yearly_draw_results.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one canonical actual for physical draw year {physical_draw_year}; found {matches}")
    return matches[0]


def projection_file(directory: Path, token: str) -> Path:
    matches = sorted(directory.glob(f"*{token}*projection.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {token} projection in {directory}; found {matches}")
    return matches[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_year_paths(values: list[str], option: str) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        try:
            year_text, path_text = value.split("=", 1)
            year = int(year_text)
        except (ValueError, TypeError) as exc:
            raise SystemExit(f"{option} must use YEAR=PATH; received {value!r}") from exc
        path = Path(path_text).resolve()
        if not path.is_file():
            raise SystemExit(f"{option} file does not exist: {path}")
        if year in parsed:
            raise SystemExit(f"{option} repeats year {year}")
        parsed[year] = path
    return parsed


def build_isolated_truth(year_paths: dict[int, Path], out_dir: Path) -> Path:
    fields: list[str] = []
    rows: list[dict[str, str]] = []
    input_rows: dict[str, int] = {}
    for year, path in sorted(year_paths.items()):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            year_rows = [dict(row) for row in reader]
        observed_years = {
            str(row.get("actual_draw_year") or row.get("source_year") or row.get("draw_year") or row.get("year") or "").strip()
            for row in year_rows
        }
        if observed_years != {str(year)}:
            raise SystemExit(f"Isolated truth {path} contains years {sorted(observed_years)}, expected only {year}")
        rows.extend(year_rows)
        input_rows[str(year)] = len(year_rows)

    truth_dir = out_dir / "isolated_truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    truth_path = truth_dir / "official_source_truth_combined.csv"
    with truth_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ISOLATED_OFFICIAL_SOURCE_TRUTH_NOT_PROMOTED",
        "rows": len(rows),
        "input_rows_by_draw_year": input_rows,
        "inputs": {
            str(year): {"path": str(path).replace("\\", "/"), "sha256": sha256(path)}
            for year, path in sorted(year_paths.items())
        },
        "output": {"path": str(truth_path).replace("\\", "/"), "sha256": sha256(truth_path)},
        "production_writes": [],
    }
    (truth_dir / "isolated_truth_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return truth_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-start", type=int, default=2018)
    parser.add_argument("--source-end", type=int, default=2024)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--truth-year-file",
        action="append",
        default=[],
        metavar="YEAR=PATH",
        help="Use one or more isolated official yearly truth files instead of the retained unified truth.",
    )
    parser.add_argument(
        "--actual-year-file",
        action="append",
        default=[],
        metavar="YEAR=PATH",
        help="Override the frozen actual used for a physical target draw year.",
    )
    parser.add_argument(
        "--identity-crosswalk-dir",
        type=Path,
        help="Directory containing the selected adjacent-year identity crosswalk files.",
    )
    parser.add_argument(
        "--identity-crosswalk-kind",
        choices=["reviewed", "pre_draw"],
        default="reviewed",
        help="Use target-reviewed diagnostic tables or pre-draw source-only exception tables.",
    )
    parser.add_argument("--bonus-central-estimate", choices=["deterministic", "simulation_mean"], default="deterministic")
    parser.add_argument("--bonus-iterations", type=int, default=1)
    parser.add_argument("--final-probability-stage", action="store_true", help="Score the exact public post-family calculation, retaining both input and final forecasts.")
    parser.add_argument("--all-family-final-stage", action="store_true", help="Apply mixed_row to every family, with no unavailable historical harvest or prior-row blend input.")
    parser.add_argument("--exact-codes-only", action="store_true", help="Disable implicit current-year scorer identity bridges.")
    parser.add_argument(
        "--verified-outcome-audit",
        type=Path,
        help="Hash-verified 2026 UtahDraws count audit used only to prepare observed 2026 scoring outcomes.",
    )
    parser.add_argument("--reuse-family-predictions", action="store_true", help="Replay final calculation/scoring from the retained family forecasts; never regenerate or change their inputs.")
    parser.add_argument("--refresh-general-deer", action="store_true", help="Rebuild only general deer from source-only canonical history, retaining the original family CSV unchanged.")
    parser.add_argument("--bear-central-estimate", choices=["deterministic", "simulation_mean"], default="deterministic")
    parser.add_argument("--bear-iterations", type=int, default=1)
    parser.add_argument(
        "--bear-returning-cohort-mode",
        choices=[
            "off",
            "source_calibrated_tail_mixture",
            "lane_cohort_hierarchical",
        ],
        default="off",
    )
    args = parser.parse_args()
    if args.all_family_final_stage and not args.final_probability_stage:
        parser.error("--all-family-final-stage requires --final-probability-stage")
    if args.source_end < args.source_start:
        raise SystemExit("--source-end must be at least --source-start")
    truth_year_paths = parse_year_paths(args.truth_year_file, "--truth-year-file")
    actual_year_paths = parse_year_paths(args.actual_year_file, "--actual-year-file")
    if args.verified_outcome_audit is not None:
        audit_summary = args.verified_outcome_audit / "summary.json"
        if not audit_summary.is_file():
            raise SystemExit(f"Verified 2026 outcome audit is missing: {audit_summary}")
        if args.source_start <= 2025 <= args.source_end:
            current_truth = canonical_actual(2026)
            truth_key = current_truth.relative_to(REPO).as_posix()
            recorded_hash = json.loads(audit_summary.read_text(encoding="utf-8")).get(
                "input_hashes", {}
            ).get(truth_key)
            if recorded_hash != sha256(current_truth):
                raise SystemExit("Verified 2026 outcome audit does not match the current canonical")
    truth_path = build_isolated_truth(truth_year_paths, args.out_dir) if truth_year_paths else TRUTH
    if not truth_path.exists():
        raise SystemExit(f"Normalized official truth is missing: {truth_path}")

    for source_year in range(args.source_start, args.source_end + 1):
        target_year = source_year + 1
        fold = args.out_dir / f"{source_year}_to_{target_year}"
        prediction_dir = fold / "prediction_phase"
        projection_dir = fold / "scoring_projection"
        comparison_dir = fold / "comparison_phase"
        family_command = [
                sys.executable,
                "-m",
                "engine.utah_draw_predictive.run_all_families",
                "--source-year",
                str(source_year),
                "--target-year",
                str(target_year),
                "--score-target-year",
                str(target_year + 1),
                "--truth-path",
                str(truth_path),
                "--audit-dir",
                str(prediction_dir),
                "--runtime-permit-source",
                "source_year_proxy",
                "--bonus-central-estimate",
                args.bonus_central_estimate,
                "--bonus-iterations",
                str(args.bonus_iterations),
                "--bear-central-estimate",
                args.bear_central_estimate,
                "--bear-iterations",
                str(args.bear_iterations),
                "--bear-returning-cohort-mode",
                args.bear_returning_cohort_mode,
            ]
        forecast_path = prediction_dir / "family_predictions.csv"
        if args.reuse_family_predictions:
            if not forecast_path.is_file() or not (prediction_dir / "run_metadata.json").is_file():
                raise SystemExit(f"Retained family evidence missing: {prediction_dir}")
        else:
            run(family_command)
        if args.refresh_general_deer:
            if str(REPO) not in sys.path:
                sys.path.insert(0, str(REPO))
            from engine.utah_draw_predictive.run_all_families import (
                _read_csv, _write_csv, _row_year, _with_historical_target_metadata,
                _with_run_fields, _finalize_prediction_output_row, _dedupe_final_family_prediction_rows,
            )
            from engine.utah_draw_predictive.preference_general_deer import build_preference_general_deer_predictions
            original_forecast_path = forecast_path
            source_history = [r for r in _read_csv(truth_path) if 2017 <= (_row_year(r) or 0) <= source_year]
            source_only = [r for r in source_history if _row_year(r) == source_year]
            history_years = sorted({_row_year(r) for r in source_history})
            deer_rows = build_preference_general_deer_predictions(
                _with_historical_target_metadata(source_history, source_year, target_year),
                _with_historical_target_metadata(source_only, source_year, target_year),
                target_year, history_years,
            )
            deer_rows = [_finalize_prediction_output_row(r) for r in _with_run_fields(
                deer_rows, source_year, target_year + 1, "preference_general_deer"
            )]
            deer_rows, deer_duplicates = _dedupe_final_family_prediction_rows(deer_rows)
            retained = [r for r in _read_csv(original_forecast_path) if r.get("family") != "preference_general_deer"]
            forecast_path = prediction_dir / "family_predictions_deer_refreshed.csv"
            _write_csv(forecast_path, retained + deer_rows)
            del source_history, source_only, retained
        if args.final_probability_stage:
            if str(REPO) not in sys.path:
                sys.path.insert(0, str(REPO))
            from engine.utah_predictive_mixed.materialize import CORE_FINAL_PROBABILITY_DESIGNS, FINAL_PROBABILITY_CONTRACT, mixed_row
            from engine.utah_predictive_mixed.models import BlendWeights
            with forecast_path.open(encoding="utf-8-sig", newline="") as handle:
                source_predictions = list(csv.DictReader(handle))
            final_predictions = [
                mixed_row(row, None, None, BlendWeights(), forecast_year=target_year)
                if args.all_family_final_stage or row.get("draw_system_type") in CORE_FINAL_PROBABILITY_DESIGNS else row
                for row in source_predictions
            ]
            final_path = prediction_dir / "final_public_predictions.csv"
            fields = list(dict.fromkeys(field for row in final_predictions for field in row))
            with final_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(final_predictions)
            final_gate = {
                "status": "PASS", "contract": FINAL_PROBABILITY_CONTRACT,
                "entrypoint": "engine.utah_predictive_mixed.materialize.mixed_row",
                "input_sha256": hashlib.sha256(forecast_path.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
                "implementation_sha256": hashlib.sha256((REPO / "engine/utah_predictive_mixed/materialize.py").read_bytes()).hexdigest(),
                "historical_database_csv_read_count": 0,
                "current_harvest_feature_read_count": 0,
                "rows": len(final_predictions),
                "scope": "ALL_FAMILIES" if args.all_family_final_stage else "CORE_DESIGNS_ONLY",
                "prior_input_policy": "NONE_NO_UNVERIFIED_HISTORICAL_RUNTIME_PRIOR",
                "harvest_input_policy": "NONE_NO_CURRENT_HARVEST_IN_HISTORICAL_FORECAST",
            }
            metadata_path = prediction_dir / "run_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["final_probability_gate"] = final_gate
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            forecast_path = final_path
        projection_command = [
                sys.executable,
                "scripts/project_legacy_canonical_for_blind_scoring.py",
                "--frozen-truth",
                str(actual_year_paths.get(target_year) or canonical_actual(target_year)),
                "--frozen-forecast",
                str(forecast_path),
                "--out-dir",
                str(projection_dir),
                "--source-year",
                str(source_year),
                "--forecast-year",
                str(target_year),
                # Source-only scoring identity reconciliation counts an exact
                # final key once and keeps the declared primary owner when an
                # OIL or Sportsman fallback is also present.  It never selects
                # a row from the held-out outcome.
                "--reconcile-scoring-identities",
        ]
        if target_year == 2026 and args.verified_outcome_audit is not None:
            projection_command.extend(["--verified-outcome-audit", str(args.verified_outcome_audit)])
        if args.identity_crosswalk_dir is not None:
            prefix = (
                "pre_draw_hunt_identity_crosswalk"
                if args.identity_crosswalk_kind == "pre_draw"
                else "reviewed_hunt_identity_crosswalk"
            )
            identity_crosswalk = (
                args.identity_crosswalk_dir
                / f"{prefix}_{source_year}_to_{target_year}.csv"
            )
            if not identity_crosswalk.is_file():
                raise SystemExit(f"Identity crosswalk is missing: {identity_crosswalk}")
            projection_command.extend(["--identity-crosswalk", str(identity_crosswalk)])
        run(projection_command)
        run(
            [
                sys.executable,
                "tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py",
                "--predictions",
                str(projection_file(projection_dir, "forecast")),
                "--truth",
                str(projection_file(projection_dir, "actual")),
                "--output-dir",
                str(comparison_dir),
                "--source-year",
                str(source_year),
                "--target-year",
                str(target_year),
                *(["--exact-codes-only"] if args.exact_codes_only else []),
            ]
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
