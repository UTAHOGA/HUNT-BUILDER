const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const repoRoot = process.cwd();
const truthPath = 'C:/Users/tyler/Desktop/conservation codes.xlsx';
const workbookPath = path.join(
  repoRoot,
  'data_truth/conservation_permit_truth/2025-27 Conservation Permits.xlsx'
);
const auditPath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_truth_2025_27_bible_audit.csv'
);

function norm(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim();
}

function readTruthTruth(pathToFile) {
  const workbook = XLSX.readFile(pathToFile);
  const ws = workbook.Sheets[workbook.SheetNames[0]];
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

const truthByCode = readTruthTruth(truthPath);

const workbook = XLSX.readFile(workbookPath);
const sheetName = workbook.SheetNames[0];
const sheet = workbook.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
if (!rows.length) throw new Error('Workbook is empty.');

const header = rows[0];
const required = ['HUNT CODE', 'HUNT NAME', 'SPECIES', 'SEX', 'WEAPON'];
const indexes = Object.fromEntries(required.map((name) => [name, header.indexOf(name)]));
for (const [name, idx] of Object.entries(indexes)) {
  if (idx < 0) throw new Error(`Missing required column: ${name}`);
}

const audit = [
  ['row', 'source_no', 'hunt_code', 'field', 'old_value', 'new_value', 'truth_source_row']
];

let updatedRows = 0;
let fieldChanges = 0;
let matchedTruth = 0;
let missingTruth = 0;

for (let i = 1; i < rows.length; i += 1) {
  const row = rows[i];
  const sourceNo = norm(row[header.indexOf('No.')]);
  const code = norm(row[indexes['HUNT CODE']]).toUpperCase();
  if (!code) continue;

  const truth = truthByCode.get(code);
  if (!truth) {
    missingTruth += 1;
    continue;
  }

  matchedTruth += 1;
  let rowChanged = false;

  const updates = [
    ['HUNT NAME', indexes['HUNT NAME'], truth.huntName],
    ['SPECIES', indexes['SPECIES'], truth.species],
    ['SEX', indexes['SEX'], truth.sex],
    ['WEAPON', indexes['WEAPON'], truth.weapon],
  ];

  for (const [field, col, nextValue] of updates) {
    const oldValue = norm(row[col]);
    const exactOld = row[col];
    if (oldValue !== nextValue || exactOld !== nextValue) {
      audit.push([String(i + 1), sourceNo, code, field, oldValue, nextValue, String(truth.sourceRow)]);
      row[col] = nextValue;
      fieldChanges += 1;
      rowChanged = true;
    }
  }

  if (rowChanged) {
    updatedRows += 1;
  }
}

workbook.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
XLSX.writeFile(workbook, workbookPath);

const csv = audit
  .map((line) => line.map((item) => `"${String(item).replace(/"/g, '""')}"`).join(','))
  .join('\n') + '\n';
fs.writeFileSync(auditPath, csv, 'utf8');

console.log(`updated_rows=${updatedRows}`);
console.log(`field_changes=${fieldChanges}`);
console.log(`matched_truth=${matchedTruth}`);
console.log(`missing_truth=${missingTruth}`);
console.log(`audit=${path.relative(repoRoot, auditPath)}`);
