const fs = require(''fs'');
function parseCsv(path){
  const text=fs.readFileSync(path,''utf8'').replace(/^\uFEFF/, '''').replace(/\r/g,'''');
  const lines=text.split(''\n'');
  if(!lines.length) return [];
  const hdr=parseLine(lines[0]);
  const out=[];
  for(let i=1;i<lines.length;i++){
    const line=lines[i];
    if(!line.trim()) continue;
    const vals=parseLine(line);
    const row=Object.fromEntries(hdr.map((h,idx)=>[h, vals[idx] ?? '''']));
    out.push(row);
  }
  return out;
}
function parseLine(line){
  const vals=[];
  let cur='''';
  let q=false;
  for(let i=0;i<line.length;i++){
    const ch=line[i];
    const n=line[i+1];
    if(q){
      if(ch==='"' && n==='"'){cur+='"'; i++;}
      else if(ch==='"') q=false;
      else cur+=ch;
    } else {
      if(ch==='"') q=true;
      else if(ch==='',''){}
      else if(ch==='',''){ vals.push(cur); cur=''''; }
      else cur += ch;
    }
  }
  vals.push(cur);
  return vals;
}
