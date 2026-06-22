const XLSX=require('xlsx');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const s=wb.SheetNames[0];
const rows=XLSX.utils.sheet_to_json(wb.Sheets[s],{header:1,defval:''});
for(let i=28;i<=80 && i<rows.length;i++){
  const r=rows[i];
  if(!r || !r.length) continue;
  if(String(r[0])==='') continue;
  console.log((i+1).toString().padStart(3,'0'), r[0], r[1], r[3], r[4], r[5], r[8]);
}
