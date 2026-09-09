from pathlib import Path


def test_research_probability_selection_is_certification_gated() -> None:
    text = Path("hunt-research.js").read_text(encoding="utf-8")
    assert "function getCertificationGatedOdds(row)" in text
    assert "uncertified_probability_withheld" in text
    assert "certification_metadata_missing_probability_withheld" in text
    assert "row.certified_p_draw_pct" in text
    assert "row.certified_p_draw_mean" in text
    assert "source: 'guaranteed_line_met'" not in text
    assert "badge: 'Experimental'" in text
    assert "badge: 'Insufficient evidence'" in text
    assert "pointStatus: 'Experimental — prediction withheld'" in text
    assert "pointStatus: 'Insufficient evidence — prediction withheld'" in text


def test_research_calls_future_line_a_projection_not_a_guarantee() -> None:
    html = Path("research.html").read_text(encoding="utf-8")
    text = Path("hunt-research.js").read_text(encoding="utf-8")
    assert "Projected Draw Line" in html
    assert "Guaranteed To Draw Line" not in html
    assert "pts short of projected line" in text
    assert "projected_draw_line_2026" in text
    assert "the drawing is still not guaranteed" in text
    assert "Projected draw line" in text


def test_public_contract_requires_certified_probability_fields_for_draws() -> None:
    text = Path("scripts/build-public-data-contracts.js").read_text(encoding="utf-8")
    assert "const isCertified = certificationStatus === 'CERTIFIED'" in text
    assert "['certified_p_draw_mean', 'certified_p_draw']" in text
    assert "['certified_p_draw_pct']" in text
    assert "(isAvailabilityOnly ? ['p_availability'] : [])" in text
    assert "['p_draw_mean', 'p_draw', 'p_availability']" not in text
    assert "prediction_certification_status" in text
    assert "projected_draw_line_points" in text
