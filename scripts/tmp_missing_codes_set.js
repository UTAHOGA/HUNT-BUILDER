const XLSX=require('xlsx');
const fs=require('fs');
const parseRows=fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n');
const db=new Set();
for(let i=1;i<parseRows.length;i++){
  const row=parseRows[i]; if(!row.trim()) continue; const c=row.split(',')[0]; if(c) db.add(c.replace(/"/g,''));
}
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
const missing=new Set();
for(let i=1;i<rows.length;i++){
  const no=String(rows[i][0]||'').trim();
  if(!no || no==='No.') continue;
  const codes=String(rows[i][1]||'').split('|').map(s=>s.trim()).filter(Boolean);
  for(const code of codes){ if(!db.has(code)) missing.add(code);} 
}
console.log([...missing].sort().join('\n'));
