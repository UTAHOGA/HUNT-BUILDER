#!/usr/bin/env node
/* Build printable, site-aligned PDFs from the project's Utah source records. */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output', 'pdf', 'utah-source-records');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const RECORDS = [
  {
    source: 'docs/HARD_DATA_AND_RUNTIME_LINEAGE_2026-08-26.md',
    title: 'Utah Source Records',
    subtitle: 'Hard Data Recovery and Runtime Lineage - 2026',
    file: 'UOGA_Utah_Source_Records_Hard_Data_and_Runtime_Lineage_2026.pdf',
  },
  {
    source: 'docs/UTAH_DRAW_DESIGN_BASELINE.md',
    title: 'Utah Draw Design Baseline',
    subtitle: 'Official Draw System Routing and Engine Evaluation',
    file: 'UOGA_Utah_Draw_Design_Baseline_2026.pdf',
  },
  {
    source: 'docs/draw_results_truth_official_table_schema.md',
    title: 'Utah Draw Results Truth',
    subtitle: 'Official Table Shape and Canonical Record Schema',
    file: 'UOGA_Draw_Results_Truth_Official_Table_Schema.pdf',
  },
  {
    source: 'docs/yearly_draw_source_naming_and_scoring_policy.md',
    title: 'Utah Draw Source Policy',
    subtitle: 'Yearly Source Naming, Scoring, and Retention Rules',
    file: 'UOGA_Yearly_Draw_Source_Naming_and_Scoring_Policy.pdf',
  },
  {
    source: 'docs/utah_rules_sources.md',
    title: 'Utah Rules Sources',
    subtitle: 'Rule Assumptions and Mechanical Source Anchors',
    file: 'UOGA_Utah_Rules_Sources.pdf',
  },
];

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function inline(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2">$1</a>');
  return html;
}

function table(lines) {
  const rows = lines
    .filter((line, index) => index !== 1 || !/^\|?\s*:?-{3,}/.test(line.trim()))
    .map((line) => line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => inline(cell.trim())));
  if (!rows.length) return '';
  const [header, ...body] = rows;
  return `<div class="table-wrap"><table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join('')}</tr></thead><tbody>${body.map((cells) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const result = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith('```')) {
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) code.push(lines[index++]);
      index += 1;
      result.push(`<pre>${escapeHtml(code.join('\n'))}</pre>`);
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = Math.min(heading[1].length + 1, 5);
      result.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }
    if (/^\|.+\|\s*$/.test(line)) {
      const rows = [];
      while (index < lines.length && /^\|.+\|\s*$/.test(lines[index])) rows.push(lines[index++]);
      result.push(table(rows));
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) items.push(lines[index++].replace(/^[-*]\s+/, ''));
      result.push(`<ul>${items.map((item) => `<li>${inline(item)}</li>`).join('')}</ul>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) items.push(lines[index++].replace(/^\d+\.\s+/, ''));
      result.push(`<ol>${items.map((item) => `<li>${inline(item)}</li>`).join('')}</ol>`);
      continue;
    }
    if (/^[-*_]{3,}\s*$/.test(line)) {
      result.push('<hr>');
      index += 1;
      continue;
    }
    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(#{1,4}\s|```|\|.+\|\s*$|[-*]\s+|\d+\.\s+)/.test(lines[index])) paragraph.push(lines[index++].trim());
    result.push(`<p>${inline(paragraph.join(' '))}</p>`);
  }
  return result.join('\n');
}

function documentHtml(record, markdown) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(record.title)}</title>
<style>
  @page { size: letter; margin: 0.55in 0.52in 0.7in; }
  * { box-sizing: border-box; }
  body { color: #2c1d12; font-family: Arial, Helvetica, sans-serif; font-size: 9.35pt; line-height: 1.42; margin: 0; }
  .brand-bar { height: 9px; background: #dc7800; margin: -0.55in -0.52in 0.27in; }
  .brand { color: #d77300; font-size: 8pt; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; }
  h1 { color: #3a200d; font-size: 25pt; line-height: 1.03; margin: 5px 0 5px; letter-spacing: -.02em; }
  .subtitle { color: #775437; font-size: 11.5pt; font-weight: 600; margin: 0 0 13px; }
  .record-line { border-top: 1px solid #d88932; border-bottom: 1px solid #ead2b6; color: #795638; font-size: 7.7pt; line-height: 1.35; margin: 0 0 18px; padding: 7px 0; }
  .record-line p { margin: 0; overflow-wrap: anywhere; }
  .record-line p + p { margin-top: 3px; }
  .record-line strong { color: #5b361b; font-size: 7.1pt; letter-spacing: .05em; text-transform: uppercase; }
  h2 { break-after: avoid; background: #f5e7d4; border-left: 5px solid #dc7800; color: #3a200d; font-size: 15pt; margin: 21px 0 9px; padding: 5px 9px; }
  h3 { break-after: avoid; color: #8a4c0b; font-size: 11.5pt; margin: 15px 0 5px; text-transform: uppercase; letter-spacing: .025em; }
  h4, h5 { break-after: avoid; color: #50311b; font-size: 10pt; margin: 12px 0 4px; }
  p { margin: 0 0 8px; }
  ul, ol { margin: 5px 0 10px 20px; padding: 0; }
  li { margin: 2px 0; }
  code { background: #f4eadc; border: 1px solid #e6ccb0; border-radius: 2px; color: #713b0a; font-family: 'Courier New', monospace; font-size: .9em; padding: 1px 3px; }
  pre { background: #2a1a0f; border-left: 5px solid #dc7800; color: #f9ead8; font-family: 'Courier New', monospace; font-size: 7.6pt; line-height: 1.35; overflow-wrap: anywhere; padding: 9px 11px; white-space: pre-wrap; }
  .table-wrap { break-inside: avoid; margin: 9px 0 13px; overflow: hidden; }
  table { border-collapse: collapse; font-size: 7.55pt; width: 100%; }
  thead { display: table-header-group; }
  th { background: #dc7800; color: white; font-weight: 700; padding: 5px 6px; text-align: left; vertical-align: top; }
  td { border: 1px solid #e2a368; padding: 4px 6px; vertical-align: top; }
  tbody tr:nth-child(even) { background: #fbf3e8; }
  a { color: #9a5000; text-decoration: none; overflow-wrap: anywhere; }
  hr { border: 0; border-top: 1px solid #e2c4a1; margin: 15px 0; }
</style></head><body>
<div class="brand-bar"></div><div class="brand">U.O.G.A. Hunt Builder | Official Source Record</div>
<h1>${escapeHtml(record.title)}</h1><p class="subtitle">${escapeHtml(record.subtitle)}</p>
<div class="record-line"><p><strong>Rendered from</strong><br>${escapeHtml(record.source)}</p><p><strong>Record purpose</strong><br>Printable project source documentation. This export preserves the authored record; it does not create or alter source data.</p></div>
${markdownToHtml(markdown)}
</body></html>`;
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  if (!fs.existsSync(CHROME)) throw new Error(`Chrome executable not found: ${CHROME}`);
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  try {
    for (const record of RECORDS) {
      const sourcePath = path.join(ROOT, record.source);
      const source = fs.readFileSync(sourcePath, 'utf8');
      const page = await browser.newPage();
      await page.setContent(documentHtml(record, source), { waitUntil: 'load' });
      await page.pdf({
        path: path.join(OUTPUT_DIR, record.file),
        format: 'Letter',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate: '<div></div>',
        footerTemplate: '<div style="box-sizing:border-box;color:#8b6a4c;font-family:Arial,Helvetica,sans-serif;font-size:7.5pt;padding:0 0.52in;text-align:right;width:100%;">U.O.G.A. Hunt Builder - Utah source records - Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
        margin: { top: '0.55in', right: '0.52in', bottom: '0.7in', left: '0.52in' },
      });
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ output_dir: path.relative(ROOT, OUTPUT_DIR), files: RECORDS.map((record) => record.file) }, null, 2));
}

main().catch((error) => { console.error(error.stack || error.message); process.exit(1); });
