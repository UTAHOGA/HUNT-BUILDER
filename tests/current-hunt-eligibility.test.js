const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const manifest = JSON.parse(fs.readFileSync('data/hunt-eligibility-2026.json', 'utf8'));
const window = {};
vm.runInNewContext(fs.readFileSync('assets/js/current-hunt-eligibility.js', 'utf8'), { window });
const api = window.UOGA_HUNT_ELIGIBILITY;
assert.equal(api.isCurrent('BR7004'), false, 'Fail closed until evidence loads');
api.install(manifest);
const catalog = JSON.parse(fs.readFileSync('data/hunt-master-canonical-2026-foundation.json', 'utf8'));
assert.equal(Object.keys(manifest.records).length, catalog.length);
assert.equal(new Set([...manifest.current_codes, ...manifest.historical_reference_codes]).size, catalog.length);
assert.equal(manifest.current_codes.length + manifest.historical_reference_codes.length, catalog.length);
for (const code of ['BR7004', 'MB6011', 'PD1050', 'LD1020']) assert(api.isCurrent(code), code);
for (const code of ['PD1025', 'BR7008', 'BR7108', 'BR7208', 'BR7324', 'CG9999', 'BR1018', 'UNKNOWN']) assert(!api.isCurrent(code), code);
for (const row of catalog) {
  assert.equal(api.isCurrent(row), manifest.current_codes.includes(row.hunt_code));
}
assert(catalog.some(row => row.hunt_code === 'PD1025'), 'Retired source record must be retained');
assert.equal(manifest.records.PD1025.successor_hunt_code, 'PD1050');
console.log(`Eligibility checked across ${catalog.length} records: ${manifest.current_codes.length} current, ${manifest.historical_reference_codes.length} retained separately`);
