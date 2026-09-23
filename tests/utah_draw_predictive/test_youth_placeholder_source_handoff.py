import pytest
from engine.utah_draw_predictive.run_all_families import (
    _source_backed_probability_rows, _with_run_fields,
    _merge_source_backed_family_rows, _youth_reserve_input_placeholder,
    _source_backed_conditional_handoff_placeholder,
)


def placeholder(**changes):
    row = dict(family='youth_draw', hunt_code='DA1000', species='Deer', residency='Resident',
               points='0', draw_pool='youth_antlerless_deer',
               draw_system_type='YOUTH_ANTLERLESS_OR_DOE_RESERVE',
               model_strategy='youth_antlerless_or_doe_reserve_preference_v1',
               algorithm_status='IN_SCOPE_MODEL_PENDING', youth_reserve_model_valid='FALSE',
               data_quality_flags='YOUTH_RESERVE_PROBABILITY_INPUT_MISSING',
               p_draw='', p_draw_mean='', p_preference_draw='')
    return {**row, **changes}


def source(**changes):
    row = dict(hunt_code='DA1000', species='Deer', hunt_type='Antlerless',
               draw_system_type='PREFERENCE_ANTLERLESS_DEER', draw_pool='youth',
               residency='Resident', points='0', eligible_applicants='18', total_permits='2',
               regular_permits='2', p_draw='0.1111111111', source_is_youth='true',
               source_file='official_dwr_archive/big_game_antlerless/17_antlerless_youth_points.pdf',
               pdf_page='1', record_type='point_level_draw_result')
    return {**row, **changes}


def test_exact_source_lane_can_handoff_unmodeled_placeholder():
    primary = placeholder()
    fallback = _source_backed_probability_rows([source()], {'youth_draw': [primary]}, 2017, 2018)['youth_draw']
    added = _with_run_fields(fallback, 2017, 2018, 'youth_draw')
    rows, replaced = _merge_source_backed_family_rows('youth_draw', [primary], added)
    assert len(rows) == len(replaced) == 1
    assert rows[0]['p_draw'] == '0.111111'
    assert rows[0]['residency'] == 'Resident'
    assert rows[0]['pdf_page'] == '1'
    assert rows[0]['model_strategy'] == 'youth_draw_source_backed_roll_forward'


@pytest.mark.parametrize('changes', [
    {'algorithm_status': 'NO_TRANSITION_EVIDENCE'},
    {'algorithm_status': 'NOT_SCORED_SOURCE_ROLL_FORWARD_GUARANTEE_BLOCKED'},
    {'p_draw': '0'}, {'p_draw': '0.25'}, {'youth_reserve_model_valid': 'TRUE'},
    {'family': 'bonus_oil_big_game'}, {'data_quality_flags': ''},
])
def test_real_models_and_intentional_abstentions_are_not_placeholders(changes):
    assert not _youth_reserve_input_placeholder(placeholder(**changes))


def test_nonresident_source_does_not_replace_resident_placeholder():
    primary = placeholder()
    fallback = _source_backed_probability_rows([source(residency='Nonresident')], {'youth_draw': [primary]}, 2017, 2018)['youth_draw']
    rows, replaced = _merge_source_backed_family_rows('youth_draw', [primary], fallback)
    assert primary in rows and not replaced


def test_empty_source_does_not_supply_probability_to_placeholder():
    assert not _source_backed_probability_rows([source(eligible_applicants='0', regular_permits='0', total_permits='0', p_draw='')],
                                             {'youth_draw': [placeholder()]}, 2017, 2018).get('youth_draw')


def test_observed_zero_success_is_not_copied_as_future_zero_probability():
    fallback = _source_backed_probability_rows(
        [source(eligible_applicants='18', regular_permits='0', total_permits='0', p_draw='0')],
        {'youth_draw': [placeholder()]},
        2017,
        2018,
    )['youth_draw']
    assert fallback[0]['p_draw'] == ''
    assert fallback[0]['algorithm_status'] == 'NO_TRANSITION_EVIDENCE'
    assert fallback[0]['classification_status'] == 'SOURCE_ROLL_FORWARD_ZERO_OUTCOME_BLOCKED'
    assert fallback[0]['prediction_status'] == 'NOT_SCORED'


def test_prior_certainty_stays_blank_after_handoff():
    fallback = _source_backed_probability_rows([source(eligible_applicants='2', p_draw='1')],
                                             {'youth_draw': [placeholder()]}, 2017, 2018)['youth_draw']
    assert fallback[0]['p_draw'] == ''
    assert fallback[0]['algorithm_status'] == 'NOT_SCORED_SOURCE_ROLL_FORWARD_GUARANTEE_BLOCKED'


def test_adult_source_never_fills_youth_placeholder():
    adult = source(source_file='official_dwr_archive/big_game_antlerless/17_antlerless_points.pdf',
                   draw_pool='general_season_antlerless_deer', source_is_youth='false')
    fallback = _source_backed_probability_rows([adult], {'youth_draw': [placeholder()]}, 2017, 2018)
    assert not fallback.get('youth_draw')


def test_missing_exact_source_preserves_placeholder():
    primary = placeholder()
    assert _merge_source_backed_family_rows('youth_draw', [primary], []) == ([primary], [])


def bonus_conditional_placeholder(**changes):
    row = dict(
        family='bonus_le_big_game', hunt_code='DB1017', species='Deer',
        residency='Resident', points='12', draw_pool='limited_entry_deer',
        draw_system_type='BONUS_LE_BIG_GAME', model_strategy='generic_big_game_bonus',
        algorithm_status='NOT_SCORED_CONDITIONAL_RUNG_NO_TRANSITION_EVIDENCE',
        p_draw='', p_draw_mean='', p_bonus_pool='', p_random_pool='',
    )
    return {**row, **changes}


def bonus_source(**changes):
    row = dict(
        row_type='point_level_draw_result', hunt_code='DB1017',
        hunt_name='Limited-entry deer', species='Deer', sex_type='Buck',
        hunt_type='Limited Entry', hunt_class='Limited Entry',
        draw_system_type='BONUS_LE_BIG_GAME', draw_pool='limited_entry_deer',
        residency='Resident', points='12', eligible_applicants='8',
        bonus_permits='4', regular_permits='1', total_permits='5',
        p_draw='0.625', source_file='17_big_game_odds_report.pdf', pdf_page='20',
        record_type='point_level_draw_result',
    )
    return {**row, **changes}


def test_fractional_exact_source_row_replaces_blank_bonus_conditional_rung():
    primary = bonus_conditional_placeholder()
    fallback = _source_backed_probability_rows(
        [bonus_source()], {'bonus_le_big_game': [primary]}, 2017, 2018
    )['bonus_le_big_game']
    rows, replaced = _merge_source_backed_family_rows(
        'bonus_le_big_game', [primary], fallback
    )
    assert _source_backed_conditional_handoff_placeholder('bonus_le_big_game', primary)
    assert len(rows) == len(replaced) == 1
    assert rows[0]['p_draw'] == '0.625000'
    assert rows[0]['model_strategy'] == 'bonus_le_big_game_source_backed_roll_forward'


@pytest.mark.parametrize('source_probability', ['0', '1'])
def test_zero_or_certain_source_row_preserves_blank_bonus_conditional_rung(source_probability):
    primary = bonus_conditional_placeholder()
    fallback = _source_backed_probability_rows(
        [bonus_source(p_draw=source_probability)],
        {'bonus_le_big_game': [primary]},
        2017,
        2018,
    ).get('bonus_le_big_game', [])
    rows, replaced = _merge_source_backed_family_rows(
        'bonus_le_big_game', [primary], fallback
    )
    assert rows == [primary]
    assert replaced == []


def test_oil_handoff_matches_exact_lane_despite_sparse_primary_metadata():
    primary = bonus_conditional_placeholder(
        family='bonus_oil_big_game', hunt_code='BI6515', points='8',
        species='', sex_type='', hunt_type='Once-in-a-Lifetime', hunt_class='',
        draw_system_type='BONUS_OIL_BIG_GAME', draw_pool='once_in_a_lifetime',
    )
    source_row = bonus_source(
        hunt_code='BI6515', points='8', species='Bison', sex_type='Cow',
        hunt_name='Bison Archery - Henry Mtns (cow Only) - Archery',
        hunt_type='O.I.L.', hunt_class='ONCE_IN_A_LIFETIME',
        draw_system_type='BONUS_OIL_BIG_GAME', draw_pool='max_weighted_split',
        eligible_applicants='2', bonus_permits='1', regular_permits='0',
        total_permits='1', p_draw='0.5', source_file='19_bg-odds.pdf', pdf_page='497',
    )
    fallback = _source_backed_probability_rows(
        [source_row], {'bonus_oil_big_game': [primary]}, 2019, 2020
    )['bonus_oil_big_game']
    finalized = _with_run_fields(fallback, 2019, 2020, 'bonus_oil_big_game')
    rows, replaced = _merge_source_backed_family_rows(
        'bonus_oil_big_game', [primary], finalized
    )
    assert len(rows) == len(replaced) == 1
    assert rows[0]['hunt_code'] == 'BI6515'
    assert rows[0]['p_draw'] == '0.500000'
