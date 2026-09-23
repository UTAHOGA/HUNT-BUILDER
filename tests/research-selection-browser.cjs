const assert = require('assert/strict');
const { chromium } = require('playwright');
const base = process.env.RESEARCH_TEST_URL || 'https://localhost:4187';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    for (const [code, residency, points] of [
      ['MB6011', 'Resident', 12], ['MB6011', 'Resident', 30],
      ['MB6011', 'Nonresident', 12], ['BR7004', 'Resident', 12],
      ['DA1001', 'Resident', 3], ['PD1025', 'Resident', 3],
    ]) {
      await page.goto(`${base}/research.html?hunt_code=${code}&residency=${residency}&points=${points}`, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(({ code, residency, points }) => {
        const selection = window.UOGA_HUNT_RESEARCH_SNAPSHOT?.filters;
        return selection?.huntCode === code && selection?.residency === residency && selection?.points === points;
      }, { code, residency, points }, { timeout: 90000 });
      await page.waitForFunction(({ code, points }) => {
        const panel = document.getElementById('uogaApplicationOutlookDashboard');
        if (!window.UOGA_HUNT_ELIGIBILITY.isCurrent(code)) return panel?.textContent.includes('Historical/reference');
        return panel?.querySelector('.uoga-outlook-hero-title span')?.textContent.includes(`${points} points`)
          && panel.textContent.includes('Most recent mapped harvest success');
      }, { code, points }, { timeout: 90000 });
      const result = await page.evaluate(() => {
        const snapshot = window.UOGA_HUNT_RESEARCH_SNAPSHOT;
        return {
          current: window.UOGA_HUNT_ELIGIBILITY.isCurrent(snapshot.filters.huntCode),
          summaryPoints: snapshot.summaryRow?.points ?? null,
          summaryProbability: snapshot.summaryRow?.certified_p_draw_mean ?? null,
          ladderProbability: snapshot.ladderRows.find(row => Number(row.points) === snapshot.filters.points)?.certified_p_draw_mean ?? null,
          summaryOdds: document.getElementById('summaryOdds')?.textContent,
          selectedOddsValue: snapshot.displayContext?.selectedOdds?.value,
          harvest: document.getElementById('selectedHarvestSuccess')?.textContent,
          detailHidden: document.getElementById('detailContent')?.hidden,
          dashboard: document.getElementById('uogaApplicationOutlookDashboard')?.textContent,
        };
      });
      if (result.current) {
        if (result.summaryPoints !== null) assert.equal(Number(result.summaryPoints), points);
        assert.equal(result.summaryProbability, result.ladderProbability, 'Selected summary and ladder probability must agree');
        assert(result.dashboard.includes(result.selectedOddsValue), `Dashboard must display the selected summary odds: ${result.selectedOddsValue}`);
        assert(result.dashboard.includes(result.harvest), 'Dashboard must display the same harvest context');
      } else {
        assert(result.detailHidden);
        assert.equal(result.summaryPoints, null);
      }
      delete result.dashboard;
      console.log(JSON.stringify({ code, residency, points, ...result }));
    }
    assert.deepEqual(errors, [], 'No JavaScript page errors');
    console.log('Six browser selection checks passed');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
