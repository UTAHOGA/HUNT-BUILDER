import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workbookPath = path.join(
  rootDir,
  "processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx",
);
const databasePath = path.join(rootDir, "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv");
const auditPath = path.join(
  rootDir,
  "audits/2025_canonical_finalization/2025_27_conservation_dwr_season_reconcile_audit.csv",
);
const applyChanges = process.argv.includes("--apply");

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
      continue;
    }
    cell += char;
  }

  row.push(cell);
  if (row.some((value) => value !== "")) rows.push(row);
  if (rows.length === 0) return [];

  const headers = rows[0].map((header) => compact(header).replace(/^\uFEFF/, ""));
  return rows.slice(1).map((values) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[index] ?? "";
    });
    return record;
  });
}

function normalizeText(value) {
  return compact(value)
    .toLowerCase()
    .replaceAll("&", "and")
    .replaceAll("/", " ")
    .replaceAll("-", " ")
    .replace(/[()]/g, " ")
    .replace(/\ble\b/g, "")
    .replace(/\bcwmu\b/g, "")
    .replace(/\bconservation\b/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeSpecies(value) {
  const text = normalizeText(value);
  if (text === "rocky mountain sheep") return "rocky mountain bighorn sheep";
  if (text === "bear") return "black bear";
  return text;
}

function normalizeSex(value) {
  const text = normalizeText(value).replace("hunters choice", "hunter s choice");
  const aliases = new Map([
    ["male only", "ram"],
    ["female only", "ewe"],
    ["ram", "ram"],
    ["ewe", "ewe"],
    ["buck", "buck"],
    ["either sex", "either sex"],
    ["hunter s choice", "either sex"],
  ]);
  return aliases.get(text) ?? text;
}

function normalizeWeapon(value) {
  const text = normalizeText(value)
    .replace(/\balw\b/g, "any legal weapon")
    .replace(/\bmuzz\b/g, "muzzleloader")
    .replace(/\bmzldr\b/g, "muzzleloader")
    .replace(/\brifle\b/g, "any legal weapon")
    .replace(/\s+/g, " ")
    .trim();
  if (text.includes("archery")) return "archery";
  if (text.includes("muzzleloader")) return "muzzleloader";
  if (text.includes("multiseason") || text.includes("multi season")) return "multiseason";
  if (text.includes("any legal weapon")) return "any legal weapon";
  return text;
}

function normalizeName(value) {
  return normalizeText(value)
    .replace(/\bprivate lands? only\b/g, "")
    .replace(/\bprivate lands?\b/g, "")
    .replace(/\bstatewide permit\b/g, "statewide")
    .replace(/\bmtns\b/g, "mtn")
    .replace(/\s+/g, " ")
    .trim();
}

function makeKey(row, source = false) {
  const species = normalizeSpecies(source ? row.species : row.Species);
  const sex = normalizeSex(source ? row.sex_type : row["SEX TYPE"]);
  const name = normalizeName(source ? row.hunt_name : row["HUNT NAME"]);
  const weapon = normalizeWeapon(source ? row.weapon : row.WEAPON);
  return [species, sex, name, weapon].join("|");
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function splitCompositeSeason(season, workbookWeapon) {
  const weapon = normalizeWeapon(workbookWeapon);
  if (weapon === "multiseason") return compact(season);
  const parts = compact(season).split(/\s*\|\s*/);
  const labels = {
    archery: ["archery", "arch"],
    muzzleloader: ["muzz", "muzzleloader"],
    "any legal weapon": ["alw", "any legal weapon"],
  };
  for (const part of parts) {
    const normalized = normalizeText(part);
    if ((labels[weapon] ?? []).some((label) => normalized.includes(label))) {
      const withoutLabel = part.replace(/^[^:]+:\s*/, "").trim();
      return withoutLabel || part;
    }
  }
  return "";
}

const databaseRows = parseCsv(await fs.readFile(databasePath, "utf8"));
const sourceRows = databaseRows
  .map((row) => ({
    hunt_code: compact(row.hunt_code).toUpperCase(),
    boundary_id: compact(row.boundary_id).replace(/\.0$/, ""),
    hunt_name: compact(row.hunt_name),
    species: compact(row.species),
    sex_type: compact(row.sex_type),
    weapon: compact(row.weapon),
    season: compact(row.season),
    source_file: compact(row.permit_allotment_2026_source_file) || compact(row.permits_2026_source),
  }))
  .filter((row) => row.hunt_code && row.hunt_name && row.species && row.sex_type && row.weapon && row.season);

const sourceByKey = new Map();
for (const row of sourceRows) {
  const key = makeKey(row, true);
  if (!sourceByKey.has(key)) sourceByKey.set(key, []);
  sourceByKey.get(key).push(row);
}

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Table 1");
const usedRange = sheet.getUsedRange(true);
const values = usedRange.values;
const headers = values[0].map((header) => compact(header));
const col = Object.fromEntries(headers.map((header, index) => [header, index]));

const auditRows = [];
let blanksBefore = 0;
let filled = 0;
let skippedNoMatch = 0;
let skippedAmbiguous = 0;

for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
  const rowValues = values[rowIndex];
  const workbookRow = Object.fromEntries(headers.map((header, index) => [header, compact(rowValues[index])]));
  if (workbookRow.SEASON) continue;

  blanksBefore += 1;
  const key = makeKey(workbookRow);
  const candidates = sourceByKey.get(key) ?? [];
  const uniqueCandidatesBySeason = new Map();
  for (const candidate of candidates) {
    const sourceSeason = splitCompositeSeason(candidate.season, workbookRow.WEAPON) || candidate.season;
    if (!sourceSeason) continue;
    const candidateKey = [candidate.hunt_code, candidate.boundary_id, sourceSeason].join("|");
    uniqueCandidatesBySeason.set(candidateKey, { ...candidate, sourceSeason });
  }

  const usableCandidates = [...uniqueCandidatesBySeason.values()];
  let status = "";
  let selected = null;
  if (usableCandidates.length === 1) {
    selected = usableCandidates[0];
    status =
      selected.hunt_code === compact(workbookRow["HUNT CODE"]).toUpperCase()
        ? "applied_dwr_code_name_weapon_match"
        : "applied_dwr_name_weapon_match_code_disagreement";
  } else if (usableCandidates.length === 0) {
    skippedNoMatch += 1;
    status = "skipped_no_dwr_name_weapon_match";
  } else {
    const distinctSeasons = [...new Set(usableCandidates.map((candidate) => candidate.sourceSeason))];
    const distinctCodes = [...new Set(usableCandidates.map((candidate) => candidate.hunt_code))];
    if (distinctSeasons.length === 1 && distinctCodes.length === 1) {
      selected = usableCandidates[0];
      status =
        selected.hunt_code === compact(workbookRow["HUNT CODE"]).toUpperCase()
          ? "applied_dwr_duplicate_same_result"
          : "applied_dwr_duplicate_same_result_code_disagreement";
    } else {
      skippedAmbiguous += 1;
      status = "skipped_ambiguous_dwr_matches";
    }
  }

  if (selected) {
    filled += 1;
    if (applyChanges) {
      sheet.getRangeByIndexes(rowIndex, col["HUNT CODE"], 1, 1).values = [[selected.hunt_code]];
      sheet.getRangeByIndexes(rowIndex, col["BOUNDARY ID"], 1, 1).values = [[selected.boundary_id]];
      sheet.getRangeByIndexes(rowIndex, col.SEASON, 1, 1).values = [[selected.sourceSeason]];
    }
  }

  auditRows.push({
    excel_row: rowIndex + 1,
    workbook_hunt_code: workbookRow["HUNT CODE"],
    workbook_boundary_id: workbookRow["BOUNDARY ID"],
    workbook_species: workbookRow.Species,
    workbook_hunt_name: workbookRow["HUNT NAME"],
    workbook_sex_type: workbookRow["SEX TYPE"],
    workbook_weapon: workbookRow.WEAPON,
    workbook_organization: workbookRow.Organization,
    matched_dwr_hunt_code: selected?.hunt_code ?? usableCandidates.map((candidate) => candidate.hunt_code).join(" | "),
    matched_dwr_boundary_id: selected?.boundary_id ?? usableCandidates.map((candidate) => candidate.boundary_id).join(" | "),
    matched_dwr_season: selected?.sourceSeason ?? usableCandidates.map((candidate) => candidate.sourceSeason).join(" | "),
    matched_dwr_source_file: selected?.source_file ?? usableCandidates.map((candidate) => candidate.source_file).join(" | "),
    status,
  });
}

await fs.mkdir(path.dirname(auditPath), { recursive: true });
const auditHeaders = [
  "excel_row",
  "workbook_hunt_code",
  "workbook_boundary_id",
  "workbook_species",
  "workbook_hunt_name",
  "workbook_sex_type",
  "workbook_weapon",
  "workbook_organization",
  "matched_dwr_hunt_code",
  "matched_dwr_boundary_id",
  "matched_dwr_season",
  "matched_dwr_source_file",
  "status",
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
      blanksBefore,
      filled,
      skippedNoMatch,
      skippedAmbiguous,
      auditRows: auditRows.length,
      auditPath,
      workbookPath: applyChanges ? workbookPath : undefined,
    },
    null,
    2,
  ),
);
