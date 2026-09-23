from pathlib import Path

import pymupdf

from engine.utah.quality.verify_all_failing_engines_pdfs import (
    ROOT, YEARS, check_inventory, compare_row, inspect_pdf, visible_lines,
    difference_record, compare_endpoint_rows,
)
from scripts.audit_antlerless_pdf_canonical_cells import parse_line


def test_repository_root_is_not_engine_directory():
    assert (ROOT/'AGENTS.MD').is_file()
    assert (ROOT/'pipeline').is_dir()
    assert list(YEARS) == list(range(2017, 2027))


def test_difference_report_keeps_document_and_cell_separate():
    result = difference_record(2020, 'ANTLERLESS', 'actual.pdf', ('EA1121', '15'),
                               dict(source=1, canonical='0', status='VALUE_MISMATCH'))
    assert result['source_file'] == 'actual.pdf'
    assert result['source'] == 1


def test_endpoint_parity_reads_raw_json_and_preserves_zero_and_youth(tmp_path):
    import json
    csv_path = tmp_path/'csv'/'endpoint.csv'
    raw = tmp_path/'json'/'endpoint.json'
    raw.parent.mkdir()
    raw.write_text(json.dumps({'Data':[{'HuntCode':'EA1000', 'OddsList':[
        {'ResidencyTypeID':1, 'Point':2.0, 'IsYouth':False, 'ParticipantCount':10,
         'SuccessfulCount':3, 'SuccessfulByMaxPointRoundCount':3, 'SuccessfulByRegularRoundCount':0},
        {'ResidencyTypeID':1, 'Point':2.0, 'IsYouth':True, 'ParticipantCount':5,
         'SuccessfulCount':2, 'SuccessfulByMaxPointRoundCount':2, 'SuccessfulByRegularRoundCount':0}]}]}))
    row = dict(hunt_code='EA1000', residency='Resident', points='2', source_is_youth='false',
               eligible_applicants='10', total_permits='3', bonus_permits='3', regular_permits='0', successful_applicants='3')
    assert compare_endpoint_rows([row], csv_path)['status'] == 'NUMERIC_PARITY_VERIFIED'
    row['regular_permits'] = '3'
    result = compare_endpoint_rows([row], csv_path)
    assert result['status'] == 'BLOCKED'
    assert result['issues'][0]['source'] == 0


def test_missing_pdf_is_explicit_failure(tmp_path):
    result = inspect_pdf(tmp_path/'missing.pdf')
    assert result['status'] == 'FAIL'
    assert result['blockers'] == ['MISSING_FILE']
    assert result['pages_actual'] is None


def test_unreadable_pdf_is_not_silently_passed(tmp_path):
    path = tmp_path/'broken.pdf'
    path.write_bytes(b'not a PDF')
    result = inspect_pdf(path)
    assert result['status'] == 'FAIL'
    assert any('UNREADABLE' in r for r in result['blockers'])


def test_real_inventory_column_names_checked():
    result = dict(sha_actual='abcd', size_actual=123, pages_actual=3)
    assert check_inventory(dict(sha256='ABCD', file_size_bytes='123', page_count='3'), result) == []
    assert len(check_inventory(dict(sha256='wrong', file_size_bytes='124', page_count='4'), result)) == 3


def test_zero_regular_numeric_mismatch_is_detected():
    source = parse_line('2 10 3 0 3 1 in 3.3 2 0 0 0 0 N/A')
    canonical = {k:str(v) for k,v in source.items()}
    canonical['resident_regular_permits'] = '3'
    count, differences = compare_row(canonical, source)
    assert count == 10
    assert differences == [dict(field='resident_regular_permits', source=0, canonical='3', status='VALUE_MISMATCH')]


def test_rotation_aware_words_preserve_table_line():
    # Real archived rotated page, read only. This guards column transposition.
    path = ROOT/'pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game/24_bg-odds.pdf'
    with pymupdf.open(path) as doc:
        rows = [r for line in visible_lines(doc[1]) if (r := parse_line(line))]
    point = next(r for r in rows if r['points']=='22')
    assert point['resident_eligible_applicants'] == 5
    assert point['resident_bonus_permits'] == 4
    assert point['nonresident_eligible_applicants'] == 2


def test_documented_carryover_keeps_raw_difference_visible():
    source = parse_line('15 0 0 0 1 1 in 1.0 15 0 0 0 0 N/A')
    canonical = {k:str(v) for k,v in source.items()}
    canonical.update(resident_total_permits='0', resident_success_ratio='N/A',
                     qa_notes='OFFICIAL_SOURCE_TOP_POINT_TOTAL_RATIO_CARRYOVER')
    _, differences = compare_row(canonical, source)
    assert len(differences)==2
    assert {r['status'] for r in differences} == {'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'}


def test_main_writes_blocked_report_with_real_cell_difference(tmp_path, monkeypatch):
    import csv
    import json
    from engine.utah.quality import verify_all_failing_engines_pdfs as audit
    def table(path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    root = tmp_path/'repo'
    pdf = root/'source.pdf'
    root.mkdir()
    pdf.write_bytes(b'test fixture; extraction mocked')
    inventory, database = root/'inventory.csv', root/'DATABASE.csv'
    table(inventory, [dict(path='source.pdf')])
    table(database, [dict(hunt_code='EA1121')])
    master = root/'canonical.csv'
    table(master, [dict(hunt_code='EA1121')])
    parsed = parse_line('2 10 3 0 3 1 in 3.3 2 0 0 0 0 N/A')
    row = {k:str(v) for k,v in parsed.items()}
    row.update(hunt_code='EA1121', source_scope='ANTLERLESS', source_file='source.pdf',
               source_path='source.pdf', pdf_page='1', resident_regular_permits='3')
    table(root/'data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2024_for_2025_canonical_yearly_draw_results.csv', [row])
    for value in ('scripts/resolve-antlerless-hunt-codes-2026.py',
                  'data_truth/draw_results_truth/normalized/draw_results_long.csv',
                  'governance/prediction-family-certification.json'):
        path = root/value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('protected fixture')
    for name, value in dict(ROOT=root, YEARS=[2024], SCOPES=['ANTLERLESS'], PDF_ROOTS=[],
                            MANIFESTS=[], HUNT_MASTER_CANONICAL=master, INVENTORY=inventory, DATABASE=database).items():
        monkeypatch.setattr(audit, name, value)
    monkeypatch.setattr(audit, 'inspect_pdf', lambda p: dict(path='source.pdf', sha_actual=audit.sha(p),
        size_actual=p.stat().st_size, pages_actual=1, codes=['EA1121'], blockers=[],
        status='READABLE_NOT_NUMERICALLY_CERTIFIED', table_rows={('EA1121', 'point_level_draw_result','2','1'):parsed}))
    monkeypatch.setattr('sys.argv', ['audit', '--skip-download', '--out-dir', str(root/'out')])
    assert audit.main() == 1
    report = json.loads((root/'out/2026_all_species_all_years_2017_2026_audit.json').read_text())
    assert report['summary']['difference_counts'] == {'VALUE_MISMATCH':1}
    assert report['summary']['protected_files_changed'] == []
    differences = list(csv.DictReader((root/'out/2026_all_species_all_years_2017_2026_audit_cell_differences.csv').open()))
    assert differences[0]['source_file'] == 'source.pdf'
    assert differences[0]['source'] == '0'


def test_download_rejects_html_without_creating_pdf(tmp_path, monkeypatch):
    from engine.utah.quality import verify_all_failing_engines_pdfs as audit
    class Response:
        status_code = 200
        headers = {'Content-Type':'text/html'}
        content = b'<html>Not a report</html>'
        text = content.decode()
        url = 'https://wildlife.utah.gov/test.pdf'
        def raise_for_status(self):
            pass
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    monkeypatch.setattr(audit, 'OFFICIAL_INDEXES', [])
    monkeypatch.setattr(audit, 'REQUESTED_2026_URLS', ['https://wildlife.utah.gov/test.pdf'])
    monkeypatch.setattr(audit.requests, 'get', lambda *args, **kwargs: Response())
    checks = audit.pull_official_2026(tmp_path)
    assert checks[0]['status'] == 'FETCH_OR_IDENTITY_FAILED'
    assert 'not PDF bytes' in checks[0]['reason']
    assert not list(tmp_path.rglob('*.pdf'))
