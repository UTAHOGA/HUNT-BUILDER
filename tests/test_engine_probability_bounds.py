from tools.run_engine_hardening_validation_calibration import probability_from_row


def test_probability_from_decimal_and_percent_columns_is_bounded_decimal():
    assert probability_from_row({"p_draw": "0.25"}) == 0.25
    assert probability_from_row({"p_draw_percent": "25"}) == 0.25
    assert probability_from_row({"eligible_applicants": "4", "total_permits": "1"}) == 0.25
