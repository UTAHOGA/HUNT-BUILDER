import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const REPO_ROOT = process.cwd();
const OUTPUT_DIR = path.join(REPO_ROOT, "outputs");
const PREVIEW_DIR = path.join(OUTPUT_DIR, "2024_standardized_long_preview");
const OUTPUT_XLSX = path.join(OUTPUT_DIR, "2024 standardized long.xlsx");
const OUTPUT_REPORT = path.join(OUTPUT_DIR, "2024_standardized_long_report.json");
const YEAR = 2024;

const FILE_RECORDS = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "draw_results_2024_for_2025_candidate_promotion_file_records.csv",
);
const HUNT_CODE_ROLLUP = path.join(
  REPO_ROOT,
  "data_truth",
  "draw_results_truth",
  "normalized",
  "draw_results_2024_for_2025_candidate_promotion_hunt_code_rollup.csv",
);

const POINT_ROW_TYPES = new Set(["point_level_draw_result", "point_row", "point_level", "point"]);
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
const TRAILING_DESCRIPTOR_RE =
  /\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$/i;
const LEADING_JUNK_REPLACEMENTS = [
  /^premium[-\s]*limited[-\s]*entry[\s-]*/i,
  /^premium[-\s]*le[\s-]*/i,
  /^limited[-\s]*entry[\s-]*/i,
  /^cwmu[\s-]*/i,
  /^youth[\s-]*/i,
  /^general[-\s]*season[\s-]*/i,
  /^draw[-\s]*only[\s-]*/i,
  /^management[\s-]*/i,
  /^archery[\s-]*/i,
  /^muzzleloader[\s-]*/i,
  /^rifle[\s-]*/i,
  /^shotgun[\s-]*/i,
  /^any[-\s]*legal[-\s]*weapon[\s-]*/i,
  /^any[-\s]*weapon[\s-]*/i,
  /^multi[-\s]*season[\s-]*/i,
  /^ham+s+\s*/i,
  /^(?:bison|black bear|cougar|deer|desert bighorn sheep|elk|moose|mountain goat|pronghorn|rocky mountain sheep|turkey)(?:\s*\([^)]*\))?[\s-]*/i,
  /^(?:bull|buck|cow|doe|ram|ewe|bearded|antlerless|hunters choice|either sex)[\s-]*/i,
];

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
  const text = normalize(
    firstNonEmpty([
      value,
      row.hunt_type,
      row.huntType,
      row.hunt_class,
      row.huntClass,
      row.draw_design,
      row.drawDesign,
    ]),
  );
  if (!text) return "";
  const context = normalize([text, row.hunt_name, row.huntName, row.hunt_class, row.huntClass].map(clean).join(" "));
  if (/sportsman/i.test(context)) return "Sportsman";
  if (/statewide/i.test(text) && /sportsman/i.test(context)) return "Sportsman";
  return text;
}

function normalizeDrawMethod(huntType, row = {}) {
  const text = normalizeHuntType(
    firstNonEmpty([
      huntType,
      row.hunt_type,
      row.huntType,
      row.hunt_class,
      row.huntClass,
      row.draw_design,
      row.drawDesign,
    ]),
    row,
  );
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

  const context = normalize(
    [row.hunt_type, row.huntType, row.hunt_class, row.huntClass, row.draw_design, row.drawDesign, row.season]
      .map(clean)
      .join(" "),
  );

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

    for (const pattern of LEADING_JUNK_REPLACEMENTS) {
      const next = text.replace(pattern, "");
      if (next !== text) {
        text = next.trim();
        changed = true;
      }
    }

    const segments = text
      .split(/\s+-\s*|\s*-\s+/)
      .map((segment) => segment.trim())
      .filter(Boolean);

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

    const leadingHyphenNext = text.replace(/^[\s-]+/, "");
    if (leadingHyphenNext !== text) {
      text = leadingHyphenNext.trim();
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
    .replace(/^[-â€“â€”:\s]+/, "")
    .replace(/[-â€“â€”:\s]+$/, "")
    .replace(/\bHAM+S+\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function buildRollupMap(rows) {
  const map = new Map();
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;

    const huntName = cleanHuntName(firstNonEmpty([row.hunt_name, row.raw_hunt_name]), row);
    const species = speciesLabel(row.species, code);
    const huntType = normalizeHuntType(row.hunt_type, row);
    const weapon = cleanWeapon(firstNonEmpty([row.weapon, huntName, huntType]));
    const sex = firstNonEmpty([clean(row.sex_type || row.sex), deriveSexFromName(huntName, species, row)]);
    const residentTotal = numericOrBlank(row.resident_total_permits_sum);
    const nonresidentTotal = numericOrBlank(row.nonresident_total_permits_sum);
    const totalPublic = numericOrBlank(row.total_public_permits_sum);
    map.set(code, {
      code,
      boundaryId: numericOrBlank(row.boundary_id),
      huntName,
      species,
      sex,
      huntType,
      weapon,
      huntClass: clean(row.hunt_class),
      season: clean(row.season),
      residentTotal,
      nonresidentTotal,
      totalPublic,
    });
  }
  return map;
}

function buildPointMetaMap(rows) {
  const map = new Map();
  for (const row of rows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    const existing = map.get(code) || {};
    map.set(code, {
      drawPool: firstNonEmpty([existing.drawPool, row.draw_pool]),
      drawMethod: firstNonEmpty([existing.drawMethod, row.draw_method]),
    });
  }
  return map;
}

function buildSummaryRows(rollupRows, rollupMap, pointMetaMap) {
  const out = [];
  for (const row of rollupRows) {
    const code = clean(row.hunt_code).toUpperCase();
    if (!code) continue;
    const rollup = rollupMap.get(code);
    if (!rollup) continue;

    let resident = rollup.residentTotal;
    let nonresident = rollup.nonresidentTotal;
    let total = rollup.totalPublic;

    if (total === "" && (resident !== "" || nonresident !== "")) {
      total = Number(resident || 0) + Number(nonresident || 0);
    }

    if (resident === "" && nonresident === "" && total !== "" && /sportsman/i.test(rollup.huntType)) {
      resident = total;
    }

    const meta = pointMetaMap.get(code) || {};
    const huntName = rollup.huntName;
    const species = rollup.species;
    const weapon = firstNonEmpty([rollup.weapon, cleanWeapon(firstNonEmpty([row.weapon, huntName, rollup.huntType]))]);
    const sex = firstNonEmpty([rollup.sex, deriveSexFromName(huntName, species, row)]);
    const drawPool = normalizeDrawPool(meta.drawPool, rollup);
    const drawMethod = normalizeDrawMethod(firstNonEmpty([meta.drawMethod, rollup.huntType]), rollup);

    out.push({
      "ACTUAL DRAW YEAR": YEAR,
      "HUNT CODE": code,
      "BOUNDARY ID": rollup.boundaryId,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      "DRAW POOL": drawPool,
      "DRAW METHOD": drawMethod,
      [`PERMITS ${YEAR} RES`]: resident,
      [`PERMITS ${YEAR} NR`]: nonresident,
      [`PERMITS ${YEAR} TOTAL`]: total,
    });
  }

  out.sort((left, right) => left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true }));
  return out;
}

function buildPointRows(pointRows, rollupMap) {
  const grouped = new Map();

  for (const row of pointRows) {
    if (!isPointRow(row)) continue;
    const code = clean(row.hunt_code).toUpperCase();
    const points = parseMaybeNumber(row.points);
    if (!code || points === "") continue;
    const key = `${code}__${points}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }

  const out = [];
  for (const [key, group] of grouped.entries()) {
    const [code, pointsText] = key.split("__");
    const rollup = rollupMap.get(code) || {};
    const first = group[0] || {};
    const huntName = firstNonEmpty([rollup.huntName, cleanHuntName(first.hunt_name, first), cleanHuntName(first.raw_hunt_name, first)]);
    const species = firstNonEmpty([rollup.species, speciesLabel(first.species, code)]);
    const weapon = firstNonEmpty([rollup.weapon, cleanWeapon(firstNonEmpty([first.weapon, huntName, rollup.huntType]))]);
    const sex = firstNonEmpty([rollup.sex, first.sex_type, deriveSexFromName(huntName, species, first)]);
    const huntType = normalizeHuntType(firstNonEmpty([rollup.huntType, first.hunt_type]), first);
    const drawPool = normalizeDrawPool(firstNonEmpty(group.map((entry) => entry.draw_pool)), rollup);
    const drawMethod = normalizeDrawMethod(firstNonEmpty([first.draw_method, rollup.huntType, first.hunt_type]), first);

    const residentPermits =
      rollup.residentTotal !== ""
        ? rollup.residentTotal
        : sumNumeric(
            group
              .filter((entry) => clean(entry.residency).toLowerCase() === "resident")
              .map((entry) => entry.total_permits),
          );
    const nonresidentPermits =
      rollup.nonresidentTotal !== ""
        ? rollup.nonresidentTotal
        : sumNumeric(
            group
              .filter((entry) => clean(entry.residency).toLowerCase() === "nonresident")
              .map((entry) => entry.total_permits),
          );
    const totalPermits =
      rollup.totalPublic !== ""
        ? rollup.totalPublic
        : Number(residentPermits || 0) + Number(nonresidentPermits || 0);

    out.push({
      "ACTUAL DRAW YEAR": YEAR,
      "HUNT CODE": code,
      SPECIES: species,
      "HUNT NAME": huntName,
      WEAPON: weapon,
      SEX: sex,
      "HUNT TYPE": huntType,
      POINTS: parseMaybeNumber(pointsText),
      [`PERMITS ${YEAR} RES`]: residentPermits,
      [`PERMITS ${YEAR} NR`]: nonresidentPermits,
      [`PERMITS ${YEAR} TOTAL`]: totalPermits,
      "ELIGIBLE APPLICANTS": numericOrBlank(sumNumeric(group.map((entry) => entry.eligible_applicants))),
      "BONUS PERMITS": numericOrBlank(sumNumeric(group.map((entry) => entry.bonus_permits))),
      "REGULAR PERMITS": numericOrBlank(sumNumeric(group.map((entry) => entry.regular_permits))),
      "TOTAL PERMITS": numericOrBlank(sumNumeric(group.map((entry) => entry.total_permits))),
      "DRAW POOL": drawPool,
      "DRAW METHOD": drawMethod,
      "SOURCE FILE": firstNonEmpty(group.map((entry) => entry.source_file || entry.draw_source_file)),
      "SOURCE PAGE": numericOrBlank(firstNonEmpty(group.map((entry) => entry.pdf_page || entry.official_page))),
    });
  }

  out.sort((left, right) => {
    const codeCmp = left["HUNT CODE"].localeCompare(right["HUNT CODE"], undefined, { numeric: true });
    if (codeCmp !== 0) return codeCmp;
    return Number(right.POINTS || -1) - Number(left.POINTS || -1);
  });

  return out;
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
  sheet.getRange("I:I").format.columnWidthPx = 120;
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
  sheet.getRange("G:G").format.columnWidthPx = 135;
  sheet.getRange("H:H").format.columnWidthPx = 80;
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

const rollupRows = readCsv(await fs.readFile(HUNT_CODE_ROLLUP, "utf8"));
const pointRows = readCsv(await fs.readFile(FILE_RECORDS, "utf8"));
const rollupMap = buildRollupMap(rollupRows);
const pointMetaMap = buildPointMetaMap(pointRows);
const summaryRows = buildSummaryRows(rollupRows, rollupMap, pointMetaMap);
const longRows = buildPointRows(pointRows, rollupMap);

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("2024 Summary");
const longSheet = workbook.worksheets.add("2024 Long");

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
  `PERMITS ${YEAR} RES`,
  `PERMITS ${YEAR} NR`,
  `PERMITS ${YEAR} TOTAL`,
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
  `PERMITS ${YEAR} RES`,
  `PERMITS ${YEAR} NR`,
  `PERMITS ${YEAR} TOTAL`,
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

await savePreview(workbook, "2024 Summary", "A1:L18", path.join(PREVIEW_DIR, "2024_summary_preview.png"));
await savePreview(workbook, "2024 Long", "A1:S18", path.join(PREVIEW_DIR, "2024_long_preview.png"));
await exportWorkbook(workbook, OUTPUT_XLSX);

const transformedSummary = summaryRows.filter((row) => row["HUNT NAME"] !== cleanHuntName(row["HUNT NAME"]));
const transformedLong = longRows.filter((row) => row["HUNT NAME"] !== cleanHuntName(row["HUNT NAME"]));

const report = {
  status: "PASS",
  generated_at_utc: new Date().toISOString(),
  source_rollup: path.relative(REPO_ROOT, HUNT_CODE_ROLLUP).replaceAll("\\", "/"),
  source_point_rows: path.relative(REPO_ROOT, FILE_RECORDS).replaceAll("\\", "/"),
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
