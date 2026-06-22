const fs = require('fs');

function parseLine(line) {
  const vals = [];
  let cur = '';
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    const next = line[i + 1];
    if (q) {
      if (ch === '"' && next === '"') { cur += '"'; i += 1; }
      else if (ch === '"') q = false;
      else cur += ch;
    } else {
      if (ch === '"') q = true;
      else if (ch === ',') { vals.push(cur); cur = ''; }
      else cur += ch;
    }
  }
  vals.push(cur);
  return vals;
}

function parseCsv(path) {
  const raw = fs.readFileSync(path, 'utf8').replace(/^\uFEFF/, '').replace(/\r/g, '');
  const lines = raw.split('\n');
  if (!lines.length) return [];
  const header = parseLine(lines[0]);
  const out = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    const values = parseLine(line);
    const row = Object.fromEntries(header.map((h, idx) => [h, values[idx] ?? '']));
    out.push(row);
  }
  return out;
}

function norm(v) { return String(v || '').trim().toUpperCase(); }

const dbRows = parseCsv('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
const db = new Set();
for (const r of dbRows) {
  const code = norm(r.hunt_code);
  if (code) db.add(code);
}

const rows = parseCsv('audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv');
const bad = [];
for (const r of rows) {
  const joinType = String(r.join_type || '').trim();
  const conf = String(r.match_confidence || '').trim();
  const sel = norm(r.selected_hunt_code);
  if (!sel || sel.includes('|')) continue;
  if (!['selected', 'possible_candidates'].includes(joinType)) continue;
  if (conf !== 'HIGH') continue;

  if (!db.has(sel)) {
    bad.push({
      source_no: r.source_no,
      xlsx_row: r.xlsx_row,
      written: r.hunt_code_written,
      selected: r.selected_hunt_code,
      possible: r.possible_hunt_codes,
      notes: r.match_notes,
      area: r.workbook_hunt_name,
      species: r.workbook_species,
      join: r.match_method || r.join_type,
    });
  }
}

console.log('count', bad.length);
for (const b of bad.slice(0, 200)) {
  console.log(`${b.source_no}\t${b.xlsx_row}\t${b.written}\t${b.selected}\t${b.possible}\t${b.species}\t${b.area}\t${b.notes}`);
}
