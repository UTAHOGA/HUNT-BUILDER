from __future__ import annotations

from engine.utah_draw_predictive.run_all_families import (
    _drop_total_scope_bear_guarantees_when_source_backed,
)


def _bear_row(**overrides: str) -> dict[str, str]:
    row = {
        "source_family": "BEAR_DRAW_RESULTS",
        "hunt_code": "BR7003",
        "residency": "Resident",
        "metric_scope": "resident",
        "points": "7",
        "algorithm_status": "MODELED_BONUS",
        "source_file": "",
        "data_quality_flags": "FIRST_CHOICE_ONLY_MODEL|TOTAL_SCOPE_HISTORY_USED_FOR_RESIDENCY",
        "p_draw_mean": "1.000000",
    }
    row.update(overrides)
    return row


def test_exact_source_backed_bear_lane_replaces_total_scope_residency_model() -> None:
    broad_model = _bear_row(draw_pool="black_bear")
    source_backed = _bear_row(
        draw_pool="max_weighted_split",
        algorithm_status="MODELED_SOURCE_BACKED_ROLL_FORWARD",
        source_file="2021 Bear Draw Results.pdf",
        data_quality_flags="",
        p_draw_mean="0.333333",
    )

    rows, dropped = _drop_total_scope_bear_guarantees_when_source_backed([broad_model, source_backed])

    assert dropped == 1
    assert rows == [source_backed]


def test_lane_specific_bear_model_is_not_removed() -> None:
    lane_specific_model = _bear_row(data_quality_flags="FIRST_CHOICE_ONLY_MODEL")
    source_backed = _bear_row(
        algorithm_status="MODELED_SOURCE_BACKED_ROLL_FORWARD",
        source_file="2021 Bear Draw Results.pdf",
        data_quality_flags="",
        p_draw_mean="0.333333",
    )

    rows, dropped = _drop_total_scope_bear_guarantees_when_source_backed([lane_specific_model, source_backed])

    assert dropped == 0
    assert rows == [lane_specific_model, source_backed]


def test_blocked_source_without_probability_does_not_remove_modeled_row() -> None:
    broad_model = _bear_row()
    blocked_source = _bear_row(
        algorithm_status="NOT_SCORED_SOURCE_ROLL_FORWARD_GUARANTEE_BLOCKED",
        source_file="2021 Bear Draw Results.pdf",
        data_quality_flags="",
        p_draw_mean="",
    )

    rows, dropped = _drop_total_scope_bear_guarantees_when_source_backed([broad_model, blocked_source])

    assert dropped == 0
    assert rows == [broad_model, blocked_source]


def test_zero_source_probability_does_not_override_modeled_guarantee() -> None:
    broad_model = _bear_row()
    zero_source = _bear_row(
        algorithm_status="MODELED_SOURCE_BACKED_ROLL_FORWARD",
        source_file="2021 Bear Draw Results.pdf",
        data_quality_flags="",
        p_draw_mean="0.000000",
    )

    rows, dropped = _drop_total_scope_bear_guarantees_when_source_backed([broad_model, zero_source])

    assert dropped == 0
    assert rows == [broad_model, zero_source]


def test_non_guarantee_total_scope_model_is_not_removed() -> None:
    broad_model = _bear_row(p_draw_mean="0.750000")
    source_backed = _bear_row(
        algorithm_status="MODELED_SOURCE_BACKED_ROLL_FORWARD",
        source_file="2021 Bear Draw Results.pdf",
        data_quality_flags="",
        p_draw_mean="0.333333",
    )

    rows, dropped = _drop_total_scope_bear_guarantees_when_source_backed([broad_model, source_backed])

    assert dropped == 0
    assert rows == [broad_model, source_backed]
