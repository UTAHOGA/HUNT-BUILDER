const fs = require('fs');
const path = require('path');
const assert = require('assert');

const root = path.resolve(__dirname, '..');
const researchHtml = fs.readFileSync(path.join(root, 'research.html'), 'utf8');
const huntResearchJs = fs.readFileSync(path.join(root, 'hunt-research.js'), 'utf8');
const outlookDashboardJs = fs.readFileSync(path.join(root, 'assets', 'js', 'research-outlook-dashboard.js'), 'utf8');

assert(researchHtml.includes('id="pointLadderAccordion"'), 'point ladder accordion should have a stable id');
assert(researchHtml.includes('Hunt Data Snapshot'), 'modal should be decision-focused, not source-focused');
assert(researchHtml.includes('source-plain-note'), 'modal should include plain-language context styling');

assert(huntResearchJs.includes('pointLadderAccordion: document.getElementById'), 'ladder accordion should be wired in JS');
assert(huntResearchJs.includes('function setupLadderAutoOpen()'), 'ladder should auto-open setup function');
assert(huntResearchJs.includes('IntersectionObserver'), 'ladder should open when scrolled into view');
assert(huntResearchJs.includes("addEventListener('mouseenter'"), 'ladder should open on mouse entry');
assert(huntResearchJs.includes('function buildDecisionBoxes('), 'hunt data popup should render decision boxes');
assert(huntResearchJs.includes('Can You Catch The Train?'), 'hunt data popup should explain catch-up status');
assert(huntResearchJs.includes('Plain-English Formula'), 'hunt data popup should explain algorithm plainly');
assert(huntResearchJs.includes('Harvest Snapshot'), 'hunt data popup should show mapped harvest data');
assert(huntResearchJs.includes('buildDecisionBoxes(meta, row, referenceRow, filters)'), 'modal should use decision boxes');
assert(huntResearchJs.includes('referenceRow?.harvest'), 'harvest snapshot should accept split-detail harvest aliases');
assert(huntResearchJs.includes('referenceRow?.hunters'), 'harvest snapshot should accept split-detail hunter aliases');
assert(huntResearchJs.includes('referenceRow?.satisfaction'), 'harvest snapshot should accept split-detail satisfaction aliases');

assert(outlookDashboardJs.includes('annual harvested age'), 'annual harvest age should be labeled explicitly');
assert(outlookDashboardJs.includes('DWR-reported 3-year harvest age'), 'reported three-year harvest age should be shown separately');
assert(outlookDashboardJs.includes('DWR unit current harvested age (3-year avg)'), 'Hunt Planner current age should stay distinct');
assert(outlookDashboardJs.includes('hunter satisfaction'), 'satisfaction should replace the empty percent-five-plus tile');
assert(outlookDashboardJs.includes('Hunt Quality Profile'), 'Hunt Research should show the Hunt Quality Profile');
assert(outlookDashboardJs.includes('U.O.G.A. score, not a DWR score'), 'the profile must be distinguished from DWR measures');
assert(outlookDashboardJs.includes('management_objective_target'), 'the exact management target should be displayed');
assert(outlookDashboardJs.includes('management_current_value'), 'the matching current management measure should be displayed');
assert(!outlookDashboardJs.includes('metricRow("Percent 5+"'), 'empty percent-five-plus metric should not render');

console.log('hunt research ladder/data panel guard passed');
