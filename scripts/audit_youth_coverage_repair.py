"""Verify all original blocking keys and the exact authorized forecast delta."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.utah_draw_predictive.run_all_families import _youth_reserve_input_placeholder
from scripts.project_legacy_canonical_for_blind_scoring import sha256


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        yield from csv.DictReader(handle)


def key(row):
    return tuple(row[k] for k in ('draw_design_key', 'draw_pool_key', 'hunt_code', 'residency', 'points'))


def audit(base, original_gaps):
    output = base/'coverage_repair_integrity.json'
    if output.exists():
        raise ValueError('Refusing to overwrite evidence')
    ledger = list(rows(base/'placeholder_handoff_ledger.csv'))
    gaps = [r for r in rows(original_gaps) if r['certification_gap_status'] == 'BLOCKING_ENGINE_GAP']
    failures, resolution, fold_results = [], [], []
    for year in range(2017, 2026):
        fold = base/f'source_{year}'/f'{year}_to_{year+1}'
        candidate = fold/'prediction_phase/final_public_predictions.csv'
        freeze = json.loads((candidate.parent/'candidate_freeze.json').read_text(encoding='utf-8'))
        original = Path(freeze['original_final'])
        if sha256(original) != freeze['original_sha256'] or sha256(candidate) != freeze['final_sha256']:
            failures.append(f'{year}: frozen forecast hash changed')
        excluded = {int(r['original_csv_line']) for r in ledger if int(r['source_year']) == year}
        remaining = iter(rows(candidate))
        matched = 0
        for line, before in enumerate(rows(original), 2):
            if line in excluded:
                if not _youth_reserve_input_placeholder(before):
                    failures.append(f'{year}: excluded non-placeholder {line}')
                continue
            after = next(remaining, None)
            if after is None or any(before.get(k, '') != after.get(k, '') for k in set(before) | set(after)):
                failures.append(f'{year}: existing forecast changed at original row {line}')
            matched += 1
        added = list(remaining)
        if matched != freeze['original_rows_preserved'] or len(added) != freeze['fallback_rows_added']:
            failures.append(f'{year}: row accounting mismatch')
        for row in added:
            if row.get('family') != 'youth_draw' or row.get('model_strategy') != 'youth_draw_source_backed_roll_forward':
                failures.append(f'{year}: unauthorized family/strategy addition')
            if int(row['source_year']) != year or not row.get('source_file'):
                failures.append(f'{year}: invalid source lineage')
        score_file = fold/'comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv'
        scored = Counter(key(r) for r in rows(score_file) if r['scoring_decision'] == 'score_probability')
        if any(count != 1 for count in scored.values()):
            failures.append(f'{year}: duplicate scored key')
        sidecar = fold/'comparison_phase/draw_line_aware_actual_gap_classifications.csv'
        classified = {key(r): r for r in rows(sidecar)} if sidecar.exists() else {}
        counts = Counter()
        for old in gaps:
            if int(old['source_year']) != year:
                continue
            k = key(old)
            status = 'NOW_SCORED' if k in scored else classified.get(k, {}).get('certification_gap_status', 'MISSING_FROM_REVIEW')
            counts[status] += 1
            resolution.append({**old, 'repair_resolution': status})
            if status not in {'NOW_SCORED', 'SOURCE_CLASSIFIED'}:
                failures.append(f'{year}: original gap not resolved {k}: {status}')
        fold_results.append(dict(source_year=year, original_gaps=sum(counts.values()), resolution_counts=dict(counts),
                                 preserved_forecast_rows=matched, added_source_fallback_rows=len(added),
                                 repeated_scored_keys=sum(n-1 for n in scored.values())))
    with (base/'original_gap_resolution.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(resolution[0]))
        writer.writeheader()
        writer.writerows(resolution)
    result = dict(status='PASS' if not failures else 'FAIL', failures=failures, folds=fold_results,
                  original_blocking_gaps=len(gaps), resolution_counts=dict(Counter(r['repair_resolution'] for r in resolution)),
                  original_gap_file_sha256=sha256(original_gaps), certified_or_deployed=False)
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--original-gaps', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(audit(args.candidate, args.original_gaps))
