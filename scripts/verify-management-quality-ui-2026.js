const path = require('node:path');
const { chromium } = require('playwright');

const target = process.env.HUNT_RESEARCH_QA_URL || 'http://127.0.0.1:8765/research.html';
const screenshot = process.env.HUNT_RESEARCH_QA_SCREENSHOT
  || path.resolve('processed_data/audits/management_quality_release_20260906/research-management-quality-desktop.png');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.route('**/hunt-research.js*', (route) => route.abort());
  await page.route('**/processed_data/hunt_research_2026*', (route) => route.abort());
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.locator('#huntCodeInput').fill('MB6000');
  await page.locator('#residencySelect').selectOption({ label: 'Resident' });
  await page.locator('#pointsInput').fill('10');
  await page.evaluate(() => {
    document.getElementById('detailContent').hidden = false;
    document.getElementById('detailEmpty').hidden = true;
    window.dispatchEvent(new CustomEvent('uoga:hunt-research-rendered', {
      detail: {
        engineRows: [],
        ladderRows: [],
        masterRows: [],
        referenceRows: [],
        loadedSources: {},
      },
    }));
  });
  const panel = page.locator('#uogaApplicationOutlookDashboard');
  try {
    await panel.getByText('Hunt Quality Profile', { exact: true }).waitFor({ timeout: 90000 });
  } catch (error) {
    console.error(JSON.stringify({
      panelText: await panel.innerText().catch(() => ''),
      pageErrors,
    }, null, 2));
    throw error;
  }
  await panel.getByText('Management Plan Context', { exact: true }).waitFor({ timeout: 90000 });
  await panel.getByText('U.O.G.A. score, not a DWR score', { exact: false }).waitFor({ timeout: 90000 });
  const result = await page.evaluate(() => {
    const element = document.getElementById('uogaApplicationOutlookDashboard');
    const text = element?.innerText || '';
    const lower = text.toLowerCase();
    return {
      hasManagementTarget: lower.includes('dwr objective'),
      hasCurrentManagementValue: lower.includes('current dwr value'),
      hasAnnualAge: lower.includes('annual harvested age'),
      hasReportedThreeYearAge: lower.includes('dwr-reported 3-year harvest age'),
      hasPlannerAge: lower.includes('dwr unit current harvested age (3-year avg)'),
      hasQualityProfile: lower.includes('hunt quality profile'),
      hasUogaDisclaimer: lower.includes('u.o.g.a. score, not a dwr score'),
      scoreText: [...(element?.querySelectorAll('.uoga-outlook-panel') || [])]
        .find((item) => item.innerText.toLowerCase().includes('hunt quality profile'))?.innerText || '',
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  });
  if (pageErrors.length) throw new Error(`Page errors: ${pageErrors.join(' | ')}`);
  for (const [key, value] of Object.entries(result)) {
    if (key.startsWith('has') && !value) throw new Error(`Missing UI evidence: ${key}`);
  }
  if (result.horizontalOverflow) throw new Error('Desktop page has horizontal overflow.');
  let screenshotStatus = 'captured';
  try {
    await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled', timeout: 30000 });
  } catch (error) {
    screenshotStatus = `skipped: ${error.message.split('\n')[0]}`;
  }
  console.log(JSON.stringify({ ...result, pageErrors, screenshotStatus }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
