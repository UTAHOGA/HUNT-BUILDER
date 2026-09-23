import pytest
from scripts.project_legacy_canonical_for_blind_scoring import reconcile_scoring_identities, project_predictions
from scripts.build_blind_acceptance_review import load_draw_line_fold, write_csv


def oil(strategy, p):
    return dict(family='bonus_oil_big_game', draw_system_type='BONUS_OIL_BIG_GAME',
                hunt_code='BI6500', residency='Resident', points='0',
                draw_pool='MAX_WEIGHTED_SPLIT', model_strategy=strategy, p_draw=p)


@pytest.mark.parametrize('primary_probability', ['0', '', '0.3'])
def test_primary_owner_wins_even_if_blank_or_lower(primary_probability):
    primary = oil('generic_big_game_bonus', primary_probability)
    fallback = oil('bonus_oil_big_game_source_backed_roll_forward', '0.8')
    for rows in ([primary, fallback], [fallback, primary]):
        _, kept, decisions = reconcile_scoring_identities([], rows)
        assert kept == [primary]
        assert len(decisions) == 1


def test_fallback_without_primary_is_preserved():
    row = oil('bonus_oil_big_game_source_backed_roll_forward', '0.8')
    assert reconcile_scoring_identities([], [row])[1] == [row]


def test_two_primary_rows_fail_closed():
    with pytest.raises(ValueError, match='collision'):
        reconcile_scoring_identities([], [oil('generic_big_game_bonus', '0.2'), oil('generic_big_game_bonus', '0.4')])


def test_identical_final_records_count_once_with_provenance():
    row = oil('generic_big_game_bonus', '0.2')
    _, retained, evidence = reconcile_scoring_identities([], [row, dict(row)])
    assert retained == [row]
    assert evidence[0]['reason'] == 'IDENTICAL_FINAL_RECORD_COUNTED_ONCE'


def test_dedicated_youth_and_adult_remain_distinct():
    base = dict(family='dedicated_hunter', draw_system_type='PREFERENCE_DEDICATED_HUNTER_DEER',
                hunt_code='DB1770', residency='Resident', points='0', p_draw='0.5')
    adult = dict(base, source_family='DEDICATED_HUNTER_DEER', draw_pool='dedicated_hunter')
    youth = dict(base, source_family='YOUTH_DEDICATED_HUNTER_DEER', draw_pool='youth_dedicated_hunter')
    truth = [dict(adult, source_is_youth='false'), dict(youth, source_is_youth='true', draw_pool='dedicated_hunter')]
    actual, forecasts, decisions = reconcile_scoring_identities(truth, project_predictions([adult, youth]))
    assert [r['draw_pool'] for r in actual] == ['DEDICATED_HUNTER', 'youth_dedicated_hunter']
    assert [r['draw_pool'] for r in forecasts] == ['DEDICATED_HUNTER', 'youth_dedicated_hunter']
    assert not decisions


def test_acceptance_refuses_repeated_actual_key(tmp_path):
    row = dict(scoring_decision='score_probability', draw_design_key='BONUS_OIL_BIG_GAME',
               draw_pool_key='max_weighted_split', hunt_code='BI6500', residency='Resident',
               points='0', predicted_probability='0.2', actual_probability='0')
    path = tmp_path / 'scores.csv'
    write_csv(path, [row, dict(row, predicted_probability='0.4')])
    with pytest.raises(ValueError, match='repeated official scoring key'):
        load_draw_line_fold('2025_to_2026', path)


def test_sportsman_owner_and_fallback_do_not_create_two_samples():
    primary = dict(family='sportsman', hunt_code='BR1000', residency='Resident', points='',
                   draw_pool='sportsman_random_only', model_strategy='SPORTSMAN_RANDOM_ONLY', p_draw='0.01')
    fallback = dict(primary, points='0', draw_pool='random',
                    model_strategy='sportsman_source_backed_roll_forward', p_draw='0.02')
    _, rows, decisions = reconcile_scoring_identities([], [primary, fallback])
    assert rows == [primary]
    assert decisions[0]['hunt_code'] == 'BR1000'


@pytest.mark.parametrize('design,pool', [
    ('YOUTH_GENERAL_DEER_RESERVE', 'youth_general_season_deer'),
    ('PREFERENCE_ANTLERLESS_DEER', 'youth_antlerless_deer'),
    ('PREFERENCE_ANTLERLESS_ELK', 'youth_antlerless_elk'),
    ('PREFERENCE_DOE_PRONGHORN', 'youth_doe_pronghorn'),
    ('PREFERENCE_GENERAL_SEASON_BUCK_DEER', 'youth_general_season_deer'),
])
def test_youth_overlay_keeps_parent_design_and_distinct_pool(design, pool):
    from scripts.project_legacy_canonical_for_blind_scoring import source_pool_identity
    from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer
    row = dict(family='youth_draw', draw_system_type=design, source_family='YOUTH_SOURCE',
               hunt_code='DA1000', points='2', residency='Resident', draw_pool='old_wrong_pool')
    row['draw_pool'] = source_pool_identity(row, 'youth_draw')
    expected_design = 'PREFERENCE_GENERAL_SEASON_BUCK_DEER' if design == 'YOUTH_GENERAL_DEER_RESERVE' else design
    assert scorer.prediction_alignment_key(row)[:2] == (expected_design, pool)


def test_absent_youth_dimension_is_not_filled_from_code():
    from scripts.project_legacy_canonical_for_blind_scoring import source_pool_identity
    row = dict(hunt_code='DB1592', source_is_youth='', draw_pool='unresolved',
               draw_system_type='PREFERENCE_GENERAL_SEASON_BUCK_DEER')
    assert source_pool_identity(row, 'preference_general_deer') == 'unresolved'
    assert row['source_is_youth'] == ''


@pytest.mark.parametrize('design', ['BONUS_CWMU_BIG_GAME', 'MAX_WEIGHTED_SPLIT'])
def test_cwmu_turkey_explicit_youth_pool_is_not_merged_into_adult(design):
    from scripts.project_legacy_canonical_for_blind_scoring import source_pool_identity
    from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer
    base = dict(hunt_code='TK1018', species='Turkey', hunt_type='CWMU', draw_system_type=design,
                draw_pool='max_weighted_split', residency='Resident', points='2')
    adult = dict(base, source_is_youth='false')
    youth = dict(base, source_is_youth='true')
    assert source_pool_identity(adult, 'bonus_cwmu_big_game') == 'max_weighted_split'
    pool = source_pool_identity(youth, 'bonus_cwmu_big_game')
    assert pool == 'youth_cwmu_turkey'
    assert scorer.structural_draw_pool('bonus_cwmu_big_game', pool) == pool


def test_empty_display_is_not_conflicting_numeric_observation():
    from scripts.audit_reconciled_scoring_integrity import repeated_actual_status
    assert repeated_actual_status({(0., 0., None), (3., 1., .3333333)}) == 'EMPTY_DISPLAY_SEPARATE_FROM_POPULATED_RESULT'
    assert repeated_actual_status({(0., 0., None), (3., 0., 0.)}) == 'EMPTY_DISPLAY_SEPARATE_FROM_POPULATED_RESULT'
    assert repeated_actual_status({(3., 1., .3333333), (3., 0., 0.)}) == 'CONFLICT_REQUIRES_SOURCE_REVIEW'
    assert repeated_actual_status({(0., 1., None), (3., 1., .3333333)}) == 'CONFLICT_REQUIRES_SOURCE_REVIEW'
    assert repeated_actual_status({(0., 0., None), (3., None, None)}) == 'CONFLICT_REQUIRES_SOURCE_REVIEW'


def test_preference_abstention_requires_replayed_absence_not_status_alone(monkeypatch):
    from scripts.classify_historical_actual_gaps import preference_abstention_evidence
    from engine.utah_draw_predictive import dedicated_hunter as dh, preference_antlerless as ant
    from engine.utah_draw_predictive import run_all_families as runner
    monkeypatch.setattr(runner, '_with_historical_target_metadata', lambda rows, *_: rows)
    observed = []
    def build(rows, years):
        observed.append(years)
        return {}, {}, {}
    for owner in (dh, ant):
        monkeypatch.setattr(owner, '_build_truth_ladders', build)
        monkeypatch.setattr(owner, '_build_retention_and_zero_growth', lambda _: ({}, {}, {}))
    row = dict(family='dedicated_hunter', hunt_code='DB1770', points='0', residency='Resident',
               draw_pool='dedicated_hunter', draw_system_type='PREFERENCE_DEDICATED_HUNTER_DEER',
               algorithm_status='NO_TRANSITION_EVIDENCE', p_draw='',
               reason_codes='NO_THREE_YEAR_ENROLLMENT_EXPIRATION_EVIDENCE')
    result = preference_abstention_evidence([{'actual_draw_year': '2017'}, {'actual_draw_year': '2018'}], [row], 2017)
    assert len(result) == 1
    assert all(years == {2017} for years in observed)
    assert next(iter(result.values()))['required_expiring_cohort_draw_year'] == 2015
    monkeypatch.setattr(dh, '_build_truth_ladders', lambda *_: ({}, {}, {('dedicated_hunter', 'DB1770', 2015): {}}))
    assert not preference_abstention_evidence([{'actual_draw_year': '2017'}], [row], 2017)
    assert not preference_abstention_evidence([{'actual_draw_year': '2017'}], [dict(row, p_draw='0')], 2017)
