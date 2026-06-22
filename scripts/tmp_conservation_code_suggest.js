const fs = require('fs');
const XLSX = require('xlsx');

const staged = 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx';
const databasePath = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';

function parseCsv(path){
 const lines = fs.readFileSync(path,'utf8').replace(/\r/g,'').split('\n').filter(l=>l.length);
 const headers = lines[0].split(',').map(s=>s.replace(/^"|"$/g,'').trim());
 const out=[];
 for(let i=1;i<lines.length;i++){
   const line=lines[i]; if(!line.trim()) continue;
   const vals=[]; let cur=''; let q=false;
   for(let j=0;j<line.length;j++){
     const ch=line[j], nx=line[j+1];
     if(q){ if(ch==='"'&&nx==='"'){cur+='"';j++;} else if(ch==='"') q=false; else cur+=ch; }
     else { if(ch==='"') q=true; else if(ch===','){vals.push(cur);cur='';} else cur+=ch; }
   }
   vals.push(cur);
   const row={}; headers.forEach((h,idx)=>row[h]=vals[idx]||'');
   out.push(row);
 }
 return {headers,out};
}
function norm(v){return String(v||'').trim().toLowerCase().replace(/\s+/g,' ').replace(/&/g,' and ').replace(/[’']/g,'').replace(/[^a-z0-9 ]/g,' ');}
function clean(v){return String(v||'').trim();}
function normArea(v){return norm(v).replace(/\b(mtn|mts|mtns|mountains|mountain|s)\b/g,'').replace(/\s+/g,' ').trim();}
function parseSpeciesRow(v){
 const s=norm(v);
 let sex='either';
 if(/antlerless|buck|male|any female|female|doe|do/ .test(s)) {}
 if(/antlerless/.test(s)) sex='antlerless';
 else if(/buck|male/.test(s)) sex='buck';
 else if(/doe|female/.test(s)) sex='doe';
 const sp=s.replace(/antlerless/g,'').replace(/buck/g,'').replace(/male/g,'').replace(/doe/g,'').replace(/female/g,'').replace(/\s+/g,' ').trim();
 return {sex, species: sp};
}

const dbRows = parseCsv(databasePath).out.filter(r=>clean(r.hunt_code));
const dbByCode = new Map();
for(const r of dbRows) dbByCode.set(norm(r.hunt_code).toUpperCase(), r);

const wb = XLSX.readFile(staged);
const sh = wb.Sheets[wb.SheetNames[0]];
const rows = XLSX.utils.sheet_to_json(sh,{header:1,defval:''});
const h=rows[0];
const ix={
 no:h.indexOf('No.'),
 code:h.indexOf('HUNT CODE'),
 species:h.indexOf('Species'),
 area:h.indexOf('Area'),
 cond:h.indexOf('Condition'),
};

let changed=0;
const audit=[];
for(let i=1;i<rows.length;i++){
 const r=rows[i];
 const no=clean(r[ix.no]); if(!no||no==='No.') continue;
 const speciesText=clean(r[ix.species]); const areaText=clean(r[ix.area]); const condText=clean(r[ix.cond]);
 const current = (r[ix.code]||'').split('|').map(s=>clean(s)).filter(Boolean);
 const parsed = parseSpeciesRow(speciesText);
 const cond=norm(condText);
 const areaN = normArea(areaText);
 const candidates=[];
 for(const dr of dbRows){
   const dbSpecies = norm(dr.species);
   const dbSex = norm(dr.sex_type);
   const dbWeapon = norm(dr.weapon);
   const dbType = norm(dr.hunt_type);
   const dbName = normArea(dr.hunt_name);

   const spMatch = parsed.species && (dbSpecies===parsed.species || parsed.species.includes(dbSpecies) || dbSpecies.includes(parsed.species));
   const sexMatch = parsed.sex==='either' ||
      (parsed.sex==='antlerless' && dbSex.includes('antlerless')) ||
      (parsed.sex==='buck' && (dbSex.includes('buck')||dbSex.includes('male')) ) ||
      (parsed.sex==='doe' && (dbSex.includes('doe')||dbSex.includes('female')));
   let condMatch=true;
   if(cond){
      if(cond==='any legal weapon' || cond==='any') condMatch=/any legal weapon/.test(dbWeapon);
      else if(cond==='hunter\'s choice') condMatch=true;
      else if(cond==='archery') condMatch=/archery/.test(dbWeapon);
      else if(cond==='muzzleloader') condMatch=/muzzleloader/.test(dbWeapon);
      else if(cond==='multiseason') condMatch= /multiseason/.test(dbType);
      else if(['early','mid','late'].includes(cond)) condMatch = (dbType.includes(cond) || dbName.includes(cond));
      else condMatch = dbWeapon.includes(cond) || dbType.includes(cond);
   }
   const areaMatch = !areaN || !dbName ? true : (dbName.includes(areaN) || areaN.includes(dbName) || dbName==='statewide' || /statewide/.test(dbName));

   let score = 0;
   if(spMatch) score++;
   if(sexMatch) score++;
   if(condMatch) score++;
   if(areaMatch) score++;

   if(spMatch && sexMatch && areaMatch && (condMatch || cond=='')) {
      candidates.push({code:dr.hunt_code, score});
   }
 }
 const sorted = candidates.sort((a,b)=>b.score-a.score);
 const best = sorted[0];
 if(current.length===1 && best && current[0].toUpperCase()===clean(best.code).toUpperCase()) continue;
 if(current.length<=1 && best && sorted.length===1){
    audit.push({row:i+1,no,current:current.join('|'),suggested:best.code,reason:`single_match_${cond||'nomatchcond'}`});
    changed++;
 }
}
console.log('single_match_updates',changed);
for(const a of audit.slice(0,200)) console.log(`${a.row}\t${a.no}\t${a.current}\t${a.suggested}\t${a.reason}`);
