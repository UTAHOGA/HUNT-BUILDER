const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),blake3=require('blake3-wasm');
const root=path.resolve(process.argv[2]);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-manifest.json'),'utf8'));
const remote=JSON.parse(fs.readFileSync(path.join(root,'pages-promoted.json'),'utf8'));
if(remote.environment!=='production'||Object.keys(remote.files).length!==manifest.hosts.pages.files.length)throw new Error('Unexpected production inventory');
for(const row of manifest.hosts.pages.files){
  const bytes=fs.readFileSync(path.join(root,'pages-dist',row.path));
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==row.sha256)throw new Error(`Local hash drift: ${row.path}`);
  const uploadHash=blake3.hash(bytes.toString('base64')+path.extname(row.path).substring(1)).toString('hex').slice(0,32);
  if(remote.files['/'+row.path]!==uploadHash)throw new Error(`Deployed Pages hash mismatch: ${row.path}`);
}
const result={status:'PASS',deployment:remote.id,files:manifest.hosts.pages.files.length,method:'SHA256 candidate plus exact Cloudflare content-addressed deployment manifest'};
fs.writeFileSync(path.join(root,'pages-upload-verification.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
