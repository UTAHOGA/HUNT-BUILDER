from engine.utah_draw_predictive.classifier import classify_draw_system_type


def test_oil_le_ple_big_game_rows_continue_to_classify_as_bonus() -> None:
    assert classify_draw_system_type({"hunt_type": "Once-in-a-lifetime", "species": "Moose", "sex_type": "Bull"}) == "BONUS_OIL_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Elk", "sex_type": "Bull"}) == "BONUS_LE_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Premium Limited Entry", "species": "Deer", "sex_type": "Buck"}) == "BONUS_PLE_BIG_GAME"


def test_turkey_bear_and_cougar_remain_target_scope() -> None:
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Turkey", "sex_type": "Bearded"}) == "BONUS_TURKEY"
    assert classify_draw_system_type({"hunt_type": "Limited Entry - Fall", "species": "Black Bear", "sex_type": "Either Sex"}) == "BEAR_DRAW"
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Cougar", "sex_type": ""}) == "MOUNTAIN_LION_DRAW"


def test_antlerless_moose_and_ewe_bighorn_can_classify_as_bonus() -> None:
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Moose", "sex_type": "Antlerless"}) == "BONUS_ANTLERLESS_MOOSE"
    assert classify_draw_system_type({"hunt_type": "General Season", "species": "Rocky Mountain Bighorn Sheep", "sex_type": "Ewe"}) == "BONUS_EWE_BIGHORN"


def test_private_lands_only_antlerless_elk_classifies_separately() -> None:
    row = {"hunt_type": "General Season - Private Land Only", "species": "Elk", "sex_type": "Antlerless", "hunt_name": "Private Lands Only Antlerless Elk"}
    assert classify_draw_system_type(row) == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"


def test_hams_hamss_and_late_limited_entry_route_to_bonus_not_general_preference() -> None:
    assert classify_draw_system_type({"hunt_type": "Limited Entry HAMSS", "species": "Deer", "sex_type": "Buck", "weapon": "HAMSS"}) == "BONUS_LE_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Limited Entry HAMS", "species": "Elk", "sex_type": "Bull", "weapon": "HAMS"}) == "BONUS_LE_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Deer", "sex_type": "Buck", "weapon": "Muzzleloader Late"}) == "BONUS_LE_BIG_GAME"


def test_restricted_weapon_general_deer_and_limited_entry_deer_stay_separate() -> None:
    assert classify_draw_system_type({"hunt_type": "General Season", "species": "Deer", "sex_type": "Buck", "weapon": "Restricted Rifle"}) == "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Deer", "sex_type": "Buck", "weapon": "Restricted Archery"}) == "BONUS_LE_BIG_GAME"


def test_nine_mile_otc_bison_and_sportsman_bison_do_not_enter_oil_bison() -> None:
    assert classify_draw_system_type({"hunt_code": "BI6527", "hunt_name": "Nine Mile", "hunt_type": "Over the Counter", "species": "Bison", "sex_type": "Hunter's Choice"}) == "OTC_OR_REMAINING_TARGET"
    assert classify_draw_system_type({"hunt_code": "BI1000", "hunt_name": "Sportsman Bison", "hunt_type": "Sportsman", "hunt_class": "Statewide Permit", "species": "Bison", "sex_type": "Hunter's Choice"}) == "SPORTSMAN_PERMIT"


def test_bighorn_species_and_turkey_acquisition_methods_do_not_merge() -> None:
    assert classify_draw_system_type({"hunt_type": "Once-in-a-lifetime", "species": "Desert Bighorn Sheep", "sex_type": "Ram"}) == "BONUS_OIL_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Once-in-a-lifetime", "species": "Rocky Mountain Bighorn Sheep", "sex_type": "Ram"}) == "BONUS_OIL_BIG_GAME"
    assert classify_draw_system_type({"hunt_type": "Limited Entry", "species": "Turkey", "sex_type": "Bearded"}) == "BONUS_TURKEY"
    assert classify_draw_system_type({"hunt_type": "Spring General Season", "species": "Turkey", "sex_type": "Bearded"}) == "OTC_OR_REMAINING_TARGET"
    assert classify_draw_system_type({"hunt_type": "Fall Management", "species": "Turkey", "sex_type": "Either Sex"}) == "OTC_OR_REMAINING_TARGET"
