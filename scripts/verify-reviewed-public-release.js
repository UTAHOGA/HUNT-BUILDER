const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
async function main(){
  const root=path.resolve(process.argv[2]);
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-manifest.json'),'utf8'));
  const checks=[];
  for(const [host,origin] of Object.entries({pages:'https://huntbuilder.pages.dev',vercel:'https://huntbuilder.uoga.org'})){
    const files=manifest.hosts[host].files;
    const selected=new Set(manifest.overlay);
    for(const name of ['index.html','hard-copy.html','research.html','ui.js','header-layout.js']) selected.add(name);
    for(const code of ['BR1001','BR7004','MB6011','DB0008','DA1001','EA1010','TK1003']) selected.add(`processed_data/hunt_research_2026_split/hunts/${code}.json`);
    for(const folder of ['hard-copy/draw-results/2026/','public/hard-copy/draw-results/2026/']){
      for(const row of files.filter(r=>r.path.startsWith(folder)&&r.path.endsWith('.pdf')).slice(0,3))selected.add(row.path);
    }
    const geo=files.find(r=>r.path.endsWith('.geojson'));if(geo)selected.add(geo.path);
    await Promise.all([...selected].map(async name=>{
      const expected=files.find(r=>r.path===name);if(!expected)throw new Error(`Required candidate asset missing: ${name}`);
      const url=new URL('/'+name.split('/').map(encodeURIComponent).join('/'),origin);
      url.searchParams.set('reviewed_release','20260921-v2');
      const response=await fetch(url,{signal:AbortSignal.timeout(120000)});
      if(!response.ok||new URL(response.url).origin!==origin)throw new Error(`Public read failed: ${host}/${name}: ${response.status}`);
      const bytes=Buffer.from(await response.arrayBuffer()),actual=crypto.createHash('sha256').update(bytes).digest('hex');
      if(actual!==expected.sha256)throw new Error(`Public hash mismatch: ${host}/${name}`);
      checks.push({host,path:name,sha256:actual,bytes:bytes.length});
    }));
  }
  fs.writeFileSync(path.join(root,'public-readback.json'),JSON.stringify({status:'PASS',verified_at:new Date().toISOString(),checks},null,2)+'\n');
  console.log(`PASS: ${checks.length} public file readbacks; same Research shell on both hosts`);
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
