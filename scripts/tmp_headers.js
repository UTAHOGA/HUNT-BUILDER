const XLSX=require('xlsx');
const wb=XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const s=wb.SheetNames[0];
const rows=XLSX.utils.sheet_to_json(wb.Sheets[s],{header:1,defval:''});
console.log(rows[0]);
