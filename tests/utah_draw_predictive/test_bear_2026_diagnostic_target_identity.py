from engine.utah_draw_predictive import bear as bear_module
from engine.utah_draw_predictive import run_all_families as run_module


def _current_row(code: str, res: str, nr: str) -> dict[str, str]:
    return {
        "hunt_code": code,
        "hunt_name": "La Sal Mtns" if code != "BR7021" else "Dolores Triangle",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "hunt_class": "Max/Weighted Split",
        "weapon": "Any Legal Weapon",
        "permits_2026_res": res,
        "permits_2026_nr": nr,
        "permits_2026_total": str(int(res) + int(nr)),
    }


def test_2025_to_2026_bear_identity_bridge_adds_only_reviewed_current_codes(monkeypatch) -> None:
    current_rows = [
        _current_row("BR7022", "40", "3"),
        _current_row("BR7127", "25", "2"),
        _current_row("BR7239", "6", "0"),
        _current_row("BR7326", "13", "1"),
        _current_row("BR7021", "2", "0"),
        _current_row("BR7126", "6", "0"),
        _current_row("BR7238", "2", "0"),
    ]
    monkeypatch.setattr(run_module, "_read_runtime_database_rows", lambda: current_rows)

    rows = run_module._with_2026_bear_diagnostic_target_identity_rows(
        [{"hunt_code": "BR7008", "species": "Black Bear"}],
        source_year=2025,
        target_year=2026,
    )
    by_code = {row["hunt_code"]: row for row in rows}

    assert set(by_code) == {"BR7008", "BR7022", "BR7127", "BR7239", "BR7326", "BR7021", "BR7126", "BR7238"}
    assert by_code["BR7022"]["bear_crosswalk_parent_hunt_code"] == "BR7008"
    assert by_code["BR7326"]["bear_crosswalk_parent_hunt_code"] == "BR7307"
    assert by_code["BR7021"]["bear_target_identity_status"] == "CURRENT_NEW_UNIT_NO_COMPARABLE_HISTORY"
    assert by_code["BR7022"]["target_identity_diagnostic"] == "CURRENT_2026_BEAR_IDENTITY_BRIDGE"


def test_new_bear_unit_is_visible_but_never_receives_an_invented_probability(monkeypatch) -> None:
    monkeypatch.setattr(bear_module, "official_bear_draw_odds_hunt_codes", lambda: set())
    monkeypatch.setattr(bear_module, "official_bear_pursuit_hunt_codes", lambda: set())

    rows, _ = bear_module.build_bear_bonus_predictions(
        truth_rows=[],
        db_rows=[dict(_current_row("BR7021", "2", "0"), bear_target_identity_status="CURRENT_NEW_UNIT_NO_COMPARABLE_HISTORY")],
        forecast_year=2026,
        history_years=[2025],
    )

    resident = next(row for row in rows if row["residency"] == "Resident")
    assert resident["p_draw"] == ""
    assert resident["algorithm_status"] == "NOT_SCORED_NEW_UNIT_NO_COMPARABLE_HISTORY"
    assert "NOT_SCORED_NEW_UNIT_NO_COMPARABLE_HISTORY" in resident["reason_codes"]


def test_target_identity_bridge_is_declared_instead_of_passing_as_source_only() -> None:
    row = run_module._leakage_row(
        2025,
        2026,
        "bonus_bear",
        [{"source_years_used": "2018,2019,2020,2021,2022,2023,2024,2025", "target_identity_diagnostic": "CURRENT_2026_BEAR_IDENTITY_BRIDGE"}],
    )

    assert row["current_year_authority_file_used"] == "true"
    assert row["target_identity_diagnostic_used"] == "true"
    assert row["leakage_status"] == "DECLARED_CURRENT_TARGET_IDENTITY_DIAGNOSTIC"
