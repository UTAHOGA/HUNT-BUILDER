import csv

import engine.utah_draw_predictive.run_all_families as runner
from engine.utah_draw_predictive.run_all_families import (
    _effective_draw_pool_for_family,
    _family_for_legacy_row,
    _prefix_family_guess,
    _source_backed_family_for_row,
    _source_family_for_output_row,
)


def test_reference_only_lifetime_deer_does_not_route_to_preference_general_deer() -> None:
    row = {
        "hunt_code": "DB1509",
        "hunt_name": "La Sal, La Sal Mtns",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "LIFETIME_DEER",
        "hunt_draw_class": "LIFETIME_DEER",
        "draw_design": "Preference",
        "draw_system_type": "REFERENCE_ONLY",
    }

    assert _family_for_legacy_row(row) == ""
    assert _prefix_family_guess(row) == ""


def test_crosswalk_authority_overrides_legacy_preference_routing(tmp_path, monkeypatch) -> None:
    authority_path = tmp_path / "hunt_code_crosswalk_authority_2020_2026.csv"
    with authority_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "authority_status",
                "source_year",
                "hunt_year",
                "hunt_code",
                "draw_system_type",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "authority_status": "GUIDEBOOK_AUTHORITY",
                "source_year": "2026",
                "hunt_year": "2027",
                "hunt_code": "DB0008",
                "draw_system_type": "AVAILABILITY_ONLY",
            }
        )
        writer.writerow(
            {
                "authority_status": "GUIDEBOOK_AUTHORITY",
                "source_year": "2021",
                "hunt_year": "2022",
                "hunt_code": "DB1512",
                "draw_system_type": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
            }
        )
        writer.writerow(
            {
                "authority_status": "GUIDEBOOK_AUTHORITY",
                "source_year": "2022",
                "hunt_year": "2023",
                "hunt_code": "EA1239",
                "draw_system_type": "PREFERENCE_ANTLERLESS_ELK",
            }
        )
        writer.writerow(
            {
                "authority_status": "GUIDEBOOK_AUTHORITY",
                "source_year": "2023",
                "hunt_year": "2024",
                "hunt_code": "EA1239",
                "draw_system_type": "CWMU_PRIVATE_VOUCHER",
            }
        )
        writer.writerow(
            {
                "authority_status": "GUIDEBOOK_AUTHORITY",
                "source_year": "2023",
                "hunt_year": "2024",
                "hunt_code": "PD1031",
                "draw_system_type": "CWMU_PRIVATE_VOUCHER",
            }
        )

    monkeypatch.setattr(runner, "AUTHORITY_PATH", authority_path)
    runner._crosswalk_authority_by_year_code.cache_clear()

    db0008 = {
        "actual_draw_year": "2026",
        "hunt_code": "DB0008",
        "hunt_name": "Deer Extended",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "Preference",
        "draw_design": "Preference",
    }
    db1512 = {
        "actual_draw_year": "2021",
        "hunt_code": "DB1512",
        "hunt_name": "Nine Mile",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "General Season",
        "hunt_class": "Preference",
        "draw_design": "Preference",
    }

    assert runner._family_for_legacy_row(db0008) == ""
    assert runner._family_for_legacy_row(db1512) == "preference_general_deer"
    assert runner._family_for_legacy_row(
        {
            "actual_draw_year": "2023",
            "hunt_code": "EA1239",
            "species": "Elk",
            "sex_type": "Antlerless",
            "hunt_class": "Preference",
            "draw_design": "Preference",
        }
    ) == ""
    assert runner._family_for_legacy_row(
        {
            "actual_draw_year": "2023",
            "hunt_code": "PD1031",
            "species": "Pronghorn",
            "sex_type": "Doe",
            "hunt_class": "",
            "draw_design": "Preference",
            "draw_system_type": "PREFERENCE_DOE_PRONGHORN",
        }
    ) == "preference_doe_pronghorn"


def test_pb_hunt_codes_route_to_limited_entry_not_premium_limited_entry() -> None:
    row = {
        "hunt_code": "PB5025",
        "species": "Elk",
        "hunt_type": "Limited Entry",
        "hunt_name": "Premium Limited Entry Bull Elk",
        "draw_system_type": "BONUS_LE_BIG_GAME",
    }

    assert _source_backed_family_for_row(row) == "bonus_le_big_game"


def test_le_child_pdfs_split_into_species_lanes() -> None:
    deer_row = {
        "hunt_code": "DB1201",
        "hunt_name": "Limited Entry Buck Deer",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "Limited Entry",
        "hunt_class": "Limited Entry",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "source_file": "2017_PERMITS=2018_MODEL__L.E._DEER_DRAW_RESULTS.pdf",
    }
    elk_row = {
        "hunt_code": "EB1202",
        "hunt_name": "Limited Entry Bull Elk",
        "species": "Elk",
        "sex_type": "Bull",
        "hunt_type": "Limited Entry",
        "hunt_class": "Limited Entry",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "source_file": "2017_PERMITS=2018_MODEL__L.E._ELK_DRAW_RESULTS.pdf",
    }
    pronghorn_row = {
        "hunt_code": "PB1203",
        "hunt_name": "Limited Entry Buck Pronghorn",
        "species": "Pronghorn",
        "sex_type": "Buck",
        "hunt_type": "Limited Entry",
        "hunt_class": "Limited Entry",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "source_file": "2017_PERMITS=2018_MODEL__L.E._PRONGHORN_DRAW_RESULTS.pdf",
    }

    assert _source_backed_family_for_row(deer_row) == "bonus_le_big_game"
    assert _source_backed_family_for_row(elk_row) == "bonus_le_big_game"
    assert _source_backed_family_for_row(pronghorn_row) == "bonus_le_big_game"
    assert _effective_draw_pool_for_family(deer_row, "bonus_le_big_game") == "limited_entry_deer"
    assert _effective_draw_pool_for_family(elk_row, "bonus_le_big_game") == "limited_entry_elk"
    assert _effective_draw_pool_for_family(pronghorn_row, "bonus_le_big_game") == "limited_entry_pronghorn"
    assert _source_family_for_output_row("bonus_le_big_game", deer_row) == "LE_BIG_GAME"
    assert _source_family_for_output_row("bonus_le_big_game", elk_row) == "LE_BIG_GAME"
    assert _source_family_for_output_row("bonus_le_big_game", pronghorn_row) == "LE_BIG_GAME"


def test_le_deer_unit_name_with_elk_does_not_route_to_elk_pool() -> None:
    row = {
        "hunt_code": "DB1014",
        "hunt_name": "San Juan, Elk Ridge",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "Limited Entry",
        "hunt_class": "Limited Entry",
        "draw_system_type": "BONUS_LE_BIG_GAME",
        "source_file": "2018_PERMITS=2019_MODEL__L.E._DEER_DRAW_RESULTS.pdf",
    }

    assert _effective_draw_pool_for_family(row, "bonus_le_big_game") == "limited_entry_deer"


def test_cwmu_rows_route_to_their_own_bonus_bucket() -> None:
    row = {
        "hunt_code": "DB1306",
        "hunt_name": "Washakie CWMU",
        "species": "Deer",
        "sex_type": "Buck",
        "hunt_type": "CWMU",
        "hunt_class": "CWMU",
        "draw_design": "Bonus",
        "draw_system_type": "BONUS_CWMU_BIG_GAME",
        "draw_pool": "standard",
        "source_file": "2017_PERMITS=2018_MODEL__CWMU BIG GAME DRAW RESULTS.pdf",
    }

    assert _family_for_legacy_row(row) == "bonus_cwmu_big_game"
    assert _source_backed_family_for_row(row) == "bonus_cwmu_big_game"
    assert _effective_draw_pool_for_family(row, "bonus_cwmu_big_game") == "cwmu_big_game"
    assert _source_family_for_output_row("bonus_cwmu_big_game", row) == "CWMU_BIG_GAME"
