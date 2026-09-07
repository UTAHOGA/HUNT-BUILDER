from engine.utah_draw_predictive.run_all_families import _available_history_years


def test_history_selection_preserves_an_official_pre_2018_audit_predecessor() -> None:
    rows = [
        {"actual_draw_year": "2017"},
        {"actual_draw_year": "2018"},
        {"actual_draw_year": "2019"},
    ]

    assert _available_history_years(rows, 2018) == [2017, 2018]


def test_history_selection_keeps_normal_series_behavior_when_2017_is_absent() -> None:
    rows = [
        {"actual_draw_year": "2018"},
        {"actual_draw_year": "2019"},
        {"actual_draw_year": "2020"},
    ]

    assert _available_history_years(rows, 2019) == [2018, 2019]
