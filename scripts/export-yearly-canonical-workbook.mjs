import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const CANONICAL_DIR = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "canonical_yearly",
);
const LONG_FILE = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "draw_results_long.csv",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs", "yearly_canonical_workbooks");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "_preview");

const SCORABLE_RECORD_TYPES = new Set([
  "point_level_draw_result",
  "sportsman_total",
]);

const TEXT_COLUMNS = new Set([
  "hunt_code",
  "conservation_code",
  "source_file",
  "source_scope",
  "source_namespace",
  "draw_source_namespace",
  "hunt_name",
  "species",
  "sex_type",
  "draw_design",
  "weapon",
  "hunt_type",
  "season",
  "residency",
  "record_type",
  "algorithm_status",
  "source_dataset",
  "extraction_status",
  "parse_method",
  "qa_status",
  "notes",
  "success_ratio",
]);

function clean(value) {
  return value == null ? "" : String(value).trim();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
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
      if (char === "\r" && next === "\n") i += 1;
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

  const [header, ...body] = rows.filter((entry) => entry.some((value) => value !== ""));
  return {
    header,
    rows: body.map((values) => Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""]))),
  };
}

function maybeNumber(column, value) {
  const text = clean(value).replaceAll(",", "");
  if (!text || TEXT_COLUMNS.has(column)) return clean(value);
  const number = Number(text);
  return Number.isFinite(number) ? number : clean(value);
}

function normalizeType(value) {
  return clean(value).toLowerCase();
}

function isScorable(row) {
  return SCORABLE_RECORD_TYPES.has(normalizeType(row.record_type));
}

function isDisplayReference(row) {
  return !isScorable(row);
}

function firstNonBlank(rows, column) {
  for (const row of rows) {
    const value = clean(row[column]);
    if (value) return value;
  }
  return "";
}

function uniqueNonBlank(rows, column) {
  return [...new Set(rows.map((row) => clean(row[column])).filter(Boolean))].sort();
}

function firstNumber(rows, column) {
  for (const row of rows) {
    const value = clean(row[column]).replaceAll(",", "");
    if (!value) continue;
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return "";
}

function countBy(rows, column) {
  const counts = new Map();
  for (const row of rows) {
    const value = clean(row[column]) || "(blank)";
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function findCanonicalPath(year) {
  return path.join(CANONICAL_DIR, `draw_results_${year}_for_${Number(year) + 1}_canonical_yearly_draw_results.csv`);
}

async function existingYears() {
  const entries = await fs.readdir(CANONICAL_DIR);
  return entries
    .map((name) => name.match(/^draw_results_(\d{4})_for_\d{4}_canonical_yearly_draw_results\.csv$/)?.[1])
    .filter(Boolean)
    .sort();
}

function parseArgs() {
  const args = process.argv.slice(2);
  if (args.includes("--all")) return { all: true, years: [] };
  const years = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--year" && args[index + 1]) {
      years.push(args[index + 1]);
      index += 1;
    } else if (/^\d{4}$/.test(arg)) {
      years.push(arg);
    }
  }
  return { all: false, years: years.length ? years : [String(new Date().getFullYear() - 1)] };
}

function groupByHuntCode(rows) {
  const grouped = new Map();
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    if (!grouped.has(code)) grouped.set(code, []);
    grouped.get(code).push(row);
  }
  return grouped;
}

function buildSummaryRows(rows, year) {
  const grouped = groupByHuntCode(rows);
  const resColumn = `permits_${year}_res`;
  const nrColumn = `permits_${year}_nr`;
  const totalColumn = `permits_${year}_total`;
  const output = [];

  for (const [huntCode, group] of grouped.entries()) {
    const permitsRes = firstNumber(group, resColumn);
    const permitsNr = firstNumber(group, nrColumn);
    let permitsTotal = firstNumber(group, totalColumn);
    if (permitsTotal === "" && (permitsRes !== "" || permitsNr !== "")) {
      permitsTotal = Number(permitsRes || 0) + Number(permitsNr || 0);
    }
    output.push({
      actual_draw_year: Number(year),
      model_target_year: Number(year) + 1,
      hunt_code: huntCode,
      boundary_id: firstNumber(group, "boundary_id"),
      species: firstNonBlank(group, "species"),
      sex_type: firstNonBlank(group, "sex_type"),
      weapon: firstNonBlank(group, "weapon"),
      hunt_name: firstNonBlank(group, "hunt_name"),
      hunt_type: firstNonBlank(group, "hunt_type"),
      draw_design: firstNonBlank(group, "draw_design"),
      season: firstNonBlank(group, "season"),
      [resColumn]: permitsRes,
      [nrColumn]: permitsNr,
      [totalColumn]: permitsTotal,
      canonical_rows: group.length,
      scorable_rows: group.filter(isScorable).length,
      display_reference_rows: group.filter(isDisplayReference).length,
      record_types: uniqueNonBlank(group, "record_type").join("; "),
      source_files: uniqueNonBlank(group, "source_file").slice(0, 5).join("; "),
    });
  }

  output.sort((left, right) => left.hunt_code.localeCompare(right.hunt_code, undefined, { numeric: true }));
  return output;
}

function buildAuditRows({ year, canonicalPath, canonicalRows, longRows, summaryRows }) {
  const canonicalCodes = new Set(canonicalRows.map((row) => clean(row.hunt_code).toUpperCase()).filter(Boolean));
  const longCodes = new Set(longRows.map((row) => clean(row.hunt_code).toUpperCase()).filter(Boolean));
  const longOnly = [...longCodes].filter((code) => !canonicalCodes.has(code)).sort();
  const canonicalOnly = [...canonicalCodes].filter((code) => !longCodes.has(code)).sort();
  const typeCounts = countBy(canonicalRows, "hunt_type");
  const designCounts = countBy(canonicalRows, "draw_design");
  const recordTypeCounts = countBy(canonicalRows, "record_type");

  return [
    ["actual_draw_year", year],
    ["model_target_year", Number(year) + 1],
    ["source_canonical", path.relative(REPO_ROOT, canonicalPath)],
    ["source_long_file", path.relative(REPO_ROOT, LONG_FILE)],
    ["canonical_rows", canonicalRows.length],
    ["canonical_unique_hunt_codes", canonicalCodes.size],
    ["long_file_slice_rows", longRows.length],
    ["long_file_slice_unique_hunt_codes", longCodes.size],
    ["summary_hunt_code_rows", summaryRows.length],
    ["scorable_rows", canonicalRows.filter(isScorable).length],
    ["display_reference_rows", canonicalRows.filter(isDisplayReference).length],
    ["canonical_codes_missing_from_long_slice_count", canonicalOnly.length],
    ["long_slice_codes_missing_from_canonical_count", longOnly.length],
    ["canonical_codes_missing_from_long_slice_sample", canonicalOnly.slice(0, 40).join(", ")],
    ["long_slice_codes_missing_from_canonical_sample", longOnly.slice(0, 40).join(", ")],
    ["record_type_counts", recordTypeCounts.map(([name, count]) => `${name}: ${count}`).join("; ")],
    ["hunt_type_counts", typeCounts.map(([name, count]) => `${name}: ${count}`).join("; ")],
    ["draw_design_counts", designCounts.map(([name, count]) => `${name}: ${count}`).join("; ")],
  ];
}

function matrixFromRows(header, rows) {
  return [header, ...rows.map((row) => header.map((column) => maybeNumber(column, row[column])))];
}

function writeTable(sheet, rowIndex, columnIndex, header, rows) {
  const matrix = matrixFromRows(header, rows);
  const range = sheet.getRangeByIndexes(rowIndex, columnIndex, matrix.length, header.length);
  range.values = matrix;
  sheet.getRangeByIndexes(rowIndex, columnIndex, 1, header.length).format = {
    fill: "#183A37",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
}

function setUsefulWidths(sheet, header) {
  const widthByColumn = {
    hunt_code: 100,
    conservation_code: 120,
    hunt_name: 280,
    source_file: 260,
    source_scope: 180,
    species: 140,
    sex_type: 120,
    draw_design: 140,
    weapon: 150,
    hunt_type: 140,
    season: 180,
    record_type: 150,
    notes: 260,
    source_files: 300,
    record_types: 220,
  };
  header.forEach((column, index) => {
    const width = widthByColumn[column] || (column.startsWith("permits_") ? 105 : 95);
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
}

async function savePreview(workbook, year) {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  const preview = await workbook.render({
    sheetName: "Summary",
    range: "A1:S30",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(PREVIEW_DIR, `${year}_summary.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

async function exportYear(year, longParsed) {
  const canonicalPath = findCanonicalPath(year);
  const canonicalParsed = parseCsv(await fs.readFile(canonicalPath, "utf8"));
  const canonicalRows = canonicalParsed.rows;
  const longRows = longParsed.rows.filter((row) => clean(row.actual_draw_year) === String(year));
  const summaryRows = buildSummaryRows(canonicalRows, year);
  const scorableRows = canonicalRows.filter(isScorable);
  const displayRows = canonicalRows.filter(isDisplayReference);
  const auditRows = buildAuditRows({ year, canonicalPath, canonicalRows, longRows, summaryRows });

  const workbook = Workbook.create();
  const readmeSheet = workbook.worksheets.add("README");
  const summarySheet = workbook.worksheets.add("Summary");
  const canonicalSheet = workbook.worksheets.add("Canonical Rows");
  const longSheet = workbook.worksheets.add("Long File Slice");
  const scorableSheet = workbook.worksheets.add("Scorable Rows");
  const displaySheet = workbook.worksheets.add("Display Reference Rows");
  const auditSheet = workbook.worksheets.add("Audit");

  const readmeRows = [
    ["Workbook purpose", "Generated yearly review workbook from canonical yearly truth plus matching draw_results_long.csv slice."],
    ["Generated from", path.relative(REPO_ROOT, canonicalPath)],
    ["Long file source", path.relative(REPO_ROOT, LONG_FILE)],
    ["Rule", "Canonical Rows is the full yearly canonical file."],
    ["Rule", "Long File Slice is a copy of draw_results_long.csv filtered to this actual_draw_year."],
    ["Rule", "Scorable Rows are only point_level_draw_result and sportsman_total rows."],
    ["Rule", "Display Reference Rows are quota, allocation, conservation, reference, and other non-scorable rows."],
  ];
  writeTable(readmeSheet, 0, 0, ["Item", "Detail"], readmeRows.map(([Item, Detail]) => ({ Item, Detail })));
  setUsefulWidths(readmeSheet, ["Item", "Detail"]);

  const summaryHeader = [
    "actual_draw_year",
    "model_target_year",
    "hunt_code",
    "boundary_id",
    "species",
    "sex_type",
    "weapon",
    "hunt_name",
    "hunt_type",
    "draw_design",
    "season",
    `permits_${year}_res`,
    `permits_${year}_nr`,
    `permits_${year}_total`,
    "canonical_rows",
    "scorable_rows",
    "display_reference_rows",
    "record_types",
    "source_files",
  ];
  writeTable(summarySheet, 0, 0, summaryHeader, summaryRows);
  setUsefulWidths(summarySheet, summaryHeader);

  writeTable(canonicalSheet, 0, 0, canonicalParsed.header, canonicalRows);
  setUsefulWidths(canonicalSheet, canonicalParsed.header);

  writeTable(longSheet, 0, 0, longParsed.header, longRows);
  setUsefulWidths(longSheet, longParsed.header);

  writeTable(scorableSheet, 0, 0, canonicalParsed.header, scorableRows);
  setUsefulWidths(scorableSheet, canonicalParsed.header);

  writeTable(displaySheet, 0, 0, canonicalParsed.header, displayRows);
  setUsefulWidths(displaySheet, canonicalParsed.header);

  writeTable(auditSheet, 0, 0, ["Item", "Detail"], auditRows.map(([Item, Detail]) => ({ Item, Detail })));
  setUsefulWidths(auditSheet, ["Item", "Detail"]);

  await savePreview(workbook, year);
  const outputPath = path.join(OUTPUT_DIR, `${year}_PERMITS=${Number(year) + 1}_MODEL__CANONICAL_WORKBOOK.xlsx`);
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(outputPath);

  return {
    year: Number(year),
    output_xlsx: path.relative(REPO_ROOT, outputPath).replaceAll("\\", "/"),
    source_canonical: path.relative(REPO_ROOT, canonicalPath).replaceAll("\\", "/"),
    canonical_rows: canonicalRows.length,
    long_file_slice_rows: longRows.length,
    summary_hunt_code_rows: summaryRows.length,
    scorable_rows: scorableRows.length,
    display_reference_rows: displayRows.length,
    canonical_columns: canonicalParsed.header.length,
    long_file_columns: longParsed.header.length,
  };
}

async function main() {
  const args = parseArgs();
  const years = args.all ? await existingYears() : args.years;
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const longParsed = parseCsv(await fs.readFile(LONG_FILE, "utf8"));
  const report = {
    generated_at_utc: new Date().toISOString(),
    output_dir: path.relative(REPO_ROOT, OUTPUT_DIR).replaceAll("\\", "/"),
    years: [],
  };

  for (const year of years) {
    report.years.push(await exportYear(year, longParsed));
  }

  const reportPath = path.join(OUTPUT_DIR, "yearly_canonical_workbooks_report.json");
  await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
