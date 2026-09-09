from types import SimpleNamespace

from scripts.classify_historical_actual_gaps import SOURCE_CLASSIFIED, classify_gap


def test_zero_applicant_prior_rung_is_source_limitation_not_engine_coverage_defect():
    gap = {
        "draw_design_key": "BONUS_PLE_BIG_GAME",
        "draw_pool_key": "max_weighted_split",
        "hunt_code": "DB1008",
        "residency": "Nonresident",
        "points": "7",
    }
    key = (
        "BONUS_PLE_BIG_GAME",
        "max_weighted_split",
        "DB1008",
        "Nonresident",
        "7",
    )
    prior_point = SimpleNamespace(
        residency="Nonresident",
        actual_eligible_applicants=0.0,
        actual_drawn=0.0,
    )
    source_row = {
        "nonresident_eligible_applicants": "0",
        "nonresident_total_permits": "0",
        "source_file": "2024_L.E. DEER DRAW RESULTS.pdf",
    }

    classification, status, evidence = classify_gap(
        gap,
        exact_rows={key: [(prior_point, source_row)]},
        lanes={key[:4]},
        hunts={key[:3]},
    )

    assert classification == "SOURCE_LIMITATION_PRIOR_YEAR_EMPTY_POINT_RUNG"
    assert status == SOURCE_CLASSIFIED
    assert evidence["prior_year_eligible_applicants"] == 0.0
