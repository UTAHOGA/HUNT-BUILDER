const fs=require('fs');
const lines=fs.readFileSync('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv','utf8').replace(/\r/g,'').split('\n');
const headers=lines[0].split(',').map(h=>h.replace(/^"|"$/g,''));
let out=0;
for(let i=1;i<lines.length;i++){
  const l=lines[i]; if(!l.trim()) continue;
  const vals=[]; let cur=''; let q=false;
  for(let j=0;j<l.length;j++){
    const ch=l[j],nx=l[j+1];
    if(q){ if(ch==='"'&&nx==='"'){cur+='"';j++;} else if(ch==='"') q=false; else cur+=ch; }
    else { if(ch==='"') q=true; else if(ch===','){vals.push(cur);cur='';} else cur+=ch; }
  }
  vals.push(cur);
  const row={}; headers.forEach((h,idx)=>row[h]=vals[idx]||'');
  const code=row.hunt_code||'';
  if(/^BI653[0-9]{1,2}$/.test(code)||code==='BI6523' || code==='BI6503' || code==='BI6504' || code.startsWith('BI650') || code.startsWith('BI651') || code.startsWith('BI653')){
    if(code.startsWith('BI65')){
      if(code==='BI6528'||code==='BI6529'||code==='BI6530'||code==='BI6531'||code==='BI6537'||code.startsWith('BI653')||code==='BI6523'||code==='BI6503'||code==='BI6504'||code==='BI6505'||code==='BI6506'||code==='BI6509'||code==='BI6516'||code==='BI6539') {
        if((row.hunt_name||'').toLowerCase().includes('book cliffs') || (row.hunt_name||'').toLowerCase().includes('henry') || (row.hunt_name||'').toLowerCase().includes('little') || (row.hunt_name||'').toLowerCase().includes('bitter')){
          out++;
          console.log(code,row.hunt_name,row.organization,row.hunt_type,row.weapon,row.sex_type,row.boundary_id);
        }
      }
    }
  }
}
console.log('count',out);
