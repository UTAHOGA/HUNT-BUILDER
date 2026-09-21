"""Fail-closed regression checks for the isolated PDF truth audit."""
import copy
import csv

import pytest

from scripts.audit_bear_pdf_truth_year import compare_canonical, number, parse_table
from scripts.build_bear_pdf_history_audit import transition_status


def table():
    return [
        ["1", "3", "1", "1", "2", "1 in 1.5", "1", "0", "0", "0", "0", "N/A"],
        ["0", "5", "0", "1", "1", "1 in 5.0", "0", "2", "0", "1", "1", "1 in 2.0"],
        ["0"] + [None] * 11,
        ["Totals", "8", "1", "2", "3", "1 in 2.7", "Totals", "2", "0", "1", "1", "1 in 2.0"],
    ]


def test_separate_lanes_printed_totals_and_empty_artifact():
    rows, totals, artifacts = parse_table(table(), 1)
    assert len(rows) == 4
    assert len(totals) == 2
    assert len(artifacts) == 1
    assert rows[0]["eligible_applicants"] == 3
    assert rows[1]["eligible_applicants"] == 0
    assert rows[1]["observed_success_fraction"] == ""
    assert not any("p_draw" in row for row in rows)


@pytest.mark.parametrize("value", [None, "", "N/A", "abc", "-1", "1.5", "1,2"])
def test_missing_or_malformed_count_is_not_invented_zero(value):
    with pytest.raises(ValueError):
        number(value)


def test_published_comma_integer():
    assert number("1,234") == 1234


def test_2022_empty_column_does_not_shift_residency():
    original = [row for row in table() if row[1] is not None]
    shifted = [row[:1] + [None] + row[1:] for row in original]
    assert parse_table(shifted, 1)[:2] == parse_table(original, 1)[:2]


def test_2023_split_cells_use_single_published_number_not_sum():
    original = [row for row in table() if row[1] is not None]
    split = [row[:2] + [None, row[2], None] + [row[3], None, None] + row[4:] for row in original]
    assert parse_table(split, 1)[:2] == parse_table(original, 1)[:2]
    split[0][2] = "9"
    with pytest.raises(ValueError, match="Ambiguous"):
        parse_table(split, 1)


def test_missing_cohort_and_all_winners_abstain_without_claiming_zero_applicants():
    assert transition_status(None, 4)[0] == "NO_TRANSITION_EVIDENCE"
    status, reason = transition_status({"eligible_applicants": "5", "total_permits": "5"}, 4)
    assert status == "NO_TRANSITION_EVIDENCE"
    assert "unsuccessful" in reason
    assert transition_status({"eligible_applicants": "5", "total_permits": "2"}, 4)[0] == "SOURCE_COHORT_PRESENT_NOT_PROVEN_SAME_HUNT_RETURN"
    assert transition_status(None, 0)[0] == "ZERO_POINT_ENTRY_REQUIRES_SEPARATE_DEMAND_EVIDENCE"


@pytest.mark.parametrize("defect", ["wrong_lane", "missing_rung", "duplicate_rung", "bad_sum", "bad_total", "bad_ratio", "extra_artifact", "new_shape"])
def test_bad_source_cannot_be_silently_accepted(defect):
    rows = copy.deepcopy(table())
    if defect == "wrong_lane":
        rows[0][6] = "0"
    elif defect == "missing_rung":
        rows.pop(0)
    elif defect == "duplicate_rung":
        rows.insert(1, rows[0])
    elif defect == "bad_sum":
        rows[0][4] = "3"
    elif defect == "bad_total":
        rows[-1][1] = "9"
        rows[-1][5] = "1 in 3.0"
    elif defect == "bad_ratio":
        rows[0][5] = "1 in 3.0"
    elif defect == "extra_artifact":
        rows.insert(2, ["0"] + [None] * 11)
    else:
        rows[0].append(None)
    with pytest.raises(ValueError):
        parse_table(rows, 1)


def test_comparison_does_not_hide_residency_swap_or_program_mismatch(tmp_path):
    point_rows, total_rows, _ = parse_table(table(), 1)
    common = {"hunt_code": "BR1008", "hunt_name": "Book Cliffs - Pursuit", "species": "Black Bear",
              "draw_pool": "RESTRICTED_BEAR_PURSUIT", "pdf_page": 3,
              "source_file": "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/black_bear/20_drawing_odds.pdf"}
    points = [{**common, **row, "record_type": "point_level_draw_result"} for row in point_rows]
    totals = [{**common, **row, "record_type": "hunt_total_draw_result"} for row in total_rows]
    canonical_rows = []
    for left, right in zip((points + totals)[::2], (points + totals)[1::2]):
        row = {**common, "actual_draw_year": 2020, "points": left["points"], "record_type": left["record_type"]}
        for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits"):
            row["resident_" + field] = left[field]
            row["nonresident_" + field] = right[field]
            row[field] = left[field] + right[field]
            if field != "total_permits":
                row["total_" + field] = row[field]
        canonical_rows.append(row)

    path = tmp_path / "canonical.csv"

    def write():
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=canonical_rows[0])
            writer.writeheader()
            writer.writerows(canonical_rows)

    write()
    assert compare_canonical(points, totals, path, 2020)["status"] == "PASS"
    canonical_rows[0]["resident_eligible_applicants"] = 0
    canonical_rows[0]["nonresident_eligible_applicants"] = 3
    canonical_rows[0]["draw_pool"] = "LIMITED_ENTRY_BEAR_HUNT"
    write()
    result = compare_canonical(points, totals, path, 2020)
    assert result["status"] == "REVIEW_REQUIRED"
    assert {entry["field"] for entry in result["mismatches"]} == {
        "resident_eligible_applicants", "nonresident_eligible_applicants", "draw_pool"}
