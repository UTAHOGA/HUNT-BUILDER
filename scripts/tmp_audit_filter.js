const fs = require('fs');

function parseCsv(text) {
  const lines = text.replace(/\r/g, '').split('\n');
  if (!lines.length) return [];
  let headers = null;
  const rows = [];
  function parseLine(line) {
    const out = [];
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
        else if (ch === ',') { out.push(cur); cur = ''; }
        else cur += ch;
      }
    }
    out.push(cur);
    return out;
  }

  headers = parseLine(lines[0] || '').map((h) => h.replace(/^\uFEFF/, ''));

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    const values = parseLine(line);
    const row = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] ?? '';
    });
    rows.push(row);
  }
  return rows;
}

function hasPipe(v) {
  return String(v || '').includes('|');
}

const rows = parseCsv(fs.readFileSync('audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv', 'utf8').trimEnd());
const selectedPipeWithWritable = rows.filter((r) => {
  if (!(r.join_type === 'selected' || r.join_type === 'possible_candidates')) return false;
  const written = String(r.hunt_code_written || '').trim().toUpperCase();
  const selected = String(r.selected_hunt_code || '').trim().toUpperCase();
  const possible = String(r.possible_hunt_codes || '').trim().toUpperCase();
  if (written && (written === selected)) return false;
  if (selected && written !== selected && written && !hasPipe(written)) return true;
  if (hasPipe(written) && selected && !hasPipe(selected) && !written.split('|').includes(selected)) return true;
  if (hasPipe(written) && selected && hasPipe(selected) && written !== possible) return false;
  return false;
});

console.log('count', selectedPipeWithWritable.length);
for (const r of selectedPipeWithWritable.slice(0, 120)) {
  console.log([r.source_no, r.xlsx_row, r.hunt_code_written, r.selected_hunt_code, r.possible_hunt_codes, r.match_confidence, r.join_type, r.match_notes].join(' | '));
}
