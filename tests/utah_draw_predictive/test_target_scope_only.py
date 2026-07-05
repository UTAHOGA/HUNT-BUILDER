from engine.utah_draw_predictive.classifier import classify_draw_system_type, is_target_scope


def test_target_scope_keeps_turkey_bear_and_cougar() -> None:
    turkey = {"hunt_type": "Limited Entry", "species": "Turkey", "sex_type": "Bearded"}
    bear = {"hunt_type": "Limited Entry - Fall", "species": "Black Bear", "sex_type": "Either Sex"}
    cougar = {"hunt_type": "Limited Entry", "species": "Cougar"}
    assert is_target_scope(turkey) is True
    assert is_target_scope(bear) is True
    assert is_target_scope(cougar) is True
    assert classify_draw_system_type(turkey) == "BONUS_TURKEY"
    assert classify_draw_system_type(bear) == "BEAR_DRAW"
    assert classify_draw_system_type(cougar) == "COUGAR_LICENSE_BASED"


def test_target_scope_keeps_private_lands_only_antlerless_elk() -> None:
    row = {"hunt_type": "General Season - Private Land Only", "species": "Elk", "sex_type": "Antlerless", "hunt_name": "Private Lands Only Antlerless Elk"}
    assert is_target_scope(row) is True
    assert classify_draw_system_type(row) == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"
