import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const RAW_POINT_ROWS = path.join(
  REPO_ROOT,
  "pipeline",
  "RAW",
  "hunt_unit_database",
  "2024",
  "csv",
  "draw_results_2023_for_2024_long.csv",
);
const RAW_HUNT_CODE_ROLLUP = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "draw_results_2023_for_2024_candidate_promotion_hunt_code_rollup.csv",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2023 PERMITS.xlsx");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2023_PERMITS_report.json");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2023_PERMITS_preview");

const YEARS = [2023];
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
  "HAMS",
  "Hounds",
  "Rifle",
  "Shotgun",
  "Any Weapon",
  "Pursuit Only",
];
const LEADING_PREFIXES = [
  "Limited Entry",
  "Premium Le",
  "Premium Limited Entry",
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
  "Bison",
  "Black Bear",
  "Cougar",
  "Deer",
  "Desert Bighorn Sheep",
  "Elk",
  "Moose",
  "Mountain Goat",
  "Pronghorn",
  "Rocky Mountain Sheep",
  "Turkey",
  "Sportsman",
];
const POINT_ROW_TYPES = new Set(["point_level_draw_result", "point_row", "point_level", "point"]);

function clean(value) {
  return value == null ? "" : String(value).trim();
}

function normalize(value) {
  return clean(value)
    .replace(/\u2019/g, "'")
    .replace(/\u2018/g, "'")
    .replace(/\u2013/g, "-")
    .replace(/\u2014/g, "-")
    .replace(/\s+/g, " ");
}

function escapeRegExp(value) {
  return clean(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseMaybeNumber(value) {
  const text = clean(value).replaceAll(",", "");
  if (!text) return "";
  const number = Number(text);
  return Number.isFinite(number) ? number : "";
}

function sumNumeric(values) {
  let total = 0;
  let found = false;
  for (const value of values) {
    const numeric = parseMaybeNumber(value);
    if (numeric === "") continue;
    total += numeric;
    found = true;
  }
  return found ? total : "";
}

function readCsv(text) {
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

function rowType(row) {
  return clean(row.row_type || row.record_type).toLowerCase();
}

function isPointRow(row) {
  return POINT_ROW_TYPES.has(rowType(row));
}

function splitUnitSegments(text) {
  return normalize(text)
    .split(/\s+-\s*|\s*-\s+/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function isWeaponish(text) {
  const compact = normalize(text).toLowerCase().replace(/[^a-z]/g, "");
  return WEAPON_SUFFIXES.some((suffix) => {
    const target = normalize(suffix).toLowerCase().replace(/[^a-z]/g, "");
    return compact === target || compact.endsWith(target);
  });
}

function isSpeciesLead(text) {
  return /^Any\s+(?:Bull|Buck|Antlerless|Cow|Doe|Ram)\b/i.test(clean(text));
}

const TRAILING_DESCRIPTOR_RE =
  /\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$/i;

function cleanHuntName(value, row = {}) {
  let text = normalize(value)
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*\/\s*/g, "/")
    .trim();

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
      const prefixRegex = new RegExp(`^${escapeRegExp(prefix)}(?:\\s*-\\s*|\\s+)?`, "i");
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

    const suffixMatch = text.match(/^(.*?)(?:\s*-\s*)([^-]+?)\s*$/);
    if (suffixMatch) {
      const head = suffixMatch[1].trim();
      const tail = suffixMatch[2].trim();
      const compactTail = normalize(tail).toLowerCase().replace(/[^a-z]/g, "");
      const weaponish = WEAPON_SUFFIXES.some((suffix) => {
        const compactSuffix = normalize(suffix).toLowerCase().replace(/[^a-z]/g, "");
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

  return normalize(text)
    .replace(/^[-–—:\s]+/, "")
    .replace(/[-–—:\s]+$/, "")
    .replace(/\bHAMMS\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function cleanWeapon(value) {
  const text = normalize(value);
  if (!text) return "";
  if (/\bH\.?A\.?M\.?S\.?\b/i.test(text) || /\bHAMS\b/i.test(text)) return "HAMMS";
  if (/\bPursuit\b/i.test(text)) return "Pursuit Only";
  if (/\bAny Legal Weapon\b/i.test(text) || /\bALW\b/i.test(text)) return "Any Legal Weapon";
  if (/\bAny Weapon\b/i.test(text)) return "Any Weapon";
  if (/\bArchery\b/i.test(text)) return "Archery";
  if (/\bMuzzleloader\b/i.test(text) || /\bMzldr\b/i.test(text) || /\bMzl\b/i.test(text)) return "Muzzleloader";
  if (/\bMulti-?season\b/i.test(text)) return "Multi-season";
  if (/\bRifle\b/i.test(text)) return "Rifle";
  if (/\bShotgun\b/i.test(text) || /\bShotgn\b/i.test(text)) return "Shotgun";
  if (/\bHounds\b/i.test(text)) return "Hounds";
  return text;
}

function firstNonEmpty(values) {
  for (const value of values) {
    const text = clean(value);
    if (text) return text;
  }
  return "";
}

function buildRollupMap(rows) {
  const map = new Map();
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    map.set(code, {
      code,
      huntName: cleanHuntName(row.hunt_name, row),
      species: clean(row.species),
      sex: clean(row.sex_type),
      huntType: clean(row.hunt_type),
      weapon: cleanWeapon(row.weapon),
      residentTotal: parseMaybeNumber(row.resident_total_permits_sum),
      nonresidentTotal: parseMaybeNumber(row.nonresident_total_permits_sum),
      totalPublic: parseMaybeNumber(row.total_public_permits_sum),
      sourceFiles: clean(row.source_files),
    });
  }
  return map;
}

function buildSummaryRows(rows, rollupMap) {
  const out = [];
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    const rollup = rollupMap.get(code);
    if (!rollup) continue;
    let resident = rollup.residentTotal;
    let nonresident = rollup.nonresidentTotal;
    let total = rollup.totalPublic;
    if ((resident === "" || resident === 0) && (nonresident === "" || nonresident === 0) && total !== "") {
      if (clean(rollup.huntType).toLowerCase() === "sportsman") resident = total;
    }
    if (total === "" && (resident !== "" || nonresident !== "")) {
      total = Number(resident || 0) + Number(nonresident || 0);
    }
    out.push({
      "ACTUAL DRAW YEAR": 2023,
      "HUNT CODE": code,
      SPECIES: rollup.species,
      "HUNT NAME": rollup.huntName,
      WEAPON: rollup.weapon,
      SEX: rollup.sex,
      "PERMITS 2023 RES": resident,
      "PERMITS 2023 NR": nonresident,
      "PERMITS 2023 TOTAL": total,
    });
  }

  out.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return out;
}

function buildPointRows(rows, rollupMap) {
  const out = [];
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    const rollup = rollupMap.get(code) || {};
    out.push({
      "ACTUAL DRAW YEAR": 2023,
      "HUNT CODE": code,
      SPECIES: firstNonEmpty([row.species, rollup.species]),
      "HUNT NAME": firstNonEmpty([rollup.huntName, cleanHuntName(row.hunt_name, row)]),
      WEAPON: cleanWeapon(firstNonEmpty([row.weapon, rollup.weapon])),
      SEX: firstNonEmpty([row.sex_type, rollup.sex]),
      "HUNT TYPE": firstNonEmpty([row.hunt_type, rollup.huntType]),
      RESIDENCY: firstNonEmpty([row.residency]),
      POINTS: parseMaybeNumber(row.points),
      "ELIGIBLE APPLICANTS": parseMaybeNumber(row.eligible_applicants),
      "BONUS PERMITS": parseMaybeNumber(row.bonus_permits),
      "REGULAR PERMITS": parseMaybeNumber(row.regular_permits),
      "TOTAL PERMITS": parseMaybeNumber(row.total_permits),
      "SUCCESS RATIO": firstNonEmpty([row.success_ratio]),
      "DRAW POOL": firstNonEmpty([row.draw_pool]),
      "DRAW METHOD": firstNonEmpty([row.draw_method]),
      "SOURCE FILE": firstNonEmpty([row.source_file]),
      "SOURCE PAGE": firstNonEmpty([row.source_pdf_page]),
    });
  }

  out.sort((left, right) => {
    const codeCmp = left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true });
    if (codeCmp !== 0) return codeCmp;
    const pointsLeft = Number(left.POINTS === "" ? -1 : left.POINTS);
    const pointsRight = Number(right.POINTS === "" ? -1 : right.POINTS);
    if (pointsRight !== pointsLeft) return pointsRight - pointsLeft;
    return left.RESIDENCY.localeCompare(right.RESIDENCY);
  });

  return out;
}

function styleSummarySheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.getUsedRange().format = { font: { name: "Aptos", size: 10, color: "#2F2418" }, wrapText: true };
  sheet.getRange(`A1:I1`).format = {
    fill: "#5E3A1B",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:I${rowCount}`).format = { fill: "#FFFDF8", font: { color: "#2F2418" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`C2:C${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`D2:D${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`E2:F${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`G2:I${rowCount}`).format = { horizontalAlignment: "center", numberFormat: "0" };
  sheet.getRange("A:A").format.columnWidthPx = 92;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 170;
  sheet.getRange("D:D").format.columnWidthPx = 330;
  sheet.getRange("E:E").format.columnWidthPx = 140;
  sheet.getRange("F:F").format.columnWidthPx = 110;
  sheet.getRange("G:G").format.columnWidthPx = 130;
  sheet.getRange("H:H").format.columnWidthPx = 130;
  sheet.getRange("I:I").format.columnWidthPx = 140;
}

function stylePointSheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.getUsedRange().format = { font: { name: "Aptos", size: 10, color: "#2F2418" }, wrapText: true };
  sheet.getRange(`A1:R1`).format = {
    fill: "#254A3F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:R${rowCount}`).format = { fill: "#F7FBF9", font: { color: "#20332D" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`G2:G${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`H2:H${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`I2:N${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`O2:P${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`Q2:R${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange("A:A").format.columnWidthPx = 88;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 120;
  sheet.getRange("D:D").format.columnWidthPx = 300;
  sheet.getRange("E:E").format.columnWidthPx = 120;
  sheet.getRange("F:F").format.columnWidthPx = 100;
  sheet.getRange("G:G").format.columnWidthPx = 135;
  sheet.getRange("H:H").format.columnWidthPx = 110;
  sheet.getRange("I:I").format.columnWidthPx = 70;
  sheet.getRange("J:J").format.columnWidthPx = 90;
  sheet.getRange("K:K").format.columnWidthPx = 90;
  sheet.getRange("L:L").format.columnWidthPx = 90;
  sheet.getRange("M:M").format.columnWidthPx = 90;
  sheet.getRange("N:N").format.columnWidthPx = 90;
  sheet.getRange("O:O").format.columnWidthPx = 90;
  sheet.getRange("P:P").format.columnWidthPx = 130;
  sheet.getRange("Q:Q").format.columnWidthPx = 180;
  sheet.getRange("R:R").format.columnWidthPx = 90;
}

async function savePreview(workbook, sheetName, range, outputPath) {
  const preview = await workbook.render({
    sheetName,
    range,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(outputPath, Buffer.from(await preview.arrayBuffer()));
}

async function exportWorkbook(workbook, outputPath) {
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
}

await fs.mkdir(OUTPUT_DIR, { recursive: true });
await fs.mkdir(PREVIEW_DIR, { recursive: true });

const rollupRows = readCsv(await fs.readFile(RAW_HUNT_CODE_ROLLUP, "utf8"));
const pointRows = readCsv(await fs.readFile(RAW_POINT_ROWS, "utf8"));
const rollupMap = buildRollupMap(rollupRows);
const summaryRows = buildSummaryRows(rollupRows, rollupMap);
const longRows = buildPointRows(pointRows, rollupMap);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("2023 Summary");
const longSheet = workbook.worksheets.add("2023 Long");

const summaryColumns = [
  "ACTUAL DRAW YEAR",
  "HUNT CODE",
  "SPECIES",
  "HUNT NAME",
  "WEAPON",
  "SEX",
  "PERMITS 2023 RES",
  "PERMITS 2023 NR",
  "PERMITS 2023 TOTAL",
];
const longColumns = [
  "ACTUAL DRAW YEAR",
  "HUNT CODE",
  "SPECIES",
  "HUNT NAME",
  "WEAPON",
  "SEX",
  "HUNT TYPE",
  "RESIDENCY",
  "POINTS",
  "ELIGIBLE APPLICANTS",
  "BONUS PERMITS",
  "REGULAR PERMITS",
  "TOTAL PERMITS",
  "SUCCESS RATIO",
  "DRAW POOL",
  "DRAW METHOD",
  "SOURCE FILE",
  "SOURCE PAGE",
];

const summaryValues = [summaryColumns, ...summaryRows.map((row) => summaryColumns.map((column) => row[column]))];
const longValues = [longColumns, ...longRows.map((row) => longColumns.map((column) => row[column]))];

summarySheet.getRangeByIndexes(0, 0, summaryValues.length, summaryValues[0].length).values = summaryValues;
longSheet.getRangeByIndexes(0, 0, longValues.length, longValues[0].length).values = longValues;

styleSummarySheet(summarySheet, summaryValues.length);
stylePointSheet(longSheet, longValues.length);

const previewSummary = await workbook.render({
  sheetName: "2023 Summary",
  range: "A1:I18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(PREVIEW_DIR, "2023_summary_preview.png"),
  Buffer.from(await previewSummary.arrayBuffer()),
);

const previewLong = await workbook.render({
  sheetName: "2023 Long",
  range: "A1:R18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(PREVIEW_DIR, "2023_long_preview.png"),
  Buffer.from(await previewLong.arrayBuffer()),
);

await exportWorkbook(workbook, OUTPUT_XLSX);

const transformedSummary = summaryRows.filter((row) => row["HUNT NAME"] !== cleanHuntName(row["HUNT NAME"]));
const transformedLong = longRows.filter((row) => row["HUNT NAME"] !== cleanHuntName(row["HUNT NAME"]));

const report = {
  status: "PASS",
  generated_at_utc: new Date().toISOString(),
  source_rollup: path.relative(REPO_ROOT, RAW_HUNT_CODE_ROLLUP).replaceAll("\\", "/"),
  source_point_rows: path.relative(REPO_ROOT, RAW_POINT_ROWS).replaceAll("\\", "/"),
  output_xlsx: path.relative(REPO_ROOT, OUTPUT_XLSX).replaceAll("\\", "/"),
  summary_rows: summaryRows.length,
  long_rows: longRows.length,
  unique_hunt_codes: rollupMap.size,
  transformed_summary_names: transformedSummary.slice(0, 25).map((row) => ({
    hunt_code: row["HUNT CODE"],
    before: row["HUNT NAME"],
    after: cleanHuntName(row["HUNT NAME"]),
  })),
  transformed_long_names: transformedLong.slice(0, 25).map((row) => ({
    hunt_code: row["HUNT CODE"],
    before: row["HUNT NAME"],
    after: cleanHuntName(row["HUNT NAME"]),
  })),
};

await fs.writeFile(OUTPUT_REPORT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
