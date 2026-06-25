from engine.utah_draw_predictive.classifier import classify_draw_system_type, sanitize_modeled_probability_fields
from engine.utah_draw_predictive.turkey import build_youth_turkey_predictions
from engine.utah_draw_predictive.youth import build_youth_predictions


def test_youth_rows_do_not_accidentally_classify_as_bonus_or_adult_preference() -> None:
    youth_deer = {
        "hunt_code": "DB1501",
        "hunt_name": "Box Elder",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "General-season Archery Buck Deer",
        "weapon": "Archery",
        "draw_pool": "youth",
        "source_file": "2025 Youth G.S. Deer Draw Results.pdf",
    }
    youth_elk = {
        "hunt_code": "EB1011",
        "hunt_name": "Youth General Season Bull Elk",
        "species": "Elk",
        "sex_type": "Bull",
        "hunt_type": "General Season - Youth",
        "hunt_class": "General Bull",
        "weapon": "Any Legal Weapon",
        "source_file": "DATABASE.csv",
    }
    assert classify_draw_system_type(youth_deer) != "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
    assert classify_draw_system_type(youth_elk) not in {"BONUS_OIL_BIG_GAME", "BONUS_LE_BIG_GAME", "BONUS_PLE_BIG_GAME"}
    assert classify_draw_system_type(youth_elk) == "YOUTH_OTC_OR_AVAILABILITY"


def test_raw_youth_turkey_source_rows_wait_for_materializer() -> None:
    row = {
        "hunt_code": "TK1003",
        "hunt_name": "Central Region",
        "species": "Turkey",
        "hunt_type": "Limited Entry",
        "hunt_class": "Youth",
        "draw_pool": "youth_turkey",
        "draw_design": "Max/Weighted Split",
        "source_file": "2025_PERMITS=2026_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
        "source_dataset": "predictive",
        "p_draw": "0.50",
        "p_bonus_pool": "0.25",
        "p_random_pool": "0.25",
    }

    classified = sanitize_modeled_probability_fields(dict(row))

    assert classify_draw_system_type(row) == "YOUTH_TURKEY_SET_ASIDE"
    assert classified["algorithm_status"] == "IN_SCOPE_MODEL_PENDING"
    assert classified["p_draw"] == ""
    assert classified["p_bonus_pool"] == ""
    assert classified["p_random_pool"] == ""


def test_materialized_youth_turkey_uses_bonus_set_aside_model() -> None:
    truth_rows = [
        {
            "year": "2025",
            "actual_draw_year": "2025",
            "hunt_code": "TK1003",
            "hunt_name": "Central Region",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "source_file": "2025_PERMITS=2026_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
            "residency": "Resident",
            "points": "1",
            "eligible_applicants": "10",
            "bonus_permits": "1",
            "regular_permits": "1",
            "total_permits": "2",
        },
        {
            "year": "2025",
            "actual_draw_year": "2025",
            "hunt_code": "TK1003",
            "hunt_name": "Central Region",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "source_file": "2025_PERMITS=2026_MODEL__YOUTH TURKEY DRAW RESULTS.pdf",
            "residency": "Resident",
            "points": "0",
            "eligible_applicants": "25",
            "bonus_permits": "0",
            "regular_permits": "3",
            "total_permits": "3",
        },
    ]
    db_rows = [
        {
            "hunt_code": "TK1003",
            "hunt_name": "Central Region",
            "species": "Turkey",
            "hunt_type": "Limited Entry",
            "hunt_class": "Max/Weighted Split",
            "permits_2026_total": "100",
        }
    ]

    rows, report = build_youth_turkey_predictions(truth_rows, db_rows, 2026, [2025])
    modeled = [sanitize_modeled_probability_fields(dict(row)) for row in rows if row.get("residency") == "Resident"]

    assert report["youth_turkey_modeled_rows"] > 0
    assert all(row["draw_system_type"] == "YOUTH_TURKEY_SET_ASIDE" for row in modeled)
    assert all(row["algorithm_status"] == "MODELED_BONUS" for row in modeled)
    assert any((row.get("p_draw") or "").strip() for row in modeled)
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in modeled)


def test_youth_artifact_rows_do_not_use_bonus_or_preference_fields() -> None:
    rows, _report = build_youth_predictions(
        [],
        [
            {
                "hunt_code": "EB1007",
                "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
                "species": "Elk",
                "sex_type": "Bull",
                "hunt_type": "General Season - Any Bull",
                "hunt_class": "Youth",
                "weapon": "Any Legal Weapon",
                "season": "Sept 12 2026 - Sept 22 2026",
                "permits_2026_total": "750",
            }
        ],
        2026,
        [2025],
    )
    assert all((row.get("p_bonus_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_random_pool") or "").strip() == "" for row in rows)
    assert all((row.get("p_preference_draw") or "").strip() == "" for row in rows)
