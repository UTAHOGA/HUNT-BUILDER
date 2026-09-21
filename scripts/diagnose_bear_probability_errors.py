"""Hindsight attribution only: never a forecast or certification candidate.

Uses following-year demand/awards deliberately to distinguish demand error,
quota-proxy error, and remaining mechanics/realized-random-outcome error.
These oracle calculations must never feed the prediction owner.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from engine.utah_draw_predictive.bear import (
    compute_bonus_pool_probability, _weighted_random_probability, combine_probabilities,
)
from scripts.audit_bear_controlled_candidates import new_directory, read_rows, write_rows, dump
from scripts.bear_grouped_uncertainty import metric_values


def diagnose(folds, out):
    out = new_directory(out)
    scored = read_rows(folds / 'final_scored_rows.csv')
    results = []
    key = lambda r: (r['hunt_code'], r['residency'], r['points'])
    for fold in sorted({r['fold'] for r in scored}):
        actual = read_rows(folds / fold / 'actual_projection.csv')
        predictions = {key(r): r for r in read_rows(folds / fold / 'prediction_phase/final_predictions.csv')}
        lanes = defaultdict(list)
        for row in actual:
            lanes[key(row)[:2]].append(row)
        for row in [r for r in scored if r['fold'] == fold]:
            lane = lanes[key(row)[:2]]
            ladder = {int(r['points']): int(r['eligible_applicants']) for r in lane}
            point = int(row['points'])
            pred = predictions[key(row)]
            for label, bonus, regular in [
                ('PERFECT_DEMAND_SOURCE_QUOTA_PROXY', int(pred['max_point_permits_2026']), int(pred['random_permits_2026'])),
                ('PERFECT_DEMAND_AND_ACTUAL_POOL_AWARDS', sum(int(r['bonus_permits']) for r in lane), sum(int(r['regular_permits']) for r in lane)),
            ]:
                b, _, _ = compute_bonus_pool_probability(point, ladder, bonus)
                q = _weighted_random_probability(point, ladder, regular, bonus)
                probability = min(.99, combine_probabilities(b, q))
                results.append({**row, 'diagnostic': label, 'candidate_prediction': row['predicted_probability'],
                                'predicted_probability': probability,
                                'not_a_forecast': True, 'target_actuals_used': True})
    groups = defaultdict(list)
    for row in results:
        for lane in ('POOLED_DESIGN', row['residency']):
            groups[(row['diagnostic'], row['draw_design'], lane)].append(row)
    summaries = []
    for (label, design, lane), rows in sorted(groups.items()):
        errors = np.asarray([float(r['predicted_probability']) - float(r['actual_probability']) for r in rows])
        summaries.append(dict(diagnostic=label, design=design, residency=lane, rows=len(rows), **metric_values(errors)))
    write_rows(out / 'oracle_diagnostics.csv', results)
    write_rows(out / 'oracle_summary.csv', summaries)
    dump(out / 'WARNING.json', {'not_a_forecast': True, 'uses_target_actuals': True,
                               'certification_or_production_use_allowed': False,
                               'residual_error_is_not_pure_sampling_error': 'Includes mechanics approximation and group/award behavior as well as realized random outcomes.'})
    print(summaries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folds', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    diagnose(args.folds, args.out_dir)
