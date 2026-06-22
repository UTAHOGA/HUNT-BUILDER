const fs=require('fs');
const db = Object.fromEntries(fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n').slice(1).filter(Boolean).map(l=>{let vals=[];let cur='';let q=false;for(let i=0;i<l.length;i++){const ch=l[i],nx=l[i+1];if(q){if(ch==='"'&&nx==='"'){cur+='"';i++;}else if(ch==='"'){q=false;}else cur+=ch;}else{if(ch==='"')q=true;else if(ch===','){vals.push(cur);cur='';}else cur+=ch;}}vals.push(cur);return [vals[0].toUpperCase(),true];}));
const rows=fs.readFileSync('audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv','utf8').replace(/\r/g,'').split('\n').filter(Boolean).slice(1);
const bad=[];
for(const line of rows){const vals=[];let cur='';let q=false;for(let i=0;i<line.length;i++){const ch=line[i],nx=line[i+1];if(q){if(ch==='"'&&nx==='"'){cur+='"';i++;}else if(ch==='"'){q=false;}else cur+=ch;}else{if(ch==='"')q=true;else if(ch===','){vals.push(cur);cur='';}else cur+=ch;}}vals.push(cur);const selected=(vals[4]||'').trim();const possible=(vals[5]||'').trim();const status=vals[3];const no=vals[1];
const codes=(selected||possible||'').split('|').map(c=>c.trim()).filter(Boolean);
for(const c of codes){if(!db[c.toUpperCase()]) bad.push({no,code:c,status});}
}
console.log('bad codes',bad.length);
bad.slice(0,200).forEach(b=>console.log(`${b.no}\t${b.code}\t${b.status}`));
