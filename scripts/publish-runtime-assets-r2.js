#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const cp = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const AUDIT_PATH = path.join(ROOT, 'processed_data', 'audits', 'large_file_classification_audit.csv');
const MANIFEST_PUBLIC_PATH = path.join(ROOT, 'public', 'data', 'runtime-manifest.json');
const MANIFEST_DATA_PATH = path.join(ROOT, 'data', 'runtime-manifest.json');
const LARGE_FILE_THRESHOLD_BYTES = 5 * 1024 * 1024;
const GIT_LFS_POINTER_PREFIX = 'version https://git-lfs.github.com/spec/v1';

const args = process.argv.slice(2);
const shouldUpload = args.includes('--upload');
const strict = args.includes('--strict');
const dryRun = args.includes('--dry-run') || !shouldUpload;
const verbose = args.includes('--verbose');

const R2_PUBLIC_BASE = String(process.env.UOGA_R2_PUBLIC_BASE || process.env.CLOUDFLARE_OBJECT_BASE || process.env.CLOUDFLARE_BASE || 'https://json.uoga.workers.dev').trim().replace(/\/+$/, '');
const R2_ENDPOINT = String(process.env.UOGA_R2_S3_ENDPOINT || '').trim();
const R2_BUCKET = String(process.env.UOGA_R2_BUCKET || '').trim();
const R2_PREFIX = String(process.env.UOGA_R2_PREFIX || '').trim().replace(/^\/+|\/+$/g, '');
const AWS_PROFILE = String(process.env.UOGA_AWS_PROFILE || process.env.AWS_PROFILE || '').trim();

const FRONTEND_REFERENCE_FILES = [
  'index.html',
  'research.html',
  'verify.html',
  'hard-copy.html',
  'app.js',
  'config.js',
  'data.js',
  'hunt-research.js',
  'assets/js/research-outlook-dashboard.js',
];

const CATALOG = [
  {
    key: 'builder_display_boundary_index_2026_json',
    relPath: 'processed_data/display-boundary-index-2026.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Builder/map boundary manifest JSON.',
  },
  {
    key: 'builder_composite_boundaries_2026_geojson',
    relPath: 'processed_data/statewide_composite_boundaries_2026.geojson',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Primary composite boundaries runtime source for Builder.',
  },
  {
    key: 'builder_composite_hunt_unit_mapping_2026_geojson',
    relPath: 'processed_data/composite_hunt_unit_mapping_2026.geojson',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Direct unit boundary fallback map used by Builder.',
  },
  {
    key: 'builder_composite_boundaries_2026_final_locked_geojson',
    relPath: 'processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_ON_PROMOTION',
    public_use: false,
    served_live: false,
    notes: 'Canonical locked reference; publish only when intentionally pinned.',
  },
  {
    key: 'builder_hunt_master_foundation_json',
    relPath: 'data/hunt-master-canonical-2026-foundation.json',
    source_type: 'data',
    classification: 'REPO_SMALL',
    update_mode: 'AUTO_PUBLIC_REPO',
    public_use: true,
    served_live: true,
    notes: 'Builder first-load canonical hunt master; rebuilt from DATABASE.csv.',
  },
  {
    key: 'builder_hunt_master_source_of_truth_json',
    relPath: 'data/hunt-master-canonical-2026-source-of-truth.json',
    source_type: 'data',
    classification: 'REPO_SMALL',
    update_mode: 'AUTO_PUBLIC_REPO',
    public_use: true,
    served_live: true,
    notes: 'Builder fallback hunt master; kept aligned with first-load master.',
  },
  {
    key: 'processed_hunt_master_source_of_truth_json',
    relPath: 'processed_data/hunt-master-canonical-2026-source-of-truth.json',
    source_type: 'processed_data',
    classification: 'REPO_SMALL',
    update_mode: 'AUTO_PUBLIC_REPO',
    public_use: true,
    served_live: true,
    notes: 'Processed mirror of current hunt master for public/reference consumers.',
  },
  {
    key: 'processed_hunt_master_source_of_truth_csv',
    relPath: 'processed_data/hunt-master-canonical-2026-source-of-truth.csv',
    source_type: 'processed_data',
    classification: 'REPO_SMALL',
    update_mode: 'AUTO_PUBLIC_REPO',
    public_use: true,
    served_live: true,
    notes: 'Processed CSV mirror of current hunt master for public/reference consumers.',
  },
  {
    key: 'research_hunt_research_2026_json',
    relPath: 'processed_data/hunt_research_2026.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Research summary contract feed.',
  },
  {
    key: 'research_hunt_research_2026_summary_json',
    relPath: 'processed_data/hunt_research_2026_summary.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Compact Research summary contract feed.',
  },
  {
    key: 'research_hunt_research_2026_ladder_json',
    relPath: 'processed_data/hunt_research_2026_ladder.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Full Research ladder JSON contract.',
  },
  {
    key: 'research_hunt_research_2026_ladder_preference_json',
    relPath: 'processed_data/hunt_research_2026_ladder_preference.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Preference-point Research ladder JSON contract.',
  },
  {
    key: 'research_hunt_research_2026_ladder_bonus_max_random_json',
    relPath: 'processed_data/hunt_research_2026_ladder_bonus_max_random.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Bonus/max-random Research ladder JSON contract.',
  },
  {
    key: 'research_hunt_research_2026_split_index_json',
    relPath: 'processed_data/hunt_research_2026_split/hunt_research_2026.index.json',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Split Research index aligned to DATABASE.csv for legacy/detail consumers.',
  },
  {
    key: 'research_draw_reality_engine_csv',
    relPath: 'processed_data/draw_reality_engine.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Observed draw runtime engine feed.',
  },
  {
    key: 'research_draw_reality_engine_v2_csv',
    relPath: 'processed_data/draw_reality_engine_v2.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Observed draw engine fallback feed.',
  },
  {
    key: 'research_draw_reality_engine_predictive_v2_csv',
    relPath: 'processed_data/draw_reality_engine_predictive_v2.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Predictive mode feed; published to R2 for browser/runtime compatibility.',
  },
  {
    key: 'research_point_ladder_view_csv',
    relPath: 'processed_data/point_ladder_view.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Research ladder runtime feed.',
  },
  {
    key: 'research_hunt_master_enriched_csv',
    relPath: 'processed_data/hunt_master_enriched.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Research enriched hunt reference runtime feed.',
  },
  {
    key: 'research_hunt_unit_reference_linked_csv',
    relPath: 'processed_data/hunt_unit_reference_linked.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Research unit reference runtime feed.',
  },
  {
    key: 'verify_outfitters_public_contract_json',
    relPath: 'processed_data/public_contracts/outfitters-public.json',
    source_type: 'processed_data/public_contracts',
    classification: 'REPO_SMALL',
    update_mode: 'AUTO_PUBLIC_REPO',
    public_use: true,
    served_live: true,
    notes: 'Verify directory contract feed (small).',
  },
  {
    key: 'public_contract_hunt_odds_history_json',
    relPath: 'processed_data/public_contracts/hunt_odds_history.json',
    source_type: 'processed_data/public_contracts',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: false,
    notes: 'Large public contract artifact; not direct page dependency today.',
  },
  {
    key: 'runtime_ml_draw_predictions_v1_csv',
    relPath: 'processed_data/ml_draw_predictions_v1.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Large ML model output; public/download runtime artifact served from R2.',
  },
  {
    key: 'runtime_draw_reality_view_csv',
    relPath: 'processed_data/draw_reality_view.csv',
    source_type: 'processed_data',
    classification: 'R2_PUBLIC',
    update_mode: 'AUTO_PUBLIC_R2',
    public_use: true,
    served_live: true,
    notes: 'Display-only draw reality view; public/download artifact served from R2.',
  },
  {
    key: 'runtime_hunt_master_enriched_2026_draw_subset_csv',
    relPath: 'processed_data/hunt_master_enriched_2026_draw_subset.csv',
    source_type: 'processed_data',
    classification: 'REVIEW_REQUIRED',
    update_mode: 'MANUAL_REVIEW_REQUIRED',
    public_use: false,
    served_live: false,
    notes: 'Missing in repo; requires lineage review before use.',
  },
  {
    key: 'truth_draw_results_long_csv',
    relPath: 'data_truth/draw_results_truth/normalized/draw_results_long.csv',
    source_type: 'data_truth',
    classification: 'LFS_REFERENCE_ONLY',
    update_mode: 'AUTO_ON_PROMOTION',
    public_use: false,
    served_live: false,
    notes: 'Truth-source long-form draw rows; not a direct browser runtime feed.',
  },
  {
    key: 'internal_hunt_truth_sqlite',
    relPath: 'processed_data/hunt_truth_from_json.sqlite',
    source_type: 'processed_data',
    classification: 'INTERNAL_ONLY',
    update_mode: 'INTERNAL_ONLY',
    public_use: false,
    served_live: false,
    notes: 'Internal SQLite build/reference artifact.',
  },
  {
    key: 'internal_draw_system_coverage_report_csv',
    relPath: 'processed_data/draw_system_coverage_report.csv',
    source_type: 'processed_data',
    classification: 'INTERNAL_ONLY',
    update_mode: 'INTERNAL_ONLY',
    public_use: false,
    served_live: false,
    notes: 'Internal QA/audit report artifact.',
  },
  {
    key: 'reference_draw_reality_engine_backup_before_2024_import_csv',
    relPath: 'processed_data/draw_reality_engine_backup_before_2024_import.csv',
    source_type: 'processed_data',
    classification: 'LFS_REFERENCE_ONLY',
    update_mode: 'AUTO_ON_PROMOTION',
    public_use: false,
    served_live: false,
    notes: 'Historical backup/reference dataset.',
  },
  {
    key: 'internal_backups_point_ladder_view_glob',
    relPath: 'processed_data/backups/**/point_ladder_view.csv',
    source_type: 'processed_data/backups',
    classification: 'INTERNAL_ONLY',
    update_mode: 'INTERNAL_ONLY',
    public_use: false,
    served_live: false,
    notes: 'Backup copies only; never publish directly.',
  },
];

function readFileSafe(relPath) {
  const fullPath = path.join(ROOT, relPath);
  if (!fs.existsSync(fullPath)) return '';
  return fs.readFileSync(fullPath, 'utf8');
}

const FRONTEND_CONTENT = FRONTEND_REFERENCE_FILES
  .map((relPath) => ({ relPath, content: readFileSafe(relPath) }))
  .filter((row) => row.content);

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function csvEscape(value) {
  const text = value == null ? '' : String(value);
  if (!/[",\n]/.test(text)) return text;
  return `"${text.replace(/"/g, '""')}"`;
}

function writeCsv(filePath, rows, headers) {
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((header) => csvEscape(row[header])).join(','));
  }
  ensureDir(filePath);
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`, 'utf8');
}

function toPosix(relPath) {
  return String(relPath || '').replace(/\\/g, '/');
}

function fileSize(relPath) {
  const fullPath = path.join(ROOT, relPath);
  if (!fs.existsSync(fullPath)) return 0;
  return fs.statSync(fullPath).size;
}

function isGitLfsPointer(relPath) {
  const fullPath = path.join(ROOT, relPath);
  if (!fs.existsSync(fullPath)) return false;
  const fd = fs.openSync(fullPath, 'r');
  try {
    const buffer = Buffer.alloc(120);
    const bytesRead = fs.readSync(fd, buffer, 0, buffer.length, 0);
    const head = buffer.slice(0, bytesRead).toString('utf8');
    return head.startsWith(GIT_LFS_POINTER_PREFIX);
  } finally {
    fs.closeSync(fd);
  }
}

function gitStorageMode(relPath, isPointer) {
  const pathForGit = toPosix(relPath);
  try {
    const output = cp.execSync(`git check-attr filter -- "${pathForGit}"`, {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
    });
    const trimmed = String(output || '').trim();
    if (/:\s*filter:\s*lfs$/i.test(trimmed)) {
      return isPointer ? 'GIT_LFS_POINTER' : 'GIT_LFS_OBJECT';
    }
  } catch {
    // fall through to blob.
  }
  return isPointer ? 'GIT_LFS_POINTER' : 'GIT_BLOB';
}

function detectFrontendUsage(relPath) {
  const posixPath = toPosix(relPath);
  const filename = path.basename(posixPath);
  return FRONTEND_CONTENT.some(({ content }) => content.includes(posixPath) || content.includes(filename));
}

function toRecommendedTarget(classification) {
  switch (classification) {
    case 'REPO_SMALL':
      return 'GITHUB_REPO';
    case 'LFS_REFERENCE_ONLY':
      return 'GIT_LFS_REFERENCE';
    case 'R2_PUBLIC':
      return 'CLOUDFLARE_R2_PUBLIC';
    case 'INTERNAL_ONLY':
      return 'LOCAL_INTERNAL_ONLY';
    default:
      return 'REVIEW_REQUIRED';
  }
}

function canonicalUrlFor(entry) {
  if (!entry.public_use) return '';
  if (entry.classification === 'REPO_SMALL') return `/${toPosix(entry.relPath)}`;
  if (entry.classification === 'R2_PUBLIC') return `${R2_PUBLIC_BASE}/${toPosix(entry.relPath)}`;
  return '';
}

function buildRuntimeManifest(assets) {
  return {
    generated_at: new Date().toISOString(),
    generated_by: 'scripts/publish-runtime-assets-r2.js',
    architecture: {
      github: 'code + small manifests/config',
      vercel: 'frontend app host',
      r2: 'large public/runtime assets',
    },
    public_base: R2_PUBLIC_BASE,
    assets,
  };
}

function classifyCatalogRows() {
  const rows = [];
  const manifestAssets = [];
  const classificationCounts = {
    REPO_SMALL: 0,
    LFS_REFERENCE_ONLY: 0,
    R2_PUBLIC: 0,
    INTERNAL_ONLY: 0,
    REVIEW_REQUIRED: 0,
  };

  for (const entry of CATALOG) {
    const isGlob = entry.relPath.includes('*');
    if (isGlob) {
      rows.push({
        path: toPosix(entry.relPath),
        size_bytes: '',
        current_storage_mode: 'GLOB_PATTERN',
        classification: entry.classification,
        served_live: entry.served_live ? 'yes' : 'no',
        used_by_frontend: entry.public_use ? 'yes' : 'no',
        recommended_target: toRecommendedTarget(entry.classification),
        notes: entry.notes,
      });
      classificationCounts[entry.classification] = (classificationCounts[entry.classification] || 0) + 1;
      continue;
    }

    const fullPath = path.join(ROOT, entry.relPath);
    const exists = fs.existsSync(fullPath);
    const size = exists ? fileSize(entry.relPath) : 0;
    const lfsPointer = exists ? isGitLfsPointer(entry.relPath) : false;
    const storageMode = exists ? gitStorageMode(entry.relPath, lfsPointer) : 'MISSING';
    const usedByFrontend = detectFrontendUsage(entry.relPath);
    const canonicalUrl = canonicalUrlFor(entry);
    const notes = [];
    if (!exists) notes.push('missing_file');
    if (lfsPointer) notes.push('git_lfs_pointer_payload_detected');
    if (size > LARGE_FILE_THRESHOLD_BYTES) notes.push(`large_file>${LARGE_FILE_THRESHOLD_BYTES}`);
    if (entry.classification === 'R2_PUBLIC' && !entry.public_use) notes.push('not_public_even_though_r2_classification');
    if (entry.update_mode === 'MANUAL_REVIEW_REQUIRED') notes.push('manual_review_required');
    if (entry.classification === 'REVIEW_REQUIRED') notes.push('review_required');
    if (entry.relPath.includes('backups/')) notes.push('backup_archive_path');

    rows.push({
      path: toPosix(entry.relPath),
      size_bytes: exists ? size : '',
      current_storage_mode: storageMode,
      classification: entry.classification,
      served_live: entry.served_live ? 'yes' : 'no',
      used_by_frontend: usedByFrontend ? 'yes' : 'no',
      recommended_target: toRecommendedTarget(entry.classification),
      notes: [entry.notes, ...notes].filter(Boolean).join('; '),
    });

    classificationCounts[entry.classification] = (classificationCounts[entry.classification] || 0) + 1;

    manifestAssets.push({
      key: entry.key,
      source_type: entry.source_type,
      path: toPosix(entry.relPath),
      canonical_url: canonicalUrl || null,
      generated_at: new Date().toISOString(),
      size_bytes: exists ? size : null,
      update_mode: entry.update_mode,
      classification: entry.classification,
      current_storage_mode: storageMode,
      public_use: Boolean(entry.public_use),
      used_by_frontend: Boolean(usedByFrontend),
      served_live: Boolean(entry.served_live),
      notes: [entry.notes, ...notes].filter(Boolean).join('; '),
    });
  }

  return { rows, manifestAssets, classificationCounts };
}

function parseGitattributesNotes() {
  const attrsPath = path.join(ROOT, '.gitattributes');
  if (!fs.existsSync(attrsPath)) return [];
  const content = fs.readFileSync(attrsPath, 'utf8');
  const issues = [];
  if (content.includes('Git[[:space:]]LFS/*.exe')) {
    issues.push('suspicious_pattern:Git[[:space:]]LFS/*.exe');
  }
  return issues;
}

function runAwsUpload(localPath, objectKey) {
  const args = ['s3', 'cp', localPath, `s3://${R2_BUCKET}/${objectKey}`, '--endpoint-url', R2_ENDPOINT];
  if (AWS_PROFILE) {
    args.push('--profile', AWS_PROFILE);
  }
  if (verbose || dryRun) {
    console.log(`[upload] aws ${args.join(' ')}`);
  }
  if (dryRun) return;
  cp.execFileSync('aws', args, {
    cwd: ROOT,
    stdio: 'inherit',
  });
}

function uploadR2Assets(manifestAssets) {
  if (dryRun) {
    console.log('[upload] Dry run mode enabled; no R2 uploads executed.');
    return;
  }
  if (!R2_ENDPOINT || !R2_BUCKET) {
    throw new Error('R2 upload requested but UOGA_R2_S3_ENDPOINT or UOGA_R2_BUCKET is missing.');
  }
  const toUpload = manifestAssets.filter((asset) => asset.classification === 'R2_PUBLIC' && asset.public_use && asset.path && fs.existsSync(path.join(ROOT, asset.path)));
  for (const asset of toUpload) {
    const objectKey = R2_PREFIX ? `${R2_PREFIX}/${asset.path}` : asset.path;
    runAwsUpload(path.join(ROOT, asset.path), objectKey);
  }
}

function writeManifestFiles(manifest) {
  ensureDir(MANIFEST_PUBLIC_PATH);
  ensureDir(MANIFEST_DATA_PATH);
  const payload = JSON.stringify(manifest, null, 2);
  fs.writeFileSync(MANIFEST_PUBLIC_PATH, `${payload}\n`, 'utf8');
  fs.writeFileSync(MANIFEST_DATA_PATH, `${payload}\n`, 'utf8');
}

function main() {
  const { rows, manifestAssets, classificationCounts } = classifyCatalogRows();
  const gitattributesIssues = parseGitattributesNotes();

  writeCsv(AUDIT_PATH, rows, [
    'path',
    'size_bytes',
    'current_storage_mode',
    'classification',
    'served_live',
    'used_by_frontend',
    'recommended_target',
    'notes',
  ]);

  const manifest = buildRuntimeManifest(manifestAssets);
  writeManifestFiles(manifest);

  uploadR2Assets(manifestAssets);

  console.log(`Wrote audit: ${path.relative(ROOT, AUDIT_PATH).replace(/\\/g, '/')}`);
  console.log(`Wrote manifest: ${path.relative(ROOT, MANIFEST_PUBLIC_PATH).replace(/\\/g, '/')}`);
  console.log(`Wrote mirror: ${path.relative(ROOT, MANIFEST_DATA_PATH).replace(/\\/g, '/')}`);
  console.log(`Classification counts: ${JSON.stringify(classificationCounts)}`);
  if (gitattributesIssues.length) {
    console.log(`.gitattributes issues: ${gitattributesIssues.join(', ')}`);
    if (strict) {
      process.exitCode = 2;
    }
  }
}

main();
