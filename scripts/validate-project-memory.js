const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..');

function repoPath(root, relativePath) {
  return path.join(root, ...String(relativePath).split('/'));
}

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function validateProjectMemory(root = REPO) {
  const failures = [];
  const warnings = [];
  const facts = [];
  let checks = 0;

  function check(condition, message) {
    checks += 1;
    if (!condition) failures.push(message);
  }

  function warn(condition, message) {
    if (!condition) warnings.push(message);
  }

  function readText(relativePath) {
    const filePath = repoPath(root, relativePath);
    check(fs.existsSync(filePath), `Required file is missing: ${relativePath}`);
    return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : '';
  }

  function readJson(relativePath) {
    const text = readText(relativePath);
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch (error) {
      failures.push(`Invalid JSON in ${relativePath}: ${error.message}`);
      return {};
    }
  }

  const authority = readJson('governance/engine-authority.json');
  const packageJson = readJson('package.json');
  const agents = readText('AGENTS.MD');
  const currentState = readText('docs/CURRENT_STATE.md');
  const drawDesignBaseline = readText('docs/UTAH_DRAW_DESIGN_BASELINE.md');
  const config = readText('config.js');
  const researchLoader = readText('hunt-research.js');
  const mixedConstants = readText('engine/utah_predictive_mixed/__init__.py');
  const pipelineConstants = readText('engine/utah_bonus_predictive/rules.py');

  check(authority.schema_version === '1.2.0', 'Memory schema_version must be 1.2.0.');
  check(authority.authority === 'HUNT_BUILDER_PROJECT_MEMORY', 'Unexpected memory authority identifier.');
  check(authority.lifecycle?.promotion_status === 'BLOCKED', 'Current promotion status must remain BLOCKED until recorded blockers are cleared.');
  check(authority.lifecycle?.production_prediction_accuracy_certified === false, 'Current prediction accuracy must not be marked certified.');
  check(Number.isInteger(authority.lifecycle?.active_forecast_year), 'Active forecast year must be an integer.');
  check(Array.isArray(authority.lifecycle?.promotion_blockers) && authority.lifecycle.promotion_blockers.length > 0, 'Blocked promotion requires explicit blocker codes.');

  const requiredAgentInstructions = [
    'docs/CURRENT_STATE.md',
    'governance/engine-authority.json',
    'docs/UTAH_DRAW_DESIGN_BASELINE.md',
    'docs/decisions/',
    'npm run validate:project-memory',
    'Do not create a new prediction-engine stack',
  ];
  for (const instruction of requiredAgentInstructions) {
    check(agents.includes(instruction), `AGENTS.MD is missing memory instruction: ${instruction}`);
  }

  check(currentState.includes(`Memory contract: \`${authority.schema_version}\``), 'CURRENT_STATE.md memory version does not match the authority schema.');
  check(currentState.includes(`Last verified: \`${authority.last_verified_date}\``), 'CURRENT_STATE.md verification date does not match the authority record.');
  check(currentState.includes(authority.lifecycle.phase), 'CURRENT_STATE.md does not state the declared lifecycle phase.');
  check(currentState.includes('Promotion status: `BLOCKED`'), 'CURRENT_STATE.md must state the current blocked promotion status.');
  check(drawDesignBaseline.includes('Black bear restricted pursuit permits'), 'Draw-design baseline must distinguish restricted bear pursuit.');
  check(drawDesignBaseline.includes('Black bear limited-entry hunting permits'), 'Draw-design baseline must distinguish limited-entry bear hunting.');
  check(drawDesignBaseline.includes('Resident and nonresident rules'), 'Draw-design baseline must preserve residency rules.');
  check(drawDesignBaseline.includes('just-missed high-point cohort'), 'Draw-design baseline must preserve the applicant-behavior anchor.');

  const routing = authority.draw_design_routing || {};
  check(routing.preferred_authority_field === 'draw_design', 'Draw-design routing must prefer draw_design.');
  check(routing.compatibility_alias_field === 'draw_system_type', 'Draw-design routing must retain draw_system_type only as a compatibility alias.');
  check(Object.keys(routing.families || {}).length >= 5, 'Draw-design routing must declare bonus, preference, random, youth, and non-draw behavior.');
  check(authority.official_draw_design_baseline?.document === 'docs/UTAH_DRAW_DESIGN_BASELINE.md', 'Official baseline document is not canonical.');
  check(authority.residency_rule_layer?.authority === 'OFFICIAL_CURRENT_RESIDENT_AND_NONRESIDENT_QUOTA_LANES', 'Residency quota authority is not explicit.');
  check(authority.applicant_behavior_model?.primary_anchor === 'LATEST_OFFICIAL_UNSUCCESSFUL_APPLICANTS_ADVANCED_ONE_POINT', 'Applicant behavior must anchor on the latest unsuccessful cohort.');

  for (const relativePath of authority.required_documents || []) {
    const filePath = repoPath(root, relativePath);
    check(fs.existsSync(filePath), `Required memory document is missing: ${relativePath}`);
    if (fs.existsSync(filePath) && relativePath.includes('/decisions/ADR-')) {
      check(fs.readFileSync(filePath, 'utf8').includes('Status: Accepted'), `Required ADR is not accepted: ${relativePath}`);
    }
  }

  const scripts = packageJson.scripts || {};
  check(scripts['validate:project-memory'] === 'node scripts/validate-project-memory.js', 'package.json must expose the canonical memory validator command.');
  check(String(scripts.test || '').includes('validate:project-memory'), 'The normal npm test command must run the project-memory validator.');

  const roleEntries = Object.values(authority.engine_roles || {});
  check(roleEntries.length === 4, 'Exactly four declared engine roles are required by the current architecture.');
  for (const role of roleEntries) {
    check(typeof role.path === 'string' && fs.existsSync(repoPath(root, role.path)), `Declared engine role path is missing: ${role.path || '<blank>'}`);
  }

  const engineRoot = repoPath(root, 'engine');
  const actualEngineDirectories = fs.readdirSync(engineRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name !== '__pycache__')
    .map((entry) => entry.name)
    .sort();
  const allowedEngineDirectories = [...(authority.engine_directory_allowlist || [])].sort();
  check(
    JSON.stringify(actualEngineDirectories) === JSON.stringify(allowedEngineDirectories),
    `Engine directory allowlist mismatch. Actual=${actualEngineDirectories.join(',')} Allowed=${allowedEngineDirectories.join(',')}`,
  );

  const runtimeOwner = authority.engine_roles?.post_family_calibration_owner || {};
  check(mixedConstants.includes(`MODEL_VERSION = "${runtimeOwner.model_version}"`), 'Mixed engine MODEL_VERSION disagrees with engine authority.');
  check(mixedConstants.includes(`RULE_VERSION = "${runtimeOwner.rule_version}"`), 'Mixed engine RULE_VERSION disagrees with engine authority.');

  const pipelineOwner = authority.engine_roles?.forecast_materialization_owner || {};
  check(pipelineConstants.includes(`MODEL_VERSION = "${pipelineOwner.pipeline_version}"`), 'Forecast pipeline MODEL_VERSION disagrees with engine authority.');
  check(pipelineConstants.includes(`RULE_VERSION = "${pipelineOwner.rule_version}"`), 'Forecast pipeline RULE_VERSION disagrees with engine authority.');

  const evidence = authority.latest_evidence?.prediction_build_evidence || {};
  check(evidence.storage === 'GIT_TRACKED_COMPACT_AUTHORITY', 'Prediction build evidence must remain a compact Git-tracked authority record.');
  check(evidence.source_manifest_path === 'processed_data/utah_bonus_predictive_manifest.json', 'Prediction source-manifest path is not canonical.');
  check(evidence.source_manifest_storage === 'REPO_EXTERNAL_GENERATED_ARTIFACT', 'Prediction source manifest must remain repo-external generated data.');
  check(evidence.source_manifest_local_policy === 'OPTIONAL_LOCAL_HYDRATION', 'Prediction source-manifest local hydration policy is not optional.');
  check(/^[a-f0-9]{64}$/.test(evidence.source_manifest_sha256 || ''), 'Prediction source-manifest SHA-256 is missing or invalid.');
  check(evidence.pipeline_version === pipelineOwner.pipeline_version, 'Compact prediction evidence pipeline version disagrees with the declared build pipeline.');
  check(evidence.rule_version === pipelineOwner.rule_version, 'Compact prediction evidence rule version disagrees with the declared build pipeline.');
  check(evidence.forecast_year === authority.lifecycle.active_forecast_year, 'Compact prediction evidence forecast year disagrees with project memory.');
  check(Number.isInteger(evidence.prediction_rows) && evidence.prediction_rows > 0, 'Compact prediction evidence has no valid prediction row count.');
  check(Number.isInteger(evidence.backtest_rows) && evidence.backtest_rows > 0, 'Compact prediction evidence has no valid backtest row count.');
  check(evidence.duplicate_prediction_keys === 0, 'Compact prediction evidence must retain the verified zero duplicate prediction-key count.');
  check(/^[a-f0-9]{64}$/.test(evidence.database_sha256_at_build || ''), 'Compact prediction evidence has no valid DATABASE.csv SHA-256.');
  check(/^[a-f0-9]{64}$/.test(evidence.normalized_draw_truth_sha256 || ''), 'Compact prediction evidence has no valid normalized draw-truth SHA-256.');
  check(/^[a-f0-9]{64}$/.test(evidence.frozen_prediction_sha256 || ''), 'Compact prediction evidence has no valid frozen prediction SHA-256.');

  const promotionEvidence = authority.latest_evidence?.local_prediction_promotion_2026_08_27 || {};
  check(evidence.source_manifest_sha256 === promotionEvidence.promoted_manifest_sha256, 'Compact prediction evidence does not match the promoted manifest SHA-256.');
  check(evidence.frozen_prediction_sha256 === promotionEvidence.frozen_prediction_sha256, 'Compact prediction evidence does not match the promoted frozen prediction SHA-256.');

  const sourceManifestPath = evidence.source_manifest_path || '';
  const sourceManifestFile = sourceManifestPath ? repoPath(root, sourceManifestPath) : '';
  const sourceManifestExists = Boolean(sourceManifestFile) && fs.existsSync(sourceManifestFile);
  let sourceManifest = null;
  if (sourceManifestExists) {
    try {
      sourceManifest = JSON.parse(fs.readFileSync(sourceManifestFile, 'utf8'));
    } catch (error) {
      failures.push(`Invalid JSON in ${sourceManifestPath}: ${error.message}`);
    }
  } else {
    warnings.push(`Repo-external prediction source manifest is not hydrated locally; compact governance evidence remains active: ${sourceManifestPath || '<blank>'}`);
  }

  if (sourceManifest) {
    check(sha256(sourceManifestFile) === evidence.source_manifest_sha256, 'Hydrated prediction source-manifest SHA-256 disagrees with compact governance evidence.');
    check(sourceManifest.model_version === evidence.pipeline_version, 'Hydrated prediction source-manifest model version is stale.');
    check(sourceManifest.rule_version === evidence.rule_version, 'Hydrated prediction source-manifest rule version is stale.');
    check(sourceManifest.forecast_year === evidence.forecast_year, 'Hydrated prediction source-manifest forecast year is stale.');
    check(sourceManifest.output_row_counts?.['ml_draw_predictions_v1.csv'] === evidence.prediction_rows, 'Hydrated prediction source-manifest prediction row count is stale.');
    check(sourceManifest.output_row_counts?.['backtest_utah_bonus_draw.csv'] === evidence.backtest_rows, 'Hydrated prediction source-manifest backtest row count is stale.');
  }

  check(config.includes('processed_data/hunt_research_2026_summary.json'), 'config.js no longer declares the canonical Research summary.');
  check(config.includes('processed_data/hunt_research_2026_split/hunt_research_2026.index.json'), 'config.js no longer declares the canonical Research split index.');
  check(researchLoader.includes('USE_SPLIT_CANONICAL_CONTRACT'), 'Hunt Research no longer declares the canonical split-contract gate.');
  check(researchLoader.includes("engine: 'canonical_summary_contract'"), 'Hunt Research canonical summary route is missing.');

  const database = authority.truth_authority?.current_hunt_and_permit_reference || {};
  const databasePath = repoPath(root, database.path || '');
  check(fs.existsSync(databasePath), `Required truth authority is missing: ${database.path || '<blank>'}`);
  if (fs.existsSync(databasePath)) {
    const currentHash = sha256(databasePath);
    check(currentHash === database.verified_sha256, `DATABASE.csv changed without updating project memory. Expected=${database.verified_sha256} Actual=${currentHash}`);
    facts.push(`database_sha256=${currentHash}`);

    if (sourceManifest) {
      const manifestDatabaseEntry = Object.entries(sourceManifest.source_files_used || {})
        .find(([filePath]) => filePath.replaceAll('\\', '/').endsWith('/pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv')
          || filePath.replaceAll('\\', '/') === 'pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv');
      check(Boolean(manifestDatabaseEntry), 'Hydrated prediction source manifest does not retain the DATABASE.csv source hash.');
      if (manifestDatabaseEntry) {
        check(evidence.database_sha256_at_build === manifestDatabaseEntry[1], 'Hydrated prediction source-manifest DATABASE.csv hash is stale.');
      }
    }

    if (evidence.database_sha256_at_build) {
      const staleBuildDeclared = (authority.lifecycle?.promotion_blockers || [])
        .includes('CURRENT_DATABASE_NEWER_THAN_CHECKED_IN_PREDICTION_MANIFEST');
      if (staleBuildDeclared) {
        check(currentHash !== evidence.database_sha256_at_build, 'The recorded stale-build blocker is no longer true; rebuild evidence and promotion status must be reviewed.');
      } else {
        check(currentHash === evidence.database_sha256_at_build, 'Current DATABASE.csv differs from compact prediction-build evidence without a declared stale-build blocker.');
      }
    }
  }

  const drawTruth = authority.truth_authority?.normalized_draw_actuals || {};
  warn(fs.existsSync(repoPath(root, drawTruth.path || '')), `External prediction rebuild input is not hydrated locally: ${drawTruth.path || '<blank>'}`);

  for (const artifact of authority.runtime_artifacts || []) {
    check(typeof artifact.path === 'string' && artifact.path.length > 0, `Runtime artifact ${artifact.role || '<unknown>'} has no logical path.`);
    check(/^https:\/\//.test(artifact.external_url || ''), `Runtime artifact ${artifact.role || '<unknown>'} has no HTTPS external URL.`);
    check(['GIT_TRACKED', 'OPTIONAL_R2_BACKED'].includes(artifact.local_policy), `Runtime artifact ${artifact.role || '<unknown>'} has an unsupported local policy: ${artifact.local_policy || '<blank>'}`);
    const exists = fs.existsSync(repoPath(root, artifact.path || ''));
    if (artifact.local_policy === 'GIT_TRACKED') {
      check(exists, `Git-tracked runtime artifact is missing: ${artifact.path}`);
    } else if (artifact.local_policy === 'OPTIONAL_R2_BACKED') {
      warn(exists, `R2-backed runtime artifact is not hydrated locally (allowed for code-only validation): ${artifact.path}`);
    }
  }

  const drift = authority.known_contract_drift || [];
  check(drift.length >= 1, 'Known runtime-contract drift items must remain explicit until resolved.');
  check(new Set(drift.map((item) => item.id)).size === drift.length, 'Known contract-drift IDs must be unique.');
  check(drift.every((item) => item.status === 'UNRESOLVED_REQUIRES_REVIEW'), 'Resolved contract drift must be removed through a reviewed memory update.');

  const invariants = new Set(authority.protected_invariants || []);
  for (const invariant of [
    'DO_NOT_CREATE_NEW_ENGINE_STACK_WITHOUT_TYLER_APPROVAL',
    'DO_NOT_ROUTE_DIFFERENT_DRAW_DESIGNS_THROUGH_ONE_GENERIC_FORMULA',
    'DRAW_DESIGN_IS_PRIMARY_ROUTING_AUTHORITY',
    'BEAR_HUNT_AND_RESTRICTED_PURSUIT_ARE_DISTINCT_BONUS_PROGRAMS',
    'RESIDENCY_IS_A_RULE_LAYER_NOT_A_POST_HOC_LABEL',
    'LAST_YEAR_HIGH_POINT_UNSUCCESSFUL_COHORT_IS_PRIMARY_DEMAND_ANCHOR',
    'DO_NOT_FABRICATE_PROBABILITY_FROM_PERMIT_TOTALS_OR_REFERENCE_ROWS',
    'DO_NOT_PROMOTE_WITHOUT_BLIND_FOLLOWING_YEAR_ACCURACY_EVIDENCE',
    'DO_NOT_PUBLISH_OR_UPLOAD_WITHOUT_EXPLICIT_TYLER_AUTHORIZATION',
  ]) {
    check(invariants.has(invariant), `Protected invariant is missing: ${invariant}`);
  }

  facts.push(`memory_schema=${authority.schema_version || 'unknown'}`);
  facts.push(`lifecycle=${authority.lifecycle?.phase || 'unknown'}`);
  facts.push(`forecast_year=${authority.lifecycle?.active_forecast_year || 'unknown'}`);
  facts.push(`runtime_model=${runtimeOwner.model_version || 'unknown'}`);
  facts.push(`build_pipeline=${pipelineOwner.pipeline_version || 'unknown'}`);
  facts.push(`prediction_evidence=${evidence.storage || 'unknown'}`);
  facts.push('runtime_storage=R2_BACKED_WITH_OPTIONAL_LOCAL_HYDRATION');
  facts.push(`promotion=${authority.lifecycle?.promotion_status || 'unknown'}`);
  facts.push(`known_contract_drift=${drift.length}`);

  return { checks, failures, warnings, facts };
}

function printResult(result) {
  const status = result.failures.length ? 'FAIL' : 'PASS';
  console.log(`PROJECT_MEMORY_STATUS=${status}`);
  console.log(`CHECKS=${result.checks}`);
  for (const fact of result.facts) console.log(`FACT ${fact}`);
  for (const warning of result.warnings) console.log(`WARNING ${warning}`);
  for (const failure of result.failures) console.error(`FAILURE ${failure}`);
}

if (require.main === module) {
  const result = validateProjectMemory();
  printResult(result);
  process.exitCode = result.failures.length ? 1 : 0;
}

module.exports = {
  validateProjectMemory,
};
