const fs = require('fs');
const path = require('path');
const readline = require('readline');

const ROOT = path.resolve(__dirname, '..');
const MAX_PAGES_FILE_BYTES = 25 * 1024 * 1024;
const CLOUDFLARE_BASE = (process.env.CLOUDFLARE_OBJECT_BASE || process.env.CLOUDFLARE_R2_BASE || 'https://json.uoga.workers.dev').replace(/\/+$/, '');

const INPUTS = {
  currentDatabase: 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv',
  currentCanonicalRaw: 'pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv',
  currentCanonicalProcessed: 'processed_data/hunt-master-canonical-2026-source-of-truth.csv',
  huntDatabaseComplete: 'processed_data/hunt_database_complete.csv',
  huntMasterEnriched: 'processed_data/hunt_master_enriched.csv',
  huntUnitReferenceLinked: 'processed_data/hunt_unit_reference_linked.csv',
  drawRealityEngine: 'processed_data/draw_reality_engine.csv',
  drawRealityEngineV2: 'processed_data/draw_reality_engine_v2.csv',
  drawRealityEnginePredictive: 'processed_data/draw_reality_engine_predictive_v2.csv',
  mlDrawPredictions: 'processed_data/ml_draw_predictions_v1.csv',
  pointLadderView: 'processed_data/point_ladder_view.csv',
  coverageReport: 'processed_data/draw_system_coverage_report.csv',
  predictiveCoverageReport: 'processed_data/predictive_coverage_report.csv',
  crosswalk: 'processed_data/current_to_historical_hunt_code_crosswalk_2026.csv',
  harvestMaster: 'processed_data/harvest_master.csv',
  harvestQualityAllYears: 'processed_data/harvest_quality_features_all_years_by_hunt_code.csv',
  harvestQuality2026: 'pipeline/RAW/hunt_unit_database/2026/csv/harvest_quality_features_by_hunt_code_2025_for_2026.csv',
  researchLibraryMaster: 'processed_data/research_library_master.csv',
};

const OUTPUTS = {
  canonicalCurrent: 'processed_data/library/canonical_current_hunts_2026.csv',
  libraryCsv: 'processed_data/library/library_page_hunts.csv',
  libraryJson: 'processed_data/library/library_page_data.json',
  librarySummary: 'processed_data/library/library_page_summary.json',
  libraryManifestCsv: 'processed_data/library/hard_data_library_manifest.csv',
  libraryManifestJson: 'processed_data/library/hard_data_library_manifest.json',
  productionCsv: 'processed_data/production/library_page_hunts.csv',
  productionJson: 'processed_data/production/library_page_data.json',
  productionSummary: 'processed_data/production/library_page_summary.json',
  hardDataExportCsv: 'processed_data/hard_data_exports/library/library_page_hunts.csv',
  hardDataExportJson: 'processed_data/hard_data_exports/library/library_page_data.json',
  hardDataExportSummary: 'processed_data/hard_data_exports/library/library_page_summary.json',
  hardDataExportManifestCsv: 'processed_data/hard_data_exports/library/hard_data_manifest.csv',
  hardDataExportManifestJson: 'processed_data/hard_data_exports/library/hard_data_manifest.json',
  hardDataWebManifestJson: 'processed_data/hard_data_exports/hard_data_manifest.web.json',
  publicCsv: 'public/hard-copy/data/library_page_hunts.csv',
  publicJson: 'public/hard-copy/data/library_page_data.json',
  publicSummary: 'public/hard-copy/data/library_page_summary.json',
  publicManifestCsv: 'public/hard-copy/manifests/hard_data_manifest.csv',
  publicManifestJson: 'public/hard-copy/manifests/hard_data_manifest.json',
  buildReport: 'processed_data/audits/library_page_build_report.json',
  missingInputs: 'processed_data/audits/library_page_missing_inputs.csv',
};

function abs(rel) { return path.join(ROOT, rel); }
function exists(rel) { return fs.existsSync(abs(rel)); }
function ensureParent(rel) { fs.mkdirSync(path.dirname(abs(rel)), { recursive: true }); }
function sizeBytes(rel) { return exists(rel) ? fs.statSync(abs(rel)).size : 0; }
function isPagesPublishable(rel) { return exists(rel) && sizeBytes(rel) <= MAX_PAGES_FILE_BYTES; }
function cloudflareHref(rel) { return `${CLOUDFLARE_BASE}/${rel.replace(/\\/g, '/')}`; }
function localHref(rel) { return `./${rel.replace(/\\/g, '/')}`; }
function hrefFor(rel) { return isPagesPublishable(rel) ? localHref(rel) : cloudflareHref(rel); }
function deliveryFor(rel) { return isPagesPublishable(rel) ? 'pages-local' : 'cloudflare-fallback'; }

function normalizeHeader(value) {
  return String(value || '').replace(/^\uFEFF/, '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function parseCsvLine(line) {
  const values = [];
  let field = '';
  let inQuotes = false;
  const src = String(line || '').replace(/^\uFEFF/, '');
  for (let i = 0; i < src.length; i += 1) {
    const c = src[i];
    const n = src[i + 1];
    if (c === '"' && inQuotes && n === '"') { field += '"'; i += 1; }
    else if (c === '"') inQuotes = !inQuotes;
    else if (c === ',' && !inQuotes) { values.push(field); field = ''; }
    else field += c;
  }
  values.push(field);
  return values;
}

function rowFromValues(headers, values, sourceFile) {
  const row = {};
  headers.forEach((header, index) => { row[header] = String(values[index] == null ? '' : values[index]).trim(); });
  row.__source_file = sourceFile;
  return row;
}

async function scanCsv(rel, onRow) {
  if (!exists(rel)) return 0;
  const rl = readline.createInterface({ input: fs.createReadStream(abs(rel), { encoding: 'utf8' }), crlfDelay: Infinity });
  let headers = null;
  let count = 0;
  for await (const line of rl) {
    if (!String(line || '').trim()) continue;
    if (!headers) { headers = parseCsvLine(line).map(normalizeHeader); continue; }
    count += 1;
    await onRow(rowFromValues(headers, parseCsvLine(line), rel), count);
  }
  return count;
}

function writeJson(rel, value) {
  ensureParent(rel);
  fs.writeFileSync(abs(rel), `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function writeCsv(rel, rows) {
  ensureParent(rel);
  if (!rows.length) { fs.writeFileSync(abs(rel), '', 'utf8'); return; }
  const headers = Array.from(rows.reduce((set, row) => { Object.keys(row).forEach((key) => set.add(key)); return set; }, new Set()));
  const esc = (value) => {
    const s = value == null ? '' : String(value);
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  fs.writeFileSync(abs(rel), `${[headers.map(esc).join(',')].concat(rows.map((row) => headers.map((header) => esc(row[header])).join(','))).join('\n')}\n`, 'utf8');
}

function copyIfExists(fromRel, toRel) {
  if (!exists(fromRel)) return false;
  ensureParent(toRel);
  fs.copyFileSync(abs(fromRel), abs(toRel));
  return true;
}

function first(row, candidates) {
  for (const candidate of candidates) {
    const value = row[normalizeHeader(candidate)];
    if (value != null && String(value).trim() !== '') return String(value).trim();
  }
  return '';
}

function huntCode(row) { return first(row, ['hunt_code', 'current_hunt_code', 'current_code', 'current_hunt_number', 'huntcode', 'hunt_number', 'huntnumber', 'hunt no', 'hunt_no', 'hunt', 'code', 'permit_number', 'permit_no', 'hunt id', 'hunt_id']).toUpperCase().replace(/\s+/g, '').replace(/[^A-Z0-9]/g, ''); }
function species(row) { return first(row, ['species', 'hunt_species', 'animal', 'big_game_species', 'category', 'hunt_category', 'hunt_type_species']); }
function huntName(row) { return first(row, ['hunt_name', 'huntname', 'name', 'hunt_title', 'display_name', 'description', 'hunt_description', 'unit_name', 'hunt_unit']); }
function unit(row) { return first(row, ['unit', 'unit_name', 'hunt_unit', 'management_unit', 'area', 'location', 'boundary_name', 'display_unit']); }
function weapon(row) { return first(row, ['weapon', 'weapon_type', 'legal_weapon', 'method', 'season_type']); }
function permits(row) { return first(row, ['permits', 'permit_count', 'permit_count_2026', 'permits_2026', 'total_permits', 'available', 'quota', 'allotment']); }
function classification(row) { return first(row, ['classification', 'hunt_classification', 'draw_type', 'prediction_type', 'model_type', 'category', 'status', 'coverage_status', 'reason', 'reason_code', 'reason_codes', 'exclusion_reason']); }
function probability(row) { return first(row, ['display_odds_pct', 'p_draw_mean', 'p_draw_p50', 'draw_probability', 'odds', 'probability', 'p50']); }
function modelVersion(row) { return first(row, ['model_version', 'model', 'version', 'rule_version']); }

function roleFor(rel) {
  if (rel.endsWith('DATABASE.csv')) return 'current official/canonical 2026 hunt database';
  if (rel.includes('hunt_master_canonical') || rel.includes('hunt-master-canonical')) return 'canonical current hunt source of truth';
  if (rel.includes('hunt_master_enriched')) return 'enriched hunt master';
  if (rel.includes('draw_reality_engine_predictive')) return 'primary prediction output';
  if (rel.includes('draw_reality_engine')) return 'draw reality engine output';
  if (rel.includes('ml_draw_predictions')) return 'ML prediction output';
  if (rel.includes('point_ladder')) return 'point ladder output';
  if (rel.includes('coverage')) return 'coverage/classification report';
  if (rel.includes('crosswalk')) return 'current-to-historical crosswalk';
  if (rel.includes('harvest')) return 'harvest evidence';
  if (rel.includes('research_library_master')) return 'research-page source';
  return 'supporting input';
}
function groupFor(rel) {
  if (rel.includes('library_page')) return 'exports';
  if (rel.includes('manifest')) return 'exports';
  if (rel.includes('DATABASE.csv') || rel.includes('hunt-master-canonical') || rel.includes('hunt_master_canonical')) return 'canonical';
  if (rel.includes('draw_reality') || rel.includes('point_ladder') || rel.includes('prediction')) return 'exports';
  if (rel.includes('coverage') || rel.includes('audit')) return 'pipeline_logs';
  if (rel.includes('crosswalk')) return 'raw_library';
  if (rel.includes('harvest')) return 'raw_library';
  if (rel.includes('research')) return 'raw_library';
  return 'exports';
}
function typeFor(rel) { return path.extname(rel).replace('.', '').toLowerCase() || 'file'; }
function titleFromRel(rel) { return path.basename(rel, path.extname(rel)).replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/\b\w/g, (m) => m.toUpperCase()); }
const PUBLIC_WEB_MANIFEST_ALLOWED_PREFIXES = [
  './processed_data/hard_data_exports/library/',
  './public/hard-copy/',
  './hard-copy/',
];
const PUBLIC_WEB_MANIFEST_ALLOWED_TYPES = new Set(['csv', 'json', 'pdf', 'xlsx']);
const BLOCKED_INTERNAL_PATTERNS = [
  /\bagents\b/i,
  /\bcodex\b/i,
  /\baudit\b/i,
  /\bimplementation\b/i,
  /\binternal\b/i,
  /\bplanning\b/i,
  /\btask\b/i,
  /\.md($|[?#])/i,
  /\.txt($|[?#])/i,
];
function decodeSafe(value) {
  try {
    return decodeURIComponent(String(value || ''));
  } catch {
    return String(value || '');
  }
}
function isBlockedInternalToken(value) {
  return BLOCKED_INTERNAL_PATTERNS.some((pattern) => pattern.test(decodeSafe(value)));
}
function isPublicWebManifestItemAllowed(item) {
  const href = String(item?.href || '').trim();
  const type = String(item?.type || '').trim().toLowerCase();
  const title = String(item?.title || '').trim();
  const subtitle = String(item?.subtitle || '').trim();
  if (!href || !type) return false;
  if (!PUBLIC_WEB_MANIFEST_ALLOWED_TYPES.has(type)) return false;
  if (!PUBLIC_WEB_MANIFEST_ALLOWED_PREFIXES.some((prefix) => href.startsWith(prefix))) return false;
  return !isBlockedInternalToken(`${href} ${title} ${subtitle}`);
}
function manifestItem(rel, subtitle, options = {}) {
  return {
    group: options.group || groupFor(rel),
    type: options.type || typeFor(rel),
    year: options.year || '2026',
    title: options.title || titleFromRel(rel),
    subtitle,
    href: options.href || hrefFor(rel),
    local_href: localHref(rel),
    cloudflare_href: cloudflareHref(rel),
    delivery: deliveryFor(rel),
    size_mb: exists(rel) ? Number((sizeBytes(rel) / (1024 * 1024)).toFixed(2)) : 0,
    source: options.source || (rel.startsWith('processed_data/') ? 'processed_data' : 'pipeline'),
    scope: options.scope || 'runtime',
  };
}

function pickCurrentSource() { return [INPUTS.currentDatabase, INPUTS.currentCanonicalProcessed, INPUTS.currentCanonicalRaw, INPUTS.huntDatabaseComplete, INPUTS.huntMasterEnriched].find((rel) => exists(rel)) || null; }
function inputStatus(name, rel) { return { name, source_file: rel, role: roleFor(rel), exists: exists(rel) ? 'true' : 'false', row_count: exists(rel) ? 'not_scanned' : 0, size_bytes: sizeBytes(rel), size_mb: Number((sizeBytes(rel) / (1024 * 1024)).toFixed(2)), delivery: deliveryFor(rel), href: hrefFor(rel), local_href: localHref(rel), cloudflare_href: cloudflareHref(rel) }; }
function classifyState({ hasPrediction, hasCoverage, classText }) {
  const upper = String(classText || '').toUpperCase();
  const nonPredictiveTerms = ['HARVEST_OBJECTIVE', 'UNLIMITED', 'PRIVATE_LANDS', 'SPORTSMAN', 'CONSERVATION', 'EXPO', 'AVAILABILITY', 'ALLOCATION', 'NONPREDICTIVE', 'NON_PREDICTIVE', 'OUT_OF_SCOPE', 'NOT_OIL_LE_PLE'];
  if (hasPrediction) return 'PREDICTION_ELIGIBLE_AND_MODELED';
  if (nonPredictiveTerms.some((term) => upper.includes(term))) return 'EXCLUDED_WITH_DOCUMENTED_NON_PREDICTIVE_REASON';
  if (hasCoverage) return 'CLASSIFIED_NEEDS_MODEL_OR_EXCLUSION_REVIEW';
  return 'MANUAL_REVIEW_REQUIRED';
}
function mergeFirst(existing, row, sourceName) {
  if (!existing) return { ...row, __source_file: row.__source_file || sourceName };
  const merged = { ...existing };
  for (const [key, value] of Object.entries(row)) if ((merged[key] == null || String(merged[key]).trim() === '') && value != null && String(value).trim() !== '') merged[key] = value;
  return merged;
}
async function buildFirstRowMap(files, currentCodes) {
  const map = new Map();
  const rowCounts = {};
  for (const rel of files) {
    let count = 0;
    await scanCsv(rel, (row) => { count += 1; const code = huntCode(row); if (!code || !currentCodes.has(code)) return; map.set(code, mergeFirst(map.get(code), row, rel)); });
    rowCounts[rel] = count;
    console.log(`Scanned ${rel}: ${count} rows, matched ${map.size} current codes total`);
  }
  return { map, rowCounts };
}
function countBy(rows, key) { return rows.reduce((counts, row) => { const value = String(row[key] || 'UNKNOWN').trim() || 'UNKNOWN'; counts[value] = (counts[value] || 0) + 1; return counts; }, {}); }

async function main() {
  Object.values(OUTPUTS).forEach((rel) => ensureParent(rel));
  const inputs = Object.entries(INPUTS).map(([name, rel]) => inputStatus(name, rel));
  writeCsv(OUTPUTS.missingInputs, inputs.filter((input) => input.exists !== 'true'));

  const currentSource = pickCurrentSource();
  if (!currentSource) throw new Error('No current 2026 hunt database source found.');
  copyIfExists(currentSource, OUTPUTS.canonicalCurrent);

  const currentRows = [];
  const currentCodes = new Set();
  await scanCsv(currentSource, (row) => { const code = huntCode(row); if (!code) return; currentRows.push(row); currentCodes.add(code); });
  console.log(`Current source used: ${currentSource}`);
  console.log(`Current hunt rows loaded: ${currentRows.length}`);

  const enriched = await buildFirstRowMap([INPUTS.huntMasterEnriched], currentCodes);
  const reference = await buildFirstRowMap([INPUTS.huntUnitReferenceLinked], currentCodes);
  const predictive = await buildFirstRowMap([INPUTS.drawRealityEnginePredictive], currentCodes);
  const reality = await buildFirstRowMap([INPUTS.drawRealityEngine, INPUTS.drawRealityEngineV2], currentCodes);
  const ml = await buildFirstRowMap([INPUTS.mlDrawPredictions], currentCodes);
  const point = await buildFirstRowMap([INPUTS.pointLadderView], currentCodes);
  const coverage = await buildFirstRowMap([INPUTS.coverageReport, INPUTS.predictiveCoverageReport], currentCodes);
  const crosswalk = await buildFirstRowMap([INPUTS.crosswalk], currentCodes);
  const harvest = await buildFirstRowMap([INPUTS.harvestMaster, INPUTS.harvestQualityAllYears, INPUTS.harvestQuality2026], currentCodes);

  const pageRows = currentRows.map((cur) => {
    const code = huntCode(cur);
    const enr = enriched.map.get(code) || {};
    const ref = reference.map.get(code) || {};
    const pred = predictive.map.get(code) || {};
    const real = reality.map.get(code) || {};
    const mlRow = ml.map.get(code) || {};
    const pointRow = point.map.get(code) || {};
    const cov = coverage.map.get(code) || {};
    const realClass = classification(real);
    const hasReferenceOnlyReality = String(realClass || '').toUpperCase().includes('DATABASE_REFERENCE_ONLY_NO_DRAW_DETAIL');
    const hasPrediction = predictive.map.has(code) || ml.map.has(code) || (reality.map.has(code) && !hasReferenceOnlyReality);
    const hasCoverage = coverage.map.has(code);
    const classText = classification(cov) || classification(enr) || classification(pred) || classification(real) || '';
    const finalState = classifyState({ hasPrediction, hasCoverage, classText });
    const gateStatus = finalState === 'PREDICTION_ELIGIBLE_AND_MODELED' || finalState === 'EXCLUDED_WITH_DOCUMENTED_NON_PREDICTIVE_REASON' ? 'PASS' : 'BLOCK';
    return {
      hunt_code: code,
      species: species(cur) || species(enr) || species(ref),
      hunt_name: huntName(cur) || huntName(enr) || huntName(ref),
      unit: unit(cur) || unit(enr) || unit(ref),
      weapon: weapon(cur) || weapon(enr) || weapon(ref),
      permits_2026: permits(cur) || permits(enr) || permits(ref),
      classification: classText,
      modeled: hasPrediction ? 'true' : 'false',
      has_prediction: hasPrediction ? 'true' : 'false',
      has_point_ladder: point.map.has(code) ? 'true' : 'false',
      has_crosswalk: crosswalk.map.has(code) ? 'true' : 'false',
      has_harvest_evidence: harvest.map.has(code) ? 'true' : 'false',
      has_coverage_record: hasCoverage ? 'true' : 'false',
      display_odds_or_probability: probability(pred) || probability(real) || probability(mlRow) || probability(pointRow),
      model_version: modelVersion(pred) || modelVersion(real) || modelVersion(mlRow),
      final_state: finalState,
      gate_status: gateStatus,
      manual_review_required: gateStatus === 'BLOCK' ? 'true' : 'false',
      source_current_database: currentSource,
      source_prediction: hasPrediction ? INPUTS.drawRealityEnginePredictive : '',
      source_crosswalk: crosswalk.map.has(code) ? INPUTS.crosswalk : '',
      source_coverage: hasCoverage ? INPUTS.coverageReport : '',
    };
  });

  const scannedRowCounts = { ...enriched.rowCounts, ...reference.rowCounts, ...predictive.rowCounts, ...reality.rowCounts, ...ml.rowCounts, ...point.rowCounts, ...coverage.rowCounts, ...crosswalk.rowCounts, ...harvest.rowCounts };
  const summary = {
    generated_at: new Date().toISOString(),
    current_source_used: currentSource,
    cloudflare_fallback_base: CLOUDFLARE_BASE,
    pages_file_limit_mb: Number((MAX_PAGES_FILE_BYTES / (1024 * 1024)).toFixed(1)),
    counts: {
      total_current_hunts: pageRows.length,
      modeled_count: pageRows.filter((row) => row.has_prediction === 'true').length,
      excluded_non_predictive_count: pageRows.filter((row) => row.final_state === 'EXCLUDED_WITH_DOCUMENTED_NON_PREDICTIVE_REASON').length,
      manual_review_count: pageRows.filter((row) => row.manual_review_required === 'true').length,
      promotion_gate_pass_count: pageRows.filter((row) => row.gate_status === 'PASS').length,
      promotion_gate_block_count: pageRows.filter((row) => row.gate_status === 'BLOCK').length,
      cloudflare_fallback_file_count: inputs.filter((item) => item.delivery === 'cloudflare-fallback').length,
    },
    species_counts: countBy(pageRows, 'species'),
    classification_counts: countBy(pageRows, 'classification'),
    final_state_counts: countBy(pageRows, 'final_state'),
    gate_status_counts: countBy(pageRows, 'gate_status'),
    input_file_status: inputs,
    scanned_row_counts: scannedRowCounts,
    recommendation: pageRows.some((row) => row.gate_status === 'BLOCK') ? 'REVIEW: hard-data library page package built, but blocked rows remain.' : 'PASS: hard-data library page package built with no blocked current hunt rows.',
  };

  const manifestRows = inputs.map((input) => ({ ...input, used_as_current_source: input.source_file === currentSource ? 'true' : 'false' }));
  writeCsv(OUTPUTS.libraryCsv, pageRows); writeJson(OUTPUTS.libraryJson, pageRows); writeJson(OUTPUTS.librarySummary, summary);
  writeCsv(OUTPUTS.libraryManifestCsv, manifestRows); writeJson(OUTPUTS.libraryManifestJson, summary);
  writeCsv(OUTPUTS.productionCsv, pageRows); writeJson(OUTPUTS.productionJson, pageRows); writeJson(OUTPUTS.productionSummary, summary);
  writeCsv(OUTPUTS.hardDataExportCsv, pageRows); writeJson(OUTPUTS.hardDataExportJson, pageRows); writeJson(OUTPUTS.hardDataExportSummary, summary);
  writeCsv(OUTPUTS.hardDataExportManifestCsv, manifestRows); writeJson(OUTPUTS.hardDataExportManifestJson, summary);
  writeCsv(OUTPUTS.publicCsv, pageRows); writeJson(OUTPUTS.publicJson, pageRows); writeJson(OUTPUTS.publicSummary, summary);
  writeCsv(OUTPUTS.publicManifestCsv, manifestRows); writeJson(OUTPUTS.publicManifestJson, summary);

  const webManifest = [
    manifestItem(OUTPUTS.hardDataExportCsv, 'Page-ready hard-data hunt library records as CSV.', { group: 'exports', title: 'Hard Data Library Page Records CSV' }),
    manifestItem(OUTPUTS.hardDataExportJson, 'Page-ready hard-data hunt library records as JSON.', { group: 'exports', title: 'Hard Data Library Page Records JSON' }),
    manifestItem(OUTPUTS.hardDataExportSummary, 'Build summary for modeled, excluded, manual-review, and gate status counts.', { group: 'exports', title: 'Hard Data Library Page Summary' }),
  ];
  for (const input of inputs.filter((item) => item.exists === 'true' && item.source_file.startsWith('processed_data/'))) {
    webManifest.push(
      manifestItem(input.source_file, `${input.role}; size ${input.size_mb || 0} MB.`, {
        group: groupFor(input.source_file),
        title: titleFromRel(input.source_file),
        scope: input.role.includes('coverage') || input.role.includes('crosswalk') ? 'audit' : 'runtime',
      })
    );
  }
  const safeWebManifest = Array.from(new Map(webManifest.map((item) => [item.href, item])).values())
    .filter(isPublicWebManifestItemAllowed);
  writeJson(OUTPUTS.hardDataWebManifestJson, safeWebManifest);
  writeJson(OUTPUTS.buildReport, summary);

  console.log('\nHard-data library page build complete');
  console.log('====================================');
  console.log(`Current source used: ${currentSource}`);
  console.log(`Total current hunts: ${summary.counts.total_current_hunts}`);
  console.log(`Modeled:             ${summary.counts.modeled_count}`);
  console.log(`Manual review:       ${summary.counts.manual_review_count}`);
  console.log(`Cloudflare fallbacks:${summary.counts.cloudflare_fallback_file_count}`);
  console.log(`Gate PASS:           ${summary.counts.promotion_gate_pass_count}`);
  console.log(`Gate BLOCK:          ${summary.counts.promotion_gate_block_count}`);
  console.log('\nPrimary outputs:');
  console.log(`- ${OUTPUTS.libraryCsv}`);
  console.log(`- ${OUTPUTS.librarySummary}`);
  console.log(`- ${OUTPUTS.hardDataExportJson}`);
  console.log(`- ${OUTPUTS.hardDataWebManifestJson}`);
  console.log(`\n${summary.recommendation}`);
}

main().catch((error) => { console.error('Failed to build hard-data library page package.'); console.error(error); process.exit(1); });
