from __future__ import annotations

from engine.utah_bonus_predictive.materialize import _apply_current_target_design, _deduplicate_prediction_identities


def test_prediction_identity_resolution_prefers_current_max_weighted_target() -> None:
    legacy = {
        "hunt_code": "DB1000", "residency": "Resident", "points": "0", "draw_system_type": "BONUS_PLE_BIG_GAME",
        "p_draw": "0.000000", "reason_codes": "BONUS_RULE_SIMULATED|DRAW_POOL_LIMITED_ENTRY_DEER",
    }
    target = {
        "hunt_code": "DB1000", "residency": "Resident", "points": "0", "draw_system_type": "BONUS_PLE_BIG_GAME",
        "p_draw": "0.000760", "forecast_applicants_at_level": "38",
        "reason_codes": "BONUS_RULE_SIMULATED|DRAW_POOL_MAX_WEIGHTED_SPLIT",
    }

    resolved, audit = _deduplicate_prediction_identities([legacy, target], surface="test")

    assert resolved == [target]
    assert len(audit) == 1
    assert audit[0]["resolution"] == "CURRENT_TARGET_DRAW_POOL_PRECEDENCE"
    assert audit[0]["kept_probability"] == "0.000760"


def test_current_planner_design_overrides_retired_historical_hunt_label() -> None:
    rows = _apply_current_target_design(
        [
            {
                "hunt_code": "DB1058",
                "hunt_name": "Management Rifle Cactus Buck Deer",
                "species": "Deer",
                "hunt_type": "Limited Entry",
                "draw_pool": "limited_entry",
                "p_draw": "0.2",
            }
        ],
        [
            {
                "hunt_code": "DB1058",
                "hunt_name": "Paunsaugunt",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "Limited Entry",
                "hunt_class": "Preference",
                "weapon": "Any Legal Weapon",
                "draw_pool": "max_weighted_split",
                "draw_design": "MAX_WEIGHTED_SPLIT",
            }
        ],
    )
    assert rows[0]["hunt_name"] == "Paunsaugunt"
    assert rows[0]["draw_system_type"] == "BONUS_LE_BIG_GAME"
