from scripts.review_remaining_source_rows import endpoint_companions, source


def fixtures():
    original = dict(hunt_code='DB1592', residency='Nonresident', points='3',
                    eligible_applicants='1', successful_applicants='1',
                    bonus_permits='0', regular_permits='1', total_permits='1')
    raw = dict(HuntID=1249, ParticipantCount=1, SuccessfulCount=1,
               SuccessfulByMaxPointRoundCount=0, SuccessfulByRegularRoundCount=1)
    index = {('DB1592', 'nonresident', source.decimal('3')):
             [dict(raw, IsYouth=False), dict(raw, IsYouth=True)]}
    canonical = [(line, dict(original, source_is_youth=pool,
                            source_dataset='UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260902',
                            source_row_identifier=f'utahdraws:package:hunt-id=1249:is-youth={pool}:csv-data-row={line}',
                            source_file='retained endpoint'))
                 for line, pool in ((10, 'false'), (11, 'true'))]
    return original, canonical, index


def test_both_typed_companions_retained_without_assigning_original_pool():
    original, canonical, index = fixtures()
    result = endpoint_companions(original, canonical, index)
    assert {r['source_is_youth'] for r in result} == {'false', 'true'}
    assert 'source_is_youth' not in original


def test_missing_duplicate_or_conflicting_companion_is_not_proof():
    original, canonical, index = fixtures()
    assert endpoint_companions(original, canonical[:1], index) == []
    assert endpoint_companions(original, canonical + canonical[:1], index) == []
    canonical[0][1]['successful_applicants'] = '0'
    assert endpoint_companions(original, canonical, index) == []


def test_equal_key_with_wrong_values_or_wrong_parent_is_not_a_duplicate():
    original, canonical, index = fixtures()
    original['eligible_applicants'] = '2'
    assert endpoint_companions(original, canonical, index) == []
    original['eligible_applicants'] = '1'
    canonical[0][1]['source_row_identifier'] = 'utahdraws:wrong-hunt-id=9999:is-youth=false:'
    assert endpoint_companions(original, canonical, index) == []
