from tools.run_engine_hardening_validation_calibration import row_year


def test_row_year_prefers_explicit_target_or_truth_year_fields():
    assert row_year({"actual_draw_year": "2025", "year": "2024"}) == 2025
    assert row_year({"target_year": "2027"}) == 2027
