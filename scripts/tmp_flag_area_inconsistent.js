const fs = require('fs');
const XLSX = require('xlsx');

const staged = 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx';
const dbPath = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';

function parseCSVLine(line){
  const out=[]; let current=''; let inQuotes=false;
  for(let i=0;i<line.length;i++){
    const ch=line[i], nx=line[i+1];
    if(inQuotes){
      if(ch==='"' && nx==='"'){current+='"'; i++;}
      else if(ch==='"') inQuotes=false;
      else current+=ch;
    } else if(ch==='"'){inQuotes=true;}
    else if(ch===','){out.push(current); current='';}
    else current+=ch;
  }
  out.push(current);
  return out;
}
const rows=fs.readFileSync(dbPath,'utf8').replace(/\r/g,'').split('\n').filter(Boolean);
const headers=rows[0].split(',').map(s=>s.replace(/^"|"$/g,''));
const dbByCode=new Map();
for(let i=1;i<rows.length;i++){
  const cols=parseCSVLine(rows[i]);
  const rec={}; headers.forEach((h,idx)=>rec[h]=(cols[idx]||'').replace(/^"|"$/g,''));
  const code=String(rec.hunt_code||'').trim();
  if(code) dbByCode.set(code.toUpperCase(), rec);
}

function norm(v){return String(v||'').trim().toLowerCase().replace(/\s+/g,' ').replace(/&/g,' and ').replace(/\bmt\b/g,'mountain').replace(/\bmtns?\b/g,'mountain').replace(/[^a-z0-9 ]/g,' ').trim();}
function contains(a,b){return a.includes(b) || b.includes(a);}

const wb=XLSX.readFile(staged);
const ws=wb.Sheets[wb.SheetNames[0]];
const sheet=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});
const h=sheet[0];
const idxNo=h.indexOf('No.'); const idxCode=h.indexOf('HUNT CODE'); const idxArea=h.indexOf('Area');
let bad=0;
const rowsOut=[];
for(let i=1;i<sheet.length;i++){
  const row=sheet[i]; if(!row || !row[idxNo]) continue;
  const no=String(row[idxNo]||'').trim(); if(!no||no==='No.') continue;
  const area=norm(row[idxArea]);
  const codes=String(row[idxCode]||'').split('|').map(c=>c.trim()).filter(Boolean);
  if(!codes.length) continue;
  let matched=false; let best=[];
  for(const code of codes){
    const rec=dbByCode.get(code.toUpperCase());
    if(!rec){best.push(`${code}:missing`); continue;}
    const name=norm(rec.hunt_name);
    const s1=norm(rec.species); const s2=area;
    const areaMatch=!area || !name ? true : contains(area,name);
    best.push(`${code}:areaMatch${areaMatch?1:0}`);
    if(areaMatch) matched=true;
  }
  if(!matched){
    bad++;
    rowsOut.push(`${i+1}\t${no}\t${row[idxCode]}\t${row[idxArea]}\t${best.join('; ')}`);
  }
}
console.log('rows_flagged',bad);
rowsOut.slice(0,200).forEach(r=>console.log(r));
