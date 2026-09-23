import pytest

from scripts.audit_antlerless_pdf_canonical_cells import parse_line


def test_pdf_columns_preserve_both_residencies_and_zero_regular():
    row = parse_line('4 409 2 0 2 1 in 204.5 4 74 0 1 1 1 in 74.0')
    assert row['resident_eligible_applicants'] == 409
    assert row['resident_bonus_permits'] == 2
    assert row['resident_regular_permits'] == 0
    assert row['resident_total_permits'] == 2
    assert row['nonresident_regular_permits'] == 1


def test_totals_are_not_zero_point_rows():
    row = parse_line('Totals 1,313 2 2 4 1 in 328.3 Totals 245 0 1 1 1 in 245.0')
    assert row['record_type'] == 'hunt_total_draw_result'
    assert row['points'] == ''
    assert row['resident_eligible_applicants'] == 1313


def test_mismatched_point_columns_are_rejected():
    with pytest.raises(ValueError, match='alignment'):
        parse_line('4 0 0 0 0 N/A 3 0 0 0 0 N/A')


def test_missing_numeric_cell_is_not_filled():
    assert parse_line('4 0 0 0 N/A 4 0 0 0 0 N/A') is None
