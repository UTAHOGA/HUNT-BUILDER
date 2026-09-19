"""Develop deer repairs on the predeclared 2017-2022 source folds only.

This quick paired diagnostic does not certify; final certification reprojects
and scores all official actual rows with the unchanged complete scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.audit_core_le_deer_repair import BASE, read, key, stats
from engine.utah_draw_predictive.run_all_families import (
    _with_historical_target_metadata, _with_run_fields, _finalize_prediction_output_row, _write_csv,
)
from engine.utah_draw_predictive.preference_general_deer import build_preference_general_deer_predictions
from engine.utah_predictive_mixed.materialize import mixed_row
from engine.utah_predictive_mixed.models import BlendWeights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise SystemExit("Use a separately named development artifact; refusing overwrite")
    args.out_dir.mkdir(parents=True)
    history = []
    all_scores = []
    by_fold = {}
    inputs = {}
    for source_year in range(2017, 2023):
        path = REPO / f"data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{source_year}_for_{source_year + 1}_canonical_yearly_draw_results.csv"
        source = read(path)
        history.extend(source)
        inputs[str(source_year)] = hashlib.sha256(path.read_bytes()).hexdigest()
        forecasts = build_preference_general_deer_predictions(
            _with_historical_target_metadata(history, source_year, source_year + 1),
            _with_historical_target_metadata(source, source_year, source_year + 1),
            source_year + 1, list(range(2017, source_year + 1)),
        )
        forecasts = [mixed_row(_finalize_prediction_output_row(r), None, None, BlendWeights(), forecast_year=source_year + 1)
                     for r in _with_run_fields(forecasts, source_year, source_year + 2, "preference_general_deer")]
        _write_csv(args.out_dir / f"{source_year}_forecast.csv", forecasts)
        lookup = {key(r): r for r in forecasts}
        scores = []
        missing = []
        for row in read(BASE / f"historical_folds/{source_year}_to_{source_year + 1}/comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv"):
            if row["draw_design_key"] != "PREFERENCE_GENERAL_SEASON_BUCK_DEER" or row["scoring_decision"] != "score_probability":
                continue
            match = lookup.get(key(row), {})
            if not str(match.get("p_draw_mean", "")).strip():
                missing.append(key(row))
                continue
            scores.append({**row, "baseline_probability": row["predicted_probability"], "predicted_probability": match["p_draw_mean"]})
        by_fold[str(source_year)] = {**stats(scores), "missing_keys": missing}
        all_scores.extend(scores)
        print(source_year, json.dumps(by_fold[str(source_year)]), flush=True)
    report = {"purpose": "DEVELOPMENT_ONLY_NOT_CERTIFICATION", "source_years": [2017, 2018, 2019, 2020, 2021, 2022],
              "inputs": inputs, "overall": stats(all_scores), "by_fold": by_fold,
              "by_residency": {lane: stats([r for r in all_scores if r["residency"] == lane]) for lane in ["Resident", "Nonresident"]},
              "implementation_sha256": {str(p): hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in
                  ["engine/utah_draw_predictive/preference_general_deer.py", "engine/utah_draw_predictive/run_all_families.py", "engine/utah_predictive_mixed/materialize.py"]}}
    _write_csv(args.out_dir / "paired_development_scores.csv", all_scores)
    (args.out_dir / "development_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
