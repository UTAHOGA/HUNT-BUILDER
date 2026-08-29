from scripts.project_black_bear_residency_lanes import project


def _official_lane(residency: str, classification: str) -> dict[str, str]:
    return {
        "reported_draw_year": "2018",
        "hunt_code": "BR7002",
        "hunt_name": "Cache / East Canyon",
        "residency": residency,
        "points": "0",
        "eligible_applicants": "10",
        "bonus_permits": "1",
        "regular_permits": "1",
        "total_permits": "2",
        "source_file": "pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/official_dwr_archive/black_bear/18_drawing_odds.pdf",
        "page_number": "8",
        "source_classification": classification,
    }


def test_lane_projection_preserves_retained_official_bear_identity() -> None:
    projected, counts = project(
        [
            {
                "actual_draw_year": "2018",
                "hunt_code": "BR7002",
                "hunt_name": "legacy parser text",
                "record_type": "POINT_ROW",
                "points": "0",
                "draw_design": "LIMITED_ENTRY_BEAR_HUNT",
            }
        ],
        [
            _official_lane("Resident", "TRUE_BEAR_BONUS_DRAW"),
            _official_lane("Nonresident", "TRUE_BEAR_BONUS_DRAW"),
        ],
        through_year=2018,
    )

    assert counts["official_lane_rows"] == 2
    assert len(projected) == 2
    assert {row["residency"] for row in projected} == {"Resident", "Nonresident"}
    assert {row["hunt_name"] for row in projected} == {"Cache / East Canyon"}
    assert {row["bear_source_classification"] for row in projected} == {"TRUE_BEAR_BONUS_DRAW"}
    assert {row["bear_source_identity_source"] for row in projected} == {"RETAINED_OFFICIAL_BLACK_BEAR_PDF"}
