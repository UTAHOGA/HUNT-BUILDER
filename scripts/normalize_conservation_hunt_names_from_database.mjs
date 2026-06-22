import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = path.resolve(
  "processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx",
);
const databasePath = path.resolve("pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv");
const auditPath = path.resolve(
  "audits/2025_canonical_finalization/2025_27_conservation_hunt_name_database_normalization.csv",
);
const applyChanges = process.argv.includes("--apply");
const strictKeyMode = process.argv.includes("--strict-key");

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

  const headers = rows[0].map((header) => header.replace(/^\uFEFF/, ""));
  return rows.slice(1).map((values) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[index] ?? "";
    });
    return record;
  });
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function writeAudit(rows) {
  const headers = [
    "excel_row",
    "hunt_code",
    "boundary_id",
    "species",
    "sex_type",
    "weapon",
    "old_hunt_name",
    "new_hunt_name",
    "database_hunt_name_raw",
    "database_hunt_name_clean",
    "score",
    "field_score",
    "status",
    "reason",
  ];
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((header) => csvEscape(row[header])).join(","));
  }
  return fs.writeFile(auditPath, `${lines.join("\n")}\n`, "utf8");
}

function compact(text) {
  return String(text ?? "")
    .replace(/[’‘]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeForCompare(text) {
  return compact(text)
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\bmtns\b/g, "mountains")
    .replace(/\bmtn\b/g, "mountain")
    .replace(/\bcyn\b/g, "canyon")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function keyPart(text) {
  return normalizeForCompare(text);
}

function speciesKey(text) {
  const value = normalizeForCompare(text);
  if (value === "antlerless elk" || value === "bull elk" || value === "cow elk") return "elk";
  if (value === "antlerless deer" || value === "buck deer" || value === "doe deer") return "deer";
  if (value === "black bear") return "bear";
  if (value === "rocky mountain bighorn sheep" || value === "rocky mountain sheep") {
    return "rocky mountain sheep";
  }
  return value;
}

function strictKey(row) {
  return [
    compact(row.hunt_code).toUpperCase(),
    speciesKey(row.species),
    keyPart(row.sex_type),
  ].join("|");
}

function cleanHuntName(text) {
  let name = compact(text);

  name = name.replace(/\s+-\s+Statewide Permit$/i, " - Statewide");
  name = name.replace(
    /^(Black Bear|Bear|Bison|Buck Deer|Deer|Bull Elk|Elk|Moose|Mountain Goat|Rocky Mountain Bighorn Sheep|Desert Bighorn Sheep|Pronghorn|Pronghorn Antelope|Turkey|Cougar)\s+-\s+Statewide$/i,
    "Statewide",
  );
  name = name.replace(/\bStatewide Permit\b/gi, "Statewide");
  name = name.replace(/\s+\bPermit\b$/i, "");

  name = name.replace(/\s*\((hunter'?s choice|early|late|mid|conservation)\)\s*$/i, "");
  name = name.replace(/\s+-\s*(Any Legal Weapon|Archery|Muzzleloader|Multi[- ]?season|Multiseason|HAMS|HAMMS|Rifle|Shotgun).*$/i, "");
  name = name.replace(/\s+-\s*(Hunter'?s Choice|Early|Late|Mid)\s*$/i, "");

  name = name.replace(
    /\s+\b(Bull|Buck|Cow|Doe|Ram|Ewe|Male Only|Female Only|Either Sex|Hunter'?s Choice|Bearded|Antlerless)\s+(Black Bear|Bear|Bison|Deer|Elk|Moose|Mountain Goat|Rocky Mountain Bighorn Sheep|Rocky Mountain Sheep|Desert Bighorn Sheep|Pronghorn|Turkey|Cougar)\b$/i,
    "",
  );
  name = name.replace(
    /\s+\b(Black Bear|Bear|Bison|Buck Deer|Deer|Bull Elk|Elk|Moose|Mountain Goat|Rocky Mountain Bighorn Sheep|Rocky Mountain Sheep|Desert Bighorn Sheep|Pronghorn|Turkey|Cougar)\b$/i,
    "",
  );
  name = name.replace(/\s+\b(Premium|Premium LE|Limited Entry|LE|OIL|Once-in-a-lifetime|Conservation)\b$/i, "");

  return compact(name);
}

function isBadHuntName(name) {
  const normalized = normalizeForCompare(name);
  if (!normalized) return true;
  const badPhrases = [
    "any legal weapon",
    "muzzleloader",
    "multiseason",
    "multi season",
    "archery",
    "hams",
    "hamms",
    "statewide permit",
    "hunters choice",
    "female only",
    "male only",
    "either sex",
    "cow only",
    "bull only",
    "buck only",
    "bearded",
  ];
  return badPhrases.some((phrase) => normalized.includes(phrase));
}

function levenshteinSimilarity(a, b) {
  const left = normalizeForCompare(a);
  const right = normalizeForCompare(b);
  if (!left && !right) return 1;
  if (!left || !right) return 0;

  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  const current = Array.from({ length: right.length + 1 }, () => 0);

  for (let i = 1; i <= left.length; i += 1) {
    current[0] = i;
    for (let j = 1; j <= right.length; j += 1) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1;
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + cost,
      );
    }
    for (let j = 0; j <= right.length; j += 1) previous[j] = current[j];
  }

  return 1 - previous[right.length] / Math.max(left.length, right.length);
}

function tokenSet(text) {
  return new Set(normalizeForCompare(text).split(" ").filter(Boolean));
}

function tokenJaccard(a, b) {
  const left = tokenSet(a);
  const right = tokenSet(b);
  if (left.size === 0 && right.size === 0) return 1;
  if (left.size === 0 || right.size === 0) return 0;
  let intersection = 0;
  for (const token of left) {
    if (right.has(token)) intersection += 1;
  }
  return intersection / new Set([...left, ...right]).size;
}

function comparableByContainment(current, candidate) {
  const left = normalizeForCompare(current);
  const right = normalizeForCompare(candidate);
  if (!left || !right) return false;
  if (left === right) return true;
  const shorter = left.length < right.length ? left : right;
  const longer = left.length < right.length ? right : left;
  return shorter.length >= 10 && longer.includes(shorter);
}

function fieldScore(workbookRow, databaseRow) {
  let score = 0;
  if (compact(workbookRow.boundary_id) && compact(workbookRow.boundary_id) === compact(databaseRow.boundary_id)) score += 3;
  if (normalizeForCompare(workbookRow.species) && normalizeForCompare(workbookRow.species) === normalizeForCompare(databaseRow.species)) score += 2;
  if (normalizeForCompare(workbookRow.sex_type) && normalizeForCompare(workbookRow.sex_type) === normalizeForCompare(databaseRow.sex_type)) score += 1;
  if (normalizeForCompare(workbookRow.weapon) && normalizeForCompare(workbookRow.weapon) === normalizeForCompare(databaseRow.weapon)) score += 1;
  return score;
}

function chooseCandidate(workbookRow, databaseRows) {
  const currentClean = cleanHuntName(workbookRow.hunt_name);
  const scored = databaseRows
    .map((databaseRow) => {
      const raw = compact(databaseRow.hunt_name);
      const clean = cleanHuntName(raw);
      const nameScore = Math.max(
        levenshteinSimilarity(currentClean, clean),
        tokenJaccard(currentClean, clean),
        comparableByContainment(currentClean, clean) ? 0.91 : 0,
      );
      return {
        databaseRow,
        raw,
        clean,
        nameScore,
        fieldScore: fieldScore(workbookRow, databaseRow),
      };
    })
    .filter((item) => item.clean && !isBadHuntName(item.clean))
    .sort((a, b) => b.nameScore - a.nameScore || b.fieldScore - a.fieldScore);

  if (scored.length === 0) return null;
  return scored[0];
}

const databaseText = await fs.readFile(databasePath, "utf8");
const databaseRows = parseCsv(databaseText);
const databaseByCode = new Map();
const databaseByStrictKey = new Map();
for (const row of databaseRows) {
  const code = compact(row.hunt_code).toUpperCase();
  if (!code) continue;
  if (!databaseByCode.has(code)) databaseByCode.set(code, []);
  databaseByCode.get(code).push(row);

  const key = strictKey(row);
  if (!databaseByStrictKey.has(key)) databaseByStrictKey.set(key, []);
  databaseByStrictKey.get(key).push(row);
}

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("Table 1");
const usedRange = sheet.getUsedRange(true);
const values = usedRange.values;
const headers = values[0].map((header) => compact(header));
const column = Object.fromEntries(headers.map((header, index) => [header.toLowerCase(), index]));

for (const required of ["hunt code", "boundary id", "species", "hunt name", "sex type", "weapon"]) {
  if (!(required in column)) {
    throw new Error(`Missing required workbook column: ${required}`);
  }
}

const auditRows = [];
let updated = 0;
let alreadyAligned = 0;
let skipped = 0;

for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
  const row = values[rowIndex];
  const workbookRow = {
    hunt_code: compact(row[column["hunt code"]]).toUpperCase(),
    boundary_id: compact(row[column["boundary id"]]),
    species: compact(row[column.species]),
    hunt_name: compact(row[column["hunt name"]]),
    sex_type: compact(row[column["sex type"]]),
    weapon: compact(row[column.weapon]),
  };
  const excelRow = rowIndex + 1;
  const candidates = strictKeyMode
    ? databaseByStrictKey.get(strictKey(workbookRow)) ?? []
    : databaseByCode.get(workbookRow.hunt_code) ?? [];

  if (candidates.length === 0) {
    skipped += 1;
    auditRows.push({
      excel_row: excelRow,
      ...workbookRow,
      old_hunt_name: workbookRow.hunt_name,
      new_hunt_name: workbookRow.hunt_name,
      database_hunt_name_raw: "",
      database_hunt_name_clean: "",
      score: "",
      field_score: "",
      status: strictKeyMode
        ? "skipped_no_database_strict_key_match"
        : "skipped_no_database_hunt_code_match",
      reason: strictKeyMode
        ? "No DATABASE.csv rows with matching hunt_code + species + sex_type."
        : "No DATABASE.csv rows with matching hunt_code.",
    });
    continue;
  }

  if (strictKeyMode) {
    const cleanNames = new Map();
    for (const candidate of candidates) {
      const clean = cleanHuntName(candidate.hunt_name);
      if (clean && !isBadHuntName(clean)) {
        cleanNames.set(normalizeForCompare(clean), clean);
      }
    }
    if (cleanNames.size !== 1) {
      skipped += 1;
      auditRows.push({
        excel_row: excelRow,
        ...workbookRow,
        old_hunt_name: workbookRow.hunt_name,
        new_hunt_name: workbookRow.hunt_name,
        database_hunt_name_raw: candidates.map((row) => compact(row.hunt_name)).join(" | "),
        database_hunt_name_clean: [...cleanNames.values()].join(" | "),
        score: "",
        field_score: "",
        status: "skipped_ambiguous_database_strict_key",
        reason: "Strict key matched multiple different clean DATABASE.csv hunt names.",
      });
      continue;
    }
  }

  const best = chooseCandidate(workbookRow, candidates);
  if (!best) {
    skipped += 1;
    auditRows.push({
      excel_row: excelRow,
      ...workbookRow,
      old_hunt_name: workbookRow.hunt_name,
      new_hunt_name: workbookRow.hunt_name,
      database_hunt_name_raw: "",
      database_hunt_name_clean: "",
      score: "",
      field_score: "",
      status: "skipped_no_clean_database_hunt_name",
      reason: "Matching code existed, but no clean database hunt_name was safe to use.",
    });
    continue;
  }

  const currentClean = cleanHuntName(workbookRow.hunt_name);
  const dbClean = best.clean;
  const same = normalizeForCompare(currentClean) === normalizeForCompare(dbClean);
  const shouldUpdate =
    !same &&
    !isBadHuntName(dbClean) &&
    (best.nameScore >= 0.86 ||
      (best.nameScore >= 0.78 && best.fieldScore >= 4) ||
      comparableByContainment(currentClean, dbClean));

  if (same) {
    alreadyAligned += 1;
    auditRows.push({
      excel_row: excelRow,
      ...workbookRow,
      old_hunt_name: workbookRow.hunt_name,
      new_hunt_name: workbookRow.hunt_name,
      database_hunt_name_raw: best.raw,
      database_hunt_name_clean: dbClean,
      score: best.nameScore.toFixed(3),
      field_score: best.fieldScore,
      status: "already_aligned",
      reason: "Clean workbook name already matches clean database name.",
    });
  } else if (shouldUpdate) {
    updated += 1;
    if (applyChanges) {
      sheet.getRangeByIndexes(rowIndex, column["hunt name"], 1, 1).values = [[dbClean]];
    }
    auditRows.push({
      excel_row: excelRow,
      ...workbookRow,
      old_hunt_name: workbookRow.hunt_name,
      new_hunt_name: dbClean,
      database_hunt_name_raw: best.raw,
      database_hunt_name_clean: dbClean,
      score: best.nameScore.toFixed(3),
      field_score: best.fieldScore,
      status: applyChanges ? "updated_to_database_clean_name" : "would_update_to_database_clean_name",
      reason: "Matching hunt_code and close cleaned hunt_name.",
    });
  } else {
    skipped += 1;
    auditRows.push({
      excel_row: excelRow,
      ...workbookRow,
      old_hunt_name: workbookRow.hunt_name,
      new_hunt_name: workbookRow.hunt_name,
      database_hunt_name_raw: best.raw,
      database_hunt_name_clean: dbClean,
      score: best.nameScore.toFixed(3),
      field_score: best.fieldScore,
      status: "skipped_not_close_enough",
      reason: "Same hunt_code, but cleaned names were not close enough for a safe automatic replacement.",
    });
  }
}

await fs.mkdir(path.dirname(auditPath), { recursive: true });
await writeAudit(auditRows);

if (applyChanges) {
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(workbookPath);
}

console.log(
  JSON.stringify(
    {
      mode: applyChanges ? "apply" : "dry-run",
      workbookRows: values.length - 1,
      updated,
      alreadyAligned,
      skipped,
      auditPath,
      workbookPath: applyChanges ? workbookPath : undefined,
    },
    null,
    2,
  ),
);
