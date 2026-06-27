from __future__ import annotations

import csv
from pathlib import Path

from engine.utah.point_ladder_pool import format_historical_draw_result


REPO = Path(__file__).resolve().parents[2]
LADDER = REPO / "processed_data" / "point_ladder_view.csv"
RESEARCH_HTML = REPO / "research.html"


def _ladder_row(hunt_code: str, residency: str, points: int) -> dict[str, str]:
    with LADDER.open(newline="", encoding="utf-8-sig") as handle:
        rows = csv.DictReader(handle)
        return next(
            row
            for row in rows
            if row["hunt_code"] == hunt_code
            and row["residency"] == residency
            and int(float(row["points"])) == points
        )


def test_rows_with_dwr_na_and_zero_permits_render_blank_not_not_available():
    row = _ladder_row("EB3024", "Resident", 28)
    assert row["total_permits"] == "0"
    assert row["success_ratio"] == ""
    assert row["display_2025_draw_results"] == ""
    assert row["dwr_result_display"] == ""
    assert row["display_2025_draw_results"] != "Not available"
    assert format_historical_draw_result(21, 0, "N/A") == ""


def test_rows_below_max_boundary_with_permits_are_historical_random_successes():
    row = _ladder_row("EB3024", "Resident", 12)
    assert row["max_point_pool_boundary"] == "29"
    assert row["random_pool_start_point"] == "28"
    assert row["point_pool_zone"] == "random_pool"
    assert row["historical_result_pool"] == "random_pool"
    assert row["bonus_permits"] == "0"
    assert row["regular_permits"] == "1"
    assert row["total_permits"] == "1"
    assert row["display_2025_draw_results"] == "~1 in 49.0 or 2.0%"


def test_historical_random_successes_do_not_become_max_point_guarantees():
    row = _ladder_row("EB3024", "Resident", 12)
    assert row["display_2026_max_point_pool"] == ""
    assert row["display_2026_random_draw"]
    assert row["display_2026_random_draw"] != row["display_2025_draw_results"]


def test_2026_random_draw_blank_above_random_pool_boundary():
    assert _ladder_row("EB3024", "Resident", 30)["display_2026_random_draw"] == ""
    assert _ladder_row("EB3024", "Resident", 29)["point_pool_zone"] == "max_pool_cutoff_mixed"
    assert _ladder_row("EB3024", "Resident", 29)["display_2026_random_draw"] != ""


def test_2026_random_draw_populated_at_and_below_boundary_from_model():
    row_28 = _ladder_row("EB3024", "Resident", 28)
    row_12 = _ladder_row("EB3024", "Resident", 12)
    assert row_28["point_pool_zone"] == "random_pool"
    assert row_28["display_2026_random_draw"].startswith("~1 in ")
    assert row_28["random_draw_model_source"] == "p_random_pool"
    assert row_12["display_2026_random_draw"].startswith("~1 in ")
    assert row_12["display_2026_random_draw"] != "~1 in 49.0 or 2.0%"


def test_2026_max_point_pool_populated_only_for_modeled_max_point_rows():
    row_30 = _ladder_row("EB3024", "Resident", 30)
    row_29 = _ladder_row("EB3024", "Resident", 29)
    row_28 = _ladder_row("EB3024", "Resident", 28)
    row_31 = _ladder_row("EB3024", "Resident", 31)
    assert row_30["point_pool_zone"] == "max_pool_guaranteed"
    assert row_29["point_pool_zone"] == "max_pool_cutoff_mixed"
    assert row_30["display_2026_max_point_pool"] == "~1 in 1 or 100%"
    assert row_29["display_2026_max_point_pool"] == "~1 in 7 or 14.3%"
    assert row_28["display_2026_max_point_pool"] == ""
    assert row_31["display_2026_max_point_pool"] == ""


def test_2026_ladder_uses_rolled_forward_applicant_stack_and_official_quota():
    row_29 = _ladder_row("EB3024", "Resident", 29)
    assert row_29["forecast_applicants_at_level"] == "21"
    assert row_29["forecast_applicants_above"] == "2"
    assert row_29["quota_source_status"] == "official"
    assert row_29["p_max_pool_mean"] == "0.142857"
    assert "APPLICANT_STACK_ROLLED_FORWARD" in row_29["reason_codes"]
    assert "MIXED_MAX_POINT_CUTOFF" in row_29["reason_codes"]


def test_eb3038_live_mixed_cutoff_contract_is_covered():
    row_19 = _ladder_row("EB3038", "Resident", 19)
    row_20 = _ladder_row("EB3038", "Resident", 20)
    row_21 = _ladder_row("EB3038", "Resident", 21)

    assert row_20["projected_2026_max_cutoff_point"] == "20.0"
    assert row_20["projected_2026_random_pool_start_point"] == "19"
    assert row_19["point_pool_zone"] == "random_pool"
    assert row_20["point_pool_zone"] == "max_pool_cutoff_mixed"
    assert row_21["point_pool_zone"] == "max_pool_guaranteed"
    assert row_19["display_2026_max_point_pool"] == ""
    assert row_19["display_2026_random_draw"].startswith("~1 in ")
    assert row_20["display_2026_max_point_pool"].startswith("~1 in ")
    assert row_20["display_2026_random_draw"].startswith("~1 in ")
    assert row_21["display_2026_max_point_pool"] == "~1 in 1 or 100%"
    assert row_21["display_2026_random_draw"] == ""
    assert row_20["quota_source_status"] == "official"
    assert "MIXED_MAX_POINT_CUTOFF" in row_20["reason_codes"]
    assert "APPLICANT_STACK_ROLLED_FORWARD" in row_20["reason_codes"]


def test_ladder_preserves_dwr_historical_result_fields():
    row = _ladder_row("EB3024", "Resident", 12)
    for field in (
        "point",
        "residency",
        "applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
        "success_ratio",
        "dwr_result_display",
    ):
        assert field in row


def test_guaranteed_ladder_line_uses_requested_orange_and_brown_box():
    text = RESEARCH_HTML.read_text(encoding="utf-8")
    assert "--guaranteed-line-orange: rgb(250, 120, 0);" in text
    assert "--highlight-outline-brown: rgb(55, 34, 22);" in text
    assert ".report-table tbody tr.is-guaranteed-row" in text
    assert "background: var(--guaranteed-line-orange);" in text
    assert "box-shadow: inset 0 0 0 2px var(--highlight-outline-brown);" in text
