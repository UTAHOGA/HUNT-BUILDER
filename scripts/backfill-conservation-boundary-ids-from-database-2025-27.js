const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const REPO_ROOT = path.resolve(__dirname, '..');

const TARGET_WORKBOOKS = [
  'processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx',
];
const LOOKUP_PATH = 'audits/2025_canonical_finalization/2025_27_conservation_hunt_code_boundary_lookup.csv';
const DATABASE_PATH = 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv';
const OUTPUT_AUDIT = 'audits/2025_canonical_finalization/2025_27_conservation_permits_staged_boundary_backfill_audit.csv';
const OUTPUT_SUMMARY = 'audits/2025_canonical_finalization/2025_27_conservation_permits_staged_boundary_backfill_summary.json';
const OUTPUT_LOCKED_MANIFEST = 'audits/2025_canonical_finalization/2025_27_conservation_permits_staged_boundary_backfill_locked_manifest.csv';
const BOUNDARY_DIR = 'processed_data/boundaries';

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
  const headers = rows.shift().map((value) => String(value || '').replace(/^\uFEFF/, '').trim());

  return rows
    .filter((candidate) => candidate.some((cell) => String(cell || '').trim()))
    .map((candidate) => Object.fromEntries(headers.map((header, index) => [header, candidate[index] ?? ''])));
}

function writeCsv(relativePath, headers, rows) {
  const lines = [headers, ...rows.map((row) => headers.map((header) => row[header] ?? ''))].map((row) =>
    row
      .map((value) => {
        const text = String(value ?? '');
        return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
      })
      .join(',')
  );
  fs.writeFileSync(abs(relativePath), `${lines.join('\r\n')}\r\n`, 'utf8');
}

function norm(value) {
  return String(value || '').trim();
}

function normCode(value) {
  return norm(value).toUpperCase();
}

function splitCodes(rawCode) {
  return normCode(rawCode)
    .split('|')
    .map((value) => normCode(value))
    .filter(Boolean);
}

function splitBoundaryIds(rawValue) {
  return norm(rawValue)
    .split(/[;,]/)
    .map((value) => norm(value))
    .filter(Boolean);
}

function normalizeTokenized(value) {
  return norm(value)
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[’'"]/g, '')
    .replace(/[()]/g, ' ')
    .replace(/\b(alternative|hunter\\s*'\\s*s\\s*choice|hunter's\\s*choice|late|early|mid|multiseason)\\b/g, (match) =>
      match.replace(/\s+/g, ' ')
    )
    .replace(/\\bconservation\\b/g, '')
    .replace(/\\bany legal weapon\\b/g, 'any legal weapon')
    .replace(/[^a-z0-9]+/gi, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

function tokenSet(value) {
  if (!value) return [];
  return normalizeTokenized(value)
    .split(' ')
    .filter(Boolean);
}

function overlapScore(lhs, rhs) {
  const a = new Set(tokenSet(lhs));
  const b = new Set(tokenSet(rhs));
  if (!a.size || !b.size) return 0;
  let score = 0;
  for (const token of a) {
    if (b.has(token)) score += 1;
  }
  return score;
}

function parseBoundaryReference(value) {
  return norm(value)
    .replace(/\\bsemi-colon\\b/gi, ';')
    .trim();
}

function safeArrayFromSet(valueSet) {
  return [...new Set([...valueSet])].sort((left, right) => {
    const leftNumeric = Number.parseInt(left, 10);
    const rightNumeric = Number.parseInt(right, 10);
    if (Number.isFinite(leftNumeric) && Number.isFinite(rightNumeric)) {
      return leftNumeric - rightNumeric;
    }
    return String(left).localeCompare(String(right));
  });
}

function readCsvMap(filePath, keyColumn) {
  const rows = parseCsv(fs.readFileSync(filePath, 'utf8'));
  const map = new Map();

  for (const row of rows) {
    const key = normCode(row[keyColumn]);
    if (!key) continue;
    map.set(key, { ...row });
  }

  return map;
}

function buildBoundaryReverseMap(lookupMap, databaseMap) {
  const map = new Map();
  const add = (boundaryId, code) => {
    const cleanId = norm(boundaryId);
    if (!cleanId) return;
    const codes = map.get(cleanId);
    if (codes) {
      codes.add(code);
    } else {
      map.set(cleanId, new Set([code]));
    }
  };

  for (const [code, row] of lookupMap.entries()) {
    const fromBoundary = splitBoundaryIds(row.boundary_id);
    const fromMembers = splitBoundaryIds(row.member_boundary_ids);
    const candidateBoundaryIds = [...fromBoundary, ...fromMembers];
    for (const boundaryId of candidateBoundaryIds) {
      add(boundaryId, code);
    }
  }

  for (const [code, row] of databaseMap.entries()) {
    const fromBoundary = splitBoundaryIds(row.boundary_id);
    for (const boundaryId of fromBoundary) {
      add(boundaryId, code);
    }
  }

  return map;
}

function scoreMatch(rowContext, code, candidate) {
  let score = 0;

  const dbSpecies = normalizeTokenized(candidate.species);
  const rowSpecies = normalizeTokenized(rowContext.species);
  const rowArea = normalizeTokenized(rowContext.area);
  const rowCondition = normalizeTokenized(rowContext.condition);
  const rowName = normalizeTokenized(rowContext.huntName);
  const dbName = normalizeTokenized(candidate.hunt_name);
  const dbSex = normalizeTokenized(candidate.sex_type);
  const dbWeapon = normalizeTokenized(candidate.weapon);
  const dbHuntType = normalizeTokenized(candidate.hunt_type);

  if (rowSpecies && dbSpecies && overlapScore(rowSpecies, dbSpecies) > 0) score += 2;
  if (dbSex && normalizeTokenized(rowContext.sex) && overlapScore(rowContext.sex, dbSex) > 0) score += 2;
  if (dbWeapon && rowCondition) {
    if (rowCondition.includes('hunter') && (dbWeapon.includes('any') || dbWeapon.includes('hunter'))) score += 1;
    if (overlapScore(rowCondition, dbWeapon) > 0) score += 1;
  }
  if (dbHuntType && rowCondition && overlapScore(rowCondition, dbHuntType) > 0) score += 1;
  if (rowArea && dbName) score += overlapScore(rowArea, dbName);
  if (rowName && dbName) score += overlapScore(rowName, dbName);

  const existingBoundary = rowContext.boundary;
  if (existingBoundary && candidate.boundaryIds.includes(existingBoundary)) {
    score += 2;
  }

  const candidateCode = normCode(code);
  if (candidateCode) score += 0.1 * candidateCode.length;
  return score;
}

function pickBestCandidate(candidates, rowContext, explicitWasPipe) {
  const scored = [];

  for (const candidateCode of candidates) {
    const lookupRow = lookupIndex.get(candidateCode) || {};
    const dbRow = databaseIndex.get(candidateCode) || {};
    const merged = {
      code: candidateCode,
      boundaryIds: safeArrayFromSet(new Set([...splitBoundaryIds(lookupRow.boundary_id), ...splitBoundaryIds(dbRow.boundary_id)])),
      hunt_name: norm(dbRow.hunt_name || lookupRow.database_hunt_name || ''),
      species: norm(dbRow.species || ''),
      sex_type: norm(dbRow.sex_type || ''),
      weapon: norm(dbRow.weapon || ''),
      hunt_type: norm(dbRow.hunt_type || ''),
    };

    const hasBoundary = merged.boundaryIds.length > 0;
    const score = scoreMatch(rowContext, candidateCode, merged);
    scored.push({ ...merged, score, source: hasBoundary ? 'LOOKUP_OR_DB' : 'NO_BOUNDARY', isExplicit: !explicitWasPipe });
  }

  if (!scored.length) return { status: 'UNRESOLVED_NO_CANDIDATES' };
  scored.sort((a, b) => b.score - a.score);
  const best = scored[0];

  if (scored.length === 1) {
    return {
      status: explicitWasPipe ? 'BEST_SINGLE_CANDIDATE' : 'SINGLE_CANDIDATE',
      picked: best,
      alternatives: scored,
    };
  }

  if (best.score > scored[1].score) {
    return {
      status: explicitWasPipe ? 'BEST_PIPED_SELECTION' : 'BEST_UNIQUE_SELECTION',
      picked: best,
      alternatives: scored,
    };
  }

  return {
    status: 'AMBIGUOUS',
    picked: best,
    alternatives: scored,
    topScore: best.score,
    topCount: scored.filter((item) => item.score === best.score).length,
  };
}

const lookupIndex = readCsvMap(abs(LOOKUP_PATH), 'hunt_code');
const databaseIndex = readCsvMap(abs(DATABASE_PATH), 'hunt_code');
const boundaryToCodes = buildBoundaryReverseMap(lookupIndex, databaseIndex);

function resolveFromBoundaryFallback(boundaryId, rowContext) {
  const candidates = safeArrayFromSet(boundaryToCodes.get(norm(boundaryId)) || new Set());
  if (!candidates.length) return { status: 'UNRESOLVED_NO_BOUNDARY_CANDIDATES' };
  if (candidates.length === 1) {
    const code = candidates[0];
    const dbRow = databaseIndex.get(code) || {};
    return {
      status: 'BOUNDARY_UNIQUE_MATCH',
      picked: {
        code,
        boundaryIds: splitBoundaryIds(dbRow.boundary_id).length ? splitBoundaryIds(dbRow.boundary_id) : splitBoundaryIds(norm(boundaryId)),
        hunt_name: norm(dbRow.hunt_name || ''),
        species: norm(dbRow.species || ''),
        sex_type: norm(dbRow.sex_type || ''),
        weapon: norm(dbRow.weapon || ''),
        hunt_type: norm(dbRow.hunt_type || ''),
      },
      source: 'BOUNDARY',
    };
  }

  const scoring = candidates.map((code) => {
    const dbRow = databaseIndex.get(code) || {};
    const merged = {
      code,
      boundaryIds: splitBoundaryIds(dbRow.boundary_id),
      hunt_name: norm(dbRow.hunt_name || ''),
      species: norm(dbRow.species || ''),
      sex_type: norm(dbRow.sex_type || ''),
      weapon: norm(dbRow.weapon || ''),
      hunt_type: norm(dbRow.hunt_type || ''),
    };
    const score = scoreMatch(rowContext, code, merged);
    return { code, score, ...merged };
  }).sort((a, b) => b.score - a.score);

  if (!scoring.length) return { status: 'UNRESOLVED_NO_BOUNDARY_CANDIDATES' };
  const best = scoring[0];
  const topScore = best.score;
  const tieCount = scoring.filter((r) => r.score === topScore).length;

  if (tieCount === 1) {
    return {
      status: 'BOUNDARY_NAME_SCORE_MATCH',
      picked: best,
      source: 'BOUNDARY',
      topScore,
      topCount: 1,
    };
  }

  return {
    status: 'BOUNDARY_AMBIGUOUS',
    candidates: scoring,
    picked: best,
    source: 'BOUNDARY',
    topScore,
    topCount: tieCount,
  };
}

function formatBoundarySource(candidate, chosenFromCodes, chosenBoundary) {
  const hasPath = candidate && (candidate.boundary_geojson_path || candidate.database_hunt_name || candidate.hunt_name);
  const boundaryPathFromLookup = candidate?.boundary_geojson_path;
  if (boundaryPathFromLookup) return boundaryPathFromLookup;

  if (!chosenBoundary || !chosenBoundary.length) return '';
  if (chosenBoundary.length > 1) return '';

  const safeBoundary = chosenBoundary[0];
  const guessedPath = path.join(BOUNDARY_DIR, `${safeBoundary}.geojson`);
  if (fs.existsSync(abs(guessedPath))) return guessedPath.replace(/\\/g, '/');
  if (lookupIndex.has(chosenBoundary[0])) {
    return parseBoundaryFromLookup(chosenBoundary[0]);
  }
  return '';
}

function parseBoundaryFromLookup(code) {
  const lookupRow = lookupIndex.get(code) || {};
  const direct = norm(lookupRow.boundary_geojson_path);
  return direct ? direct.replace(/\\/g, '/').replace(/\/+/g, '/') : '';
}

function deriveMapPathForBoundary(code, chosenBoundaryIds) {
  if (code) {
    const codePath = path.join(BOUNDARY_DIR, `${code}.geojson`);
    if (fs.existsSync(abs(codePath))) return codePath.replace(/\\/g, '/');
  }

  if (!chosenBoundaryIds.length) return '';
  if (chosenBoundaryIds.length === 1) {
    const directLookupPath = parseBoundaryFromLookup(code);
    if (directLookupPath) return directLookupPath;
    const guessedPath = path.join(BOUNDARY_DIR, `${chosenBoundaryIds[0]}.geojson`);
    if (fs.existsSync(abs(guessedPath))) return guessedPath.replace(/\\/g, '/');
    return '';
  }

  return '';
}

function processWorkbook(workbookPath) {
  const wb = XLSX.readFile(abs(workbookPath));
  const sheetName = wb.SheetNames[0];
  const sheet = wb.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
  if (!rows.length) throw new Error(`Workbook is empty: ${workbookPath}`);

  const header = rows[0];
  const idx = {
    no: header.indexOf('No.'),
    code: header.indexOf('HUNT CODE'),
    area: header.indexOf('Area'),
    species: header.indexOf('Species'),
    condition: header.indexOf('Condition'),
    sex: header.indexOf('SEX'),
    weapon: header.indexOf('WEAPON'),
    name: header.indexOf('HUNT NAME'),
    boundary: header.indexOf('BOUNDARY ID'),
    map: header.indexOf('MAP GEOJSON'),
  };

  const required = Object.entries(idx).filter(([, value]) => value < 0).map(([name]) => name);
  if (required.length) throw new Error(`Workbook missing required columns: ${required.join(', ')}`);

  const stats = {
    totalDataRows: 0,
    mappedBoundaryIds: 0,
    changedBoundaryRows: 0,
    changedCodeRows: 0,
    mappedFromLookup: 0,
    mappedFromDatabase: 0,
    mappedFromBoundaryFallback: 0,
    unresolved: 0,
    unchanged: 0,
    locked: 0,
  };

  const auditRows = [];
  const lockedRows = [];
  let resolvedCodeFromRow = '';

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    if (!row || !row.length) continue;

    const excelRowNumber = String(rowIndex + 1);
    const rowNo = norm(row[idx.no]);
    if (!rowNo) continue;
    stats.totalDataRows += 1;

    const existingCode = normCode(row[idx.code]);
    const existingBoundary = splitBoundaryIds(norm(row[idx.boundary])).join(';');
    const existingMap = norm(row[idx.map]);
    const rawCodes = splitCodes(existingCode);

    let candidateCodes = rawCodes;
    let codeSource = 'explicit';
    if (!candidateCodes.length && resolvedCodeFromRow) {
      candidateCodes = [resolvedCodeFromRow];
      codeSource = 'inherited_last_code';
    }

    const rowContext = {
      species: norm(row[idx.species]),
      area: norm(row[idx.area]),
      condition: norm(row[idx.condition]),
      sex: norm(row[idx.sex]),
      weapon: norm(row[idx.weapon]),
      huntName: norm(row[idx.name]),
      boundary: norm(row[idx.boundary]),
    };

    const rowBoundaryCandidates = splitBoundaryIds(row[idx.boundary]);
    let selected = null;
    let boundaryStatus = 'UNRESOLVED';
    let codeStatus = 'UNRESOLVED';
    let resolutionSource = '';
    let boundaryCandidateCodes = '';
    let beforeBoundary = existingBoundary;
    let afterBoundary = existingBoundary;
    let beforeCode = existingCode;
    let afterCode = existingCode;
    let beforeMap = existingMap;

    if (candidateCodes.length) {
      const explicitPipe = rawCodes.length > 1;
      const top = pickBestCandidate(candidateCodes, rowContext, explicitPipe);
      if (top && top.picked) {
        boundaryStatus = top.status;
        codeStatus = top.status.includes('AMBIGUOUS') ? 'AMBIGUOUS' : 'RESOLVED';
        resolutionSource = explicitPipe ? 'hunt_code_candidates' : 'hunt_code';

        const pick = top.picked;
        afterCode = pick.code;
        const uniqueBoundaries = safeArrayFromSet(new Set(pick.boundaryIds || []));

        if (rowBoundaryCandidates.length) {
          selected = {
            code: afterCode,
            boundaryIds: rowBoundaryCandidates,
            source: 'row_existing_boundary_preserved',
          };
          afterBoundary = existingBoundary;
          boundaryStatus = `${boundaryStatus}_PRESERVED_BOUNDARY`;
        } else if (!uniqueBoundaries.length) {
          selected = {
            code: afterCode,
            boundaryIds: rowBoundaryCandidates,
            source: 'row_existing_boundary',
          };
          boundaryStatus = `${boundaryStatus}_NO_REF_BOUNDARY`;
        } else if (uniqueBoundaries.length === 1) {
          selected = {
            code: afterCode,
            boundaryIds: uniqueBoundaries,
            source: 'code_map',
          };
          afterBoundary = uniqueBoundaries.join(';');
        } else if (uniqueBoundaries.length > 1) {
          selected = {
            code: afterCode,
            boundaryIds: uniqueBoundaries,
            source: 'code_map_multi',
          };
          afterBoundary = uniqueBoundaries.join(';');
        }
      } else {
        boundaryStatus = top?.status || 'UNRESOLVED';
      }
    }

    if (!selected && !rawCodes.length && rowBoundaryCandidates.length) {
      const fallback = resolveFromBoundaryFallback(rowBoundaryCandidates[0], rowContext);
      boundaryStatus = fallback.status;
      if (fallback.picked && fallback.topCount === 1) {
        selected = {
          code: normCode(fallback.picked.code),
          boundaryIds: safeArrayFromSet(new Set(fallback.picked.boundaryIds || rowBoundaryCandidates)),
          source: 'boundary_fallback',
        };
        afterCode = selected.code;
        afterBoundary = safeArrayFromSet(new Set(selected.boundaryIds)).join(';');
        codeStatus = 'RESOLVED_BY_BOUNDARY';
        resolutionSource = 'boundary_id';
        stats.mappedFromBoundaryFallback += 1;
      }
    }

    if (selected && !boundaryCandidateCodes) {
      boundaryCandidateCodes = selected.code;
    }

    const changedBoundary = beforeBoundary !== afterBoundary;
    const changedCode = beforeCode !== afterCode;

    if (changedCode) {
      row[idx.code] = afterCode;
      stats.changedCodeRows += 1;
    }

    if (changedBoundary) {
      row[idx.boundary] = afterBoundary;
      const mapCandidateBoundary = safeArrayFromSet(new Set(afterBoundary.split(';').map((value) => norm(value)).filter(Boolean)));
      const mapPath = deriveMapPathForBoundary(afterCode, mapCandidateBoundary);
      if (mapPath) {
        row[idx.map] = mapPath;
      }
      stats.changedBoundaryRows += 1;
    } else if (!norm(row[idx.map]) && beforeBoundary) {
      const mapCandidateBoundary = safeArrayFromSet(new Set(beforeBoundary.split(';').map((value) => norm(value)).filter(Boolean)));
      const mapPath = deriveMapPathForBoundary(afterCode || resolvedCodeFromRow, mapCandidateBoundary);
      if (mapPath) row[idx.map] = mapPath;
    }

    if (selected && selected.boundaryIds.length) {
      stats.mappedBoundaryIds += 1;
      const sourceType = selected.source;
      if (sourceType === 'code_map' || sourceType === 'code_map_multi') {
        if (lookupIndex.has(selected.code) || databaseIndex.has(selected.code)) {
          if (lookupIndex.has(selected.code)) stats.mappedFromLookup += 1;
          else stats.mappedFromDatabase += 1;
        }
      }
    }

    if (rowContext.boundary && (selected || changedBoundary)) {
      resolvedCodeFromRow = afterCode || resolvedCodeFromRow || existingCode;
    }

    let lockStatus = 'UNLOCKED';
    let lockReason = '';
    if (selected && (selected.boundaryIds.length || afterCode)) {
      stats.locked += 1;
      lockStatus = 'LOCKED';
      lockReason = 'row resolved via hunt code / boundary matching';
    } else {
      stats.unresolved += 1;
      lockReason = 'no unique resolution available';
    }

    if (changedBoundary || changedCode) {
      stats.locked += 0;
    } else {
      stats.unchanged += 1;
    }

    auditRows.push({
      target_workbook: workbookPath,
      worksheet: sheetName,
      excel_row_number: excelRowNumber,
      data_row_no: rowNo,
      source_no: row[idx.no] || '',
      selected_hunt_code: norm(row[idx.code]),
      input_hunt_code_status: codeStatus,
      boundary_audit_status: boundaryStatus,
      before_boundary_id: beforeBoundary,
      after_boundary_id: afterBoundary,
      boundary_candidate_codes: boundaryCandidateCodes,
      changed: String(changedBoundary || changedCode),
      map_geojson_before: beforeMap || existingMap || '',
      map_geojson_after: norm(row[idx.map]) || existingMap || '',
      resolution_source: resolutionSource || '',
      match_notes: lockReason,
      before_code: beforeCode,
      after_code: afterCode,
      locked: lockStatus,
    });

    lockedRows.push({
      target_workbook: workbookPath,
      excel_row_number: excelRowNumber,
      data_row_no: rowNo,
      source_no: row[idx.no] || '',
      selected_hunt_code: afterCode || existingCode,
      boundary_audit_status: boundaryStatus,
      before_boundary_id: beforeBoundary,
      after_boundary_id: afterBoundary,
      lock_status: lockStatus,
      lock_reason: lockReason,
    });
  }

  wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(rows);
  XLSX.writeFile(wb, abs(workbookPath));
  return { rows: rows.length - 1, auditRows, lockedRows, stats, workbookPath };
}

const allAuditRows = [];
const allLockedRows = [];
const workbookSummaries = [];

for (const workbook of TARGET_WORKBOOKS) {
  const result = processWorkbook(workbook);
  allAuditRows.push(
    ...result.auditRows.map((row) => ({
      ...row,
      target_workbook: path.relative(REPO_ROOT, abs(row.target_workbook)).replace(/\\/g, '/'),
    }))
  );
  allLockedRows.push(
    ...result.lockedRows.map((row) => ({
      ...row,
      target_workbook: path.relative(REPO_ROOT, abs(row.target_workbook)).replace(/\\/g, '/'),
    }))
  );
  workbookSummaries.push({
    target_workbook: workbook,
    ...result.stats,
    rows_written: String(result.rows),
  });
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
    'boundary_audit_status',
    'before_boundary_id',
    'after_boundary_id',
    'boundary_candidate_codes',
    'changed',
    'map_geojson_before',
    'map_geojson_after',
    'resolution_source',
    'match_notes',
    'before_code',
    'after_code',
    'locked',
  ].map((s) => String(s)),
  allAuditRows
);

writeCsv(
  OUTPUT_LOCKED_MANIFEST,
  [
    'target_workbook',
    'excel_row_number',
    'data_row_no',
    'source_no',
    'selected_hunt_code',
    'boundary_audit_status',
    'before_boundary_id',
    'after_boundary_id',
    'lock_status',
    'lock_reason',
  ],
  allLockedRows
);

const summary = {
  generated_at: new Date().toISOString(),
  target_workbooks: TARGET_WORKBOOKS,
  lookup_file: LOOKUP_PATH,
  database_file: DATABASE_PATH,
  total_workbook_rows: workbookSummaries.reduce((sum, wb) => sum + Number(wb.rows_written), 0),
  total_audit_rows: allAuditRows.length,
  target_summaries: workbookSummaries,
};
fs.writeFileSync(abs(OUTPUT_SUMMARY), `${JSON.stringify(summary, null, 2)}\n`, 'utf8');

let boundaryStatusCount = {};
for (const row of allAuditRows) {
  boundaryStatusCount[row.boundary_audit_status] = (boundaryStatusCount[row.boundary_audit_status] || 0) + 1;
}
console.log(
  JSON.stringify(
    {
      ok: true,
      output_audit: OUTPUT_AUDIT,
      output_summary: OUTPUT_SUMMARY,
      output_locked_manifest: OUTPUT_LOCKED_MANIFEST,
      boundary_status_breakdown: boundaryStatusCount,
    },
    null,
    2
  )
);
