const fs = require('fs');
const XLSX = require('xlsx');

const dbText = fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv', 'utf8').replace(/\r/g, '');
const dbLines = dbText.split('\n').slice(1);
const db = new Set();
for (const l of dbLines) {
  if (!l.trim()) continue;
  const vals=[];
  let cur=''; let q=false;
  for (let i=0;i<l.length;i++){
    const ch=l[i], nx=l[i+1];
    if(q){ if(ch==='"'&&nx==='"'){cur+='"';i++;}
      else if(ch==='"') q=false; else cur+=ch; }
    else { if(ch==='"') q=true; else if(ch===','){vals.push(cur);cur='';} else cur+=ch; }
  }
  vals.push(cur);
  const c = (vals[0] || '').replace(/"/g, '').trim();
  if(c) db.add(c.toUpperCase());
}

const wb = XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header:1, defval:''});
const headers=rows[0];
const codeIdx=headers.indexOf('HUNT CODE');
let bad=[];
for (let i=1;i<rows.length;i++) {
  const row = rows[i] || [];
  const no = String(row[0] || '').trim();
  const codes = String(row[codeIdx] || '').split('|').map(s=>s.trim()).filter(Boolean);
  for (const code of codes) {
    if (!db.has(code.toUpperCase())) {
      bad.push({row: i+1, no, code});
    }
  }
}

console.log('bad', bad.length);
for (const b of bad) {
  console.log(`${b.row}\t${b.no}\t${b.code}`);
}
