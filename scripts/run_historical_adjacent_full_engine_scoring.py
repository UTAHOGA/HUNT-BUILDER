#!/usr/bin/env python3
"""Run source-only adjacent-year full-engine historical scoring folds.

Each fold generates the forecast from official truth at or before the source
year, writes it to an isolated audit directory, then scores it against the
following year's frozen canonical. No runtime, canonical, or hosted artifact
is modified.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-start", type=int, default=2018)
    parser.add_argument("--source-end", type=int, default=2024)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.source_end < args.source_start:
        raise SystemExit("--source-end must be at least --source-start")
    if not TRUTH.exists():
        raise SystemExit(f"Normalized official truth is missing: {TRUTH}")

    for source_year in range(args.source_start, args.source_end + 1):
        target_year = source_year + 1
        fold = args.out_dir / f"{source_year}_to_{target_year}"
        prediction_dir = fold / "prediction_phase"
        projection_dir = fold / "scoring_projection"
        comparison_dir = fold / "comparison_phase"
        run(
            [
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
                str(TRUTH),
                "--audit-dir",
                str(prediction_dir),
                "--runtime-permit-source",
                "source_year_proxy",
            ]
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
