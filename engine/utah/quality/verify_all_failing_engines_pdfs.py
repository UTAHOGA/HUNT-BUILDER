"""Read-only PDF inventory, source-scope and canonical numeric verification.

File integrity, current-code overlap and numeric parity are separate results.
Unsupported layouts/missing evidence block a full-verification claim. No deletion,
truth rewriting, forecasting, or certification/promotion is performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import requests

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.audit_antlerless_pdf_canonical_cells import parse_line, METRICS
from engine.utah.quality.audit_database_vs_canonical import load_canonical

YEARS = range(2017, 2027)
SCOPES = ('BIG_GAME', 'GENERAL_SEASON_DEER', 'DEDICATED_HUNTER',
          'YOUTH_GENERAL_SEASON_DEER', 'YOUTH_ANY_BULL_ELK', 'YOUTH_DEDICATED_HUNTER',
          'LIFETIME_GENERAL_SEASON_DEER', 'SPORTSMAN', 'ANTLERLESS', 'YOUTH_ANTLERLESS',
          'BLACK_BEAR', 'TURKEY', 'YOUTH_TURKEY', 'COUGAR')
PDF_ROOTS = (ROOT/'pipeline/RAW/hunt_unit_database', ROOT/'data_truth/draw_results_truth/raw_pdfs')
INVENTORY = ROOT/'data_model/quality/raw_pdf_inventory.csv'
DATABASE = ROOT/'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'
HUNT_MASTER_CANONICAL = ROOT/'data/utah/official_downloads_2026/hunt_master_canonical_2026.csv'
MASTER_PATHS = (ROOT/'data/utah/official_downloads_2026/hunt_master_canonical_2026.csv',
                ROOT/'data/hunt-master-canonical-2026-source-of-truth.csv',
                ROOT/'processed_data/hunt_master_enriched.csv')
CODE = re.compile(r'\b[A-Z]{2,3}\d{3,4}\b')
HUNT = re.compile(r'\bHunt\s*:\s*([A-Z]{2,3}\d{3,4})\b', re.I)
PINNED = ROOT/'pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf'
PINNED_SHA = '2b1b19782089732b9cacc2fd9ce00e60e1093acda6f3ed70d29e8d6e3ae83b08'
MANIFESTS = tuple(ROOT/'pipeline/manifests'/name for name in (
    'utah_dwr_draw_pdf_links_2020plus.csv', 'utah_bear_turkey_pdf_links_2020plus.csv',
    'pdf_model_ready_manifest_with_target_year_v3.csv', 'pdf_training_manifest_2023_2026.csv'))
OFFICIAL_INDEXES = ('https://wildlife.utah.gov/biggame/odds', 'https://wildlife.utah.gov/odds')
REQUESTED_2026_URLS = (
    'https://wildlife.utah.gov/pdf/bg/2026/26_antlerless_drawing_odds_report.pdf',
    'https://wildlife.utah.gov/pdf/bg/2026/26_bg-odds.pdf',
    'https://wildlife.utah.gov/pdf/bg/2026/26_deer_odds.pdf',
    'https://wildlife.utah.gov/pdf/bear/2026/26_drawing_odds.pdf',
)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href' and v)


def pull_official_2026(out):
    """Retain verified PDF responses only; never overwrite an archived source."""
    checks, urls = [], set(REQUESTED_2026_URLS)
    for url in OFFICIAL_INDEXES:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            parser = Links()
            parser.feed(response.text)
            discovered = sorted({urljoin(url, link) for link in parser.links
                if '.pdf' in link.lower() and re.search(r'(?:2026|/26[_-])', link)})
            urls.update(link for link in discovered if urlparse(link).hostname == 'wildlife.utah.gov')
            checks.append(dict(url=url, status='INDEX_READ', discovered_2026_pdf_urls=discovered))
        except requests.RequestException as exc:
            checks.append(dict(url=url, status='INDEX_FETCH_FAILED', reason=str(exc)))
    archive = ROOT/'pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_archive/download_verified'
    for url in sorted(urls):
        check = dict(url=url, checked_at=datetime.now(timezone.utc).isoformat())
        try:
            response = requests.get(url, timeout=30)
            check.update(http_status=response.status_code, final_url=response.url,
                         content_type=response.headers.get('Content-Type'))
            response.raise_for_status()
            if urlparse(response.url).hostname != 'wildlife.utah.gov':
                raise ValueError('Redirect left official DWR host')
            content = response.content
            if not content.startswith(b'%PDF-'):
                raise ValueError('Response is not PDF bytes')
            with pymupdf.open(stream=content, filetype='pdf') as doc:
                header = '\n'.join(doc[i].get_text() for i in range(min(3, len(doc))))
                if not len(doc) or not re.search(r'\b2026\b', header) or not re.search(r'draw|odds', header, re.I):
                    raise ValueError('2026 draw report identity not verified in document')
                check['pages_actual'] = len(doc)
            digest = hashlib.sha256(content).hexdigest()
            archive.mkdir(parents=True, exist_ok=True)
            target = archive/(hashlib.sha1(url.encode()).hexdigest()[:8]+'__'+Path(urlparse(url).path).name)
            if target.exists():
                if sha(target) != digest:
                    raise ValueError('Retained file differs; review needed, not overwritten')
                status = 'VERIFIED_EXISTING'
            else:
                with target.open('xb') as f:
                    f.write(content)
                status = 'DOWNLOADED_VERIFIED'
            check.update(status=status, path=rel(target), sha_actual=digest, size_actual=len(content))
        except (requests.RequestException, ValueError, RuntimeError, OSError) as exc:
            check.update(status='FETCH_OR_IDENTITY_FAILED', reason=str(exc))
        checks.append(check)
        print(f"2026 official check: {check['status']} {url}", flush=True)
    (out/'2026_official_pdf_fetch_audit.json').write_text(json.dumps(checks, indent=2)+'\n', encoding='utf-8')
    return checks


def difference_record(year, scope, source_file, key, difference):
    # Source document identity and source cell value are distinct fields.
    return dict(year=year, scope=scope, source_file=source_file, key=str(key), **difference)


def endpoint_key(code, residency, point, youth):
    from decimal import Decimal
    return (str(code).upper(), str(residency).upper(), str(Decimal(str(point)).normalize()), youth)


def compare_endpoint_rows(rows, csv_path):
    """Compare to raw JSON, not to another generated CSV; exact youth/lane keys."""
    endpoint = csv_path.parent.parent/'json'/csv_path.with_suffix('.json').name
    issues, matched, cells = [], 0, 0
    if not endpoint.is_file():
        return dict(status='MISSING_RAW_ENDPOINT', matched_rows=0, cells_compared=0, issues=[], path=rel(endpoint))
    digest = sha(endpoint)
    try:
        payload = json.loads(endpoint.read_text(encoding='utf-8-sig'))
        index = defaultdict(list)
        for hunt in payload['Data']:
            for raw in hunt.get('OddsList', []):
                lane = {1:'Resident', 2:'Nonresident'}.get(raw.get('ResidencyTypeID'))
                if lane is None or raw.get('Point') is None or not isinstance(raw.get('IsYouth'), bool):
                    continue
                key = endpoint_key(hunt['HuntCode'], lane, raw['Point'], raw['IsYouth'])
                index[key].append(raw)
        fields = {'eligible_applicants':'ParticipantCount', 'bonus_permits':'SuccessfulByMaxPointRoundCount',
                  'regular_permits':'SuccessfulByRegularRoundCount', 'total_permits':'SuccessfulCount',
                  'successful_applicants':'SuccessfulCount'}
        for row in rows:
            youth_text = row.get('source_is_youth', '').lower()
            if youth_text not in ('true', 'false'):
                match = re.search(r'is-youth=(true|false)', row.get('source_row_identifier', ''), re.I)
                youth_text = match[1].lower() if match else ''
            if youth_text not in ('true', 'false') or row.get('points', '') == '':
                issues.append(dict(key=row.get('source_row_identifier'), status='ENDPOINT_IDENTITY_UNRESOLVED'))
                continue
            key = endpoint_key(row['hunt_code'], row['residency'], row['points'], youth_text == 'true')
            candidates = index.get(key, [])
            if len(candidates) != 1:
                issues.append(dict(key=str(key), status='ENDPOINT_KEY_MISSING_OR_AMBIGUOUS', candidates=len(candidates)))
                continue
            matched += 1
            for canonical_field, raw_field in fields.items():
                value, raw_value = row.get(canonical_field), candidates[0].get(raw_field)
                if value in (None, '') or raw_value is None:
                    issues.append(dict(key=str(key), field=canonical_field, status='ENDPOINT_CELL_MISSING'))
                    continue
                cells += 1
                if float(value) != float(raw_value):
                    issues.append(dict(key=str(key), field=canonical_field, source=raw_value, canonical=value, status='VALUE_MISMATCH'))
        if sha(endpoint) != digest:
            issues.append(dict(status='SOURCE_CHANGED_DURING_READ'))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        issues.append(dict(status='ENDPOINT_READ_FAILED', reason=str(exc)))
    return dict(status='BLOCKED' if issues else 'NUMERIC_PARITY_VERIFIED', matched_rows=matched,
                cells_compared=cells, issues=issues, path=rel(endpoint), sha_actual=digest)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def rel(path):
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def local(value):
    p = Path(str(value).replace('\\', '/'))
    return p if p.is_absolute() else ROOT/p


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r)) or ['status']
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def visible_lines(page):
    """Group words in displayed coordinates, including rotated DWR tables."""
    words = []
    for word in page.get_text('words'):
        rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
        words.append(((rect.y0+rect.y1)/2, rect.x0, word[4]))
    lines = []
    for y, x, text in sorted(words):
        if not lines or abs(y-lines[-1][0]) > 2:
            lines.append((y, []))
        lines[-1][1].append((x, text))
    return [' '.join(text for _, text in sorted(words)) for _, words in lines]


def inspect_pdf(path):
    result = dict(path=rel(path), sha_actual=None, size_actual=None, pages_actual=None,
                  codes=[], status='FAIL', blockers=[], table_rows={}, header_years=[])
    if not path.is_file():
        result['blockers'].append('MISSING_FILE')
        return result
    try:
        result['sha_actual'] = sha(path)
        result['size_actual'] = path.stat().st_size
        codes, tables, years = set(), {}, set()
        with pymupdf.open(path) as pdf:
            result['pages_actual'] = len(pdf)
            if not len(pdf):
                result['blockers'].append('EMPTY_PDF')
            total_words = 0
            for page_no, page in enumerate(pdf, 1):
                lines = visible_lines(page)
                text = '\n'.join(lines)
                total_words += len(text.strip())
                # Do not infer draw year from archive/model-year folders.
                if page_no <= 3:
                    years.update(re.findall(r'\b(20\d{2})\s+(?:Draw|Sportsman)', text, re.I))
                hunts = HUNT.findall(text)
                codes.update(h.upper() for h in hunts)
                if 'Sportsman' in text:
                    codes.update(CODE.findall(text))
                if len(hunts) != 1:
                    continue
                for line in lines:
                    parsed = parse_line(line)
                    if parsed is None:
                        continue
                    key = (hunts[0].upper(), parsed['record_type'], parsed['points'], str(page_no))
                    if key in tables:
                        result['blockers'].append('DUPLICATE_SOURCE_ROW:' + str(key))
                    tables[key] = parsed
            if not total_words:
                result['blockers'].append('NO_EXTRACTABLE_TEXT')
        result.update(codes=sorted(codes), table_rows=tables, header_years=sorted(years))
        if sha(path) != result['sha_actual']:
            result['blockers'].append('SOURCE_CHANGED_DURING_READ')
    except Exception as exc:
        result['blockers'].append(f'UNREADABLE_OR_UNPARSED_PDF:{type(exc).__name__}:{exc}')
    result['status'] = 'FAIL' if result['blockers'] else 'READABLE_NOT_NUMERICALLY_CERTIFIED'
    return result


def check_inventory(entry, result):
    reasons = []
    for keys, measured, name in ((('sha256',), result['sha_actual'], 'SHA'),
                                 (('file_size_bytes', 'size_bytes', 'file_size'), result['size_actual'], 'SIZE'),
                                 (('page_count', 'pages'), result['pages_actual'], 'PAGES')):
        expected = next((entry[k] for k in keys if entry.get(k) not in (None, '')), None)
        if expected is not None and str(expected).lower() != str(measured).lower():
            reasons.append(f'{name}_MISMATCH:expected={expected}:actual={measured}')
    return reasons


def compare_row(canonical, parsed):
    diffs, count = [], 0
    for lane in ('resident', 'nonresident'):
        for metric in METRICS:
            field = f'{lane}_{metric}'
            value = canonical.get(field, '')
            if value == '':
                diffs.append(dict(field=field, source=parsed[field], canonical=value, status='CANONICAL_CELL_MISSING'))
                continue
            count += 1
            try:
                actual = value.strip() if metric == 'success_ratio' else int(value.replace(',', ''))
            except ValueError:
                actual = None
            if actual != parsed[field]:
                # Preserve printed differences; do not silently normalize anomalies.
                documented = ('OFFICIAL_SOURCE_TOP_POINT_TOTAL_RATIO_CARRYOVER' in canonical.get('qa_notes', '')
                              and metric in ('total_permits', 'success_ratio')
                              and parsed[f'{lane}_eligible_applicants'] == 0
                              and parsed[f'{lane}_bonus_permits'] == 0
                              and parsed[f'{lane}_regular_permits'] == 0
                              and actual == (0 if metric == 'total_permits' else 'N/A'))
                diffs.append(dict(field=field, source=parsed[field], canonical=value,
                                  status='DOCUMENTED_SOURCE_DISPLAY_CARRYOVER' if documented else 'VALUE_MISMATCH'))
    return count, diffs


def reference_inventory(results):
    """Reconcile stale path references without silently treating them as live truth."""
    legacy_path = ROOT/'data_model/quality/raw_pdf_inventory_audit.csv'
    legacy = read_csv(legacy_path) if legacy_path.exists() else []
    checks = []
    for row in legacy:
        value = row.get('path', '')
        if not value or Path(value).suffix.lower() != '.pdf':
            continue
        path = local(value).resolve()
        measured = results.get(path)
        checks.append(dict(source_manifest=rel(legacy_path), path=value,
            prior_status=row.get('promotion_status', ''),
            status=('MISSING_LEGACY_REFERENCED_FILE' if not path.is_file() else
                    measured['status'] if measured else 'OUTSIDE_SCANNED_ROOTS_REQUIRES_REVIEW')))
    manifest_counts = {}
    for manifest in MANIFESTS:
        if not manifest.is_file():
            checks.append(dict(source_manifest=rel(manifest), status='MISSING_MANIFEST'))
            continue
        rows = read_csv(manifest)
        manifest_counts[rel(manifest)] = len(rows)
        for row in rows:
            value = row.get('final_path') or row.get('path') or row.get('source_path')
            if value and value.lower().endswith('.pdf'):
                p = local(value)
                checks.append(dict(source_manifest=rel(manifest), path=value,
                    status='PATH_PRESENT' if p.is_file() else 'LEGACY_MANIFEST_PATH_UNRESOLVED'))
            elif row.get('url', '').lower().endswith('.pdf'):
                # These are the exact downloader target conventions, not a basename guess.
                url, year = row['url'], row.get('publish_year', '')
                prefix = hashlib.sha1(url.encode()).hexdigest()[:8]
                name = (f"{row['species']}_{Path(row.get('href', url)).name}" if row.get('species')
                        else f"{row.get('label') or 'draw_results'}.pdf")
                name = ' '.join(''.join('_' if c in '<>:"/\\|?*' else c for c in name).split())
                p = ROOT/f'pipeline/RAW/hunt_unit_database/{year}/pdf/draw_odds'/(prefix+'__'+name)
                checks.append(dict(source_manifest=rel(manifest), path=rel(p), url=url,
                    status='PATH_PRESENT' if p.is_file() else 'MISSING_DOWNLOAD_TARGET'))
    return checks, dict(legacy_audit_rows=len(legacy),
        legacy_status_counts=dict(Counter(r.get('promotion_status') for r in legacy)),
        original_flagged_rows=[r for r in checks if r.get('prior_status') in ('HOLD_UNREADABLE_PDF','HOLD_UNKNOWN_YEAR')],
        manifest_rows=manifest_counts, reference_status_counts=dict(Counter(r['status'] for r in checks)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=ROOT/'processed_data')
    parser.add_argument('--baseline-inventory', type=Path)
    parser.add_argument('--skip-download', action='store_true', help='Offline audit; official publication freshness remains unchecked')
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    name = '2026_all_species_all_years_2017_2026_audit'
    if (out/(name+'.json')).exists():
        raise SystemExit('Refusing to overwrite completed audit; use --out-dir with a new directory')
    fetch_checks = [] if args.skip_download else pull_official_2026(out)
    inv = read_csv(INVENTORY)
    baseline = read_csv(args.baseline_inventory) if args.baseline_inventory else []
    db_codes = {r['hunt_code'].strip().upper() for r in read_csv(DATABASE) if r.get('hunt_code')}
    master = HUNT_MASTER_CANONICAL
    canonical_rows, excluded_canonical_rows = load_canonical(master)
    hm_codes = set(canonical_rows)
    inputs = [INVENTORY, DATABASE, ROOT/'scripts/resolve-antlerless-hunt-codes-2026.py',
              ROOT/'data_truth/draw_results_truth/normalized/draw_results_long.csv',
              Path(__file__), ROOT/'governance/prediction-family-certification.json']
    inputs += [p for p in MANIFESTS if p.is_file()]
    if master:
        inputs.append(master)
    canonicals, missing = {}, []
    parents, scope_counts = defaultdict(list), Counter()
    for year in YEARS:
        path = ROOT/f'data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv'
        if not path.is_file():
            missing.append(dict(year=year, path=rel(path), status='MISSING_CANONICAL'))
            continue
        inputs.append(path)
        canonicals[year] = read_csv(path)
        for row in canonicals[year]:
            scope_counts[(year, row.get('source_scope'))] += 1
            parents[(year, row.get('source_scope', ''), row.get('source_file', ''))].append(row)
    frozen = {rel(p): sha(p) for p in inputs}
    paths = {p.resolve() for base in PDF_ROOTS if base.exists() for p in base.rglob('*.pdf')}
    inv_by_path, old_by_path = defaultdict(list), defaultdict(list)
    for collection, dest in ((inv, inv_by_path), (baseline, old_by_path)):
        for row in collection:
            value = row.get('path') or row.get('file_path') or row.get('relative_path')
            if value and Path(value).suffix.lower() == '.pdf':
                p = local(value).resolve()
                paths.add(p)
                dest[p].append(row)
    resolved = {}
    for parent, rows in parents.items():
        year, scope, source = parent
        source_paths = {r['source_path'] for r in rows if r.get('source_path')}
        direct = {local(p).resolve() for p in source_paths if local(p).suffix.lower() == '.pdf' and local(p).is_file()}
        archive = ROOT/f'pipeline/RAW/hunt_unit_database/{year}/pdf/draw_odds'/source
        if not direct and archive.is_file():
            direct.add(archive.resolve())
        if not direct:
            # Exact basename only, restricted to the physical draw year's folder;
            # never substitute an adult file for a youth source.
            direct = {p for p in paths if p.name.lower() == Path(source).name.lower()
                      and f'/{year}/' in p.as_posix()}
        if len({sha(p) for p in direct}) > 1:
            missing.append(dict(year=year, source=source, status='AMBIGUOUS_PARENT_COPIES'))
            direct = set()
        resolved[parent] = min(direct, key=str) if direct else None
        paths.update(direct)
    results, cache = {}, {}
    for index, path in enumerate(sorted(paths), 1):
        digest = sha(path) if path.is_file() else None
        if digest is not None and digest in cache:
            result = {**cache[digest], 'path': rel(path), 'blockers': list(cache[digest]['blockers'])}
        else:
            result = inspect_pdf(path)
            if digest:
                cache[digest] = result
        reasons = [reason for r in inv_by_path[path] for reason in check_inventory(r, result)]
        result = {**result, 'inventory_checks': reasons,
                  'prior_inventory_changes': [reason for r in old_by_path[path] for reason in check_inventory(r, result)],
                  'db_overlap': len(set(result['codes']) & db_codes),
                  'hm_overlap': len(set(result['codes']) & hm_codes)}
        if reasons:
            result['status'] = 'FAIL'
        # A hash prefix alone never proves a PDF synthetic and never authorizes deletion.
        result['previously_disputed_signature'] = bool(digest and digest.startswith('21ea12ab'))
        if path == PINNED.resolve() and (digest, result['size_actual'], result['pages_actual']) != (PINNED_SHA, 774859, 203):
            result['blockers'].append('PINNED_2024_ADULT_ANTLERLESS_SIGNATURE_MISMATCH')
            result['status'] = 'FAIL'
        results[path] = result
        if index % 50 == 0:
            print(f'PDFs inspected {index}/{len(paths)}', flush=True)
    source_reviews, differences = [], []
    for parent, rows in sorted(parents.items()):
        year, scope, source = parent
        # Endpoint/Planner records have no original PDF page. Never parse their
        # source CSV as a PDF or substitute a locally designed presentation PDF.
        if year == 2026 and (source.startswith('UtahDraws live') or source.startswith('https://')):
            csv_paths = {local(r['source_path']) for r in rows if r.get('source_path')}
            if source.startswith('UtahDraws live') and len(csv_paths) == 1:
                endpoint_review = compare_endpoint_rows(rows, next(iter(csv_paths)))
                for diff in endpoint_review['issues']:
                    differences.append(difference_record(year, scope, source, diff.get('key', ''), {k:v for k,v in diff.items() if k!='key'}))
                source_reviews.append(dict(year=year, scope=scope, source=source,
                    path=endpoint_review['path'], canonical_rows=len(rows),
                    matched_rows=endpoint_review['matched_rows'], cells_compared=endpoint_review['cells_compared'],
                    status=endpoint_review['status'], source_kind='OFFICIAL_ENDPOINT_JSON',
                    sha_actual=endpoint_review.get('sha_actual'),
                    issues=dict(Counter(d['status'] for d in endpoint_review['issues']))))
            else:
                status = 'PLANNER_REFERENCE_NOT_DRAW_PDF' if source.startswith('https://') else 'ENDPOINT_PARENT_MAPPING_REQUIRES_FRESH_PARITY'
                source_reviews.append(dict(year=year, scope=scope, source=source, path='',
                    canonical_rows=len(rows), matched_rows=0, cells_compared=0,
                    status=status, source_kind='NON_PDF', issues={status:len(rows)}))
            continue
        path = resolved[parent]
        pdf = results.get(path)
        matched = cells = 0
        statuses = Counter()
        seen = set()
        for row in rows:
            key = (row['hunt_code'], row['record_type'], row['points'], row['pdf_page'])
            parsed = pdf['table_rows'].get(key) if pdf else None
            if key in seen:
                statuses['DUPLICATE_CANONICAL_KEY'] += 1
            seen.add(key)
            if parsed is None:
                statuses['UNVERIFIED_LAYOUT_OR_KEY'] += 1
                differences.append(dict(year=year, scope=scope, source=source, key=str(key), status='UNVERIFIED_LAYOUT_OR_KEY'))
                continue
            matched += 1
            count, diffs = compare_row(row, parsed)
            cells += count
            for diff in diffs:
                statuses[diff['status']] += 1
                differences.append(difference_record(year, scope, source, key, diff))
        extra = set(pdf['table_rows']) - seen if pdf else set()
        for key in sorted(extra):
            differences.append(dict(year=year, scope=scope, source=source, key=str(key), status='PDF_ROW_NOT_IN_CANONICAL'))
        statuses['PDF_ROW_NOT_IN_CANONICAL'] += len(extra)
        blockers = not pdf or pdf['status'] == 'FAIL' or any(v for k,v in statuses.items() if k != 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER')
        source_reviews.append(dict(year=year, scope=scope, source=source, path=rel(path) if path else '',
            canonical_rows=len(rows), matched_rows=matched, cells_compared=cells,
            status='BLOCKED' if blockers else 'NUMERIC_PARITY_VERIFIED', issues=dict(statuses)))
        if path is None:
            missing.append(dict(year=year, source=source, status='MISSING_PARENT_PDF'))
    matrix = []
    for year in YEARS:
        for scope in sorted(set(SCOPES) | {s for y,s in scope_counts if y == year}):
            group = [r for r in source_reviews if r['year'] == year and r['scope'] == scope]
            status = ('SOURCE_SCOPE_ABSENT_REQUIRES_PUBLICATION_REVIEW' if not group else
                      'BLOCKED' if any(r['status']!='NUMERIC_PARITY_VERIFIED' for r in group) else 'NUMERIC_PARITY_VERIFIED')
            matrix.append(dict(year=year, scope=scope, status=status, canonical_rows=scope_counts[(year,scope)],
                               source_files=';'.join(r['source'] for r in group)))
    changed = {p for p, digest in frozen.items() if not (ROOT/p).is_file() or sha(ROOT/p) != digest}
    serial = [{k:v for k,v in r.items() if k != 'table_rows'} for r in results.values()]
    reference_checks, reference_summary = reference_inventory(results)
    summary = dict(status='BLOCKED' if missing or changed or any(r['status']!='NUMERIC_PARITY_VERIFIED' for r in matrix)
                   or any(r['status']=='FAIL' for r in serial) else 'VERIFIED',
        generated_at=datetime.now(timezone.utc).isoformat(), inventory_rows=len(inv),
        years=list(YEARS), official_2026_pdf_checks=fetch_checks,
        database_unique_codes=len(db_codes), hunt_master_unique_codes=len(hm_codes), hunt_master=rel(master) if master else None,
        current_code_canonical_under_review=rel(master),
        database_not_in_active_canonical=sorted(db_codes-hm_codes),
        explicitly_retired_or_inactive_codes=sorted(excluded_canonical_rows),
        current_code_draw_overlap_basis='ACTIVE_HUNT_MASTER_CANONICAL_INTERSECT_SOURCE_DRAW_CODES',
        pdf_files=len(serial), unique_pdf_hashes=len(cache), unreadable_or_integrity_failures=sum(r['status']=='FAIL' for r in serial),
        canonical_sources=len(source_reviews), verified_sources=sum(r['status']=='NUMERIC_PARITY_VERIFIED' for r in source_reviews),
        matched_canonical_rows=sum(r['matched_rows'] for r in source_reviews), compared_cells=sum(r['cells_compared'] for r in source_reviews),
        difference_counts=dict(Counter(r['status'] for r in differences)), missing=missing,
        matrix_status_counts=dict(Counter(r['status'] for r in matrix)), protected_hashes=frozen,
        protected_files_changed=sorted(changed),
        inventory_manifest_reconciliation=reference_summary,
        limitations=['Current hunt-master canonical is audited against official evidence; DATABASE does not supply its code list.',
                    'Historical draw truth retains year-correct source rows independently of current-hunt eligibility.',
                    'Unsupported table layouts remain unverified, never passed.',
                    'Missing yearly scopes require official publication/program review; no fabricated universal file count.',
                    'Point-purchase/reference PDFs are inspected but are not hunt-level draw truth.',
                    'This audit changes no engine, truth, or certification status.'])
    write_csv(out/(name+'_files.csv'), serial)
    write_csv(out/(name+'_canonical_sources.csv'), source_reviews)
    write_csv(out/(name+'_cell_differences.csv'), differences)
    write_csv(out/(name+'_scope_matrix.csv'), matrix)
    write_csv(out/(name+'_manifest_references.csv'), reference_checks)
    (out/(name+'.json')).write_text(json.dumps({'summary':summary,'files':serial,'sources':source_reviews,'scope_matrix':matrix}, indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='protected_hashes'},indent=2))
    return 0 if summary['status']=='VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
