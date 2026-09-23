from engine.utah.quality.build_source_mapping_and_hunt_crosswalk import (
    canonical_pdf_key, prior_numeric_row_status, source_row_applicability, row_reconciliation_status,
)


def row(**changes):
    return dict(dict(hunt_code='BI6500', record_type='point_level_draw_result',
                     points='3', pdf_page='535'), **changes)


def test_unmatched_total_does_not_poison_matched_point_row():
    total = row(record_type='hunt_total_draw_result', points='')
    diffs = {canonical_pdf_key(total): [{'review_classification': 'UNVERIFIED_LAYOUT_OR_KEY'}]}
    assert prior_numeric_row_status(row(), diffs, True, True).startswith('PRIOR_NUMERIC')
    assert prior_numeric_row_status(total, diffs, True, True) == 'NOT_NUMERICALLY_VERIFIED'
    assert source_row_applicability(total) == 'AGGREGATE_NOT_POINT_RUNG'
    assert row_reconciliation_status({'NOT_NUMERICALLY_VERIFIED': 1, 'VERIFIED': 10}) == 'PARTIAL'
    assert row_reconciliation_status({'NOT_NUMERICALLY_VERIFIED': 1}) == 'UNVERIFIED'
    assert row_reconciliation_status({'VERIFIED': 10}) == 'PASS'


def test_hash_or_incomplete_accounting_cannot_verify_rows():
    assert prior_numeric_row_status(row(), {}, False, True) == 'NOT_NUMERICALLY_VERIFIED'
    assert prior_numeric_row_status(row(), {}, True, False) == 'NOT_NUMERICALLY_VERIFIED'


def test_positive_applicant_zero_outcome_still_requires_review():
    r = row(eligible_applicants='1', successful_applicants='0', bonus_permits='0',
            regular_permits='0', total_permits='0')
    assert source_row_applicability(r) == 'REQUIRES_SCORABLE_SOURCE_REVIEW'
    r['eligible_applicants'] = '0'
    assert source_row_applicability(r) == 'EMPTY_DISPLAY_NOT_SCORABLE'
    r['successful_applicants'] = ''
    assert source_row_applicability(r) == 'REQUIRES_SCORABLE_SOURCE_REVIEW'


def test_sportsman_totals_are_not_generic_hunt_totals():
    assert source_row_applicability(row(record_type='sportsman_total_draw_result')) == 'REQUIRES_SCORABLE_SOURCE_REVIEW'


def test_numeric_mismatch_is_not_accepted_as_spacing():
    diffs = {canonical_pdf_key(row()): [{'review_classification': 'VALUE_MISMATCH'}]}
    assert prior_numeric_row_status(row(), diffs, True, True) == 'NOT_NUMERICALLY_VERIFIED'
