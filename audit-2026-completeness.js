const fs = require('fs');
const path = require('path');

const INPUT = path.join(__dirname, 'processed_data', 'hunt_database_complete.csv');
const OUT_JSON = path.join(__dirname, 'processed_data', 'hunt_database_2026_completeness_report.json');
const OUT_CSV = path.join(__dirname, 'processed_data', 'hunt_database_2026_gaps.csv');
const topGapLimitArg = process.argv.find((arg) => arg.startsWith('--top='));
const TOP_GAP_LIMIT = topGapLimitArg ? Number(topGapLimitArg.split('=')[1]) : 200;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ',') {
      row.push(cell);
      cell = '';
    } else if (ch === '\n') {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
    } else if (ch !== '\r') {
      cell += ch;
    }
  }

  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }

  return rows;
}

function asBool(v) {
  return String(v || '').trim().toLowerCase() === 'true';
}

function asNum(v) {
  const n = Number(String(v || '').replace(/,/g, '').trim());
  return Number.isFinite(n) ? n : null;
}

const raw = fs.readFileSync(INPUT, 'utf8');
const [header, ...dataRows] = parseCsv(raw);
const idx = Object.fromEntries(header.map((k, i) => [k, i]));

const requiredFlags = [
  'has_master_record',
  'has_permits',
  'has_draw_history',
  'has_projection',
  'has_engine_model',
  'has_ladder_rows',
  'has_context_metrics'
];

const gaps = [];
const bySpecies = {};
let completeRows = 0;

for (const row of dataRows) {
  const missingFlags = requiredFlags.filter((flag) => !asBool(row[idx[flag]]));
  const permits2026 = asNum(row[idx.public_permits_2026]);
  const projectedApplicants = asNum(row[idx.projected_applicants_2026]);

  const warnings = [];
  if (permits2026 === null) warnings.push('missing_permits_2026');
  if (projectedApplicants === null) warnings.push('missing_projected_applicants_2026');
  if ((permits2026 || 0) > 0 && (projectedApplicants || 0) === 0) warnings.push('permits_without_applicants_projection');

  const species = row[idx.species] || 'Unknown';
  bySpecies[species] = bySpecies[species] || { total: 0, complete: 0, withGaps: 0 };
  bySpecies[species].total += 1;

  if (missingFlags.length === 0 && warnings.length === 0) {
    completeRows += 1;
    bySpecies[species].complete += 1;
    continue;
  }

  bySpecies[species].withGaps += 1;
  gaps.push({
    hunt_code: row[idx.hunt_code],
    residency: row[idx.residency],
    species,
    hunt_name: row[idx.hunt_name],
    coverage_status: row[idx.coverage_status],
    missing_flags: missingFlags.join('|') || '',
    warnings: warnings.join('|') || ''
  });
}

const report = {
  generated_at_utc: new Date().toISOString(),
  input_file: path.relative(__dirname, INPUT),
  total_rows: dataRows.length,
  fully_complete_rows: completeRows,
  rows_with_gaps_or_warnings: gaps.length,
  completion_percent: Number(((completeRows / dataRows.length) * 100).toFixed(2)),
  required_flags: requiredFlags,
  by_species: bySpecies,
  top_gap_rows: gaps.slice(0, Number.isFinite(TOP_GAP_LIMIT) && TOP_GAP_LIMIT > 0 ? TOP_GAP_LIMIT : 200)
};

fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 2));

const csvHeader = ['hunt_code', 'residency', 'species', 'hunt_name', 'coverage_status', 'missing_flags', 'warnings'];
const csvLines = [csvHeader.join(',')];
for (const g of gaps) {
  csvLines.push(csvHeader.map((key) => `"${String(g[key] || '').replace(/"/g, '""')}"`).join(','));
}
fs.writeFileSync(OUT_CSV, `${csvLines.join('\n')}\n`);

console.log(`Wrote ${path.relative(__dirname, OUT_JSON)} and ${path.relative(__dirname, OUT_CSV)}`);
console.log(`Completion: ${report.fully_complete_rows}/${report.total_rows} (${report.completion_percent}%)`);
