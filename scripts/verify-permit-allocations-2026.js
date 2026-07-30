const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const SOURCE_FILE = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';
const SOURCE_LABEL = 'DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS';
const LAST_SYNC_FILE = 'processed_data/permit_allocation_2026_last_sync.json';

const ALLOCATION_FIELDS = [
  'permits_2026_res',
  'permits_2026_nr',
  'permits_2026_total',
  'permits_2026_conservation',
  'permits_2026_expo',
  'permits_2026_sportsman',
  'permit_status',
  'permit_allocation_type',
  'special_permit_area_id',
  'special_permit_category',
  'special_permit_note',
  'special_permit_overlay_source',
  'permit_source_authority',
  'permit_note',
  'permit_overlay_source',
  'data_status',
];

const PROVENANCE_FIELDS = ['permits_2026_source'];

const FORBIDDEN_FIELDS = [
  'permits_2025_draw_res',
  'permits_2025_draw_nr',
  'permits_2025_draw_total',
  'permits_2025_res',
  'permits_2025_nr',
  'permits_2025_total',
  'hunters_2025',
  'harvest_2025',
  'success_percent_2025',
  'avg_days_2025',
  'satisfaction_2025',
];

const CSV_TARGETS = [
  'processed_data/hunt_master_enriched.csv',
  'processed_data/hunt_unit_reference_linked.csv',
  'processed_data/draw_reality_engine.csv',
  'processed_data/point_ladder_view.csv',
];

const JSON_ROW_TARGETS = [
  'data/hunt-master-canonical-2026-database-candidate.json',
  'data/hunt-master-canonical-2026-foundation.json',
  'data/hunt-master-canonical-2026-source-of-truth.json',
  'processed_data/hunt-master-canonical-2026-source-of-truth.json',
  'canonical/hunt-planner-2026.json',
  'generated/pages/hunt-planner.json',
];

const JSON_METADATA_TARGETS = [
  'generated/pages/hunt-research.json',
];

function abs(file) {
  return path.join(REPO, file);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      quoted = true;
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
  if (!rows.length) return { headers: [], records: [] };
  const headers = rows.shift().map((header) => String(header || '').trim().replace(/^\uFEFF/, ''));
  const records = rows
    .filter((values) => values.some((value) => String(value || '').trim()))
    .map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || '']).filter(([header]) => header)));
  return { headers, records };
}

function readCsv(file) {
  return parseCsv(fs.readFileSync(abs(file), 'utf8').replace(/^\uFEFF/, ''));
}

function normalizeCode(value) {
  return String(value || '').trim().toUpperCase();
}

function clean(value) {
  return String(value ?? '').trim();
}

function cleanPermit(value) {
  const text = clean(value);
  if (!text) return '';
  const match = text.match(/-?\d+(?:\.\d+)?/);
  if (!match) return text;
  const number = Number(match[0]);
  return Number.isFinite(number) ? String(Math.trunc(number)) : text;
}

function permitStatus(row) {
  const res = cleanPermit(row.permits_2026_res);
  const nr = cleanPermit(row.permits_2026_nr);
  const total = cleanPermit(row.permits_2026_total || row.total_2026_permits);
  const conservation = cleanPermit(row.permits_2026_conservation);
  const expo = cleanPermit(row.permits_2026_expo);
  const sportsman = cleanPermit(row.permits_2026_sportsman);
  if (res && nr && total) return 'FULL_SPLIT';
  if (!res && !nr && total) return 'TOTAL_ONLY';
  if (!res && !nr && !total && (conservation || expo || sportsman)) return 'SPECIAL_PERMIT_ONLY';
  if (!res && !nr && !total) return 'NO_QUOTA_PUBLISHED';
  return 'PARTIAL_SPLIT';
}

function normalizedAllocation(row) {
  const status = clean(row.permit_status) || permitStatus(row);
  return {
    hunt_code: normalizeCode(row.hunt_code || row.hunt_number),
    permits_2026_res: cleanPermit(row.permits_2026_res),
    permits_2026_nr: cleanPermit(row.permits_2026_nr),
    permits_2026_total: cleanPermit(row.permits_2026_total || row.total_2026_permits),
    permits_2026_conservation: cleanPermit(row.permits_2026_conservation),
    permits_2026_expo: cleanPermit(row.permits_2026_expo),
    permits_2026_sportsman: cleanPermit(row.permits_2026_sportsman),
    permit_status: status,
    permit_allocation_type: clean(row.permit_allocation_type) || (status === 'SPECIAL_PERMIT_ONLY' ? clean(row.special_permit_category) || status : status),
    special_permit_area_id: clean(row.special_permit_area_id),
    special_permit_category: clean(row.special_permit_category),
    special_permit_note: clean(row.special_permit_note),
    special_permit_overlay_source: clean(row.special_permit_overlay_source),
    permit_source_authority: clean(row.permit_source_authority) || 'Utah DWR published 2026 permit allocation',
    permit_note: clean(row.permit_note || row.NOTES),
    permit_overlay_source: clean(row.permit_overlay_source) || SOURCE_FILE,
    data_status: clean(row.data_status) || (status === 'NO_QUOTA_PUBLISHED' ? 'SOURCE_CONFIRMED_NO_QUOTA_PUBLISHED' : 'COMPLETE'),
    permits_2026_source: SOURCE_LABEL,
  };
}

function isAcceptedRacProvenance(field, actual, expected) {
  if (actual === expected) return true;
  if (field === 'permit_source_authority') {
    return /RAC/i.test(actual) && Boolean(expected);
  }
  if (field === 'permit_overlay_source') {
    return /^pipeline\/RAW\/hunt_unit_database\/2026\/csv\/2026_rac_/i.test(actual)
      && Boolean(expected);
  }
  if (field === 'permits_2026_source') {
    return ['2026_RAC_TRUTH_SOURCE', '2026_RAC_CURRENT_YEAR_ALLOTMENT'].includes(actual)
      && Boolean(expected);
  }
  return false;
}

function loadDatabase() {
  const parsed = readCsv(SOURCE_FILE);
  const index = new Map();
  const duplicates = [];
  for (const row of parsed.records) {
    const normalized = normalizedAllocation(row);
    if (!normalized.hunt_code) continue;
    if (index.has(normalized.hunt_code)) duplicates.push(normalized.hunt_code);
    index.set(normalized.hunt_code, normalized);
  }
  return { ...parsed, index, duplicates: [...new Set(duplicates)].sort() };
}

function rowsFromJson(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.hunt_catalog)) return data.hunt_catalog;
  if (Array.isArray(data.hunts)) return data.hunts;
  if (data.hunt_planner && Array.isArray(data.hunt_planner.hunts)) return data.hunt_planner.hunts;
  return [];
}

function statusCounts(db) {
  const counts = { FULL_SPLIT: 0, TOTAL_ONLY: 0, SPECIAL_PERMIT_ONLY: 0, NO_QUOTA_PUBLISHED: 0, PARTIAL_SPLIT: 0 };
  for (const truth of db.index.values()) counts[truth.permit_status] = (counts[truth.permit_status] || 0) + 1;
  return counts;
}

function verifyRecord(record, truth, file, rowNumber) {
  const issues = [];
  for (const field of [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS]) {
    const actual = clean(record[field]);
    const expected = clean(truth[field]);
    if (actual !== expected && !isAcceptedRacProvenance(field, actual, expected)) {
      issues.push({
        type: 'ALLOCATION_FIELD_MISMATCH',
        file,
        row: rowNumber,
        hunt_code: truth.hunt_code,
        field,
        expected,
        actual,
      });
    }
  }

  for (const permitField of ['permits_2026_res', 'permits_2026_nr', 'permits_2026_total']) {
    const actual = clean(record[permitField]);
    const expected = clean(truth[permitField]);
    if (actual && actual !== expected) {
      const copiedFrom = FORBIDDEN_FIELDS.find((field) => actual === clean(record[field]));
      if (copiedFrom) {
        issues.push({
          type: 'FORBIDDEN_SOURCE_COPY_SUSPECTED',
          file,
          row: rowNumber,
          hunt_code: truth.hunt_code,
          field: permitField,
          actual,
          copied_from: copiedFrom,
        });
      }
    }
  }

  if (truth.permit_status === 'TOTAL_ONLY') {
    if (clean(record.permits_2026_res) || clean(record.permits_2026_nr)) {
      issues.push({
        type: 'TOTAL_ONLY_HAS_INFERRED_SPLIT',
        file,
        row: rowNumber,
        hunt_code: truth.hunt_code,
        permits_2026_res: clean(record.permits_2026_res),
        permits_2026_nr: clean(record.permits_2026_nr),
      });
    }
  }

  if (truth.permit_status === 'NO_QUOTA_PUBLISHED') {
    if (clean(record.permits_2026_res) || clean(record.permits_2026_nr) || clean(record.permits_2026_total)) {
      issues.push({
        type: 'NO_QUOTA_HAS_INVENTED_PERMITS',
        file,
        row: rowNumber,
        hunt_code: truth.hunt_code,
        permits_2026_res: clean(record.permits_2026_res),
        permits_2026_nr: clean(record.permits_2026_nr),
        permits_2026_total: clean(record.permits_2026_total),
      });
    }
  }

  for (const field of ['permit_source_authority', 'permit_overlay_source', 'data_status', 'permits_2026_source']) {
    if (!clean(record[field])) {
      issues.push({
        type: 'MISSING_SOURCE_PROVENANCE',
        file,
        row: rowNumber,
        hunt_code: truth.hunt_code,
        field,
      });
    }
  }

  return issues;
}

function verifyCsv(file, db) {
  const parsed = readCsv(file);
  const required = [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS];
  const missingColumns = required.filter((field) => !parsed.headers.includes(field));
  const issues = missingColumns.map((field) => ({ type: 'MISSING_COLUMN', file, field }));
  const targetOnly = new Set();
  const matchedCodes = new Set();
  let checkedRows = 0;
  let blankValuesPreserved = 0;

  parsed.records.forEach((record, index) => {
    const code = normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number);
    if (!code) return;
    const truth = db.index.get(code);
    if (!truth) {
      targetOnly.add(code);
      return;
    }
    checkedRows += 1;
    matchedCodes.add(code);
    for (const field of ALLOCATION_FIELDS) {
      if (!truth[field] && !clean(record[field])) blankValuesPreserved += 1;
    }
    issues.push(...verifyRecord(record, truth, file, index + 2));
  });

  const targetCodes = new Set(parsed.records.map((record) => normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number)).filter(Boolean));
  const databaseOnly = [...db.index.keys()].filter((code) => !targetCodes.has(code));
  return {
    file,
    type: 'csv',
    rows_checked: parsed.records.length,
    matched_rows: checkedRows,
    hunt_codes_checked: matchedCodes.size,
    fields_added: [],
    fields_updated: [],
    mismatches_after_sync: issues.length,
    blank_values_preserved: blankValuesPreserved,
    target_only_hunt_codes: [...targetOnly].sort(),
    database_only_hunt_codes: databaseOnly.sort(),
    sample_issues: issues.slice(0, 50),
  };
}

function verifyJsonRows(file, db) {
  const data = JSON.parse(fs.readFileSync(abs(file), 'utf8'));
  const rows = rowsFromJson(data);
  const issues = [];
  const targetOnly = new Set();
  const matchedCodes = new Set();
  let blankValuesPreserved = 0;

  rows.forEach((record, index) => {
    const code = normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number);
    if (!code) return;
    const truth = db.index.get(code);
    if (!truth) {
      targetOnly.add(code);
      return;
    }
    matchedCodes.add(code);
    for (const field of ALLOCATION_FIELDS) {
      if (!truth[field] && !clean(record[field])) blankValuesPreserved += 1;
    }
    issues.push(...verifyRecord(record, truth, file, index));
  });

  const targetCodes = new Set(rows.map((record) => normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number)).filter(Boolean));
  const databaseOnly = [...db.index.keys()].filter((code) => !targetCodes.has(code));
  return {
    file,
    type: 'json_rows',
    rows_checked: rows.length,
    matched_rows: matchedCodes.size,
    hunt_codes_checked: matchedCodes.size,
    fields_added: [],
    fields_updated: [],
    mismatches_after_sync: issues.length,
    blank_values_preserved: blankValuesPreserved,
    target_only_hunt_codes: [...targetOnly].sort(),
    database_only_hunt_codes: databaseOnly.sort(),
    sample_issues: issues.slice(0, 50),
  };
}

function verifyJsonMetadata(file) {
  const data = JSON.parse(fs.readFileSync(abs(file), 'utf8'));
  const required = [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS];
  const issues = [];
  if (data.datasets && typeof data.datasets === 'object') {
    for (const [name, dataset] of Object.entries(data.datasets)) {
      if (!Array.isArray(dataset.fields)) continue;
      for (const field of required) {
        if (!dataset.fields.includes(field)) {
          issues.push({ type: 'MISSING_METADATA_FIELD', file, dataset: name, field });
        }
      }
    }
  }
  return {
    file,
    type: 'json_metadata',
    rows_checked: 0,
    matched_rows: 0,
    hunt_codes_checked: 0,
    fields_added: [],
    fields_updated: [],
    mismatches_after_sync: issues.length,
    blank_values_preserved: 0,
    target_only_hunt_codes: [],
    database_only_hunt_codes: [],
    sample_issues: issues.slice(0, 50),
  };
}

function writeReports(report) {
  fs.mkdirSync(abs('canonical'), { recursive: true });
  fs.mkdirSync(abs('docs'), { recursive: true });
  fs.writeFileSync(abs('canonical/permit-allocation-2026-integrity-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  const lines = [
    '# 2026 Permit Allocation Integrity Report',
    '',
    `Generated: ${report.generated_at}`,
    `Source file used: ${report.source_file}`,
    `Source label: ${report.source_label}`,
    `Promotion blockers: ${report.promotion_blocker_count}`,
    '',
    '## Status Counts',
    '',
    `- FULL_SPLIT: ${report.status_counts.FULL_SPLIT || 0}`,
    `- TOTAL_ONLY: ${report.status_counts.TOTAL_ONLY || 0}`,
    `- SPECIAL_PERMIT_ONLY: ${report.status_counts.SPECIAL_PERMIT_ONLY || 0}`,
    `- NO_QUOTA_PUBLISHED: ${report.status_counts.NO_QUOTA_PUBLISHED || 0}`,
    `- PARTIAL_SPLIT: ${report.status_counts.PARTIAL_SPLIT || 0}`,
    '',
    '## Files Audited',
    '',
    '| File | Rows checked | Codes checked | Mismatches before | Mismatches after | Blank values preserved | Target-only codes | Database-only codes |',
    '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ...report.files.map((item) => `| ${item.file} | ${item.rows_checked} | ${item.hunt_codes_checked} | ${item.mismatches_before_sync || 0} | ${item.mismatches_after_sync} | ${item.blank_values_preserved} | ${item.target_only_hunt_codes.length} | ${item.database_only_hunt_codes.length} |`),
    '',
    '## Guardrails',
    '',
    `- Allocation fields match DATABASE.csv: ${report.promotion_blocker_count === 0 ? 'PASS' : 'FAIL'}`,
    '- Historical draw-result and harvest/performance fields are not accepted as allocation sources.',
    '- TOTAL_ONLY rows may not contain inferred resident/nonresident splits.',
    '- NO_QUOTA_PUBLISHED rows may not contain invented permit totals.',
    '- SPECIAL_PERMIT_ONLY rows may contain special permit counts while remaining excluded from normal public draw permit totals.',
    '- Source/provenance markers are required.',
    '',
    '## Skipped Missing Targets',
    '',
    ...(report.skipped_missing_targets.length
      ? report.skipped_missing_targets.map((file) => `- ${file}`)
      : ['- None']),
    '',
  ];
  fs.writeFileSync(abs('docs/permit-allocation-2026-integrity-report.md'), `${lines.join('\n')}\n`, 'utf8');
}

function main() {
  const writeReportFiles = !process.argv.includes('--no-write');
  const db = loadDatabase();
  const lastSync = fs.existsSync(abs(LAST_SYNC_FILE)) ? JSON.parse(fs.readFileSync(abs(LAST_SYNC_FILE), 'utf8')) : null;
  const skippedMissingTargets = [];
  const existingCsvTargets = CSV_TARGETS.filter((file) => {
    const ok = fs.existsSync(abs(file));
    if (!ok) skippedMissingTargets.push(file);
    return ok;
  });
  const existingJsonRowTargets = JSON_ROW_TARGETS.filter((file) => {
    const ok = fs.existsSync(abs(file));
    if (!ok) skippedMissingTargets.push(file);
    return ok;
  });
  const existingJsonMetadataTargets = JSON_METADATA_TARGETS.filter((file) => {
    const ok = fs.existsSync(abs(file));
    if (!ok) skippedMissingTargets.push(file);
    return ok;
  });
  const files = [
    ...existingCsvTargets.map((file) => verifyCsv(file, db)),
    ...existingJsonRowTargets.map((file) => verifyJsonRows(file, db)),
    ...existingJsonMetadataTargets.map((file) => verifyJsonMetadata(file)),
  ];
  if (lastSync && Array.isArray(lastSync.files)) {
    for (const item of files) {
      const synced = lastSync.files.find((candidate) => candidate.file === item.file);
      if (synced) {
        item.fields_added = synced.fields_added || [];
        item.fields_updated = synced.fields_updated || [];
        item.mismatches_before_sync = synced.mismatches_before_sync || 0;
        item.changed_rows = synced.changed_rows || 0;
        item.changed_cells = synced.changed_cells || 0;
      }
    }
  }
  const blockers = files.filter((item) => item.mismatches_after_sync > 0);
  const report = {
    generated_at: new Date().toISOString(),
    mode: 'verify',
    source_file: SOURCE_FILE,
    source_label: SOURCE_LABEL,
    database_rows: db.records.length,
    database_unique_hunt_codes: db.index.size,
    database_duplicate_hunt_codes: db.duplicates,
    allocation_fields: ALLOCATION_FIELDS,
    forbidden_fields: FORBIDDEN_FIELDS,
    status_counts: statusCounts(db),
    files,
    skipped_missing_targets: skippedMissingTargets,
    files_changed: lastSync?.files_changed || [],
    totals: {
      rows_updated: files.reduce((sum, item) => sum + (item.changed_rows || 0), 0),
      fields_added: [...new Set(files.flatMap((item) => item.fields_added || []))].sort(),
      fields_updated: [...new Set(files.flatMap((item) => item.fields_updated || []))].sort(),
      mismatches_before_sync: files.reduce((sum, item) => sum + (item.mismatches_before_sync || 0), 0),
      mismatches_after_sync: files.reduce((sum, item) => sum + item.mismatches_after_sync, 0),
      blank_values_preserved: files.reduce((sum, item) => sum + item.blank_values_preserved, 0),
    },
    promotion_blocker_count: blockers.length,
    promotion_blockers: blockers.map((item) => ({ file: item.file, issues: item.sample_issues })),
  };
  if (writeReportFiles) writeReports(report);
  console.log(JSON.stringify({
    ok: report.promotion_blocker_count === 0,
    source_file: SOURCE_FILE,
    files_audited: files.length,
    rows_updated: report.totals.rows_updated,
    mismatches_before_sync: report.totals.mismatches_before_sync,
    mismatches_after_sync: report.totals.mismatches_after_sync,
    promotion_blockers: report.promotion_blocker_count,
    report_json: writeReportFiles ? 'canonical/permit-allocation-2026-integrity-report.json' : null,
    report_md: writeReportFiles ? 'docs/permit-allocation-2026-integrity-report.md' : null,
  }, null, 2));
  if (report.promotion_blocker_count) process.exitCode = 1;
}

main();
