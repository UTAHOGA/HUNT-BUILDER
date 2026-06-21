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
  "draw_results_2019_for_2020_canonical_yearly_draw_results.csv",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2019_hunt_code_reference.xlsx");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2019_hunt_code_reference_report.json");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2019_hunt_code_reference_preview");
const MAIN_SHEET = "2019 Hunt Code Reference";
const NOTES_SHEET = "Source Notes";

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
  [/\bLimited[- ]Entry\b/g, "Limited Entry"],
];

const TRAILING_DESCRIPTOR_RE =
  /\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$/i;

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

    if (char === "\"") {
      if (inQuotes && next === "\"") {
        field += "\"";
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
  return body.map((values) =>
    Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""])),
  );
}

function toCsv(rows, columns) {
  const escape = (value) => {
    const text = String(value ?? "");
    if (/[",\r\n]/.test(text)) return `"${text.replaceAll("\"", "\"\"")}"`;
    return text;
  };

  return [
    columns.map(escape).join(","),
    ...rows.map((row) => columns.map((column) => escape(row[column])).join(",")),
  ].join("\r\n");
}

function normalizeWhitespace(text) {
  return clean(text).replace(/\s+/g, " ");
}

function normalizePunctuation(text) {
  return text.replace(/\s*,\s*/g, ", ").replace(/\s*\/\s*/g, "/");
}

function compactText(text) {
  return text.toLowerCase().replace(/[^a-z]/g, "");
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
    } else if (
      segments.length === 2 &&
      (isWeaponish(segments[0]) || isSpeciesLead(segments[0]))
    ) {
      text = segments[1];
      changed = true;
    }

    for (const prefix of LEADING_PREFIXES) {
      const prefixRegex = new RegExp(`^${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:\\s*-\\s*|\\s+)?`, "i");
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

  text = text.replace(/\s+/g, " ").replace(/\s*,\s*/g, ", ").trim();
  return text.trim();
}

function firstUniqueTotalRows(rows) {
  const seen = new Set();
  const out = [];

  for (const row of rows) {
    if (clean(row.row_type) !== "hunt_total_draw_result") continue;
    const code = clean(row.hunt_code).toUpperCase();
    if (!code || seen.has(code)) continue;
    seen.add(code);
    out.push({
      "ACTUAL DRAW YEAR": clean(row.actual_draw_year),
      "HUNT CODE": code,
      "HUNT NAME": cleanHuntName(row.hunt_name, row),
      "PERMITS TOTAL": clean(row.permits_year_total),
      _source_hunt_name: clean(row.hunt_name),
    });
  }

  out.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return out;
}

function styleMainSheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;

  const used = sheet.getUsedRange();
  used.format = {
    font: { name: "Aptos", size: 10, color: "#2F2418" },
    wrapText: true,
  };

  sheet.getRange("A1:D1").format = {
    fill: "#5E3A1B",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange(`A2:D${rowCount}`).format = {
    fill: "#FFFDF8",
    font: { color: "#2F2418" },
    wrapText: true,
  };
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0" };
  sheet.getRange(`D2:D${rowCount}`).format = { numberFormat: "0" };

  sheet.getRange("A:A").format.columnWidthPx = 120;
  sheet.getRange("B:B").format.columnWidthPx = 95;
  sheet.getRange("C:C").format.columnWidthPx = 330;
  sheet.getRange("D:D").format.columnWidthPx = 110;
}

function styleNotesSheet(sheet) {
  sheet.showGridLines = false;
  sheet.getRange("A1:B1").format = {
    fill: "#5E3A1B",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange("A2:B7").format = {
    font: { name: "Aptos", size: 10, color: "#2F2418" },
    wrapText: true,
  };
  sheet.getRange("A:A").format.columnWidthPx = 180;
  sheet.getRange("B:B").format.columnWidthPx = 920;
}

const sourceText = await fs.readFile(SOURCE_CSV, "utf8");
const sourceRows = parseCsv(sourceText);
const outputRows = firstUniqueTotalRows(sourceRows);

const dataCsv = toCsv(outputRows, [
  "ACTUAL DRAW YEAR",
  "HUNT CODE",
  "HUNT NAME",
  "PERMITS TOTAL",
]) + "\r\n";

const workbook = Workbook.create();
const dataSheet = workbook.worksheets.add(MAIN_SHEET);
const notesSheet = workbook.worksheets.add(NOTES_SHEET);

const dataWorkbook = await Workbook.fromCSV(dataCsv, { sheetName: MAIN_SHEET });
const importedDataSheet = dataWorkbook.worksheets.getItem(MAIN_SHEET);
const dataRange = importedDataSheet.getUsedRange();
const dataValues = dataRange.values;
for (let rowIndex = 1; rowIndex < dataValues.length; rowIndex += 1) {
  const year = dataValues[rowIndex][0];
  const permitsTotal = dataValues[rowIndex][3];
  if (year !== "" && year != null) dataValues[rowIndex][0] = Number(year);
  if (permitsTotal !== "" && permitsTotal != null) dataValues[rowIndex][3] = Number(permitsTotal);
}
dataSheet.getRangeByIndexes(0, 0, dataValues.length, dataValues[0].length).values = dataValues;

notesSheet.getRange("A1:B7").values = [
  ["Field", "Notes"],
  ["Source", path.relative(REPO_ROOT, SOURCE_CSV).replaceAll("\\", "/")],
  ["Row selection", "One row per unique hunt code from hunt_total_draw_result rows for actual_draw_year 2019."],
  ["HUNT NAME cleanup", "Removed obvious species/program prefixes, trailing weapon suffixes, and common OCR spacing artifacts."],
  ["Purpose", "Keep the hunt code reference readable while preserving the canonical 2019 permit total."],
  ["Caveat", "Display names are normalized for the workbook; the source canonical CSV remains unchanged."],
  ["Example", "Bison - Book Cliffs (hunter's Choice) - Any Legal Weapon -> Book Cliffs"],
];

styleMainSheet(dataSheet, outputRows.length + 1);
styleNotesSheet(notesSheet);

await fs.mkdir(OUTPUT_DIR, { recursive: true });
await fs.mkdir(PREVIEW_DIR, { recursive: true });

const previewData = await workbook.render({
  sheetName: MAIN_SHEET,
  range: `A1:D20`,
  scale: 1,
  format: "png",
});
await fs.writeFile(path.join(PREVIEW_DIR, "data_sheet_preview.png"), Buffer.from(await previewData.arrayBuffer()));

const previewNotes = await workbook.render({
  sheetName: NOTES_SHEET,
  range: "A1:B8",
  scale: 1,
  format: "png",
});
await fs.writeFile(path.join(PREVIEW_DIR, "notes_sheet_preview.png"), Buffer.from(await previewNotes.arrayBuffer()));

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
  cleanup_rules: [
    "Strip obvious leading program/species labels from hunt_name when they are glued into the PDF-extracted text.",
    "Strip trailing weapon suffixes like Any Legal Weapon, Archery, Muzzleloader, Rifle, and Shotgun.",
    "Remove common OCR spacing artifacts in names like An y and Henr y.",
    "Preserve the source canonical CSV unchanged.",
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
