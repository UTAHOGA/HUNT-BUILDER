import pytest
import csv
import json
from scripts import project_legacy_canonical_for_blind_scoring as adapter
from scripts.project_legacy_canonical_for_blind_scoring import expand_actual, prepare_verified_outcome


def actual(**changes):
    row = dict(record_type='point_level_draw_result', hunt_code='MB6011', residency='Resident',
               source_is_youth='false', source_file='Official UtahDraws', draw_design='MAX_WEIGHTED_SPLIT',
               points='28', eligible_applicants='80', bonus_permits='0', regular_permits='0',
               total_permits='0', successful_applicants='0', success_ratio='N/A', p_draw='', p_draw_percent='')
    row.update(changes)
    return row


def test_positive_applicants_zero_awards_becomes_observed_zero_only_when_verified():
    source = actual()
    assert expand_actual([source])[0]['p_draw'] == ''
    result = expand_actual([source], {2})[0]
    assert result['p_draw'] == result['p_draw_percent'] == '0'
    assert result['success_ratio'] == 'N/A'
    assert source['p_draw'] == ''
    assert {k: v for k, v in result.items() if k not in ('p_draw', 'p_draw_percent', 'actual_probability_source')} == {
        k: v for k, v in source.items() if k not in ('p_draw', 'p_draw_percent')}


@pytest.mark.parametrize('changes', [
    {'eligible_applicants': '0'}, {'eligible_applicants': ''}, {'total_permits': ''},
    {'bonus_permits': ''}, {'regular_permits': ''}, {'regular_permits': '1'},
    {'total_permits': '100', 'bonus_permits': '100'}, {'eligible_applicants': 'nan'},
    {'eligible_applicants': 'inf'}, {'eligible_applicants': '-1'}, {'eligible_applicants': '1.5'},
    {'source_is_youth': ''}, {'source_file': ''}, {'scoring_allowed': 'false'},
    {'record_type': 'hunt_total_draw_result'}, {'draw_design': 'REFERENCE_ONLY'},
    {'successful_applicants': '1'}, {'p_draw': '0'}, {'p_draw': 'not valid'}, {'resident_p_draw': '0'},
])
def test_empty_invalid_reference_or_existing_outcome_is_preserved(changes):
    row = actual(**changes)
    assert prepare_verified_outcome(row) == row


def test_partial_success_is_an_observed_frequency_not_a_forecast():
    row = actual(eligible_applicants='12', bonus_permits='9', total_permits='9', successful_applicants='9')
    assert prepare_verified_outcome(row)['p_draw'] == '0.75'


def test_preference_is_not_mistaken_for_reference():
    assert prepare_verified_outcome(actual(draw_design='PREFERENCE_ANTLERLESS_DEER'))['p_draw'] == '0'


def test_opposite_residency_not_filled_by_verified_neighbor():
    rows = [actual(), actual(residency='Nonresident', eligible_applicants='5')]
    projected = expand_actual(rows, {2})
    assert projected[0]['p_draw'] == '0'
    assert projected[1]['p_draw'] == ''


@pytest.mark.parametrize('damage', ['', 'truth_hash', 'endpoint_hash', 'numeric_cell', 'pool'])
def test_endpoint_evidence_is_rechecked_not_accepted_from_label(tmp_path, monkeypatch, damage):
    from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as source
    monkeypatch.setattr(adapter, 'REPO', tmp_path)
    row = actual()
    truth = tmp_path / 'canonical.csv'
    with truth.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    endpoint = tmp_path / 'endpoint.json'
    endpoint.write_text(json.dumps({'Data': [{'HuntCode': 'MB6011', 'OddsList': [{
        'ResidencyTypeID': 1, 'Point': 28, 'IsYouth': damage == 'pool', 'ParticipantCount': 79 if damage == 'numeric_cell' else 80,
        'SuccessfulCount': 0, 'SuccessfulByMaxPointRoundCount': 0, 'SuccessfulByRegularRoundCount': 0}]}]}))
    digest = adapter.sha256(endpoint)
    evidence = dict(canonical_csv_line=2, hunt_code='MB6011', residency='Resident', points='28', source_is_youth='false',
                    parity='ENDPOINT_POPULATED_FIELDS_MATCH', endpoint=str(endpoint), endpoint_sha256=digest)
    with (tmp_path / 'canonical_endpoint_probability_review.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence))
        writer.writeheader()
        writer.writerow(evidence)
    (tmp_path / 'summary.json').write_text(json.dumps({'input_hashes': {
        'canonical.csv': 'changed' if damage == 'truth_hash' else adapter.sha256(truth),
        source.rel(endpoint): 'changed' if damage == 'endpoint_hash' else digest}}))
    if damage:
        with pytest.raises(ValueError):
            adapter.verified_outcome_lines(tmp_path, truth, [row])
    else:
        assert adapter.verified_outcome_lines(tmp_path, truth, [row]) == {2}
