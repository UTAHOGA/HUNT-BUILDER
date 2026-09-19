/* Overlay the reviewed core contract onto the exact preserved deployed site. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const blake3 = require('blake3-wasm');
const ROOT = path.resolve(__dirname, '..');
const BASE = path.join(ROOT, 'audits/prediction_release_candidates/core_le_deer_repair_20260919');
const [candidateName = 'research_candidate', siteName = 'pages-release', baseReport = 'pages_base_preservation.json', overlayReport = 'pages_overlay_verification.json'] = process.argv.slice(2);
const SITE = path.join(BASE, siteName);
const CONTRACT = path.join(BASE, candidateName, 'processed_data');
const sha = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
const deployedHash = (bytes, name) => blake3.hash(bytes.toString('base64') + path.extname(name).substring(1)).toString('hex').slice(0, 32);

function walk(folder) {
  return fs.readdirSync(folder, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(folder, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

const reportPath = path.join(BASE, overlayReport);
if (fs.existsSync(reportPath)) throw new Error('Refusing to overwrite a frozen Pages overlay');
const preserved = JSON.parse(fs.readFileSync(path.join(BASE, baseReport)));
const before = new Map(preserved.evidence.map((row) => [row.path.slice(1), row]));
for (const [name, evidence] of before) {
  if (sha(fs.readFileSync(path.join(SITE, name))) !== evidence.sha256) throw new Error(`Preserved base changed: ${name}`);
}
const selected = new Map(['research.html', 'config.js', 'hunt-research.js'].map((name) => [name, path.join(ROOT, name)]));
selected.set('processed_data/hunt_research_2026_summary.json', path.join(CONTRACT, 'hunt_research_2026_summary.json'));
selected.set('processed_data/hunt_research_2026_split/hunt_research_2026.index.json', path.join(CONTRACT, 'hunt_research_2026_split/hunt_research_2026.index.json'));
for (const name of fs.readdirSync(path.join(CONTRACT, 'hunt_research_2026_split/hunts'))) {
  if (!/^[A-Z0-9_-]+\.json$/.test(name)) throw new Error(`Unexpected direct detail: ${name}`);
  selected.set(`processed_data/hunt_research_2026_split/hunts/${name}`, path.join(CONTRACT, 'hunt_research_2026_split/hunts', name));
}
for (const [name, source] of selected) {
  const bytes = fs.readFileSync(source);
  if (bytes.length > 25 * 1024 * 1024) throw new Error(`Pages limit: ${name}`);
  fs.mkdirSync(path.dirname(path.join(SITE, name)), { recursive: true });
  fs.copyFileSync(source, path.join(SITE, name));
}
const changed = [], added = [], unchanged = [];
const files = {};
for (const full of walk(SITE)) {
  const name = path.relative(SITE, full).split(path.sep).join('/');
  const bytes = fs.readFileSync(full);
  const digest = sha(bytes);
  files[`/${name}`] = deployedHash(bytes, name);
  if (before.get(name)?.sha256 === digest) unchanged.push(name);
  else {
    if (!selected.has(name)) throw new Error(`Unapproved change: ${name}`);
    if (digest !== sha(fs.readFileSync(selected.get(name)))) throw new Error(`Overlay differs: ${name}`);
    (before.has(name) ? changed : added).push({ path: name, sha256: digest, before_sha256: before.get(name)?.sha256 || null });
  }
}
const missing = [...before.keys()].filter((name) => !files[`/${name}`]);
if (missing.length) throw new Error(`Original production files removed: ${missing}`);
const report = { status: 'PASS_ONLY_REVIEWED_CORE_OVERLAY', original_deployment: preserved.deployment,
  original_files_preserved_or_explicitly_updated: before.size, changed, added,
  untouched_file_count: unchanged.length, untouched_files: unchanged, removed_files: missing,
  expected_deployment_files: files, root_worktree_deployed: false,
  oversized_runtime_objects: 'R2_ONLY_NOT_COPIED_TO_PAGES',
};
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ status: report.status, changed: changed.length, added: added.length, untouched: unchanged.length, removed: missing.length }));
