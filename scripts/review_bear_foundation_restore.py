"""Review frozen Bear replays without changing forecasts, truth or acceptance.

The eight historical folds and the following-year diagnostic stay separate.
Numeric errors never become exclusions. The pre-existing probability ceiling
is audited explicitly rather than being used to claim absence of certainty risk.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_bear_controlled_candidates import (
    digest, dump, new_directory, pdf_lanes, protected_data, read_rows, write_rows,
)
from scripts.build_blind_acceptance_review import (
    FALSE_GUARANTEE_THRESHOLD, THRESHOLDS, load_draw_line_fold, metrics,
)


def key(row):
    return row['hunt_code'], row['residency'], str(row['points'])


def unique(rows):
    result = {}
    for row in rows:
        if key(row) in result:
            raise ValueError(f'Duplicate replay key: {key(row)}')
        result[key(row)] = row
    return result


def lineage(rows):
    return json.dumps(sorted({(r.get('source_file', ''), r.get('pdf_page', ''),
                               r.get('source_path', '')) for r in rows}), separators=(',', ':'))


def write_diagnostics(path, rows, fields):
    """Keep the diagnostic schema even when no rows have this failure."""
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def review(base: Path, out: Path):
    out = new_directory(out)
    before = protected_data()
    scored, details, blanks, gaps, folds = [], [], [], [], []
    freezes = []
    for source_year in range(2017, 2026):
        window = 'eight_folds' if source_year < 2025 else 'diagnostic_2025_2026'
        folder = base / window / f'{source_year}_to_{source_year + 1}'
        predictions = folder / 'prediction_phase'
        freeze_path = predictions / 'forecast_freeze.json'
        frozen = json.loads(freeze_path.read_text())
        if frozen['historical_database_csv_read_count'] or frozen['target_result_read_count']:
            raise ValueError('Historical forecast read prohibited data')
        if not frozen['read_guard_installed_before_model_imports']:
            raise ValueError('Historical read guard not installed')
        for stage in ('family', 'final'):
            if digest(predictions / f'{stage}_predictions.csv') != frozen[f'{stage}_sha256']:
                raise ValueError(f'Forecast changed after freeze: {folder}/{stage}')
        for path, expected in frozen['source_hashes'].items():
            if digest(ROOT / path) != expected:
                raise ValueError(f'Frozen source changed: {path}')
        if digest(ROOT / frozen['scorer_source_file']) != frozen['scorer_sha256']:
            raise ValueError('Scorer snapshot changed')
        freezes.append({'fold': folder.name, 'sha256': digest(freeze_path), **frozen})
        family = unique(read_rows(predictions / 'family_predictions.csv'))
        final = unique(read_rows(predictions / 'final_predictions.csv'))
        if set(family) != set(final) or any(family[k]['p_draw'] != final[k]['p_draw'] for k in family):
            raise ValueError('Final website entrypoint changed Bear probabilities or coverage')
        source = pdf_lanes(source_year)
        actual = unique(read_rows(folder / 'actual_projection.csv'))
        # Source inspection happens after predictions are frozen, for diagnosis only.
        source_lanes = {}
        for row in source:
            source_lanes.setdefault((row['hunt_code'], row['residency'], row['draw_pool']), []).append(row)
        comparison = folder / 'final_comparison'
        joined = load_draw_line_fold(folder.name, comparison / 'draw_line_aware_prediction_vs_actual_rowlevel.csv')
        scored.extend(joined)
        for row in joined:
            pred = family[key(row)]
            observed = actual[key(row)]
            program = observed['draw_pool']
            prior = source_lanes.get((row['hunt_code'], row['residency'], program), [])
            rung = [r for r in prior if str(r['points']) == str(row['points'])]
            predecessor = [r for r in prior if int(r['points']) == int(row['points']) - 1]
            target_lane = [r for r in actual.values() if key(r)[:2] == key(row)[:2]
                           and r['draw_pool'] == program]
            before_ceiling = pred.get('p_draw_before_existing_ceiling', '')
            detail = {
                **row, 'window': window, 'bear_draw_subtype': program,
                'source_year': source_year, 'target_year': source_year + 1,
                'source_lane_present': bool(prior),
                'source_official_applicants_at_rung': sum(int(r['eligible_applicants']) for r in rung),
                'source_predecessor_unsuccessful': sum(int(r['eligible_applicants']) - int(r['total_permits']) for r in predecessor),
                'source_official_total_permits_lane': sum(int(r['total_permits']) for r in prior),
                'target_official_total_permits_lane': sum(int(r['total_permits']) for r in target_lane),
                'target_official_applicants_at_rung': observed['eligible_applicants'],
                'target_official_bonus_permits': observed['bonus_permits'],
                'target_official_regular_permits': observed['regular_permits'],
                'forecast_applicants_above': pred.get('applicants_above', ''),
                'actual_applicants_above': sum(int(r['eligible_applicants']) for r in target_lane if int(r['points']) > int(row['points'])),
                'forecast_quota_proxy': pred.get('forecast_quota_proxy', ''),
                'quota_source_type': pred.get('quota_source_type', ''),
                'algorithm_status': pred.get('algorithm_status', ''),
                'p_draw_before_existing_ceiling': before_ceiling,
                'uncapped_false_certainty': bool(before_ceiling and float(before_ceiling) >= FALSE_GUARANTEE_THRESHOLD
                                               and float(row['actual_probability']) < FALSE_GUARANTEE_THRESHOLD),
                'source_lineage': lineage(prior), 'target_lineage': lineage([observed]),
                'removed_from_accuracy': False,
            }
            details.append(detail)
        for row in family.values():
            if row.get('algorithm_status') != 'NO_TRANSITION_EVIDENCE':
                continue
            prior = source_lanes.get((row['hunt_code'], row['residency'], row.get('bear_draw_subtype')), [])
            blanks.append({**row, 'fold': folder.name, 'window': window,
                           'source_lane_lineage': lineage(prior),
                           'target_lineage_for_review_only': lineage([actual[key(row)]]) if key(row) in actual else '[]'})
        for row in read_rows(comparison / 'draw_line_aware_actual_gap_classifications.csv'):
            gaps.append({**row, 'fold': folder.name, 'window': window})
        for design in sorted({r['draw_design'] for r in joined}):
            folds.append({'fold': folder.name, 'window': window, 'draw_design': design,
                          **metrics([r for r in joined if r['draw_design'] == design])})

    summary = {'status': 'NOT_CERTIFIED', 'thresholds': THRESHOLDS,
               'known_retrospective_results_not_new_unseen_holdouts': True,
               'eight_fold_acceptance': json.loads((base / 'eight_folds/acceptance_summary.json').read_text())['results']['final'],
               'diagnostic_2025_2026': json.loads((base / 'diagnostic_2025_2026/acceptance_summary.json').read_text())['results']['final'],
               'nine_fold_descriptive_only': [], 'per_fold': folds,
               'existing_probability_ceiling': 0.99,
               'ceiling_not_evidence_that_structural_certainty_is_fixed': True,
               'gap_classifications': dict(Counter(r['actual_gap_classification'] for r in gaps)),
               'unresolved_gap_rows': sum(r['certification_gap_status'] != 'SOURCE_CLASSIFIED' for r in gaps),
               'source_only_reasoned_blanks': len(blanks),
               'zero_forecast_positive_actual_rows': sum(float(r['predicted_probability']) == 0 and float(r['actual_probability']) > 0 for r in details),
               'false_certainty_before_ceiling': sum(r['uncapped_false_certainty'] for r in details),
               'truth_or_runtime_written': False, 'registry_changed': False}
    for design in sorted({r['draw_design'] for r in scored}):
        summary['nine_fold_descriptive_only'].append({'draw_design': design,
            **metrics([r for r in scored if r['draw_design'] == design]),
            'uncapped_false_certainty_rows': sum(r['uncapped_false_certainty'] for r in details if r['draw_design'] == design)})
    outputs = {
        'bear_all_scored_diagnostics.csv': details,
        'bear_high_error_rows.csv': [r for r in details if float(r['absolute_error']) > .25],
        'bear_zero_forecast_positive_actual.csv': [r for r in details if float(r['predicted_probability']) == 0 and float(r['actual_probability']) > 0],
        'bear_uncapped_false_certainty.csv': [r for r in details if r['uncapped_false_certainty']],
        'bear_reasoned_blanks.csv': blanks, 'bear_actual_gaps.csv': gaps,
    }
    for filename, rows in outputs.items():
        fields = list(dict.fromkeys(field for row in rows for field in row)) if rows else list(details[0])
        write_diagnostics(out / filename, rows, fields)
    after = protected_data()
    dump(out / 'protected_file_verification.json', {'before': before, 'after': after, 'unchanged': before == after})
    if before != after:
        raise ValueError('Protected files changed during review')
    dump(out / 'forecast_freeze_inventory.json', freezes)
    summary['output_inventory'] = {name: {'rows': len(rows), 'sha256': digest(out / name)} for name, rows in outputs.items()}
    dump(out / 'bear_nine_fold_gate_summary.json', summary)
    print(json.dumps(summary, indent=2))
    return 1  # This review cannot authorize promotion.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(review(args.base, args.out_dir))
