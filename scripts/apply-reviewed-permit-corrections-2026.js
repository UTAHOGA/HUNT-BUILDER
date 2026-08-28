const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..');
const DATABASE = path.join(REPO, 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
const CONSERVATION_CROSSWALK = path.join(REPO, 'data/conservation-permit-hunt-table-2025-27.json');
const CONSERVATION_SOURCE = 'data/conservation-permit-hunt-table-2025-27.json; reviewed official DWR 2025-27 conservation-permit crosswalk; non-additive per-hunt-code coverage; checked 2026-08-28';

const CORRECTIONS = {
  EA2045: {
    permits_2026_res: '',
    permits_2026_nr: '',
    permits_2026_total: '',
    permit_allotment_2026_res: '',
    permit_allotment_2026_nr: '',
    permit_allotment_2026_total: '',
    permit_allotment_2026_status: 'SPECIAL_PERMIT_ONLY',
    conservation_permits_2026_total: '4',
    conservation_permits_2026_source: CONSERVATION_SOURCE,
  },
  PD1056: {
    permits_2026_res: '36',
    permits_2026_nr: '4',
    permits_2026_total: '40',
    permits_2026_source: 'USER_CONFIRMED_PD1056_DWR_PLANNER_TYPO_RECONCILED_WITH_DWR_DRAW_ODDS',
    permits_2026_draw_source: 'USER_CONFIRMED_PD1056_DWR_PLANNER_TYPO_RECONCILED_WITH_DWR_DRAW_ODDS',
    permit_allotment_2026_res: '36',
    permit_allotment_2026_nr: '4',
    permit_allotment_2026_total: '40',
    permit_allotment_2026_source: 'USER_CONFIRMED_PD1056_DWR_PLANNER_TYPO_RECONCILED_WITH_DWR_DRAW_ODDS',
    permit_allotment_2026_source_file: 'processed_data/audits/reviewed_permit_value_overrides_2026.csv',
    permit_allotment_2026_status: 'REVIEWED_OVERRIDE_USER_CONFIRMED',
  },
};

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    const next = text[index + 1];
    if (quoted) {
      if (character === '"' && next === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        cell += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ',') {
      row.push(cell);
      cell = '';
    } else if (character === '\n') {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
    } else if (character !== '\r') {
      cell += character;
    }
  }
  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }
  const headers = rows.shift().map((header) => String(header || '').trim().replace(/^\uFEFF/, ''));
  const records = rows
    .filter((values) => values.some((value) => String(value || '').trim()))
    .map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ''])));
  return { headers, records };
}

function csvEscape(value) {
  const text = String(value ?? '');
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(headers, records) {
  const rows = [headers, ...records.map((record) => headers.map((header) => record[header] ?? ''))];
  return `${rows.map((row) => row.map(csvEscape).join(',')).join('\r\n')}\r\n`;
}

function loadConservationCoverage() {
  const records = JSON.parse(fs.readFileSync(CONSERVATION_CROSSWALK, 'utf8'));
  if (!Array.isArray(records) || records.length !== 271) {
    throw new Error(`Expected 271 conservation area/condition records; found ${Array.isArray(records) ? records.length : 'non-array'}`);
  }

  const coverage = new Map();
  let annualPermits = 0;
  let repeatedAssignments = 0;
  for (const record of records) {
    const permitCount = Number(record.permitCount || 0);
    if (!Number.isInteger(permitCount) || permitCount <= 0) {
      throw new Error(`Invalid conservation permit count for ${record.huntCode || '<unknown>'}: ${record.permitCount}`);
    }
    const huntCodes = [...new Set((record.sourceHuntCodes || []).map((value) => String(value || '').trim().toUpperCase()).filter(Boolean))];
    annualPermits += permitCount;
    repeatedAssignments += permitCount * huntCodes.length;
    for (const huntCode of huntCodes) coverage.set(huntCode, (coverage.get(huntCode) || 0) + permitCount);
  }

  if (annualPermits !== 336) throw new Error(`Expected 336 annual conservation permits; found ${annualPermits}`);
  if (coverage.size !== 418) throw new Error(`Expected 418 covered hunt codes; found ${coverage.size}`);
  if (repeatedAssignments !== 1454) throw new Error(`Expected 1,454 repeated permit-to-code assignments; found ${repeatedAssignments}`);
  return { coverage, annualPermits, repeatedAssignments, records: records.length };
}

function main() {
  const parsed = parseCsv(fs.readFileSync(DATABASE, 'utf8').replace(/^\uFEFF/, ''));
  const conservation = loadConservationCoverage();
  const databaseCodes = new Set(parsed.records.map((record) => String(record.hunt_code || '').trim().toUpperCase()).filter(Boolean));
  const crosswalkOnlyCodes = [...conservation.coverage.keys()].filter((huntCode) => !databaseCodes.has(huntCode)).sort();
  const coveredDatabaseCodes = [...conservation.coverage.keys()].filter((huntCode) => databaseCodes.has(huntCode)).length;
  if (coveredDatabaseCodes !== 405 || crosswalkOnlyCodes.length !== 13) {
    throw new Error(`Expected 405 covered DATABASE codes and 13 crosswalk-only codes; found ${coveredDatabaseCodes} and ${crosswalkOnlyCodes.length}`);
  }
  const counts = Object.fromEntries(Object.keys(CORRECTIONS).map((huntCode) => [huntCode, 0]));
  const changes = [];

  for (const record of parsed.records) {
    const huntCode = String(record.hunt_code || '').trim().toUpperCase();
    const expectedConservation = conservation.coverage.get(huntCode);
    if (expectedConservation !== undefined) {
      const conservationFields = {
        conservation_permits_2026_total: String(expectedConservation),
        conservation_permits_2026_source: CONSERVATION_SOURCE,
      };
      const publicQuotaBlank = !String(record.permit_allotment_2026_total || '').trim() && !String(record.permits_2026_total || '').trim();
      if (String(record.hunt_type || '').trim().toLowerCase() === 'conservation' && publicQuotaBlank) {
        conservationFields.permit_allotment_2026_status = 'SPECIAL_PERMIT_ONLY';
      }
      for (const [field, after] of Object.entries(conservationFields)) {
        if (!parsed.headers.includes(field)) throw new Error(`DATABASE.csv lacks required field ${field}`);
        const before = String(record[field] ?? '');
        if (before !== after) {
          record[field] = after;
          changes.push({ hunt_code: huntCode, field, before, after });
        }
      }
    } else {
      const currentConservation = String(record.conservation_permits_2026_total || '').trim();
      if (currentConservation && currentConservation !== '0') {
        for (const field of ['conservation_permits_2026_total', 'conservation_permits_2026_source']) {
          const before = String(record[field] ?? '');
          if (before) {
            record[field] = '';
            changes.push({ hunt_code: huntCode, field, before, after: '' });
          }
        }
      }
    }

    const correction = CORRECTIONS[huntCode];
    if (!correction) continue;
    counts[huntCode] += 1;
    for (const [field, after] of Object.entries(correction)) {
      if (!parsed.headers.includes(field)) throw new Error(`DATABASE.csv lacks required field ${field}`);
      const before = String(record[field] ?? '');
      if (before !== after) {
        record[field] = after;
        changes.push({ hunt_code: huntCode, field, before, after });
      }
    }
  }

  for (const [huntCode, count] of Object.entries(counts)) {
    if (count !== 1) throw new Error(`Expected exactly one ${huntCode} row; found ${count}`);
  }

  if (changes.length) fs.writeFileSync(DATABASE, writeCsv(parsed.headers, parsed.records), 'utf8');
  console.log(JSON.stringify({
    database: path.relative(REPO, DATABASE).replace(/\\/g, '/'),
    rows_checked: counts,
    conservation: {
      area_condition_records: conservation.records,
      annual_permits: conservation.annualPermits,
      covered_hunt_codes: conservation.coverage.size,
      covered_database_codes: coveredDatabaseCodes,
      repeated_assignments: conservation.repeatedAssignments,
      crosswalk_only_codes: crosswalkOnlyCodes,
    },
    change_count: changes.length,
    changed_hunt_code_count: new Set(changes.map((change) => change.hunt_code)).size,
    sample_changes: changes.slice(0, 25),
  }, null, 2));
}

main();
