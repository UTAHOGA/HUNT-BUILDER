const fs = require(''fs'');
const path = require(''path'');
const XLSX = require(''xlsx'');

const repoRoot = process.cwd();
const workbookPath = path.join(repoRoot, ''processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx'');
const databasePath = path.join(repoRoot, ''pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv'');
const auditPath = path.join(repoRoot, ''audits/2025_canonical_finalization/2025_27_conservation_fix_audit.csv'');

function parseCsv(filePath) {
  const text = fs.readFileSync(filePath, ''utf8'').replace(/^\uFEFF/, '''');
  const rows = [];
  let row = [];
  let field = '''';
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const nx = text[i + 1];
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
      field = '''';
    } else if (ch === ''\n'') {
      row.push(field);
      if (row.some((cell) => String(cell || '''').trim() !== '''')) {
        rows.push(row);
      }
      row = [];
      field = '''';
    } else if (ch !== ''\r'') {
      field += ch;
    }
  }

  if (field.length || row.length) {
    row.push(field);
    if (row.some((cell) => String(cell || '''').trim() !== '''')) {
      rows.push(row);
    }
  }

  if (!rows.length) return { headers: [], rows: [] };
  const headers = rows.shift().map((h) => String(h || '''').replace(/^\uFEFF/, '''').trim());
  return {
    headers,
    rows: rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] || ''''])),
  };
}

const dbPayload = parseCsv(databasePath);
const dbRows = dbPayload.rows || [];
const dbByCode = new Map();
for (const row of dbRows) {
  const code = String(row.hunt_code || '''').trim().toUpperCase();
  if (code) dbByCode.set(code, row);
}

function norm(value) {
  return String(value || '''')
    .toLowerCase()
    .replace(/&/g, '' and '')
    .replace(/\bmtns\b/g, ''mountains'')
    .replace(/\bmtn\b/g, ''mountain'')
    .replace(/[^a-z0-9 ]/g, '' '')
    .replace(/\s+/g, '' '')
    .trim();
}

function speciesMatches(rowSpecies, dbRow) {
  const p = norm(rowSpecies);
  const d = norm(dbRow.species || '''');
  const sex = norm(dbRow.sex_type || '''');

  if (!p || !d) return false;
  if (p === ''black bear'') return d.includes(''black bear'') || d === ''bear'';
  if (p.includes(''antlerless elk'')) return d.includes(''elk'') && sex.includes(''antlerless'');
  if (p === ''elk'') return d.includes(''elk'');
  if (p === ''bison'') return d === ''bison'';
  if (p === ''deer'') return d === ''deer'';
  if (p === ''moose'') return d === ''moose'';
  if (p === ''mountain goat'') return d === ''mountain goat'';
  if (p.includes(''pronghorn'')) return d === ''pronghorn'';
  if (p === ''turkey'') return d === ''turkey'';
  if (p === ''rocky mountain bighorn sheep'') return d.includes(''rocky mountain bighorn sheep'');
  if (p === ''desert bighorn sheep'') return d.includes(''desert bighorn sheep'');
  return p === d;
}

function conditionMatches(rowCondition, dbRow) {
  const c = norm(rowCondition);
  const w = norm(dbRow.weapon || '''');

  if (!c || !w) return true;

  if (c === ''any legal weapon'' || c === ''any'') {
    return w.includes(''any legal weapon'') || w.includes(''any'') || w.includes(''choice'') || w.includes(''multiseason'');
  }

  if (c.includes(''hunter'') || c.includes(''choice'')) {
    return w.includes(''hunter'') || w.includes(''choice'') || w.includes(''any legal weapon'') || w.includes(''multiseason'');
  }

  if (c.includes(''multiseason'')) return w.includes(''multiseason'');
  if (c.includes(''archery'')) return w.includes(''archery'');
  if (c.includes(''muzzleloader'')) return w.includes(''muzzleloader'');

  if (c.includes(''late'') || c.includes(''early'') || c.includes(''mid'')) return true;
  if (c.includes(''ram'')) return true;

  return w.includes(c);
}

function areaMatches(area, dbName) {
  const a = norm(area);
  const b = norm(dbName);
  if (!a || !b) return false;

  const normalizedArea = a.replace(/\bconservation\b/g, '''').trim();
  const normalizedDb = b.replace(/\bconservation\b/g, '').trim();

  if (normalizedArea === 'statewide' && normalizedDb.includes('statewide')) return true;
  if (normalizedArea.includes('statewide') || normalizedDb.includes('statewide')) return false;

  const tokensArea = normalizedArea.split(' ').filter(Boolean);
  const tokensDb = new Set(normalizedDb.split(' ').filter(Boolean));

  return tokensArea.some((token) => tokensDb.has(token) || tokensDb.has(token.replace(/s$/, '''')));
}

const wb = XLSX.readFile(workbookPath);
const sheetName = wb.SheetNames[0];
const sheet = wb.Sheets[sheetName];
const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '''' });

if (!rows.length) {
  throw new Error(''No rows found in workbook.'');
}

const header = rows[0];
const col = Object.fromEntries(header.map((name, idx) => [name, idx]));
if (col[''HUNT CODE''] === undefined) throw new Error(''Could not find HUNT CODE column.'');

const audit = [[''xlsx_row'', ''source_no'', ''old_hunt_code'', ''new_hunt_code'', ''decision'', ''species'', ''area'', ''condition'']];

let totalMulticodeRows = 0;
let changedRows = 0;

for (let i = 1; i < rows.length; i += 1) {
  const row = rows[i];
  const sourceNo = String(row[col[''No.']] || '''').trim();
  if (!sourceNo) continue;

  const original = String(row[col[''HUNT CODE'']] || '''').trim();
  const candidates = original.split('|').map((c) => String(c || '''').trim().toUpperCase()).filter(Boolean);
  if (candidates.length <= 1) continue;

  totalMulticodeRows += 1;

  const species = row[col[''Species'']] || '''';
  const area = row[col[''Area'']] || '''';
  const condition = row[col[''Condition'']] || '''';

  const valid = [];
  let invalid = 0;

  for (const code of candidates) {
    const dbRow = dbByCode.get(code);
    if (!dbRow) {
      invalid += 1;
      continue;
    }

    const speciesOk = speciesMatches(species, dbRow);
    const conditionOk = conditionMatches(condition, dbRow);
    const areaOk = areaMatches(area, dbRow.hunt_name || '''');

    if (speciesOk && conditionOk && areaOk) {
      valid.push(code);
    }
  }

  if (valid.length === 1) {
    const nextCode = valid[0];
    if (nextCode !== original) {
      row[col[''HUNT CODE'']] = nextCode;
      changedRows += 1;
      audit.push([String(i + 1), sourceNo, original, nextCode, ''deterministic_match'', species, area, condition]);
    }
  } else if (invalid === candidates.length) {
    audit.push([String(i + 1), sourceNo, original, '''', ''invalid_codes_all'', species, area, condition]);
  } else {
    audit.push([String(i + 1), sourceNo, original, '''', ''ambiguous_'' + valid.length + ''_valid'', species, area, condition]);
  }
}

if (!changedRows) {
  audit.push([''summary'', '''', ''no_changes'', ''0'', ''summary'', ''0'', ''0'', ''0'']);
}

function csvEscape(cell) {
  const text = String(cell || '''');
  return '"' + text.replace(/"/g, '""') + '"';
}

const auditText = audit.map((r) => r.map(csvEscape).join(',')).join(''\n'') + ''\n'';
fs.writeFileSync(auditPath, auditText, ''utf8'');

workbook.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
XLSX.writeFile(wb, workbookPath);

console.log(''total_multicode_rows='' + totalMulticodeRows);
console.log(''changed_rows='' + changedRows);
console.log(''audit_path=' + path.relative(repoRoot, auditPath));
