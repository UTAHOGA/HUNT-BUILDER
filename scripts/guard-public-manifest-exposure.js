const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

const BLOCKED_INTERNAL_PATTERNS = [
  /\bagents\b/i,
  /\bcodex\b/i,
  /\baudit\b/i,
  /\bimplementation\b/i,
  /\binternal\b/i,
  /\bplanning\b/i,
  /\btask\b/i,
  /\.md($|[?#])/i,
  /\.txt($|[?#])/i,
];

const MANIFEST_RULES = [
  {
    file: 'public/hard-copy/data/documents.json',
    fields: ['href', 'viewer_href'],
    allowedExtensions: new Set(['pdf', 'xlsx']),
    allowedPrefixes: [
      './public/hard-copy/',
      '/public/hard-copy/',
      './hard-copy/',
      '/hard-copy/',
    ],
  },
  {
    file: 'processed_data/hard_data_exports/hard_data_manifest.web.json',
    fields: ['href', 'viewer_href'],
    allowedExtensions: new Set(['csv', 'json', 'pdf', 'xlsx']),
    allowedPrefixes: [
      './processed_data/hard_data_exports/library/',
      './public/hard-copy/',
      './hard-copy/',
    ],
  },
];

const PUBLIC_SCAN_DIRS = [
  'public',
  'processed_data/hard_data_exports',
];

function decodeSafe(value) {
  try {
    return decodeURIComponent(String(value || ''));
  } catch {
    return String(value || '');
  }
}

function isBlockedInternalToken(value) {
  const text = decodeSafe(value);
  return BLOCKED_INTERNAL_PATTERNS.some((pattern) => pattern.test(text));
}

function extensionFromPath(value) {
  const cleaned = String(value || '').trim().split('#')[0].split('?')[0];
  const match = cleaned.match(/\.([a-z0-9]+)$/i);
  return match ? String(match[1]).toLowerCase() : '';
}

function readJsonArray(relPath) {
  const file = path.join(ROOT, relPath);
  if (!fs.existsSync(file)) return [];
  const raw = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed) ? parsed : [];
}

function scanManifest(rule, violations) {
  const rows = readJsonArray(rule.file);
  rows.forEach((row, index) => {
    const title = String(row?.title || '').trim();
    const subtitle = String(row?.subtitle || '').trim();
    const combined = `${title} ${subtitle}`;
    if (isBlockedInternalToken(combined)) {
      violations.push(`${rule.file} row ${index + 1}: blocked title/subtitle token`);
    }
    for (const field of rule.fields) {
      const href = String(row?.[field] || '').trim();
      if (!href) continue;
      if (isBlockedInternalToken(href)) {
        violations.push(`${rule.file} row ${index + 1}: blocked token in ${field} -> ${href}`);
        continue;
      }
      const ext = extensionFromPath(href);
      if (!rule.allowedExtensions.has(ext)) {
        violations.push(`${rule.file} row ${index + 1}: disallowed extension .${ext || '<none>'} in ${field}`);
      }
      if (!rule.allowedPrefixes.some((prefix) => href.startsWith(prefix))) {
        violations.push(`${rule.file} row ${index + 1}: disallowed path prefix in ${field} -> ${href}`);
      }
    }
  });
}

function walkFiles(dirPath, output = []) {
  if (!fs.existsSync(dirPath)) return output;
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      walkFiles(fullPath, output);
      continue;
    }
    output.push(fullPath);
  }
  return output;
}

function scanPublicPaths(violations) {
  for (const relDir of PUBLIC_SCAN_DIRS) {
    const absDir = path.join(ROOT, relDir);
    const files = walkFiles(absDir);
    for (const file of files) {
      const rel = path.relative(ROOT, file).replace(/\\/g, '/');
      if (isBlockedInternalToken(rel)) {
        violations.push(`public path contains blocked internal token: ${rel}`);
      }
    }
  }
}

function main() {
  const violations = [];

  for (const rule of MANIFEST_RULES) {
    scanManifest(rule, violations);
  }
  scanPublicPaths(violations);

  if (violations.length) {
    console.error('Public manifest exposure guard FAILED:');
    violations.forEach((item) => console.error(`- ${item}`));
    process.exit(1);
  }

  console.log('Public manifest exposure guard PASS');
}

main();
