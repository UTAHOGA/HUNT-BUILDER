import math

from engine.utah_draw_predictive.sportsman import build_sportsman_predictions


def test_sportsman_random_only_contract() -> None:
    rows, report = build_sportsman_predictions([], [], 2026, [2025])

    assert len(rows) == 10
    assert report["sportsman_code_count_guardrail"] == "PASS"
    assert report["sportsman_draw_design"] == "SPORTSMAN_RANDOM_ONLY"
    assert report["sportsman_random_only"] is True
    assert report["sportsman_split_draw"] is False
    assert report["sportsman_residency_scope"] == "RESIDENT_ONLY"
    assert report["nonresident_row_count"] == 0
    assert report["nonresident_quota_total"] == 0

    assert {row["hunt_code"] for row in rows} == {
        "BI1000",
        "BR1000",
        "DB0007",
        "DS1000",
        "EB1000",
        "GO1000",
        "MB1000",
        "PB1000",
        "RS0001",
        "TK0001",
    }
    assert all(row["draw_system_type"] == "SPORTSMAN_PERMIT" for row in rows)
    assert all(row["model_strategy"] == "SPORTSMAN_RANDOM_ONLY" for row in rows)
    assert all(row["sportsman_residency_scope"] == "RESIDENT_ONLY" for row in rows)
    assert all(row["sportsman_random_only"] == "TRUE" for row in rows)
    assert all(row["sportsman_split_draw"] == "FALSE" for row in rows)
    assert all(row["sportsman_nonresident_quota"] == "0" for row in rows)
    assert all(row["p_bonus_pool"] == "" for row in rows)
    assert all(row["p_random_pool"] == "" for row in rows)
    assert all(row["p_preference_draw"] == "" for row in rows)

    for row in rows:
        applicants = int(row["sportsman_applicants"])
        permit_count = int(row["sportsman_permit_count"])
        expected = permit_count / applicants
        assert permit_count == 1
        assert math.isclose(float(row["p_sportsman_draw"]), expected, rel_tol=0, abs_tol=1e-6)
        assert math.isclose(float(row["p_draw"]), expected, rel_tol=0, abs_tol=1e-6)
