from __future__ import annotations

import pytest

from scripts.audit_antlerless_raw_certainty import audit, raw_preference_probability


def row(**overrides: str) -> dict[str, str]:
    result = {
        "fold": "2023_to_2024",
        "draw_design": "PREFERENCE_ANTLERLESS_ELK",
        "hunt_code": "EA1001",
        "residency": "Nonresident",
        "points": "4",
        "draw_pool_key": "preference_antlerless_elk",
        "forecast_public_permits_target": "3",
        "forecast_applicants_above": "1",
        "forecast_applicants_at_level": "2",
        "predicted_probability": "0.995",
        "actual_probability": "0.5",
    }
    result.update(overrides)
    return result


def test_display_ceiling_does_not_hide_raw_certainty_miss() -> None:
    summary, affected = audit([row()])
    assert raw_preference_probability(row()) == 1.0
    assert summary["raw_certainty_misses"] == 1
    assert summary["masked_by_display_calibration"] == 1
    assert summary["by_design_hunt_class"] == {"PREFERENCE_ANTLERLESS_ELK|UNKNOWN": 1}
    assert affected[0]["raw_preference_probability"] == "1.000000"


def test_mixed_cutoff_and_actual_guarantee_are_not_misses() -> None:
    mixed = row(forecast_public_permits_target="2", points="3")
    actual_guarantee = row(points="5", actual_probability="1.0")
    summary, affected = audit([mixed, actual_guarantee])
    assert summary["raw_certainty_misses"] == 0
    assert affected == []


def test_duplicate_scoring_key_fails_closed() -> None:
    with pytest.raises(ValueError, match="Repeated exact scoring key"):
        audit([row(), row()])
