const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const repoRoot = process.cwd();
const truthPath = path.join('C:\\Users\\tyler\\Desktop\\conservation codes.xlsx');
const workbookPath = path.join(
  repoRoot,
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx'
);
const auditPath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_bible_truth_backfill_audit.csv'
);

const norm = (value) => String(value || '')
  .replace(/\s+/g, ' ')
  .trim();

function readTruth(filePath) {
  const wb = XLSX.readFile(filePath);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
  const out = new Map();

  for (let i = 1; i < rows.length; i += 1) {
    const row = rows[i] || [];
    const huntName = norm(row[0]);
    const huntCode = norm(row[1]).toUpperCase();
    if (!huntCode) continue;

    out.set(huntCode, {
      huntName,
      species: norm(row[3]),
      sex: norm(row[2]),
      weapon: norm(row[4]),
      huntType: norm(row[5]),
      season: norm(row[6]),
      sourceRow: i + 1,
    });
  }
  return out;
}

function ensureColumn(cols, name, insertAfter = null) {
  if (cols.includes(name)) return cols.indexOf(name);
  const idx = insertAfter == null ? cols.length : cols.indexOf(insertAfter) + 1;
  const at = idx < 0 ? cols.length : idx;
  cols.splice(at, 0, name);
  return at;
}

const truthByCode = readTruth(truthPath);
const wb = XLSX.readFile(workbookPath);
const sheetName = wb.SheetNames[0];
const ws = wb.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

if (!rows.length) throw new Error('Target workbook has no rows.');
const header = rows[0];
const codeCol = header.indexOf('HUNT CODE');
const speciesCol = header.indexOf('Species');
const areaCol = header.indexOf('Area');
const conditionCol = header.indexOf('Condition');
const noCol = header.indexOf('No.');

if (codeCol < 0 || speciesCol < 0) {
  throw new Error('Target workbook is missing required columns.');
}

const huntNameCol = ensureColumn(header, 'HUNT NAME', header[areaCol < 0 ? speciesCol : areaCol]);
const weaponCol = ensureColumn(header, 'WEAPON', header[conditionCol < 0 ? speciesCol : conditionCol]);
const sexCol = ensureColumn(header, 'SEX', header[speciesCol]);

const audit = [
  ['row', 'source_no', 'hunt_code', 'field', 'old_value', 'new_value', 'truth_source_row']
];

let changed = 0;
let missingTruth = 0;
let skippedPipe = 0;
let updatedRows = 0;

for (let i = 1; i < rows.length; i += 1) {
  const row = rows[i];
  const rawCode = norm(row[codeCol]);
  const codes = rawCode.split('|').map((c) => c.trim()).filter(Boolean);

  if (codes.length !== 1) {
    skippedPipe += 1;
    continue;
  }

  const huntCode = codes[0].toUpperCase();
  const truth = truthByCode.get(huntCode);
  if (!truth) {
    missingTruth += 1;
    continue;
  }

  const setVal = (colName, colIndex, newValue, sourceField) => {
    const oldValue = norm(row[colIndex]);
    if (oldValue !== norm(newValue)) {
      audit.push([
        String(i + 1),
        String(row[noCol] || ''),
        huntCode,
        colName,
        oldValue,
        newValue,
        String(truth.sourceRow),
      ]);
      row[colIndex] = newValue;
      return true;
    }
    return false;
  };

  const rowChanged =
    setVal('HUNT NAME', huntNameCol, truth.huntName, 'huntName') ||
    setVal('Species', speciesCol, truth.species, 'species') ||
    setVal('WEAPON', weaponCol, truth.weapon, 'weapon') ||
    setVal('SEX', sexCol, truth.sex, 'sex');
  // Keep condition aligned to weapon if it is populated in truth and currently empty/different.
  if (truth.weapon) {
    if (setVal('Condition', conditionCol, truth.weapon, 'weaponFromTruth')) {
      // handled by audit
    }
  }

  if (rowChanged) {
    changed += 1;
  }
  if (rawCode && truth) updatedRows += 1;
}

wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
XLSX.writeFile(wb, workbookPath);

const csv = audit
  .map((row) => row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
  .join('\n') + '\n';
fs.writeFileSync(auditPath, csv, 'utf8');

console.log(`updated_rows=${updatedRows}`);
console.log(`field_changes=${changed}`);
console.log(`skipped_pipe_rows=${skippedPipe}`);
console.log(`missing_truth=${missingTruth}`);
console.log(`audit=${path.relative(repoRoot, auditPath)}`);
