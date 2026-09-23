// Post-build retention guard: a clean Git checkout must not silently remove
// deployed document/boundary/detail assets that are deliberately kept out of Git.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ROOT = path.resolve(__dirname, '..');
const OUTPUT = path.join(ROOT, 'pages-dist');
async function main() {
  const pins = JSON.parse(fs.readFileSync(path.join(ROOT,'governance/website-retained-assets.json'),'utf8'));
  // Derived data is released separately, never synthesized from fixtures by a
  // website build. Keep these previously reviewed public contracts byte-exact.
  const retainedData = name => name.startsWith('processed_data/public_contracts/') || name.startsWith('processed_data/production/') ||
    ['data/hunt_predictions.json','data/hunt_odds_history.json','data/hunt_odds_history.csv','data/hunt_application_outlook.json','data/public_contract_summary.json','data/source_snapshots.json'].includes(name);
  const pending = pins.files.filter(row=>!fs.existsSync(path.join(OUTPUT,row.path)) || retainedData(row.path));
  let next = 0;
  await Promise.all(Array.from({length:8}, async()=>{
    while(next < pending.length) {
      const row = pending[next++];
      const file = path.resolve(OUTPUT,row.path);
      if(!file.startsWith(OUTPUT+path.sep)) throw new Error(`Unsafe retained asset path: ${row.path}`);
      const url = new URL(row.path, pins.source_origin + '/');
      const response = await fetch(url, {signal:AbortSignal.timeout(120000)});
      if(!response.ok || new URL(response.url).origin !== url.origin) throw new Error(`Retained asset unavailable: ${row.path}`);
      const bytes = Buffer.from(await response.arrayBuffer());
      if(bytes.length!==row.bytes || crypto.createHash('sha256').update(bytes).digest('hex')!==row.sha256) throw new Error(`Retained asset hash mismatch: ${row.path}`);
      fs.mkdirSync(path.dirname(file),{recursive:true});
      fs.writeFileSync(file,bytes,{flag:retainedData(row.path)?'w':'wx'});
    }
  }));
  for(const row of pins.files) if(!fs.existsSync(path.join(OUTPUT,row.path))) throw new Error(`Build lost retained URL: ${row.path}`);
  console.log(`PASS: ${pins.files.length} retained URLs present; ${pending.length} missing assets restored with verified hashes`);
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
