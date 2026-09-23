"""Independently compare printed antlerless cells to retained canonical cells.

Read-only inputs. Uses pdfplumber text, independent of the canonical's recorded
PYMUPDF_FIND_TABLES extraction. Never imports the canonical-building extractor.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / 'pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf'
CANONICAL = ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2024_for_2025_canonical_yearly_draw_results.csv'
PARENT = 'official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf'
METRICS = ('eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits', 'success_ratio')
LANE = r'(Totals|\d+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(N/A|1 in [\d,.]+)'
ROW = re.compile(r'^' + LANE + r'\s+' + LANE + r'$')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_line(line):
    match = ROW.fullmatch(line.strip())
    if not match:
        return None
    cells = match.groups()
    if cells[0] != cells[6]:
        raise ValueError('Resident/nonresident point alignment differs: ' + line)
    result = {'points': '' if cells[0] == 'Totals' else cells[0],
              'record_type': 'hunt_total_draw_result' if cells[0] == 'Totals' else 'point_level_draw_result'}
    for offset, lane in ((0, 'resident'), (6, 'nonresident')):
        for i, metric in enumerate(METRICS, start=1):
            value = cells[offset+i]
            result[f'{lane}_{metric}'] = value if metric == 'success_ratio' else int(value.replace(',', ''))
    return result


def comparison_status(canonical_row, lane, metric, pdf_value, canonical_value):
    """Explain approved display-only differences without hiding numeric drift."""
    if pdf_value == canonical_value:
        return 'MATCH'
    if metric == 'success_ratio' and re.sub(r'\s+', '', str(pdf_value)) == re.sub(r'\s+', '', str(canonical_value)):
        return 'RATIO_WHITESPACE_ONLY'
    marker = f'OFFICIAL_SOURCE_TOP_POINT_TOTAL_RATIO_CARRYOVER:{lane}:points=15:'
    note = canonical_row.get('qa_notes', '')
    if (canonical_row.get('record_type') == 'point_level_draw_result'
            and canonical_row.get('points') == '15'
            and marker in note
            and all(canonical_row.get(f'{lane}_{field}') == '0'
                    for field in ('eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits'))):
        printed = note.split(marker, 1)[1].split('|', 1)[0]
        match = re.search(r'displayed_total_permits=(\d+):displayed_success_ratio=([^:\s]+)', printed)
        if match:
            if metric == 'total_permits' and str(pdf_value) == match.group(1) and canonical_value == 0:
                return 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'
            if (metric == 'success_ratio' and canonical_value == 'N/A'
                    and re.sub(r'\s+', '', str(pdf_value)) == match.group(2)):
                return 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'
    return 'VALUE_MISMATCH'


def write_csv(path, rows, empty_fields=()):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(empty_fields)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--canonical', type=Path)
    parser.add_argument('--parent')
    parser.add_argument('--actual-year', type=int)
    parser.add_argument('--official-index-audit', type=Path)
    args = parser.parse_args()
    explicit = (args.pdf, args.canonical, args.parent, args.actual_year, args.official_index_audit)
    if any(x is not None for x in explicit) and not all(x is not None for x in explicit):
        parser.error('Explicit source mode requires PDF, canonical, parent, actual year and official index audit together')
    pdf = args.pdf or PDF
    canonical_path = args.canonical or CANONICAL
    parent = args.parent or PARENT
    actual_year = args.actual_year or 2024
    out = args.out_dir.resolve()
    if not any(out.is_relative_to(ROOT / name) for name in ('audit_output_phase1_candidate', 'audit_output_real_final')):
        parser.error('Output must be inside a separate audit directory')
    out.mkdir(parents=True, exist_ok=False)
    issues, extracted, pages = [], [], []
    if args.pdf:
        receipt = json.loads(args.official_index_audit.read_text(encoding='utf-8'))
        verified = [r for r in receipt['official_reports'] if r['scope_year'] == actual_year
                    and r['remote_sha256'] == sha(pdf) and not r['fetch_error']]
        if not verified:
            issues.append({'status': 'NO_EXACT_OFFICIAL_SOURCE_HASH_FOR_YEAR'})
        inputs = (pdf, canonical_path, args.official_index_audit, Path(__file__))
    else:
        spec = importlib.util.spec_from_file_location('resolver_signature_audit', ROOT/'scripts/resolve-antlerless-hunt-codes-2026.py')
        resolver = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = resolver
        spec.loader.exec_module(resolver)
        inputs = (pdf, canonical_path, Path(resolver.__file__))
    hashes = {str(p.resolve().relative_to(ROOT)): sha(p) for p in inputs}
    with pdfplumber.open(pdf) as doc:
        if not args.pdf and (sha(pdf), pdf.stat().st_size, len(doc.pages)) != (resolver.EXPECTED_SHA256, resolver.EXPECTED_SIZE_BYTES, resolver.EXPECTED_PAGES):
            issues.append({'status': 'PDF_SIGNATURE_MISMATCH'})
        for page_number, page in enumerate(doc.pages, 1):
            text = page.extract_text() or ''
            hunts = re.findall(r'^Hunt:\s+([A-Z]{2}\d{4})\s+(.+)$', text, re.M)
            if not hunts:
                role = 'SPECIES_SUMMARY_NOT_HUNT_TRUTH' if 'Species:' in text else 'UNRECOGNIZED_PAGE'
                pages.append(dict(pdf_page=page_number, role=role, parsed_rows=0))
                if role == 'UNRECOGNIZED_PAGE':
                    issues.append(dict(status=role, pdf_page=page_number))
                continue
            if len(hunts) != 1:
                raise ValueError(f'Ambiguous hunt page: {page_number}')
            code, name = hunts[0]
            if args.pdf and set(re.findall(r'\b(20\d{2})\s+Draw\s+7\b', text)) != {str(actual_year)}:
                issues.append(dict(status='HUNT_PAGE_DRAW_YEAR_UNVERIFIED', pdf_page=page_number))
            count = 0
            for line_number, line in enumerate(text.splitlines(), 1):
                row = parse_line(line)
                if row is not None:
                    extracted.append(dict(hunt_code=code, hunt_name=name, pdf_page=page_number,
                        text_line=line_number, raw_pdf_line=line, **row))
                    count += 1
                elif re.match(r'^(?:\d+|Totals)\s+(?:\d+|N/A)\s', line):
                    issues.append(dict(status='UNPARSED_NUMERIC_LINE', pdf_page=page_number, line=line))
            pages.append(dict(pdf_page=page_number, hunt_code=code, role='HUNT_TABLE', parsed_rows=count))
            if not count:
                issues.append(dict(status='EMPTY_HUNT_TABLE', pdf_page=page_number))
    with canonical_path.open(encoding='utf-8-sig', newline='') as handle:
        canonical = [r for r in csv.DictReader(handle) if r['source_file'] == parent]
    if any(r['actual_draw_year'] != str(actual_year) for r in canonical):
        issues.append(dict(status='CANONICAL_DRAW_YEAR_MISMATCH'))
    key = lambda r: (r['hunt_code'], r['record_type'], r['points'])
    indexed = defaultdict(list)
    for row in canonical:
        indexed[key(row)].append(row)
    comparisons, matched, seen = [], 0, Counter()
    for row in extracted:
        k = key(row)
        seen[k] += 1
        matches = indexed.get(k, [])
        if len(matches) != 1:
            issues.append(dict(status='MISSING_OR_DUPLICATE_CANONICAL_KEY', key=str(k), count=len(matches)))
            continue
        canonical_row = matches[0]
        matched += 1
        if canonical_row['pdf_page'] != str(row['pdf_page']):
            issues.append(dict(status='PAGE_LINEAGE_MISMATCH', key=str(k), pdf_page=row['pdf_page'], canonical_page=canonical_row['pdf_page']))
        for lane in ('resident', 'nonresident'):
            for metric in METRICS:
                field = f'{lane}_{metric}'
                raw = canonical_row.get(field, '')
                expected = row[field]
                try:
                    actual = raw.strip() if metric == 'success_ratio' else int(raw.replace(',', ''))
                except (ValueError, AttributeError):
                    actual = None
                status = comparison_status(canonical_row, lane, metric, expected, actual)
                comparisons.append(dict(hunt_code=row['hunt_code'], record_type=row['record_type'],
                    points=row['points'], pdf_page=row['pdf_page'], text_line=row['text_line'],
                    field=field, pdf_value=expected, canonical_value=raw,
                    status=status))
    for k, values in indexed.items():
        if not seen[k]:
            issues.append(dict(status='CANONICAL_ROW_NOT_IN_PDF', key=str(k)))
    for k, count in seen.items():
        if count != 1:
            issues.append(dict(status='DUPLICATE_PDF_KEY', key=str(k), count=count))
    documented = [r for r in comparisons if r['status'] in
                  ('RATIO_WHITESPACE_ONLY', 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER')]
    mismatches = [r for r in comparisons if r['status'] == 'VALUE_MISMATCH']
    unchanged = all(sha(ROOT/p) == h for p, h in hashes.items())
    passed = bool(extracted and not issues and not mismatches and unchanged)
    summary = dict(status=('PASS_WITH_DOCUMENTED_NORMALIZATIONS' if documented else 'PASS') if passed else 'BLOCKED',
        scope=f'Entire retained {actual_year} antlerless report: {parent}; no other source scopes',
        source_hashes=hashes, source_size=pdf.stat().st_size, physical_pages=len(pages),
        page_roles=dict(Counter(r['role'] for r in pages)), hunts=len({r['hunt_code'] for r in extracted}),
        canonical_rows=len(canonical), extracted_rows=len(extracted), matched_rows=matched,
        numeric_cells=sum(r['field'].endswith(METRICS[:-1]) for r in comparisons),
        ratio_cells=sum(r['field'].endswith('success_ratio') for r in comparisons),
        mismatched_cells=len(mismatches), documented_normalization_cells=len(documented),
        documented_normalization_types=dict(Counter(r['status'] for r in documented)),
        issues=issues, input_hashes_unchanged=unchanged,
        parser='Independent pdfplumber linear text; canonical used PYMUPDF_FIND_TABLES')
    write_csv(out/'pdf_extracted_rows.csv', extracted)
    write_csv(out/'cell_comparisons.csv', comparisons)
    write_csv(out/'documented_normalizations.csv', documented,
              ['hunt_code', 'field', 'pdf_value', 'canonical_value', 'status'])
    write_csv(out/'cell_mismatches.csv', mismatches, ['hunt_code', 'field', 'pdf_value', 'canonical_value'])
    write_csv(out/'page_coverage.csv', pages)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
