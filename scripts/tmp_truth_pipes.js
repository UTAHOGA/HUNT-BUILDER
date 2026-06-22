const XLSX=require('xlsx');
const wb=XLSX.readFile('data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
let hasPipe=0; let rowsWithPipe=[];
for(let i=1;i<rows.length;i++){
  const code=String(rows[i][1]||'');
  if(code.includes('|')) {hasPipe++; rowsWithPipe.push([rows[i][0],code,rows[i][3],rows[i][4],rows[i][7]]);} 
}
console.log('truth rows',rows.length-1,'pipe',hasPipe);
for (const r of rowsWithPipe.slice(0,40)) console.log(r);
