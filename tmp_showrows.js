const XLSX=require('xlsx');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
const header=rows[0];
for(let i=61;i<=68;i++){
  const r=rows[i];
  console.log('row',i+1, r.map((c,idx)=>`${header[idx]}=${c}`).join(' | '));
}
