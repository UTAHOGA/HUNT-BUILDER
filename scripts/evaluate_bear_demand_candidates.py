"""Freeze and compare opt-in demand candidates through the existing Bear owners.

This is isolated evaluation orchestration, not another model or runtime. All
known folds are retrospective development evidence, never new holdouts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_bear_controlled_candidates import (
    CROSSWALKS, canonical, digest, dump, new_directory, pdf_lanes,
    protected_data, read_rows, write_rows, year_dir,
)
from scripts.bear_grouped_uncertainty import review_groups, metric_values
import numpy as np

MODES = {
    'baseline': ('cohort_rollforward', 'simulation_mean', 200),
    'cumulative_stack': ('cumulative_stack', 'deterministic', 1),
    'joint_transition': ('cumulative_transition_ensemble', 'deterministic', 1),
    'adaptive_cumulative': ('adaptive_cumulative_stack', 'deterministic', 1),
}
CODE = [
    'engine/utah_draw_predictive/bear.py', 'engine/utah_draw_predictive/classifier.py',
    'engine/utah_draw_predictive/run_all_families.py',
    'engine/utah_predictive_mixed/materialize.py', 'engine/utah_predictive_mixed/quota.py',
    'scripts/audit_bear_controlled_candidates.py', 'scripts/build_blind_acceptance_review.py',
    'scripts/project_legacy_canonical_for_blind_scoring.py',
    'tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py',
    'scripts/bear_grouped_uncertainty.py', 'scripts/evaluate_bear_demand_candidates.py',
    'tests/utah_draw_predictive/test_bear_demand_transition_ensemble.py',
    'tests/utah_draw_predictive/test_bear_limited_evidence_policy.py',
]
POLICY = ['governance/bear-restricted-pursuit-limited-evidence.v1.json',
          'docs/decisions/ADR-0009-restricted-pursuit-limited-evidence-policy.md']


def freeze(out, candidate_set, scorer_snapshot=None):
    out = new_directory(out)
    dump(out / 'protected_before.json', protected_data())
    # Execute the uncertainty/group-integrity tests BEFORE scoring this revision.
    check = subprocess.run([sys.executable, '-m', 'pytest', CODE[-2], CODE[-1], '-q',
                            '--basetemp', str(out / 'pytest_basetemp')], cwd=ROOT,
                           capture_output=True, text=True)
    (out / 'pre_score_tests.txt').write_text(check.stdout + check.stderr, encoding='utf-8')
    if check.returncode:
        raise RuntimeError('Pre-score grouped uncertainty tests failed')
    paths, identities, census = set(), [], []
    cutoffs = {}
    for year in range(2017, 2026):
        if year < 2020:
            paths.add(canonical(year))
        else:
            paths.update((year_dir(year) / f'bear_{year}_pdf_point_lanes.csv',
                          year_dir(year) / 'pdf_extract_freeze.json'))
        if year > 2017:
            crosswalk = CROSSWALKS / f'pre_draw_hunt_identity_crosswalk_{year-1}_to_{year}.csv'
            paths.add(crosswalk)
            for row in read_rows(crosswalk):
                evidence = Path(row['target_application_evidence_file'])
                paths.add(evidence if evidence.is_absolute() else ROOT / evidence)
                code = row['to_hunt_code'] or row['from_hunt_code']
                if code.startswith('BR') and row['applicant_stack_carry_forward_allowed'] == 'FALSE':
                    cutoffs[code] = year
        lanes = pdf_lanes(year)
        grouped = defaultdict(list)
        for row in lanes:
            grouped[(row['draw_pool'], row['hunt_code'], row['residency'])].append(row)
        for (program, code, residency), rows in sorted(grouped.items()):
            census.append(dict(year=year, hunt_code=code, residency=residency, program=program,
                               point_rows=len(rows), applicants=sum(int(r['eligible_applicants']) for r in rows),
                               permits=sum(int(r['total_permits']) for r in rows),
                               source_files='|'.join(sorted({r['source_file'] for r in rows}))))
        for program, code in sorted({(key[0], key[1]) for key in grouped}):
            identities.append(dict(target_year=year, hunt_code=code, program=program,
                                   hunt_identity=code, program_regime=f'{program}:since_{cutoffs.get(code, 2017)}',
                                   grouping_basis='EXACT_CODE_PROGRAM_WITH_PRE_DRAW_REGIME_RESET',
                                   residencies_grouped_together=True))
    write_rows(out / 'official_history_census.csv', census)
    write_rows(out / 'frozen_identity_groups.csv', identities)
    code_paths = list(CODE)
    if scorer_snapshot:
        code_paths.remove('tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py')
        code_paths.append(scorer_snapshot.resolve().relative_to(ROOT).as_posix())
    manifest = {
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'APPLICANT_DEMAND_AND_FINAL_PROBABILITY_DEVELOPMENT_NOT_RELEASE',
        'policy_hashes': {p: digest(ROOT / p) for p in POLICY},
        'implementation_and_scorer_hashes': {p: digest(ROOT / p) for p in code_paths},
        'scorer_snapshot': scorer_snapshot.resolve().relative_to(ROOT).as_posix() if scorer_snapshot else None,
        'source_inventory_and_cutoff': {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)},
        'history_start': 2017, 'actual_cutoff': 2025,
        'fold_roster': [f'{y}_to_{y+1}' for y in range(2017, 2025)],
        'identity_groups_sha256': digest(out / 'frozen_identity_groups.csv'),
        'census_sha256': digest(out / 'official_history_census.csv'),
        'pre_score_tests_sha256': digest(out / 'pre_score_tests.txt'),
        'previously_viewed_results': 'All 2018-2025 results and prior five/eight-fold diagnostics were already viewed. None is a genuinely unseen holdout.',
        'eligibility_and_gap_rules': 'Existing frozen ADR-0006 scorer; source-only pre-draw crosswalks; existing owner no-transition gate. All numeric misses retained; every blank inventoried; no DATABASE history reads.',
        'parameters_and_seeds': {
            'modes': {name: MODES[name] for name in candidate_set}, 'history_start': 2017, 'returning_cohort_mode': 'off',
            'joint_recent_contiguous_transitions': 3, 'joint_persistence_scenarios': 2,
            'joint_average': 'MEAN_OF_COMPLETE_SCENARIO_PROBABILITIES_NOT_RECOMBINED_COMPONENT_MEANS',
            'existing_probability_ceiling_unchanged': .99,
            'baseline_simulation_seed': 20260701,
            'grouped_resampling_seed': 20260920, 'replicates_each_analysis': 10000,
            'adaptive_cumulative': {'recent_contiguous_transitions': 3,
                                    'cohort_blend_fit': 'SAME_HUNT_PROGRAM_RESIDENCY_SOURCE_TRANSITIONS_ONLY',
                                    'count_weight': '1/max(1,earlier_cumulative_count)',
                                    'blend_prior': .5, 'ridge_strength': 1.0,
                                    'innovation_shrinkage_zero_prior_count': 2},
        },
        'production_writes_allowed': False, 'threshold_changes_allowed': False,
    }
    dump(out / 'candidate_manifest.json', manifest)
    dump(out / 'candidate_manifest_seal.json', {'sha256': digest(out / 'candidate_manifest.json')})
    for path in code_paths:
        destination = out / 'implementation_snapshot' / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, destination)
    print(f'FROZEN {out}', flush=True)


def verify(out, *, frozen_snapshot_for_review=False):
    manifest = json.loads((out / 'candidate_manifest.json').read_text())
    if digest(out / 'candidate_manifest.json') != json.loads((out / 'candidate_manifest_seal.json').read_text())['sha256']:
        raise ValueError('Candidate manifest changed')
    for section in ('policy_hashes', 'implementation_and_scorer_hashes', 'source_inventory_and_cutoff'):
        for path, expected in manifest[section].items():
            if digest(ROOT / path) != expected:
                snapshot = out / 'implementation_snapshot' / path
                if not (frozen_snapshot_for_review and section == 'implementation_and_scorer_hashes'
                        and snapshot.is_file() and digest(snapshot) == expected):
                    raise ValueError(f'Frozen input/code changed: {path}')
    for filename, key in [('frozen_identity_groups.csv', 'identity_groups_sha256'),
                          ('official_history_census.csv', 'census_sha256'), ('pre_score_tests.txt', 'pre_score_tests_sha256')]:
        if digest(out / filename) != manifest[key]:
            raise ValueError(f'Frozen evidence changed: {filename}')
    if protected_data() != json.loads((out / 'protected_before.json').read_text()):
        raise ValueError('Protected production bytes changed')
    return manifest


def run(out, mode):
    manifest = verify(out)
    demand, central, iterations = manifest['parameters_and_seeds']['modes'][mode]
    command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/audit_bear_controlled_candidates.py'),
               '--phase', 'folds', '--out-dir', str(out / mode), '--history-start', '2017',
               '--source-start', '2017', '--source-end', '2024', '--demand-mode', demand,
               '--central-estimate', central, '--iterations', str(iterations)]
    if manifest.get('scorer_snapshot'):
        scorer = manifest['scorer_snapshot']
        command.extend(['--scorer-snapshot', str(ROOT / scorer), '--scorer-sha256',
                        manifest['implementation_and_scorer_hashes'][scorer]])
    # Each forecast sub-process installs the source-read guard before owner imports.
    with (out / f'{mode}_run.log').open('x', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    verify(out)
    if result.returncode:
        raise RuntimeError(f'{mode} failed; retain its log and partial artifacts')
    print(f'COMPLETED {mode}', flush=True)


def review(out):
    manifest = verify(out, frozen_snapshot_for_review=True)
    dump(out / 'review_implementation_hashes.json', {
        'frozen_model_snapshots_verified': True,
        'evaluation_orchestrator': digest(Path(__file__)),
        'grouped_uncertainty': digest(ROOT / 'scripts/bear_grouped_uncertainty.py'),
        'post_score_report_repair': 'Native JSON integer serialization; no score, grouping, resampling or model change.',
    })
    identities = {(r['target_year'], r['program'], r['hunt_code']): r
                  for r in read_rows(out / 'frozen_identity_groups.csv')}
    summaries, paired, keys_by_mode = [], [], {}
    for mode in manifest['parameters_and_seeds']['modes']:
        base = out / mode
        all_scored = read_rows(base / 'final_scored_rows.csv')
        keys_by_mode[mode] = {(r['fold'], r['draw_design'], r['hunt_code'], r['residency'], r['points']) for r in all_scored}
        for row in all_scored:
            row['target_year'] = int(row['fold'].split('_to_')[1])
            program = 'RESTRICTED_BEAR_PURSUIT' if 'PURSUIT' in row['draw_design'] else 'LIMITED_ENTRY_BEAR_HUNT'
            identity = identities[(str(row['target_year']), program, row['hunt_code'])]
            row.update(hunt_identity=identity['hunt_identity'], program_regime=identity['program_regime'])
        by_group = defaultdict(list)
        for row in all_scored:
            for window in ['eight_folds'] + (['recent_five_folds'] if row['target_year'] >= 2021 else []):
                for lane in ['POOLED_DESIGN', row['residency']]:
                    by_group[(window, row['draw_design'], lane)].append(row)
        for (window, design, lane), rows in sorted(by_group.items()):
            errors = np.asarray([float(r['predicted_probability']) - float(r['actual_probability']) for r in rows])
            summaries.append(dict(candidate=mode, window=window, design=design, residency=lane,
                                  rows=len(rows), **metric_values(errors)))
        pursuit = [r for r in all_scored if 'PURSUIT' in r['draw_design']]
        dump(out / f'{mode}_pursuit_grouped_uncertainty.json', review_groups(pursuit))
        final_verified = 0
        diagnostics, gaps, demand_errors = [], [], []
        inventory, uncapped = Counter(), Counter()
        for fold_name in manifest['fold_roster']:
            folder = base / fold_name / 'prediction_phase'
            frozen = json.loads((folder / 'forecast_freeze.json').read_text())
            if frozen['historical_database_csv_read_count'] or frozen['target_result_read_count']:
                raise ValueError('Historical source boundary failed')
            for stage in ('family', 'final'):
                if digest(folder / f'{stage}_predictions.csv') != frozen[f'{stage}_sha256']:
                    raise ValueError('Forecast bytes changed after scoring')
            key = lambda r: (r['hunt_code'], r['residency'], r['points'])
            family = {key(r): r for r in read_rows(folder / 'family_predictions.csv')}
            actual = {key(r): r for r in read_rows(base / fold_name / 'actual_projection.csv')}
            actual_lanes = defaultdict(list)
            for row in actual.values():
                actual_lanes[(row['hunt_code'], row['residency'])].append(row)
            for row in read_rows(folder / 'final_predictions.csv'):
                if row['p_draw'] != family[key(row)]['p_draw']:
                    raise ValueError('Final website calculation changed family probability')
                final_verified += 1
            comparison = base / fold_name / 'final_comparison'
            for row in read_rows(comparison / 'draw_line_aware_actual_ladder_scoring_rows.csv'):
                inventory[row['scoring_decision']] += 1
            gaps.extend({**r, 'fold': fold_name} for r in read_rows(comparison / 'draw_line_aware_actual_gap_classifications.csv'))
            for row in [r for r in all_scored if r['fold'] == fold_name]:
                prediction, observed = family[key(row)], actual[key(row)]
                above = sum(int(r['eligible_applicants']) for r in actual_lanes[key(row)[:2]]
                            if int(r['points']) > int(row['points']))
                before_ceiling = prediction.get('p_draw_before_existing_ceiling', '')
                false_certainty = bool(before_ceiling and float(before_ceiling) >= .999999
                                       and float(row['actual_probability']) < .999999)
                uncapped[row['draw_design']] += int(false_certainty)
                detail = {**row, 'forecast_applicants_above': prediction['applicants_above'],
                          'actual_applicants_above': above,
                          'forecast_applicants_at_level': prediction['applicants_at_level'],
                          'actual_applicants_at_level': observed['eligible_applicants'],
                          'p_draw_before_existing_ceiling': before_ceiling,
                          'uncapped_false_certainty': false_certainty,
                          'actual_pdf': observed['source_file'], 'actual_pdf_page': observed['pdf_page'],
                          'removed_from_accuracy': False}
                demand_errors.append(detail)
                if float(row['absolute_error']) > .25:
                    diagnostics.append(detail)
        write_rows(out / f'{mode}_demand_and_probability_diagnostics.csv', demand_errors)
        write_rows(out / f'{mode}_large_errors.csv', diagnostics)
        write_rows(out / f'{mode}_all_actual_gaps.csv', gaps)
        dump(out / f'{mode}_final_contract.json', {'verified_rows': final_verified,
                                                 'family_probability_equals_final_probability': True,
                                                 'source_boundary_passed_all_folds': True,
                                                 'uncapped_false_certainty': dict(uncapped),
                                                 'existing_ceiling_unchanged': .99,
                                                 'actual_inventory': dict(inventory),
                                                 'gap_classifications': dict(Counter(r['actual_gap_classification'] or 'UNRESOLVED' for r in gaps)),
                                                 'unresolved_gaps': sum(r['certification_gap_status'] == 'UNRESOLVED' for r in gaps)})
        paired.extend({**r, 'candidate': mode} for r in all_scored)
    if any(keys != keys_by_mode['baseline'] for keys in keys_by_mode.values()):
        raise ValueError('Candidate changed scored coverage; inspect before comparing accuracy')
    write_rows(out / 'candidate_metrics.csv', summaries)
    write_rows(out / 'all_candidate_scored_rows.csv', paired)
    after = protected_data()
    dump(out / 'protected_after.json', {'files': after, 'changed': []})
    dump(out / 'evaluation_status.json', {
        'production_written': False, 'default_model_changed': False,
        'same_scored_keys_for_all_candidates': True, 'release_decision': 'DO_NOT_PROMOTE',
        'unseen_validation': False, 'official_history_years': '2017-2025',
        'protected_files_byte_identical': len(after),
        'certification_registry_changed': False,
    })
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['freeze', 'run', 'review'])
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--mode', choices=list(MODES))
    parser.add_argument('--candidate-set', nargs='+', choices=list(MODES), default=list(MODES))
    parser.add_argument('--scorer-snapshot', type=Path)
    args = parser.parse_args()
    if args.phase == 'freeze':
        freeze(args.out_dir, args.candidate_set, args.scorer_snapshot)
    elif args.phase == 'run':
        if not args.mode:
            parser.error('--mode required for run')
        run(args.out_dir.resolve(), args.mode)
    else:
        review(args.out_dir.resolve())
