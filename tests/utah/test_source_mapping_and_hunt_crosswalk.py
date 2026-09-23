import csv
import json
from pathlib import Path

import pymupdf
import pytest

from engine.utah.quality import audit_database_vs_canonical as identity
from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as mapping


def test_repository_root():
    assert (mapping.ROOT/'AGENTS.md').is_file()
    assert mapping.ROOT == Path(__file__).resolve().parents[2]


def test_missing_pdf_is_recorded_not_skipped(tmp_path):
    result = mapping.extract_pdf(tmp_path/'missing.pdf')
    assert result['status'] == 'ERROR'
    assert result['errors']


def test_real_code_pages_and_hash(tmp_path):
    path = tmp_path/'report.pdf'
    with pymupdf.open() as doc:
        for text in ('2019 Draw Results Hunt: EA1007', 'Hunt: EA1007 Hunt: DB1592'):
            doc.new_page().insert_text((40, 40), text)
        doc.save(path)
    result = mapping.extract_pdf(path)
    assert result['sha256'] == mapping.sha(path)
    assert result['codes'] == {'EA1007': [1, 2], 'DB1592': [2]}
    assert result['header_years'] == ['2019']


def test_ratio_normalizes_spacing_only():
    row = dict(status='VALUE_MISMATCH', field='resident_success_ratio', source='1 in 4.6', canonical='1in4.6')
    assert mapping.classify_difference(row) == 'RATIO_WHITESPACE_ONLY'
    row['canonical'] = '1in4.5'
    assert mapping.classify_difference(row) == 'VALUE_MISMATCH'


def test_only_total_rows_are_aggregate():
    row = dict(status='PDF_ROW_NOT_IN_CANONICAL', key="('EA1007', 'hunt_total_draw_result', '', '5')")
    assert mapping.classify_difference(row) == 'AGGREGATE_TOTAL_NOT_POINT_RUNG'
    row['key'] = "('EA1007', 'point_level_draw_result', '0', '5')"
    assert mapping.classify_difference(row) == 'PDF_ROW_NOT_IN_CANONICAL'


def test_carryover_is_preserved():
    assert mapping.classify_difference({'status': 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'}) == 'DOCUMENTED_SOURCE_DISPLAY_CARRYOVER'


def test_endpoint_explicit_zero_never_falls_back_to_total():
    row = dict(hunt_code='EA1007', residency='resident', points='2', source_is_youth='false',
               eligible_applicants='10', successful_applicants='2', regular_permits='0', bonus_permits='2', total_permits='2')
    raw = dict(IsYouth=False, ParticipantCount=10, SuccessfulCount=2,
               SuccessfulByMaxPointRoundCount=2, SuccessfulByRegularRoundCount=0)
    key = ('EA1007', 'resident', mapping.decimal('2'))
    assert mapping.endpoint_parity(row, {key: [raw]}) == ('ENDPOINT_POPULATED_FIELDS_MATCH', 5)
    raw['SuccessfulByRegularRoundCount'] = 2
    assert mapping.endpoint_parity(row, {key: [raw]})[0] == 'ENDPOINT_VALUE_MISMATCH'


def test_endpoint_cannot_choose_youth_from_outcome_values():
    row = dict(hunt_code='EA1007', residency='resident', points='0', eligible_applicants='1', successful_applicants='1')
    key = ('EA1007', 'resident', mapping.decimal('0'))
    raw = [dict(IsYouth=False, ParticipantCount=1, SuccessfulCount=1),
           dict(IsYouth=True, ParticipantCount=10, SuccessfulCount=2)]
    assert mapping.endpoint_parity(row, {key: raw})[0] == 'ENDPOINT_SOURCE_DIMENSION_UNRESOLVED'
    other_key = ('EA1007', 'nonresident', mapping.decimal('5'))
    assert mapping.endpoint_parity(row, {key: raw[:1], other_key:raw[1:]})[0] == 'ENDPOINT_SOURCE_DIMENSION_UNRESOLVED'


def test_single_hunt_pool_recovered_without_using_outcome_values():
    row = dict(hunt_code='EB1007',source_scope='YOUTH_GENERAL_SEASON_ELK',source_is_youth='')
    index = {('EB1007','resident',mapping.decimal('0')):[dict(IsYouth=False,ParticipantCount=100)]}
    assert mapping.recover_source_pool(row,index) == ('false','EXACT_ENDPOINT_HUNT_SINGLE_POOL')
    index[('EB1007','resident',mapping.decimal('0'))][0]['ParticipantCount']=999
    assert mapping.recover_source_pool(row,index)[0] == 'false'


def test_pool_label_conflict_not_silently_overwritten():
    row = dict(hunt_code='TK1003',source_is_youth='false',source_row_identifier='utahdraws:file:is-youth=true:csv-row=7')
    assert mapping.recover_source_pool(row,{}) == ('','CONFLICTING_EXPLICIT_SOURCE_POOL_LABELS')
    row['source_is_youth']='ambiguous_coalesced_true_false'
    row['source_row_identifier']='coalesced:one:is-youth=false:csv-row=1|two:is-youth=true:csv-row=2'
    assert mapping.recover_source_pool(row,{})==('','COALESCED_OR_UNRESOLVED_SOURCE_POOL_METADATA')


def test_planner_youth_hunt_is_independent_of_source_pool_flag():
    from engine.utah.quality.recover_source_pool_labels_2026 import eligibility
    planner={'EB1007':{'payload':{'huntYears':[{'HUNT_YEAR':2026}],
                                 'huntMaster':{'HUNT_NAME':'Draw-only Youth Any Bull/Hunters Choice Elk'}}}}
    assert eligibility('EB1007',planner,{False})=='YOUTH_ONLY_EXPLICIT_PLANNER_NAME'


def test_exact_positive_vector_requires_unique_all_field_match():
    from engine.utah.quality.recover_source_pool_labels_2026 import exact_positive_row_pool
    row=dict(hunt_code='DB1592',residency='resident',points='2',eligible_applicants='8',
             successful_applicants='7',regular_permits='7',bonus_permits='0',total_permits='7')
    a=dict(IsYouth=False,ParticipantCount=8,SuccessfulCount=7,SuccessfulByRegularRoundCount=7,SuccessfulByMaxPointRoundCount=0)
    b=dict(a,IsYouth=True,ParticipantCount=2)
    index={('DB1592','resident',mapping.decimal('2')):[a,b]}
    assert exact_positive_row_pool(row,index)[0]=='false'
    b['ParticipantCount']=8
    assert exact_positive_row_pool(row,index)[0]==''
    row['eligible_applicants']='0'
    row['successful_applicants']='0'
    row['regular_permits']='0'
    row['total_permits']='0'
    assert exact_positive_row_pool(row,index)[0]==''


def test_parent_table_needs_two_anchors_and_no_conflicting_keys():
    from engine.utah.quality.recover_source_pool_labels_2026 import table_pool_identity
    a=dict(hunt_code='DB1592',residency='resident',points='1',eligible_applicants='8',successful_applicants='7')
    b=dict(a,points='2',eligible_applicants='9')
    index={('DB1592','resident',mapping.decimal(point)):[dict(IsYouth=False,ParticipantCount=n,SuccessfulCount=7),
                                                      dict(IsYouth=True,ParticipantCount=3,SuccessfulCount=1)] for point,n in [('1',8),('2',9)]}
    assert table_pool_identity([a],index)[0]==''
    assert table_pool_identity([a,b],index)[0]=='false'
    assert table_pool_identity([a,b,dict(a,eligible_applicants='5')],index)[0]==''


def test_metadata_application_syncs_long_and_preserves_backups(tmp_path,monkeypatch):
    from engine.utah.quality import recover_source_pool_labels_2026 as recovery
    from scripts import rebuild_draw_results_long_from_canonical_yearly as rebuild
    monkeypatch.setattr(mapping,'ROOT',tmp_path)
    monkeypatch.setattr(rebuild,'ROOT',tmp_path)
    canonical=tmp_path/'canonical.csv'
    long_path=tmp_path/'long.csv'
    monkeypatch.setattr(recovery,'CANONICAL',canonical)
    monkeypatch.setattr(rebuild,'LONG_FILE',long_path)
    monkeypatch.setattr(rebuild,'canonical_files',lambda:[canonical])
    fields=['actual_draw_year','residency','eligible_applicants','total_permits','source_is_youth','source_file','pdf_page']
    row=dict(zip(fields,['2026','Resident','3','1','','official.pdf','1']))
    for path in (canonical,long_path):
        recovery.write_csv(path,[row],fields)
    old_canonical=mapping.sha(canonical)
    old_long=mapping.sha(long_path)
    review=tmp_path/'review'
    review.mkdir()
    recovery.write_csv(review/canonical.name,[dict(row,source_is_youth='false')],fields)
    recovery.write_csv(review/'pool_label_recovery.csv',[dict(recovered_source_is_youth='false',numeric_status='ENDPOINT_POPULATED_FIELDS_MATCH')],
                       ['recovered_source_is_youth','numeric_status'])
    mapping.write_json(review/'summary.json',dict(changed_nonlabel_rows=[],changed_inputs=[],numeric_cell_differences=0,
                                                input_hashes={'canonical.csv':old_canonical}))
    assert recovery.apply_reviewed_metadata(review)==0
    assert mapping.read_csv(canonical)==mapping.read_csv(long_path)
    assert mapping.read_csv(canonical)[0]['source_is_youth']=='false'
    assert mapping.sha(review/'rollback'/canonical.name)==old_canonical
    assert mapping.sha(review/'rollback'/long_path.name)==old_long
    assert json.loads((review/'metadata_application.json').read_text())['numeric_or_other_cells_changed']==0


def test_long_freeze_accepts_builder_column_order_but_rejects_value_changes(tmp_path,monkeypatch):
    import importlib
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'scripts'))
    freeze=importlib.import_module('freeze_draw_results_long_truth')
    builder=importlib.import_module('rebuild_draw_results_long_from_canonical_yearly')
    canonical=tmp_path/'canonical.csv'
    canonical.write_text('actual_draw_year,hunt_code,source_is_youth\n2026,EB1007,false\n',encoding='utf-8')
    long_path=tmp_path/'long.csv'
    long_path.write_text('source_is_youth,hunt_code,actual_draw_year\nfalse,EB1007,2026\n',encoding='utf-8')
    monkeypatch.setattr(freeze,'ROOT',tmp_path)
    monkeypatch.setattr(freeze,'LONG',long_path)
    monkeypatch.setattr(builder,'LONG_FILE',long_path)
    monkeypatch.setattr(freeze,'OUT',tmp_path/'report.json')
    monkeypatch.setattr(freeze,'canonical_files',lambda:[canonical])
    assert freeze.main()==0
    long_path.write_text('source_is_youth,hunt_code,actual_draw_year\ntrue,EB1007,2026\n',encoding='utf-8')
    assert freeze.main()==1


def test_current_missing_canonical_is_not_retired():
    assert identity.current_identity_status(False, {'fetch_status': 'OK', 'hunt_year': '2026'}) == 'CURRENT_PLANNER_MISSING_CANONICAL'
    assert identity.current_identity_status(True, {}) == 'CANONICAL_NOT_IN_CURRENT_PLANNER_REVIEW'


def test_canonical_explicit_retirement_only(tmp_path):
    path = tmp_path/'canonical.csv'
    path.write_text('hunt_code,status,is_retired\n ea1007 ,active,\nDB1000, Retired ,\nBR1000,,true\n', encoding='utf-8')
    active, excluded = identity.load_canonical(path)
    assert set(active) == {'EA1007'}
    assert set(excluded) == {'DB1000', 'BR1000'}


@pytest.mark.parametrize('content', ['hunt_code\n', 'hunt_code\nEA1007\nea1007\n', 'other\nx\n'])
def test_invalid_canonical_fails_closed(tmp_path, content):
    path = tmp_path/'canonical.csv'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        identity.load_canonical(path)


def test_crosswalk_preserves_all_providers_and_does_not_approve_relationship(tmp_path, monkeypatch):
    monkeypatch.setattr(mapping, 'ROOT', tmp_path)
    path = tmp_path/'data_truth/crosswalk_truth/normalized/2026_no_exact_history_additions_crosswalk.csv'
    path.parent.mkdir(parents=True)
    path.write_text('current_hunt_code,historical_hunt_code,guidebook_first_listed_file,guidebook_first_listed_page\n'
                    'BR7021,BR7008,pipeline/2026/guidebooks/bear.pdf,73\n', encoding='utf-8')
    sources = [dict(pdf_path='pipeline/2026/guidebooks/bear.pdf', status='CODE_PRESENCE_ONLY',
                    sha256='a', codes={'BR7021':[73], 'BR7008':[74]})]
    report = mapping.previous_crosswalk_review(sources, {'BR7021':{}}, {'BR7008':{2025}})
    row = report['records'][0]
    assert row['cited_first_listing_page_verified']
    assert row['review_status'] == 'GUIDEBOOK_LISTING_CONFIRMED_NOT_PREDECESSOR_PROOF'
    assert row['historical_canonical_years']['BR7008'] == [2025]
    assert row['current_canonical_codes'] == ['BR7021']
    assert report['missing_crosswalk_files']


def test_requested_exports_use_dynamic_counts_and_preserve_unresolved(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, 'ROOT', tmp_path)
    canonical = tmp_path/'canonical.csv'
    database = tmp_path/'database.csv'
    planner = tmp_path/'planner.csv'
    sources = tmp_path/'sources.json'
    canonical.write_text('hunt_code\nEA1007\nDB1592\n', encoding='utf-8')
    database.write_text('hunt_code\nEA1007\nDB1592\nBR7008\n', encoding='utf-8')
    planner.write_text('hunt_code,fetch_status,hunt_year\nEA1007,OK,2026\nBR7022,OK,2026\nDB1592,OK,2025\n', encoding='utf-8')
    sources.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(identity, 'HUNT_MASTER_CANONICAL', canonical)
    monkeypatch.setattr(identity, 'DATABASE', database)
    out = tmp_path/'out'
    identity.export_evidence(planner, sources, out)
    current = json.loads((out/'current_but_uncanonicalized_171.json').read_text())
    assert current['count'] == 1
    assert current['codes'] == ['BR7022']
    unconfirmed = json.loads((out/'canonical_without_confirmation_33.json').read_text())
    assert unconfirmed['codes'] == ['DB1592']
    crosswalk = json.loads((out/'hunt_crosswalk_with_evidence.json').read_text())
    assert crosswalk['unresolved_lineage'] == ['BR7008']
    assert all(not row['numeric_match'] for row in crosswalk['rows'])
    assert all('RETIRED' not in row['classification'] for row in crosswalk['rows'])
    with pytest.raises(ValueError, match='already exist'):
        identity.export_evidence(planner, sources, out)
