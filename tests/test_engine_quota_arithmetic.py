from tools.run_engine_hardening_validation_calibration import safe_float


def test_safe_float_handles_quota_style_numbers():
    assert safe_float("1,234") == 1234
    assert safe_float("12.5%") == 12.5
    assert safe_float("unlimited") is None
