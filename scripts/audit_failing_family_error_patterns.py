"""Group retained independent scores for feed triage; no new predictions or acceptance."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

FAMILIES = {'BONUS_CWMU_BIG_GAME', 'PREFERENCE_ANTLERLESS_DEER',
            'PREFERENCE_ANTLERLESS_ELK', 'PREFERENCE_DOE_PRONGHORN',
            'PREFERENCE_DEDICATED_HUNTER_DEER', 'PREFERENCE_GENERAL_SEASON_BUCK_DEER'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scores', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256(args.scores.read_bytes()).hexdigest()
    groups, tails, seen = defaultdict(list), [], set()
    with args.scores.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if row['fold'] == '2025_to_2026':
                continue
            family = row['draw_design']
            if family.split('__')[0] not in FAMILIES:
                continue
            key = tuple(row.get(k, '') for k in ('fold', 'draw_design', 'hunt_code',
                        'residency', 'points', 'draw_pool_key', 'algorithm_status'))
            if key in seen:
                raise ValueError(f'Repeated scoring key: {key}')
            seen.add(key)
            group = (family, row['residency'], row['algorithm_status'])
            groups[group].append(row)
            if float(row['absolute_error']) > .25:
                tails.append(row)
    summary = []
    for key, rows in sorted(groups.items()):
        errors = [float(r['absolute_error']) for r in rows]
        summary.append(dict(zip(('family', 'residency', 'algorithm_status'), key),
                            scored_rows=len(rows), mae_pp=100*sum(errors)/len(rows),
                            tail_rows=sum(e > .25 for e in errors),
                            zero_forecast_positive_actual=sum(float(r['predicted_probability']) == 0
                                and float(r['actual_probability']) > 0 for r in rows),
                            overpredicted_rows=sum(float(r['predicted_probability']) > float(r['actual_probability']) for r in rows)))
    with (args.out_dir/'tail_rows.csv').open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(tails[0]) if tails else ['fold'])
        writer.writeheader()
        writer.writerows(tails)
    if hashlib.sha256(args.scores.read_bytes()).hexdigest() != digest:
        raise ValueError('Input changed during audit')
    result = {'scope': 'SAVED_SCORE_FEED_TRIAGE_NOT_NEW_CERTIFICATION',
              'source': str(args.scores), 'source_sha256': digest,
              'target_2026_excluded': True, 'scored_rows': len(seen),
              'tail_rows': len(tails), 'groups': summary}
    (args.out_dir/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
