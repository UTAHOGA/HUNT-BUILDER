"""Verified Bear PDF lanes must not consult future PDFs or Sportsman counts."""
import pytest

from engine.utah_draw_predictive import bear, sportsman


@pytest.mark.parametrize("classification,expected", [
    ("TRUE_BEAR_BONUS_DRAW", bear.LIMITED_ENTRY_BEAR_HUNT),
    ("BEAR_PURSUIT_BONUS_DRAW", bear.RESTRICTED_BEAR_PURSUIT),
])
def test_verified_historical_pdf_classifies_without_other_data(monkeypatch, classification, expected):
    def forbidden(*args, **kwargs):
        raise AssertionError("Historical intake attempted to load another source")

    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", forbidden)
    monkeypatch.setattr(bear, "official_bear_pursuit_hunt_codes", forbidden)
    monkeypatch.setattr(sportsman, "_read_sportsman_source_rows", forbidden)
    row = {"hunt_code": "BR7000" if classification == "TRUE_BEAR_BONUS_DRAW" else "BR1008",
           "species": "Black Bear", "actual_draw_year": "2020", "points": "2", "residency": "Resident",
           "bear_source_classification": classification, "bear_source_identity_source": "RETAINED_OFFICIAL_BLACK_BEAR_PDF",
           "source_file": "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/black_bear/20_drawing_odds.pdf",
           "qa_status": "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED"}
    assert bear.classify_bear_subtype(row) == expected


@pytest.mark.parametrize("code,expected", [
    ("BR1000", bear.STATEWIDE_BEAR_PERMIT), ("BR1001", bear.HARVEST_OBJECTIVE_AVAILABILITY),
    ("BR1007", bear.UNLIMITED_PURSUIT_PERMIT), ("BR1018", bear.UNLIMITED_PURSUIT_PERMIT),
])
def test_explicit_bear_nonladder_products_do_not_load_draw_files(monkeypatch, code, expected):
    def forbidden(*args, **kwargs):
        raise AssertionError("Nonladder identity unnecessarily read draw results")

    monkeypatch.setattr(bear, "official_bear_draw_odds_hunt_codes", forbidden)
    monkeypatch.setattr(sportsman, "_read_sportsman_source_rows", forbidden)
    assert bear.classify_bear_subtype({"hunt_code": code, "species": "Black Bear"}) == expected
