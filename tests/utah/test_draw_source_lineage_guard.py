import pytest

from scripts.rebuild_draw_results_long_from_canonical_yearly import require_source_lineage


@pytest.mark.parametrize("row", [
    {"source_file": "official.pdf", "pdf_page": "4"},
    {"source_file": "UtahDraws live DrawOddsData: Big Game:Limited-Entry", "source_dataset": "UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260618"},
    {"source_file": "https://dwrapps.utah.gov/huntboundary/HuntTableData?species=Elk", "source_dataset": "DWR_HUNT_PLANNER_2026_ANTLERLESS_REFRESH_20260621"},
])
def test_preserves_pdf_or_explicit_official_endpoint_lineage(row):
    require_source_lineage(row)


@pytest.mark.parametrize("row", [
    {"source_file": "official.pdf"},
    {"pdf_page": "4"},
    {"source_file": "unverified website", "source_dataset": "UTAHDRAWS_"},
    {"source_file": "UtahDraws live DrawOddsData: Big Game:Limited-Entry"},
])
def test_lost_or_unverified_lineage_is_blocked(row):
    with pytest.raises(ValueError, match="Missing official source/page lineage"):
        require_source_lineage(row)
