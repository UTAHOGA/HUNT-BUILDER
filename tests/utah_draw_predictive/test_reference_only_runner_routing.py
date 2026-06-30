import csv

import engine.utah_draw_predictive.run_all_families as runner
from engine.utah_draw_predictive.run_all_families import _family_for_legacy_row, _prefix_family_guess


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
