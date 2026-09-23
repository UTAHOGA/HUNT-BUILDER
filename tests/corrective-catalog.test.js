const assert = require('node:assert/strict');
const fs = require('node:fs');
const cp = require('node:child_process');
const v = require('../scripts/verify-permit-allocations-2026');
const database = v.loadDatabase();
const numeric = ['permits_2026_res', 'permits_2026_nr', 'permits_2026_total', 'conservation_permits_2026_total'];
for (const name of v.JSON_ROW_TARGETS) {
  if (!name.startsWith('data/')) {
    const beforeDocument = JSON.parse(cp.execFileSync('git', ['show', `HEAD:${name}`], {encoding:'utf8',maxBuffer:30e6}));
    const afterDocument = JSON.parse(fs.readFileSync(name,'utf8'));
    delete beforeDocument.hunt_catalog; delete afterDocument.hunt_catalog;
    assert.deepEqual(afterDocument,beforeDocument,`${name}: unrelated page-contract sections changed`);
  }
  const before = v.rowsFromJson(JSON.parse(cp.execFileSync('git', ['show', `HEAD:${name}`], {encoding:'utf8', maxBuffer:30e6})));
  const prior = new Map(before.map(r => [r.hunt_code, r]));
  const current = v.rowsFromJson(JSON.parse(fs.readFileSync(name, 'utf8')));
  assert.equal(current.length, database.index.size, name);
  assert.equal(new Set(current.map(r=>r.hunt_code)).size, current.length);
  for (const r of current) {
    const expected = database.index.get(r.hunt_code);
    assert(expected, `${name}: unrecognized code ${r.hunt_code}`);
    assert.deepEqual(v.verifyRecord(r, expected, name, 0), []);
    // The 1,848-row current catalog's quota values are never changed by this repair.
    if (name.startsWith('data/')) for (const f of numeric) assert.equal(r[f], prior.get(r.hunt_code)[f], `${r.hunt_code}/${f}`);
  }
}
const canonical = v.normalizedAllocation({hunt_code:'TEST', permits_2026_total:'10', permits_2026_source:'CANONICAL_YEARLY_DRAW_RESULTS_2026_FOR_2027_MODEL'});
assert.equal(canonical.permits_2026_source, 'CANONICAL_YEARLY_DRAW_RESULTS_2026_FOR_2027_MODEL');
assert(v.verifyRecord({...canonical, permits_2026_total:'11'}, canonical, 'fixture', 0).some(i=>i.field==='permits_2026_total'));
assert(v.verifyRecord({...canonical, permits_2026_source:'MADE_UP'}, canonical, 'fixture', 0).some(i=>i.field==='permits_2026_source'));
assert(v.verifyRecord({...canonical, permits_2026_nr:'1'}, canonical, 'fixture', 0).some(i=>i.type==='TOTAL_ONLY_HAS_INFERRED_SPLIT'));
console.log('PASS: all five catalogs match source, numeric quotas unchanged, incorrect quotas/provenance/splits rejected');
