import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "standardized_long_reconcile_preview");
const YEAR_CONFIGS = [
  {
    year: 2019,
    source: path.join(
      REPO_ROOT,
      "data_truth",
      "draw_results_truth",
      "normalized",
      "canonical_yearly",
      "draw_results_2019_for_2020_canonical_yearly_draw_results.csv",
    ),
  },
  {
    year: 2020,
    source: path.join(
      REPO_ROOT,
      "data_truth",
      "draw_results_truth",
      "normalized",
      "canonical_yearly",
      "draw_results_2020_for_2021_canonical_yearly_draw_results.csv",
    ),
  },
  {
    year: 2021,
    source: path.join(
      REPO_ROOT,
      "data_truth",
      "draw_results_truth",
      "normalized",
      "canonical_yearly",
      "draw_results_2021_for_2022_canonical_yearly_draw_results.csv",
    ),
  },
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

function parseMaybeNumber(value) {
  const text = clean(value).replaceAll(",", "");
  if (!text) return "";
  const number = Number(text);
  return Number.isFinite(number) ? number : "";
}

function numericOrBlank(value) {
  const parsed = parseMaybeNumber(value);
  return parsed === "" ? "" : parsed;
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

function yearPermitValue(row, year, suffix) {
  const explicit = clean(row[`permits_${year}_${suffix}`]);
  if (explicit) return explicit;
  const generic = clean(row[`permits_year_${suffix}`]);
  return generic;
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

function isTotalRow(row) {
  return rowType(row) === "hunt_total_draw_result";
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
  return clean(speciesCode);
}

function cleanWeapon(value) {
  const text = normalize(value);
  if (!text) return "";
  if (/\bH\.?A\.?M\.?S\.?\b/i.test(text) || /\bHAM+S+\b/i.test(text)) return "HAMMS";
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

function deriveSexFromName(rawName, species, row = {}) {
  const text = normalize(rawName).toUpperCase();
  const huntType = clean(row.hunt_type || row.huntType).toUpperCase();
  if (/\bPURSUIT\b/.test(text)) return "Either";
  if (/\bBEARDED\b/.test(text)) return "Bearded";
  if (huntType === "SPORTSMAN") return "Either";
  if (species === "Black Bear" || species === "Mountain Goat" || species === "Cougar") return "Either";
  if (species === "Turkey") return "Bearded";
  if (species === "Bison") return "Hunters Choice";
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
  if (/\bEITHER SEX\b/.test(text)) return "Either Sex";
  return "";
}

function normalizeHuntType(value, row = {}) {
  const text = normalize(firstNonEmpty([
    value,
    row.hunt_type,
    row.huntType,
    row.hunt_class,
    row.huntClass,
    row.draw_design,
    row.drawDesign,
  ]));
  if (!text) return "";
  const context = normalize([text, row.hunt_name, row.huntName, row.hunt_class, row.huntClass].map(clean).join(" "));
  if (/sportsman/i.test(context)) return "Sportsman";
  if (/statewide/i.test(text) && /sportsman/i.test(context)) return "Sportsman";
  return text;
}

function normalizeDrawMethod(huntType, row = {}) {
  const text = normalizeHuntType(firstNonEmpty([
    huntType,
    row.hunt_type,
    row.huntType,
    row.hunt_class,
    row.huntClass,
    row.draw_design,
    row.drawDesign,
  ]), row);
  if (!text) return "";
  if (/sportsman/i.test(text)) return "Sportsman";
  if (/once[-\s]*in[-\s]*a[-\s]*lifetime/i.test(text)) return "O.I.L.";
  if (/limited[-\s]*entry|premium[-\s]*limited[-\s]*entry/i.test(text)) return "L.E.";
  if (/general[-\s]*season/i.test(text)) return "G.S.";
  if (/multiseason/i.test(text)) return "M.S.";
  if (/pursuit/i.test(text)) return "Pursuit";
  if (/cwmu/i.test(text)) return "C.W.M.U.";
  if (/antlerless/i.test(text)) return "A.L.";
  return text;
}

function normalizeDrawPool(value, row = {}) {
  const explicit = normalize(firstNonEmpty([value, row.draw_pool, row.drawPool]));
  if (explicit) {
    if (/random/i.test(explicit)) return "random";
    if (/max/i.test(explicit)) return "max";
    if (/split/i.test(explicit)) return "split";
    if (/bonus/i.test(explicit)) return "bonus";
    if (/preference/i.test(explicit)) return "preference";
    if (/standard/i.test(explicit)) return "standard";
    return explicit;
  }

  const context = normalize([
    row.hunt_type,
    row.huntType,
    row.hunt_class,
    row.huntClass,
    row.draw_design,
    row.drawDesign,
    row.season,
  ].map(clean).join(" "));

  if (/sportsman/i.test(context) || /general[-\s]*season/i.test(context) || /pursuit/i.test(context)) return "random";
  if (/max/i.test(context)) return "max";
  if (/split/i.test(context)) return "split";
  if (/bonus/i.test(context)) return "bonus";
  return "standard";
}

function cleanHuntName(value, row = {}) {
  let text = normalize(value)
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*\/\s*/g, "/")
    .trim();

  let changed = true;
  while (changed) {
    changed = false;

    const segments = text.split(/\s+-\s*|\s*-\s+/).map((segment) => segment.trim()).filter(Boolean);
    if (segments.length >= 3 && /^(?:Any Legal Weapon|Any Weapon|Archery|Muzzleloader|Multi-season|Rifle|Shotgun|HAMMS|HAMS|HAMSS|Pursuit Only|Hounds)$/i.test(segments.at(-1))) {
      text = segments.slice(1, -1).join(" - ");
      changed = true;
    } else if (
      segments.length === 2 &&
      /^(?:Any Legal Weapon|Any Weapon|Archery|Muzzleloader|Multi-season|Rifle|Shotgun|HAMMS|HAMS|HAMSS|Pursuit Only|Hounds)$/i.test(segments[0])
    ) {
      text = segments[1];
      changed = true;
    }

    const next = text
      .replace(/^\s*(?:Limited Entry|Premium Limited Entry|Cwmu|CWMU|Youth|General Season|Draw-only|Management|Archery|Muzzleloader|Rifle|Shotgun|Any Legal Weapon|Any Weapon|Multi-season|HAMMS|HAMS|HAMSS|ALW)\s*(?:-\s*|\s+)?/i, "")
      .replace(/\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$/i, "")
      .replace(/\bHAM+S+\b/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();
    if (next !== text) {
      text = next;
      changed = true;
    }
  }

  if (clean(row.hunt_type).toUpperCase() === "CWMU" && /\bCWMU\b$/i.test(text)) {
    text = text.replace(/\s*CWMU\s*$/i, "").trim();
  }

  const huntType = normalizeHuntType(row.hunt_type || row.huntType, row);
  const sportsmanContext = normalize([text, huntType, row.hunt_class, row.huntClass].map(clean).join(" "));
  if (/sportsman/i.test(sportsmanContext)) {
    return "Sportsman";
  }

  return text.replace(/^[-\s:]+/, "").replace(/[-\s:]+$/, "").trim();
}

function groupByCode(rows, predicate = () => true) {
  const grouped = new Map();
  for (const row of rows) {
    if (!predicate(row)) continue;
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    if (!grouped.has(code)) grouped.set(code, []);
    grouped.get(code).push(row);
  }
  return grouped;
}

function buildSummaryRows(rows, year) {
  const byCode = groupByCode(rows, (row) => isTotalRow(row) || isPointRow(row));
  const output = [];

  for (const [code, groupRows] of byCode.entries()) {
    const totalRows = groupRows.filter(isTotalRow);
    const sourceRows = totalRows.length ? totalRows : groupRows.filter(isPointRow);
    const first = sourceRows[0] || groupRows[0] || {};
    const huntName = cleanHuntName(firstNonEmpty([
      ...sourceRows.map((row) => row.hunt_name),
      ...sourceRows.map((row) => row.raw_hunt_name),
    ]), first);
    const species = firstNonEmpty(sourceRows.map((row) => row.species)) || speciesLabel(first.species, code);
    const weapon = cleanWeapon(firstNonEmpty([
      ...sourceRows.map((row) => row.weapon),
      huntName,
      first.draw_design,
      first.hunt_type,
      first.hunt_class,
    ]));
    const sex = firstNonEmpty([
      ...sourceRows.map((row) => row.sex_type || row.sex),
      deriveSexFromName(huntName, species, first),
    ]);
    const boundaryId = parseMaybeNumber(firstNonEmpty(sourceRows.map((row) => row.boundary_id)));
    const huntType = normalizeHuntType(firstNonEmpty([
      ...sourceRows.map((row) => row.hunt_type),
      ...sourceRows.map((row) => row.hunt_class),
      ...sourceRows.map((row) => row.draw_design),
    ]), first);
    const drawPool = normalizeDrawPool(firstNonEmpty(sourceRows.map((row) => row.draw_pool)), first);
    const drawMethod = normalizeDrawMethod(huntType, first);
    let permitsRes = numericOrBlank(firstNonEmpty(sourceRows.map((row) => yearPermitValue(row, year, "res"))));
    let permitsNr = numericOrBlank(firstNonEmpty(sourceRows.map((row) => yearPermitValue(row, year, "nr"))));
    let permitsTotal = numericOrBlank(firstNonEmpty(sourceRows.map((row) => yearPermitValue(row, year, "total"))));
    if (permitsTotal === "" && permitsRes !== "" && permitsNr !== "") {
      permitsTotal = Number(permitsRes) + Number(permitsNr);
    }

    output.push({
      "ACTUAL DRAW YEAR": year,
      "HUNT CODE": code,
      "BOUNDARY ID": boundaryId,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      "DRAW POOL": drawPool,
      "DRAW METHOD": drawMethod,
      [`PERMITS ${year} RES`]: permitsRes,
      [`PERMITS ${year} NR`]: permitsNr,
      [`PERMITS ${year} TOTAL`]: permitsTotal,
      _first: first,
    });
  }

  output.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return output;
}

function buildLongRows(rows, year, summaryRows) {
  const grouped = new Map();
  for (const row of rows) {
    if (!isPointRow(row)) continue;
    const code = clean(row.hunt_code).toUpperCase();
    const points = parseMaybeNumber(row.points);
    if (!code || points === "") continue;
    const key = `${code}__${points}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }

  const summaryLookup = new Map(summaryRows.map((row) => [row["HUNT CODE"], row]));
  const output = [];
  for (const [key, groupRows] of grouped.entries()) {
    const [code, pointsText] = key.split("__");
    const first = groupRows[0] || {};
    const summary = summaryLookup.get(code) || {};
    const huntName = cleanHuntName(firstNonEmpty([
      ...groupRows.map((row) => row.hunt_name),
      summary["HUNT NAME"],
      ...groupRows.map((row) => row.raw_hunt_name),
    ]), first);
    const species = firstNonEmpty(groupRows.map((row) => row.species)) || summary.SPECIES || speciesLabel(first.species, code);
    const weapon = cleanWeapon(firstNonEmpty([
      ...groupRows.map((row) => row.weapon),
      summary.WEAPON,
      huntName,
      first.draw_design,
      first.hunt_type,
      first.hunt_class,
    ]));
    const sex = firstNonEmpty([
      ...groupRows.map((row) => row.sex_type || row.sex),
      summary.SEX,
      deriveSexFromName(huntName, species, first),
    ]);
    const huntType = normalizeHuntType(firstNonEmpty([
      ...groupRows.map((row) => row.hunt_type),
      ...groupRows.map((row) => row.hunt_class),
      first.draw_design,
      summary["DRAW METHOD"],
    ]), first);
    const permitsRes = numericOrBlank(firstNonEmpty(groupRows.map((row) => yearPermitValue(row, year, "res"))) || summary[`PERMITS ${year} RES`] || "");
    const permitsNr = numericOrBlank(firstNonEmpty(groupRows.map((row) => yearPermitValue(row, year, "nr"))) || summary[`PERMITS ${year} NR`] || "");
    let permitsTotal = numericOrBlank(firstNonEmpty(groupRows.map((row) => yearPermitValue(row, year, "total"))) || summary[`PERMITS ${year} TOTAL`] || "");
    if (permitsTotal === "" && permitsRes !== "" && permitsNr !== "") {
      permitsTotal = Number(permitsRes) + Number(permitsNr);
    }
    const eligibleApplicants = numericOrBlank(sumNumeric(groupRows.map((row) => row.eligible_applicants)));
    const bonusPermits = numericOrBlank(sumNumeric(groupRows.map((row) => row.bonus_permits)));
    const regularPermits = numericOrBlank(sumNumeric(groupRows.map((row) => row.regular_permits)));
    const totalPermits = numericOrBlank(sumNumeric(groupRows.map((row) => row.total_permits)));
    const drawPool = normalizeDrawPool(firstNonEmpty(groupRows.map((row) => row.draw_pool)), first);
    const drawMethod = normalizeDrawMethod(huntType, first);
    const sourceFile = firstNonEmpty(groupRows.map((row) => row.source_file || row.draw_source_file));
    const sourcePage = numericOrBlank(firstNonEmpty(groupRows.map((row) => row.pdf_page || row.official_page)));

    output.push({
      "ACTUAL DRAW YEAR": year,
      "HUNT CODE": code,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      "HUNT TYPE": huntType,
      POINTS: numericOrBlank(pointsText),
      [`PERMITS ${year} RES`]: permitsRes,
      [`PERMITS ${year} NR`]: permitsNr,
      [`PERMITS ${year} TOTAL`]: permitsTotal,
      "ELIGIBLE APPLICANTS": eligibleApplicants,
      "BONUS PERMITS": bonusPermits,
      "REGULAR PERMITS": regularPermits,
      "TOTAL PERMITS": totalPermits,
      "DRAW POOL": drawPool,
      "DRAW METHOD": drawMethod,
      "SOURCE FILE": sourceFile,
      "SOURCE PAGE": sourcePage,
    });
  }

  output.sort((left, right) => {
    const codeCmp = left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true });
    if (codeCmp !== 0) return codeCmp;
    return Number(right.POINTS || -1) - Number(left.POINTS || -1);
  });

  return output;
}

function styleSummarySheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.getUsedRange().format = { font: { name: "Aptos", size: 10, color: "#2F2418" }, wrapText: true };
  sheet.getRange(`A1:L1`).format = {
    fill: "#5E3A1B",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:L${rowCount}`).format = { fill: "#FFFDF8", font: { color: "#2F2418" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:C${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`D2:F${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`G2:H${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`I2:L${rowCount}`).format = { horizontalAlignment: "center", numberFormat: "0" };
  sheet.getRange("A:A").format.columnWidthPx = 92;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 110;
  sheet.getRange("D:D").format.columnWidthPx = 160;
  sheet.getRange("E:E").format.columnWidthPx = 310;
  sheet.getRange("F:F").format.columnWidthPx = 120;
  sheet.getRange("G:G").format.columnWidthPx = 120;
  sheet.getRange("H:H").format.columnWidthPx = 120;
  sheet.getRange("I:I").format.columnWidthPx = 100;
  sheet.getRange("J:J").format.columnWidthPx = 120;
  sheet.getRange("K:K").format.columnWidthPx = 120;
  sheet.getRange("L:L").format.columnWidthPx = 130;
}

function styleLongSheet(sheet, rowCount) {
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  sheet.getUsedRange().format = { font: { name: "Aptos", size: 10, color: "#2F2418" }, wrapText: true };
  sheet.getRange(`A1:S1`).format = {
    fill: "#254A3F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:S${rowCount}`).format = { fill: "#F7FBF9", font: { color: "#20332D" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`C2:C${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`D2:F${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange(`G2:G${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`H2:H${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`I2:K${rowCount}`).format = { horizontalAlignment: "center", numberFormat: "0" };
  sheet.getRange(`L2:O${rowCount}`).format = { horizontalAlignment: "center", numberFormat: "0" };
  sheet.getRange(`P2:Q${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`R2:S${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange("A:A").format.columnWidthPx = 92;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 120;
  sheet.getRange("D:D").format.columnWidthPx = 300;
  sheet.getRange("E:E").format.columnWidthPx = 120;
  sheet.getRange("F:F").format.columnWidthPx = 120;
  sheet.getRange("G:G").format.columnWidthPx = 130;
  sheet.getRange("H:H").format.columnWidthPx = 78;
  sheet.getRange("I:I").format.columnWidthPx = 100;
  sheet.getRange("J:J").format.columnWidthPx = 100;
  sheet.getRange("K:K").format.columnWidthPx = 110;
  sheet.getRange("L:L").format.columnWidthPx = 110;
  sheet.getRange("M:M").format.columnWidthPx = 90;
  sheet.getRange("N:N").format.columnWidthPx = 90;
  sheet.getRange("O:O").format.columnWidthPx = 90;
  sheet.getRange("P:P").format.columnWidthPx = 110;
  sheet.getRange("Q:Q").format.columnWidthPx = 100;
  sheet.getRange("R:R").format.columnWidthPx = 180;
  sheet.getRange("S:S").format.columnWidthPx = 90;
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

const report = {
  status: "PASS",
  generated_at_utc: new Date().toISOString(),
  workbooks: [],
};

for (const config of YEAR_CONFIGS) {
  const sourceRows = readCsv(await fs.readFile(config.source, "utf8"));

  const summaryRows = buildSummaryRows(sourceRows, config.year);
  const longRows = buildLongRows(sourceRows, config.year, summaryRows);

  const workbook = Workbook.create();
  const summarySheet = workbook.worksheets.add(`${config.year} Summary`);
  const longSheet = workbook.worksheets.add(`${config.year} Long`);

  const summaryColumns = [
    "ACTUAL DRAW YEAR",
    "HUNT CODE",
    "BOUNDARY ID",
    "SPECIES",
    "HUNT NAME",
    "WEAPON",
    "SEX",
    "DRAW POOL",
    "DRAW METHOD",
    `PERMITS ${config.year} RES`,
    `PERMITS ${config.year} NR`,
    `PERMITS ${config.year} TOTAL`,
  ];
  const longColumns = [
    "ACTUAL DRAW YEAR",
    "HUNT CODE",
    "SPECIES",
    "HUNT NAME",
    "WEAPON",
    "SEX",
    "HUNT TYPE",
    "POINTS",
    `PERMITS ${config.year} RES`,
    `PERMITS ${config.year} NR`,
    `PERMITS ${config.year} TOTAL`,
    "ELIGIBLE APPLICANTS",
    "BONUS PERMITS",
    "REGULAR PERMITS",
    "TOTAL PERMITS",
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
  styleLongSheet(longSheet, longValues.length);

  const plainOutput = path.join(OUTPUT_DIR, `${config.year} standardized long.xlsx`);
  const clusteredOutput = path.join(OUTPUT_DIR, `${config.year} standardized long clustered.xlsx`);
  await exportWorkbook(workbook, plainOutput);
  await exportWorkbook(workbook, clusteredOutput);

  await savePreview(workbook, `${config.year} Summary`, `A1:L18`, path.join(PREVIEW_DIR, `${config.year}_summary_preview.png`));
  await savePreview(workbook, `${config.year} Long`, `A1:S18`, path.join(PREVIEW_DIR, `${config.year}_long_preview.png`));

  report.workbooks.push({
    year: config.year,
    output_xlsx: path.relative(REPO_ROOT, plainOutput).replaceAll("\\", "/"),
    clustered_xlsx: path.relative(REPO_ROOT, clusteredOutput).replaceAll("\\", "/"),
    summary_rows: summaryRows.length,
    long_rows: longRows.length,
  });
}

await fs.writeFile(
  path.join(OUTPUT_DIR, "standardized_long_reconcile_report.json"),
  `${JSON.stringify(report, null, 2)}\n`,
  "utf8",
);

console.log(JSON.stringify(report, null, 2));
