const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const [releaseRoot] = process.argv.slice(2);
if(!releaseRoot) throw new Error('Release directory required');
const root = path.resolve(releaseRoot);
const tree = JSON.parse(fs.readFileSync(path.join(root,'vercel-uploaded-tree.json'),'utf8'));
const release = JSON.parse(fs.readFileSync(path.join(root,'release-manifest.json'),'utf8'));
const files = new Map();
function walk(rows,parent='') {for(const row of rows){const name=parent?`${parent}/${row.name}`:row.name;if(row.type==='directory')walk(row.children||[],name);else files.set(name,row.uid);}}
walk(tree);
let checked=0;
for(const row of release.hosts.vercel.files){
  const bytes=fs.readFileSync(path.join(root,'vercel/.vercel/output/static',row.path));
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==row.sha256)throw new Error(`Local candidate mutated: ${row.path}`);
  if(crypto.createHash('sha1').update(bytes).digest('hex')!==files.get(`src/.vercel/output/static/${row.path}`))throw new Error(`Uploaded object mismatch: ${row.path}`);
  checked++;
}
const result={status:'PASS',deployment:'dpl_F3Zwa8DGDx19CP7HLdr73jRCo7PM',checked,method:'Local SHA256 release manifest plus Vercel content-addressed SHA1 upload inventory'};
fs.writeFileSync(path.join(root,'vercel-upload-verification.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
