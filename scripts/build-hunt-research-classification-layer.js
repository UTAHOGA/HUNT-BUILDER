const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');
const zlib = require('zlib');

const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'processed_data', 'research_page');
const auditDir = path.join(root, 'processed_data', 'audits');

const paths = {
  syncMatrix: 'processed_data/audits/active_data_feed_sync_matrix.json',
  readiness: 'processed_data/audits/engine_readiness_report.json',
  management: 'processed_data/management_context/hunt_management_objective_context.json',
  elkPlan: 'elk_statewide_plan_foundational_reference_codex_expanded.md',
  deerPlanExpanded: 'mule_deer_statewide_plan_foundational_reference_codex_expanded.md',
  deerPlan: 'mule_deer_statewide_plan_foundational_reference.md',
  age: 'data_model/harvest_quality/harvest_average_age_global_merge_database.csv',
  harvest: 'processed_data/harvest_quality_features_all_years_by_hunt_code.csv',
  master: 'processed_data/hunt_master_enriched.csv',
  ladder: 'processed_data/point_ladder_view.csv',
  predictive: 'processed_data/draw_reality_engine_predictive_v2.csv',
  yearChange: 'processed_data/audits/year_to_year_hunt_change_report.csv',
  database: 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv',
};

const pathCandidates = {
  syncMatrix: [
    paths.syncMatrix,
  ],
  readiness: [
    paths.readiness,
  ],
  management: [
    paths.management,
    'processed_data/management_context/hunt_management_context.json',
  ],
  master: [
    paths.master,
    'pipeline/RAW/hunt_unit_database/2026/csv/hunt_master_canonical_2026_built.csv',
    'hunt_master_canonical_2026_built.csv',
    paths.database,
  ],
  ladder: [
    paths.ladder,
    'point_ladder_view.csv',
  ],
  predictive: [
    paths.predictive,
    'processed_data/draw_reality_engine_v2.csv',
    'draw_reality_engine_v2.csv',
    'draw_reality_engine.csv',
  ],
  harvest: [
    paths.harvest,
    'data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv',
    'data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv',
    'pipeline/RAW/hunt_unit_database/2026/csv/harvest_quality_features_by_hunt_code_2025_for_2026.csv',
  ],
  age: [
    paths.age,
    'processed_data/harvest_age_features_by_hunt_code_latest.csv',
  ],
  yearChange: [
    paths.yearChange,
  ],
  database: [
    paths.database,
  ],
};

const outputFiles = {
  outlookJson: 'processed_data/research_page/hunt_application_outlook.json',
  outlookCsv: 'processed_data/research_page/hunt_application_outlook.csv',
  tagsCsv: 'processed_data/research_page/hunt_classification_tags.csv',
  tagsJson: 'processed_data/research_page/hunt_classification_tags.json',
  sleeperCsv: 'processed_data/research_page/sleeper_hunts_report.csv',
  sleeperJson: 'processed_data/research_page/sleeper_hunts_report.json',
  newCsv: 'processed_data/research_page/new_hunts_report.csv',
  newJson: 'processed_data/research_page/new_hunts_report.json',
  demographicsJson: 'processed_data/research_page/demographic_hunt_recommendations.json',
  managementContextJson: 'processed_data/management_context/hunt_management_objective_context.json',
  auditJson: 'processed_data/audits/hunt_classification_layer_audit.json',
};

const masterColumns = [
  'hunt_code', 'boundary_id', 'hunt_name', 'species', 'sex_type', 'weapon', 'hunt_class',
  'hunt_type', 'access_type', 'residency', 'points', 'public_permits_2025',
  'public_permits_2026', 'odds_2026_projected', 'max_point_permits_2026',
  'random_permits_2026', 'success_percent', 'permits_2026_res', 'permits_2026_nr',
  'permits_2026_total', 'permit_status', 'permit_allocation_type', 'data_status',
  'draw_2026_system_type', 'draw_system_type', 'algorithm_status', 'draw_routing_reason',
  'draw_pool', 'availability_status', 'new_this_year', 'permit_allotment_2026_res',
  'permit_allotment_2026_nr', 'permit_allotment_2026_total', 'current_age_3yr_average',
  'average_harvest_age', 'average_harvest_age_review_status',
];

const ladderColumns = [
  'hunt_code', 'residency', 'points', 'guaranteed_at_2025', 'guaranteed_at_2026',
  'guaranteed_delta_2025_to_2026', 'applicants_above', 'applicants_at_level',
  'random_draw_odds_2026', 'status', 'trend', 'draw_outlook', 'permits_2026_res',
  'permits_2026_nr', 'permits_2026_total', 'max_point_permits_2026',
  'random_permits_2026', 'draw_2026_system_type', 'permit_status', 'availability_status',
  'new_this_year', 'p_max_pool_mean', 'p_random_mean', 'p_draw_mean',
  'forecast_applicants_at_level', 'forecast_applicants_above', 'is_2026_max_point_pool',
  'is_2026_random_pool', 'display_odds_pct', 'display_odds_text',
  'demand_pressure_category', 'current_age_3yr_average', 'average_harvest_age',
  'average_harvest_age_review_status', 'species', 'hunt_name', 'hunt_class',
  'draw_system_type', 'model_version', 'rule_version',
];

const predictiveColumns = [
  'hunt_code', 'hunt_name', 'species', 'sex_type', 'hunt_type', 'hunt_class', 'residency',
  'points', 'draw_pool', 'p_draw', 'p_draw_pct', 'p_draw_mean', 'p_max_pool_mean',
  'p_random_mean', 'draw_outlook', 'draw_system_type', 'algorithm_status', 'model_version',
  'rule_version', 'public_permits_2026', 'max_point_permits_2026', 'random_permits_2026',
  'applicants_above', 'applicants_at_level', 'forecast_applicants_at_level',
  'forecast_applicants_above', 'status', 'trend', 'availability_status',
  'permit_availability_type', 'p_availability', 'availability_pct',
  'guaranteed_at_2025', 'guaranteed_at_2026', 'random_draw_odds_2026', 'boundary_id',
  'current_age_3yr_average', 'average_harvest_age', 'average_harvest_age_review_status',
];

const harvestColumns = [
  'reported_hunt_year', 'model_target_year', 'hunt_code', 'species', 'sex_type',
  'hunt_name', 'hunt_type', 'weapon', 'permits', 'hunters_afield', 'harvest_total',
  'percent_success', 'average_days', 'average_age', 'source_file', 'source_page',
  'source_status', 'data_quality_flags', 'recommended_use',
];

const ageColumns = [
  'hunt_code', 'current_hunt_code', 'hunt_name', 'species', 'reported_hunt_year',
  'model_target_year', 'unit_name', 'boundary_id', 'average_harvest_age',
  'age_data_available', 'percent_5plus', 'percent_mature_or_5_plus', 'age_metric_type',
  'source_file', 'source_page', 'source_table_title', 'review_status', 'review_reason',
  'quality_score_eligible', 'trophy_age_score_eligible',
];

function rel(file) {
  return path.relative(root, file).replace(/\\/g, '/');
}

function text(value) {
  return String(value ?? '').trim();
}

function upper(value) {
  return text(value).toUpperCase();
}

function lower(value) {
  return text(value).toLowerCase();
}

function hasValue(value) {
  const raw = upper(value);
  return !!raw && !['N/A', 'NA', 'NOT AVAILABLE', 'NULL', 'NONE', 'UNDEFINED'].includes(raw);
}

function num(value) {
  const raw = text(value);
  if (!raw || !/[0-9]/.test(raw)) return null;
  const parsed = Number(raw.replace(/[^0-9.-]/g, ''));
  return Number.isFinite(parsed) ? parsed : null;
}

function firstText(...values) {
  for (const value of values) {
    if (hasValue(value)) return text(value);
  }
  return '';
}

function firstNum(...values) {
  for (const value of values) {
    const n = num(value);
    if (n != null) return n;
  }
  return null;
}

function resolveRuntimePath(key) {
  const candidates = pathCandidates[key] || [];
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(path.join(root, candidate))) return candidate;
  }
  return candidates[0] || '';
}

function resolveRuntimePaths() {
  return {
    syncMatrix: resolveRuntimePath('syncMatrix'),
    readiness: resolveRuntimePath('readiness'),
    management: resolveRuntimePath('management'),
    master: resolveRuntimePath('master'),
    ladder: resolveRuntimePath('ladder'),
    predictive: resolveRuntimePath('predictive'),
    harvest: resolveRuntimePath('harvest'),
    age: resolveRuntimePath('age'),
    yearChange: resolveRuntimePath('yearChange'),
    database: resolveRuntimePath('database'),
    elkPlan: paths.elkPlan,
    deerPlanExpanded: paths.deerPlanExpanded,
    deerPlan: paths.deerPlan,
  };
}

function pct(value) {
  const n = num(value);
  if (n == null) return null;
  return n <= 1 && n >= 0 ? n * 100 : n;
}

function yes(value) {
  return ['TRUE', 'YES', 'Y', '1'].includes(upper(value));
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

function parseCsvLine(line) {
  const cells = [];
  let value = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const next = line[i + 1];
    if (ch === '"') {
      if (quoted && next === '"') {
        value += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      cells.push(value);
      value = '';
    } else {
      value += ch;
    }
  }
  cells.push(value);
  return cells;
}

async function isGzipFile(file) {
  const handle = await fsp.open(file, 'r');
  try {
    const buffer = Buffer.alloc(2);
    const result = await handle.read(buffer, 0, 2, 0);
    return result.bytesRead === 2 && buffer[0] === 0x1f && buffer[1] === 0x8b;
  } finally {
    await handle.close();
  }
}

async function readCsv(relPath, wantedColumns = null) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return [];
  const input = await isGzipFile(file)
    ? fs.createReadStream(file).pipe(zlib.createGunzip())
    : fs.createReadStream(file, { encoding: 'utf8' });
  const rows = [];
  const wanted = wantedColumns ? new Set(wantedColumns.map((col) => col.toLowerCase())) : null;
  let headers = null;
  let selected = [];
  const rl = readline.createInterface({ input, crlfDelay: Infinity });
  for await (const line of rl) {
    if (!headers) {
      if (!text(line)) continue;
      headers = parseCsvLine(line).map(text);
      selected = headers
        .map((header, index) => ({ header, index }))
        .filter(({ header }) => !wanted || wanted.has(header.toLowerCase()));
    } else if (text(line)) {
      const cells = parseCsvLine(line);
      rows.push(Object.fromEntries(selected.map(({ header, index }) => [header, cells[index] ?? ''])));
    }
  }
  return rows;
}

async function readJson(relPath) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return [];
  const parsed = JSON.parse(await fsp.readFile(file, 'utf8'));
  return Array.isArray(parsed) ? parsed : Array.isArray(parsed.rows) ? parsed.rows : Array.isArray(parsed.data) ? parsed.data : parsed;
}

async function sha256(relPath) {
  const file = path.join(root, relPath);
  if (!fs.existsSync(file)) return '';
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    fs.createReadStream(file).on('data', (chunk) => hash.update(chunk)).on('error', reject).on('end', () => resolve(hash.digest('hex')));
  });
}

function code(row) {
  return upper(row.hunt_code || row.current_hunt_code);
}

function keyFor(huntCode, residency) {
  return `${upper(huntCode)}|${normalizeResidency(residency)}`;
}

function normalizeResidency(value) {
  const raw = upper(value);
  if (raw.startsWith('NON')) return 'Nonresident';
  if (raw.startsWith('RES')) return 'Resident';
  return text(value) || 'All';
}

function normalizeUnitKey(value) {
  return upper(value)
    .replace(/\b(UNIT|HUNT|AREA|MOUNTAINS|MOUNTAIN|MTNS|LE|LIMITED ENTRY|GENERAL SEASON|ARCHERY|MUZZLELOADER|ANY WEAPON|ANY LEGAL WEAPON|RIFLE|BUCK|BULL|COW|DOE|PRIVATE LAND ONLY|LANDOWNER ASSOCIATION|CWMU|PREMIUM|PRIVATE)\b/g, ' ')
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

function unitSpeciesKey(unitName, species) {
  const unit = normalizeUnitKey(unitName);
  const sp = upper(species);
  return unit && sp ? `${unit}|${sp}` : '';
}

function chooseText(target, field, value) {
  if (!hasValue(target[field]) && hasValue(value)) target[field] = text(value);
}

function chooseNum(target, field, value) {
  const n = num(value);
  if (n != null && target[field] == null) target[field] = n;
}

function addTag(tagRows, row, tag, category, reason) {
  if (!tag) return;
  const unique = `${row.hunt_code}|${row.residency}|${tag}`;
  if (row._tagSet.has(unique)) return;
  row._tagSet.add(unique);
  row.tags.push(tag);
  tagRows.push({
    hunt_code: row.hunt_code,
    hunt_name: row.hunt_name,
    species: row.species,
    residency: row.residency,
    tag,
    tag_category: category,
    reason,
    data_confidence: row.data_confidence,
  });
}

function median(values) {
  const nums = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!nums.length) return null;
  const mid = Math.floor(nums.length / 2);
  return nums.length % 2 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
}

function round(value, digits = 1) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : '';
}

function peerKey(row) {
  return `${row.species}|${row.hunt_class || row.hunt_type || 'unknown'}`;
}

function speciesIncludes(row, term) {
  return lower(row.species).includes(term);
}

function classText(row) {
  return lower([row.hunt_name, row.hunt_class, row.hunt_type, row.weapon, row.sex_type].join(' '));
}

function famousOrPremiumName(row) {
  return /henry|paunsaugunt|antelope island|book cliffs|boulder|kaiparowits|premium|once-in-a-lifetime|sportsman|statewide permit/.test(classText(row));
}

function buildSourceBadges(row) {
  const badges = ['Official DWR Source'];
  if (row.modeled_draw_probability !== '') badges.push('U.O.G.A. Modeled Output');
  if (row.management_objective_type) badges.push('Management Plan Context');
  if (row.data_confidence === 'LIMITED') badges.push('Review / Limited Data');
  if (row.tags.includes('STATUS_OR_AVAILABILITY_ONLY')) badges.push('Status / Availability Only');
  return badges.join('|');
}

function managementStatus(row, mgmt) {
  if (!mgmt) return { status: '', observed: null, reason: '' };
  const min = num(mgmt.management_objective_min);
  const max = num(mgmt.management_objective_max);
  const speciesName = lower(row.species || mgmt.species);
  if (speciesName.includes('elk')) {
    const observed = num(row.average_harvest_age || row.current_age_3yr_average);
    if (observed == null || observed <= 0 || min == null || max == null) {
      return { status: 'OBJECTIVE_KNOWN_NO_OBSERVED_DATA', observed: null, reason: 'Elk age objective exists, but verified observed average age is missing.' };
    }
    if (observed > max) return { status: 'QUALITY_ABOVE_OBJECTIVE', observed, reason: `Observed age ${round(observed)} is above objective range ${min}-${max}.` };
    if (observed >= min && observed <= max) return { status: 'QUALITY_MEETING_OBJECTIVE', observed, reason: `Observed age ${round(observed)} is within objective range ${min}-${max}.` };
    return { status: 'QUALITY_BELOW_OBJECTIVE', observed, reason: `Observed age ${round(observed)} is below objective range ${min}-${max}.` };
  }
  if (speciesName.includes('deer')) {
    const threshold = num(mgmt.age_structure_threshold_min);
    const pct5 = num(row.percent_5plus);
    if (threshold != null && pct5 != null && pct5 > 0) {
      if (pct5 >= threshold) return { status: 'QUALITY_MEETING_OBJECTIVE', observed: pct5, reason: `Verified percent age 5+ ${round(pct5)}% meets threshold ${threshold}%.` };
      return { status: 'QUALITY_BELOW_OBJECTIVE', observed: pct5, reason: `Verified percent age 5+ ${round(pct5)}% is below threshold ${threshold}%.` };
    }
    return { status: 'OBJECTIVE_KNOWN_NO_OBSERVED_DATA', observed: null, reason: 'Mule deer objective exists, but verified buck:doe or percent age 5+ data is missing.' };
  }
  return { status: 'OBJECTIVE_KNOWN_NO_OBSERVED_DATA', observed: null, reason: 'Objective exists, but comparison rule is not available for this species.' };
}

function managementDirectionLabel(status) {
  const s = upper(status);
  if (s === 'QUALITY_ABOVE_OBJECTIVE') return 'Above Objective';
  if (s === 'QUALITY_MEETING_OBJECTIVE') return 'Meeting Objective';
  if (s === 'QUALITY_BELOW_OBJECTIVE') return 'Below Objective';
  if (s === 'OBJECTIVE_KNOWN_NO_OBSERVED_DATA') return 'Objective Known / Observed Evidence Limited';
  return 'Objective Context Loaded';
}

function buildSyntheticManagementRows(databaseRows) {
  const byCode = new Map();
  databaseRows.forEach((row) => {
    const c = upper(row.hunt_code);
    if (!c || byCode.has(c)) return;
    const species = lower(row.species);
    const huntType = lower(row.hunt_type);
    const huntClass = lower(row.hunt_class);
    let synthetic = null;

    if (species.includes('elk')) {
      if (huntType.includes('limited entry') || huntClass.includes('limited entry') || huntClass.includes('premium')) {
        synthetic = {
          hunt_code: c,
          species: row.species,
          management_objective_type: 'Elk LE Age Objective',
          management_objective_min: 5.5,
          management_objective_max: 7.0,
          objective_unit: 'years avg harvested bull age',
          objective_status_rule: 'Compare observed average harvested age against statewide LE objective band.',
          notes: 'Context from statewide elk plan; does not change permits or draw odds.',
        };
      }
    } else if (species.includes('deer')) {
      if (huntType.includes('premium limited entry') || huntClass.includes('premium')) {
        synthetic = {
          hunt_code: c,
          species: row.species,
          management_objective_type: 'Mule Deer Premium LE Expectation',
          management_objective_min: 40,
          management_objective_max: 45,
          objective_unit: 'bucks per 100 does objective band',
          age_structure_threshold_min: 40,
          objective_status_rule: 'Use verified percent age 5+ as observed evidence when available.',
          notes: 'Premium LE quality context from statewide mule deer plan; not a direct odds input.',
        };
      } else if (huntType.includes('limited entry')) {
        synthetic = {
          hunt_code: c,
          species: row.species,
          management_objective_type: 'Mule Deer LE Objective',
          management_objective_min: 25,
          management_objective_max: 30,
          objective_unit: 'bucks per 100 does objective band',
          objective_status_rule: 'Observed buck:doe evidence is external; keep as context-only benchmark.',
          notes: 'LE management objective context from statewide mule deer plan.',
        };
      } else if (huntType.includes('general')) {
        synthetic = {
          hunt_code: c,
          species: row.species,
          management_objective_type: 'Mule Deer General Objective',
          management_objective_min: 15,
          management_objective_max: 20,
          objective_unit: 'bucks per 100 does objective band',
          objective_status_rule: 'Use as management context only unless observed buck:doe evidence is loaded.',
          notes: 'General-season objective context from statewide mule deer plan.',
        };
      }
    }

    if (synthetic) byCode.set(c, synthetic);
  });
  return [...byCode.values()];
}

function permitDirectionWatch(row, yearFlag) {
  if (yearFlag?.permit_change_pct != null) {
    const pct = Number(yearFlag.permit_change_pct);
    if (Math.abs(pct) > 20) {
      return `Permit-change flag exceeds 20% (${round(pct)}%). Management review context.`;
    }
    return `Permit-change signal ${round(pct)}% (within 20% auto-change context).`;
  }
  const creep = num(row.point_creep_1yr);
  if (creep != null && creep >= 1) {
    return 'Point-creep increase observed; watch permit direction if RAC change exceeds 20%.';
  }
  return 'No permit-direction flag loaded from year-change audit.';
}

function recommendedAction(row) {
  const t = new Set(row.tags);
  if (t.has('DATA_LIMITED_DO_NOT_OVERSELL') || t.has('INSUFFICIENT_DRAW_DATA')) return 'Objective or opportunity data is incomplete. Treat this as a limited-confidence research lead.';
  if (t.has('BEGINNER_ANTLERLESS')) return 'Beginner-friendly antlerless/freezer opportunity.';
  if (t.has('SLEEPER_CANDIDATE')) return 'Potential overlooked opportunity. Review the details before applying.';
  if (t.has('POINT_SAVER')) return 'High-quality hunt, but consider saving points unless it fits your long-term plan.';
  if (t.has('HARD_DRIVER')) return 'Hard-driver hunt: quality potential, physical effort or patience likely required.';
  if (row.decision_label === 'STRONG APPLY') return 'Strong application candidate for current point context.';
  if (row.decision_label === 'WITHIN REACH') return 'Good application candidate if the hunt matches your goals.';
  if (row.decision_label === 'QUALITY LONG SHOT') return 'High-quality hunt, but expect long odds.';
  if (row.decision_label === 'STATUS / AVAILABILITY ONLY') return 'Status/availability opportunity. Confirm current rules and availability before planning.';
  return 'Longer-odds hunt. Compare against similar opportunities before spending points.';
}

function confidence(row) {
  const hasDraw = row.modeled_draw_probability !== '' || hasValue(row.decision_label);
  const hasHarvest = row.harvest_success_pct !== '' || row.average_days_hunted !== '';
  const hasAge = row.average_harvest_age !== '' || row.percent_5plus !== '';
  if (hasDraw && hasHarvest && hasAge) return 'HIGH';
  if (hasDraw) return 'MEDIUM';
  if (hasValue(row.hunt_name)) return 'LIMITED';
  return 'BLOCKED';
}

async function build() {
  const resolved = resolveRuntimePaths();
  const protectedBefore = {
    database: await sha256(resolved.database),
    predictive: await sha256(resolved.predictive),
    ladder: await sha256(resolved.ladder),
  };

  const syncMatrix = await readJson(resolved.syncMatrix);
  const readiness = await readJson(resolved.readiness);
  const managementRows = await readJson(resolved.management);
  const hasElkPlan = fs.existsSync(path.join(root, resolved.elkPlan));
  const hasDeerPlan = fs.existsSync(path.join(root, resolved.deerPlanExpanded)) || fs.existsSync(path.join(root, resolved.deerPlan));

  const [master, ladder, predictive, harvest, age, yearChanges, database] = await Promise.all([
    readCsv(resolved.master, masterColumns),
    readCsv(resolved.ladder, ladderColumns),
    readCsv(resolved.predictive, predictiveColumns),
    readCsv(resolved.harvest, harvestColumns),
    readCsv(resolved.age, ageColumns),
    readCsv(resolved.yearChange),
    readCsv(resolved.database),
  ]);

  const syntheticManagementRows = managementRows.length ? [] : buildSyntheticManagementRows(database);
  const managementRowsEffective = managementRows.length ? managementRows : syntheticManagementRows;
  const managementByCode = new Map(managementRowsEffective.map((row) => [upper(row.hunt_code), row]));
  const masterByCode = new Map();
  master.forEach((row) => {
    const c = code(row);
    if (c && !masterByCode.has(c)) masterByCode.set(c, row);
  });
  const databaseByCode = new Map();
  database.forEach((row) => {
    const c = code(row);
    if (c && !databaseByCode.has(c)) databaseByCode.set(c, row);
  });
  const yearFlags = new Map();
  yearChanges.forEach((row) => {
    const c = upper(row.hunt_code);
    if (!c) return;
    const entry = yearFlags.get(c) || { flags: new Set(), permit_change_pct: null };
    text(row.change_flags).split('|').filter(Boolean).forEach((flag) => entry.flags.add(flag));
    const pctChange = num(row.permit_change_pct_2025_to_2026);
    if (pctChange != null) entry.permit_change_pct = pctChange;
    yearFlags.set(c, entry);
  });

  const masterSeedRows = ladder.length
    ? ladder.map((row) => ({
      hunt_code: row.hunt_code,
      boundary_id: row.boundary_id,
      hunt_name: row.hunt_name,
      species: row.species,
      sex_type: row.sex_type,
      weapon: row.weapon,
      hunt_class: row.hunt_class,
      hunt_type: row.hunt_type,
      residency: row.residency,
      draw_pool: row.draw_pool,
      draw_2026_system_type: row.draw_2026_system_type,
      draw_system_type: row.draw_system_type,
      availability_status: row.availability_status,
      model_version: row.model_version,
      rule_version: row.rule_version,
      permits_2026_res: row.permits_2026_res || row.permit_allotment_2026_res,
      permits_2026_nr: row.permits_2026_nr || row.permit_allotment_2026_nr,
      permits_2026_total: row.permits_2026_total || row.permit_allotment_2026_total || row.public_permits_2026,
      current_age_3yr_average: row.current_age_3yr_average,
      average_harvest_age: row.average_harvest_age,
      new_this_year: row.new_this_year,
    }))
    : master;

  const base = new Map();
  masterSeedRows.forEach((row) => {
    const c = code(row);
    if (!c) return;
    const masterRow = masterByCode.get(c) || {};
    const dbRow = databaseByCode.get(c) || {};
    const key = keyFor(c, row.residency);
    const item = base.get(key) || {
      hunt_code: c,
      residency: normalizeResidency(row.residency),
      tags: [],
      _tagSet: new Set(),
      _probabilities: [],
      _applicantsAtLevel: [],
      _applicantsAbove: [],
      _permitTotals: [],
      _pointRows: 0,
      _maxPointPermits: [],
      _randomPermits: [],
    };
    chooseText(item, 'hunt_name', firstText(row.hunt_name, masterRow.hunt_name, dbRow.hunt_name));
    chooseText(item, 'species', firstText(row.species, masterRow.species, dbRow.species));
    chooseText(item, 'sex_type', firstText(row.sex_type, masterRow.sex_type, dbRow.sex_type));
    chooseText(item, 'weapon', firstText(row.weapon, masterRow.weapon, dbRow.weapon));
    chooseText(item, 'hunt_class', firstText(row.hunt_class, masterRow.hunt_class, dbRow.hunt_class));
    chooseText(item, 'hunt_type', firstText(row.hunt_type, masterRow.hunt_type, dbRow.hunt_type));
    chooseText(item, 'access_type', firstText(row.access_type, masterRow.access_type, dbRow.access_type));
    chooseText(item, 'unit_name', firstText(row.unit_name, row.hunt_name, masterRow.unit_name, masterRow.hunt_name, dbRow.hunt_name));
    chooseText(item, 'boundary_id', firstText(row.boundary_id, masterRow.boundary_id, dbRow.boundary_id));
    chooseText(item, 'draw_family', firstText(row.draw_2026_system_type, row.draw_system_type, masterRow.draw_2026_system_type, masterRow.draw_system_type, dbRow.draw_2026_system_type, dbRow.draw_system_type, row.draw_pool));
    chooseText(item, 'draw_pool', firstText(row.draw_pool, masterRow.draw_pool));
    chooseText(item, 'availability_status', firstText(row.availability_status, row.permit_status, row.data_status, masterRow.availability_status, masterRow.permit_status, masterRow.data_status));
    chooseText(item, 'model_version', firstText(row.model_version, masterRow.model_version));
    chooseText(item, 'rule_version', firstText(row.rule_version, masterRow.rule_version));
    chooseNum(item, 'permits_2026_res', firstNum(row.permits_2026_res, row.permit_allotment_2026_res, masterRow.permits_2026_res, masterRow.permit_allotment_2026_res, dbRow.permit_allotment_2026_res, dbRow.permits_2026_res));
    chooseNum(item, 'permits_2026_nr', firstNum(row.permits_2026_nr, row.permit_allotment_2026_nr, masterRow.permits_2026_nr, masterRow.permit_allotment_2026_nr, dbRow.permit_allotment_2026_nr, dbRow.permits_2026_nr));
    chooseNum(item, 'permits_2026_total', firstNum(row.permits_2026_total, row.permit_allotment_2026_total, row.public_permits_2026, masterRow.permits_2026_total, masterRow.permit_allotment_2026_total, masterRow.public_permits_2026, dbRow.permit_allotment_2026_total, dbRow.permits_2026_total));
    const currentAge = firstNum(row.current_age_3yr_average, masterRow.current_age_3yr_average, dbRow.current_age_3yr_average);
    if (currentAge != null && currentAge > 0 && item.current_age_3yr_average == null) item.current_age_3yr_average = currentAge;
    const ageValue = firstNum(row.average_harvest_age, masterRow.average_harvest_age, dbRow.average_harvest_age);
    if (ageValue != null && ageValue > 0 && item.average_harvest_age == null) {
      item.average_harvest_age = ageValue;
      item._ageSource = resolved.master;
    }
    if (yes(row.new_this_year) || yes(masterRow.new_this_year) || yes(dbRow.new_this_year)) item.new_this_year = true;
    base.set(key, item);
  });

  function withBase(row) {
    const c = code(row);
    if (!c) return null;
    const key = keyFor(c, row.residency);
    const item = base.get(key);
    if (!item) return null;
    return item;
  }

  ladder.forEach((row) => {
    const item = withBase(row);
    if (!item) return;
    item._pointRows += 1;
    chooseText(item, 'draw_family', row.draw_2026_system_type || row.draw_system_type);
    chooseText(item, 'model_version', row.model_version);
    chooseText(item, 'rule_version', row.rule_version);
    const p = pct(row.p_draw_mean || row.display_odds_pct || row.random_draw_odds_2026);
    if (p != null) item._probabilities.push(p);
    const line = num(row.guaranteed_at_2026);
    if (line != null && (item.guaranteed_line_points == null || line < item.guaranteed_line_points)) item.guaranteed_line_points = line;
    const creep = num(row.guaranteed_delta_2025_to_2026);
    if (creep != null) item.point_creep_1yr = item.point_creep_1yr == null ? creep : Math.max(item.point_creep_1yr, creep);
    const at = num(row.forecast_applicants_at_level || row.applicants_at_level);
    if (at != null) item._applicantsAtLevel.push(at);
    const above = num(row.forecast_applicants_above || row.applicants_above);
    if (above != null) item._applicantsAbove.push(above);
    const maxPermits = num(row.max_point_permits_2026);
    if (maxPermits != null) item._maxPointPermits.push(maxPermits);
    const randomPermits = num(row.random_permits_2026);
    if (randomPermits != null) item._randomPermits.push(randomPermits);
    const totalPermits = num(row.permits_2026_total);
    if (totalPermits != null) item._permitTotals.push(totalPermits);
    if (yes(row.is_2026_random_pool)) item.has_random_pool = true;
    if (yes(row.is_2026_max_point_pool)) item.has_max_pool = true;
    if (upper(row.demand_pressure_category).includes('HIGH')) item.high_pressure = true;
  });

  predictive.forEach((row) => {
    const item = withBase(row);
    if (!item) return;
    chooseText(item, 'draw_family', row.draw_system_type || row.draw_pool);
    chooseText(item, 'model_version', row.model_version);
    chooseText(item, 'rule_version', row.rule_version);
    const p = pct(row.p_draw_mean || row.p_draw_pct || row.p_draw || row.p_availability || row.availability_pct);
    if (p != null) item._probabilities.push(p);
    const line = num(row.guaranteed_at_2026);
    if (line != null && (item.guaranteed_line_points == null || line < item.guaranteed_line_points)) item.guaranteed_line_points = line;
    const at = num(row.forecast_applicants_at_level || row.applicants_at_level);
    if (at != null) item._applicantsAtLevel.push(at);
    const above = num(row.forecast_applicants_above || row.applicants_above);
    if (above != null) item._applicantsAbove.push(above);
  });

  const harvestByCode = new Map();
  const unitSpeciesAgeCandidates = new Map();
  harvest.forEach((row) => {
    const c = code(row);
    const year = num(row.reported_hunt_year) || 0;
    const harvestAverageAge = num(row.average_age || row.average_harvest_age);
    if (c) {
      const existing = harvestByCode.get(c);
      if (!existing || year >= existing.year) {
        harvestByCode.set(c, {
          year,
          harvest_success_pct: pct(row.percent_success),
          average_days_hunted: num(row.average_days),
          harvest_average_age: harvestAverageAge,
          source_file: text(row.source_file),
          source_page: text(row.source_page),
        });
      }
    }
    const key = unitSpeciesKey(row.hunt_name || row.unit_name, row.species);
    if (key && harvestAverageAge != null && harvestAverageAge > 0) {
      const prior = unitSpeciesAgeCandidates.get(key);
      const payload = {
        year,
        age: harvestAverageAge,
        source_file: text(row.source_file),
        source_page: text(row.source_page),
      };
      if (!prior || year > prior.year) {
        unitSpeciesAgeCandidates.set(key, { year, rows: [payload] });
      } else if (year === prior.year) {
        prior.rows.push(payload);
      }
    }
  });

  const unitSpeciesAgeFallback = new Map();
  unitSpeciesAgeCandidates.forEach((entry, key) => {
    if (!entry?.rows?.length) return;
    const ages = [...new Set(entry.rows.map((row) => round(row.age, 3)))];
    const minAge = Math.min(...ages);
    const maxAge = Math.max(...ages);
    if (maxAge - minAge > 0.2) return;
    unitSpeciesAgeFallback.set(key, {
      age: round(median(ages)),
      source_file: entry.rows[0].source_file,
      source_page: entry.rows[0].source_page,
      reported_hunt_year: entry.year,
      source_scope: 'unit_level_repeated_to_hunt_code',
    });
  });

  const ageByCode = new Map();
  age.forEach((row) => {
    const c = code(row);
    if (!c) return;
    const year = num(row.reported_hunt_year) || 0;
    const existing = ageByCode.get(c);
    const avgAge = num(row.average_harvest_age);
    const percent5 = num(row.percent_5plus || row.percent_mature_or_5_plus);
    if (!existing || year >= existing.year) {
      ageByCode.set(c, {
        year,
        average_harvest_age: avgAge != null && avgAge > 0 ? avgAge : null,
        percent_5plus: percent5 != null && percent5 > 0 ? percent5 : null,
        source_file: text(row.source_file),
        source_page: text(row.source_page),
        source_table_title: text(row.source_table_title),
        review_status: text(row.review_status),
      });
    }
  });

  const rows = [...base.values()].sort((a, b) => `${a.hunt_code}|${a.residency}`.localeCompare(`${b.hunt_code}|${b.residency}`));
  rows.forEach((row) => {
    const h = harvestByCode.get(row.hunt_code) || {};
    if (h.harvest_success_pct != null) row.harvest_success_pct = round(h.harvest_success_pct);
    if (h.average_days_hunted != null) row.average_days_hunted = round(h.average_days_hunted);
    if ((row.average_harvest_age == null || row.average_harvest_age === '') && h.harvest_average_age != null && h.harvest_average_age > 0) {
      row.average_harvest_age = round(h.harvest_average_age);
      row._ageSource = resolved.harvest;
    }
    if (hasValue(h.source_file)) row.harvest_source_file = h.source_file;
    if (hasValue(h.source_page)) row.harvest_source_page = h.source_page;
    const a = ageByCode.get(row.hunt_code) || {};
    if (a.average_harvest_age != null) {
      row.average_harvest_age = round(a.average_harvest_age);
      row._ageSource = resolved.age;
    }
    if ((row.average_harvest_age == null || row.average_harvest_age === '')) {
      const unitKey = unitSpeciesKey(row.unit_name || row.hunt_name, row.species);
      const fallback = unitSpeciesAgeFallback.get(unitKey);
      if (fallback && num(fallback.age) != null && num(fallback.age) > 0) {
        row.average_harvest_age = round(fallback.age);
        row._ageSource = `${resolved.harvest}:unit_species_fallback`;
        if (!hasValue(row.age_source_file) && hasValue(fallback.source_file)) row.age_source_file = fallback.source_file;
        if (!hasValue(row.age_source_page) && hasValue(fallback.source_page)) row.age_source_page = fallback.source_page;
        if (!hasValue(row.age_review_status)) row.age_review_status = 'REVIEW_UNIT_LEVEL_REPEATED';
      }
    }
    if (a.percent_5plus != null) row.percent_5plus = round(a.percent_5plus);
    if (hasValue(a.source_file)) row.age_source_file = a.source_file;
    if (hasValue(a.source_page)) row.age_source_page = a.source_page;
    if (hasValue(a.source_table_title)) row.age_source_table_title = a.source_table_title;
    if (hasValue(a.review_status)) row.age_review_status = a.review_status;
    row.average_harvest_age = num(row.average_harvest_age) > 0 ? round(num(row.average_harvest_age)) : '';
    row.current_age_3yr_average = num(row.current_age_3yr_average) > 0 ? round(num(row.current_age_3yr_average)) : '';
    row.percent_5plus = num(row.percent_5plus) > 0 ? round(num(row.percent_5plus)) : '';
    row.modeled_draw_probability = row._probabilities.length ? round(median(row._probabilities)) : '';
    row.current_points_context_available = row._pointRows > 0;
    row.guaranteed_line_points = row.guaranteed_line_points ?? '';
    row.point_creep_1yr = row.point_creep_1yr ?? '';
    row.permits_2026_total = row.permits_2026_total ?? median(row._permitTotals) ?? '';
    row.permits_2026_res = row.permits_2026_res ?? '';
    row.permits_2026_nr = row.permits_2026_nr ?? '';
    row.management_objective_type = '';
    row.management_objective_range = '';
    row.management_objective_status = '';
    row.sleeper_score = 0;
    row.sleeper_reasons = '';
    row.data_confidence = 'LIMITED';
  });

  const peerStats = new Map();
  rows.forEach((row) => {
    const key = peerKey(row);
    const stat = peerStats.get(key) || { odds: [], success: [], permits: [], creep: [] };
    if (row.modeled_draw_probability !== '') stat.odds.push(Number(row.modeled_draw_probability));
    if (row.harvest_success_pct !== '') stat.success.push(Number(row.harvest_success_pct));
    if (row.permits_2026_total !== '') stat.permits.push(Number(row.permits_2026_total));
    if (row.point_creep_1yr !== '') stat.creep.push(Number(row.point_creep_1yr));
    peerStats.set(key, stat);
  });
  for (const stat of peerStats.values()) {
    stat.oddsMedian = median(stat.odds);
    stat.successMedian = median(stat.success);
    stat.permitMedian = median(stat.permits);
    stat.creepMedian = median(stat.creep);
  }

  const tagRows = [];
  const sleeperRows = [];
  const newRows = [];

  rows.forEach((row) => {
    const p = row.modeled_draw_probability === '' ? null : Number(row.modeled_draw_probability);
    const success = row.harvest_success_pct === '' ? null : Number(row.harvest_success_pct);
    const permits = row.permits_2026_total === '' ? null : Number(row.permits_2026_total);
    const creep = row.point_creep_1yr === '' ? null : Number(row.point_creep_1yr);
    const maxPermits = median(row._maxPointPermits) || 0;
    const randomPermits = median(row._randomPermits) || 0;
    const textBlob = classText(row);
    const y = yearFlags.get(row.hunt_code);

    row.data_confidence = confidence(row);
    if (/status|availability|harvest objective|over-the-counter|general season|no_quota|statewide permit|sportsman/.test(textBlob + ' ' + lower(row.availability_status || row.draw_family))) {
      addTag(tagRows, row, 'STATUS_OR_AVAILABILITY_ONLY', 'APPLICATION_ODDS', 'Hunt is status/availability or special-permit oriented rather than a normal point-probability row.');
    }
    if (p == null) addTag(tagRows, row, 'INSUFFICIENT_DRAW_DATA', 'APPLICATION_ODDS', 'No modeled draw probability was available in the active runtime feeds.');
    else if (p >= 60) addTag(tagRows, row, 'WITHIN_REACH', 'APPLICATION_ODDS', `Modeled median draw probability is ${round(p)}%.`);
    else addTag(tagRows, row, 'LONG_SHOT', 'APPLICATION_ODDS', `Modeled median draw probability is ${round(p)}%.`);
    if (creep != null && creep >= 1) addTag(tagRows, row, 'POINT_CREEP_WARNING', 'APPLICATION_ODDS', `Guaranteed line moved by ${round(creep)} point(s).`);
    if (maxPermits > 0 && row.guaranteed_line_points !== '' && Number(row.guaranteed_line_points) >= 8) addTag(tagRows, row, 'MAX_POINT_HUNT', 'APPLICATION_ODDS', 'Hunt has a meaningful max-point draw line.');
    if (randomPermits > 0 && maxPermits <= 0) addTag(tagRows, row, 'RANDOM_POOL_ONLY', 'APPLICATION_ODDS', 'Available modeled permits are random-pool/status oriented.');

    const mgmt = managementByCode.get(row.hunt_code);
    if (mgmt) {
      row.management_objective_type = text(mgmt.management_objective_type);
      const min = text(mgmt.management_objective_min);
      const max = text(mgmt.management_objective_max);
      row.management_objective_range = min || max ? `${min}${max ? `-${max}` : ''} ${text(mgmt.objective_unit)}`.trim() : text(mgmt.objective_unit);
      const status = managementStatus(row, mgmt);
      row.management_objective_status = status.status;
      row.management_objective_note = status.reason;
      row.management_direction = managementDirectionLabel(status.status);
      addTag(tagRows, row, status.status, 'QUALITY_OBJECTIVE', status.reason);
    }
    row.permit_direction_watch = permitDirectionWatch(row, y);

    if (success != null && success >= 50) addTag(tagRows, row, 'HIGH_HARVEST_SUCCESS', 'QUALITY_OBJECTIVE', `Harvest success ${round(success)}% is strong.`);
    if (success != null && success > 0 && success < 20) addTag(tagRows, row, 'LOW_HARVEST_SUCCESS', 'QUALITY_OBJECTIVE', `Harvest success ${round(success)}% is low.`);
    if (row.average_harvest_age !== '' || row.current_age_3yr_average !== '' || row.percent_5plus !== '') addTag(tagRows, row, 'VERIFIED_AGE_DATA', 'QUALITY_OBJECTIVE', 'Verified age or age-structure data is present.');
    else addTag(tagRows, row, 'NO_VERIFIED_AGE_DATA', 'QUALITY_OBJECTIVE', 'No verified age or age-structure metric is available for this hunt code.');

    const antlerless = /antlerless|cow|doe|ewe/.test(textBlob);
    const youth = /youth/.test(textBlob);
    const oil = /once-in-a-lifetime|bighorn|sheep|mountain goat|bison/.test(textBlob);
    const trophy = /buck|bull|male|limited entry|premium|once-in-a-lifetime|cwmu/.test(textBlob);
    if (youth) addTag(tagRows, row, 'YOUTH_OPPORTUNITY', 'HUNTER_PERSONA', 'Youth opportunity wording appears in the hunt metadata.');
    if (antlerless && (permits == null || permits >= 20 || p == null || p >= 25)) addTag(tagRows, row, 'BEGINNER_ANTLERLESS', 'HUNTER_PERSONA', 'Antlerless/freezer-style opportunity with usable permit or odds context.');
    if (antlerless || (success != null && success >= 50)) addTag(tagRows, row, 'FREEZER_FILLER', 'HUNTER_PERSONA', 'Meat-opportunity signal from antlerless classification or high harvest success.');
    if (!oil && success != null && success >= 45 && /any legal weapon|general season|private lands/.test(textBlob)) addTag(tagRows, row, 'ELDER_FRIENDLY', 'HUNTER_PERSONA', 'Higher-success and simpler-weapon/access signal; terrain still needs local review.');
    if (oil || /mtn|mountain|backcountry|wilderness|restricted|hams/.test(textBlob)) addTag(tagRows, row, 'HARD_DRIVER', 'HUNTER_PERSONA', 'Likely harder or more specialized hunt class based on species/class/weapon text.');
    if (trophy || row.management_objective_status === 'QUALITY_ABOVE_OBJECTIVE') addTag(tagRows, row, 'TROPHY_DREAMER', 'HUNTER_PERSONA', 'Trophy/quality-oriented class or objective context.');
    if ((p != null && p < 20 && trophy) || row.tags.includes('MAX_POINT_HUNT')) addTag(tagRows, row, 'POINT_SAVER', 'HUNTER_PERSONA', 'High-demand quality hunt where saving points may be rational.');
    if (permits != null && permits >= 50 && !oil) addTag(tagRows, row, 'GROUP_FRIENDLY', 'HUNTER_PERSONA', 'Higher permit count makes group planning more plausible.');
    if (/multi|extended|late|nov|dec|jan|dedicated/.test(textBlob)) addTag(tagRows, row, 'EXTEND_THE_SEASON', 'HUNTER_PERSONA', 'Season/class text suggests extended or late-season planning value.');
    if (row.data_confidence === 'LIMITED' || row.data_confidence === 'BLOCKED') addTag(tagRows, row, 'DATA_LIMITED_DO_NOT_OVERSELL', 'HUNTER_PERSONA', 'Only limited data supports this output.');

    if (row.new_this_year || y?.flags.has('new_hunts_2026')) addTag(tagRows, row, 'NEW_2026_HUNT', 'NEW_TREND', 'Year-to-year audit or current feed marks this as new for 2026.');
    if (y?.flags.has('same_name_different_code') || y?.flags.has('deleted_hunts_2026')) addTag(tagRows, row, 'DELETED_OR_RENAMED_HISTORY', 'NEW_TREND', 'Year-to-year audit found code/name discontinuity.');
    if (y?.permit_change_pct != null && y.permit_change_pct > 20) addTag(tagRows, row, 'PERMIT_INCREASE_WATCH', 'NEW_TREND', `Permit count increased ${round(y.permit_change_pct)}%.`);
    if (y?.permit_change_pct != null && y.permit_change_pct < -20) addTag(tagRows, row, 'PERMIT_REDUCTION_RISK', 'NEW_TREND', `Permit count decreased ${round(y.permit_change_pct)}%.`);
    if (row.high_pressure) addTag(tagRows, row, 'HIGH_PRESSURE_HUNT', 'NEW_TREND', 'Runtime feed marks demand pressure as high.');

    const peer = peerStats.get(peerKey(row)) || {};
    const sleeperReasons = [];
    let sleeperScore = 0;
    if (p != null && peer.oddsMedian != null && p > peer.oddsMedian + 5) { sleeperScore += 1; sleeperReasons.push('better odds than peer median'); }
    if (success != null && peer.successMedian != null && success > peer.successMedian + 5) { sleeperScore += 1; sleeperReasons.push('harvest success above peer median'); }
    if (permits != null && peer.permitMedian != null && permits >= peer.permitMedian) { sleeperScore += 1; sleeperReasons.push('permit count at or above peer median'); }
    if (creep != null && peer.creepMedian != null && creep <= peer.creepMedian) { sleeperScore += 1; sleeperReasons.push('point creep not worse than peer median'); }
    if (['QUALITY_ABOVE_OBJECTIVE', 'QUALITY_MEETING_OBJECTIVE'].includes(row.management_objective_status)) { sleeperScore += 1; sleeperReasons.push('management objective meeting/above where comparable data exists'); }
    if (!famousOrPremiumName(row)) { sleeperScore += 1; sleeperReasons.push('not an obvious marquee hunt name'); }
    if (row.tags.includes('DATA_LIMITED_DO_NOT_OVERSELL')) sleeperScore = Math.max(0, sleeperScore - 1);
    row.sleeper_score = sleeperScore;
    row.sleeper_reasons = sleeperReasons.join('; ');
    if (sleeperScore >= 4) {
      addTag(tagRows, row, 'SLEEPER_CANDIDATE', 'NEW_TREND', row.sleeper_reasons);
      addTag(tagRows, row, 'OVERLOOKED_OPPORTUNITY', 'NEW_TREND', 'Positive sleeper heuristic; verify before applying.');
      addTag(tagRows, row, 'OPPORTUNIST', 'HUNTER_PERSONA', 'Better-than-peer opportunity signal.');
    }

    if (row.tags.includes('STATUS_OR_AVAILABILITY_ONLY')) row.decision_label = 'STATUS / AVAILABILITY ONLY';
    else if (p == null) row.decision_label = 'INSUFFICIENT DATA';
    else if (p >= 60) row.decision_label = 'STRONG APPLY';
    else if (p >= 25) row.decision_label = 'WITHIN REACH';
    else if (trophy || row.management_objective_status === 'QUALITY_ABOVE_OBJECTIVE') row.decision_label = 'QUALITY LONG SHOT';
    else row.decision_label = 'LONG SHOT';

    row.persona_tags = row.tags.filter((tag) => [
      'YOUTH_OPPORTUNITY', 'BEGINNER_ANTLERLESS', 'FREEZER_FILLER', 'ELDER_FRIENDLY',
      'HARD_DRIVER', 'TROPHY_DREAMER', 'POINT_SAVER', 'OPPORTUNIST', 'GROUP_FRIENDLY',
      'EXTEND_THE_SEASON', 'DATA_LIMITED_DO_NOT_OVERSELL',
    ].includes(tag)).join('|');
    row.recommended_action = recommendedAction(row);
    row.source_badges = buildSourceBadges(row);
    row.data_confidence = confidence(row);

    if (row.tags.includes('SLEEPER_CANDIDATE')) {
      sleeperRows.push({
        hunt_code: row.hunt_code,
        hunt_name: row.hunt_name,
        species: row.species,
        residency: row.residency,
        hunt_class: row.hunt_class,
        modeled_draw_probability: row.modeled_draw_probability,
        harvest_success_pct: row.harvest_success_pct ?? '',
        permits_2026_total: row.permits_2026_total,
        sleeper_score: row.sleeper_score,
        sleeper_reasons: row.sleeper_reasons,
        data_limitations: row.tags.includes('DATA_LIMITED_DO_NOT_OVERSELL') ? 'Limited supporting data; do not oversell.' : '',
      });
    }
    if (row.tags.includes('NEW_2026_HUNT')) {
      newRows.push({
        hunt_code: row.hunt_code,
        hunt_name: row.hunt_name,
        species: row.species,
        residency: row.residency,
        hunt_class: row.hunt_class,
        permits_2026_total: row.permits_2026_total,
        change_flags: y ? [...y.flags].join('|') : 'new_this_year',
        recommended_review: 'Review year-to-year continuity, point ladder behavior, and public display language before promotion.',
      });
    }
  });

  const outlookColumns = [
    'hunt_code', 'hunt_name', 'species', 'residency', 'draw_family', 'hunt_class', 'weapon',
    'hunt_type', 'draw_pool', 'unit_name', 'boundary_id', 'current_points_context_available', 'modeled_draw_probability',
    'guaranteed_line_points', 'point_creep_1yr', 'harvest_success_pct',
    'average_days_hunted', 'average_harvest_age', 'current_age_3yr_average', 'percent_5plus',
    'management_objective_type', 'management_objective_range', 'management_objective_status',
    'management_objective_note', 'management_direction', 'permit_direction_watch',
    'permits_2026_res', 'permits_2026_nr', 'permits_2026_total',
    'decision_label', 'persona_tags', 'sleeper_score', 'sleeper_reasons',
    'recommended_action', 'data_confidence', 'source_badges', 'model_version', 'rule_version',
    'availability_status', 'harvest_source_file', 'harvest_source_page', 'age_source_file',
    'age_source_page', 'age_source_table_title', 'age_review_status',
  ];
  const cleanRows = rows.map((row) => Object.fromEntries(outlookColumns.map((col) => [col, row[col] ?? ''])));
  const managementContextRows = [];
  const managementSeen = new Set();
  for (const row of rows) {
    if (!hasValue(row.management_objective_type) && !hasValue(row.management_objective_status)) continue;
    if (managementSeen.has(row.hunt_code)) continue;
    managementSeen.add(row.hunt_code);
    const mg = managementByCode.get(row.hunt_code) || {};
    managementContextRows.push({
      hunt_code: row.hunt_code,
      species: row.species,
      hunt_name: row.hunt_name,
      hunt_type: row.hunt_type,
      hunt_class: row.hunt_class,
      management_objective_type: row.management_objective_type,
      management_objective_min: mg.management_objective_min ?? '',
      management_objective_max: mg.management_objective_max ?? '',
      objective_unit: mg.objective_unit || row.management_objective_range || '',
      objective_status: row.management_objective_status,
      management_direction: row.management_direction || '',
      notes: row.management_objective_note || mg.notes || '',
      permit_direction_watch: row.permit_direction_watch || '',
      source_class: managementRows.length ? 'reviewed_management_context_file' : 'synthetic_plan_context_from_database',
      context_only: true,
    });
  }

  const sleeperColumns = ['hunt_code', 'hunt_name', 'species', 'residency', 'hunt_class', 'modeled_draw_probability', 'harvest_success_pct', 'permits_2026_total', 'sleeper_score', 'sleeper_reasons', 'data_limitations'];
  const newColumns = ['hunt_code', 'hunt_name', 'species', 'residency', 'hunt_class', 'permits_2026_total', 'change_flags', 'recommended_review'];
  const tagColumns = ['hunt_code', 'hunt_name', 'species', 'residency', 'tag', 'tag_category', 'reason', 'data_confidence'];

  const demographics = {};
  const personaTags = ['YOUTH_OPPORTUNITY', 'BEGINNER_ANTLERLESS', 'FREEZER_FILLER', 'ELDER_FRIENDLY', 'HARD_DRIVER', 'TROPHY_DREAMER', 'POINT_SAVER', 'OPPORTUNIST', 'GROUP_FRIENDLY', 'EXTEND_THE_SEASON'];
  personaTags.forEach((tag) => {
    const candidates = rows
      .filter((row) => row.tags.includes(tag))
      .sort((a, b) => (b.sleeper_score - a.sleeper_score) || ((Number(b.modeled_draw_probability) || 0) - (Number(a.modeled_draw_probability) || 0)))
      .slice(0, 25)
      .map((row) => ({
        hunt_code: row.hunt_code,
        hunt_name: row.hunt_name,
        species: row.species,
        residency: row.residency,
        decision_label: row.decision_label,
        modeled_draw_probability: row.modeled_draw_probability,
        harvest_success_pct: row.harvest_success_pct ?? '',
        sleeper_score: row.sleeper_score,
        recommended_action: row.recommended_action,
      }));
    demographics[tag] = { count: rows.filter((row) => row.tags.includes(tag)).length, recommendations: candidates };
  });

  const tagCounts = tagRows.reduce((acc, row) => {
    acc[row.tag] = (acc[row.tag] || 0) + 1;
    return acc;
  }, {});
  const validation = {
    output_average_harvest_age_zero_count: cleanRows.filter((row) => num(row.average_harvest_age) === 0).length,
    average_days_hunted_mapped_as_age_suspect_count: rows.filter((row) => row.average_harvest_age !== '' && row.average_days_hunted !== '' && text(row.average_harvest_age) === text(row.average_days_hunted) && row._ageSource !== resolved.age).length,
    average_days_hunted_same_as_verified_age_count: rows.filter((row) => row.average_harvest_age !== '' && row.average_days_hunted !== '' && text(row.average_harvest_age) === text(row.average_days_hunted) && row._ageSource === resolved.age).length,
    blocked_rows: cleanRows.filter((row) => row.data_confidence === 'BLOCKED').length,
  };
  const protectedAfter = {
    database: await sha256(resolved.database),
    predictive: await sha256(resolved.predictive),
    ladder: await sha256(resolved.ladder),
  };

  await writeJson(outputFiles.outlookJson, cleanRows);
  await writeCsv(outputFiles.outlookCsv, cleanRows, outlookColumns);
  await writeJson(outputFiles.tagsJson, tagRows);
  await writeCsv(outputFiles.tagsCsv, tagRows, tagColumns);
  await writeJson(outputFiles.sleeperJson, sleeperRows);
  await writeCsv(outputFiles.sleeperCsv, sleeperRows, sleeperColumns);
  await writeJson(outputFiles.newJson, newRows);
  await writeCsv(outputFiles.newCsv, newRows, newColumns);
  await writeJson(outputFiles.demographicsJson, {
    generated_at: new Date().toISOString(),
    purpose: 'Visitor-friendly hunt classification and persona recommendation layer. Display-only; does not modify draw odds, p_draw, permits, or quotas.',
    persona_groups: demographics,
  });
  await writeJson(outputFiles.managementContextJson, managementContextRows);
  await writeJson(outputFiles.auditJson, {
    generated_at: new Date().toISOString(),
    inputs: {
      sync_matrix_rows: Array.isArray(syncMatrix) ? syncMatrix.length : 0,
      readiness_engines: readiness.engines ? readiness.engines.length : 0,
      management_context_rows: managementRows.length,
      management_context_rows_effective: managementRowsEffective.length,
      management_context_source: managementRows.length ? 'file' : 'synthetic_from_database_and_plan_rules',
      elk_plan_present: hasElkPlan,
      mule_deer_plan_present: hasDeerPlan,
      master_rows: master.length,
      ladder_rows: ladder.length,
      predictive_rows: predictive.length,
      harvest_rows: harvest.length,
      age_rows: age.length,
      database_rows: database.length,
      year_change_rows: yearChanges.length,
      source_paths: {
        sync_matrix: resolved.syncMatrix,
        readiness: resolved.readiness,
        management: resolved.management,
        master: resolved.master,
        ladder: resolved.ladder,
        predictive: resolved.predictive,
        harvest: resolved.harvest,
        age: resolved.age,
        year_change: resolved.yearChange,
        database: resolved.database,
      },
    },
    outputs: {
      outlook_rows: cleanRows.length,
      tag_rows: tagRows.length,
      sleeper_hunt_rows: sleeperRows.length,
      new_hunt_rows: newRows.length,
      demographic_groups: personaTags.length,
      management_context_output_rows: managementContextRows.length,
    },
    tag_counts: tagCounts,
    demographic_counts: Object.fromEntries(Object.entries(demographics).map(([tag, group]) => [tag, group.count])),
    validations: validation,
    protected_file_hashes_unchanged: {
      database: protectedBefore.database === protectedAfter.database,
      predictive: protectedBefore.predictive === protectedAfter.predictive,
      ladder: protectedBefore.ladder === protectedAfter.ladder,
    },
    guardrails: [
      'No DATABASE.csv truth values modified.',
      'No prediction formulas, point ladder math, p_draw, permits, or quotas modified.',
      'Management objectives are benchmark/context only and never overwrite observed age or draw probability.',
      'Mule deer percent_5plus is kept separate from average_harvest_age.',
    ],
  });

  console.log(JSON.stringify({
    outlook_rows: cleanRows.length,
    tag_rows: tagRows.length,
    sleeper_hunt_rows: sleeperRows.length,
    new_hunt_rows: newRows.length,
    validation,
    protected_file_hashes_unchanged: {
      database: protectedBefore.database === protectedAfter.database,
      predictive: protectedBefore.predictive === protectedAfter.predictive,
      ladder: protectedBefore.ladder === protectedAfter.ladder,
    },
  }, null, 2));
}

build().catch((error) => {
  console.error(error);
  process.exit(1);
});
