from __future__ import annotations

import csv
from pathlib import Path


FRONTEND_PATH = Path("hunt-research.js")
RESEARCH_HTML_PATH = Path("research.html")
FIXTURE_PATH = Path("data/utah/fixtures/draw_reality_engine.csv")
POINT_LADDER_PATH = Path("processed_data/point_ladder_view.csv")


def _frontend_text() -> str:
    return FRONTEND_PATH.read_text(encoding="utf-8")


def _block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _fixture_max_pool_row() -> dict[str, str]:
    rows = list(csv.DictReader(FIXTURE_PATH.open(encoding="utf-8")))
    return next(r for r in rows if r["status"] == "MAX POOL")


def _select_draw_odds_percent(row: dict[str, str]) -> float | None:
    for key in (
        "display_odds_pct",
        "p_draw_mean",
        "odds_2026_projected",
        "max_pool_projection_2026",
        "random_draw_odds_2026",
        "random_draw_projection_2026",
    ):
        value = row.get(key, "")
        if value in ("", None):
            continue
        parsed = float(value)
        if key == "p_draw_mean":
            return parsed * 100
        return parsed
    return None


def _format_combined_odds(percent_value: float | None) -> str:
    if percent_value is None:
        return "Not available"
    if percent_value <= 0:
        return "No modeled chance"

    capped = min(100.0, max(0.0, percent_value))
    percent_text = f"{int(capped)}%" if float(capped).is_integer() else f"{float(f'{capped:.1f}')}%"

    if capped >= 99.9:
        return f"~1 in 1 or {percent_text}"

    denominator = 100 / capped
    denominator_text = str(float(f"{denominator:.1f}")).rstrip("0").rstrip(".") if denominator < 10 else str(round(denominator))
    return f"~1 in {denominator_text} or {percent_text}"


def _verdict_badge_from_selected_odds(row: dict[str, str]) -> str:
    guaranteed_probability = float(row["guaranteed_probability"])
    selected_percent = _select_draw_odds_percent(row)
    if guaranteed_probability >= 0.999:
        return "Guaranteed"
    if selected_percent is None:
        return "Random Chance Only"
    if selected_percent >= 99.9:
        return "Guaranteed"
    if selected_percent >= 90:
        return "Very likely"
    if selected_percent >= 25:
        return "On the Line"
    if selected_percent > 0:
        return "Random / Long-shot Chance"
    return "Not Catchable Right Now"


def _outlook_signal_from_selected_odds(row: dict[str, str]) -> str:
    guaranteed_probability = float(row["guaranteed_probability"])
    selected_percent = _select_draw_odds_percent(row)
    if guaranteed_probability >= 0.999:
        return "green"
    if selected_percent is None:
        return "red"
    if selected_percent >= 99.9:
        return "green"
    if selected_percent >= 25:
        return "yellow"
    return "red"


def test_max_pool_not_automatic_100():
    text = _frontend_text()
    assert "if (row.status === 'MAX POOL') return 100;" not in text
    assert "if (!hasModeledFields && row.status === 'MAX POOL') return { value: '100%', source: 'guaranteed' };" not in text


def test_frontend_uses_modeled_probability_before_legacy_max_pool():
    text = _frontend_text()
    block = _block(text, "function selectDrawOddsPercent(row)", "function getDisplayedOdds(row)")
    assert "display_odds_pct" in block
    assert "p_draw_mean" in block
    assert "odds_2026_projected" in block
    assert "max_pool_projection_2026" in block
    assert "random_draw_odds_2026" in block
    assert "random_draw_projection_2026" in block
    assert block.index("display_odds_pct") < block.index("p_draw_mean")
    assert block.index("p_draw_mean") < block.index("odds_2026_projected")
    assert "row.status === 'MAX POOL'" not in block


def test_frontend_uses_engine_group_fallback_for_non_point_families():
    text = _frontend_text()
    assert "function getEngineGroupFallbackRow(" in text
    assert "const rawEngineGroupFallbackRow = getEngineGroupFallbackRow(filters.huntCode, filters.residency, filters.drawPool);" in text
    assert "const engineGroupFallbackRow = SHOW_AUDIT_ONLY_ROWS || !isOutOfScopeNonTargetRow(rawEngineGroupFallbackRow)" in text
    assert "const summaryRow = engineRow || engineGroupFallbackRow || ladderPointRow || null;" in text


def test_fixture_row_with_max_pool_and_modeled_probability_exists():
    row = _fixture_max_pool_row()
    assert row["p_draw_mean"] == "0.420"
    assert row["guaranteed_probability"] == "0.000"
    assert row["display_odds_pct"] == "42.000"
    assert float(row["display_odds_pct"]) == 42.0
    assert round(float(row["p_draw_mean"]) * 100, 3) == 42.0
    assert float(row["guaranteed_probability"]) < 0.999


def test_max_pool_fixture_row_is_not_guaranteed_badge():
    row = _fixture_max_pool_row()
    assert _verdict_badge_from_selected_odds(row) != "Guaranteed"
    assert _verdict_badge_from_selected_odds(row) == "On the Line"


def test_format_odds_combined_guaranteed():
    assert _format_combined_odds(100) == "~1 in 1 or 100%"


def test_format_odds_combined_50_percent():
    assert _format_combined_odds(50) == "~1 in 2 or 50%"


def test_format_odds_combined_42_percent():
    assert _format_combined_odds(42) == "~1 in 2.4 or 42%"


def test_format_odds_combined_25_percent():
    assert _format_combined_odds(25) == "~1 in 4 or 25%"


def test_format_odds_combined_10_percent():
    assert _format_combined_odds(10) == "~1 in 10 or 10%"


def test_format_odds_combined_one_percent():
    assert _format_combined_odds(1) == "~1 in 100 or 1%"


def test_format_odds_combined_zero_percent():
    assert _format_combined_odds(0) == "No modeled chance"


def test_format_odds_combined_missing():
    assert _format_combined_odds(None) == "Not available"


def test_modeled_max_pool_42_percent_displays_one_in_2_4_or_42_percent():
    row = _fixture_max_pool_row()
    assert _format_combined_odds(_select_draw_odds_percent(row)) == "~1 in 2.4 or 42%"


def test_max_pool_status_does_not_display_one_in_1_or_100_without_numeric_guarantee():
    row = _fixture_max_pool_row()
    assert _format_combined_odds(_select_draw_odds_percent(row)) != "~1 in 1 or 100%"


def test_no_percent_only_primary_odds_display():
    text = _frontend_text()
    block = _block(text, "function getPrimaryOddsLabel(meta, row, displayedOdds)", "function getOutlookSignal(meta, row)")
    assert "displayedOdds.value" in block
    assert "formatProbability(" not in block
    assert "summaryOdds.textContent = getPrimaryOddsLabel(meta, row, displayedOdds);" in text


def test_ladder_odds_use_combined_format():
    text = _frontend_text()
    block = _block(text, "function renderLadder(meta, huntCode, residency, points, drawPool)", "function renderEmpty(filters, coverageMessage)")
    assert "getMaxPointPoolDisplay(row)" in block
    assert "getRandomDrawDisplay(row)" in block
    assert "formatOddsAsOneInOrPercent(rawPrimary)" in block
    assert "formatProbability(rawPrimary)" not in block


def test_guaranteed_max_point_pool_display_uses_99_percent_label():
    text = _frontend_text()
    block = _block(text, "function getMaxPointPoolDisplay(row)", "function getRandomDrawDisplay(row)")
    assert "const MAX_POINT_POOL_GUARANTEED_DISPLAY = '~1 in 1 or 99%';" in text
    assert "zone === 'max_point_pool' || zone === 'max_pool_guaranteed'" in block
    assert "return MAX_POINT_POOL_GUARANTEED_DISPLAY;" in block
    assert "formatOddsAsOneInOrPercent(100)" not in block


def test_mixed_cutoff_max_point_pool_display_keeps_modeled_fraction():
    text = _frontend_text()
    block = _block(text, "function getMaxPointPoolDisplay(row)", "function getRandomDrawDisplay(row)")
    assert "max_pool_cutoff_mixed" in block
    assert "display_2026_max_point_pool" in block
    assert "p_max_pool_mean" in block


def test_source_snapshot_odds_use_combined_format():
    text = _frontend_text()
    block = _block(text, "function buildSourceBoxes(meta, row, referenceRow)", "function openSourceModal(meta, row, referenceRow, residency)")
    assert "['2025 Draw Results', formatHistoricalDrawResult(row)" in block
    assert "formatHistoricalRatioFromPercent(row?.odds_2025_actual)" in block
    assert "['2026 Draw Odds', getDisplayedOdds(row).value]" in block


def test_historical_dwr_success_ratio_is_not_displayed_as_a_percent():
    text = _frontend_text()
    historical_block = _block(text, "function normalizeHistoricalOddsDisplay(value)", "function hasDataQualityFlag(row, flag)")
    fallback_block = _block(text, "function formatHistoricalDrawResult(row)", "function isOddsDisplayText(value)")
    assert "const sourceRatio = text.match(/1\\s*in\\s*([0-9]+(?:\\.[0-9]+)?)/i);" in historical_block
    assert "return `1 in ${sourceRatio[1]}`;" in historical_block
    assert "formatHistoricalRatioFromPercent(pct)" in historical_block
    assert "or ${percent.toFixed(1)}%" not in fallback_block
    assert "return `1 in ${(applicants / totalPermits).toFixed(1)}`;" in fallback_block


def test_ladder_source_pill_click_matches_csv_point_values_numerically():
    text = _frontend_text()
    block = _block(text, 'els.ladderTableBody?.addEventListener(\'click\'', 'els.sourceModalClose?.addEventListener')
    assert 'const point = Number.parseInt(trigger.getAttribute(\'data-point\') || \'\', 10);' in block
    assert '.find((candidate) => Number(candidate.points) === point);' in block
    assert '.find((candidate) => candidate.points === point);' not in block


def test_ladder_hunt_data_pills_only_render_on_user_and_guaranteed_rows():
    text = _frontend_text()
    block = _block(text, "els.ladderTableBody.innerHTML = rows.map((row) => {", "const rawPrimary = firstAvailable")
    assert "Hunt Data" in block
    assert "(isUserRow || isGuaranteedLineRow(row)) && hasSourceData" in block
    assert "label: 'Sources'" not in block


def test_backpack_includes_hunt_data_action():
    ui_text = Path("ui.js").read_text(encoding="utf-8")
    assert "function huntDataHref(item)" in ui_text
    assert "./hard-copy.html?hunt_code=${encodeURIComponent(item.hunt_code)}" in ui_text
    assert 'data-backpack-link="hunt-data"' in ui_text
    assert ">Hunt Data</a>" in ui_text


def test_source_snapshot_shows_official_2026_quota_source():
    text = _frontend_text()
    block = _block(text, "function buildSourceBoxes(meta, row, referenceRow)", "function openSourceModal(meta, row, referenceRow, residency)")
    assert "2026 quota source:" in block
    assert "['2026 Quota Source', quotaSourceDisplay]" in block


def test_ladder_column_labels_use_correct_pool_language():
    html = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    js = _frontend_text()
    assert "2025 Draw Results" in html
    assert "2026 Max Point Pool" in html
    assert "2025 Actual Odds" not in html
    assert "2026 Max Pool" not in html
    assert "els.ladderPrimaryHeader.textContent = '2026 Max Point Pool';" in js


def test_draw_pool_selector_is_internal_not_hunter_facing():
    html = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    assert '<label for="drawPoolSelect">Draw Pool</label>' not in html
    assert 'id="drawPoolSelect"' in html
    assert 'draw-pool-field is-internal" hidden' in html
    assert '<label for="drawPoolSelect">Internal draw-pool routing</label>' in html


def test_standard_draw_pool_is_not_rendered_as_visible_hunter_copy():
    text = _frontend_text()
    readout_block = _block(text, "function renderFilterReadout(filters)", "function getHarvestSuccessDisplay(meta, referenceRow)")
    basket_block = _block(text, "function renderBasket()", "async function loadData()")
    assert "getDrawPoolHandoffLabel(filters.drawPool)" in readout_block
    assert "${filters.drawPool}" not in readout_block
    assert "Pool: ${escapeHtml(normalizeDrawPool(item.draw_pool))}" not in basket_block
    assert "getDrawPoolHandoffLabel(item.draw_pool)" in basket_block


def test_builder_and_backpack_carry_draw_pool_internally():
    app_text = Path("app.js").read_text(encoding="utf-8")
    ui_text = Path("ui.js").read_text(encoding="utf-8")
    assert "function inferResearchDrawPool(hunt)" in app_text
    assert "localStorage.setItem('selected_hunt_research_draw_pool', normalizedDrawPool);" in app_text
    assert "./research.html?hunt_code=${encodeURIComponent(code)}&draw_pool=${encodeURIComponent(normalizedDrawPool)}" in app_text
    assert "data-draw-pool=" in ui_text
    assert "localStorage.setItem('selected_hunt_research_draw_pool', drawPool);" in ui_text


def test_guaranteed_to_draw_line_uses_requested_orange():
    html = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    js = _frontend_text()
    assert "--guaranteed-line-orange: rgb(250, 120, 0);" in html
    assert "function isGuaranteedLineRow(row)" in js
    assert "row?.projected_2026_max_cutoff_point" in js
    assert "row?.guaranteed_at_2026" in js
    assert "const summaryGuaranteedPoint = num(row?.guaranteed_at_2026);" in js
    assert "if (summaryGuaranteedPoint !== null) return summaryGuaranteedPoint;" in js
    assert "Math.round(rowPoint) === Math.round(guaranteedLinePoint)" in js
    assert "if (isGuaranteedLineRow(row))" in js
    guaranteed_row_block = _block(
        html,
        ".report-table tbody tr.is-guaranteed-row {",
        ".report-table tbody tr.is-user-row {",
    )
    user_guaranteed_block = _block(
        html,
        ".report-table tbody tr.is-user-row.is-guaranteed-row {",
        ".report-table tbody tr.is-guaranteed-row td,",
    )
    guaranteed_marker_block = _block(
        html,
        ".marker-pill.guaranteed {",
        ".marker-pill.user {",
    )
    assert "background: var(--guaranteed-line-orange);" in guaranteed_row_block
    assert ".report-table tbody tr.is-guaranteed-row td" in html
    assert "var(--guaranteed-line-orange)" in user_guaranteed_block
    assert "rgba(250, 120, 0" in guaranteed_marker_block
    assert "color: var(--guaranteed-line-orange);" in guaranteed_marker_block


def test_guaranteed_line_highlight_matches_summary_not_random_start_boundary():
    rows = [
        row
        for row in csv.DictReader(POINT_LADDER_PATH.open(encoding="utf-8"))
        if row["hunt_code"] == "MB6011"
        and row["residency"] == "Resident"
        and row["draw_pool"] == "standard"
        and row["points"] in {"29", "28"}
    ]
    by_point = {row["points"]: row for row in rows}
    assert by_point["29"]["guaranteed_at_2026"] == "29"
    assert by_point["28"]["projected_2026_max_cutoff_point"] == "28.0"
    assert by_point["28"]["point_pool_zone"] == "max_pool_cutoff_mixed"

    js = _frontend_text()
    guaranteed_fn = _block(js, "function getGuaranteedLinePoint(row)", "function isGuaranteedLineRow(row)")
    assert guaranteed_fn.index("guaranteed_at_2026") < guaranteed_fn.index("projected_2026_max_cutoff_point")


def test_highlighted_ladder_boxes_use_dark_brown_outline():
    html = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    assert "--highlight-outline-brown: rgb(55, 34, 22);" in html
    assert html.count("var(--highlight-outline-brown)") >= 8

    guaranteed_row_block = _block(
        html,
        ".report-table tbody tr.is-guaranteed-row {",
        ".report-table tbody tr.is-user-row {",
    )
    user_guaranteed_block = _block(
        html,
        ".report-table tbody tr.is-user-row.is-guaranteed-row {",
        ".report-table tbody tr.is-guaranteed-row td,",
    )
    guaranteed_marker_block = _block(
        html,
        ".marker-pill.guaranteed {",
        ".marker-pill.user {",
    )
    assert "inset 0 0 0 2px var(--highlight-outline-brown)" in guaranteed_row_block
    assert "inset 0 0 0 2px var(--highlight-outline-brown)" in user_guaranteed_block
    assert "border-color: var(--highlight-outline-brown);" in guaranteed_marker_block


def test_hunter_points_and_guaranteed_line_use_distinct_highlight_colors():
    html = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    assert "--hunter-points-blue: rgb(219, 242, 255);" in html
    assert "--hunter-points-blue-strong: rgb(0, 96, 140);" in html
    assert "--guaranteed-line-orange: rgb(250, 120, 0);" in html

    user_row_block = _block(
        html,
        ".report-table tbody tr.is-user-row {",
        ".report-table tbody tr.is-cutoff-row {",
    )
    guaranteed_row_block = _block(
        html,
        ".report-table tbody tr.is-guaranteed-row {",
        ".report-table tbody tr.is-user-row {",
    )
    user_guaranteed_block = _block(
        html,
        ".report-table tbody tr.is-user-row.is-guaranteed-row {",
        ".report-table tbody tr.is-guaranteed-row td,",
    )
    assert "background: var(--hunter-points-blue);" in user_row_block
    assert "var(--hunter-points-blue-strong)" in user_row_block
    assert "background: var(--guaranteed-line-orange);" in guaranteed_row_block
    assert "var(--hunter-points-blue-strong)" in user_guaranteed_block
    assert "var(--guaranteed-line-orange)" in user_guaranteed_block


def test_no_status_max_pool_return_100_shortcut():
    text = _frontend_text()
    assert "row.status === 'MAX POOL'" not in _block(text, "function getDisplayedOdds(row)", "function isPreferenceAntlerless(meta)")


def test_max_pool_status_does_not_force_guaranteed_badge():
    text = _frontend_text()
    block = _block(text, "function getVerdictState(meta, row, filters, coverageMessage)", "function renderVerdict(meta, row, filters, coverageMessage)")
    assert "row.status === 'MAX POOL'" not in block
    assert _verdict_badge_from_selected_odds(_fixture_max_pool_row()) != "Guaranteed"


def test_max_pool_status_does_not_force_green_light():
    text = _frontend_text()
    block = _block(text, "function getOutlookSignal(meta, row)", "function renderOutlookLight(signal)")
    assert "row.status === 'MAX POOL'" not in block
    assert _outlook_signal_from_selected_odds(_fixture_max_pool_row()) != "green"
    assert _outlook_signal_from_selected_odds(_fixture_max_pool_row()) == "yellow"


def test_research_page_green_legend_no_longer_claims_max_pool_guarantee():
    text = RESEARCH_HTML_PATH.read_text(encoding="utf-8")
    assert "Green:</strong> Guaranteed draw." not in text
    assert "Green:</strong> The selected draw-odds field is effectively guaranteed." in text


def test_out_of_scope_rows_hidden_from_normal_prediction_display():
    text = _frontend_text()
    assert "const SHOW_AUDIT_ONLY_ROWS = (() => {" in text
    assert "rawEngineRows.filter((row) => !isOutOfScopeNonTargetRow(row))" in text
    assert "This category is outside the approved target prediction universe and is hidden from the standard Hunt Research view." in text


def test_out_of_scope_rows_have_audit_label_when_debug_mode_is_enabled():
    text = _frontend_text()
    assert "function getOutOfScopeAuditLabel()" in text
    assert "return 'Out of scope / not a target prediction category';" in text
