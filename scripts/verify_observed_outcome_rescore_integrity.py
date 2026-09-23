"""Verify frozen rescore deltas and expose repeated structural scoring keys."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(old, new, output_dir=None):
    # Recheck retained evidence without replacing the prior audit beside it.
    destination = output_dir if output_dir is not None else new
    output = destination / 'projection_integrity_and_duplicate_review.json'
    repeated_output = destination / 'repeated_structural_scoring_keys.csv'
    if output.exists() or repeated_output.exists():
        raise ValueError('Refusing to overwrite integrity review')
    destination.mkdir(parents=True, exist_ok=True)
    folds, duplicates, failures = [], [], []
    for year in range(2017, 2026):
        parent = old / 'parallel' if year >= 2020 else old
        fold = f'source_{year}/{year}_to_{year + 1}'
        before, after = parent / fold, new / fold
        old_actual = next((before / 'scoring_projection').glob('*actual*projection.csv'))
        new_actual = next((after / 'scoring_projection').glob('*actual*projection.csv'))
        original, corrected = rows(old_actual), rows(new_actual)
        changed = 0
        if len(original) != len(corrected):
            failures.append(f'{year}: actual row count changed')
        for line, (a, b) in enumerate(zip(original, corrected), 2):
            diff = {k for k in set(a) | set(b) if a.get(k, '') != b.get(k, '')}
            if not diff:
                continue
            changed += 1
            if (diff - {'p_draw', 'p_draw_percent', 'actual_probability_source'} or
                    a.get('p_draw') or a.get('p_draw_percent') or b.get('p_draw') != '0' or
                    float(a.get('eligible_applicants') or 0) <= 0 or float(a.get('total_permits') or 0) != 0):
                failures.append(f'{year}: unexpected actual delta line {line}')
        forecast_same = digest(next((before / 'scoring_projection').glob('*forecast*projection.csv'))) == digest(next((after / 'scoring_projection').glob('*forecast*projection.csv')))
        if not forecast_same:
            failures.append(f'{year}: frozen forecast projection changed')
        scoring_name = 'comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv'
        groups = defaultdict(list)
        for row in rows(after / scoring_name):
            if row['scoring_decision'] == 'score_probability':
                key = tuple(row[k] for k in ('draw_design_key', 'draw_pool_key', 'hunt_code', 'residency', 'points'))
                groups[key].append(row)
        fold_duplicates = 0
        for key, values in groups.items():
            if len(values) > 1:
                fold_duplicates += 1
                duplicates.append(dict(source_year=year, draw_design=key[0], draw_pool=key[1], hunt_code=key[2],
                                       residency=key[3], points=key[4], rows=len(values),
                                       probabilities='|'.join(r['predicted_probability'] for r in values),
                                       actual_probability=values[0]['actual_probability']))
        folds.append(dict(source_year=year, actual_rows=len(corrected), observed_zeros_restored=changed,
                          forecast_projection_unchanged=forecast_same,
                          score_csv_identical=digest(before / scoring_name) == digest(after / scoring_name),
                          scorable_prediction_rows=sum(map(len, groups.values())), distinct_actual_keys=len(groups),
                          repeated_structural_score_keys=fold_duplicates))
    with repeated_output.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(duplicates[0]) if duplicates else ['source_year', 'hunt_code'])
        writer.writeheader()
        writer.writerows(duplicates)
    result = dict(status='PASS_PROJECTION_INTEGRITY' if not failures else 'FAIL', failures=failures, folds=folds,
                  certification_hold=bool(duplicates),
                  explanation='Repeated forecast structural keys remain diagnostic evidence, not independent actual samples. No forecast chosen, removed or modified by this check.')
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--rescore', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path,
                        help='Write a fresh integrity review here without changing retained rescore evidence.')
    args = parser.parse_args()
    raise SystemExit(verify(args.original, args.rescore, args.output_dir))
