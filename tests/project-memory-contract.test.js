const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const { validateProjectMemory } = require('../scripts/validate-project-memory');

const root = path.resolve(__dirname, '..');
const result = validateProjectMemory(root);

assert.deepStrictEqual(result.failures, [], result.failures.join('\n'));
assert(result.checks >= 40, `Expected a substantive memory contract, received ${result.checks} checks.`);
assert(result.facts.includes('promotion=BLOCKED'), 'The current uncertified build must remain explicitly blocked.');
const drawTruthPath = path.join(root, 'data_truth', 'draw_results_truth', 'normalized', 'draw_results_long.csv');
assert(
  fs.existsSync(drawTruthPath) || result.warnings.some((warning) => warning.includes('draw_results_long.csv')),
  'The external draw-truth hydration state must remain visible.',
);
assert(result.facts.some((fact) => fact.startsWith('known_contract_drift=')), 'Known source/design drift must remain visible.');

console.log(`project memory contract passed (${result.checks} checks, ${result.warnings.length} expected hydration warnings)`);
