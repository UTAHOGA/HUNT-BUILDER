import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const YEAR = 2026;
const MODEL_YEAR = 2027;
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2026 standardized long.xlsx");
const OUTPUT_SCORABLE_CSV = path.join(OUTPUT_DIR, "2026 scorable draw results.csv");
const OUTPUT_QUOTA_CSV = path.join(OUTPUT_DIR, "2026 quota allotment rows.csv");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2026_standardized_long_report.json");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2026_standardized_long_preview");
const CANONICAL = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "canonical_yearly",
  "draw_results_2026_for_2027_canonical_yearly_draw_results.csv",
);
const COMPARISON_SUMMARY = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "comparison_summary.json",
);
const ANTLERLESS_COMPARISON_SUMMARY = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "comparison_summary_after_antlerless_append.json",
);
const ANTLERLESS_AUDIT = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "dwr_hunt_planner_2026_antlerless_vs_canonical_hunt_code_audit.csv",
);
const STAGED_RAW_COMPARISON = path.join(
  REPO_ROOT,
  "audits",
  "2026_live_source_comparison",
  "staged_raw_2026_vs_fresh_downloads_summary.json",
);
const FAMILY_DOCS_MANIFEST = path.join(
  OUTPUT_DIR,
  "2026_PERMITS=2027_MODEL_species_family_docs",
  "2026_PERMITS=2027_MODEL_species_family_manifest.csv",
);

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

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function serializeCsv(header, rows) {
  return [
    header.map(csvEscape).join(","),
    ...rows.map((row) => header.map((column) => csvEscape(row[column] ?? "")).join(",")),
  ].join("\n") + "\n";
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

function antlerlessMissingCount(antlerlessComparison, comparison) {
  return antlerlessComparison.antlerless_missing_unique_codes ?? comparison.antlerless_missing_from_canonical ?? "";
}

function antlerlessConflictCount(antlerlessComparison, comparison) {
  const counts = antlerlessComparison.antlerless_status_counts;
  if (counts && typeof counts === "object") {
    return Object.entries(counts)
      .filter(([status]) => status !== "matched" && status !== "missing_from_canonical")
      .reduce((total, [, count]) => total + Number(count || 0), 0);
  }
  return comparison.antlerless_permit_mismatch_or_blank ?? "";
}

function sumColumn(rows, column) {
  let total = 0;
  for (const row of rows) {
    const value = Number(clean(row[column]).replaceAll(",", ""));
    if (Number.isFinite(value)) total += value;
  }
  return total;
}

function applyHeaderStyle(range) {
  range.format = {
    fill: "#1F4E5F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
}

function writeTable(sheet, anchorRow, anchorCol, header, rows) {
  const matrix = [header, ...rows];
  const range = sheet.getRangeByIndexes(anchorRow, anchorCol, matrix.length, header.length);
  range.values = matrix;
  applyHeaderStyle(sheet.getRangeByIndexes(anchorRow, anchorCol, 1, header.length));
  range.format.borders = { preset: "all", style: "thin", color: "#D9E2E7" };
  return range;
}

function setColumnWidths(sheet, widths) {
  widths.forEach((width, index) => {
    if (!width) return;
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidth = width;
  });
}

async function readJsonIfExists(filePath) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch {
    return {};
  }
}

async function readCsvIfExists(filePath) {
  try {
    return parseCsv(await fs.readFile(filePath, "utf8"));
  } catch {
    return { header: [], rows: [] };
  }
}

async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });

  const parsed = parseCsv(await fs.readFile(CANONICAL, "utf8"));
  const header = parsed.header;
  const rows = parsed.rows;
  const uniqueHuntCodes = new Set(rows.map((row) => clean(row.hunt_code)).filter(Boolean));
  const quotaRows = rows.filter((row) => clean(row.record_type) === "hunt_planner_permit_quota");
  const scorableRows = rows.filter((row) =>
    ["point_level_draw_result", "sportsman_total"].includes(clean(row.record_type)),
  );
  await fs.writeFile(OUTPUT_SCORABLE_CSV, serializeCsv(header, scorableRows), "utf8");
  await fs.writeFile(OUTPUT_QUOTA_CSV, serializeCsv(header, quotaRows), "utf8");
  const comparison = await readJsonIfExists(COMPARISON_SUMMARY);
  const antlerlessComparison = await readJsonIfExists(ANTLERLESS_COMPARISON_SUMMARY);
  const stagedRawComparison = await readJsonIfExists(STAGED_RAW_COMPARISON);
  const familyDocsManifest = await readCsvIfExists(FAMILY_DOCS_MANIFEST);

  const workbook = Workbook.create();
  const summarySheet = workbook.worksheets.add("Summary");
  const longSheet = workbook.worksheets.add("Long");
  const quotaSheet = workbook.worksheets.add("Quota");
  const familyDocsSheet = workbook.worksheets.add("Family Docs");
  const auditSheet = workbook.worksheets.add("Audit");

  summarySheet.showGridLines = false;
  familyDocsSheet.showGridLines = false;
  auditSheet.showGridLines = false;

  summarySheet.getRange("A1:F1").merge();
  summarySheet.getRange("A1").values = [[`${YEAR} Permits = ${MODEL_YEAR} Model Standardized Long Workbook`]];
  summarySheet.getRange("A1").format = {
    fill: "#143642",
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };

  const summaryRows = [
    ["Source canonical", path.relative(REPO_ROOT, CANONICAL)],
    ["Actual draw year", YEAR],
    ["Model target year", MODEL_YEAR],
    ["Canonical rows", rows.length],
    ["Scorable draw-result rows", scorableRows.length],
    ["Unique hunt codes", uniqueHuntCodes.size],
    ["Point-level rows", rows.filter((row) => clean(row.record_type) === "point_level_draw_result").length],
    ["Sportsman total rows", rows.filter((row) => clean(row.record_type) === "sportsman_total").length],
    ["Hunt Planner quota rows", quotaRows.length],
    ["Quota rows with boundary ID", quotaRows.filter((row) => clean(row.boundary_id)).length],
    ["UtahDraws live missing hunt codes", comparison.utahdraws_missing_from_canonical ?? ""],
    ["Antlerless Hunt Planner missing hunt codes", antlerlessMissingCount(antlerlessComparison, comparison)],
    ["Antlerless remaining permit conflicts", antlerlessConflictCount(antlerlessComparison, comparison)],
    ["permits_2026_res sum", sumColumn(rows, "permits_2026_res")],
    ["permits_2026_nr sum", sumColumn(rows, "permits_2026_nr")],
    ["permits_2026_total sum", sumColumn(rows, "permits_2026_total")],
  ];
  writeTable(summarySheet, 2, 0, ["Metric", "Value"], summaryRows);

  const typeRows = countBy(rows, "hunt_type").map(([name, count]) => [name, count]);
  writeTable(summarySheet, 2, 3, ["Hunt Type", "Rows"], typeRows);
  const designRows = countBy(rows, "draw_design").map(([name, count]) => [name, count]);
  writeTable(summarySheet, 2, 6, ["Draw Design", "Rows"], designRows);
  summarySheet.freezePanes.freezeRows(2);

  const longValues = scorableRows.map((row) => header.map((column) => maybeNumber(column, row[column])));
  writeTable(longSheet, 0, 0, header, longValues);
  longSheet.freezePanes.freezeRows(1);
  longSheet.freezePanes.freezeColumns(4);

  const quotaValues = quotaRows.map((row) => header.map((column) => maybeNumber(column, row[column])));
  writeTable(quotaSheet, 0, 0, header, quotaValues);
  quotaSheet.freezePanes.freezeRows(1);
  quotaSheet.freezePanes.freezeColumns(4);

  if (familyDocsManifest.header.length) {
    familyDocsSheet.getRange("A1:I1").merge();
    familyDocsSheet.getRange("A1").values = [[`${YEAR} Permits = ${MODEL_YEAR} Model Species Family PDF/XLSX Outputs`]];
    familyDocsSheet.getRange("A1").format = {
      fill: "#143642",
      font: { bold: true, color: "#FFFFFF", size: 15 },
    };
    writeTable(
      familyDocsSheet,
      2,
      0,
      familyDocsManifest.header,
      familyDocsManifest.rows.map((row) => familyDocsManifest.header.map((column) => maybeNumber(column, row[column]))),
    );
    setColumnWidths(familyDocsSheet, [58, 46, 14, 18, 18, 30, 95, 95, 75]);
    familyDocsSheet.freezePanes.freezeRows(3);
  } else {
    writeTable(familyDocsSheet, 0, 0, ["Item", "Detail"], [["family_docs_manifest", "Not found at export time"]]);
  }

  const auditRows = [
    ["canonical_source", path.relative(REPO_ROOT, CANONICAL)],
    ["live_comparison_summary", path.relative(REPO_ROOT, COMPARISON_SUMMARY)],
    ["fresh_antlerless_comparison_summary", path.relative(REPO_ROOT, ANTLERLESS_COMPARISON_SUMMARY)],
    ["antlerless_audit", path.relative(REPO_ROOT, ANTLERLESS_AUDIT)],
    ["staged_raw_vs_fresh_downloads", path.relative(REPO_ROOT, STAGED_RAW_COMPARISON)],
    ["family_docs_manifest", path.relative(REPO_ROOT, FAMILY_DOCS_MANIFEST)],
    ["long_sheet_rule", "Long sheet contains only scorable draw-result rows: point_level_draw_result and sportsman_total."],
    ["quota_sheet_rule", "Quota sheet contains only non-scorable hunt_planner_permit_quota rows."],
    ["raw_truth_pdf_unique_hunt_codes", stagedRawComparison.raw_truth_pdf_unique_hunt_codes ?? ""],
    ["raw_truth_pdf_missing_from_canonical", stagedRawComparison.gap_counts?.raw_truth_pdf_missing_from_canonical ?? ""],
    ["canonical_missing_from_raw_truth_pdf", stagedRawComparison.gap_counts?.canonical_missing_from_raw_truth_pdf ?? ""],
    ["staged_xlsx_unique_hunt_codes", stagedRawComparison.staged_xlsx_unique_hunt_codes ?? ""],
    ["fresh_downloads_unique_hunt_codes", stagedRawComparison.fresh_all_unique_hunt_codes ?? ""],
    ["canonical_missing_from_staged_xlsx", stagedRawComparison.gap_counts?.canonical_missing_from_staged_xlsx ?? ""],
    ["fresh_downloads_missing_from_staged_xlsx", stagedRawComparison.gap_counts?.fresh_downloads_missing_from_staged_xlsx ?? ""],
    ["notes", "Hunt Planner permit/quota rows are non-scorable display/feed rows and must not route through the point-level draw odds engine."],
    ["remaining_conflict", "BI6505: Hunt Planner cow-only quota conflicts with UtahDraws/canonical permit total."],
    ["remaining_conflict", "BI6536: Hunt Planner cow-only quota conflicts with UtahDraws/canonical permit total."],
  ];
  writeTable(auditSheet, 0, 0, ["Item", "Detail"], auditRows);
  auditSheet.freezePanes.freezeRows(1);

  const summaryPreview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(
    path.join(PREVIEW_DIR, "summary.png"),
    new Uint8Array(await summaryPreview.arrayBuffer()),
  );

  const longPreview = await workbook.render({ sheetName: "Long", range: "A1:P25", scale: 1, format: "png" });
  await fs.writeFile(path.join(PREVIEW_DIR, "long_A1_P25.png"), new Uint8Array(await longPreview.arrayBuffer()));

  const quotaPreview = await workbook.render({ sheetName: "Quota", range: "A1:P25", scale: 1, format: "png" });
  await fs.writeFile(path.join(PREVIEW_DIR, "quota_A1_P25.png"), new Uint8Array(await quotaPreview.arrayBuffer()));

  const familyDocsPreview = await workbook.render({ sheetName: "Family Docs", range: "A1:I30", scale: 1, format: "png" });
  await fs.writeFile(path.join(PREVIEW_DIR, "family_docs_A1_I30.png"), new Uint8Array(await familyDocsPreview.arrayBuffer()));

  const auditPreview = await workbook.render({ sheetName: "Audit", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(PREVIEW_DIR, "audit.png"), new Uint8Array(await auditPreview.arrayBuffer()));

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(OUTPUT_XLSX);

  const report = {
    output_xlsx: OUTPUT_XLSX,
    output_scorable_csv: OUTPUT_SCORABLE_CSV,
    output_quota_csv: OUTPUT_QUOTA_CSV,
    source_canonical: CANONICAL,
    rows: rows.length,
    scorable_rows: scorableRows.length,
    columns: header.length,
    unique_hunt_codes: uniqueHuntCodes.size,
    sheets: ["Summary", "Long", "Quota", "Family Docs", "Audit"],
    family_docs_manifest: FAMILY_DOCS_MANIFEST,
    family_docs_rows: familyDocsManifest.rows.length,
    quota_rows: quotaRows.length,
    quota_rows_with_boundary_id: quotaRows.filter((row) => clean(row.boundary_id)).length,
    antlerless_missing_from_canonical: antlerlessMissingCount(antlerlessComparison, comparison),
    antlerless_remaining_permit_conflicts: antlerlessConflictCount(antlerlessComparison, comparison),
  };
  await fs.writeFile(OUTPUT_REPORT, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
