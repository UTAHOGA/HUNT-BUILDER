const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const auditDir = path.join(root, 'processed_data', 'audits');
const pages = ['index.html', 'research.html', 'hard-copy.html', 'verify.html'];

const thresholds = {
  scriptStyleReview: 500 * 1024,
  dataR2: 5 * 1024 * 1024,
  geoSplit: 5 * 1024 * 1024,
  pagesPdfLimit: 25 * 1024 * 1024,
  imageCompress: 1 * 1024 * 1024,
};

const scanRoots = [
  'pages-dist',
  'assets',
  'data',
  'processed_data/library',
  'processed_data/hard_data_exports',
  'processed_data/production',
  'public',
];

const runtimeDenyTokens = [
  'hunt_master_enriched.csv',
  'point_ladder_view.csv',
  'draw_reality_engine_predictive_v2.csv',
  'draw_reality_engine_v2.csv',
  'ml_draw_predictions_v1.csv',
  'draw_system_coverage_report.csv',
  'predictive_coverage_report.csv',
  'model_outputs/',
  'processed_data/audits/',
  'current_to_historical_hunt_code_crosswalk_2026.csv',
  'hunt_database_complete.csv',
  'active_data_feed_',
  'classification_tags',
  'hunt_application_outlook',
];

function text(value) {
  return String(value ?? '').trim();
}

function lower(value) {
  return text(value).toLowerCase();
}

function bool(value) {
  return value ? 'true' : 'false';
}

function esc(value) {
  const raw = value == null ? '' : Array.isArray(value) ? value.join('|') : String(value);
  return /[",\r\n]/.test(raw) ? `"${raw.replace(/"/g, '""')}"` : raw;
}

async function writeCsv(relPath, rows, columns) {
  const file = path.join(root, relPath);
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const lines = [columns.map(esc).join(',')];
  for (const row of rows) lines.push(columns.map((col) => esc(row[col])).join(','));
  await fsp.writeFile(file, `${lines.join('\n')}\n`, 'utf8');
}

async function writeJson(relPath, value) {
  const file = path.join(root, relPath);
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function rel(file) {
  return path.relative(root, file).replace(/\\/g, '/');
}

async function exists(file) {
  try {
    await fsp.access(file);
    return true;
  } catch {
    return false;
  }
}

async function walk(dir, out = []) {
  if (!(await exists(dir))) return out;
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (['.git', 'node_modules'].includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, out);
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

function fileType(filePath) {
  const ext = path.extname(filePath).slice(1).toLowerCase();
  if (['html', 'htm'].includes(ext)) return 'HTML';
  if (ext === 'js' || ext === 'mjs') return 'JS';
  if (ext === 'css') return 'CSS';
  if (ext === 'csv') return 'CSV';
  if (ext === 'json') return 'JSON';
  if (ext === 'geojson' || ext === 'kml') return 'GeoJSON';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'ico'].includes(ext)) return 'image';
  if (ext === 'pdf') return 'PDF';
  if (['xlsx', 'xls'].includes(ext)) return 'spreadsheet';
  if (['sqlite', 'db'].includes(ext)) return 'database';
  return ext ? ext.toUpperCase() : 'unknown';
}

function isLarge(type, size) {
  if (['JS', 'CSS'].includes(type)) return size > thresholds.scriptStyleReview;
  if (['CSV', 'JSON'].includes(type)) return size > thresholds.dataR2;
  if (type === 'GeoJSON') return size > thresholds.geoSplit;
  if (type === 'PDF') return size > thresholds.pagesPdfLimit;
  if (type === 'image') return size > thresholds.imageCompress;
  return size > thresholds.dataR2;
}

function recommendationFor(row) {
  const recs = [];
  if (row.should_not_publish === 'true') recs.push('Do not publish directly to Pages; move behind curated link/R2 or remove from public package.');
  if (row.should_cloudflare_r2 === 'true') recs.push('Serve from Cloudflare/R2 or Workers endpoint instead of Pages.');
  if (row.should_split === 'true') recs.push('Split/tile/simplify this asset before browser runtime use.');
  if (row.should_compress === 'true') recs.push('Compress or convert before public delivery.');
  if (row.should_lazy_load === 'true') recs.push('Lazy-load only after user opens this page feature.');
  if (row.is_blocking_likely === 'true') recs.push('Review as likely render/load blocker.');
  if (!recs.length) recs.push('OK for current audit threshold.');
  return recs.join(' ');
}

function cleanUrl(url) {
  return text(url)
    .replace(/^\.\/+/, '')
    .replace(/^\//, '')
    .split('?')[0]
    .split('#')[0];
}

function parseHtmlDeps(page) {
  const file = path.join(root, page);
  if (!fs.existsSync(file)) return { js: [], css: [], external: [], inline_script_count: 0 };
  const raw = fs.readFileSync(file, 'utf8');
  const head = raw.split(/<\/head>/i)[0] || raw;
  const js = [];
  const css = [];
  const external = [];
  const scriptRe = /<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi;
  const cssRe = /<link\b[^>]*\brel=["']stylesheet["'][^>]*\bhref=["']([^"']+)["'][^>]*>/gi;
  let match;
  while ((match = scriptRe.exec(raw))) {
    const src = match[1];
    if (/^https?:\/\//i.test(src)) external.push(src);
    else js.push(cleanUrl(src));
  }
  while ((match = cssRe.exec(raw))) {
    const href = match[1];
    if (/^https?:\/\//i.test(href)) external.push(href);
    else css.push(cleanUrl(href));
  }
  const inlineScriptCount = (head.match(/<script\b(?![^>]*\bsrc=)/gi) || []).length;
  return { js: [...new Set(js)], css: [...new Set(css)], external: [...new Set(external)], inline_script_count: inlineScriptCount };
}

function loadConfig() {
  const sandbox = {
    window: {
      location: { protocol: 'https:', hostname: 'huntbuilder.uoga.org' },
      UOGA_LOCAL_CONFIG: {},
    },
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(root, 'config.js'), 'utf8'), sandbox, { filename: 'config.js' });
  return sandbox.window.UOGA_CONFIG || {};
}

function flattenSources(value) {
  const out = [];
  function visit(item) {
    if (!item) return;
    if (typeof item === 'string') out.push(item);
    else if (Array.isArray(item)) item.forEach(visit);
    else if (typeof item === 'object') Object.values(item).forEach(visit);
  }
  visit(value);
  return [...new Set(out.filter(Boolean))];
}

function dataDepsForPage(page, cfg) {
  if (page === 'index.html') {
    return flattenSources([
      cfg.HUNT_DATA_SOURCES,
      cfg.HUNT_BOUNDARY_SOURCES,
      cfg.BOUNDARY_MANIFEST_SOURCES,
      cfg.DISPLAY_BOUNDARY_INDEX_SOURCES,
      cfg.FINALIZED_BOUNDARY_SOURCES,
      cfg.COMPOSITE_BOUNDARY_SOURCES,
      cfg.OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
      cfg.OUTFITTERS_DATA_SOURCES,
      cfg.OUTFITTER_FEDERAL_COVERAGE_SOURCES,
      cfg.CONSERVATION_PERMIT_AREA_SOURCES,
      cfg.CONSERVATION_PERMIT_HUNT_TABLE_SOURCES,
    ]);
  }
  if (page === 'research.html') {
    return flattenSources([
      cfg.HUNT_RESEARCH_ENGINE_SOURCES,
      cfg.HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES,
      cfg.HUNT_RESEARCH_LADDER_SOURCES,
      cfg.HUNT_RESEARCH_MASTER_SOURCES,
      cfg.HUNT_RESEARCH_REFERENCE_SOURCES,
      './processed_data/management_context/hunt_management_objective_context.json',
    ]);
  }
  if (page === 'hard-copy.html') {
    return ['./processed_data/hard_data_exports/library/public_library_allowlist.json'];
  }
  if (page === 'verify.html') {
    return ['https://wildlife.utah.gov/guide/outfitter.html'];
  }
  return [];
}

async function dependencyMap() {
  const cfg = loadConfig();
  const depByPath = new Map();
  const pageReports = [];
  for (const page of pages) {
    const deps = parseHtmlDeps(page);
    const dataFiles = dataDepsForPage(page, cfg);
    const allLocal = [...deps.js, ...deps.css, ...dataFiles.map(cleanUrl).filter((url) => !/^https?:/i.test(url))];
    allLocal.forEach((dep) => {
      const clean = cleanUrl(dep);
      if (!clean) return;
      const set = depByPath.get(clean) || new Set();
      set.add(page);
      depByPath.set(clean, set);
      const distClean = `pages-dist/${clean}`;
      const distSet = depByPath.get(distClean) || new Set();
      distSet.add(page);
      depByPath.set(distClean, distSet);
    });
    const large = [];
    for (const dep of allLocal) {
      const clean = cleanUrl(dep);
      const src = path.join(root, clean);
      const dist = path.join(root, 'pages-dist', clean);
      const candidate = fs.existsSync(dist) ? dist : src;
      if (fs.existsSync(candidate)) {
        const stat = await fsp.stat(candidate);
        if (isLarge(fileType(candidate), stat.size)) large.push(`${clean} (${Math.round(stat.size / 1024)} KiB)`);
      }
    }
    const likely = [];
    if (deps.css.length) likely.push('CSS in document head blocks first render.');
    if (deps.external.some((url) => url.includes('sentry'))) likely.push('Sentry CDN loads on page start.');
    if (page === 'index.html') likely.push('Map/boundary data and Google Maps should stay builder-only and lazy where possible.');
    if (page === 'research.html') likely.push('Large Research CSVs should remain Cloudflare-first and ladder should wait for hunt selection.');
    if (page === 'hard-copy.html') likely.push('PDF.js/page-flip should remain lazy-loaded only when opening PDF viewer.');
    if (page === 'verify.html') likely.push('Outfitter data should not load until the page needs public cards/search.');
    pageReports.push({
      page,
      js_files_loaded: deps.js.join('|'),
      css_files_loaded: deps.css.join('|'),
      data_files_fetched: dataFiles.join('|'),
      large_dependencies: large.join('|'),
      external_dependencies: deps.external.join('|'),
      likely_load_blockers: likely.join('|'),
      recommended_lazy_load_changes: recommendationsForPage(page).join('|'),
    });
  }
  return { depByPath, pageReports };
}

function recommendationsForPage(page) {
  if (page === 'index.html') return [
    'Keep Google Maps, boundary GeoJSON, and outfitter matching builder-only.',
    'Prefer R2/Workers for composite boundary GeoJSON and large canonical data.',
    'Defer outfitter marker geocoding until a hunt is selected.',
  ];
  if (page === 'research.html') return [
    'Keep Cloudflare-first runtime CSVs.',
    'Lazy-load management objective/comparable-hunts layer after core summary.',
    'Avoid rendering full ladder until a hunt is selected.',
    'Keep source/model details collapsed by default.',
  ];
  if (page === 'hard-copy.html') return [
    'Keep PDF flipbook libraries lazy until a PDF is opened.',
    'Split public library manifest by folder/category.',
    'Hide raw runtime/audit files from public library.',
  ];
  if (page === 'verify.html') return [
    'Use outfitter-public.json only after records are public-ready.',
    'Lazy-load public outfitter cards/search data after page shell renders.',
  ];
  return [];
}

async function performanceReport(depByPath) {
  const files = new Set();
  for (const scanRoot of scanRoots) {
    const dir = path.join(root, scanRoot);
    for (const file of await walk(dir)) files.add(file);
  }
  const rows = [];
  for (const file of [...files].sort((a, b) => rel(a).localeCompare(rel(b)))) {
    const stat = await fsp.stat(file);
    const r = rel(file);
    const type = fileType(file);
    const dependency = [...(depByPath.get(r) || depByPath.get(r.replace(/^pages-dist\//, '')) || new Set())].join('|');
    const large = isLarge(type, stat.size);
    const isRuntime = /processed_data\/(hunt_master|point_ladder|draw_reality|ml_draw|research_page|audits)/i.test(r);
    const shouldR2 = (['CSV', 'JSON'].includes(type) && stat.size > thresholds.dataR2) || (type === 'GeoJSON' && stat.size > thresholds.geoSplit) || (type === 'PDF' && stat.size > thresholds.pagesPdfLimit);
    const shouldSplit = (type === 'GeoJSON' && stat.size > thresholds.geoSplit) || (['CSV', 'JSON'].includes(type) && stat.size > thresholds.dataR2 && isRuntime);
    const shouldCompress = (type === 'image' && stat.size > thresholds.imageCompress) || (['CSV', 'JSON'].includes(type) && stat.size > thresholds.dataR2 && !/\.gz$/i.test(r));
    const shouldNotPublish = (type === 'database') || (type === 'PDF' && stat.size > thresholds.pagesPdfLimit) || /processed_data\/audits\//.test(r) || /CLEAN_XLXS_STAGED|_XLXS_CLEAN_BUILD|_PDF_CLEAN_BUILD|XLXS\.zip/i.test(r);
    const likelyBlocking = !!dependency && (['CSS'].includes(type) || (type === 'JS' && stat.size > thresholds.scriptStyleReview));
    const shouldLazy = !!dependency && (large || type === 'PDF' || type === 'GeoJSON' || isRuntime || /outfitter|library_page|management_context/i.test(r));
    const row = {
      path: r,
      size_bytes: stat.size,
      file_type: type,
      page_dependency: dependency || '',
      is_large: bool(large),
      is_blocking_likely: bool(likelyBlocking),
      should_lazy_load: bool(shouldLazy),
      should_cloudflare_r2: bool(shouldR2),
      should_compress: bool(shouldCompress),
      should_split: bool(shouldSplit),
      should_not_publish: bool(shouldNotPublish),
      recommendation: '',
    };
    row.recommendation = recommendationFor(row);
    rows.push(row);
  }
  return rows;
}

async function readJsonArray(relPath) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return [];
  const parsed = JSON.parse(await fsp.readFile(file, 'utf8'));
  return Array.isArray(parsed) ? parsed : Array.isArray(parsed.rows) ? parsed.rows : Array.isArray(parsed.data) ? parsed.data : [parsed];
}

function inferYear(item, hay) {
  const y = text(item.year || '').match(/20\d{2}/)?.[0] || hay.match(/20\d{2}/)?.[0] || '';
  return y;
}

function libraryCategory(item, sourcePath, stat, visibleIds, hrefSet, basenameCounts) {
  const href = cleanUrl(item.href || sourcePath);
  const hay = lower(`${item.title || ''} ${item.subtitle || ''} ${item.href || ''} ${sourcePath}`);
  const year = inferYear(item, hay);
  const status = [];
  if (runtimeDenyTokens.some((token) => hay.includes(token))) status.push('raw_runtime_should_hide');
  if (/audit|manifest|intermediate|staged|clean_build|_build_report|validation|coverage_report/.test(hay)) status.push('internal_only');
  if (/guidebook|regulation|application|deadline|calendar|harvest|draw|permit|hunt table|map|boundary|library_page_hunts/.test(hay)) status.push('public_useful');
  if (/library_page_data|library_page_summary|hard_data_manifest/.test(hay)) status.push('internal_only');
  if (basenameCounts.get(path.basename(href || sourcePath).toLowerCase()) > 1) status.push('duplicate');
  if (year && Number(year) < 2024 && /regulation|guidebook|application/.test(hay)) status.push('outdated');
  if (stat && stat.size > thresholds.pagesPdfLimit && /\.pdf$/i.test(sourcePath || href)) status.push('oversized');
  if (item.title && /[_-]{2,}|\.csv|\.json|\.pdf/i.test(item.title)) status.push('needs_title_cleanup');
  if (!item.subtitle && !item.public_role && visibleIds.has(item.id)) status.push('needs_source_note');
  if (visibleIds.has(item.id) && !status.includes('public_useful')) status.push('public_but_categorize_better');
  if (!status.length) status.push(hrefSet.has(sourcePath) ? 'public_but_categorize_better' : 'internal_only');
  const localTarget = path.join(root, href);
  const pagesTarget = path.join(root, 'pages-dist', href);
  if (href && !/^https?:/i.test(href) && !fs.existsSync(localTarget) && !fs.existsSync(pagesTarget)) status.push('broken_link');
  return [...new Set(status)];
}

async function publicLibraryReport() {
  const allowlist = await readJsonArray('processed_data/hard_data_exports/library/public_library_allowlist.json');
  const visibleIds = new Set(allowlist.map((item) => text(item.id)).filter(Boolean));
  const hrefSet = new Set(allowlist.map((item) => cleanUrl(item.href)).filter(Boolean));
  const libraryFiles = [];
  for (const dir of ['processed_data/library', 'processed_data/hard_data_exports', 'public/hard-copy']) {
    for (const file of await walk(path.join(root, dir))) libraryFiles.push(file);
  }
  const basenameCounts = new Map();
  libraryFiles.forEach((file) => {
    const name = path.basename(file).toLowerCase();
    basenameCounts.set(name, (basenameCounts.get(name) || 0) + 1);
  });
  allowlist.forEach((item) => {
    const href = cleanUrl(item.href);
    if (href) basenameCounts.set(path.basename(href).toLowerCase(), (basenameCounts.get(path.basename(href).toLowerCase()) || 0) + 1);
  });
  const rows = [];
  for (const item of allowlist) {
    const href = cleanUrl(item.href);
    const local = path.join(root, href);
    const dist = path.join(root, 'pages-dist', href);
    const target = fs.existsSync(local) ? local : fs.existsSync(dist) ? dist : '';
    const stat = target ? await fsp.stat(target) : null;
    const statuses = libraryCategory(item, href, stat, visibleIds, hrefSet, basenameCounts);
    rows.push({
      source: 'public_library_allowlist',
      id: item.id || '',
      title: item.title || '',
      href: item.href || '',
      folder_id: item.folderId || item.folder_id || '',
      type: item.type || '',
      year: item.year || inferYear(item, lower(`${item.title || ''} ${item.href || ''}`)),
      size_bytes: stat?.size || '',
      visible_in_public_library: 'true',
      curation_status: statuses.join('|'),
      recommendation: libraryRecommendation(statuses),
    });
  }
  for (const file of libraryFiles) {
    const r = rel(file);
    const stat = await fsp.stat(file);
    const statuses = libraryCategory({}, r, stat, visibleIds, hrefSet, basenameCounts);
    rows.push({
      source: 'library_file_inventory',
      id: '',
      title: path.basename(file),
      href: r,
      folder_id: '',
      type: path.extname(file).slice(1).toLowerCase(),
      year: inferYear({}, lower(r)),
      size_bytes: stat.size,
      visible_in_public_library: bool(hrefSet.has(r)),
      curation_status: statuses.join('|'),
      recommendation: libraryRecommendation(statuses),
    });
  }
  return rows;
}

function libraryRecommendation(statuses) {
  if (statuses.includes('broken_link')) return 'Fix or remove broken public library link before display.';
  if (statuses.includes('raw_runtime_should_hide')) return 'Keep out of public library; route users to Hunt Research or curated summaries.';
  if (statuses.includes('internal_only')) return 'Do not expose directly in public hard-copy library.';
  if (statuses.includes('oversized')) return 'Move to Cloudflare/R2 or provide a smaller viewer/summary artifact.';
  if (statuses.includes('outdated')) return 'Keep only if clearly marked historical; otherwise hide from current-cycle folders.';
  if (statuses.includes('duplicate')) return 'Keep one canonical public entry and hide duplicates.';
  if (statuses.includes('needs_title_cleanup')) return 'Rename title for hunter-facing clarity.';
  if (statuses.includes('needs_source_note')) return 'Add source/year note before promotion.';
  if (statuses.includes('public_but_categorize_better')) return 'Curate into a clearer folder and add visitor-facing title/subtitle.';
  return 'Public-useful under current library rules.';
}

function list(value) {
  if (Array.isArray(value)) return value.map(text).filter(Boolean);
  if (!text(value)) return [];
  return [text(value)];
}

function inferServices(row) {
  const hay = lower(`${row.notes || ''} ${list(row.speciesServed).join(' ')} ${list(row.unitsServed).join(' ')} ${row.listingName || ''}`);
  const out = new Set();
  out.add('fully guided');
  if (/pack|horse|mule/.test(hay)) out.add('pack-out/recovery');
  if (/private/.test(hay)) out.add('private land access');
  if (/trophy|limited|henry|paunsaugunt|premium/.test(hay)) out.add('trophy hunt support');
  if (/antlerless|cow|doe|freezer/.test(hay)) out.add('antlerless/freezer hunt');
  if (/youth|beginner|entry/.test(hay)) out.add('youth/entry-level support');
  if (/bison|sheep|goat|once|oil|high country|mountain/.test(hay)) out.add('OIL species support');
  if (/sheep|goat|high country|mountain/.test(hay)) out.add('mountain goat/sheep/high-country support');
  if (/scout/.test(hay)) out.add('scouting package');
  return [...out];
}

function outfitterId(row, index) {
  return lower(row.id || row.slug || row.listingName || row.displayName || `outfitter-${index}`)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

async function outfitterReport() {
  const publicRows = await readJsonArray('data/outfitters-public.json');
  const internalRows = await readJsonArray('data/outfitters.json');
  const rows = [];
  const sourceRows = [
    ...publicRows.map((row) => ({ row, source: 'public' })),
    ...internalRows.map((row) => ({ row, source: 'internal' })),
  ];
  sourceRows.forEach(({ row, source }, index) => {
    const id = outfitterId(row, index);
    const name = text(row.display_name || row.displayName || row.listingName || row.businessName);
    const species = list(row.species || row.speciesServed);
    const units = list(row.units || row.unitsServed);
    const services = list(row.services || row.service_types || row.serviceTypes);
    const serviceTypes = services.length ? services : inferServices(row);
    const phone = list(row.phone || row.phonePrimary).join('|');
    const email = list(row.email || row.emailPrimary).join('|');
    const website = text(row.website);
    const reviewedAt = text(row.reviewed_at || row.reviewedAt);
    const evidenceCount = Number(row.source_evidence_count || row.sourceEvidenceCount || 0);
    const missing = [];
    if (!name) missing.push('display_name');
    if (!species.length) missing.push('species');
    if (!units.length) missing.push('units');
    if (!serviceTypes.length) missing.push('service_types');
    if (!website && !phone && !email) missing.push('contact');
    if (!reviewedAt) missing.push('reviewed_at');
    if (!evidenceCount) missing.push('source_evidence_count');
    const risk = [];
    if (source === 'internal') risk.push('not_in_public_feed');
    if (/first-pass|trial|normalization/i.test(text(row.notes))) risk.push('normalization_only');
    if (!phone && !email) risk.push('no_direct_contact');
    if (!units.length) risk.push('no_unit_coverage');
    if (!reviewedAt) risk.push('no_review_date');
    let readiness = 'PUBLIC_READY';
    if (source === 'internal') readiness = 'HOLD_INTERNAL_ONLY';
    if (missing.includes('contact')) readiness = 'NEEDS_CONTACT_INFO';
    if (missing.includes('units')) readiness = 'NEEDS_UNIT_COVERAGE';
    if (missing.includes('service_types')) readiness = 'NEEDS_SERVICE_TYPES';
    if (missing.includes('reviewed_at')) readiness = 'NEEDS_REVIEW_DATE';
    if (source === 'internal') readiness = 'HOLD_INTERNAL_ONLY';
    if (!name) readiness = 'BROKEN_RECORD';
    rows.push({
      outfitter_id: id,
      display_name: name,
      designation: text(row.designation || row.certLevel || row.listingType),
      status: text(row.status || row.verificationStatus),
      species: species.join('|'),
      units: units.join('|'),
      services: services.join('|'),
      contact: [website, phone, email].filter(Boolean).join('|'),
      website,
      phone,
      email,
      reviewed_at: reviewedAt,
      source_evidence_count: evidenceCount || '',
      insurance_or_license_notes: text(row.insurance_or_license_notes || row.licenseNotes || row.notes),
      federal_permit_units: [...list(row.federal_permit_units), ...list(row.blmDistricts), ...list(row.usfsForests)].join('|'),
      service_types: serviceTypes.join('|'),
      public_profile_ready: bool(source === 'public' && readiness === 'PUBLIC_READY'),
      missing_fields: missing.join('|'),
      risk_flags: risk.join('|'),
      readiness_status: readiness,
      source_feed: source,
    });
  });
  return { rows, publicRows, internalRows };
}

function summarize(rows, field) {
  return rows.reduce((acc, row) => {
    const value = text(row[field]) || '(blank)';
    acc[value] = (acc[value] || 0) + 1;
    return acc;
  }, {});
}

function markdownOutfitter(readinessRows, publicCount, internalCount) {
  const byStatus = summarize(readinessRows, 'readiness_status');
  const lines = [
    '# Outfitter Data Readiness Report',
    '',
    `Generated: ${new Date().toISOString()}`,
    '',
    `- Public feed rows: ${publicCount}`,
    `- Internal feed rows: ${internalCount}`,
    `- Audited records: ${readinessRows.length}`,
    '',
    '## Readiness Status Counts',
    '',
  ];
  Object.entries(byStatus).sort((a, b) => b[1] - a[1]).forEach(([status, count]) => lines.push(`- ${status}: ${count}`));
  lines.push('', '## Main Recommendations', '');
  lines.push('- Promote no outfitter publicly until reviewed_at and source_evidence_count fields exist.');
  lines.push('- Add explicit service_types instead of relying on inferred services.');
  lines.push('- Add unit coverage keyed to hunt codes or reviewed boundary IDs before matching becomes public-facing.');
  lines.push('- Keep internal-only records out of `outfitters-public.json` until contact, service, unit, and review fields are complete.');
  lines.push('');
  return `${lines.join('\n')}\n`;
}

async function main() {
  await fsp.mkdir(auditDir, { recursive: true });
  const { depByPath, pageReports } = await dependencyMap();
  const assets = await performanceReport(depByPath);
  const libraryRows = await publicLibraryReport();
  const outfitters = await outfitterReport();
  const largest = assets.slice().sort((a, b) => b.size_bytes - a.size_bytes).slice(0, 25);
  const performanceSummary = {
    generated_at: new Date().toISOString(),
    asset_count: assets.length,
    large_asset_count: assets.filter((row) => row.is_large === 'true').length,
    cloudflare_r2_recommended_count: assets.filter((row) => row.should_cloudflare_r2 === 'true').length,
    should_not_publish_count: assets.filter((row) => row.should_not_publish === 'true').length,
    largest_files: largest,
  };
  const librarySummary = {
    generated_at: new Date().toISOString(),
    item_count: libraryRows.length,
    visible_allowlist_count: libraryRows.filter((row) => row.source === 'public_library_allowlist').length,
    status_counts: libraryRows.reduce((acc, row) => {
      row.curation_status.split('|').filter(Boolean).forEach((status) => { acc[status] = (acc[status] || 0) + 1; });
      return acc;
    }, {}),
    rows: libraryRows,
  };
  const outfitterPayload = {
    generated_at: new Date().toISOString(),
    public_feed_rows: outfitters.publicRows.length,
    internal_feed_rows: outfitters.internalRows.length,
    readiness_status_counts: summarize(outfitters.rows, 'readiness_status'),
    risk_flag_counts: outfitters.rows.reduce((acc, row) => {
      row.risk_flags.split('|').filter(Boolean).forEach((flag) => { acc[flag] = (acc[flag] || 0) + 1; });
      return acc;
    }, {}),
    required_fields: ['outfitter_id', 'display_name', 'designation', 'status', 'species', 'units', 'services', 'contact', 'website', 'phone', 'email', 'reviewed_at', 'source_evidence_count', 'insurance_or_license_notes', 'federal_permit_units', 'service_types', 'public_profile_ready', 'missing_fields', 'risk_flags'],
    records: outfitters.rows,
  };
  const dependencyPayload = {
    generated_at: new Date().toISOString(),
    pages: pageReports,
  };

  await writeCsv('processed_data/audits/site_performance_asset_report.csv', assets, ['path', 'size_bytes', 'file_type', 'page_dependency', 'is_large', 'is_blocking_likely', 'should_lazy_load', 'should_cloudflare_r2', 'should_compress', 'should_split', 'should_not_publish', 'recommendation']);
  await writeJson('processed_data/audits/site_performance_asset_report.json', performanceSummary);
  await writeCsv('processed_data/audits/public_library_curation_report.csv', libraryRows, ['source', 'id', 'title', 'href', 'folder_id', 'type', 'year', 'size_bytes', 'visible_in_public_library', 'curation_status', 'recommendation']);
  await writeJson('processed_data/audits/public_library_curation_report.json', librarySummary);
  await writeJson('processed_data/audits/outfitter_data_readiness_report.json', outfitterPayload);
  await fsp.writeFile(path.join(auditDir, 'outfitter_data_readiness_report.md'), markdownOutfitter(outfitters.rows, outfitters.publicRows.length, outfitters.internalRows.length), 'utf8');
  await writeJson('processed_data/audits/page_runtime_dependency_report.json', dependencyPayload);

  console.log(JSON.stringify({
    asset_count: assets.length,
    large_asset_count: performanceSummary.large_asset_count,
    cloudflare_r2_recommended_count: performanceSummary.cloudflare_r2_recommended_count,
    library_items: libraryRows.length,
    visible_library_items: librarySummary.visible_allowlist_count,
    outfitter_public_rows: outfitters.publicRows.length,
    outfitter_internal_rows: outfitters.internalRows.length,
    outfitter_status_counts: outfitterPayload.readiness_status_counts,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
