// Restore the frozen small per-hunt runtime for clean-checkout website builds.
// Never generate probabilities or silently overwrite mismatching local data.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const ROOT = path.resolve(__dirname, '..');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

async function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'governance/research-detail-assets.json'), 'utf8'));
  let next = 0, restored = 0;
  await Promise.all(Array.from({ length: 8 }, async () => {
    while (next < manifest.files.length) {
      const file = manifest.files[next++];
      if (!/^processed_data\/hunt_research_2026_split\/hunts\/[A-Z0-9]+\.json$/.test(file.path)) throw new Error('Invalid runtime asset path');
      const destination = path.join(ROOT, file.path);
      if (fs.existsSync(destination)) {
        if (hash(fs.readFileSync(destination)) !== file.sha256) throw new Error(`Local runtime differs from reviewed release: ${file.path}`);
        continue;
      }
      const response = await fetch(`${manifest.source_origin}/${file.path}`, { signal: AbortSignal.timeout(60000) });
      if (!response.ok) throw new Error(`Runtime hydration HTTP ${response.status}: ${file.path}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      if (bytes.length !== file.bytes || hash(bytes) !== file.sha256) throw new Error(`Runtime hash mismatch: ${file.path}`);
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      fs.writeFileSync(destination, bytes, { flag: 'wx' });
      restored++;
    }
  }));
  console.log(`Reviewed Research detail files verified: ${manifest.files.length}; restored: ${restored}`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
