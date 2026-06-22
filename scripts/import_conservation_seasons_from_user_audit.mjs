import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workbookPath = path.join(
  rootDir,
  "processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx",
);
const sourceCsvPath = "C:/Users/tyler/Desktop/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv";
const auditPath = path.join(
  rootDir,
  "audits/2025_canonical_finalization/2025_27_conservation_user_season_import_audit.csv",
);
const applyChanges = process.argv.includes("--apply");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }
    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i += 1;
      row.push(cell);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
      continue;
    }
    cell += ch;
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

function compact(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function compare(value) {
  return compact(value).toLowerCase();
}

function speciesBase(value) {
  const text = compare(value);
  if (["antlerless elk", "bull elk", "cow elk"].includes(text)) return "elk";
  if (["antlerless deer", "buck deer", "doe deer"].includes(text)) return "deer";
  if (text === "black bear") return "bear";
  if (text === "rocky mountain bighorn sheep") return "rocky mountain sheep";
  return text;
}

function sexBase(value) {
  const text = compare(value).replace("hunters choice", "hunter's choice");
  if (text === "ram") return "male only";
  if (text === "ewe") return "female only";
  return text;
}

function sourceKey(row) {
  return [
    speciesBase(row.species),
    sexBase(row.sex_type),
    compare(row["hunt name"]),
    compare(row.organization),
  ].join("|");
}

function workbookKey(row) {
  return [
    speciesBase(row[col.Species]),
    sexBase(row[col["SEX TYPE"]]),
    compare(row[col["HUNT NAME"]]),
    compare(row[col.Organization]),
  ].join("|");
}

function sourceCodeContains(workbookCode, sourceCode) {
  const target = compare(workbookCode);
  return compare(sourceCode)
    .split("|")
    .map((part) => part.trim())
    .includes(target);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function plausibleSeason(value) {
  const years = [...compact(value).matchAll(/\b(20\d{2})\b/g)].map((match) => Number(match[1]));
  return years.length === 0 || years.every((year) => year >= 2025 && year <= 2027);
}

const sourceRows = parseCsv(await fs.readFile(sourceCsvPath, "utf8"));
const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Table 1");
const usedRange = sheet.getUsedRange(true);
const values = usedRange.values;
const headers = values[0].map((header) => compact(header));
const col = Object.fromEntries(headers.map((header, index) => [header, index]));

const sourceByKey = new Map();
for (const row of sourceRows) {
  const key = sourceKey(row);
  if (!sourceByKey.has(key)) sourceByKey.set(key, []);
  sourceByKey.get(key).push(row);
}

const auditRows = [];
let applied = 0;
let skippedImplausible = 0;
let skippedNonblank = 0;
let skippedKeyMismatch = 0;
let skippedAmbiguous = 0;

for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
  const workbookRow = values[rowIndex];
  const excelRow = rowIndex + 1;
  const workbookSeason = compact(workbookRow[col.SEASON]);
  if (workbookSeason) {
    skippedNonblank += 1;
    continue;
  }

  const candidates = sourceByKey.get(workbookKey(workbookRow)) ?? [];
  const plausibleCandidates = candidates.filter((candidate) => {
    const season = compact(candidate.season);
    return season && plausibleSeason(season);
  });
  const codeMatchedSeasons = [
    ...new Set(
      plausibleCandidates
        .filter((candidate) => sourceCodeContains(workbookRow[col["HUNT CODE"]], candidate["hunt code"]))
        .map((candidate) => compact(candidate.season)),
    ),
  ];
  const plausibleSeasons = [...new Set(plausibleCandidates.map((candidate) => compact(candidate.season)))];

  let sourceSeason = "";
  let status = "";
  let sourceCodes = candidates.map((candidate) => compact(candidate["hunt code"])).join(" | ");
  if (codeMatchedSeasons.length === 1) {
    sourceSeason = codeMatchedSeasons[0];
  } else if (codeMatchedSeasons.length > 1) {
    skippedAmbiguous += 1;
    status = "skipped_ambiguous_code_matched_source_seasons";
  } else if (plausibleSeasons.length === 1) {
    sourceSeason = plausibleSeasons[0];
  } else if (plausibleSeasons.length > 1) {
    skippedAmbiguous += 1;
    status = "skipped_ambiguous_source_seasons";
  } else if (candidates.length > 0) {
    skippedImplausible += 1;
    status = "skipped_no_plausible_source_season";
  } else {
    skippedKeyMismatch += 1;
    status = "skipped_no_matching_source_row";
  }

  if (sourceSeason) {
    applied += 1;
    status = applyChanges ? "applied" : "would_apply";
    if (applyChanges) {
      sheet.getRangeByIndexes(rowIndex, col.SEASON, 1, 1).values = [[sourceSeason]];
    }
  }

  auditRows.push({
    excel_row: excelRow,
    hunt_code: compact(workbookRow[col["HUNT CODE"]]),
    boundary_id: compact(workbookRow[col["BOUNDARY ID"]]),
    species: compact(workbookRow[col.Species]),
    hunt_name: compact(workbookRow[col["HUNT NAME"]]),
    sex_type: compact(workbookRow[col["SEX TYPE"]]),
    weapon: compact(workbookRow[col.WEAPON]),
    organization: compact(workbookRow[col.Organization]),
    old_season: workbookSeason,
    source_season: sourceSeason || plausibleSeasons.join(" | "),
    new_season: status === "applied" || status === "would_apply" ? sourceSeason : workbookSeason,
    status,
    source_codes: sourceCodes,
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
  "organization",
  "old_season",
  "source_season",
  "new_season",
  "status",
  "source_codes",
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
      sourceRows: sourceRows.length,
      applied,
      skippedImplausible,
      skippedNonblank,
      skippedKeyMismatch,
      skippedAmbiguous,
      auditRows: auditRows.length,
      auditPath,
      workbookPath: applyChanges ? workbookPath : undefined,
    },
    null,
    2,
  ),
);
