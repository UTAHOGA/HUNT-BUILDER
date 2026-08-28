#!/usr/bin/env node
/* Render the retained UtahDraws 2026 capture in a U.O.G.A.-colored DWR draw-results layout. */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const SOURCE_DIR = path.join(ROOT, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'json', 'draw_results', 'utahdraws_2026_20260826', 'utahdraws_2026', 'json');
const OUTPUT_DIR = path.resolve(ROOT, process.env.UTAH_DRAWS_PDF_OUTPUT_DIR || path.join('output', 'pdf', 'utahdraws-2026-source-records'));
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

function esc(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function value(input) {
  if (input === null) return 'null';
  if (input === undefined) return '';
  return String(input);
}

function hash(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function outputName(sourceName) {
  return `UOGA_UTAH_DRAWS_2026_${sourceName.replace(/\.json$/i, '').replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '')}.pdf`;
}

function sourceLabel(sourceName) {
  return sourceName.replace(/^2026_/, '').replace(/\.json$/i, '').replaceAll('_', ' ');
}

function pointValue(row) {
  const point = row.PreferencePoint ?? row.Point;
  return Number.isFinite(Number(point)) ? Number(point) : 0;
}

function pointLabel(point) {
  return Number.isInteger(point) ? String(point) : String(point).replace(/\.0+$/, '');
}

function successRatio(applicants, successes) {
  if (!applicants || !successes) return 'N/A';
  return `1 in ${(applicants / successes).toFixed(1)}`;
}

function audienceRows(hunt, isYouth) {
  const lanes = new Map();
  for (const row of hunt.OddsList || []) {
    if (Boolean(row.IsYouth) !== isYouth) continue;
    lanes.set(`${row.ResidencyTypeID}|${pointValue(row)}`, row);
  }
  return lanes;
}

function rowFor(lanes, residencyId, point) {
  return lanes.get(`${residencyId}|${point}`) || null;
}

function metrics(row) {
  if (!row) return ['0', '0', '0', '0', 'N/A'];
  const applicants = Number(row.ParticipantCount || 0);
  const max = Number(row.SuccessfulByMaxPointRoundCount || 0);
  const regular = Number(row.SuccessfulByRegularRoundCount || 0);
  const total = Number(row.AllChoicesSuccessfulCount ?? (max + regular));
  return [String(applicants), String(max), String(regular), String(total), successRatio(applicants, total)];
}

function totals(rows) {
  const sum = (field) => rows.reduce((total, row) => total + Number(row?.[field] || 0), 0);
  const applicants = sum('ParticipantCount');
  const max = sum('SuccessfulByMaxPointRoundCount');
  const regular = sum('SuccessfulByRegularRoundCount');
  const total = rows.reduce((count, row) => count + Number(row?.AllChoicesSuccessfulCount ?? (Number(row?.SuccessfulByMaxPointRoundCount || 0) + Number(row?.SuccessfulByRegularRoundCount || 0))), 0);
  return [String(applicants), String(max), String(regular), String(total), successRatio(applicants, total)];
}

function panel(header, pointName, rows, residencyId, points) {
  const laneRows = points.map((point) => rowFor(rows, residencyId, point));
  return `<section class="panel"><h3>${header}</h3><table><thead><tr><th>${pointName}</th><th>Total<br>Eligible<br>Applicants</th><th>Max-point<br># Permits</th><th>Regular<br># Permits</th><th>Total<br># Permits</th><th>Success<br>Ratio</th></tr></thead><tbody>${points.map((point) => `<tr><td>${pointLabel(point)}</td>${metrics(rowFor(rows, residencyId, point)).map((cell) => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}<tr class="totals"><td>Totals</td>${totals(laneRows).map((cell) => `<td>${esc(cell)}</td>`).join('')}</tr></tbody></table></section>`;
}

function huntPage(hunt, sourceName, isYouth) {
  const rows = audienceRows(hunt, isYouth);
  const points = [...new Set([...rows.values()].map(pointValue))].sort((a, b) => b - a);
  const pointName = hunt.IsBonusPoint ? 'Bonus<br>Points' : 'Preference<br>Points';
  const audience = isYouth ? 'Youth Applicants' : 'All Applicants';
  const species = hunt.SpeciesSubtypeName || hunt.HuntCategoryName || sourceLabel(sourceName);
  const season = (hunt.SeasonWeapons || []).map((entry) => entry.WeaponName).filter(Boolean).join(' / ');
  const headline = [hunt.HuntCode, hunt.HuntName, season].filter(Boolean).join(' - ');
  return `<section class="hunt-page"><div class="report-header"><div class="wordmark">U.O.G.A.<span>HUNT BUILDER</span></div><div class="report-title">2026 UtahDraws Draw Results</div><div class="report-meta">UTAH SOURCE RECORD<br>CAPTURED 08/26/2026</div></div><div class="species"><strong>Species:</strong> ${esc(species)} - ${audience}</div><div class="hunt-name"><strong>Hunt:</strong> ${esc(headline || `Hunt ID ${value(hunt.HuntID)}`)}</div><div class="panels">${panel('Resident Applicants', pointName, rows, 1, points)}${panel('Nonresident Applicants', pointName, rows, 2, points)}</div><div class="source-note">Retained UtahDraws source rendering. Point rows are shown exactly by residency and applicant audience; source file and output integrity are listed in the companion manifest.</div></section>`;
}

function supplementTable(headers, rows) {
  return `<table class="supplement-table"><thead><tr>${headers.map((header) => `<th>${esc(header)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${esc(value(cell))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function supplementPages(payload, sourceName) {
  return Object.entries(payload.Data || {}).map(([key, sourceRows]) => {
    const rows = Array.isArray(sourceRows) ? sourceRows : [sourceRows];
    const headers = [...new Set(rows.flatMap((row) => row && typeof row === 'object' ? Object.keys(row) : ['Value']))];
    const tableRows = rows.map((row) => headers.map((header) => row && typeof row === 'object' ? row[header] : row));
    return `<section class="hunt-page supplement-page"><div class="report-header"><div class="wordmark">U.O.G.A.<span>HUNT BUILDER</span></div><div class="report-title">2026 UtahDraws Draw Results</div><div class="report-meta">UTAH SOURCE RECORD<br>${esc(sourceName)}</div></div><div class="species"><strong>Source record:</strong> ${esc(key)}</div><div class="hunt-name"><strong>Draw-odds endpoint metadata</strong></div>${supplementTable(headers, tableRows)}<div class="source-note">Retained UtahDraws source rendering. This endpoint metadata is not a hunt probability table.</div></section>`;
  }).join('');
}

function documentHtml({ sourceName, payload }) {
  const hunts = Array.isArray(payload.Data) ? payload.Data : [];
  const pages = hunts.length ? hunts.flatMap((hunt) => [...new Set((hunt.OddsList || []).map((row) => Boolean(row.IsYouth)))].map((state) => huntPage(hunt, sourceName, state))).join('') : supplementPages(payload, sourceName);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(sourceLabel(sourceName))}</title><style>
    @page { size: letter; margin: .42in .42in .46in; }
    * { box-sizing: border-box; }
    body { color: #352115; font-family: Arial, Helvetica, sans-serif; margin: 0; }
    .hunt-page { break-after: avoid; break-before: page; height: 9.35in; overflow: hidden; }
    .hunt-page:first-child { break-before: auto; }
    .report-header { align-items: end; border-top: 2px solid #dc7800; display: grid; gap: 12px; grid-template-columns: 118px 1fr 150px; padding: 8px 0 5px; }
    .wordmark { color: #3a200d; font-size: 20pt; font-weight: 900; letter-spacing: -.04em; line-height: .82; }
    .wordmark span { color: #dc7800; display: block; font-size: 6.5pt; letter-spacing: .13em; margin-left: 1px; }
    .report-title { color: #3a200d; font-size: 16pt; font-weight: 500; text-align: center; }
    .report-meta { color: #795638; font-size: 6.2pt; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; text-align: right; }
    .species { border-top: 1px solid #dc7800; color: #3a200d; font-size: 10.5pt; margin-top: 3px; padding-top: 5px; }
    .hunt-name { color: #3a200d; font-size: 10.5pt; margin: 5px 0 11px; overflow-wrap: anywhere; }
    .panels { display: grid; gap: 0; grid-template-columns: 1fr 1fr; }
    .panel { border: 2px solid #3a200d; }
    .panel + .panel { border-left: 0; }
    h3 { color: #3a200d; font-size: 10.5pt; margin: 0; padding: 4px 0 5px; text-align: center; }
    table { border-collapse: collapse; table-layout: fixed; width: 100%; }
    th { color: #7d4305; font-size: 7.2pt; font-weight: 800; padding: 3px 2px 6px; text-align: center; vertical-align: bottom; }
    td { border: 1px solid #7c5030; font-size: 7.55pt; padding: 1.7px 3px; text-align: right; }
    td:first-child { text-align: center; }
    .totals td { border-top: 2px solid #3a200d; font-weight: 800; }
    .totals td:first-child { color: #3a200d; font-size: 8.5pt; }
    .source-note { border-top: 1px solid #dc7800; color: #795638; font-size: 6.1pt; line-height: 1.25; margin-top: 9px; padding-top: 4px; }
    .supplement-page { height: 9.35in; }
    .supplement-table { border: 2px solid #3a200d; margin-top: 8px; table-layout: auto; }
    .supplement-table th { background: #f5e7d4; border: 1px solid #7c5030; font-size: 7pt; padding: 4px; }
    .supplement-table td { font-size: 7pt; text-align: left; }
  </style></head><body>${pages}</body></html>`;
}

async function main() {
  if (!fs.existsSync(SOURCE_DIR)) throw new Error(`Source directory not found: ${SOURCE_DIR}`);
  if (!fs.existsSync(CHROME)) throw new Error(`Chrome executable not found: ${CHROME}`);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const files = fs.readdirSync(SOURCE_DIR).filter((name) => name.endsWith('.json')).sort();
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const manifest = [];
  try {
    for (const sourceName of files) {
      const sourcePath = path.join(SOURCE_DIR, sourceName);
      const payload = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
      const hunts = Array.isArray(payload.Data) ? payload.Data : [];
      const oddsCount = hunts.reduce((total, hunt) => total + (hunt.OddsList || []).length, 0);
      const outputFile = outputName(sourceName);
      const outputPath = path.join(OUTPUT_DIR, outputFile);
      const page = await browser.newPage();
      await page.setContent(documentHtml({ sourceName, payload }), { waitUntil: 'load' });
      await page.pdf({ path: outputPath, format: 'Letter', printBackground: true, displayHeaderFooter: true, headerTemplate: '<div></div>', footerTemplate: '<div style="box-sizing:border-box;color:#795638;font-family:Arial,Helvetica,sans-serif;font-size:6.5pt;padding:0 .42in;text-align:right;width:100%;">U.O.G.A. Hunt Builder - Retained UtahDraws Draw Results - Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>', margin: { top: '.42in', right: '.42in', bottom: '.46in', left: '.42in' } });
      await page.close();
      manifest.push({ source_file: sourceName, source_sha256: hash(sourcePath), source_bytes: fs.statSync(sourcePath).size, output_file: outputFile, output_sha256: hash(outputPath), output_bytes: fs.statSync(outputPath).size, hunt_records: hunts.length, odds_records: oddsCount });
      console.log(`${sourceName} -> ${outputFile}`);
    }
  } finally { await browser.close(); }
  const totals = manifest.reduce((acc, row) => ({ source_bytes: acc.source_bytes + row.source_bytes, output_bytes: acc.output_bytes + row.output_bytes, hunt_records: acc.hunt_records + row.hunt_records, odds_records: acc.odds_records + row.odds_records }), { source_bytes: 0, output_bytes: 0, hunt_records: 0, odds_records: 0 });
  const manifestPath = path.join(OUTPUT_DIR, 'utahdraws_2026_source_record_pdf_manifest.json');
  fs.writeFileSync(manifestPath, `${JSON.stringify({ generated_at_utc: new Date().toISOString(), layout: 'UOGA-colored DWR draw-results mirror', source_directory: path.relative(ROOT, SOURCE_DIR), output_directory: path.relative(ROOT, OUTPUT_DIR), file_count: manifest.length, totals, files: manifest }, null, 2)}\n`);
  console.log(JSON.stringify({ output_dir: path.relative(ROOT, OUTPUT_DIR), manifest: path.relative(ROOT, manifestPath), file_count: manifest.length, totals }, null, 2));
}

main().catch((error) => { console.error(error.stack || error.message); process.exit(1); });
