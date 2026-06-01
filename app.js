const uogaConfig = window.UOGA_CONFIG;
const uogaData = window.UOGA_DATA;

if (!uogaConfig || !uogaData) {
  console.error('UOGA config/data missing. Check script load order and file paths.');
  throw new Error('UOGA config/data missing. Check script load order and file paths.');
}

const {
  GOOGLE_MAPS_API_KEY,
  GOOGLE_BASELINE_DEFAULT_CENTER,
  GOOGLE_BASELINE_DEFAULT_ZOOM,
  UTAH_LOCATION_BOUNDS,
  CLOUDFLARE_BASE,
  HUNT_DATA_VERSION,
  OUTFITTERS_DATA_VERSION,
  OUTFITTER_COVERAGE_VERSION,
  HUNT_BOUNDARY_SOURCES,
  DISPLAY_BOUNDARY_INDEX_SOURCES,
  BOUNDARY_MANIFEST_SOURCES,
  FINALIZED_BOUNDARY_SOURCES,
  COMPOSITE_BOUNDARY_SOURCES,
  OUTFITTERS_DATA_SOURCES,
  OUTFITTER_FEDERAL_COVERAGE_SOURCES,
  CONSERVATION_PERMIT_AREA_SOURCES,
  CONSERVATION_PERMIT_HUNT_TABLE_SOURCES,
  LOGO_DNR,
  LOGO_DWR_SELECTOR,
  LOGO_DNR_ROOMY,
  LOGO_CWMU,
  LOGO_DWR_WMA,
  LOGO_USFS,
  LOGO_BLM,
  LOGO_SITLA,
  LOGO_STATE_PARKS,
  LOCAL_CWMU_BOUNDARIES_PATH,
  CWMU_BOUNDARY_IDS_PATH,
  PUBLIC_OWNERSHIP_LAYER_URL,
  BLM_SURFACE_OWNERSHIP_LAYER_URL,
  BLM_ADMIN_LAYER_URL,
  BLM_ADMIN_QUERY_URL,
  CWMU_QUERY_URL,
  STATE_PARKS_QUERY_URL,
  WMA_QUERY_URL,
  WILDERNESS_QUERY_URL,
  UTAH_OUTLINE_QUERY_URL,
  USFS_QUERY_URL,
  WATERFOWL_WMA_NAMES,
  HUNT_DATA_SOURCES,
  ELK_BOUNDARY_TABLE_SOURCES,
  OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
  SPIKE_ELK_HUNT_CODES,
  HUNT_BOUNDARY_NAME_OVERRIDES,
  huntPlannerMapStyle,
  HUNT_TYPE_ORDER,
  HUNT_CLASS_ORDER,
  SEX_ORDER,
  WEAPON_ORDER,
  DNR_ORANGE,
  DNR_BROWN,
  KNOWN_OUTFITTER_COORDS
} = uogaConfig;

const {
  fetchJson,
  fetchGeoJson,
  fetchFirstGeoJson,
  fetchArcGisPagedGeoJson,
  loadOfficialBoundaryLookup: loadOfficialBoundaryLookupFromData,
  applyOfficialBoundaryMappings: applyOfficialBoundaryMappingsFromData,
  loadOfficialElkBoundaryFeatures: loadOfficialElkBoundaryFeaturesFromData,
  loadDerivedSpikeElkRecords: loadDerivedSpikeElkRecordsFromData,
  loadHuntDataRecords,
  loadFirstNormalizedList
} = uogaData;

const boundaryResolver = window.UOGA_BOUNDARY_RESOLVER || {};
const normalizeHuntCodeFromResolver = typeof boundaryResolver.normalizeHuntCode === 'function'
  ? boundaryResolver.normalizeHuntCode
  : (value) => String(value ?? '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
const normalizeBoundaryIdFromResolver = typeof boundaryResolver.normalizeBoundaryId === 'function'
  ? boundaryResolver.normalizeBoundaryId
  : (value) => {
      const raw = String(value ?? '').trim();
      if (!raw) return '';
      if (/^-?\d+(\.\d+)?$/.test(raw)) return String(Math.trunc(Number(raw)));
      return raw;
    };
const parseBoundaryIdListFromResolver = typeof boundaryResolver.parseIdList === 'function'
  ? boundaryResolver.parseIdList
  : (value) => {
      if (Array.isArray(value)) return value.flatMap(parseBoundaryIdListFromResolver);
      const text = String(value ?? '').trim();
      if (!text) return [];
      if (/[,\|;\/]/.test(text)) return text.split(/[,\|;\/]/).map(v => String(v).trim()).filter(Boolean);
      return [text];
    };
const indexBoundaryFeaturesFromResolver = typeof boundaryResolver.indexBoundaryFeatures === 'function'
  ? boundaryResolver.indexBoundaryFeatures
  : (geojson) => {
      const byBoundaryId = new Map();
      const features = Array.isArray(geojson?.features) ? geojson.features : [];
      features.forEach(feature => {
        const props = feature?.properties || {};
        const ids = [
          props?.BoundaryID,
          props?.BOUNDARYID,
          props?.Boundary_Id,
          props?.boundary_id,
        ]
          .flatMap(v => parseBoundaryIdListFromResolver(v))
          .map(v => normalizeBoundaryIdFromResolver(v))
          .filter(Boolean);
        ids.forEach(id => {
          if (!byBoundaryId.has(id)) byBoundaryId.set(id, []);
          byBoundaryId.get(id).push(feature);
        });
      });
      return { byBoundaryId, featureCount: features.length };
    };
const resolveBoundaryForHuntFromResolver = typeof boundaryResolver.resolveBoundaryForHunt === 'function'
  ? boundaryResolver.resolveBoundaryForHunt
  : () => ({ status: 'unavailable' });
const loadBoundaryManifestFromResolver = typeof boundaryResolver.loadBoundaryManifest === 'function'
  ? boundaryResolver.loadBoundaryManifest
  : async () => ({ sourceUsed: '', rowCount: 0, rows: [], byHuntCode: new Map(), byMergedBoundaryId: new Map(), error: null });

let googleBaselineMap = null, googleEarth3dMap = null, googleEarth3dLibraryPromise = null, googleEarth3dBoundaryOverlays = [], huntUnitsLayer = null, googleApiReady = false, huntHoverFeature = null, selectedBoundaryFeature = null, huntData = [], huntBoundaryGeoJson = null, selectedBoundaryMatches = [], selectedHunt = null, selectionInfoWindow = null, usfsLayer = null, blmLayer = null, blmDetailLayer = null, wildernessLayer = null, utahOutlineLayer = null, sitlaLayer = null, stateLandsLayer = null, stateParksLayer = null, wmaLayer = null, cwmuLayer = null, privateLayer = null, outfitters = [], outfitterFederalCoverage = [], outfitterMarkers = [], activeLoads = 0, outfitterMarkerRunId = 0, suppressLandClickUntil = 0;
let selectedHuntFocusOnly = false;
let finalizedBoundaryGeoJson = null;
let independentBoundaryLayer = null;
let independentBoundaryRefreshToken = 0;
const independentBoundaryGeoJsonCache = new Map();
const googleEarth3dGeoJsonCache = new Map();
let compositeBoundaryLookupPromise = null;
let compositeBoundaryMembersByCompositeId = new Map();
let boundaryManifestLoadPromise = null;
let boundaryManifestByHuntCode = new Map();
let boundaryManifestByMergedBoundaryId = new Map();
let boundaryManifestByDisplayBoundaryId = new Map();
let boundaryManifestSourceUsed = '';
let selectedBoundaryFallbackLayer = null;

function getGooglePreferredBasemapType() {
  const VALID = new Set(['roadmap', 'terrain', 'hybrid', 'satellite']);
  try {
    const raw = String(localStorage.getItem('uoga_google_basemap_type_v2') || '').trim();
    return VALID.has(raw) ? raw : 'terrain';
  } catch {
    return 'terrain';
  }
}
let googleMapsLoadTimeoutId = null;
let googleApiLoading = false;
let googleMapFailureMessage = '';
let googleEarth3dLastFocusSignature = '';
let googleEarth3dLastSelectedHuntKey = '';
let googleEarth3dLastBoundaryFocusSignature = '';
let googleEarth3dReorientTimeoutId = null;
let dwrFrameLoadTimeoutId = null;
let controlsBound = false;
let conservationPermitAreas = [];
let conservationPermitHuntTable = [];
const conservationPermitAreaCodeSet = new Set();
const conservationPermitAreaSpeciesUnitNameSet = new Set();
const conservationPermitAreaSpeciesUnitCodeSet = new Set();
const conservationPermitAreaAllowedTypeMap = new Map();
const outfitterGeocodeCache = new Map();
const outfitterMarkerIndex = new Map();
const blmOwnershipPointCache = new Map();
const blmDistrictPointCache = new Map();
const outfitterFederalCoverageIndex = new Map();
// Temporary debug guard: keep Google map as the active mode while we validate key/referrer setup.
const FORCE_GOOGLE_ONLY_DEBUG = false;
// Google 3D map components require the beta channel.
const GOOGLE_MAPS_SCRIPT_CHANNEL = 'beta';
const GOOGLE_MAPS_SCRIPT_LIBRARIES = 'maps3d';
const GOOGLE_EARTH_OUTLINE_ONLY_RANGE = 120000;
const GOOGLE_EARTH_TRANSPARENT_FILL = 'rgba(0,0,0,0)';
const GOOGLE_EARTH_ATMOSPHERE_PROFILE = 'standard';
const ENABLE_SELECTED_HUNT_FLOAT = false;
const GOOGLE_EARTH_TOPOGRAPHY_EXAGGERATION = 1.5;
const LIVE_FILTER_DESKTOP_DEBOUNCE_MS = 220;
const ENABLE_LIVE_MATRIX_APPLY = false;
let devDebugPanelEl = null;
let devDebugPanelTimerId = null;
let lastTrackedMapMode = '';
let liveFilterDebounceTimerId = null;
const APP_VERSION = '2026-05-01-analytics-1';

const searchInput = document.getElementById('searchInput'),
  speciesFilter = document.getElementById('speciesFilter'),
  sexFilter = document.getElementById('sexFilter'),
  huntTypeFilter = document.getElementById('huntTypeFilter'),
  weaponFilter = document.getElementById('weaponFilter'),
  huntCategoryFilter = document.getElementById('huntCategoryFilter'),
  unitFilter = document.getElementById('unitFilter'),
  mapTypeSelect = document.getElementById('mapTypeSelect'),
  streetViewBtn = document.getElementById('streetViewBtn'),
  resetViewBtn = document.getElementById('resetViewBtn'),
  applyFiltersBtn = document.getElementById('applyFiltersBtn'),
  clearFiltersBtn = document.getElementById('clearFiltersBtn'),
  statusEl = document.getElementById('status'),
  toggleDwrUnits = document.getElementById('toggleDwrUnits'),
  toggleUSFS = document.getElementById('toggleUSFS'),
  toggleBLM = document.getElementById('toggleBLM'),
  toggleBLMDetail = document.getElementById('toggleBLMDetail'),
  federalLayersSummary = document.getElementById('federalLayersSummary'),
  toggleSITLA = document.getElementById('toggleSITLA'),
  toggleStateParks = document.getElementById('toggleStateParks'),
  toggleWma = document.getElementById('toggleWma'),
  toggleCwmu = document.getElementById('toggleCwmu'),
  togglePrivate = document.getElementById('togglePrivate'),
  stateLayersSummary = document.getElementById('stateLayersSummary'),
  privateLayersSummary = document.getElementById('privateLayersSummary'),
  mapChooser = document.getElementById('mapChooser'),
  mapChooserTitle = document.getElementById('mapChooserTitle'),
  mapChooserKicker = document.getElementById('mapChooserKicker'),
  mapChooserBody = document.getElementById('mapChooserBody'),
  selectedHuntFloat = document.getElementById('selectedHuntFloat'),
  dwrMapFrame = document.getElementById('dwrMapFrame'),
  plannerDnrLogoLink = document.getElementById('plannerDnrLogoLink'),
  instructionsTab = document.getElementById('instructionsTab'),
  instructionsPanel = document.getElementById('instructionsPanel'),
  instructionsReadBtn = document.getElementById('instructionsReadBtn');

// --- UTILITIES ---
function escapeHtml(v) { return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function safeUrl(value) {
  try {
    const url = new URL(String(value), window.location.origin);
    return ['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol) ? url.href : '#';
  } catch {
    return '#';
  }
}
function safe(v) { return String(v ?? ''); }
function firstNonEmpty(...a) { for (let x of a) { let t = safe(x).trim(); if (t) return t; } return ''; }
function trackAnalytics(eventName, props = {}) {
  try {
    const env = isLocalDevHost() ? 'development' : 'production';
    const mapMode = safe(mapTypeSelect?.value || '').toLowerCase() || 'unknown';
    const page = (() => {
      const path = safe(window.location?.pathname || '/').toLowerCase();
      if (path.endsWith('/research.html')) return 'research';
      if (path.endsWith('/verify.html')) return 'verify';
      if (path.endsWith('/hard-copy.html')) return 'hard-copy';
      if (path.endsWith('/hunt-research.html')) return 'hunt-research';
      return 'builder';
    })();
    window.UOGA_ANALYTICS?.track?.(eventName, {
      app_version: APP_VERSION,
      env,
      page,
      map_mode: mapMode,
      ...props
    });
  } catch (_) {}
}
  function titleCaseWords(v) { return safe(v).split(/\s+/).filter(Boolean).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' '); }
  function normalizeVisibleVerificationLabel(v) { return safe(v).replace(/\bVetted\b/g, 'Verified'); }
function setInstructionsOpen(isOpen) {
  if (!instructionsPanel || !instructionsTab) return;
  instructionsPanel.hidden = !isOpen;
  instructionsTab.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}
function readInstructionsAudio() {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    updateStatus('Audio instructions are not supported in this browser.');
    return;
  }
  const text = 'Choose map mode and land layers. Filter species, sex, hunt type, and units. Click a unit or hunt card to inspect odds and details. Save hunts to Hunt Backpack for cross page workflow.';
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  utterance.lang = 'en-US';
  window.speechSynthesis.speak(utterance);
}
function assetUrl(path) {
  try {
    return new URL(path, window.location.href).href;
  } catch {
    return path;
  }
}
function isMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia('(max-width: 900px)').matches;
}

function initOwnershipControlInHeader() {
  // Land ownership controls stay anchored on the left side of the map.
  const dock = document.getElementById('ownershipDock');
  if (!dock) return;
  dock.classList.remove('ownership-dock--header');
  dock.hidden = false;
  dock.setAttribute('aria-hidden', 'false');
}

function setOwnershipControlsExpandedForEarth(expanded = true) {
  const dock = document.getElementById('ownershipDock');
  if (!dock) return;
  const groups = dock.querySelectorAll('details.ownership-group');
  groups.forEach((group) => {
    if (expanded) {
      group.setAttribute('open', '');
    } else {
      group.removeAttribute('open');
    }
  });
}

function normalizeResearchDrawPool(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const allowedPools = new Set([
    'standard',
    'youth',
    'lifetime',
    'dedicated_hunter',
    'youth_dedicated_hunter',
    'youth_mature_bull',
    'youth_turkey',
  ]);
  return allowedPools.has(normalized) ? normalized : 'standard';
}

function inferResearchDrawPool(hunt) {
  if (!hunt) return 'standard';
  return normalizeResearchDrawPool(firstNonEmpty(
    hunt.draw_pool,
    hunt.drawPool,
    hunt.draw_pool_type,
    hunt.hunt_pool,
    hunt.hunt_class,
    hunt.huntClass
  ));
}

function normalizeResearchResidency(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '') === 'nonresident'
    ? 'Nonresident'
    : 'Resident';
}

function normalizeResearchPoints(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.round(parsed) : 12;
}

function persistResearchSelectionContext(record) {
  if (!record?.hunt_code) return;
  const payload = {
    ...record,
    huntCode: record.hunt_code,
    source: record.source || 'hunt-builder',
    updated_at: Number(record.updated_at) || Date.now()
  };
  try {
    sessionStorage.setItem('selectedHuntForResearch', JSON.stringify(payload));
  } catch (_) {}
  try {
    localStorage.setItem('selectedHuntForResearch', JSON.stringify(payload));
    localStorage.setItem('selected_hunt_code', payload.hunt_code);
    localStorage.setItem('selected_hunt_research_residency', payload.residency || 'Resident');
    localStorage.setItem('selected_hunt_research_draw_pool', payload.draw_pool || 'standard');
    localStorage.setItem('selected_hunt_research_points', String(payload.selected_points ?? payload.points ?? 12));
  } catch (_) {}
}

function openHuntResearch(huntCode, residency = 'Resident', points = 12, drawPool = 'standard', context = {}) {
  const code = String(huntCode || '').trim().toUpperCase();
  if (!code) return;
  const normalizedResidency = normalizeResearchResidency(residency);
  const normalizedPoints = normalizeResearchPoints(points);
  const normalizedDrawPool = normalizeResearchDrawPool(drawPool);
  const selectedContext = {
    ...context,
    hunt_code: code,
    huntCode: code,
    residency: normalizedResidency,
    selected_points: normalizedPoints,
    points: normalizedPoints,
    draw_pool: normalizedDrawPool,
    updated_at: Date.now(),
    source: 'hunt-builder'
  };

  persistResearchSelectionContext(selectedContext);

  const params = new URLSearchParams({
    hunt_code: code,
    residency: normalizedResidency,
    points: String(normalizedPoints),
    draw_pool: normalizedDrawPool
  });
  window.location.href = `./research.html?${params.toString()}`;
}

function buildBackpackHuntRecord(hunt, residency = 'Resident', points = 12) {
  if (!hunt) return null;
  const huntCode = getHuntCode(hunt);
  if (!huntCode) return null;
  const normalizedResidency = normalizeResearchResidency(residency);
  const normalizedPoints = normalizeResearchPoints(points);
  return {
    hunt_code: huntCode,
    huntCode,
    hunt_name: firstNonEmpty(hunt.hunt_name, getUnitName(hunt), getHuntTitle(hunt), huntCode),
    unit: getUnitName(hunt),
    unit_code: getUnitCode(hunt),
    species: getSpeciesDisplay(hunt),
    sex: getNormalizedSex(hunt),
    weapon: getWeapon(hunt),
    hunt_type: getHuntType(hunt),
    hunt_class: getHuntCategory(hunt),
    residency: normalizedResidency,
    draw_pool: inferResearchDrawPool(hunt),
    selected_points: normalizedPoints,
    points: normalizedPoints,
    boundary_id: getBoundaryId(hunt),
    season_dates: getDates(hunt),
    source: 'hunt-builder',
    updated_at: Date.now()
  };
}

function saveHuntToBackpack(hunt, residency = 'Resident', points = 12) {
  const record = buildBackpackHuntRecord(hunt, residency, points);
  if (!record) return null;
  window.UOGA_UI?.recordRecentHunt?.(record);
  if (window.UOGA_UI?.getBasket && window.UOGA_UI?.setBasket) {
    const currentBasket = window.UOGA_UI.getBasket();
    const nextBasket = [
      record,
      ...currentBasket.filter(item => safe(item?.hunt_code).trim().toUpperCase() !== safe(record.hunt_code).trim().toUpperCase())
    ];
    window.UOGA_UI.setBasket(nextBasket);
  }
  window.UOGA_UI?.setSelectedHuntCode?.(record.hunt_code);
  return record;
}

function saveHuntAndOpenResearch(hunt, residency = 'Resident', points = 12) {
  const record = saveHuntToBackpack(hunt, residency, points);
  const huntCode = record?.hunt_code || getHuntCode(hunt);
  if (!huntCode) return;
  openHuntResearch(huntCode, record?.residency || residency, record?.selected_points ?? points, record?.draw_pool || inferResearchDrawPool(hunt), record || {});
}

function openCompareHunts(hunt, residency = 'Resident', points = 12) {
  const record = saveHuntToBackpack(hunt, residency, points);
  if (!record) return;
  const trayShell = document.querySelector('.uoga-backpack-shell');
  const trayToggle = document.querySelector('.uoga-backpack-toggle');
  if (trayToggle && (!trayShell || !trayShell.classList.contains('is-open'))) {
    trayToggle.click();
  }
  const basketPanel = document.getElementById('huntBasket');
  const compareTarget = basketPanel || document.querySelector('.uoga-backpack-toggle');
  compareTarget?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
  if (basketPanel) {
    basketPanel.classList.add('jump-flash');
    window.setTimeout(() => basketPanel.classList.remove('jump-flash'), 900);
  }
  updateStatus(`${record.hunt_code} saved. Compare hunts in Hunt Backpack.`);
}

function openOutfitterMatches(hunt) {
  if (!hunt) return;
  const huntKey = getHuntRecordKey(hunt);
  const selectedKey = selectedHunt ? getHuntRecordKey(selectedHunt) : '';
  if (!selectedHunt || huntKey !== selectedKey) {
    updateSelectedHunt(hunt);
  } else {
    renderOutfitters();
  }
  const outfitterPanel = document.getElementById('outfitterResults')?.closest('.rightbar-section') || document.getElementById('outfitterResults');
  outfitterPanel?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  updateStatus(`Outfitter matches loaded for ${getHuntCode(hunt) || 'selected hunt'}.`);
}

// --- DATA NORMALIZATION ---
function normalizeSpeciesLabel(value) {
  const text = safe(value).trim().toLowerCase();
  if (!text) return '';
  if (text === 'mule deer' || text === 'deer') return 'Deer';
  if (text.includes('desert') && text.includes('bighorn')) return 'Desert Bighorn Sheep';
  if (text.includes('rocky') && text.includes('bighorn')) return 'Rocky Mountain Bighorn Sheep';
  if (text === 'bighorn sheep') {
    return 'Bighorn Sheep';
  }
  return titleCaseWords(text);
}

function inferBighornSpecies(hunt) {
  const code = safe(getHuntCode(hunt)).toUpperCase();
  const title = safe(getHuntTitle(hunt)).toLowerCase();
  const rawSpecies = safe(firstNonEmpty(hunt.species, hunt.Species)).toLowerCase();
  const haystack = `${title} ${rawSpecies}`;
  if (code.startsWith('DS') || haystack.includes('desert bighorn')) return 'Desert Bighorn Sheep';
  if (code.startsWith('RS') || code.startsWith('RE') || haystack.includes('rocky mountain bighorn')) return 'Rocky Mountain Bighorn Sheep';
  return 'Bighorn Sheep';
}

function getSpeciesDisplayList(h) {
  const rawSpecies = safe(firstNonEmpty(h.species, h.Species));
  const normalized = rawSpecies.split(',').map(normalizeSpeciesLabel).filter(Boolean);
  const resolved = normalized.map(species => species === 'Bighorn Sheep' ? inferBighornSpecies(h) : species);
  return Array.from(new Set(resolved));
}
function getSpeciesDisplay(h) { return getSpeciesDisplayList(h)[0] || ''; }

function getNormalizedSex(valueOrHunt) {
  const raw = typeof valueOrHunt === 'string' ? safe(valueOrHunt).trim() : firstNonEmpty(valueOrHunt.sex, valueOrHunt.Sex);
  const hunt = typeof valueOrHunt === 'string' ? null : valueOrHunt;
  const val = raw.toLowerCase();
  const species = hunt ? getSpeciesDisplay(hunt) : '';
  if (val.includes('choice')) return "Hunter's Choice";
  if (val.includes('either')) return 'Either Sex';
  if (val === 'ewe') return 'Ewe';
  if ((val === 'doe' || val === 'cow' || val.includes('antlerless')) && species === 'Rocky Mountain Bighorn Sheep') return 'Ewe';
  if ((val === 'doe' || val === 'cow' || val.includes('antlerless')) && species === 'Desert Bighorn Sheep') return 'Ram';
  if (val === 'doe' || val === 'cow' || val.includes('antlerless')) return 'Antlerless';
  if (val.includes('bearded')) return 'Bearded';
  if (val.includes('ram')) return 'Ram';
  if (val.includes('buck')) return 'Buck';
  if (val.includes('bull')) return 'Bull';
  if (val.includes('male only') && hunt) {
    if (species === 'Moose') return 'Bull';
    if (species === 'Rocky Mountain Bighorn Sheep') return 'Ram';
    if (species === 'Desert Bighorn Sheep') return 'Ram';
  }
  return titleCaseWords(raw) || 'All';
}

function getHuntCode(h) { return firstNonEmpty(h.huntCode, h.hunt_code, h.HuntCode, h.code); }
function getHuntTitle(h) { return firstNonEmpty(h.title, h.Title, h.huntTitle, getHuntCode(h)); }
function getUnitCode(h) { return firstNonEmpty(h.unitCode, h.unit_code, h.UnitCode); }
function getUnitName(h) { return firstNonEmpty(h.unitName, h.unit_name, h.UnitName, h.dwr_unit_name, h.DwrUnitName); }
function getBoundaryNamesForHunt(h) {
  const code = safe(getUnitCode(h)).trim();
  const unitName = safe(getUnitName(h)).trim();
  const strippedUnitName = unitName.replace(/\s*\((?:conservation|private lands only|select areas only)\)\s*$/i, '').trim();
  const officialNames = Array.isArray(h?.officialBoundaryNames) ? h.officialBoundaryNames : [];
  const boundaryNames = Array.isArray(h?.boundaryNames) ? h.boundaryNames : [];
  const externalBoundaryNames = Array.isArray(h?.externalBoundaryNames) ? h.externalBoundaryNames : [];
  const base = [unitName, strippedUnitName, ...boundaryNames, ...officialNames, ...externalBoundaryNames];
  const overrides = Array.isArray(HUNT_BOUNDARY_NAME_OVERRIDES[code]) ? HUNT_BOUNDARY_NAME_OVERRIDES[code] : [];
  return [...new Set([...base, ...overrides].map(v => safe(v).trim()).filter(Boolean))];
}

function isCompositeBoundaryId(value) {
  const id = safe(value).trim();
  if (!id) return false;
  return !/^\d+$/.test(id);
}

function getCompositeMemberBoundaryIds(boundaryId) {
  const normalized = safe(boundaryId).trim();
  return normalized ? (compositeBoundaryMembersByCompositeId.get(normalized) || []) : [];
}

function getResolvedBoundaryIdsForHunt(hunt) {
  const huntCode = normalizeHuntCodeFromResolver(getHuntCode(hunt));
  const manifestRow = huntCode ? boundaryManifestByHuntCode.get(huntCode) : null;

  const resolvedRaw = firstNonEmpty(
    hunt?.resolvedBoundaryIds,
    hunt?.resolved_boundary_ids,
    hunt?.resolvedFeatureIds,
    hunt?.resolved_feature_ids
  );
  const resolved = parseBoundaryIdCandidates(resolvedRaw)
    .map(id => safe(id).trim())
    .filter(Boolean);
  if (resolved.length) return [...new Set(resolved)];
  const manifestBoundaryId = safe(normalizeBoundaryIdFromResolver(firstNonEmpty(
    manifestRow?.dwr_boundary_id,
    manifestRow?.boundary_id,
    manifestRow?.boundaryId,
    manifestRow?.BoundaryID,
  ))).trim();
  if (manifestBoundaryId) return [manifestBoundaryId];
  const memberIdsFromManifest = parseBoundaryIdListFromResolver(firstNonEmpty(
    manifestRow?.dwr_member_boundary_ids,
    manifestRow?.member_boundary_ids,
    manifestRow?.memberBoundaryIds,
  ))
    .map(id => safe(normalizeBoundaryIdFromResolver(id)).trim())
    .filter(Boolean);
  if (memberIdsFromManifest.length) return [...new Set(memberIdsFromManifest)];
  // If manifest/display-boundary mapping exists but no explicit DWR ID, do not
  // fall back to legacy synthetic boundary IDs from hunt records.
  if (manifestRow) return [];
  const boundaryId = safe(getBoundaryId(hunt)).trim();
  return boundaryId ? [boundaryId] : [];
}

function buildBoundaryMatcher(hunts) {
  const boundaryIds = new Set();
  const addBoundaryId = (value) => {
    const normalizedId = safe(value).trim();
    if (!normalizedId) return;
    boundaryIds.add(normalizedId);
    if (isCompositeBoundaryId(normalizedId)) {
      getCompositeMemberBoundaryIds(normalizedId).forEach(memberId => boundaryIds.add(memberId));
    }
  };
  hunts.forEach(hunt => {
    getResolvedBoundaryIdsForHunt(hunt).forEach(addBoundaryId);
  });
  return {
    matches(featureBoundaryIds) {
      const ids = Array.isArray(featureBoundaryIds) ? featureBoundaryIds : [featureBoundaryIds];
      for (const id of ids) {
        const normalizedId = safe(id).trim();
        if (normalizedId && boundaryIds.has(normalizedId)) return true;
      }
      return false;
    }
  };
}

function parseBoundaryIdCandidates(value) {
  if (Array.isArray(value)) {
    return value
      .flatMap(parseBoundaryIdCandidates)
      .map(v => safe(v).trim())
      .filter(Boolean);
  }
  if (value == null) return [];
  const text = safe(value).trim();
  if (!text) return [];
  if ((text.startsWith('[') && text.endsWith(']')) || (text.startsWith('{') && text.endsWith('}'))) {
    try {
      return parseBoundaryIdCandidates(JSON.parse(text));
    } catch (_) {
      // Fall through to delimiter parsing.
    }
  }
  if (/[,\|;\/]/.test(text)) {
    return text
      .split(/[,\|;\/]/)
      .map(v => safe(v).trim())
      .filter(Boolean);
  }
  return [text];
}

function getFeatureBoundaryCandidateIds(props = {}) {
  const ids = new Set();
  const add = (value) => {
    parseBoundaryIdCandidates(value).forEach(id => {
      const normalized = safe(id).trim();
      if (normalized) ids.add(normalized);
    });
  };
  add(props?.BoundaryID);
  add(props?.Boundary_Id);
  add(props?.BOUNDARYID);
  add(props?.boundary_id);
  // Composite boundary files encode unit memberships in member_boundary_ids.
  add(props?.member_boundary_ids);
  add(props?.memberBoundaryIds);
  return [...ids];
}

function getDataFeatureBoundaryCandidateIds(feature) {
  if (!feature?.getProperty) return [];
  return getFeatureBoundaryCandidateIds({
    BoundaryID: feature.getProperty('BoundaryID'),
    Boundary_Id: feature.getProperty('Boundary_Id'),
    BOUNDARYID: feature.getProperty('BOUNDARYID'),
    boundary_id: feature.getProperty('boundary_id'),
    member_boundary_ids: feature.getProperty('member_boundary_ids'),
    memberBoundaryIds: feature.getProperty('memberBoundaryIds')
  });
}

function normalizeRelativeGeoPath(pathValue) {
  const raw = safe(pathValue).trim();
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith('./')) return raw;
  return `./${raw.replace(/^\/+/, '')}`;
}

function buildBoundaryFeatureIndexFromGeoJson(geojson) {
  return indexBoundaryFeaturesFromResolver(geojson || { type: 'FeatureCollection', features: [] });
}

async function loadBoundaryManifestRuntime() {
  if (!boundaryManifestLoadPromise) {
    boundaryManifestLoadPromise = (async () => {
      const result = await loadBoundaryManifestFromResolver({
        sources: [
          ...(Array.isArray(DISPLAY_BOUNDARY_INDEX_SOURCES) ? DISPLAY_BOUNDARY_INDEX_SOURCES : []),
          ...(Array.isArray(BOUNDARY_MANIFEST_SOURCES) ? BOUNDARY_MANIFEST_SOURCES : []),
        ],
        fetchJson,
      });
      boundaryManifestByHuntCode = result?.byHuntCode instanceof Map ? result.byHuntCode : new Map();
      boundaryManifestByMergedBoundaryId = result?.byMergedBoundaryId instanceof Map ? result.byMergedBoundaryId : new Map();
      boundaryManifestByDisplayBoundaryId = new Map();
      if (Array.isArray(result?.rows)) {
        result.rows.forEach((row) => {
          const displayBoundaryId = safe(row?.display_boundary_id).trim();
          if (displayBoundaryId) boundaryManifestByDisplayBoundaryId.set(displayBoundaryId, row);
        });
      }
      boundaryManifestSourceUsed = safe(result?.sourceUsed).trim();
      if (result?.error) {
        console.warn('Boundary manifest load failed; using legacy boundary mapping fallback.', result.error);
      } else if (boundaryManifestByHuntCode.size) {
        console.log(`Loaded boundary manifest rows: ${boundaryManifestByHuntCode.size} (${boundaryManifestSourceUsed || 'unknown source'})`);
      }
      return {
        byHuntCode: boundaryManifestByHuntCode,
        byMergedBoundaryId: boundaryManifestByMergedBoundaryId,
        byDisplayBoundaryId: boundaryManifestByDisplayBoundaryId,
        sourceUsed: boundaryManifestSourceUsed,
      };
    })();
  }
  return boundaryManifestLoadPromise;
}

function getBoundaryFeatureIndex() {
  return buildBoundaryFeatureIndexFromGeoJson(finalizedBoundaryGeoJson || huntBoundaryGeoJson);
}

function resolveBoundaryForHuntRuntime(hunt) {
  const resolved = resolveBoundaryForHuntFromResolver(
    hunt,
    boundaryManifestByHuntCode,
    getBoundaryFeatureIndex(),
  );
  return resolved || { status: 'unavailable' };
}

function applyBoundaryManifestToHunts(records) {
  records.forEach((record) => {
    const resolved = resolveBoundaryForHuntRuntime(record);
    const memberIds = Array.isArray(resolved?.dwr_member_boundary_ids)
      ? resolved.dwr_member_boundary_ids.map((id) => safe(id).trim()).filter(Boolean)
      : [];
    const normalizedBoundaryId = safe(resolved?.dwr_boundary_id).trim();
    const resolvedIds = memberIds.length ? memberIds : (normalizedBoundaryId ? [normalizedBoundaryId] : []);
    const displayBoundaryId = safe(resolved?.display_boundary_id).trim();
    const selectedBoundaryId = safe(resolved?.boundary_id || displayBoundaryId || normalizedBoundaryId).trim();

    if (displayBoundaryId) {
      record.display_boundary_id = displayBoundaryId;
      record.displayBoundaryId = displayBoundaryId;
    }
    if (selectedBoundaryId) {
      record.boundary_id = selectedBoundaryId;
      record.boundaryId = selectedBoundaryId;
    }
    record.dwr_boundary_id = normalizedBoundaryId || null;
    record.dwrBoundaryId = normalizedBoundaryId || null;
    record.dwr_member_boundary_ids = memberIds;
    record.dwrMemberBoundaryIds = memberIds;

    if (resolvedIds.length) {
      record.resolvedBoundaryIds = resolvedIds;
      record.resolved_boundary_ids = resolvedIds;
    }

    if (resolved?.boundary_geojson_path) {
      record.boundary_geojson_path = resolved.boundary_geojson_path;
      record.boundaryGeojsonPath = resolved.boundary_geojson_path;
    }
    if (resolved?.boundary_kmz_path) {
      record.boundary_kmz_path = resolved.boundary_kmz_path;
      record.boundaryKmzPath = resolved.boundary_kmz_path;
    }
    if (resolved?.boundary_kml_path) {
      record.boundary_kml_path = resolved.boundary_kml_path;
      record.boundaryKmlPath = resolved.boundary_kml_path;
    }
    if (resolved?.merged_boundary_id) {
      record.merged_boundary_id = resolved.merged_boundary_id;
      record.mergedBoundaryId = resolved.merged_boundary_id;
    }
    if (resolved?.boundary_geometry_type) {
      record.boundary_geometry_type = resolved.boundary_geometry_type;
      record.boundaryGeometryType = resolved.boundary_geometry_type;
    }
    if (resolved?.dwr_boundary_link && !safe(getBoundaryLink(record)).trim()) {
      record.boundaryLink = resolved.dwr_boundary_link;
      record.dwr_boundary_link = resolved.dwr_boundary_link;
    }
    if (memberIds.length) {
      record.member_boundary_ids = memberIds;
      record.memberBoundaryIds = memberIds;
      record.member_boundary_count = memberIds.length;
      record.memberBoundaryCount = memberIds.length;
    }
    record.geometry_status = resolved?.status === 'unavailable' ? 'unavailable' : 'mapped';
  });
}

function clearSelectedBoundaryFallbackLayer() {
  if (selectedBoundaryFallbackLayer) {
    selectedBoundaryFallbackLayer.setMap(null);
    selectedBoundaryFallbackLayer = null;
  }
}

function drawSelectedBoundaryFallbackFeatureCollection(featureCollection) {
  clearSelectedBoundaryFallbackLayer();
  if (!googleBaselineMap) return;
  const features = Array.isArray(featureCollection?.features) ? featureCollection.features : [];
  if (!features.length) return;
  selectedBoundaryFallbackLayer = new google.maps.Data({ map: googleBaselineMap });
  selectedBoundaryFallbackLayer.addGeoJson({ type: 'FeatureCollection', features });
  selectedBoundaryFallbackLayer.setStyle({
    visible: true,
    strokeColor: '#c84f00',
    strokeWeight: 4,
    fillColor: '#ff8a3d',
    fillOpacity: 0.22,
  });
}

async function applySelectedHuntBoundaryResolution(hunt) {
  clearSelectedBoundaryFallbackLayer();
  if (!hunt || !googleBaselineMap) return;
  const resolved = resolveBoundaryForHuntRuntime(hunt);
  const directPath = normalizeRelativeGeoPath(resolved?.boundary_geojson_path);
  if (directPath) {
    try {
      const geojson = await fetchGeoJson(directPath);
      drawSelectedBoundaryFallbackFeatureCollection(geojson);
      return;
    } catch (error) {
      console.warn(`Direct boundary GeoJSON load failed for ${safe(getHuntCode(hunt))}: ${directPath}`, error);
    }
  }
  const fallbackCollection = getFallbackFeatureCollectionForResolvedBoundary(hunt, resolved);
  if (fallbackCollection?.features?.length) {
    drawSelectedBoundaryFallbackFeatureCollection(fallbackCollection);
    return;
  }
  if (resolved?.feature_collection?.features?.length) {
    drawSelectedBoundaryFallbackFeatureCollection(resolved.feature_collection);
  }
}

function getBoundaryDisplaySummary(hunt) {
  const resolved = resolveBoundaryForHuntRuntime(hunt);
  const huntNumber = safe(getHuntCode(hunt)).trim().toUpperCase();
  const memberIds = Array.isArray(resolved.dwr_member_boundary_ids) ? resolved.dwr_member_boundary_ids : [];
  if (resolved.status === 'mapped' && safe(resolved.merged_boundary_id).trim()) {
    const memberCount = memberIds.length;
    return {
      line: `Boundary: Hunt Number ${huntNumber || 'Unavailable'}${memberCount ? ` (${memberCount} mapped areas)` : ''}`,
      kmzPath: normalizeRelativeGeoPath(resolved.boundary_kmz_path),
    };
  }
  if (resolved.status === 'mapped' && safe(resolved.dwr_boundary_id).trim()) {
    return {
      line: `Boundary: Hunt Number ${huntNumber || 'Unavailable'}`,
      kmzPath: normalizeRelativeGeoPath(resolved.boundary_kmz_path),
    };
  }
  if (resolved.status === 'fallback_member_features') {
    const memberCount = memberIds.length;
    return {
      line: `Boundary: Hunt Number ${huntNumber || 'Unavailable'}${memberCount ? ` (${memberCount} mapped areas)` : ''}`,
      kmzPath: normalizeRelativeGeoPath(resolved.boundary_kmz_path),
    };
  }
  return {
    line: 'Boundary: Boundary unavailable',
    kmzPath: normalizeRelativeGeoPath(resolved.boundary_kmz_path),
  };
}

function getDisplayBoundaryIdForHunt(hunt) {
  const resolved = resolveBoundaryForHuntRuntime(hunt);
  const displayBoundaryId = safe(resolved?.display_boundary_id).trim();
  if (displayBoundaryId) return displayBoundaryId;
  const numericId = safe(resolved?.dwr_boundary_id || resolved?.boundary_id).trim();
  if (numericId) return numericId;
  const huntCode = safe(getHuntCode(hunt)).trim().toUpperCase();
  return huntCode ? `VERIFIED_${huntCode}_2026` : '';
}

function buildIndependentBoundaryTargets(hunts) {
  const targetsByDisplayId = new Map();
  (Array.isArray(hunts) ? hunts : []).forEach((hunt) => {
    const resolved = resolveBoundaryForHuntRuntime(hunt);
    const displayBoundaryId = getDisplayBoundaryIdForHunt(hunt);
    if (!displayBoundaryId) return;
    const existing = targetsByDisplayId.get(displayBoundaryId) || {
      displayBoundaryId,
      hunts: [],
      geojsonPath: '',
      featureCollection: null,
    };
    existing.hunts.push(hunt);
    if (!existing.geojsonPath) {
      existing.geojsonPath = normalizeRelativeGeoPath(resolved?.boundary_geojson_path);
    }
    if (!existing.featureCollection && resolved?.feature_collection?.features?.length) {
      existing.featureCollection = resolved.feature_collection;
    }
    targetsByDisplayId.set(displayBoundaryId, existing);
  });
  return Array.from(targetsByDisplayId.values());
}

function getFallbackFeatureCollectionForResolvedBoundary(hunt, resolved) {
  const featureIndex = getBoundaryFeatureIndex();
  const byBoundaryId = featureIndex?.byBoundaryId instanceof Map ? featureIndex.byBoundaryId : null;
  if (!byBoundaryId?.size) return null;

  const candidateIds = [];
  const addCandidates = (value) => {
    parseBoundaryIdCandidates(value).forEach((id) => {
      const normalized = safe(id).trim();
      if (normalized) candidateIds.push(normalized);
    });
  };

  addCandidates(resolved?.dwr_member_boundary_ids);
  addCandidates(resolved?.member_boundary_ids);
  addCandidates(resolved?.dwr_boundary_id);
  addCandidates(resolved?.boundary_id);
  addCandidates(getBoundaryId(hunt));
  addCandidates(hunt?.boundary_id);
  addCandidates(hunt?.boundaryId);
  addCandidates(hunt?.BoundaryID);

  const uniqueIds = [...new Set(candidateIds)];
  if (!uniqueIds.length) return null;

  const features = [];
  const seen = new Set();
  uniqueIds.forEach((id) => {
    const candidateFeatures = byBoundaryId.get(id);
    if (!Array.isArray(candidateFeatures) || !candidateFeatures.length) return;
    candidateFeatures.forEach((feature) => {
      const props = feature?.properties || {};
      const featureId = safe(firstNonEmpty(props.BoundaryID, props.Boundary_Id, props.BOUNDARYID, props.boundary_id)).trim();
      const dedupeKey = `${id}|${featureId}|${feature?.geometry?.type || ''}`;
      if (seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      features.push(feature);
    });
  });

  return features.length ? { type: 'FeatureCollection', features } : null;
}

async function getIndependentBoundaryFeatureCollection(target) {
  if (!target) return null;
  if (target.featureCollection?.features?.length) return target.featureCollection;
  if (Array.isArray(target.hunts) && target.hunts.length) {
    for (const hunt of target.hunts) {
      const resolved = resolveBoundaryForHuntRuntime(hunt);
      const fallbackCollection = getFallbackFeatureCollectionForResolvedBoundary(hunt, resolved);
      if (fallbackCollection?.features?.length) return fallbackCollection;
    }
  }
  const geojsonPath = safe(target.geojsonPath).trim();
  if (!geojsonPath) return null;
  if (independentBoundaryGeoJsonCache.has(geojsonPath)) {
    return independentBoundaryGeoJsonCache.get(geojsonPath);
  }
  const request = fetchGeoJson(geojsonPath)
    .then((geojson) => geojson)
    .catch((error) => {
      independentBoundaryGeoJsonCache.delete(geojsonPath);
      throw error;
    });
  independentBoundaryGeoJsonCache.set(geojsonPath, request);
  return request;
}

function clearIndependentBoundaryLayer() {
  if (independentBoundaryLayer) {
    independentBoundaryLayer.setMap(null);
    independentBoundaryLayer = null;
  }
}

function ensureIndependentBoundaryLayer() {
  if (!googleBaselineMap) return null;
  if (independentBoundaryLayer) return independentBoundaryLayer;
  independentBoundaryLayer = new google.maps.Data({ map: googleBaselineMap });
  independentBoundaryLayer.addListener('click', (event) => {
    openBoundaryPopup(event.feature, event.latLng);
  });
  return independentBoundaryLayer;
}

async function refreshIndependentBoundaryLayer() {
  const token = ++independentBoundaryRefreshToken;
  const showBoundaries = shouldShowHuntBoundaries();
  const showAllUnits = shouldShowAllHuntUnits();
  const filtered = getDisplayHunts();
  const huntsToRender = selectedHunt
    ? [...filtered, selectedHunt]
    : filtered;
  const shouldRender = showBoundaries && !showAllUnits && huntsToRender.length > 0;
  if (!shouldRender) {
    clearIndependentBoundaryLayer();
    return;
  }

  const targets = buildIndependentBoundaryTargets(huntsToRender);
  if (!targets.length) {
    clearIndependentBoundaryLayer();
    return;
  }

  const loaded = await Promise.all(
    targets.map(async (target) => {
      try {
        const fc = await getIndependentBoundaryFeatureCollection(target);
        return { target, featureCollection: fc };
      } catch (error) {
        console.warn(`Independent boundary load failed for ${target.displayBoundaryId}`, error);
        return { target, featureCollection: null };
      }
    }),
  );
  if (token !== independentBoundaryRefreshToken) return;

  const layer = ensureIndependentBoundaryLayer();
  if (!layer) return;

  clearIndependentBoundaryLayer();
  const nextLayer = ensureIndependentBoundaryLayer();
  if (!nextLayer) return;

  let addedFeatureCount = 0;
  loaded.forEach(({ target, featureCollection }) => {
    const features = Array.isArray(featureCollection?.features) ? featureCollection.features : [];
    if (!features.length) return;
    const huntCodes = [...new Set(target.hunts.map((hunt) => safe(getHuntCode(hunt)).trim().toUpperCase()).filter(Boolean))];
    const clonedFeatures = features.map((feature) => {
      const props = { ...(feature?.properties || {}) };
      props.UOGA_DISPLAY_BOUNDARY_ID = target.displayBoundaryId;
      props.UOGA_HUNT_CODES = huntCodes.join('|');
      return {
        ...feature,
        properties: props,
      };
    });
    nextLayer.addGeoJson({ type: 'FeatureCollection', features: clonedFeatures });
    addedFeatureCount += clonedFeatures.length;
  });

  const selectedDisplayBoundaryId = selectedHunt ? getDisplayBoundaryIdForHunt(selectedHunt) : '';
  nextLayer.setStyle((feature) => {
    const featureDisplayBoundaryId = safe(feature.getProperty('UOGA_DISPLAY_BOUNDARY_ID')).trim();
    const isSelected = selectedDisplayBoundaryId && featureDisplayBoundaryId === selectedDisplayBoundaryId;
    return {
      visible: true,
      strokeColor: isSelected ? '#c84f00' : '#3653b3',
      strokeWeight: isSelected ? 4 : 1.8,
      fillColor: isSelected ? '#ff8a3d' : '#3653b3',
      fillOpacity: isSelected ? 0.22 : 0.08,
      zIndex: isSelected ? 250 : 200,
    };
  });

  if (!addedFeatureCount) {
    clearIndependentBoundaryLayer();
  }
}

let officialBoundaryLookupPromise = null;
async function loadOfficialBoundaryLookup() {
  if (!officialBoundaryLookupPromise) {
    officialBoundaryLookupPromise = loadOfficialBoundaryLookupFromData({
      OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
      normalizeHuntCode,
      safe
    });
  }
  return officialBoundaryLookupPromise;
}

async function applyOfficialBoundaryMappings(records) {
  return applyOfficialBoundaryMappingsFromData(records, {
    OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
    normalizeHuntCode,
    getHuntCode,
    getBoundaryId,
    safe
  });
}

async function loadCompositeBoundaryLookup() {
  if (!compositeBoundaryLookupPromise) {
    compositeBoundaryLookupPromise = (async () => {
      const lookup = new Map();
      const sources = Array.isArray(COMPOSITE_BOUNDARY_SOURCES) ? COMPOSITE_BOUNDARY_SOURCES : [];
      if (!sources.length) {
        compositeBoundaryMembersByCompositeId = lookup;
        return lookup;
      }
      try {
        const geojson = await fetchFirstGeoJson(sources);
        const features = Array.isArray(geojson?.features) ? geojson.features : [];
        features.forEach(feature => {
          const props = feature?.properties || {};
          const compositeId = safe(firstNonEmpty(props.BoundaryID, props.boundary_id)).trim();
          if (!compositeId) return;
          const members = parseBoundaryIdCandidates(firstNonEmpty(props.member_boundary_ids, props.memberBoundaryIds))
            .map(id => safe(id).trim())
            .filter(Boolean);
          if (members.length) lookup.set(compositeId, [...new Set(members)]);
        });
      } catch (error) {
        console.warn('Composite boundary lookup unavailable; continuing without member expansion.', error);
      }
      compositeBoundaryMembersByCompositeId = lookup;
      return lookup;
    })();
  }
  return compositeBoundaryLookupPromise;
}

function getRequiredUsfsForestsForHunt(hunt) {
  const boundaryKeys = getBoundaryNamesForHunt(hunt).map(normalizeBoundaryKey);
  const required = new Set();
  boundaryKeys.forEach(key => {
    if (!key) return;
    if (
      key.includes('manti') ||
      key.includes('san rafael') ||
      key.includes('la sal') ||
      key.includes('dolores') ||
      key.includes('ferron') ||
      key.includes('price canyon') ||
      key.includes('gordon creek') ||
      key.includes('mohrland') ||
      key.includes('horn mtn') ||
      key.includes('moab') ||
      key.includes('monticello')
    ) {
      required.add('manti-la-sal');
    }
    if (
      key.includes('fishlake') ||
      key.includes('thousand lakes') ||
      key.includes('fillmore') ||
      key.includes('monroe') ||
      key.includes('beaver') ||
      key.includes('mt dutton') ||
      key.includes('plateau')
    ) {
      required.add('fishlake');
    }
    if (key.includes('nebo')) {
      required.add('uinta-wasatch-cache');
    }
  });
  return [...required];
}
function getUnitValue(h) { return firstNonEmpty(getUnitCode(h), getUnitName(h)); }
function getBoundaryId(h) {
  return firstNonEmpty(
    h.boundaryIdNumeric,
    h.boundary_id_numeric,
    h.boundaryId,
    h.boundaryID,
    h.BoundaryID,
    h.boundary_id,
    h.originalBoundaryId
  );
}
function normalizeHuntCode(value) { return safe(value).trim().toUpperCase(); }
function getHuntRecordKey(h) {
  return [
    normalizeHuntCode(getHuntCode(h)),
    safe(getBoundaryId(h)).trim(),
    safe(getWeapon(h)).trim().toLowerCase(),
    normalizeBoundaryKey(getUnitName(h) || getUnitCode(h))
  ].join('|');
}
function getSelectedHuntKey() {
  return selectedHunt ? getHuntRecordKey(selectedHunt) : '';
}
function normalizeWeaponLabel(raw) {
  const value = safe(raw).trim();
  const lower = value.toLowerCase();
  if (!value) return '';
  if (lower.includes('any legal weapon')) return 'Any Legal Weapon';
  if (lower.includes('extended archery')) return 'Extended Archery';
  if (lower.includes('restricted archery')) return 'Restricted Archery';
  if (lower.includes('restricted muzzleloader')) return 'Restricted Muzzleloader';
  if (lower.includes('restricted multiseason')) return 'Restricted Multiseason';
  if (lower.includes('restricted rifle')) return 'Restricted Rifle';
  if (lower.includes('muzzleloader')) return 'Muzzleloader';
  if (lower.includes('archery')) return 'Archery';
  if (lower.includes('dedicated hunter')) return 'Multiseason';
  if (lower.includes('hamss') || lower.includes('shotgun') || lower.includes('straight-walled')) return 'HAMSS';
  if (lower.includes('multiseason')) return 'Multiseason';
  return value;
}
function getWeapon(h) { return normalizeWeaponLabel(firstNonEmpty(h.weapon, h.Weapon)); }
function weaponMatchesFilter(hunt, selectedWeapon) {
  if (!selectedWeapon || selectedWeapon === 'All') return true;
  const huntWeapon = getWeapon(hunt);
  if (huntWeapon === selectedWeapon) return true;
  if (
    hunt?.syntheticConservationPermit &&
    selectedWeapon === 'Any Legal Weapon' &&
    (huntWeapon === 'Multiseason' || huntWeapon === 'Restricted Multiseason' || huntWeapon === "Hunter's Choice")
  ) {
    return true;
  }
  return false;
}
function normalizeHuntTypeLabel(raw) {
  const value = safe(raw).trim();
  const lower = value.toLowerCase();
  if (!value) return '';
  if (lower.includes('private land only')) return 'Private Land Only';
  if (lower.includes('premium')) return 'Premium Limited Entry';
  if (lower.includes('limited')) return 'Limited Entry';
  if (lower.includes('once-in-a-lifetime')) return 'Once-in-a-Lifetime';
  if (lower.includes('dedicated hunter')) return 'Dedicated Hunter';
  if (lower.includes('management')) return 'Management';
  if (lower.includes('youth')) return 'Youth';
  if (lower.includes('conservation')) return 'Conservation';
  if (lower.includes('cwmu')) return 'CWMU';
  if (lower.includes('antlerless')) return 'Antlerless';
  if (lower.includes('general')) return 'General Season';
  return value;
}
function buildConservationSpeciesKey(species, value) {
  const normalizedSpecies = normalizeBoundaryKey(species);
  const normalizedValue = normalizeBoundaryKey(value);
  if (!normalizedSpecies || !normalizedValue) return '';
  return `${normalizedSpecies}|${normalizedValue}`;
}
function indexConservationPermitAreas(list) {
  conservationPermitAreas = Array.isArray(list) ? list : [];
  conservationPermitAreaCodeSet.clear();
  conservationPermitAreaSpeciesUnitNameSet.clear();
  conservationPermitAreaSpeciesUnitCodeSet.clear();
  conservationPermitAreaAllowedTypeMap.clear();

  conservationPermitAreas.forEach(entry => {
    const species = safe(entry?.species).trim();
    const allowedRawTypes = new Set((Array.isArray(entry?.allowedRawHuntTypes) ? entry.allowedRawHuntTypes : []).map(v => safe(v).trim().toLowerCase()).filter(Boolean));
    (Array.isArray(entry?.huntCodes) ? entry.huntCodes : []).forEach(code => {
      const normalizedCode = normalizeHuntCode(code);
      if (!normalizedCode) return;
      conservationPermitAreaCodeSet.add(normalizedCode);
      if (allowedRawTypes.size) conservationPermitAreaAllowedTypeMap.set(`code|${normalizedCode}`, allowedRawTypes);
    });
    (Array.isArray(entry?.unitNames) ? entry.unitNames : []).forEach(name => {
      const key = buildConservationSpeciesKey(species, name);
      if (!key) return;
      conservationPermitAreaSpeciesUnitNameSet.add(key);
      if (allowedRawTypes.size) conservationPermitAreaAllowedTypeMap.set(`name|${key}`, allowedRawTypes);
    });
    (Array.isArray(entry?.unitCodes) ? entry.unitCodes : []).forEach(code => {
      const key = buildConservationSpeciesKey(species, code);
      if (!key) return;
      conservationPermitAreaSpeciesUnitCodeSet.add(key);
      if (allowedRawTypes.size) conservationPermitAreaAllowedTypeMap.set(`codekey|${key}`, allowedRawTypes);
    });
  });
}
async function loadConservationPermitAreas() {
  try {
    const list = await loadFirstNormalizedList(
      CONSERVATION_PERMIT_AREA_SOURCES,
      json => Array.isArray(json) ? json : [],
      []
    );
    indexConservationPermitAreas(list);
  } catch (error) {
    console.error('Conservation permit area load failed; continuing without conservation register.', error);
    indexConservationPermitAreas([]);
  }
}
async function loadConservationPermitHuntTable() {
  try {
    conservationPermitHuntTable = await loadFirstNormalizedList(
      CONSERVATION_PERMIT_HUNT_TABLE_SOURCES,
      json => Array.isArray(json) ? json : [],
      []
    );
  } catch (error) {
    console.error('Conservation permit hunt table load failed; continuing without synthetic conservation hunts.', error);
    conservationPermitHuntTable = [];
  }
}
function isConservationPermitHunt(h) {
  return !!h?.syntheticConservationPermit;
}
function getHuntType(h) {
  if (h?.syntheticConservationPermit) return 'Conservation';
  const raw = firstNonEmpty(h.huntType, h.HuntType, h.type);
  return normalizeHuntTypeLabel(raw);
}
function normalizeHuntCategoryLabel(raw) {
  const value = safe(raw).trim();
  const lower = value.toLowerCase();
  if (!value) return '';
  if (lower.includes('statewide permit')) return 'Statewide Permit';
  if (lower.includes('private land only')) return 'Private Land Only';
  if (lower.includes('extended archery')) return 'Extended Archery';
  if (lower.includes('premium')) return 'Premium Limited Entry';
  if (lower.includes('limited')) return 'Limited Entry';
  if (lower.includes('cwmu')) return 'CWMU';
  if (lower.includes('youth')) return 'Youth';
  if (lower.includes('conservation')) return 'Conservation';
  if (lower.includes('management')) return 'Management';
  if (lower.includes('spike')) return 'Spike Only';
  if (lower.includes('general bull') || lower.includes('bull elk') || lower.includes('any bull')) return 'General Bull';
  if (lower.includes('antlerless')) return 'Antlerless';
  if (lower.includes('general')) return 'General Season';
  return value;
}
function normalizeSelectionMatrixLabel(value) {
  return safe(value)
    .toLowerCase()
    .replace(/o\.?\s*i\.?\s*l\.?/g, 'once in a lifetime')
    .replace(/once[-\s]*in[-\s]*a[-\s]*lifetime/g, 'once in a lifetime')
    .replace(/private lands only/g, 'private land only')
    .replace(/general-season/g, 'general season')
    .replace(/limited-entry/g, 'limited entry')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
function huntClassFurtherDiversifies(huntType, huntClass) {
  const normalizedType = normalizeSelectionMatrixLabel(huntType);
  const normalizedClass = normalizeSelectionMatrixLabel(huntClass);
  if (!normalizedClass) return false;
  if (normalizedClass === normalizedType) return false;
  return true;
}
function getHuntCategory(h) {
  if (h?.syntheticConservationPermit) {
    const syntheticCategory = normalizeHuntCategoryLabel(firstNonEmpty(h.huntCategory, h.HuntCategory, h.category, 'Conservation'));
    return huntClassFurtherDiversifies(getHuntType(h), syntheticCategory) ? syntheticCategory : '';
  }
  const raw = firstNonEmpty(h.huntCategory, h.HuntCategory, h.category);
  const normalized = normalizeHuntCategoryLabel(raw);
  const huntType = getHuntType(h);
  const species = getSpeciesDisplay(h);
  const sex = getNormalizedSex(h);
  const haystack = `${safe(raw)} ${getHuntTitle(h)} ${getUnitName(h)}`.toLowerCase();

  if (species === 'Elk' && sex === 'Bull') {
    if (huntType === 'Limited Entry') {
      if (
        haystack.includes('bull elk') ||
        haystack.includes('mature bull') ||
        haystack.includes('any bull') ||
        normalized === 'General Bull' ||
        normalized === 'General Season'
      ) {
        return 'Mature Bull';
      }
    }

    if (huntType === 'General Season') {
      if (haystack.includes('spike')) return 'Spike Only';
      if (
        haystack.includes('bull elk') ||
        haystack.includes('any bull') ||
        haystack.includes('hunters choice') ||
        normalized === 'General Bull'
      ) {
        return 'General Bull';
      }
    }
  }

  if (!huntClassFurtherDiversifies(huntType, normalized)) return '';
  return normalized;
}
function getHuntCodeDigits(h) {
  const code = normalizeHuntCode(getHuntCode(h));
  const match = code.match(/(\d{4})$/);
  return match ? match[1] : '';
}
function isPrivateLandOnlyRecord(h) {
  const huntType = safe(getHuntType(h)).toLowerCase();
  const huntCategory = safe(getHuntCategory(h)).toLowerCase();
  const dates = safe(getDates(h)).toLowerCase();
  const unitName = safe(getUnitName(h)).toLowerCase();
  const title = safe(getHuntTitle(h)).toLowerCase();
  return (
    huntType.includes('private land') ||
    huntCategory.includes('private land') ||
    dates.includes('private land') ||
    unitName.includes('private land') ||
    title.includes('private land')
  );
}
function isLegitPrivateLandException(h) {
  const species = safe(getSpeciesDisplay(h)).toLowerCase();
  const sex = safe(getNormalizedSex(h)).toLowerCase();
  const weapon = safe(getWeapon(h)).toLowerCase();
  const huntType = safe(getHuntType(h)).toLowerCase();
  const title = safe(getHuntTitle(h)).toLowerCase();
  return (
    species === 'elk' &&
    sex === 'antlerless' &&
    weapon === 'any legal weapon' &&
    (huntType.includes('private land') || title.includes('private land')) &&
    (
      huntType.includes('otc') ||
      huntType.includes('over-the-counter') ||
      title.includes('otc') ||
      title.includes('over-the-counter')
    )
  );
}
function getPrivateTwinKey(h) {
  return [
    getHuntCodeDigits(h),
    normalizeBoundaryKey(getSpeciesDisplay(h)),
    normalizeBoundaryKey(getNormalizedSex(h)),
    normalizeBoundaryKey(getWeapon(h)),
    normalizeBoundaryKey(getUnitName(h)),
    normalizeBoundaryKey(getHuntType(h).replace(/private lands? only/gi, '').trim())
  ].join('|');
}
function buildPublicTwinKeySet(records) {
  const keys = new Set();
  records.forEach(record => {
    if (isPrivateLandOnlyRecord(record)) return;
    const digits = getHuntCodeDigits(record);
    if (!digits) return;
    keys.add(getPrivateTwinKey(record));
  });
  return keys;
}
function buildSyntheticConservationPermitHunts(records) {
  void records;
  if (!Array.isArray(conservationPermitHuntTable) || !conservationPermitHuntTable.length) return [];

  return conservationPermitHuntTable.map((row, index) => {
    const boundaryIds = [...new Set((Array.isArray(row?.boundaryIds) ? row.boundaryIds : []).map(id => safe(id).trim()).filter(Boolean))];
    const boundaryNames = [...new Set((Array.isArray(row?.unitNames) ? row.unitNames : [row?.area]).map(v => safe(v).trim()).filter(Boolean))];
    const species = firstNonEmpty(row?.species);
    const area = firstNonEmpty(row?.area, boundaryNames[0], row?.matchedRegisterLabel);
    const unitCode = firstNonEmpty(row?.unitCode, normalizeBoundaryKey(area), `conservation-permit-${index + 1}`);
    const huntCode = firstNonEmpty(row?.huntCode, `CP-${normalizeBoundaryKey(species)}-${normalizeBoundaryKey(area)}`).toUpperCase();

    return {
      syntheticConservationPermit: true,
      huntCode,
      species,
      sex: firstNonEmpty(row?.sex),
      huntType: 'Conservation',
      huntCategory: firstNonEmpty(row?.huntClass, 'Conservation'),
      weapon: firstNonEmpty(row?.weapon, row?.condition),
      unitCode,
      unitName: area,
      boundaryId: boundaryIds.length === 1 ? boundaryIds[0] : '',
      boundaryIds,
      officialBoundaryIds: boundaryIds,
      officialBoundaryNames: boundaryNames,
      boundaryNames,
      seasonLabel: 'Conservation Permit Area',
      dates: 'See official conservation permit details',
      title: firstNonEmpty(row?.matchedRegisterLabel, area, `${species} Conservation Permit`),
      source: 'Verified Utah DWR conservation permit table',
      sourceHuntCodes: Array.isArray(row?.sourceHuntCodes) ? row.sourceHuntCodes.slice() : [],
      permitCount: row?.permitCount,
      organizations: Array.isArray(row?.organizations) ? row.organizations.slice() : [],
      averageValue: row?.averageValue
    };
  }).filter(row => Array.isArray(row.boundaryIds) && row.boundaryIds.length);
}
function getDates(h) { return firstNonEmpty(h.seasonLabel, h.seasonDates, h.dates); }
function getBoundaryLink(h) { return firstNonEmpty(h.boundaryLink, h.boundaryURL, h.huntBoundaryLink); }
function getSpeciesHeadingLabel(species) {
  if (species === 'Rocky Mountain Bighorn Sheep') return 'R.M. Bighorn Sheep';
  if (species === 'Desert Bighorn Sheep') return 'Desert Bighorn Sheep';
  return species;
}
function getPermitTotal(hunt) {
  const values = [
    hunt.permitsTotal, hunt.permitTotal, hunt.totalPermits, hunt.quota,
    hunt.residentPermits, hunt.nonresidentPermits, hunt.resident, hunt.nonresident
  ].map(v => Number(v)).filter(v => Number.isFinite(v) && v >= 0);
  if (!values.length) return null;
  if (values.length >= 2 && values[0] !== values[1]) return values[0] + values[1];
  return values[0];
}
function getPanelHeading(hunt) {
  const species = getSpeciesDisplay(hunt) || 'Hunt';
  const speciesHeading = getSpeciesHeadingLabel(species);
  const sex = getNormalizedSex(hunt) || '';
  const huntType = getHuntType(hunt) || '';
  const huntClass = getHuntCategory(hunt) || '';
  const combined = `${huntType} ${huntClass}`.toLowerCase();
  const permitTotal = getPermitTotal(hunt);

  const prefixParts = [];
  const isOil = combined.includes('once-in-a-lifetime');
  const isPremium = combined.includes('premium');
  if (isOil) prefixParts.push('O.I.L.');
  else if (isPremium || combined.includes('limited')) prefixParts.push('L.E.');
  else if (combined.includes('general')) prefixParts.push('G.S.');

  let classLabel = '';
  if (combined.includes('mature bull')) classLabel = 'Mature Bull';
  else if (combined.includes('mature buck')) classLabel = 'Mature Buck';
  else if (combined.includes('general bull')) classLabel = 'General Bull';
  else if (combined.includes('general buck')) classLabel = 'General Buck';
  else if (combined.includes('spike')) classLabel = 'Spike Only';
  else if (combined.includes('antlerless')) classLabel = 'Antlerless';
  else if (sex === 'Bull' && prefixParts.includes('L.E.')) classLabel = 'Mature Bull';
  else if (sex === 'Buck' && prefixParts.includes('L.E.')) classLabel = 'Mature Buck';
  else if (sex === 'Bull' && prefixParts.includes('G.S.')) classLabel = 'General Bull';
  else if (sex === 'Buck' && prefixParts.includes('G.S.')) classLabel = 'General Buck';
  else if (sex && sex !== 'All') classLabel = sex;

  const parts = [];
  if (prefixParts.length) parts.push(prefixParts.join(' '));
  const isTrophyOilSpecies = isOil && ['Rocky Mountain Bighorn Sheep', 'Desert Bighorn Sheep', 'Moose', 'Mountain Goat', 'Bison'].includes(species);
  const isPremiumDeerTrophy = isPremium && species === 'Deer';
  const isLowPermitElkTrophy = species === 'Elk' && prefixParts.includes('L.E.') && permitTotal !== null && permitTotal < 20;
  const isTrophy = isTrophyOilSpecies || isPremiumDeerTrophy || isLowPermitElkTrophy;

  if (isTrophy) {
    parts.push('Trophy');
    if (species === 'Elk' || species === 'Deer') {
      if (classLabel && !/^antlerless$/i.test(classLabel)) parts.push(classLabel);
      parts.push(speciesHeading);
    } else {
      parts.push(speciesHeading);
    }
  } else {
    if (classLabel) parts.push(classLabel);
    parts.push(speciesHeading);
  }
  return parts.join(' ');
}
function normalizeBoundaryKey(value) {
  return safe(value)
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
function hasActiveMatrixSelections() {
  return [
    safe(searchInput?.value).trim(),
    speciesFilter?.value && speciesFilter.value !== 'All Species' ? speciesFilter.value : '',
    sexFilter?.value && sexFilter.value !== 'All' ? sexFilter.value : '',
    huntTypeFilter?.value && huntTypeFilter.value !== 'All' ? huntTypeFilter.value : '',
    huntCategoryFilter?.value && huntCategoryFilter.value !== 'All' ? huntCategoryFilter.value : '',
    weaponFilter?.value && weaponFilter.value !== 'All' ? weaponFilter.value : '',
    unitFilter?.value || ''
  ].filter(Boolean).length > 0;
}
function hasReadyUnitSelection() {
  return !!safe(unitFilter?.value).trim();
}

const PROGRESSIVE_MATRIX_SEQUENCE = [
  'speciesFilter',
  'sexFilter',
  'huntTypeFilter',
  'weaponFilter',
  'huntCategoryFilter',
  'unitFilter'
];

function getMatrixResetValue(controlId) {
  if (controlId === 'speciesFilter') return 'All Species';
  if (controlId === 'unitFilter') return '';
  return 'All';
}

function resetMatrixControl(controlId) {
  const el = document.getElementById(controlId);
  if (!el) return;
  el.value = getMatrixResetValue(controlId);
}

function resetDownstreamMatrixControls(changedId) {
  const idx = PROGRESSIVE_MATRIX_SEQUENCE.indexOf(changedId);
  if (idx < 0) return;
  PROGRESSIVE_MATRIX_SEQUENCE.slice(idx + 1).forEach(resetMatrixControl);
}

function countSpecificOptions(selectEl, defaultValue) {
  if (!selectEl) return 0;
  return Array.from(selectEl.options || [])
    .map(option => safe(option.value).trim())
    .filter(value => value && value !== defaultValue)
    .length;
}

function setMatrixStepVisibility(controlId, visible) {
  const el = document.getElementById(controlId);
  const step = el?.closest?.('.matrix-step');
  if (!el || !step) return;
  if (!visible) {
    resetMatrixControl(controlId);
  }
  step.classList.toggle('is-collapsed', !visible);
  step.setAttribute('aria-hidden', visible ? 'false' : 'true');
  el.disabled = !visible;
}

function syncProgressiveSelectionMatrix() {
  if (!speciesFilter || !sexFilter || !huntTypeFilter || !weaponFilter || !huntCategoryFilter || !unitFilter) return;
  const speciesReady = safe(speciesFilter.value) !== 'All Species';
  const sexReady = speciesReady && safe(sexFilter.value) !== 'All';
  const huntTypeReady = sexReady && safe(huntTypeFilter.value) !== 'All';
  const weaponReady = huntTypeReady && safe(weaponFilter.value) !== 'All';
  const huntClassChoiceCount = countSpecificOptions(huntCategoryFilter, 'All');
  const huntClassNeeded = weaponReady && huntClassChoiceCount > 1;
  const huntClassReady = !huntClassNeeded || safe(huntCategoryFilter.value) !== 'All';

  setMatrixStepVisibility('speciesFilter', true);
  setMatrixStepVisibility('sexFilter', speciesReady);
  setMatrixStepVisibility('huntTypeFilter', sexReady);
  setMatrixStepVisibility('weaponFilter', huntTypeReady);
  setMatrixStepVisibility('huntCategoryFilter', huntClassNeeded);
  setMatrixStepVisibility('unitFilter', weaponReady && huntClassReady);
}

// --- FILTERING ENGINE ---
function getFilteredHunts(excludeKey = '') {
  const search = safe(searchInput?.value).trim().toLowerCase();
  const species = safe(speciesFilter?.value || 'All Species');
  const sex = safe(sexFilter?.value || 'All');
  const huntType = safe(huntTypeFilter?.value || 'All');
  const weapon = safe(weaponFilter?.value || 'All');
  const huntCategory = safe(huntCategoryFilter?.value || 'All');
  const unit = safe(unitFilter?.value || '');
  const publicTwinKeys = buildPublicTwinKeySet(huntData);

  return huntData.filter(h => {
    const sDisplay = getSpeciesDisplay(h);
    const hSex = getNormalizedSex(h);
    const hHuntType = getHuntType(h);
    const hWeapon = getWeapon(h);
    const hHuntCategory = getHuntCategory(h);
    const hUnit = getUnitValue(h);

    const searchOk = !search
      || getHuntTitle(h).toLowerCase().includes(search)
      || getHuntCode(h).toLowerCase().includes(search)
      || getUnitName(h).toLowerCase().includes(search);
    const speciesOk = excludeKey === 'species' || species === 'All Species' || sDisplay === species;
    const sexOk = excludeKey === 'sex' || sex === 'All' || hSex === sex;
    const huntTypeOk = excludeKey === 'huntType' || huntType === 'All' || hHuntType === huntType;
    const weaponOk = excludeKey === 'weapon' || weaponMatchesFilter(h, weapon);
    const huntCategoryOk = excludeKey === 'huntCategory' || huntCategory === 'All' || hHuntCategory === huntCategory;
    const unitOk = excludeKey === 'unit' || !unit || hUnit === unit;
    const conservationDisplayOk = huntType !== 'Conservation' || !!h?.syntheticConservationPermit;
    const duplicatedPrivateTwinHidden = !(
      isPrivateLandOnlyRecord(h) &&
      !isLegitPrivateLandException(h) &&
      getHuntCodeDigits(h) &&
      publicTwinKeys.has(getPrivateTwinKey(h))
    );

    return searchOk && speciesOk && sexOk && huntTypeOk && weaponOk && huntCategoryOk && unitOk && conservationDisplayOk && duplicatedPrivateTwinHidden;
  });
}

function getDisplayHunts() {
  if (!hasActiveMatrixSelections() && !selectedHunt) return [];
  if (selectedHuntFocusOnly && selectedHunt) return [selectedHunt];
  if (selectedHunt && !hasActiveMatrixSelections()) return [selectedHunt];
  return getFilteredHunts();
}
function shouldShowHuntBoundaries() {
  // Show hunt unit geometry only after user has started matrix selection
  // (or explicitly selected a hunt), with Hunt Units acting as a master toggle.
  return !!toggleDwrUnits?.checked && (hasActiveMatrixSelections() || !!selectedHunt);
}
function shouldShowAllHuntUnits() {
  // We intentionally avoid default "paint whole state" behavior on initial load.
  return false;
}
function normalizeListValues(values) {
  if (Array.isArray(values)) return values.map(v => safe(v).trim()).filter(Boolean);
  const one = safe(values).trim();
  return one ? [one] : [];
}
function normalizeBoolean(value) {
  if (typeof value === 'boolean') return value;
  const lowered = safe(value).trim().toLowerCase();
  return lowered === 'true' || lowered === 'yes' || lowered === '1';
}
function choosePrimaryListValue(primaryValue, values) {
  const list = normalizeListValues(values);
  const primary = safe(primaryValue).trim();
  if (primary && primary.length > 3) return primary;
  return list[0] || primary;
}
function normalizeOutfitterRecord(record) {
  if (!record || typeof record !== 'object') return null;
  const isNested = !!(record.contact || record.branding || record.serviceArea || record.headquarters);
  if (!isNested) {
    return {
      ...record,
      listingName: firstNonEmpty(record.listingName, record.displayName, record.businessName, record.Outfitter),
      logoUrl: firstNonEmpty(record.logoUrl, record.logo, record.logoURL),
      website: firstNonEmpty(record.website, record.url),
      phone: normalizeListValues(record.phone),
      speciesServed: normalizeListValues(record.speciesServed),
      unitsServed: normalizeListValues(record.unitsServed),
      address: firstNonEmpty(record.address, record.hometown),
      city: firstNonEmpty(record.city),
      region: firstNonEmpty(record.region, record.state)
    };
  }

  const contact = record.contact || {};
  const branding = record.branding || {};
  const headquarters = record.headquarters || {};
  const serviceArea = record.serviceArea || {};
  const services = record.services || {};

  return {
    ...record,
    listingName: firstNonEmpty(record.displayName, record.legalBusinessName, record.businessName, record.Outfitter),
    businessName: firstNonEmpty(record.displayName, record.legalBusinessName, record.businessName),
    logoUrl: firstNonEmpty(branding.logoUrl, branding.cardImageUrl, branding.heroImageUrl),
    website: firstNonEmpty(contact.website, contact.facebookUrl, contact.instagramUrl, contact.instagramHandle),
    phone: normalizeListValues(contact.phoneNumbers?.length ? contact.phoneNumbers : contact.phonePrimary),
    email: normalizeListValues(contact.emailAddresses?.length ? contact.emailAddresses : contact.emailPrimary),
    phonePrimary: choosePrimaryListValue(contact.phonePrimary, contact.phoneNumbers),
    emailPrimary: choosePrimaryListValue(contact.emailPrimary, contact.emailAddresses),
    ownerNames: normalizeListValues(contact.ownerNames?.length ? contact.ownerNames : contact.primaryName),
    address: firstNonEmpty(headquarters.mailingAddress, headquarters.publicMeetingLocation),
    hometown: firstNonEmpty(headquarters.publicMeetingLocation, headquarters.city),
    city: firstNonEmpty(headquarters.city),
    region: firstNonEmpty(headquarters.region, headquarters.state),
    state: firstNonEmpty(headquarters.state),
    latitude: Number.isFinite(Number(headquarters.latitude)) ? Number(headquarters.latitude) : null,
    longitude: Number.isFinite(Number(headquarters.longitude)) ? Number(headquarters.longitude) : null,
    speciesServed: normalizeListValues(serviceArea.speciesServed),
    unitsServed: normalizeListValues(serviceArea.unitsServed),
    usfsForests: normalizeListValues(serviceArea.usfsForests),
    usfsForestIds: normalizeListValues(serviceArea.usfsForestIds),
    usfsDistrictIds: normalizeListValues(serviceArea.usfsDistrictIds),
    blmDistricts: normalizeListValues(serviceArea.blmDistricts),
    blmDistrictIds: normalizeListValues(serviceArea.blmDistrictIds),
    zoneTags: normalizeListValues(serviceArea.zoneTags),
    countiesServed: normalizeListValues(serviceArea.countiesServed),
    wmasServed: normalizeListValues(serviceArea.wmasServed),
    stateParks: normalizeListValues(serviceArea.stateParks),
    sitla: normalizeListValues(serviceArea.sitla),
    statewide: normalizeBoolean(serviceArea.statewide),
    guidedHunts: normalizeBoolean(services.guidedHunts),
    diySupport: normalizeBoolean(services.diySupport),
    trespassAccess: normalizeBoolean(services.trespassAccess),
    lodgingIncluded: normalizeBoolean(services.lodgingIncluded),
    mealsIncluded: normalizeBoolean(services.mealsIncluded),
    packTrips: normalizeBoolean(services.packTrips),
    youthHunts: normalizeBoolean(services.youthHunts),
    archery: normalizeBoolean(services.archery),
    muzzleloader: normalizeBoolean(services.muzzleloader),
    socialUrls: [
      firstNonEmpty(contact.facebookUrl),
      firstNonEmpty(contact.instagramUrl, contact.instagramHandle),
      firstNonEmpty(contact.youtubeUrl)
    ].filter(Boolean)
  };
}
function normalizeOutfitterList(list) {
  return (Array.isArray(list) ? list : []).map(normalizeOutfitterRecord).filter(Boolean);
}
function getOutfitterCoverageKey(species, unitCode) {
  return `${normalizeBoundaryKey(species)}|${normalizeBoundaryKey(unitCode)}`;
}
function normalizeOutfitterCoverageList(list) {
  return (Array.isArray(list) ? list : []).map(row => {
    const species = firstNonEmpty(row.Species, row.species);
    const unitCode = firstNonEmpty(row.UnitCode, row.unitCode);
    const unitName = firstNonEmpty(row.UnitName, row.unitName);
    return {
      species,
      unitCode,
      unitName,
      primaryUsfsForestName: firstNonEmpty(row.PrimaryUsfsForestName, row.primaryUsfsForestName),
      primaryBlmDistrictName: firstNonEmpty(row.PrimaryBlmDistrictName, row.primaryBlmDistrictName),
      usfsAuthoritySource: firstNonEmpty(row.UsfsAuthoritySource, row.usfsAuthoritySource),
      blmAuthoritySource: firstNonEmpty(row.BlmAuthoritySource, row.blmAuthoritySource),
      usfsPermitMatchedOutfitters: normalizeListValues(firstNonEmpty(row.UsfsPermitMatchedOutfitters, row.usfsPermitMatchedOutfitters)),
      blmPermitMatchedOutfitters: normalizeListValues(firstNonEmpty(row.BlmPermitMatchedOutfitters, row.blmPermitMatchedOutfitters)),
      federalPermitMatchedOutfitters: normalizeListValues(firstNonEmpty(row.FederalPermitMatchedOutfitters, row.federalPermitMatchedOutfitters)),
      federalCoverageEligible: firstNonEmpty(row.FederalCoverageEligible, row.federalCoverageEligible),
      notes: firstNonEmpty(row.Notes, row.notes)
    };
  }).filter(row => row.species && row.unitCode);
}
function indexOutfitterFederalCoverage(list) {
  outfitterFederalCoverageIndex.clear();
  outfitterFederalCoverage = normalizeOutfitterCoverageList(list);
  outfitterFederalCoverage.forEach(row => {
    outfitterFederalCoverageIndex.set(getOutfitterCoverageKey(row.species, row.unitCode), row);
  });
}
function getFederalCoverageForHunt(hunt) {
  if (!hunt) return null;
  return outfitterFederalCoverageIndex.get(getOutfitterCoverageKey(getSpeciesDisplay(hunt), getUnitCode(hunt))) || null;
}
function deterministicHash(input) {
  const text = safe(input);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}
function getOutfitterLocalityScore(outfitter, hunt, requiredUsfsForests = []) {
  const unitName = normalizeBoundaryKey(getUnitName(hunt));
  const unitCode = normalizeBoundaryKey(getUnitCode(hunt));
  const city = normalizeBoundaryKey(outfitter.city);
  const hometown = normalizeBoundaryKey(outfitter.hometown);
  const region = normalizeBoundaryKey(outfitter.region);
  const usfsForestIds = normalizeListValues(outfitter.usfsForestIds).map(normalizeBoundaryKey);
  let score = 0;

  [city, hometown, region].filter(Boolean).forEach(place => {
    if (!place) return;
    if (unitName && (unitName.includes(place) || place.includes(unitName))) score += 8;
    if (unitCode && (unitCode.includes(place) || place.includes(unitCode))) score += 5;
  });

  if ((city === 'manti' || hometown === 'manti' || region === 'manti')
    && requiredUsfsForests.includes('manti-la-sal')) {
    score += 6;
  }
  if (requiredUsfsForests.some(required => usfsForestIds.includes(required))) {
    score += 2;
  }
  return score;
}
function orderOutfitterMatchesForDisplay(hunt, matches, requiredUsfsForests = []) {
  const huntSeed = `${normalizeBoundaryKey(getSpeciesDisplay(hunt))}|${normalizeBoundaryKey(getUnitCode(hunt))}|${normalizeBoundaryKey(getUnitName(hunt))}`;
  return [...matches].sort((a, b) => {
    const aLocal = getOutfitterLocalityScore(a, hunt, requiredUsfsForests);
    const bLocal = getOutfitterLocalityScore(b, hunt, requiredUsfsForests);
    if (bLocal !== aLocal) return bLocal - aLocal;
    const aReasons = normalizeListValues(a.matchReasons).length;
    const bReasons = normalizeListValues(b.matchReasons).length;
    if (bReasons !== aReasons) return bReasons - aReasons;
    const aRand = deterministicHash(`${huntSeed}|${safe(a.id || a.slug || a.listingName)}`);
    const bRand = deterministicHash(`${huntSeed}|${safe(b.id || b.slug || b.listingName)}`);
    return aRand - bRand;
  });
}
function noteOutfitterInteraction() {
  suppressLandClickUntil = Date.now() + 800;
}
function shouldSuppressLandClick() {
  return Date.now() < suppressLandClickUntil;
}
function slugText(value) {
  return safe(value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}
function getOwnershipName(props) {
  return firstNonEmpty(
    props.label_state,
    props.LABEL_STATE,
    props.ut_lgd,
    props.UT_LGD,
    props.desig,
    props.DESIG,
    props.admin,
    props.ADMIN,
    props.owner,
    props.OWNER
  );
}
function getOwnershipCounty(props) {
  return firstNonEmpty(props.county, props.COUNTY, props.co_name, props.CO_NAME);
}
function getOwnershipAcres(props) {
  return firstNonEmpty(props.gis_acres, props.GIS_ACRES, props.acres, props.ACRES);
}
function getOwnershipBucket(props) {
  const haystack = slugText([
    props.owner, props.OWNER, props.admin, props.ADMIN, props.desig, props.DESIG,
    props.label_state, props.LABEL_STATE, props.ut_lgd, props.UT_LGD
  ].filter(Boolean).join(' '));

  if (haystack.includes('state park')) return 'stateParks';
  if (haystack.includes('wildlife management area') || haystack.includes('waterfowl management area') || haystack.includes(' wma')) return 'wma';
  if (haystack.includes('trust') || haystack.includes('sitla') || haystack.includes('school and institutional trust lands')) return 'sitla';
  if (haystack.includes('private')) return 'private';
  if (haystack.includes('state')) return 'stateLands';
  return '';
}
function getOwnershipSubtitle(bucket, props) {
  if (bucket === 'sitla') return 'SITLA';
  if (bucket === 'stateParks') return 'State Parks';
  if (bucket === 'private') return 'Private Land';
  if (bucket === 'wma') {
    return "UT. DWR W.M.A.'s";
  }
  return '';
}
function getOwnershipTitle(bucket, props) {
  const base = getOwnershipName(props);
  if (bucket === 'sitla') {
    return base && !/utah state trust lands/i.test(base)
      ? base
      : firstNonEmpty(getOwnershipCounty(props) && `${getOwnershipCounty(props)} County SITLA`, 'Utah State Trust Lands');
  }
  if (bucket === 'stateParks') return firstNonEmpty(base, 'Utah State Park');
  if (bucket === 'stateLands') return firstNonEmpty(base, getOwnershipCounty(props) && `${getOwnershipCounty(props)} County State Lands`, 'Utah State Lands');
  if (bucket === 'private') return firstNonEmpty(base, getOwnershipCounty(props) && `${getOwnershipCounty(props)} County Private Land`, 'Private Land');
  if (bucket === 'wma') return firstNonEmpty(base, 'Wildlife Management Area');
  return firstNonEmpty(base, 'Land Ownership');
}
function buildOwnershipDetails(bucket, props) {
  const county = getOwnershipCounty(props);
  const acres = getOwnershipAcres(props);
  const detailBits = [];
  let noticeText = '';
  if (county) detailBits.push(`${county} County`);
  if (acres) detailBits.push(`${acres} acres`);
  if (bucket === 'wma') {
    noticeText = "Utah DWR W.M.A.'s do not imply outfitter approval, endorsement, or exclusive access.";
  }
  const detailText = detailBits.join(' | ');
  let logo = '';
  if (bucket === 'sitla') logo = LOGO_SITLA;
  if (bucket === 'stateParks') logo = LOGO_STATE_PARKS;
  if (bucket === 'wma') logo = LOGO_DWR_WMA;
  return {
    logo,
    logoSize: logo ? 68 : undefined,
    title: getOwnershipTitle(bucket, props),
    subtitle: getOwnershipSubtitle(bucket, props),
    detailText,
    noticeText
  };
}
function setLayerVisibility(layer, visible) {
  if (!layer) return;
  layer.setMap(visible ? googleBaselineMap : null);
}
function shouldShowWildernessOverlay() {
  return !!(toggleUSFS?.checked || toggleBLM?.checked);
}
function shouldShowWildernessFeature(featureOrAgency) {
  const agency = typeof featureOrAgency === 'string'
    ? safe(featureOrAgency).toUpperCase()
    : safe(featureOrAgency?.getProperty?.('Agency')).toUpperCase();
  if (agency === 'FS') return !!toggleUSFS?.checked;
  if (agency === 'BLM') return !!toggleBLM?.checked;
  return false;
}
function shouldDeprioritizeFederalClicks() {
  return false;
}
function updateWildernessOverlayVisibility() {
  setLayerVisibility(wildernessLayer, shouldShowWildernessOverlay());
}
function updateStatus(message) {
  if (statusEl) statusEl.textContent = message;
}

function normalizeMapModeHash(value) {
  const hash = safe(value).trim().toLowerCase().replace(/^#/, '');
  if (hash === 'google-earth' || hash === 'earth') return 'earth';
  if (hash === 'google-maps' || hash === 'google-map' || hash === 'google') return 'google';
  if (hash === 'dwr' || hash === 'dwr-map') return 'dwr';
  return '';
}

function getMapModeHash(value) {
  const mode = safe(value).trim().toLowerCase();
  if (mode === 'earth') return '#google-earth';
  if (mode === 'dwr') return '#dwr';
  return '';
}

function syncPlannerNavState() {
  if (typeof document === 'undefined') return;
  const navLinks = Array.from(document.querySelectorAll('.page-nav-strip [data-map-nav]'));
  if (!navLinks.length) return;
  const activeMode = safe(mapTypeSelect?.value || 'google').trim().toLowerCase();
  navLinks.forEach((link) => {
    const mode = safe(link.getAttribute('data-map-nav')).trim().toLowerCase();
    const isActive = mode === activeMode;
    link.classList.toggle('active', isActive);
    if (isActive) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
}

function syncMapModeFromHash() {
  const hashMode = normalizeMapModeHash(typeof window !== 'undefined' ? window.location.hash : '');
  if (!hashMode || !mapTypeSelect || safe(mapTypeSelect.value).toLowerCase() === hashMode) return;
  mapTypeSelect.value = hashMode;
  applyMapMode();
}

function syncHashFromMapMode() {
  if (typeof window === 'undefined' || !mapTypeSelect) return;
  const nextHash = getMapModeHash(mapTypeSelect.value);
  if (nextHash && window.location.hash === nextHash) return;
  if (!nextHash && !window.location.hash) return;
  history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`);
}

function forceGoogleMapVisible() {
  const mapWrap = document.querySelector('.map-wrap');
  const mapEl = document.getElementById('map');
  if (mapWrap) {
    mapWrap.classList.remove('is-dwr-mode');
    mapWrap.classList.remove('is-earth-mode');
  }
  if (mapEl) {
    mapEl.style.display = '';
  }
  if (dwrMapFrame) {
    dwrMapFrame.hidden = true;
    dwrMapFrame.style.display = '';
  }
  if (googleEarth3dMap) {
    googleEarth3dMap.hidden = true;
  }
  clearGoogleEarth3dBoundaryOverlays();
  if (mapTypeSelect && safe(mapTypeSelect.value).toLowerCase() !== 'google') {
    mapTypeSelect.value = 'google';
  }
  syncPlannerNavState();
  syncHashFromMapMode();
  if (googleBaselineMap && typeof google !== 'undefined') {
    google.maps.event.trigger(googleBaselineMap, 'resize');
  }
}

function resetAllFilters() {
  if (searchInput) searchInput.value = '';
  if (speciesFilter) speciesFilter.value = 'All Species';
  if (sexFilter) sexFilter.value = 'All';
  if (huntTypeFilter) huntTypeFilter.value = 'All';
  if (weaponFilter) weaponFilter.value = 'All';
  if (huntCategoryFilter) huntCategoryFilter.value = 'All';
  if (unitFilter) unitFilter.value = '';
  selectedHunt = null;
  selectedBoundaryFeature = null;
  clearSelectedBoundaryFallbackLayer();
  closeSelectedHuntPopup();
  closeSelectedHuntFloat();
  closeSelectionInfoWindow();
  refreshSelectionMatrix();
  styleBoundaryLayer();
  refreshGoogleEarth3dBoundaryOverlay();
  renderMatchingHunts();
  renderSelectedHunt();
  updateStatus('Filters cleared. Select a species or click a hunt unit.');
}

function handleFilterChange(event) {
  const activeMode = safe(mapTypeSelect?.value || 'google').toLowerCase();
  selectedHuntFocusOnly = false;
  selectedHunt = null;
  selectedBoundaryFeature = null;
  clearSelectedBoundaryFallbackLayer();
  closeSelectedHuntPopup();
  closeSelectedHuntFloat();
  closeSelectionInfoWindow();
  const changedId = safe(event?.target?.id);
  resetDownstreamMatrixControls(changedId);
  if (!googleBaselineMap) {
    refreshSelectionMatrix();
    updateStatus('Google map is still loading. Filter selection saved; boundaries will appear when the map is ready.');
    return;
  }
  if (toggleDwrUnits && hasActiveMatrixSelections()) {
    toggleDwrUnits.checked = true;
  }
  refreshSelectionMatrix();
  styleBoundaryLayer();
  refreshGoogleEarth3dBoundaryOverlay();
  renderMatchingHunts();
  renderSelectedHunt();
  renderOutfitters();
  if (activeMode === 'earth') {
    refreshGoogleEarth3dBoundaryOverlaySoon();
  } else if (activeMode === 'dwr') {
    updateDwrMapFrame(getPreferredDwrHuntCandidate());
  }
  maybeAutoAdvanceFilterMatrix(changedId);
  if (ENABLE_LIVE_MATRIX_APPLY) {
    scheduleLiveFilterApply();
  } else {
    const count = getDisplayHunts().length;
    updateStatus(`${count} matching hunt${count === 1 ? '' : 's'} ready. Press Apply to open choices.`);
  }
}

function refreshSelectionMatrix() {
  if (!speciesFilter || !sexFilter || !huntTypeFilter || !weaponFilter || !huntCategoryFilter || !unitFilter) return;

  const speciesOptions = sortWithPreferredOrder(
    Array.from(new Set(huntData.map(getSpeciesDisplay).filter(Boolean))),
    ['Deer', 'Elk', 'Pronghorn', 'Moose', 'Bison', 'Black Bear', 'Cougar', 'Turkey', 'Desert Bighorn Sheep', 'Rocky Mountain Bighorn Sheep', 'Mountain Goat']
  );
  const previousSpecies = speciesFilter.value || 'All Species';
  speciesFilter.innerHTML = `<option value="All Species">All Species</option>` + speciesOptions.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  speciesFilter.value = speciesOptions.includes(previousSpecies) ? previousSpecies : 'All Species';

  const sexData = getFilteredHunts('sex');
  const sexOptions = sortWithPreferredOrder(Array.from(new Set(['All', ...sexData.map(getNormalizedSex).filter(Boolean)])), ['All', ...SEX_ORDER]);
  const prevSex = sexFilter.value || 'All';
  sexFilter.innerHTML = sexOptions.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  sexFilter.value = sexOptions.includes(prevSex) ? prevSex : 'All';

  const huntTypeData = getFilteredHunts('huntType');
  const huntTypeOptions = sortWithPreferredOrder(Array.from(new Set(['All', ...huntTypeData.map(getHuntType).filter(Boolean)])), ['All', ...HUNT_TYPE_ORDER]);
  const prevHuntType = huntTypeFilter.value || 'All';
  huntTypeFilter.innerHTML = huntTypeOptions.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  huntTypeFilter.value = huntTypeOptions.includes(prevHuntType) ? prevHuntType : 'All';

  const weaponData = getFilteredHunts('weapon');
  const weaponOptions = sortWithPreferredOrder(Array.from(new Set(['All', ...weaponData.map(getWeapon).filter(Boolean)])), ['All', ...WEAPON_ORDER]);
  const prevWeapon = weaponFilter.value || 'All';
  weaponFilter.innerHTML = weaponOptions.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  weaponFilter.value = weaponOptions.includes(prevWeapon) ? prevWeapon : 'All';

  const categoryData = getFilteredHunts('huntCategory');
  const categoryOptions = sortWithPreferredOrder(Array.from(new Set(['All', ...categoryData.map(getHuntCategory).filter(Boolean)])), ['All', ...HUNT_CLASS_ORDER]);
  const prevHuntCategory = huntCategoryFilter.value || 'All';
  huntCategoryFilter.innerHTML = categoryOptions.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  huntCategoryFilter.value = categoryOptions.includes(prevHuntCategory) ? prevHuntCategory : 'All';
  syncProgressiveSelectionMatrix();

  const hasNonUnitSelections = [
    safe(searchInput?.value).trim(),
    speciesFilter.value !== 'All Species' ? speciesFilter.value : '',
    sexFilter.value !== 'All' ? sexFilter.value : '',
    huntTypeFilter.value !== 'All' ? huntTypeFilter.value : '',
    huntCategoryFilter.value !== 'All' ? huntCategoryFilter.value : '',
    weaponFilter.value !== 'All' ? weaponFilter.value : ''
  ].filter(Boolean).length > 0;

  const unitsMap = new Map();
  const unitSource = hasNonUnitSelections ? getFilteredHunts('unit') : huntData;
  unitSource.forEach(h => {
    const unitValue = getUnitValue(h);
    if (unitValue) unitsMap.set(unitValue, getUnitName(h) || unitValue);
  });
  const unitOptions = Array.from(unitsMap.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  const prevUnit = unitFilter.value || '';
  unitFilter.innerHTML = `<option value="">All DWR Hunt Units</option>` + unitOptions.map(([v, l]) => `<option value="${escapeHtml(v)}">${escapeHtml(l)}</option>`).join('');
  unitFilter.value = unitOptions.some(([v]) => v === prevUnit) ? prevUnit : '';
  syncProgressiveSelectionMatrix();
}

// --- CORE APP LOGIC ---
async function loadHuntData() {
  await loadBoundaryManifestRuntime();
  huntData = await loadHuntDataRecords({
    HUNT_DATA_SOURCES,
    ELK_BOUNDARY_TABLE_SOURCES,
    OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
    SPIKE_ELK_HUNT_CODES,
    getHuntRecordKey,
    getHuntCode,
    getBoundaryId,
    getSpeciesDisplay,
    getNormalizedSex,
    getUnitName,
    normalizeHuntCode,
    normalizeBoundaryKey,
    firstNonEmpty,
    safe,
    updateStatus
  });
  const syntheticConservationHunts = buildSyntheticConservationPermitHunts(huntData);
  huntData = [...huntData, ...syntheticConservationHunts];
  applyBoundaryManifestToHunts(huntData);
  refreshSelectionMatrix();
  updateStatus(`Loaded ${huntData.length} hunts.${boundaryManifestByHuntCode.size ? ` Boundary manifest rows: ${boundaryManifestByHuntCode.size}.` : ''}`);
}

async function loadOfficialElkBoundaryFeatures() {
  return loadOfficialElkBoundaryFeaturesFromData({ ELK_BOUNDARY_TABLE_SOURCES });
}

async function loadDerivedSpikeElkRecords(existingRecords) {
  return loadDerivedSpikeElkRecordsFromData(existingRecords, {
    ELK_BOUNDARY_TABLE_SOURCES,
    SPIKE_ELK_HUNT_CODES,
    normalizeHuntCode,
    getHuntCode,
    getBoundaryId,
    getSpeciesDisplay,
    getNormalizedSex,
    getUnitName,
    normalizeBoundaryKey,
    firstNonEmpty,
    safe
  });
}

function buildMatchingHuntCard(h, selectedKey) {
  const selected = selectedKey && selectedKey === getHuntRecordKey(h);
  const huntKey = escapeHtml(getHuntRecordKey(h));
  const name = escapeHtml(firstNonEmpty(h.hunt_name, getHuntTitle(h), getUnitName(h), ''));
  const code = escapeHtml(getHuntCode(h) || '');
  const weapon = escapeHtml(getWeapon(h) || 'Weapon pending');
  const huntType = escapeHtml(getHuntType(h) || 'Hunt type pending');
  return `
    <div class="hunt-card${selected ? ' is-selected' : ''}" data-hunt-key="${huntKey}" role="button" tabindex="0">
      <div class="hunt-card-head">
        <img src="${LOGO_DWR_SELECTOR}" alt="Utah DWR" class="hunt-card-logo">
        <div>
          <div class="hunt-card-code">${code}</div>
          <div class="hunt-card-title">${name}</div>
          <div class="hunt-card-meta">${weapon} | ${huntType}</div>
        </div>
      </div>
      <div class="hunt-card-actions">
        <button type="button" class="secondary hunt-research-ring hunt-research-pill" data-hunt-research-key="${huntKey}">
          View Research
        </button>
        <button type="button" class="secondary hunt-research-ring" data-hunt-compare-key="${huntKey}">
          Compare Hunts
        </button>
        <button type="button" class="secondary hunt-research-ring" data-hunt-save-key="${huntKey}">
          Save Hunt
        </button>
        <button type="button" class="secondary hunt-research-ring" data-hunt-outfitters-key="${huntKey}">
          Find Outfitters
        </button>
      </div>
    </div>`;
}

function renderMatchingHunts() {
  const container = document.getElementById('matchingHunts');
  if (!container) return;
  const list = getDisplayHunts();
  const selectedKey = getSelectedHuntKey();
  updateStatus(
    !hasActiveMatrixSelections() && !selectedHunt
      ? 'Select filters or click a hunt unit to begin.'
      : `${list.length} matching hunt${list.length === 1 ? '' : 's'}`
  );
  container.innerHTML = list.length
    ? list.map(h => buildMatchingHuntCard(h, selectedKey)).join('')
    : '<div class="empty-note">Use the matrix or click a hunt unit to load matching hunts.</div>';
}

function closeSelectionInfoWindow() {
  if (selectionInfoWindow) {
    selectionInfoWindow.close();
    selectionInfoWindow = null;
  }
}

function closeSelectedHuntFloat(zoomToUnit = false) {
  if (!selectedHuntFloat) return;
  selectedHuntFloat.classList.remove('is-open');
  selectedHuntFloat.setAttribute('aria-hidden', 'true');
  selectedHuntFloat.innerHTML = '';
  if (zoomToUnit && selectedHunt && safe(mapTypeSelect?.value).toLowerCase() === 'google') {
    zoomToSelectedBoundary();
  }
  if (safe(mapTypeSelect?.value).toLowerCase() === 'earth') {
    refreshGoogleEarth3dBoundaryOverlaySoon();
  }
}
function getSelectedUnitGroups() {
  const groups = new Map();
  getDisplayHunts().forEach(hunt => {
    const resolved = resolveBoundaryForHuntRuntime(hunt);
    const key = firstNonEmpty(
      resolved?.display_boundary_id,
      resolved?.merged_boundary_id,
      resolved?.dwr_boundary_id,
      resolved?.boundary_id,
      getBoundaryId(hunt),
      getUnitValue(hunt),
      getUnitName(hunt),
      getHuntCode(hunt),
    );
    if (!key) return;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        unitValue: getUnitValue(hunt),
        unitName: getUnitName(hunt) || getHuntTitle(hunt),
        hunts: []
      });
    }
    groups.get(key).hunts.push(hunt);
  });
  return Array.from(groups.values()).sort((a, b) => safe(a.unitName).localeCompare(safe(b.unitName)));
}
function openSelectedUnitsChooser() {
  if (!mapChooser || !mapChooserBody || !mapChooserTitle || !mapChooserKicker) return;
  const groups = getSelectedUnitGroups();
  if (groups.length <= 1) {
    closeSelectedHuntPopup();
    return;
  }
  closeSelectedHuntFloat();
  closeSelectionInfoWindow();
  selectedBoundaryMatches = [];
  mapChooserKicker.textContent = 'Selected Units';
  mapChooserTitle.textContent = `${groups.length} Units Selected`;
  mapChooserBody.innerHTML = groups.map(group => `
    <div class="map-chooser-card" data-selected-unit="${escapeHtml(group.unitValue || group.key)}" role="button" tabindex="0">
      <div class="hunt-card-title">${escapeHtml(group.unitName)}</div>
      <div class="map-chooser-meta">${group.hunts.length} matching hunt${group.hunts.length === 1 ? '' : 's'}</div>
      <div class="map-chooser-meta">${escapeHtml(getSpeciesDisplay(group.hunts[0]))} | ${escapeHtml(getHuntType(group.hunts[0]))}</div>
    </div>
  `).join('');
  mapChooser.classList.add('is-open');
  mapChooser.setAttribute('aria-hidden', 'false');
  mapChooserBody.querySelectorAll('[data-selected-unit]').forEach(card => {
    const select = () => {
      const unitValue = safe(card.getAttribute('data-selected-unit'));
      if (unitFilter) unitFilter.value = unitValue;
      refreshSelectionMatrix();
      styleBoundaryLayer();
      refreshGoogleEarth3dBoundaryOverlay();
      renderMatchingHunts();
      renderSelectedHunt();
      renderOutfitters();
      const hunts = getDisplayHunts().filter(h => getUnitValue(h) === unitValue);
      const unitTitle = firstNonEmpty(hunts[0] && getUnitName(hunts[0]), unitValue);
      showHuntMatchesChooser(unitTitle, hunts, 'Available Hunts');
    };
    card.addEventListener('click', select);
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        select();
      }
    });
  });
}

function openSelectedHuntFloat() {
  // Keep interaction lightweight: map clicks + hunt cards should drive selection/fly-in.
  if (!ENABLE_SELECTED_HUNT_FLOAT) {
    closeSelectedHuntFloat();
    return;
  }
  if (safe(mapTypeSelect?.value).toLowerCase() === 'dwr') {
    closeSelectedHuntFloat();
    return;
  }
  if (!selectedHuntFloat || !selectedHunt) {
    closeSelectedHuntFloat();
    return;
  }

  const code = escapeHtml(getHuntCode(selectedHunt) || '');
  const name = escapeHtml(firstNonEmpty(selectedHunt.hunt_name, getUnitName(selectedHunt), getHuntTitle(selectedHunt), 'Selected Hunt'));
  const species = escapeHtml(getSpeciesDisplay(selectedHunt) || 'Not loaded');
  const weapon = escapeHtml(getWeapon(selectedHunt) || 'Not loaded');
  const huntType = escapeHtml(getHuntType(selectedHunt) || 'Not loaded');
  const dates = escapeHtml(getDates(selectedHunt) || 'See official hunt details');
  const boundaryMeta = getBoundaryDisplaySummary(selectedHunt);
  const boundaryLine = escapeHtml(boundaryMeta.line);
  const boundaryLink = getBoundaryLink(selectedHunt);
  const kmzLink = boundaryMeta.kmzPath;
  const safeBoundaryLink = boundaryLink ? safeUrl(boundaryLink) : '';
  const safeKmzLink = kmzLink ? safeUrl(kmzLink) : '';

  selectedHuntFloat.innerHTML = `
    <section class="selected-unit-placard">
      <div class="selected-unit-placard-head">
        <div>
          <p class="selected-unit-placard-kicker">Selected Unit</p>
          <h3 class="selected-unit-placard-title">${code || 'Selected Hunt'}</h3>
        </div>
        <button type="button" class="selected-unit-placard-close" data-close-selected-hunt-float aria-label="Close selected hunt">X</button>
      </div>
      <div class="selected-unit-placard-body">
        <div class="selected-unit-placard-top">
          <img src="${LOGO_DWR_SELECTOR}" alt="Utah DWR logo" class="selected-unit-placard-logo">
          <div>
            <div class="selected-unit-placard-code">Utah DWR hunt</div>
            <div class="selected-unit-placard-name">${name}</div>
            <p class="selected-unit-placard-sub">${species} &middot; ${weapon} &middot; ${huntType}</p>
          </div>
        </div>
        <div class="selected-unit-placard-grid">
          <div class="selected-unit-placard-pill">
            <span class="selected-unit-placard-pill-label">Unit</span>
            <span class="selected-unit-placard-pill-value">${escapeHtml(getUnitName(selectedHunt) || getHuntTitle(selectedHunt) || 'Not loaded')}</span>
          </div>
          <div class="selected-unit-placard-pill">
            <span class="selected-unit-placard-pill-label">Dates</span>
            <span class="selected-unit-placard-pill-value">${dates}</span>
          </div>
          <div class="selected-unit-placard-pill">
            <span class="selected-unit-placard-pill-label">Boundary</span>
            <span class="selected-unit-placard-pill-value">${boundaryLine}</span>
          </div>
        </div>
        <div class="selected-unit-placard-actions">
          <button type="button" class="secondary hunt-research-ring hunt-research-pill selected-unit-placard-primary-btn" data-inline-hunt-research>
            View Research
          </button>
          <button type="button" class="secondary hunt-research-ring selected-unit-placard-primary-btn" data-inline-hunt-compare>
            Compare Hunts
          </button>
          <button type="button" class="secondary hunt-research-ring selected-unit-placard-primary-btn" data-inline-hunt-save>
            Save Hunt
          </button>
          <button type="button" class="secondary hunt-research-ring selected-unit-placard-primary-btn" data-inline-hunt-outfitters>
            Find Outfitters
          </button>
          <button type="button" class="secondary hunt-research-ring selected-unit-placard-map-btn selected-unit-placard-primary-btn" data-inline-view-map>
            View Map
          </button>
          ${safeBoundaryLink && safeBoundaryLink !== '#' ? `<a href="${escapeHtml(safeBoundaryLink)}" target="_blank" rel="noopener noreferrer">View on DWR</a>` : ''}
          ${safeKmzLink && safeKmzLink !== '#' ? `<a href="${escapeHtml(safeKmzLink)}" target="_blank" rel="noopener noreferrer">Download KMZ</a>` : ''}
        </div>
        <div class="selected-unit-placard-note">Built to stay just off the left rail so the map area still breathes.</div>
      </div>
    </section>`;
  selectedHuntFloat.classList.add('is-open');
  selectedHuntFloat.setAttribute('aria-hidden', 'false');
  selectedHuntFloat.querySelector('[data-close-selected-hunt-float]')?.addEventListener('click', () => closeSelectedHuntFloat());
  selectedHuntFloat.querySelector('[data-inline-view-map]')?.addEventListener('click', () => closeSelectedHuntFloat(true));
  selectedHuntFloat.querySelector('[data-inline-hunt-research]')?.addEventListener('click', () => {
    saveHuntAndOpenResearch(selectedHunt, 'Resident', 12);
  });
  selectedHuntFloat.querySelector('[data-inline-hunt-compare]')?.addEventListener('click', () => {
    openCompareHunts(selectedHunt, 'Resident', 12);
  });
  selectedHuntFloat.querySelector('[data-inline-hunt-save]')?.addEventListener('click', () => {
    const record = saveHuntToBackpack(selectedHunt, 'Resident', 12);
    if (record?.hunt_code) updateStatus(`${record.hunt_code} saved to Hunt Backpack.`);
  });
  selectedHuntFloat.querySelector('[data-inline-hunt-outfitters]')?.addEventListener('click', () => {
    openOutfitterMatches(selectedHunt);
  });
}

function buildLandInfoCard({ logo, title, subtitle, detailText = '', noticeText = '', detailsLinkText = '', detailsLink = '', logoSize = 46, cardMinWidth = 270, cardMaxWidth = 320 }) {
  const resolvedLogo = logo ? assetUrl(logo) : '';
  const safeResolvedLogo = resolvedLogo ? safeUrl(resolvedLogo) : '';
  const safeDetailsLink = detailsLink ? safeUrl(detailsLink) : '';
  return `
    <div style="display:grid;gap:8px;min-width:${Number(cardMinWidth) || 270}px;max-width:${Number(cardMaxWidth) || 320}px;">
      <div style="display:flex;align-items:center;gap:10px;">
        ${safeResolvedLogo && safeResolvedLogo !== '#' ? `<img src="${safeResolvedLogo}" alt="${escapeHtml(subtitle)} logo" style="width:${Number(logoSize) || 46}px;height:${Number(logoSize) || 46}px;object-fit:contain;display:block;flex:0 0 auto;">` : ''}
        <div>
          <div style="font-size:15px;font-weight:900;letter-spacing:.04em;text-transform:uppercase;color:${DNR_ORANGE};line-height:1.05;">${escapeHtml(subtitle)}</div>
          <div style="font-size:15px;font-weight:900;color:#2b1c12;">${escapeHtml(title)}</div>
        </div>
      </div>
      ${detailText ? `<div style="font-size:12px;line-height:1.35;color:#6b5646;">${escapeHtml(detailText)}</div>` : ''}
      ${noticeText ? `<div style="font-size:12px;line-height:1.4;color:#7b3f1d;font-weight:700;background:#fff4ea;border:1px solid #edc39f;border-radius:10px;padding:8px 10px;">${escapeHtml(noticeText)}</div>` : ''}
      ${safeDetailsLink && safeDetailsLink !== '#' ? `<a href="${escapeHtml(safeDetailsLink)}" target="_blank" rel="noopener noreferrer" style="color:#2f7fd1;font-weight:800;text-decoration:none;">${escapeHtml(detailsLinkText || 'Open details')}</a>` : ''}
    </div>`;
}

function openLandInfoWindow(card, position) {
  closeSelectedHuntFloat();
  closeSelectedHuntPopup();
  closeSelectionInfoWindow();
  selectionInfoWindow = new google.maps.InfoWindow({
    content: card,
    position,
    pixelOffset: new google.maps.Size(0, -12),
    maxWidth: 340
  });
  selectionInfoWindow.open(googleBaselineMap);
}
function openInlineHuntDetails(hunt) {
  const section = document.getElementById('huntDetailsSection');
  const frame = document.getElementById('huntDetailsFrame');
  const title = document.getElementById('huntDetailsTitle');
  const meta = document.getElementById('huntDetailsMeta');
  const fallback = document.getElementById('huntDetailsFallbackLink');
  const link = getBoundaryLink(hunt);
  if (!section || !frame || !link || !hunt) return;
  if (title) title.textContent = `${getHuntCode(hunt)} | ${getUnitName(hunt) || getHuntTitle(hunt)}`;
  if (meta) meta.textContent = `${getSpeciesDisplay(hunt)} | ${getNormalizedSex(hunt)} | ${getHuntType(hunt)} | ${getWeapon(hunt)}`;
  if (fallback) fallback.href = link;
  frame.src = link;
  section.hidden = false;
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  updateStatus('Official Utah DWR hunt details loaded below the map.');
}
function closeInlineHuntDetails() {
  const section = document.getElementById('huntDetailsSection');
  const frame = document.getElementById('huntDetailsFrame');
  if (!section || !frame) return;
  section.hidden = true;
  frame.src = 'about:blank';
}

function buildDnrPlate(hunt, compact = false, roomy = false) {
  const plateUrl = assetUrl(roomy ? LOGO_DNR_ROOMY : LOGO_DNR);
  const code = escapeHtml(getHuntCode(hunt) || '');
  const unit = escapeHtml(getUnitName(hunt) || getHuntTitle(hunt));
  const species = escapeHtml(getSpeciesDisplay(hunt) || 'N/A');
  const sex = escapeHtml(getNormalizedSex(hunt) || 'N/A');
  const huntType = escapeHtml(getHuntType(hunt) || 'N/A');
  const weapon = escapeHtml(getWeapon(hunt) || 'N/A');
  const dates = escapeHtml(getDates(hunt) || 'See official hunt details');
  const heading = escapeHtml(getPanelHeading(hunt));
  const boundaryLink = getBoundaryLink(hunt);
  const boundaryMeta = getBoundaryDisplaySummary(hunt);
  const boundaryLine = escapeHtml(boundaryMeta.line);
  const kmzPath = boundaryMeta.kmzPath;
  const panelWidth = roomy ? 760 : (compact ? 480 : 560);
  const panelHeight = roomy ? 420 : (compact ? 184 : 214);
  const wrapperWidth = compact ? `width:${panelWidth}px;max-width:${panelWidth}px;` : `width:${panelWidth}px;max-width:100%;`;
  const titleSize = roomy ? '24px' : (compact ? '21px' : '23px');
  const metaSize = roomy ? '15px' : (compact ? '14px' : '15px');
  const infoTop = roomy ? '108px' : (compact ? '15px' : '17px');
  const infoLeft = roomy ? '37%' : (compact ? '38%' : '37%');
  const infoRight = roomy ? '30px' : '18px';
  const infoBottom = roomy ? '28px' : '16px';
  const infoGap = roomy ? '10px' : (compact ? '7px' : '9px');
  const detailGap = roomy ? '6px' : (compact ? '4px' : '6px');
  const unitSize = roomy ? '18px' : (compact ? '18px' : '19px');
  const linkSize = roomy ? '16px' : metaSize;

  if (roomy) {
    return `
      <div style="position:relative;width:${panelWidth}px;max-width:100%;height:${panelHeight}px;border:1px solid ${DNR_ORANGE};border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 8px 24px rgba(58,37,18,0.18);">
        <img src="${plateUrl}" alt="Utah DNR hunt information plate" style="display:block;width:${panelWidth}px;max-width:100%;height:${panelHeight}px;object-fit:contain;border:0;">
        <div style="position:absolute;left:52px;top:322px;width:220px;display:grid;gap:1px;color:#2b1c12;">
          <div style="font-size:42px;font-weight:900;line-height:0.98;color:${DNR_BROWN};">${code}</div>
        </div>
        <div style="position:absolute;top:140px;left:37%;right:34px;bottom:28px;display:grid;align-content:start;gap:10px;color:#2b1c12;">
          <div style="display:grid;gap:4px;justify-items:center;text-align:center;">
            <div style="font-size:28px;font-weight:900;letter-spacing:.01em;text-transform:uppercase;color:${DNR_ORANGE};line-height:1.02;">${heading}</div>
            <div style="font-size:32px;font-weight:900;line-height:1.02;">${unit}</div>
          </div>
          <div style="display:grid;gap:6px;font-size:18px;line-height:1.28;">
            <div><strong>Species:</strong> ${species}</div>
            <div><strong>Sex:</strong> ${sex}</div>
            <div><strong>Hunt Type:</strong> ${huntType}</div>
            <div><strong>Weapon:</strong> ${weapon}</div>
            <div><strong>Dates:</strong> ${dates}</div>
          </div>
          ${boundaryLink ? `<button type="button" data-inline-hunt-details style="margin-top:4px;padding:0;border:0;background:transparent;color:#2f7fd1;font-size:18px;font-weight:800;text-decoration:none;text-align:left;cursor:pointer;">Official Utah DWR Hunt Details</button>` : ''}
        </div>
      </div>`;
  }

  return `
    <div style="position:relative;${wrapperWidth}height:${panelHeight}px;border:1px solid ${DNR_ORANGE};border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 8px 24px rgba(58,37,18,0.18);">
      <img src="${plateUrl}" alt="Utah DNR hunt information plate" style="display:block;width:${panelWidth}px;max-width:100%;height:${panelHeight}px;object-fit:fill;border:0;">
      <div style="position:absolute;top:${infoTop};left:${infoLeft};right:${infoRight};bottom:${infoBottom};display:grid;align-content:start;gap:${infoGap};color:#2b1c12;">
        <div style="display:grid;gap:3px;">
          <div style="font-size:${roomy ? '12px' : '13px'};font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:${DNR_ORANGE};">${heading}</div>
          <div style="font-size:${titleSize};font-weight:900;line-height:1.05;">${code}</div>
          <div style="font-size:${unitSize};font-weight:800;line-height:1.12;">${unit}</div>
        </div>
        <div style="display:grid;gap:${detailGap};font-size:${metaSize};line-height:1.28;">
          <div><strong>Species:</strong> ${species}</div>
          <div><strong>Sex:</strong> ${sex}</div>
          <div><strong>Hunt Type:</strong> ${huntType}</div>
          <div><strong>Weapon:</strong> ${weapon}</div>
          <div><strong>Dates:</strong> ${dates}</div>
        </div>
        ${boundaryLink ? `<button type="button" data-inline-hunt-details style="margin-top:2px;padding:0;border:0;background:transparent;color:#2f7fd1;font-size:${linkSize};font-weight:800;text-decoration:none;text-align:left;cursor:pointer;">Official Utah DWR Hunt Details</button>` : ''}
      </div>
    </div>`;
}

async function syncSelectedHuntAcrossMapModes({ closeChooser = true, zoomGoogle = true } = {}) {
  if (!selectedHunt) {
    clearSelectedBoundaryFallbackLayer();
    return;
  }
  renderSelectedHunt();
  renderOutfitters();
  renderMatchingHunts();
  if (closeChooser) closeSelectedHuntPopup();
  try {
    await applySelectedHuntBoundaryResolution(selectedHunt);
  } catch (error) {
    console.warn('Selected hunt boundary resolution failed.', error);
  }
  styleBoundaryLayer();
  updateDwrMapFrame(selectedHunt);

  const mode = safe(mapTypeSelect?.value || 'google').toLowerCase();
  if (mode === 'earth') {
    refreshGoogleEarth3dBoundaryOverlaySoon();
    return;
  }
  if (mode === 'google' && zoomGoogle && huntUnitsLayer && googleBaselineMap) {
    zoomToSelectedBoundary();
  }
}

window.selectHuntByKey = (key, options = {}) => {
  const h = huntData.find(x => getHuntRecordKey(x) === key);
  if (!h) return;
  selectedHuntFocusOnly = !!options.focusOnly;
  selectedHunt = h;
  trackAnalytics('hunt_selected', {
    hunt_code: safe(getHuntCode(h)),
    species: safe(getSpeciesDisplay(h)),
    hunt_type: safe(getHuntType(h)),
    weapon: safe(getWeapon(h)),
  });
  syncSelectedHuntAcrossMapModes({ closeChooser: true, zoomGoogle: true }).catch((error) => {
    console.warn('Hunt selection sync failed.', error);
  });
};
window.selectHuntByCode = (code) => {
  const want = safe(code).trim().toUpperCase();
  if (!want) return;
  const h = huntData.find(x => safe(getHuntCode(x)).trim().toUpperCase() === want);
  if (h) window.selectHuntByKey(getHuntRecordKey(h), { focusOnly: true });
};

function renderSelectedHunt() {
  const panel = document.getElementById('selectedHuntPanel');
  const hunt = selectedHunt;

  if (!panel) return;

  if (!hunt) {
    panel.innerHTML = '<div class="empty-note">Select a hunt to see draw odds, trends, and outfitter matches.</div>';
    closeSelectedHuntFloat();
    return;
  }

  const name = escapeHtml(firstNonEmpty(hunt.hunt_name, getUnitName(hunt), getHuntTitle(hunt), 'Unknown Hunt'));
  const code = escapeHtml(getHuntCode(hunt) || '');
  const species = escapeHtml(getSpeciesDisplay(hunt) || '');
  const weapon = escapeHtml(getWeapon(hunt) || '');
  const huntType = escapeHtml(getHuntType(hunt) || '');
  const boundaryMeta = getBoundaryDisplaySummary(hunt);
  const boundaryLine = escapeHtml(boundaryMeta.line);
  const dwrBoundaryLink = getBoundaryLink(hunt);
  const downloadKmzPath = boundaryMeta.kmzPath;
  const safeDwrBoundaryLink = dwrBoundaryLink ? safeUrl(dwrBoundaryLink) : '';
  const safeDownloadKmzPath = downloadKmzPath ? safeUrl(downloadKmzPath) : '';

  window.UOGA_UI?.recordRecentHunt?.({
    hunt_code: getHuntCode(hunt),
    hunt_name: firstNonEmpty(hunt.hunt_name, getUnitName(hunt), getHuntTitle(hunt), 'Unknown Hunt'),
    unit: getUnitName(hunt),
    species: getSpeciesDisplay(hunt),
    weapon: getWeapon(hunt),
    draw_pool: inferResearchDrawPool(hunt),
    updated_at: Date.now()
  });

  panel.innerHTML = `
    <div class="selected-hunt-card">
      <div style="display:grid; gap:10px;">
        <div><strong>${name}</strong></div>
        <div><strong>Hunt Code:</strong> ${code}</div>
        <div><strong>Species:</strong> ${species}</div>
        <div><strong>Weapon:</strong> ${weapon}</div>
        <div><strong>Hunt Type:</strong> ${huntType}</div>
        <div><strong>${boundaryLine}</strong></div>
        ${safeDwrBoundaryLink && safeDwrBoundaryLink !== '#' ? `<div><a href="${escapeHtml(safeDwrBoundaryLink)}" target="_blank" rel="noopener noreferrer">View on DWR</a></div>` : ''}
        ${safeDownloadKmzPath && safeDownloadKmzPath !== '#' ? `<div><a href="${escapeHtml(safeDownloadKmzPath)}" target="_blank" rel="noopener noreferrer">Download KMZ</a></div>` : ''}

        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
          <button
            type="button"
            class="secondary hunt-research-ring hunt-research-pill"
            id="selectedHuntResearchBtn">
            View Research
          </button>
          <button
            type="button"
            class="secondary hunt-research-ring"
            id="selectedHuntCompareBtn">
            Compare Hunts
          </button>
          <button
            type="button"
            class="secondary hunt-research-ring"
            id="selectedHuntSaveBtn">
            Save Hunt
          </button>
          <button
            type="button"
            class="secondary hunt-research-ring"
            id="selectedHuntOutfittersBtn">
            Find Outfitters
          </button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('selectedHuntResearchBtn')?.addEventListener('click', () => {
    saveHuntAndOpenResearch(hunt, 'Resident', 12);
  });
  document.getElementById('selectedHuntCompareBtn')?.addEventListener('click', () => {
    openCompareHunts(hunt, 'Resident', 12);
  });
  document.getElementById('selectedHuntSaveBtn')?.addEventListener('click', () => {
    const record = saveHuntToBackpack(hunt, 'Resident', 12);
    if (record?.hunt_code) updateStatus(`${record.hunt_code} saved to Hunt Backpack.`);
  });
  document.getElementById('selectedHuntOutfittersBtn')?.addEventListener('click', () => {
    openOutfitterMatches(hunt);
  });

  if (safe(mapTypeSelect?.value).toLowerCase() === 'dwr') {
    updateDwrMapFrame(hunt);
  }

  openSelectedHuntFloat();
}

function getMatchingOutfittersForHunt(hunt) {
  if (!hunt || !outfitters.length) return [];
  const publishedCoverage = getFederalCoverageForHunt(hunt);
  const species = normalizeBoundaryKey(getSpeciesDisplay(hunt));
  const unitCode = normalizeBoundaryKey(getUnitCode(hunt));
  const unitName = normalizeBoundaryKey(getUnitName(hunt));
  const requiredUsfsForests = getRequiredUsfsForestsForHunt(hunt);
  const evaluated = outfitters.map(o => {
    const speciesServed = normalizeListValues(o.speciesServed).map(normalizeBoundaryKey);
    const unitsServed = normalizeListValues(o.unitsServed).map(normalizeBoundaryKey);
    const usfsForests = normalizeListValues(o.usfsForests).map(normalizeBoundaryKey);
    const usfsForestIds = normalizeListValues(o.usfsForestIds).map(normalizeBoundaryKey);
    const speciesMatch = !speciesServed.length || speciesServed.includes(species);
    const unitMatch = !unitsServed.length
      || unitsServed.includes(unitCode)
      || unitsServed.includes(unitName)
      || unitsServed.some(u => unitName.includes(u) || u.includes(unitName) || unitCode.includes(u));
    const forestMatch = !requiredUsfsForests.length
      || requiredUsfsForests.some(required => usfsForestIds.includes(required) || usfsForests.includes(required));
    const confidence = [
      speciesMatch ? 1 : 0,
      unitMatch ? 1 : 0,
      forestMatch ? 2 : 0,
      usfsForestIds.length ? 1 : 0
    ].reduce((sum, value) => sum + value, 0);
    const matchReasons = [];
    if (forestMatch && requiredUsfsForests.length) {
      const forestLabel = requiredUsfsForests[0]
        .split('-')
        .map(part => titleCaseWords(part))
        .join('-');
      matchReasons.push(`${forestLabel} Permit Match`);
    }
    if (unitMatch && unitsServed.length) matchReasons.push('Unit Match');
    if (speciesMatch && speciesServed.length) matchReasons.push('Species Match');
    if (o.guidedHunts) matchReasons.push('Guided Hunts');
    return { outfitter: o, speciesMatch, unitMatch, forestMatch, confidence, matchReasons };
  });

  const strongMatches = evaluated
    .filter(row => row.speciesMatch && row.unitMatch && row.forestMatch)
    .sort((a, b) => b.confidence - a.confidence || a.outfitter.listingName.localeCompare(b.outfitter.listingName))
    .map(row => ({ ...row.outfitter, matchReasons: row.matchReasons }));

  const speciesOnlyMatches = evaluated
    .filter(row => row.speciesMatch && row.forestMatch)
    .sort((a, b) => b.confidence - a.confidence || a.outfitter.listingName.localeCompare(b.outfitter.listingName))
    .map(row => ({ ...row.outfitter, matchReasons: row.matchReasons }));

  const fallbackMatches = strongMatches.length ? strongMatches : speciesOnlyMatches;
  if (publishedCoverage && publishedCoverage.federalCoverageEligible !== 'No') {
    const publishedNames = normalizeListValues(
      publishedCoverage.federalPermitMatchedOutfitters?.length
        ? publishedCoverage.federalPermitMatchedOutfitters
        : publishedCoverage.usfsPermitMatchedOutfitters
    );
    if (publishedNames.length) {
      const lookup = new Map(outfitters.map(o => [safe(o.listingName).trim().toLowerCase(), o]));
      const publishedMatches = publishedNames
        .map(name => lookup.get(safe(name).trim().toLowerCase()))
        .filter(Boolean)
        .map(o => {
          const matchReasons = [];
          if (publishedCoverage.primaryUsfsForestName) {
            matchReasons.push(`${publishedCoverage.primaryUsfsForestName} Permit Match`);
          }
          if (publishedCoverage.primaryBlmDistrictName) {
            matchReasons.push(`${publishedCoverage.primaryBlmDistrictName} Permit Match`);
          }
          return { ...o, matchReasons: [...new Set(matchReasons)] };
        });
      const merged = [];
      const mergedIndex = new Map();
      const upsert = (candidate) => {
        const key = safe(firstNonEmpty(candidate.id, candidate.slug, candidate.listingName)).trim().toLowerCase();
        if (!key) return;
        const existing = mergedIndex.get(key);
        if (!existing) {
          const normalized = {
            ...candidate,
            matchReasons: [...new Set(normalizeListValues(candidate.matchReasons))]
          };
          mergedIndex.set(key, normalized);
          merged.push(normalized);
          return;
        }
        existing.matchReasons = [...new Set([
          ...normalizeListValues(existing.matchReasons),
          ...normalizeListValues(candidate.matchReasons)
        ])];
      };
      publishedMatches.forEach(upsert);
      fallbackMatches.forEach(upsert);
      if (merged.length) return orderOutfitterMatchesForDisplay(hunt, merged, requiredUsfsForests);
    }
  }
  return orderOutfitterMatchesForDisplay(hunt, fallbackMatches, requiredUsfsForests);
}

function renderOutfitters() {
  const container = document.getElementById('outfitterResults');
  if (!container) return;
  if (!selectedHunt) {
    container.innerHTML = '<div class="empty-note">Select a hunt to load matching verified outfitters.</div>';
    clearOutfitterMarkers();
    return;
  }
  const matches = getMatchingOutfittersForHunt(selectedHunt);
  if (!matches.length) {
    container.innerHTML = '<div class="empty-note">No verified outfitters matched this hunt yet.</div>';
    clearOutfitterMarkers();
    return;
  }
  container.innerHTML = matches.map(o => {
    const website = safe(o.website).trim();
    const safeWebsite = website ? safeUrl(website) : '';
    const phone = getOutfitterPrimaryPhone(o);
    const email = getOutfitterPrimaryEmail(o);
    const logo = safe(o.logoUrl).trim();
    const safeLogo = logo ? safeUrl(logo) : '';
    const location = getOutfitterLocationText(o);
    const tags = [...normalizeListValues(o.matchReasons), ...getOutfitterSummaryTags(o)].slice(0, 4);
    return `
      <div class="outfitter-card" data-outfitter-id="${escapeHtml(firstNonEmpty(o.id, o.slug, o.listingName))}" role="button" tabindex="0" title="Zoom to ${escapeHtml(o.listingName || 'outfitter')}">
        <div class="outfitter-card-header">
          ${safeLogo && safeLogo !== '#' ? `<img class="outfitter-card-logo" src="${escapeHtml(safeLogo)}" alt="${escapeHtml(o.listingName || 'Outfitter logo')}">` : ''}
          <div class="outfitter-card-title-wrap">
            <div class="hunt-card-title">${escapeHtml(o.listingName || 'Outfitter')}</div>
            <div class="outfitter-card-subline">${escapeHtml(normalizeVisibleVerificationLabel(firstNonEmpty(o.verificationStatus, o.certLevel, o.listingType, 'Outfitter')))}</div>
          </div>
        </div>
        ${location ? `<div class="outfitter-card-subline">${escapeHtml(location)}</div>` : ''}
        ${tags.length ? `<div class="outfitter-card-meta-row">${tags.map(tag => `<span class="outfitter-card-chip">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
        <div class="outfitter-card-actions">
          <button type="button" class="outfitter-action-btn primary" data-outfitter-focus="${escapeHtml(firstNonEmpty(o.id, o.slug, o.listingName))}">Map Link</button>
          ${safeWebsite && safeWebsite !== '#' ? `<a class="outfitter-action-btn" href="${escapeHtml(safeWebsite)}" target="_blank" rel="noopener noreferrer">Website</a>` : ''}
        </div>
        ${phone ? `<div class="hunt-card-meta">${escapeHtml(phone)}</div>` : ''}
        ${email ? `<div class="hunt-card-meta">${escapeHtml(email)}</div>` : ''}
      </div>`;
  }).join('');
  container.querySelectorAll('[data-outfitter-focus]').forEach(button => {
    const outfitterId = button.getAttribute('data-outfitter-focus');
    const outfitter = matches.find(item => firstNonEmpty(item.id, item.slug, item.listingName) === outfitterId);
    if (!outfitter) return;
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      focusOutfitter(outfitter);
    });
  });
  container.querySelectorAll('[data-outfitter-id]').forEach(card => {
    const outfitterId = card.getAttribute('data-outfitter-id');
    const outfitter = matches.find(item => firstNonEmpty(item.id, item.slug, item.listingName) === outfitterId);
    if (!outfitter) return;
    const open = () => focusOutfitter(outfitter);
    card.addEventListener('click', open);
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
  });
  updateOutfitterMarkers(matches);
}

function getOutfitterLocationText(outfitter) {
  const address = safe(outfitter.address).trim();
  const hometown = safe(outfitter.hometown).trim();
  const city = safe(outfitter.city).trim();
  const region = safe(outfitter.region).trim();
  const state = safe(outfitter.state).trim() || 'Utah';
  if (address) return address;
  if (hometown && city && hometown.toLowerCase() !== city.toLowerCase()) return `${hometown} | ${city}, ${state}`;
  if (hometown) return hometown;
  if (city) return `${city}, ${state}`;
  if (region) return region;
  return '';
}
function getOutfitterPrimaryPhone(outfitter) {
  return choosePrimaryListValue(outfitter.phonePrimary, outfitter.phone);
}
function getOutfitterPrimaryEmail(outfitter) {
  return choosePrimaryListValue(outfitter.emailPrimary, outfitter.email);
}
function getOutfitterSummaryTags(outfitter) {
  const tags = [];
  const listingType = normalizeVisibleVerificationLabel(firstNonEmpty(outfitter.verificationStatus, outfitter.certLevel, outfitter.listingType));
  if (listingType) tags.push(listingType);
  if (outfitter.guidedHunts) tags.push('Guided Hunts');
  if (outfitter.packTrips) tags.push('Pack Trips');
  if (outfitter.lodgingIncluded) tags.push('Lodging');
  if (outfitter.archery) tags.push('Archery');
  if (outfitter.muzzleloader) tags.push('Muzzleloader');
  return Array.from(new Set(tags));
}
function getKnownOutfitterCoords(outfitter) {
  const keys = [
    firstNonEmpty(outfitter?.id),
    firstNonEmpty(outfitter?.slug),
    safe(firstNonEmpty(outfitter?.listingName, outfitter?.displayName, outfitter?.businessName)).toLowerCase().trim()
  ].filter(Boolean);
  for (const key of keys) {
    const coords = KNOWN_OUTFITTER_COORDS.get(key);
    if (coords && Number.isFinite(coords.lat) && Number.isFinite(coords.lng)) return coords;
  }
  return null;
}
function isWithinUtahBounds(lat, lng) {
  return Number.isFinite(lat) && Number.isFinite(lng)
    && lat >= UTAH_LOCATION_BOUNDS.minLat
    && lat <= UTAH_LOCATION_BOUNDS.maxLat
    && lng >= UTAH_LOCATION_BOUNDS.minLng
    && lng <= UTAH_LOCATION_BOUNDS.maxLng;
}
function getLatLngLiteral(value) {
  if (!value) return null;
  if (typeof value.lat === 'function' && typeof value.lng === 'function') {
    return { lat: value.lat(), lng: value.lng() };
  }
  if (typeof value.lat === 'number' && typeof value.lng === 'number') {
    return { lat: value.lat, lng: value.lng };
  }
  return null;
}
function isUtahGeocodeResult(result) {
  const location = getLatLngLiteral(result?.geometry?.location);
  if (!location || !isWithinUtahBounds(location.lat, location.lng)) return false;
  const components = Array.isArray(result?.address_components) ? result.address_components : [];
  const stateComponent = components.find(component => Array.isArray(component.types) && component.types.includes('administrative_area_level_1'));
  if (!stateComponent) return true;
  const shortName = safe(stateComponent.short_name).toUpperCase();
  const longName = safe(stateComponent.long_name).toUpperCase();
  return shortName === 'UT' || longName === 'UTAH';
}
function formatUtahAddressPart(value) {
  return safe(value)
    .replace(/\bNorth\b/ig, 'N')
    .replace(/\bSouth\b/ig, 'S')
    .replace(/\bEast\b/ig, 'E')
    .replace(/\bWest\b/ig, 'W')
    .replace(/\bUtah\b/ig, 'UT')
    .replace(/\s+/g, ' ')
    .replace(/\s*\.\s*/g, '.')
    .trim();
}
function cleanUtahAddress(rawAddress, city, state) {
  const raw = safe(rawAddress).trim();
  if (!raw) return '';
  const parts = raw.split(',').map(part => formatUtahAddressPart(part)).filter(Boolean);
  const cityText = formatUtahAddressPart(city);
  const stateText = formatUtahAddressPart(state) || 'UT';
  const zip = firstNonEmpty(raw.match(/\b\d{5}(?:-\d{4})?\b/)?.[0], '');
  const street = parts.find(part => /\d/.test(part) && /\b(?:N|S|E|W|HWY|HIGHWAY|RD|ROAD|ST|STREET|AVE|AVENUE|DR|DRIVE|LN|LANE|BLVD|WAY|CT|COURT|CIR|CIRCLE)\b/i.test(part))
    || parts.find(part => /\d/.test(part) && !/\b(?:UT|USA|UNITED STATES)\b/i.test(part))
    || '';
  const cityCandidate = cityText
    || parts.find(part => /^[A-Za-z .'-]+$/.test(part) && !/\b(?:UT|USA|UNITED STATES)\b/i.test(part) && !/\d/.test(part))
    || '';
  const normalizedState = stateText.toUpperCase() === 'UTAH' ? 'UT' : stateText.toUpperCase();
  const combined = [street, cityCandidate, normalizedState, zip].filter(Boolean).join(', ');
  return combined.length >= 8 ? combined : '';
}
function getOutfitterGeocodeQueries(outfitter) {
  const address = safe(outfitter.address).trim();
  const hometown = safe(outfitter.hometown).trim();
  const city = safe(outfitter.city).trim();
  const region = safe(outfitter.region).trim();
  const state = safe(outfitter.state).trim() || 'Utah';
  const cleanedAddress = cleanUtahAddress(address, city || hometown, state);
  const queries = [];
  const pushQuery = value => {
    const text = safe(value).trim();
    if (!text) return;
    if (/^utah$/i.test(text)) return;
    if (!queries.includes(text)) queries.push(text);
  };

  pushQuery(cleanedAddress);
  pushQuery(address);
  if (address && !/utah/i.test(address)) pushQuery(`${address}, ${state}`);
  if (cleanedAddress && !/\bUT\b/i.test(cleanedAddress) && !/utah/i.test(cleanedAddress)) pushQuery(`${cleanedAddress}, UT`);
  if (hometown && city && hometown.toLowerCase() !== city.toLowerCase()) pushQuery(`${hometown}, ${city}, ${state}`);
  pushQuery(hometown && !/utah/i.test(hometown) ? `${hometown}, ${state}` : hometown);
  pushQuery(city ? `${city}, ${state}` : '');
  pushQuery(region && !/utah/i.test(region) ? `${region}, ${state}` : region);
  return queries;
}

function buildOutfitterPopupCard(outfitter) {
  const logo = safe(outfitter.logoUrl).trim();
  const safeLogo = logo ? safeUrl(logo) : '';
  const name = safe(outfitter.listingName).trim() || 'Outfitter';
  const website = safe(outfitter.website).trim();
  const safeWebsite = website ? safeUrl(website) : '';
  const phone = getOutfitterPrimaryPhone(outfitter);
  const email = getOutfitterPrimaryEmail(outfitter);
  const location = getOutfitterLocationText(outfitter);
  const tags = [...normalizeListValues(outfitter.matchReasons), ...getOutfitterSummaryTags(outfitter)].slice(0, 5);
  return `
    <div style="display:grid;gap:10px;min-width:280px;max-width:340px;">
      <div style="display:grid;grid-template-columns:58px minmax(0,1fr);align-items:center;gap:12px;">
        ${safeLogo && safeLogo !== '#' ? `<img src="${escapeHtml(safeLogo)}" alt="${escapeHtml(name)} logo" style="width:58px;height:58px;object-fit:cover;object-position:center;border-radius:12px;background:#fff;padding:3px;border:1px solid #d6c1ae;box-shadow:0 6px 14px rgba(0,0,0,.14);">` : ''}
        <div>
          <div style="font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:${DNR_ORANGE};">Verified Outfitter</div>
          <div style="font-size:17px;font-weight:900;color:#2b1c12;line-height:1.15;">${escapeHtml(name)}</div>
        </div>
      </div>
      ${tags.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px;">${tags.map(tag => `<span style="display:inline-flex;align-items:center;padding:5px 9px;border-radius:999px;background:rgba(214,106,31,.11);border:1px solid rgba(214,106,31,.2);font-size:12px;font-weight:800;color:#3b2417;">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
      ${location ? `<div style="font-size:13px;color:#6b5646;line-height:1.35;">${escapeHtml(location)}</div>` : ''}
      ${phone ? `<div style="font-size:13px;color:#6b5646;">${escapeHtml(phone)}</div>` : ''}
      ${email ? `<div style="font-size:13px;color:#6b5646;">${escapeHtml(email)}</div>` : ''}
      ${safeWebsite && safeWebsite !== '#' ? `<a href="${escapeHtml(safeWebsite)}" target="_blank" rel="noopener noreferrer" style="color:#2f7fd1;font-weight:800;text-decoration:none;">Visit website</a>` : ''}
    </div>`;
}
function openOutfitterInfoWindow(outfitter, position) {
  noteOutfitterInteraction();
  closeSelectionInfoWindow();
  selectionInfoWindow = new google.maps.InfoWindow({
    content: buildOutfitterPopupCard(outfitter),
    position,
    pixelOffset: new google.maps.Size(0, -36)
  });
  selectionInfoWindow.open(googleBaselineMap);
}
function toLatLngLiteral(value) {
  if (!value) return null;
  if (typeof value.lat === 'function' && typeof value.lng === 'function') {
    return { lat: value.lat(), lng: value.lng() };
  }
  if (typeof value.lat === 'number' && typeof value.lng === 'number') {
    return { lat: value.lat, lng: value.lng };
  }
  return null;
}
function getDistanceMeters(a, b) {
  const p1 = toLatLngLiteral(a);
  const p2 = toLatLngLiteral(b);
  if (!p1 || !p2) return Number.POSITIVE_INFINITY;
  const toRad = (deg) => deg * Math.PI / 180;
  const earthRadius = 6371000;
  const dLat = toRad(p2.lat - p1.lat);
  const dLng = toRad(p2.lng - p1.lng);
  const lat1 = toRad(p1.lat);
  const lat2 = toRad(p2.lat);
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earthRadius * Math.asin(Math.sqrt(h));
}
function findNearbyOutfitterMarker(position, maxDistanceMeters = 120) {
  let nearest = null;
  let nearestDistance = Number.POSITIVE_INFINITY;
  outfitterMarkerIndex.forEach(({ position: markerPosition, outfitter }) => {
    const distance = getDistanceMeters(position, markerPosition);
    if (distance < nearestDistance && distance <= maxDistanceMeters) {
      nearest = { outfitter, position: markerPosition, distance };
      nearestDistance = distance;
    }
  });
  return nearest;
}
function resolveOutfitterPriorityClick(position) {
  const nearby = findNearbyOutfitterMarker(position);
  if (!nearby) return false;
  focusOutfitter(nearby.outfitter);
  return true;
}

function clearOutfitterMarkers() {
  outfitterMarkerRunId += 1;
  outfitterMarkers.forEach(marker => marker?.setMap?.(null));
  outfitterMarkers = [];
  outfitterMarkerIndex.clear();
}

function createOutfitterLogoMarker(position, outfitter) {
  const marker = new google.maps.OverlayView();
  marker.position = position;
  marker.outfitter = outfitter;
  marker.div = null;
  marker.onAdd = function() {
    const div = document.createElement('div');
    div.className = 'outfitter-logo-pin-shell';
    const initials = (safe(outfitter.listingName).trim().match(/[A-Z0-9]/ig) || ['O']).slice(0, 2).join('').toUpperCase();
    const logoUrl = safe(outfitter.logoUrl).trim();
    const safeLogoUrl = logoUrl ? safeUrl(logoUrl) : '';
    const logoMarkup = safeLogoUrl && safeLogoUrl !== '#'
      ? `<img src="${escapeHtml(safeLogoUrl)}" alt="${escapeHtml(outfitter.listingName || 'Outfitter')}">`
      : `<span class="outfitter-logo-pin-fallback">${escapeHtml(initials)}</span>`;
    div.innerHTML = `
      <div class="outfitter-logo-pin-base"></div>
      <div class="outfitter-logo-pin-center">
        ${logoMarkup}
      </div>`;
    div.title = safe(outfitter.listingName).trim() || 'Outfitter';
    div.style.pointerEvents = 'auto';
    if (google.maps.OverlayView?.preventMapHitsAndGesturesFrom) {
      google.maps.OverlayView.preventMapHitsAndGesturesFrom(div);
    }
    const openOutfitterInfo = (event) => {
      if (event) {
        event.preventDefault?.();
        event.stopPropagation?.();
      }
      openOutfitterInfoWindow(outfitter, position);
    };
    ['pointerdown', 'mousedown', 'touchstart'].forEach(type => {
      div.addEventListener(type, event => {
        event.preventDefault?.();
        event.stopPropagation?.();
        noteOutfitterInteraction();
      }, { passive: false });
    });
    div.addEventListener('click', openOutfitterInfo, { passive: false });
    this.div = div;
    this.getPanes().overlayMouseTarget.appendChild(div);
  };
  marker.draw = function() {
    if (!this.div) return;
    const projection = this.getProjection();
    if (!projection) return;
    const point = projection.fromLatLngToDivPixel(position);
    if (!point) return;
    this.div.style.position = 'absolute';
    this.div.style.left = `${point.x - 27}px`;
    this.div.style.top = `${point.y - 82}px`;
  };
  marker.onRemove = function() {
    if (this.div?.parentNode) this.div.parentNode.removeChild(this.div);
    this.div = null;
  };
  return marker;
}

function geocodeOutfitter(outfitter) {
  const key = `${safe(outfitter.listingName)}|${getOutfitterLocationText(outfitter)}`;
  if (outfitterGeocodeCache.has(key)) {
    return Promise.resolve(outfitterGeocodeCache.get(key));
  }
  const knownCoords = getKnownOutfitterCoords(outfitter);
  if (knownCoords) {
    const knownLocation = new google.maps.LatLng(knownCoords.lat, knownCoords.lng);
    outfitterGeocodeCache.set(key, knownLocation);
    return Promise.resolve(knownLocation);
  }
  if (Number.isFinite(outfitter?.latitude) && Number.isFinite(outfitter?.longitude)) {
    if (isWithinUtahBounds(outfitter.latitude, outfitter.longitude)) {
      const directLocation = new google.maps.LatLng(outfitter.latitude, outfitter.longitude);
      outfitterGeocodeCache.set(key, directLocation);
      return Promise.resolve(directLocation);
    }
  }
  if (!google.maps?.Geocoder) return Promise.resolve(null);
  const queries = getOutfitterGeocodeQueries(outfitter);
  if (!queries.length) return Promise.resolve(null);
  const geocoder = new google.maps.Geocoder();
  return new Promise(async resolve => {
    for (const query of queries) {
      const loc = await new Promise(done => {
        geocoder.geocode({
          address: query,
          componentRestrictions: { country: 'US' }
        }, (results, status) => {
          const result = status === 'OK' && Array.isArray(results)
            ? results.find(entry => isUtahGeocodeResult(entry))
            : null;
          const location = result?.geometry?.location || null;
          done(location);
        });
      });
      if (loc) {
        outfitterGeocodeCache.set(key, loc);
        resolve(loc);
        return;
      }
    }
    outfitterGeocodeCache.set(key, null);
    resolve(null);
  });
}
async function focusOutfitter(outfitter) {
  if (!googleBaselineMap || !outfitter) return;
  const markerKey = firstNonEmpty(outfitter.id, outfitter.slug, outfitter.listingName);
  const indexed = outfitterMarkerIndex.get(markerKey);
  let location = indexed?.position || null;
  if (!location) {
    location = await geocodeOutfitter(outfitter);
  }
  if (!location) {
    updateStatus(`Couldn't place ${firstNonEmpty(outfitter.listingName, 'that outfitter')} on the map yet.`);
    return;
  }
  noteOutfitterInteraction();
  if (safe(mapTypeSelect?.value).toLowerCase() === 'earth') {
    mapTypeSelect.value = 'google';
    applyMapMode();
  }
  googleBaselineMap.panTo(location);
  if ((googleBaselineMap.getZoom?.() || 0) < 14) {
    googleBaselineMap.setZoom(14);
  }
  openOutfitterInfoWindow(outfitter, location);
  updateStatus(`${firstNonEmpty(outfitter.listingName, 'Outfitter')} focused on the map.`);
}

async function updateOutfitterMarkers(matches) {
  clearOutfitterMarkers();
  const runId = outfitterMarkerRunId;
  if (!googleBaselineMap || safe(mapTypeSelect?.value).toLowerCase() !== 'google') return;
  const unique = [];
  const seen = new Set();
  for (const outfitter of matches) {
    const name = safe(outfitter.listingName).trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    unique.push(outfitter);
  }
  for (const outfitter of unique) {
    try {
      const location = await geocodeOutfitter(outfitter);
      if (runId !== outfitterMarkerRunId) return;
      if (!location) continue;
      const marker = createOutfitterLogoMarker(location, outfitter);
      marker.setMap(googleBaselineMap);
      outfitterMarkers.push(marker);
      outfitterMarkerIndex.set(firstNonEmpty(outfitter.id, outfitter.slug, outfitter.listingName), { marker, position: location });
    } catch (error) {
      console.error('Outfitter marker failed', outfitter?.listingName, error);
    }
  }
}

function updateStateLayersSummary() {
  if (!stateLayersSummary) return;
  const count = [toggleSITLA, toggleStateParks, toggleWma].filter(el => !!el?.checked).length;
  stateLayersSummary.textContent = count ? `(${count})` : '';
}
function updateFederalLayersSummary() {
  if (!federalLayersSummary) return;
  const count = [toggleUSFS, toggleBLM, toggleBLMDetail].filter(el => !!el?.checked).length;
  federalLayersSummary.textContent = count ? `(${count})` : '';
}
function updatePrivateLayersSummary() {
  if (!privateLayersSummary) return;
  const count = [togglePrivate, toggleCwmu].filter(el => !!el?.checked).length;
  privateLayersSummary.textContent = count ? `(${count})` : '';
}

function openSelectedHuntPopup() {
  closeSelectedHuntPopup();
}

function closeSelectedHuntPopup() {
  if (!mapChooser) return;
  mapChooser.classList.remove('is-open');
  mapChooser.classList.remove('is-hunt-results');
  mapChooser.setAttribute('aria-hidden', 'true');
  selectedBoundaryMatches = [];
  if (mapChooserBody) {
    mapChooserBody.innerHTML = '<div class="map-chooser-empty">Click a hunt boundary to load matching hunts.</div>';
  }
}

function getFeatureMatches(feature) {
  const displayBoundaryId = safe(feature?.getProperty?.('UOGA_DISPLAY_BOUNDARY_ID')).trim();
  const featureHuntCodes = safe(feature?.getProperty?.('UOGA_HUNT_CODES'))
    .split('|')
    .map((code) => safe(code).trim().toUpperCase())
    .filter(Boolean);
  if (displayBoundaryId || featureHuntCodes.length) {
    const displaySource = getDisplayHunts();
    const source = (hasActiveMatrixSelections() || selectedHunt) ? displaySource : huntData;
    return source.filter((hunt) => {
      const huntCode = safe(getHuntCode(hunt)).trim().toUpperCase();
      if (!huntCode) return false;
      if (featureHuntCodes.includes(huntCode)) return true;
      if (displayBoundaryId) return getDisplayBoundaryIdForHunt(hunt) === displayBoundaryId;
      return false;
    });
  }

  const featureBoundaryIds = getDataFeatureBoundaryCandidateIds(feature);
  const boundaryIdSet = new Set(featureBoundaryIds);
  const displaySource = getDisplayHunts();
  const source = (hasActiveMatrixSelections() || selectedHunt) ? displaySource : huntData;
  return source.filter(h => {
    const resolvedIds = getResolvedBoundaryIdsForHunt(h);
    return resolvedIds.some(id => boundaryIdSet.has(id));
  });
}

function buildPopupCardForHunt(hunt) {
  // Keep map popups clean: no large branding plates/logos. Hunters want the code + unit + key details fast.
  const code = escapeHtml(getHuntCode(hunt) || '');
  const unit = escapeHtml(getUnitName(hunt) || getHuntTitle(hunt));
  const species = escapeHtml(getSpeciesDisplay(hunt) || 'N/A');
  const sex = escapeHtml(getNormalizedSex(hunt) || 'N/A');
  const huntType = escapeHtml(getHuntType(hunt) || 'N/A');
  const weapon = escapeHtml(getWeapon(hunt) || 'N/A');
  const dates = escapeHtml(getDates(hunt) || 'See official hunt details');
  const heading = escapeHtml(getPanelHeading(hunt));
  const boundaryLink = getBoundaryLink(hunt);
  const boundaryMeta = getBoundaryDisplaySummary(hunt);
  const boundaryLine = escapeHtml(boundaryMeta.line);
  const kmzPath = boundaryMeta.kmzPath;
  const safeKmzPath = kmzPath ? safeUrl(kmzPath) : '';

  return `
    <div style="min-width:320px;max-width:420px;border:1px solid rgba(92,65,45,.75);border-radius:14px;overflow:hidden;background:rgba(35,30,26,.96);color:#f4efe4;box-shadow:0 12px 34px rgba(0,0,0,.35);">
      <div style="padding:12px 14px;border-bottom:1px solid rgba(244,239,228,.12);background:linear-gradient(180deg, rgba(255,102,0,.20), rgba(255,102,0,.06));">
        <div style="font-size:11px;font-weight:900;letter-spacing:.10em;text-transform:uppercase;color:#ff6600;">${heading}</div>
        <div style="margin-top:4px;display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="font-size:18px;font-weight:900;line-height:1.1;">${unit}</div>
          <div style="font-size:16px;font-weight:900;letter-spacing:.02em;">${code}</div>
        </div>
      </div>
      <div style="padding:12px 14px;display:grid;gap:8px;">
        <div style="font-size:13px;color:rgba(244,239,228,.78);line-height:1.35;">${species} | ${sex} | ${huntType}</div>
        <div style="font-size:13px;color:rgba(244,239,228,.78);line-height:1.35;">${weapon}</div>
        <div style="font-size:13px;color:rgba(244,239,228,.78);line-height:1.35;">${dates}</div>
        <div style="font-size:13px;color:rgba(244,239,228,.9);line-height:1.35;">${boundaryLine}</div>
        ${boundaryLink ? `<button type="button" data-inline-hunt-details class="secondary" style="justify-self:start;">Official Utah DWR Hunt Details</button>` : ''}
        ${safeKmzPath && safeKmzPath !== '#' ? `<a href="${escapeHtml(safeKmzPath)}" target="_blank" rel="noopener noreferrer" style="color:#ffba7d;font-weight:700;text-decoration:none;">Download KMZ</a>` : ''}
      </div>
    </div>`;
}

function buildPopupListForMatches(matches) {
  return `
    <div style="display:grid;gap:10px;min-width:320px;max-width:380px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <img src="${LOGO_DWR_SELECTOR}" alt="Utah DWR logo" style="width:48px;height:48px;object-fit:contain;border-radius:8px;background:#fff;padding:3px;border:1px solid #d6c1ae;">
        <div>
          <div style="font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:${DNR_ORANGE};">DWR Hunt Unit</div>
          <div style="font-size:15px;font-weight:900;color:#2b1c12;">Multiple Available Hunts</div>
        </div>
      </div>
      ${matches.slice(0, 8).map(h => `
        <button type="button" data-popup-hunt-key="${escapeHtml(getHuntRecordKey(h))}" style="text-align:left;border:1px solid #d6c1ae;border-radius:10px;background:#fffdf8;padding:10px;cursor:pointer;color:#2b1c12;">
          <div style="font-weight:900;">${escapeHtml(getHuntCode(h))} | ${escapeHtml(getUnitName(h) || getHuntTitle(h))}</div>
          <div style="font-size:12px;color:#6b5646;">${escapeHtml(getSpeciesDisplay(h))} | ${escapeHtml(getNormalizedSex(h))} | ${escapeHtml(getWeapon(h))}</div>
        </button>
      `).join('')}
    </div>`;
}

function showHuntMatchesChooser(title, matches, kicker = 'Available Hunts') {
  if (!mapChooser || !mapChooserBody || !mapChooserTitle || !mapChooserKicker) return;
  closeSelectedHuntFloat();
  selectedBoundaryMatches = matches.slice();
  mapChooserKicker.textContent = kicker;
  mapChooserTitle.textContent = firstNonEmpty(title, 'Available Hunts');
  mapChooser.classList.add('is-hunt-results');
  mapChooserBody.innerHTML = matches.length ? matches.slice(0, 12).map(h => `
    <div class="map-chooser-card" data-popup-hunt-key="${escapeHtml(getHuntRecordKey(h))}" role="button" tabindex="0">
      <div class="hunt-card-title">${escapeHtml(getHuntCode(h))} | ${escapeHtml(getUnitName(h) || getHuntTitle(h))}</div>
      <div class="map-chooser-meta">${escapeHtml(getSpeciesDisplay(h))} | ${escapeHtml(getNormalizedSex(h))} | ${escapeHtml(getHuntType(h))}</div>
      <div class="map-chooser-meta">${escapeHtml(getWeapon(h))} | ${escapeHtml(getDates(h) || 'See official hunt details')}</div>
    </div>
  `).join('') : '<div class="map-chooser-empty">No matching hunts found for this boundary.</div>';
  mapChooser.classList.add('is-open');
  mapChooser.setAttribute('aria-hidden', 'false');
  mapChooserBody.querySelectorAll('[data-popup-hunt-key]').forEach(card => {
    const select = () => {
      closeSelectedHuntPopup();
      window.selectHuntByKey(card.getAttribute('data-popup-hunt-key'));
    };
    card.addEventListener('click', select);
    card.addEventListener('keydown', evt => {
      if (evt.key === 'Enter' || evt.key === ' ') {
        evt.preventDefault();
        select();
      }
    });
  });
}
function openMapChooser(feature, matches) {
  const boundaryName = firstNonEmpty(feature?.getProperty?.('Boundary_Name'), 'Selected Unit');
  showHuntMatchesChooser(boundaryName, matches, hasActiveMatrixSelections() || selectedHunt ? 'Available Hunts' : 'Selected Unit');
}

function openBoundaryPopup(feature, latLng) {
  if (!googleBaselineMap || !feature || !latLng) return;
  suppressLandClickUntil = Date.now() + 240;
  const matches = getFeatureMatches(feature);
  selectedBoundaryFeature = feature;
  selectedBoundaryMatches = matches.slice();
  closeSelectionInfoWindow();
  closeSelectedHuntPopup();
  fitDataFeatureBounds(feature, 11);
  const boundaryName = firstNonEmpty(feature?.getProperty?.('Boundary_Name'), 'Selected Unit');
  if (matches.length > 1) {
    openMapChooser(feature, matches);
    updateStatus(`${matches.length} matching hunts in ${boundaryName}. Choose one to fly in.`);
    return;
  }
  if (matches.length === 1) {
    const key = getHuntRecordKey(matches[0]);
    if (key) {
      window.selectHuntByKey(key);
      updateStatus(`Selected ${getHuntCode(matches[0]) || 'hunt'} in ${boundaryName}.`);
      return;
    }
  }
  updateStatus(`Zoomed to ${boundaryName}.`);
}

async function loadOutfitters() {
  outfitters = await loadFirstNormalizedList(OUTFITTERS_DATA_SOURCES, normalizeOutfitterList, []);
}
async function loadOutfitterFederalCoverage() {
  const normalized = await loadFirstNormalizedList(OUTFITTER_FEDERAL_COVERAGE_SOURCES, normalizeOutfitterCoverageList, []);
  indexOutfitterFederalCoverage(normalized);
}
function getLatLngCacheKey(latLng, precision = 4) {
  if (!latLng) return '';
  return `${Number(latLng.lat()).toFixed(precision)},${Number(latLng.lng()).toFixed(precision)}`;
}
function formatBlmDistrictTitle(attrs) {
  const name = firstNonEmpty(attrs?.ADMU_NAME, attrs?.DISTRICT_NAME);
  const parentName = firstNonEmpty(attrs?.PARENT_NAME, attrs?.Parent_Name);
  const orgType = firstNonEmpty(attrs?.BLM_ORG_TYPE);
  if (!name) return 'BLM Administrative Unit';
  if (/field/i.test(orgType) && parentName) {
    if (/district/i.test(parentName)) return parentName;
    return `${parentName} District`;
  }
  if (/district/i.test(name) || /field/i.test(name)) return name;
  if (/district/i.test(orgType)) return `${name} District`;
  if (/field/i.test(orgType)) return `${name} Field Office`;
  return name;
}
async function queryBlmOwnershipAtLatLng(latLng) {
  if (!latLng) return null;
  const cacheKey = getLatLngCacheKey(latLng);
  if (blmOwnershipPointCache.has(cacheKey)) return blmOwnershipPointCache.get(cacheKey);
  const queryUrl = `${BLM_SURFACE_OWNERSHIP_LAYER_URL}/query?where=${encodeURIComponent("UT_LGD IN ('Bureau of Land Management (BLM)','BLM Wilderness Area')")}&geometry=${encodeURIComponent(`${latLng.lng()},${latLng.lat()}`)}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=UT_LGD,COUNTY,CO_NAME,GIS_ACRES,ACRES,OWNER&returnGeometry=false&f=json`;
  const promise = fetchJson(queryUrl)
    .then(json => Array.isArray(json?.features) ? json.features[0]?.attributes || null : null)
    .catch(error => {
      console.error('BLM ownership point query failed', error);
      return null;
    });
  blmOwnershipPointCache.set(cacheKey, promise);
  return promise;
}
async function queryBlmDistrictAtLatLng(latLng) {
  if (!latLng) return null;
  const cacheKey = getLatLngCacheKey(latLng);
  if (blmDistrictPointCache.has(cacheKey)) return blmDistrictPointCache.get(cacheKey);
  const queryUrl = `${BLM_ADMIN_LAYER_URL}/query?where=${encodeURIComponent("BLM_ORG_TYPE IN ('District','Field')")}&geometry=${encodeURIComponent(`${latLng.lng()},${latLng.lat()}`)}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=ADMU_NAME,PARENT_NAME,BLM_ORG_TYPE&returnGeometry=false&orderByFields=BLM_ORG_TYPE%20ASC&f=json`;
  const promise = fetchJson(queryUrl)
    .then(json => Array.isArray(json?.features) ? json.features[0]?.attributes || null : null)
    .catch(error => {
      console.error('BLM district point query failed', error);
      return null;
    });
  blmDistrictPointCache.set(cacheKey, promise);
  return promise;
}
const OWNERSHIP_BUCKET_QUERIES = {
  sitla: "state_lgd = 'State Trust Lands'",
  private: "state_lgd = 'Private'",
  stateLands: "state_lgd IN ('Other State','State Sovereign Land')"
};
const ownershipBucketGeoJsonPromises = new Map();
function getOwnershipBucketGeoJson(bucket) {
  if (!ownershipBucketGeoJsonPromises.has(bucket)) {
    const where = OWNERSHIP_BUCKET_QUERIES[bucket] || '1=0';
    ownershipBucketGeoJsonPromises.set(bucket, fetchArcGisPagedGeoJson(PUBLIC_OWNERSHIP_LAYER_URL, where));
  }
  return ownershipBucketGeoJsonPromises.get(bucket);
}
let cwmuGeoJsonPromise = null;
async function getCwmuGeoJson() {
  if (!cwmuGeoJsonPromise) {
    cwmuGeoJsonPromise = fetchGeoJson(CWMU_QUERY_URL).catch(async error => {
      console.error('Live CWMU service failed, falling back to local CWMU GeoJSON', error);
      try {
        return await fetchGeoJson(LOCAL_CWMU_BOUNDARIES_PATH);
      } catch (localError) {
        console.error('Local CWMU GeoJSON failed, falling back to cached IDs', localError);
      }
      const [boundaryIds, boundaryGeoJson] = await Promise.all([
        fetchJson(CWMU_BOUNDARY_IDS_PATH).then(ids => Array.isArray(ids) ? ids.map(id => String(id)) : []),
        getHuntBoundaryGeoJson()
      ]);
      const allowedIds = new Set(boundaryIds);
      const features = Array.isArray(boundaryGeoJson?.features)
        ? boundaryGeoJson.features.filter(feature => allowedIds.has(String(feature?.properties?.BoundaryID ?? '')))
        : [];
      return { type: 'FeatureCollection', features };
    }).catch(async error => {
      cwmuGeoJsonPromise = null;
      throw error;
    });
  }
  return cwmuGeoJsonPromise;
}
let huntBoundaryGeoJsonPromise = null;
function getHuntBoundaryGeoJson() {
  if (huntBoundaryGeoJson) return Promise.resolve(huntBoundaryGeoJson);
  if (!huntBoundaryGeoJsonPromise) {
    huntBoundaryGeoJsonPromise = fetchFirstGeoJson(HUNT_BOUNDARY_SOURCES).then(geojson => {
      huntBoundaryGeoJson = geojson;
      return geojson;
    });
  }
  return huntBoundaryGeoJsonPromise;
}
function getGoogleEarth3dGeoJson(key, loader) {
  if (!googleEarth3dGeoJsonCache.has(key)) {
    const request = Promise.resolve()
      .then(loader)
      .catch(error => {
        googleEarth3dGeoJsonCache.delete(key);
        throw error;
      });
    googleEarth3dGeoJsonCache.set(key, request);
  }
  return googleEarth3dGeoJsonCache.get(key);
}
function getGeoJsonFeatureList(geojson) {
  return Array.isArray(geojson?.features) ? geojson.features : [];
}
function createOwnershipLayer(bucket, style, clickBuilder) {
  const layer = new google.maps.Data();
  getOwnershipBucketGeoJson(bucket).then(geojson => {
    layer.addGeoJson(geojson);
  }).catch(err => console.error('Ownership layer failed', err));
  layer.setStyle(style);
  layer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    const card = clickBuilder(event.feature);
    openLandInfoWindow(card, event.latLng);
  });
  return layer;
}
function fitDataFeatureBounds(feature, maxZoom = 12) {
  if (!googleBaselineMap || !feature?.getGeometry) return false;
  const geometry = feature.getGeometry();
  if (!geometry?.forEachLatLng) return false;
  const bounds = new google.maps.LatLngBounds();
  let found = false;
  geometry.forEachLatLng(latLng => {
    bounds.extend(latLng);
    found = true;
  });
  if (!found) return false;
  googleBaselineMap.fitBounds(bounds);
  google.maps.event.addListenerOnce(googleBaselineMap, 'bounds_changed', () => {
    if ((googleBaselineMap.getZoom() || 0) > maxZoom) googleBaselineMap.setZoom(maxZoom);
  });
  return true;
}
async function ensureSitlaLayer() {
  if (sitlaLayer || !googleBaselineMap) return sitlaLayer;
  sitlaLayer = createOwnershipLayer(
    'sitla',
    { strokeColor: '#2a78d2', strokeWeight: 2, fillColor: '#6fb3ff', fillOpacity: 0.08, zIndex: 34 },
    feature => buildLandInfoCard(buildOwnershipDetails('sitla', featureProps(feature)))
  );
  setLayerVisibility(sitlaLayer, !!toggleSITLA?.checked);
  return sitlaLayer;
}
function featureProps(feature) {
  const names = ['label_state','LABEL_STATE','ut_lgd','UT_LGD','desig','DESIG','admin','ADMIN','owner','OWNER','county','COUNTY','gis_acres','GIS_ACRES','acres','ACRES'];
  const props = {};
  names.forEach(name => { props[name] = feature.getProperty(name); });
  return props;
}
async function ensureStateLandsLayer() {
  if (stateLandsLayer || !googleBaselineMap) return stateLandsLayer;
  stateLandsLayer = createOwnershipLayer(
    'stateLands',
    { strokeColor: '#2f8f9a', strokeWeight: 2, fillColor: '#6ac7d2', fillOpacity: 0.08, zIndex: 33 },
    feature => buildLandInfoCard(buildOwnershipDetails('stateLands', featureProps(feature)))
  );
  setLayerVisibility(stateLandsLayer, false);
  return stateLandsLayer;
}
async function ensureStateParksLayer() {
  if (stateParksLayer || !googleBaselineMap) return stateParksLayer;
  const geojson = await fetchGeoJson(STATE_PARKS_QUERY_URL);
  stateParksLayer = new google.maps.Data();
  stateParksLayer.addGeoJson(geojson);
  stateParksLayer.setStyle({
    strokeColor: '#0d6f78',
    strokeWeight: 2.5,
    fillColor: '#5ec7d1',
    fillOpacity: 0.1,
    zIndex: 35
  });
  stateParksLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    const title = firstNonEmpty(
      event.feature.getProperty('name'),
      event.feature.getProperty('Name'),
      event.feature.getProperty('NAME'),
      event.feature.getProperty('UNIT_NAME'),
      event.feature.getProperty('UnitName'),
      event.feature.getProperty('ParkName'),
      'Utah State Park'
    );
    const detailsLink = firstNonEmpty(
      event.feature.getProperty('weblink1'),
      event.feature.getProperty('Weblink1'),
      event.feature.getProperty('WEBLINK1')
    );
    const detailText = [
      firstNonEmpty(event.feature.getProperty('City'), event.feature.getProperty('CITY')),
      firstNonEmpty(event.feature.getProperty('County'), event.feature.getProperty('COUNTY'))
    ].filter(Boolean).join(' | ');
    openLandInfoWindow(buildLandInfoCard({
      logo: LOGO_STATE_PARKS,
      title,
      subtitle: 'Utah State Parks',
      detailText,
      logoSize: 68,
      cardMinWidth: 180,
      cardMaxWidth: 220,
      detailsLinkText: detailsLink ? 'Park Details' : '',
      detailsLink
    }), event.latLng);
  });
  setLayerVisibility(stateParksLayer, !!toggleStateParks?.checked);
  return stateParksLayer;
}
async function ensureWmaLayer() {
  if (wmaLayer || !googleBaselineMap) return wmaLayer;
  const geojson = await fetchGeoJson(WMA_QUERY_URL);
  wmaLayer = new google.maps.Data();
  wmaLayer.addGeoJson(geojson);
  wmaLayer.setStyle({
    strokeColor: '#b38a00',
    strokeWeight: 2.5,
    fillColor: '#ffd84d',
    fillOpacity: 0.12,
    zIndex: 36
  });
  wmaLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    fitDataFeatureBounds(event.feature, 12);
    const title = firstNonEmpty(
      event.feature.getProperty('Name'),
      event.feature.getProperty('NAME'),
      'Wildlife Management Area'
    );
    openLandInfoWindow(buildLandInfoCard({
      logo: LOGO_DWR_WMA,
      title,
      subtitle: "UT. DWR W.M.A.'s",
      logoSize: 68,
      noticeText: "Utah DWR W.M.A.'s do not imply outfitter approval, endorsement, or exclusive access."
    }), event.latLng);
  });
  setLayerVisibility(wmaLayer, !!toggleWma?.checked);
  return wmaLayer;
}
async function ensureCwmuLayer() {
  if (cwmuLayer || !googleBaselineMap) return cwmuLayer;
  const geojson = await getCwmuGeoJson();
  const features = Array.isArray(geojson?.features) ? geojson.features : [];
  cwmuLayer = new google.maps.Data();
  cwmuLayer.addGeoJson({ type: 'FeatureCollection', features });
  cwmuLayer.setStyle({
    strokeColor: '#b11f1f',
    strokeWeight: 2,
    fillColor: '#ff6b6b',
    fillOpacity: 0.1,
    zIndex: 37
  });
  cwmuLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    fitDataFeatureBounds(event.feature, 12);
    openLandInfoWindow(buildLandInfoCard({
      logo: LOGO_CWMU,
      title: firstNonEmpty(
        event.feature.getProperty('Boundary_Name'),
        event.feature.getProperty('NAME'),
        event.feature.getProperty('Name'),
        'CWMU Area'
      ),
      subtitle: 'Cooperative Wildlife Management Unit',
      logoSize: 68,
      noticeText: 'No access without the appropriate CWMU permit.'
    }), event.latLng);
  });
  setLayerVisibility(cwmuLayer, !!toggleCwmu?.checked);
  return cwmuLayer;
}
async function ensurePrivateLayer() {
  if (privateLayer || !googleBaselineMap) return privateLayer;
  privateLayer = createOwnershipLayer(
    'private',
    { strokeColor: '#8f4a3a', strokeWeight: 1.5, fillColor: '#c99284', fillOpacity: 0.05, zIndex: 32 },
    feature => buildLandInfoCard(buildOwnershipDetails('private', featureProps(feature)))
  );
  setLayerVisibility(privateLayer, !!togglePrivate?.checked);
  return privateLayer;
}

async function ensureUsfsLayer() {
  if (usfsLayer || !googleBaselineMap) return usfsLayer;
  const geojson = await fetchGeoJson(USFS_QUERY_URL);
  usfsLayer = new google.maps.Data();
  usfsLayer.addGeoJson(geojson);
  usfsLayer.setStyle({
    strokeColor: '#2f6b3b',
    strokeWeight: 2,
    fillColor: '#7ea96b',
    fillOpacity: 0.08,
    zIndex: 14
  });
  usfsLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    if (shouldDeprioritizeFederalClicks()) return;
    openLandInfoWindow(buildLandInfoCard({
      logo: LOGO_USFS,
      title: firstNonEmpty(event.feature.getProperty('FORESTNAME'), 'National Forest'),
      subtitle: 'US Forest Service',
      logoSize: 68
    }), event.latLng);
  });
  setLayerVisibility(usfsLayer, !!toggleUSFS?.checked);
  return usfsLayer;
}

async function ensureBlmLayer() {
  if (blmLayer || !googleBaselineMap) return blmLayer;
  const geojson = await fetchGeoJson(BLM_ADMIN_QUERY_URL);
  blmLayer = new google.maps.Data();
  blmLayer.addGeoJson(geojson);
  blmLayer.setStyle({
    strokeColor: '#b9722f',
    strokeWeight: 2,
    fillColor: '#d8af7b',
    fillOpacity: 0.04,
    clickable: false,
    zIndex: 12
  });
  setLayerVisibility(blmLayer, !!toggleBLM?.checked);
  return blmLayer;
}

async function ensureBlmDetailLayer() {
  if (blmDetailLayer || !googleBaselineMap) return blmDetailLayer;
  const geojson = await fetchArcGisPagedGeoJson(
    BLM_SURFACE_OWNERSHIP_LAYER_URL,
    "UT_LGD IN ('Bureau of Land Management (BLM)','BLM Wilderness Area')"
  );
  blmDetailLayer = new google.maps.Data();
  blmDetailLayer.addGeoJson(geojson);
  applyBlmDetailLayerStyle();
  blmDetailLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    if (shouldDeprioritizeFederalClicks()) return;
    queryBlmDistrictAtLatLng(event.latLng).then(districtHit => {
      const county = firstNonEmpty(
        event.feature.getProperty('COUNTY'),
        event.feature.getProperty('county'),
        event.feature.getProperty('CO_NAME'),
        event.feature.getProperty('co_name')
      );
      const surfaceLabel = firstNonEmpty(
        event.feature.getProperty('UT_LGD'),
        event.feature.getProperty('ut_lgd'),
        event.feature.getProperty('OWNER'),
        event.feature.getProperty('owner'),
        'Bureau of Land Management (BLM)'
      );
      const detailText = [
        county ? `${county} County` : '',
        surfaceLabel
      ].filter(Boolean).join(' | ');
      openLandInfoWindow(buildLandInfoCard({
        logo: LOGO_BLM,
        title: firstNonEmpty(
          formatBlmDistrictTitle(districtHit),
          'BLM District'
        ),
        subtitle: 'Bureau of Land Management',
        detailText,
        logoSize: 68
      }), event.latLng);
    });
  });
  setLayerVisibility(blmDetailLayer, !!(toggleBLM?.checked || toggleBLMDetail?.checked));
  return blmDetailLayer;
}
function applyBlmDetailLayerStyle() {
  if (!blmDetailLayer) return;
  blmDetailLayer.setStyle(() => {
    const showVisibleDetail = !!toggleBLMDetail?.checked;
    return {
      strokeColor: '#b9722f',
      strokeWeight: showVisibleDetail ? 1.25 : 0.1,
      strokeOpacity: showVisibleDetail ? 0.55 : 0,
      fillColor: '#d8af7b',
      fillOpacity: showVisibleDetail ? 0.03 : 0,
      clickable: true,
      zIndex: 11
    };
  });
}
async function ensureWildernessLayer() {
  if (wildernessLayer || !googleBaselineMap) return wildernessLayer;
  const geojson = await fetchGeoJson(WILDERNESS_QUERY_URL);
  wildernessLayer = new google.maps.Data();
  wildernessLayer.addGeoJson(geojson);
  wildernessLayer.setStyle(feature => {
    const agency = safe(feature.getProperty('Agency')).toUpperCase();
    const isUsfs = agency === 'FS';
    const isVisible = shouldShowWildernessFeature(agency);
    return {
      visible: isVisible,
      clickable: isVisible,
      strokeColor: isUsfs ? '#1f5130' : '#8a611d',
      strokeWeight: 2,
      strokeOpacity: isVisible ? 0.9 : 0,
      fillColor: isUsfs ? '#7f9f74' : '#c8a76f',
      fillOpacity: isVisible ? 0.12 : 0,
      zIndex: 31
    };
  });
  wildernessLayer.addListener('click', event => {
    if (shouldSuppressLandClick()) return;
    if (!shouldShowWildernessFeature(event.feature)) return;
    if (resolveOutfitterPriorityClick(event.latLng)) return;
    fitDataFeatureBounds(event.feature, 11);
    const agency = safe(event.feature.getProperty('Agency')).toUpperCase();
    const subtitle = agency === 'FS' ? 'USFS Wilderness' : 'BLM Wilderness';
    const detailBits = [];
    const acreage = event.feature.getProperty('Acreage');
    if (acreage) detailBits.push(`${Number(acreage).toLocaleString()} acres`);
    openLandInfoWindow(buildLandInfoCard({
      logo: agency === 'FS' ? LOGO_USFS : LOGO_BLM,
      title: firstNonEmpty(event.feature.getProperty('NAME'), 'Wilderness Area'),
      subtitle,
      detailText: detailBits.join(' | '),
      detailsLinkText: event.feature.getProperty('URL') ? 'Area Details' : '',
      detailsLink: firstNonEmpty(event.feature.getProperty('URL')),
      logoSize: 68
    }), event.latLng);
  });
  updateWildernessOverlayVisibility();
  return wildernessLayer;
}
async function ensureUtahOutlineLayer() {
  if (utahOutlineLayer || !googleBaselineMap) return utahOutlineLayer;
  const geojson = await fetchGeoJson(UTAH_OUTLINE_QUERY_URL);
  utahOutlineLayer = new google.maps.Data();
  utahOutlineLayer.addGeoJson(geojson);
  utahOutlineLayer.setStyle({
    strokeColor: '#c84f00',
    strokeWeight: 3,
    strokeOpacity: 0.95,
    fillOpacity: 0,
    clickable: false,
    zIndex: 9
  });
  utahOutlineLayer.setMap(googleBaselineMap);
  return utahOutlineLayer;
}

function getDwrBoundaryUrl(hunt = selectedHunt) {
  const huntCode = safe(hunt ? getHuntCode(hunt) : '').trim().toUpperCase();
  if (huntCode) {
    return `https://dwrapps.utah.gov/huntboundary/hbstart?HN=${encodeURIComponent(huntCode)}`;
  }
  return 'https://dwrapps.utah.gov/huntboundary/hbstart';
}

function updateDwrMapFrame(hunt = selectedHunt) {
  if (!dwrMapFrame) return;
  const src = getDwrBoundaryUrl(hunt);
  if (dwrMapFrame.getAttribute('src') !== src) {
    dwrMapFrame.setAttribute('src', src);
    if (dwrFrameLoadTimeoutId) {
      clearTimeout(dwrFrameLoadTimeoutId);
      dwrFrameLoadTimeoutId = null;
    }
    dwrFrameLoadTimeoutId = setTimeout(() => {
      updateStatus('DWR map may be blocked in iframe. Use the DWR logo to open map directly.');
      dwrFrameLoadTimeoutId = null;
    }, 7000);
  }
  if (plannerDnrLogoLink) {
    plannerDnrLogoLink.href = src;
    plannerDnrLogoLink.target = '_blank';
    plannerDnrLogoLink.rel = 'noopener noreferrer';
  }
}

function getPreferredDwrHuntCandidate() {
  const visibleHunts = getDisplayHunts();
  if (!visibleHunts.length) return null;
  if (selectedHunt) {
    const selectedKey = getHuntRecordKey(selectedHunt);
    if (visibleHunts.some(h => getHuntRecordKey(h) === selectedKey)) {
      return selectedHunt;
    }
  }
  return visibleHunts[0] || null;
}

function initDwrFrameEvents() {
  if (!dwrMapFrame || dwrMapFrame.__uogaEventsBound) return;
  dwrMapFrame.__uogaEventsBound = true;
  dwrMapFrame.addEventListener('load', () => {
    if (dwrFrameLoadTimeoutId) {
      clearTimeout(dwrFrameLoadTimeoutId);
      dwrFrameLoadTimeoutId = null;
    }
    if (safe(mapTypeSelect?.value).toLowerCase() === 'dwr') {
      updateStatus('Utah DWR map active.');
    }
  });
  dwrMapFrame.addEventListener('error', () => {
    if (dwrFrameLoadTimeoutId) {
      clearTimeout(dwrFrameLoadTimeoutId);
      dwrFrameLoadTimeoutId = null;
    }
    updateStatus('DWR iframe failed to load. Use the DWR logo to open map directly.');
  });
}

function ensureGoogleEarth3dElement() {
  const stage = document.querySelector('.map-stage') || document.querySelector('.map-wrap');
  if (!stage) return null;
  let el = document.getElementById('googleEarth3dMap');
  if (!el) {
    el = document.createElement('gmp-map-3d');
    el.id = 'googleEarth3dMap';
    el.className = 'google-earth-3d-map';
    el.setAttribute('aria-label', 'Google Earth 3D map');
    // 2025 Maps JS 3D requirement: mode must be explicitly HYBRID or SATELLITE.
    el.setAttribute('mode', 'HYBRID');
    el.setAttribute('center', `${GOOGLE_BASELINE_DEFAULT_CENTER.lat},${GOOGLE_BASELINE_DEFAULT_CENTER.lng},1800`);
    el.setAttribute('range', '420000');
    el.setAttribute('tilt', '64');
    el.setAttribute('heading', '25');
    el.setAttribute('gesture-handling', 'greedy');
    // Keep Google Earth native controls enabled.
    el.removeAttribute('default-ui-hidden');
    el.hidden = true;
    el.addEventListener('gmp-error', (event) => {
      el.hidden = true;
      const details = String(event?.detail?.message || event?.message || '').trim();
      const reason = details
        ? `Google Earth 3D could not render (${details}).`
        : 'Google Earth 3D could not render.';
      handleGoogleEarth3dUnavailable(reason);
    });
    stage.appendChild(el);
  }
  return el;
}

function getGoogleEarth3dTroubleshootingHint() {
  return 'Check browser hardware acceleration and ensure 3D mode is enabled (HYBRID/SATELLITE runtime).';
}

function handleGoogleEarth3dUnavailable(reason = 'Google Earth 3D unavailable.') {
  const map3d = document.getElementById('googleEarth3dMap');
  if (map3d) {
    map3d.hidden = true;
  }
  clearGoogleEarth3dBoundaryOverlays();

  // Keep the user in Earth mode; do not auto-fallback to another map mode.
  if (safe(mapTypeSelect?.value).toLowerCase() === 'earth') {
    const mapWrap = document.querySelector('.map-wrap');
    if (mapWrap) {
      mapWrap.classList.add('is-earth-mode');
    }
  }
  updateStatus(`${reason} ${getGoogleEarth3dTroubleshootingHint()}`.trim());

  renderDevDebugPanel();
}

function applyGoogleEarthAtmosphereProfile(el = googleEarth3dMap) {
  if (!el) return;
  // Single default visual treatment (no extra toggle UI).
  if (GOOGLE_EARTH_ATMOSPHERE_PROFILE === 'standard') {
    el.style.filter = 'saturate(1.06) contrast(1.04) brightness(1.01)';
  } else {
    el.style.filter = '';
  }
}

function forceGoogleEarthNavigationControlsOpen(el = googleEarth3dMap) {
  if (!el) return;
  // Keep native Earth controls visible.
  try { el.removeAttribute('default-ui-hidden'); } catch (_) {}
  try { el.defaultUiHidden = false; } catch (_) {}
  try { el.defaultUIHidden = false; } catch (_) {}

  // Best-effort expansion click for runtimes that collapse nav controls by default.
  // If internals are inaccessible (closed shadow DOM), this safely no-ops.
  try {
    const root = el.shadowRoot;
    if (!root) return;
    const expandCandidate = Array.from(root.querySelectorAll('button,[role="button"]')).find((node) => {
      const label = String(node.getAttribute?.('aria-label') || node.title || node.textContent || '').toLowerCase();
      const expanded = String(node.getAttribute?.('aria-expanded') || '').toLowerCase();
      return (
        (label.includes('navigation') || label.includes('controls') || label.includes('compass') || label.includes('map controls'))
        && expanded !== 'true'
      );
    });
    if (expandCandidate) expandCandidate.click();
  } catch (_) {}
}

function scheduleGoogleEarthControlsOpenPass(el = googleEarth3dMap) {
  if (!el || typeof window === 'undefined') return;
  const passes = [0, 280, 900, 1800];
  passes.forEach((delay) => {
    window.setTimeout(() => forceGoogleEarthNavigationControlsOpen(el), delay);
  });
}

function applyGoogleEarthTopographyBoost(el = googleEarth3dMap) {
  if (!el) return false;
  const value = Number(GOOGLE_EARTH_TOPOGRAPHY_EXAGGERATION);
  if (!Number.isFinite(value) || value <= 0) return false;

  let appliedProperty = false;
  const propertyCandidates = ['exaggeration', 'terrainExaggeration', 'terrainScale', 'verticalScale', 'elevationScale'];
  propertyCandidates.forEach((prop) => {
    try {
      if (prop in el) {
        el[prop] = value;
        appliedProperty = true;
      }
    } catch (_) {}
  });

  // Safe attribute fallback; harmless if unsupported by runtime.
  ['exaggeration', 'terrain-exaggeration', 'terrain-scale', 'vertical-scale', 'elevation-scale'].forEach((attr) => {
    try {
      el.setAttribute(attr, String(value));
    } catch (_) {}
  });

  return appliedProperty;
}

async function ensureGoogleEarth3dMap() {
  const el = ensureGoogleEarth3dElement();
  if (!el) return null;
  if (!window.google?.maps?.importLibrary) return null;
  if (!googleEarth3dLibraryPromise) {
    googleEarth3dLibraryPromise = window.google.maps.importLibrary('maps3d');
  }
  const maps3d = await googleEarth3dLibraryPromise;
  if (!maps3d?.Map3DElement) {
    handleGoogleEarth3dUnavailable('Google Earth 3D is not available for this API key/runtime.');
    return null;
  }

  googleEarth3dMap = el;
  const hybridMode = maps3d?.MapMode?.HYBRID || 'HYBRID';
  el.mode = hybridMode;
  try { el.setAttribute('mode', String(hybridMode)); } catch (_) {}
  // Keep Google Earth native controls enabled.
  el.removeAttribute('default-ui-hidden');
  if ('defaultUiHidden' in el) {
    try { el.defaultUiHidden = false; } catch (_) {}
  }
  forceGoogleEarthNavigationControlsOpen(el);
  applyGoogleEarthAtmosphereProfile(el);
  applyGoogleEarthTopographyBoost(el);
  scheduleGoogleEarthControlsOpenPass(el);
  bindGoogleEarth3dZoomStyleEvents(el);
  syncGoogleEarth3dCamera();
  return el;
}

function syncGoogleEarth3dCamera() {
  const el = googleEarth3dMap || document.getElementById('googleEarth3dMap');
  if (!el) return;
  let center = GOOGLE_BASELINE_DEFAULT_CENTER;
  if (googleBaselineMap?.getCenter) {
    const googleCenter = googleBaselineMap.getCenter();
    if (googleCenter) {
      center = { lat: googleCenter.lat(), lng: googleCenter.lng() };
    }
  }
  el.center = { lat: center.lat, lng: center.lng, altitude: 1800 };
  el.range = 420000;
  el.tilt = 64;
  el.heading = 25;
}

function clearGoogleEarth3dBoundaryOverlays() {
  googleEarth3dBoundaryOverlays.forEach(overlay => {
    if (overlay?.remove) overlay.remove();
  });
  googleEarth3dBoundaryOverlays = [];
}

function getGoogleEarth3dCurrentRange(map3d = googleEarth3dMap) {
  const value = Number(map3d?.range);
  return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
}

function shouldUseGoogleEarthOutlineOnly(rangeValue = getGoogleEarth3dCurrentRange(), threshold = GOOGLE_EARTH_OUTLINE_ONLY_RANGE) {
  return Number.isFinite(rangeValue) && rangeValue <= threshold;
}

function applyGoogleEarth3dOverlayZoomStyle(overlay, rangeValue = getGoogleEarth3dCurrentRange()) {
  if (!overlay) return;
  const baseStyle = overlay.__uogaBaseStyle;
  if (!baseStyle) return;
  const fillColor = String(baseStyle.fillColor || '').trim();
  if (!fillColor || fillColor === GOOGLE_EARTH_TRANSPARENT_FILL) return;
  const threshold = Number(overlay.__uogaOutlineOnlyRange);
  const outlineOnly = shouldUseGoogleEarthOutlineOnly(
    rangeValue,
    Number.isFinite(threshold) ? threshold : GOOGLE_EARTH_OUTLINE_ONLY_RANGE
  );
  overlay.fillColor = outlineOnly ? GOOGLE_EARTH_TRANSPARENT_FILL : fillColor;
}

function applyGoogleEarth3dZoomStylesForCurrentRange(map3d = googleEarth3dMap) {
  const currentRange = getGoogleEarth3dCurrentRange(map3d);
  googleEarth3dBoundaryOverlays.forEach((overlay) => applyGoogleEarth3dOverlayZoomStyle(overlay, currentRange));
}

function scheduleGoogleEarth3dZoomStyleRefresh() {
  if (typeof window === 'undefined') return;
  if (window.__uogaEarthZoomStyleTimer) {
    clearTimeout(window.__uogaEarthZoomStyleTimer);
  }
  window.__uogaEarthZoomStyleTimer = window.setTimeout(() => {
    applyGoogleEarth3dZoomStylesForCurrentRange();
  }, 36);
}

function bindGoogleEarth3dZoomStyleEvents(map3d) {
  if (!map3d || map3d.__uogaEarthZoomStyleEventsBound) return;
  map3d.__uogaEarthZoomStyleEventsBound = true;
  map3d.addEventListener('gmp-rangechange', scheduleGoogleEarth3dZoomStyleRefresh);
  map3d.addEventListener('gmp-steadychange', scheduleGoogleEarth3dZoomStyleRefresh);
}

function getGoogleEarth3dBoundaryFeatures() {
  const features = Array.isArray(huntBoundaryGeoJson?.features) ? huntBoundaryGeoJson.features : [];
  if (!features.length) return [];

  if (selectedHunt) {
    const matcher = buildBoundaryMatcher([selectedHunt]);
    return features.filter(feature => {
      const props = feature?.properties || {};
      return matcher.matches(getFeatureBoundaryCandidateIds(props), normalizeBoundaryKey(props.Boundary_Name));
    }).slice(0, 8);
  }

  if (selectedBoundaryFeature) {
    const selectedId = safe(selectedBoundaryFeature.getProperty?.('BoundaryID'));
    const selectedName = normalizeBoundaryKey(selectedBoundaryFeature.getProperty?.('Boundary_Name'));
    return features.filter(feature => {
      const props = feature?.properties || {};
      const featureIds = getFeatureBoundaryCandidateIds(props);
      return (selectedId && featureIds.includes(selectedId))
        || (selectedName && normalizeBoundaryKey(props.Boundary_Name) === selectedName);
    }).slice(0, 8);
  }

  const displayHunts = getDisplayHunts();
  if (!displayHunts.length || shouldShowAllHuntUnits()) return [];
  const matcher = buildBoundaryMatcher(displayHunts);
  return features.filter(feature => {
    const props = feature?.properties || {};
    return matcher.matches(getFeatureBoundaryCandidateIds(props), normalizeBoundaryKey(props.Boundary_Name));
  }).slice(0, 12);
}

async function getGoogleEarth3dBoundaryFeaturesResolved() {
  const sourceHunts = selectedHunt ? [selectedHunt] : getDisplayHunts();
  if (!sourceHunts.length) return [];
  if (!selectedHunt && shouldShowAllHuntUnits()) return [];

  const targets = buildIndependentBoundaryTargets(sourceHunts);
  if (!targets.length) return getGoogleEarth3dBoundaryFeatures();

  const collected = [];
  for (const target of targets) {
    try {
      const fc = await getIndependentBoundaryFeatureCollection(target);
      const features = Array.isArray(fc?.features) ? fc.features : [];
      if (!features.length) continue;
      const huntCodes = [...new Set(target.hunts.map((hunt) => safe(getHuntCode(hunt)).trim().toUpperCase()).filter(Boolean))];
      features.forEach((feature) => {
        const props = { ...(feature?.properties || {}) };
        props.UOGA_DISPLAY_BOUNDARY_ID = target.displayBoundaryId;
        props.UOGA_HUNT_CODES = huntCodes.join('|');
        collected.push({ ...feature, properties: props });
      });
    } catch (error) {
      console.warn(`Google Earth boundary load failed for ${target.displayBoundaryId}`, error);
    }
  }

  return collected.length ? collected : getGoogleEarth3dBoundaryFeatures();
}

function closeRingIfNeeded(points) {
  if (points.length < 3) return points;
  const first = points[0];
  const last = points[points.length - 1];
  if (first.lat === last.lat && first.lng === last.lng) return points;
  return [...points, { ...first }];
}

function simplifyGoogleEarth3dRing(ring, maxPoints = 900) {
  if (!Array.isArray(ring)) return [];
  const clean = ring
    .map(coord => Array.isArray(coord) ? { lng: Number(coord[0]), lat: Number(coord[1]) } : null)
    .filter(point => Number.isFinite(point?.lat) && Number.isFinite(point?.lng));
  if (clean.length <= maxPoints) return closeRingIfNeeded(clean);
  const step = Math.ceil(clean.length / maxPoints);
  const sampled = clean.filter((_, index) => index % step === 0);
  return closeRingIfNeeded(sampled);
}

function getFeatureCoordinateBounds(features) {
  const bounds = { north: -90, south: 90, east: -180, west: 180, count: 0 };
  const visitCoord = (coord) => {
    if (!Array.isArray(coord)) return;
    const lng = Number(coord[0]);
    const lat = Number(coord[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    bounds.north = Math.max(bounds.north, lat);
    bounds.south = Math.min(bounds.south, lat);
    bounds.east = Math.max(bounds.east, lng);
    bounds.west = Math.min(bounds.west, lng);
    bounds.count += 1;
  };
  const visitNested = (value) => {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === 'number') {
      visitCoord(value);
      return;
    }
    value.forEach(visitNested);
  };
  features.forEach(feature => visitNested(feature?.geometry?.coordinates));
  return bounds.count ? bounds : null;
}

function getGoogleEarth3dCameraTarget(features) {
  const bounds = getFeatureCoordinateBounds(features);
  if (!bounds) return null;
  const center = {
    lat: (bounds.north + bounds.south) / 2,
    lng: (bounds.east + bounds.west) / 2,
    altitude: 1800
  };
  const latMeters = Math.max(1, Math.abs(bounds.north - bounds.south) * 111320);
  const lngMeters = Math.max(1, Math.abs(bounds.east - bounds.west) * 111320 * Math.cos(center.lat * Math.PI / 180));
  const range = Math.min(850000, Math.max(45000, Math.max(latMeters, lngMeters) * 1.9));
  return {
    center,
    range,
    tilt: 64,
    heading: 25
  };
}

function syncGoogleEarth3dCameraToFeatures(features) {
  const el = googleEarth3dMap || document.getElementById('googleEarth3dMap');
  const target = getGoogleEarth3dCameraTarget(features);
  if (!el || !target) return;
  el.center = target.center;
  el.range = target.range;
  el.tilt = target.tilt;
  el.heading = target.heading;
}

function getGoogleEarth3dFocusSignature(features) {
  if (!Array.isArray(features) || !features.length) return '';
  return features
    .slice(0, 20)
    .map((feature, index) => {
      const props = feature?.properties || {};
      const id = safe(props.BoundaryID || props.Boundary_Id || props.BOUNDARYID || '');
      const name = normalizeBoundaryKey(props.Boundary_Name || props.NAME || props.Name || '');
      return `${id || 'na'}:${name || index}`;
    })
    .join('|');
}

function reorientGoogleEarth3dCameraForFocus(features, { force = false } = {}) {
  const el = googleEarth3dMap || document.getElementById('googleEarth3dMap');
  const target = getGoogleEarth3dCameraTarget(features);
  if (!el || !target) return;
  el.hidden = false;

  const signature = getGoogleEarth3dFocusSignature(features);
  if (!force && signature && signature === googleEarth3dLastFocusSignature) return;
  if (signature) googleEarth3dLastFocusSignature = signature;

  const zoomOutCamera = {
    center: target.center,
    range: Math.max(target.range * 2.2, 220000),
    tilt: Math.max(48, target.tilt - 10),
    heading: target.heading
  };
  const zoomInCamera = {
    center: target.center,
    range: target.range,
    tilt: target.tilt,
    heading: target.heading
  };

  if (googleEarth3dReorientTimeoutId) {
    clearTimeout(googleEarth3dReorientTimeoutId);
    googleEarth3dReorientTimeoutId = null;
  }

  const performZoomIn = () => {
    if (safe(mapTypeSelect?.value).toLowerCase() !== 'earth') return;
    try {
      if (typeof el.stopCameraAnimation === 'function') {
        el.stopCameraAnimation();
      }
      if (typeof el.flyCameraTo === 'function') {
        el.flyCameraTo({ endCamera: zoomInCamera, durationMillis: 700 });
      } else {
        el.center = zoomInCamera.center;
        el.range = zoomInCamera.range;
        el.tilt = zoomInCamera.tilt;
        el.heading = zoomInCamera.heading;
      }
    } catch (error) {
      console.warn('Google Earth reorient zoom-in failed', error);
      el.center = zoomInCamera.center;
      el.range = zoomInCamera.range;
      el.tilt = zoomInCamera.tilt;
      el.heading = zoomInCamera.heading;
    }
  };

  try {
    if (typeof el.stopCameraAnimation === 'function') {
      el.stopCameraAnimation();
    }
    if (typeof el.flyCameraTo === 'function') {
      el.flyCameraTo({ endCamera: zoomOutCamera, durationMillis: 380 });
    } else {
      el.center = zoomOutCamera.center;
      el.range = zoomOutCamera.range;
      el.tilt = zoomOutCamera.tilt;
      el.heading = zoomOutCamera.heading;
    }
  } catch (error) {
    console.warn('Google Earth reorient zoom-out failed', error);
  }

  googleEarth3dReorientTimeoutId = setTimeout(performZoomIn, 340);
}

function getGoogleEarth3dOverlayDefinitions() {
  return [
    {
      key: 'sitla',
      enabled: !!toggleSITLA?.checked,
      style: { strokeColor: '#2a78d2ff', strokeWidth: 2, fillColor: '#6fb3ff20' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('sitla', () => getOwnershipBucketGeoJson('sitla')))
    },
    {
      key: 'stateParks',
      enabled: !!toggleStateParks?.checked,
      style: { strokeColor: '#0d6f78ff', strokeWidth: 2.5, fillColor: '#5ec7d126' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('stateParks', () => fetchGeoJson(STATE_PARKS_QUERY_URL)))
    },
    {
      key: 'wma',
      enabled: !!toggleWma?.checked,
      style: { strokeColor: '#b38a00ff', strokeWidth: 2.5, fillColor: '#ffd84d30' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('wma', () => fetchGeoJson(WMA_QUERY_URL)))
    },
    {
      key: 'cwmu',
      enabled: !!toggleCwmu?.checked,
      style: { strokeColor: '#b11f1fff', strokeWidth: 2, fillColor: '#ff6b6b26' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('cwmu', () => getCwmuGeoJson()))
    },
    {
      key: 'private',
      enabled: !!togglePrivate?.checked,
      style: { strokeColor: '#8f4a3aff', strokeWidth: 1.5, fillColor: '#c9928418' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('private', () => getOwnershipBucketGeoJson('private')))
    },
    {
      key: 'usfs',
      enabled: !!toggleUSFS?.checked,
      style: { strokeColor: '#2f6b3bff', strokeWidth: 2, fillColor: '#7ea96b20' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('usfs', () => fetchGeoJson(USFS_QUERY_URL)))
    },
    {
      key: 'blm',
      enabled: !!toggleBLM?.checked,
      style: { strokeColor: '#b9722fff', strokeWidth: 2, fillColor: '#d8af7b12' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('blm', () => fetchGeoJson(BLM_ADMIN_QUERY_URL)))
    },
    {
      key: 'blmDetail',
      enabled: !!toggleBLMDetail?.checked,
      style: { strokeColor: '#b9722fcc', strokeWidth: 1.25, fillColor: '#d8af7b08' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson(
        'blmDetail',
        () => fetchArcGisPagedGeoJson(BLM_SURFACE_OWNERSHIP_LAYER_URL, "UT_LGD IN ('Bureau of Land Management (BLM)','BLM Wilderness Area')")
      ))
    },
    {
      key: 'wilderness',
      enabled: shouldShowWildernessOverlay(),
      style: { strokeColor: '#8a611dff', strokeWidth: 2, fillColor: '#c8a76f26' },
      loader: async () => {
        const features = getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('wilderness', () => fetchGeoJson(WILDERNESS_QUERY_URL)));
        return features.filter(feature => shouldShowWildernessFeature(safe(feature?.properties?.Agency)));
      }
    },
    {
      key: 'utahOutline',
      enabled: true,
      style: { strokeColor: '#c84f00ff', strokeWidth: 3, fillColor: '#00000000' },
      loader: async () => getGeoJsonFeatureList(await getGoogleEarth3dGeoJson('utahOutline', () => fetchGeoJson(UTAH_OUTLINE_QUERY_URL)))
    }
  ];
}

function appendGoogleEarth3dFeatureOverlays(map3d, Polygon3DElement, features, style, maxPointsPerRing = 650) {
  if (!map3d || !Polygon3DElement || !Array.isArray(features) || !features.length) return 0;
  let drawn = 0;
  features.forEach(feature => {
    const geometry = feature?.geometry || {};
    const polygons = geometry.type === 'Polygon'
      ? [geometry.coordinates]
      : geometry.type === 'MultiPolygon'
        ? geometry.coordinates
        : [];
    polygons.slice(0, 10).forEach(polygon => {
      const paths = polygon
        .map(ring => simplifyGoogleEarth3dRing(ring, maxPointsPerRing))
        .filter(ring => ring.length >= 4);
      if (!paths.length) return;
      const overlay = new Polygon3DElement(style);
      overlay.path = paths[0];
      if (paths.length > 1 && 'innerPaths' in overlay) {
        overlay.innerPaths = paths.slice(1);
      }
      overlay.__uogaBaseStyle = {
        strokeColor: style?.strokeColor,
        strokeWidth: style?.strokeWidth,
        fillColor: style?.fillColor
      };
      overlay.__uogaOutlineOnlyRange = style?.outlineOnlyRange;
      applyGoogleEarth3dOverlayZoomStyle(overlay, getGoogleEarth3dCurrentRange(map3d));
      map3d.append(overlay);
      googleEarth3dBoundaryOverlays.push(overlay);
      drawn += 1;
    });
  });
  return drawn;
}

async function refreshGoogleEarth3dBoundaryOverlay() {
  if (safe(mapTypeSelect?.value).toLowerCase() !== 'earth') return;
  const map3d = await ensureGoogleEarth3dMap();
  if (!map3d) return;
  if (map3d.hidden) return;
  const maps3d = await googleEarth3dLibraryPromise;
  const Polygon3DElement = maps3d?.Polygon3DElement || google?.maps?.maps3d?.Polygon3DElement;
  if (!Polygon3DElement) return;

  clearGoogleEarth3dBoundaryOverlays();
  const boundaryFeatures = await getGoogleEarth3dBoundaryFeaturesResolved();
  const focusFeatures = [];
  let drawnOverlays = 0;

  if (boundaryFeatures.length) {
    const polygonOptions = {
      strokeColor: '#ff6600ff',
      strokeWidth: 5,
      fillColor: GOOGLE_EARTH_TRANSPARENT_FILL,
      drawsOccludedSegments: true,
      zIndex: 100
    };
    drawnOverlays += appendGoogleEarth3dFeatureOverlays(
      map3d,
      Polygon3DElement,
      boundaryFeatures,
      polygonOptions,
      boundaryFeatures.length > 1 ? 450 : 900
    );
    focusFeatures.push(...boundaryFeatures);
  }

  const overlayDefinitions = getGoogleEarth3dOverlayDefinitions().filter(def => def.enabled);
  const overlayResults = await Promise.all(overlayDefinitions.map(async (def) => {
    try {
      const features = await def.loader();
      return { def, features };
    } catch (error) {
      console.error(`Google Earth overlay "${def.key}" failed`, error);
      return { def, features: [] };
    }
  }));

  overlayResults.forEach(({ def, features }) => {
    if (!features.length) return;
    drawnOverlays += appendGoogleEarth3dFeatureOverlays(
      map3d,
      Polygon3DElement,
      features,
      {
        ...def.style,
        drawsOccludedSegments: true
      },
      420
    );
    if (def.key !== 'utahOutline') {
      focusFeatures.push(...features.slice(0, 120));
    }
  });

  const selectedHuntKey = getSelectedHuntKey();
  const boundaryFocusSignature = getGoogleEarth3dFocusSignature(boundaryFeatures);
  const huntChanged = !!selectedHuntKey && selectedHuntKey !== googleEarth3dLastSelectedHuntKey;
  const boundaryFocusChanged = !!boundaryFocusSignature && boundaryFocusSignature !== googleEarth3dLastBoundaryFocusSignature;
  if (selectedHuntKey) {
    googleEarth3dLastSelectedHuntKey = selectedHuntKey;
  } else {
    googleEarth3dLastSelectedHuntKey = '';
  }
  if (boundaryFocusSignature) {
    googleEarth3dLastBoundaryFocusSignature = boundaryFocusSignature;
  } else {
    googleEarth3dLastBoundaryFocusSignature = '';
  }

  if (boundaryFeatures.length) {
    reorientGoogleEarth3dCameraForFocus(boundaryFeatures, { force: huntChanged || boundaryFocusChanged });
  } else if (huntChanged && focusFeatures.length) {
    reorientGoogleEarth3dCameraForFocus(focusFeatures, { force: true });
  } else if (focusFeatures.length && !selectedHuntKey) {
    // Only auto-fit to broad overlay extents when no explicit hunt is selected.
    syncGoogleEarth3dCameraToFeatures(focusFeatures);
  }

  if (!drawnOverlays) {
    updateStatus('Google Earth 3D active. Select a hunt or turn on overlays to draw land boundaries.');
    return;
  }

  applyGoogleEarth3dZoomStylesForCurrentRange(map3d);

  const enabledOverlayCount = overlayDefinitions.length;
  const boundaryMessage = boundaryFeatures.length
    ? ` Showing ${boundaryFeatures.length} hunt unit boundar${boundaryFeatures.length === 1 ? 'y' : 'ies'}.`
    : '';
  updateStatus(`Google Earth 3D active with ${enabledOverlayCount} land overlay${enabledOverlayCount === 1 ? '' : 's'} and ${drawnOverlays} polygons.${boundaryMessage}`);
}

function refreshGoogleEarth3dBoundaryOverlaySoon() {
  if (safe(mapTypeSelect?.value).toLowerCase() !== 'earth') return;
  if (typeof window === 'undefined') {
    refreshGoogleEarth3dBoundaryOverlay().catch(err => console.error('Google Earth overlay refresh failed', err));
    return;
  }
  if (window.__uogaEarthOverlayRefreshTimer) {
    clearTimeout(window.__uogaEarthOverlayRefreshTimer);
  }
  window.__uogaEarthOverlayRefreshTimer = window.setTimeout(() => {
    refreshGoogleEarth3dBoundaryOverlay().catch(err => console.error('Google Earth overlay refresh failed', err));
  }, 40);
}

function handleGoogleMapUnavailable(reason = 'Google map unavailable.') {
  googleMapFailureMessage = reason;
  const mapWrap = document.querySelector('.map-wrap');
  if (!mapWrap) return;
  googleMapFailureMessage = reason;
  if (typeof window !== 'undefined') {
    window.__UOGA_GOOGLE_MAP_STATUS = reason;
  }
  mapWrap.classList.remove('is-dwr-mode');
  mapWrap.classList.remove('is-earth-mode');
  if (dwrMapFrame) {
    dwrMapFrame.hidden = true;
  }
  if (googleEarth3dMap) {
    googleEarth3dMap.hidden = true;
  }
  const mapEl = document.getElementById('map');
  if (mapEl) {
    mapEl.hidden = true;
  }
  if (mapTypeSelect) {
    mapTypeSelect.value = 'dwr';
    applyMapMode();
    updateStatus(`${reason} Switched to Utah DWR map.`);
  } else {
    updateStatus(reason);
  }
  renderDevDebugPanel();
}

function applyMapMode() {
  let value = safe(mapTypeSelect?.value || 'google').toLowerCase();
  if (FORCE_GOOGLE_ONLY_DEBUG && value === 'earth') {
    value = 'google';
    if (mapTypeSelect) {
      mapTypeSelect.value = 'google';
    }
  }
  const mapWrap = document.querySelector('.map-wrap');
  if (!mapWrap) return;
  const basemapControl = document.getElementById('basemapPopover') || document.getElementById('globeBasemapControl');
  const ownershipDock = document.getElementById('ownershipDock');
  if (value !== lastTrackedMapMode) {
    trackAnalytics('map_mode_changed', { mode: value });
    lastTrackedMapMode = value;
  }
  syncPlannerNavState();
  syncHashFromMapMode();

  mapWrap.classList.remove('is-dwr-mode');
  mapWrap.classList.remove('is-earth-mode');
  mapWrap.classList.remove('is-google-mode');
  if (dwrMapFrame) {
    dwrMapFrame.hidden = true;
  }
  if (googleEarth3dMap) {
    googleEarth3dMap.hidden = true;
  }
  if (ownershipDock) {
    ownershipDock.hidden = false;
    ownershipDock.setAttribute('aria-hidden', 'false');
  }
  if (value !== 'earth') {
    clearGoogleEarth3dBoundaryOverlays();
  }

  if (value === 'dwr') {
    clearSelectedBoundaryFallbackLayer();
    clearOutfitterMarkers();
    closeSelectedHuntFloat();
    updateDwrMapFrame(getPreferredDwrHuntCandidate());
    if (dwrMapFrame) {
      dwrMapFrame.hidden = false;
    }
    if (ownershipDock) {
      ownershipDock.hidden = true;
      ownershipDock.setAttribute('aria-hidden', 'true');
    }
    mapWrap.classList.add('is-dwr-mode');
    if (basemapControl) basemapControl.hidden = true;
    updateStatus('Utah DWR map active.');
    return;
  }

  if (value === 'earth') {
    clearSelectedBoundaryFallbackLayer();
    if (basemapControl) basemapControl.hidden = true;
    window.UOGA_BASEMAP_UI?.setPanelOpen?.(false);
    googleBaselineMap?.getStreetView?.()?.setVisible(false);
    clearOutfitterMarkers();
    mapWrap.classList.add('is-earth-mode');
    // Keep ownership menus collapsed in Earth mode; only Earth native map controls
    // should be prominent for visitors.
    setOwnershipControlsExpandedForEarth(false);
    const mapEl = document.getElementById('map');
    if (mapEl) mapEl.hidden = true;
    updateStatus('Loading Google Earth 3D...');
    ensureGoogleEarth3dMap()
      .then((el) => {
        if (safe(mapTypeSelect?.value).toLowerCase() !== 'earth') return;
        if (el) {
          el.hidden = false;
          forceGoogleEarthNavigationControlsOpen(el);
          scheduleGoogleEarthControlsOpenPass(el);
          applyGoogleEarthAtmosphereProfile(el);
          applyGoogleEarthTopographyBoost(el);
          refreshGoogleEarth3dBoundaryOverlay();
          return;
        }
        handleGoogleEarth3dUnavailable('Google Earth 3D unavailable.');
      })
      .catch((err) => {
        console.error('Google Earth 3D failed to load.', err);
        const details = String(err?.message || '').trim();
        handleGoogleEarth3dUnavailable(
          details ? `Google Earth 3D failed to load (${details}).` : 'Google Earth 3D failed to load.'
        );
      });
    return;
  }

  // Switching back to Google mode should show the Google map container even if the API is still loading.
  mapWrap.classList.remove('is-earth-mode');
  const mapEl = document.getElementById('map');
  if (mapEl) mapEl.hidden = false;

  if (!googleBaselineMap) {
    if (googleApiLoading) {
      updateStatus('Loading Google map...');
      return;
    }
    handleGoogleMapUnavailable(`Google map is unavailable. (${getGoogleKeySourceLabel()}) ${buildGoogleReferrerHint()}`);
    return;
  }

  if (basemapControl) basemapControl.hidden = false;
  mapWrap.classList.add('is-google-mode');
  if (value === 'google') {
    googleBaselineMap.setMapTypeId(getGooglePreferredBasemapType());
  } else {
    // Back-compat: if older code paths still pass google basemap ids here, honor them.
    googleBaselineMap.setMapTypeId(value);
  }
  googleBaselineMap.getStreetView()?.setVisible(false);
  styleBoundaryLayer();
  if (selectedHunt) {
    applySelectedHuntBoundaryResolution(selectedHunt).catch((error) => {
      console.warn('Selected hunt boundary resolution failed during map mode apply.', error);
    });
  }
  if (selectedHunt) {
    updateOutfitterMarkers(getMatchingOutfittersForHunt(selectedHunt));
  }
  updateStatus(`${value === 'google' ? 'Google' : titleCaseWords(value)} map active.`);
}

function resetMapView() {
  if (googleBaselineMap) {
    googleBaselineMap.setCenter(GOOGLE_BASELINE_DEFAULT_CENTER);
    googleBaselineMap.setZoom(GOOGLE_BASELINE_DEFAULT_ZOOM);
  }
}

function getSelectedHuntCenter() {
  if (!selectedHunt) return null;
  if (selectedBoundaryFallbackLayer) {
    const bounds = new google.maps.LatLngBounds();
    let found = false;
    selectedBoundaryFallbackLayer.forEach((feature) => {
      feature.getGeometry().forEachLatLng((latLng) => {
        bounds.extend(latLng);
        found = true;
      });
    });
    if (found) return bounds.getCenter();
  }
  if (!huntUnitsLayer) return null;
  const matcher = buildBoundaryMatcher([selectedHunt]);
  let center = null;
  huntUnitsLayer.forEach(f => {
    const ids = getDataFeatureBoundaryCandidateIds(f);
    const name = normalizeBoundaryKey(f.getProperty('Boundary_Name'));
    if (matcher.matches(ids, name)) {
      const bounds = new google.maps.LatLngBounds();
      f.getGeometry().forEachLatLng(ll => bounds.extend(ll));
      center = bounds.getCenter();
    }
  });
  return center;
}

function openStreetViewAtFocus() {
  if (!googleBaselineMap || typeof google === 'undefined' || !google.maps?.StreetViewService) return;
  if (safe(mapTypeSelect?.value).toLowerCase() === 'earth') {
    mapTypeSelect.value = 'google';
    applyMapMode();
  }
  const pano = googleBaselineMap.getStreetView();
  const target = getSelectedHuntCenter() || googleBaselineMap.getCenter();
  if (!target) {
    updateStatus('No Street View location available yet.');
    return;
  }

  const streetViewService = new google.maps.StreetViewService();
  const radii = [5000, 15000, 50000];
  const tryRadius = (index) => {
    if (index >= radii.length) {
      updateStatus('No Street View imagery found near this hunt.');
      return;
    }
    streetViewService.getPanorama({
      location: target,
      radius: radii[index],
      preference: google.maps.StreetViewPreference.NEAREST,
      source: google.maps.StreetViewSource.OUTDOOR
    }, (data, status) => {
      if (status === google.maps.StreetViewStatus.OK && data?.location?.latLng) {
        googleBaselineMap.setCenter(data.location.latLng);
        pano.setPosition(data.location.latLng);
        pano.setPov({ heading: 0, pitch: 0 });
        pano.setVisible(true);
        updateStatus('Street View active.');
        return;
      }
      tryRadius(index + 1);
    });
  };

  tryRadius(0);
}


function installPageScrollOnMap(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (el.__uogaWheelScrollInstalled) return;
  el.__uogaWheelScrollInstalled = true;

  // Capture phase so we see the wheel before map libraries can swallow it.
  el.addEventListener('wheel', (e) => {
    // With Google Maps cooperative mode, Ctrl+wheel is the intentional zoom gesture.
    // Default (no Ctrl) should scroll the page.
    if (e.ctrlKey) return;
    e.preventDefault();
    window.scrollBy({ top: e.deltaY, left: 0, behavior: 'auto' });
  }, { passive: false, capture: true });
}
// --- MAP ENGINE ---
function initGoogleBaseline() {
  if (googleMapsLoadTimeoutId) {
    clearTimeout(googleMapsLoadTimeoutId);
    googleMapsLoadTimeoutId = null;
  }
  googleApiLoading = false;
  googleMapFailureMessage = '';
  if (typeof window !== 'undefined') {
    window.__UOGA_GOOGLE_MAP_STATUS = 'Google map active.';
  }
  if (mapTypeSelect && safe(mapTypeSelect.value).toLowerCase() === 'earth') {
    mapTypeSelect.value = 'google';
  }
  googleBaselineMap = new google.maps.Map(document.getElementById('map'), {
    center: GOOGLE_BASELINE_DEFAULT_CENTER, zoom: GOOGLE_BASELINE_DEFAULT_ZOOM,
    styles: huntPlannerMapStyle,
    mapTypeId: getGooglePreferredBasemapType(),
    gestureHandling: 'greedy',
    streetViewControl: true,
    fullscreenControl: true,
    mapTypeControl: false
  });
  googleBaselineMap.addListener('click', () => {
    if (shouldSuppressLandClick()) return;
    closeSelectedHuntFloat();
    closeSelectedHuntPopup();
  });
  // Expose the active map instance so UI helpers (google-basemap.js) can reliably control it.
  window.googleBaselineMap = googleBaselineMap;
  googleApiReady = true;
  installPageScrollOnMap('map');
  if (huntBoundaryGeoJson) buildBoundaryLayer();
  ensureUtahOutlineLayer().catch(err => console.error('Utah outline failed', err));
  if (toggleBLM?.checked) ensureBlmLayer().catch(err => console.error('BLM layer failed', err));
  if (toggleBLM?.checked || toggleBLMDetail?.checked) ensureBlmDetailLayer().catch(err => console.error('BLM detail layer failed', err));
  if (toggleUSFS?.checked) ensureUsfsLayer().catch(err => console.error('USFS layer failed', err));
  if (shouldShowWildernessOverlay()) ensureWildernessLayer().catch(err => console.error('Wilderness layer failed', err));
  if (toggleSITLA?.checked) ensureSitlaLayer().catch(err => console.error('SITLA layer failed', err));
  if (toggleStateParks?.checked) ensureStateParksLayer().catch(err => console.error('State parks layer failed', err));
  if (toggleWma?.checked) ensureWmaLayer().catch(err => console.error('WMA layer failed', err));
  if (togglePrivate?.checked) ensurePrivateLayer().catch(err => console.error('Private layer failed', err));
  if (toggleCwmu?.checked) ensureCwmuLayer().catch(err => console.error('CWMU layer failed', err));
  updateStateLayersSummary();
  updateFederalLayersSummary();
  updatePrivateLayersSummary();
  applyMapMode();
  updateStatus('Map ready. Select filters or click a hunt unit.');
  trackAnalytics('map_loaded', { mode: safe(mapTypeSelect?.value || 'google').toLowerCase() });
  renderDevDebugPanel();
  bindControls();
}

if (typeof window !== 'undefined') {
  window.initGoogleBaseline = initGoogleBaseline;
}

function buildBoundaryLayer() {
  huntUnitsLayer = new google.maps.Data({ map: googleBaselineMap });
  if (huntBoundaryGeoJson) {
      huntUnitsLayer.addGeoJson(huntBoundaryGeoJson);
      huntUnitsLayer.setStyle({ strokeColor: '#3653b3', strokeWeight: 1, fillOpacity: 0.05 });
      huntUnitsLayer.addListener('click', event => {
        openBoundaryPopup(event.feature, event.latLng);
      });
      styleBoundaryLayer();
  }
}

function styleBoundaryLayer() {
    if (!huntUnitsLayer) {
      return;
    }
    const showBoundaries = shouldShowHuntBoundaries();
    const showAllUnits = shouldShowAllHuntUnits();
    const useIndependentLayerOnly = showBoundaries && !showAllUnits;
    const filtered = getDisplayHunts();
    const matcher = buildBoundaryMatcher(filtered);
    const selectedMatcher = selectedHunt ? buildBoundaryMatcher([selectedHunt]) : null;
    let visibleMatches = 0;
    huntUnitsLayer.forEach(f => {
        const ids = getDataFeatureBoundaryCandidateIds(f);
        const name = normalizeBoundaryKey(f.getProperty('Boundary_Name'));
        if (showAllUnits || matcher.matches(ids, name)) visibleMatches += 1;
    });
    const showFilteredMatches = showBoundaries && (showAllUnits || visibleMatches > 0);
    huntUnitsLayer.setStyle(f => {
        const ids = getDataFeatureBoundaryCandidateIds(f);
        const name = normalizeBoundaryKey(f.getProperty('Boundary_Name'));
        const isMatch = showAllUnits || matcher.matches(ids, name);
        const isSelected = !!selectedMatcher && selectedMatcher.matches(ids, name);
        const visible = useIndependentLayerOnly
          ? false
          : (showFilteredMatches ? isMatch : showBoundaries);
        const emphasized = showFilteredMatches && isMatch;
        return {
          visible,
          strokeColor: isSelected ? '#c84f00' : '#3653b3',
          strokeWeight: isSelected ? 4 : emphasized ? 1.8 : 1,
          fillColor: isSelected ? '#ff8a3d' : '#3653b3',
          fillOpacity: visible ? (isSelected ? 0.22 : emphasized ? 0.08 : 0.02) : 0
        };
    });
    refreshIndependentBoundaryLayer().catch((error) => {
      console.warn('Independent boundary layer refresh failed.', error);
    });
}

function runApplyFiltersFlow(trigger = 'manual') {
  selectedHuntFocusOnly = false;
  closeSelectedHuntPopup();
  closeSelectedHuntFloat();
  closeSelectionInfoWindow();
  selectedHunt = null;
  selectedBoundaryFeature = null;
  clearSelectedBoundaryFallbackLayer();
  if (toggleDwrUnits && hasActiveMatrixSelections()) {
    toggleDwrUnits.checked = true;
  }
  refreshSelectionMatrix();
  styleBoundaryLayer();
  refreshGoogleEarth3dBoundaryOverlay();
  renderMatchingHunts();
  renderSelectedHunt();
  renderOutfitters();

  const results = getDisplayHunts();
  const count = results.length;
  const selectedUnitValue = safe(unitFilter?.value).trim();
  const selectedUnitGroups = getSelectedUnitGroups();
  const isLive = trigger === 'live';

  if (!isLive) {
    if (typeof window !== 'undefined' && document.getElementById('matchingHunts')) {
      document.getElementById('matchingHunts').scrollTop = 0;
    }
    scrollSidebarToHuntResults();
  }

  if (!count) {
    updateStatus('No matching hunts found for the current filters.');
  } else {
    if (!isLive) {
      if (selectedUnitValue && selectedUnitGroups.length === 1) {
        zoomToDisplayHuntsBounds();
      } else if (!selectedUnitValue) {
        zoomToDisplayHuntsBounds();
      }
      const chooserTitle = selectedUnitValue
        ? firstNonEmpty(selectedUnitGroups[0]?.unitName, selectedUnitValue, 'Available Hunts')
        : `Available Hunts (${count})`;
      showHuntMatchesChooser(chooserTitle, results, 'Available Hunts');
      updateStatus(`${count} matching hunt${count === 1 ? '' : 's'} applied.`);
    } else {
      updateStatus(`${count} matching hunt${count === 1 ? '' : 's'} (live update).`);
    }
  }

  trackAnalytics('filters_applied', {
    trigger,
    matches: count,
    species: safe(speciesFilter?.value || ''),
    sex: safe(sexFilter?.value || ''),
    hunt_type: safe(huntTypeFilter?.value || ''),
    hunt_class: safe(huntCategoryFilter?.value || ''),
    weapon: safe(weaponFilter?.value || ''),
    unit: safe(unitFilter?.value || ''),
  });
}

function scheduleLiveFilterApply() {
  if (isMobileViewport()) return;
  if (!googleBaselineMap) return;
  if (liveFilterDebounceTimerId) {
    window.clearTimeout(liveFilterDebounceTimerId);
  }
  liveFilterDebounceTimerId = window.setTimeout(() => {
    runApplyFiltersFlow('live');
  }, LIVE_FILTER_DESKTOP_DEBOUNCE_MS);
}

function syncApplyFiltersButtonLabel() {
  if (!applyFiltersBtn) return;
  applyFiltersBtn.textContent = 'Apply';
  applyFiltersBtn.title = 'Apply filters and open matching hunts';
}

function bindControls() {
  if (controlsBound) return;
  controlsBound = true;

  searchInput?.addEventListener('input', handleFilterChange);
  searchInput?.addEventListener('change', handleFilterChange);
  [speciesFilter, sexFilter, huntTypeFilter, weaponFilter, huntCategoryFilter, unitFilter].forEach(el => {
    el?.addEventListener('change', handleFilterChange);
  });
  applyFiltersBtn?.addEventListener('click', () => runApplyFiltersFlow('manual'));
  clearFiltersBtn?.addEventListener('click', resetAllFilters);
  syncApplyFiltersButtonLabel();
  window.addEventListener('resize', syncApplyFiltersButtonLabel);
  document.getElementById('matchingHunts')?.addEventListener('click', event => {
    const researchBtn = event.target.closest('[data-hunt-research-key]');
    if (researchBtn) {
      event.stopPropagation();
      event.preventDefault();
      const key = researchBtn.getAttribute('data-hunt-research-key');
      const hunt = key ? huntData.find(candidate => getHuntRecordKey(candidate) === key) : null;
      if (hunt) saveHuntAndOpenResearch(hunt, 'Resident', 12);
      return;
    }
    const compareBtn = event.target.closest('[data-hunt-compare-key]');
    if (compareBtn) {
      event.stopPropagation();
      event.preventDefault();
      const key = compareBtn.getAttribute('data-hunt-compare-key');
      const hunt = key ? huntData.find(candidate => getHuntRecordKey(candidate) === key) : null;
      if (hunt) openCompareHunts(hunt, 'Resident', 12);
      return;
    }
    const saveBtn = event.target.closest('[data-hunt-save-key]');
    if (saveBtn) {
      event.stopPropagation();
      event.preventDefault();
      const key = saveBtn.getAttribute('data-hunt-save-key');
      const hunt = key ? huntData.find(candidate => getHuntRecordKey(candidate) === key) : null;
      if (hunt) {
        const record = saveHuntToBackpack(hunt, 'Resident', 12);
        if (record?.hunt_code) updateStatus(`${record.hunt_code} saved to Hunt Backpack.`);
      }
      return;
    }
    const outfitterBtn = event.target.closest('[data-hunt-outfitters-key]');
    if (outfitterBtn) {
      event.stopPropagation();
      event.preventDefault();
      const key = outfitterBtn.getAttribute('data-hunt-outfitters-key');
      const hunt = key ? huntData.find(candidate => getHuntRecordKey(candidate) === key) : null;
      if (hunt) openOutfitterMatches(hunt);
      return;
    }
    const selectBtn = event.target.closest('[data-hunt-select-key]');
    if (selectBtn) {
      event.stopPropagation();
      event.preventDefault();
      const key = selectBtn.getAttribute('data-hunt-select-key');
      if (key) window.selectHuntByKey(key);
      return;
    }
    const card = event.target.closest('[data-hunt-key]');
    if (!card) return;
    window.selectHuntByKey(card.getAttribute('data-hunt-key'));
  });
  document.getElementById('matchingHunts')?.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    if (event.target.closest('[data-hunt-research-key], [data-hunt-compare-key], [data-hunt-save-key], [data-hunt-outfitters-key], [data-hunt-select-key]')) {
      return;
    }
    const researchBtn = event.target.closest('[data-hunt-research-key]');
    if (researchBtn) {
      event.preventDefault();
      const key = researchBtn.getAttribute('data-hunt-research-key');
      const hunt = key ? huntData.find(candidate => getHuntRecordKey(candidate) === key) : null;
      if (hunt) saveHuntAndOpenResearch(hunt, 'Resident', 12);
      return;
    }
    if (event.target.closest('[data-hunt-select-key]')) return;
    const card = event.target.closest('[data-hunt-key]');
    if (!card) return;
    event.preventDefault();
    window.selectHuntByKey(card.getAttribute('data-hunt-key'));
  });
  document.getElementById('closeMapChooserBtn')?.addEventListener('click', closeSelectedHuntPopup);
  document.getElementById('closeHuntDetailsBtn')?.addEventListener('click', closeInlineHuntDetails);
  mapTypeSelect?.addEventListener('change', applyMapMode);
  streetViewBtn?.addEventListener('click', openStreetViewAtFocus);
  resetViewBtn?.addEventListener('click', resetMapView);
  toggleDwrUnits?.addEventListener('change', () => {
    if (!toggleDwrUnits.checked) {
      closeSelectionInfoWindow();
      closeSelectedHuntPopup();
      closeSelectedHuntFloat();
    }
    styleBoundaryLayer();
    refreshGoogleEarth3dBoundaryOverlaySoon();
    if (toggleDwrUnits.checked && hasActiveMatrixSelections()) {
      if (safe(mapTypeSelect?.value).toLowerCase() === 'earth') {
        refreshGoogleEarth3dBoundaryOverlaySoon();
      } else if (safe(mapTypeSelect?.value).toLowerCase() === 'google') {
        zoomToDisplayHuntsBounds();
      }
    }
  });
  toggleUSFS?.addEventListener('change', async () => {
    if (toggleUSFS.checked) await ensureUsfsLayer().catch(err => console.error('USFS layer failed', err));
    setLayerVisibility(usfsLayer, !!toggleUSFS.checked);
    if (shouldShowWildernessOverlay()) await ensureWildernessLayer().catch(err => console.error('Wilderness layer failed', err));
    updateWildernessOverlayVisibility();
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateFederalLayersSummary();
  });
  toggleBLM?.addEventListener('change', async () => {
    if (toggleBLM.checked) await ensureBlmLayer().catch(err => console.error('BLM layer failed', err));
    setLayerVisibility(blmLayer, !!toggleBLM.checked);
    if (toggleBLM.checked || toggleBLMDetail?.checked) await ensureBlmDetailLayer().catch(err => console.error('BLM detail layer failed', err));
    setLayerVisibility(blmDetailLayer, !!(toggleBLM.checked || toggleBLMDetail?.checked));
    applyBlmDetailLayerStyle();
    if (shouldShowWildernessOverlay()) await ensureWildernessLayer().catch(err => console.error('Wilderness layer failed', err));
    updateWildernessOverlayVisibility();
    if (toggleUSFS?.checked) {
      setLayerVisibility(usfsLayer, false);
      setLayerVisibility(usfsLayer, true);
    }
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateFederalLayersSummary();
  });
  toggleBLMDetail?.addEventListener('change', async () => {
    if (toggleBLMDetail.checked) await ensureBlmDetailLayer().catch(err => console.error('BLM detail layer failed', err));
    setLayerVisibility(blmDetailLayer, !!(toggleBLM?.checked || toggleBLMDetail.checked));
    applyBlmDetailLayerStyle();
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateFederalLayersSummary();
  });
  toggleSITLA?.addEventListener('change', async () => {
    if (toggleSITLA.checked) await ensureSitlaLayer().catch(err => console.error('SITLA layer failed', err));
    setLayerVisibility(sitlaLayer, !!toggleSITLA.checked);
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateStateLayersSummary();
  });
  toggleStateParks?.addEventListener('change', async () => {
    if (toggleStateParks.checked) await ensureStateParksLayer().catch(err => console.error('State parks layer failed', err));
    setLayerVisibility(stateParksLayer, !!toggleStateParks.checked);
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateStateLayersSummary();
  });
  toggleWma?.addEventListener('change', async () => {
    if (toggleWma.checked) await ensureWmaLayer().catch(err => console.error('WMA layer failed', err));
    setLayerVisibility(wmaLayer, !!toggleWma.checked);
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updateStateLayersSummary();
  });
  toggleCwmu?.addEventListener('change', async () => {
    if (toggleCwmu.checked) await ensureCwmuLayer().catch(err => console.error('CWMU layer failed', err));
    setLayerVisibility(cwmuLayer, !!toggleCwmu.checked);
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updatePrivateLayersSummary();
  });
  togglePrivate?.addEventListener('change', async () => {
    if (togglePrivate.checked) await ensurePrivateLayer().catch(err => console.error('Private layer failed', err));
    setLayerVisibility(privateLayer, !!togglePrivate.checked);
    refreshGoogleEarth3dBoundaryOverlaySoon();
    updatePrivateLayersSummary();
  });
  instructionsTab?.addEventListener('click', () => {
    setInstructionsOpen(instructionsPanel?.hidden ?? false);
  });
  plannerDnrLogoLink?.addEventListener('click', (event) => {
    event.preventDefault();
    if (mapTypeSelect) {
      mapTypeSelect.value = 'dwr';
      applyMapMode();
    }
  });
  document.addEventListener('click', (event) => {
    if (!instructionsPanel || !instructionsTab || instructionsPanel.hidden) return;
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (instructionsPanel.contains(target) || instructionsTab.contains(target)) return;
    setInstructionsOpen(false);
  });
  document.addEventListener('uoga:backpack-changed', () => {
    const basket = window.UOGA_UI?.getBasket?.();
    const basketCount = Array.isArray(basket) ? basket.length : 0;
    trackAnalytics('hunt_saved_to_backpack', { basket_count: basketCount });
  });
}

function zoomToSelectedBoundary() {
  if (!selectedHunt) return;
  const bounds = new google.maps.LatLngBounds();
  let found = false;
  if (selectedBoundaryFallbackLayer) {
    selectedBoundaryFallbackLayer.forEach((feature) => {
      feature.getGeometry().forEachLatLng((latLng) => {
        bounds.extend(latLng);
        found = true;
      });
    });
  }
  if (!found && !huntUnitsLayer) return;
  const matcher = buildBoundaryMatcher([selectedHunt]);
  if (!found) {
    huntUnitsLayer.forEach(f => {
      const featureBoundaryIds = getDataFeatureBoundaryCandidateIds(f);
      const featureName = normalizeBoundaryKey(f.getProperty('Boundary_Name'));
      if (matcher.matches(featureBoundaryIds, featureName)) {
        f.getGeometry().forEachLatLng(ll => { bounds.extend(ll); found = true; });
      }
    });
  }
  if (found) {
    googleBaselineMap.fitBounds(bounds);
    google.maps.event.addListenerOnce(googleBaselineMap, 'bounds_changed', () => {
      const maxZoom = 9;
      if ((googleBaselineMap.getZoom?.() || 0) > maxZoom) {
        googleBaselineMap.setZoom(maxZoom);
      }
    });
  }
}

function zoomToDisplayHuntsBounds() {
  if (!huntUnitsLayer || !googleBaselineMap) return false;
  const filtered = getDisplayHunts();
  if (!filtered.length) return false;
  const matcher = buildBoundaryMatcher(filtered);
  const bounds = new google.maps.LatLngBounds();
  let found = false;
  huntUnitsLayer.forEach(f => {
    const ids = getDataFeatureBoundaryCandidateIds(f);
    const name = normalizeBoundaryKey(f.getProperty('Boundary_Name'));
    if (matcher.matches(ids, name)) {
      f.getGeometry().forEachLatLng(ll => {
        bounds.extend(ll);
        found = true;
      });
    }
  });
  if (found) {
    googleBaselineMap.fitBounds(bounds);
    return true;
  }
  return false;
}

function getSidebarScrollContainer() {
  return document.querySelector('.sidebar');
}

function scrollSidebarToElement(targetEl, offset = 12, behavior = 'smooth') {
  if (!targetEl) return;
  const container = getSidebarScrollContainer();
  if (!container) {
    targetEl.scrollIntoView({ behavior, block: 'start' });
    return;
  }
  const containerRect = container.getBoundingClientRect();
  const targetRect = targetEl.getBoundingClientRect();
  const nextTop = container.scrollTop + (targetRect.top - containerRect.top) - offset;
  container.scrollTo({ top: Math.max(0, nextTop), behavior });
}

function isAdvancedMatrixSelection(controlId) {
  const el = document.getElementById(controlId);
  if (!el) return false;
  const value = safe(el.value).trim();
  if (!value) return false;
  if (controlId === 'speciesFilter') return value !== 'All Species';
  return value !== 'All';
}

function getNextVisibleMatrixControlId(sequence, idx) {
  for (let i = idx + 1; i < sequence.length; i += 1) {
    const el = document.getElementById(sequence[i]);
    const step = el?.closest?.('.matrix-step');
    if (el && !el.disabled && !step?.classList.contains('is-collapsed')) {
      return sequence[i];
    }
  }
  return 'applyFiltersBtn';
}

function maybeAutoAdvanceFilterMatrix(changedId) {
  const sequence = PROGRESSIVE_MATRIX_SEQUENCE;
  const idx = sequence.indexOf(changedId);
  if (idx < 0) return;
  if (!isAdvancedMatrixSelection(changedId)) return;
  const currentEl = document.getElementById(changedId);
  const nextId = getNextVisibleMatrixControlId(sequence, idx);
  const nextEl = document.getElementById(nextId);
  if (!nextEl) return;
  window.setTimeout(() => {
    // Keep the prior selection in view while guiding to the next step.
    scrollSidebarToElement(currentEl || nextEl, 12, 'smooth');
    if (!isMobileViewport() && typeof nextEl.focus === 'function') {
      nextEl.focus({ preventScroll: true });
    }
  }, 60);
}

function scrollSidebarToHuntResults() {
  const results = document.getElementById('matchingHunts');
  if (!results) return;
  const panel = results.closest('.panel') || results;
  window.setTimeout(() => {
    scrollSidebarToElement(panel, 10, 'smooth');
  }, 40);
}

function bootstrapPendingHuntSelection() {
  const params = new URLSearchParams(window.location.search || '');
  const pendingCode = safe(params.get('hunt_code')).trim().toUpperCase();
  if (!pendingCode) return;
  const match = huntData.find((hunt) => safe(getHuntCode(hunt)).trim().toUpperCase() === pendingCode);
  if (!match) return;
  selectedHuntFocusOnly = true;
  selectedHunt = match;
  syncSelectedHuntAcrossMapModes({ closeChooser: false, zoomGoogle: true });
}

// --- BOOTSTRAP ---
document.addEventListener('DOMContentLoaded', async () => {
  if (maybeRedirectLocalIpToLocalhost()) return;
  initOwnershipControlInHeader();
  installGoogleAuthErrorMonitor();
  initDevDebugPanel();
  initDwrFrameEvents();
  window.addEventListener('hashchange', syncMapModeFromHash);
  syncPlannerNavState();
  updateStatus(`Loading Google map (${getGoogleKeySourceLabel()})...`);

  const activeGoogleMapsKey = await resolveGoogleMapsApiKeyWithLocalWait();
  if (!isLikelyGoogleApiKey(activeGoogleMapsKey)) {
    handleGoogleMapUnavailable('Google map disabled until a valid key is provided.');
  }
  // Load Google Maps API. Boundaries and land layers stay wired to this map.
  window.gm_authFailure = () => {
    console.error('Google Maps API authentication failed.');
    handleGoogleMapsFailure('Google map authentication failed.');
  };
  loadGoogleMapsApiScript(activeGoogleMapsKey);
  
  // Load Data
  await loadConservationPermitAreas();
  await loadConservationPermitHuntTable();
  await loadCompositeBoundaryLookup();
  await loadHuntData();
  await loadOutfitters();
  await loadOutfitterFederalCoverage();
  try {
      finalizedBoundaryGeoJson = await fetchFirstGeoJson(FINALIZED_BOUNDARY_SOURCES);
  } catch (e) {
      console.warn('Finalized boundary GeoJSON load failed; boundary-id fallback may be limited.', e);
  }
  try {
      huntBoundaryGeoJson = await fetchFirstGeoJson(HUNT_BOUNDARY_SOURCES);
      if (huntData.length) applyBoundaryManifestToHunts(huntData);
      if (googleApiReady) buildBoundaryLayer();
  } catch(e) { console.error("GeoJSON load failed", e); }

  refreshSelectionMatrix();
  renderMatchingHunts();
  bootstrapPendingHuntSelection();
  bindControls();
  syncMapModeFromHash();
  applyMapMode();
});

async function resolveGoogleMapsApiKeyWithLocalWait() {
  let key = resolveGoogleMapsApiKey();
  if (isLikelyGoogleApiKey(key) || !isLocalDevHost()) return key;

  // config.local.js is dynamically injected from index.html in local dev and may land after DOMContentLoaded.
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 100));
    key = resolveGoogleMapsApiKey();
    if (isLikelyGoogleApiKey(key)) return key;
  }
  return key;
}

function sortWithPreferredOrder(arr, pref) {
    const map = new Map(pref.map((v, i) => [v, i]));
    return arr.sort((a, b) => (map.has(a) ? map.get(a) : 99) - (map.has(b) ? map.get(b) : 99));
}

function getCurrentOrigin() {
  if (typeof window === 'undefined') return '';
  const origin = String(window.location?.origin || '').trim();
  return origin || `${window.location.protocol}//${window.location.host}`;
}

function maybeRedirectLocalIpToLocalhost() {
  if (typeof window === 'undefined') return false;
  const protocol = String(window.location?.protocol || '');
  const hostname = String(window.location?.hostname || '').toLowerCase();
  if ((protocol !== 'http:' && protocol !== 'https:') || hostname !== '127.0.0.1') return false;
  const port = window.location?.port ? `:${window.location.port}` : '';
  const target = `${protocol}//localhost${port}${window.location.pathname || '/'}${window.location.search || ''}${window.location.hash || ''}`;
  try {
    const guardKey = 'uoga_localhost_redirect_done_v1';
    if (sessionStorage.getItem(guardKey) === '1') return false;
    sessionStorage.setItem(guardKey, '1');
  } catch {
    // ignore sessionStorage failures and still attempt redirect
  }
  window.location.replace(target);
  return true;
}

function buildGoogleReferrerHint() {
  const origin = getCurrentOrigin();
  if (!origin) return 'Add your local URL to allowed HTTP referrers in Google Maps key restrictions.';
  return `Allow this referrer in Google Maps key restrictions: ${origin}/*`;
}

function isLocalDevHost() {
  if (typeof window === 'undefined') return false;
  if (window.location?.protocol === 'file:') return true;
  const host = String(window.location?.hostname || '').toLowerCase();
  return host === 'localhost'
    || host === '127.0.0.1'
    || host === '::1'
    || host === '[::1]'
    || host.endsWith('.local')
    || host.endsWith('.lan')
    || /^10\./.test(host)
    || /^192\.168\./.test(host)
    || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
}

function isLikelyGoogleApiKey(value) {
  const key = String(value || '').trim();
  return /^AIza[0-9A-Za-z_-]{35}$/.test(key);
}

function getLocalGoogleMapsApiKeyOverride() {
  if (!isLocalDevHost() || typeof window === 'undefined') return '';
  const fileOverride = String(window.UOGA_LOCAL_CONFIG?.GOOGLE_MAPS_API_KEY || '').trim();
  if (isLikelyGoogleApiKey(fileOverride)) return fileOverride;
  const runtimeOverride = String(window.UOGA_LOCAL_GOOGLE_MAPS_API_KEY || '').trim();
  if (isLikelyGoogleApiKey(runtimeOverride)) return runtimeOverride;
  try {
    const stored = String(localStorage.getItem('uoga_google_maps_api_key') || '').trim();
    return isLikelyGoogleApiKey(stored) ? stored : '';
  } catch {
    return '';
  }
}

function resolveGoogleMapsApiKey() {
  const localOverride = getLocalGoogleMapsApiKeyOverride();
  if (localOverride) return localOverride;
  return isLikelyGoogleApiKey(GOOGLE_MAPS_API_KEY) ? String(GOOGLE_MAPS_API_KEY).trim() : '';
}

function getGoogleMapsKeySource() {
  if (getLocalGoogleMapsApiKeyOverride()) return 'local override key';
  return isLikelyGoogleApiKey(GOOGLE_MAPS_API_KEY) ? 'config key' : 'missing key';
}

function getGoogleKeySourceLabel() {
  const resolvedKey = resolveGoogleMapsApiKey();
  if (resolvedKey) {
    const masked = `${resolvedKey.slice(0, 6)}...${resolvedKey.slice(-4)}`;
    return `${getGoogleMapsKeySource()} (${masked})`;
  }
  return isLocalDevHost() ? 'missing local dev key' : 'missing production key';
}

function loadGoogleMapsApiScript(apiKey) {
  if (!isLikelyGoogleApiKey(apiKey) || googleApiReady || googleApiLoading) return false;
  const key = String(apiKey).trim();
  if (window.google?.maps?.Map) {
    window.setTimeout(initGoogleBaseline, 0);
    return true;
  }
  const existing = document.getElementById('uoga-google-maps-api');
  if (existing?.parentNode) {
    existing.parentNode.removeChild(existing);
  }
  const script = document.createElement('script');
  script.id = 'uoga-google-maps-api';
  script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=${GOOGLE_MAPS_SCRIPT_CHANNEL}&libraries=${GOOGLE_MAPS_SCRIPT_LIBRARIES}&loading=async&callback=initGoogleBaseline`;
  script.async = true;
  script.defer = true;
  googleApiLoading = true;
  script.onerror = () => {
    console.error('Google Maps API failed to load.');
    handleGoogleMapsFailure('Google map failed to load.');
  };
  document.head.appendChild(script);
  if (googleMapsLoadTimeoutId) {
    clearTimeout(googleMapsLoadTimeoutId);
  }
  googleMapsLoadTimeoutId = setTimeout(() => {
    if (!googleApiReady) {
      console.error('Google Maps API load timed out.');
      handleGoogleMapsFailure('Google map timed out.');
    }
  }, 12000);
  return true;
}

function handleGoogleMapsFailure(failureReason) {
  googleApiLoading = false;
  const fallbackMessage = `${failureReason} (${getGoogleKeySourceLabel()}) ${buildGoogleReferrerHint()}`;
  googleMapFailureMessage = fallbackMessage;
  handleGoogleMapUnavailable(fallbackMessage);
  renderDevDebugPanel();
}

function installGoogleAuthErrorMonitor() {
  if (typeof window === 'undefined') return;
  if (window.__uogaGoogleAuthMonitorInstalled) return;
  window.__uogaGoogleAuthMonitorInstalled = true;

  window.addEventListener('error', (event) => {
    const msg = String(event?.message || '');
    if (msg.includes('RefererNotAllowedMapError')) {
      handleGoogleMapsFailure('Google map blocked by referrer restrictions.');
      return;
    }
    if (
      msg.includes('InvalidKeyMapError')
      || msg.includes('InvalidKey')
      || msg.includes('ApiProjectMapError')
      || msg.includes('NoApiKeys')
      || msg.includes('BillingNotEnabledMapError')
    ) {
      handleGoogleMapsFailure('Google map key is invalid.');
    }
  });
}

function getCurrentMapModeForDebug() {
  const value = safe(mapTypeSelect?.value).toLowerCase();
  if (value === 'dwr') return 'dwr';
  if (value === 'earth') return 'earth';
  return 'google';
}

function ensureDevDebugPanel() {
  if (!isLocalDevHost() || typeof document === 'undefined') return null;
  if (devDebugPanelEl && document.body.contains(devDebugPanelEl)) return devDebugPanelEl;
  const panel = document.createElement('aside');
  panel.id = 'uogaDevDebugPanel';
  panel.setAttribute('aria-live', 'polite');
  panel.style.position = 'fixed';
  panel.style.left = '12px';
  panel.style.bottom = '12px';
  panel.style.zIndex = '10050';
  panel.style.maxWidth = '360px';
  panel.style.padding = '10px 12px';
  panel.style.border = '1px solid rgba(0,0,0,0.25)';
  panel.style.borderRadius = '10px';
  panel.style.background = 'rgba(18,18,18,0.92)';
  panel.style.color = '#f7f7f7';
  panel.style.font = '12px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
  panel.style.boxShadow = '0 6px 18px rgba(0,0,0,0.35)';
  panel.style.pointerEvents = 'none';
  document.body.appendChild(panel);
  devDebugPanelEl = panel;
  return panel;
}

function renderDevDebugPanel() {
  if (!isLocalDevHost()) return;
  const panel = ensureDevDebugPanel();
  if (!panel) return;
  const mapMode = getCurrentMapModeForDebug();
  const keySource = getGoogleMapsKeySource();
  const lastError = googleMapFailureMessage || 'none';
  const currentUrl = String(window.location?.href || '');
  const timestamp = new Date().toISOString();
  const snapshot = [
    `time=${timestamp}`,
    `mode=${mapMode}`,
    `key_source=${keySource}`,
    `last_google_error=${lastError}`,
    `url=${currentUrl}`
  ].join('\n');
  panel.innerHTML = [
    '<div style="font-weight:700; margin-bottom:6px;">UOGA Dev Debug</div>',
    `<div><strong>map mode:</strong> ${escapeHtml(mapMode)}</div>`,
    `<div><strong>key source:</strong> ${escapeHtml(keySource)}</div>`,
    `<div><strong>last google error:</strong> ${escapeHtml(lastError)}</div>`,
    '<button id="uogaDebugCopyBtn" type="button" style="margin-top:8px; border:1px solid rgba(255,255,255,0.35); border-radius:8px; background:rgba(255,255,255,0.08); color:#fff; padding:6px 8px; font:12px/1.2 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; pointer-events:auto; cursor:pointer;">Copy Debug Snapshot</button>'
  ].join('');
  const btn = panel.querySelector('#uogaDebugCopyBtn');
  if (btn) {
    btn.onclick = async () => {
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(snapshot);
          btn.textContent = 'Copied';
        } else {
          btn.textContent = 'Clipboard unavailable';
        }
      } catch {
        btn.textContent = 'Copy failed';
      } finally {
        window.setTimeout(() => {
          btn.textContent = 'Copy Debug Snapshot';
        }, 1200);
      }
    };
  }
}

function initDevDebugPanel() {
  if (!isLocalDevHost()) return;
  renderDevDebugPanel();
  if (devDebugPanelTimerId) {
    clearInterval(devDebugPanelTimerId);
  }
  devDebugPanelTimerId = setInterval(renderDevDebugPanel, 700);
}
// === Map mode custom picker sync ===
document.addEventListener('DOMContentLoaded', () => {
  if (window.__uogaMapModePickerBound) return;
  window.__uogaMapModePickerBound = true;

  const select = document.getElementById('mapTypeSelect');
  const picker = document.querySelector('[data-map-mode-picker]');
  const toggle = document.getElementById('mapModeToggleBtn');
  const menu = picker?.querySelector('.map-mode-menu');
  const current = picker?.querySelector('.map-mode-current');

  if (!select || !picker || !toggle || !menu || !current) return;

  const modes = {
    google: {
      html: '<img class="map-mode-logo" src="./assets/logos/google-maps-logo.png" alt="Google Maps">'
    },
    earth: {
      html: '<img class="map-mode-logo" src="./assets/logos/google_earth_logo.png?v=20260430-map-selector-1" alt="Google Earth">'
    },
    dwr: {
      html: '<img class="map-mode-logo map-mode-logo--dwr-current" src="./assets/logos/DWR-LOGO-TEXT.png?v=20260430-map-selector-1" alt="Utah DWR">'
    }
  };

  function syncPicker() {
    const value = select.value || 'google';
    current.innerHTML = (modes[value] || modes.google).html;

    menu.querySelectorAll('.map-mode-option').forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.mapModeValue === value);
    });
  }

  function closePicker() {
    menu.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  }

  toggle.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();

    const willOpen = menu.hidden;
    menu.hidden = !willOpen;
    toggle.setAttribute('aria-expanded', String(willOpen));
  });

  menu.querySelectorAll('.map-mode-option').forEach(btn => {
    btn.addEventListener('click', event => {
      event.preventDefault();

      select.value = btn.dataset.mapModeValue;
      select.dispatchEvent(new Event('change', { bubbles: true }));

      closePicker();
      toggle.focus();

      syncPicker();
    });
  });

  document.addEventListener('click', event => {
    if (!picker.contains(event.target)) {
      closePicker();
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closePicker();
  });

  select.addEventListener('change', syncPicker);

  // initialize
  syncPicker();
});
