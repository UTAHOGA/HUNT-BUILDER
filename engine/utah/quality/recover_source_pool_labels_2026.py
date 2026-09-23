"""Recover 2026 canonical pool metadata and independently recheck raw cells.

Writes a review candidate and row-keyed evidence only. Engine/runtime and original
canonical bytes stay fixed; ambiguous shared-code tables are never relabeled.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as source

CANONICAL = source.YEARLY/'draw_results_2026_for_2027_canonical_yearly_draw_results.csv'
PLANNER = ROOT/'audit_output_phase1_candidate/current_canonical_identity_20260921/planner_popup/dwr_huntplanner_hanumber_2026_raw_payloads.json'
GUIDES = ROOT/'audit_output_phase1_candidate/source_mapping_crosswalk_20260921_v3/source_mapping_2017_2026.json'
METRICS = {'eligible_applicants':'ParticipantCount', 'successful_applicants':'SuccessfulCount',
           'bonus_permits':'SuccessfulByMaxPointRoundCount',
           'regular_permits':'SuccessfulByRegularRoundCount', 'total_permits':'SuccessfulCount'}


def has_activity(row):
    return any((source.decimal(row.get(k,'')) or 0)>0 for k in METRICS)


def table_pool_identity(rows, index):
    """Identify a lost table label by an exact multirow source fingerprint.

    This is transcription/source reconciliation, never forecast calibration.
    Require two distinct positive keys, all populated cells matching one pool,
    and a real competing-pool cell disagreement (not just missing competitors).
    """
    anchors = {}
    for r in rows:
        if r.get('points','')=='' or not has_activity(r):
            continue
        key=(r['hunt_code'],r['residency'].lower(),source.decimal(r['points']))
        if key in anchors and any(r.get(f,'')!=anchors[key].get(f,'') for f in METRICS):
            return '', 'CONFLICTING_PARENT_TABLE_KEYS'
        anchors[key]=r
    if len(anchors)<2:
        return '', 'INSUFFICIENT_PARENT_TABLE_ANCHORS'
    matching, contradicted = [], set()
    for pool in (False,True):
        all_match = True
        for key,row in anchors.items():
            raw = [r for r in index.get(key,[]) if isinstance(r.get('IsYouth'),bool) and r['IsYouth']==pool]
            if len(raw)!=1:
                all_match = False
                continue
            if any(source.decimal(row[field])!=source.decimal(raw[0].get(raw_field))
                   for field,raw_field in METRICS.items() if row.get(field,'')!=''):
                contradicted.add(pool)
                all_match=False
        if all_match:
            matching.append(pool)
    if len(matching)==1 and (not matching[0]) in contradicted:
        return str(matching[0]).lower(), 'EXACT_PARENT_TABLE_MULTIROW_NUMERIC_IDENTITY'
    return '', 'PARENT_TABLE_FINGERPRINT_AMBIGUOUS_OR_CONFLICTING'


def exact_positive_row_pool(row,index):
    """Recover transcription identity from a unique exact raw numeric vector.

    No fuzzy match, odds/error optimization, or zero-only matching. Equal adult
    and youth vectors remain ambiguous. This cannot be used in a forecast.
    """
    if not has_activity(row) or row.get('eligible_applicants','')=='' or row.get('successful_applicants','')=='':
        return '', 'NO_POSITIVE_SOURCE_IDENTITY_ANCHOR'
    key=(row['hunt_code'],row['residency'].lower(),source.decimal(row['points']))
    matches=[raw for raw in index.get(key,[]) if isinstance(raw.get('IsYouth'),bool)
             and all(source.decimal(row[field]) is not None and source.decimal(row[field])==source.decimal(raw.get(raw_field))
                     for field,raw_field in METRICS.items() if row.get(field,'')!='')]
    if len(matches)==1:
        return str(matches[0]['IsYouth']).lower(), 'EXACT_POSITIVE_RAW_ROW_VECTOR_IDENTITY'
    return '', 'MULTIPLE_OR_NO_EXACT_SOURCE_VECTORS'


def eligibility(code, planner, pool_flags):
    item = planner.get(code)
    if not item:
        return 'NO_CURRENT_PLANNER_CONFIRMATION'
    data = item['payload']
    current = [r for r in data.get('huntYears', []) if str(r.get('HUNT_YEAR')) == '2026']
    if not current:
        return 'NO_CURRENT_PLANNER_CONFIRMATION'
    name = data.get('huntMaster', {}).get('HUNT_NAME', '')
    if re.search(r'^(?:draw.only\s+)?youth\b', name, re.I):
        return 'YOUTH_ONLY_EXPLICIT_PLANNER_NAME'
    if pool_flags == {False, True}:
        return 'SHARED_HUNT_WITH_SEPARATE_YOUTH_SOURCE_POOL'
    return 'NOT_IDENTIFIED_AS_YOUTH_ONLY_IN_PLANNER'


def write_csv(path, rows, fields):
    with path.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def apply_reviewed_metadata(review_dir):
    """Apply supported labels as one backed-up canonical/long metadata change."""
    from itertools import zip_longest
    from scripts import rebuild_draw_results_long_from_canonical_yearly as rebuild
    receipt=review_dir/'metadata_application.json'
    if receipt.exists():
        raise ValueError('Application already recorded')
    summary=json.loads((review_dir/'summary.json').read_text(encoding='utf-8'))
    if summary['changed_nonlabel_rows'] or summary['changed_inputs'] or summary['numeric_cell_differences']:
        raise ValueError('Candidate failed immutable/value checks')
    for path,digest in summary['input_hashes'].items():
        # Audit implementation has gained this application routine; all data,
        # raw evidence, and the resolver implementation must still match.
        if source.local(path)==Path(__file__).resolve():
            continue
        if source.sha(source.local(path))!=digest:
            raise ValueError(f'Input changed after review: {path}')
    proposed=review_dir/CANONICAL.name
    before=source.read_csv(CANONICAL)
    after=source.read_csv(proposed)
    evidence=source.read_csv(review_dir/'pool_label_recovery.csv')
    if len(before)!=len(after) or len(before)!=len(evidence):
        raise ValueError('Candidate or evidence row count differs')
    changed=0
    for a,b,e in zip(before,after,evidence):
        if set(a)!=set(b) or any(a[k]!=b[k] for k in a if k!='source_is_youth'):
            raise ValueError('Nonlabel canonical change detected')
        if a['source_is_youth']!=b['source_is_youth']:
            if a['source_is_youth'] or b['source_is_youth'] not in ('true','false'):
                raise ValueError('Only missing labels may be filled')
            if e['recovered_source_is_youth']!=b['source_is_youth'] or e['numeric_status'] not in (
                    'ENDPOINT_POPULATED_FIELDS_MATCH','EMPTY_DISPLAY_RUNG_WITHOUT_ENDPOINT_RECORD_NOT_NUMERICALLY_VERIFIED'):
                raise ValueError('Unsupported label promotion')
            changed+=1
    long_path=rebuild.LONG_FILE
    original_files=rebuild.canonical_files()
    long_before=source.sha(long_path)
    canonical_before=source.sha(CANONICAL)
    preview_dir=review_dir/'long_preview'
    if preview_dir.exists():
        raise ValueError('Long preview exists; inspect the previous application attempt')
    rebuild.AUDIT_DIR=preview_dir
    rebuild.canonical_files=lambda:[proposed if p==CANONICAL else p for p in original_files]
    result=rebuild.rebuild(write=False,allow_split_row_canonical=True)
    if result.get('blocked'):
        raise ValueError('Existing long builder rejected candidate')
    preview=source.local(result['output_path'])
    long_changes=0
    with long_path.open(encoding='utf-8-sig',newline='') as a, preview.open(encoding='utf-8-sig',newline='') as b:
        old,new=csv.DictReader(a),csv.DictReader(b)
        if old.fieldnames!=new.fieldnames:
            raise ValueError('Long-file schema drift')
        for left,right in zip_longest(old,new):
            if left is None or right is None or any(left[k]!=right[k] for k in left if k!='source_is_youth'):
                raise ValueError('Long preview differs outside pool labels')
            if left['source_is_youth']!=right['source_is_youth']:
                if left['actual_draw_year']!='2026' or left['source_is_youth'] or right['source_is_youth'] not in ('true','false'):
                    raise ValueError('Unexpected long pool-label change')
                long_changes+=1
    if long_changes!=changed:
        raise ValueError('Canonical/long label-change count mismatch')
    backup=review_dir/'rollback'
    backup.mkdir()
    shutil.copy2(CANONICAL,backup/CANONICAL.name)
    shutil.copy2(long_path,backup/long_path.name)
    if source.sha(backup/CANONICAL.name)!=canonical_before or source.sha(backup/long_path.name)!=long_before:
        raise ValueError('Backup hash mismatch')
    if source.sha(CANONICAL)!=canonical_before or source.sha(long_path)!=long_before:
        raise ValueError('Source changed during preview build')
    temp=CANONICAL.with_suffix('.pool-recovery.tmp')
    if temp.exists():
        raise ValueError('Canonical temporary path already exists')
    shutil.copy2(proposed,temp)
    try:
        temp.replace(CANONICAL)
        preview.replace(long_path)
    except Exception:
        shutil.copy2(backup/CANONICAL.name,CANONICAL)
        shutil.copy2(backup/long_path.name,long_path)
        raise
    record=dict(status='APPLIED_LOCAL_METADATA_ONLY',changed_canonical_labels=changed,changed_long_labels=long_changes,
                old_canonical_sha256=canonical_before,new_canonical_sha256=source.sha(CANONICAL),
                old_long_sha256=long_before,new_long_sha256=source.sha(long_path),backup_dir=source.rel(backup),
                numeric_or_other_cells_changed=0,engine_or_runtime_rebuilt=False,
                note='Prior frozen reports remain historical evidence. This does not recertify or publish predictions.')
    source.write_json(receipt,record)
    print(json.dumps(record,indent=2))
    return 0


def run(out):
    if out.exists():
        raise ValueError('Use a fresh output directory; preserve prior evidence')
    out.mkdir(parents=True)
    rows = source.read_csv(CANONICAL)
    tables = defaultdict(list)
    for row in rows:
        if row.get('source_dataset')=='OFFICIAL_DWR_2026_PDF_DRAW_RESULTS':
            tables[(row['source_file'],row['hunt_code'],row.get('pdf_page',''))].append(row)
    parents, parent_hashes = source.retained_parent_index()
    inputs = {source.rel(p): source.sha(p) for p in (CANONICAL, PLANNER, GUIDES, Path(__file__), Path(source.__file__))}
    inputs.update(parent_hashes)
    planner = {r['hunt_code']:r for r in json.loads(PLANNER.read_text(encoding='utf-8'))}
    guide_index = defaultdict(list)
    for s in json.loads(GUIDES.read_text(encoding='utf-8')):
        if '/2026/pdf/guidebooks/' not in s['pdf_path'] or s['status']=='ERROR':
            continue
        path = source.local(s['pdf_path'])
        if source.sha(path) != s['sha256']:
            raise ValueError(f'Guidebook changed: {path}')
        inputs[source.rel(path)] = s['sha256']
        for code, pages in s['codes'].items():
            guide_index[code].append(dict(path=s['pdf_path'], pages=pages, sha256=s['sha256']))
    raw_dirs = [ROOT/f'pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_{date}/utahdraws_2026/json'
                for date in ('20260902', '20260826')]
    indices, table_labels, reviews, candidate, differences = {}, {}, [], [], []
    for number, original in enumerate(rows, 2):
        row = dict(original)
        review = dict(canonical_csv_line=number, hunt_code=row['hunt_code'], residency=row.get('residency', ''),
                      points=row.get('points', ''), source_scope=row.get('source_scope', ''),
                      canonical_source=row.get('source_file', ''), pdf_page=row.get('pdf_page', ''),
                      old_source_is_youth=row.get('source_is_youth', ''), recovered_source_is_youth='',
                      recovery_method='', numeric_status='', fields_compared=0, endpoint_path='',
                      endpoint_sha256='', row_index_changed=False, error='')
        endpoint = None
        pool_flags = set()
        try:
            if (row['source_file'].startswith('https://') or row.get('source_dataset', '').startswith('DWR_HUNT_PLANNER')
                    or row.get('source_scope','').endswith('_REFERENCE')):
                review.update(recovery_method='NOT_A_DRAW_OUTCOME_ROW', numeric_status='REFERENCE_NOT_NUMERIC_DRAW_TRUTH')
            else:
                name = source.pdf_endpoint(row) if row.get('source_dataset') == 'OFFICIAL_DWR_2026_PDF_DRAW_RESULTS' else source.live_endpoint(row)
                candidates = [d/name for d in raw_dirs if (d/name).is_file()]
                if not candidates:
                    raise FileNotFoundError(name)
                direct = row.get('source_path', '').replace('\\', '/')
                exact = [p for p in candidates if p.parent.parent.as_posix() in source.local(direct).as_posix()]
                mapped = {p['path'] for p in parents.get((2026,row['source_file']), []) if p['verified'] and p['path'].name==name}
                endpoint = exact[0] if len(exact)==1 else next(iter(mapped)) if len(mapped)==1 else candidates[0]
                if endpoint not in indices:
                    indices[endpoint] = source.raw_endpoint_index(endpoint)
                    inputs[source.rel(endpoint)] = source.sha(endpoint)
                index = indices[endpoint]
                pool, method = source.recover_source_pool(row, index)
                table_key = (row['source_file'],row['hunt_code'],row.get('pdf_page',''))
                if not pool and method=='SHARED_CODE_MULTIPLE_SOURCE_POOLS_REQUIRES_PARENT_TABLE' and table_key in tables:
                    cache_key=(endpoint,table_key)
                    if cache_key not in table_labels:
                        table_labels[cache_key]=table_pool_identity(tables[table_key],index)
                    table_pool,table_method=table_labels[cache_key]
                    if table_pool:
                        pool,method=table_pool,table_method
                if not pool and method=='SHARED_CODE_MULTIPLE_SOURCE_POOLS_REQUIRES_PARENT_TABLE':
                    exact_pool,exact_method=exact_positive_row_pool(row,index)
                    if exact_pool:
                        pool,method=exact_pool,exact_method
                pool_flags = {r['IsYouth'] for (c,_,_), group in index.items() if c==row['hunt_code']
                              for r in group if isinstance(r.get('IsYouth'),bool)}
                review.update(recovered_source_is_youth=pool, recovery_method=method,
                              endpoint_path=source.rel(endpoint), endpoint_sha256=inputs[source.rel(endpoint)])
                if pool:
                    row['source_is_youth'] = pool
                status, cells = source.endpoint_parity(row, index)
                if status=='ENDPOINT_IDENTITY_MISSING_OR_AMBIGUOUS' and not has_activity(row):
                    point=row.get('points','') or ('0' if 'SPORTSMAN' in row.get('source_scope','') else '')
                    key=(row['hunt_code'],row['residency'].lower(),source.decimal(point))
                    matches=[r for r in index.get(key,[]) if isinstance(r.get('IsYouth'),bool) and r['IsYouth']==(pool=='true')]
                    if not matches:
                        status='EMPTY_DISPLAY_RUNG_WITHOUT_ENDPOINT_RECORD_NOT_NUMERICALLY_VERIFIED'
                review.update(numeric_status=status, fields_compared=cells,
                              row_index_changed=row['source_is_youth'] != original['source_is_youth'])
                if pool:
                    point = row.get('points', '') or ('0' if 'SPORTSMAN' in row.get('source_scope','') else '')
                    key=(row['hunt_code'],row['residency'].lower(),source.decimal(point))
                    matched=[r for r in index.get(key,[]) if isinstance(r.get('IsYouth'),bool) and r['IsYouth']==(pool=='true')]
                    if len(matched)==1:
                        raw=matched[0]
                        for field, raw_field in METRICS.items():
                            if row.get(field,'')!='' and source.decimal(row[field]) != source.decimal(raw.get(raw_field)):
                                differences.append(dict(canonical_csv_line=number,hunt_code=row['hunt_code'],residency=row['residency'],
                                    points=point,pool=pool,field=field,canonical_value=row[field],endpoint_value=raw.get(raw_field),endpoint=source.rel(endpoint)))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            review.update(recovery_method='PARENT_READ_OR_MAPPING_ERROR',numeric_status='UNRESOLVED',error=f'{type(exc).__name__}: {exc}')
        review.update(hunt_eligibility=eligibility(row['hunt_code'],planner,pool_flags),
                      planner_source=planner.get(row['hunt_code'],{}).get('source_url',''),
                      guidebook_evidence=json.dumps(guide_index.get(row['hunt_code'],[])))
        candidate.append(row)
        reviews.append(review)
    # Metadata-only invariant: every row and every other original cell is identical.
    changed_other=[n for n,(a,b) in enumerate(zip(rows,candidate),2) if any(a[k]!=b[k] for k in a if k!='source_is_youth')]
    changed_inputs=[p for p,h in inputs.items() if source.sha(source.local(p))!=h]
    summary=dict(generated_at=datetime.now(timezone.utc).isoformat(), canonical_rows=len(rows),
                 labels_recovered=sum(r['row_index_changed'] for r in reviews),
                 recovery_methods=dict(Counter(r['recovery_method'] for r in reviews)),
                 numeric_status_counts=dict(Counter(r['numeric_status'] for r in reviews)),
                 compared_cells=sum(r['fields_compared'] for r in reviews), numeric_cell_differences=len(differences),
                 changed_nonlabel_rows=changed_other, changed_inputs=changed_inputs, input_hashes=inputs,
                 candidate_only=True, original_canonical_changed=False,
                 interpretation='Pool is separate from youth-only eligibility. Multirow exact parent-table matching is source transcription reconciliation, not forecast tuning or prior-year inheritance.',
                 status='BLOCKED' if changed_other or changed_inputs or differences or any(r['numeric_status'] in (
                     'UNRESOLVED','ENDPOINT_SOURCE_DIMENSION_UNRESOLVED','ENDPOINT_VALUE_MISMATCH',
                     'ENDPOINT_IDENTITY_MISSING_OR_AMBIGUOUS','ENDPOINT_MISSING_CANONICAL_METRICS') for r in reviews) else 'REVIEW_COMPLETE')
    write_csv(out/'pool_label_recovery.csv',reviews,list(reviews[0]))
    write_csv(out/CANONICAL.name,candidate,list(rows[0]))
    write_csv(out/'numeric_cell_differences.csv',differences,list(differences[0]) if differences else ['canonical_csv_line','field'])
    source.write_json(out/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='input_hashes'},indent=2))
    return 1 if summary['status']=='BLOCKED' else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--apply-reviewed-metadata',action='store_true')
    args=parser.parse_args()
    raise SystemExit(apply_reviewed_metadata(args.out_dir.resolve()) if args.apply_reviewed_metadata else run(args.out_dir.resolve()))
