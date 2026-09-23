// Build isolated, host-preserving release candidates. No network or promotion.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ROOT = path.resolve(__dirname, '..');
const [evidenceArg, outputArg] = process.argv.slice(2);
if (!evidenceArg || !outputArg) throw new Error('Usage: evidence-directory NEW-output-directory');
const evidence = path.resolve(evidenceArg), output = path.resolve(outputArg);
if (fs.existsSync(output)) throw new Error('Refusing to overwrite a release candidate');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const pages = read(path.join(evidence, 'pages-backup-manifest.json'));
const vercel = read(path.join(evidence, 'vercel-public-before/manifest.json'));
const r2 = read(path.join(evidence, 'r2-verified/snapshot_manifest.json'));
if (pages.status !== 'PASS_EXACT_DEPLOYED_BASE_PRESERVED' || vercel.status !== 'PASS_PUBLIC_BUILD_INVENTORY_SNAPSHOT' || r2.status !== 'PASS') throw new Error('Verified backups required');
const overlay = ['research.html', 'config.js', 'hunt-research.js', 'assets/js/research-outlook-dashboard.js',
  'embed-mode.js', 'style.css', 'sentry-browser-init.js', 'data/runtime-manifest.json',
  'data/hunt-master-canonical-2026-foundation.json', 'data/hunt-master-canonical-2026-source-of-truth.json'];
for (const name of ['embed-mode.js','style.css','sentry-browser-init.js','data/runtime-manifest.json']) {
  const normalized = file => fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n');
  if(normalized(path.join(ROOT,name))!==normalized(path.join(evidence,'pages-backup',name))) throw new Error(`Unreviewed shared dependency change: ${name}`);
}
function safe(base, name) {
  const result = path.resolve(base, name.replace(/^\/+/, ''));
  if (!result.startsWith(base + path.sep)) throw new Error(`Unsafe path: ${name}`);
  return result;
}
function copy(source, base, name) {
  const dest = safe(base, name);
  fs.mkdirSync(path.dirname(dest), {recursive:true});
  fs.copyFileSync(source, dest);
}
function check(base, row) {
  const file = safe(base, row.path);
  if (hash(file) !== row.sha256 || fs.statSync(file).size !== row.bytes) throw new Error(`Backup hash mismatch: ${row.path}`);
  return file;
}
for (const row of vercel.evidence.filter(r=>r.status===200)) {
  if (new URL(row.final_url).origin !== new URL(vercel.origin).origin) throw new Error('Login redirects cannot be retained as public website files');
}
const targets = {pages:path.join(output,'pages-dist'), vercel:path.join(output,'vercel/.vercel/output/static')};
const manifests = {};
for (const [host, dest] of Object.entries(targets)) {
  fs.mkdirSync(dest,{recursive:true});
  const baseline = new Map();
  for (const row of pages.evidence) {
    const name = row.path.replace(/^\/+/, '');
    copy(check(path.join(evidence,'pages-backup'),row),dest,name);
    baseline.set(name,{...row,path:name});
  }
  // Preserve Vercel's distinct existing non-Research files. Restore missing
  // library/detail assets from the exact deployed Pages copy, never a dirty repo.
  if (host === 'vercel') for (const row of vercel.evidence.filter(r=>r.status===200)) {
    copy(check(path.join(evidence,'vercel-public-before/files'),row),dest,row.path);
    baseline.set(row.path,row);
  }
  for (const name of overlay) copy(path.join(ROOT,name),dest,name);
  const files = [...baseline.keys()].sort().map(name=>{
    const file = safe(dest,name), sha256=hash(file), previous=baseline.get(name);
    if (!overlay.includes(name) && sha256 !== previous.sha256) throw new Error(`Unapproved change: ${host}/${name}`);
    if (fs.statSync(file).size > 25*1024*1024) throw new Error(`Oversize Pages object: ${name}`);
    return {path:name,sha256,bytes:fs.statSync(file).size,previous_sha256:previous.sha256,reviewed_overlay:overlay.includes(name)};
  });
  manifests[host] = {output:dest,files};
}
for (const name of overlay) if(hash(path.join(targets.pages,name))!==hash(path.join(targets.vercel,name))) throw new Error(`Host contract mismatch: ${name}`);
for (const obj of r2.objects) if(hash(path.join(evidence,'r2-verified',obj.key))!==obj.sha256) throw new Error(`R2 backup changed: ${obj.key}`);
fs.writeFileSync(path.join(output,'vercel/.vercel/output/config.json'), JSON.stringify({version:3,routes:[{src:'/research',dest:'/research.html'},{handle:'filesystem'}]},null,2)+'\n');
const manifest = {status:'LOCAL_HASH_VERIFIED_NOT_DEPLOYED',source_revision:require('node:child_process').execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),
  created_at:new Date().toISOString(),overlay,hosts:manifests,r2_objects_unchanged:r2.objects,
  rollback:{pages_deployment:pages.deployment,vercel_deployment:'dpl_4uTKeSGStQyhu1eRQ33yh3koRwGg',pages_manifest:path.join(evidence,'pages-backup-manifest.json'),vercel_inventory:path.join(evidence,'vercel-public-before/manifest.json'),invalid_rejected_snapshot:path.join(evidence,'vercel-before')}};
fs.writeFileSync(path.join(output,'release-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({status:manifest.status,pages_files:manifests.pages.files.length,vercel_files:manifests.vercel.files.length,overlay}));
