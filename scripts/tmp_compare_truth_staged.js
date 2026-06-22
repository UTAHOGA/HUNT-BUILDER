const fs = require('fs');
const XLSX = require('xlsx');

function sheetRows(rel){
  const wb = XLSX.readFile(rel);
  const s = wb.SheetNames[0];
  const rows = XLSX.utils.sheet_to_json(wb.Sheets[s], { header:1, defval: '' });
  const headers = rows[0] || [];
  const noIdx = headers.indexOf('No.');
  const codeIdx = headers.indexOf('HUNT CODE');
  const speciesIdx = headers.indexOf('SPECIES');
  const sexIdx = headers.indexOf('SEX');
  const huntIdx = headers.indexOf('HUNT NAME');
  const weaponIdx = headers.indexOf('WEAPON');
  if ([noIdx, codeIdx, speciesIdx, sexIdx, huntIdx, weaponIdx].some(i=>i<0)) {
    throw new Error('missing columns in '+rel);
  }
  const out=[];
  for (let i=1;i<rows.length;i++){
    const r=rows[i]||[];
    const no=String(r[noIdx]||'').trim();
    if(!no) continue;
    out.push({no,code:String(r[codeIdx]||'').trim(),species:String(r[speciesIdx]||'').trim(),sex:String(r[sexIdx]||'').trim(),hunt:String(r[huntIdx]||'').trim(),weapon:String(r[weaponIdx]||'').trim()});
  }
  return out;
}

const truth = sheetRows('data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx');
const staged = sheetRows('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const tmap = new Map(truth.map(r=>[r.no,r]));
const diffs=[];
const rowOnlyInTruth=[];
for (const s of staged){
  const t=tmap.get(s.no);
  if(!t){
    diffs.push({no:s.no, type:'missing_truth_row'});
    continue;
  }
  if((t.code||'')!== (s.code||'')) diffs.push({no:s.no,type:'code', truth:t.code, staged:s.code,species:t.species,sex:t.sex,hunt:t.hunt,weapon:t.weapon,st_species:s.species});
}
const stagedMap=new Map(staged.map(r=>[r.no,r]));
for (const t of truth){ if(!stagedMap.has(t.no)) rowOnlyInTruth.push(t.no); }
console.log('staged rows', staged.length,'truth rows',truth.length,'diffs',diffs.length,'missingTruthRows',rowOnlyInTruth.length);
let shown=0;
for (const d of diffs){ if(shown>=120) break; if(d.type==='code'){console.log([d.no,d.truth,d.staged,d.species,d.sex,d.hunt,d.weapon].join(' | '));} else {console.log(JSON.stringify(d));} shown++;}
