#!/usr/bin/env python3
"""Run source-only adjacent-year Bear scoring without rebuilding other families."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.utah_draw_predictive.bear import build_bear_bonus_predictions
from engine.utah_draw_predictive.run_all_families import (
    _historical_source_year_runtime_db_rows,
    _read_csv,
    _row_year,
    _source_backed_probability_rows,
    _with_run_fields,
    _write_csv,
)


TRUTH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"


def run(command: list[str]) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=REPO, check=True)


def canonical_actual(physical_draw_year: int) -> Path:
    matches = sorted(
        CANONICAL_DIR.glob(
            f"draw_results_{physical_draw_year}_for_{physical_draw_year + 1}_canonical_yearly_draw_results.csv"
        )
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one canonical actual for physical draw year {physical_draw_year}; found {matches}"
        )
    return matches[0]


def projection_file(directory: Path, token: str) -> Path:
    matches = sorted(directory.glob(f"*{token}*projection.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {token} projection in {directory}; found {matches}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-start", type=int, required=True)
    parser.add_argument("--source-end", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--central-estimate",
        choices=["deterministic", "simulation_mean"],
        default="deterministic",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260701)
    args = parser.parse_args()
    if args.source_end < args.source_start:
        raise SystemExit("--source-end must be at least --source-start")
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")
    if not TRUTH.exists():
        raise SystemExit(f"Normalized official truth is missing: {TRUTH}")

    all_truth_rows = _read_csv(TRUTH)
    for source_year in range(args.source_start, args.source_end + 1):
        target_year = source_year + 1
        history_years = [source_year] if source_year == 2017 else list(range(2018, source_year + 1))
        source_rows = [row for row in all_truth_rows if _row_year(row) == source_year]
        history_rows = [row for row in all_truth_rows if (_row_year(row) or 0) in set(history_years)]
        runtime_db_rows = _historical_source_year_runtime_db_rows(source_rows, source_year)

        fold = args.out_dir / f"{source_year}_to_{target_year}"
        prediction_dir = fold / "prediction_phase"
        projection_dir = fold / "scoring_projection"
        comparison_dir = fold / "comparison_phase"

        bear_rows, bear_report = build_bear_bonus_predictions(
            history_rows,
            runtime_db_rows,
            target_year,
            history_years,
            central_estimate_mode=args.central_estimate,
            iterations=args.iterations,
            seed=args.seed,
        )
        prediction_rows = _with_run_fields(
            bear_rows,
            source_year,
            target_year + 1,
            "bonus_bear",
        )
        source_backed_rows = _source_backed_probability_rows(
            source_rows,
            {"bonus_bear": prediction_rows},
            source_year,
            target_year + 1,
        ).get("bonus_bear", [])
        prediction_rows.extend(
            _with_run_fields(
                source_backed_rows,
                source_year,
                target_year + 1,
                "bonus_bear",
            )
        )
        prediction_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(prediction_dir / "family_predictions.csv", prediction_rows)
        (prediction_dir / "bonus_bear_runtime_report.json").write_text(
            json.dumps(bear_report, indent=2) + "\n",
            encoding="utf-8",
        )

        run(
            [
                sys.executable,
                "scripts/project_legacy_canonical_for_blind_scoring.py",
                "--frozen-truth",
                str(canonical_actual(target_year)),
                "--frozen-forecast",
                str(prediction_dir / "family_predictions.csv"),
                "--out-dir",
                str(projection_dir),
            ]
        )
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
            ]
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
