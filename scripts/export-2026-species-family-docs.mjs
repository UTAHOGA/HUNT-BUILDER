import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const YEAR = 2026;
const MODEL_YEAR = 2027;
const RAW_PDF_DIR = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "raw_pdfs",
  "2026_PERMITS=2027_MODEL",
);
const CANONICAL = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "canonical_yearly",
  "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
);
const RAW_PDF_CODE_SOURCES = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "raw_truth_pdf_2026_hunt_code_sources.csv",
);
const ANTLERLESS_PDF_CODE_SOURCES = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "antlerless_pdf_2026_hunt_code_sources.csv",
);
const OUT_ROOT = path.join(REPO_ROOT, "outputs", "2026_PERMITS=2027_MODEL_species_family_docs");
const PDF_OUT_DIR = path.join(OUT_ROOT, "pdf");
const XLSX_OUT_DIR = path.join(OUT_ROOT, "xlsx");
const PREVIEW_DIR = path.join(OUT_ROOT, "previews");
const MANIFEST_CSV = path.join(OUT_ROOT, "2026_PERMITS=2027_MODEL_species_family_manifest.csv");
const MANIFEST_JSON = path.join(OUT_ROOT, "2026_PERMITS=2027_MODEL_species_family_manifest.json");
const INDEX_XLSX = path.join(OUT_ROOT, "2026_PERMITS=2027_MODEL__SPECIES_FAMILY_INDEX.xlsx");

const NUMERIC_COLUMNS = new Set([
  "actual_draw_year",
  "model_target_year",
  "pdf_page",
  "points",
  "eligible_applicants",
  "bonus_permits",
  "regular_permits",
  "total_permits",
  "p_draw",
  "p_draw_percent",
  "boundary_id",
  "permits_2026_res",
  "permits_2026_nr",
  "permits_2026_total",
]);

const ROLLUP_COLUMNS = [
  "actual_draw_year",
  "model_target_year",
  "hunt_code",
  "hunt_name",
  "species",
  "sex_type",
  "weapon",
  "hunt_type",
  "draw_design",
  "season",
  "boundary_id",
  "permits_2026_res",
  "permits_2026_nr",
  "permits_2026_total",
  "record_type",
  "source_file",
];

function clean(value) {
  return value == null ? "" : String(value).trim();
}

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function toCsv(rows) {
  return rows.map((row) => row.map(csvEscape).join(",")).join("\n") + "\n";
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += char;
  }

  if (field.length > 0 || row.length > 0) row.push(field);
  if (row.length) rows.push(row);

  const nonEmptyRows = rows.filter((entry) => entry.some((value) => value !== ""));
  const [header, ...body] = nonEmptyRows;
  return {
    header,
    rows: body.map((values) => Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""]))),
  };
}

function maybeNumber(column, value) {
  const text = clean(value).replaceAll(",", "");
  if (!NUMERIC_COLUMNS.has(column) || text === "") return clean(value);
  const number = Number(text);
  return Number.isFinite(number) ? number : clean(value);
}

function countBy(rows, column) {
  const counts = new Map();
  for (const row of rows) {
    const value = clean(row[column]) || "(blank)";
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function applyTitleStyle(range) {
  range.format = {
    fill: "#143642",
    font: { bold: true, color: "#FFFFFF", size: 15 },
  };
}

function applyHeaderStyle(range) {
  range.format = {
    fill: "#1F4E5F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
}

function writeTable(sheet, anchorRow, anchorCol, header, rows, { lightBorders = true } = {}) {
  const matrix = [header, ...rows];
  const range = sheet.getRangeByIndexes(anchorRow, anchorCol, matrix.length, header.length);
  range.values = matrix;
  applyHeaderStyle(sheet.getRangeByIndexes(anchorRow, anchorCol, 1, header.length));
  if (lightBorders && matrix.length <= 5000) {
    range.format.borders = { preset: "all", style: "thin", color: "#D9E2E7" };
  }
  return range;
}

function setColumnWidths(sheet, widths) {
  widths.forEach((width, index) => {
    if (!width) return;
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width;
  });
}

function titleFromPdfName(name) {
  return name
    .replace(/\.pdf$/i, "")
    .replace(/^2026_PERMITS(?:=|_)2027_MODEL__/, "")
    .replaceAll("_", " ");
}

function sortCode(a, b) {
  const prefixCompare = a.slice(0, 2).localeCompare(b.slice(0, 2));
  if (prefixCompare !== 0) return prefixCompare;
  const numberA = Number(a.replace(/^\D+/, ""));
  const numberB = Number(b.replace(/^\D+/, ""));
  if (Number.isFinite(numberA) && Number.isFinite(numberB) && numberA !== numberB) return numberA - numberB;
  return a.localeCompare(b);
}

function buildSourceCodeMap(rawSources) {
  const sourceToCodes = new Map();
  for (const row of rawSources) {
    const huntCode = clean(row.hunt_code);
    if (!huntCode) continue;
    for (const source of clean(row.sources).split(/;\s*/).filter(Boolean)) {
      if (!source.toLowerCase().endsWith(".pdf")) continue;
      if (!sourceToCodes.has(source)) sourceToCodes.set(source, new Set());
      sourceToCodes.get(source).add(huntCode);
    }
  }
  return sourceToCodes;
}

function buildRowsByCode(canonicalRows) {
  const rowsByCode = new Map();
  for (const row of canonicalRows) {
    const code = clean(row.hunt_code);
    if (!code) continue;
    if (!rowsByCode.has(code)) rowsByCode.set(code, []);
    rowsByCode.get(code).push(row);
  }
  return rowsByCode;
}

function buildRollupRows(codes, rowsByCode) {
  const rows = [];
  for (const code of codes) {
    const canonicalRows = rowsByCode.get(code) ?? [];
    const preferred =
      canonicalRows.find((row) => clean(row.record_type) === "point_level_draw_result") ??
      canonicalRows.find((row) => clean(row.record_type) === "sportsman_total") ??
      canonicalRows[0] ??
      {};
    rows.push(ROLLUP_COLUMNS.map((column) => maybeNumber(column, preferred[column])));
  }
  return rows;
}

async function renderPreview(workbook, pdfName) {
  const stem = path.basename(pdfName, ".pdf");
  const previewBase = path.join(PREVIEW_DIR, `${stem}__summary.png`);
  const preview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(previewBase, new Uint8Array(await preview.arrayBuffer()));
  return previewBase;
}

async function saveWorkbook(workbook, outPath) {
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outPath);
}

async function createFamilyWorkbook({ pdfName, pdfPath, outPdf, outXlsx, codes, canonicalHeader, canonicalRows, rowsByCode }) {
  const familyRows = [];
  for (const code of codes) familyRows.push(...(rowsByCode.get(code) ?? []));

  const workbook = Workbook.create();
  const summarySheet = workbook.worksheets.add("Summary");
  const rollupSheet = workbook.worksheets.add("Hunt Rollup");
  const pointRowsSheet = workbook.worksheets.add("Canonical Rows");
  const auditSheet = workbook.worksheets.add("Audit");

  for (const sheet of [summarySheet, rollupSheet, pointRowsSheet, auditSheet]) {
    sheet.showGridLines = false;
  }

  summarySheet.getRange("A1:L1").merge();
  summarySheet.getRange("A1").values = [[`${YEAR} Permits = ${MODEL_YEAR} Model - ${titleFromPdfName(pdfName)}`]];
  applyTitleStyle(summarySheet.getRange("A1"));

  const summaryRows = [
    ["Source PDF", path.relative(REPO_ROOT, pdfPath)],
    ["Output PDF", path.relative(REPO_ROOT, outPdf)],
    ["Output workbook", path.relative(REPO_ROOT, outXlsx)],
    ["Canonical source", path.relative(REPO_ROOT, CANONICAL)],
    ["Actual draw year", YEAR],
    ["Model target year", MODEL_YEAR],
    ["Hunt codes in source PDF", codes.length],
    ["Canonical rows joined by hunt code", familyRows.length],
    ["Unique canonical hunt codes joined", new Set(familyRows.map((row) => clean(row.hunt_code))).size],
  ];
  writeTable(summarySheet, 2, 0, ["Metric", "Value"], summaryRows);
  writeTable(
    summarySheet,
    2,
    3,
    ["Record Type", "Rows"],
    countBy(familyRows, "record_type").map(([recordType, count]) => [recordType, count]),
  );
  writeTable(
    summarySheet,
    2,
    6,
    ["Hunt Type", "Rows"],
    countBy(familyRows, "hunt_type").map(([huntType, count]) => [huntType, count]),
  );
  setColumnWidths(summarySheet, [38, 110, 3, 20, 12, 3, 24, 12, 3, 18, 12, 12]);
  summarySheet.freezePanes.freezeRows(2);

  writeTable(rollupSheet, 0, 0, ROLLUP_COLUMNS, buildRollupRows(codes, rowsByCode));
  setColumnWidths(rollupSheet, [14, 14, 12, 34, 24, 18, 28, 20, 22, 30, 12, 14, 14, 14, 22, 46]);
  rollupSheet.freezePanes.freezeRows(1);
  rollupSheet.freezePanes.freezeColumns(3);

  const pointValues = familyRows.map((row) => canonicalHeader.map((column) => maybeNumber(column, row[column])));
  writeTable(pointRowsSheet, 0, 0, canonicalHeader, pointValues, { lightBorders: false });
  setColumnWidths(pointRowsSheet, [12, 14, 18, 28, 28, 46, 10, 14, 12, 34, 24, 18, 22, 28, 20, 30]);
  pointRowsSheet.freezePanes.freezeRows(1);
  pointRowsSheet.freezePanes.freezeColumns(4);

  const auditRows = [
    ["join_key", "hunt_code"],
    ["source_code_map", path.relative(REPO_ROOT, RAW_PDF_CODE_SOURCES)],
    ["source_pdf_copied_without_relayout", "yes"],
    ["canonical_rows_not_found_for_pdf_codes", codes.filter((code) => !rowsByCode.has(code)).join(", ")],
    ["notes", "PDF layout is the existing UOGA-styled source document; workbook tabs are populated from canonical rows that match PDF hunt codes."],
  ];
  writeTable(auditSheet, 0, 0, ["Item", "Detail"], auditRows);
  setColumnWidths(auditSheet, [34, 110]);
  auditSheet.freezePanes.freezeRows(1);

  const shouldPreview =
    /SPORTSMAN DRAW RESULTS|L\.E\. BULL ELK DRAW RESULTS|L\.E\. BUCK DEER DRAW RESULTS|COMPREHENSIVE/i.test(pdfName);
  const previewPath = shouldPreview ? await renderPreview(workbook, pdfName) : "";
  await saveWorkbook(workbook, outXlsx);

  return {
    pdfName,
    title: titleFromPdfName(pdfName),
    outputPdf: path.relative(REPO_ROOT, outPdf),
    outputXlsx: path.relative(REPO_ROOT, outXlsx),
    preview: previewPath ? path.relative(REPO_ROOT, previewPath) : "",
    huntCodeCount: codes.length,
    canonicalRowCount: familyRows.length,
    canonicalCodeCount: new Set(familyRows.map((row) => clean(row.hunt_code))).size,
    missingCanonicalCodes: codes.filter((code) => !rowsByCode.has(code)),
    recordTypes: Object.fromEntries(countBy(familyRows, "record_type")),
    huntTypes: Object.fromEntries(countBy(familyRows, "hunt_type")),
    drawDesigns: Object.fromEntries(countBy(familyRows, "draw_design")),
  };
}

async function createIndexWorkbook(manifestRows) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("Family Index");
  const auditSheet = workbook.worksheets.add("Audit");
  sheet.showGridLines = false;
  auditSheet.showGridLines = false;

  sheet.getRange("A1:L1").merge();
  sheet.getRange("A1").values = [[`${YEAR} Permits = ${MODEL_YEAR} Model Species Family Document Index`]];
  applyTitleStyle(sheet.getRange("A1"));

  const header = [
    "family_document",
    "hunt_code_count",
    "canonical_row_count",
    "canonical_code_count",
    "missing_canonical_codes",
    "output_pdf",
    "output_xlsx",
    "preview",
  ];
  const rows = manifestRows.map((row) => [
    row.title,
    row.huntCodeCount,
    row.canonicalRowCount,
    row.canonicalCodeCount,
    row.missingCanonicalCodes.join(", "),
    row.outputPdf,
    row.outputXlsx,
    row.preview,
  ]);
  writeTable(sheet, 2, 0, header, rows);
  setColumnWidths(sheet, [48, 16, 18, 18, 28, 86, 86, 72]);
  sheet.freezePanes.freezeRows(3);

  const auditRows = [
    ["canonical_source", path.relative(REPO_ROOT, CANONICAL)],
    ["raw_pdf_folder", path.relative(REPO_ROOT, RAW_PDF_DIR)],
    ["raw_pdf_code_sources", path.relative(REPO_ROOT, RAW_PDF_CODE_SOURCES)],
    ["manifest_csv", path.relative(REPO_ROOT, MANIFEST_CSV)],
    ["manifest_json", path.relative(REPO_ROOT, MANIFEST_JSON)],
    ["notes", "Each family workbook uses PDF hunt-code membership, then joins rows from the 2026 canonical file."],
  ];
  writeTable(auditSheet, 0, 0, ["Item", "Detail"], auditRows);
  setColumnWidths(auditSheet, [34, 110]);
  auditSheet.freezePanes.freezeRows(1);
  await saveWorkbook(workbook, INDEX_XLSX);
}

async function main() {
  await fs.mkdir(PDF_OUT_DIR, { recursive: true });
  await fs.mkdir(XLSX_OUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });

  const canonicalParsed = parseCsv(await fs.readFile(CANONICAL, "utf8"));
  const rawSourceParsed = parseCsv(await fs.readFile(RAW_PDF_CODE_SOURCES, "utf8"));
  let antlerlessSourceRows = [];
  try {
    antlerlessSourceRows = parseCsv(await fs.readFile(ANTLERLESS_PDF_CODE_SOURCES, "utf8")).rows;
  } catch {
    antlerlessSourceRows = [];
  }
  const rowsByCode = buildRowsByCode(canonicalParsed.rows);
  const sourceToCodes = buildSourceCodeMap([...rawSourceParsed.rows, ...antlerlessSourceRows]);
  const pdfFiles = (await fs.readdir(RAW_PDF_DIR))
    .filter((name) => name.toLowerCase().endsWith(".pdf"))
    .sort((a, b) => a.localeCompare(b));

  const manifestRows = [];
  const uniquePdfHuntCodes = new Set();
  for (const pdfName of pdfFiles) {
    const codes = [...(sourceToCodes.get(pdfName) ?? new Set())].sort(sortCode);
    if (!codes.length) continue;
    for (const code of codes) uniquePdfHuntCodes.add(code);

    const pdfPath = path.join(RAW_PDF_DIR, pdfName);
    const outPdf = path.join(PDF_OUT_DIR, pdfName);
    const outXlsx = path.join(XLSX_OUT_DIR, `${path.basename(pdfName, ".pdf")}.xlsx`);
    await fs.copyFile(pdfPath, outPdf);
    manifestRows.push(
      await createFamilyWorkbook({
        pdfName,
        pdfPath,
        outPdf,
        outXlsx,
        codes,
        canonicalHeader: canonicalParsed.header,
        canonicalRows: canonicalParsed.rows,
        rowsByCode,
      }),
    );
  }

  const manifestHeader = [
    "pdf_name",
    "title",
    "hunt_code_count",
    "canonical_row_count",
    "canonical_code_count",
    "missing_canonical_codes",
    "output_pdf",
    "output_xlsx",
    "preview",
  ];
  const manifestCsvRows = [
    manifestHeader,
    ...manifestRows.map((row) => [
      row.pdfName,
      row.title,
      row.huntCodeCount,
      row.canonicalRowCount,
      row.canonicalCodeCount,
      row.missingCanonicalCodes.join("; "),
      row.outputPdf,
      row.outputXlsx,
      row.preview,
    ]),
  ];
  await fs.writeFile(MANIFEST_CSV, toCsv(manifestCsvRows), "utf8");
  await fs.writeFile(MANIFEST_JSON, JSON.stringify({ generatedAt: new Date().toISOString(), rows: manifestRows }, null, 2));
  await createIndexWorkbook(manifestRows);

  console.log(
    JSON.stringify(
      {
        outputRoot: path.relative(REPO_ROOT, OUT_ROOT),
        pdfDocuments: manifestRows.length,
        xlsxDocuments: manifestRows.length + 1,
        manifestCsv: path.relative(REPO_ROOT, MANIFEST_CSV),
        manifestJson: path.relative(REPO_ROOT, MANIFEST_JSON),
        indexXlsx: path.relative(REPO_ROOT, INDEX_XLSX),
        uniquePdfHuntCodes: uniquePdfHuntCodes.size,
        missingCanonicalRowsAcrossFamilyDocs: manifestRows.reduce((total, row) => total + row.missingCanonicalCodes.length, 0),
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
