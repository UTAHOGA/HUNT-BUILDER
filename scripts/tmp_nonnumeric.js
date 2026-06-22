const XLSX=require('xlsx');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
for(let i=1;i<rows.length;i++){
  const no=String(rows[i][0]||'');
  if(no && no!=='No.' && !/^\d+$/.test(no)){
    console.log(i+1,no, rows[i][1]);
  }
}
