const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const workbookPath = path.join(__dirname, '..', 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const databasePath = path.join(__dirname, '..', 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');

function parseCsvLines(filePath) {
  return fs
    .readFileSync(filePath, 'utf8')
    .replace(/\r/g, '')
    .split('\n')
    .filter((line) => line.trim().length > 0);
}

function loadValidHuntCodes() {
  const lines = parseCsvLines(databasePath);
  const valid = new Set();

  for (let i = 1; i < lines.length; i += 1) {
    const row = lines[i];
    const code = (row.split(',')[0] || '').replace(/"/g, '').trim();
    if (code) {
      valid.add(code);
    }
  }

  return valid;
}

function canonicalizeCodeCell(rawCode, validCodes) {
  const codes = String(rawCode || '')
    .split('|')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

  if (!codes.length) {
    return { code: '', removed: [], unchanged: true };
  }

  const valid = codes.filter((code) => validCodes.has(code));
  const removed = codes.filter((code) => !validCodes.has(code));

  return {
    code: valid.join('|'),
    removed,
    unchanged: removed.length === 0,
  };
}

function cleanWorkbook() {
  const wb = XLSX.readFile(workbookPath);
  const sheetName = wb.SheetNames[0];
  const rows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1, defval: '' });

  const headers = rows[0];
  const noCol = headers.indexOf('No.');
  const huntCodeCol = headers.indexOf('HUNT CODE');

  if (noCol < 0 || huntCodeCol < 0) {
    throw new Error('Expected columns No. and HUNT CODE were not found in staged workbook.');
  }

  const validHuntCodes = loadValidHuntCodes();
  const cleanedRows = [];
  const audit = {
    totalRowsInput: rows.length - 1,
    droppedHeaderRows: 0,
    filteredCodes: 0,
    removedCodeEntries: [],
  };

  cleanedRows.push(headers);

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex] || [];
    const noValue = String(row[noCol] || '').trim();

    if (!noValue || noValue === 'No.') {
      if (noValue === 'No.') {
        audit.droppedHeaderRows += 1;
      }
      continue;
    }

    const beforeCode = String(row[huntCodeCol] || '').trim();
    const patch = canonicalizeCodeCell(beforeCode, validHuntCodes);

    if (!patch.unchanged) {
      row[huntCodeCol] = patch.code;
      audit.filteredCodes += 1;
      if (patch.removed.length) {
        audit.removedCodeEntries.push({
          row: String(rowIndex + 1),
          sourceNo: noValue,
          beforeCode,
          removed: patch.removed.join('|'),
          afterCode: patch.code,
        });
      }
    }

    cleanedRows.push(row);
  }

  wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(cleanedRows);
  XLSX.writeFile(wb, workbookPath);

  console.log(`cleaned_rows=${cleanedRows.length - 1}`);
  console.log(`dropped_header_rows=${audit.droppedHeaderRows}`);
  console.log(`filtered_code_rows=${audit.filteredCodes}`);
  for (const item of audit.removedCodeEntries) {
    console.log([item.row, item.sourceNo, item.beforeCode, item.removed, item.afterCode].join('|'));
  }
}

cleanWorkbook();
