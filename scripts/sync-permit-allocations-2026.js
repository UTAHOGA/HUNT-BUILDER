const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const SOURCE_FILE = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';
const SOURCE_LABEL = 'DATABASE_2026_DWR_APPROVED_PUBLISHED_PERMIT_ALLOCATIONS';
const STAMP = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+$/, '').replace('T', '_');
const BACKUP_DIR = `processed_data/backups/permit_allocations_2026_${STAMP}`;
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
const PUBLIC_COMPAT_FIELDS = ['public_permits_2026', 'public_permits_2026_source'];

const CSV_TARGETS = [
  { file: 'processed_data/hunt_master_enriched.csv', updatePublicPermits: true },
  { file: 'processed_data/hunt_unit_reference_linked.csv', updatePublicPermits: true },
  { file: 'processed_data/draw_reality_engine.csv', updatePublicPermits: true },
  { file: 'processed_data/point_ladder_view.csv', updatePublicPermits: false },
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

function csvEscape(value) {
  const text = String(value ?? '');
  if (/[",\r\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function writeCsv(headers, records) {
  const rows = [headers, ...records.map((record) => headers.map((header) => record[header] ?? ''))];
  return `${rows.map((row) => row.map(csvEscape).join(',')).join('\r\n')}\r\n`;
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

function backup(file) {
  if (!fs.existsSync(abs(file))) return;
  const dest = abs(path.join(BACKUP_DIR, file));
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(abs(file), dest);
}

function setField(record, field, value, changes) {
  const before = clean(record[field]);
  const after = clean(value);
  if (before !== after) {
    record[field] = after;
    changes.push({ field, before, after });
  } else if (record[field] === undefined) {
    record[field] = after;
  }
}

function compatibilityPublicPermits(record, truth) {
  if (truth.permit_status === 'NO_QUOTA_PUBLISHED' || truth.permit_status === 'SPECIAL_PERMIT_ONLY') return '';
  if (truth.permit_status === 'TOTAL_ONLY') return truth.permits_2026_total;
  const residency = clean(record.residency).toLowerCase();
  if (residency.startsWith('non')) return truth.permits_2026_nr;
  if (residency.startsWith('res')) return truth.permits_2026_res;
  return truth.permits_2026_total;
}

function auditRecord(record, truth, target) {
  const mismatches = [];
  for (const field of [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS]) {
    if (clean(record[field]) !== clean(truth[field])) {
      mismatches.push({
        file: target.file || target,
        hunt_code: truth.hunt_code,
        field,
        expected: clean(truth[field]),
        actual: clean(record[field]),
      });
    }
  }
  return mismatches;
}

function rowsFromJson(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.hunt_catalog)) return data.hunt_catalog;
  if (Array.isArray(data.hunts)) return data.hunts;
  if (data.hunt_planner && Array.isArray(data.hunt_planner.hunts)) return data.hunt_planner.hunts;
  return [];
}

function syncCsvTarget(target, db) {
  const parsed = readCsv(target.file);
  const headers = [...parsed.headers];
  const required = [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS];
  if (target.updatePublicPermits) required.push(...PUBLIC_COMPAT_FIELDS);
  const addedColumns = [];
  for (const field of required) {
    if (!headers.includes(field)) {
      headers.push(field);
      addedColumns.push(field);
    }
  }

  const beforeMismatches = [];
  const afterMismatches = [];
  const rowChanges = [];
  const missingFromDatabase = new Set();
  const matchedCodes = new Set();
  let matchedRows = 0;
  let blankValuesPreserved = 0;

  parsed.records.forEach((record, index) => {
    for (const header of headers) {
      if (record[header] === undefined) record[header] = '';
    }
    const code = normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number);
    if (!code) return;
    const truth = db.index.get(code);
    if (!truth) {
      missingFromDatabase.add(code);
      return;
    }
    matchedRows += 1;
    matchedCodes.add(code);
    beforeMismatches.push(...auditRecord(record, truth, target));
    const changes = [];
    for (const field of ALLOCATION_FIELDS) {
      if (!truth[field]) blankValuesPreserved += 1;
      setField(record, field, truth[field], changes);
    }
    for (const field of PROVENANCE_FIELDS) {
      setField(record, field, truth[field], changes);
    }
    if (target.updatePublicPermits) {
      const publicPermits = compatibilityPublicPermits(record, truth);
      setField(record, 'public_permits_2026', publicPermits, changes);
      setField(record, 'public_permits_2026_source', publicPermits ? SOURCE_LABEL : '', changes);
    }
    afterMismatches.push(...auditRecord(record, truth, target));
    if (changes.length) rowChanges.push({ row_number: index + 2, hunt_code: code, changes });
  });

  if (rowChanges.length || addedColumns.length) {
    backup(target.file);
    fs.writeFileSync(abs(target.file), writeCsv(headers, parsed.records), 'utf8');
  }

  const targetCodes = new Set(parsed.records.map((record) => normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number)).filter(Boolean));
  const missingFromTarget = [...db.index.keys()].filter((code) => !targetCodes.has(code));
  return {
    file: target.file,
    type: 'csv',
    rows_checked: parsed.records.length,
    matched_rows: matchedRows,
    hunt_codes_checked: matchedCodes.size,
    fields_added: addedColumns,
    fields_updated: [...new Set(rowChanges.flatMap((row) => row.changes.map((change) => change.field)))].sort(),
    changed_rows: rowChanges.length,
    changed_cells: rowChanges.reduce((sum, row) => sum + row.changes.length, 0),
    blank_values_preserved: blankValuesPreserved,
    mismatches_before_sync: beforeMismatches.length,
    mismatches_after_sync: afterMismatches.length,
    target_only_hunt_codes: [...missingFromDatabase].sort(),
    database_only_hunt_codes: missingFromTarget.sort(),
    sample_changes: rowChanges.slice(0, 25),
    sample_mismatches_before_sync: beforeMismatches.slice(0, 25),
    sample_mismatches_after_sync: afterMismatches.slice(0, 25),
  };
}

function syncJsonRows(file, db) {
  const data = JSON.parse(fs.readFileSync(abs(file), 'utf8'));
  const rows = rowsFromJson(data);
  const beforeMismatches = [];
  const afterMismatches = [];
  const rowChanges = [];
  const missingFromDatabase = new Set();
  const matchedCodes = new Set();
  let blankValuesPreserved = 0;

  rows.forEach((record, index) => {
    const code = normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number);
    if (!code) return;
    const truth = db.index.get(code);
    if (!truth) {
      missingFromDatabase.add(code);
      return;
    }
    matchedCodes.add(code);
    beforeMismatches.push(...auditRecord(record, truth, file));
    const changes = [];
    for (const field of ALLOCATION_FIELDS) {
      if (!truth[field]) blankValuesPreserved += 1;
      setField(record, field, truth[field], changes);
    }
    for (const field of PROVENANCE_FIELDS) {
      setField(record, field, truth[field], changes);
    }
    afterMismatches.push(...auditRecord(record, truth, file));
    if (changes.length) rowChanges.push({ row_index: index, hunt_code: code, changes });
  });

  if (rowChanges.length) {
    backup(file);
    fs.writeFileSync(abs(file), `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  }

  const targetCodes = new Set(rows.map((record) => normalizeCode(record.hunt_code || record.huntCode || record.code || record.hunt_number)).filter(Boolean));
  const missingFromTarget = [...db.index.keys()].filter((code) => !targetCodes.has(code));
  return {
    file,
    type: 'json_rows',
    rows_checked: rows.length,
    matched_rows: matchedCodes.size,
    hunt_codes_checked: matchedCodes.size,
    fields_added: [],
    fields_updated: [...new Set(rowChanges.flatMap((row) => row.changes.map((change) => change.field)))].sort(),
    changed_rows: rowChanges.length,
    changed_cells: rowChanges.reduce((sum, row) => sum + row.changes.length, 0),
    blank_values_preserved: blankValuesPreserved,
    mismatches_before_sync: beforeMismatches.length,
    mismatches_after_sync: afterMismatches.length,
    target_only_hunt_codes: [...missingFromDatabase].sort(),
    database_only_hunt_codes: missingFromTarget.sort(),
    sample_changes: rowChanges.slice(0, 25),
    sample_mismatches_before_sync: beforeMismatches.slice(0, 25),
    sample_mismatches_after_sync: afterMismatches.slice(0, 25),
  };
}

function syncJsonMetadata(file) {
  const data = JSON.parse(fs.readFileSync(abs(file), 'utf8'));
  const required = [...ALLOCATION_FIELDS, ...PROVENANCE_FIELDS];
  const changes = [];
  if (data.datasets && typeof data.datasets === 'object') {
    for (const [name, dataset] of Object.entries(data.datasets)) {
      if (!Array.isArray(dataset.fields)) continue;
      for (const field of required) {
        if (!dataset.fields.includes(field)) {
          dataset.fields.push(field);
          changes.push({ dataset: name, field });
        }
      }
    }
  }
  if (changes.length) {
    backup(file);
    fs.writeFileSync(abs(file), `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  }
  return {
    file,
    type: 'json_metadata',
    rows_checked: 0,
    matched_rows: 0,
    hunt_codes_checked: 0,
    fields_added: [...new Set(changes.map((change) => change.field))].sort(),
    fields_updated: [],
    changed_rows: changes.length ? 1 : 0,
    changed_cells: changes.length,
    blank_values_preserved: 0,
    mismatches_before_sync: changes.length,
    mismatches_after_sync: 0,
    target_only_hunt_codes: [],
    database_only_hunt_codes: [],
    sample_changes: changes.slice(0, 25),
    sample_mismatches_before_sync: [],
    sample_mismatches_after_sync: [],
  };
}

function statusCounts(db) {
  const counts = {
    FULL_SPLIT: 0,
    TOTAL_ONLY: 0,
    NO_QUOTA_PUBLISHED: 0,
    PARTIAL_SPLIT: 0,
  };
  for (const truth of db.index.values()) {
    counts[truth.permit_status] = (counts[truth.permit_status] || 0) + 1;
  }
  return counts;
}

function writeReports(report) {
  fs.mkdirSync(abs('canonical'), { recursive: true });
  fs.mkdirSync(abs('docs'), { recursive: true });
  fs.mkdirSync(abs('processed_data'), { recursive: true });
  fs.writeFileSync(abs('canonical/permit-allocation-2026-integrity-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  fs.writeFileSync(abs(LAST_SYNC_FILE), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  const lines = [
    '# 2026 Permit Allocation Integrity Report',
    '',
    `Generated: ${report.generated_at}`,
    `Source file used: ${report.source_file}`,
    `Source label: ${report.source_label}`,
    `Promotion blockers: ${report.promotion_blocker_count}`,
    '',
    'These fields represent DWR-approved/published 2026 permit allocations. They are intentionally separate from historical draw-result fields and harvest/performance fields.',
    '',
    '## Status Counts',
    '',
    `- FULL_SPLIT: ${report.status_counts.FULL_SPLIT || 0}`,
    `- TOTAL_ONLY: ${report.status_counts.TOTAL_ONLY || 0}`,
    `- NO_QUOTA_PUBLISHED: ${report.status_counts.NO_QUOTA_PUBLISHED || 0}`,
    `- PARTIAL_SPLIT: ${report.status_counts.PARTIAL_SPLIT || 0}`,
    '',
    '## Files Audited',
    '',
    '| File | Rows checked | Codes checked | Fields added | Fields updated | Mismatches before | Mismatches after | Blank values preserved | Target-only codes | Database-only codes |',
    '| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |',
    ...report.files.map((item) => `| ${item.file} | ${item.rows_checked} | ${item.hunt_codes_checked} | ${item.fields_added.join(', ') || 'none'} | ${item.fields_updated.join(', ') || 'none'} | ${item.mismatches_before_sync} | ${item.mismatches_after_sync} | ${item.blank_values_preserved} | ${item.target_only_hunt_codes.length} | ${item.database_only_hunt_codes.length} |`),
    '',
    '## Changed Files',
    '',
    ...report.files_changed.map((file) => `- ${file}`),
    '',
  ];
  fs.writeFileSync(abs('docs/permit-allocation-2026-integrity-report.md'), `${lines.join('\n')}\n`, 'utf8');
}

function main() {
  const db = loadDatabase();
  const skippedMissingTargets = [];
  const existingTargets = (targets) => targets.filter((target) => {
    const file = typeof target === 'string' ? target : target.file;
    if (fs.existsSync(abs(file))) return true;
    skippedMissingTargets.push(file);
    return false;
  });
  const fileReports = [
    ...existingTargets(CSV_TARGETS).map((target) => syncCsvTarget(target, db)),
    ...existingTargets(JSON_ROW_TARGETS).map((file) => syncJsonRows(file, db)),
    ...existingTargets(JSON_METADATA_TARGETS).map((file) => syncJsonMetadata(file)),
  ];
  const promotionBlockers = fileReports.filter((item) => item.mismatches_after_sync > 0);
  const report = {
    generated_at: new Date().toISOString(),
    mode: 'sync',
    source_file: SOURCE_FILE,
    source_label: SOURCE_LABEL,
    database_rows: db.records.length,
    database_unique_hunt_codes: db.index.size,
    database_duplicate_hunt_codes: db.duplicates,
    allocation_fields: ALLOCATION_FIELDS,
    forbidden_historical_draw_fields: [
      'permits_2025_draw_res',
      'permits_2025_draw_nr',
      'permits_2025_draw_total',
      'permits_2025_res',
      'permits_2025_nr',
      'permits_2025_total',
    ],
    forbidden_harvest_performance_fields: [
      'hunters_2025',
      'harvest_2025',
      'success_percent_2025',
      'avg_days_2025',
      'satisfaction_2025',
    ],
    status_counts: statusCounts(db),
    backup_dir: BACKUP_DIR,
    skipped_missing_targets: skippedMissingTargets,
    files: fileReports,
    files_changed: fileReports.filter((item) => item.changed_rows || item.changed_cells || item.fields_added.length).map((item) => item.file),
    totals: {
      rows_updated: fileReports.reduce((sum, item) => sum + item.changed_rows, 0),
      fields_added: [...new Set(fileReports.flatMap((item) => item.fields_added))].sort(),
      fields_updated: [...new Set(fileReports.flatMap((item) => item.fields_updated))].sort(),
      mismatches_before_sync: fileReports.reduce((sum, item) => sum + item.mismatches_before_sync, 0),
      mismatches_after_sync: fileReports.reduce((sum, item) => sum + item.mismatches_after_sync, 0),
      blank_values_preserved: fileReports.reduce((sum, item) => sum + item.blank_values_preserved, 0),
    },
    promotion_blocker_count: promotionBlockers.length,
    promotion_blockers: promotionBlockers.map((item) => ({ file: item.file, mismatches_after_sync: item.mismatches_after_sync })),
  };
  writeReports(report);
  console.log(JSON.stringify({
    ok: report.promotion_blocker_count === 0,
    source_file: SOURCE_FILE,
    files_changed: report.files_changed.length,
    rows_updated: report.totals.rows_updated,
    mismatches_before_sync: report.totals.mismatches_before_sync,
    mismatches_after_sync: report.totals.mismatches_after_sync,
    report_json: 'canonical/permit-allocation-2026-integrity-report.json',
    report_md: 'docs/permit-allocation-2026-integrity-report.md',
  }, null, 2));
  if (report.promotion_blocker_count) process.exitCode = 1;
}

main();
