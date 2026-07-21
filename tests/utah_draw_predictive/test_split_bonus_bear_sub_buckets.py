from __future__ import annotations

from scripts.split_bonus_bear_sub_buckets import (
    HARVEST_OBJECTIVE_BUCKET,
    LIMITED_ENTRY_BUCKET,
    NON_PUBLIC_BUCKET,
    RESTRICTED_PURSUIT_BUCKET,
    UNLIMITED_PURSUIT_BUCKET,
    bonus_bear_bucket,
    is_scorable_bonus_bear_row,
    split_bonus_bear_rows,
)


def test_bonus_bear_bucket_classification_covers_key_subtypes() -> None:
    assert bonus_bear_bucket({"bear_draw_subtype": "", "draw_method": "Bonus", "probability_metric": "p_draw"}) == LIMITED_ENTRY_BUCKET
    assert bonus_bear_bucket({"bear_draw_subtype": "LIMITED_ENTRY_BEAR_HUNT", "draw_method": "Bonus", "probability_metric": "p_draw"}) == LIMITED_ENTRY_BUCKET
    assert bonus_bear_bucket({"bear_draw_subtype": "RESTRICTED_BEAR_PURSUIT", "draw_method": "Bonus", "probability_metric": "p_draw"}) == RESTRICTED_PURSUIT_BUCKET
    assert bonus_bear_bucket({"bear_draw_subtype": "UNLIMITED_PURSUIT_PERMIT", "draw_method": "Bonus", "probability_metric": "p_availability"}) == UNLIMITED_PURSUIT_BUCKET
    assert bonus_bear_bucket({"bear_draw_subtype": "HARVEST_OBJECTIVE_AVAILABILITY", "draw_method": "Bonus", "probability_metric": "p_availability"}) == HARVEST_OBJECTIVE_BUCKET
    assert bonus_bear_bucket({"bear_draw_subtype": "CONSERVATION_OR_NON_PUBLIC", "draw_method": "Bonus", "probability_metric": "p_draw"}) == NON_PUBLIC_BUCKET


def test_bonus_bear_scorable_flag_only_accepts_public_draw_odds_rows() -> None:
    assert is_scorable_bonus_bear_row({
        "bear_draw_subtype": "",
        "draw_method": "Bonus",
        "probability_metric": "p_draw",
        "classification_status": "MODELED_SOURCE_BACKED_ROLL_FORWARD",
    })
    assert not is_scorable_bonus_bear_row({
        "bear_draw_subtype": "",
        "draw_method": "Bonus",
        "probability_metric": "p_draw",
        "classification_status": "SOURCE_DATA_INCOMPLETE_NO_PUBLIC_DRAW_PROBABILITY",
    })
    assert not is_scorable_bonus_bear_row({
        "bear_draw_subtype": "HARVEST_OBJECTIVE_AVAILABILITY",
        "draw_method": "Bonus",
        "probability_metric": "p_availability",
        "classification_status": "MODELED_AVAILABILITY",
    })


def test_split_bonus_bear_rows_adds_bucket_columns() -> None:
    rows = [
        {
            "hunt_code": "BR7102",
            "bear_draw_subtype": "LIMITED_ENTRY_BEAR_HUNT",
            "draw_method": "Bonus",
            "probability_metric": "p_draw",
            "classification_status": "SOURCE_DATA_INCOMPLETE_NO_PUBLIC_DRAW_PROBABILITY",
        },
        {
            "hunt_code": "BR1001",
            "bear_draw_subtype": "HARVEST_OBJECTIVE_AVAILABILITY",
            "draw_method": "Bonus",
            "probability_metric": "p_availability",
            "classification_status": "MODELED_AVAILABILITY",
        },
    ]

    bucketed_rows, buckets, counts = split_bonus_bear_rows(rows)

    assert bucketed_rows[0]["bonus_bear_bucket"] == LIMITED_ENTRY_BUCKET
    assert bucketed_rows[0]["bonus_bear_bucket_is_scorable"] == "false"
    assert bucketed_rows[1]["bonus_bear_bucket"] == HARVEST_OBJECTIVE_BUCKET
    assert bucketed_rows[1]["bonus_bear_bucket_is_scorable"] == "false"
    assert counts[LIMITED_ENTRY_BUCKET] == 1
    assert counts[HARVEST_OBJECTIVE_BUCKET] == 1
    assert len(buckets[LIMITED_ENTRY_BUCKET]) == 1
