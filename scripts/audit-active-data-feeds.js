const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');
const vm = require('vm');
const zlib = require('zlib');

const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'processed_data', 'audits');
const pagesLimit = 25 * 1024 * 1024;
const jsonParseLimit = 20 * 1024 * 1024;

const scanDirs = [
  'data',
  'processed_data',
  'processed_data/model_outputs',
  'processed_data/management_context',
  'processed_data/hard_data_exports',
  'processed_data/library',
  'processed_data/production',
  'pipeline/RAW',
  'docs',
  'engine',
  'scripts',
];

const coreFiles = {
  database: 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv',
  master: 'processed_data/hunt_master_enriched.csv',
  ladder: 'processed_data/point_ladder_view.csv',
  engine: 'processed_data/draw_reality_engine.csv',
  engineV2: 'processed_data/draw_reality_engine_v2.csv',
  predictive: 'processed_data/draw_reality_engine_predictive_v2.csv',
  ml: 'processed_data/ml_draw_predictions_v1.csv',
  reference: 'processed_data/hunt_unit_reference_linked.csv',
  harvest: 'processed_data/harvest_master.csv',
  harvestQuality: 'processed_data/harvest_quality_features_all_years_by_hunt_code.csv',
  harvestAgeLatest: 'processed_data/harvest_age_features_by_hunt_code_latest.csv',
  harvestAgeAll: 'processed_data/harvest_age_features_by_hunt_code_all_years.csv',
  modelScores: 'processed_data/model_outputs/hunt_decision_scores_v1.csv',
  management: 'processed_data/management_context/hunt_management_objective_context.json',
  outfittersPublic: 'data/outfitters-public.json',
  outfitters: 'data/outfitters.json',
};

const coreColumns = [
  'hunt_code',
  'current_hunt_code',
  'historical_hunt_code',
  'ha_number',
  'HuntCode',
  'huntCode',
  'hunt_name',
  'unit_name',
  'hunt_unit',
  'name',
  'unit',
  'HuntName',
  'boundary_id',
  'species',
  'animal',
  'game_species',
  'year',
  'reported_hunt_year',
  'model_target_year',
  'forecast_year',
  'draw_year',
  'publish_year',
  'residency',
  'res_status',
  'resident_nonresident',
  'points',
  'bonus_points',
  'preference_points',
  'point_level',
  'hunt_type',
  'hunt_class',
  'draw_pool',
  'permits_2024',
  'permits_2024_total',
  'permits_2025',
  'permits_2025_total',
  'permits_2026',
  'permits_2026_total',
  'permits_2026_res',
  'permits_2026_nr',
  'permit_allotment_2026_total',
  'permit_allotment_2026_res',
  'permit_allotment_2026_nr',
  'p_draw',
  'p_draw_mean',
  'draw_probability',
  'average_harvest_age',
  'current_age_3yr_average',
  'average_days_hunted',
  'percent_5plus',
  'observed_value',
  'current_population_estimate',
];

const fieldNeedles = {
  hunt_code: ['hunt_code', 'current_hunt_code', 'historical_hunt_code', 'ha_number'],
  year: ['year', 'reported_hunt_year', 'model_target_year', 'draw_year', 'publish_year'],
  residency: ['residency', 'resident_nonresident', 'res_status'],
  points: ['points', 'bonus_points', 'preference_points', 'point_level'],
  species: ['species', 'animal', 'game_species'],
  permits: ['permit', 'permits', 'quota', 'allotment', 'tags'],
  applicants: ['applicant', 'applications', 'first_choice'],
  draw_probability: ['p_draw', 'p_draw_mean', 'draw_probability', 'odds', 'probability', 'p50'],
  harvest_success: ['harvest_success', 'success_percent', 'percent_success'],
  average_days_hunted: ['average_days_hunted', 'avg_days_hunted', 'mean_days_hunted'],
  average_harvest_age: ['average_harvest_age', 'avg_harvest_age', 'mean_age', 'harvest_age'],
  percent_5plus: ['percent_5plus', 'percent_5_plus', 'pct_5plus', 'age_5plus'],
  management_objective: ['objective', 'management_objective', 'age_objective', 'population_objective'],
  source_fields: ['source', 'source_file', 'source_page', 'source_url', 'retrieved_at'],
  data_as_of: ['data_as_of', 'as_of', 'retrieved_at', 'generated_at', 'updated_at'],
  model_version: ['model_version', 'engine_version', 'prediction_version'],
  rule_version: ['rule_version', 'rules_version', 'draw_rule_version'],
};

function rel(file) {
  return path.relative(root, file).replace(/\\/g, '/');
}

function text(value) {
  return String(value ?? '').trim();
}

function upper(value) {
  return text(value).toUpperCase();
}

function num(value) {
  const raw = text(value);
  if (!raw || !/[0-9]/.test(raw)) return null;
  const parsed = Number(raw.replace(/[^0-9.-]/g, ''));
  return Number.isFinite(parsed) ? parsed : null;
}

function meaningful(value) {
  const raw = upper(value);
  return !!raw && !['N/A', 'NA', 'NOT AVAILABLE', 'NULL', 'NONE', 'UNDEFINED'].includes(raw);
}

function esc(value) {
  const raw = value == null ? '' : Array.isArray(value) ? value.join('|') : String(value);
  return /[",\r\n]/.test(raw) ? `"${raw.replace(/"/g, '""')}"` : raw;
}

async function writeCsv(name, rows, columns) {
  const lines = [columns.map(esc).join(',')];
  for (const row of rows) lines.push(columns.map((col) => esc(row[col])).join(','));
  await fsp.writeFile(path.join(outDir, name), `${lines.join('\n')}\n`, 'utf8');
}

async function writeJson(name, value) {
  await fsp.writeFile(path.join(outDir, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function parseCsvLine(line) {
  const cells = [];
  let value = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const next = line[i + 1];
    if (ch === '"') {
      if (quoted && next === '"') {
        value += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      cells.push(value);
      value = '';
    } else {
      value += ch;
    }
  }
  cells.push(value);
  return cells;
}

function parseCsv(raw, wantedColumns = null) {
  const rows = [];
  let headers = null;
  let selected = null;
  let row = [];
  let value = '';
  let quoted = false;
  const commitRow = () => {
    row.push(value);
    if (row.some((cell) => text(cell))) {
      if (!headers) {
        headers = row.map(text);
        const wanted = wantedColumns ? new Set(wantedColumns.map((col) => col.toLowerCase())) : null;
        selected = headers
          .map((header, index) => ({ header, index }))
          .filter(({ header }) => !wanted || wanted.has(header.toLowerCase()));
      } else {
        rows.push(Object.fromEntries(selected.map(({ header, index }) => [header, row[index] ?? ''])));
      }
    }
    row = [];
    value = '';
  };
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    const next = raw[i + 1];
    if (ch === '"') {
      if (quoted && next === '"') {
        value += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      row.push(value);
      value = '';
    } else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && next === '\n') i += 1;
      commitRow();
    } else {
      value += ch;
    }
  }
  if (value.length || row.length) {
    commitRow();
  }
  return rows;
}

async function readCsv(relPath, wantedColumns = null) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return [];
  return parseCsv(await readTextMaybeGzip(file), wantedColumns);
}

async function readJson(relPath) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return [];
  const parsed = JSON.parse(await fsp.readFile(file, 'utf8'));
  return Array.isArray(parsed) ? parsed : Array.isArray(parsed.rows) ? parsed.rows : Array.isArray(parsed.data) ? parsed.data : [parsed];
}

async function sha(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    fs.createReadStream(file).on('data', (chunk) => hash.update(chunk)).on('error', reject).on('end', () => resolve(hash.digest('hex')));
  });
}

async function firstText(file, count = 512) {
  const handle = await fsp.open(file, 'r');
  try {
    const buffer = Buffer.alloc(count);
    const result = await handle.read(buffer, 0, count, 0);
    return buffer.slice(0, result.bytesRead).toString('utf8');
  } finally {
    await handle.close();
  }
}

async function isGzipFile(file) {
  const handle = await fsp.open(file, 'r');
  try {
    const buffer = Buffer.alloc(2);
    const result = await handle.read(buffer, 0, 2, 0);
    return result.bytesRead === 2 && buffer[0] === 0x1f && buffer[1] === 0x8b;
  } finally {
    await handle.close();
  }
}

async function readTextMaybeGzip(file) {
  const buffer = await fsp.readFile(file);
  return buffer.length >= 2 && buffer[0] === 0x1f && buffer[1] === 0x8b
    ? zlib.gunzipSync(buffer).toString('utf8')
    : buffer.toString('utf8');
}

async function csvProfile(file) {
  let header = [];
  let rowCount = 0;
  const input = await isGzipFile(file) ? fs.createReadStream(file).pipe(zlib.createGunzip()) : fs.createReadStream(file, { encoding: 'utf8' });
  const rl = readline.createInterface({ input, crlfDelay: Infinity });
  for await (const line of rl) {
    if (!header.length) {
      if (text(line)) header = parseCsvLine(line).map(text);
    } else if (text(line)) {
      rowCount += 1;
    }
  }
  return { row_count: rowCount, column_count: header.length, columns: header };
}

async function jsonProfile(file, size) {
  if (size > jsonParseLimit) return { row_count: '', column_count: '', columns: [] };
  try {
    const parsed = JSON.parse(await fsp.readFile(file, 'utf8'));
    const rows = Array.isArray(parsed) ? parsed : Array.isArray(parsed.features) ? parsed.features : Array.isArray(parsed.rows) ? parsed.rows : Array.isArray(parsed.data) ? parsed.data : [parsed];
    const columns = new Set();
    rows.slice(0, 200).forEach((row) => Object.keys(row?.properties || row || {}).forEach((key) => columns.add(key)));
    return { row_count: rows.length, column_count: columns.size, columns: [...columns].sort() };
  } catch {
    return { row_count: '', column_count: '', columns: [] };
  }
}

function colHas(columns, group) {
  const lower = columns.map((c) => c.toLowerCase());
  return fieldNeedles[group].some((needle) => lower.some((col) => col === needle || col.includes(needle)));
}

function family(file, columns) {
  const p = file.toLowerCase();
  const cols = columns.join('|').toLowerCase();
  if (p.endsWith('database.csv')) return 'official_hunt_database';
  if (p.includes('outfitter')) return 'outfitter_data';
  if (p.includes('management_context') || cols.includes('management_objective') || cols.includes('population_objective')) return 'management_plan_context';
  if (p.includes('boundary') || p.endsWith('.geojson')) return 'boundary_geo';
  if (p.includes('point_ladder')) return 'point_ladder';
  if (p.includes('draw_reality_engine_predictive') || p.includes('ml_draw_predictions')) return 'draw_prediction';
  if (p.includes('draw_reality') || p.includes('draw_results') || p.includes('draw_truth')) return 'draw_truth';
  if (p.includes('harvest_age') || cols.includes('average_harvest_age')) return 'harvest_age';
  if (p.includes('harvest_quality')) return 'harvest_quality';
  if (p.includes('harvest')) return 'harvest_truth';
  if (p.includes('library') || p.includes('hard_data_exports') || p.includes('hard-copy')) return 'public_library';
  if (p.includes('hunt_master') || p.includes('hunt_unit_reference') || p.includes('canonical')) return 'hunt_reference';
  if (p.includes('model_outputs')) return 'model_output';
  if (p.includes('audit') || p.includes('report')) return 'audit_report';
  if (p.includes('snapshot')) return 'source_snapshot';
  if (p.includes('processed_data')) return 'website_runtime';
  return 'unknown';
}

function role(dataFamily, file) {
  if (dataFamily === 'official_hunt_database') return 'source_truth';
  if (['draw_truth', 'harvest_truth'].includes(dataFamily)) return 'normalized_truth';
  if (['draw_prediction', 'model_output'].includes(dataFamily)) return 'model_output';
  if (['point_ladder', 'hunt_reference', 'website_runtime', 'boundary_geo'].includes(dataFamily)) return 'runtime_feed';
  if (dataFamily === 'management_plan_context') return 'context_only';
  if (dataFamily === 'public_library') return 'website_display';
  if (dataFamily === 'outfitter_data') return file.includes('public') ? 'public_runtime_feed' : 'runtime_feed';
  if (dataFamily === 'audit_report') return 'audit_only';
  return 'unknown';
}

function engines(dataFamily) {
  const uses = [];
  if (['official_hunt_database', 'hunt_reference', 'boundary_geo'].includes(dataFamily)) uses.push('hunt_builder');
  if (['hunt_reference', 'point_ladder', 'draw_truth', 'draw_prediction'].includes(dataFamily)) uses.push('hunt_research');
  if (['draw_truth', 'draw_prediction', 'point_ladder'].includes(dataFamily)) uses.push('predictive_draw_engine');
  if (['harvest_truth', 'harvest_quality'].includes(dataFamily)) uses.push('harvest_quality_engine');
  if (dataFamily === 'harvest_age') uses.push('age_quality_engine');
  if (dataFamily === 'management_plan_context') uses.push('management_objective_engine');
  if (dataFamily === 'outfitter_data') uses.push('outfitter_matching');
  if (dataFamily === 'public_library') uses.push('public_library');
  return uses.length ? uses.join('|') : 'none';
}

function pages(dataFamily) {
  const use = [];
  if (['official_hunt_database', 'hunt_reference', 'boundary_geo', 'outfitter_data'].includes(dataFamily)) use.push('hunt_builder');
  if (['hunt_reference', 'point_ladder', 'draw_truth', 'draw_prediction', 'management_plan_context'].includes(dataFamily)) use.push('hunt_research');
  if (dataFamily === 'public_library') use.push('hard-copy/library');
  if (dataFamily === 'outfitter_data') use.push('outfitter');
  return use.join('|') || 'none';
}

async function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const item of await fsp.readdir(dir, { withFileTypes: true })) {
    if (['.git', 'node_modules', 'pages-dist'].includes(item.name)) continue;
    const full = path.join(dir, item.name);
    if (item.isDirectory()) await walk(full, out);
    else if (item.isFile()) out.push(full);
  }
  return out;
}

async function inventory() {
  const files = new Set();
  for (const dir of scanDirs) (await walk(path.join(root, dir))).forEach((file) => files.add(file));
  Object.values(coreFiles).forEach((p) => { const f = path.join(root, p); if (fs.existsSync(f)) files.add(f); });
  const rows = [];
  for (const file of [...files].sort((a, b) => rel(a).localeCompare(rel(b)))) {
    const stat = await fsp.stat(file);
    const extension = path.extname(file).slice(1).toLowerCase();
    const head = await firstText(file).catch(() => '');
    const isPointer = head.startsWith('version https://git-lfs.github.com/spec/v1');
    let profile = { row_count: '', column_count: '', columns: [] };
    if (!isPointer && extension === 'csv') profile = await csvProfile(file);
    if (!isPointer && ['json', 'geojson'].includes(extension)) profile = await jsonProfile(file, stat.size);
    const dataFamily = family(rel(file), profile.columns);
    const sourceRole = role(dataFamily, rel(file).toLowerCase());
    const publicUse = ['runtime_feed', 'public_runtime_feed', 'website_display'].includes(sourceRole) ? engines(dataFamily) : 'none';
    const row = {
      file_path: rel(file),
      file_name: path.basename(file),
      extension,
      size_bytes: stat.size,
      sha256: await sha(file),
      row_count: profile.row_count,
      column_count: profile.column_count,
      columns: profile.columns.join('|'),
      data_family: dataFamily,
      source_role: sourceRole,
      engine_use: engines(dataFamily),
      public_runtime_use: publicUse,
      website_page_use: pages(dataFamily),
      is_git_lfs_pointer: isPointer,
      is_large_runtime_file: stat.size > pagesLimit,
      has_hunt_code: colHas(profile.columns, 'hunt_code'),
      has_year: colHas(profile.columns, 'year'),
      has_residency: colHas(profile.columns, 'residency'),
      has_points: colHas(profile.columns, 'points'),
      has_species: colHas(profile.columns, 'species'),
      has_permits: colHas(profile.columns, 'permits'),
      has_applicants: colHas(profile.columns, 'applicants'),
      has_draw_probability: colHas(profile.columns, 'draw_probability'),
      has_harvest_success: colHas(profile.columns, 'harvest_success'),
      has_average_days_hunted: colHas(profile.columns, 'average_days_hunted'),
      has_average_harvest_age: colHas(profile.columns, 'average_harvest_age'),
      has_percent_5plus: colHas(profile.columns, 'percent_5plus'),
      has_management_objective: colHas(profile.columns, 'management_objective'),
      has_source_fields: colHas(profile.columns, 'source_fields'),
      data_as_of_field_present: colHas(profile.columns, 'data_as_of'),
      model_version_field_present: colHas(profile.columns, 'model_version'),
      rule_version_field_present: colHas(profile.columns, 'rule_version'),
      recommended_status: 'OK_INVENTORIED',
      notes: '',
    };
    if (row.is_git_lfs_pointer) row.recommended_status = 'BLOCK_PUBLIC_POINTER';
    else if (row.is_large_runtime_file && row.public_runtime_use !== 'none') row.recommended_status = 'NEEDS_CLOUDFLARE_OR_DIST_EXCLUSION';
    else if (row.data_family === 'unknown') row.recommended_status = 'REVIEW_CLASSIFICATION';
    row.notes = [row.is_git_lfs_pointer ? 'Git LFS pointer content' : '', row.is_large_runtime_file ? 'larger than Pages single-file limit' : ''].filter(Boolean).join('; ');
    rows.push(row);
  }
  return rows;
}

function code(row) {
  return upper(row.hunt_code || row.current_hunt_code || row.historical_hunt_code || row.ha_number || row.HuntCode || row.huntCode);
}
function huntName(row) { return text(row.hunt_name || row.unit_name || row.hunt_unit || row.name || row.unit || row.HuntName); }
function species(row) { return text(row.species || row.animal || row.game_species); }
function residency(row) { return text(row.residency || row.res_status || row.resident_nonresident); }
function points(row) { const n = num(row.points || row.bonus_points || row.preference_points || row.point_level); return n == null ? '' : String(n); }

function uniq(rows, getter) {
  const set = new Set();
  (rows || []).forEach((row) => { const value = getter(row); if (meaningful(value)) set.add(String(value)); });
  return set;
}

function headers(rows) {
  const set = new Set();
  (rows || []).slice(0, 50).forEach((row) => Object.keys(row).forEach((key) => set.add(key)));
  return [...set];
}

function edge(source_file, rows, target, targetRows, join_keys, required_columns, fix) {
  const have = new Set(headers(rows).map((h) => h.toLowerCase()));
  const missing = required_columns.filter((col) => !have.has(col.toLowerCase()));
  const sourceCodes = uniq(rows, code);
  const targetCodes = targetRows ? uniq(targetRows, code) : new Set();
  let matched = 0;
  for (const c of sourceCodes) if (targetCodes.has(c)) matched += 1;
  const unmatched = targetRows ? Math.max(0, sourceCodes.size - matched) : '';
  let syncStatus = 'SYNC_CHECKED';
  if (missing.length) syncStatus = 'MISSING_COLUMNS';
  else if (targetRows && sourceCodes.size && !matched) syncStatus = 'NO_HUNT_CODE_MATCHES';
  else if (targetRows && unmatched > 0) syncStatus = 'PARTIAL_MATCH';
  return {
    source_file,
    target_file_or_page: target,
    join_keys: join_keys.join('|'),
    required_columns: required_columns.join('|'),
    missing_required_columns: missing.join('|'),
    row_count: (rows || []).length,
    matched_hunt_code_count: targetRows ? matched : '',
    unmatched_hunt_code_count: unmatched,
    sync_status: syncStatus,
    recommended_fix: missing.length ? `Populate/review columns: ${missing.join(', ')}` : fix,
  };
}

async function loadCore() {
  const core = { paths: coreFiles };
  for (const [key, relPath] of Object.entries(coreFiles)) {
    core[key] = relPath.endsWith('.json') ? await readJson(relPath) : await readCsv(relPath, coreColumns);
  }
  return core;
}

function syncMatrix(core) {
  return [
    edge(core.paths.database, core.database, 'Hunt Builder page', core.reference, ['hunt_code', 'boundary_id'], ['hunt_code', 'hunt_name', 'species'], 'Keep DATABASE aligned to reference/boundary rows.'),
    edge(core.paths.reference, core.reference, 'Hunt Research page', core.database, ['hunt_code', 'residency'], ['hunt_code', 'species'], 'Reference should align to current DATABASE hunt-code universe.'),
    edge(core.paths.ladder, core.ladder, 'Point ladder', core.reference, ['hunt_code', 'residency', 'points'], ['hunt_code', 'residency', 'points'], 'Generate ladder/status rows for missing current hunts.'),
    edge(core.paths.predictive, core.predictive, 'Predictive draw probability', core.reference, ['hunt_code', 'residency', 'points'], ['hunt_code', 'residency', 'points', 'p_draw_mean'], 'Keep p_draw fields keyed by hunt/residency/points.'),
    edge(core.paths.harvestQuality, core.harvestQuality, 'Harvest quality', core.reference, ['hunt_code', 'reported_hunt_year'], ['hunt_code'], 'Crosswalk annual harvest rows with lineage.'),
    edge(core.paths.harvestAgeLatest, core.harvestAgeLatest, 'Age quality', core.reference, ['hunt_code', 'reported_hunt_year'], ['hunt_code', 'average_harvest_age'], 'Only promote reviewed numeric age rows.'),
    edge(core.paths.management, core.management, 'State management objective comparison', core.reference, ['hunt_code', 'boundary_id'], ['hunt_code'], 'Render benchmark-only unless observed values are mapped.'),
    edge(core.paths.master, core.master, 'Comparable hunts', core.reference, ['species', 'hunt_type', 'residency', 'hunt_code'], ['hunt_code', 'species'], 'Comparable hunts require consistent species/type/residency fields.'),
    edge('processed_data/hard_data_exports + processed_data/library', core.reference, 'Public hard-copy/library page', core.database, ['hunt_code', 'boundary_id'], ['hunt_code', 'hunt_name', 'species'], 'Keep library mapping status explicit.'),
    edge(core.paths.outfittersPublic, core.outfittersPublic, 'Outfitter verification/matching page', core.reference, ['boundary_id', 'hunt_code', 'species'], [], 'Add reviewed coverage links where possible.'),
  ];
}

function holes(core, inv) {
  const out = [];
  const add = (severity, issue_type, file_path, hunt_code, details, recommended_fix) => out.push({ severity, issue_type, file_path, hunt_code, details, recommended_fix });
  inv.forEach((row) => {
    if (row.is_git_lfs_pointer) add('CRITICAL', 'public_runtime_file_is_git_lfs_pointer', row.file_path, '', 'File is a Git LFS pointer.', 'Serve via Cloudflare/R2 or remove from browser runtime.');
    if (row.is_large_runtime_file && row.public_runtime_use !== 'none') add('HIGH', 'public_runtime_file_too_large_for_pages', row.file_path, '', `${row.size_bytes} bytes`, 'Prefer Cloudflare/R2 before Pages for this runtime file.');
  });
  const files = [[core.paths.database, core.database], [core.paths.reference, core.reference], [core.paths.ladder, core.ladder], [core.paths.predictive, core.predictive], [core.paths.engineV2, core.engineV2], [core.paths.harvestAgeLatest, core.harvestAgeLatest]];
  files.forEach(([file, rows]) => rows.forEach((row, i) => {
    const c = code(row);
    if (!c) add('HIGH', 'hunt_code_missing', file, '', `Row ${i + 2}`, 'Review mapping; runtime rows need hunt_code or mapping status.');
    const res = num(row.permits_2026_res ?? row.permit_allotment_2026_res);
    const nr = num(row.permits_2026_nr ?? row.permit_allotment_2026_nr);
    const total = num(row.permits_2026_total ?? row.permit_allotment_2026_total);
    if (res != null && nr != null && total != null && res + nr !== total) add('HIGH', 'permit_total_mismatch', file, c, `Res ${res} + NonRes ${nr} != Total ${total}`, 'Audit permit lineage; do not auto-overwrite.');
    const p = num(row.p_draw_mean ?? row.p_draw ?? row.draw_probability);
    if (p != null && (!meaningful(residency(row)) || !meaningful(points(row)))) add('HIGH', 'p_draw_mean_exists_but_points_or_residency_missing', file, c, `p_draw-like value ${p}`, 'Repair draw keys before runtime use.');
    if (p != null && (p < 0 || p > 100)) add('HIGH', 'draw_probability_outside_expected_range', file, c, `Value ${p}`, 'Normalize/document probability scale.');
    const age = num(row.average_harvest_age);
    if (age === 0) add('MEDIUM', 'average_harvest_age_zero', file, c, 'average_harvest_age = 0', 'Treat as missing; do not display as verified age.');
    if (meaningful(row.average_harvest_age) && text(row.average_harvest_age) === text(row.average_days_hunted)) add('HIGH', 'average_days_hunted_appears_in_age_field', file, c, text(row.average_harvest_age), 'Review age mapping.');
    if (meaningful(row.percent_5plus) && text(row.percent_5plus) === text(row.average_harvest_age)) add('HIGH', 'percent_5plus_mapped_as_average_harvest_age', file, c, text(row.percent_5plus), 'Review age mapping.');
  }));
  const dup = (file, rows, keys) => {
    const seen = new Map();
    rows.forEach((row) => {
      const key = keys.map((k) => upper(row[k])).join('|');
      if (key.replace(/\|/g, '')) seen.set(key, (seen.get(key) || 0) + 1);
    });
    for (const [key, count] of seen) if (count > 1) add('MEDIUM', 'duplicate_hunt_code_year_residency_points', file, key.split('|')[0], `${count} rows share ${key}`, 'Review duplicate context before promotion.');
  };
  dup(core.paths.ladder, core.ladder, ['hunt_code', 'year', 'residency', 'points']);
  dup(core.paths.predictive, core.predictive, ['hunt_code', 'model_target_year', 'residency', 'points']);
  const refCodes = uniq(core.reference, code);
  const ladderCodes = uniq(core.ladder, code);
  for (const c of ladderCodes) if (!refCodes.has(c)) add('HIGH', 'point_ladder_row_exists_but_hunt_reference_missing', core.paths.ladder, c, 'Ladder code not in reference feed.', 'Reconcile ladder universe with reference feed.');
  for (const c of refCodes) if (!ladderCodes.has(c)) add('MEDIUM', 'hunt_reference_row_exists_but_ladder_missing', core.paths.reference, c, 'Reference code has no ladder row.', 'Generate ladder/status row or classify as non-ladder family.');
  const current = [...core.database, ...core.reference, ...core.master];
  const speciesByCode = new Map();
  const nameByCode = new Map();
  current.forEach((row) => {
    const c = code(row);
    if (!c) return;
    if (species(row)) (speciesByCode.get(c) || speciesByCode.set(c, new Set()).get(c)).add(species(row).toLowerCase());
    if (huntName(row)) (nameByCode.get(c) || nameByCode.set(c, new Set()).get(c)).add(huntName(row).toLowerCase());
  });
  for (const [c, set] of speciesByCode) if (set.size > 1) add('HIGH', 'same_hunt_code_different_species_across_files', 'current feeds', c, [...set].join('|'), 'Review code reuse/stale rows.');
  for (const [c, set] of nameByCode) if (set.size > 1) add('MEDIUM', 'same_hunt_code_conflicting_hunt_name_across_files', 'current feeds', c, [...set].slice(0, 6).join('|'), 'Review renamed hunts and crosswalk.');
  core.management.forEach((row) => {
    const c = code(row);
    if (c && !meaningful(row.observed_value) && !meaningful(row.current_age_3yr_average) && !meaningful(row.current_population_estimate)) add('MEDIUM', 'management_objective_exists_but_observed_comparison_missing', core.paths.management, c, 'Objective row lacks observed comparison value.', 'Render as benchmark-only or add observed source fields.');
  });
  return out;
}

function yearAudit(core) {
  const rows = [];
  core.database.forEach((row) => {
    const c = code(row);
    if (!c) return;
    const p24 = num(row.permits_2024_total ?? row.permits_2024);
    const p25 = num(row.permits_2025_total ?? row.permits_2025);
    const p26 = num(row.permits_2026_total ?? row.permits_2026 ?? row.permit_allotment_2026_total);
    const flags = [];
    if ((p25 == null || p25 === 0) && p26 != null && p26 > 0) flags.push('new_hunts_2026');
    if (p25 != null && p25 > 0 && (p26 == null || p26 === 0)) flags.push('deleted_hunts_2026');
    if (p25 != null && p25 > 0 && p26 != null && p26 !== p25) flags.push('permit_count_changed');
    const pct = p25 && p26 != null ? ((p26 - p25) / p25) * 100 : null;
    if (pct != null && Math.abs(pct) > 20) flags.push('permit_change_gt_20_percent');
    if (!uniq(core.ladder.filter((r) => code(r) === c), code).size) flags.push('point_ladder_missing');
    if (!uniq(core.harvestQuality.filter((r) => code(r) === c), code).size && !uniq(core.harvest.filter((r) => code(r) === c), code).size) flags.push('harvest_missing');
    if (!uniq(core.harvestAgeLatest.filter((r) => code(r) === c), code).size) flags.push('age_missing');
    if (!uniq(core.management.filter((r) => code(r) === c), code).size) flags.push('management_objective_missing');
    if (flags.length) rows.push({
      hunt_code: c,
      hunt_name: huntName(row),
      species: species(row),
      permits_2024: p24 ?? '',
      permits_2025: p25 ?? '',
      permits_2026: p26 ?? '',
      permit_change_pct_2025_to_2026: pct == null ? '' : Number(pct.toFixed(2)),
      draw_family_changed: '',
      species_changed: '',
      change_flags: flags.join('|'),
      context_note: species(row).toLowerCase().includes('deer') && flags.includes('permit_change_gt_20_percent') ? 'Deer permit change exceeds 20% context flag; audit only, not prediction.' : '',
    });
  });
  const byName = new Map();
  core.database.forEach((row) => {
    const key = `${huntName(row).toLowerCase()}|${species(row).toLowerCase()}`;
    if (!huntName(row)) return;
    (byName.get(key) || byName.set(key, []).get(key)).push(row);
  });
  for (const list of byName.values()) {
    const codes = new Set(list.map(code).filter(Boolean));
    if (codes.size > 1) list.forEach((row) => rows.push({
      hunt_code: code(row),
      hunt_name: huntName(row),
      species: species(row),
      permits_2024: '',
      permits_2025: '',
      permits_2026: '',
      permit_change_pct_2025_to_2026: '',
      draw_family_changed: '',
      species_changed: '',
      change_flags: 'same_name_different_code',
      context_note: `Same name/species maps to codes: ${[...codes].join(', ')}`,
    }));
  }
  return rows;
}

function loadConfig() {
  const sandbox = { window: { location: { protocol: 'https:', hostname: 'huntbuilder.uoga.org' } }, console };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(root, 'config.js'), 'utf8'), sandbox, { filename: 'config.js' });
  return sandbox.window.UOGA_CONFIG || {};
}

async function testUrl(url) {
  const row = { url, status: '', content_type: '', byte_length: '', is_lfs_pointer: false, looks_like_csv_or_json: false, ok_for_browser_runtime: false, error: '' };
  if (!/^https?:/.test(url)) {
    row.error = 'local_or_non_http_source_not_fetched';
    return row;
  }
  try {
    const response = await fetch(url, { cache: 'no-store' });
    const body = await response.text();
    const first = body.split(/\r?\n/).find((line) => text(line)) || '';
    row.status = response.status;
    row.content_type = response.headers.get('content-type') || '';
    row.byte_length = Buffer.byteLength(body);
    row.is_lfs_pointer = body.startsWith('version https://git-lfs.github.com/spec/v1');
    row.looks_like_csv_or_json = (first.includes(',') && !first.trim().startsWith('<html')) || first.trim().startsWith('{') || first.trim().startsWith('[');
    row.ok_for_browser_runtime = response.ok && !row.is_lfs_pointer && row.looks_like_csv_or_json;
  } catch (error) {
    row.error = error.message;
  }
  return row;
}

async function runtimeDelivery() {
  const cfg = loadConfig();
  const groups = {
    HUNT_RESEARCH_ENGINE_SOURCES: cfg.HUNT_RESEARCH_ENGINE_SOURCES || [],
    HUNT_RESEARCH_LADDER_SOURCES: cfg.HUNT_RESEARCH_LADDER_SOURCES || [],
    HUNT_RESEARCH_MASTER_SOURCES: cfg.HUNT_RESEARCH_MASTER_SOURCES || [],
    HUNT_RESEARCH_REFERENCE_SOURCES: cfg.HUNT_RESEARCH_REFERENCE_SOURCES || [],
  };
  const tests = [];
  for (const [source_group, urls] of Object.entries(groups)) {
    for (let i = 0; i < urls.length; i += 1) tests.push({ ...(await testUrl(urls[i])), source_group, source_order: i + 1 });
  }
  const ordering = Object.entries(groups).map(([source_group, urls]) => ({
    source_group,
    first_source: urls[0] || '',
    cloudflare_first: /^https:\/\/json\.uoga\.workers\.dev/.test(urls[0] || ''),
    source_count: urls.length,
  }));
  return {
    generated_at: new Date().toISOString(),
    cloudflare_first_all_research_runtime_groups: ordering.every((row) => row.cloudflare_first),
    ordering,
    source_tests: tests,
  };
}

function readiness(core, issueRows, runtime) {
  const ref = uniq(core.reference, code).size;
  const ladder = uniq(core.ladder, code).size;
  const pred = uniq(core.predictive, code).size;
  const harvest = uniq(core.harvestQuality, code).size || uniq(core.harvest, code).size;
  const age = uniq(core.harvestAgeLatest, code).size;
  const mgmt = uniq(core.management, code).size;
  const ageIssueTypes = new Set(['average_harvest_age_zero', 'average_days_hunted_appears_in_age_field', 'percent_5plus_mapped_as_average_harvest_age']);
  const enginesOut = [];
  function add(engine_name, required_inputs, available_inputs, missing_inputs, critical_holes, can_populate_results, confidence, recommended_next_fix) {
    let status = 'READY';
    if (critical_holes.length) status = 'NEEDS_SOURCE_SYNC';
    if (missing_inputs.length) status = can_populate_results ? 'PARTIAL' : 'BLOCKED';
    if (!available_inputs.length) status = 'PLACEHOLDER_ONLY';
    enginesOut.push({ engine_name, status, required_inputs, available_inputs, missing_inputs, critical_holes, can_populate_results, confidence, recommended_next_fix });
  }
  add('Hunt Builder selection/filter/map', ['DATABASE.csv', 'hunt reference', 'boundary files'], [`reference codes ${ref}`], [], [], ref > 0, 'HIGH', 'Keep DATABASE/reference/boundary IDs aligned.');
  add('Hunt Research core summary', ['reference', 'engine', 'ladder', 'Cloudflare runtime'], [`reference codes ${ref}`, `runtime ok ${runtime.source_tests.filter((r) => r.ok_for_browser_runtime).length}`], runtime.cloudflare_first_all_research_runtime_groups ? [] : ['Cloudflare-first ordering'], [], ref > 0, 'HIGH', 'Maintain Cloudflare-first runtime CSV delivery.');
  add('Point ladder', ['point_ladder_view.csv'], [`ladder codes ${ladder}`, `ladder rows ${core.ladder.length}`], ladder ? [] : ['point_ladder_view.csv'], issueRows.filter((r) => r.issue_type === 'hunt_reference_row_exists_but_ladder_missing').slice(0, 5).map((r) => r.hunt_code), ladder > 0, 'HIGH', 'Review current hunts missing ladder/status rows.');
  add('Predictive draw odds', ['draw_reality_engine_predictive_v2.csv', 'p_draw_mean'], [`predictive codes ${pred}`, `predictive rows ${core.predictive.length}`], pred ? [] : ['predictive rows'], issueRows.filter((r) => r.issue_type.includes('draw_probability') || r.issue_type.includes('p_draw')).slice(0, 5).map((r) => `${r.hunt_code}:${r.issue_type}`), pred > 0, 'MEDIUM', 'Resolve pending families after source sync; do not change formulas in audit task.');
  add('Comparable hunts', ['hunt_master_enriched.csv'], [`master rows ${core.master.length}`], core.master.length ? [] : ['hunt_master_enriched.csv'], [], core.master.length > 0, 'MEDIUM', 'Improve comparable scoring after field consistency audit.');
  add('Harvest quality', ['harvest_master.csv', 'harvest_quality_features_all_years_by_hunt_code.csv'], [`harvest codes ${harvest}`], harvest ? [] : ['harvest quality rows'], [], harvest > 0, 'MEDIUM', 'Continue annual harvest crosswalk lineage repair.');
  add('Age quality', ['harvest_age_features_by_hunt_code_latest.csv'], [`age codes ${age}`], age ? [] : ['reviewed age rows'], issueRows.filter((r) => ageIssueTypes.has(r.issue_type)).slice(0, 5).map((r) => `${r.hunt_code}:${r.issue_type}`), age > 0, 'MEDIUM', 'Keep observed average_harvest_age separate from days and 3-year current age.');
  add('State management objective', ['hunt_management_objective_context.json'], [`management codes ${mgmt}`], mgmt ? [] : ['management context'], issueRows.filter((r) => r.issue_type.includes('management_objective')).slice(0, 5).map((r) => r.hunt_code), mgmt > 0, 'MEDIUM', 'Render benchmark-only unless observed comparison exists.');
  add('Outfitter matching', ['outfitters-public.json'], [`outfitter rows ${core.outfittersPublic.length}`], core.outfittersPublic.length ? [] : ['outfitter public data'], [], core.outfittersPublic.length > 0, 'MEDIUM', 'Add reviewed coverage/boundary links.');
  add('Public library', ['processed_data/library', 'hard_data_exports'], [`reference codes ${ref}`], [], [], true, 'MEDIUM', 'Keep library mapping statuses explicit and audit moved PDFs.');
  return enginesOut;
}

function readinessMd(report) {
  const lines = ['# Engine Readiness Report', '', `Generated: ${report.generated_at}`, '', '| Engine/Page | Status | Can Populate | Confidence | Critical Holes | Next Fix |', '|---|---:|---:|---:|---|---|'];
  report.engines.forEach((row) => lines.push(`| ${row.engine_name} | ${row.status} | ${row.can_populate_results ? 'yes' : 'no'} | ${row.confidence} | ${row.critical_holes.join('<br>') || 'None flagged in top audit'} | ${row.recommended_next_fix} |`));
  lines.push('', '## Summary Counts', '');
  Object.entries(report.summary_counts).forEach(([key, value]) => lines.push(`- ${key}: ${value}`));
  return `${lines.join('\n')}\n`;
}

async function main() {
  await fsp.mkdir(outDir, { recursive: true });
  const inv = await inventory();
  const core = await loadCore();
  const sync = syncMatrix(core);
  const issueRows = holes(core, inv);
  const yty = yearAudit(core);
  const runtime = await runtimeDelivery();
  const engineRows = readiness(core, issueRows, runtime);
  const report = {
    generated_at: new Date().toISOString(),
    summary_counts: {
      inventory_files: inv.length,
      sync_edges: sync.length,
      data_holes: issueRows.length,
      year_to_year_flags: yty.length,
      runtime_sources_tested: runtime.source_tests.length,
      runtime_sources_ok: runtime.source_tests.filter((r) => r.ok_for_browser_runtime).length,
      engines_ready: engineRows.filter((e) => e.status === 'READY').length,
      engines_partial: engineRows.filter((e) => e.status === 'PARTIAL').length,
      engines_blocked: engineRows.filter((e) => e.status === 'BLOCKED').length,
      engines_placeholder_only: engineRows.filter((e) => e.status === 'PLACEHOLDER_ONLY').length,
      engines_needs_source_sync: engineRows.filter((e) => e.status === 'NEEDS_SOURCE_SYNC').length,
    },
    engines: engineRows,
  };
  await writeCsv('active_data_feed_inventory.csv', inv, ['file_path','file_name','extension','size_bytes','sha256','row_count','column_count','columns','data_family','source_role','engine_use','public_runtime_use','website_page_use','is_git_lfs_pointer','is_large_runtime_file','has_hunt_code','has_year','has_residency','has_points','has_species','has_permits','has_applicants','has_draw_probability','has_harvest_success','has_average_days_hunted','has_average_harvest_age','has_percent_5plus','has_management_objective','has_source_fields','data_as_of_field_present','model_version_field_present','rule_version_field_present','recommended_status','notes']);
  await writeJson('active_data_feed_inventory.json', inv);
  await writeCsv('active_data_feed_sync_matrix.csv', sync, ['source_file','target_file_or_page','join_keys','required_columns','missing_required_columns','row_count','matched_hunt_code_count','unmatched_hunt_code_count','sync_status','recommended_fix']);
  await writeJson('active_data_feed_sync_matrix.json', sync);
  await writeCsv('data_holes_and_inconsistencies.csv', issueRows, ['severity','issue_type','file_path','hunt_code','details','recommended_fix']);
  await writeCsv('year_to_year_hunt_change_report.csv', yty, ['hunt_code','hunt_name','species','permits_2024','permits_2025','permits_2026','permit_change_pct_2025_to_2026','draw_family_changed','species_changed','change_flags','context_note']);
  await writeJson('year_to_year_hunt_change_report.json', yty);
  await writeJson('runtime_public_delivery_report.json', runtime);
  await writeJson('engine_readiness_report.json', report);
  await fsp.writeFile(path.join(outDir, 'engine_readiness_report.md'), readinessMd(report), 'utf8');
  console.log(JSON.stringify(report.summary_counts, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
