from scripts.build_certified_research_contract_release_manifest import schema_compatibility


def test_only_proven_empty_row_probability_placeholders_may_leave_container():
    old = {"kind": "json_object", "top_level_keys": ["details_by_hunt_code", "certified_p_draw"],
           "empty_top_level_keys": ["certified_p_draw"]}
    new = {"kind": "json_object", "top_level_keys": ["details_by_hunt_code"]}
    result = schema_compatibility(old, new)
    assert result["compatible"]
    assert result["removed_empty_container_probability_placeholders"] == ["certified_p_draw"]
    assert not schema_compatibility({**old, "empty_top_level_keys": []}, new)["compatible"]
    assert not schema_compatibility({**old, "top_level_keys": ["details_by_hunt_code", "source_index"],
                                     "empty_top_level_keys": ["source_index"]}, new)["compatible"]
    assert not schema_compatibility(old, {**new, "top_level_keys": []})["compatible"]


def test_prediction_release_does_not_refresh_harvest_context():
    from scripts.build_certified_research_contract_candidate import merge_row
    base = {"hunt_code": "DB1510", "residency": "Resident", "harvest_quality_index": "64", "hunter_satisfaction": ""}
    prediction = {"harvest_quality_index": "71", "hunter_satisfaction": "4.5", "harvest_new_measure": "8"}
    result = merge_row(base, prediction)
    assert result["harvest_quality_index"] == "64"
    assert result["hunter_satisfaction"] == ""
    assert "harvest_new_measure" not in result
