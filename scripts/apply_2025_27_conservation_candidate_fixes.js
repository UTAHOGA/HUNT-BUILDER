const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const repoRoot = process.cwd();
const workbookPath = path.join(
  repoRoot,
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx'
);
const dbPath = path.join(
  repoRoot,
  'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'
);
const candidateAuditPath = path.join(repoRoot, 'tmp_conservation_candidates_eval.txt');
const outAuditPath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_candidate_fixes_audit.csv'
);

function readCsvRows(filePath) {
  const text = fs.readFileSync(filePath, 'utf8').replace(/\r/g, '');
  const lines = text.split('\n');
  const parsed = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    const row = [];
    let field = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      const nx = line[i + 1];
      if (inQuotes) {
        if (ch === '"' && nx === '"') {
          field += '"';
          i += 1;
        } else if (ch === '"') {
          inQuotes = false;
        } else {
          field += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ',') {
        row.push(field);
        field = '';
      } else {
        field += ch;
      }
    }
    row.push(field);
    parsed.push(row);
  }
  return parsed;
}

function parseDatabaseCodes(filePath) {
  const rows = readCsvRows(filePath);
  const header = rows.shift() || [];
  const codeIndex = header.indexOf('hunt_code');
  const codes = new Set();
  for (const row of rows) {
    if (row[codeIndex]) {
      codes.add(String(row[codeIndex]).trim().toUpperCase());
    }
  }
  return codes;
}

function parseCandidateAudit(filePath) {
  const text = fs.readFileSync(filePath, 'utf16le').replace(/\r/g, '');
  const lines = text.split('\n').filter(Boolean);
  const updates = new Map();
  for (const line of lines) {
    const parts = line.split('\t');
    if (parts.length < 4) continue;
    const xlsxRow = Number(parts[0]);
    const oldCode = String(parts[2] || '').trim();
    const newCode = String(parts[3] || '').trim().toUpperCase();
    if (!Number.isInteger(xlsxRow) || xlsxRow <= 1) continue;
    if (!oldCode.includes('|')) continue;
    updates.set(xlsxRow, { oldCode, newCode });
  }
  return updates;
}

const dbCodes = parseDatabaseCodes(dbPath);
const updates = parseCandidateAudit(candidateAuditPath);

const wb = XLSX.readFile(workbookPath);
const sheetName = wb.SheetNames[0];
const ws = wb.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
if (!rows.length) throw new Error('Workbook has no rows.');

const header = rows[0];
const huntCodeCol = header.indexOf('HUNT CODE');
if (huntCodeCol < 0) throw new Error('Missing HUNT CODE column');
const noCol = header.indexOf('No.');
if (noCol < 0) throw new Error('Missing No. column');

const audit = [['xlsx_row', 'source_no', 'old_hunt_code', 'new_hunt_code', 'status']];
let updated = 0;
let skippedMissingCode = 0;
let skippedInvalidCode = 0;
let skippedNotFound = 0;

for (const [xlsxRow, payload] of updates.entries()) {
  const rowIndex = xlsxRow - 1;
  if (rowIndex < 1 || rowIndex >= rows.length) {
    skippedNotFound += 1;
    audit.push([String(xlsxRow), '', payload.oldCode, payload.newCode, 'row_out_of_bounds']);
    continue;
  }

  const row = rows[rowIndex];
  const current = String(row[huntCodeCol] || '').trim();
  if (current !== payload.oldCode) {
    skippedNotFound += 1;
    audit.push([String(xlsxRow), String(row[noCol] || ''), current, payload.newCode, 'old_code_mismatch']);
    continue;
  }
  if (!dbCodes.has(payload.newCode)) {
    skippedInvalidCode += 1;
    audit.push([String(xlsxRow), String(row[noCol] || ''), current, payload.newCode, 'new_code_not_in_db']);
    continue;
  }
  if (!current.includes('|')) {
    skippedMissingCode += 1;
    audit.push([String(xlsxRow), String(row[noCol] || ''), current, payload.newCode, 'already_single_code']);
    continue;
  }
  row[huntCodeCol] = payload.newCode;
  updated += 1;
  audit.push([String(xlsxRow), String(row[noCol] || ''), current, payload.newCode, 'updated']);
}

wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
XLSX.writeFile(wb, workbookPath);

const csv = audit
  .map((r) => r.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(','))
  .join('\n') + '\n';
fs.writeFileSync(outAuditPath, csv, 'utf8');

console.log(`updated=${updated}`);
console.log(`skipped_missing_code=${skippedMissingCode}`);
console.log(`skipped_invalid_code=${skippedInvalidCode}`);
console.log(`skipped_not_found=${skippedNotFound}`);
console.log(`audit_path=${path.relative(repoRoot, outAuditPath)}`);
