from engine.utah_bonus_predictive.materialize import _point_sort_key


def test_point_sort_key_accepts_numeric_and_reference_labels() -> None:
    values = ["TOTAL", "2", "0;1;2;TOTAL", "1", ""]

    assert sorted(values, key=_point_sort_key) == ["", "1", "2", "0;1;2;TOTAL", "TOTAL"]

