const fs = require("fs");
const XLSX = require("xlsx");

function parseLine(line) {
  const vals = [];
  let cur = "";
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    const next = line[i + 1];
    if (q) {
      if (ch === '"' && next === '"') { cur += '"'; i += 1; }
      else if (ch === '"') q = false;
      else cur += ch;
    } else {
      if (ch === '"') q = true;
      else if (ch === ",") { vals.push(cur); cur = ""; }
      else cur += ch;
    }
  }
  vals.push(cur);
  return vals;
}

function parseCsv(path) {
  const text = fs.readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r/g, "");
  const lines = text.split("\n");
  if (!lines.length) return [];
  const header = parseLine(lines[0]);
  const out = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    const vals = parseLine(line);
    const row = Object.fromEntries(header.map((h, idx) => [h, vals[idx] ?? ""]));
    out.push(row);
  }
  return out;
}

const audit = parseCsv("audits/2025_canonical_finalization/2025_27_conservation_permits_xlsx_hunt_code_join_audit.csv");
const wb = XLSX.readFile("processed_data/hard_data_exports/hunt_tables/2026/CLEAN_XLXS_STAGED/2025-27 Conservation Permits.xlsx");
const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header:1, defval: "" });
const headers = rows[0];
const noIdx = headers.indexOf("No.");
const codeIdx = headers.indexOf("HUNT CODE");
const staged = new Map();
for (let i = 1; i < rows.length; i++) {
  const no = String(rows[i][noIdx] || "").trim();
  const code = String(rows[i][codeIdx] || "").trim();
  if (no) staged.set(no, code);
}

const mismatches = [];
for (const r of audit) {
  const selected = String(r.selected_hunt_code || "").trim();
  if (!selected) continue;
  const no = String(r.source_no || "").trim();
  if (!no) continue;
  const sCode = staged.get(no);
  if (!sCode) continue;
  if (sCode !== selected) mismatches.push([no, sCode, selected, r.join_type, r.match_confidence]);
}

console.log('mismatch_count', mismatches.length);
for (const m of mismatches.slice(0, 10)) {
  console.log(m.join("\t"));
}
