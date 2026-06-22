const fs=require('fs');
const XLSX=require('xlsx');
const joinFile='data_truth/harvest_results_truth/raw_packages/unknown_for_unknown_full_joined_harvest_backcheck_conservation_annual_per_row_corrected/full_joined_hunt_code_backcheck_2021_2026_conservation_annual_per_row.csv';
const staged='processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx';
function parse(path){
 const txt=fs.readFileSync(path,'utf8').replace(/^\uFEFF/,'').replace(/\r/g,'');
 const lines=txt.split('\n').filter(l=>l.trim());
 const h=lines[0].split(',').map(x=>x.replace(/^"|"$/g,''));
 const parseLine=(line)=>{const out=[];let c='';let q=false;for(let i=0;i<line.length;i++){const ch=line[i],n=line[i+1];if(q){if(ch==='"'&&n==='"'){c+='"';i++;} else if(ch==='"') q=false; else c+=ch;} else {if(ch==='"') q=true; else if(ch===','){out.push(c);c='';} else c+=ch;}}out.push(c);return out;};
 return lines.slice(1).map((line)=>{const vals=parseLine(line);const r={};h.forEach((col,idx)=>r[col]=vals[idx]||'');return r;});
}
const joinRows=parse(joinFile);
const map=new Map();for(const r of joinRows){if((r.source_year||'')==='2026' || (r.model_target_year||'')==='2026'){const no=String(r.source_no||'').trim();if(no) map.set(no,{code:String(r.selected_hunt_code||'').trim(),species:r.species,hunt_name:r.hunt_name,area:r.area,method:r.match_method,conf:r.match_confidence});}}
const wb=XLSX.readFile(staged);const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});const h=rows[0];const ni=h.indexOf('No.');const ci=h.indexOf('HUNT CODE');
let mismatch=0;const list=[];for(let i=1;i<rows.length;i++){const no=String(rows[i][ni]||'').trim();if(!no||no==='No.') continue;const sj=map.get(no);if(!sj) continue;const sc=String(rows[i][ci]||'').trim();if(sj.code && sc!==sj.code){mismatch++;list.push({no,staged:sc,joined:sj.code,species:sj.species});}}
console.log('rows',joinRows.length,'mismatch',mismatch);list.slice(0,120).forEach(r=>console.log(`${r.no}\t${r.staged}\t${r.joined}\t${r.species}`));
