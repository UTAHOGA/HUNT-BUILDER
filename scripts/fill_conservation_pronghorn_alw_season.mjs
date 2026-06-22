import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workbookPath = path.join(
  rootDir,
  "processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx",
);
const auditPath = path.join(
  rootDir,
  "audits/2025_canonical_finalization/2025_27_conservation_pronghorn_alw_season_fill.csv",
);
const applyChanges = process.argv.includes("--apply");
const targetSeason = "Sept 12 2026 - Sept 20 2026";

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Table 1");
const usedRange = sheet.getUsedRange(true);
const values = usedRange.values;
const headers = values[0].map((header) => compact(header));
const column = Object.fromEntries(headers.map((header, index) => [header, index]));

const auditRows = [];
for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
  const row = values[rowIndex];
  const huntCode = compact(row[column["HUNT CODE"]]);
  const species = compact(row[column.Species]);
  const sexType = compact(row[column["SEX TYPE"]]);
  const weapon = compact(row[column.WEAPON]);
  const oldSeason = compact(row[column.SEASON]);

  const isLimitedEntryAlwBuckPronghorn =
    huntCode !== "PB1000" &&
    species.toLowerCase() === "pronghorn" &&
    sexType.toLowerCase() === "buck" &&
    ["any legal weapon", "alw", "a.l.w.", "rifle"].includes(weapon.toLowerCase());

  if (!isLimitedEntryAlwBuckPronghorn || oldSeason === targetSeason) {
    continue;
  }

  if (applyChanges) {
    sheet.getRangeByIndexes(rowIndex, column.SEASON, 1, 1).values = [[targetSeason]];
  }

  auditRows.push({
    excel_row: rowIndex + 1,
    hunt_code: huntCode,
    boundary_id: compact(row[column["BOUNDARY ID"]]),
    species,
    hunt_name: compact(row[column["HUNT NAME"]]),
    sex_type: sexType,
    weapon,
    old_season: oldSeason,
    new_season: targetSeason,
    organization: compact(row[column.Organization]),
    applied: applyChanges ? "yes" : "no",
  });
}

await fs.mkdir(path.dirname(auditPath), { recursive: true });
const auditHeaders = [
  "excel_row",
  "hunt_code",
  "boundary_id",
  "species",
  "hunt_name",
  "sex_type",
  "weapon",
  "old_season",
  "new_season",
  "organization",
  "applied",
];
const lines = [auditHeaders.join(",")];
for (const row of auditRows) {
  lines.push(auditHeaders.map((header) => csvEscape(row[header])).join(","));
}
await fs.writeFile(auditPath, `${lines.join("\n")}\n`, "utf8");

if (applyChanges) {
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(workbookPath);
}

console.log(
  JSON.stringify(
    {
      mode: applyChanges ? "apply" : "dry-run",
      updates: auditRows.length,
      targetSeason,
      auditPath,
      workbookPath: applyChanges ? workbookPath : undefined,
    },
    null,
    2,
  ),
);
