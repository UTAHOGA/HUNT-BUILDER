from __future__ import annotations

"""Source-index and exact canonical lineage review; never edits truth or runtime.

Current identity comes from the named master, historical identity from each
year's canonical. DATABASE contributes permit context only, never membership.
Document/code presence is not numeric parity, continuity, or retirement proof.
"""

import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf
# --- Youth-Source-Feed-Pending-Forecast-Fix ---
from engine.utah.quality.species_routing import corrected_species_routing, _pending_forecast_path, _build_youth_isolated_ladders, PENDING_NO_HISTORY_2026
# --- End Fix ---
from engine.utah.quality.audit_database_vs_canonical import load_canonical
from scripts.audit_2026_live_endpoint_rows import expected_endpoint as live_endpoint
from scripts.audit_2026_pdf_rows_vs_utahdraws_snapshot import expected_endpoint as pdf_endpoint
from engine.utah.quality.sportsman_source_table import read_sportsman_page, compare_sportsman_row

INVENTORY = ROOT/'data_model/quality/raw_pdf_inventory.csv'
DATABASE = ROOT/'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'
CANON = ROOT/'data/utah/official_downloads_2026/hunt_master_canonical_2026.csv'
YEARLY = ROOT/'data_truth/draw_results_truth/normalized/canonical_yearly'
AUDIT_JSON = ROOT/'processed_data/2026_all_species_all_years_2017_2026_audit.json'
CODE = re.compile(r'\b[A-Z]{1,3}\d{3,4}\b')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def local(value):
    path = Path(str(value).replace('\\', '/'))
    return (path if path.is_absolute() else ROOT/path).resolve()


def rel(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def extract_pdf(path):
    """One extraction per content hash, all page references, explicit failures."""
    result = dict(sha256=None, pages=0, codes={}, header_years=[], status='ERROR', errors=[])
    try:
        result['sha256'] = sha(path)
        pages_by_code, years, text_length = defaultdict(list), set(), 0
        with pymupdf.open(path) as pdf:
            result['pages'] = len(pdf)
            for number, page in enumerate(pdf, 1):
                text = page.get_text()
                text_length += len(text.strip())
                for code in sorted(set(CODE.findall(text))):
                    pages_by_code[code].append(number)
                if number <= 3:
                    years.update(re.findall(r'\b(20\d{2})\s+(?:Draw|Sportsman)', text, re.I))
        result.update(codes=dict(pages_by_code), header_years=sorted(years))
        if not result['pages'] or not text_length:
            result['errors'].append('EMPTY_OR_NO_EXTRACTABLE_TEXT')
        if sha(path) != result['sha256']:
            result['errors'].append('SOURCE_CHANGED_DURING_EXTRACTION')
        result['status'] = 'ERROR' if result['errors'] else ('CODE_PRESENCE_ONLY' if pages_by_code else 'NO_HUNT_CODES_DETECTED')
    except Exception as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
    return result


def classify_difference(row):
    status = row['status']
    if status == 'VALUE_MISMATCH' and row.get('field', '').endswith('success_ratio'):
        if re.sub(r'\s+', '', row.get('source', '')) == re.sub(r'\s+', '', row.get('canonical', '')):
            return 'RATIO_WHITESPACE_ONLY'
    if status == 'PDF_ROW_NOT_IN_CANONICAL':
        try:
            key = ast.literal_eval(row['key'])
            if key[1] == 'hunt_total_draw_result' and key[2] == '':
                return 'AGGREGATE_TOTAL_NOT_POINT_RUNG'
        except (ValueError, SyntaxError, IndexError):
            pass
    return status


def decimal(value):
    try:
        return Decimal(str(value).replace(',', '').strip())
    except InvalidOperation:
        return None


def raw_endpoint_index(path):
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    index = defaultdict(list)
    if not isinstance(payload.get('Data'), list):
        raise ValueError('Missing raw Data list')
    for hunt in payload['Data']:
        for row in hunt.get('OddsList', []):
            lane = {1: 'resident', 2: 'nonresident'}.get(row.get('ResidencyTypeID'))
            if lane and row.get('Point') is not None:
                key = (str(hunt['HuntCode']).upper(), lane, decimal(row['Point']))
                index[key].append(row)
    return index


def recover_source_pool(row, index):
    """Recover the endpoint pool, not the applicant's age eligibility.

    Single-pool evidence covers the entire hunt in the exact endpoint, never
    just a sparse point rung. Outcome values cannot select the pool.
    """
    explicit = row.get('source_is_youth', '').strip().lower()
    markers = {m.lower() for m in re.findall(r'(?:^|:)is-youth=(true|false)(?=$|:|\|)',
                       row.get('source_row_identifier', ''), re.I)}
    if len(markers)>1 or (explicit and explicit not in ('true','false')):
        return '', 'COALESCED_OR_UNRESOLVED_SOURCE_POOL_METADATA'
    marker_flag = next(iter(markers)) if markers else ''
    if explicit in ('true', 'false'):
        if marker_flag and marker_flag != explicit:
            return '', 'CONFLICTING_EXPLICIT_SOURCE_POOL_LABELS'
        return explicit, 'EXPLICIT_CANONICAL_POOL'
    if marker_flag:
        return marker_flag, 'EXACT_SOURCE_ROW_IDENTIFIER'
    code = row['hunt_code'].strip().upper()
    raw_rows = [r for (hunt, _, _), values in index.items() if hunt == code for r in values]
    if not raw_rows or any(not isinstance(r.get('IsYouth'), bool) for r in raw_rows):
        return '', 'NO_COMPLETE_TYPED_ENDPOINT_HUNT'
    flags = {r['IsYouth'] for r in raw_rows}
    if len(flags) == 1:
        return str(next(iter(flags))).lower(), 'EXACT_ENDPOINT_HUNT_SINGLE_POOL'
    # Source scope identifies a table, unlike hunt_class, which was copied from
    # Planner and can say Adult for both rows of a shared-code draw.
    scope = row.get('source_scope', '').upper()
    if scope.startswith('YOUTH_') and scope != 'YOUTH_GENERAL_SEASON_ELK':
        return 'true', 'EXPLICIT_YOUTH_REPORT_SCOPE'
    return '', 'SHARED_CODE_MULTIPLE_SOURCE_POOLS_REQUIRES_PARENT_TABLE'


def endpoint_review_identity(row, index):
    """Audit-only label recovery; no canonical mutation or forecast use.

    Reuse the established exact positive-vector transcription rule. Equal
    vectors in different pools remain ambiguous; never choose the first row.
    """
    youth, reason = recover_source_pool(row, index)
    if youth or reason in {'COALESCED_OR_UNRESOLVED_SOURCE_POOL_METADATA', 'CONFLICTING_EXPLICIT_SOURCE_POOL_LABELS'}:
        return youth, reason
    if row.get('source_dataset') == 'OFFICIAL_DWR_2026_PDF_DRAW_RESULTS':
        from engine.utah.quality.recover_source_pool_labels_2026 import exact_positive_row_pool
        return exact_positive_row_pool(row, index)
    return youth, reason


def endpoint_parity(row, index):
    point = row.get('points', '')
    if not point and 'SPORTSMAN' in row.get('source_scope', '').upper():
        point = '0'
    key = (row['hunt_code'].upper(), row.get('residency', '').lower(), decimal(point))
    matches = index.get(key, [])
    youth, recovery = endpoint_review_identity(row, index)
    if youth not in ('true', 'false'):
        return 'ENDPOINT_SOURCE_DIMENSION_UNRESOLVED', 0
    if youth in ('true', 'false'):
        matches = [r for r in matches if isinstance(r.get('IsYouth'), bool) and r['IsYouth'] == (youth == 'true')]
    if len(matches) != 1:
        return 'ENDPOINT_IDENTITY_MISSING_OR_AMBIGUOUS', 0
    raw = matches[0]
    fields = {'eligible_applicants': 'ParticipantCount', 'successful_applicants': 'SuccessfulCount',
              'bonus_permits': 'SuccessfulByMaxPointRoundCount',
              'regular_permits': 'SuccessfulByRegularRoundCount', 'total_permits': 'SuccessfulCount'}
    count = 0
    for field, raw_field in fields.items():
        if row.get(field, '') == '':
            continue
        count += 1
        if decimal(row[field]) is None or decimal(row[field]) != decimal(raw.get(raw_field)):
            return 'ENDPOINT_VALUE_MISMATCH', count
    required = row.get('eligible_applicants', '') != '' and row.get('successful_applicants', row.get('total_permits', '')) != ''
    return ('ENDPOINT_POPULATED_FIELDS_MATCH' if required and count >= 2 else 'ENDPOINT_MISSING_CANONICAL_METRICS'), count


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def row_reconciliation_status(counts):
    """A pending summary must not invalidate separately verified point rows."""
    pending = counts.get('NOT_NUMERICALLY_VERIFIED', 0)
    verified = sum(counts.values()) - pending
    return 'PARTIAL' if pending and verified else ('UNVERIFIED' if pending else 'PASS')


def source_row_applicability(row):
    """Scoring applicability is separate from source numeric verification."""
    if row.get('record_type') == 'hunt_total_draw_result':
        return 'AGGREGATE_NOT_POINT_RUNG'
    if (row.get('source_file', '').startswith('https://')
            and row.get('source_scope') in {'DWR_HUNT_PLANNER_ANTLERLESS', 'DWR_HUNT_PLANNER_CWMU'}
            and not any(row.get(k, '') for k in ('eligible_applicants', 'successful_applicants'))):
        return 'PLANNER_REFERENCE_NOT_DRAW_OUTCOME'
    fields = ('eligible_applicants', 'successful_applicants', 'bonus_permits', 'regular_permits', 'total_permits')
    if (all(decimal(row.get(k)) == 0 for k in fields)
            and not any(row.get(k, '') for k in ('p_draw', 'p_draw_percent'))):
        return 'EMPTY_DISPLAY_NOT_SCORABLE'
    return 'REQUIRES_SCORABLE_SOURCE_REVIEW'


def canonical_pdf_key(row):
    return tuple(row.get(k, '') for k in ('hunt_code', 'record_type', 'points', 'pdf_page'))


def prior_numeric_row_status(row, keyed_differences, hash_valid, accounting_valid):
    """A failed total must not erase separately matched point-cell evidence.

    Reuse only a complete, hash-linked prior comparison with exact row keys.
    No absence of a difference is accepted unless source row accounting closes.
    """
    if not hash_valid or not accounting_valid:
        return 'NOT_NUMERICALLY_VERIFIED'
    accepted = {'RATIO_WHITESPACE_ONLY', 'AGGREGATE_TOTAL_NOT_POINT_RUNG',
                'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'}
    issues = keyed_differences.get(canonical_pdf_key(row), [])
    if any(d['review_classification'] not in accepted for d in issues):
        return 'NOT_NUMERICALLY_VERIFIED'
    return 'PRIOR_NUMERIC_AUDIT_HASH_VERIFIED_WITH_DOCUMENTED_NORMALIZATIONS'


def retained_parent_index():
    """Earlier mappings are leads, verified by current parent bytes, not status text."""
    index = defaultdict(list)
    hashes = {}
    base = ROOT/'data_truth/draw_results_truth/validation'
    for name in ('canonical_parent_source_mapping_2017.csv', 'canonical_parent_source_mapping_2018_2026.csv'):
        path = base/name
        hashes[rel(path)] = sha(path)
        for row in read_csv(path):
            key = (int(row['draw_year']), row['canonical_source_label'])
            paths = [v.strip() for v in row.get('parent_archive_paths', '').split('|') if v.strip()]
            digests = [v.strip() for v in row.get('parent_sha256s', '').split('|') if v.strip()]
            for value in paths:
                parent = local(value)
                verified = parent.is_file() and sha(parent) in digests
                index[key].append(dict(path=parent, verified=verified, mapping_file=rel(path),
                                       previous_status=row.get('mapping_status', '')))
    return index, hashes


def previous_crosswalk_review(sources, active, presence):
    """Attach actual guidebook code/page evidence without approving inferred recodes."""
    files = [ROOT/p for p in (
        'data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv',
        'data_truth/crosswalk_truth/normalized/2026_no_exact_history_additions_crosswalk.csv',
        'processed_data/current_to_historical_hunt_code_crosswalk_2026.csv',
        'processed_data/audits/hunt_code_year_to_year_crosswalk_2020_2026.csv',
        'data/hunt-master-canonical-2026-historical-le-to-eb-crosswalk.csv')]
    fields = ('hunt_code', 'current_hunt_code', 'historical_hunt_code', 'historical_2024_code',
              'historical_2025_code', 'current_2026_code', 'from_hunt_code', 'to_hunt_code',
              'source_hunt_number', 'recommended_eb_code')
    guides = [s for s in sources if '/guidebooks/' in s['pdf_path'] and s['status'] != 'ERROR']
    evidence = defaultdict(list)
    for guide in guides:
        for code, pages in guide['codes'].items():
            evidence[code].append(dict(path=guide['pdf_path'], sha256=guide['sha256'], pages=pages))
    records, hashes, missing = [], {}, []
    for path in files:
        if not path.is_file():
            missing.append(rel(path))
            continue
        hashes[rel(path)] = sha(path)
        for number, row in enumerate(read_csv(path), 2):
            codes = sorted({row.get(f, '').strip().upper() for f in fields
                            if CODE.fullmatch(row.get(f, '').strip().upper())})
            cited = row.get('guidebook_first_listed_file', '')
            page = row.get('guidebook_first_listed_page', '')
            code = row.get('current_hunt_code', '')
            confirmed = bool(cited and page.isdigit() and any(
                local(e['path']) == local(cited) and int(page) in e['pages'] for e in evidence.get(code, [])))
            records.append(dict(crosswalk_file=rel(path), csv_line=number, original_record=row,
                                codes=codes, current_canonical_codes=[c for c in codes if c in active],
                                historical_canonical_years={c: sorted(presence.get(c, set())) for c in codes},
                                guidebook_code_presence=[c for c in codes if c in evidence],
                                cited_first_listing_page_verified=confirmed,
                                review_status='GUIDEBOOK_LISTING_CONFIRMED_NOT_PREDECESSOR_PROOF' if confirmed else 'PRIOR_CROSSWALK_REQUIRES_RELATIONSHIP_EVIDENCE'))
    return dict(input_hashes=hashes, missing_crosswalk_files=missing, records=records,
                guidebook_code_page_index=dict(evidence), guidebook_pdfs_scanned=len(guides),
                interpretation='All prior rows retained. Code presence and last observed year do not prove recoding or discontinuation. No crosswalk is newly approved here.')


def build(out):
    names = ['source_mapping_2017_2026.json', 'hunt_crosswalk_2017_2026.json',
             'historical_canonical_source_links_2017_2026.json', 'database_vs_canonical_review.json',
             'source_mapping_closure_review.json', 'source_mapping_normalized_differences.csv',
             'existing_crosswalk_guidebook_review.json', 'endpoint_row_source_review.csv']
    names.append('canonical_row_source_review.csv')
    if any((out/name).exists() for name in names + ['sportsman_numeric_cell_review.json']):
        raise ValueError('Output already exists; use --out-dir with a fresh folder to preserve evidence')
    out.mkdir(parents=True, exist_ok=True)
    active, excluded = load_canonical(CANON)
    prior = json.loads(AUDIT_JSON.read_text(encoding='utf-8-sig'))
    retained_parents, parent_mapping_hashes = retained_parent_index()
    inventories = read_csv(INVENTORY)
    inputs = [CANON, DATABASE, INVENTORY, AUDIT_JSON, Path(__file__)]
    paths, expected = set(), defaultdict(set)
    for entry in inventories:
        path = local(entry.get('path', ''))
        if path.suffix.lower() == '.pdf':
            paths.add(path)
            if entry.get('sha256'):
                expected[path].add(entry['sha256'].lower())
    for entry in prior['files']:
        path = local(entry['path'])
        paths.add(path)
        if entry.get('sha_actual'):
            expected[path].add(entry['sha_actual'])
    annual, missing_years = {}, []
    for year in range(2017, 2027):
        path = YEARLY/f'draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv'
        if not path.is_file():
            missing_years.append(year)
            continue
        annual[year] = read_csv(path)
        inputs.append(path)
    inputs.append(Path(__file__).with_name('sportsman_source_table.py'))
    inputs.append(Path(__file__).with_name('recover_source_pool_labels_2026.py'))
    frozen = {rel(p): sha(p) for p in inputs}
    frozen.update(parent_mapping_hashes)
    cache, sources = {}, []
    for number, path in enumerate(sorted(paths), 1):
        digest = sha(path) if path.is_file() else None
        if digest not in cache or digest is None:
            result = extract_pdf(path)
            if digest:
                cache[digest] = result
        else:
            result = cache[digest]
        result = {**result, 'pdf_path': rel(path), 'errors': list(result['errors'])}
        if expected[path] and expected[path] != {digest}:
            result['status'] = 'ERROR'
            result['errors'].append('INVENTORY_OR_PRIOR_AUDIT_SHA_MISMATCH')
        codes = set(result['codes'])
        result.update(codes_parsed=len(codes), codes_current_canonical_overlap=len(codes & set(active)),
                      codes_outside_current_canonical=sorted(codes-set(active)),
                      year_policy='Header years are evidence; archive folders are not assumed draw years.')
        sources.append(result)
        if number % 100 == 0:
            print(f'Indexed {number}/{len(paths)} PDF paths', flush=True)
    by_path = {local(s['pdf_path']): s for s in sources}
    by_code = defaultdict(list)
    for source in sources:
        if source['status'] == 'ERROR':
            continue
        for code, pages in source['codes'].items():
            by_code[code].append(dict(path=source['pdf_path'], sha256=source['sha256'], pages=pages))
    # Reuse recorded source selection only after measuring the parent and canonical hashes.
    old_sources = {(s['year'], s['scope'], s['source']): s for s in prior['sources']}
    old_pdf_hashes = {local(s['path']): s.get('sha_actual') for s in prior['files']}
    difference_path = AUDIT_JSON.with_name(AUDIT_JSON.stem+'_cell_differences.csv')
    differences = read_csv(difference_path)
    frozen[rel(difference_path)] = sha(difference_path)
    diff_groups = defaultdict(list)
    keyed_diff_groups = defaultdict(lambda: defaultdict(list))
    for row in differences:
        row['review_classification'] = classify_difference(row)
        label = row.get('source_file') or row.get('source', '')
        diff_groups[(int(row['year']), row['scope'], label)].append(row)
        try:
            key = ast.literal_eval(row.get('key', ''))
            if isinstance(key, tuple) and len(key) == 4:
                keyed_diff_groups[(int(row['year']), row['scope'], label)][key].append(row)
        except (ValueError, SyntaxError):
            pass
    endpoint_cache, endpoint_hashes = {}, {}
    snapshots = ROOT/'pipeline/RAW/hunt_unit_database/2026/json/draw_results'
    endpoint_dirs = [snapshots/'utahdraws_2026_20260902/utahdraws_2026/json',
                     snapshots/'utahdraws_2026_20260826/utahdraws_2026/json']
    groups, presence = defaultdict(list), defaultdict(set)
    source_rows = defaultdict(list)
    for year, rows in annual.items():
        for row in rows:
            code = row['hunt_code'].strip().upper()
            presence[code].add(year)
            groups[(year, row.get('source_scope', ''), row.get('source_file', ''), code)].append(row)
            source_rows[(year, row.get('source_scope', ''), row.get('source_file', ''))].append(row)
    accounting = {}
    for parent, rows in source_rows.items():
        keys = [canonical_pdf_key(r) for r in rows]
        old = old_sources.get(parent, {})
        missing = {k for k, ds in keyed_diff_groups[parent].items()
                   if any(d['status'] == 'UNVERIFIED_LAYOUT_OR_KEY' for d in ds)}
        accounting[parent] = (len(set(keys)) == len(keys)
                              and old.get('canonical_rows') == len(rows)
                              and missing <= set(keys)
                              and old.get('matched_rows') == len(rows) - len(missing))
    links, endpoint_checks, row_checks, numeric_cells = [], [], [], []
    sportsman_cache = {}
    for (year, scope, label, code), rows in sorted(groups.items()):
        old = old_sources.get((year, scope, label), {})
        retained = retained_parents.get((year, label), [])
        path = local(old['path']) if old.get('path') else None
        source = by_path.get(path)
        statuses = Counter()
        endpoint_row_statuses = []
        parent_paths, pages = set(), set()
        if source and source['status'] != 'ERROR':
            code_pages = set(source['codes'].get(code, []))
            for row in rows:
                page = str(row.get('pdf_page', ''))
                if page.isdigit() and int(page) in code_pages:
                    statuses['PDF_CODE_AND_PAGE_LINKED'] += 1
                    pages.add(int(page))
                else:
                    statuses['PDF_CODE_OR_PAGE_UNRESOLVED'] += 1
            parent_paths.add(source['pdf_path'])
        elif year == 2026 and not label.startswith('https://'):
            for row in rows:
                check = dict(hunt_code=code, source_scope=scope, canonical_source=label,
                             residency=row.get('residency', ''), points=row.get('points', ''),
                             source_is_youth=row.get('source_is_youth', ''), pdf_page=row.get('pdf_page', ''),
                             endpoint_path='', status='', compared_fields=0, error='',
                             recovered_pool_for_review='', pool_recovery_basis='')
                try:
                    name = pdf_endpoint(row) if row.get('source_dataset') == 'OFFICIAL_DWR_2026_PDF_DRAW_RESULTS' else live_endpoint(row)
                    candidates = [d/name for d in endpoint_dirs if (d/name).is_file()]
                    if not candidates:
                        raise FileNotFoundError(name)
                    # Prefer exact retained source snapshot when the row identifies it.
                    source_path = row.get('source_path', '').replace('\\', '/')
                    preferred = [p for p in candidates if p.parent.parent.as_posix() in local(source_path).as_posix()]
                    endpoint = preferred[0] if len(preferred) == 1 else candidates[0]
                    mapped = {p['path'] for p in retained if p['verified'] and p['path'].name == name}
                    if not preferred and len(mapped) == 1:
                        endpoint = next(iter(mapped))
                    if endpoint not in endpoint_cache:
                        endpoint_cache[endpoint] = raw_endpoint_index(endpoint)
                        endpoint_hashes[rel(endpoint)] = sha(endpoint)
                    status, _ = endpoint_parity(row, endpoint_cache[endpoint])
                    check.update(endpoint_path=rel(endpoint), status=status, compared_fields=_)
                    pool, basis = endpoint_review_identity(row, endpoint_cache[endpoint])
                    check.update(recovered_pool_for_review=pool, pool_recovery_basis=basis)
                    statuses[status] += 1
                    parent_paths.add(rel(endpoint))
                except (KeyError, ValueError, OSError, TypeError) as exc:
                    statuses['ENDPOINT_PARENT_UNRESOLVED'] += 1
                    check.update(status='ENDPOINT_PARENT_UNRESOLVED', error=f'{type(exc).__name__}: {exc}')
                endpoint_checks.append(check)
                endpoint_row_statuses.append(check['status'])
        else:
            statuses['REFERENCE_SOURCE_REVIEW' if label.startswith('https://') else 'PARENT_SOURCE_UNRESOLVED'] += len(rows)
        yearly_path = YEARLY/f'draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv'
        hash_valid = (prior['summary']['protected_hashes'].get(rel(yearly_path)) == frozen[rel(yearly_path)]
                      and source is not None and old_pdf_hashes.get(path) == source['sha256'])
        issues = [d['review_classification'] for d in diff_groups[(year, scope, label)]
                  if code in d.get('key', '')]
        accepted = {'RATIO_WHITESPACE_ONLY', 'AGGREGATE_TOTAL_NOT_POINT_RUNG', 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'}
        numeric = 'NOT_NUMERICALLY_VERIFIED'
        if hash_valid and not any(i not in accepted for i in issues) and old.get('matched_rows', 0):
            numeric = 'PRIOR_NUMERIC_AUDIT_HASH_VERIFIED_WITH_DOCUMENTED_NORMALIZATIONS'
        if statuses and set(statuses) == {'ENDPOINT_POPULATED_FIELDS_MATCH'}:
            numeric = 'RAW_ENDPOINT_POPULATED_FIELDS_MATCH'
        numeric_rows, applicability_rows = Counter(), Counter()
        unverified_scorable = 0
        for number, row in enumerate(rows):
            row_numeric = prior_numeric_row_status(row, keyed_diff_groups[(year, scope, label)],
                                                  hash_valid, accounting[(year, scope, label)])
            if endpoint_row_statuses:
                row_numeric = ('RAW_ENDPOINT_POPULATED_FIELDS_MATCH'
                               if endpoint_row_statuses[number] == 'ENDPOINT_POPULATED_FIELDS_MATCH'
                               else 'NOT_NUMERICALLY_VERIFIED')
            if scope == 'SPORTSMAN' and row_numeric == 'NOT_NUMERICALLY_VERIFIED' and hash_valid:
                review = dict(draw_year=year, hunt_code=code, canonical_source=label,
                              pdf_page=row.get('pdf_page', ''), source_path=rel(path),
                              source_sha256=source['sha256'])
                try:
                    page_key = (path, int(row['pdf_page']))
                    if page_key not in sportsman_cache:
                        try:
                            sportsman_cache[page_key] = read_sportsman_page(*page_key)
                        except (ValueError, OSError, IndexError) as exc:
                            sportsman_cache[page_key] = str(exc)
                    table = sportsman_cache[page_key]
                    if isinstance(table, str):
                        raise ValueError(table)
                    if code not in table:
                        raise ValueError('Exact hunt code missing from Sportsman source page')
                    matched, cells = compare_sportsman_row(row, table[code])
                    numeric_cells.extend({**review, **c} for c in cells)
                    if matched:
                        row_numeric = 'SPORTSMAN_PDF_OUTCOME_CELLS_MATCH'
                except (KeyError, ValueError, OSError, IndexError) as exc:
                    numeric_cells.append(dict(review, field='', canonical='', source='',
                                              basis='SOURCE_TABLE_PARSE', status=f'BLOCKED: {exc}'))
            applicability = source_row_applicability(row)
            numeric_rows[row_numeric] += 1
            applicability_rows[applicability] += 1
            unverified_scorable += int(row_numeric == 'NOT_NUMERICALLY_VERIFIED'
                                      and applicability == 'REQUIRES_SCORABLE_SOURCE_REVIEW')
            row_checks.append(dict(draw_year=year, hunt_code=code, source_scope=scope,
                                   canonical_source=label, record_type=row.get('record_type', ''),
                                   pdf_page=row.get('pdf_page', ''), points=row.get('points', ''),
                                   residency=row.get('residency', ''), source_is_youth=row.get('source_is_youth', ''),
                                   numeric_status=row_numeric, scoring_applicability=applicability))
        links.append(dict(draw_year=year, hunt_code=code, source_scope=scope,
                          canonical_source_label=label, canonical_rows=len(rows),
                          prior_parent_mappings=[{**p, 'path':rel(p['path'])} for p in retained],
                          historical_only=code not in active, parent_paths=sorted(parent_paths),
                          pdf_pages=sorted(pages), link_status_counts=dict(statuses), numeric_status=numeric,
                          difference_classifications=dict(Counter(issues)),
                          numeric_row_status_counts=dict(numeric_rows),
                          reconciliation_status=row_reconciliation_status(numeric_rows),
                          scoring_applicability_counts=dict(applicability_rows),
                          unresolved_scorable_rows=unverified_scorable,
                          record_type_counts=dict(Counter(r.get('record_type', '') for r in rows)),
                          residency_values=sorted({r.get('residency', '') for r in rows}),
                          youth_values=sorted({r.get('source_is_youth', '') for r in rows})))
    # DATABASE is read only for permit-reference values plus the explicitly requested set-difference diagnostic.
    db_rows = read_csv(DATABASE)
    db = {r['hunt_code'].strip().upper(): r for r in db_rows if r.get('hunt_code', '').strip()}
    permit_fields = sorted({k for r in db_rows for k in r if 'permit' in k.lower() or 'quota' in k.lower()})
    crosswalk = [dict(hunt_code=code, species=r.get('species', ''),
                      current_status='CANONICAL_MEMBERSHIP_UNDER_OFFICIAL_REVIEW',
                      source_pdfs=by_code.get(code, []), canonical_draw_years=sorted(presence.get(code, set())),
                      continuity='SAME_CODE_PRESENCE_ONLY_NOT_A_RECODE_OR_PROGRAM_EQUIVALENCE',
                      database_permit_reference={k:db.get(code, {}).get(k, '') for k in permit_fields})
                 for code,r in sorted(active.items())]
    old_crosswalks = previous_crosswalk_review(sources, active, presence)
    frozen.update(old_crosswalks['input_hashes'])
    changed = [p for p,h in frozen.items() if not local(p).is_file() or sha(local(p)) != h]
    changed += [p for p,h in endpoint_hashes.items() if sha(local(p)) != h]
    changed += [s['pdf_path'] for s in sources if s['sha256'] and sha(local(s['pdf_path'])) != s['sha256']]
    unresolved = [r for r in links if r['numeric_status'] == 'NOT_NUMERICALLY_VERIFIED']
    summary = dict(generated_at=datetime.now(timezone.utc).isoformat(),
                   status='BLOCKED' if unresolved or missing_years or changed or any(s['status']=='ERROR' for s in sources) else 'SOURCE_REVIEW_COMPLETE',
                   pdf_paths=len(sources), unique_pdf_hashes=len(cache), pdf_errors=sum(s['status']=='ERROR' for s in sources),
                   current_canonical_codes=len(active), historical_canonical_codes=len(presence),
                   canonical_rows=sum(map(len, annual.values())), source_hunt_groups=len(links),
                   numeric_status_rows=dict(Counter({s:sum(r['canonical_rows'] for r in links if r['numeric_status']==s) for s in {r['numeric_status'] for r in links}})),
                   unresolved_source_hunt_groups=len(unresolved),
                   reconciliation_status_groups=dict(Counter(r['reconciliation_status'] for r in links)),
                   numeric_status_rows_exact=dict(Counter(r['numeric_status'] for r in row_checks)),
                   scoring_applicability_rows=dict(Counter(r['scoring_applicability'] for r in row_checks)),
                   unresolved_scorable_source_rows=sum(r['unresolved_scorable_rows'] for r in links),
                   unresolved_scorable_source_groups=sum(r['unresolved_scorable_rows'] > 0 for r in links),
                   previous_crosswalk_records=len(old_crosswalks['records']),
                   guidebook_pdfs_scanned=old_crosswalks['guidebook_pdfs_scanned'],
                   confirmed_cited_guidebook_listing_pages=sum(r['cited_first_listing_page_verified'] for r in old_crosswalks['records']),
                   normalized_difference_counts=dict(Counter(r['review_classification'] for r in differences)),
                   missing_years=missing_years, changed_inputs=changed, input_hashes=frozen, raw_endpoint_hashes=endpoint_hashes,
                   limitations=['No code is called retired merely because it is absent from current canonical.',
                                'Historical rows remain in their physical-year canonicals; no additions to current master.',
                                'PDF code presence is not numeric parity or proof of current eligibility.',
                                'Generated presentation PDFs are not substitutes for raw endpoint or official PDF truth.',
                                'Only populated endpoint metrics are compared; missing split fields are not invented.',
                                'Source review is not engine certification; no prediction or website data changed.'])
    write_json(out/names[0], sources)
    write_json(out/names[1], crosswalk)
    write_json(out/names[2], links)
    write_json(out/names[3], dict(database_not_in_current_canonical=sorted(set(db)-set(active)),
                                explicitly_flagged_retired_or_inactive=sorted(excluded),
                                interpretation='Unresolved catalog difference, not a retired list and not an explanation of NO_PROBABILITY.'))
    write_json(out/names[4], summary)
    write_json(out/names[6], old_crosswalks)
    write_json(out/'sportsman_numeric_cell_review.json', numeric_cells)
    with (out/names[8]).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(row_checks[0]) if row_checks else ['numeric_status'])
        w.writeheader()
        w.writerows(row_checks)
    with (out/names[7]).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(endpoint_checks[0]) if endpoint_checks else ['status'])
        w.writeheader()
        w.writerows(endpoint_checks)
    with (out/names[5]).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(differences[0]) if differences else ['review_classification'])
        w.writeheader()
        w.writerows(differences)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('input_hashes', 'raw_endpoint_hashes')}, indent=2))
    return 1 if summary['status']=='BLOCKED' else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=ROOT/'processed_data')
    args = parser.parse_args()
    return build(args.out_dir.resolve())


if __name__ == '__main__':
    raise SystemExit(main())

