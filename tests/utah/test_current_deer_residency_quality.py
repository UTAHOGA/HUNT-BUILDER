from copy import deepcopy

import pytest

from engine.utah.quality.verify_current_deer_residencies import audit, verify_rows
from engine.utah_draw_predictive import bear


def sample():
    expected = [{"hunt_code": "DB1592", "target_permits_res": "97", "target_permits_nr": "10",
                 "target_permits_total": "107", "target_permits_scope": "REGULAR_DRAW_AFTER_PROGRAM_ALLOCATIONS",
                 "target_permits_source_sha256": "measured"}]
    lanes = [{"hunt_code": "DB1592", "residency": residency, "draw_allocation": allocation,
              "draw_allocation_total": "107", "scope": expected[0]["target_permits_scope"],
              "source_sha256": "measured"}
             for residency, allocation in (("Resident", "97"), ("Nonresident", "10"))]
    planner = [{"hunt_code": "DB1592", "hunt_year": "2026", "permits_2026_total": "200"}]
    return expected, lanes, planner


@pytest.mark.parametrize("code,res,nr,planner_total", [
    ("DB1592", 97, 10, 200),
    ("DB1630", 349, 39, 720),
])
def test_separate_totals_are_not_summed_or_required_to_match(code, res, nr, planner_total):
    expected, lanes, planner = sample()
    expected[0].update(hunt_code=code, target_permits_res=str(res),
                       target_permits_nr=str(nr), target_permits_total=str(res + nr))
    for lane, allocation in zip(lanes, (res, nr)):
        lane.update(hunt_code=code, draw_allocation=str(allocation),
                    draw_allocation_total=str(res + nr))
    planner[0].update(hunt_code=code, permits_2026_total=str(planner_total))
    review, failures = verify_rows(deepcopy(expected), lanes, expected, planner, 2026)
    assert failures == []
    assert review[0]["planner_hunt_total"] == planner_total
    assert review[0]["regular_draw_allocation"] == res + nr
    assert review[0]["resident_regular"] + review[0]["nonresident_regular"] == res + nr
    assert review[0]["planner_regular_difference_status"] == "REFERENCE_TOTAL_DIFFERENCE_NON_BLOCKING"
    assert review[0]["totals_are_additive"] is False


@pytest.mark.parametrize("mutation", ["missing_lane", "duplicate_lane", "wrong_number", "wrong_total", "wrong_source", "old_planner", "extra_hunt"])
def test_quality_gate_rejects_bad_staging(mutation):
    expected, lanes, planner = sample()
    if mutation == "missing_lane":
        lanes.pop()
    elif mutation == "duplicate_lane":
        lanes.append(dict(lanes[0]))
    elif mutation == "wrong_number":
        lanes[1]["draw_allocation"] = "103"
    elif mutation == "wrong_total":
        lanes[1]["draw_allocation_total"] = "200"
    elif mutation == "wrong_source":
        lanes[1]["source_sha256"] = "other"
    elif mutation == "old_planner":
        planner[0]["hunt_year"] = "2025"
    else:
        lanes.append({**lanes[0], "hunt_code": "DB9999"})
    assert verify_rows(deepcopy(expected), lanes, expected, planner, 2026)[1]


def test_new_bear_hunts_are_allowed_without_inventing_predecessors(monkeypatch):
    monkeypatch.setattr(bear, "_parse_official_bear_draw_odds_pdf", lambda: {})
    assert bear.BEAR_NEW_HUNT_GUIDEBOOK_PAGES_2026 == {"BR7021": 73, "BR7126": 74, "BR7238": 75}
    for code in bear.BEAR_NEW_HUNT_GUIDEBOOK_PAGES_2026:
        assert code in bear.official_bear_draw_odds_hunt_codes()
        assert code not in bear.BEAR_HISTORY_CODE_ALIASES_2026
        assert code not in bear.official_bear_pursuit_hunt_codes()


def test_missing_input_and_import_failure_stay_blocked(tmp_path, monkeypatch):
    def broken_import(name):
        raise ImportError("missing identity validator")
    monkeypatch.setattr("engine.utah.quality.verify_current_deer_residencies.importlib.import_module", broken_import)
    result = audit(tmp_path / "missing", tmp_path / "planner", tmp_path / "authority")
    assert result["data_status"] == "BLOCKED"
    assert result["failures"]
    assert result["bear_import_status"] == "FAIL"
    assert result["promotion_status"] == "BLOCKED_LOCAL_STAGING_ONLY"
