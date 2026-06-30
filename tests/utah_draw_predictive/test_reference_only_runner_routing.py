from engine.utah_draw_predictive.run_all_families import _family_for_legacy_row, _prefix_family_guess


def test_reference_only_lifetime_deer_does_not_route_to_preference_general_deer() -> None:
    row = {
        "hunt_code": "DB1509",
        "hunt_name": "La Sal, La Sal Mtns",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "LIFETIME_DEER",
        "hunt_draw_class": "LIFETIME_DEER",
        "draw_design": "Preference",
        "draw_system_type": "REFERENCE_ONLY",
    }

    assert _family_for_legacy_row(row) == ""
    assert _prefix_family_guess(row) == ""
