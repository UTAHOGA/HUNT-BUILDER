"""DB0008 draw evidence must not become random odds from a weapon label."""
import json
from pathlib import Path

from engine.utah_draw_predictive.classifier import classify_draw_system_type
from engine.utah_draw_predictive.preference_general_deer import _build_truth_ladders

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'pipeline/RAW/hunt_unit_database/2026/json/draw_results/utahdraws_2026_20260902/utahdraws_2026/json/2026_big_game_05_general_season_buck_deer.json'


def row(**extra):
    return dict(hunt_code='DB0008', hunt_name='Deer Extended Archery Only',
                species='Deer', sex_type='Buck', hunt_type='General Season',
                weapon='Archery', **extra)


def test_general_deer_weapon_is_not_a_random_design():
    assert classify_draw_system_type(row()) == 'PREFERENCE_GENERAL_SEASON_BUCK_DEER'


def test_retained_endpoint_is_preference_with_distinct_pools():
    hunts = json.loads(SOURCE.read_text(encoding='utf-8'))['Data']
    matches = [h for h in hunts if h['HuntCode'] == 'DB0008']
    assert len(matches) == 1
    hunt = matches[0]
    assert hunt['IsBonusPoint'] is False
    assert hunt['PointCalculationTypeID'] == 1
    assert {r['IsYouth'] for r in hunt['OddsList']} == {False, True}


def test_adult_ladder_does_not_admit_youth_or_reference_rows():
    common = dict(draw_system_type='PREFERENCE_GENERAL_SEASON_BUCK_DEER',
                  year='2026', residency='Resident', points='0',
                  eligible_applicants='3', total_permits='1')
    adult = row(**common, draw_pool='adult_general_deer')
    youth = row(**common, draw_pool='youth_general_deer')
    reference = dict(adult, draw_system_type='AVAILABILITY_ONLY', total_permits='2000')
    ladders, _, _ = _build_truth_ladders([adult, youth, reference], {2026})
    assert len(ladders) == 1
    cell = next(iter(ladders.values()))[0]
    assert cell == {'eligible': 3, 'drawn': 1}
