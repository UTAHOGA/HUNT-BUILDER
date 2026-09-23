from scripts.audit_2026_pdf_probability_semantics import missing_zero_outcome


def row(**changes):
    return dict(record_type='point_level_draw_result', residency='Resident',
                eligible_applicants='12', total_permits='0', **changes)


def test_explicit_source_verified_zero_award_is_missing_outcome():
    assert missing_zero_outcome(row(), 'ENDPOINT_POPULATED_FIELDS_MATCH')


def test_unverified_source_cannot_supply_zero():
    assert not missing_zero_outcome(row(), 'ENDPOINT_IDENTITY_MISSING_OR_AMBIGUOUS')


def test_empty_and_missing_count_cells_are_not_zero_observations():
    for changes in ({'eligible_applicants': '0'}, {'eligible_applicants': ''}, {'total_permits': ''}):
        data = row()
        data.update(changes)
        assert not missing_zero_outcome(data, 'ENDPOINT_POPULATED_FIELDS_MATCH')


def test_existing_zero_and_reference_row_are_not_missing_point_outcomes():
    assert not missing_zero_outcome(row(p_draw='0'), 'ENDPOINT_POPULATED_FIELDS_MATCH')
    data = row()
    data['record_type'] = 'hunt_planner_permit_reference'
    assert not missing_zero_outcome(data, 'ENDPOINT_POPULATED_FIELDS_MATCH')
