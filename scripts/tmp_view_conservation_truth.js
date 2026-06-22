const XLSX=require('xlsx');
const wb = XLSX.readFile('data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx');
const s = wb.SheetNames[0];
const rows = XLSX.utils.sheet_to_json(wb.Sheets[s], {defval:''});
console.log('rows', rows.length);
if (rows.length) console.log('cols', Object.keys(rows[0]).join(', '));
console.log(rows.slice(0,8));
