const XLSX = require('xlsx');
const path = require('path');
const ws = [
  path.join(__dirname, '..', 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'Conservation Permits', '2025-27 Conservation Permits.xlsx'),
  path.join(__dirname, '..', 'processed_data', 'hard_data_exports', 'hunt_tables', '2026', 'CLEAN_XLXS_STAGED', '2025-27 Conservation Permits.xlsx')
];
for (const f of ws) {
  const wb = XLSX.readFile(f);
  const s = wb.SheetNames[0];
  const rows = XLSX.utils.sheet_to_json(wb.Sheets[s], {header:1, defval:''});
  const header = rows[0];
  console.log('\nFILE', path.basename(f));
  console.log('rows', rows.length);
  console.log('header', header.join(' | '));
  for (let i = 1; i <= Math.min(8, rows.length-1); i++) {
    const row = rows[i];
    console.log(i, row.slice(0, 8).join(' | '));
  }
}
