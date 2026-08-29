from __future__ import annotations

from engine.utah_draw_predictive.run_all_families import _historical_source_year_runtime_db_rows


def _bear_lane_row(*, residency: str, permits: int) -> dict[str, object]:
    return {
        "record_type": "POINT",
        "hunt_code": "BR9999",
        "hunt_name": "Residency lane fixture",
        "species": "Black Bear",
        "hunt_type": "Limited Entry",
        "hunt_class": "BLACK_BEAR",
        "weapon": "Any Legal Weapon",
        "draw_system_type": "BEAR_DRAW",
        "draw_pool": "black_bear",
        "residency": residency,
        "points": "0",
        # These broad source columns are intentionally present on both
        # normalized lane rows.  They must not be added twice.
        "resident_total_permits": "5",
        "nonresident_total_permits": "2",
        "total_permits": str(permits),
        "source_file": "official_bear_draw_results.pdf",
    }


def test_historical_proxy_uses_scoped_permits_once_per_residency_lane() -> None:
    rows = _historical_source_year_runtime_db_rows(
        [
            _bear_lane_row(residency="Resident", permits=5),
            _bear_lane_row(residency="Nonresident", permits=2),
        ],
        2021,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["forecast_permits_res"] == "5"
    assert row["forecast_permits_nr"] == "2"
    assert row["forecast_permits_total"] == "7"
