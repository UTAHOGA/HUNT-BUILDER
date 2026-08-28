from pathlib import Path

from engine.utah_draw_predictive import bear


def test_missing_official_bear_pdf_is_a_blocker_not_a_crash(monkeypatch, tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing-bear-draw-odds.pdf"
    monkeypatch.setattr(bear, "BEAR_DRAW_ODDS_SOURCE_PDF", missing_pdf)
    bear._parse_official_bear_draw_odds_pdf.cache_clear()
    try:
        rows, report = bear.build_bear_draw_odds_source_audit(
            [
                {
                    "hunt_code": "BR1001",
                    "hunt_name": "Harvest objective",
                    "species": "Black bear",
                }
            ]
        )
    finally:
        bear._parse_official_bear_draw_odds_pdf.cache_clear()

    assert rows[0]["source_classification"] == "BEAR_HARVEST_OBJECTIVE_AVAILABILITY"
    assert report["source_status"] == "MISSING_REPO_EXTERNAL_SOURCE"
    assert report["blocker"] is True
    assert report["production_ready"] is False
