"""Read-only numeric comparison for the official multi-hunt Sportsman layout.

These are applicant/outcome columns, not bonus-point ladders. No code aliasing,
forecast generation, or canonical mutation occurs here.
"""
import re
from decimal import Decimal, InvalidOperation

import pymupdf

from engine.utah.quality.verify_all_failing_engines_pdfs import visible_lines

CELL = r'(?:[\d,]+|N/A)'
RATIO = r'(?:1\s+in\s+[\d,.]+|N/A)'
ROW = re.compile(r'^(?P<code>[A-Z]{2}\d{4})\s+.+?\s+'
                 + r'\s+'.join(f'(?P<c{i}>{CELL})' for i in range(8))
                 + rf'\s+(?P<rr>{RATIO})\s+(?P<nr>{RATIO})$')
TOTAL = re.compile(r'^(?:Grand Totals\s*\.*|Total)\s+'
                   + r'\s+'.join(f'(?P<c{i}>{CELL})' for i in range(8)) + r'$')


def number(value):
    try:
        return Decimal(str(value).replace(',', '').strip())
    except InvalidOperation:
        return None


def parse_sportsman_lines(lines):
    header = ' '.join(lines)
    if not all(word in header for word in ('Sportsman', 'Successful', 'Resident', 'Quota')):
        raise ValueError('Not an official Sportsman outcome table layout')
    rows, totals = {}, []
    for line in lines:
        match = ROW.fullmatch(line)
        if match:
            code = match['code']
            if code in rows:
                raise ValueError(f'Duplicate Sportsman source code: {code}')
            cells = [match[f'c{i}'] for i in range(8)]
            # Published N/A is retained. Zero is used ONLY to reconcile totals
            # for the explicitly nonparticipating NR columns, never as odds.
            values = [number(c) for c in cells]
            if any(values[i] is None for i in (0, 2, 4, 5, 7)):
                raise ValueError(f'Missing resident source outcome: {code}')
            if any(values[i] not in (None, 0) for i in (1, 3, 6)) or match['nr'] != 'N/A':
                raise ValueError(f'Unexpected participating NR Sportsman layout: {code}')
            if values[0] + values[2] != values[4] or values[5] != values[7]:
                raise ValueError(f'Sportsman source arithmetic conflict: {code}')
            rows[code] = dict(cells=cells, resident_success_ratio=match['rr'],
                              nonresident_success_ratio=match['nr'], source_text=line)
        else:
            total = TOTAL.fullmatch(line)
            if total:
                totals.append([total[f'c{i}'] for i in range(8)])
            elif re.match(r'^[A-Z]{2}\d{4}\b', line):
                raise ValueError(f'Unparsed Sportsman source row: {line}')
    if not rows or len(totals) != 1:
        raise ValueError('Missing rows or ambiguous Sportsman grand total')
    for i, total in enumerate(totals[0]):
        if sum(number(r['cells'][i]) or 0 for r in rows.values()) != (number(total) or 0):
            raise ValueError(f'Sportsman grand total mismatch, column {i}')
    return rows


def read_sportsman_page(path, page_number):
    with pymupdf.open(path) as pdf:
        return parse_sportsman_lines(visible_lines(pdf[page_number - 1]))


def compare_sportsman_row(row, source):
    """Return cell evidence; missing source metrics never become a passing zero."""
    c = [number(v) for v in source['cells']]
    expected = {
        'resident_eligible_applicants': c[0] + c[2], 'resident_total_permits': c[0],
        'resident_successful_applicants': c[0], 'resident_unsuccessful_applicants': c[2],
        'eligible_applicants': c[4], 'successful_applicants': c[0],
        'unsuccessful_applicants': c[2], 'total_eligible_applicants': c[4],
        'total_permits': c[0],
    }
    # The source is explicitly Sportsman random-only; components in older
    # canonicals are derived normalizations, not printed bonus columns.
    for prefix in ('', 'resident_', 'total_'):
        expected[prefix + 'bonus_permits'] = Decimal(0)
        expected[prefix + 'regular_permits'] = c[0]
    for field in ('eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits',
                  'p_draw', 'p_draw_percent'):
        expected['nonresident_' + field] = Decimal(0)
    probability = c[0] / c[4] if c[4] else None
    for prefix in ('', 'resident_', 'total_'):
        expected[prefix + 'p_draw'] = probability
        expected[prefix + 'p_draw_percent'] = probability * 100 if probability is not None else None
    evidence = []
    for field, value in expected.items():
        if row.get(field, '') == '':
            continue
        actual = number(row[field])
        tolerance = Decimal('0.000000005') if 'p_draw' in field else Decimal(0)
        ok = value is not None and actual is not None and abs(actual - value) <= tolerance
        basis = ('NONPARTICIPATING_NR_NORMALIZATION_NOT_ODDS' if field.startswith('nonresident_')
                 else 'RANDOM_ONLY_COMPONENT_NORMALIZATION' if 'bonus_' in field or 'regular_' in field
                 else 'COUNT_DERIVED_PROBABILITY' if 'p_draw' in field else 'PRINTED_OUTCOME_COUNTS')
        evidence.append(dict(field=field, canonical=row[field], source=str(value), basis=basis,
                             status='MATCH' if ok else 'VALUE_MISMATCH'))
    for field in ('resident_success_ratio', 'nonresident_success_ratio', 'success_ratio'):
        if row.get(field, '') == '':
            continue
        expected_ratio = source['nonresident_success_ratio' if field.startswith('nonresident_') else 'resident_success_ratio']
        normalize = lambda v: re.sub(r'[\s,]', '', v).lower()
        evidence.append(dict(field=field, canonical=row[field], source=expected_ratio,
                             basis='PRINTED_RATIO_WHITESPACE_COMMA_NORMALIZATION',
                             status='MATCH' if normalize(row[field]) == normalize(expected_ratio) else 'VALUE_MISMATCH'))
    required = all(row.get(f, '') != '' for f in ('eligible_applicants', 'successful_applicants'))
    return required and bool(evidence) and all(e['status'] == 'MATCH' for e in evidence), evidence
