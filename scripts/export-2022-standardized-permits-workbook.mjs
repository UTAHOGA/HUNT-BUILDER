import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const RAW_POINT_ROWS = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "canonical_yearly",
  "draw_results_2022_for_2023_canonical_yearly_draw_results.csv",
);
const RAW_HUNT_CODE_ROLLUP = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "draw_results_2022_for_2023_candidate_promotion_hunt_code_rollup.csv",
);
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2022 PERMITS.xlsx");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2022_PERMITS_report.json");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2022_PERMITS_preview");

const YEARS = [2022];
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
  "HAMSS",
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
  "HAMSS",
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

function deriveSexFromName(rawName, species, row = {}) {
  const text = normalize(rawName).toUpperCase();
  const huntType = clean(row.hunt_type).toUpperCase();
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
    .replace(/\bHAM+S+\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
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
  return "";
}

function normalizeHuntType(value, row = {}) {
  const text = normalize(firstNonEmpty([value, row.hunt_type, row.huntType, row.hunt_class, row.huntClass, row.draw_design, row.drawDesign]));
  if (!text) return "";
  const context = normalize([text, row.hunt_name, row.huntName, row.hunt_class, row.huntClass].map(clean).join(" "));
  if (/sportsman/i.test(context)) return "Sportsman";
  if (/statewide/i.test(text) && /sportsman/i.test(context)) return "Sportsman";
  return text;
}

function normalizeDrawMethod(huntType, row = {}) {
  const text = normalizeHuntType(firstNonEmpty([huntType, row.hunt_type, row.huntType, row.hunt_class, row.huntClass, row.draw_design, row.drawDesign]), row);
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
  const text = normalize(firstNonEmpty([value, row.draw_pool, row.drawPool]));
  if (text) {
    if (/random/i.test(text)) return "random";
    if (/max/i.test(text)) return "max";
    if (/split/i.test(text)) return "split";
    if (/bonus/i.test(text)) return "bonus";
    if (/preference/i.test(text)) return "preference";
    return text;
  }

  const context = normalize([row.hunt_type, row.huntType, row.hunt_class, row.huntClass, row.draw_design, row.drawDesign, row.season].map(clean).join(" "));
  if (/sportsman/i.test(context) || /general[-\s]*season/i.test(context) || /pursuit/i.test(context)) return "random";
  if (/split/i.test(context)) return "split";
  if (/max/i.test(context)) return "max";
  if (/limited[-\s]*entry|once[-\s]*in[-\s]*a[-\s]*lifetime|cwmu|antlerless|premium[-\s]*limited[-\s]*entry/i.test(context)) {
    return "bonus";
  }
  return "";
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
    const species = speciesLabel(row.species, row.hunt_code);
    const huntType = normalizeHuntType(row.hunt_type, row);
    const huntName = cleanHuntName(row.hunt_name, row);
    map.set(code, {
      code,
      huntName,
      species,
      sex: firstNonEmpty([clean(row.sex_type), deriveSexFromName(row.hunt_name, species, row)]),
      huntType,
      weapon: cleanWeapon(firstNonEmpty([row.weapon, row.hunt_name, huntType])),
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
    const huntName = firstNonEmpty([rollup.huntName, rollup.huntType, cleanHuntName(row.hunt_name, row)]);
    out.push({
      "ACTUAL DRAW YEAR": 2022,
      "HUNT CODE": code,
      SPECIES: firstNonEmpty([rollup.species, speciesLabel(row.species, code)]),
      "HUNT NAME": huntName,
      WEAPON: firstNonEmpty([rollup.weapon, cleanWeapon(firstNonEmpty([row.weapon, row.hunt_name, rollup.huntType]))]),
      SEX: firstNonEmpty([rollup.sex, deriveSexFromName(huntName, firstNonEmpty([rollup.species, speciesLabel(row.species, code)]), row)]),
      "PERMITS 2022 RES": resident,
      "PERMITS 2022 NR": nonresident,
      "PERMITS 2022 TOTAL": total,
    });
  }

  out.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return out;
}

function buildPointRows(rows, rollupMap) {
  const grouped = new Map();
  for (const row of rows) {
    if (!isPointRow(row)) continue;
    const code = clean(row.hunt_code).toUpperCase();
    const points = parseMaybeNumber(row.points);
    if (!code || points === "") continue;
    const key = `${code}__${points}`;
    if (!grouped.has(key)) {
      grouped.set(key, []);
    }
    grouped.get(key).push(row);
  }

  const out = [];
  for (const [key, group] of grouped.entries()) {
    const [code, pointsText] = key.split("__");
    const rollup = rollupMap.get(code) || {};
    const first = group[0] || {};
    const huntName = firstNonEmpty([rollup.huntName, cleanHuntName(first.hunt_name, first), rollup.huntType]);
    const species = firstNonEmpty([rollup.species, speciesLabel(first.species, code)]);
    const weapon = firstNonEmpty([rollup.weapon, cleanWeapon(firstNonEmpty([first.weapon, first.hunt_name, rollup.huntType]))]);
    const sex = firstNonEmpty([rollup.sex, first.sex_type, deriveSexFromName(huntName, species, first)]);
    const huntType = normalizeHuntType(firstNonEmpty([rollup.huntType, first.hunt_type]), first);
    const drawPool = normalizeDrawPool(firstNonEmpty(group.map((row) => row.draw_pool)), rollup);
    const drawMethod = normalizeDrawMethod(firstNonEmpty([rollup.huntType, first.hunt_type, first.hunt_class, first.draw_design]), first);
    const residentPermits =
      rollup.residentTotal !== "" ? rollup.residentTotal : sumNumeric(group.filter((row) => clean(row.residency).toLowerCase() === "resident").map((row) => row.total_permits));
    const nonresidentPermits =
      rollup.nonresidentTotal !== "" ? rollup.nonresidentTotal : sumNumeric(group.filter((row) => clean(row.residency).toLowerCase() === "nonresident").map((row) => row.total_permits));
    const totalPermits =
      rollup.totalPublic !== "" ? rollup.totalPublic : Number(residentPermits || 0) + Number(nonresidentPermits || 0);
    const eligibleApplicants = sumNumeric(group.map((row) => row.eligible_applicants));
    const bonusPermits = sumNumeric(group.map((row) => row.bonus_permits));
    const regularPermits = sumNumeric(group.map((row) => row.regular_permits));
    const totalPermitCounts = sumNumeric(group.map((row) => row.total_permits));
    out.push({
      "ACTUAL DRAW YEAR": 2022,
      "HUNT CODE": code,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      "HUNT TYPE": huntType,
      POINTS: parseMaybeNumber(pointsText),
      "PERMITS 2022 RES": residentPermits,
      "PERMITS 2022 NR": nonresidentPermits,
      "PERMITS 2022 TOTAL": totalPermits,
      "ELIGIBLE APPLICANTS": eligibleApplicants,
      "BONUS PERMITS": bonusPermits,
      "REGULAR PERMITS": regularPermits,
      "TOTAL PERMITS": totalPermitCounts,
      "DRAW POOL": drawPool,
      "DRAW METHOD": drawMethod,
      "SOURCE FILE": firstNonEmpty(group.map((row) => row.source_file)),
      "SOURCE PAGE": firstNonEmpty(group.map((row) => row.pdf_page || row.official_page)),
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
  sheet.getRange(`A1:S1`).format = {
    fill: "#254A3F",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    horizontalAlignment: "center",
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:S${rowCount}`).format = { fill: "#F7FBF9", font: { color: "#20332D" }, wrapText: true };
  }
  sheet.getRange(`A2:A${rowCount}`).format = { numberFormat: "0", horizontalAlignment: "center" };
  sheet.getRange(`B2:B${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`G2:G${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`H2:H${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`I2:O${rowCount}`).format = { horizontalAlignment: "center" };
  sheet.getRange(`P2:S${rowCount}`).format = { horizontalAlignment: "left" };
  sheet.getRange("A:A").format.columnWidthPx = 88;
  sheet.getRange("B:B").format.columnWidthPx = 100;
  sheet.getRange("C:C").format.columnWidthPx = 120;
  sheet.getRange("D:D").format.columnWidthPx = 300;
  sheet.getRange("E:E").format.columnWidthPx = 120;
  sheet.getRange("F:F").format.columnWidthPx = 100;
  sheet.getRange("G:G").format.columnWidthPx = 135;
  sheet.getRange("H:H").format.columnWidthPx = 110;
  sheet.getRange("I:I").format.columnWidthPx = 90;
  sheet.getRange("J:J").format.columnWidthPx = 90;
  sheet.getRange("K:K").format.columnWidthPx = 90;
  sheet.getRange("L:L").format.columnWidthPx = 110;
  sheet.getRange("M:M").format.columnWidthPx = 90;
  sheet.getRange("N:N").format.columnWidthPx = 90;
  sheet.getRange("O:O").format.columnWidthPx = 90;
  sheet.getRange("P:P").format.columnWidthPx = 130;
  sheet.getRange("Q:Q").format.columnWidthPx = 110;
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

const rollupRows = readCsv(await fs.readFile(RAW_HUNT_CODE_ROLLUP, "utf8"));
const pointRows = readCsv(await fs.readFile(RAW_POINT_ROWS, "utf8"));
const rollupMap = buildRollupMap(rollupRows);
const summaryRows = buildSummaryRows(rollupRows, rollupMap);
const longRows = buildPointRows(pointRows, rollupMap);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("2022 Summary");
const longSheet = workbook.worksheets.add("2022 Long");

const summaryColumns = [
  "ACTUAL DRAW YEAR",
  "HUNT CODE",
  "SPECIES",
  "HUNT NAME",
  "WEAPON",
  "SEX",
  "PERMITS 2022 RES",
  "PERMITS 2022 NR",
  "PERMITS 2022 TOTAL",
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
  "PERMITS 2022 RES",
  "PERMITS 2022 NR",
  "PERMITS 2022 TOTAL",
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
stylePointSheet(longSheet, longValues.length);

const previewSummary = await workbook.render({
  sheetName: "2022 Summary",
  range: "A1:I18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(PREVIEW_DIR, "2022_summary_preview.png"),
  Buffer.from(await previewSummary.arrayBuffer()),
);

const previewLong = await workbook.render({
  sheetName: "2022 Long",
  range: "A1:S18",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  path.join(PREVIEW_DIR, "2022_long_preview.png"),
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
