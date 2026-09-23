"""Read-only annual report inventory against freshly retained official indexes.

Remote PDFs are hashed in memory, never installed into RAW. A byte match proves
source identity, not numeric canonical parity or a successful prediction feed.
Cougar season headings and printed draw years remain distinct dimensions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pymupdf
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'pipeline/RAW/hunt_unit_database'
INDEXES = ('https://wildlife.utah.gov/biggame/odds', 'https://wildlife.utah.gov/odds')
YEARS = range(2017, 2027)
DRAW_TITLE = re.compile(r'\b(20\d{2})\s+Draws?\s+(?:\d+|R|T)\b', re.I)
REPORT_TITLE = re.compile(r'\b(20\d{2})\s+(?:Sportsman|Black Bear|Cougar|Turkey)\s+(?:Odds|Draw)', re.I)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class ReportIndex(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.headings, self.rows = url, {}, []
        self.capture, self.parts, self.href = None, [], ''

    def handle_starttag(self, tag, attrs):
        if tag in ('h2', 'h3', 'h4', 'a'):
            self.capture, self.parts = tag, []
            self.href = dict(attrs).get('href', '')

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != self.capture:
            return
        text = ' '.join(' '.join(self.parts).split())
        if tag.startswith('h'):
            level = int(tag[1])
            self.headings = {k: v for k, v in self.headings.items() if k < level}
            self.headings[level] = text
        elif urlsplit(self.href).path.lower().endswith('.pdf'):
            if '/biggame/' in self.url:
                family, period = 'Big game', self.headings.get(2, '')
            else:
                family, period = self.headings.get(2, ''), self.headings.get(3, '')
            if family not in ('Big game', 'Black bear', 'Cougar', 'Wild turkey'):
                self.capture = None
                return
            m = re.fullmatch(r'(20\d{2})(?:-(\d{2}))?', period)
            if m:
                # Scope year for a season-range header is the ending season year,
                # NOT a claim that the drawing took place in that calendar year.
                year = int('20' + m[2]) if m[2] else int(m[1])
                if year in YEARS:
                    self.rows.append(dict(index_url=self.url, family=family,
                        index_period=period, scope_year=year, label=text,
                        section=self.headings.get(3, ''), url=urljoin(self.url, self.href)))
        self.capture = None


def unique_reports(rows):
    return list({(r['scope_year'], r['url']): r for r in rows}.values())


def fetch_hash(row):
    result = dict(row)
    try:
        response = requests.get(row['url'], timeout=(15, 90))
        response.raise_for_status()
        data = response.content
        if not data.lstrip().startswith(b'%PDF-'):
            raise ValueError('Response is not a PDF')
        result.update(remote_sha256=hashlib.sha256(data).hexdigest(),
                      remote_size_bytes=len(data), fetch_error='')
    except Exception as exc:
        result.update(remote_sha256='', fetch_error=f'{type(exc).__name__}: {exc}')
    return result


def inspect_titles(path):
    try:
        with pymupdf.open(path) as doc:
            evidence = []
            for i in range(min(3, len(doc))):
                text = doc[i].get_text()
                draws = sorted(set(DRAW_TITLE.findall(text)))
                reports = sorted(set(REPORT_TITLE.findall(text)))
                if draws or reports:
                    evidence.append(dict(page=i+1, draw_years=draws, report_years=reports))
            return dict(pages=len(doc), title_evidence=evidence, error='')
    except Exception as exc:
        return dict(pages=None, title_evidence=[], error=f'{type(exc).__name__}: {exc}')


def text_fingerprint(doc):
    return [hashlib.sha256(page.get_text().encode('utf-8')).hexdigest() for page in doc]


def review_variants(files, checked):
    """Compare unrecognized local versions without equating text to cell parity."""
    known = {r['remote_sha256'] for r in checked if r['remote_sha256']}
    reports = {Path(urlsplit(r['url']).path).name.lower(): r for r in checked}
    reviews, seen = [], set()
    for local in files:
        if local['category'] != 'draw_odds' or local['folder_year'] == 2026:
            continue
        if local['sha256'] in known or local['sha256'] in seen:
            continue
        seen.add(local['sha256'])
        report = reports.get(Path(local['path']).name.lower())
        item = dict(local_path=local['path'], local_sha256=local['sha256'])
        if not report:
            item['status'] = 'NOT_LISTED_IN_SELECTED_FAMILY_INDEXES'
        else:
            item.update(official_url=report['url'], official_sha256=report['remote_sha256'])
            try:
                response = requests.get(report['url'], timeout=(15, 90))
                response.raise_for_status()
                if hashlib.sha256(response.content).hexdigest() != report['remote_sha256']:
                    raise ValueError('Official source changed during audit')
                with pymupdf.open(stream=response.content, filetype='pdf') as remote, pymupdf.open(ROOT/local['path']) as retained:
                    a, b = text_fingerprint(remote), text_fingerprint(retained)
                item.update(official_page_text_hashes=a, local_page_text_hashes=b,
                    official_pages=len(a), local_pages=len(b),
                    status='ALL_PAGE_TEXT_MATCH_BYTES_DIFFER' if a == b else 'PAGE_TEXT_DIFFERS_REQUIRES_REVIEW')
            except Exception as exc:
                item.update(status='VARIANT_REVIEW_UNRESOLVED', error=f'{type(exc).__name__}: {exc}')
        item['numeric_canonical_parity_proven'] = False
        reviews.append(item)
    return reviews


def antlerless_profile(path):
    grouped = defaultdict(Counter)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            source = row.get('source_file', '')
            if not any(name in source for name in (
                    '25_antlerless_drawing_odds_report.pdf',
                    '25_youth_antlerless_drawing_odds_report.pdf')):
                continue
            stats = grouped[source]
            stats['rows'] += 1
            stats['actual_year_' + row.get('actual_draw_year', '')] += 1
            stats[row.get('record_type', 'unknown')] += 1
            if row.get('record_type') == 'point_level_draw_result':
                for lane in ('resident', 'nonresident'):
                    cells = [row.get(f'{lane}_{field}', '') for field in (
                        'eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits')]
                    stats[lane + '_point_rows_with_complete_counts'] += all(v != '' for v in cells)
                    stats[lane + '_positive_applicant_point_rows'] += bool(cells[0] and float(cells[0]) > 0)
    return {k: dict(v) for k, v in grouped.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.relative_to(ROOT / 'audit_output_real_final')
    out.mkdir(parents=True, exist_ok=False)
    truth = ROOT / 'data_truth/draw_results_truth/normalized'
    protected = list((truth / 'canonical_yearly').glob('*.csv')) + [truth / 'draw_results_long.csv']
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in protected}
    files, by_hash, title_cache = [], defaultdict(list), {}
    for path in sorted(RAW.glob('20*/pdf/**/*.pdf')):
        year = int(path.relative_to(RAW).parts[0])
        if year not in YEARS:
            continue
        digest = sha(path)
        item = dict(path=path.relative_to(ROOT).as_posix(), folder_year=year,
                    sha256=digest, size_bytes=path.stat().st_size,
                    category=path.relative_to(RAW).parts[2])
        if item['category'] == 'draw_odds':
            if digest not in title_cache:
                title_cache[digest] = inspect_titles(path)
            item.update(title_cache[digest])
        files.append(item)
        by_hash[digest].append(item['path'])
    print(f'Inventoried {len(files)} PDF paths / {len(by_hash)} unique hashes.', flush=True)
    indexes, links = [], []
    for i, url in enumerate(INDEXES):
        response = requests.get(url, timeout=(15, 60))
        response.raise_for_status()
        (out / f'official_index_{i}.html').write_bytes(response.content)
        index = ReportIndex(url)
        index.feed(response.text)
        links.extend(index.rows)
        indexes.append(dict(url=url, sha256=hashlib.sha256(response.content).hexdigest()))
    reports = unique_reports(links)
    print(f'Hash-checking {len(reports)} unique official PDF links against local sources.', flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(fetch_hash, reports))
    for row in checked:
        row['matching_pipeline_paths'] = by_hash.get(row['remote_sha256'], [])
        row['status'] = ('OFFICIAL_FETCH_UNRESOLVED' if row['fetch_error'] else
                         'EXACT_BYTES_RETAINED' if row['matching_pipeline_paths'] else
                         'OFFICIAL_BYTES_NOT_FOUND_IN_PIPELINE')
        row['numeric_canonical_parity_proven'] = False
    variants = review_variants(files, checked)
    annual = []
    for year in YEARS:
        local = [r for r in files if r['folder_year'] == year]
        draw = [r for r in local if r['category'] == 'draw_odds']
        published = [r for r in checked if r['scope_year'] == year]
        annual.append(dict(year=year, all_pdf_paths=len(local), draw_pdf_paths=len(draw),
            distinct_draw_hashes=len({r['sha256'] for r in draw}),
            official_index_unique_links=len(published),
            official_statuses=dict(Counter(r['status'] for r in published)),
            official_families=dict(Counter(r['family'] for r in published))))
    canonical = truth / 'canonical_yearly/draw_results_2025_for_2026_canonical_yearly_draw_results.csv'
    profiles = {p.name: antlerless_profile(p) for p in (canonical, truth/'draw_results_long.csv')}
    stale = []
    removed = 'pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/2024 antlerless draw results.pdf'
    for directory in ('scripts', 'engine'):
        for path in (ROOT/directory).rglob('*.py'):
            if path.resolve() == Path(__file__).resolve():
                continue
            for line, text in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                if removed in text.replace('\\', '/'):
                    stale.append(dict(path=path.relative_to(ROOT).as_posix(), line=line))
    changed = [p for p, digest in before.items() if sha(ROOT/p) != digest]
    changed_raw = [r['path'] for r in files if not (ROOT/r['path']).exists() or sha(ROOT/r['path']) != r['sha256']]
    result = dict(scope='ANNUAL_SOURCE_IDENTITY_AND_FEED_INVENTORY_NOT_CELL_PARITY_OR_CERTIFICATION',
        audited_at=datetime.now(timezone.utc).isoformat(), official_indexes=indexes,
        annual=annual, official_reports=checked, pipeline_files=files,
        source_variant_reviews=variants,
        antlerless_2025_profiles=profiles, stale_removed_path_references=stale,
        removed_2024_copy_still_exists=(ROOT/removed).exists(),
        protected_truth_hashes=before, changed_truth=changed, changed_raw=changed_raw,
        limitations=['Official index omission does not prove a draw program ended.',
            '2026 UtahDraws endpoint packages are not required to have independently authored DWR PDFs.',
            'Cougar season-range scope year differs from printed draw year; retain both.',
            'Combined and split publications, point purchases and duplicate copies are not independent hunt ladders.',
            'Printed titles examined on first three pages only; unknown titles remain unverified.',
            'No sources, canonicals, forecast outputs or runtime artifacts were changed.'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(annual=annual, antlerless_2025_profiles=profiles,
        stale_removed_path_references=stale, changed_truth=changed, changed_raw=changed_raw), indent=2))
    return int(bool(changed or changed_raw or any(r['status'] != 'EXACT_BYTES_RETAINED' for r in checked)))


if __name__ == '__main__':
    raise SystemExit(main())
