const fs = require('fs');
const XLSX = require('xlsx');

function parseCsv(path) {
  const text = fs.readFileSync(path, 'utf8').replace(/^\uFEFF/, '');
  const rows = [];
  let row = [];
  let val = '';
  let q = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const nx = text[i + 1];

    if (q) {
      if (ch === '"' && nx === '"') {
        val += '"';
        i += 1;
      } else if (ch === '"') {
        q = false;
      } else {
        val += ch;
      }
    } else {
      if (ch === '"') {
        q = true;
      } else if (ch === ',') {
        row.push(val);
        val = '';
      } else if (ch === '\n') {
        row.push(val);
        if (row.some((x) => String(x).trim() !== '')) rows.push(row);
        row = [];
        val = '';
      } else if (ch !== '\r') {
        val += ch;
      }
    }
  }

  if (val.length || row.length) {
    row.push(val);
    if (row.some((x) => String(x).trim() !== '')) rows.push(row);
  }

  if (!rows.length) return { headers: [], records: [] };
  const headers = rows.shift().map((h) => h.replace(/^\uFEFF/, '').trim());
  return {
    headers,
    records: rows.map((r) => Object.fromEntries(headers.map((h, idx) => [h, r[idx] || '']))),
  };
}

const norm = (v) => String(v || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
function speciesMatch(pdf, dbSpec, dbSex) {
  const p = norm(pdf);
  const d = norm(dbSpec);
  if (!p || !d) return false;
  if (p === 'black bear') return d.includes('black bear') || d === 'bear';
  if (p === 'antlerless elk' || p === 'elk') return d.includes('elk');
  if (p === 'deer') return d === 'deer';
  if (p === 'bison') return d === 'bison';
  if (p === 'moose') return d === 'moose';
  if (p === 'mountain goat') return d === 'mountain goat';
  if (p === 'desert bighorn sheep') return d.includes('desert bighorn sheep');
  if (p === 'rocky mountain bighorn sheep') return d.includes('rocky mountain bighorn sheep');
  if (p === 'pronghorn') return d === 'pronghorn';
  if (p === 'turkey') return d === 'turkey';
  return p === d;
}

function condMatch(condition, dbWeapon) {
  const pc = norm(condition);
  const dw = norm(dbWeapon);
  if (!pc || !dw) return true;
  if (pc === 'any legal weapon' || pc === 'any') return /any legal weapon|any/.test(dw) || /hunter/.test(dw) || dw.includes('multiseason') || dw.includes('choice');
  if (pc.includes('hunter') || pc.includes('choice')) return dw.includes('hunter') || dw.includes('choice') || dw.includes('any legal weapon') || dw.includes('multiseason');
  if (pc.includes('multiseason')) return dw.includes('multiseason');
  if (pc.includes('archery')) return dw.includes('archery');
  if (pc.includes('muzzleloader')) return dw.includes('muzzleloader');
  if (pc.includes('ram')) return true;
  if (pc.includes('late') || pc.includes('early') || pc.includes('mid')) return true;
  return dw.includes(pc);
}

function areaMatch(area, dbName) {
  const a = norm(area);
  const b = norm(dbName);
  if (!a || !b) return false;
  if (b.includes('statewide') && a.includes('statewide')) return true;
  if (a.includes('statewide') || b.includes('statewide')) return false;
  const cleanA = a.replace(/\bconservation\b/g, '').trim();
  const cleanB = b.replace(/\bconservation\b/g, '').replace(/\(/g, ' ').replace(/\)/g, ' ').trim();
  const tokensA = cleanA.split(' ').filter(Boolean);
  const tokensB = cleanB.split(' ').filter(Boolean);
  let overlap = 0;
  for (const t of tokensA) {
    if (tokensB.includes(t)) overlap += 1;
  }
  if (overlap === 0) return false;
  return overlap >= 1;
}

const db = parseCsv('pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv').records;
const byCode = new Map();
for (const r of db) {
  if (r.hunt_code) byCode.set(r.hunt_code.trim().toUpperCase(), r);
}

const wb = XLSX.readFile('processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx');
const ws = wb.Sheets[wb.SheetNames[0]];
const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
const h = rows[0];
const col = Object.fromEntries(h.map((name, i) => [name, i]));

let totalMulti = 0;
let deterministic = 0;

for (let i = 1; i < rows.length; i += 1) {
  const r = rows[i];
  if (!String(r[col['No.']] || '').trim()) continue;
  const current = String(r[col['HUNT CODE']] || '').split('|').map((s) => s.trim()).filter(Boolean);
  if (current.length <= 1) continue;

  totalMulti += 1;
  const species = r[col['Species']];
  const area = r[col['Area']];
  const cond = r[col['Condition']];
  const matched = [];

  for (const c of current) {
    const dr = byCode.get(c.toUpperCase());
    if (!dr) {
      matched.push({ code: c, ok: false, reason: 'not_in_db' });
      continue;
    }
    const ok = speciesMatch(species, dr.species, dr.sex_type) && condMatch(cond, dr.weapon) && areaMatch(area, dr.hunt_name);
    matched.push({ code: c, ok, dbName: dr.hunt_name, weapon: dr.weapon, dbSpecies: dr.species });
  }

  const good = matched.filter((x) => x.ok);
  if (good.length === 1) {
    deterministic += 1;
    console.log([i + 1, r[col['No.']], current.join('|'), good[0].code, species, area, cond].join('\t'));
  }
}

console.log('totalMulti=' + totalMulti);
console.log('deterministic=' + deterministic);
