"""Freeze scoped youth feed candidates, then score all nine using existing tools.

No target actual rows are read until every candidate is frozen. Unrelated
forecast rows are copied field-for-field from the retained final forecasts.
This reuses the existing source fallback and final mixed_row, not a new model.
"""
import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.utah_draw_predictive import run_all_families as owner
from engine.utah_predictive_mixed.materialize import mixed_row
from engine.utah_predictive_mixed.models import BlendWeights
from scripts.project_legacy_canonical_for_blind_scoring import sha256, write_csv
from scripts.run_historical_adjacent_full_engine_scoring import canonical_actual
from scripts.review_all_year_family_scoring import review


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def run(base, out, endpoint):
    if out.exists():
        raise ValueError('Use a fresh candidate folder; prior evidence is retained')
    out.mkdir(parents=True)
    protected = list((ROOT/'data_truth/draw_results_truth/normalized').rglob('*.csv'))
    protected += [ROOT/'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv']
    for package in ('utah', 'utah_draw_predictive', 'utah_bonus_predictive', 'utah_predictive_mixed'):
        protected += list((ROOT/'engine'/package).rglob('*.py'))
    frozen = {}
    for year in range(2017, 2026):
        parent = base/'parallel' if year >= 2020 and (base/'parallel').exists() else base
        original = parent/f'source_{year}'/f'{year}_to_{year+1}'/'prediction_phase'/'final_public_predictions.csv'
        frozen[year] = original
        protected.append(original)
    before = {str(p.relative_to(ROOT)): sha256(p) for p in protected}
    baseline = out/'protected_before.json'
    baseline.write_text(json.dumps(before, indent=2), encoding='utf-8')
    ledger = []
    # Forecast phase: source canonical only, no target outcome or gap list.
    for year, original in frozen.items():
        source = canonical_actual(year)
        source_rows = [r for r in read(source) if owner._source_backed_family_for_row(r) == 'youth_draw']
        if any(int(r.get('actual_draw_year') or r.get('year') or year) != year for r in source_rows):
            raise ValueError('Source-year leakage')
        youth = [r for r in read(original) if r.get('family') == 'youth_draw']
        fallback = owner._source_backed_probability_rows(source_rows, {'youth_draw': youth}, year, year+1).get('youth_draw', [])
        added = owner._with_run_fields(fallback, year, year+1, 'youth_draw')
        _, replaced = owner._merge_source_backed_family_rows('youth_draw', youth, added)
        replacement_keys = {owner._source_backed_lane_key('youth_draw', r) for r in replaced}
        final_added = [mixed_row(r, None, None, BlendWeights(), forecast_year=year+1) for r in added]
        folder = out/f'source_{year}'/f'{year}_to_{year+1}'/'prediction_phase'
        folder.mkdir(parents=True)
        final = folder/'final_public_predictions.csv'
        with original.open(encoding='utf-8-sig', newline='') as src, final.open('x', encoding='utf-8', newline='') as dst:
            reader = csv.DictReader(src)
            fields = list(dict.fromkeys(list(reader.fieldnames) + [k for r in final_added for k in r]))
            writer = csv.DictWriter(dst, fieldnames=fields)
            writer.writeheader()
            preserved = 0
            for line, row in enumerate(reader, 2):
                if owner._youth_reserve_input_placeholder(row) and owner._source_backed_lane_key('youth_draw', row) in replacement_keys:
                    ledger.append(dict(source_year=year, original_csv_line=line, hunt_code=row['hunt_code'],
                                       residency=row['residency'], points=row['points'],
                                       reason='UNMODELED_INPUT_PLACEHOLDER_HANDOFF_TO_EXISTING_EXACT_SOURCE_FALLBACK'))
                else:
                    writer.writerow(row)
                    preserved += 1
            writer.writerows(final_added)
        freeze = dict(source_year=year, target_year=year+1, source=str(source), source_sha256=sha256(source),
                      original_final=str(original), original_sha256=sha256(original), final_sha256=sha256(final),
                      original_rows_preserved=preserved, placeholders_replaced=len(replaced), fallback_rows_added=len(final_added),
                      owner_sha256=sha256(ROOT/'engine/utah_draw_predictive/run_all_families.py'),
                      final_calculation='mixed_row(row, None, None, BlendWeights())',
                      final_implementation_sha256=sha256(ROOT/'engine/utah_predictive_mixed/materialize.py'),
                      target_outcomes_read_for_generation=False, certified_or_deployed=False)
        (folder/'candidate_freeze.json').write_text(json.dumps(freeze, indent=2), encoding='utf-8')
        print(f'{year}->{year+1}: frozen; {len(replaced)} placeholders handed off, {len(final_added)} source fallback rows', flush=True)
    write_csv(out/'placeholder_handoff_ledger.csv', list(ledger[0]) if ledger else ['source_year'], ledger)
    print('ALL NINE CANDIDATES FROZEN; beginning separate target scoring', flush=True)

    def score(year):
        fold = out/f'source_{year}'/f'{year}_to_{year+1}'
        projection = fold/'scoring_projection'
        cmd = [sys.executable, 'scripts/project_legacy_canonical_for_blind_scoring.py',
               '--frozen-truth', str(canonical_actual(year+1)), '--frozen-forecast', str(fold/'prediction_phase/final_public_predictions.csv'),
               '--out-dir', str(projection), '--source-year', str(year), '--forecast-year', str(year+1), '--reconcile-scoring-identities']
        if year == 2025:
            cmd += ['--verified-outcome-audit', str(endpoint)]
        with (fold/'projection.log').open('x', encoding='utf-8') as log:
            subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        cmd = [sys.executable, 'tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py',
               '--predictions', str(next(projection.glob('*forecast*projection.csv'))),
               '--truth', str(next(projection.glob('*actual*projection.csv'))),
               '--output-dir', str(fold/'comparison_phase'), '--source-year', str(year), '--target-year', str(year+1), '--exact-codes-only']
        with (fold/'scoring.log').open('x', encoding='utf-8') as log:
            subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(f'{year}->{year+1}: scored', flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(score, range(2017, 2026)))
    result = review(out, baseline, base, forecast_candidate_base=out)
    print(json.dumps({'blocking_gaps': result['unresolved_gaps'], **result['combined_nine_fold_metrics']}), flush=True)
    return int(bool(result.get('protected_file_changes')))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frozen-base', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--verified-outcome-audit', type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args.frozen_base.resolve(), args.output_dir.resolve(), args.verified_outcome_audit.resolve()))
