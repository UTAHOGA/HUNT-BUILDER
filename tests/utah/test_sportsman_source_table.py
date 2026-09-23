import pytest

from engine.utah.quality.sportsman_source_table import parse_sportsman_lines, compare_sportsman_row
from engine.utah.quality.build_source_mapping_and_hunt_crosswalk import endpoint_review_identity, decimal


def lines():
    return ['Utah Division of Wildlife Resources Sportsman Successful Resident Quota',
            'BI1000 Sportsman Bison 1 0 4,964 0 4,965 1 N/A 1 1 in 4,965.0 N/A',
            'Grand Totals .......... 1 0 4,964 0 4,965 1 0 1']


def test_exact_outcomes_and_ratio_match_without_alias_or_bonus_ladder():
    src = parse_sportsman_lines(lines())['BI1000']
    row = dict(eligible_applicants='4965', successful_applicants='1',
               resident_success_ratio='1 in 4965.0', resident_p_draw='0.0002014099')
    ok, cells = compare_sportsman_row(row, src)
    assert ok and all(c['status'] == 'MATCH' for c in cells)
    row['successful_applicants'] = '2'
    assert not compare_sportsman_row(row, src)[0]


def test_old_nonresident_na_remains_documented_not_a_probability():
    src_lines = [lines()[0], 'TK1000 TK - -Turkey 1 N/A 1372 N/A 1373 1 N/A 1 1 in 1373.0 N/A',
                 'Total 1 N/A 1372 N/A 1373 1 N/A 1']
    src = parse_sportsman_lines(src_lines)['TK1000']
    ok, cells = compare_sportsman_row(dict(eligible_applicants='1373', successful_applicants='1',
                                         nonresident_p_draw='0'), src)
    assert ok and src['cells'][1] == 'N/A'
    assert cells[-1]['basis'] == 'NONPARTICIPATING_NR_NORMALIZATION_NOT_ODDS'


@pytest.mark.parametrize('replacement', [
    'Grand Totals .......... 1 0 4,960 0 4,965 1 0 1',
    'Grand Totals .......... 1 0 4,964 0 4,960 1 0 1',
    '',
])
def test_bad_or_missing_grand_total_fails_closed(replacement):
    with pytest.raises(ValueError):
        parse_sportsman_lines(lines()[:-1] + [replacement])


def test_missing_field_and_duplicate_hunt_are_not_silently_dropped():
    with pytest.raises(ValueError, match='Duplicate'):
        parse_sportsman_lines(lines() + [lines()[1]])
    with pytest.raises(ValueError, match='Unparsed'):
        parse_sportsman_lines(lines() + ['BR1000 Sportsman Bear 1 MISSING'])


def test_source_pdf_positive_vector_recovery_does_not_guess_equal_pools():
    row = dict(hunt_code='DB0008', residency='Resident', points='1',
               source_dataset='OFFICIAL_DWR_2026_PDF_DRAW_RESULTS',
               eligible_applicants='4', successful_applicants='4')
    raw = dict(IsYouth=True, ParticipantCount=4, SuccessfulCount=4)
    idx = {('DB0008', 'resident', decimal('1')): [raw, dict(raw, IsYouth=False, ParticipantCount=55)]}
    assert endpoint_review_identity(row, idx)[0] == 'true'
    idx[('DB0008', 'resident', decimal('1'))][1]['ParticipantCount'] = 4
    assert endpoint_review_identity(row, idx)[0] == ''
    row['source_row_identifier'] = 'is-youth=true:is-youth=false'
    assert endpoint_review_identity(row, idx)[0] == ''
