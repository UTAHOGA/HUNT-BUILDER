from __future__ import annotations

from engine.utah_draw_predictive.dedicated_hunter import build_preference_dedicated_hunter_predictions
from engine.utah_draw_predictive.preference_antlerless import build_preference_antlerless_predictions
from engine.utah_draw_predictive.preference_general_deer import build_preference_general_deer_predictions


def _split_truth_row(
    *,
    year: int,
    hunt_code: str,
    hunt_name: str,
    species: str,
    sex_type: str,
    hunt_type: str = "General Season",
    hunt_class: str = "Public",
    weapon: str = "Any Legal Weapon",
    draw_pool: str = "standard",
    points: str = "0",
) -> dict[str, str]:
    return {
        "actual_draw_year": str(year),
        "year": str(year),
        "hunt_code": hunt_code,
        "hunt_name": hunt_name,
        "species": species,
        "sex_type": sex_type,
        "hunt_type": hunt_type,
        "hunt_class": hunt_class,
        "weapon": weapon,
        "draw_pool": draw_pool,
        "points": points,
        "resident_eligible_applicants": "100",
        "resident_regular_permits": "20",
        "resident_total_permits": "20",
        "resident_p_draw": "0.200000",
        "resident_p_draw_percent": "20.000",
        "nonresident_eligible_applicants": "25",
        "nonresident_regular_permits": "3",
        "nonresident_total_permits": "3",
        "nonresident_p_draw": "0.120000",
        "nonresident_p_draw_percent": "12.000",
        "total_eligible_applicants": "125",
        "total_regular_permits": "23",
        "total_permits": "23",
        "total_p_draw": "0.184000",
        "total_p_draw_percent": "18.400",
        "source_residencies": "Resident; Nonresident",
        f"permits_{year}_res": "20",
        f"permits_{year}_nr": "3",
        f"permits_{year}_total": "23",
        "source_file": f"{year}_official_draw_results.pdf",
    }


def _assert_historical_rows(rows: list[dict[str, object]], source_year: int) -> None:
    assert rows
    assert all(str(row.get("p_draw", "")).strip() for row in rows)
    assert all(str(row.get("p_draw_pct", "")).strip() for row in rows)
    assert all(str(row.get("model_strategy", "")).strip() for row in rows)
    assert {row.get("preference_model_valid") for row in rows} == {"TRUE"}
    assert all(str(source_year) in str(row.get("source_years_used", "")) for row in rows)
    assert all(str(row.get("source_file", "")).find("2026") == -1 for row in rows)
    assert all(str(row.get("reason_codes", "")).find("2026") == -1 for row in rows)
    assert all(row.get("applicants_at_level") != 1 for row in rows if row.get("probability_applicant_count") == 1)


def test_2018_to_2019_preference_families_use_source_year_permits_without_2026() -> None:
    source_year = 2018
    target_year = 2019
    general_rows = build_preference_general_deer_predictions(
        truth_rows=[
            _split_truth_row(
                year=source_year,
                hunt_code="DB1501",
                hunt_name="Box Elder General Season Buck Deer",
                species="Deer",
                sex_type="Buck",
                weapon="Rifle",
            )
        ],
        db_rows=[
            {
                "hunt_code": "DB1501",
                "hunt_name": "Box Elder General Season Buck Deer",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "weapon": "Rifle",
                "permits_2018_total": "23",
            }
        ],
        forecast_year=target_year,
        history_years=[source_year],
    )
    antlerless_rows = build_preference_antlerless_predictions(
        truth_rows=[
            _split_truth_row(
                year=source_year,
                hunt_code="EA1001",
                hunt_name="Central Mountains Antlerless Elk",
                species="Elk",
                sex_type="Antlerless",
            )
        ],
        db_rows=[
            {
                "hunt_code": "EA1001",
                "hunt_name": "Central Mountains Antlerless Elk",
                "species": "Elk",
                "sex_type": "Antlerless",
                "hunt_type": "General Season",
                "weapon": "Any Legal Weapon",
                "permits_2018_total": "23",
            }
        ],
        forecast_year=target_year,
        history_years=[source_year],
    )
    dedicated_rows = build_preference_dedicated_hunter_predictions(
        truth_rows=[
            _split_truth_row(
                year=source_year,
                hunt_code="DB1770",
                hunt_name="Box Elder Dedicated Hunter Buck Deer",
                species="Deer",
                sex_type="Buck",
                hunt_class="Dedicated Hunter",
                weapon="Dedicated Hunter",
                draw_pool="dedicated_hunter",
            )
        ],
        db_rows=[
            {
                "hunt_code": "DB1770",
                "hunt_name": "Box Elder Dedicated Hunter Buck Deer",
                "species": "Deer",
                "sex_type": "Buck",
                "hunt_type": "General Season",
                "hunt_class": "DEDICATED_HUNTER_DEER",
                "weapon": "Dedicated Hunter",
                "draw_pool": "dedicated_hunter",
                "permits_2018_total": "23",
            }
        ],
        forecast_year=target_year,
        history_years=[source_year],
    )

    _assert_historical_rows(general_rows, source_year)
    _assert_historical_rows(antlerless_rows, source_year)
    _assert_historical_rows(dedicated_rows, source_year)


def test_2019_to_2020_ready_preference_families_use_2019_source_permits() -> None:
    source_year = 2019
    target_year = 2020
    truth_rows = [
        _split_truth_row(year=source_year, hunt_code="DB1501", hunt_name="Box Elder General Season Buck Deer", species="Deer", sex_type="Buck"),
        _split_truth_row(year=source_year, hunt_code="DA1001", hunt_name="Cache Antlerless Deer", species="Deer", sex_type="Antlerless"),
        _split_truth_row(year=source_year, hunt_code="EA1001", hunt_name="Central Mountains Antlerless Elk", species="Elk", sex_type="Antlerless"),
        _split_truth_row(year=source_year, hunt_code="PB5001", hunt_name="West Desert Doe Pronghorn", species="Pronghorn", sex_type="Doe"),
        _split_truth_row(
            year=source_year,
            hunt_code="DB1770",
            hunt_name="Box Elder Dedicated Hunter Buck Deer",
            species="Deer",
            sex_type="Buck",
            hunt_class="Dedicated Hunter",
            weapon="Dedicated Hunter",
            draw_pool="dedicated_hunter",
        ),
    ]
    db_rows = [
        {"hunt_code": "DB1501", "hunt_name": "Box Elder General Season Buck Deer", "species": "Deer", "sex_type": "Buck", "hunt_type": "General Season", "permits_2019_total": "23"},
        {"hunt_code": "DA1001", "hunt_name": "Cache Antlerless Deer", "species": "Deer", "sex_type": "Antlerless", "hunt_type": "General Season", "permits_2019_total": "23"},
        {"hunt_code": "EA1001", "hunt_name": "Central Mountains Antlerless Elk", "species": "Elk", "sex_type": "Antlerless", "hunt_type": "General Season", "permits_2019_total": "23"},
        {"hunt_code": "PB5001", "hunt_name": "West Desert Doe Pronghorn", "species": "Pronghorn", "sex_type": "Doe", "hunt_type": "General Season", "permits_2019_total": "23"},
        {"hunt_code": "DB1770", "hunt_name": "Box Elder Dedicated Hunter Buck Deer", "species": "Deer", "sex_type": "Buck", "hunt_type": "General Season", "hunt_class": "DEDICATED_HUNTER_DEER", "weapon": "Dedicated Hunter", "draw_pool": "dedicated_hunter", "permits_2019_total": "23"},
    ]

    general_rows = build_preference_general_deer_predictions(truth_rows, db_rows, target_year, [source_year])
    antlerless_rows = build_preference_antlerless_predictions(truth_rows, db_rows, target_year, [source_year])
    dedicated_rows = build_preference_dedicated_hunter_predictions(truth_rows, db_rows, target_year, [source_year])

    assert general_rows
    assert dedicated_rows
    assert [row for row in antlerless_rows if row["draw_system_type"] == "PREFERENCE_ANTLERLESS_DEER"]
    assert [row for row in antlerless_rows if row["draw_system_type"] == "PREFERENCE_ANTLERLESS_ELK"]
    assert [row for row in antlerless_rows if row["draw_system_type"] == "PREFERENCE_DOE_PRONGHORN"]
    _assert_historical_rows(general_rows + antlerless_rows + dedicated_rows, source_year)

