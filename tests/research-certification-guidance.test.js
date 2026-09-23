const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');

function load(relative, exports, overlay = false) {
  const nodes = new Map();
  const document = { getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, { textContent: '', innerHTML: '', value: '3',
      setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} } });
    return nodes.get(id);
  } };
  const window = { location: { search: '', pathname: '/research.html' }, UOGA_CONFIG: {} };
  let source = fs.readFileSync(path.join(root, relative), 'utf8');
  const end = overlay ? /  if \(document.readyState === "loading"\) \{[\s\S]*$/ : /  init\(\);\s*\}\)\(\);\s*$/;
  assert(end.test(source), 'Test seam must replace only initialization');
  source = source.replace(end, `  window.test = {${exports}};\n})();`);
  vm.runInNewContext(source, { window, document, URLSearchParams, console });
  return { ...window.test, nodes };
}

const core = load('hunt-research.js', 'getCertificationGatedOdds,getCertificationDisplayStatus,getGuaranteedLinePoint,isGuaranteedLineRow,getPointCreepDisplay,getRecommendation,renderSummary,formatHistoricalDrawResult,historicalDrawBoundaryReason,getHarvestSuccessDisplay,getEngineRow,getEngineGroupFallbackRow,getLadderRows,indexData');
const overlay = load('assets/js/research-outlook-dashboard.js', 'getSelectedOddsInfo,getGuaranteedLine,getPointTrend,getPointStatusLabel,dashboardHtml,applyCoreSnapshot,getSelection,findContext,comparableStatus,sourceDetails', true);
const filters = { huntCode: 'BR1013', residency: 'Resident', points: 3, drawPool: 'standard' };
const base = { hunt_code: 'BR1013', hunt_name: 'Bear pursuit', residency: 'Resident', points: 3,
  projected_draw_line_2026: 2, guaranteed_at_2026: 2, guaranteed_marker: 'Y',
  trend: 'GREEN', gap: -1, p_draw_mean: .99, display_2026_random_draw: '99%',
  total_permits: 7, dwr_result_display: '1 in 1.7' };
let checked = 0;
for (const status of ['', 'INSUFFICIENT_EVIDENCE', 'EXPERIMENTAL_NOT_CERTIFIED', 'PROVISIONALLY_VALIDATED_LIMITED_EVIDENCE', 'CERTIFIED']) {
  const row = { ...base, prediction_certification_status: status };
  const before = JSON.stringify(row);
  assert.equal(core.getCertificationGatedOdds(row).percent, null);
  assert.equal(core.getGuaranteedLinePoint(row, [base]), null);
  assert.equal(core.isGuaranteedLineRow(row), false);
  assert.equal(core.getPointCreepDisplay(row), 'Prediction withheld');
  assert.match(core.getRecommendation({}, row, {}), /withheld|No future/i);
  core.renderSummary({}, row, filters, '', {});
  assert.equal(core.nodes.get('summaryGuaranteed').textContent, 'Prediction withheld');
  assert.equal(core.nodes.get('summaryTrendText').textContent, 'Prediction withheld');
  assert.equal(core.nodes.get('summaryOdds').textContent, 'Not available');
  assert.equal(core.nodes.get('summaryTrend').innerHTML, '');
  assert.equal(overlay.getSelectedOddsInfo(row, base, base, { modeled_draw_probability: 1 }).percent, null);
  assert.equal(overlay.getGuaranteedLine(row, base), '');
  assert.equal(overlay.getPointTrend(row, base), '');
  assert.equal(overlay.getPointStatusLabel(filters, row, base), 'Prediction withheld');
  const html = overlay.dashboardHtml(filters, { selectedRow: row, meta: {}, reference: {}, managementRows: [], comparable: [],
    outlookRow: { decision_label: 'Strong', recommended_action: 'Apply now', source_badges: 'U.O.G.A. Modeled Output' } });
  assert(!html.includes('Apply now'));
  assert(!html.includes('U.O.G.A. Modeled Output'));
  assert(!/At guaranteed|above guaranteed|Guaranteed line/.test(html));
  assert.equal(JSON.stringify(row), before, 'Display must not mutate historical or permit fields');
  checked++;
}
for (const p of [0, .005, .5, .995, 1]) {
  const row = { ...base, prediction_certification_status: 'CERTIFIED', certified_p_draw_mean: p };
  assert.equal(core.getCertificationGatedOdds(row).percent, p * 100);
  assert.equal(overlay.getSelectedOddsInfo(row).percent, p * 100);
  assert.equal(core.getCertificationDisplayStatus(row), null);
  assert.equal(Number(overlay.getGuaranteedLine(row)), 2);
  checked++;
}
console.log(`Research certification guidance: ${checked} status/probability cases passed`);
assert.equal(core.formatHistoricalDrawResult({ applicants: 100, total_permits: 10 }), '', 'Generic counts are not historical results');
assert.equal(core.formatHistoricalDrawResult({ hunt_code: 'BR1013', dwr_result_display: '1 in 1.7' }), '1 in 1.7');
assert.equal(core.formatHistoricalDrawResult({ odds_2025_actual: 25 }), '1 in 4.0');
for (const hunt_code of ['BR7021', 'BR7022', 'BR7126', 'BR7127', 'BR7238', 'BR7239', 'BR7326']) {
  assert.equal(core.formatHistoricalDrawResult({ hunt_code, dwr_result_display: '1 in 1.7', odds_2025_actual: 25 }), '');
  assert.match(core.historicalDrawBoundaryReason({ hunt_code }), /No comparable 2025 draw history/);
}
console.log('Historical display: explicit actuals only; all seven split boundaries enforced');
overlay.applyCoreSnapshot({ filters, engineRows: [{ ...base, points: 10, prediction_certification_status: 'CERTIFIED', certified_p_draw_mean: .9 }] });
assert.equal(overlay.getSelection().huntCode, 'BR1013');
assert.equal(overlay.getSelectedOddsInfo(overlay.findContext(filters).selectedRow).percent, null, 'Never borrow another point rung');
assert(!overlay.comparableStatus({ modeled_draw_probability: .99 }).includes('99'), 'Comparison cards cannot publish raw odds');
assert(!overlay.sourceDetails(filters, { source_file: '2026/DATABASE.csv', source_page: '999' }, {}).includes('2026/DATABASE.csv'), 'Inherited catalog provenance is not historical draw evidence');

core.indexData([{ ...base, points: 10, prediction_certification_status: 'CERTIFIED', certified_p_draw_mean: .9 }], [], [], []);
assert.equal(core.getEngineGroupFallbackRow('BR1013', 'Resident', 'standard'), null, 'No borrowed draw rung when selected point is absent');
const adult = { ...base, draw_pool: 'adult', certified_p_draw_mean: .2 };
const youth = { ...base, draw_pool: 'youth', certified_p_draw_mean: .8 };
core.indexData([adult, youth], [adult, youth], [], []);
assert.equal(core.getLadderRows('BR1013', 'Resident', 'standard').length, 0, 'Ambiguous adult/youth pools must not silently fall back');
assert.equal(core.getLadderRows('BR1013', 'Resident', 'other').length, 0, 'Explicit pool must not borrow another pool');
assert.equal(core.getLadderRows('BR1013', 'Resident', 'youth')[0].certified_p_draw_mean, .8);
const residentLane = { ...base, residency: 'Resident', draw_pool: 'standard', certified_p_draw_mean: .2 };
const nonresidentLane = { ...base, residency: 'Nonresident', draw_pool: 'standard', certified_p_draw_mean: .8 };
core.indexData([residentLane, nonresidentLane], [residentLane, nonresidentLane], [], []);
assert.equal(core.getEngineRow('BR1013', 'Resident', 3, 'standard').certified_p_draw_mean, .2);
assert.equal(core.getEngineRow('BR1013', 'Nonresident', 3, 'standard').certified_p_draw_mean, .8);
assert.equal(core.getLadderRows('BR1013', 'Resident', 'standard')[0].residency, 'Resident');
assert.equal(core.getLadderRows('BR1013', 'Nonresident', 'standard')[0].residency, 'Nonresident');
core.indexData([residentLane], [residentLane], [], []);
assert.equal(core.getEngineRow('BR1013', 'Nonresident', 3, 'standard'), null, 'Missing Nonresident row must remain missing');
assert.equal(core.getLadderRows('BR1013', 'Nonresident', 'standard').length, 0, 'Missing Nonresident ladder must remain empty');
assert.equal(core.getHarvestSuccessDisplay({}, {}, { success_percent: 100, success_ratio: 1, prior_year_success_rate: 1 }), 'Not available');
assert.equal(core.getHarvestSuccessDisplay({}, { harvest_success_pct: 0.5 }, { success_percent: 100 }), '0.5%');
assert.equal(core.getHarvestSuccessDisplay({}, { harvest_success_pct: 87 }, { success_percent: 1.8 }), '87%');
const selected = { ...base, prediction_certification_status: 'CERTIFIED', certified_p_draw_mean: .2 };
overlay.applyCoreSnapshot({ filters, summaryRow: selected, engineRows: [{ ...selected, certified_p_draw_mean: .8 }], ladderRows: [selected] });
assert.equal(overlay.getSelectedOddsInfo(overlay.findContext(filters).selectedRow).percent, 20, 'Dashboard must use the core exact selected row, not conflicting summary data');
console.log('Exact point/pool and harvest-source regression checks passed');
