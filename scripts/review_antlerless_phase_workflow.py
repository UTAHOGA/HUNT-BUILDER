"""Retain measured phase-workflow evidence without overwriting prior audits.

This is an audit/report adapter, not an engine or a certification registry writer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / 'audits/prediction_release_candidates/antlerless_certification_review_20260921_v1'
sys.path[:0] = [str(ROOT), str(RETAINED)]
from assess_candidate import FAMILIES, grouped, metrics, read, sha
from engine.utah_draw_predictive.preference_antlerless import (
    _build_truth_ladders, _target_draw_system_type, _band_for_points,
)
from engine.utah_draw_predictive.run_all_families import _with_historical_target_metadata

CANONICAL = ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly'
PDF = 'pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf'
RESOLVER = 'scripts/resolve-antlerless-hunt-codes-2026.py'
DATABASE = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'
PREDICTIVE = 'processed_data/draw_reality_engine_predictive_v2.csv'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def inventory(out):
    import pdfplumber
    if out.exists() and any(out.iterdir()):
        raise ValueError('Refusing to overwrite retained audit evidence')
    out.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / p for p in (PDF, RESOLVER, DATABASE, PREDICTIVE,
        'processed_data/point_ladder_view.csv',
        'data_truth/draw_results_truth/normalized/draw_results_long.csv',
        'governance/prediction-family-certification.json')]
    paths += sorted(CANONICAL.glob('*.csv'))
    paths += [p for p in (ROOT / 'audit_output_real_final').rglob('*') if p.is_file()]
    paths += [p for p in (ROOT / 'audit_output_phase1_candidate').rglob('*') if p.is_file() and out not in p.parents]
    protected = {p.relative_to(ROOT).as_posix(): {'exists': p.is_file(), 'sha256': sha(p) if p.is_file() else None,
                 'bytes': p.stat().st_size if p.is_file() else None} for p in paths}
    years = Counter()
    with (ROOT / 'data_truth/draw_results_truth/normalized/draw_results_long.csv').open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            years[row.get('actual_draw_year', '')] += 1
    with pdfplumber.open(ROOT / PDF) as pdf:
        pages = len(pdf.pages)
    spec = importlib.util.spec_from_file_location('resolver_read_only_probe', ROOT / RESOLVER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    source_ok = (protected[PDF]['sha256'] == module.EXPECTED_SHA256
                 and protected[PDF]['bytes'] == module.EXPECTED_SIZE_BYTES
                 and pages == module.EXPECTED_PAGES)
    result = {'protected': protected, 'long_actual_year_counts': dict(sorted(years.items())),
              'missing_2017_2025_years': [y for y in range(2017, 2026) if not years[str(y)]],
              'pdf_pages_measured': pages, 'pdf_signature_matches_resolver': source_ok,
              'resolver_sha256_is_not_pdf_sha256': protected[PDF]['sha256'] != protected[RESOLVER]['sha256']}
    write_json(out / 'truth_inventory.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'protected'}, indent=2))
    if not source_ok or result['missing_2017_2025_years'] or any(not v['exists'] for v in protected.values()):
        raise SystemExit('Truth inventory blocked; inspect measured inventory')


def report(out, forecasts, baseline):
    if (out / 'cert_report.json').exists():
        raise ValueError('Refusing to overwrite retained completed review')
    scores = read(forecasts / 'full_adult_census/scores.csv')
    census = read(forecasts / 'full_adult_census/census.csv')
    baseline_scores = read(baseline / 'full_adult_census/scores.csv')
    projector_spec = importlib.util.spec_from_file_location('report_official_actuals', RETAINED/'exact_year_adult_pool_diagnostic.py')
    projector = importlib.util.module_from_spec(projector_spec)
    projector_spec.loader.exec_module(projector)
    official_source_lanes, intake_differences, intake_compared = set(), [], 0
    target_ladders = defaultdict(dict)
    for row in census:
        target_ladders[(row['source_year'], row['draw_design_key'], row['hunt_code'], row['residency'])][int(row['points'])] = row
    for year in range(2017, 2026):
        predictions = {(r['draw_system_type'], r['hunt_code'], r['residency'], r['points']): r for r in read(forecasts / f'{year}_forecast.csv')}
        for row in (r for r in scores if r['source_year'] == str(year)):
            key = (row['draw_design_key'], row['hunt_code'], row['residency'], row['points'])
            prediction = predictions[key]
            ladder = target_ladders[(str(year), *key[:3])]
            quota = float(prediction['public_permits_2026'])
            above = float(prediction['applicants_above'])
            at = float(prediction['probability_applicant_count'])
            row.update(forecast_quota_proxy=quota, forecast_applicants_above=above,
                forecast_applicants_at_level=prediction['applicants_at_level'],
                source_hunt_name=prediction.get('hunt_name', ''),
                target_awards_diagnostic_only=sum(float(r['regular_awards'] or 0) for r in ladder.values()),
                target_applicants_above_diagnostic_only=sum(float(r['applicants'] or 0) for p, r in ladder.items() if p > int(key[3])),
                uncapped_mechanical_full_allocation=quota >= above+at,
                existing_tail_ceiling_in_reason='PREFERENCE_TAIL_CALIBRATED_FROM_REPO_BACKTEST' in prediction.get('reason_codes', ''))
    source_evidence, source_ladders, gap_rows, profile_support = {}, {}, [], []
    hist_ladders = {}
    original_normalizer = subprocess.check_output(['git', 'show', 'HEAD:engine/utah_draw_predictive/preference_ladder_normalizer.py'], cwd=ROOT).decode('utf-8')
    current_normalizer_path = ROOT / 'engine/utah_draw_predictive/preference_ladder_normalizer.py'
    current_normalizer = current_normalizer_path.read_text(encoding='utf-8')
    normalizer_change_is_field_preservation_only = current_normalizer == original_normalizer.replace('    "draw_design",\n', '    "draw_design",\n    "allocation_type",\n')
    added_field_in_replay_inputs = 0
    for year in range(2017, 2026):
        source = read(CANONICAL / f'draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv')
        source_actuals, _, conflicts = projector.actual_points(source, year)
        if conflicts:
            raise ValueError(f'Conflicting source actuals: {year}')
        official_source_lanes.update((str(year), *key[:3]) for key in source_actuals)
        engine_source = _with_historical_target_metadata(source, year, year+1)
        added_field_in_replay_inputs += sum('allocation_type' in r for r in engine_source)
        ladders, _, _ = _build_truth_ladders(engine_source, {year})
        hist_ladders.update(ladders)
        parents_by_code = defaultdict(set)
        for source_row in source:
            if source_row.get('source_file'):
                parents_by_code[source_row.get('hunt_code')].add(source_row['source_file'])
        for (family, _, code, pool, lane), ladder in ladders.items():
            key = (str(year), family, code, lane)
            if key in source_evidence:
                raise ValueError(f'Ambiguous source pool: {key}')
            source_ladders[key] = ladder
            for point, counts in ladder.items():
                actual = source_actuals.get((family, code, lane, str(point)))
                if actual is not None:
                    intake_compared += 1
                    if counts['eligible'] != actual['applicants'] or counts['drawn'] != actual['regular_awards']:
                        intake_differences.append({'source_year': year, 'family': family, 'hunt_code': code, 'residency': lane,
                            'points': point, 'engine': counts, 'official': actual})
            parents = sorted(parents_by_code[code])
            source_evidence[key] = {'source_lane_present': True, 'source_pool': pool,
                                   'source_lane_regular_awards': sum(v['drawn'] for v in ladder.values()),
                                   'source_files': '|'.join(p for p in parents if p)}
        supports = defaultdict(list)
        for (fam, prior_year, code, pool, lane), ladder in hist_ladders.items():
            nxt = hist_ladders.get((fam, prior_year+1, code, pool, lane))
            if nxt is None:
                continue
            for point, counts in ladder.items():
                if counts['eligible'] > counts['drawn']:
                    supports[(fam, code, pool, lane, _band_for_points(point))].append(prior_year)
        for key, years in supports.items():
            if len(years) >= 2 and len(set(years)) < 2:
                profile_support.append(dict(source_year=year, family=key[0], hunt_code=key[1], draw_pool=key[2],
                    residency=key[3], point_band=key[4], rung_observations=len(years), independent_transitions=len(set(years))))
    for row in census:
        if not row['classification'].startswith('MISSING_FORECAST'):
            continue
        key = (row['source_year'], row['draw_design_key'], row['hunt_code'], row['residency'])
        evidence = source_evidence.get(key, {'source_lane_present': False, 'source_lane_regular_awards': 0, 'source_files': ''})
        if row['forecast_algorithm_status'] == 'NO_TRANSITION_EVIDENCE':
            classification = 'NO_PROGRAM_RESIDENCY_TRANSITION_EVIDENCE'
        elif not evidence['source_lane_present']:
            classification = 'UNRESOLVED_SOURCE_ROUTING' if key in official_source_lanes else 'NO_EXACT_SOURCE_ADULT_RESIDENCY_LANE'
        elif evidence['source_lane_regular_awards'] <= 0:
            classification = 'SOURCE_LANE_ZERO_REGULAR_AWARDS_PROXY'
        else:
            classification = 'UNRESOLVED_ENGINE_COVERAGE'
        ladder = source_ladders.get(key, {})
        point = int(row['points'])
        prior = ladder.get(point-1, {})
        gap_rows.append({**row, **evidence, 'source_same_point_present': point in ladder,
                         'prior_point': point-1 if point > 0 else '',
                         'prior_point_applicants': prior.get('eligible', ''),
                         'prior_point_regular_awards': prior.get('drawn', ''),
                         'coverage_classification': classification})
    for row in scores:
        row['absolute_error_pp'] = abs(float(row['predicted_probability'])-float(row['actual_probability']))*100
    write_csv(out / 'coverage_gap_classifications.csv', gap_rows)
    write_csv(out / 'single_transition_multi_rung_profiles.csv', profile_support)
    write_csv(out / 'draw_line_aware_prediction_vs_actual.csv', scores)
    write_csv(out / 'draw_line_aware_prediction_vs_actual_by_family.csv', grouped(scores, ('draw_design_key',)))
    write_csv(out / 'hunt_metrics.csv', grouped(scores, ('draw_design_key', 'hunt_code', 'residency')))
    write_csv(out / 'fold_metrics.csv', grouped(scores, ('draw_design_key', 'source_year', 'target_year')))
    saved = read(ROOT / PREDICTIVE)
    private_codes = {r['hunt_code'] for r in read(ROOT / 'pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/elk antlerless private lands only EA.csv')}
    database = read(ROOT / DATABASE)
    probabilities = ('p_draw', 'p_draw_mean', 'p_draw_pct', 'p_preference_draw', 'certified_p_draw', 'certified_p_draw_mean', 'certified_p_draw_pct')
    private = [dict(hunt_code=r['hunt_code'], owner_excluded=_target_draw_system_type(r) is None,
                    saved_probability_rows=sum(any(str(p.get(f, '')).strip() for f in probabilities) for p in saved if p['hunt_code'] == r['hunt_code']))
               for r in database if r['hunt_code'] in private_codes]
    write_csv(out / 'private_lands_exclusions.csv', private)
    refs = [r for r in saved if r.get('model_version') == 'antlerless_reference_v1.0.0']
    decisions, breakdown = [], {}
    for family in FAMILIES:
        rows = [r for r in scores if r['draw_design_key'] == family]
        old = [r for r in baseline_scores if r['draw_design_key'] == family]
        m = metrics(rows)
        worst = sorted(rows, key=lambda r: abs(float(r['predicted_probability'])-float(r['actual_probability'])), reverse=True)[:20]
        gaps = [r for r in gap_rows if r['draw_design_key'] == family]
        checks = {'mae_le_10pp': m['mae_pp'] is not None and m['mae_pp'] <= 10,
                  'p90_le_30pp': m['p90_pp'] is not None and m['p90_pp'] <= 30,
                  'tail_over_25pp_le_10pct': m['tail_over_25pp_pct'] is not None and m['tail_over_25pp_pct'] <= 10,
                  'requested_tail_over_20pp_le_10pct': m['tail_over_20pp_pct'] is not None and m['tail_over_20pp_pct'] <= 10,
                  'rows_ge_400': len(rows) >= 400, 'folds_ge_2': len({r['source_year'] for r in rows}) >= 2,
                  'zero_false_guarantees': m['false_guarantees'] == 0,
                  'no_unresolved_gaps': all(not r['coverage_classification'].startswith('UNRESOLVED') for r in gaps),
                  'intake_numeric_parity': not intake_differences}
        decisions.append({'family': family, **m, 'checks': checks, 'metric_result': 'PASS' if all(checks.values()) else 'FAIL',
                          'status': 'EXPERIMENTAL_NOT_CERTIFIED', 'promote': False})
        breakdown[family] = {**m, 'baseline_metrics': metrics(old), 'prefix_counts': dict(Counter(r['hunt_code'][:2] for r in rows)),
            'top_20_worst_point_rows': worst, 'coverage_counts': dict(Counter(r['coverage_classification'] for r in gaps)),
            'uncapped_full_allocation_misses_diagnostic': sum(r['uncapped_mechanical_full_allocation'] and float(r['actual_probability']) < .999999 for r in rows),
            'early_known_folds_2017_2022': metrics([r for r in rows if int(r['source_year']) <= 2022]),
            'known_2023_to_2024': metrics([r for r in rows if r['source_year'] == '2023']),
            'known_2024_to_2025': metrics([r for r in rows if r['source_year'] == '2024']),
            'diagnostic_2025_to_2026': metrics([r for r in rows if r['source_year'] == '2025'])}
    # Code-number ranges are not evidence of a season or public allocation.
    breakdown['elk_subgroups'] = {'status': 'NO_POST_HOC_CERTIFICATION_SPLIT',
        'private_lands': {'codes': len(private), 'probability_violations': sum(r['saved_probability_rows'] for r in private), 'status': 'NO_PROBABILITY'},
        'note': 'Do not declare EA1000-EA1100 public or cherry-pick late/high-point exclusions from error. All scored elk remain in their declared design.'}
    cwmu = [r for r in saved if r.get('draw_system_type') == 'BONUS_CWMU_BIG_GAME']
    breakdown['CWMU'] = {'status': 'INSUFFICIENT_CURRENT_CANDIDATE_EVIDENCE', 'saved_rows': len(cwmu),
        'saved_numeric_rows': sum(bool(str(r.get('p_draw', '')).strip()) for r in cwmu),
        'reason': 'Current special_bonus owner explicitly disables CWMU public materialization; preference antlerless is not its bonus engine. Old scores cannot certify this candidate.'}
    decisions.append({'family': 'BONUS_CWMU_BIG_GAME', 'metric_result': 'BLOCKED', 'status': 'INSUFFICIENT_EVIDENCE', 'promote': False})
    write_json(out / 'species_hunt_breakdown.json', breakdown)
    write_json(out / 'online_hunt_codes.json', {'newly_eligible_for_probability_promotion': [], 'deployed': [], 'existing_live_designs_unchanged': True})
    before = json.loads((out / 'truth_inventory.json').read_text())['protected']
    changes = {p: {'before': v['sha256'], 'after': sha(ROOT/p) if (ROOT/p).is_file() else None}
               for p, v in before.items() if v['sha256'] != (sha(ROOT/p) if (ROOT/p).is_file() else None)}
    hashes = {p.name: sha(p) for p in out.glob('*.csv')}
    normalizer_evidence = {'change_during_replay': 'Preserve allocation_type in collapsed lane metadata',
        'only_added_shared_field': normalizer_change_is_field_preservation_only,
        'source_input_rows_containing_added_field': added_field_in_replay_inputs,
        'behavior_equivalent_on_replayed_inputs': normalizer_change_is_field_preservation_only and added_field_in_replay_inputs == 0,
        'loaded_normalizer_git_blob_sha256': hashlib.sha256(original_normalizer.encode()).hexdigest(),
        'current_normalizer_sha256': sha(current_normalizer_path)}
    replay_evidence_path = out/'replay_implementation_verification.json'
    if replay_evidence_path.exists():
        replay_evidence = json.loads(replay_evidence_path.read_text())
        normalizer_evidence = {
            'loaded_current_normalizer_before_forecasts': replay_evidence['before_sha256']['engine/utah_draw_predictive/preference_ladder_normalizer.py'] == sha(current_normalizer_path),
            'all_implementation_files_unchanged_during_replay': replay_evidence['all_implementation_files_unchanged_during_replay'],
            'behavior_equivalent_on_replayed_inputs': not replay_evidence['changed_during_replay'],
            'replay_manifest_sha256': sha(replay_evidence_path)}
    write_json(out / 'normalizer_replay_equivalence.json', normalizer_evidence)
    write_json(out/'source_intake_parity.json', {'compared_engine_point_rows': intake_compared,
        'numeric_differences': intake_differences, 'independent_projector_sha256': sha(RETAINED/'exact_year_adult_pool_diagnostic.py'),
        'absent_source_lane_gaps_independently_verified': sum(r['coverage_classification'] == 'NO_EXACT_SOURCE_ADULT_RESIDENCY_LANE' for r in gap_rows)})
    write_json(out / 'cert_report.json', {'release_decision': 'DO_NOT_PROMOTE', 'family_decisions': decisions,
        'evaluation_type': 'SOURCE_ONLY_KNOWN_YEAR_COMPARISON_NOT_UNTOUCHED_HOLDOUT', 'csv_sha256': hashes,
        'protected_file_changes': changes, 'reference_codes': len({r['hunt_code'] for r in refs}),
        'reference_probability_violations': sum(any(str(r.get(f, '')).strip() for f in probabilities) for r in refs),
        'resolver_sha256': sha(ROOT/RESOLVER), 'source_pdf_sha256': sha(ROOT/PDF),
        'normalizer_replay_equivalence': normalizer_evidence,
        'source_intake_compared_rows': intake_compared, 'source_intake_differences': len(intake_differences),
        'prior_real_final_preserved': not any(p.startswith('audit_output_real_final/') for p in changes),
        'registry_changed': False, 'newly_published': [], 'gap_count': len(gap_rows),
        'gap_classifications': dict(Counter(r['coverage_classification'] for r in gap_rows)),
        'limitations': ['Known outcomes are not untouched holdouts', 'Existing raw-hash/stale-build gate remains blocked',
                       'No post-hoc elk subgroup promotion', 'CWMU current implementation is not certified by antlerless preference scores']} )
    print(json.dumps({'decisions': decisions, 'protected_changes': changes, 'gap_classifications': dict(Counter(r['coverage_classification'] for r in gap_rows))}, indent=2))
    if changes or intake_differences or not normalizer_evidence['behavior_equivalent_on_replayed_inputs']:
        raise SystemExit('Protected files changed; promotion blocked')


def publication_diagnostic(out):
    folder = out / 'saved_publication_diagnostic'
    folder.mkdir(exist_ok=False)
    selected = [r for r in read(ROOT / PREDICTIVE) if r.get('draw_system_type') in (*FAMILIES, 'BONUS_CWMU_BIG_GAME')]
    path = folder / 'selected_saved_predictions.csv'
    write_csv(path, selected)
    command = [sys.executable, str(ROOT / 'tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.FROZEN.py'),
               '--predictions', str(path), '--truth', str(ROOT / 'data_truth/draw_results_truth/normalized/draw_results_long.csv'),
               '--output-dir', str(folder / 'frozen_scorer'), '--source-year', '2025', '--target-year', '2026']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (folder / 'scorer.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    write_json(folder / 'run.json', {'purpose': 'SAVED_PUBLICATION_DIAGNOSTIC_NOT_FRESH_CANDIDATE_CERTIFICATION',
        'command': command, 'returncode': result.returncode, 'source_sha256': sha(ROOT/PREDICTIVE),
        'selected_sha256': sha(path), 'selected_rows': len(selected), 'families': dict(Counter(r['draw_system_type'] for r in selected)),
        'numeric_p_draw_rows': sum(bool(r.get('p_draw', '').strip()) for r in selected),
        'scorer_sha256': sha(ROOT / 'tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.FROZEN.py')})
    print(json.dumps({'diagnostic_exit': result.returncode, 'selected_rows': len(selected), 'log': str(folder/'scorer.log')}))


def replay(out, forecasts):
    owners = sorted((ROOT / 'engine').rglob('*.py'))
    owners += [ROOT / 'scripts/evaluate_antlerless_preference_development.py', ROOT / 'scripts/verify-antlerless-adjacent-year-forecasts.py']
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in owners}
    write_json(out / 'replay_start_hashes.json', before)
    commands = [
        [sys.executable, 'scripts/evaluate_antlerless_preference_development.py', '--out-dir', str(forecasts), '--source-year-start', '2017', '--source-year-end', '2025'],
        [sys.executable, 'scripts/verify-antlerless-adjacent-year-forecasts.py', '--forecasts', str(forecasts), '--out-dir', str(forecasts/'full_adult_census')],
    ]
    for index, command in enumerate(commands):
        with (out / f'replay_step_{index+1}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        print(json.dumps({'step': index+1, 'returncode': result.returncode}), flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    changes = {p: {'before': value, 'after': sha(ROOT/p)} for p, value in before.items() if value != sha(ROOT/p)}
    write_json(out / 'replay_implementation_verification.json', {'before_sha256': before, 'changed_during_replay': changes,
        'all_implementation_files_unchanged_during_replay': not changes, 'commands': commands})
    if changes:
        raise SystemExit('Replay implementation changed; results are not releasable')


def independent_gap_check(out):
    spec = importlib.util.spec_from_file_location('independent_actual_projector', RETAINED/'exact_year_adult_pool_diagnostic.py')
    projector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(projector)
    gaps = read(out/'coverage_gap_classifications.csv')
    counts, mismatches, hashes = Counter(), [], {}
    for year in range(2017, 2026):
        path = CANONICAL/f'draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv'
        hashes[path.name] = sha(path)
        points, _, conflicts = projector.actual_points(read(path), year)
        if conflicts:
            raise ValueError(f'Official source conflict: {year}')
        lanes = {k[:3] for k in points}
        for row in gaps:
            if row['source_year'] != str(year) or row['coverage_classification'] != 'NO_EXACT_SOURCE_ADULT_RESIDENCY_LANE':
                continue
            key = (row['draw_design_key'], row['hunt_code'], row['residency'])
            if key in lanes:
                mismatches.append(row)
            else:
                counts['independently_verified_absent_exact_source_lane'] += 1
    write_json(out/'coverage_independent_check.json', {'counts': dict(counts), 'mismatches': mismatches,
        'source_sha256': hashes, 'projector_sha256': sha(RETAINED/'exact_year_adult_pool_diagnostic.py')})
    if mismatches:
        raise SystemExit('Gap classification disagrees with independent official source projection')


def test_review(out):
    files = ['tests/utah_draw_predictive/' + name + '.py' for name in (
        'test_antlerless_evidence_contract', 'test_antlerless_preference',
        'test_preference_historical_target_year_awareness', 'test_cwmu_bonus_public',
        'test_cwmu_private_not_modeled', 'test_general_season_deer_preference',
        'test_dedicated_hunter_preference', 'test_private_lands_antlerless_elk_not_preference',
        'test_private_lands_antlerless_elk_allocation', 'test_antlerless_preference_classification',
        'test_official_residency_allocation', 'test_research_guidance_source_scopes')]
    files += ['tests/utah_predictive_mixed/test_rollover_applicant_stack.py',
              'tests/utah/test_antlerless_hunt_code_resolution_2026.py',
              'tests/utah/test_antlerless_resolver_fail_closed.py']
    command = [sys.executable, '-m', 'pytest', *files, '-q', '--basetemp', str(out/'pytest_temp')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = out/'test_results.log'
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    write_json(out/'test_results.json', {'command': command, 'returncode': result.returncode,
        'log_sha256': sha(log), 'test_file_sha256': {p: sha(ROOT/p) for p in files}})
    print(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['inventory', 'report', 'publication', 'replay', 'coverage', 'tests'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--forecasts', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.phase == 'inventory':
        inventory(args.out.resolve())
    elif args.phase == 'report':
        report(args.out.resolve(), args.forecasts.resolve(), args.baseline.resolve())
    elif args.phase == 'publication':
        publication_diagnostic(args.out.resolve())
    elif args.phase == 'coverage':
        independent_gap_check(args.out.resolve())
    elif args.phase == 'tests':
        test_review(args.out.resolve())
    else:
        replay(args.out.resolve(), args.forecasts.resolve())
