const XLSX=require('xlsx');
function toMap(row){const out={}; for(const [k,v] of Object.entries(row)) out[k.toLowerCase()] = String(v||'').trim(); return out;}
function idx(headers, names){
 for(const n of names){
   const i = headers.findIndex(h => h.toLowerCase()===n.toLowerCase());
   if(i>=0) return i;
 }
 return -1;
}
function read(rel, speciesName, areaName, condName, codeName, noName='No.'){
 const wb = XLSX.readFile(rel);
 const s = wb.SheetNames[0];
 const rows = XLSX.utils.sheet_to_json(wb.Sheets[s], { header:1, defval:'' });
 const h = rows[0] || [];
 const noIdx = idx(h,['No.','No']);
 const codeIdx = idx(h,['HUNT CODE']);
 const speciesIdx = idx(h,[speciesName,'SPECIES']);
 const areaIdx = idx(h,[areaName,'Area','HUNT NAME','Hunt Name']);
 const condIdx = idx(h,[condName,'Condition','WEAPON','Weapon']);
 const out=[];
 for(let i=1;i<rows.length;i++){
   const r = rows[i]||[];
   if(!String(r[noIdx]||'').trim()) continue;
   out.push({rowNum:i+1,no:String(r[noIdx]).trim(),code:String(r[codeIdx]||'').trim(),species:String(r[speciesIdx]||'').trim(),area:String(r[areaIdx]||'').trim(),cond:String(r[condIdx]||'').trim()});
 }
 return out;
}
const truth = read('data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx','SPECIES','HUNT NAME','WEAPON','HUNT CODE');
const staged = read('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx','Species','Area','Condition','HUNT CODE');
console.log('counts', truth.length, staged.length);
const mism=[];
const tByNo = new Map(truth.map(r=>[r.no,r]));
for(const s of staged){
 const t=tByNo.get(s.no);
 if(!t){mism.push({no:s.no,type:'missing_truth',staged:s.code,species:s.species,area:s.area,cond:s.cond}); continue;}
 if(t.code!==s.code) mism.push({no:s.no,type:'code',truth:t.code,staged:s.code,species:t.species,area:t.area,cond:t.cond,stSpecies:s.species,stArea:s.area,stCond:s.cond});
 if(t.species && s.species && t.species.toLowerCase()!==s.species.toLowerCase()) mism.push({no:s.no,type:'species',truth:t.species,staged:s.species});
 if(t.area && s.area && t.area.toLowerCase()!==s.area.toLowerCase()) mism.push({no:s.no,type:'area',truth:t.area,staged:s.area});
 if(t.cond && s.cond && t.cond.toLowerCase()!==s.cond.toLowerCase()) mism.push({no:s.no,type:'cond',truth:t.cond,staged:s.cond});
}
console.log('mismatch rows', mism.length);
for(const m of mism.slice(0,80)) console.log(JSON.stringify(m));
