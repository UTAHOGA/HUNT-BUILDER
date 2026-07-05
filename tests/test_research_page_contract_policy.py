from tools.validate_research_page_canonical_contract import classify_extra_code, recommended_fix_for_classification


def test_bonus_point_purchase_only_codes_are_not_stale_hunt_codes():
    assert classify_extra_code("BER", {}, set(), set()) == "bonus_point_purchase_only"
    assert classify_extra_code("GDR", {}, set(), set()) == "bonus_point_purchase_only"


def test_cougar_reporting_codes_collapse_to_cg9999_policy():
    assert classify_extra_code("CG0001", {}, set(), set()) == "terminated_crosswalk_to_CG9999"
    assert "CG9999" in recommended_fix_for_classification("terminated_crosswalk_to_CG9999")


def test_ea1287_is_terminated_for_current_2026_runtime():
    assert classify_extra_code("EA1287", {}, set(), set()) == "terminated_2026"
