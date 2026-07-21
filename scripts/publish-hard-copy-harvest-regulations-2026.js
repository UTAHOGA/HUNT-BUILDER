const fs = require('fs');
const path = require('path');

const repo = process.cwd();
const manifestPath = path.join(repo, 'processed_data', 'hard_data_exports', 'hard_copy_pdf_manifest.web.json');

function readJsonAllowBom(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '');
  return JSON.parse(raw);
}

const pdfs = [
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'harvest_report', '2026-03-06-2025-preliminary-bg-harvest.pdf'),
    group: 'harvest_report',
    publicDir: path.join('source_pdfs', 'harvest_report', '2025'),
    fileName: '2025-preliminary-big-game-harvest-report.pdf',
    year: '2025',
    title: '2025 Preliminary Big Game Harvest Report',
    subtitle: 'Official Utah DWR preliminary big-game harvest report published March 6, 2026.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2026 Waterfowl.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2026'),
    fileName: '2026-waterfowl-guidebook.pdf',
    year: '2026',
    title: '2026 Waterfowl Guidebook',
    subtitle: 'Official Utah DWR waterfowl regulation guidebook.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2025_REGULATIONS__UPLAND_TURKEY.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2025-26'),
    fileName: '2025-26-upland-game-turkey-guidebook.pdf',
    year: '2025',
    title: '2025 Upland Turkey Guidebook',
    subtitle: 'Official Utah DWR upland game and turkey regulation guidebook.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2026 Bear Cougar Furbearer Guidebook.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2026'),
    fileName: '2026-bear-cougar-furbearer-guidebook.pdf',
    year: '2026',
    title: '2026 Bear Cougar Furbearer Guidebook',
    subtitle: 'Official Utah DWR bear, cougar, and furbearer regulation guidebook.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2026 Big Game Application.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2026'),
    fileName: '2026-big-game-application-guidebook.pdf',
    year: '2026',
    title: '2026 Big Game Application Guidebook',
    subtitle: 'Official Utah DWR big-game application guidebook.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2026 Fishing.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2026'),
    fileName: '2026-fishing-guidebook.pdf',
    year: '2026',
    title: '2026 Fishing Guidebook',
    subtitle: 'Official Utah DWR fishing regulation guidebook.'
  },
  {
    source: path.join(repo, 'pipeline', 'RAW', 'hunt_unit_database', '2026', 'pdf', 'regulations', '2026 Turkey.pdf'),
    group: 'regulation',
    publicDir: path.join('source_pdfs', 'regulations', '2026'),
    fileName: '2026-turkey-guidebook.pdf',
    year: '2026',
    title: '2026 Turkey Guidebook',
    subtitle: 'Official Utah DWR turkey regulation guidebook.'
  }
];

const basePublicDir = path.join(repo, 'processed_data', 'hard_data_exports');
const copied = [];
for (const item of pdfs) {
  if (!fs.existsSync(item.source)) throw new Error(`Missing source PDF: ${item.source}`);
  const outDir = path.join(basePublicDir, item.publicDir);
  fs.mkdirSync(outDir, { recursive: true });
  const dest = path.join(outDir, item.fileName);
  fs.copyFileSync(item.source, dest);
  copied.push({ title: item.title, dest, bytes: fs.statSync(dest).size });
}

const manifest = readJsonAllowBom(manifestPath);
const titles = new Set(pdfs.map((item) => item.title.toLowerCase()));
const hrefs = new Set(pdfs.map((item) => `./processed_data/hard_data_exports/${item.publicDir.replace(/\\/g, '/')}/${item.fileName}`));
const filtered = manifest.filter((entry) => {
  const title = String(entry.title || '').trim().toLowerCase();
  const href = String(entry.href || '');
  return !titles.has(title) && !hrefs.has(href);
});
const entries = pdfs.map((item) => ({
  group: item.group,
  type: 'pdf',
  year: item.year,
  title: item.title,
  subtitle: item.subtitle,
  href: `./processed_data/hard_data_exports/${item.publicDir.replace(/\\/g, '/')}/${item.fileName}`,
  source_authority: 'Utah Division of Wildlife Resources',
  source_year: item.year,
  model_year_folder: '2026',
  source_role: 'official_source',
  parent_title: null
}));
const next = [...entries, ...filtered];
const manifestChanged = JSON.stringify(manifest) !== JSON.stringify(next);
if (manifestChanged) {
  fs.writeFileSync(manifestPath, JSON.stringify(next, null, 2) + '\n');
}
console.log(JSON.stringify({
  copied,
  manifest_entries_added: entries.length,
  manifest_total: next.length,
  manifest_updated: manifestChanged,
}, null, 2));
