#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const DATABASE_CSV = path.join(ROOT, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'csv', 'DATABASE.csv');
const DWR_POPUP_CSV = path.join(ROOT, 'processed_data', 'dwr_huntplanner_hanumber_2026.csv');
const AUDIT_JSON = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_overlay_audit.json');
const AUDIT_CSV = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_overlay_audit.csv');
const NONMATCH_CSV = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_permit_nonmatches.csv');
const ALLOTMENT_AUDIT_CSV = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_allotment_fill_audit.csv');
const BACKFILL_VS_2025_CSV = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_backfilled_permits_vs_2025.csv');
const IDENTITY_AUDIT_CSV = path.join(ROOT, 'processed_data', 'audits', 'database_dwr_huntplanner_2026_identity_audit.csv');
const MANAGEMENT_UNITS_CSV = path.join(ROOT, 'data_model', 'harvest_quality', 'huntplanner_management_units_2026.csv');
const MANAGEMENT_UNIT_CONFLICTS_CSV = path.join(ROOT, 'processed_data', 'audits', 'dwr_huntplanner_management_unit_conflicts_2026.csv');
const SKIP_PERMIT_WRITES = process.argv.includes('--skip-permit-writes');

const PROTECTED_PERMIT_COLUMNS = [
  'permits_2026_res',
  'permits_2026_nr',
  'permits_2026_total',
  'permits_2026_source',
  'permit_allotment_2026_res',
  'permit_allotment_2026_nr',
  'permit_allotment_2026_total',
  'permit_allotment_2026_source',
  'permit_allotment_2026_source_file',
  'permit_allotment_2026_status'
];

const REMOVED_DUPLICATE_PERMIT_COLUMNS = [
  'dwr_huntplanner_permits_2026_res',
  'dwr_huntplanner_permits_2026_nr',
  'dwr_huntplanner_permits_2026_total',
];

const DATA_COLUMNS = [
  'percent_harvest_success_previous_hunting_season',
  'current_age_3yr_average',
  'dwr_huntplanner_source_url',
  'dwr_huntplanner_source_retrieved_at',
  'dwr_huntplanner_management_stats_available',
  'dwr_huntplanner_hunt_year',
  'dwr_huntplanner_hunt_name',
  'dwr_huntplanner_species',
  'dwr_huntplanner_sex_type',
  'dwr_huntplanner_hunt_type',
  'dwr_huntplanner_weapon',
  'dwr_huntplanner_season_type',
  'dwr_huntplanner_draw_designation',
  'dwr_huntplanner_management_unit_key',
  'dwr_huntplanner_percent_harvest_success_previous_hunting_season',
  'dwr_huntplanner_public_harvest_success_previous_hunting_season',
  'dwr_huntplanner_cwmu_harvest_success_previous_hunting_season',
  'dwr_huntplanner_current_age_3yr_average',
  'dwr_huntplanner_age_objective',
  'dwr_huntplanner_population_objective',
  'dwr_huntplanner_current_population_estimate',
  'dwr_huntplanner_bucks_per_100_does_objective',
  'dwr_huntplanner_current_bucks_per_100_does_3yr_average',
  'dwr_huntplanner_bulls_per_100_cows_objective',
  'dwr_huntplanner_bulls_per_100_cows_estimate',
  'dwr_huntplanner_total_hunters_previous_hunting_season'
];

const TOKEN_REPLACEMENTS = new Map([
  ['alw', 'any legal weapon'],
  ['mtn', 'mountain'],
  ['mtns', 'mountains'],
  ['mt', 'mount']
]);

const GENERIC_NAME_TOKENS = new Set([
  'antlerless', 'association', 'bull', 'buck', 'deer', 'elk', 'hunt', 'landowner',
  'limited', 'entry', 'male', 'female', 'only', 'permit', 'premium', 'unit'
]);

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

  if (!rows.length) return { headers: [], records: [] };
  const headers = rows[0].map(h => h.replace(/^\uFEFF/, ''));
  const records = rows.slice(1).filter(r => r.some(v => v !== '')).map(values => {
    const out = {};
    headers.forEach((header, index) => {
      out[header] = values[index] ?? '';
    });
    return out;
  });
  return { headers, records };
}

function csvEscape(value) {
  const s = value == null ? '' : String(value);
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function writeCsv(filePath, rows, headers) {
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map(header => csvEscape(row[header])).join(','));
  }
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`, 'utf8');
}

function normalizeCode(value) {
  return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function protectedPermitFingerprint(records) {
  const protectedRows = records.map(row => {
    const item = { hunt_code: normalizeCode(row.hunt_code) };
    for (const column of PROTECTED_PERMIT_COLUMNS) item[column] = String(row[column] ?? '');
    return item;
  }).sort((left, right) => left.hunt_code.localeCompare(right.hunt_code));
  return crypto.createHash('sha256').update(JSON.stringify(protectedRows)).digest('hex');
}

function normalizeText(value) {
  let text = String(value || '').toLowerCase().replace(/\u2019/g, "'");
  text = text.replace(/(?<=[a-z])'(?=[a-z])/g, '');
  for (const [source, replacement] of TOKEN_REPLACEMENTS.entries()) {
    text = text.replace(new RegExp(`\\b${source}\\b`, 'g'), replacement);
  }
  return (text.match(/[a-z0-9]+/g) || []).join(' ');
}

function normalizeSpecies(value) {
  const text = normalizeText(value);
  const aliases = new Map([
    ['antlerless deer', 'deer'],
    ['mule deer', 'deer'],
    ['antlerless elk', 'elk'],
    ['rocky bighorn', 'rocky mountain bighorn sheep'],
    ['desert bighorn', 'desert bighorn sheep']
  ]);
  return aliases.get(text) || text;
}

function meaningfulNameTokens(value) {
  return normalizeText(value).split(' ').filter(Boolean).map(token => {
    if (GENERIC_NAME_TOKENS.has(token)) return '';
    return token.length > 4 && token.endsWith('s') ? token.slice(0, -1) : token;
  }).filter(Boolean);
}

function oneEditOrEqual(left, right) {
  if (left === right) return true;
  if (Math.abs(left.length - right.length) > 1) return false;
  if (left.length === right.length) {
    let differences = 0;
    for (let i = 0; i < left.length; i += 1) if (left[i] !== right[i]) differences += 1;
    return differences <= 1;
  }
  const [shorter, longer] = left.length < right.length ? [left, right] : [right, left];
  let shortIndex = 0;
  let longIndex = 0;
  let skipped = false;
  while (shortIndex < shorter.length && longIndex < longer.length) {
    if (shorter[shortIndex] === longer[longIndex]) shortIndex += 1;
    else if (skipped) return false;
    else skipped = true;
    longIndex += 1;
  }
  return true;
}

function huntNameCompatible(left, right) {
  const leftNormalized = normalizeText(left);
  const rightNormalized = normalizeText(right);
  if (!leftNormalized || !rightNormalized) return false;
  if (leftNormalized === rightNormalized) return true;
  const leftTokens = meaningfulNameTokens(left);
  const rightTokens = meaningfulNameTokens(right);
  if (!leftTokens.length || !rightTokens.length) return false;
  if (oneEditOrEqual(leftTokens.join(''), rightTokens.join(''))) return true;
  const leftSet = new Set(leftTokens);
  const rightSet = new Set(rightTokens);
  const smaller = leftSet.size <= rightSet.size ? leftSet : rightSet;
  const larger = leftSet.size <= rightSet.size ? rightSet : leftSet;
  if ([...smaller].every(token => larger.has(token))) return true;
  let matches = 0;
  for (const leftToken of leftSet) {
    if ([...rightSet].some(rightToken => oneEditOrEqual(leftToken, rightToken))) matches += 1;
  }
  return matches / Math.max(leftSet.size, rightSet.size) >= 0.75;
}

function identityStatus(databaseRow, dwrRow) {
  if (normalizeCode(databaseRow.hunt_code) !== normalizeCode(dwrRow.hunt_code)) return 'HUNT_CODE_MISMATCH';
  if (normalizeSpecies(databaseRow.species) !== normalizeSpecies(dwrRow.dwr_species)) return 'HUNT_CODE_SPECIES_MISMATCH';
  if (!huntNameCompatible(databaseRow.hunt_name, dwrRow.dwr_hunt_name)) return 'HUNT_CODE_NAME_MISMATCH';
  return 'MATCHED_CODE_NAME_SPECIES';
}

function managementUnitKey(dwr) {
  const species = normalizeSpecies(dwr.dwr_species);
  const unit = meaningfulNameTokens(dwr.dwr_hunt_name).join('_');
  return species && unit ? `${species}:${unit}` : '';
}

const MANAGEMENT_VALUE_FIELDS = [
  'dwr_huntplanner_current_age_3yr_average',
  'dwr_huntplanner_age_objective',
  'dwr_huntplanner_population_objective',
  'dwr_huntplanner_current_population_estimate',
  'dwr_huntplanner_bucks_per_100_does_objective',
  'dwr_huntplanner_current_bucks_per_100_does_3yr_average',
  'dwr_huntplanner_bulls_per_100_cows_objective',
  'dwr_huntplanner_bulls_per_100_cows_estimate',
  'dwr_huntplanner_total_hunters_previous_hunting_season'
];

function sortedUnique(values) {
  return [...new Set(values.map(value => String(value || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function buildManagementUnitRows(records) {
  const groups = new Map();
  for (const row of records) {
    const key = String(row.dwr_huntplanner_management_unit_key || '').trim();
    if (!key || !MANAGEMENT_VALUE_FIELDS.some(field => String(row[field] || '').trim())) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }

  const units = [];
  const conflicts = [];
  for (const [key, sourceRows] of [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const unit = {
      management_unit_key: key,
      species: sourceRows[0].dwr_huntplanner_species || sourceRows[0].species || '',
      management_unit_name: sourceRows[0].dwr_huntplanner_hunt_name || sourceRows[0].hunt_name || '',
      source_hunt_code_count: sourceRows.length,
      source_hunt_codes: sortedUnique(sourceRows.map(row => row.hunt_code)).join('|'),
      source_weapons: sortedUnique(sourceRows.map(row => row.dwr_huntplanner_weapon)).join('|'),
      source_urls: sortedUnique(sourceRows.map(row => row.dwr_huntplanner_source_url)).join('|'),
      source_retrieved_at: sortedUnique(sourceRows.map(row => row.dwr_huntplanner_source_retrieved_at)).pop() || '',
      value_conflict_fields: '',
      evidence_status: 'DEDUPED_UNIT_EVIDENCE'
    };
    const conflictFields = [];
    for (const field of MANAGEMENT_VALUE_FIELDS) {
      const outputField = field.replace(/^dwr_huntplanner_/, '');
      const values = sortedUnique(sourceRows.map(row => row[field]));
      unit[outputField] = values.length === 1 ? values[0] : '';
      if (values.length > 1) {
        conflictFields.push(outputField);
        conflicts.push({
          management_unit_key: key,
          species: unit.species,
          management_unit_name: unit.management_unit_name,
          field: outputField,
          conflicting_values: values.join('|'),
          source_hunt_codes: unit.source_hunt_codes,
          source_urls: unit.source_urls
        });
      }
    }
    unit.value_conflict_fields = conflictFields.join('|');
    if (conflictFields.length) unit.evidence_status = 'REVIEW_VALUE_CONFLICT';
    units.push(unit);
  }
  return { units, conflicts };
}

function num(value) {
  const s = String(value ?? '').trim();
  if (!s) return null;
  const n = Number(s.replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

function hasNonZeroNumeric(value) {
  const n = num(value);
  return n != null && n !== 0;
}

function isCwmuRow(row, dwr) {
  return [
    row.hunt_type,
    row.hunt_class,
    row.hunt_name,
    dwr.hunt_type,
    dwr.hunt_name
  ].some(value => /cwmu/i.test(String(value || '')));
}

function effectiveDwrPermitValue(row, dwr, databaseField, dwrField) {
  const dwrRes = num(dwr.permits_2026_res);
  const dwrNr = num(dwr.permits_2026_nr);
  const dwrTotal = num(dwr.permits_2026_total);

  // DWR CWMU rows publish resident/nonresident public-permit values, but
  // the Hunt Planner JSON often leaves the total slot as 0. Derive total
  // from the split rather than treating the resident slot as a total-only value.
  if (isCwmuSplitWithDerivedTotal(row, dwr)) {
    if (databaseField === 'permits_2026_res') return String(dwrRes);
    if (databaseField === 'permits_2026_nr') return String(dwrNr);
    if (databaseField === 'permits_2026_total') return String(dwrRes + dwrNr);
  }

  return dwr[dwrField] || '';
}

function isCwmuSplitWithDerivedTotal(row, dwr) {
  const dwrRes = num(dwr.permits_2026_res);
  const dwrNr = num(dwr.permits_2026_nr);
  const dwrTotal = num(dwr.permits_2026_total);
  return isCwmuRow(row, dwr) && dwrRes != null && dwrRes > 0 && dwrNr != null && dwrTotal === 0;
}

function sameNumeric(a, b) {
  const na = num(a);
  const nb = num(b);
  if (na == null && nb == null) return true;
  if (na == null || nb == null) return false;
  return na === nb;
}

function sameDisplayValue(a, b) {
  const sa = String(a ?? '').trim();
  const sb = String(b ?? '').trim();
  if (!sa && !sb) return true;
  if (sameNumeric(sa, sb)) return true;
  return sa.toLowerCase() === sb.toLowerCase();
}

function differenceType(databaseValue, dwrValue) {
  const db = String(databaseValue ?? '').trim();
  const dwr = String(dwrValue ?? '').trim();
  const dbn = num(db);
  const dwrn = num(dwr);
  if (!db && dwrn === 0) return 'DATABASE_BLANK_DWR_ZERO';
  if (!db && dwr) return 'DATABASE_BLANK_DWR_VALUE';
  if (db && !dwr) return 'DATABASE_VALUE_DWR_BLANK';
  if (dbn != null && dwrn != null && dbn !== dwrn) return 'NUMERIC_CONFLICT';
  return 'OTHER_DIFFERENCE';
}

function compareBackfillTo2025(row, databaseField, dwrValue, sourceUrl) {
  const field2025 = databaseField.replace('permits_2026_', 'permits_2025_');
  const value2025 = row[field2025] || '';
  const n2026 = num(dwrValue);
  const n2025 = num(value2025);
  let absoluteChange = '';
  let percentChange = '';
  let changeFlag = 'NO_2025_VALUE';

  if (n2026 != null && n2025 != null) {
    absoluteChange = n2026 - n2025;
    if (n2025 === 0) {
      changeFlag = n2026 === 0 ? 'NO_CHANGE' : 'NEW_FROM_ZERO_2025';
    } else {
      percentChange = (absoluteChange / n2025) * 100;
      changeFlag = Math.abs(percentChange) >= 20 ? 'BIG_CHANGE_20_PERCENT_OR_MORE' : 'WITHIN_20_PERCENT';
    }
  }

  return {
    hunt_code: row.hunt_code,
    hunt_name: row.hunt_name,
    species: row.species,
    field_2026: databaseField,
    field_2025: field2025,
    value_2026_backfilled_from_dwr: dwrValue || '',
    value_2025: value2025,
    absolute_change: absoluteChange,
    percent_change: percentChange === '' ? '' : percentChange.toFixed(2),
    change_flag: changeFlag,
    dwr_source_url: sourceUrl || ''
  };
}

function main() {
  if (!fs.existsSync(DATABASE_CSV)) throw new Error(`DATABASE.csv not found: ${DATABASE_CSV}`);
  if (!fs.existsSync(DWR_POPUP_CSV)) throw new Error(`DWR Hunt Planner extract not found: ${DWR_POPUP_CSV}`);

  const database = parseCsv(fs.readFileSync(DATABASE_CSV, 'utf8'));
  const popup = parseCsv(fs.readFileSync(DWR_POPUP_CSV, 'utf8'));
  const protectedPermitFingerprintBefore = protectedPermitFingerprint(database.records);
  const popupByCode = new Map();
  for (const row of popup.records) {
    const code = normalizeCode(row.hunt_code);
    if (code) popupByCode.set(code, row);
  }

  const headers = database.headers.filter(column => !REMOVED_DUPLICATE_PERMIT_COLUMNS.includes(column));
  for (const column of DATA_COLUMNS) {
    if (!headers.includes(column)) headers.push(column);
  }

  const permitComparisons = [];
  const identityAuditRows = [];
  let matchedRows = 0;
  let missingPopupRows = 0;
  let percentHarvestRows = 0;
  let currentAgeRows = 0;
  let permitExactMatches = 0;
  let permitBlankDwrZero = 0;
  let permitBlankDwrValue = 0;
  let permitNumericConflicts = 0;
  let permitOtherDifferences = 0;
  const allotmentAuditRows = [];
  let allotmentFilledCells = 0;
  let allotmentAlreadyMatchedCells = 0;
  let allotmentNotFilledNonmatchCells = 0;
  let allotmentNoDatabasePermitCells = 0;
  let allotmentConflictCells = 0;
  const backfillVs2025Rows = [];
  let permitCellsBackfilledFromDwr = 0;
  let permitBackfillBigChangeCells = 0;
  let permitBackfillNo2025ValueCells = 0;

  for (const row of database.records) {
    for (const column of REMOVED_DUPLICATE_PERMIT_COLUMNS) {
      delete row[column];
    }

    const code = normalizeCode(row.hunt_code);
    const dwr = popupByCode.get(code);
    if (!dwr) {
      missingPopupRows += 1;
      identityAuditRows.push({
        hunt_code: row.hunt_code,
        database_hunt_name: row.hunt_name,
        dwr_hunt_name: '',
        database_species: row.species,
        dwr_species: '',
        identity_status: 'MISSING_DWR_HUNT_CODE',
        source_url: ''
      });
      continue;
    }

    const rowIdentityStatus = identityStatus(row, dwr);
    identityAuditRows.push({
      hunt_code: row.hunt_code,
      database_hunt_name: row.hunt_name,
      dwr_hunt_name: dwr.dwr_hunt_name || '',
      database_species: row.species,
      dwr_species: dwr.dwr_species || '',
      identity_status: rowIdentityStatus,
      source_url: dwr.source_url || ''
    });
    if (rowIdentityStatus !== 'MATCHED_CODE_NAME_SPECIES') continue;

    matchedRows += 1;
    const huntPlannerSuccess = dwr.percent_harvest_success_previous_hunting_season || '';
    const cwmu = isCwmuRow(row, dwr);
    row.dwr_huntplanner_source_url = dwr.source_url || '';
    row.dwr_huntplanner_source_retrieved_at = dwr.source_retrieved_at || '';
    row.dwr_huntplanner_management_stats_available = dwr.management_stats_available || '';
    row.dwr_huntplanner_hunt_year = dwr.hunt_year || '';
    row.dwr_huntplanner_hunt_name = dwr.dwr_hunt_name || '';
    row.dwr_huntplanner_species = dwr.dwr_species || '';
    row.dwr_huntplanner_sex_type = dwr.dwr_sex_type || '';
    row.dwr_huntplanner_hunt_type = dwr.dwr_hunt_type || '';
    row.dwr_huntplanner_weapon = dwr.dwr_weapon || '';
    row.dwr_huntplanner_season_type = dwr.dwr_season_type || '';
    row.dwr_huntplanner_draw_designation = dwr.dwr_draw_designation || '';
    row.dwr_huntplanner_management_unit_key = managementUnitKey(dwr);
    row.dwr_huntplanner_percent_harvest_success_previous_hunting_season = huntPlannerSuccess;
    row.dwr_huntplanner_public_harvest_success_previous_hunting_season = cwmu ? '' : huntPlannerSuccess;
    row.dwr_huntplanner_cwmu_harvest_success_previous_hunting_season = cwmu ? huntPlannerSuccess : '';
    row.dwr_huntplanner_current_age_3yr_average = dwr.current_age_3yr_average || '';
    row.current_age_3yr_average = dwr.current_age_3yr_average || '';
    row.dwr_huntplanner_age_objective = dwr.age_objective || '';
    row.dwr_huntplanner_population_objective = dwr.population_objective || '';
    row.dwr_huntplanner_current_population_estimate = dwr.current_population_estimate || '';
    row.dwr_huntplanner_bucks_per_100_does_objective = dwr.bucks_per_100_does_objective || '';
    row.dwr_huntplanner_current_bucks_per_100_does_3yr_average = dwr.current_bucks_per_100_does_3yr_average || '';
    row.dwr_huntplanner_bulls_per_100_cows_objective = dwr.bulls_per_100_cows_objective || '';
    row.dwr_huntplanner_bulls_per_100_cows_estimate = dwr.bulls_per_100_cows_estimate || '';
    row.dwr_huntplanner_total_hunters_previous_hunting_season = dwr.total_hunters_previous_hunting_season || '';

    if (huntPlannerSuccess) percentHarvestRows += 1;
    if (row.current_age_3yr_average) currentAgeRows += 1;

    let rowAllotmentFilled = false;
    let rowPermitBackfilled = false;
    let rowCwmuSplitDerived = false;
    for (const [databaseField, dwrField, allotmentField] of [
      ['permits_2026_res', 'permits_2026_res', 'permit_allotment_2026_res'],
      ['permits_2026_nr', 'permits_2026_nr', 'permit_allotment_2026_nr'],
      ['permits_2026_total', 'permits_2026_total', 'permit_allotment_2026_total']
    ]) {
      const effectiveDwrValue = effectiveDwrPermitValue(row, dwr, databaseField, dwrField);
      const cwmuSplitWithDerivedTotal = isCwmuSplitWithDerivedTotal(row, dwr);
      const cwmuDerivedValue = cwmuSplitWithDerivedTotal && effectiveDwrValue !== (dwr[dwrField] || '');
      if (cwmuSplitWithDerivedTotal) rowCwmuSplitDerived = true;

      let backfilledPermitFromDwr = false;
      const shouldBackfillDwrValue = hasNonZeroNumeric(effectiveDwrValue) || (
        cwmuSplitWithDerivedTotal &&
        databaseField === 'permits_2026_nr' &&
        num(effectiveDwrValue) === 0 &&
        hasNonZeroNumeric(dwr.permits_2026_res)
      );
      if (!SKIP_PERMIT_WRITES && !String(row[databaseField] ?? '').trim() && !String(row[allotmentField] ?? '').trim() && shouldBackfillDwrValue) {
        row[databaseField] = effectiveDwrValue;
        row[allotmentField] = effectiveDwrValue;
        backfilledPermitFromDwr = true;
        rowPermitBackfilled = true;
        rowAllotmentFilled = true;
        permitCellsBackfilledFromDwr += 1;
        const backfillRow = compareBackfillTo2025(row, databaseField, effectiveDwrValue, dwr.source_url || '');
        if (backfillRow.change_flag === 'BIG_CHANGE_20_PERCENT_OR_MORE' || backfillRow.change_flag === 'NEW_FROM_ZERO_2025') {
          permitBackfillBigChangeCells += 1;
        }
        if (backfillRow.change_flag === 'NO_2025_VALUE') permitBackfillNo2025ValueCells += 1;
        backfillVs2025Rows.push(backfillRow);
      }

      const comparisonStatus = backfilledPermitFromDwr
        ? 'BACKFILLED_FROM_DWR_VALUE'
        : sameNumeric(row[databaseField], effectiveDwrValue)
        ? 'MATCH'
        : differenceType(row[databaseField], effectiveDwrValue);

      if (comparisonStatus === 'MATCH' || comparisonStatus === 'BACKFILLED_FROM_DWR_VALUE') permitExactMatches += 1;
      else if (comparisonStatus === 'DATABASE_BLANK_DWR_ZERO') permitBlankDwrZero += 1;
      else if (comparisonStatus === 'DATABASE_BLANK_DWR_VALUE') permitBlankDwrValue += 1;
      else if (comparisonStatus === 'NUMERIC_CONFLICT') permitNumericConflicts += 1;
      else permitOtherDifferences += 1;

      permitComparisons.push({
        hunt_code: row.hunt_code,
        hunt_name: row.hunt_name,
        species: row.species,
        field: databaseField,
        comparison_status: comparisonStatus,
        database_value: row[databaseField] || '',
        dwr_huntplanner_value: effectiveDwrValue || '',
        source_url: dwr.source_url || ''
      });

      let allotmentAction = '';
      if (backfilledPermitFromDwr) {
        allotmentFilledCells += 1;
        allotmentAction = 'FILLED_PERMIT_AND_ALLOTMENT_FROM_DWR_NONZERO';
      } else if (!String(row[databaseField] ?? '').trim()) {
        allotmentNoDatabasePermitCells += 1;
        allotmentAction = 'NOT_FILLED_NO_DATABASE_PERMIT_VALUE';
      } else if (comparisonStatus !== 'MATCH') {
        allotmentNotFilledNonmatchCells += 1;
        allotmentAction = 'NOT_FILLED_PERMIT_DWR_NONMATCH';
      } else if (!SKIP_PERMIT_WRITES && !String(row[allotmentField] ?? '').trim()) {
        row[allotmentField] = row[databaseField];
        allotmentFilledCells += 1;
        rowAllotmentFilled = true;
        allotmentAction = 'FILLED_FROM_MATCHED_DATABASE_AND_DWR_PERMIT';
      } else if (sameDisplayValue(row[allotmentField], row[databaseField])) {
        allotmentAlreadyMatchedCells += 1;
        allotmentAction = 'ALREADY_MATCHED_DATABASE_AND_DWR_PERMIT';
      } else {
        allotmentConflictCells += 1;
        allotmentAction = 'ALLOTMENT_CONFLICT_NOT_OVERWRITTEN';
      }

      allotmentAuditRows.push({
        hunt_code: row.hunt_code,
        hunt_name: row.hunt_name,
        species: row.species,
        permit_field: databaseField,
        allotment_field: allotmentField,
        dwr_field: dwrField,
        permit_dwr_comparison_status: comparisonStatus,
        allotment_action: allotmentAction,
        database_permit_value: row[databaseField] || '',
        allotment_value_after: row[allotmentField] || '',
        dwr_huntplanner_value: effectiveDwrValue || '',
        source_url: dwr.source_url || ''
      });
    }

    if (!SKIP_PERMIT_WRITES && rowAllotmentFilled) {
      if (!row.permit_allotment_2026_source) row.permit_allotment_2026_source = 'DWR_HUNT_PLANNER_HaNumber_MATCHED_PERMITS_2026';
      if (!row.permit_allotment_2026_source_file) row.permit_allotment_2026_source_file = dwr.source_url || '';
      if (!row.permit_allotment_2026_status) row.permit_allotment_2026_status = 'DWR_HUNTPLANNER_CONFIRMED_MATCH';
    }
    if (!SKIP_PERMIT_WRITES && rowPermitBackfilled) {
      if (!row.permits_2026_source) row.permits_2026_source = 'DWR_HUNT_PLANNER_HaNumber_NONZERO_BACKFILL';
      if (!row.permit_allotment_2026_source) row.permit_allotment_2026_source = 'DWR_HUNT_PLANNER_HaNumber_NONZERO_BACKFILL';
      if (!row.permit_allotment_2026_source_file) row.permit_allotment_2026_source_file = dwr.source_url || '';
      if (!row.permit_allotment_2026_status) row.permit_allotment_2026_status = 'DWR_HUNTPLANNER_NONZERO_BACKFILLED';
    }
    if (!SKIP_PERMIT_WRITES && rowCwmuSplitDerived) {
      if (!row.permit_allotment_2026_source) row.permit_allotment_2026_source = 'DWR_HUNT_PLANNER_HaNumber_CWMU_RES_NR_TOTAL_DERIVED';
      if (!row.permit_allotment_2026_source_file) row.permit_allotment_2026_source_file = dwr.source_url || '';
      if (!row.permits_2026_source) row.permits_2026_source = 'DWR_HUNT_PLANNER_HaNumber_CWMU_RES_NR_TOTAL_DERIVED';
      if (
        !row.permit_allotment_2026_status ||
        row.permit_allotment_2026_status === 'LIVE_DWR_CWMU_TOTAL_ONLY_FROM_QUOTA_RES'
      ) {
        row.permit_allotment_2026_status = 'DWR_HUNTPLANNER_CWMU_RES_NR_TOTAL_DERIVED';
      }
    }
  }

  const protectedPermitFingerprintAfter = protectedPermitFingerprint(database.records);
  if (SKIP_PERMIT_WRITES && protectedPermitFingerprintBefore !== protectedPermitFingerprintAfter) {
    throw new Error('Protected 2026 permit/allotment fields changed during a --skip-permit-writes refresh. No files were written.');
  }

  fs.mkdirSync(path.dirname(AUDIT_JSON), { recursive: true });
  const managementUnits = buildManagementUnitRows(database.records);
  writeCsv(DATABASE_CSV, database.records, headers);
  writeCsv(AUDIT_CSV, permitComparisons, [
    'hunt_code',
    'hunt_name',
    'species',
    'field',
    'comparison_status',
    'database_value',
    'dwr_huntplanner_value',
    'source_url'
  ]);
  writeCsv(NONMATCH_CSV, permitComparisons.filter(row => !['MATCH', 'BACKFILLED_FROM_DWR_VALUE'].includes(row.comparison_status)), [
    'hunt_code',
    'hunt_name',
    'species',
    'field',
    'comparison_status',
    'database_value',
    'dwr_huntplanner_value',
    'source_url'
  ]);
  writeCsv(ALLOTMENT_AUDIT_CSV, allotmentAuditRows, [
    'hunt_code',
    'hunt_name',
    'species',
    'permit_field',
    'allotment_field',
    'dwr_field',
    'permit_dwr_comparison_status',
    'allotment_action',
    'database_permit_value',
    'allotment_value_after',
    'dwr_huntplanner_value',
    'source_url'
  ]);
  writeCsv(IDENTITY_AUDIT_CSV, identityAuditRows, [
    'hunt_code',
    'database_hunt_name',
    'dwr_hunt_name',
    'database_species',
    'dwr_species',
    'identity_status',
    'source_url'
  ]);
  const managementUnitColumns = [
    'management_unit_key',
    'species',
    'management_unit_name',
    'current_age_3yr_average',
    'age_objective',
    'population_objective',
    'current_population_estimate',
    'bucks_per_100_does_objective',
    'current_bucks_per_100_does_3yr_average',
    'bulls_per_100_cows_objective',
    'bulls_per_100_cows_estimate',
    'total_hunters_previous_hunting_season',
    'source_hunt_code_count',
    'source_hunt_codes',
    'source_weapons',
    'source_urls',
    'source_retrieved_at',
    'value_conflict_fields',
    'evidence_status'
  ];
  writeCsv(MANAGEMENT_UNITS_CSV, managementUnits.units, managementUnitColumns);
  writeCsv(MANAGEMENT_UNIT_CONFLICTS_CSV, managementUnits.conflicts, [
    'management_unit_key',
    'species',
    'management_unit_name',
    'field',
    'conflicting_values',
    'source_hunt_codes',
    'source_urls'
  ]);
  const comparisonStatusCounts = permitComparisons.reduce((acc, row) => {
    acc[row.comparison_status] = (acc[row.comparison_status] || 0) + 1;
    return acc;
  }, {});
  let effectiveBackfillVs2025Rows = backfillVs2025Rows;
  if (!effectiveBackfillVs2025Rows.length && fs.existsSync(BACKFILL_VS_2025_CSV)) {
    effectiveBackfillVs2025Rows = parseCsv(fs.readFileSync(BACKFILL_VS_2025_CSV, 'utf8')).records;
  }
  const effectiveBackfillBigChangeCells = effectiveBackfillVs2025Rows.filter(row => (
    row.change_flag === 'BIG_CHANGE_20_PERCENT_OR_MORE' || row.change_flag === 'NEW_FROM_ZERO_2025'
  )).length;
  const effectiveBackfillNo2025ValueCells = effectiveBackfillVs2025Rows.filter(row => row.change_flag === 'NO_2025_VALUE').length;
  const effectiveAllotmentFilledCells = allotmentFilledCells || effectiveBackfillVs2025Rows.length;
  writeCsv(BACKFILL_VS_2025_CSV, effectiveBackfillVs2025Rows, [
    'hunt_code',
    'hunt_name',
    'species',
    'field_2026',
    'field_2025',
    'value_2026_backfilled_from_dwr',
    'value_2025',
    'absolute_change',
    'percent_change',
    'change_flag',
    'dwr_source_url'
  ]);

  const audit = {
    created_at: new Date().toISOString(),
    database_csv: path.relative(ROOT, DATABASE_CSV).replace(/\\/g, '/'),
    dwr_popup_csv: path.relative(ROOT, DWR_POPUP_CSV).replace(/\\/g, '/'),
    database_rows: database.records.length,
    dwr_popup_rows: popup.records.length,
    matched_hunt_code_rows: matchedRows,
    missing_dwr_popup_rows: missingPopupRows,
    columns_removed: REMOVED_DUPLICATE_PERMIT_COLUMNS,
    columns_added_or_confirmed: DATA_COLUMNS,
    permit_writes_skipped: SKIP_PERMIT_WRITES,
    protected_permit_columns: PROTECTED_PERMIT_COLUMNS,
    protected_permit_fingerprint_before: protectedPermitFingerprintBefore,
    protected_permit_fingerprint_after: protectedPermitFingerprintAfter,
    protected_permit_fingerprint_unchanged: protectedPermitFingerprintBefore === protectedPermitFingerprintAfter,
    identity_status_counts: identityAuditRows.reduce((acc, row) => {
      acc[row.identity_status] = (acc[row.identity_status] || 0) + 1;
      return acc;
    }, {}),
    rows_with_percent_harvest_success_previous_hunting_season: percentHarvestRows,
    rows_with_current_age_3yr_average: currentAgeRows,
    permit_comparison_cells: permitComparisons.length,
    permit_exact_match_cells: permitExactMatches,
    permit_nonmatch_cells: permitComparisons.length - permitExactMatches,
    permit_nonmatch_hunt_codes: [...new Set(permitComparisons.filter(r => r.comparison_status !== 'MATCH').map(r => r.hunt_code))].length,
    permit_comparison_status_counts: comparisonStatusCounts,
    permit_blank_dwr_zero_cells: permitBlankDwrZero,
    permit_blank_dwr_value_cells: permitBlankDwrValue,
    permit_numeric_conflict_cells: permitNumericConflicts,
    permit_other_difference_cells: permitOtherDifferences,
    permit_cells_backfilled_from_dwr_values: effectiveBackfillVs2025Rows.length,
    permit_cells_backfilled_from_dwr_nonzero: effectiveBackfillVs2025Rows.filter(row => hasNonZeroNumeric(row.value_2026_backfilled_from_dwr)).length,
    permit_backfill_cells_filled_this_run: permitCellsBackfilledFromDwr,
    permit_backfill_big_change_cells_vs_2025: effectiveBackfillBigChangeCells,
    permit_backfill_no_2025_value_cells: effectiveBackfillNo2025ValueCells,
    allotment_filled_cells_total: effectiveAllotmentFilledCells,
    allotment_filled_cells_this_run: allotmentFilledCells,
    allotment_filled_cells_from_matched_database_and_dwr: effectiveAllotmentFilledCells,
    allotment_already_matched_cells: allotmentAlreadyMatchedCells,
    allotment_not_filled_permit_dwr_nonmatch_cells: allotmentNotFilledNonmatchCells,
    allotment_not_filled_no_database_permit_cells: allotmentNoDatabasePermitCells,
    allotment_conflict_not_overwritten_cells: allotmentConflictCells,
    audit_csv: path.relative(ROOT, AUDIT_CSV).replace(/\\/g, '/'),
    permit_nonmatch_csv: path.relative(ROOT, NONMATCH_CSV).replace(/\\/g, '/'),
    allotment_audit_csv: path.relative(ROOT, ALLOTMENT_AUDIT_CSV).replace(/\\/g, '/'),
    identity_audit_csv: path.relative(ROOT, IDENTITY_AUDIT_CSV).replace(/\\/g, '/'),
    management_units_csv: path.relative(ROOT, MANAGEMENT_UNITS_CSV).replace(/\\/g, '/'),
    management_unit_conflicts_csv: path.relative(ROOT, MANAGEMENT_UNIT_CONFLICTS_CSV).replace(/\\/g, '/'),
    management_unit_rows: managementUnits.units.length,
    management_unit_conflicts: managementUnits.conflicts.length,
    backfill_vs_2025_csv: path.relative(ROOT, BACKFILL_VS_2025_CSV).replace(/\\/g, '/'),
    notes: [
      'DATABASE.csv uses the existing permits_2026_res, permits_2026_nr, and permits_2026_total columns; duplicate DWR-prefixed permit columns are not kept.',
      'permit_allotment_2026_res, permit_allotment_2026_nr, and permit_allotment_2026_total are filled only when DATABASE permits_2026_* and DWR Hunt Planner popup values match exactly.',
      'For CWMU rows where DWR publishes resident/nonresident permit values but leaves the total slot as 0, total is derived as resident plus nonresident and marked DWR_HUNTPLANNER_CWMU_RES_NR_TOTAL_DERIVED.',
      'If both DATABASE permits_2026_* and permit_allotment_2026_* are blank while DWR Hunt Planner has a current permit value, both DATABASE fields are backfilled from DWR and compared to the matching 2025 permit field.',
      'DWR Hunt Planner management fields are merged only when exact hunt code plus compatible hunt name and species agree; boundary_id is never a match key.',
      'The dashboard-backed percent_harvest_success_previous_hunting_season column is preserved; the Hunt Planner value is retained separately with public and CWMU-specific columns.',
      'current_age_3yr_average is DWR Hunt Planner current age context, not prior-year average harvest age.',
      'Deer buck-to-doe ratios, Elk age, population context, classifications, and source/retrieval lineage are retained in explicit DWR Hunt Planner columns.',
      'The management_unit_key permits unit-level de-duplication when one biological metric is repeated across multiple weapon-specific hunt codes.',
      'Permit values are compared in the audit; nonmatching values are reported and existing DATABASE permit columns are not overwritten by this script.'
    ]
  };
  fs.writeFileSync(AUDIT_JSON, `${JSON.stringify(audit, null, 2)}\n`, 'utf8');

  console.log('DWR Hunt Planner harvest/age fields merged into DATABASE.csv.');
  console.log(`DATABASE rows: ${database.records.length}`);
  console.log(`Matched hunt codes: ${matchedRows}`);
  console.log(`Missing DWR popup rows: ${missingPopupRows}`);
  console.log(`Previous-season harvest success rows: ${percentHarvestRows}`);
  console.log(`Current age 3-year average rows: ${currentAgeRows}`);
  console.log(`Permit exact-match cells: ${permitExactMatches}`);
  console.log(`Permit non-match cells: ${permitComparisons.length - permitExactMatches}`);
  console.log(`Permit cells backfilled from DWR values: ${effectiveBackfillVs2025Rows.length}`);
  console.log(`Permit cells filled this run: ${permitCellsBackfilledFromDwr}`);
  console.log(`Allotment cells filled from matched permits: ${effectiveAllotmentFilledCells}`);
  console.log(`Allotment cells filled this run: ${allotmentFilledCells}`);
  console.log(`Allotment cells already matched: ${allotmentAlreadyMatchedCells}`);
  console.log(`Audit: ${AUDIT_JSON}`);
  console.log(`Permit nonmatches: ${NONMATCH_CSV}`);
  console.log(`Allotment audit: ${ALLOTMENT_AUDIT_CSV}`);
  console.log(`Backfill vs 2025 audit: ${BACKFILL_VS_2025_CSV}`);
}

main();
