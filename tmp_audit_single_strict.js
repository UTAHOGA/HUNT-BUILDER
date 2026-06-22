const fs = require('fs');
const XLSX = require('xlsx');

function readCsv(path){
  const text = fs.readFileSync(path,'utf8').replace(/^\uFEFF/,'').replace(/\r/g,'');
  const lines = text.split('\n');
  const headers = parseCsvLine(lines.shift());
  const rows=[];
  for(const line of lines){
    if(!line.trim()) continue;
    rows.push(parseCsvLine(line));
  }
  return {headers, rows};
}
function parseCsvLine(line){
  const out=[]; let cur=''; let q=false;
  for(let i=0;i<line.length;i++){
    const ch=line[i], nx=line[i+1];
    if(q){
      if(ch==='"' && nx==='"'){cur+='"'; i++;}
      else if(ch==='"'){q=false;}
      else cur+=ch;
    } else {
      if(ch==='"') q=true;
      else if(ch===','){out.push(cur); cur='';}
      else cur+=ch;
    }
  }
  out.push(cur);
  return out;
}

function norm(v){return String(v||'').trim().toLowerCase().replace(/\s+/g,' ').replace(/&/g,' and ').replace(/[’']/g,'').replace(/[^a-z0-9\s]/g,' ').trim();}
function normArea(v){return norm(v).replace(/\b(central|south|north|east|west|mtn|mtns|mountain|mountains)\b/g,'').replace(/\s+/g,' ').trim();}
function parseSpecies(v){
  const s=norm(v);
  const sex = /antlerless|doe|female/.test(s)?'antlerless':(/buck|male/.test(s)?'buck':(/cow/.test(s)?'cow':'either'));
  const species=s.replace(/antlerless|buck|male|cow|doe|female/g,'').replace(/\s+/g,' ').trim();
  return {species,sex};
}
function normWeapon(v){
  const s=norm(v);
  if(!s) return '';
  if(s === 'hunter\'s choice' || s==='hunter s choice') return 'hunterschoice';
  if(['any legal weapon','any'].includes(s)) return 'any legal weapon';
  return s;
}

const db = readCsv('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
const dbRows = db.rows.map(cols=>{
  const row={}; db.headers.forEach((h,i)=>row[h]=cols[i]||'');
  row._code = norm(row.hunt_code).toUpperCase();
  row._species = norm(row.species);
  row._sex = norm(row.sex_type);
  row._weapon = norm(row.weapon);
  row._type = norm(row.hunt_type);
  row._name = normArea(row.hunt_name);
  return row;
});
const codeIndex={}; for(const r of dbRows) codeIndex[r._code]=r;
const wb = XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header:1, defval:''});
const h=rows[0];
const idxNo=h.indexOf('No.'); const idxCode=h.indexOf('HUNT CODE'); const idxSpecies=h.indexOf('Species'); const idxArea=h.indexOf('Area'); const idxCond=h.indexOf('Condition');
let suspicious=[];
for(let i=1;i<rows.length;i++){
  const r=rows[i]; const no=String(r[idxNo]||'').trim(); if(!no) continue;
  const code=String(r[idxCode]||'').trim(); if(!code || code.includes('|')) continue;
  const dbRow=codeIndex[norm(code).toUpperCase()];
  if(!dbRow){ suspicious.push({row:i+1,no,code,why:'code_not_in_db'}); continue; }
  const ps=parseSpecies(r[idxSpecies]);
  const area = normArea(r[idxArea]);
  const cond = normWeapon(r[idxCond]);
  const speciesOk = !ps.species || dbRow._species===ps.species || dbRow._species.includes(ps.species) || ps.species.includes(dbRow._species);
  const sexOk = ps.sex==='either' || (ps.sex==='antlerless' && /(antlerless|buckless|both)/.test(dbRow._sex)?false: dbRow._sex.includes(ps.sex) || (ps.sex==='buck' && dbRow._sex.includes('buck')) || (ps.sex==='cow' && dbRow._sex.includes('cow')) || ps.sex==='antlerless' && dbRow._sex.includes('antlerless'));
  const condNorm = cond === 'hunterschoice' ? 'any' : cond;
  let weaponOk=true;
  if(condNorm){
    if(condNorm === 'any legal weapon'){ weaponOk = /any legal weapon/.test(dbRow._weapon); }
    else if(condNorm === 'mid' || condNorm==='late' || condNorm==='early') weaponOk = /mid|late|early/.test(dbRow._type) || /mid|late|early/.test(dbRow._name);
    else if(condNorm==='any'){ weaponOk=true; }
    else { weaponOk = dbRow._weapon.includes(condNorm) || dbRow._type.includes(condNorm); }
  }
  const areaMatch = !area ? true : (dbRow._name.includes(area) || area.includes(dbRow._name) || dbRow._name.includes('statewide'));
  if(!(speciesOk && sexOk && areaMatch && weaponOk)){
    suspicious.push({row:i+1,no,code,why:`species=${speciesOk}|sex=${sexOk}|area=${areaMatch}|weapon=${weaponOk}`});
  }
}
console.log('strict suspicious',suspicious.length);
for(const s of suspicious){ console.log(`${s.row}\t${s.no}\t${s.code}\t${s.why}`); }
