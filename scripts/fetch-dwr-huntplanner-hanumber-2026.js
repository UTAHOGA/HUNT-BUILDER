#!/usr/bin/env node
/*
  Pulls the same public DWR Hunt Planner JSON used by the click-popup panels.
  This is a source extract only: it does not modify DATABASE.csv or prediction outputs.
*/
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DATABASE_CSV = path.join(ROOT, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'csv', 'DATABASE.csv');
const OUTPUT_DIR_ARG_INDEX = process.argv.indexOf('--output-dir');
const HUNT_TABLE_DIR_ARG_INDEX = process.argv.indexOf('--hunt-table-dir');
const outputDirArg = OUTPUT_DIR_ARG_INDEX >= 0 ? process.argv[OUTPUT_DIR_ARG_INDEX + 1] : '';
const huntTableDirArg = HUNT_TABLE_DIR_ARG_INDEX >= 0 ? process.argv[HUNT_TABLE_DIR_ARG_INDEX + 1] : '';
const OUTPUT_DIR = outputDirArg ? path.resolve(ROOT, outputDirArg) : path.join(ROOT, 'processed_data');
const HUNT_TABLE_DIR = huntTableDirArg ? path.resolve(ROOT, huntTableDirArg) : '';
const OUT_CSV = path.join(OUTPUT_DIR, 'dwr_huntplanner_hanumber_2026.csv');
const OUT_JSON = path.join(OUTPUT_DIR, 'dwr_huntplanner_hanumber_2026.json');
const OUT_RAW_JSON = path.join(OUTPUT_DIR, 'dwr_huntplanner_hanumber_2026_raw_payloads.json');
const AUDIT_JSON = path.join(OUTPUT_DIR, 'dwr_huntplanner_hanumber_2026_audit.json');
const AUDIT_CSV = path.join(OUTPUT_DIR, 'dwr_huntplanner_hanumber_2026_audit.csv');
const BASE_URL = 'https://dwrapps.utah.gov/huntboundary/HaNumber?roles=&hn=';
const CONCURRENCY = Number(process.env.HUNTPLANNER_CONCURRENCY || 8);
const TIMEOUT_MS = Number(process.env.HUNTPLANNER_TIMEOUT_MS || 20000);

const OUTPUT_COLUMNS = [
  'hunt_code',
  'source_url',
  'fetch_status',
  'http_status',
  'error_message',
  'database_code_present',
  'database_hunt_name',
  'database_species',
  'database_sex_type',
  'database_weapon',
  'database_hunt_type',
  'database_boundary_id',
  'dwr_hunt_name',
  'dwr_print_hunt_name',
  'dwr_species',
  'dwr_sex_type',
  'dwr_weapon',
  'dwr_hunt_type',
  'dwr_season_type',
  'dwr_draw_designation',
  'dwr_waiting_period_years',
  'dwr_special_provisions_text',
  'dwr_notes_text',
  'dwr_harvest_reporting_text',
  'hunt_year',
  'duplicate_until_date',
  'otc_sales_begin_date',
  'otc_sales_end_date',
  'permit_qty',
  'season_date_text',
  'permits_2026_res',
  'permits_2026_nr',
  'permits_2026_total',
  'permits_2026_res_youth',
  'permits_2026_nr_youth',
  'permits_sold_draw_total',
  'permits_sold_draw_res',
  'permits_sold_draw_nr',
  'permits_sold_otc_total',
  'permits_sold_otc_res',
  'permits_sold_otc_nr',
  'harvest_survey_due',
  'harvest_penalty_date',
  'surrender_info_text',
  'security_level',
  'display_non_approved',
  'boundaries',
  'boundary_count',
  'management_stats_available',
  'percent_harvest_success_previous_hunting_season',
  'population_objective',
  'current_population_estimate',
  'bucks_per_100_does_objective',
  'current_bucks_per_100_does_3yr_average',
  'age_objective',
  'current_age_3yr_average',
  'bulls_per_100_cows_objective',
  'bulls_per_100_cows_estimate',
  'total_hunters_previous_hunting_season',
  'draw_odds_report_note',
  'big_game_annual_report_note',
  'management_obj_raw',
  'management_obj_labels_json',
  'management_obj_pairs_json',
  'hunt_bio_general_information',
  'hunt_bio_biologist_notes',
  'hunt_bio_safety_considerations',
  'hunt_bio_weather_considerations',
  'source_access_method',
  'source_retrieved_at',
  'review_status',
  'review_reason'
];

function normalizeCode(value) {
  return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function stripHtml(value) {
  return String(value || '')
    .replace(/[\u2013\u2014\u2212]/g, '-')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let inQuotes = false;
  const src = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    const next = src[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i++;
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
      row.push(cell.replace(/\r$/, ''));
      rows.push(row);
      row = [];
      cell = '';
    } else {
      cell += ch;
    }
  }
  if (cell.length || row.length) {
    row.push(cell.replace(/\r$/, ''));
    rows.push(row);
  }
  if (!rows.length) return [];
  const headers = rows[0];
  return rows.slice(1).filter(r => r.some(v => String(v || '').trim())).map(r => {
    const out = {};
    headers.forEach((h, i) => { out[h] = r[i] || ''; });
    return out;
  });
}

function loadCurrentHuntTableCodes(directory) {
  if (!directory) return [];
  if (!fs.existsSync(directory)) throw new Error(`Missing Hunt Planner table directory: ${directory}`);
  const codes = new Set();
  for (const name of fs.readdirSync(directory).sort()) {
    if (!/^dwr_huntboundary_.+\.json$/i.test(name) || /hasetup/i.test(name)) continue;
    const filePath = path.join(directory, name);
    const payload = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (!Array.isArray(payload)) continue;
    for (const row of payload) {
      const code = normalizeCode(row && (row.HUNT_NBR || row.hunt_code || row.huntCode));
      if (code) codes.add(code);
    }
  }
  return [...codes].sort();
}

function csvEscape(value) {
  const s = value == null ? '' : String(value);
  if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function writeCsv(filePath, rows, columns) {
  const lines = [columns.map(csvEscape).join(',')];
  for (const row of rows) {
    lines.push(columns.map(col => csvEscape(row[col])).join(','));
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, lines.join('\n') + '\n', 'utf8');
}

function first(obj, keys) {
  for (const key of keys) {
    const value = obj && obj[key];
    if (value !== undefined && value !== null && String(value).trim() !== '') return value;
  }
  return '';
}

function numericText(value) {
  const s = stripHtml(value);
  if (!s) return '';
  return s;
}

function managementLabelMap(displayNames) {
  const labels = {};
  for (const item of displayNames || []) {
    if (item.TABLE_NAME === 'HUNT_BIO' && /^MANAGEMENT_OBJ\d+$/.test(item.FIELD_NAME || '')) {
      labels[item.FIELD_NAME] = stripHtml(item.DISPLAY_TEXT || '');
    }
  }
  return labels;
}

function assignManagementField(row, label, value) {
  const l = String(label || '').toLowerCase().replace(/\s+/g, ' ').trim();
  const v = numericText(value);
  if (!v) return;
  if (l.includes('percent harvest success')) row.percent_harvest_success_previous_hunting_season = v;
  else if (l === 'population objective') row.population_objective = v;
  else if (l.includes('current population estimate')) row.current_population_estimate = v;
  else if (l.includes('bucks per 100 does objective')) row.bucks_per_100_does_objective = v;
  else if (l.includes('current bucks per 100 does')) row.current_bucks_per_100_does_3yr_average = v;
  else if (l === 'age objective') row.age_objective = v;
  else if (l.includes('current age')) row.current_age_3yr_average = v;
  else if (l.includes('bulls per 100 cows objective')) row.bulls_per_100_cows_objective = v;
  else if (l.includes('bulls per 100 cows estimate')) row.bulls_per_100_cows_estimate = v;
  else if (l.includes('total hunters')) row.total_hunters_previous_hunting_season = v;
  else if (l.includes('drawing odds report')) row.draw_odds_report_note = v;
  else if (l.includes('big game annual report')) row.big_game_annual_report_note = v;
}

async function fetchJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      headers: {
        'accept': 'application/json,text/plain,*/*',
        'user-agent': 'HUNT-BUILDER data audit (contact: local owner)'
      },
      signal: controller.signal
    });
    const text = await response.text();
    if (!response.ok) {
      return { ok: false, status: response.status, error: text.slice(0, 500), data: null };
    }
    return { ok: true, status: response.status, error: '', data: JSON.parse(text) };
  } catch (err) {
    return { ok: false, status: '', error: err && err.message ? err.message : String(err), data: null };
  } finally {
    clearTimeout(timer);
  }
}

function flattenRecord(code, dbRow, result, retrievedAt) {
  const sourceUrl = BASE_URL + encodeURIComponent(code);
  const base = Object.fromEntries(OUTPUT_COLUMNS.map(col => [col, '']));
  Object.assign(base, {
    hunt_code: code,
    source_url: sourceUrl,
    database_code_present: dbRow ? 'true' : 'false',
    database_hunt_name: first(dbRow, ['hunt_name', 'HUNT_NAME']),
    database_species: first(dbRow, ['species', 'SPECIES']),
    database_sex_type: first(dbRow, ['sex_type', 'GENDER']),
    database_weapon: first(dbRow, ['weapon', 'WEAPON']),
    database_hunt_type: first(dbRow, ['hunt_type', 'HUNT_TYPE']),
    database_boundary_id: first(dbRow, ['boundary_id', 'HUNT_AREA_ID']),
    source_access_method: 'DWR_HUNT_PLANNER_HaNumber_JSON',
    source_retrieved_at: retrievedAt
  });
  if (!result.ok || !result.data) {
    base.fetch_status = 'ERROR';
    base.http_status = result.status;
    base.error_message = result.error;
    base.review_status = 'REVIEW';
    base.review_reason = 'DWR_HANUMBER_FETCH_FAILED';
    return base;
  }
  const data = result.data;
  const master = data.huntMaster || {};
  const year = Array.isArray(data.huntYears) && data.huntYears.length ? data.huntYears[0] : {};
  const bio = Array.isArray(data.huntBios) && data.huntBios.length ? data.huntBios[0] : {};
  const labels = managementLabelMap(data.huntDisplayNames || []);
  const rawManagement = bio.MANAGEMENT_OBJ || '';
  const statValues = rawManagement ? String(rawManagement).split('~') : [];
  const managementPairs = {};
  for (let i = 0; i < statValues.length; i++) {
    const label = labels[`MANAGEMENT_OBJ${i}`] || `MANAGEMENT_OBJ${i}`;
    managementPairs[label] = numericText(statValues[i] || '');
  }

  Object.assign(base, {
    fetch_status: 'OK',
    http_status: result.status,
    dwr_hunt_name: stripHtml(master.HUNT_NAME || ''),
    dwr_print_hunt_name: stripHtml(master.PRINT_HUNT_NAME || ''),
    dwr_species: stripHtml(master.SPECIES || ''),
    dwr_sex_type: stripHtml(master.GENDER || ''),
    dwr_weapon: stripHtml(master.WEAPON || ''),
    dwr_hunt_type: stripHtml(master.HUNT_TYPE || ''),
    dwr_season_type: stripHtml(master.SEASON_TYPE || ''),
    dwr_draw_designation: stripHtml(master.DRAW_DESIGNATION || ''),
    dwr_waiting_period_years: master.WAITING_PERIOD_YEARS ?? '',
    dwr_special_provisions_text: stripHtml(master.SPECIAL_PROVISIONS || ''),
    dwr_notes_text: stripHtml(master.NOTES || ''),
    dwr_harvest_reporting_text: stripHtml(master.HARVEST_REPORTING || ''),
    hunt_year: year.HUNT_YEAR || '',
    duplicate_until_date: stripHtml(year.DUPLICATE_UNTIL_DATE || ''),
    otc_sales_begin_date: stripHtml(year.OTC_SALES_BEGIN_DATE || ''),
    otc_sales_end_date: stripHtml(year.OTC_SALES_END_DATE || ''),
    permit_qty: year.PERMIT_QTY ?? '',
    season_date_text: stripHtml(year.SEASON_DATE_TEXT || ''),
    permits_2026_res: year.QUOTA_RES ?? '',
    permits_2026_nr: year.QUOTA_NRES ?? '',
    permits_2026_total: year.QUOTA ?? '',
    permits_2026_res_youth: year.QUOTA_RES_YOUTH ?? '',
    permits_2026_nr_youth: year.QUOTA_NRES_YOUTH ?? '',
    permits_sold_draw_total: year.QUOTA_SOLD_DRAW ?? '',
    permits_sold_draw_res: year.QUOTA_RES_SOLD_DRAW ?? '',
    permits_sold_draw_nr: year.QUOTA_NRES_SOLD_DRAW ?? '',
    permits_sold_otc_total: year.QUOTA_OTC ?? '',
    permits_sold_otc_res: year.QUOTA_RES_OTC ?? '',
    permits_sold_otc_nr: year.QUOTA_NRES_OTC ?? '',
    harvest_survey_due: stripHtml(year.HARV_SURV_DUE || ''),
    harvest_penalty_date: stripHtml(year.HARV_PENALTY_DATE || ''),
    surrender_info_text: stripHtml(year.SURRENDER_INFO || ''),
    security_level: data.SecurityLevel ?? '',
    display_non_approved: data.displayNonApproved ?? '',
    boundaries: Array.isArray(data.boundaries) ? data.boundaries.join('|') : '',
    boundary_count: Array.isArray(data.boundaries) ? data.boundaries.length : '',
    hunt_boundary_infos_json: JSON.stringify(data.huntBoundaryInfos || []),
    management_stats_available: rawManagement && statValues.some(v => stripHtml(v)) ? 'true' : 'false',
    management_obj_raw: stripHtml(rawManagement),
    management_obj_labels_json: JSON.stringify(labels),
    management_obj_pairs_json: JSON.stringify(managementPairs),
    hunt_bio_general_information: stripHtml(bio.GENERAL_INFORMATION || ''),
    hunt_bio_biologist_notes: stripHtml(bio.BIOLOGIST_NOTES || ''),
    hunt_bio_safety_considerations: stripHtml(bio.SAFETY_CONS || ''),
    hunt_bio_weather_considerations: stripHtml(bio.WEATHER_CONS || '')
  });

  for (let i = 0; i < statValues.length; i++) {
    assignManagementField(base, labels[`MANAGEMENT_OBJ${i}`] || `MANAGEMENT_OBJ${i}`, statValues[i]);
  }

  const hasCore = Boolean(master.HUNT_NBR || year.HUNT_NBR);
  base.review_status = hasCore ? 'PASS' : 'REVIEW';
  const reasons = [];
  if (!hasCore) reasons.push('NO_HUNT_MASTER_OR_YEAR_RECORD');
  if (base.database_code_present !== 'true') reasons.push('NOT_IN_DATABASE_CSV');
  if (base.management_stats_available !== 'true') reasons.push('NO_MANAGEMENT_STATS_IN_POPUP');
  if (base.current_age_3yr_average && !base.age_objective) reasons.push('CURRENT_AGE_WITHOUT_AGE_OBJECTIVE_REVIEW');
  base.review_reason = reasons.join('|') || 'OK';
  return base;
}

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const index = next++;
      out[index] = await fn(items[index], index);
      if ((index + 1) % 100 === 0) console.log(`Fetched ${index + 1}/${items.length}`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return out;
}

function countBy(rows, key) {
  const counts = {};
  for (const row of rows) {
    const value = row[key] || '(blank)';
    counts[value] = (counts[value] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
}

async function main() {
  if (!fs.existsSync(DATABASE_CSV)) throw new Error(`Missing DATABASE.csv: ${DATABASE_CSV}`);
  const dbRows = parseCsv(fs.readFileSync(DATABASE_CSV, 'utf8'));
  const dbByCode = new Map();
  for (const row of dbRows) {
    const code = normalizeCode(row.hunt_code || row.HUNT_NBR);
    if (code) dbByCode.set(code, row);
  }
  const codes = HUNT_TABLE_DIR ? loadCurrentHuntTableCodes(HUNT_TABLE_DIR) : [...dbByCode.keys()].sort();
  if (!codes.length) throw new Error('No Hunt Planner popup codes were found.');
  const retrievedAt = new Date().toISOString();
  const inputLabel = HUNT_TABLE_DIR ? `official HuntTableData matrix ${HUNT_TABLE_DIR}` : 'DATABASE.csv code list';
  console.log(`Fetching ${codes.length} DWR Hunt Planner popup records from ${inputLabel} with concurrency=${CONCURRENCY}`);
  const pulled = await mapLimit(codes, CONCURRENCY, async (code) => {
    const url = BASE_URL + encodeURIComponent(code);
    const result = await fetchJson(url);
    return {
      record: flattenRecord(code, dbByCode.get(code), result, retrievedAt),
      raw: result.ok && result.data ? result.data : null
    };
  });
  const rows = pulled.map(item => item.record);
  const rawPayloads = pulled
    .filter(item => item.raw)
    .map(item => ({
      hunt_code: item.record.hunt_code,
      source_url: item.record.source_url,
      source_retrieved_at: item.record.source_retrieved_at,
      payload: item.raw
    }));

  rows.sort((a, b) => String(a.hunt_code).localeCompare(String(b.hunt_code)));
  fs.mkdirSync(path.dirname(OUT_CSV), { recursive: true });
  fs.mkdirSync(path.dirname(AUDIT_JSON), { recursive: true });
  writeCsv(OUT_CSV, rows, OUTPUT_COLUMNS);
  fs.writeFileSync(OUT_JSON, JSON.stringify(rows, null, 2) + '\n', 'utf8');
  fs.writeFileSync(OUT_RAW_JSON, JSON.stringify(rawPayloads, null, 2) + '\n', 'utf8');

  const audit = {
    created_at: new Date().toISOString(),
    source: 'https://dwrapps.utah.gov/huntboundary/HaNumber?hn={hunt_code}&roles=',
    input_database_csv: path.relative(ROOT, DATABASE_CSV).replace(/\\/g, '/'),
    hunt_code_source: HUNT_TABLE_DIR ? 'OFFICIAL_DWR_HUNTTABLEDATA_MATRIX' : 'DATABASE_CSV_LEGACY_DEFAULT',
    hunt_table_dir: HUNT_TABLE_DIR ? path.relative(ROOT, HUNT_TABLE_DIR).replace(/\\/g, '/') : '',
    current_hunt_codes_requested: codes.length,
    current_hunt_codes_from_database: dbByCode.size,
    rows_written: rows.length,
    fetch_ok: rows.filter(r => r.fetch_status === 'OK').length,
    fetch_error: rows.filter(r => r.fetch_status !== 'OK').length,
    pass_rows: rows.filter(r => r.review_status === 'PASS').length,
    review_rows: rows.filter(r => r.review_status === 'REVIEW').length,
    rows_with_management_stats: rows.filter(r => r.management_stats_available === 'true').length,
    rows_with_percent_harvest_success: rows.filter(r => r.percent_harvest_success_previous_hunting_season).length,
    rows_with_current_age_3yr_average: rows.filter(r => r.current_age_3yr_average).length,
    rows_with_age_objective: rows.filter(r => r.age_objective).length,
    rows_with_population_objective: rows.filter(r => r.population_objective).length,
    rows_with_current_population_estimate: rows.filter(r => r.current_population_estimate).length,
    rows_with_waiting_period_years: rows.filter(r => String(r.dwr_waiting_period_years).trim() !== '').length,
    rows_with_special_provisions: rows.filter(r => r.dwr_special_provisions_text).length,
    rows_with_notes: rows.filter(r => r.dwr_notes_text).length,
    rows_with_harvest_reporting_text: rows.filter(r => r.dwr_harvest_reporting_text).length,
    rows_with_surrender_info: rows.filter(r => r.surrender_info_text).length,
    rows_with_draw_odds_note: rows.filter(r => r.draw_odds_report_note).length,
    rows_with_permit_total: rows.filter(r => r.permits_2026_total !== undefined && r.permits_2026_total !== null && String(r.permits_2026_total) !== '').length,
    species_counts: countBy(rows, 'dwr_species'),
    review_reason_counts: countBy(rows.map(r => ({ reason: r.review_reason || 'OK' })), 'reason'),
    eb3038_sample: rows.find(r => r.hunt_code === 'EB3038') || null,
    outputs: {
      csv: path.relative(ROOT, OUT_CSV).replace(/\\/g, '/'),
      json: path.relative(ROOT, OUT_JSON).replace(/\\/g, '/'),
      raw_payloads_json: path.relative(ROOT, OUT_RAW_JSON).replace(/\\/g, '/'),
      audit_json: path.relative(ROOT, AUDIT_JSON).replace(/\\/g, '/'),
      audit_csv: path.relative(ROOT, AUDIT_CSV).replace(/\\/g, '/')
    },
    notes: [
      'current_age_3yr_average is DWR Hunt Planner current age context, not prior-year average harvest age.',
      'When --hunt-table-dir is used, the popup code universe comes from official current HuntTableData, not DATABASE.csv.',
      'This extract is source evidence only and does not modify DATABASE.csv or prediction outputs.'
    ]
  };
  fs.writeFileSync(AUDIT_JSON, JSON.stringify(audit, null, 2) + '\n', 'utf8');
  const auditRows = Object.entries(audit).filter(([, v]) => typeof v !== 'object').map(([metric, value]) => ({ metric, value }));
  writeCsv(AUDIT_CSV, auditRows, ['metric', 'value']);

  console.log('Done.');
  console.log(`Rows written: ${rows.length}`);
  console.log(`Fetch OK: ${audit.fetch_ok}; errors: ${audit.fetch_error}`);
  console.log(`Management stats: ${audit.rows_with_management_stats}`);
  console.log(`Percent harvest success: ${audit.rows_with_percent_harvest_success}`);
  console.log(`Current age 3yr average: ${audit.rows_with_current_age_3yr_average}`);
  console.log(`Outputs:\n- ${OUT_CSV}\n- ${OUT_JSON}\n- ${OUT_RAW_JSON}\n- ${AUDIT_JSON}\n- ${AUDIT_CSV}`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
