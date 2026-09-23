const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(process.argv[2]);
const repo=path.resolve(__dirname,'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
const before=read('../r2-verified/snapshot_manifest.json');
const afterObjects=before.objects.map(expected=>{
  let local=path.join(root,'../r2-after',expected.key);
  const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  if(hash(local)!==expected.sha256 && expected.key==='processed_data/draw_reality_engine_predictive_v2.csv') {
    // A reset interrupted the first readback. Retain it and verify the separate retry.
    local=path.join(root,'../r2-after-predictive-retry.csv');
  }
  const sha256=hash(local),bytes=fs.statSync(local).size;
  if(sha256!==expected.sha256||bytes!==expected.bytes)throw new Error(`Post-release R2 mismatch: ${expected.key}`);
  return {key:expected.key,sha256,bytes,local_readback:local};
});
fs.writeFileSync(path.join(root,'../r2-after/snapshot_manifest.json'),JSON.stringify({status:'PASS',verified_at:new Date().toISOString(),objects:afterObjects},null,2)+'\n',{flag:'wx'});
const records=['vercel-upload-verification.json','pages-upload-verification.json','public-readback.json',
  'browser-qa-preview-pages-full.json','browser-qa-live-vercel-full.json','browser-qa-live-pages-smoke.json',
  '../r2-after/snapshot_manifest.json'];
const checks=records.map(name=>{
  const data=read(name);
  if(data.status!=='PASS')throw new Error(`Release verification did not pass: ${name}`);
  if(name.endsWith('-full.json')&&data.scenarios.length!==1255)throw new Error(`Incomplete population QA: ${name}`);
  return {report:name,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex'),status:data.status,
    ...(data.scenarios?{scenarios:data.scenarios.length,failed_requests:data.failed_requests.length,console_errors:data.console_errors.length}:{})};
});
const release=read('release-manifest.json');
release.base_revision=release.source_revision;delete release.source_revision;
release.source_state='REVIEWED_WORKTREE_OVERLAY_ON_BASE_REVISION';
release.status='PROMOTED_AND_PUBLICLY_VERIFIED';
release.verified_at=new Date().toISOString();
release.production={pages:read('pages-upload-verification.json').deployment,vercel:read('vercel-upload-verification.json').deployment,
  urls:['https://huntbuilder.uoga.org/research.html','https://huntbuilder.pages.dev/research']};
release.checks=checks;
const output=path.join(repo,'governance/releases/20260921-corrective-release.json');
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify(release,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:release.status,output,checks:checks.length}));
