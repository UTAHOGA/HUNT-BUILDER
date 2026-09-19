#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const target = process.env.HUNT_RESEARCH_QA_URL;
const output = process.env.HUNT_RESEARCH_QA_OUTPUT;
const coveragePath = process.env.HUNT_RESEARCH_QA_COVERAGE;
const contractPath = process.env.HUNT_RESEARCH_QA_CONTRACT;
const expectedRuntimeHashes = contractPath
  ? JSON.parse(fs.readFileSync(path.join(contractPath, 'candidate_build_audit.json'), 'utf8')).outputs
  : null;
let activeBrowser;

if (!target || !output) {
  throw new Error('HUNT_RESEARCH_QA_URL and HUNT_RESEARCH_QA_OUTPUT are required.');
}

const scenarios = [
  { label: 'resident_low', code: 'BI6500', residency: 'Resident', points: '0', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'resident_mixed_line', code: 'BI6503', residency: 'Resident', points: '29', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'resident_high', code: 'DB1106', residency: 'Resident', points: '32', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'nonresident_low', code: 'BI6503', residency: 'Nonresident', points: '0', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'nonresident_mixed_line', code: 'BI6504', residency: 'Nonresident', points: '29', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'nonresident_high', code: 'DB1103', residency: 'Nonresident', points: '32', drawPool: 'standard', expected: 'CERTIFIED' },
  { label: 'bear', code: 'BR1001', residency: 'Nonresident', points: '0', drawPool: 'standard', expected: 'SUPPRESSED' },
  { label: 'cwmu', code: 'PD1015', residency: 'Resident', points: '0', drawPool: 'youth', expected: 'SUPPRESSED' },
  { label: 'turkey', code: 'TK1003', residency: 'Nonresident', points: '0', drawPool: 'standard', expected: 'SUPPRESSED' },
  { label: 'antlerless_deer', code: 'DA1001', residency: 'Resident', points: '0', drawPool: 'standard', expected: 'SUPPRESSED' },
  { label: 'antlerless_elk', code: 'EA1007', residency: 'Resident', points: '0', drawPool: 'standard', expected: 'SUPPRESSED' },
  { label: 'dedicated_hunter', code: 'DB1770', residency: 'Resident', points: '0', drawPool: 'dedicated_hunter', expected: 'SUPPRESSED' },
  { label: 'youth', code: 'EB1007', residency: 'Nonresident', points: '0', drawPool: 'youth', expected: 'SUPPRESSED' },
  // Deer uses preference order, not a bonus/random split. Exercise both
  // official residency lanes below, at, and above its projected cutoff.
  ...['Resident', 'Nonresident'].flatMap((residency) => [
    { label: `deer_${residency}_low`, code: 'DB1510', residency, points: '0', drawPool: 'standard', expected: 'CERTIFIED' },
    { label: `deer_${residency}_mixed_line`, code: 'DB1510', residency, points: '2', drawPool: 'standard', expected: 'CERTIFIED' },
    { label: `deer_${residency}_high`, code: 'DB1510', residency, points: '5', drawPool: 'standard', expected: 'CERTIFIED' },
  ]),
];

// The fixed examples remain useful smoke tests, but cannot prove population
// coverage. Add an independently enumerated scenario for every forecastable
// core hunt/residency lane. Missing history is audited separately as withheld.
let eligibleLaneCount = 0;
let eligibleLanesAccounted = 0;
let coverageEvidence = null;
if (coveragePath) {
  const coverage = JSON.parse(fs.readFileSync(coveragePath, 'utf8'));
  coverageEvidence = coverage;
  if (coverage.status !== 'PASS' || !coverage.complete_eligible_accounting) {
    throw new Error('Independent eligible coverage must pass before browser release QA.');
  }
  for (const lane of coverage.inventory) {
    if (lane.coverage_status === 'HISTORICAL_REFERENCE_ONLY') continue;
    const points = lane.forecast_points ? lane.forecast_points.split(';') : ['0'];
    scenarios.push({ label: `coverage_${lane.hunt_code}_${lane.residency}`, code: lane.hunt_code,
      residency: lane.residency, points: points[0], drawPool: 'standard', expected: 'SUPPRESSED' });
    eligibleLaneCount += Number(Boolean(lane.forecast_points));
    eligibleLanesAccounted += 1;
  }
  // These historical example rungs do not have a supported applicant cohort.
  for (const scenario of scenarios) {
    const lane = coverage.inventory.find((row) => row.hunt_code === scenario.code && row.residency === scenario.residency);
    if (lane) {
      if (!lane.certified_probabilities) throw new Error('Coverage must include exact certified probabilities.');
      scenario.expectedProbability = lane.certified_probabilities[scenario.points] ?? null;
      scenario.expected = scenario.expectedProbability === null ? 'SUPPRESSED' : 'CERTIFIED';
    }
  }
}

function clean(value) {
  return String(value || '').trim();
}

async function main() {
  const startedAt = Date.now();
  const browser = await chromium.launch({ headless: true });
  activeBrowser = browser;
  const consoleErrors = [];
  const failedRequests = [];
  const dataResponses = [];
  const runtimeHashTasks = [];
  const results = [];
  const startupTimings = [];
  const workerCount = Math.min(4, scenarios.length);
  const batches = Array.from({ length: workerCount }, (_, i) => scenarios.filter((_, j) => j % workerCount === i));
  await Promise.all(batches.map(async (batch) => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  if (expectedRuntimeHashes) {
    // The official summary contract exceeds Chromium's default per-resource
    // inspector cache. Retain its actual response bytes for hash verification
    // without substituting an independent fetch for what the page received.
    const networkSession = await page.context().newCDPSession(page);
    await networkSession.send('Network.enable', {
      maxTotalBufferSize: 128 * 1024 * 1024,
      maxResourceBufferSize: 64 * 1024 * 1024,
    });
  }
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(`Uncaught: ${error.message}`));
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`));
  page.on('response', (response) => {
    if (/hunt_research_2026_(summary|ladder)|hunt_research_2026\.(index|details)/.test(response.url())) {
      dataResponses.push({ url: response.url(), status: response.status() });
    }
    const role = /\/hunt_research_2026_summary\.json(?:\?|$)/.test(response.url()) ? 'summary'
      : /\/hunt_research_2026\.index\.json(?:\?|$)/.test(response.url()) ? 'index' : null;
    if (expectedRuntimeHashes && role && response.ok()) {
      runtimeHashTasks.push((async () => {
        const actual = crypto.createHash('sha256').update(await response.body()).digest('hex');
        return { role, url: response.url(), sha256: actual,
          expected_sha256: expectedRuntimeHashes[role].sha256, passed: actual === expectedRuntimeHashes[role].sha256 };
      })().catch((error) => ({ role, url: response.url(), passed: false,
        error: error.message, expected_sha256: expectedRuntimeHashes[role].sha256 })));
    }
  });

  const navigationStartedAt = Date.now();
  const initialUrl = new URL(target);
  if (!initialUrl.searchParams.has('hunt_code')) {
    initialUrl.searchParams.set('hunt_code', 'BI6500');
    initialUrl.searchParams.set('residency', 'Resident');
    initialUrl.searchParams.set('points', '0');
    initialUrl.searchParams.set('draw_pool', 'standard');
  }
  await page.goto(initialUrl.href, { waitUntil: 'domcontentloaded', timeout: 120000 });
  const domContentLoadedMs = Date.now() - navigationStartedAt;
  await page.waitForFunction(() => {
    const text = document.querySelector('#filterReadout')?.textContent || '';
    return Boolean(window.UOGA_HUNT_RESEARCH_SNAPSHOT?.filters)
      && !/loading hunt research data/i.test(text);
  }, null, { timeout: 180000 });
  const researchReadyMs = Date.now() - navigationStartedAt;
  startupTimings.push({ dom_content_loaded_ms: domContentLoadedMs, research_ready_ms: researchReadyMs });

  for (const scenario of batch) {
    console.log(`RUNNING_SCENARIO=${scenario.label}`);
    await page.evaluate((next) => {
      document.querySelector('#huntCodeInput').value = next.code;
      document.querySelector('#residencySelect').value = next.residency;
      document.querySelector('#drawPoolSelect').value = next.drawPool;
      document.querySelector('#pointsInput').value = next.points;
      document.querySelector('#drawPoolSelect').dispatchEvent(new Event('change', { bubbles: true }));
    }, scenario);
    // The snapshot is emitted after renderSummary/renderLadder complete.
    // Wait on that state, not a fixed delay that can race a slow detail fetch.
    await page.waitForFunction((next) => {
      const filters = window.UOGA_HUNT_RESEARCH_SNAPSHOT?.filters;
      return filters
        && filters.huntCode === next.code
        && filters.residency === next.residency
        && String(filters.points) === next.points
        && filters.drawPool === next.drawPool;
    }, scenario, { timeout: 30000 });

    const observed = await page.evaluate(() => ({
      code: document.querySelector('#selectedHuntCodeRead')?.textContent,
      lineLabel: document.querySelector('#summaryGuaranteed')?.previousElementSibling?.textContent,
      lineValue: document.querySelector('#summaryGuaranteed')?.textContent,
      odds: document.querySelector('#summaryOdds')?.textContent,
      pointStatus: document.querySelector('#summaryStatus')?.textContent,
      verdict: document.querySelector('#verdictMessage')?.textContent,
      badge: document.querySelector('#verdictBadge')?.textContent,
      ladderHeading: document.querySelector('#ladderHeaderCol3')?.textContent,
      visibleText: document.querySelector('#detailContent')?.innerText,
    }));
    const odds = clean(observed.odds);
    const statusText = `${clean(observed.pointStatus)} ${clean(observed.verdict)} ${clean(observed.badge)}`;
    const numericOddsVisible = /%|1\s+in\s+[0-9]/i.test(odds);
    const modeledZeroVisible = /no modeled chance/i.test(odds);
    const percentMatch = odds.match(/([0-9]+(?:\.[0-9]+)?)%/);
    const exactCertifiedValueMatches = scenario.expected !== 'CERTIFIED'
      || scenario.expectedProbability === undefined
      || (scenario.expectedProbability === 0 && modeledZeroVisible)
      || (percentMatch && Math.abs(Number(percentMatch[1]) - scenario.expectedProbability * 100) <= 0.051);
    const checks = {
      loaded_requested_hunt: clean(observed.code).toUpperCase() === scenario.code,
      projected_draw_line_label: clean(observed.lineLabel) === 'Projected Draw Line',
      no_positive_guarantee_claim: !/(guaranteed to draw|guaranteed draw|draw is guaranteed)/i.test(clean(observed.visibleText)),
      certified_probability_visible: scenario.expected !== 'CERTIFIED' || numericOddsVisible
        || (scenario.expectedProbability === 0 && modeledZeroVisible),
      certified_probability_matches_frozen_value: Boolean(exactCertifiedValueMatches),
      noncertified_probability_suppressed: scenario.expected !== 'SUPPRESSED' || (!numericOddsVisible && !modeledZeroVisible),
      honest_noncertified_status: scenario.expected !== 'SUPPRESSED' || /(experimental|insufficient evidence|not evaluated|prediction withheld|over the counter|first come, first served|model pending)/i.test(statusText),
    };
    results.push({ ...scenario, observed, checks, passed: Object.values(checks).every(Boolean) });
  }
  await page.close();
  }));
  results.sort((a, b) => a.label.localeCompare(b.label));
  const runtimeSourceHashChecks = await Promise.all(runtimeHashTasks);
  const runtimeHashesPass = !expectedRuntimeHashes || (
    ['summary', 'index'].every((role) => runtimeSourceHashChecks.some((row) => row.role === role))
    && runtimeSourceHashChecks.every((row) => row.passed)
  );

  const payload = {
    schema_version: 'certified-research-browser-qa.v1',
    target,
    status: results.every((row) => row.passed)
      && !consoleErrors.length
      && !failedRequests.length
      && runtimeHashesPass
      ? 'PASS' : 'FAIL',
    probability_contract: 'CERTIFIED_P_DRAW_FIELDS_ONLY',
    independent_coverage_report: coveragePath || null,
    independent_coverage_sha256: coveragePath ? crypto.createHash('sha256').update(fs.readFileSync(coveragePath)).digest('hex') : null,
    audited_prediction_sha256: coverageEvidence?.sources?.prediction?.sha256 || null,
    runtime_source_hash_checks: runtimeSourceHashChecks,
    eligible_forecast_lanes_tested: eligibleLaneCount,
    eligible_lanes_accounted_tested: eligibleLanesAccounted,
    startup_timing: {
      dom_content_loaded_ms: Math.max(...startupTimings.map((row) => row.dom_content_loaded_ms)),
      research_ready_ms: Math.max(...startupTimings.map((row) => row.research_ready_ms)),
      isolated_browser_contexts: workerCount,
      total_qa_ms: Date.now() - startedAt,
    },
    scenarios: results,
    data_responses: dataResponses,
    console_errors: consoleErrors,
    failed_requests: failedRequests,
  };
  const absoluteOutput = path.isAbsolute(output) ? output : path.join(ROOT, output);
  fs.mkdirSync(path.dirname(absoluteOutput), { recursive: true });
  fs.writeFileSync(absoluteOutput, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  await browser.close();
  console.log(`CERTIFIED_RESEARCH_BROWSER_QA=${payload.status}`);
  console.log(`SCENARIOS=${results.length} PASSED=${results.filter((row) => row.passed).length}`);
  console.log(`FAILED_REQUESTS=${failedRequests.length} CONSOLE_ERRORS=${consoleErrors.length}`);
  if (payload.status !== 'PASS') {
    results.filter((row) => !row.passed).forEach((row) => console.log(`FAILED_SCENARIO=${row.label} ${JSON.stringify(row.checks)}`));
    process.exitCode = 1;
  }
}

main().catch(async (error) => {
  if (activeBrowser) await activeBrowser.close();
  console.error(error);
  process.exitCode = 1;
});
