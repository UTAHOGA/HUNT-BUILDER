const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const REPO_ROOT = path.resolve(__dirname, '..');

const ARCGIS_FILE = 'pipeline/RAW/hunt_unit_database/2026/arcgis/udwr_huntnumber_boundary_table1.json';
const HUNT_CODE_AUDIT = 'audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv';
const OUTPUT_AUDIT = 'audits/2025_canonical_finalization/2025_27_conservation_permits_staged_boundary_backfill_audit.csv';
const OUTPUT_SUMMARY = 'audits/2025_canonical_finalization/2025_27_conservation_permits_staged_boundary_backfill_summary.json';

const TARGET_WORKBOOKS = [
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx',
];

function abs(relativePath) {
  return path.join(REPO_ROOT, relativePath);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = '';
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (quoted) {
      if (char === '"' && next === '"') {
        value += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        value += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ',') {
      row.push(value);
      value = '';
    } else if (char === '\n') {
      row.push(value);
      rows.push(row);
      row = [];
      value = '';
    } else if (char !== '\r') {
      value += char;
    }
  }

  if (value.length || row.length) {
    row.push(value);
    rows.push(row);
  }

  if (!rows.length) return [];
  const headers = rows.shift().map((value) => String(value || '').trim().replace(/^\uFEFF/, ''));

  return rows
    .filter((r) => r.some((cell) => String(cell || '').trim()))
    .map((r) => Object.fromEntries(headers.map((header, index) => [header, r[index] ?? ''])));
}

function writeCsv(relativePath, headers, rows) {
  const lines = [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ''))].map((row) =>
    row.map((cell) => {
      const text = String(cell ?? '');
      return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }).join(',')
  );
  fs.writeFileSync(abs(relativePath), `${lines.join('\r\n')}\r\n`, 'utf8');
}

function clean(value) {
  return String(value || '').trim();
}

function normalizeHuntCode(value) {
  return clean(value).toUpperCase();
}

function splitBoundaryIds(value) {
  return clean(value)
    .split(/[,;]/)
    .map((item) => clean(item))
    .filter(Boolean);
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10));
}

function loadBoundaryMap() {
  const raw = JSON.parse(fs.readFileSync(abs(ARCGIS_FILE), 'utf8'));
  const features = raw?.features || [];
  const map = new Map();

  for (const feature of features) {
    const attrs = feature?.attributes || {};
    const code = normalizeHuntCode(attrs.HUNT_NUMBER);
    const boundaryId = clean(attrs.BOUNDARYID);
    if (!code || !boundaryId) continue;

    const current = map.get(code) || new Set();
    current.add(boundaryId);
    map.set(code, current);
  }

  const normalized = {};
  for (const [code, ids] of map.entries()) {
    normalized[code] = uniqueSorted([...ids]);
  }
  return normalized;
}

function loadHuntCodeAudit() {
  const rows = parseCsv(fs.readFileSync(abs(HUNT_CODE_AUDIT), 'utf8'));
  const bySourceNo = new Map();
  const byWorkbookRow = new Map();

  for (const row of rows) {
    const sourceNo = clean(row.source_no);
    const xlsxRow = clean(row.xlsx_row);
    const payload = {
      source_no: sourceNo,
      xlsx_row: xlsxRow,
      selected_hunt_code: clean(row.selected_hunt_code),
      possible_hunt_codes: clean(row.possible_hunt_codes),
      status: clean(row.join_type),
      note: clean(row.match_notes),
    };

    if (sourceNo) bySourceNo.set(sourceNo, payload);
    if (xlsxRow) byWorkbookRow.set(xlsxRow, payload);
  }

  return { bySourceNo, byWorkbookRow };
}

function mapBoundaryForCodes(codes, boundaryByCode) {
  const normalizedCodes = codes.filter(Boolean).map(normalizeHuntCode);

  if (!normalizedCodes.length) {
    return {
      status: 'NO_HUNT_CODE',
      boundaryIds: [],
      notes: 'No hunt code candidates available for this row.',
      exactCodeBoundaryAgreement: false,
    };
  }

  const codeToIds = normalizedCodes.map((code) => ({ code, ids: splitBoundaryIds(boundaryByCode[code] ? boundaryByCode[code].join(',') : '') }));
  const allMapped = codeToIds.every((entry) => entry.ids.length > 0);
  const codeSignature = [...new Set(codeToIds.map((entry) => entry.ids.join('|')).filter(Boolean))];

  if (allMapped && codeSignature.length === 1) {
    const boundaryIds = codeToIds[0].ids;
    const status = boundaryIds.length === 1 ? 'MAPPED_SINGLE' : 'MAPPED_MULTI_BOUNDARY_IDS';
    return {
      status,
      boundaryIds,
      notes:
        boundaryIds.length === 1
          ? `Single boundary_id ${boundaryIds[0]} from all matching hunt code(s).`
          : `All matching hunt codes map to the same ${boundaryIds.length} boundary IDs.`,
      exactCodeBoundaryAgreement: true,
      inputCodes: normalizedCodes,
    };
  }

  if (allMapped && codeSignature.length > 1) {
    const unionIds = uniqueSorted(normalizedCodes.flatMap((code) => splitBoundaryIds(boundaryByCode[code]?.join(',') || '')));
    return {
      status: 'MAPPED_CODE_DISAGREEMENT',
      boundaryIds: unionIds,
      notes: `Hunt code boundary sets differ: ${JSON.stringify(codeToIds)}.`,
      exactCodeBoundaryAgreement: false,
      inputCodes: normalizedCodes,
    };
  }

  const partialUnion = uniqueSorted(normalizedCodes.flatMap((code) => splitBoundaryIds(boundaryByCode[code]?.join(',') || '')));
  if (partialUnion.length) {
    return {
      status: 'PARTIAL_MAPPING',
      boundaryIds: partialUnion,
      notes: 'At least one code is unmapped; used union of mapped hunt-code boundary IDs.',
      exactCodeBoundaryAgreement: false,
      inputCodes: normalizedCodes,
    };
  }

  return {
    status: 'UNMAPPED',
    boundaryIds: [],
    notes: `No ArcGIS mapping found for codes: ${normalizedCodes.join(', ')}`,
    exactCodeBoundaryAgreement: false,
    inputCodes: normalizedCodes,
  };
}

function ensureColumn(headers, rows, columnName, fallbackIndex) {
  let idx = headers.indexOf(columnName);
  if (idx >= 0) return { idx, inserted: false };

  const insertIdx = fallbackIndex >= 0 ? fallbackIndex : headers.length;
  headers.splice(insertIdx, 0, columnName);
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    let row = rows[rowIndex];
    if (!Array.isArray(row)) {
      row = [];
      rows[rowIndex] = row;
    }
    row.splice(insertIdx, 0, '');
  }
  return { idx: insertIdx, inserted: true };
}

function processWorkbook(workbookRelativePath, boundaryByCode, auditMaps) {
  const workbookPath = abs(workbookRelativePath);
  const wb = XLSX.readFile(workbookPath);
  const sheetName = wb.SheetNames[0];
  const rows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1, defval: '' });

  const headers = rows[0];
  const noCol = headers.indexOf('No.');
  const huntCodeFallback = noCol >= 0 ? noCol + 1 : 0;
  const huntCode = ensureColumn(headers, rows, 'HUNT CODE', huntCodeFallback);
  const huntCodeColIdx = headers.indexOf('HUNT CODE');
  const boundaryCol = ensureColumn(headers, rows, 'BOUNDARY ID', huntCodeColIdx + 1);
  const boundaryColIdx = headers.indexOf('BOUNDARY ID');

  const auditRows = [];
  const summary = {
    totalDataRows: 0,
    mappedSingleBoundary: 0,
    mappedMultiBoundary: 0,
    mappedPartially: 0,
    mappedConflict: 0,
    unmapped: 0,
    unchanged: 0,
    huntCodesAdded: 0,
    insertedHuntCodeColumn: huntCode.inserted ? 1 : 0,
    insertedBoundaryColumn: boundaryCol.inserted ? 1 : 0,
  };

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    if (!row || !row.length) continue;
    summary.totalDataRows += 1;

    const rowNo = clean(row[noCol]);
    const sourceKey = rowNo || String(rowIndex + 1);
    const workbookRowNo = String(rowIndex + 1);
    const auditRow = auditMaps.bySourceNo.get(sourceKey) || auditMaps.byWorkbookRow.get(workbookRowNo);

    const existingCodeCell = clean(row[huntCodeColIdx]);
    const selectedCodes = clean(
      auditRow?.selected_hunt_code || auditRow?.possible_hunt_codes || existingCodeCell || ''
    );
    if (!existingCodeCell && selectedCodes) {
      row[huntCodeColIdx] = selectedCodes;
      summary.huntCodesAdded += 1;
    }

    const usedCodes = selectedCodes.split('|').map(clean).filter(Boolean);
    const lookup = mapBoundaryForCodes(usedCodes, boundaryByCode);
    const beforeBoundaryId = clean(row[boundaryColIdx]);
    const afterBoundaryId = lookup.boundaryIds.join(';');
    const didChange = beforeBoundaryId !== afterBoundaryId;
    if (didChange) {
      row[boundaryColIdx] = afterBoundaryId;
    } else {
      summary.unchanged += 1;
    }

    switch (lookup.status) {
      case 'MAPPED_SINGLE':
        summary.mappedSingleBoundary += 1;
        break;
      case 'MAPPED_MULTI_BOUNDARY_IDS':
        summary.mappedMultiBoundary += 1;
        break;
      case 'PARTIAL_MAPPING':
        summary.mappedPartially += 1;
        break;
      case 'MAPPED_CODE_DISAGREEMENT':
        summary.mappedConflict += 1;
        break;
      default:
        summary.unmapped += 1;
        break;
    }

    auditRows.push({
      target_workbook: path.basename(workbookPath),
      worksheet: sheetName,
      excel_row_number: String(rowIndex + 1),
      data_row_no: rowNo,
      source_no: auditRow?.source_no || '',
      selected_hunt_code: selectedCodes,
      input_hunt_code_status: auditRow?.status || '',
      join_note: auditRow?.note || '',
      before_boundary_id: beforeBoundaryId,
      after_boundary_id: afterBoundaryId,
      boundary_audit_status: lookup.status,
      boundary_notes: lookup.notes,
      boundary_id_count: String(lookup.boundaryIds.length),
      boundary_candidate_codes: lookup.inputCodes?.join('|') || selectedCodes,
      boundary_boundary_agreement: String(lookup.exactCodeBoundaryAgreement),
      changed: String(didChange),
    });
  }

  const outputPath = abs(workbookRelativePath);
  wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
  XLSX.writeFile(wb, outputPath);

  return {
    auditRows,
    summary,
    workbookPath: workbookRelativePath,
  };
}

function run() {
  const boundaryByCode = loadBoundaryMap();
  const { bySourceNo, byWorkbookRow } = loadHuntCodeAudit();
  const allAuditRows = [];
  const allSummary = [];
  let totalRowsUpdated = 0;

  for (const workbook of TARGET_WORKBOOKS) {
    const result = processWorkbook(workbook, boundaryByCode, { bySourceNo, byWorkbookRow });
    totalRowsUpdated += result.auditRows.length;
    allSummary.push({
      target_workbook: workbook,
      ...result.summary,
      unmatched_rows: String(result.summary.unmapped),
    });
    allAuditRows.push(
      ...result.auditRows.map((row) => ({
        ...row,
        target_workbook: path.relative(REPO_ROOT, abs(workbook)).replace(/\\/g, '/'),
      }))
    );
  }

  writeCsv(
    OUTPUT_AUDIT,
    [
      'target_workbook',
      'worksheet',
      'excel_row_number',
      'data_row_no',
      'source_no',
      'selected_hunt_code',
      'input_hunt_code_status',
      'join_note',
      'before_boundary_id',
      'after_boundary_id',
      'boundary_audit_status',
      'boundary_notes',
      'boundary_id_count',
      'boundary_candidate_codes',
      'boundary_boundary_agreement',
      'changed',
    ],
    allAuditRows
  );

  const summary = {
    generated_at: new Date().toISOString(),
    target_workbooks: TARGET_WORKBOOKS,
    arcgis_file: ARCGIS_FILE,
    hunt_code_audit_file: HUNT_CODE_AUDIT,
    total_audit_rows: allAuditRows.length,
    rows_written: totalRowsUpdated,
    boundary_code_map_size: Object.keys(boundaryByCode).length,
    target_summaries: allSummary,
  };
  fs.writeFileSync(abs(OUTPUT_SUMMARY), `${JSON.stringify(summary, null, 2)}\n`, 'utf8');

  console.log(JSON.stringify({
    ok: true,
    updated_rows: totalRowsUpdated,
    target_workbooks: TARGET_WORKBOOKS,
    output_audit: OUTPUT_AUDIT,
    output_summary: OUTPUT_SUMMARY,
  }, null, 2));
}

run();
