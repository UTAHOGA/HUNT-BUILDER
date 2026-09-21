#!/usr/bin/env node
// Local display regression against exact retained live payloads. Not certification.
const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const output = path.resolve(process.argv[2] || path.join(ROOT, 'audits/research_evidence_display_20260920'));
const scenarios = [
  ['BI6500', 'Resident', 0], ['BI6503', 'Resident', 29], ['DB1106', 'Resident', 32],
  ['BI6503', 'Nonresident', 0], ['BI6504', 'Nonresident', 29], ['DB1103', 'Nonresident', 32],
  ['BR1001', 'Nonresident', 0], ['PD1015', 'Resident', 0, 'youth'],
  ['TK1003', 'Nonresident', 0], ['DA1001', 'Resident', 0], ['EA1007', 'Resident', 0],
  ['DB1770', 'Resident', 0, 'dedicated_hunter'], ['EB1007', 'Nonresident', 0, 'youth'],
  ['BR1013', 'Resident', 3], ['BR1013', 'Nonresident', 3], ['BR7004', 'Resident', 10],
  ['BR7021', 'Resident', 0], ['BR7022', 'Nonresident', 0],
  ...['Resident', 'Nonresident'].flatMap(r => [0, 2, 5].map(p => ['DB1510', r, p])),
];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const mime = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
async function main() {
  if (fs.existsSync(output)) throw new Error(`Refusing to overwrite ${output}`);
  fs.mkdirSync(output, { recursive: true });
  const details = {}, evidence = [];
  await Promise.all([...new Set(scenarios.map(s => s[0]))].map(async code => {
    const url = `https://huntbuilder.pages.dev/processed_data/hunt_research_2026_split/hunts/${code}.json`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    details[code] = JSON.parse(bytes);
    fs.writeFileSync(path.join(output, `${code}.json`), bytes, { flag: 'wx' });
    evidence.push({ code, url, sha256: hash(bytes) });
  }));
  const summary = Object.values(details).flatMap(d => d.research_summary_rows || []);
  const index = Object.entries(details).map(([code, d]) => ({ hunt_code: code, hunt_name: d.hunt_name, species: d.species, detail_path: `hunts/${code}.json` }));
  const override = `\nObject.assign(window.UOGA_CONFIG, {
    HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK:false,HUNT_RESEARCH_USE_SPLIT_CONTRACT:true,HUNT_RESEARCH_USE_SPLIT_DETAIL_DIRECT:true,
    HUNT_RESEARCH_SUMMARY_SOURCES:['/__fixture/summary.json'],HUNT_RESEARCH_SPLIT_INDEX_SOURCES:['/__fixture/index.json'],
    HUNT_RESEARCH_SPLIT_DETAIL_BASES:['/__fixture'],HUNT_RESEARCH_SPLIT_DETAIL_BUNDLE_SOURCES:['/__fixture/details.json']
  });`;
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (pathname.startsWith('/__fixture/')) {
      const code = pathname.match(/\/hunts\/([A-Z0-9]+)\.json$/)?.[1];
      const payload = code ? details[code] : pathname.endsWith('/summary.json') ? summary : pathname.endsWith('/index.json') ? index : { details_by_hunt_code: details };
      res.writeHead(payload ? 200 : 404, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(payload || {}));
    }
    const file = path.resolve(ROOT, '.' + (pathname === '/research' ? '/research.html' : pathname));
    if (!file.startsWith(ROOT + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      res.writeHead(404); return res.end('Not found');
    }
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream' });
    const bytes = fs.readFileSync(file);
    res.end(pathname === '/config.js' ? Buffer.concat([bytes, Buffer.from(override)]) : bytes);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  const results = [], errors = [];
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
    // Isolate optional harvest/management overlays; their absence must not
    // bypass the certified-only selected-point contract. Core payloads are real.
    await page.route(/hunt_application_outlook\.json|hunt_management_objective_context\.json/, route => route.fulfill({ contentType: 'application/json', body: '[]' }));
    page.on('pageerror', error => errors.push(error.message));
    for (const route of ['/research', '/research.html']) {
      await page.goto(`http://127.0.0.1:${server.address().port}${route}?hunt_code=BI6500&residency=Resident&points=0&draw_pool=standard`);
      await page.waitForFunction(() => window.UOGA_HUNT_RESEARCH_SNAPSHOT?.filters, null, { timeout: 30000 });
      for (const [code, residency, points, pool = 'standard'] of scenarios) {
        const next = { huntCode: code, residency, points, drawPool: pool };
        await page.evaluate(s => {
          document.querySelector('#huntCodeInput').value = s.huntCode;
          document.querySelector('#residencySelect').value = s.residency;
          document.querySelector('#pointsInput').value = s.points;
          document.querySelector('#drawPoolSelect').value = s.drawPool;
          document.querySelector('#drawPoolSelect').dispatchEvent(new Event('change', { bubbles: true }));
        }, next);
        await page.waitForFunction(s => {
          const f = window.UOGA_HUNT_RESEARCH_SNAPSHOT?.filters;
          return f && f.huntCode === s.huntCode && f.residency === s.residency && Number(f.points) === s.points && f.drawPool === s.drawPool;
        }, next, { timeout: 30000 });
        if (route.endsWith('.html')) await page.waitForFunction(s => {
          const panel = document.getElementById('uogaApplicationOutlookDashboard');
          return panel?.querySelector('h2')?.textContent.startsWith(s.huntCode + ' -')
            && panel?.innerText.includes(`${s.residency} · ${s.points} points`);
        }, next, { timeout: 10000 }).catch(async error => {
          console.error(JSON.stringify({ next, errors, panel: await page.locator('#uogaApplicationOutlookDashboard').innerText() }));
          throw error;
        });
        const observed = await page.evaluate(() => {
          const text = id => document.getElementById(id)?.textContent || '';
          return { odds: text('summaryOdds'), line: text('summaryGuaranteed'), trend: text('summaryTrendText'),
            trendLights: document.getElementById('summaryTrend')?.innerHTML || '',
            status: text('summaryStatus'), historyNote: text('ladderRange'),
            selected: window.UOGA_HUNT_RESEARCH_SNAPSHOT?.selectedRow,
            overlayOdds: [...document.querySelectorAll('#uogaApplicationOutlookDashboard .uoga-outlook-metric')]
              .find(el => el.querySelector('span')?.textContent === 'Estimated odds')?.querySelector('strong')?.textContent || '',
            dashboard: text('uogaApplicationOutlookDashboard') };
        });
        const row = (details[code].research_ladder_rows || []).find(r => r.residency === residency && Number(r.points) === points && (r.draw_pool || 'standard') === pool);
        const value = row?.certified_p_draw_pct !== '' && row?.certified_p_draw_pct != null ? Number(row.certified_p_draw_pct) :
          (row?.certified_p_draw_mean !== '' && row?.certified_p_draw_mean != null ? Number(row.certified_p_draw_mean) * 100 : null);
        const supported = row?.prediction_certification_status === 'CERTIFIED' && value !== null;
        const checks = supported ? {
          certified_value_unchanged: value === 0 ? /No modeled chance/i.test(observed.odds) : Math.abs(Number(observed.odds.match(/([\d.]+)%/)?.[1]) - value) <= .051,
        } : {
          probability_withheld: !/%|1\s+in\s+\d|No modeled chance/i.test(observed.odds),
          future_line_withheld: !/\d/.test(observed.line),
          no_colored_forecast_light: observed.trendLights === '',
        };
        if (route.endsWith('.html') && !supported) checks.overlay_withheld = /Prediction withheld/.test(observed.dashboard);
        if (route.endsWith('.html') && supported) checks.overlay_certified_value_unchanged = value === 0
          ? /No modeled chance/i.test(observed.overlayOdds)
          : Math.abs(Number(observed.overlayOdds.match(/([\d.]+)%/)?.[1]) - value) <= .051;
        if (['BR7021','BR7022'].includes(code)) checks.split_history_explained = /No comparable 2025 draw history/.test(observed.historyNote);
        results.push({ route, ...next, supported, expected_pct: value, observed, checks, passed: Object.values(checks).every(Boolean) });
        if (code === 'BR1013' && residency === 'Resident') await page.screenshot({ path: path.join(output, route.endsWith('.html') ? 'bear-overlay.png' : 'bear-core.png'), fullPage: true });
      }
    }
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
  const report = { scope: 'LOCAL_DISPLAY_REGRESSION_NOT_MODEL_CERTIFICATION', evidence, results, errors,
    passed: results.every(r => r.passed) && errors.length === 0 };
  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2), { flag: 'wx' });
  console.log(JSON.stringify({ passed: report.passed, scenarios: results.length, failures: results.filter(r => !r.passed), errors, output }, null, 2));
  if (!report.passed) process.exitCode = 1;
}
main().catch(e => { console.error(e); process.exitCode = 1; });
