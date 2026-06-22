import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const freshDir =
  process.argv.find((arg) => arg.startsWith("--fresh-dir="))?.slice("--fresh-dir=".length) ??
  path.join(rootDir, "audits/2025_canonical_finalization/fresh_live_pulls_20260621_192945");
const workbookPath = path.join(
  rootDir,
  "processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx",
);
const auditPath = path.join(
  freshDir,
  "2025_27_conservation_remaining_blanks_fresh_source_audit.csv",
);

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function normalize(value) {
  return compact(value)
    .toLowerCase()
    .replaceAll("&", "and")
    .replaceAll("/", " ")
    .replaceAll("-", " ")
    .replace(/[()]/g, " ")
    .replace(/\bmtns\b/g, "mtn")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeSpecies(value) {
  const text = normalize(value);
  if (text === "rocky mountain sheep") return "rocky mountain bighorn sheep";
  return text;
}

function normalizeSex(value) {
  const text = normalize(value);
  if (text === "male only") return "ram";
  if (text === "female only") return "ewe";
  return text;
}

function normalizeWeapon(value) {
  const text = normalize(value)
    .replace(/\balw\b/g, "any legal weapon")
    .replace(/\bmuzz\b/g, "muzzleloader")
    .replace(/\bmzldr\b/g, "muzzleloader");
  if (text.includes("muzzleloader")) return "muzzleloader";
  if (text.includes("archery")) return "archery";
  if (text.includes("any legal weapon")) return "any legal weapon";
  if (text.includes("multiseason")) return "multiseason";
  return text;
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

async function readJson(name) {
  return JSON.parse(await fs.readFile(path.join(freshDir, name), "utf8"));
}

const freshFileNames = await fs.readdir(freshDir);
const dwrTableFileNames = freshFileNames.filter(
  (name) =>
    /^dwr_huntboundary_.*\.json$/i.test(name) &&
    !["dwr_huntboundary_home.html", "dwr_huntboundary_hasetup.json"].includes(name) &&
    name !== "dwr_huntboundary_home.json",
);

const dwrRowsRaw = [];
for (const fileName of dwrTableFileNames) {
  const parsed = await readJson(fileName);
  if (Array.isArray(parsed)) dwrRowsRaw.push(...parsed);
}

const dwrRows = dwrRowsRaw.map((row) => ({
  code: compact(row.HUNT_NBR),
  species: compact(row.SPECIES),
  sex: compact(row.GENDER),
  name: compact(row.HUNT_NAME),
  weapon: compact(row.WEAPON),
  season: compact(row.SEASON_DATE_TEXT),
  quotaRes: compact(row.QUOTA_RES),
  quotaNr: compact(row.QUOTA_NRES),
  quotaTotal: compact(row.QUOTA),
}));

const utahDrawsFileNames = freshFileNames.filter((name) => /^utahdraws_.*_mht\d+\.json$/i.test(name));
const utahDrawsRowsRaw = [];
for (const fileName of utahDrawsFileNames) {
  const parsed = await readJson(fileName);
  if (Array.isArray(parsed?.Data)) utahDrawsRowsRaw.push(...parsed.Data);
}

const utahDrawsRows = utahDrawsRowsRaw.map((row) => ({
  code: compact(row.HuntCode),
  name: compact(row.HuntName),
  category: compact(row.HuntCategoryName),
  subtype: compact(row.SpeciesSubtypeName),
  mapUrl: compact(row.HuntMapURL),
}));

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Table 1");
const values = sheet.getUsedRange(true).values;
const headers = values[0].map((header) => compact(header));
const col = Object.fromEntries(headers.map((header, index) => [header, index]));

const auditRows = [];
for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
  const row = Object.fromEntries(headers.map((header, index) => [header, compact(values[rowIndex][index])]));
  if (row.SEASON) continue;

  const species = normalizeSpecies(row.Species);
  const sex = normalizeSex(row["SEX TYPE"]);
  const name = normalize(row["HUNT NAME"]);
  const weapon = normalizeWeapon(row.WEAPON);
  const sameNameDwr = dwrRows.filter(
    (candidate) =>
      normalizeSpecies(candidate.species) === species &&
      normalizeSex(candidate.sex) === sex &&
      normalize(candidate.name) === name,
  );
  const exactDwr = sameNameDwr.filter((candidate) => normalizeWeapon(candidate.weapon) === weapon);
  const sameNameUtahDraws = utahDrawsRows.filter((candidate) => normalize(candidate.name) === name);
  const exactCodeUtahDraws = utahDrawsRows.filter((candidate) => candidate.code === row["HUNT CODE"]);

  let recommendation = "manual_review";
  if (exactDwr.length === 0 && sameNameDwr.length > 0) {
    recommendation = "no_exact_dwr_weapon_match_review_weapon_or_code";
  } else if (exactDwr.length > 1) {
    recommendation = "multiple_exact_dwr_matches_review_season_label";
  } else if (exactDwr.length === 1) {
    recommendation = "single_exact_dwr_match_available";
  }

  auditRows.push({
    excel_row: rowIndex + 1,
    workbook_hunt_code: row["HUNT CODE"],
    workbook_boundary_id: row["BOUNDARY ID"],
    workbook_species: row.Species,
    workbook_hunt_name: row["HUNT NAME"],
    workbook_sex_type: row["SEX TYPE"],
    workbook_weapon: row.WEAPON,
    organization: row.Organization,
    exact_dwr_candidates: exactDwr
      .map((candidate) => `${candidate.code}|${candidate.weapon}|${candidate.season}|quota=${candidate.quotaTotal}`)
      .join(" ; "),
    same_name_dwr_candidates: sameNameDwr
      .map((candidate) => `${candidate.code}|${candidate.weapon}|${candidate.season}|quota=${candidate.quotaTotal}`)
      .join(" ; "),
    same_name_utahdraws_codes: sameNameUtahDraws
      .map((candidate) => `${candidate.code}|${candidate.category}|${candidate.subtype}`)
      .join(" ; "),
    exact_workbook_code_utahdraws: exactCodeUtahDraws
      .map((candidate) => `${candidate.code}|${candidate.name}|${candidate.category}|${candidate.subtype}`)
      .join(" ; "),
    recommendation,
  });
}

const auditHeaders = [
  "excel_row",
  "workbook_hunt_code",
  "workbook_boundary_id",
  "workbook_species",
  "workbook_hunt_name",
  "workbook_sex_type",
  "workbook_weapon",
  "organization",
  "exact_dwr_candidates",
  "same_name_dwr_candidates",
  "same_name_utahdraws_codes",
  "exact_workbook_code_utahdraws",
  "recommendation",
];
const lines = [auditHeaders.join(",")];
for (const row of auditRows) {
  lines.push(auditHeaders.map((header) => csvEscape(row[header])).join(","));
}
await fs.writeFile(auditPath, `${lines.join("\n")}\n`, "utf8");

console.log(
  JSON.stringify(
    {
      freshDir,
      auditPath,
      remainingBlankRows: auditRows.length,
      recommendations: auditRows.reduce((acc, row) => {
        acc[row.recommendation] = (acc[row.recommendation] ?? 0) + 1;
        return acc;
      }, {}),
    },
    null,
    2,
  ),
);
