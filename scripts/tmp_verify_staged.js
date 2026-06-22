const XLSX=require('xlsx');
const fs=require('fs');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
const bad=[];
for(let i=1;i<rows.length;i++){
  const no=String(rows[i][0]||'');
  if(no==='No.') bad.push(i+1);
}
const dbLines=fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n');
const db=new Set();
for(let i=1;i<dbLines.length;i++){
  const code=(dbLines[i].split(',')[0]||'').replace(/"/g,'').trim();
  if(code) db.add(code);
}
const invalidCodes=new Set();
for(let i=1;i<rows.length;i++){
  const codeCell=String(rows[i][1]||'');
  const no=String(rows[i][0]||'');
  if(!no || no==='No.') continue;
  for(const c of codeCell.split('|').map(x=>x.trim()).filter(Boolean)){
    if(!db.has(c)) invalidCodes.add(c);
  }
}
console.log('dataRows',rows.length-1);
console.log('badNoHeaders',bad.length);
console.log('invalidCodes',Array.from(invalidCodes).sort().join(','));
