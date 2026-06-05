const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const SPLIT_DIR = path.join(ROOT, 'processed_data', 'hunt_research_2026_split');
const INDEX_PATH = path.join(SPLIT_DIR, 'hunt_research_2026.index.json');
const DETAILS_DIR = path.join(SPLIT_DIR, 'hunts');
const OUT_PATH = path.join(SPLIT_DIR, 'hunt_research_2026.details.json');
const REPORT_PATH = path.join(ROOT, 'audits', 'hunt_research_engine', 'minimal_runtime_bundle_report.json');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function stableNow() {
  return new Date().toISOString();
}

function main() {
  if (!fs.existsSync(INDEX_PATH)) {
    throw new Error(`Missing split index: ${INDEX_PATH}`);
  }
  if (!fs.existsSync(DETAILS_DIR)) {
    throw new Error(`Missing split details directory: ${DETAILS_DIR}`);
  }

  const indexRows = readJson(INDEX_PATH);
  if (!Array.isArray(indexRows)) {
    throw new Error('Split index must be a JSON array.');
  }

  const detailsByHuntCode = {};
  const missing = [];
  const duplicated = [];
  const seen = new Set();

  for (const row of indexRows) {
    const huntCode = String(row && row.hunt_code || '').trim().toUpperCase();
    const detailPath = String(row && row.detail_path || '').trim();
    if (!huntCode || !detailPath) {
      missing.push({ hunt_code: huntCode, detail_path: detailPath, reason: 'missing_index_key_or_detail_path' });
      continue;
    }
    if (seen.has(huntCode)) {
      duplicated.push(huntCode);
      continue;
    }
    seen.add(huntCode);

    const detailFile = path.join(SPLIT_DIR, detailPath.replace(/[\\/]+/g, path.sep));
    if (!fs.existsSync(detailFile)) {
      missing.push({ hunt_code: huntCode, detail_path: detailPath, reason: 'missing_detail_file' });
      continue;
    }

    const detail = readJson(detailFile);
    detailsByHuntCode[huntCode] = detail;
  }

  const bundle = {
    generated_at: stableNow(),
    source_index: 'processed_data/hunt_research_2026_split/hunt_research_2026.index.json',
    detail_dir: 'processed_data/hunt_research_2026_split/hunts',
    indexed_hunt_count: indexRows.length,
    bundled_hunt_count: Object.keys(detailsByHuntCode).length,
    details_by_hunt_code: detailsByHuntCode,
  };

  fs.writeFileSync(OUT_PATH, `${JSON.stringify(bundle)}\n`, 'utf8');

  const report = {
    generated_at: bundle.generated_at,
    output_path: path.relative(ROOT, OUT_PATH).replace(/\\/g, '/'),
    output_size_bytes: fs.statSync(OUT_PATH).size,
    indexed_hunt_count: indexRows.length,
    bundled_hunt_count: bundle.bundled_hunt_count,
    missing_detail_count: missing.length,
    duplicate_index_hunt_code_count: duplicated.length,
    missing,
    duplicated,
  };

  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8');

  if (missing.length || duplicated.length) {
    throw new Error(`Minimal runtime bundle built with blockers: missing=${missing.length}, duplicated=${duplicated.length}`);
  }

  console.log(JSON.stringify(report, null, 2));
}

main();
