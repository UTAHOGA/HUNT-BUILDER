import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const SOURCE_CSV = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "canonical_yearly",
  "draw_results_2020_for_2021_canonical_yearly_draw_results.csv",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2020 PERMITS.xlsx");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2020_hunt_code_reference_report.json");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2020_hunt_code_reference_preview");
const MAIN_SHEET = "2020 Hunt Code Reference";

function clean(value) {
  return value == null ? "" : String(value).trim();
}

function normalizeWhitespace(value) {
  return clean(value).replace(/\s+/g, " ");
}

function normalizePunctuation(text) {
  return text.replace(/\s*,\s*/g, ", ").replace(/\s*\/\s*/g, "/");
}

function parseMaybeNumber(value) {
  const text = clean(value).replaceAll(",", "");
  if (!text) return "";
  const number = Number(text);
  return Number.isFinite(number) ? number : "";
}

function firstNonEmpty(values) {
  for (const value of values) {
    const text = clean(value);
    if (text) return text;
  }
  return "";
}

const PROGRAM_PREFIXES = [
  "Antlerless Rocky Mountain Bighorn Sheep",
  "Rocky Mountain Bighorn Sheep",
  "Limited Entry Archery Buck Pronghorn",
  "Limited Entry Alw (rifle) Buck Pronghorn",
  "Limited Entry Muzzleloader Buck Pronghorn",
  "Limited Entry Buck Pronghorn",
  "Limited Entry Archery Buck Deer",
  "Limited Entry Alw (rifle) Buck Deer",
  "Limited Entry Muzzleloader Buck Deer",
  "Limited Entry Multi-season Buck Deer",
  "Limited Entry Buck Deer",
  "Limited Entry Archery Bull Elk",
  "Limited Entry Alw (rifle) Bull Elk",
  "Limited Entry Muzzleloader Bull Elk",
  "Limited Entry Multi-season Bull Elk",
  "Limited Entry Bull Elk",
  "Cwmu Buck Deer",
  "CWMU Buck Deer",
  "Cwmu Bull Elk",
  "CWMU Bull Elk",
  "Cwmu Buck Pronghorn",
  "CWMU Buck Pronghorn",
  "Dedicated Hunter",
  "General Season Buck Deer",
  "Youth General Season Buck Deer",
  "Youth Dedicated Hunter",
  "Antlerless Pronghorn",
  "Doe Pronghorn",
  "Youth Doe Pronghorn",
  "Youth Antlerless Pronghorn",
  "Antlerless Moose",
  "Cow Moose",
  "Antlerless Deer",
  "Youth Antlerless Deer",
  "Antlerless Elk",
  "Youth Antlerless Elk",
  "Cow Elk",
  "Bison",
  "Buck Pronghorn",
  "Buck Deer",
  "Bull Elk",
  "Bull Moose",
  "Mountain Goat",
  "Cougar",
  "Black Bear",
  "HAMMS",
];

const LEADING_PREFIXES = [
  ...PROGRAM_PREFIXES,
  "Limited Entry",
  "Cwmu",
  "CWMU",
  "Youth",
  "General Season",
  "Draw-only",
  "Management",
  "Archery",
  "Muzzleloader",
  "Rifle",
  "Shotgun",
  "Any Legal Weapon",
  "Any Weapon",
  "Multi-season",
  "HAMMS",
  "ALW",
];

const WEAPON_SUFFIXES = [
  "Any Legal Weapon",
  "ALW",
  "Archery",
  "Muzzleloader",
  "Multi-season",
  "Mzl",
  "Muzzleloader Only",
  "Archery Only",
  "HAMMS",
  "Hounds",
  "Rifle",
  "Shotgun",
  "Any Weapon",
];

const OCR_FIXES = [
  [/\bAn y\b/g, "Any"],
  [/\bHenr y\b/g, "Henry"],
  [/\bO quirrh\b/g, "Oquirrh"],
  [/\bA rchery\b/g, "Archery"],
  [/\bArcher y\b/g, "Archery"],
  [/\bLimited[- ]Entry\b/g, "Limited Entry"],
  [/\bH\.?A\.?M\.?S\.?\b/gi, "HAMMS"],
];

const TRAILING_DESCRIPTOR_RE =
  /\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$/i;

function compactText(text) {
  return clean(text).toLowerCase().replace(/[^a-z]/g, "");
}

function splitUnitSegments(text) {
  return text
    .split(/\s+-\s*|\s*-\s+/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function isWeaponish(text) {
  const compact = compactText(text);
  return WEAPON_SUFFIXES.some((suffix) => {
    const target = compactText(suffix);
    return compact === target || compact.endsWith(target);
  });
}

function isSpeciesLead(text) {
  return /^Any\s+(?:Bull|Buck|Antlerless|Cow|Doe|Ram)\b/i.test(clean(text));
}

function deriveSpecies(rawName, huntCode) {
  const text = normalizeWhitespace(rawName).toUpperCase();
  const code = clean(huntCode).toUpperCase();
  if (code.startsWith("BI") || /\bBISON\b/.test(text)) return "Bison";
  if (code.startsWith("BR") || /\bBLACK BEAR\b/.test(text)) return "Black Bear";
  if (code.startsWith("CG") || /\bCOUGAR\b/.test(text)) return "Cougar";
  if (code.startsWith("TK") || /\bTURKEY\b/.test(text)) return "Turkey";
  if (code.startsWith("GO") || /\bGOAT\b/.test(text)) return "Mountain Goat";
  if (code.startsWith("MB") || /\bMOOSE\b/.test(text)) return "Moose";
  if (code.startsWith("DS") || /\bDESERT BIGHORN\b/.test(text)) return "Desert Bighorn Sheep";
  if (code.startsWith("RS") || /\bROCKY MOUNTAIN BIGHORN\b/.test(text)) return "Rocky Mountain Sheep";
  if (code.startsWith("PB") || code.startsWith("PD") || /\bPRONGHORN\b/.test(text)) return "Pronghorn";
  if (code.startsWith("EB") || code.startsWith("EA") || /\bELK\b/.test(text)) return "Elk";
  if (code.startsWith("DB") || code.startsWith("DA") || /\bDEER\b/.test(text)) return "Deer";
  return "";
}

function deriveWeapon(rawName, row = {}) {
  const direct = clean(row.weapon);
  if (direct) {
    if (/\bH(?:\.?A\.?M\.?S\.?|AMSS)\b/i.test(direct)) return "HAMMS";
    return direct;
  }

  const text = normalizeWhitespace(rawName);
  const suffix = text.split(/\s+-\s*/).at(-1) || "";
  for (const suffixPattern of WEAPON_SUFFIXES) {
    const re = new RegExp(`\\b${suffixPattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
    if (re.test(suffix) || re.test(text)) return suffixPattern === "HAMMS" ? "HAMMS" : suffixPattern;
  }
  if (/\bH(?:\.?A\.?M\.?S\.?|AMSS)\b/i.test(text)) return "HAMMS";
  if (/\bALW\b/i.test(text)) return "Any Legal Weapon";
  if (/\bMzl\b/i.test(text)) return "Muzzleloader";
  if (/\bPursuit\b/i.test(text)) return "Pursuit Only";
  if (/\bSPORTSMAN\b/i.test(text)) return "Any Legal Weapon";
  return "";
}

function deriveSex(rawName, species, row = {}) {
  const direct = clean(row.sex);
  if (direct) return direct;

  const text = normalizeWhitespace(rawName).toUpperCase();
  if (/\bPURSUIT\b/.test(text)) return "Either";
  if (/\bBEARDED\b/.test(text)) return "Bearded";
  if (clean(row.hunt_type).toUpperCase() === "G.S.") return "Either";
  if (species === "Black Bear" || species === "Mountain Goat" || species === "Cougar") return "Either";
  if (species === "Bison") return "Bull";
  if (species === "Deer") return "Buck";
  if (species === "Elk") return "Bull";
  if (species === "Moose") return "Bull";
  if (species === "Pronghorn") return "Buck";
  if (species === "Desert Bighorn Sheep" || species === "Rocky Mountain Sheep") return "Ram";
  if (species === "Turkey") return "Bearded";
  if (clean(row.hunt_type).toUpperCase() === "SPORTSMAN") return "Either";
  if (/\bANTLERLESS\b/.test(text)) return "Antlerless";
  if (/\bBULL\b/.test(text)) return "Bull";
  if (/\bBUCK\b/.test(text)) return "Buck";
  if (/\bCOW\b/.test(text)) return "Cow";
  if (/\bDOE\b/.test(text)) return "Doe";
  if (/\bRAM\b/.test(text)) return "Ram";
  if (/\bEWE\b/.test(text)) return "Ewe";
  return "";
}

function cleanHuntName(value, row = {}) {
  let text = normalizePunctuation(normalizeWhitespace(value));

  for (const [pattern, replacement] of OCR_FIXES) {
    text = text.replace(pattern, replacement);
  }

  let changed = true;
  while (changed) {
    changed = false;

    const segments = splitUnitSegments(text);
    if (segments.length >= 3 && isWeaponish(segments.at(-1))) {
      text = segments.slice(1, -1).join(" - ");
      changed = true;
    } else if (segments.length === 2 && (isWeaponish(segments[0]) || isSpeciesLead(segments[0]))) {
      text = segments[1];
      changed = true;
    }

    for (const prefix of LEADING_PREFIXES) {
      const prefixRegex = new RegExp(
        `^${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:\\s*-\\s*|\\s+)?`,
        "i",
      );
      const next = text.replace(prefixRegex, "");
      if (next !== text) {
        text = next.trim();
        changed = true;
      }
    }

    const descriptorNext = text.replace(TRAILING_DESCRIPTOR_RE, "");
    if (descriptorNext !== text) {
      text = descriptorNext.trim();
      changed = true;
    }

    if (clean(row.hunt_type).toUpperCase() === "CWMU" && /\bCWMU\b$/i.test(text)) {
      text = text.replace(/\s*CWMU\s*$/i, "").trim();
      changed = true;
    }

    const suffixMatch = text.match(/^(.*?)(?:\s*-\s*)([^-]+?)\s*$/);
    if (suffixMatch) {
      const head = suffixMatch[1].trim();
      const tail = suffixMatch[2].trim();
      const compactTail = compactText(tail);
      const weaponish = WEAPON_SUFFIXES.some((suffix) => {
        const compactSuffix = compactText(suffix);
        return compactTail === compactSuffix || compactTail.includes(compactSuffix);
      });
      if (weaponish) {
        text = head;
        changed = true;
      }
    }

    if (text !== text.replace(/\s{2,}/g, " ")) {
      text = text.replace(/\s{2,}/g, " ").trim();
      changed = true;
    }
  }

  return text.replace(/\bHAMMS\b/gi, "").replace(/\s{2,}/g, " ").replace(/\s*-\s*/g, " - ").replace(/^-\s*|\s*-\s*$/g, "").trim();
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
  return body.map((values) => Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""])));
}

function toCsv(rows, columns) {
  const escape = (value) => {
    const text = String(value ?? "");
    if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
    return text;
  };

  return [
    columns.map(escape).join(","),
    ...rows.map((row) => columns.map((column) => escape(row[column])).join(",")),
  ].join("\r\n");
}

function groupRowsByHuntCode(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (clean(row.row_type) !== "hunt_total_draw_result") continue;
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    if (!groups.has(code)) groups.set(code, []);
    groups.get(code).push(row);
  }
  return groups;
}

function firstUniqueTotalRows(rows) {
  const groups = groupRowsByHuntCode(rows);
  const output = [];

  for (const [code, groupRows] of groups.entries()) {
    const representative = groupRows[0];
    const rawName = firstNonEmpty([
      ...groupRows.map((row) => row.hunt_name),
      ...groupRows.map((row) => row.raw_hunt_name),
    ]);
    const species = firstNonEmpty(groupRows.map((row) => row.species)) || deriveSpecies(rawName, code);
    const weapon = firstNonEmpty(groupRows.map((row) => row.weapon)) || deriveWeapon(rawName, representative);
    const sex = firstNonEmpty(groupRows.map((row) => row.sex)) || deriveSex(rawName, species, representative);
    const huntName = firstNonEmpty(groupRows.map((row) => row.hunt_name)) || cleanHuntName(rawName, representative);
    const year = firstNonEmpty(groupRows.map((row) => row.actual_draw_year || row.year));
    const huntType = clean(representative.hunt_type).toUpperCase();

    let permitsRes = "";
    let permitsNr = "";
    let permitsTotal = "";

    for (const row of groupRows) {
      permitsRes = permitsRes || parseMaybeNumber(row.permits_year_res);
      permitsNr = permitsNr || parseMaybeNumber(row.permits_year_nr);
      permitsTotal = permitsTotal || parseMaybeNumber(row.permits_year_total);
    }

    if (huntType === "SPORTSMAN" && permitsTotal === 1 && permitsRes === "") {
      permitsRes = 1;
    }

    if (permitsTotal === "" && permitsRes !== "" && permitsNr !== "") {
      permitsTotal = permitsRes + permitsNr;
    } else if (permitsTotal === "") {
      permitsTotal = permitsRes !== "" ? permitsRes : permitsNr;
    }

    output.push({
      "ACTUAL DRAW YEAR": year,
      "HUNT CODE": code,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      [`PERMITS ${year} RES`]: permitsRes,
      [`PERMITS ${year} NR`]: permitsNr,
      [`PERMITS ${year} TOTAL`]: permitsTotal,
      _source_hunt_name: rawName,
    });
  }

  output.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return output;
}

function styleMainSheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;

  const used = sheet.getUsedRange();
  used.format = {
    font: { name: "Aptos", size: 10, color: "#2F2418" },
    wrapText: true,
  };

  sheet.getRange("A1:I1").format = {
    fill: "#5E3A1B",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:I${rowCount}`).format = {
    fill: "#FFFDF8",
    font: { color: "#2F2418" },
    wrapText: true,
  };
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`C2:C${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`D2:D${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`E2:F${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`G2:I${rowCount}`).format = { horizontalAlignment: "center", numberFormat: "0" };

  sheet.getRange("A:A").format.columnWidthPx = 92;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 165;
  sheet.getRange("D:D").format.columnWidthPx = 360;
  sheet.getRange("E:E").format.columnWidthPx = 130;
  sheet.getRange("F:F").format.columnWidthPx = 100;
  sheet.getRange("G:G").format.columnWidthPx = 130;
  sheet.getRange("H:H").format.columnWidthPx = 130;
  sheet.getRange("I:I").format.columnWidthPx = 140;
}

const sourceText = await fs.readFile(SOURCE_CSV, "utf8");
const sourceRows = parseCsv(sourceText);
const outputRows = firstUniqueTotalRows(sourceRows);

const dataCsv = toCsv(outputRows, [
  "ACTUAL DRAW YEAR",
  "HUNT CODE",
  "SPECIES",
  "HUNT NAME",
  "WEAPON",
  "SEX",
  `PERMITS 2020 RES`,
  `PERMITS 2020 NR`,
  `PERMITS 2020 TOTAL`,
]) + "\r\n";

const workbook = Workbook.create();
const dataSheet = workbook.worksheets.add(MAIN_SHEET);

const dataWorkbook = await Workbook.fromCSV(dataCsv, { sheetName: MAIN_SHEET });
const importedDataSheet = dataWorkbook.worksheets.getItem(MAIN_SHEET);
const dataRange = importedDataSheet.getUsedRange();
const dataValues = dataRange.values;
for (let rowIndex = 1; rowIndex < dataValues.length; rowIndex += 1) {
  const year = dataValues[rowIndex][0];
  const res = dataValues[rowIndex][6];
  const nr = dataValues[rowIndex][7];
  const total = dataValues[rowIndex][8];
  if (year !== "" && year != null) dataValues[rowIndex][0] = Number(year);
  if (res !== "" && res != null) dataValues[rowIndex][6] = Number(res);
  if (nr !== "" && nr != null) dataValues[rowIndex][7] = Number(nr);
  if (total !== "" && total != null) dataValues[rowIndex][8] = Number(total);
}
dataSheet.getRangeByIndexes(0, 0, dataValues.length, dataValues[0].length).values = dataValues;

styleMainSheet(dataSheet, outputRows.length + 1);

await fs.mkdir(OUTPUT_DIR, { recursive: true });
await fs.mkdir(PREVIEW_DIR, { recursive: true });

const previewData = await workbook.render({
  sheetName: MAIN_SHEET,
  range: "A1:I20",
  scale: 1,
  format: "png",
});
await fs.writeFile(path.join(PREVIEW_DIR, "data_sheet_preview.png"), Buffer.from(await previewData.arrayBuffer()));

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "final formula error scan",
});

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(OUTPUT_XLSX);

const report = {
  status: "PASS",
  source_csv: path.relative(REPO_ROOT, SOURCE_CSV),
  output_xlsx: path.relative(REPO_ROOT, OUTPUT_XLSX),
  row_count: outputRows.length,
  unique_hunt_codes: outputRows.length,
  formula_error_scan: errors.ndjson,
  column_headers: [
    "ACTUAL DRAW YEAR",
    "HUNT CODE",
    "SPECIES",
    "HUNT NAME",
    "WEAPON",
    "SEX",
    "PERMITS 2020 RES",
    "PERMITS 2020 NR",
    "PERMITS 2020 TOTAL",
  ],
  sample_transformations: outputRows
    .filter((row) => row._source_hunt_name !== row["HUNT NAME"])
    .slice(0, 12)
    .map((row) => ({
      hunt_code: row["HUNT CODE"],
      before: row._source_hunt_name,
      after: row["HUNT NAME"],
    })),
};
await fs.writeFile(OUTPUT_REPORT, `${JSON.stringify(report, null, 2)}\n`, "utf8");

console.log(JSON.stringify(report, null, 2));
