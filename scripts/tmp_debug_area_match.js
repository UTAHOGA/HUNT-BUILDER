const fs=require('fs');
const XLSX=require('xlsx');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
const db=fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n');
const headers=db[0].split(',');
const parseLine=l=>{const out=[];let cur='';let q=false;for(let i=0;i<l.length;i++){const ch=l[i],n=l[i+1];if(q){if(ch==='"'&&n==='"'){cur+='"';i++;} else if(ch==='"')q=false; else cur+=ch;} else {if(ch==='"')q=true; else if(ch===','){out.push(cur);cur='';} else cur+=ch;}}out.push(cur);return out;};
const dbMap={};for(let i=1;i<db.length;i++){if(!db[i].trim()) continue;const vals=parseLine(db[i]);const row={};headers.forEach((h,idx)=>row[h]=vals[idx]||'');dbMap[row.hunt_code]=row;}
const norm=v=>String(v||'').toLowerCase().replace(/\s+/g,' ').replace(/[&']/g,' ').replace(/[^a-z0-9 ]/g,' ').trim();
const h=rows[0];const ni=h.indexOf('No.');const ci=h.indexOf('HUNT CODE');const ai=h.indexOf('Area');
for(let i=0;i<rows.length;i++){
 const no=String(rows[i]?.[ni]||'').trim();
 if(!no||no==='No.'||Number(i)<20) continue;
 const code=String(rows[i][ci]||''); if(!code) continue;
 const area=norm(rows[i][ai]);
 const d=dbMap[code]; if(!d) continue;
 const dName=norm(d.hunt_name);
 const m=area.includes(dName)||dName.includes(area)||dName.includes('statewide');
 if(!m){console.log('r',i+1,no,code,rows[i][ai],'=>',d.hunt_name,'norm',area,'->',dName);}
}
