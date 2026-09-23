"""Replay all nine scorings, not engines; retain original forecasts and reports."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.project_legacy_canonical_for_blind_scoring import sha256
from scripts.review_all_year_family_scoring import review


def run(base, out, evidence, reconcile_identities=False, source_end=2025):
    if out.exists():
        raise ValueError('Use a new output folder; never overwrite frozen runs')
    out.mkdir(parents=True)
    protected = list((ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly').glob('*.csv'))
    protected += [ROOT / 'data_truth/draw_results_truth/normalized/draw_results_long.csv',
                  ROOT / 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv']
    for package in ('utah', 'utah_bonus_predictive', 'utah_draw_predictive', 'utah_predictive_mixed'):
        protected.extend((ROOT / 'engine' / package).rglob('*.py'))
    jobs = []
    if source_end not in range(2017, 2026):
        raise ValueError('source_end must be between 2017 and 2025')
    for year in range(2017, source_end + 1):
        parent = base / 'parallel' if year >= 2020 and (base / 'parallel').exists() else base
        original = parent / f'source_{year}' / f'{year}_to_{year + 1}'
        manifest_path = original / 'scoring_projection/scoring_projection_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        truth, forecast = Path(manifest['frozen_truth']), original / 'prediction_phase/final_public_predictions.csv'
        if not truth.is_absolute():
            truth = ROOT / truth
        if sha256(truth) != manifest['frozen_truth_sha256'] or sha256(forecast) != manifest['frozen_forecast_sha256']:
            raise ValueError(f'Original frozen inputs changed: {year}')
        if manifest.get('identity_crosswalk'):
            raise ValueError('This replay expects the recorded exact-code, no-crosswalk folds')
        protected.extend([truth, forecast, manifest_path, original / 'prediction_phase/run_metadata.json'])
        protected.extend((original / 'scoring_projection').glob('*.csv'))
        protected.extend((original / 'comparison_phase').glob('*'))
        jobs.append((year, truth, forecast, original))
    baseline = {p.relative_to(ROOT).as_posix(): sha256(p) for p in protected if p.is_file()}
    baseline_path = out / 'protected_before.json'
    baseline_path.write_text(json.dumps(baseline, indent=2), encoding='utf-8')

    def score(job):
        year, truth, forecast, original = job
        fold = out / f'source_{year}' / f'{year}_to_{year + 1}'
        projection = fold / 'scoring_projection'
        fold.mkdir(parents=True)
        command = [sys.executable, 'scripts/project_legacy_canonical_for_blind_scoring.py',
                   '--frozen-truth', str(truth), '--frozen-forecast', str(forecast),
                   '--out-dir', str(projection), '--source-year', str(year), '--forecast-year', str(year + 1)]
        if year == 2025:
            command += ['--verified-outcome-audit', str(evidence)]
        if reconcile_identities:
            command += ['--reconcile-scoring-identities']
        with (fold / 'projection.log').open('x', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        projected_forecast = next(projection.glob('*forecast*projection.csv'))
        original_forecast = next((original / 'scoring_projection').glob('*forecast*projection.csv'))
        if not reconcile_identities and sha256(projected_forecast) != sha256(original_forecast):
            raise ValueError(f'Forecast projection changed for {year}')
        command = [sys.executable, 'tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py',
                   '--predictions', str(projected_forecast), '--truth', str(next(projection.glob('*actual*projection.csv'))),
                   '--output-dir', str(fold / 'comparison_phase'), '--source-year', str(year),
                   '--target-year', str(year + 1), '--exact-codes-only']
        with (fold / 'scoring.log').open('x', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(f'{year}->{year + 1}: scoring complete; frozen forecast hash unchanged', flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(score, jobs))
    result = review(out, baseline_path, base, source_end=source_end)
    print(json.dumps(result['combined_window_metrics'], indent=2), flush=True)
    return 1 if result.get('protected_file_changes') else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-base', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--verified-outcome-audit', required=True, type=Path)
    parser.add_argument('--reconcile-scoring-identities', action='store_true')
    parser.add_argument('--source-end', type=int, default=2025)
    args = parser.parse_args()
    raise SystemExit(run(args.frozen_base.resolve(), args.output_dir.resolve(), args.verified_outcome_audit.resolve(), args.reconcile_scoring_identities, args.source_end))
