import pytest

from engine.utah_draw_predictive.preference_antlerless import (
    _build_exact_lane_transition_profiles,
    _build_truth_ladders,
    _preference_probability,
    _target_draw_system_type,
)


FAMILY = 'PREFERENCE_ANTLERLESS_ELK'
POOL = 'general_season_antlerless_elk'


def test_two_rungs_in_one_year_pair_are_not_two_independent_transitions():
    lane = (FAMILY, 'EA1001', POOL, 'Resident')
    ladders = {
        (FAMILY, 2023, *lane[1:]): {2: {'eligible': 10, 'drawn': 0}, 3: {'eligible': 20, 'drawn': 0}},
        (FAMILY, 2024, *lane[1:]): {3: {'eligible': 2, 'drawn': 0}, 4: {'eligible': 4, 'drawn': 0}},
    }
    exact, _ = _build_exact_lane_transition_profiles(ladders)
    assert (*lane, '2_3') not in exact


def test_distinct_adjacent_year_pairs_allow_exact_band_rate():
    lane = (FAMILY, 'EA1001', POOL, 'Resident')
    ladders = {
        (FAMILY, 2022, *lane[1:]): {2: {'eligible': 10, 'drawn': 0}},
        (FAMILY, 2023, *lane[1:]): {2: {'eligible': 10, 'drawn': 0}, 3: {'eligible': 2, 'drawn': 0}},
        (FAMILY, 2024, *lane[1:]): {3: {'eligible': 2, 'drawn': 0}, 4: {'eligible': 1, 'drawn': 0}},
    }
    exact, _ = _build_exact_lane_transition_profiles(ladders)
    assert exact[(*lane, '2_3')] == 0.2


@pytest.mark.parametrize('regular', ['0', 0])
def test_explicit_zero_regular_awards_do_not_fall_back_to_total(regular):
    row = dict(year='2024', hunt_code='EA1001', hunt_name='Antlerless Elk',
               species='Elk', sex_type='Antlerless', hunt_class='Public',
               draw_system_type=FAMILY, draw_pool=POOL, residency='Resident',
               points='2', eligible_applicants='10', regular_permits=regular,
               total_permits='3', drawn='3')
    ladders, _, _ = _build_truth_ladders([row], {2024})
    assert ladders[(FAMILY, 2024, 'EA1001', POOL, 'Resident')][2]['drawn'] == 0


def test_explicit_allocation_type_private_excludes_preference_probability():
    assert _target_draw_system_type(dict(draw_system_type=FAMILY, hunt_name='Antlerless Elk',
                                        allocation_type='PRIVATE')) is None


def test_youth_source_row_cannot_enter_adult_antlerless_ladder():
    adult = dict(
        year='2024', hunt_code='EA1139', hunt_name='CWMU Antlerless Elk - Hardscrabble',
        species='Elk', sex_type='Antlerless', hunt_type='CWMU', hunt_class='CWMU',
        draw_system_type='BONUS_CWMU_BIG_GAME', draw_pool='CWMU_ANTLERLESS',
        source_is_youth='false', residency='Resident', points='1',
        eligible_applicants='12', regular_permits='2',
    )
    youth = {
        **adult,
        'source_is_youth': 'true',
        'eligible_applicants': '2',
        'regular_permits': '0',
    }

    assert _target_draw_system_type(adult) == FAMILY
    assert _target_draw_system_type(youth) is None
    ladders, _, _ = _build_truth_ladders([adult, youth], {2024})
    assert ladders[(FAMILY, 2024, 'EA1139', 'cwmu_antlerless_elk', 'Resident')][1] == {
        'eligible': 12,
        'drawn': 2,
    }


def test_legacy_youth_parent_report_cannot_enter_adult_antlerless_ladder():
    adult = dict(
        year='2017', hunt_code='EA1078', hunt_name='Antlerless Elk - Plateau',
        species='Elk', sex_type='Antlerless', hunt_class='Public',
        draw_system_type=FAMILY, draw_pool=POOL, residency='Resident', points='1',
        eligible_applicants='311', regular_permits='0',
        source_file='official_dwr_archive/big_game_antlerless/17_antlerless_points.pdf',
    )
    youth = {
        **adult,
        'eligible_applicants': '26',
        'regular_permits': '1',
        'source_is_youth': '',
        'source_file': 'official_dwr_archive/big_game_antlerless/17_antlerless_youth_points.pdf',
    }

    assert _target_draw_system_type(adult) == FAMILY
    assert _target_draw_system_type(youth) is None
    ladders, _, _ = _build_truth_ladders([adult, youth], {2017})
    assert ladders[(FAMILY, 2017, 'EA1078', POOL, 'Resident')][1] == {
        'eligible': 311,
        'drawn': 0,
    }


def test_preference_cutoff_remains_fractional():
    assert _preference_probability(10, 8, 4) == 0.5
    assert _preference_probability(10, 10, 4) == 0
    assert _preference_probability(10, 0, 4) == 1


def test_collapsed_private_allocation_stays_excluded_after_lane_expansion():
    row = dict(year='2024', hunt_code='EA1001', hunt_name='Antlerless Elk',
               species='Elk', sex_type='Antlerless', hunt_class='Public',
               draw_system_type=FAMILY, draw_pool=POOL, allocation_type='PRIVATE',
               points='2', resident_eligible_applicants='10', resident_regular_permits='2')
    ladders, _, _ = _build_truth_ladders([row], {2024})
    assert not ladders


@pytest.mark.parametrize('regular', ['0', 0])
@pytest.mark.parametrize('point', ['0', 0, '2', 2])
def test_collapsed_lane_preserves_zero_regular_awards(regular, point):
    row = dict(year='2024', hunt_code='EA1001', hunt_name='Antlerless Elk',
               species='Elk', sex_type='Antlerless', hunt_class='Public',
               draw_system_type=FAMILY, draw_pool=POOL, points=point,
               resident_eligible_applicants=10, resident_regular_permits=regular,
               resident_total_permits=3)
    ladders, _, _ = _build_truth_ladders([row], {2024})
    assert ladders[(FAMILY, 2024, 'EA1001', POOL, 'Resident')][int(point)]['drawn'] == 0


@pytest.mark.parametrize('regular', ['0', 0])
def test_normalized_explicit_and_total_rows_do_not_substitute_total(regular):
    from engine.utah_draw_predictive.preference_ladder_normalizer import normalize_preference_ladder_rows

    rows = [dict(points='2', residency='Resident', eligible_applicants=10,
                 regular_permits=regular, total_permits=3, drawn=3),
            dict(points='2', total_eligible_applicants=10,
                 total_regular_permits=regular, total_permits=3)]
    normalized = normalize_preference_ladder_rows(rows)
    assert len(normalized) == 2
    assert all(str(row['drawn']) == '0' for row in normalized)
