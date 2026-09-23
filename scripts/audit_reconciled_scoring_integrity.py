"""Verify identity-only changes against retained outcome-corrected projections."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer
from scripts.project_legacy_canonical_for_blind_scoring import read_csv, sha256, write_csv


def repeated_actual_status(vectors):
    """An empty display is not an observed result or an independent sample.

    Preserve it in the evidence ledger. Missing counts, positive awards without
    applicants, or conflicting populated values still require source review.
    """
    if len(vectors) == 1:
        return 'IDENTICAL_VALUES_REPEATED_SOURCE_RECORD'
    populated = vectors - {(0.0, 0.0, None)}
    if len(populated) == 1 and any(
        v[0] is not None and v[0] > 0 and v[1] is not None
        and 0 <= v[1] <= v[0] and v[2] is not None for v in populated
    ):
        return 'EMPTY_DISPLAY_SEPARATE_FROM_POPULATED_RESULT'
    return 'CONFLICT_REQUIRES_SOURCE_REVIEW'


def audit(original, candidate, endpoint_audit, source_years=None, single_fold=False):
    years = list(range(2017, 2026)) if source_years is None else list(source_years)
    if not years or len(set(years)) != len(years) or any(y not in range(2017, 2026) for y in years):
        raise ValueError('Expected distinct physical source years within 2017-2025')
    if single_fold and len(years) != 1:
        raise ValueError('Single-fold layout requires exactly one source year')
    output = candidate / 'identity_integrity.json'
    if output.exists():
        raise ValueError('Refusing to overwrite integrity evidence')
    failures, folds, actual_duplicates = [], [], []
    scorer.HUNT_CODE_CROSSWALK = {}
    scorer.ACTIVE_SCORING_HUNT_CODE_ALIASES = {}
    for year in years:
        suffix = f'source_{year}/{year}_to_{year+1}/scoring_projection'
        old = original / suffix
        new = candidate / 'scoring_projection' if single_fold else candidate / suffix
        _, a = read_csv(next(old.glob('*actual*projection.csv')))
        _, b = read_csv(next(new.glob('*actual*projection.csv')))
        if len(a) != len(b):
            failures.append(f'{year}: actual rows lost/added')
        pool_changes = 0
        for line, (before, after) in enumerate(zip(a, b), 2):
            diff = {k for k in set(before) | set(after) if before.get(k, '') != after.get(k, '')}
            if diff - {'draw_pool'}:
                failures.append(f'{year}: changed actual cells {line}: {diff}')
            pool_changes += bool(diff)
        _, forecast_before = read_csv(next(old.glob('*forecast*projection.csv')))
        _, forecast_after = read_csv(next(new.glob('*forecast*projection.csv')))
        _, decisions = read_csv(new / 'forecast_identity_resolution.csv')
        excluded = {int(r['superseded_csv_line']) for r in decisions}
        expected = [(n, r) for n, r in enumerate(forecast_before, 2) if n not in excluded]
        if len(expected) != len(forecast_after):
            failures.append(f'{year}: unaccounted forecast count difference')
        for (line, before), after in zip(expected, forecast_after):
            if any(before.get(k, '') != after.get(k, '') for k in set(before) | set(after) if k != 'draw_pool'):
                failures.append(f'{year}: forecast value changed {line}')
        groups = defaultdict(list)
        for line, row in enumerate(b, 2):
            for point in scorer.actual_points_from_row(row):
                groups[scorer.actual_alignment_key(point)].append((line, row, point))
        conflicts = 0
        for key, members in groups.items():
            if len(members) < 2:
                continue
            vectors = {(p.actual_eligible_applicants, p.actual_drawn,
                        round(p.actual_probability, 7) if p.actual_probability is not None else None)
                       for _, _, p in members}
            status = repeated_actual_status(vectors)
            conflict = status == 'CONFLICT_REQUIRES_SOURCE_REVIEW'
            conflicts += conflict
            actual_duplicates.append(dict(source_year=year, key='|'.join(key),
                csv_lines='|'.join(str(n) for n, _, _ in members),
                status=status,
                source_files='|'.join(r.get('source_file', '') for _, r, _ in members), vectors=repr(sorted(vectors, key=str))))
        scorepath = new.parent / 'comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv'
        _, scores = read_csv(scorepath)
        keys = [tuple(r[k] for k in ('draw_design_key', 'draw_pool_key', 'hunt_code', 'residency', 'points'))
                for r in scores if r['scoring_decision'] == 'score_probability']
        if len(keys) != len(set(keys)):
            failures.append(f'{year}: repeated scored identities')
        folds.append(dict(source_year=year, independent_scored_keys=len(set(keys)),
                          repeated_scored_keys=len(keys)-len(set(keys)), actual_pool_labels_recovered=pool_changes,
                          superseded_fallback_rows=len(excluded), conflicting_actual_key_groups=conflicts))
    evidence = json.loads((endpoint_audit / 'summary.json').read_text(encoding='utf-8'))
    canonical = ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2026_for_2027_canonical_yearly_draw_results.csv'
    if sha256(canonical) != evidence['input_hashes'][canonical.relative_to(ROOT).as_posix()]:
        failures.append('Current canonical does not match endpoint evidence')
    _, endpoint_rows = read_csv(endpoint_audit / 'canonical_endpoint_probability_review.csv')
    unresolved = [r for r in endpoint_rows if r['parity'] == 'ENDPOINT_SOURCE_DIMENSION_UNRESOLVED']
    reference = [r for r in unresolved if not r.get('family')]
    draw_dimensions = [r for r in unresolved if r.get('family')]
    positive = [r for r in draw_dimensions if float(r.get('eligible') or 0) > 0]
    write_csv(candidate / 'unresolved_2026_source_dimensions.csv', list(endpoint_rows[0]), unresolved)
    write_csv(candidate / 'repeated_actual_source_records.csv', list(actual_duplicates[0]) if actual_duplicates else ['key'], actual_duplicates)
    result = dict(status='PASS_IDENTITY_ONLY_PROJECTION' if not failures else 'FAIL', failures=failures,
                  folds=folds, audited_source_years=years, frozen_probability_values_changed=False,
                  preserved_2026_verified_observed_zeros=evidence['source_verified_missing_zero_outcomes'],
                  source_dimension_gate='BLOCKED' if unresolved else 'PASS',
                  unresolved_2026_source_dimensions=len(unresolved), positive_applicant_unresolved_rows=positive,
                  unresolved_reference_rows_not_probability_evidence=len(reference),
                  unresolved_empty_draw_display_rows=sum(float(r.get('eligible') or 0) <= 0 for r in draw_dimensions),
                  unresolved_actual_numeric_conflicts=sum(r['conflicting_actual_key_groups'] for r in folds),
                  certification_or_promotion_authorized=False)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--endpoint-audit', type=Path, required=True)
    parser.add_argument('--source-years', type=int, nargs='+')
    parser.add_argument('--single-fold', action='store_true', help='Candidate directly contains scoring_projection and comparison_phase.')
    args = parser.parse_args()
    raise SystemExit(audit(args.original, args.candidate, args.endpoint_audit, args.source_years, args.single_fold))
