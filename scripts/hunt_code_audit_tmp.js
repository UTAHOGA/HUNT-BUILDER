const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const wbPath = path.join(__dirname, '..', 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const dbPath = path.join(__dirname, '..', 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
const auditPath = path.join(__dirname, '..', 'audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv');

function parseCsv(file) {
  const text = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  const lines = text.split(/\r?\n/);
  if (!lines.length) return [];
  const headers = parseLine(lines[0]);
  const out = [];
  for (let i = 1; i < lines.length; i++) {
    const row = parseLine(lines[i]);
    if (!row.length || row.every((v) => String(v || '').trim() === '')) continue;
    out.push(Object.fromEntries(headers.map((h, idx) => [h, row[idx] ?? ''])));
  }
  return out;
}

function parseLine(line) {
  const out = [];
  let cur = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    const next = line[i + 1];
    if (quoted) {
      if (ch === '"' && next === '"') {
        cur += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ',') {
      out.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function norm(v) {
  return String(v || '').trim().toLowerCase();
}

const wb = XLSX.readFile(wbPath);
const sheet = wb.SheetNames[0];
const rows = XLSX.utils.sheet_to_json(wb.Sheets[sheet], { header: 1, defval: '' });
const header = rows[0];
const noIdx = header.indexOf('No.');
const huntCodeIdx = header.indexOf('HUNT CODE');
const speciesIdx = header.indexOf('Species');
const areaIdx = header.indexOf('Area');

const db = parseCsv(dbPath);
const dbByCode = new Map();
for (const r of db) {
  const code = String(r.hunt_code || '').trim().toUpperCase();
  if (code) dbByCode.set(code, r);
}

const audit = parseCsv(auditPath);
const auditBySource = new Map();
for (const r of audit) {
  const key = String(r.source_no || r.xlsx_row || '').trim();
  if (key) auditBySource.set(key, r);
}

const stats = { rows: 0, missingInDb: 0, presentInDb: 0 };
const suspects = [];

for (let i = 1; i < rows.length; i++) {
  const row = rows[i];
  if (!row || !row.length) continue;
  const no = String(row[noIdx] || '').trim();
  const code = String(row[huntCodeIdx] || '').trim().toUpperCase();
  if (!code) continue;

  const species = norm(row[speciesIdx]);
  const area = norm(row[areaIdx]);

  stats.rows += 1;
  const dbRow = dbByCode.get(code);

  if (!dbRow) {
    stats.missingInDb += 1;
    const ar = auditBySource.get(no);
    suspects.push({
      row: i + 1,
      no,
      reason: 'not_in_db',
      current: code,
      selected: ar ? (ar.selected_hunt_code || '') : '',
      species,
      area,
    });
    continue;
  }

  stats.presentInDb += 1;
  const dbSpecies = norm(dbRow.species);
  const dbArea = norm(dbRow.hunt_name);

  const speciesMismatch = species && dbSpecies && species !== dbSpecies;
  const areaMismatch = area && dbArea && area && !dbArea.includes(area) && !area.includes(dbArea);
  if (speciesMismatch || areaMismatch) {
    suspects.push({
      row: i + 1,
      no,
      reason: 'metadata_mismatch',
      current: code,
      selected: '',
      species,
      dbSpecies,
      area,
      dbArea,
    });
  }
}

console.log(JSON.stringify(stats, null, 2));
console.log('suspects', suspects.length);
for (const s of suspects) {
  console.log([s.row, s.no, s.reason, s.current, s.selected, s.species, s.dbSpecies, s.area, s.dbArea].join('\t'));
}
