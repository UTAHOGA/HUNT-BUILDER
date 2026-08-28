from __future__ import annotations

from engine.utah_draw_predictive.run_all_families import (
    _historical_source_year_runtime_db_rows,
    _source_backed_probability_rows,
)
from engine.utah_draw_predictive.turkey import (
    _remaining_applicants_after_max_pool,
    _weighted_without_replacement_probabilities,
)


def _turkey_total(*, source_is_youth: str, resident: int, nonresident: int) -> dict[str, object]:
    return {
        "record_type": "HUNT_TOTAL",
        "hunt_code": "TK1003",
        "hunt_name": "Limited-entry turkey",
        "species": "Turkey",
        "hunt_type": "Limited Entry",
        "draw_pool": "youth_turkey" if source_is_youth == "true" else "preference_point",
        "source_is_youth": source_is_youth,
        "resident_total_permits": str(resident),
        "nonresident_total_permits": str(nonresident),
        "total_permits": str(resident + nonresident),
        "source_file": "official_turkey_draw_results.pdf",
    }


def test_historical_proxy_keeps_adult_and_youth_turkey_quotas_separate() -> None:
    rows = _historical_source_year_runtime_db_rows(
        [
            _turkey_total(source_is_youth="false", resident=250, nonresident=12),
            _turkey_total(source_is_youth="true", resident=37, nonresident=3),
        ],
        2019,
    )

    assert len(rows) == 2
    by_identity = {str(row["historical_proxy_pool_identity"]): row for row in rows}
    adult = by_identity["bonus_turkey:preference_point"]
    youth = by_identity["youth_turkey:youth_turkey"]
    assert adult["forecast_permits_res"] == "250"
    assert adult["forecast_permits_nr"] == "12"
    assert youth["forecast_permits_res"] == "37"
    assert youth["forecast_permits_nr"] == "3"


def test_weighted_turkey_selection_is_without_replacement_and_per_applicant() -> None:
    # One permit has exact per-applicant ticket odds: one point has two tickets,
    # zero points has one.  The old formula incorrectly used the whole group
    # weight as one applicant's probability.
    one_permit = _weighted_without_replacement_probabilities({0: 1, 1: 1}, 1)
    assert one_permit == {0: 1 / 3, 1: 2 / 3}

    # Every application can be selected at most once; if all remaining
    # applications are awarded, every applicant has a 100% chance.
    assert _weighted_without_replacement_probabilities({0: 2, 5: 1}, 3) == {0: 1.0, 5: 1.0}

    remaining = _remaining_applicants_after_max_pool({3: 1, 0: 1}, 1)
    assert remaining == {3: 0, 0: 1}
    assert _weighted_without_replacement_probabilities(remaining, 1)[0] == 1.0


def test_source_roll_forward_cannot_emit_copied_guarantee() -> None:
    source_rows = [
        {
            "record_type": "POINT",
            "hunt_code": "EB3127",
            "hunt_name": "Limited-entry elk",
            "species": "Elk",
            "hunt_type": "Limited Entry",
            "draw_system_type": "MAX_WEIGHTED_SPLIT",
            "draw_pool": "max_weighted_split",
            "residency": "Resident",
            "points": "22",
            "p_draw": "1.0",
            "source_file": "official_limited_entry_draw_results.pdf",
        }
    ]

    row = _source_backed_probability_rows(source_rows, {}, 2020, 2021)["bonus_le_big_game"][0]
    assert row["p_draw"] == ""
    assert row["p_draw_mean"] == ""
    assert row["prediction_status"] == "NOT_SCORED"
    assert row["reason_codes"] == "SOURCE_BACKED_PUBLISHED_POINT_PROBABILITY_ROLL_FORWARD_GUARANTEE_BLOCKED"
