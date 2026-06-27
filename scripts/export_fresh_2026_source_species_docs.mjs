import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = path.resolve(path.dirname(__filename), "..");
const AUDIT_ROOT = path.join(REPO_ROOT, "audits", "2025_canonical_finalization");
const HUNT_PLANNER_CSV = path.join(
  REPO_ROOT,
  "data_truth",
  "crosswalk_truth",
  "raw_inventory",
  "live_dwr_hunt_planner_permit_numbers_comprehensive_2026.csv",
);
const HUNT_PLANNER_POPUP_JSON = path.join(
  REPO_ROOT,
  "processed_data",
  "dwr_huntplanner_hanumber_2026.json",
);
const OUTPUT_STAMP = "20260626";
const OUTPUT_ROOT = path.join(REPO_ROOT, "outputs", `${OUTPUT_STAMP}_fresh_2026_source_species_docs`);
const DRAW_ODDS_OUT = path.join(OUTPUT_ROOT, "draw_odds_xlsx");
const HUNT_PLANNER_OUT = path.join(OUTPUT_ROOT, "hunt_planner_xlsx");
const PREVIEW_OUT = path.join(OUTPUT_ROOT, "_previews");
const INDEX_OUT = path.join(OUTPUT_ROOT, "indexes");
const MANIFEST_JSON = path.join(OUTPUT_ROOT, "fresh_2026_source_species_docs_manifest.json");

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function toCsv(rows) {
  return rows.map((row) => row.map(csvEscape).join(",")).join("\n") + "\n";
}

function clean(value) {
  return value == null ? "" : String(value).replace(/\s+/g, " ").trim();
}

function cleanForCell(value) {
  if (value == null) return "";
  if (typeof value === "number" || typeof value === "boolean") return value;
  const text = clean(value);
  if (text === "") return "";
  const numeric = Number(text.replaceAll(",", ""));
  if (!Number.isNaN(numeric) && /^-?\d+(?:\.\d+)?$/.test(text.replaceAll(",", ""))) return numeric;
  return text;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  const source = text.replace(/^\uFEFF/, "");

  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i];
    const next = source[i + 1];
    if (ch === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }
    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }
    field += ch;
  }

  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }

  const filtered = rows.filter((entry) => entry.some((value) => value !== ""));
  const [header = [], ...body] = filtered;
  return body.map((values) => Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""])));
}

async function latestFreshDir() {
  const entries = await fs.readdir(AUDIT_ROOT, { withFileTypes: true });
  const names = entries
    .filter((entry) => entry.isDirectory() && /^fresh_live_pulls_\d{8}_\d{6}$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
  if (!names.length) throw new Error(`No fresh_live_pulls_* directories found under ${AUDIT_ROOT}`);
  return path.join(AUDIT_ROOT, names[names.length - 1]);
}

function slug(value) {
  return clean(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "") || "unknown";
}

function titleCase(value) {
  return clean(value)
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function speciesGroupFromText(...values) {
  const text = values.map((value) => clean(value).toLowerCase()).join(" | ");
  if (text.includes("sportsman")) return "Sportsman";
  if (text.includes("black bear") || /\bbear\b/.test(text)) return "Black Bear";
  if (text.includes("cougar")) return "Cougar";
  if (text.includes("desert bighorn")) return "Desert Bighorn Sheep";
  if (
    text.includes("rocky mountain bighorn")
    || text.includes("rocky mtn bighorn")
    || text.includes("rocky mtn sheep")
  ) return "Rocky Mountain Bighorn Sheep";
  if (text.includes("mountain goat") || text.includes("mtn goat")) return "Mountain Goat";
  if (text.includes("pronghorn")) return "Pronghorn";
  if (text.includes("moose")) return "Moose";
  if (text.includes("bison")) return "Bison";
  if (text.includes("turkey")) return "Turkey";
  if (text.includes("elk")) return "Elk";
  if (text.includes("deer")) return "Deer";
  return "Other";
}

function groupBy(rows, keyFn) {
  const grouped = new Map();
  for (const row of rows) {
    const key = keyFn(row);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }
  return grouped;
}

function countBy(rows, key) {
  const counts = new Map();
  for (const row of rows) {
    const value = clean(row[key]) || "(blank)";
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function colLetter(indexZero) {
  let n = indexZero + 1;
  let result = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    result = String.fromCharCode(65 + r) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result;
}

function applyTitleStyle(range) {
  range.format = {
    fill: "#1F4E5F",
    font: { bold: true, color: "#FFFFFF", size: 14 },
  };
}

function applyHeaderStyle(range) {
  range.format = {
    fill: "#D9E8EF",
    font: { bold: true, color: "#17313B" },
    wrapText: true,
  };
}

function setColumnWidths(sheet, widths) {
  widths.forEach((width, idx) => {
    if (!width) return;
    sheet.getRangeByIndexes(0, idx, 1, 1).format.columnWidth = width;
  });
}

function writeTable(sheet, startRow, startCol, header, rows, widths = []) {
  const matrix = [header, ...rows].map((row) => row.map((value) => cleanForCell(value)));
  const range = sheet.getRangeByIndexes(startRow, startCol, matrix.length, header.length);
  range.values = matrix;
  applyHeaderStyle(sheet.getRangeByIndexes(startRow, startCol, 1, header.length));
  range.format.borders = { preset: "all", style: "thin", color: "#D6DEE3" };
  range.format.wrapText = true;
  if (widths.length) setColumnWidths(sheet, widths);
  const lastCol = colLetter(startCol + header.length - 1);
  const firstRow = startRow + 1;
  const lastRow = startRow + matrix.length;
  if (rows.length > 0) {
    sheet.tables.add(`${colLetter(startCol)}${firstRow}:${lastCol}${lastRow}`, true, `T${startRow}${startCol}${sheet.name.replace(/[^A-Za-z0-9]/g, "")}`);
  }
  return range;
}

function previewSheetName(sourceKind) {
  return sourceKind === "draw_odds" ? "Table 1" : "Table 1";
}

async function renderPreview(workbook, outPath, sheetName) {
  const preview = await workbook.render({ sheetName, range: "A1:H20", scale: 1, format: "png" });
  await fs.writeFile(outPath, new Uint8Array(await preview.arrayBuffer()));
}

function drawOddsFlatRows(drawOddsManifests, freshDir) {
  const rows = [];
  for (const manifestRow of drawOddsManifests) {
    if (clean(manifestRow.status).toLowerCase() !== "ok") continue;
    const fileName = clean(manifestRow.file);
    const payloadPath = path.join(freshDir, fileName);
    rows.push({ __manifest_only__: true, __payload_path__: payloadPath, ...manifestRow });
  }
  return rows;
}

async function loadDrawOddsRows(drawOddsManifests, freshDir) {
  const flat = [];
  for (const manifestRow of drawOddsManifests) {
    if (clean(manifestRow.status).toLowerCase() !== "ok") continue;
    const payloadPath = path.join(freshDir, clean(manifestRow.file));
    const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
    const hunts = Array.isArray(payload?.Data) ? payload.Data : [];
    for (const hunt of hunts) {
      const oddsList = Array.isArray(hunt?.OddsList) ? hunt.OddsList : [];
      for (const odds of oddsList) {
        flat.push({
          source_json_file: clean(manifestRow.file),
          draw_name: clean(manifestRow.draw_name),
          master_hunt_type_name: clean(manifestRow.master_hunt_type_name),
          species_group: speciesGroupFromText(
            hunt.HuntCategoryName,
            hunt.SpeciesSubtypeName,
            manifestRow.master_hunt_type_name,
            manifestRow.draw_name,
          ),
          hunt_code: clean(hunt.HuntCode).toUpperCase(),
          hunt_name: clean(hunt.HuntName),
          hunt_category: clean(hunt.HuntCategoryName),
          species_subtype: clean(hunt.SpeciesSubtypeName),
          residency: clean(odds.ResidencyTypeID) === "1" ? "Resident" : clean(odds.ResidencyTypeID) === "2" ? "Nonresident" : clean(odds.ResidencyTypeID),
          is_youth: clean(odds.IsYouth),
          points: clean(odds.Point || odds.PreferencePoint),
          eligible_applicants: clean(odds.ParticipantCount),
          successful_total: clean(odds.SuccessfulCount),
          successful_bonus: clean(odds.SuccessfulByMaxPointRoundCount),
          successful_regular: clean(odds.SuccessfulByRegularRoundCount),
          all_choices_successful: clean(odds.AllChoicesSuccessfulCount),
          resident_quota: clean(hunt.ResidentQuotaQuantity),
          nonresident_quota: clean(hunt.NonResidentQuotaQuantity),
          total_quota: clean(hunt.QuotaQuantity),
          is_bonus_point: clean(hunt.IsBonusPoint),
          point_calc_type_id: clean(hunt.PointCalculationTypeID),
          source_url: clean(manifestRow.url),
        });
      }
    }
  }
  return flat;
}

async function loadHuntPlannerRows() {
  const permitRows = parseCsv(await fs.readFile(HUNT_PLANNER_CSV, "utf8"));
  const popupRows = JSON.parse(await fs.readFile(HUNT_PLANNER_POPUP_JSON, "utf8"));
  const popupByCode = new Map(
    popupRows.map((row) => [
      clean(row.hunt_code).toUpperCase(),
      row,
    ]),
  );
  return permitRows.map((row) => {
    const huntCode = clean(row.hunt_code).toUpperCase();
    const popup = popupByCode.get(huntCode) || {};
    return {
      species_group: speciesGroupFromText(row.species, row.endpoint_species, popup.dwr_species),
      endpoint_species: clean(row.endpoint_species),
      endpoint_gender: clean(row.endpoint_gender),
      hunt_code: huntCode,
      hunt_name: clean(row.hunt_name || popup.dwr_hunt_name),
      species: clean(row.species || popup.dwr_species),
      sex_type: clean(row.sex_type || popup.dwr_sex_type),
      weapon: clean(row.weapon || popup.dwr_weapon),
      hunt_type: clean(row.hunt_type || popup.dwr_hunt_type),
      season: clean(row.season || popup.season_date_text),
      permits_res: clean(row.live_res),
      permits_nr: clean(row.live_nr),
      permits_total: clean(row.live_total),
      live_shape_status: clean(row.live_shape_status),
      draw_designation: clean(popup.dwr_draw_designation),
      waiting_period_years: clean(popup.dwr_waiting_period_years),
      source_url: clean(row.source_url || popup.source_url),
      management_stats_available: clean(popup.management_stats_available),
      percent_harvest_success_previous_hunting_season: clean(popup.percent_harvest_success_previous_hunting_season),
    };
  });
}

async function buildSpeciesWorkbook({
  sourceKind,
  speciesName,
  rows,
  outDir,
  sourceNotes,
}) {
  const workbook = Workbook.create();
  const summarySheet = workbook.worksheets.add("Summary");
  const tableSheet = workbook.worksheets.add("Table 1");
  const notesSheet = workbook.worksheets.add("Source Notes");
  for (const sheet of [summarySheet, tableSheet, notesSheet]) sheet.showGridLines = false;

  const title = sourceKind === "draw_odds"
    ? `2026 Draw Odds Pull - ${speciesName}`
    : `2026 Hunt Planner Pull - ${speciesName}`;

  summarySheet.getRange("A1:H1").merge();
  summarySheet.getRange("A1").values = [[title]];
  applyTitleStyle(summarySheet.getRange("A1"));

  const summaryRows = [
    ["source_kind", sourceKind === "draw_odds" ? "UtahDraws draw odds" : "DWR Hunt Planner"],
    ["species_group", speciesName],
    ["row_count", rows.length],
    ["unique_hunt_codes", new Set(rows.map((row) => clean(row.hunt_code))).size],
    ["source_note_count", sourceNotes.length],
  ];
  writeTable(summarySheet, 2, 0, ["Metric", "Value"], summaryRows, [28, 90]);
  const categoryKey = sourceKind === "draw_odds" ? "master_hunt_type_name" : "endpoint_gender";
  const categoryHeader = sourceKind === "draw_odds" ? "Draw Family" : "Planner Gender Endpoint";
  writeTable(
    summarySheet,
    2,
    3,
    [categoryHeader, "Rows"],
    countBy(rows, categoryKey).map(([label, count]) => [label, count]),
    [36, 12],
  );
  summarySheet.freezePanes.freezeRows(3);

  const drawOddsHeader = [
    "draw_name",
    "master_hunt_type_name",
    "hunt_code",
    "hunt_name",
    "hunt_category",
    "species_subtype",
    "residency",
    "is_youth",
    "points",
    "eligible_applicants",
    "successful_bonus",
    "successful_regular",
    "successful_total",
    "resident_quota",
    "nonresident_quota",
    "total_quota",
    "source_json_file",
  ];
  const plannerHeader = [
    "endpoint_species",
    "endpoint_gender",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "season",
    "permits_res",
    "permits_nr",
    "permits_total",
    "live_shape_status",
    "draw_designation",
    "waiting_period_years",
    "management_stats_available",
    "percent_harvest_success_previous_hunting_season",
    "source_url",
  ];
  const header = sourceKind === "draw_odds" ? drawOddsHeader : plannerHeader;
  const widths = sourceKind === "draw_odds"
    ? [18, 28, 12, 34, 24, 18, 14, 10, 10, 14, 14, 14, 14, 12, 14, 12, 34]
    : [18, 18, 12, 34, 18, 14, 22, 20, 28, 12, 12, 12, 24, 18, 12, 12, 12, 54];
  const tableRows = rows.map((row) => header.map((column) => row[column] ?? ""));
  writeTable(tableSheet, 0, 0, header, tableRows, widths);
  tableSheet.freezePanes.freezeRows(1);
  tableSheet.freezePanes.freezeColumns(3);

  const noteRows = sourceNotes.map((row) => [row.item, row.detail]);
  writeTable(notesSheet, 0, 0, ["Item", "Detail"], noteRows, [28, 110]);
  notesSheet.freezePanes.freezeRows(1);

  const baseName = `${sourceKind === "draw_odds" ? "2026_DRAWDODDS" : "2026_HUNTPLANNER"}__${slug(speciesName)}.xlsx`;
  const outPath = path.join(outDir, baseName);
  const previewPath = path.join(PREVIEW_OUT, baseName.replace(/\.xlsx$/i, "__summary.png"));
  await renderPreview(workbook, previewPath, previewSheetName(sourceKind));
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outPath);

  return {
    source_kind: sourceKind,
    species_group: speciesName,
    row_count: rows.length,
    unique_hunt_codes: new Set(rows.map((row) => clean(row.hunt_code))).size,
    output_xlsx: outPath,
    preview_png: previewPath,
  };
}

async function createIndexWorkbook(title, rows, outPath, sourceKind) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("Summary");
  sheet.showGridLines = false;
  sheet.getRange("A1:F1").merge();
  sheet.getRange("A1").values = [[title]];
  applyTitleStyle(sheet.getRange("A1"));
  const header = ["species_group", "row_count", "unique_hunt_codes", "output_xlsx", "preview_png"];
  const matrixRows = rows.map((row) => [
    row.species_group,
    row.row_count,
    row.unique_hunt_codes,
    path.relative(REPO_ROOT, row.output_xlsx),
    path.relative(REPO_ROOT, row.preview_png),
  ]);
  writeTable(sheet, 2, 0, header, matrixRows, [24, 12, 16, 86, 72]);
  const notes = workbook.worksheets.add("Source Notes");
  notes.showGridLines = false;
  writeTable(
    notes,
    0,
    0,
    ["Item", "Detail"],
    [
      ["source_kind", sourceKind],
      ["output_root", path.relative(REPO_ROOT, path.dirname(outPath))],
      ["generated_from", "fresh live pulls plus current local comprehensive hunt planner extracts"],
    ],
    [28, 110],
  );
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outPath);
}

async function main() {
  const freshDir = await latestFreshDir();
  await fs.mkdir(DRAW_ODDS_OUT, { recursive: true });
  await fs.mkdir(HUNT_PLANNER_OUT, { recursive: true });
  await fs.mkdir(PREVIEW_OUT, { recursive: true });
  await fs.mkdir(INDEX_OUT, { recursive: true });

  const drawOddsManifestRows = parseCsv(
    await fs.readFile(path.join(freshDir, "utahdraws_draw_odds_full_matrix_manifest.csv"), "utf8"),
  );
  const drawOddsRows = await loadDrawOddsRows(drawOddsManifestRows, freshDir);
  const huntPlannerRows = await loadHuntPlannerRows();

  const drawOddsGroups = groupBy(drawOddsRows, (row) => row.species_group);
  const huntPlannerGroups = groupBy(huntPlannerRows, (row) => row.species_group);

  const manifest = {
    generated_at: new Date().toISOString(),
    fresh_dir: freshDir,
    output_root: OUTPUT_ROOT,
    draw_odds: [],
    hunt_planner: [],
  };

  for (const [speciesName, rows] of [...drawOddsGroups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    manifest.draw_odds.push(
      await buildSpeciesWorkbook({
        sourceKind: "draw_odds",
        speciesName,
        rows,
        outDir: DRAW_ODDS_OUT,
        sourceNotes: [
          { item: "source_dir", detail: path.relative(REPO_ROOT, freshDir) },
          { item: "source_manifest", detail: path.relative(REPO_ROOT, path.join(freshDir, "utahdraws_draw_odds_full_matrix_manifest.csv")) },
          { item: "source_page", detail: "https://www.utahdraws.com/internetsales/home/drawodds" },
          { item: "layout_note", detail: "Species-level flat workbook built from the fresh UtahDraws 2026 full matrix pull." },
        ],
      }),
    );
  }

  for (const [speciesName, rows] of [...huntPlannerGroups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    manifest.hunt_planner.push(
      await buildSpeciesWorkbook({
        sourceKind: "hunt_planner",
        speciesName,
        rows,
        outDir: HUNT_PLANNER_OUT,
        sourceNotes: [
          { item: "source_csv", detail: path.relative(REPO_ROOT, HUNT_PLANNER_CSV) },
          { item: "source_popup_json", detail: path.relative(REPO_ROOT, HUNT_PLANNER_POPUP_JSON) },
          { item: "source_page", detail: "https://hunt.utah.gov" },
          { item: "layout_note", detail: "Species-level table built from the comprehensive 2026 DWR Hunt Planner permit pull, with popup metadata merged by hunt code." },
        ],
      }),
    );
  }

  await createIndexWorkbook(
    "2026 Draw Odds Pull Species Index",
    manifest.draw_odds,
    path.join(INDEX_OUT, "2026_DRAWDODDS__SPECIES_INDEX.xlsx"),
    "UtahDraws draw odds",
  );
  await createIndexWorkbook(
    "2026 Hunt Planner Pull Species Index",
    manifest.hunt_planner,
    path.join(INDEX_OUT, "2026_HUNTPLANNER__SPECIES_INDEX.xlsx"),
    "DWR Hunt Planner",
  );

  await fs.writeFile(MANIFEST_JSON, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  console.log(JSON.stringify({
    fresh_dir: path.relative(REPO_ROOT, freshDir),
    output_root: path.relative(REPO_ROOT, OUTPUT_ROOT),
    draw_odds_workbooks: manifest.draw_odds.length,
    hunt_planner_workbooks: manifest.hunt_planner.length,
    manifest_json: path.relative(REPO_ROOT, MANIFEST_JSON),
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
