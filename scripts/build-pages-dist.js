const fs = require('fs/promises');
const path = require('path');
const fsSync = require('fs');

const repoRoot = path.resolve(__dirname, '..');
const outDir = path.join(repoRoot, 'pages-dist');
const MAX_PAGES_FILE_BYTES = Math.max(
  1,
  Number(process.env.PAGES_DIST_MAX_BYTES_MB) > 0 ? Number(process.env.PAGES_DIST_MAX_BYTES_MB) * 1024 * 1024 : 100 * 1024 * 1024,
);
const LARGE_MANIFEST_PATH = path.join(outDir, 'data', 'large-runtime-assets.json');
const RUNTIME_MANIFEST_CANDIDATES = [
  path.join(repoRoot, 'data', 'runtime-manifest.json'),
  path.join(repoRoot, 'public', 'data', 'runtime-manifest.json'),
];
const AUDIT_REPORT_PATH = path.join(repoRoot, 'audits', 'repo_hygiene', 'pages_dist_large_asset_guard_report.json');

const rootFiles = [
  'index.html',
  'research.html',
  'hunt-research.html',
  'verify.html',
  'verify.htmlm',
  'hard-copy.html',
  'hard-data.html',
  'coverage.html',
  'builder.html',
  'vetting.html',
  'app.js',
  'config.js',
  'data.js',
  'boundary-resolver.js',
  'embed-mode.js',
  'event-handlers.js',
  'google-basemap.js',
  'header-layout.js',
  'hunt-research.js',
  'map-engine.js',
  'ownership-dock.js',
  'sentry-browser-init.js',
  'style.css',
  'ui.js',
  'uoga-analytics.js',
  'coverage.js',
  'manifest.json',
  'favicon.ico',
  'CNAME',
  '.nojekyll',
];

const dataFiles = [
  'data/hunt-master-canonical-2026-foundation.json',
  'data/hunt-master-canonical-2026-source-of-truth.json',
  'data/runtime-manifest.json',
  'data/hunt_predictions.json',
  'data/hunt_application_outlook.json',
  'data/hunt_odds_history.json',
  'data/hunt_odds_history.csv',
  'data/hunt_units.geojson',
  'data/source_snapshots.json',
  'data/public_contract_summary.json',
  'data/elk_hunt_table_official.json',
  'data/elk_antlerless_hunt_table_official.json',
  'data/pronghorn_hunt_table_official.json',
  'data/moose_hunt_table_official.json',
  'data/mountain_goat_hunt_table_official.json',
  'data/bison_hunt_table_official.json',
  'data/bighorn_sheep_hunt_table_official.json',
  'data/black_bear_hunt_table_official.json',
  'data/cougar_hunt_table_official.json',
  'data/turkey_hunt_table_official.json',
  'data/conservation-permit-areas.json',
  'data/conservation-permit-hunt-table-2025-27.json',
  'data/outfitters-public.json',
  'data/outfitters.json',
  'data/cwmu-boundaries.geojson',
  'data/dwr-GetCWMUBoundaries.json',
  'data/statewide-composite-members-2026-lite.geojson',
  'data/hunt_boundaries_finalized_2026.geojson',
];

const processedFiles = [
  'processed_data/composite_hunt_unit_mapping_2026.geojson',
  'processed_data/statewide_composite_boundaries_2026_FINAL_LOCKED.geojson',
  'processed_data/statewide_composite_boundaries_2026.geojson',
  'processed_data/draw_reality_engine.csv',
  'processed_data/draw_reality_engine_v2.csv',
  'processed_data/draw_reality_engine_predictive_v2.csv',
  'processed_data/ml_draw_predictions_v1.csv',
  'processed_data/point_ladder_view.csv',
  'processed_data/hunt_master_enriched.csv',
  'processed_data/hunt_unit_reference_linked.csv',
  'processed_data/hunt_database_complete.csv',
  'processed_data/hunt-master-canonical-2026-source-of-truth.csv',
  'processed_data/hunt-master-canonical-2026-source-of-truth.json',
  'processed_data/current_to_historical_hunt_code_crosswalk_2026.csv',
  'processed_data/draw_system_coverage_report.csv',
  'processed_data/predictive_coverage_report.csv',
  'processed_data/research_library_master.csv',
  'processed_data/harvest_master.csv',
  'processed_data/harvest_quality_features_all_years_by_hunt_code.csv',
  'processed_data/online_runtime_crosscheck.json',
  'processed_data/hunt_code_boundary_map_2026.csv',
  'processed_data/boundary_registry_2026.csv',
  'processed_data/boundary-manifest-2026.json',
  'processed_data/boundary-manifest-2026.csv',
  'processed_data/display-boundary-index-2026.json',
  'processed_data/display-boundary-index-2026.csv',
  'processed_data/boundary-id-overrides-2026.json',
  'processed_data/display-boundary-synthetic-id-map-2026.json',
  'processed_data/display-boundary-synthetic-id-map-2026.csv',
  'processed_data/boundary_id_render_map_verification_2026.json',
  'processed_data/outfitter-federal-unit-coverage-review.json',
  'processed_data/coverage-matrix.json',
  'processed_data/normalized-staging-audit.csv',
  'processed_data/normalized-staging-audit.json',
];

const dirsToCopy = [
  'assets',
  'data/boundaries',
  'processed_data/boundaries',
  'processed_data/hard_data_exports',
  'processed_data/library',
  'processed_data/management_context',
  'processed_data/production',
  'processed_data/public_contracts',
  'processed_data/research_page',
  'public/data',
  'public/hard-copy',
];

const BLOCKED_PUBLIC_EXTENSIONS = new Set(['.md', '.txt']);
const BLOCKED_PUBLIC_BASENAME_PATTERNS = [
  /^agents(?:[._-]|$)/i,
  /^codex(?:[._-]|$)/i,
  /^audit(?:[._-]|$)/i,
  /^implementation(?:[._-]|$)/i,
  /^internal(?:[._-]|$)/i,
  /^planning(?:[._-]|$)/i,
  /^task(?:[._-]|$)/i,
];
const BLOCKED_PUBLIC_PATH_PATTERNS = [
  /\/audits?\//i,
  /\/internal\//i,
];
const BLOCKED_SOURCE_DIR_PATTERNS = [
  /^\.wrangler(?:\/|\\|$)/i,
  /^node_modules(?:\/|\\|$)/i,
  /^audits(?:\/|\\|$)/i,
  /^data_truth(?:\/|\\|$)/i,
];

function toPosix(relPath) {
  return String(relPath || '').replace(/\\/g, '/');
}

function normalizeRelPath(relPath) {
  return toPosix(relPath);
}

function isBlockedSourcePath(relPath) {
  const normalized = toPosix(relPath);
  return BLOCKED_SOURCE_DIR_PATTERNS.some((pattern) => pattern.test(normalized));
}

function isBlockedPublicPath(relPath) {
  const normalized = normalizeRelPath(relPath);
  const lower = normalized.toLowerCase();
  const ext = path.extname(lower);
  if (BLOCKED_PUBLIC_EXTENSIONS.has(ext)) return true;
  if (BLOCKED_PUBLIC_PATH_PATTERNS.some((pattern) => pattern.test(lower))) return true;
  const base = path.basename(lower);
  return BLOCKED_PUBLIC_BASENAME_PATTERNS.some((pattern) => pattern.test(base));
}

function formatSizeMb(sizeBytes) {
  return Number((sizeBytes / (1024 * 1024)).toFixed(1));
}

function loadRuntimeManifestEntries() {
  for (const manifestPath of RUNTIME_MANIFEST_CANDIDATES) {
    if (!fsSync.existsSync(manifestPath)) continue;
    try {
      const raw = fsSync.readFileSync(manifestPath, 'utf8');
      const parsed = JSON.parse(raw || '{}');
      const assets = Array.isArray(parsed.assets) ? parsed.assets : [];
      const map = new Map();
      for (const asset of assets) {
        if (!asset || !asset.path) continue;
        const normalized = toPosix(asset.path);
        map.set(normalized, {
          r2_key_guess: asset.key || '',
          public_url_guess: asset.canonical_url || '',
        });
      }
      if (map.size > 0) {
        return map;
      }
    } catch {
      // Ignore malformed manifest content; pages build should continue.
    }
  }
  return new Map();
}

function addLargeRuntimeRecord(records, relPath, sizeBytes, sourceManifest, tooLarge) {
  const normalized = toPosix(relPath);
  const mapped = sourceManifest && typeof sourceManifest.get === 'function'
    ? sourceManifest.get(normalized) || {}
    : {};
  records.push({
    source_path: normalized,
    size_bytes: sizeBytes,
    size_mb: formatSizeMb(sizeBytes),
    r2_key_guess: mapped.r2_key_guess || '',
    public_url_guess: mapped.public_url_guess || '',
    copy_status: 'SKIPPED_LARGE_R2_REQUIRED',
  });
  if (Array.isArray(tooLarge)) {
    tooLarge.push(`${normalized} (${formatSizeMb(sizeBytes)} MiB; SKIPPED_LARGE_R2_REQUIRED)`);
  }
}

async function writeLargeAssetManifest(records) {
  const payload = {
    generated_at: new Date().toISOString(),
    max_public_file_bytes: MAX_PAGES_FILE_BYTES,
    max_public_file_mb: formatSizeMb(MAX_PAGES_FILE_BYTES),
    reason: 'SKIPPED_LARGE_R2_REQUIRED',
    files: records,
  };
  await ensureParent(LARGE_MANIFEST_PATH);
  await fs.writeFile(LARGE_MANIFEST_PATH, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function writeOptionalAuditReport(records, skippedPublicPaths, skippedByDirectory) {
  const report = {
    generated_at: new Date().toISOString(),
    max_public_file_bytes: MAX_PAGES_FILE_BYTES,
    max_public_file_mb: formatSizeMb(MAX_PAGES_FILE_BYTES),
    skipped_files: records.length,
    skipped_due_to_path_rules: skippedByDirectory.length,
    skipped_for_100mb_limit: skippedPublicPaths.length,
    skipped_records: records,
  };
  await ensureParent(AUDIT_REPORT_PATH);
  return fs.writeFile(AUDIT_REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
}

function simplifyRing(points) {
  if (!Array.isArray(points) || points.length < 4) return null;
  const step = points.length > 1200 ? 12 : points.length > 700 ? 8 : points.length > 300 ? 5 : 3;
  const out = [];
  for (let i = 0; i < points.length; i += step) {
    const pt = points[i];
    if (!Array.isArray(pt) || pt.length < 2) continue;
    out.push([Number(pt[0].toFixed(5)), Number(pt[1].toFixed(5))]);
  }
  const last = points[points.length - 1];
  if (Array.isArray(last) && last.length >= 2) {
    const lastRounded = [Number(last[0].toFixed(5)), Number(last[1].toFixed(5))];
    if (!out.length || out[out.length - 1][0] !== lastRounded[0] || out[out.length - 1][1] !== lastRounded[1]) {
      out.push(lastRounded);
    }
  }
  if (out.length < 4) return null;
  if (out[0][0] !== out[out.length - 1][0] || out[0][1] !== out[out.length - 1][1]) {
    out.push(out[0]);
  }
  return out.length >= 4 ? out : null;
}

async function buildBoundaryArtifacts(missing, tooLarge, skippedLargeRecords, runtimeManifest) {
  const arcgisPath = path.join(repoRoot, 'data', 'hunt_boundaries_arcgis.json');
  const liteFallbackPath = path.join(repoRoot, 'data', 'hunt-boundaries-lite.geojson');
  const outputLite = path.join(outDir, 'data', 'hunt-boundaries-lite.geojson');
  const outputFullAlias = path.join(outDir, 'data', 'hunt_boundaries.geojson');

  if (await exists(arcgisPath)) {
    const text = await fs.readFile(arcgisPath, 'utf8');
    const source = JSON.parse(text);
    const sourceFeatures = Array.isArray(source.features) ? source.features : [];
    const features = sourceFeatures.map((feature) => {
      const attrs = feature?.attributes || {};
      const rings = feature?.geometry?.rings;
      if (!Array.isArray(rings) || !rings.length) return null;
      const simplifiedRings = rings
        .slice(0, 30)
        .map(simplifyRing)
        .filter(Boolean);
      if (!simplifiedRings.length) return null;
      const boundaryId = String(attrs.BoundaryID ?? '').trim();
      const boundaryName = String(attrs.Boundary_Name ?? '').trim();
      return {
        type: 'Feature',
        properties: {
          boundary_id: boundaryId,
          BoundaryID: boundaryId,
          Boundary_Name: boundaryName,
          boundary_name: boundaryName,
          source: 'arcgis_lite_individual',
        },
        geometry: {
          type: 'MultiPolygon',
          coordinates: simplifiedRings.map((ring) => [ring]),
        },
      };
    }).filter(Boolean);

    const liteGeoJson = {
      type: 'FeatureCollection',
      name: 'hunt-boundaries-lite-individual',
      metadata: {
        source: 'data/hunt_boundaries_arcgis.json',
        purpose: 'Cloudflare-safe individual hunt boundary layer',
        feature_count: features.length,
      },
      features,
    };

    const payload = JSON.stringify(liteGeoJson);
    if (Buffer.byteLength(payload, 'utf8') > MAX_PAGES_FILE_BYTES) {
      const bytes = Buffer.byteLength(payload, 'utf8');
      addLargeRuntimeRecord(skippedLargeRecords, 'data/hunt-boundaries-lite.geojson', bytes, runtimeManifest, tooLarge);
      return;
    }

    await ensureParent(outputLite);
    await fs.writeFile(outputLite, payload, 'utf8');
    await ensureParent(outputFullAlias);
    await fs.writeFile(outputFullAlias, payload, 'utf8');
    return;
  }

  if (await exists(liteFallbackPath)) {
    await copyFileIfExists('data/hunt-boundaries-lite.geojson', missing, tooLarge, skippedLargeRecords, runtimeManifest);
    const fallbackText = await fs.readFile(liteFallbackPath, 'utf8');
    const fallbackSizeBytes = Buffer.byteLength(fallbackText, 'utf8');
    if (fallbackSizeBytes <= MAX_PAGES_FILE_BYTES) {
      await ensureParent(outputFullAlias);
      await fs.writeFile(outputFullAlias, fallbackText, 'utf8');
    } else {
      addLargeRuntimeRecord(skippedLargeRecords, 'data/hunt-boundaries-lite.geojson', fallbackSizeBytes, runtimeManifest, tooLarge);
    }
    return;
  }

  missing.push('data/hunt_boundaries_arcgis.json');
  missing.push('data/hunt-boundaries-lite.geojson');
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function ensureParent(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
}

function hasRuntimeManifestRecord(relPath, runtimeManifest) {
  if (!runtimeManifest || typeof runtimeManifest.get !== 'function') {
    return null;
  }
  const normalized = toPosix(relPath);
  const mapped = runtimeManifest.get(normalized);
  if (!mapped) return null;
  return {
    r2_key_guess: mapped.r2_key_guess || '',
    public_url_guess: mapped.public_url_guess || '',
  };
}

async function copyFileIfExists(relPath, missing, tooLarge, skippedLargeRecords, runtimeManifest) {
  if (isBlockedPublicPath(relPath)) return;
  if (isBlockedSourcePath(relPath)) {
    missing.push(`${relPath} (skipped by source-path guard)`);
    return;
  }
  const src = path.join(repoRoot, relPath);
  const dest = path.join(outDir, relPath);
  if (!(await exists(src))) {
    missing.push(relPath);
    return;
  }
  const stat = await fs.stat(src);
  if (stat.size > MAX_PAGES_FILE_BYTES) {
    addLargeRuntimeRecord(skippedLargeRecords, relPath, stat.size, runtimeManifest, tooLarge);
    return;
  }
  await ensureParent(dest);
  await fs.copyFile(src, dest);
}

async function copyDirIfExists(relPath, missing, tooLarge, skippedLargeRecords, runtimeManifest, skippedByDirectory) {
  const blockedReason = isBlockedSourcePath(relPath) ? 'source path blocked' : null;
  if (blockedReason) {
    missing.push(`${relPath} (${blockedReason})`);
    if (Array.isArray(skippedByDirectory)) {
      skippedByDirectory.push(`${relPath} (source-path blocked)`);
    }
    return;
  }
  const src = path.join(repoRoot, relPath);
  const dest = path.join(outDir, relPath);
  if (!(await exists(src))) {
    missing.push(relPath);
    return;
  }
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.cp(src, dest, {
    recursive: true,
    filter: (sourcePath) => {
      const rel = normalizeRelPath(path.relative(repoRoot, sourcePath));
      if (isBlockedSourcePath(rel) || isBlockedPublicPath(rel)) return false;
      if (fsSync.existsSync(sourcePath)) {
        const stats = fsSync.lstatSync(sourcePath);
        if (stats.isFile() && stats.size > MAX_PAGES_FILE_BYTES) {
          const mapped = hasRuntimeManifestRecord(rel, runtimeManifest) || {};
          skippedLargeRecords.push({
            source_path: toPosix(rel),
            size_bytes: stats.size,
            size_mb: formatSizeMb(stats.size),
            r2_key_guess: mapped.r2_key_guess || '',
            public_url_guess: mapped.public_url_guess || '',
            copy_status: 'SKIPPED_LARGE_R2_REQUIRED',
          });
          tooLarge.push(`${rel} (${formatSizeMb(stats.size)} MiB; SKIPPED_LARGE_R2_REQUIRED)`);
          return false;
        }
      }
      return true;
    },
  });
}

async function copyPdfIfExists(srcPath, destPath, relPath, skippedLargeRecords, tooLarge, runtimeManifest) {
  if (!(await exists(srcPath))) return;
  if (isBlockedPublicPath(relPath) || isBlockedSourcePath(relPath)) {
    return;
  }
  const stat = await fs.stat(srcPath);
  if (stat.size > MAX_PAGES_FILE_BYTES) {
    const mapped = hasRuntimeManifestRecord(relPath, runtimeManifest) || {};
    skippedLargeRecords.push({
      source_path: toPosix(relPath),
      size_bytes: stat.size,
      size_mb: formatSizeMb(stat.size),
      r2_key_guess: mapped.r2_key_guess || '',
      public_url_guess: mapped.public_url_guess || '',
      copy_status: 'SKIPPED_LARGE_R2_REQUIRED',
    });
    tooLarge.push(`${relPath} (${formatSizeMb(stat.size)} MiB; SKIPPED_LARGE_R2_REQUIRED)`);
    return;
  }
  await ensureParent(destPath);
  await fs.copyFile(srcPath, destPath);
}

async function writeConfigLocalStub() {
  const target = path.join(outDir, 'config.local.js');
  const body = [
    'window.UOGA_CONFIG_LOCAL = window.UOGA_CONFIG_LOCAL || {};',
    '',
  ].join('\n');
  await fs.writeFile(target, body, 'utf8');
}

async function copyPublicRegulationPdfs(missing, skippedLarge, tooLarge, runtimeManifest) {
  const srcDir = path.join(repoRoot, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations');
  const destDir = path.join(outDir, 'public', 'hard-copy', 'regulations', '2026');
  if (!(await exists(srcDir))) {
    missing.push('pipeline/RAW/hunt_unit_database/2026/pdf/regulations');
    return;
  }

  await fs.mkdir(destDir, { recursive: true });
  const entries = await fs.readdir(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!entry.name.toLowerCase().endsWith('.pdf')) continue;
    const srcPdf = path.join(srcDir, entry.name);
    const relPath = normalizeRelPath(path.relative(repoRoot, srcPdf));
    await copyPdfIfExists(srcPdf, path.join(destDir, entry.name), relPath, skippedLarge, tooLarge, runtimeManifest);
  }
}

async function ensureWallpaperAliases(missing) {
  const sourceDir = path.join(repoRoot, 'assets', 'backgrounds');
  const outBackgrounds = path.join(outDir, 'assets', 'backgrounds');
  const sourceLower = path.join(sourceDir, 'library-wallpaper.jpg');
  const sourceUpper = path.join(sourceDir, 'LIBRARY-WALLPAPER.jpg');
  const outLower = path.join(outBackgrounds, 'library-wallpaper.jpg');
  const outUpper = path.join(outBackgrounds, 'LIBRARY-WALLPAPER.jpg');

  const hasLower = await exists(sourceLower);
  const hasUpper = await exists(sourceUpper);
  const source = hasLower ? sourceLower : (hasUpper ? sourceUpper : null);

  if (!source) {
    missing.push('assets/backgrounds/library-wallpaper.jpg');
    return;
  }

  await fs.mkdir(outBackgrounds, { recursive: true });
  await fs.copyFile(source, outLower);
  await fs.copyFile(source, outUpper);
}

async function ensureHardCopyAliases(missing) {
  const source = path.join(outDir, 'public', 'hard-copy');
  const target = path.join(outDir, 'hard-copy');
  if (!(await exists(source))) {
    missing.push('pages-dist/public/hard-copy (hard-copy alias source missing)');
    return;
  }
  await fs.rm(target, { recursive: true, force: true });
  await fs.cp(source, target, { recursive: true });
}

async function main() {
  await fs.rm(outDir, { recursive: true, force: true });
  await fs.mkdir(outDir, { recursive: true });

  const missing = [];
  const tooLarge = [];
  const skippedLargeByManifest = [];
  const runtimeManifest = loadRuntimeManifestEntries();
  const skippedForPathRules = [];

  for (const relPath of rootFiles) {
    await copyFileIfExists(relPath, missing, tooLarge, skippedLargeByManifest, runtimeManifest);
  }

  await buildBoundaryArtifacts(missing, tooLarge, skippedLargeByManifest, runtimeManifest);
  for (const relPath of dataFiles) {
    await copyFileIfExists(relPath, missing, tooLarge, skippedLargeByManifest, runtimeManifest);
  }
  for (const relPath of processedFiles) {
    await copyFileIfExists(relPath, missing, tooLarge, skippedLargeByManifest, runtimeManifest);
  }
  for (const relPath of dirsToCopy) {
    await copyDirIfExists(relPath, missing, tooLarge, skippedLargeByManifest, runtimeManifest, skippedForPathRules);
  }

  await copyPublicRegulationPdfs(missing, skippedLargeByManifest, tooLarge, runtimeManifest);
  await ensureHardCopyAliases(missing);
  await ensureWallpaperAliases(missing);
  await writeLargeAssetManifest(skippedLargeByManifest);
  await writeOptionalAuditReport(skippedLargeByManifest, tooLarge, skippedForPathRules);

  await writeConfigLocalStub();

  console.log(`pages-dist build complete: ${outDir}`);
  if (missing.length) {
    console.log('Missing optional paths:');
    for (const item of missing) {
      console.log(`- ${item}`);
    }
  }
  if (tooLarge.length) {
    console.log(`Skipped oversized paths for Cloudflare Pages (${(MAX_PAGES_FILE_BYTES / (1024 * 1024)).toFixed(0)} MiB limit):`);
    for (const item of tooLarge) {
      console.log(`- ${item}`);
    }
  }
}

main().catch((error) => {
  console.error('Failed to build pages-dist.');
  console.error(error);
  process.exit(1);
});
