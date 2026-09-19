/* Preserve the exact deployed static site, excluding unrelated local edits. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const blake3 = require('blake3-wasm');

async function main() {
  const [manifestPath, outputPath, reportName = 'pages_base_preservation.json'] = process.argv.slice(2);
  if (!manifestPath || !outputPath) throw new Error('Usage: manifest.json new-output-directory');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const output = path.resolve(outputPath);
  if (fs.existsSync(output)) throw new Error('Refusing to overwrite a prepared release');
  if (manifest.uses_functions) throw new Error('Static-only deployment required');
  const hash = (bytes, name) => blake3.hash(bytes.toString('base64') + path.extname(name).substring(1)).toString('hex').slice(0, 32);
  const evidence = [];
  for (const [name, expected] of Object.entries(manifest.files)) {
    const relative = name.replace(/^\/+/, '');
    const destination = path.resolve(output, relative);
    if (!destination.startsWith(output + path.sep)) throw new Error(`Unsafe deployment path: ${name}`);
    const local = path.resolve('pages-dist', relative);
    let bytes = fs.existsSync(local) ? fs.readFileSync(local) : null;
    let source = 'HASH_VERIFIED_LOCAL_DEPLOYMENT_COPY';
    if (!bytes || hash(bytes, relative) !== expected) {
      const response = await fetch(`${manifest.url}${encodeURI(name)}?release_snapshot=${manifest.id}`);
      if (!response.ok) throw new Error(`Unable to preserve ${name}: HTTP ${response.status}`);
      bytes = Buffer.from(await response.arrayBuffer());
      source = 'IMMUTABLE_DEPLOYMENT_READBACK';
    }
    if (hash(bytes, relative) !== expected) throw new Error(`Deployment asset hash mismatch: ${name}`);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.writeFileSync(destination, bytes);
    evidence.push({ path: name, deployment_hash: expected, sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length, source });
  }
  const result = { status: 'PASS_EXACT_DEPLOYED_BASE_PRESERVED', deployment: manifest.id, files: evidence.length,
    output, unrelated_local_assets_included: 0, evidence };
  const reportPath = path.join(path.dirname(output), reportName);
  if (fs.existsSync(reportPath)) throw new Error('Refusing to overwrite preserved base evidence');
  fs.writeFileSync(reportPath, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ status: result.status, files: result.files, output }));
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
