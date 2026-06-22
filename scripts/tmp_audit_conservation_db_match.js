const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const workbookPath = 'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx';
const databasePath = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';

function parseCsvCustom(filePath) {
  const text = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '').replace(/\r/g, '');
  const lines = text.split('\n');
  if (!lines.length) return [];

  const headers = lines[0].split(',').map((h) => h.trim().replace(/^\"|\"$/g, ''));
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    const values = parseCsvLine(line);
    const row = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = values[j] || '';
    }
    rows.push(row);
  }
  return rows;
}

function parseCsvLine(text) {
  const out = [];
  let inQuotes = false;
  let current = '';
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        current += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        current += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      out.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  out.push(current);
  return out;
}

function norm(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/&/g, ' and ')
    .replace(/\bhe'/g, 'he ')
    .replace(/[’']/g, '')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeArea(value) {
  return norm(value)
    .replace(/\b(statewide|permit|bighorn sheep|bear|goat|mountain|mtn|mtns)\b/g, (m) => {
      if (m === 'statewide' || m === 'permit') return m;
      if (m === 'bighorn sheep') return 'bighorn sheep';
      if (m === 'bear') return 'bear';
      if (m === 'goat') return 'goat';
      if (m === 'mountain' || m === 'mtn' || m === 'mtns') return 'mount';
      return m;
    });
}

function parseSpeciesPrefix(rowSpecies) {
  const s = norm(rowSpecies);
  const sex = /antlerless/.test(s)
    ? 'antlerless'
    : /buck/.test(s)
      ? 'buck'
      : /male/.test(s)
        ? 'male'
        : /doe|female/.test(s)
          ? 'female'
          : 'either';
  const species = s
    .replace(/antlerless\s*/g, '')
    .replace(/buck\s*/g, '')
    .replace(/male\s*/g, '')
    .replace(/doe\s*/g, '')
    .replace(/female\s*/g, '')
    .trim();
  return { sex, species };
}

function normWeapons(cell) {
  const v = norm(cell);
  if (!v) return '';
  if (v === 'early' || v === 'mid' || v === 'late') return v;
  return v.replace(/\s+/g, ' ').trim();
}

const dbRows = parseCsvCustom(databasePath)
  .filter((r) => String(r.hunt_code || '').trim());
const dbByCode = new Map();
for (const r of dbRows) {
  dbByCode.set(norm(String(r.hunt_code)), r);
}

const wb = XLSX.readFile(workbookPath);
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, defval: '' });

const headers = rows[0] || [];
const colNo = headers.indexOf('No.');
const colCode = headers.indexOf('HUNT CODE');
const colSpecies = headers.indexOf('Species');
const colArea = headers.indexOf('Area');
const colCondition = headers.indexOf('Condition');

if ([colNo, colCode, colSpecies, colArea, colCondition].some((idx) => idx < 0)) {
  throw new Error('Missing expected headers in staged workbook.');
}

let bad = 0;
const out = [];

for (let i = 1; i < rows.length; i++) {
  const r = rows[i] || [];
  const no = String(r[colNo] || '').trim();
  if (!no || no === 'No.') continue;
  const codesRaw = String(r[colCode] || '');
  const codes = codesRaw
    .split('|')
    .map((c) => norm(c))
    .filter(Boolean);

  const speciesText = String(r[colSpecies] || '').trim();
  const areaText = String(r[colArea] || '').trim();
  const condText = String(r[colCondition] || '').trim();

  const parsedSpecies = parseSpeciesPrefix(speciesText);
  const areaNormalized = normalizeArea(areaText);
  const condNorm = normWeapons(condText);

  let matched = false;
  let reasons = [];

  for (const code of codes) {
    const record = dbByCode.get(code);
    if (!record) {
      reasons.push(`code_missing:${code}`);
      continue;
    }
    const dbSpecies = norm(record.species);
    const dbSex = norm(record.sex_type);
    const dbWeapon = norm(record.weapon);
    const dbName = normalizeArea(record.hunt_name);
    const dbType = norm(record.hunt_type);

    const speciesMatch =
      parsedSpecies.species
        ? parsedSpecies.species === dbSpecies ||
          parsedSpecies.species.includes(dbSpecies) ||
          dbSpecies.includes(parsedSpecies.species)
        : true;

    const sexMatch =
      parsedSpecies.sex === 'either'
        ? true
        : (dbSex.includes(parsedSpecies.sex) ||
          (parsedSpecies.sex === 'buck' && dbSex.includes('buck')) ||
          (parsedSpecies.sex === 'male' && dbSex.includes('buck')) ||
          (parsedSpecies.sex === 'antlerless' && dbSex.includes('antlerless')) ||
          (parsedSpecies.sex === 'female' && dbSex.includes('doe')));

    let weaponMatch = false;
    if (!condNorm) {
      weaponMatch = true;
    } else if (['early', 'late', 'mid'].includes(condNorm)) {
      weaponMatch = dbType.includes(condNorm) || dbName.includes(condNorm);
    } else if (condNorm === 'any legal weapon' || condNorm === 'any') {
      weaponMatch = /any legal weapon/.test(dbWeapon);
    } else if (condNorm === 'multiseason') {
      weaponMatch = /multiseason/.test(dbType) || /multiseason/.test(dbWeapon);
    } else {
      weaponMatch = dbWeapon.includes(condNorm) || dbType.includes(condNorm);
    }

    const areaMatch =
      areaNormalized && dbName
        ? areaNormalized === dbName ||
          areaNormalized.includes(dbName) ||
          dbName.includes(areaNormalized) ||
          dbName.includes('statewide')
        : true;

    const matchBits = [speciesMatch, sexMatch, weaponMatch, areaMatch];
    if (matchBits.every((m) => m)) {
      matched = true;
      break;
    }

    const score = matchBits.filter(Boolean).length;
    reasons.push(`${code}:S${speciesMatch?1:0}X${sexMatch?1:0}W${weaponMatch?1:0}A${areaMatch?1:0}`);
  }

  if (!matched) {
    bad += 1;
    out.push({
      row: i + 1,
      no,
      code: codesRaw,
      species: speciesText,
      area: areaText,
      condition: condText,
      reason: reasons.join('; '),
    });
  }
}

console.log(`suspicious rows: ${bad} of ${rows.length - 1}`);
for (const item of out.slice(0, 260)) {
  console.log(`${item.row}\t${item.no}\t${item.code}\t${item.species}\t${item.area}\t${item.condition}\t${item.reason}`);
}
