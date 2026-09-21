import json

import pytest

from engine.utah_draw_predictive.bear import (
    LIMITED_ENTRY_BEAR_HUNT as HUNT, RESTRICTED_BEAR_PURSUIT as PURSUIT,
    _forecast_cumulative_transition_ensemble, _bear_simulation_probability,
    _forecast_adaptive_cumulative_stack, build_bear_bonus_predictions, BEAR_SPLIT_HISTORY_START,
)
from scripts.bear_grouped_uncertainty import group_indices, grouped_intervals, metric_values


def ladder(counts, wins=None):
    return {p: dict(eligible=n, total=(wins or {}).get(p, 0)) for p, n in counts.items()}


def test_one_year_removes_all_winners_and_advances_once():
    history = {(HUNT, 2020, 'BR7000', 'Resident'): ladder({0: 10, 1: 6, 2: 4}, {0: 1, 1: 3, 2: 4})}
    central, scenarios, years = _forecast_cumulative_transition_ensemble(history, HUNT, 'BR7000', 'Resident')
    assert central == {0: 10, 1: 9, 2: 3, 3: 0}
    assert scenarios == [central] and years == []


def test_same_lane_only_and_monotone_joint_stack():
    history = {(HUNT, 2020, 'BR7000', 'Resident'): ladder({0: 10, 1: 5, 2: 3}, {2: 2}),
               (HUNT, 2021, 'BR7000', 'Resident'): ladder({0: 20, 1: 8, 2: 4, 3: 1})}
    expected = _forecast_cumulative_transition_ensemble(history, HUNT, 'BR7000', 'Resident')
    for subtype, code, residency in [(PURSUIT, 'BR7000', 'Resident'), (HUNT, 'BR7000', 'Nonresident'), (HUNT, 'BR9999', 'Resident')]:
        history[(subtype, 2021, code, residency)] = ladder({0: 99999, 15: 99999})
    assert _forecast_cumulative_transition_ensemble(history, HUNT, 'BR7000', 'Resident') == expected
    central, scenarios, years = expected
    assert years == [2021] and len(scenarios) == 3
    assert all(isinstance(n, int) and n >= 0 for s in [central] + scenarios for n in s.values())


def test_missing_year_does_not_bridge_transition():
    history = {(HUNT, 2020, 'BR7000', 'Resident'): ladder({0: 999}),
               (HUNT, 2022, 'BR7000', 'Resident'): ladder({0: 2}, {0: 1})}
    assert _forecast_cumulative_transition_ensemble(history, HUNT, 'BR7000', 'Resident')[2] == []


def test_complete_scenario_probability_not_product_of_mean_components():
    # Bonus and conditional random chances covary when the whole stack shifts.
    bonus, random, joint, *_ = _bear_simulation_probability(1, [{1: 1}, {2: 1, 1: 2}], 1, 1)
    assert joint == pytest.approx(.75)
    assert joint != pytest.approx(bonus + (1 - bonus) * random)


def rows():
    return [dict(target_year=y, hunt_identity=h, program_regime='2017', residency=r,
                 points=p, predicted_probability=.2, actual_probability=a)
            for y, h, a in [(2020, 'A', .1), (2021, 'A', .3), (2021, 'B', .9)]
            for r in ('Resident', 'Nonresident') for p in (1, 2, 3)]


def test_grouped_uncertainty_keeps_both_lanes_and_points_together():
    groups = group_indices(rows(), ('target_year', 'hunt_identity', 'program_regime'))
    assert [len(g) for g in groups] == [6, 6, 6]
    assert sorted(i for group in groups for i in group) == list(range(18))
    a = grouped_intervals(rows(), ('target_year', 'hunt_identity', 'program_regime'), replicates=100)
    assert a == grouped_intervals(rows(), ('target_year', 'hunt_identity', 'program_regime'), replicates=100)
    assert a['estimable']
    assert json.loads(json.dumps(a)) == a
    assert a['populations']['Resident']['intervals_95'] == a['populations']['Nonresident']['intervals_95']


def test_empty_population_never_redrawn_or_filled():
    report = grouped_intervals([r for r in rows() if r['residency'] == 'Resident'], ('target_year',), replicates=10)
    assert report['populations']['Nonresident']['undefined_replicates'] == 10
    assert not report['estimable']
    assert metric_values([]) is None


def test_one_group_cannot_claim_independent_sample_size():
    report = grouped_intervals(rows()[:6], ('target_year',), replicates=10)
    assert report['groups'] == 1
    assert not report['estimable']


def test_adaptive_cumulative_is_source_lane_specific_and_bounded():
    history = {(HUNT, year, 'BR7000', 'Resident'): ladder({0: 10 + year - 2020, 1: 5, 2: 3}, {2: 2})
               for year in range(2020, 2024)}
    expected = _forecast_adaptive_cumulative_stack(history, HUNT, 'BR7000', 'Resident')
    history[(HUNT, 2023, 'BR7000', 'Nonresident')] = ladder({0: 99999})
    assert _forecast_adaptive_cumulative_stack(history, HUNT, 'BR7000', 'Resident') == expected
    forecast, blend, years = expected
    assert 0 <= blend <= 1 and years == [2021, 2022, 2023]
    assert all(isinstance(n, int) and n >= 0 for n in forecast.values())


@pytest.mark.parametrize('mode', ['cumulative_transition_ensemble', 'adaptive_cumulative_stack'])
@pytest.mark.parametrize('code', sorted(BEAR_SPLIT_HISTORY_START))
def test_new_demand_modes_do_not_restore_split_history(mode, code):
    from tests.utah_draw_predictive.test_bear_pdf_controlled_replay import lane
    history = [lane('BR7008', 2025), lane(code, 2025)]
    rows, _ = build_bear_bonus_predictions(history, [lane(code, 2026)], 2026, [2025], demand_mode=mode)
    assert len(rows) == 2
    assert all(r['p_draw'] == '' and r['algorithm_status'] == 'NO_TRANSITION_EVIDENCE' for r in rows)


def test_cumulative_model_cannot_mix_another_arrival_model():
    with pytest.raises(ValueError, match='second arrival model'):
        build_bear_bonus_predictions([], [], 2026, [2025], demand_mode='adaptive_cumulative_stack',
                                    returning_cohort_mode='lane_cohort_hierarchical')


def test_frozen_scorer_uses_exact_bytes_and_original_resource_root(tmp_path):
    from scripts.audit_bear_controlled_candidates import load_selected_scorer, ROOT, digest
    source = tmp_path / 'scorer.py'
    source.write_text('from pathlib import Path\nREPO = Path(__file__).resolve().parents[2]\nVALUE = 19\n')
    module = load_selected_scorer(source, digest(source))
    assert module.REPO == ROOT and module.VALUE == 19
    with pytest.raises(ValueError, match='hash changed'):
        load_selected_scorer(source, 'wrong')
