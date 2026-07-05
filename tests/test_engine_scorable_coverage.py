from tools.run_engine_hardening_validation_calibration import scorable_reason


def test_scorable_reason_accepts_complete_probability_row():
    row = {"hunt_code": "DB1000", "year": "2025", "residency": "Resident", "points": "3", "p_draw": "0.5"}
    assert scorable_reason(row) == ""


def test_scorable_reason_rejects_missing_probability_or_counts():
    row = {"hunt_code": "DB1000", "year": "2025", "residency": "Resident", "points": "3"}
    assert scorable_reason(row) == "missing_applicants"
