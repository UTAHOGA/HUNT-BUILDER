// Generate compact pins and align the legacy page-catalog copies, without
// touching historical canonicals, quotas, predictions or frozen audit evidence.
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const [snapshotPath, origin] = process.argv.slice(2);
if (!snapshotPath || !origin) throw new Error('Usage: verified-pages-backup-manifest immutable-origin');
const snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
if (snapshot.status !== 'PASS_EXACT_DEPLOYED_BASE_PRESERVED') throw new Error('Verified backup required');
const files = snapshot.evidence.filter(row => /^\/processed_data\/hunt_research_2026_split\/hunts\/[A-Z0-9]+\.json$/.test(row.path))
  .map(({ path: name, sha256, bytes }) => ({ path: name.slice(1), sha256, bytes }));
if (!files.length) throw new Error('No direct runtime files in snapshot');
const manifest = { schema: 'reviewed-research-details.v1', source_origin: origin, deployment: snapshot.deployment,
  role: 'Byte-identical deployed details; not a new prediction certification', files };
const destination = path.join(ROOT, 'governance/research-detail-assets.json');
if (fs.existsSync(destination)) throw new Error('Do not overwrite frozen asset pins');
fs.writeFileSync(destination, JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
const retained = {schema:'reviewed-site-retention.v1',source_origin:origin,deployment:snapshot.deployment,
  files:snapshot.evidence.map(({path:name,sha256,bytes})=>({path:name.replace(/^\/+/,''),sha256,bytes}))};
fs.writeFileSync(path.join(ROOT,'governance/website-retained-assets.json'),JSON.stringify(retained,null,2)+'\n',{flag:'wx'});
const catalog = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/hunt-master-canonical-2026-foundation.json'), 'utf8'));
for (const relative of ['canonical/hunt-planner-2026.json', 'generated/pages/hunt-planner.json']) {
  const file = path.join(ROOT, relative);
  const document = JSON.parse(fs.readFileSync(file, 'utf8'));
  document.hunt_catalog = catalog;
  fs.writeFileSync(file, JSON.stringify(document, null, 2) + '\n');
}
console.log(JSON.stringify({ pinned_runtime_files: files.length, aligned_catalog_rows: catalog.length }));
