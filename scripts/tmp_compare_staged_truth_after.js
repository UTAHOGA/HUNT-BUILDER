const XLSX=require('xlsx');
function read(rel, codeHeader){
  const wb=XLSX.readFile(rel);
  const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
  const h=rows[0];
  const noIdx=h.indexOf('No.')>=0?h.indexOf('No.'):h.indexOf('No');
  const codeIdx=h.indexOf(codeHeader);
  const out=[];
  for(let i=1;i<rows.length;i++){
    const no=String(rows[i][noIdx]||'').trim(); if(!no) continue; out.push({no,code:String(rows[i][codeIdx]||'').trim()});
  }
  return new Map(out.map(r=>[r.no,r.code]));
}
const t=read('data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx','HUNT CODE');
const s=read('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx','HUNT CODE');
let changed=0; let missing=[]; let mismatch=[];
for(const [no,code] of t){ const cc=s.get(no); if(!cc){missing.push(no);continue;} if(code!==cc) mismatch.push([no,code,cc]); }
console.log('missing',missing.length,'mismatch',mismatch.length);
for(const m of mismatch.slice(0,40)) console.log(m.join(' | '));
