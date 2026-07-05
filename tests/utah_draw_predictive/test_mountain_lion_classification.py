from engine.utah_draw_predictive.classifier import classify_draw_system_type, resolve_algorithm_status


def test_mountain_lion_classification() -> None:
    row = {"hunt_type": "Limited Entry", "species": "Mountain Lion", "sex_type": ""}
    assert classify_draw_system_type(row) == "COUGAR_LICENSE_BASED"
    assert resolve_algorithm_status(row) == "REFERENCE_LICENSE_BASED_NO_DRAW"
