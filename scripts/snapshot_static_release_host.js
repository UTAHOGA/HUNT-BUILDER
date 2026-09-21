// Read-only public-host snapshot. Retain the immutable deployment itself too:
// Git-built Vercel deployments do not expose a source file tree through /files.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { Readable, Transform } = require('stream');
const { pipeline } = require('stream/promises');

async function main() {
  const [origin, priorManifest, repo, output] = process.argv.slice(2);
  if (!origin || !priorManifest || !repo || !output) throw new Error('Usage: immutable-origin pages-manifest repo new-output');
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite snapshot');
  const baseline = JSON.parse(fs.readFileSync(priorManifest, 'utf8'));
  const candidates = new Set(Object.keys(baseline.files).map(p => p.replace(/^\/+/, '')));
  const build = fs.readFileSync(path.join(repo, 'scripts/build-pages-dist.js'), 'utf8');
  const arrays = Object.fromEntries(['rootFiles', 'dataFiles', 'processedFiles', 'dirsToCopy'].map(name => {
    const block = build.match(new RegExp(`const ${name} = \\[([\\s\\S]*?)\\];`));
    if (!block) throw new Error(`Missing build inventory: ${name}`);
    return [name, [...block[1].matchAll(/'([^']+)'/g)].map(m => m[1])];
  }));
  for (const name of [...arrays.rootFiles, ...arrays.dataFiles, ...arrays.processedFiles]) candidates.add(name);
  const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: repo, encoding: 'utf8', maxBuffer: 20e6 }).split('\0').filter(Boolean);
  for (const name of tracked) {
    if (arrays.dirsToCopy.some(dir => name.startsWith(`${dir}/`))) candidates.add(name);
    if (name.startsWith('public/hard-copy/')) candidates.add(name.substring(7));
  }
  fs.mkdirSync(output, { recursive: true });
  const pending = [...candidates].sort();
  const evidence = [];
  let next = 0;
  async function worker() {
    while (next < pending.length) {
      const name = pending[next++];
      const destination = path.resolve(output, 'files', name);
      if (!destination.startsWith(path.resolve(output, 'files') + path.sep)) throw new Error(`Unsafe path: ${name}`);
      const url = new URL(name, origin.endsWith('/') ? origin : origin + '/').href;
      const response = await fetch(url, { signal: AbortSignal.timeout(120000) });
      // Protected deployment URLs may return a 200 login page after redirect.
      // Such bytes are not a rollback copy of the requested website asset.
      if (new URL(response.url).origin !== new URL(origin).origin) {
        await response.body.cancel();
        throw new Error(`Cross-origin redirect is not a site backup: ${name} -> ${new URL(response.url).origin}`);
      }
      if (response.status === 404) {
        evidence.push({ path: name, status: 404 });
        await response.body.cancel();
        continue;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
      const digest = crypto.createHash('sha256');
      let bytes = 0;
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      const meter = new Transform({ transform(chunk, _, callback) { bytes += chunk.length; digest.update(chunk); callback(null, chunk); } });
      await pipeline(Readable.fromWeb(response.body), meter, fs.createWriteStream(destination, { flags: 'wx' }));
      evidence.push({ path: name, status: response.status, sha256: digest.digest('hex'), bytes, final_url: response.url });
      if (evidence.length % 100 === 0) console.log(`SNAPSHOT ${evidence.length}/${pending.length}`);
    }
  }
  await Promise.all(Array.from({ length: 8 }, worker));
  const report = { status: 'PASS_PUBLIC_BUILD_INVENTORY_SNAPSHOT', origin,
    inventory_scope: 'Union of exact Pages deployment and source-declared public build inputs; immutable Vercel deployment retained for whole-site rollback',
    created_at: new Date().toISOString(), checked: evidence.length,
    files: evidence.filter(e => e.status === 200).length, evidence: evidence.sort((a,b) => a.path.localeCompare(b.path)) };
  fs.writeFileSync(path.join(output, 'manifest.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ status: report.status, checked: report.checked, files: report.files }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
