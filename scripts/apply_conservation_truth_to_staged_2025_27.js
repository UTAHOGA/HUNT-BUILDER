const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const repoRoot = process.cwd();
const truthPath = 'C:/Users/tyler/Desktop/conservation codes.xlsx';
const workbookPath = path.join(
  repoRoot,
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx'
);
const auditPath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_staged_truth_backfill_audit.csv'
);

function norm(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim();
}

function readTruth(filePath) {
  const wb = XLSX.readFile(filePath);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
  const map = new Map();

  for (let i = 1; i < rows.length; i += 1) {
    const row = rows[i] || [];
    const code = norm(row[1]).toUpperCase();
    if (!code) continue;
    map.set(code, {
      sourceRow: i + 1,
      huntName: norm(row[0]),
      species: norm(row[3]),
      sex: norm(row[2]),
      weapon: norm(row[4]),
    });
  }
  return map;
}

const truthByCode = readTruth(truthPath);

const workbook = XLSX.readFile(workbookPath);
const sheetName = workbook.SheetNames[0];
const ws = workbook.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

if (!rows.length) throw new Error('Workbook is empty.');
const header = rows[0];

const codeCol = header.indexOf('HUNT CODE');
const speciesCol = header.indexOf('Species');
const condCol = header.indexOf('Condition');
const huntNameCol = header.indexOf('HUNT NAME');
const sexCol = header.indexOf('SEX');
const weaponCol = header.indexOf('WEAPON');

for (const [name, col] of [
  ['HUNT CODE', codeCol],
  ['Species', speciesCol],
  ['Condition', condCol],
  ['HUNT NAME', huntNameCol],
  ['SEX', sexCol],
  ['WEAPON', weaponCol],
]) {
  if (col < 0) throw new Error(`Missing required column: ${name}`);
}

const audit = [['row', 'source_no', 'hunt_code', 'field', 'old_value', 'new_value', 'truth_source_row']];
let updatedRows = 0;
let fieldChanges = 0;
let matchedTruth = 0;
let missingTruth = 0;

for (let i = 1; i < rows.length; i += 1) {
  const row = rows[i];
  const sourceNo = norm(row[0]);
  if (!sourceNo || sourceNo === 'No.') continue;

  const code = norm(row[codeCol]).toUpperCase();
  if (!code) continue;
  const truth = truthByCode.get(code);
  if (!truth) {
    missingTruth += 1;
    continue;
  }

  matchedTruth += 1;
  const updates = [
    ['SPECIES', speciesCol, truth.species],
    ['HUNT NAME', huntNameCol, truth.huntName],
    ['SEX', sexCol, truth.sex],
    ['WEAPON', weaponCol, truth.weapon],
    ['Condition', condCol, truth.weapon],
  ];

  let rowChanged = false;
  for (const [field, col, nextValue] of updates) {
    const oldValue = norm(row[col]);
    const exactOld = norm(row[col]);
    if (oldValue !== nextValue) {
      row[col] = nextValue;
      fieldChanges += 1;
      rowChanged = true;
      audit.push([String(i + 1), sourceNo, code, field, oldValue, nextValue, String(truth.sourceRow)]);
    }
  }
  if (rowChanged) updatedRows += 1;
}

workbook.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
XLSX.writeFile(workbook, workbookPath);

const csv = audit
  .map((line) => line.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(','))
  .join('\n') + '\n';
fs.writeFileSync(auditPath, csv, 'utf8');

console.log(`updated_rows=${updatedRows}`);
console.log(`field_changes=${fieldChanges}`);
console.log(`matched_truth=${matchedTruth}`);
console.log(`missing_truth=${missingTruth}`);
console.log(`audit=${path.relative(repoRoot, auditPath)}`);
