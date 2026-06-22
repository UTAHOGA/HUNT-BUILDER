const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const ROOT = process.cwd();
const LIVE_PATH = path.join(ROOT, 'data_truth', 'conservation_permit_truth', '2025-27 Conservation Permits.xlsx');
const STAGED_PATH = path.join(
  ROOT,
  'processed_data',
  'hard_data_exports',
  'hunt_tables',
  '2026',
  'CLEAN_XLXS_STAGED',
  '2025-27 Conservation Permits.xlsx'
);
const AUDIT_DIR = path.join(ROOT, 'audits', '2025_canonical_finalization');
const AUDIT_CHANGES_PATH = path.join(AUDIT_DIR, '2025_27_conservation_live_reconcile_changes.csv');
const AUDIT_SUMMARY_PATH = path.join(AUDIT_DIR, '2025_27_conservation_live_reconcile_summary.json');

const OUTPUT_HEADER = [
  'No.',
  'HUNT CODE',
  'BOUNDARY ID',
  'MAP GEOJSON',
  'MAP STATUS',
  'SPECIES',
  'SEX',
  'HUNT NAME',
  'WEAPON',
  'VALUE',
  'ORGANIZATION',
  'PERMITS',
];

function asString(value) {
  if (value === undefined || value === null) return '';
  const text = String(value).trim();
  return text === 'undefined' ? '' : text;
}

function normalize(value) {
  return asString(value).toUpperCase().replace(/\s+/g, ' ').trim();
}

function parseHeader(headerRow) {
  const map = new Map();
  headerRow.forEach((header, idx) => {
    map.set(String(header || '').trim().toUpperCase(), idx);
  });
  return map;
}

function pickField(row, headerMap, ...aliases) {
  for (const alias of aliases) {
    const idx = headerMap.get(alias.toUpperCase());
    if (idx === undefined) continue;
    const value = asString(row[idx]);
    if (value) return value;
  }
  return '';
}

function readWorkbookMeta(filePath, fields) {
  const wb = XLSX.readFile(filePath);
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
  const header = rows[0] || [];
  const headerMap = parseHeader(header);

  const records = [];
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex] || [];
    const no = pickField(row, headerMap, 'No.', 'No');
    if (!no) continue;

    const rec = { no, rowIndex, rawRow: row };
    for (const [key, aliases] of Object.entries(fields)) {
      rec[key] = pickField(row, headerMap, ...aliases);
    }

    records.push(rec);
  }

  return { records, header, headerMap, workbook: wb };
}

function buildKey(rec) {
  return [
    normalize(rec.huntCode),
    normalize(rec.organization),
    normalize(rec.boundaryId),
    normalize(rec.species),
    normalize(rec.sex),
    normalize(rec.huntName),
    normalize(rec.weapon),
  ].join('|');
}

function buildMapStatus(rec) {
  if (!rec.boundaryId && !rec.mapGeojson) return '';
  if (rec.boundaryId && rec.boundaryId.includes(';')) return 'multi_code_mapped';
  if (rec.boundaryId || rec.mapGeojson) return 'single_code_mapped';
  return '';
}

function toOutputRow(liveRecord, stageRecord) {
  const row = new Array(OUTPUT_HEADER.length).fill('');
  const staged = stageRecord || {};

  OUTPUT_HEADER.forEach((header, idx) => {
    const key = normalize(header);
    if (key === 'NO.') {
      row[idx] = staged.no || liveRecord?.no || '';
      return;
    }

    if (header === 'HUNT CODE') {
      row[idx] = asString(staged.huntCode || (liveRecord ? liveRecord.huntCode : ''));
    } else if (header === 'BOUNDARY ID') {
      row[idx] = asString(staged.boundaryId || (liveRecord ? liveRecord.boundaryId : ''));
    } else if (header === 'MAP GEOJSON') {
      row[idx] = asString(staged.mapGeojson || (liveRecord ? liveRecord.mapGeojson : ''));
    } else if (header === 'MAP STATUS') {
      row[idx] =
        asString(liveRecord ? liveRecord.mapStatus : '') || buildMapStatus(staged) || '';
    } else if (header === 'SPECIES') {
      row[idx] = asString(staged.species || (liveRecord ? liveRecord.species : ''));
    } else if (header === 'SEX') {
      row[idx] = asString(staged.sex || (liveRecord ? liveRecord.sex : ''));
    } else if (header === 'HUNT NAME') {
      row[idx] = asString(staged.huntName || (liveRecord ? liveRecord.huntName : ''));
    } else if (header === 'WEAPON') {
      row[idx] = asString(staged.weapon || (liveRecord ? liveRecord.weapon : ''));
    } else if (header === 'VALUE') {
      row[idx] = asString(staged.value || (liveRecord ? liveRecord.value : ''));
    } else if (header === 'ORGANIZATION') {
      row[idx] = asString(staged.organization || (liveRecord ? liveRecord.organization : ''));
    } else if (header === 'PERMITS') {
      row[idx] = asString(liveRecord ? liveRecord.permits : '');
    }
  });

  return row;
}

function writeCsv(filePath, rows, headers) {
  const lines = [headers.join(',')];
  for (const row of rows) {
    const values = headers.map((h) => {
      const value = asString(row[h]);
      const escaped = value.replace(/\r/g, ' ').replace(/\n/g, ' ');
      return /[",\r\n]/.test(escaped) ? `"${escaped.replace(/"/g, '""')}"` : escaped;
    });
    lines.push(values.join(','));
  }
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`, 'utf8');
}

function main() {
  const liveFields = {
    no: ['No.'],
    huntCode: ['HUNT CODE'],
    boundaryId: ['BOUNDARY ID'],
    mapGeojson: ['MAP GEOJSON'],
    mapStatus: ['MAP STATUS'],
    species: ['SPECIES'],
    sex: ['SEX'],
    huntName: ['HUNT NAME'],
    weapon: ['WEAPON'],
    value: ['VALUE'],
    organization: ['ORGANIZATION'],
    permits: ['PERMITS'],
  };

  const stageFields = {
    no: ['No.'],
    huntCode: ['HUNT CODE'],
    boundaryId: ['BOUNDARY ID'],
    mapGeojson: ['MAP GEOJSON'],
    species: ['Species'],
    sex: ['SEX'],
    huntName: ['HUNT NAME'],
    weapon: ['WEAPON'],
    value: ['Value'],
    organization: ['Organization'],
    permits: ['PERMITS'],
  };

  const live = readWorkbookMeta(LIVE_PATH, liveFields);
  const staged = readWorkbookMeta(STAGED_PATH, stageFields);

  const liveByNo = new Map(live.records.map((row) => [row.no, row]));
  const liveByKey = new Map();
  const unmatchedLive = [];
  const matchedLiveNos = new Set();

  live.records.forEach((rec) => {
    const key = buildKey(rec);
    const bucket = liveByKey.get(key);
    if (bucket) {
      bucket.push(rec);
    } else {
      liveByKey.set(key, [rec]);
    }
  });

  const mergedRows = new Array(live.records.length);
  const outputChanges = [];
  const unmatchedStageNos = [];

  const usedLiveNo = new Set();
  for (const stageRec of staged.records) {
    let liveRec = liveByNo.get(stageRec.no);
    if (!liveRec || usedLiveNo.has(liveRec.no)) {
      const key = buildKey(stageRec);
      const candidates = liveByKey.get(key) || [];
      liveRec = candidates.find((c) => !usedLiveNo.has(c.no));
    }

    if (!liveRec) {
      unmatchedStageNos.push(stageRec.no);
      continue;
    }

    const out = toOutputRow(liveRec, stageRec);
    const outIndex = live.records.findIndex((r) => r.no === liveRec.no);
    mergedRows[outIndex] = out;
    usedLiveNo.add(liveRec.no);
    matchedLiveNos.add(liveRec.no);

    const liveOut = toOutputRow(liveRec, null);
    OUTPUT_HEADER.forEach((header, index) => {
      const before = asString(liveOut[index]);
      const after = asString(out[index]);
      if (before !== after) {
        outputChanges.push({
          action: 'updated',
          live_no: liveRec.no,
          staged_no: stageRec.no,
          field: header,
          old_value: before,
          new_value: after,
        });
      }
    });
  }

  // Drop unmatched live rows, but keep an explicit removal audit.
  for (let i = 0; i < live.records.length; i += 1) {
    if (!mergedRows[i]) {
      const rec = live.records[i];
      unmatchedLive.push(rec.no);
      outputChanges.push({
        action: 'dropped_live',
        live_no: rec.no,
        staged_no: '',
        field: 'row_status',
        old_value: 'present',
        new_value: 'removed_no_match_in_staged',
      });
    }
  }

  const serial = mergedRows.filter(Boolean);
  serial.forEach((row, idx) => {
    row[0] = String(idx + 1);
  });

  const outWb = live.workbook;
  const outWs = XLSX.utils.aoa_to_sheet([OUTPUT_HEADER, ...serial]);
  outWb.Sheets[outWb.SheetNames[0]] = outWs;
  XLSX.writeFile(outWb, LIVE_PATH);

  fs.mkdirSync(AUDIT_DIR, { recursive: true });
  writeCsv(AUDIT_CHANGES_PATH, outputChanges, ['action', 'live_no', 'staged_no', 'field', 'old_value', 'new_value']);

  const summary = {
    live_rows: live.records.length,
    staged_rows: staged.records.length,
    merged_rows: serial.length,
    matched_rows: matchedLiveNos.size,
    kept_live_rows: unmatchedLive.length,
    appended_stage_rows: 0,
    unmatched_stage_nos_count: unmatchedStageNos.length,
    unmatched_stage_nos: unmatchedStageNos.slice(0, 200),
    audit_changes: outputChanges.length,
  };
  fs.writeFileSync(AUDIT_SUMMARY_PATH, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');

  console.log(JSON.stringify(summary, null, 2));
  console.log(`audit: ${path.relative(ROOT, AUDIT_CHANGES_PATH)}`);
}

main();
