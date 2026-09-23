"""Audit 2026 endpoint counts, PDF cells and missing outcome probabilities.

Read-only with respect to truth, engines, forecasts and runtime. A generated
PDF is a presentation check, not independent official-source authentication.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as source
from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer

CANONICAL = ROOT / 'data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2026_for_2027_canonical_yearly_draw_results.csv'
RAW = ROOT / 'pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902/utahdraws_2026/json'
PDF = ROOT / 'pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/official_dwr_online_results/uoga_styled_approved_white_cream_topo_youth_residency_fixed_20260902/2026_uoga_big_game_draw_results.pdf'


def missing_zero_outcome(row, parity):
    """Only exact source-backed positive applicant / zero award observations."""
    apps = source.decimal(row.get('eligible_applicants'))
    awards = source.decimal(row.get('total_permits'))
    probability = scorer.actual_probability_and_counts(row, row.get('residency', ''))[0]
    return (parity == 'ENDPOINT_POPULATED_FIELDS_MATCH' and apps is not None
            and apps > 0 and awards == 0 and probability is None
            and 'point' in row.get('record_type', '').lower())


def write_rows(path, rows, fields):
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def inspect_pdf(rows):
    import pdfplumber
    checks = []
    with pdfplumber.open(PDF) as doc:
        # Complete pages visually reviewed, covering LE and OIL; not an all-PDF claim.
        for page_number, code in ((237, 'DB1016'), (761, 'MB6011'), (762, 'MB6011')):
            page = doc.pages[page_number - 1]
            if not re.search(r'Hunt:\s+' + code + r'\b', page.extract_text() or ''):
                raise ValueError(f'Unexpected PDF layout/identity on page {page_number}')
            tables = [t.extract() for t in page.find_tables()]
            found = set()
            for table in tables:
                if not table or len(table[0]) != 6:
                    continue
                lane = {'Resident Applicants': 'Resident', 'Nonresident Applicants': 'Nonresident'}.get(table[0][0])
                if not lane:
                    continue
                found.add(lane)
                expected_headers = ['Points', 'Eligible', 'Max / Bonus', 'Regular', 'Total', 'Success Ratio']
                if [' '.join((v or '').split()) for v in table[1]] != expected_headers:
                    raise ValueError(f'Unexpected column contract: {page_number}/{lane}')
                for cells in table[2:]:
                    if not (cells[0] or '').isdigit():
                        continue
                    point = cells[0]
                    hits = [r for r in rows if r['hunt_code'] == code and r['residency'] == lane
                            and r['points'] == point and r['source_is_youth'] == 'false']
                    values = cells[1:5]
                    status = 'EMPTY_DISPLAY_NOT_A_ZERO_OBSERVATION'
                    if any(v not in ('', None) for v in values):
                        if len(hits) != 1:
                            status = 'CANONICAL_IDENTITY_MISSING_OR_AMBIGUOUS'
                        else:
                            numeric = [source.decimal(hits[0].get(k)) for k in
                                       ('eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits')]
                            status = 'FOUR_COUNT_CELLS_MATCH' if numeric == [source.decimal(v) for v in values] else 'VALUE_MISMATCH'
                    checks.append(dict(page=page_number, hunt_code=code, residency=lane, points=point,
                                       eligible=cells[1], bonus=cells[2], regular=cells[3], total=cells[4],
                                       printed_success_ratio=cells[5], status=status))
            if found != {'Resident', 'Nonresident'}:
                raise ValueError(f'Missing residency table on page {page_number}')
        return checks, len(doc.pages)


def main(out, raw_dir=RAW, inspect_pdf_sample=True):
    if out.exists():
        raise ValueError('Use a new directory; earlier evidence must remain intact')
    out.mkdir(parents=True)
    inputs = [CANONICAL, Path(__file__), Path(scorer.__file__), Path(source.__file__)]
    if inspect_pdf_sample:
        inputs.append(PDF)
    hashes = {source.rel(p): source.sha(p) for p in inputs}
    rows = source.read_csv(CANONICAL)
    index, evidence, groups = {}, [], Counter()
    for line, row in enumerate(rows, 2):
        item = dict(canonical_csv_line=line, hunt_code=row['hunt_code'], residency=row.get('residency', ''),
                    points=row.get('points', ''), source_is_youth=row.get('source_is_youth', ''),
                    scope=row.get('source_scope', ''), family=scorer.family_from_actual(row),
                    eligible=row.get('eligible_applicants', ''), bonus=row.get('bonus_permits', ''),
                    regular=row.get('regular_permits', ''), awards=row.get('total_permits', ''),
                    canonical_p_draw=row.get('p_draw', ''), endpoint='', endpoint_sha256='',
                    parity='', compared_cells=0, missing_zero_outcome=False, probability_difference='', error='')
        try:
            name = source.pdf_endpoint(row) if row.get('source_dataset') == 'OFFICIAL_DWR_2026_PDF_DRAW_RESULTS' else source.live_endpoint(row)
            path = raw_dir / name
            if path not in index:
                index[path] = source.raw_endpoint_index(path)
                hashes[source.rel(path)] = source.sha(path)
            parity, cells = source.endpoint_parity(row, index[path])
            item.update(endpoint=source.rel(path), endpoint_sha256=hashes[source.rel(path)], parity=parity, compared_cells=cells)
            item['missing_zero_outcome'] = missing_zero_outcome(row, parity)
            p = scorer.actual_probability_and_counts(row, row.get('residency', ''))[0]
            apps, awards = source.decimal(item['eligible']), source.decimal(item['awards'])
            if parity == 'ENDPOINT_POPULATED_FIELDS_MATCH' and p is not None and apps and apps > 0 and awards is not None:
                delta = abs(Decimal(str(p)) - awards / apps)
                if delta > Decimal('0.0000001'):
                    item['probability_difference'] = str(delta)
        except (KeyError, ValueError, OSError, TypeError) as exc:
            item.update(parity='UNRESOLVED_OR_REFERENCE_SCOPE', error=f'{type(exc).__name__}: {exc}')
        evidence.append(item)
        if item['missing_zero_outcome']:
            groups[item['family']] += 1
    checks, pages = inspect_pdf(rows) if inspect_pdf_sample else ([], None)
    changed = [p for p, h in hashes.items() if source.sha(source.local(p)) != h]
    summary = dict(canonical_rows=len(rows), endpoint_parity=dict(Counter(r['parity'] for r in evidence)),
                   compared_cells=sum(r['compared_cells'] for r in evidence),
                   source_verified_missing_zero_outcomes=sum(groups.values()), missing_zero_by_family=dict(groups),
                   populated_probability_mismatches=sum(bool(r['probability_difference']) for r in evidence),
                   pdf_pages=pages, pdf_checked_pages=sorted({r['page'] for r in checks}),
                   pdf_status_counts=dict(Counter(r['status'] for r in checks)),
                   inputs_changed=changed, input_hashes=hashes, truth_or_forecast_changed=False,
                   endpoint_directory=source.rel(raw_dir),
                   scope='2026 exact endpoint count comparison. No forecast, scoring promotion or certification. PDF sample included only when explicitly enabled.',
                   limitation='Unresolved identity/pool rows remain unverified. If included, the PDF reproduction shares upstream UtahDraws data and its sample does not establish complete document parity.')
    write_rows(out / 'canonical_endpoint_probability_review.csv', evidence, list(evidence[0]))
    if checks:
        write_rows(out / 'pdf_cell_review.csv', checks, list(checks[0]))
    source.write_json(out / 'summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k != 'input_hashes'}, indent=2))
    return 1 if changed else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--raw-dir', type=Path, default=RAW)
    parser.add_argument('--skip-pdf-sample', action='store_true', help='Compare official endpoint records only; do not open UOGA PDFs.')
    args = parser.parse_args()
    raise SystemExit(main(args.output_dir.resolve(), args.raw_dir.resolve(), not args.skip_pdf_sample))
