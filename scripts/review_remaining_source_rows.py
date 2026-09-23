"""Resolve a retained source-review population without editing truth or forecasts."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as source


KEY = ('draw_year', 'hunt_code', 'source_scope', 'canonical_source', 'record_type',
       'pdf_page', 'points', 'residency', 'source_is_youth')
METRICS = {'eligible_applicants': 'ParticipantCount', 'successful_applicants': 'SuccessfulCount',
           'bonus_permits': 'SuccessfulByMaxPointRoundCount',
           'regular_permits': 'SuccessfulByRegularRoundCount', 'total_permits': 'SuccessfulCount'}


def review_key(row):
    return tuple(str(row.get(k, '')) for k in KEY)


def endpoint_companions(row, canonical, index):
    """Document already-retained typed source rows without choosing a legacy pool."""
    key = (row['hunt_code'], row['residency'].lower(), source.decimal(row['points']))
    raw_rows = index.get(key, [])
    if not raw_rows or any(any(source.decimal(row.get(f)) != source.decimal(raw.get(rf))
                              for f, rf in METRICS.items() if row.get(f, '') != '') for raw in raw_rows):
        return []
    results = []
    for raw in raw_rows:
        if not isinstance(raw.get('IsYouth'), bool):
            return []
        pool = str(raw['IsYouth']).lower()
        matches = []
        for line, r in canonical:
            if (r.get('source_dataset') != 'UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260902'
                    or (r['hunt_code'], r['residency'].lower(), source.decimal(r['points'])) != key
                    or r.get('source_is_youth') != pool):
                continue
            identifier = r.get('source_row_identifier', '')
            if f':hunt-id={raw["HuntID"]}:' not in identifier or f':is-youth={pool}:' not in identifier:
                continue
            if all(source.decimal(r.get(f)) == source.decimal(raw.get(rf)) for f, rf in METRICS.items()):
                matches.append(dict(canonical_csv_line=line, source_row_identifier=identifier,
                                    source_is_youth=pool, source_file=r['source_file']))
        if len(matches) != 1:
            return []
        results.extend(matches)
    return results


def review(previous, current, out):
    if out.exists():
        raise ValueError('Use a fresh output directory; retained audit evidence is never replaced')
    previous_csv = previous/'canonical_row_source_review.csv'
    current_csv = current/'canonical_row_source_review.csv'
    inputs = [previous_csv, current_csv, current/'source_mapping_closure_review.json', Path(__file__)]
    endpoint = source.local('pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902/utahdraws_2026/json/2026_big_game_05_general_season_buck_deer.json')
    canonical_path = source.YEARLY/'draw_results_2026_for_2027_canonical_yearly_draw_results.csv'
    guidebook = source.local('pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf')
    inputs.extend([endpoint, canonical_path, guidebook])
    frozen = {source.rel(p): source.sha(p) for p in inputs}
    old = [r for r in source.read_csv(previous_csv) if r['numeric_status'] == 'NOT_NUMERICALLY_VERIFIED'
           and r['scoring_applicability'] == 'REQUIRES_SCORABLE_SOURCE_REVIEW']
    new = defaultdict(list)
    for r in source.read_csv(current_csv):
        new[review_key(r)].append(r)
    canonical = list(enumerate(source.read_csv(canonical_path), 2))
    canonical_keys = defaultdict(list)
    for line, r in canonical:
        canonical_keys[review_key(dict(r, draw_year=r['actual_draw_year'], canonical_source=r['source_file']))].append((line, r))
    index = source.raw_endpoint_index(endpoint)
    outcomes, failures = [], []
    for r in old:
        matches = new[review_key(r)]
        if len(matches) != 1:
            failures.append(f'Current review key missing or duplicated: {review_key(r)}')
            continue
        after = matches[0]
        verified = after['numeric_status'] != 'NOT_NUMERICALLY_VERIFIED'
        result = dict(r, current_numeric_status=after['numeric_status'],
                      resolution='NUMERIC_SOURCE_VERIFIED' if verified else 'SOURCE_DIMENSION_STILL_UNRESOLVED',
                      inferred_legacy_pool='', independent_sample_added=False,
                      retained_endpoint_companions=[])
        if r['draw_year'] == '2026':
            originals = canonical_keys[review_key(r)]
            if len(originals) != 1:
                failures.append(f'Canonical source key missing or duplicated: {review_key(r)}')
                outcomes.append(result)
                continue
            line, original = originals[0]
            result.update(endpoint_path=source.rel(endpoint), endpoint_sha256=source.sha(endpoint),
                          canonical_csv_line=line,
                          canonical_numeric_cells={f: original.get(f, '') for f in METRICS},
                          retained_endpoint_companions=endpoint_companions(original, canonical, index))
            if r['hunt_code'] == 'DB0008':
                result.update(routing_issue='CANONICAL_AVAILABILITY_LABEL_CONFLICTS_WITH_OFFICIAL_DRAW',
                              official_design='PREFERENCE_GENERAL_SEASON_BUCK_DEER',
                              guidebook_path=source.rel(guidebook), guidebook_pages=[9, 44],
                              guidebook_sha256=source.sha(guidebook),
                              official_url='https://wildlife.utah.gov/extendedarchery',
                              routing_changed=False)
            if not verified and len(result['retained_endpoint_companions']) == 2:
                result['resolution'] = 'AMBIGUOUS_LEGACY_POOL_ALREADY_REPRESENTED_BY_TWO_VERIFIED_ENDPOINT_LANES'
        outcomes.append(result)
    changed = [p for p, digest in frozen.items() if source.sha(source.local(p)) != digest]
    failures.extend(f'Input changed: {p}' for p in changed)
    summary = dict(status='SOURCE_REVIEW_PARTIAL' if any(r['current_numeric_status']=='NOT_NUMERICALLY_VERIFIED' for r in outcomes) else 'SOURCE_ROWS_VERIFIED',
                   prior_rows=len(old), reviewed_rows=len(outcomes), failures=failures,
                   resolutions=dict(Counter(r['resolution'] for r in outcomes)),
                   verified_by_scope=dict(Counter(r['source_scope'] for r in outcomes if r['current_numeric_status']!='NOT_NUMERICALLY_VERIFIED')),
                   remaining_pool_ambiguities=sum(r['current_numeric_status']=='NOT_NUMERICALLY_VERIFIED' for r in outcomes),
                   routing_metadata_hold_codes=sorted({r['hunt_code'] for r in outcomes if r.get('routing_issue')}),
                   canonical_changed=False, forecasts_regenerated=False, certification_approved=False,
                   input_hashes=frozen, changed_inputs=changed)
    out.mkdir(parents=True)
    source.write_json(out/'remaining_source_row_resolution.json', outcomes)
    source.write_json(out/'summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='input_hashes'}, indent=2))
    return int(bool(failures) or summary['remaining_pool_ambiguities'] > 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(review(args.previous, args.current, args.out_dir))
