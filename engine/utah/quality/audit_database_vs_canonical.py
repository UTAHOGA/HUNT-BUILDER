"""Current-code eligibility audit. Absence does not by itself prove retirement."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATABASE = ROOT / 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'
HUNT_MASTER_CANONICAL = ROOT / 'data/utah/official_downloads_2026/hunt_master_canonical_2026.csv'


def load_canonical(path=HUNT_MASTER_CANONICAL):
    active, excluded, seen = {}, {}, set()
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or 'hunt_code' not in reader.fieldnames:
            raise ValueError('canonical_schema_missing_hunt_code')
        for row in reader:
            code = row.get('hunt_code', '').strip().upper()
            if not code:
                continue
            if code in seen:
                raise ValueError(f'duplicate_canonical_code:{code}')
            seen.add(code)
            row['hunt_code'] = code
            retired = row.get('is_retired', '').strip().lower() == 'true'
            inactive = row.get('status', '').strip().lower() in ('retired', 'inactive')
            (excluded if retired or inactive else active)[code] = row
    if not active:
        raise ValueError('canonical_active_code_set_empty')
    return active, excluded


def audit(database=DATABASE, canonical=HUNT_MASTER_CANONICAL):
    active, excluded = load_canonical(canonical)
    with database.open(encoding='utf-8-sig', newline='') as f:
        db = {r['hunt_code'].strip().upper() for r in csv.DictReader(f) if r.get('hunt_code', '').strip()}
    return dict(database_unique_codes=len(db), canonical_active_codes=len(active),
        explicitly_retired_or_inactive_codes=sorted(excluded),
        database_not_in_active_canonical=sorted(db-set(active)),
        canonical_not_in_database=sorted(set(active)-db),
        overlap=len(db & set(active)),
        canonical_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest(),
        database_sha256=hashlib.sha256(database.read_bytes()).hexdigest(),
        interpretation='Catalog difference only; verify current identity against official Planner. No retirement or promotion decision.')


def current_identity_status(in_canonical, planner):
    if planner and planner.get('fetch_status') != 'OK':
        return 'PLANNER_FETCH_FAILED_REVIEW'
    if planner and planner.get('hunt_year') == '2026':
        return 'CANONICAL_CONFIRMED_CURRENT' if in_canonical else 'CURRENT_PLANNER_MISSING_CANONICAL'
    if planner:
        return 'CANONICAL_PLANNER_NONCURRENT_YEAR' if in_canonical else 'PLANNER_NONCURRENT_YEAR'
    return 'CANONICAL_NOT_IN_CURRENT_PLANNER_REVIEW' if in_canonical else 'NO_CURRENT_PLANNER_CONFIRMATION'


def follow_up_unlisted(review_dir, out):
    """Retain direct official responses; absence from the table is not retirement."""
    import requests
    if out.exists():
        raise ValueError('Choose a fresh follow-up directory')
    out.mkdir(parents=True)
    with (review_dir/'current_code_reconciliation.csv').open(encoding='utf-8-sig') as f:
        reviewed = list(csv.DictReader(f))
    results = []
    for row in reviewed:
        if row['status'] != 'CANONICAL_NOT_IN_CURRENT_PLANNER_REVIEW':
            continue
        code = row['hunt_code']
        result = dict(hunt_code=code, retrieved_at=datetime.now(timezone.utc).isoformat())
        try:
            response = requests.get('https://dwrapps.utah.gov/huntboundary/HaNumber',
                                    params={'roles': '', 'hn': code}, timeout=30)
            result.update(url=response.url, http_status=response.status_code,
                          sha256=hashlib.sha256(response.content).hexdigest())
            (out/f'{code}.json').write_bytes(response.content)
            response.raise_for_status()
            data = response.json()
            master = data.get('huntMaster') or {}
            if master.get('HUNT_NBR') != code:
                raise ValueError('Official response hunt identity does not match request')
            years = [y for y in data.get('huntYears', []) if y.get('HUNT_NBR') == code]
            current = [y for y in years if str(y.get('HUNT_YEAR')) == '2026']
            result.update(years=sorted({str(y.get('HUNT_YEAR')) for y in years}),
                          current_year_records=current,
                          status='CURRENT_2026_OUTSIDE_TABLE' if current else 'NO_2026_RECORD_IN_DIRECT_ENDPOINT')
        except Exception as exc:
            result.update(status='UNRESOLVED_REQUEST_OR_IDENTITY', error=str(exc))
        results.append(result)
    canonical, _ = load_canonical()
    species = {r.get('species', '').strip().casefold() for r in canonical.values()}
    missing = [r for r in reviewed if r['status'] == 'CURRENT_PLANNER_MISSING_CANONICAL']
    in_scope = [r['hunt_code'] for r in missing if r['planner_species'].strip().casefold() in species]
    extra_scope = [r['hunt_code'] for r in missing if r['hunt_code'] not in in_scope]
    summary = dict(direct_checks=len(results), status_counts=dict(Counter(r['status'] for r in results)),
                   current_missing_in_existing_canonical_species=in_scope,
                   current_missing_additional_species=extra_scope,
                   interpretation='No retirement inferred. Existing-species scope is descriptive, not an automatic inclusion rule.',
                   results=results)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}, indent=2))
    return summary


def export_evidence(planner_path, source_mapping, out):
    """Export the requested snapshot names; all membership/counts are measured."""
    active, excluded = load_canonical(HUNT_MASTER_CANONICAL)
    canonical = set(active) | set(excluded)
    with planner_path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    planner = {r['hunt_code'].strip().upper() for r in rows
               if r.get('fetch_status') == 'OK' and str(r.get('hunt_year')) == '2026'}
    with DATABASE.open(encoding='utf-8-sig', newline='') as f:
        database = {r['hunt_code'].strip().upper() for r in csv.DictReader(f) if r.get('hunt_code', '').strip()}
    missing = sorted(planner-canonical)
    unconfirmed = sorted(canonical-planner)
    unresolved = sorted(database-planner-canonical)
    sources = json.loads(source_mapping.read_text(encoding='utf-8-sig'))
    evidence = {}
    for source in sources:
        if source['status'] == 'ERROR':
            continue
        path = ROOT/source['pdf_path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError(f'PDF changed since page indexing: {path}')
        for code, pages in source['codes'].items():
            for page in pages:
                evidence.setdefault(code, []).append(dict(pdf_path=source['pdf_path'], page=page,
                    sha=source['sha256'], codes_parsed=source['codes_parsed']))
    hashes = {str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (HUNT_MASTER_CANONICAL, DATABASE, planner_path, source_mapping)}
    followup = ROOT/'audit_output_phase1_candidate/current_canonical_identity_20260921/direct_followup/summary.json'
    followup_current = []
    if followup.is_file():
        data = json.loads(followup.read_text(encoding='utf-8'))
        followup_current = sorted(r['hunt_code'] for r in data['results'] if r['status']=='CURRENT_2026_OUTSIDE_TABLE')
        hashes[str(followup.relative_to(ROOT))] = hashlib.sha256(followup.read_bytes()).hexdigest()
    outputs = {
        'current_but_uncanonicalized_171.json': dict(count=len(missing), codes=missing,
            classification='CURRENT_PLANNER_2026_MISSING_CANONICAL_NOT_RETIRED', source_hashes=hashes),
        'canonical_without_confirmation_33.json': dict(count=len(unconfirmed), codes=unconfirmed,
            classification='MATRIX_CONFIRMATION_MISSING_REVIEW_NOT_RETIREMENT',
            direct_followup_confirmed_2026=followup_current,
            remaining_after_direct_followup=sorted(set(unconfirmed)-set(followup_current)), source_hashes=hashes),
        'hunt_crosswalk_with_evidence.json': dict(generated_at=datetime.now(timezone.utc).isoformat(),
            planner_2026_count=len(planner), canonical_count=len(canonical), database_count=len(database),
            source_hashes=hashes, unresolved_lineage=unresolved,
            failed_pdf_sources=[s for s in sources if s['status']=='ERROR'],
            numeric_policy='False means not asserted by this presence crosswalk; consult exact-year row/cell audit separately.',
            rows=[dict(hunt_code=code, in_planner_2026=code in planner,
                in_canonical_1288=code in canonical, in_database=code in database,
                direct_planner_2026_confirmation=code in followup_current,
                classification=('CURRENT_BUT_UNCANONICALIZED' if code in planner-canonical else
                    'CANONICAL_WITHOUT_MATRIX_CONFIRMATION' if code in canonical-planner else
                    'UNRESOLVED_LINEAGE' if code in unresolved else 'CANONICAL_CURRENT_CONFIRMED'),
                pdf_evidence=evidence.get(code, []), numeric_match=False)
                for code in sorted(planner | canonical | database)])}
    out.mkdir(parents=True, exist_ok=True)
    if any((out/name).exists() for name in outputs):
        raise ValueError('Requested exports already exist; choose fresh output directory')
    for name, value in outputs.items():
        with (out/name).open('x', encoding='utf-8') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
    print(json.dumps(dict(planner_2026=len(planner), canonical=len(canonical),
        current_but_uncanonicalized=len(missing), canonical_without_matrix_confirmation=len(unconfirmed),
        direct_followup_confirmed_2026=followup_current, unresolved_lineage=len(unresolved),
        files=list(outputs)), indent=2))


def current_audit(planner_path, out):
    """Write a separate review, never rewrite a canonical or publish predictions."""
    planner_path, out = planner_path.resolve(), out.resolve()
    if out.exists():
        raise ValueError('Output exists; preserve prior evidence and choose a fresh directory')
    active, excluded = load_canonical(HUNT_MASTER_CANONICAL)
    canonical = {**active, **excluded}
    with planner_path.open(encoding='utf-8-sig', newline='') as f:
        planner_rows = list(csv.DictReader(f))
    planner = {r['hunt_code'].strip().upper(): r for r in planner_rows}
    if len(planner) != len(planner_rows):
        raise ValueError('duplicate_planner_hunt_codes')
    baseline = audit()
    db = set(baseline['database_not_in_active_canonical']) | (set(active)-set(baseline['canonical_not_in_database']))
    raw_dir = ROOT/'pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902/utahdraws_2026/json'
    evidence_paths = [HUNT_MASTER_CANONICAL, DATABASE, planner_path]
    draw_sources = {}
    for path in sorted(raw_dir.glob('*.json')):
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(payload, dict) or not isinstance(payload.get('Data'), list):
            continue
        evidence_paths.append(path)
        for hunt in payload['Data']:
            code = str(hunt.get('HuntCode', '')).strip().upper()
            if re.fullmatch(r'[A-Z]{2}\d{4}', code) and hunt.get('OddsList'):
                draw_sources.setdefault(code, []).append(str(path.relative_to(ROOT)))
    rows = []
    for code in sorted(set(canonical) | set(planner) | db | set(draw_sources)):
        c, p = canonical.get(code, {}), planner.get(code, {})
        rows.append(dict(hunt_code=code, canonical_present=code in canonical,
            database_present=code in db, explicit_canonical_retired_or_inactive=code in excluded,
            status=current_identity_status(code in canonical, p),
            canonical_name=c.get('hunt_name', ''), canonical_species=c.get('species', ''),
            planner_name=p.get('dwr_hunt_name', ''), planner_species=p.get('dwr_species', ''),
            planner_hunt_year=p.get('hunt_year', ''), planner_source=p.get('source_url', ''),
            planner_retrieved_at=p.get('source_retrieved_at', ''),
            retained_2026_draw_evidence=';'.join(draw_sources.get(code, []))))
    current = {code for code,p in planner.items() if p.get('fetch_status')=='OK' and p.get('hunt_year')=='2026'}
    summary = dict(generated_at=datetime.now(timezone.utc).isoformat(),
        status='REVIEW_REQUIRED', canonical_codes=len(canonical), planner_matrix_codes=len(planner),
        planner_current_2026_codes=len(current), canonical_confirmed_current=len(set(canonical)&current),
        current_planner_missing_canonical=len(current-set(canonical)),
        canonical_without_current_planner_confirmation=len(set(canonical)-current),
        explicit_retired_or_inactive_in_canonical=sorted(excluded),
        status_counts=dict(Counter(r['status'] for r in rows)),
        retained_draw_codes=len(draw_sources), retained_draw_snapshot=str(raw_dir),
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_paths},
        guardrails=['Absence from Planner or canonical does not prove retirement.',
                    'Prior-year PDFs prove historical presence, not current eligibility.',
                    'Current-hunt master and historical yearly draw canonicals have distinct roles.',
                    'No canonical, database or prediction output was changed.'])
    out.mkdir(parents=True)
    with (out/'current_code_reconciliation.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--planner', type=Path)
    parser.add_argument('--review-dir', type=Path)
    parser.add_argument('--follow-up-review', type=Path)
    parser.add_argument('--source-mapping', type=Path)
    parser.add_argument('--export-evidence', action='store_true')
    args = parser.parse_args()
    if args.export_evidence:
        if not args.planner or not args.source_mapping:
            parser.error('--export-evidence requires --planner and --source-mapping')
        export_evidence(args.planner, args.source_mapping, args.review_dir or ROOT/'processed_data')
        return 0
    if args.follow_up_review:
        if not args.review_dir:
            parser.error('--follow-up-review requires --review-dir for separate outputs')
        follow_up_unlisted(args.follow_up_review, args.review_dir)
        return 0
    if args.planner:
        if not args.review_dir:
            parser.error('--planner requires --review-dir')
        current_audit(args.planner, args.review_dir)
        return 0
    result = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
            f.write('\n')
    print(f"DATABASE codes absent from active canonical (not proven retired): {len(result['database_not_in_active_canonical'])}")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
