import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const REPO = path.resolve(path.dirname(__filename), "..");
const SOURCE_DIR = path.join(
  REPO,
  "audits",
  "2025_canonical_finalization",
  "fresh_live_pulls_20260621_192945",
);
const OUT_DIR = path.join(REPO, "outputs", "2026_PERMITS=2027_MODEL_json_documents");

const TRACKED_TERMS = [
  "bison",
  "black_bear",
  "cougar",
  "deer",
  "desert_bighorn_sheep",
  "elk",
  "moose",
  "mountain_goat",
  "pronghorn",
  "rocky_mountain_bighorn_sheep",
  "rocky_mtn_bighorn_sheep",
  "sportsman",
  "tribal",
  "turkey",
];

const SKIP_TERMS = [
  "coyote",
  "goose",
  "grouse",
  "sandhill_crane",
  "sharp_tailed",
  "swan",
  "waterfowl",
  "hasetup",
];

function cleanName(name) {
  return name
    .replace(/\.json$/i, "")
    .replace(/^utahdraws_/, "")
    .replace(/^dwr_huntboundary_/, "huntboundary_")
    .replace(/[^A-Za-z0-9=._-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
}

function isTrackedFile(name) {
  const lower = name.toLowerCase();
  if (!lower.endsWith(".json")) return false;
  if (lower.includes("summary") || lower.includes("supplement")) return false;
  if (SKIP_TERMS.some((term) => lower.includes(term))) return false;
  return TRACKED_TERMS.some((term) => lower.includes(term));
}

function sourceKind(name) {
  if (name.startsWith("utahdraws_")) return "UtahDraws draw odds";
  if (name.startsWith("dwr_huntboundary_")) return "DWR HuntBoundary metadata";
  return "Reference/audit JSON";
}

function asRows(payload) {
  if (Array.isArray(payload)) return payload.filter((row) => row && typeof row === "object");
  if (payload && typeof payload === "object") {
    for (const key of ["Data", "data", "rows", "Results", "results"]) {
      if (Array.isArray(payload[key])) return payload[key].filter((row) => row && typeof row === "object");
    }
  }
  return [];
}

function toScalar(value) {
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value;
  if (typeof value === "number" || typeof value === "boolean") return value;
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function unique(list) {
  return [...new Set(list.filter((value) => value !== "" && value !== null && value !== undefined))];
}

function makeHuntsRows(rows, fileName) {
  return rows.map((row) => ({
    source_file: fileName,
    source_kind: sourceKind(fileName),
    hunt_id: row.HuntID ?? row.huntId ?? row.ID ?? "",
    hunt_code: row.HuntCode ?? row.HUNT_NUMBER ?? row.hunt_code ?? row.huntNumber ?? "",
    hunt_name: row.HuntName ?? row.HUNT_NAME ?? row.hunt_name ?? row.Name ?? "",
    category: row.HuntCategoryName ?? row.category ?? "",
    species: row.SpeciesSubtypeName ?? row.species ?? row.SPECIES ?? "",
    map_url: row.HuntMapURL ?? row.MapURL ?? "",
    master_hunt_type_id: row.MasterHuntTypeID ?? "",
    point_calculation_type_id: row.PointCalculationTypeID ?? "",
    is_bonus_point: row.IsBonusPoint ?? "",
    resident_quota: row.ResidentQuotaQuantity ?? "",
    nonresident_quota: row.NonResidentQuotaQuantity ?? "",
    total_quota: row.QuotaQuantity ?? "",
    season_weapon_count: Array.isArray(row.SeasonWeapons) ? row.SeasonWeapons.length : "",
    odds_row_count: Array.isArray(row.OddsList) ? row.OddsList.length : "",
  }));
}

function makeOddsRows(rows, fileName) {
  const odds = [];
  for (const row of rows) {
    const list = Array.isArray(row.OddsList) ? row.OddsList : [];
    for (const item of list) {
      odds.push({
        source_file: fileName,
        hunt_id: row.HuntID ?? item.HuntID ?? "",
        hunt_code: row.HuntCode ?? "",
        hunt_name: row.HuntName ?? "",
        category: row.HuntCategoryName ?? "",
        species: row.SpeciesSubtypeName ?? "",
        residency_type_id: item.ResidencyTypeID ?? "",
        is_youth: item.IsYouth ?? "",
        point: item.Point ?? item.PreferencePoint ?? "",
        participant_count: item.ParticipantCount ?? "",
        successful_count: item.SuccessfulCount ?? "",
        successful_regular_round: item.SuccessfulByRegularRoundCount ?? "",
        successful_max_point_round: item.SuccessfulByMaxPointRoundCount ?? "",
        all_choices_successful: item.AllChoicesSuccessfulCount ?? "",
        youth_round_first_choice_unsuccessful: item.YouthRoundFirstChoiceUnsuccessful ?? "",
        is_historical_data: item.IsHistoricalData ?? "",
      });
    }
  }
  return odds;
}

function makeSeasonRows(rows, fileName) {
  const seasons = [];
  for (const row of rows) {
    const list = Array.isArray(row.SeasonWeapons) ? row.SeasonWeapons : [];
    for (const item of list) {
      seasons.push({
        source_file: fileName,
        hunt_id: row.HuntID ?? item.HuntID ?? "",
        hunt_code: row.HuntCode ?? "",
        hunt_name: row.HuntName ?? "",
        category: row.HuntCategoryName ?? "",
        species: row.SpeciesSubtypeName ?? "",
        weapon: item.WeaponName ?? "",
        season_start: item.SeasonStartDate ?? "",
        season_end: item.SeasonEndDate ?? "",
        special_instruction: item.SpecialInstruction ?? "",
        uncertain_date_range: item.UnCertainDateRange ?? "",
        license_year: item.LicenseYear ?? "",
      });
    }
  }
  return seasons;
}

function matrixFromObjects(rows, headers) {
  return [headers, ...rows.map((row) => headers.map((header) => toScalar(row[header])))];
}

function colLetter(indexZeroBased) {
  let n = indexZeroBased + 1;
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function writeSheet(sheet, title, rows, headers) {
  sheet.showGridLines = false;
  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: "#1F4E3D",
    font: { bold: true, color: "#FFFFFF", size: 14 },
  };
  sheet.getRange("A2").values = [[`Rows: ${rows.length}`]];
  const tableRows = matrixFromObjects(rows, headers);
  const lastCol = colLetter(headers.length - 1);
  const startRow = 4;
  const range = sheet.getRange(`A${startRow}:${lastCol}${startRow + tableRows.length - 1}`);
  range.values = tableRows;
  sheet.getRange(`A${startRow}:${lastCol}${startRow}`).format = {
    fill: "#DDEBE3",
    font: { bold: true, color: "#163428" },
  };
  range.format.borders = { preset: "all", style: "thin", color: "#D5DED8" };
  range.format.wrapText = true;
  range.format.autofitColumns();
  range.format.autofitRows();
  sheet.freezePanes.freezeRows(startRow);
  if (rows.length > 0) {
    sheet.tables.add(`A${startRow}:${lastCol}${startRow + tableRows.length - 1}`, true, `${sheet.name.replace(/[^A-Za-z0-9]/g, "")}Table`);
  }
}

async function buildWorkbook(sourceFile, payload, rows) {
  const stem = cleanName(sourceFile);
  const workbook = Workbook.create();
  const hunts = makeHuntsRows(rows, sourceFile);
  const odds = makeOddsRows(rows, sourceFile);
  const seasons = makeSeasonRows(rows, sourceFile);
  const summaryRows = [
    { field: "source_file", value: sourceFile },
    { field: "source_kind", value: sourceKind(sourceFile) },
    { field: "hunt_records", value: rows.length },
    { field: "unique_hunt_codes", value: unique(hunts.map((r) => r.hunt_code)).length },
    { field: "odds_rows", value: odds.length },
    { field: "season_weapon_rows", value: seasons.length },
    { field: "license_years", value: unique(seasons.map((r) => r.license_year)).join(", ") },
    { field: "notes", value: "Document export only. Not ingested into canonical prediction truth." },
  ];

  writeSheet(workbook.worksheets.add("Summary"), `${stem} Summary`, summaryRows, ["field", "value"]);
  writeSheet(workbook.worksheets.add("Hunts"), "Hunt Records", hunts, [
    "source_file",
    "source_kind",
    "hunt_id",
    "hunt_code",
    "hunt_name",
    "category",
    "species",
    "map_url",
    "master_hunt_type_id",
    "point_calculation_type_id",
    "is_bonus_point",
    "resident_quota",
    "nonresident_quota",
    "total_quota",
    "season_weapon_count",
    "odds_row_count",
  ]);
  writeSheet(workbook.worksheets.add("Odds"), "Odds / Applicant Rows", odds, [
    "source_file",
    "hunt_id",
    "hunt_code",
    "hunt_name",
    "category",
    "species",
    "residency_type_id",
    "is_youth",
    "point",
    "participant_count",
    "successful_count",
    "successful_regular_round",
    "successful_max_point_round",
    "all_choices_successful",
    "youth_round_first_choice_unsuccessful",
    "is_historical_data",
  ]);
  writeSheet(workbook.worksheets.add("Seasons"), "Season / Weapon Rows", seasons, [
    "source_file",
    "hunt_id",
    "hunt_code",
    "hunt_name",
    "category",
    "species",
    "weapon",
    "season_start",
    "season_end",
    "special_instruction",
    "uncertain_date_range",
    "license_year",
  ]);

  const xlsxPath = path.join(OUT_DIR, `${stem}.xlsx`);
  const pngPreviewPath = path.join(OUT_DIR, "_previews", `${stem}_summary.png`);
  await fs.mkdir(path.dirname(pngPreviewPath), { recursive: true });
  const preview = await workbook.render({ sheetName: "Summary", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(pngPreviewPath, new Uint8Array(await preview.arrayBuffer()));
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(xlsxPath);
  return { source_file: sourceFile, stem, xlsx_path: xlsxPath, preview_path: pngPreviewPath, hunts: hunts.length, odds: odds.length, seasons: seasons.length };
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const entries = await fs.readdir(SOURCE_DIR);
  const tracked = entries.filter(isTrackedFile).sort();
  const skipped = entries
    .filter((name) => name.toLowerCase().endsWith(".json") && !tracked.includes(name))
    .sort();
  const manifest = [];
  for (const file of tracked) {
    const filePath = path.join(SOURCE_DIR, file);
    const payload = JSON.parse(await fs.readFile(filePath, "utf8"));
    const rows = asRows(payload);
    const result = await buildWorkbook(file, payload, rows);
    manifest.push({ ...result, status: "created_xlsx" });
    console.log(`created ${result.xlsx_path}`);
  }
  await fs.writeFile(
    path.join(OUT_DIR, "json_document_manifest.json"),
    JSON.stringify({ output_dir: OUT_DIR, tracked_count: tracked.length, skipped_count: skipped.length, generated: manifest, skipped }, null, 2) + "\n",
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
