const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const repoRoot = process.cwd();
const workbookPath = path.join(
  repoRoot,
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx'
);
const auditSourcePath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv'
);
const outAuditPath = path.join(
  repoRoot,
  'audits/2025_canonical_finalization/2025_27_conservation_staged_hunt_code_fill_audit.csv'
);

function parseCsv(filePath) {
  const text = fs.readFileSync(filePath, 'utf8').replace(/\r/g, '');
  const lines = text.split('\n').filter(Boolean);
  const out = [];

  for (const line of lines) {
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
    out.push(row);
  }
  return out;
}

function norm(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim();
}

function isHeaderRow(row, expected) {
  if (!row || row.length < 2) return false;
  return norm(row[0]) === expected[0] && norm(row[1]) === expected[1];
}

const mapping = new Map();
const joinRows = parseCsv(auditSourcePath);
const header = joinRows[0] || [];
const col = Object.fromEntries(header.map((name, idx) => [name, idx]));

for (let i = 1; i < joinRows.length; i += 1) {
  const row = joinRows[i];
  const rowNum = Number(row[col.xlsx_row]);
  if (!Number.isInteger(rowNum) || rowNum <= 1) continue;
  const confidence = norm(row[col.match_confidence]);
  const written = norm(row[col.hunt_code_written]);
  const possible = norm(row[col.possible_hunt_codes]);
  const species = norm(row[col.species]);
  const sex = norm(row[col.sex_type]);
  const huntName = norm(row[col['hunt name']]);
  const weapon = norm(row[col.weapon]);
  const reviewFlags = norm(row[col.review_flags]);

  const singleFromWritten = written && !written.includes('|');
  const singleFromPossible = possible && !possible.includes('|');
  const chosen = singleFromWritten ? written : singleFromPossible ? possible : '';

  if (!chosen || confidence !== 'HIGH') continue;
  if (reviewFlags) continue;

  mapping.set(rowNum, {
    huntCode: chosen.toUpperCase(),
    species,
    sex,
    huntName,
    weapon,
  });
}

const wb = XLSX.readFile(workbookPath);
const sheetName = wb.SheetNames[0];
const ws = wb.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

if (!rows.length) throw new Error('Workbook is empty.');

const baseHeader = rows[0];
const noCol = baseHeader.indexOf('No.');
const speciesCol = baseHeader.indexOf('Species');
const areaCol = baseHeader.indexOf('Area');
const conditionCol = baseHeader.indexOf('Condition');

const ensureColumn = (label) => {
  const idx = baseHeader.indexOf(label);
  if (idx >= 0) return idx;
  baseHeader.push(label);
  return baseHeader.length - 1;
};

const codeCol = ensureColumn('HUNT CODE');
const huntNameCol = ensureColumn('HUNT NAME');
const sexCol = ensureColumn('SEX');
const weaponCol = ensureColumn('WEAPON');

const cleaned = [baseHeader];
const audit = [['row', 'source_no', 'hunt_code', 'status', 'source']];
let rowCount = 0;
let mapped = 0;
let droppedHeader = 0;
let mappedButNoCode = 0;

for (let i = 1; i < rows.length; i += 1) {
  const row = rows[i] || [];
  if (row.length === 0) continue;
  const noValue = norm(row[noCol]);

  if (!noValue || isHeaderRow(row, ['No.', 'Species'])) {
    if (isHeaderRow(row, ['No.', 'Species'])) droppedHeader += 1;
    continue;
  }

  rowCount += 1;
  const mappedRow = mapping.get(i + 1);
  if (!mappedRow) {
    cleaned.push(row);
    continue;
  }

  if (mappedRow.huntCode) {
    row[codeCol] = mappedRow.huntCode;
  } else {
    mappedButNoCode += 1;
  }

  // Fill blanks only so we do not overwrite verified source text in existing rows.
  if (!norm(row[speciesCol])) row[speciesCol] = mappedRow.species;
  if (!norm(row[huntNameCol])) row[huntNameCol] = mappedRow.huntName;
  if (!norm(row[sexCol])) row[sexCol] = mappedRow.sex;
  if (!norm(row[weaponCol])) row[weaponCol] = mappedRow.weapon;
  if (!norm(row[conditionCol]) && mappedRow.weapon) row[conditionCol] = mappedRow.weapon;

  mapped += 1;
  audit.push([String(i + 1), noValue, mappedRow.huntCode, 'mapped', 'high_confidence_single_code']);
  cleaned.push(row);
}

wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(cleaned);
XLSX.writeFile(wb, workbookPath);

const csv = audit.map((r) => r.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(',')).join('\n') + '\n';
fs.writeFileSync(outAuditPath, csv, 'utf8');

console.log(`source_rows=${rows.length - 1}`);
console.log(`kept_rows=${rowCount}`);
console.log(`dropped_header_rows=${droppedHeader}`);
console.log(`mapped_rows=${mapped}`);
console.log(`mapped_rows_without_code=${mappedButNoCode}`);
console.log(`audit=${path.relative(repoRoot, outAuditPath)}`);
