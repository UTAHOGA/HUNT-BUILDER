const XLSX=require('xlsx');
const fs=require('fs');
function readCsv(path){
 const text=fs.readFileSync(path,'utf8').replace(/\r/g,'');
 const lines=text.split('\n').filter(l=>l.trim());
 const h=lines[0].split(',').map(s=>s.replace(/^"|"$/g,''));
 const rows=lines.slice(1).map(l=>{let out=[];let cur='';let q=false;for(let i=0;i<l.length;i++){const ch=l[i],nx=l[i+1];if(q){if(ch==='"'&&nx==='"'){cur+='"';i++;}else if(ch==='"'){q=false;}else cur+=ch;} else {if(ch==='"')q=true; else if(ch===','){out.push(cur);cur='';} else cur+=ch;}}out.push(cur);return out;}).map(c=>Object.fromEntries(h.map((x,i)=>[x,c[i]||'']));});
 return rows;}
function parse(path){const text=fs.readFileSync(path,'utf8').replace(/\r/g,'');const lines=text.split('\n').filter(l=>l.trim());const headers=lines[0].split(','); const out={}; for(let i=1;i<lines.length;i++){const vals=[];let cur='';let q=false;for(let j=0;j<lines[i].length;j++){const ch=lines[i][j],nx=lines[i][j+1];if(q){if(ch==='"'&&nx==='"'){cur+='"';j++;} else if(ch==='"') q=false; else cur+=ch;} else if(ch==='"') q=true; else if(ch===','){vals.push(cur);cur='';} else cur+=ch;}vals.push(cur); const row={};headers.forEach((h,idx)=>row[h]=vals[idx]||''); out[row.hunt_code]=row;}
 return out;}

const db=readCsv('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
const byCode={}; for(const r of db){ byCode[r.hunt_code]=r; }
const audit=readCsv('audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv');
const possible=audit.filter(r=>r.join_type==='possible_candidates');

function clean(v){return String(v||'').trim();}
let narrowed=[];
for(const row of possible){
  const candidates=clean(row.possible_hunt_codes||'').split('|').map(clean).filter(Boolean);
  const org=clean(row.workbook_organization||'');
  const area=clean(row.workbook_hunt_name||'');
  const hits=[];
  for(const c of candidates){
    const dr=byCode[c.toUpperCase()];
    if(!dr) continue;
    const orgMatch=!org || clean(dr.organization)===org;
    if(orgMatch) hits.push(c);
  }
  if(hits.length===1){
    narrowed.push({no:row.source_no, rowNo:row.xlsx_row, current:row.hunt_code_written, selected:row.selected_hunt_code, possible:row.possible_hunt_codes, org, area, pick:hits[0]});
  }
}
console.log('candidate narrowed by org',narrowed.length);
for(const n of narrowed){console.log(n.rowNo,n.no,n.current,'->',n.pick,'org',n.org,'area',n.area);}
