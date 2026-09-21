from scripts.audit_bear_controlled_candidates import (
    RESTRICTED_PURSUIT_CODES_2026,
    current_canonical_lanes_2026,
)


def test_2026_official_bear_fold_projection_is_unique_and_program_separated() -> None:
    rows = current_canonical_lanes_2026()
    keys = {(row["hunt_code"], row["residency"], row["points"]) for row in rows}

    assert len(rows) == 2814
    assert len(keys) == len(rows)
    assert {row["residency"] for row in rows} == {"Resident", "Nonresident"}
    assert sum(row["residency"] == "Resident" for row in rows) == 1407
    assert sum(row["residency"] == "Nonresident" for row in rows) == 1407

    pursuit_codes = {
        row["hunt_code"]
        for row in rows
        if row["draw_pool"] == "RESTRICTED_BEAR_PURSUIT"
    }
    limited_entry_codes = {
        row["hunt_code"]
        for row in rows
        if row["draw_pool"] == "LIMITED_ENTRY_BEAR_HUNT"
    }
    assert pursuit_codes == RESTRICTED_PURSUIT_CODES_2026
    assert len(limited_entry_codes) == 90
    assert pursuit_codes.isdisjoint(limited_entry_codes)
    assert all(row["hunt_code"] != "BR1000" for row in rows)
    assert all(row["qa_status"] == "CONFIRMED_CANONICAL_SCORABLE" for row in rows)

