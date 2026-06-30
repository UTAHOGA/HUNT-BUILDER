from engine.utah_draw_predictive.classifier import classify_draw_system_type, sanitize_modeled_probability_fields


def test_general_season_turkey_is_not_classified_as_bonus() -> None:
    row = {
        "hunt_code": "TK1000",
        "hunt_name": "Statewide",
        "species": "Turkey",
        "sex_type": "Bearded",
        "hunt_type": "Spring General Season",
        "p_draw": "0.50",
        "p_draw_pct": "50.0",
    }
    assert classify_draw_system_type(row) == "OTC_OR_REMAINING_TARGET"
    sanitized = sanitize_modeled_probability_fields(dict(row))
    assert sanitized["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW"
    assert sanitized["p_draw"] == ""
    assert sanitized["p_draw_pct"] == ""


def test_conservation_turkey_row_does_not_receive_draw_odds() -> None:
    row = {
        "hunt_code": "TK1012",
        "hunt_name": "Central Area",
        "species": "Turkey",
        "sex_type": "Bearded",
        "hunt_type": "Conservation",
        "p_draw": "0.50",
        "p_draw_pct": "50.0",
    }
    assert classify_draw_system_type(row) == "OTC_OR_REMAINING_TARGET"
    sanitized = sanitize_modeled_probability_fields(dict(row))
    assert sanitized["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW"
    assert sanitized["p_draw"] == ""
    assert sanitized["p_draw_pct"] == ""


def test_conservation_turkey_code_overrides_stale_youth_set_aside_label() -> None:
    row = {
        "hunt_code": "TK1012",
        "hunt_name": "Central Region",
        "species": "Turkey",
        "sex_type": "Bearded",
        "hunt_type": "Conservation",
        "hunt_class": "Organizations",
        "draw_system_type": "YOUTH_TURKEY_SET_ASIDE",
        "p_draw": "0.50",
        "p_draw_pct": "50.0",
    }
    assert classify_draw_system_type(row) == "OTC_OR_REMAINING_TARGET"
    sanitized = sanitize_modeled_probability_fields(dict(row))
    assert sanitized["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW"
    assert sanitized["p_draw"] == ""
    assert sanitized["p_draw_pct"] == ""
