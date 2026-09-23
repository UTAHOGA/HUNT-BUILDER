import csv
import json

import pytest

from engine.utah.current_year_allotments import export_current_deer_allocations


def inputs(tmp_path, values=(9, 1, 10)):
    hunt = {"HuntCode": "DB1502", "HuntName": "Cache", "HuntCategoryName": "General-Season",
            "SeasonWeapons": [{"LicenseYear": 2026, "WeaponName": "Archery",
                               "SeasonStartDate": "2026-08-15", "SeasonEndDate": "2026-09-11"}],
            "ResidentRegularRoundQuota": values[0], "NonResidentRegularRoundQuota": values[1],
            "RegularRoundQuota": values[2], "OddsList": "MUST_NOT_READ_OUTCOMES"}
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"Status": 0, "Data": [hunt]}), encoding="utf-8")
    row = {"hunt_code": "DB1502", "hunt_name": "Cache", "species": "Deer", "sex_type": "Buck",
           "weapon": "Archery", "season": "Aug 15 2026 - Sep 11 2026",
           "permits_2026_res": "0", "permits_2026_nr": "0", "permits_2026_total": "20"}
    database = tmp_path / "database.csv"
    with database.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return database, source


@pytest.mark.parametrize("values", [(9, 1, 10), (9, 0, 9), (0, 0, 0)])
def test_export_exact_lanes_preserves_planner_and_inputs(tmp_path, values):
    database, source = inputs(tmp_path, values)
    before = [database.read_bytes(), source.read_bytes()]
    out = tmp_path / "export"
    report = export_current_deer_allocations(database, source, out, 2026)
    with (out / "current_general_deer_target_rows.csv").open() as handle:
        row = next(csv.DictReader(handle))
    assert row["permits_2026_total"] == "20"
    assert row["permits_2026_res"] == row["permits_2026_nr"] == "0"
    assert tuple(int(row[k]) for k in ("target_permits_res", "target_permits_nr", "target_permits_total")) == values
    with (out / "current_general_deer_residency_rows.csv").open() as handle:
        lanes = list(csv.DictReader(handle))
    assert [r["residency"] for r in lanes] == ["Resident", "Nonresident"]
    assert sum(int(r["draw_allocation"]) for r in lanes) == values[2]
    assert report["residency_total_check_count"] == 1
    assert report["drawing_outcomes_read"] is False
    assert before == [database.read_bytes(), source.read_bytes()]
    with pytest.raises(ValueError, match="already exists"):
        export_current_deer_allocations(database, source, out, 2026)


@pytest.mark.parametrize("values", [(9, 1, 20), (9, None, 9), (9, -1, 8), (9, True, 10)])
def test_bad_or_missing_split_blocks_before_outputs(tmp_path, values):
    database, source = inputs(tmp_path, values)
    out = tmp_path / "export"
    with pytest.raises(ValueError, match="Unreconciled"):
        export_current_deer_allocations(database, source, out, 2026)
    assert not out.exists()


def test_duplicate_target_blocks_before_outputs(tmp_path):
    database, source = inputs(tmp_path)
    lines = database.read_text().splitlines()
    database.write_text("\n".join(lines + lines[1:]) + "\n")
    out = tmp_path / "export"
    with pytest.raises(ValueError, match="Duplicate target"):
        export_current_deer_allocations(database, source, out, 2026)
    assert not out.exists()
