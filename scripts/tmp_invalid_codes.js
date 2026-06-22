const XLSX=require('xlsx');const fs=require('fs');
function parseSet(code){return String(code||'').split('|').map(s=>String(s).trim()).filter(Boolean);}
const db= new Set();
for (const row of require('fs').readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n').slice(1)) {
  if(!row.trim()) continue;
  const code=(row.split(',')[0]||'').replace(/"/g,'').trim();
  if(code) db.add(code);
}
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header:1,defval:''});
let bad=[];
for(let i=1;i<rows.length;i++){
  const r=rows[i]||[];
  const no=r[0];
  const code=String(r[1]||'');
  if(!no) continue;
  const set=parseSet(code);
  for (const c of set){if(!db.has(c)) bad.push({no,code:c,row:i+1});}
}
console.log('singleRows', bad.filter(x=>parseSet(x.code).length===1).length); // nonsense
console.log('bad total candidates', bad.length);
for(const b of bad.slice(0,120)) console.log(b.no+'|'+b.code);
