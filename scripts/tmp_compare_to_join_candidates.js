const fs = require('fs');
const XLSX = require('xlsx');

const joinFile = 'data_truth/harvest_results_truth/raw_packages/unknown_for_unknown_full_joined_harvest_backcheck_conservation_annual_per_row_corrected/conservation_permit_hunt_code_join_candidates_annual_per_row.csv';
const staged = 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx';

function parseCsv(path){
  const raw = fs.readFileSync(path,'utf8').replace(/^\uFEFF/, '').replace(/\r/g,'');
  const lines = raw.split('\n').filter(l => l.length);
  if (!lines.length) return [];
  const headers = lines[0].split(',').map((h) => h.replace(/^"|"$/g,''));
  const parseLine = (line) => {
    const out=[]; let cur=''; let q=false;
    for(let i=0;i<line.length;i++){
      const ch=line[i]; const next=line[i+1];
      if(q){
        if(ch==='"' && next==='"'){cur+='"';i++;}
        else if(ch==='"') q=false; else cur+=ch;
      } else {
        if(ch==='"') q=true;
        else if(ch===','){out.push(cur);cur='';}
        else cur+=ch;
      }
    }
    out.push(cur); return out;
  };
  const out=[];
  for(let i=1;i<lines.length;i++){
    if(!lines[i].trim()) continue;
    const vals=parseLine(lines[i]);
    const row={}; headers.forEach((h,idx)=>row[h]=vals[idx]||'');
    out.push(row);
  }
  return out;
}

const joinRows = parseCsv(joinFile).filter(r => String(r.source_no||'').trim() && String(r.source_year_range||'') === '2025-2027');
const joinByNo = new Map();
for (const r of joinRows) {
  const no = String(r.source_no).trim();
  const sel = String(r.selected_hunt_code||'').trim();
  const conf = String(r.match_confidence||r.match_confidence||'').toLowerCase().trim();
  joinByNo.set(no, { code: sel, conf, all: r.possible_hunt_codes, method: r.match_method, condition: r.condition, species: r.species, area: r.area, organization:r.organization });
}

const wb = XLSX.readFile(staged);
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header:1, defval:'' });
const h = rows[0];
const ixNo = h.indexOf('No.');
const ixCode = h.indexOf('HUNT CODE');

let mismatch=0; const mism=[];
for(let i=1;i<rows.length;i++){
  const no = String(rows[i][ixNo]||'').trim();
  if(!no || no==='No.') continue;
  const stagedCode = String(rows[i][ixCode]||'').trim();
  const joined = joinByNo.get(no);
  if(!joined){ continue; }
  if (joined.code && stagedCode !== joined.code) {
    mismatch++;
    mism.push({ no, staged: stagedCode, join: joined.code, conf: joined.conf, possible: joined.all, method: joined.method, area: joined.area, cond: joined.condition, species: joined.species, org: joined.organization });
  }
}

console.log('join rows', joinRows.length);
console.log('mismatch', mismatch);
mism.slice(0,120).forEach(m => {
  console.log(`${m.no}\t${m.staged}\t${m.join}\t${m.conf}\t${m.area}\t${m.cond}\t${m.species}`);
});
