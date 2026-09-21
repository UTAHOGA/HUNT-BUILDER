"""Exercise the builder and identity gate, not pre-edited saved report counts."""
from copy import deepcopy

import pytest

from engine.utah_draw_predictive import bear
from engine.utah_draw_predictive.classifier import sanitize_modeled_probability_fields


def targets():
    return [
        {"hunt_code": "BI1000", "hunt_name": "Sportsman Bison", "species": "Bison", "hunt_type": "Sportsman"},
        {"hunt_code": "BR1001", "hunt_name": "Harvest Objective Units", "species": "Black Bear", "hunt_type": "O.T.C.", "weapon": "Any Legal Weapon"},
        {"hunt_code": "BR1007", "hunt_name": "Pursuit", "species": "Black Bear", "hunt_type": "O.T.C.", "weapon": "Pursuit Only"},
        {"hunt_code": "BR1018", "hunt_name": "Pursuit", "species": "Black Bear", "hunt_type": "O.T.C.", "weapon": "Pursuit Only"},
    ]


def build(source):
    rows, report = bear.build_bear_bonus_predictions([], source, 2026, [2025])
    return [sanitize_modeled_probability_fields(dict(row)) for row in rows], report


def test_fresh_bear_availability_has_bear_identity_and_exact_residency_lanes():
    source = targets()
    original = deepcopy(source)
    rows, report = build(iter(source))
    assert source == original
    assert [(r["hunt_code"], r["residency"], r["hunt_name"]) for r in rows] == [
        ("BR1001", "Resident", "Harvest Objective Units"),
        ("BR1001", "Nonresident", "Harvest Objective Units"),
        ("BR1007", "Resident", "Pursuit"),
        ("BR1018", "Nonresident", "Pursuit"),
    ]
    assert all(r["species"] == "Black Bear" and r["algorithm_status"] == "MODELED_AVAILABILITY" for r in rows)
    assert all(r[field] == "" for r in rows for field in ("p_draw", "p_draw_pct", "p_bonus_pool", "p_random_pool", "p_preference_draw"))
    assert report["bear_rows_by_algorithm_status"]["MODELED_AVAILABILITY"] == len(rows) == 4
    assert report["duplicate_key_count"] == 0
    rows[0]["hunt_name"] = "Changed test copy"
    assert rows[1]["hunt_name"] == "Harvest Objective Units"


def test_restricted_and_limited_entry_rows_do_not_fall_through_or_become_availability(monkeypatch):
    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", lambda: {"BR1008", "BR7000"})
    monkeypatch.setattr(bear, "official_bear_pursuit_hunt_codes", lambda: {"BR1008"})
    source = targets() + [
        {"hunt_code": "BR1008", "hunt_name": "Book Cliffs", "species": "Black Bear", "weapon": "Pursuit Only", "hunt_type": "Pursuit"},
        {"hunt_code": "BR7000", "hunt_name": "Beaver", "species": "Black Bear", "hunt_type": "Limited Entry"},
        {"hunt_code": "BR9998", "hunt_name": "Unverified Pursuit", "species": "Black Bear", "hunt_type": "Pursuit", "weapon": "Pursuit Only"},
        {"hunt_code": "BR9999", "hunt_name": "Unverified Harvest Objective", "species": "Black Bear", "hunt_type": "Harvest Objective"},
    ]
    rows, report = build(source)
    assert {r["hunt_code"] for r in rows} == {r["hunt_code"] for r in source if r["species"] == "Black Bear"}
    assert sum(r["algorithm_status"] == "MODELED_AVAILABILITY" for r in rows) == 4
    assert report["bear_rows_by_algorithm_status"]["MODELED_AVAILABILITY"] == 4
    assert all(r["bear_draw_subtype"] == bear.RESTRICTED_BEAR_PURSUIT for r in rows if r["hunt_code"] == "BR1008")
    assert all(r["bear_draw_subtype"] == bear.LIMITED_ENTRY_BEAR_HUNT for r in rows if r["hunt_code"] == "BR7000")
    assert all(r["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW" for r in rows if r["hunt_code"] in {"BR9998", "BR9999"})


@pytest.mark.parametrize("change", [
    {"hunt_name": "Sportsman Bison"}, {"species": "Bison"},
    {"residency": "Resident"}, {"bear_draw_subtype": bear.LIMITED_ENTRY_BEAR_HUNT},
    {"p_draw": "0.5"}, {"p_draw": 0}, {"hunt_code": "BR7000"},
])
def test_availability_gate_rejects_cross_species_wrong_lane_program_or_probability(change):
    rows, _ = build(targets())
    rows[-1].update(change)
    with pytest.raises(ValueError):
        bear.validate_bear_availability_identity(rows, targets())


def test_availability_gate_rejects_duplicate_resident_row():
    rows, _ = build(targets())
    rows[1] = dict(rows[0])
    with pytest.raises(ValueError, match="Duplicate"):
        bear.validate_bear_availability_identity(rows, targets())


def test_builder_rejects_bison_template_as_bear_target():
    source = targets()
    source[1].update(hunt_name="Sportsman Bison", species="Bison")
    with pytest.raises(ValueError, match="target identity"):
        build(source)
