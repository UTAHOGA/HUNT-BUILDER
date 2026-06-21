import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const DATA_DIR = path.join(REPO_ROOT, "data_truth", "draw_results_truth", "normalized", "canonical_yearly");
const CLEAN_2021_DIR = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "rebuilt_clean",
  "2021_PERMITS=2022_MODEL",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "draw_results_standardized_preview");

const YEARS = [2019, 2020, 2021];
const POINT_ROW_TYPES = new Set(["point_level_draw_result", "point_row", "point_level", "point"]);

function clean(value) {
  return value == null ? "" : String(value).trim();
}

function normalizeWhitespace(value) {
  return clean(value).replace(/\s+/g, " ");
}

function escapeRegExp(value) {
  return clean(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripWeaponFromHuntName(name, weapon) {
  let text = normalizeWhitespace(name);
  const weaponText = normalizeWhitespace(weapon);
  if (!text || !weaponText) return text;

  const exactPattern = new RegExp(`(^|\\s[-–—:]\\s|\\s+)${escapeRegExp(weaponText)}(?=$|[\\s.-])`, "gi");
  text = text.replace(exactPattern, " ");
  text = text.replace(new RegExp(`\\b${escapeRegExp(weaponText)}\\b\\.?`, "gi"), " ");
  text = text.replace(/\s*-\s*$/, "");
  text = text.replace(/\s{2,}/g, " ").trim();
  text = text.replace(/^[-–—:\s]+/, "").trim();
  text = text.replace(/[-–—:\s]+$/, "").trim();
  text = text.replace(/\s*-\s*/g, " - ");
  return normalizeWhitespace(text);
}

function speciesLabel(speciesCode, huntCode = "") {
  const code = clean(speciesCode).toUpperCase();
  const hunt = clean(huntCode).toUpperCase();
  if (code === "BISON" || hunt.startsWith("BI")) return "Bison";
  if (code === "BLACK_BEAR" || hunt.startsWith("BR")) return "Black Bear";
  if (code === "COUGAR" || hunt.startsWith("CG")) return "Cougar";
  if (code === "DEER" || hunt.startsWith("DB") || hunt.startsWith("DA")) return "Deer";
  if (code === "DESERT_BIGHORN_SHEEP" || hunt.startsWith("DS")) return "Desert Bighorn Sheep";
  if (code === "ELK" || hunt.startsWith("EB") || hunt.startsWith("EA")) return "Elk";
  if (code === "MOOSE" || hunt.startsWith("MB")) return "Moose";
  if (code === "MOUNTAIN_GOAT" || hunt.startsWith("GO")) return "Mountain Goat";
  if (code === "PRONGHORN" || hunt.startsWith("PB") || hunt.startsWith("PD")) return "Pronghorn";
  if (code === "ROCKY_MOUNTAIN_BIGHORN_SHEEP" || hunt.startsWith("RS")) return "Rocky Mountain Sheep";
  if (code === "TURKEY" || hunt.startsWith("TK")) return "Turkey";
  return "";
}

function deriveWeaponFromName(rawName) {
  const text = normalizeWhitespace(rawName);
  const upper = text.toUpperCase();
  if (/\bH\.?A\.?M\.?S\.?\b/.test(upper) || /\bHAMS\b/.test(upper)) return "HAMMS";
  if (/\bPURSUIT\b/.test(upper)) return "Pursuit Only";
  if (/\bANY LEGAL WEAPON\b/.test(upper) || /\bALW\b/.test(upper) || /\bSPORTSMAN\b/.test(upper)) return "Any Legal Weapon";
  if (/\bARCHERY\b/.test(upper)) return "Archery";
  if (/\bMUZZLELOADER\b/.test(upper) || /\bMZL\b/.test(upper)) return "Muzzleloader";
  if (/\bMULTI-?SEASON\b/.test(upper)) return "Multi-season";
  if (/\bRIFLE\b/.test(upper)) return "Rifle";
  if (/\bSHOTGUN\b/.test(upper)) return "Shotgun";
  if (/\bHOUNDS\b/.test(upper)) return "Hounds";
  return "";
}

function deriveSexFromName(rawName, species, row = {}) {
  const text = normalizeWhitespace(rawName).toUpperCase();
  const huntType = clean(row.hunt_type).toUpperCase();
  if (/\bPURSUIT\b/.test(text)) return "Either";
  if (/\bBEARDED\b/.test(text)) return "Bearded";
  if (huntType === "G.S." || huntType === "SPORTSMAN") return "Either";
  if (species === "Black Bear" || species === "Mountain Goat" || species === "Cougar") return "Either";
  if (species === "Turkey") return "Bearded";
  if (species === "Bison") return "Bull";
  if (species === "Deer") return "Buck";
  if (species === "Elk") return "Bull";
  if (species === "Moose") return "Bull";
  if (species === "Pronghorn") return "Buck";
  if (species === "Desert Bighorn Sheep" || species === "Rocky Mountain Sheep") return "Ram";
  if (/\bANTLERLESS\b/.test(text)) return "Antlerless";
  if (/\bBULL\b/.test(text)) return "Bull";
  if (/\bBUCK\b/.test(text)) return "Buck";
  if (/\bCOW\b/.test(text)) return "Cow";
  if (/\bDOE\b/.test(text)) return "Doe";
  if (/\bRAM\b/.test(text)) return "Ram";
  if (/\bEWE\b/.test(text)) return "Ewe";
  return "";
}

function parseMaybeNumber(value) {
  const text = clean(value).replaceAll(",", "");
  if (!text) return "";
  const number = Number(text);
  return Number.isFinite(number) ? number : "";
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

function rowType(row) {
  return clean(row.row_type || row.record_type).toLowerCase();
}

function isPointRow(row) {
  return POINT_ROW_TYPES.has(rowType(row));
}

function summaryRowType(row) {
  const rt = rowType(row);
  if (rt.includes("sportsman")) return "SPORTSMAN_TOTAL";
  return "TOTAL";
}

function firstNonEmpty(values) {
  for (const value of values) {
    const text = clean(value);
    if (text) return text;
  }
  return "";
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

function normalize2021TotalsRows(rows) {
  return rows.map((row) => {
    const rawName = clean(row.hunt_name);
    const species = speciesLabel(row.species, row.hunt_code);
    const weapon = deriveWeaponFromName(rawName);
    const residency = clean(row.residency);
    const totalPermits = clean(row.permits_total);
    return {
      hunt_code: clean(row.hunt_code),
      hunt_name: stripWeaponFromHuntName(rawName, weapon),
      raw_hunt_name: rawName,
      species,
      weapon,
      sex: deriveSexFromName(rawName, species, row),
      hunt_type: clean(row.hunt_type),
      hunt_class: clean(row.hunt_type),
      hunt_draw_class: clean(row.draw_design),
      residency,
      points: "",
      eligible_applicants: clean(row.applicants_total),
      bonus_permits: clean(row.bonus_permits),
      regular_permits: clean(row.regular_permits),
      total_permits: clean(row.permits_total),
      success_ratio: clean(row.success_ratio),
      p_draw: clean(row.success_rate),
      p_draw_percent: clean(row.success_rate),
      permits_year_res: residency.toLowerCase() === "resident" ? totalPermits : "",
      permits_year_nr: residency.toLowerCase() === "nonresident" ? totalPermits : "",
      permits_year_total: residency ? "" : totalPermits,
      row_type: "hunt_total_draw_result",
      record_type: "hunt_total_draw_result",
    };
  });
}

function normalize2021PointRows(rows) {
  return rows.map((row) => {
    const rawName = clean(row.hunt_name);
    const species = speciesLabel(row.species, row.hunt_code);
    const weapon = deriveWeaponFromName(rawName);
    return {
      hunt_code: clean(row.hunt_code),
      hunt_name: stripWeaponFromHuntName(rawName, weapon),
      raw_hunt_name: rawName,
      species,
      weapon,
      sex: deriveSexFromName(rawName, species, row),
      hunt_type: clean(row.hunt_type),
      hunt_class: clean(row.hunt_type),
      hunt_draw_class: clean(row.draw_design),
      residency: clean(row.residency),
      points: clean(row.point_level),
      eligible_applicants: clean(row.applicants),
      bonus_permits: clean(row.bonus_permits),
      regular_permits: clean(row.regular_permits),
      total_permits: clean(row.permits),
      success_ratio: clean(row.success_ratio),
      p_draw: clean(row.success_rate),
      p_draw_percent: clean(row.success_rate),
      row_type: "point_level_draw_result",
      record_type: "point_level_draw_result",
    };
  });
}

function buildSummaryRows(rows, year) {
  const byCode = new Map();
  for (const row of rows) {
    if (summaryRowType(row) !== "TOTAL") continue;
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    if (!byCode.has(code)) byCode.set(code, []);
    byCode.get(code).push(row);
  }

  const out = [];
  for (const [code, group] of byCode.entries()) {
    const representative = group[0];
    const huntName = stripWeaponFromHuntName(
      firstNonEmpty(group.map((row) => row.hunt_name)),
      firstNonEmpty(group.map((row) => row.weapon)),
    );
    out.push({
      "ACTUAL DRAW YEAR": year,
      "HUNT CODE": code,
      SPECIES: firstNonEmpty(group.map((row) => row.species)),
      "HUNT NAME": huntName,
      WEAPON: firstNonEmpty(group.map((row) => row.weapon)),
      SEX: firstNonEmpty(group.map((row) => row.sex)),
      [`PERMITS ${year} RES`]: sumNumeric(group.map((row) => row.permits_year_res)),
      [`PERMITS ${year} NR`]: sumNumeric(group.map((row) => row.permits_year_nr)),
      [`PERMITS ${year} TOTAL`]: (() => {
        const res = sumNumeric(group.map((row) => row.permits_year_res));
        const nr = sumNumeric(group.map((row) => row.permits_year_nr));
        if (res !== "" || nr !== "") return Number(res || 0) + Number(nr || 0);
        return firstNonEmpty(group.map((row) => row.permits_year_total));
      })(),
      _source_hunt_name: clean(representative.raw_hunt_name || representative.hunt_name),
    });
  }

  out.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return out;
}

function buildSummaryMatrix(rows, year) {
  return buildSummaryRows(rows, year).map((row) => [
    year,
    row["HUNT CODE"],
    row.SPECIES,
    row["HUNT NAME"],
    row.WEAPON,
    row.SEX,
    parseMaybeNumber(row[`PERMITS ${year} RES`]),
    parseMaybeNumber(row[`PERMITS ${year} NR`]),
    parseMaybeNumber(row[`PERMITS ${year} TOTAL`]),
  ]);
}

function buildPointRows(rows, year) {
  const summaryLookup = new Map();
  for (const summary of buildSummaryRows(rows, year)) {
    summaryLookup.set(summary["HUNT CODE"], summary);
  }

  const out = [];
  for (const row of rows) {
    if (!isPointRow(row)) continue;
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    const summary = summaryLookup.get(code) || {};
    out.push({
      "ACTUAL DRAW YEAR": year,
      "HUNT CODE": code,
      SPECIES: firstNonEmpty([row.species, summary.SPECIES]),
      "HUNT NAME": stripWeaponFromHuntName(
        firstNonEmpty([row.hunt_name, summary["HUNT NAME"], row.raw_hunt_name]),
        firstNonEmpty([row.weapon, summary.WEAPON]),
      ),
      WEAPON: firstNonEmpty([row.weapon, summary.WEAPON]),
      SEX: firstNonEmpty([row.sex, summary.SEX]),
      "HUNT TYPE": firstNonEmpty([row.hunt_type, row.hunt_class, row.hunt_draw_class]),
      RESIDENCY: firstNonEmpty([row.residency]),
      POINTS: firstNonEmpty([row.points]),
      "ELIGIBLE APPLICANTS": firstNonEmpty([row.eligible_applicants]),
      "BONUS PERMITS": firstNonEmpty([row.bonus_permits]),
      "REGULAR PERMITS": firstNonEmpty([row.regular_permits]),
      "TOTAL PERMITS": firstNonEmpty([row.total_permits]),
      "SUCCESS RATIO": firstNonEmpty([row.success_ratio]),
      P_DRAW: firstNonEmpty([row.p_draw]),
      "P_DRAW_PERCENT": firstNonEmpty([row.p_draw_percent]),
      "ROW TYPE": "POINT_ROW",
      _source_row_type: clean(row.row_type || row.record_type),
    });
  }

  out.sort((left, right) => {
    const codeCmp = left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true });
    if (codeCmp !== 0) return codeCmp;
    const pointsLeft = Number(left.POINTS === "" ? -1 : left.POINTS);
    const pointsRight = Number(right.POINTS === "" ? -1 : right.POINTS);
    return pointsRight - pointsLeft;
  });
  return out;
}

function buildPointMatrix(rows, year) {
  return buildPointRows(rows, year).map((row) => [
    year,
    row["HUNT CODE"],
    row.SPECIES,
    row["HUNT NAME"],
    row.WEAPON,
    row.SEX,
    row["HUNT TYPE"],
    row.RESIDENCY,
    parseMaybeNumber(row.POINTS),
    parseMaybeNumber(row["ELIGIBLE APPLICANTS"]),
    parseMaybeNumber(row["BONUS PERMITS"]),
    parseMaybeNumber(row["REGULAR PERMITS"]),
    parseMaybeNumber(row["TOTAL PERMITS"]),
    row["SUCCESS RATIO"],
    row.P_DRAW,
    row["P_DRAW_PERCENT"],
    row["ROW TYPE"],
  ]);
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
  sheet.getRange("C:C").format.columnWidthPx = 165;
  sheet.getRange("D:D").format.columnWidthPx = 360;
  sheet.getRange("E:E").format.columnWidthPx = 130;
  sheet.getRange("F:F").format.columnWidthPx = 100;
  sheet.getRange("G:G").format.columnWidthPx = 130;
  sheet.getRange("H:H").format.columnWidthPx = 130;
  sheet.getRange("I:I").format.columnWidthPx = 140;
}

function stylePointSheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.getUsedRange().format = { font: { name: "Aptos", size: 10, color: "#2F2418" }, wrapText: true };
  sheet.getRange(`A1:Q1`).format = {
    fill: "#254A3F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:Q${rowCount}`).format = { fill: "#F7FBF9", font: { color: "#20332D" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`G2:G${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`H2:H${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`I2:O${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`P2:Q${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange("A:A").format.columnWidthPx = 88;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 130;
  sheet.getRange("D:D").format.columnWidthPx = 280;
  sheet.getRange("E:E").format.columnWidthPx = 120;
  sheet.getRange("F:F").format.columnWidthPx = 110;
  sheet.getRange("G:G").format.columnWidthPx = 120;
  sheet.getRange("H:H").format.columnWidthPx = 110;
  sheet.getRange("I:I").format.columnWidthPx = 70;
  sheet.getRange("J:J").format.columnWidthPx = 90;
  sheet.getRange("K:K").format.columnWidthPx = 90;
  sheet.getRange("L:L").format.columnWidthPx = 90;
  sheet.getRange("M:M").format.columnWidthPx = 90;
  sheet.getRange("N:N").format.columnWidthPx = 90;
  sheet.getRange("O:O").format.columnWidthPx = 90;
  sheet.getRange("P:P").format.columnWidthPx = 110;
  sheet.getRange("Q:Q").format.columnWidthPx = 90;
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

const report = {
  status: "PASS",
  generated_at_utc: new Date().toISOString(),
  output_dir: path.relative(REPO_ROOT, OUTPUT_DIR).replaceAll("\\", "/"),
  preview_dir: path.relative(REPO_ROOT, PREVIEW_DIR).replaceAll("\\", "/"),
  workbooks: [],
};

await fs.mkdir(OUTPUT_DIR, { recursive: true });
await fs.mkdir(PREVIEW_DIR, { recursive: true });

const yearRows = new Map();
const yearSources = new Map();
for (const year of YEARS) {
  if (year === 2021) {
    const totalsPath = path.join(CLEAN_2021_DIR, "draw_results_2021_for_2022_CLEAN_PARENT_PDF_HUNT_TOTALS.csv");
    const pointsPath = path.join(CLEAN_2021_DIR, "draw_results_2021_for_2022_CLEAN_PARENT_PDF_POINT_ROWS.csv");
    const totalsText = await fs.readFile(totalsPath, "utf8");
    const pointsText = await fs.readFile(pointsPath, "utf8");
    yearSources.set(year, {
      summaryRows: normalize2021TotalsRows(readCsv(totalsText)),
      pointRows: normalize2021PointRows(readCsv(pointsText)),
    });
  } else {
    const sourcePath = path.join(DATA_DIR, `draw_results_${year}_for_${year + 1}_canonical_yearly_draw_results.csv`);
    const text = await fs.readFile(sourcePath, "utf8");
    const rows = readCsv(text);
    yearSources.set(year, { summaryRows: rows, pointRows: rows });
  }
}

const comparisonWorkbook = Workbook.create();
const comparisonOutput = path.join(OUTPUT_DIR, "draw_results_standardized_comparison_summary.xlsx");

for (const year of YEARS) {
  const source = yearSources.get(year) || { summaryRows: [], pointRows: [] };
  const sheetName = `${year} Summary`;
  const sheet = comparisonWorkbook.worksheets.add(sheetName);
  const dataRows = buildSummaryMatrix(source.summaryRows, year);
  const values = [["ACTUAL DRAW YEAR", "HUNT CODE", "SPECIES", "HUNT NAME", "WEAPON", "SEX", `PERMITS ${year} RES`, `PERMITS ${year} NR`, `PERMITS ${year} TOTAL`], ...dataRows];
  sheet.getRangeByIndexes(0, 0, values.length, values[0].length).values = values;
  styleSummarySheet(sheet, values.length);
  await savePreview(
    comparisonWorkbook,
    sheetName,
    "A1:I18",
    path.join(PREVIEW_DIR, `${year}_comparison_summary_preview.png`),
  );
}

await exportWorkbook(comparisonWorkbook, comparisonOutput);

report.workbooks.push({
  kind: "comparison_summary",
  output_xlsx: path.relative(REPO_ROOT, comparisonOutput).replaceAll("\\", "/"),
  years: YEARS,
  sheets: YEARS.map((year) => `${year} Summary`),
});

for (const year of YEARS) {
  const source = yearSources.get(year) || { summaryRows: [], pointRows: [] };
  const workbook = Workbook.create();
  const summarySheet = workbook.worksheets.add("Summary");
  const pointSheet = workbook.worksheets.add("Points");

  const summaryRows = buildSummaryRows(source.summaryRows, year);
  const summaryValues = [["ACTUAL DRAW YEAR", "HUNT CODE", "SPECIES", "HUNT NAME", "WEAPON", "SEX", `PERMITS ${year} RES`, `PERMITS ${year} NR`, `PERMITS ${year} TOTAL`], ...buildSummaryMatrix(source.summaryRows, year)];
  summarySheet.getRangeByIndexes(0, 0, summaryValues.length, summaryValues[0].length).values = summaryValues;
  styleSummarySheet(summarySheet, summaryValues.length);

  const pointRows = buildPointRows(source.pointRows, year);
  const pointValues = [["ACTUAL DRAW YEAR", "HUNT CODE", "SPECIES", "HUNT NAME", "WEAPON", "SEX", "HUNT TYPE", "RESIDENCY", "POINTS", "ELIGIBLE APPLICANTS", "BONUS PERMITS", "REGULAR PERMITS", "TOTAL PERMITS", "SUCCESS RATIO", "P_DRAW", "P_DRAW_PERCENT", "ROW TYPE"], ...buildPointMatrix(source.pointRows, year)];
  pointSheet.getRangeByIndexes(0, 0, pointValues.length, pointValues[0].length).values = pointValues;
  stylePointSheet(pointSheet, pointValues.length);

  const outputXlsx = path.join(OUTPUT_DIR, `${year} standardized long.xlsx`);
  await savePreview(workbook, "Summary", "A1:I18", path.join(PREVIEW_DIR, `${year}_summary_preview.png`));
  await savePreview(workbook, "Points", "A1:Q18", path.join(PREVIEW_DIR, `${year}_points_preview.png`));
  await exportWorkbook(workbook, outputXlsx);

  const summaryCodes = new Set(summaryRows.map((row) => row["HUNT CODE"]));
  const pointCodes = new Set(pointRows.map((row) => row["HUNT CODE"]));
  report.workbooks.push({
    year,
    output_xlsx: path.relative(REPO_ROOT, outputXlsx).replaceAll("\\", "/"),
    summary_rows: summaryRows.length,
    point_rows: pointRows.length,
    unique_summary_codes: summaryCodes.size,
    unique_point_codes: pointCodes.size,
  });
}

const reportPath = path.join(OUTPUT_DIR, "draw_results_standardized_comparison_report.json");
await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

console.log(JSON.stringify(report, null, 2));
