from __future__ import annotations

from engine.utah.models import ApplicationUnit, DrawState, Hunt, Quota, UtahRuleConfig
from engine.utah.simulator import run_simulation_once


HUNT_CODE = "DB2001"


def _unit(application_id: str, residency: str, points: int) -> ApplicationUnit:
    return ApplicationUnit(
        application_unit_id=application_id,
        member_application_ids=(application_id,),
        member_customer_ids_hashed=(f"customer_{application_id}",),
        group_id=None,
        group_size=1,
        residency=residency,
        species="mule deer",
        hunt_choices=(HUNT_CODE,),
        effective_points=points,
        point_type="bonus",
        youth_only_flag=False,
        valid_flag=True,
        eligible_flag=True,
        random_ticket_count=1 + points,
    )


def _state(
    units: tuple[ApplicationUnit, ...],
    *,
    resident_quota: int,
    nonresident_quota: int,
    crossover_allowed: bool,
) -> DrawState:
    state = DrawState(
        draw_year=2026,
        hunt=Hunt(hunt_code=HUNT_CODE, species="mule deer", hunt_type="limited_entry", rule_system="bonus"),
        quota=Quota(
            draw_year=2026,
            hunt_code=HUNT_CODE,
            species="mule deer",
            total_public_permits=resident_quota + nonresident_quota,
            resident_quota=resident_quota,
            nonresident_quota=nonresident_quota,
            # These combined counters reproduce the old defect. The corrected
            # simulator must derive the round allocation within each lane.
            reserved_quota=2,
            random_quota=1,
            crossover_allowed=crossover_allowed,
            quota_source="fixture",
        ),
        application_units=units,
        rule_config=UtahRuleConfig.default(),
    )
    return state


def _latest_results(state: DrawState) -> dict[str, object]:
    result = run_simulation_once(state, seed=7)
    return {item.application_unit_id: item for item in result.results}


def test_nonresident_lane_completes_before_resident_crossover() -> None:
    rows = _latest_results(
        _state(
            (_unit("resident_high", "Resident", 20), _unit("nonresident", "Nonresident", 0)),
            resident_quota=0,
            nonresident_quota=1,
            crossover_allowed=True,
        )
    )

    assert rows["nonresident"].drawn_flag is True
    assert rows["nonresident"].draw_stage == "random_bonus"
    assert rows["resident_high"].drawn_flag is False


def test_one_permit_nonresident_bonus_lane_is_random() -> None:
    rows = _latest_results(
        _state(
            (_unit("nonresident", "Nonresident", 12),),
            resident_quota=0,
            nonresident_quota=1,
            crossover_allowed=False,
        )
    )

    assert rows["nonresident"].drawn_flag is True
    assert rows["nonresident"].draw_stage == "random_bonus"
    assert "BONUS_RANDOM_SELECTED" in rows["nonresident"].reason_codes


def test_crossover_runs_only_after_separate_lane_rounds_leave_a_permit() -> None:
    rows = _latest_results(
        _state(
            (_unit("resident", "Resident", 4),),
            resident_quota=0,
            nonresident_quota=1,
            crossover_allowed=True,
        )
    )

    assert rows["resident"].drawn_flag is True
    assert rows["resident"].draw_stage == "crossover_bonus"
    assert "CROSSOVER_AFTER_SEPARATE_RESIDENCY_EVALUATION" in rows["resident"].reason_codes


def test_no_crossover_leaves_other_residency_permit_unconsumed() -> None:
    rows = _latest_results(
        _state(
            (_unit("resident", "Resident", 4),),
            resident_quota=0,
            nonresident_quota=1,
            crossover_allowed=False,
        )
    )

    assert "resident" not in rows


def test_each_lane_has_its_own_max_and_random_round() -> None:
    rows = _latest_results(
        _state(
            (
                _unit("resident_max", "Resident", 20),
                _unit("resident_random", "Resident", 0),
                _unit("nonresident", "Nonresident", 0),
            ),
            resident_quota=2,
            nonresident_quota=1,
            crossover_allowed=True,
        )
    )

    assert rows["resident_max"].draw_stage == "reserved_bonus"
    assert rows["resident_random"].draw_stage == "random_bonus"
    assert rows["nonresident"].draw_stage == "random_bonus"

