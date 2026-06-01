window.UOGA_CONFIG = (() => {
  /*
    ============================================================================
    U.O.G.A. PUBLIC SITE CONFIG
    ----------------------------------------------------------------------------
    Notes:
    - This file is client-side and fully visible to the browser.
    - Any API key here must be restricted at the provider level.
    - Keep source ordering consistent across the site.
    ============================================================================
  */

  /*
    ============================================================================
    EXTERNAL SERVICES / API KEYS
    ============================================================================
  */
  const GOOGLE_MAPS_API_KEY = 'AIzaSyC49dXQ4FOyXqaUey4ASKlnDXWiwBHDlRM';
  function isPrivateIpv4Host(host) {
    return /^10\./.test(host)
      || /^192\.168\./.test(host)
      || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
  }
  function isDevLikeHost() {
    if (typeof window === 'undefined') return false;
    if (window.location?.protocol === 'file:') return true;
    const host = String(window.location?.hostname || '').toLowerCase();
    return host === 'localhost'
      || host === '127.0.0.1'
      || host === '::1'
      || host === '[::1]'
      || host.endsWith('.local')
      || host.endsWith('.lan')
      || isPrivateIpv4Host(host);
  }
  const UOGA_LOCAL_CONFIG = (typeof window !== 'undefined' && window.UOGA_LOCAL_CONFIG && typeof window.UOGA_LOCAL_CONFIG === 'object')
    ? window.UOGA_LOCAL_CONFIG
    : {};
  const USE_PREDICTIVE_DRAW_ENGINE = UOGA_LOCAL_CONFIG.USE_PREDICTIVE_DRAW_ENGINE === true
    || String(UOGA_LOCAL_CONFIG.USE_PREDICTIVE_DRAW_ENGINE || '').trim().toLowerCase() === 'true';
  // Optional: strongly recommended for Maps JS 3D runtime stability.
  const GOOGLE_MAPS_3D_MAP_ID = String(UOGA_LOCAL_CONFIG.GOOGLE_MAPS_3D_MAP_ID || '').trim();
  const CLOUDFLARE_BASE = 'https://json.uoga.workers.dev';
  const CLOUDFLARE_R2_BASE = String(UOGA_LOCAL_CONFIG.CLOUDFLARE_R2_BASE || '').trim().replace(/\/+$/, '');
  // Single object runtime source for large mapping assets:
  // prefer explicit R2 custom domain, otherwise fall back to existing Cloudflare endpoint.
  const CLOUDFLARE_OBJECT_BASE = CLOUDFLARE_R2_BASE || CLOUDFLARE_BASE;
  const fromR2 = (relPath) => CLOUDFLARE_OBJECT_BASE ? `${CLOUDFLARE_OBJECT_BASE}/${relPath}` : '';
  const withVersion = (url, version) => `${url}?v=${version}`;
  const appendVersion = (url, version) => {
    if (!url) return '';
    const clean = String(url).trim();
    if (!clean) return '';
    return clean.includes('?') ? `${clean}&v=${version}` : `${clean}?v=${version}`;
  };

  const RUNTIME_MANIFEST_CANDIDATES = [
    './public/data/runtime-manifest.json',
    './data/runtime-manifest.json',
  ];

  function loadRuntimeManifestSync() {
    if (typeof window === 'undefined' || typeof XMLHttpRequest === 'undefined') return null;
    for (const candidate of RUNTIME_MANIFEST_CANDIDATES) {
      try {
        const req = new XMLHttpRequest();
        req.open('GET', `${candidate}?v=20260601-runtime-manifest-1`, false);
        req.send(null);
        if (req.status < 200 || req.status >= 300) continue;
        const parsed = JSON.parse(String(req.responseText || '{}'));
        const assets = Array.isArray(parsed?.assets) ? parsed.assets : [];
        const byKey = {};
        assets.forEach((asset) => {
          const key = String(asset?.key || '').trim();
          if (!key) return;
          byKey[key] = asset;
        });
        return { ...parsed, byKey };
      } catch (_err) {
        // Continue through candidates/fallback.
      }
    }
    return null;
  }

  const RUNTIME_MANIFEST = loadRuntimeManifestSync();
  const runtimeManifestAsset = (key) => {
    const k = String(key || '').trim();
    return k ? (RUNTIME_MANIFEST?.byKey?.[k] || null) : null;
  };
  const manifestCanonical = (key, version) => {
    const url = String(runtimeManifestAsset(key)?.canonical_url || '').trim();
    return url ? appendVersion(url, version) : '';
  };

  const orderedProcessedRuntimeCandidates = (relativePath, version) => {
    const local = `./${relativePath}?v=${version}`;
    const remoteBase = fromR2(relativePath);
    const remote = remoteBase ? withVersion(remoteBase, version) : '';
    // Production should prefer CDN/object-hosted runtime assets over repo-served processed_data.
    return isDevLikeHost()
      ? [local, remote].filter(Boolean)
      : [remote, local].filter(Boolean);
  };

  /*
    ============================================================================
    MAP DEFAULTS / GEOGRAPHIC BOUNDS
    ============================================================================
  */
  const GOOGLE_BASELINE_DEFAULT_CENTER = { lat: 39.2672138, lng: -111.6346885 };
  const GOOGLE_BASELINE_DEFAULT_ZOOM = 7;

  const UTAH_LOCATION_BOUNDS = {
    minLat: 36.7,
    maxLat: 42.3,
    minLng: -114.3,
    maxLng: -108.8,
  };

  /*
    ============================================================================
    VERSION TOKENS
    ----------------------------------------------------------------------------
    Use these only for cache-busting and data refresh control.
    Keep them scoped by feature family.
    ============================================================================
  */
  const HUNT_DATA_VERSION = '20260508-boundary-zero-unmapped-1';
  const OUTFITTERS_DATA_VERSION = '20260327-city-logo-refresh-1';
  const OUTFITTER_COVERAGE_VERSION = '20260327-federal-coverage-demo-1';
  const HUNT_RESEARCH_DATA_VERSION = '20260529-cloudflare-runtime-first-1';

  /*
    ============================================================================
    DATA SOURCE ORDERING RULE
    ----------------------------------------------------------------------------
    Current policy:
    - Hunt Planner remains local-first for smaller canonical assets.
    - Hunt Research large runtime CSVs are Cloudflare-first to avoid Git LFS
      pointer files being served by static hosting.

    Keep this consistent unless you intentionally flip the whole site to prefer CDN.
    ============================================================================
  */

  /*
    ============================================================================
    HUNT PLANNER DATA SOURCES
    ============================================================================
  */
  const HUNT_BOUNDARY_SOURCES = [
    // Live runtime-safe sources first. These files are served as plain GeoJSON
    // in production, while some processed_data variants may be LFS pointers.
    `./data/hunt_boundaries.geojson?v=${HUNT_DATA_VERSION}`,
    `./data/hunt-boundaries-lite.geojson?v=${HUNT_DATA_VERSION}`,
    manifestCanonical('builder_composite_boundaries_2026_geojson', HUNT_DATA_VERSION),
    ...orderedProcessedRuntimeCandidates('processed_data/statewide_composite_boundaries_2026.geojson', HUNT_DATA_VERSION),
  ].filter(Boolean);
  const BOUNDARY_MANIFEST_SOURCES = [];
  const DISPLAY_BOUNDARY_INDEX_SOURCES = [
    manifestCanonical('builder_display_boundary_index_2026_json', HUNT_DATA_VERSION),
    ...orderedProcessedRuntimeCandidates('processed_data/display-boundary-index-2026.json', HUNT_DATA_VERSION),
    `./processed_data/display-boundary-index-2026.csv?v=${HUNT_DATA_VERSION}`,
  ].filter(Boolean);
  const FINALIZED_BOUNDARY_SOURCES = [
    `./data/hunt_boundaries.geojson?v=${HUNT_DATA_VERSION}`,
    `./data/hunt-boundaries-lite.geojson?v=${HUNT_DATA_VERSION}`,
  ].filter(Boolean);
  const COMPOSITE_BOUNDARY_SOURCES = [
    `./data/statewide-composite-members-2026-lite.geojson?v=${HUNT_DATA_VERSION}`,
    manifestCanonical('builder_composite_boundaries_2026_geojson', HUNT_DATA_VERSION),
    ...orderedProcessedRuntimeCandidates('processed_data/statewide_composite_boundaries_2026.geojson', HUNT_DATA_VERSION),
  ].filter(Boolean);

  const HUNT_DATA_SOURCES = [
    {
      label: 'Canonical hunt master',
      required: true,
      authoritative: true,
      candidates: [
        `./data/hunt-master-canonical-2026-foundation.json?v=${HUNT_DATA_VERSION}`,
        `./data/hunt-master-canonical-2026-source-of-truth.json?v=${HUNT_DATA_VERSION}`,
      ],
    },
  ];

  const ELK_BOUNDARY_TABLE_SOURCES = [
    `./data/elk_hunt_table_official.json?v=${HUNT_DATA_VERSION}`,
  ];

  const OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES = [
    './data/bighorn_sheep_hunt_table_official.json',
    './data/bison_hunt_table_official.json',
    './data/black_bear_hunt_table_official.json',
    './data/cougar_hunt_table_official.json',
    './data/elk_antlerless_hunt_table_official.json',
    './data/elk_hunt_table_official.json',
    './data/moose_hunt_table_official.json',
    './data/mountain_goat_hunt_table_official.json',
    './data/pronghorn_hunt_table_official.json',
    './data/turkey_hunt_table_official.json',
  ];

  /*
    ============================================================================
    OUTFITTER / COVERAGE DATA SOURCES
    ============================================================================
  */
  const OUTFITTERS_DATA_SOURCES = [
    `./data/outfitters-public.json?v=${OUTFITTERS_DATA_VERSION}`,
    `./data/outfitters.json?v=${OUTFITTERS_DATA_VERSION}`,
  ];

  const OUTFITTER_FEDERAL_COVERAGE_SOURCES = [];

  /*
    ============================================================================
    CONSERVATION / PERMIT AREA DATA SOURCES
    ============================================================================
  */
  const CONSERVATION_PERMIT_AREA_SOURCES = [
    `./data/conservation-permit-areas.json?v=${HUNT_DATA_VERSION}`,
  ];

  const CONSERVATION_PERMIT_HUNT_TABLE_SOURCES = [
    `./data/conservation-permit-hunt-table-2025-27.json?v=${HUNT_DATA_VERSION}`,
  ];

  /*
    ============================================================================
    HUNT RESEARCH DATA SOURCES
    ============================================================================
  */
  const HUNT_RESEARCH_DATA_SOURCES = [
    manifestCanonical('research_hunt_research_2026_json', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/hunt_research_2026.json?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/hunt_research_2026.json?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  const HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES = [
    manifestCanonical('research_draw_reality_engine_csv', HUNT_RESEARCH_DATA_VERSION),
    manifestCanonical('research_draw_reality_engine_v2_csv', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/draw_reality_engine.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/draw_reality_engine.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `${CLOUDFLARE_BASE}/processed_data/draw_reality_engine_v2.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/draw_reality_engine_v2.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  const HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES = [
    manifestCanonical('research_draw_reality_engine_predictive_v2_csv', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/draw_reality_engine_predictive_v2.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/draw_reality_engine_predictive_v2.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  const HUNT_RESEARCH_ENGINE_MODE = USE_PREDICTIVE_DRAW_ENGINE ? 'predictive' : 'observed';
  const HUNT_RESEARCH_ENGINE_SOURCES = HUNT_RESEARCH_ENGINE_MODE === 'predictive'
    ? HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES
    : HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES;

  const HUNT_RESEARCH_LADDER_SOURCES = [
    manifestCanonical('research_point_ladder_view_csv', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/point_ladder_view.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/point_ladder_view.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  const HUNT_RESEARCH_MASTER_SOURCES = [
    manifestCanonical('research_hunt_master_enriched_csv', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/hunt_master_enriched.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/hunt_master_enriched.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  const HUNT_RESEARCH_REFERENCE_SOURCES = [
    manifestCanonical('research_hunt_unit_reference_linked_csv', HUNT_RESEARCH_DATA_VERSION),
    `${CLOUDFLARE_BASE}/processed_data/hunt_unit_reference_linked.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
    `./processed_data/hunt_unit_reference_linked.csv?v=${HUNT_RESEARCH_DATA_VERSION}`,
  ];

  /*
    ============================================================================
    BRAND / LOGOS
    ============================================================================
  */
  const LOGO_DNR = 'https://static.wixstatic.com/media/43f827_34cd9f26f53f4b9ebcb200f6d878bea2~mv2.jpg';
  const LOGO_DWR_SELECTOR = './assets/logos/WILDLIFE-LOGO.png';
  const LOGO_DNR_ROOMY = 'https://static.wixstatic.com/media/43f827_28020dbfc9b9434c91dc6d92d9a07cd4~mv2.png';
  const LOGO_CWMU = './assets/logos/DWR-CWMU-LOGO.png';
  const LOGO_DWR_WMA = './assets/logos/DWR-WMA.LOGO.png';
  const LOGO_USFS = './assets/logos/usfs.png';
  const LOGO_BLM = './assets/logos/blm.png';
  const LOGO_SITLA = './assets/logos/sitla.png';
  const LOGO_STATE_PARKS = './assets/logos/state-parks.png';

  /*
    ============================================================================
    MAP LAYER / GIS SERVICE SOURCES
    ============================================================================
  */
  const LOCAL_CWMU_BOUNDARIES_PATH = './data/cwmu-boundaries.geojson';
  const CWMU_BOUNDARY_IDS_PATH = './data/dwr-GetCWMUBoundaries.json';

  const PUBLIC_OWNERSHIP_LAYER_URL =
    'https://services.arcgis.com/ZzrwjTRez6FJiOq4/ArcGIS/rest/services/SITLA_Ownership/FeatureServer/0';

  const BLM_SURFACE_OWNERSHIP_LAYER_URL =
    'https://gis.blm.gov/utarcgis/rest/services/Lands/BLM_UT_SMA/FeatureServer/0';

  const BLM_ADMIN_LAYER_URL =
    'https://gis.blm.gov/utarcgis/rest/services/AdminBoundaries/BLM_UT_ADMU/FeatureServer/0';

  const BLM_ADMIN_QUERY_URL =
    `${BLM_ADMIN_LAYER_URL}/query?where=${encodeURIComponent("BLM_ORG_TYPE IN ('District','Field')")}&outFields=*&returnGeometry=true&outSR=4326&f=geojson`;

  const CWMU_QUERY_URL =
    'https://dwrmapserv.utah.gov/dwrarcgis/rest/services/hunt/CWMU_Tradelands_ver3/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson';

  const STATE_PARKS_QUERY_URL =
    'https://services.arcgis.com/ZzrwjTRez6FJiOq4/ArcGIS/rest/services/Utah_State_Park_Management_Areas/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson';

  const WMA_QUERY_URL =
    'https://services.arcgis.com/ZzrwjTRez6FJiOq4/arcgis/rest/services/WMA/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson';

  const WILDERNESS_QUERY_URL =
    "https://services1.arcgis.com/ERdCHt0sNM6dENSD/ArcGIS/rest/services/Wilderness_Areas_in_the_United_States/FeatureServer/0/query?where=" +
    encodeURIComponent("STATE = 'UT' AND Agency IN ('BLM','FS')") +
    "&outFields=NAME,Agency,URL,Acreage&returnGeometry=true&outSR=4326&f=geojson";

  const UTAH_OUTLINE_QUERY_URL =
    // ArcGIS layer uses STATE as the display field; NAME is not a valid field and returns a 400 error.
    // If this URL ever changes, prefer pinning to a local GeoJSON to avoid external schema drift.
    'https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/UtahStateBoundary/FeatureServer/0/query?where=STATE%20%3D%20%27Utah%27&outFields=STATE&returnGeometry=true&outSR=4326&f=geojson';

  const USFS_QUERY_URL =
    "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_ForestSystemBoundaries_01/MapServer/0/query?where=" +
    encodeURIComponent("FORESTNAME IN ('Ashley National Forest','Dixie National Forest','Fishlake National Forest','Manti-La Sal National Forest','Uinta-Wasatch-Cache National Forest')") +
    "&outFields=FORESTNAME&returnGeometry=true&outSR=4326&f=geojson";

  /*
    ============================================================================
    HUNT / UNIT SPECIAL CASES
    ============================================================================
  */
  const WATERFOWL_WMA_NAMES = new Set([
    'bicknell bottoms',
    'browns park',
    'clear lake',
    'desert lake',
    'farmington bay',
    'harold crane',
    'howard slough',
    'locomotive springs',
    'ogden bay',
    'public shooting grounds',
    'salt creek',
    'timpie springs',
    'topaz',
    'willard spur',
  ]);

  const SPIKE_ELK_HUNT_CODES = new Set(['EB1003', 'EB1004', 'EB1009']);

  const HUNT_BOUNDARY_NAME_OVERRIDES = {
    DB1503: ['Manti, San Rafael'],
    DB1533: ['Manti, San Rafael'],
    DB1504: ['Nebo'],
    DB1534: ['Nebo'],
    DB1510: ['Monroe'],
    DB1540: ['Monroe'],
    DB1506: ['Fillmore'],
    DB1536: ['Fillmore'],
    EA1220: [
      'Manti, North',
      'Manti, South',
      'Manti, West',
      'Manti, Central',
      'Manti, Mohrland-Stump Flat',
      'Manti, Horn Mtn',
      'Manti, Gordon Creek-Price Canyon',
      'Manti, Ferron Canyon',
    ],
    EA1221: [
      'Fishlake/Thousand Lakes',
      'Fishlake/Thousand Lakes East',
      'Fishlake/Thousand Lakes West',
    ],
    EA1258: [
      'La Sal Mtns',
      'Dolores Triangle',
      'La Sal, La Sal Mtns-North',
    ],
    'la-sal-conservation': ['La Sal'],
    'fishlake-conservation': ['Fishlake'],
    'manti-conservation': [
      'Manti, North',
      'Manti, South',
      'Manti, West',
      'Manti, Central',
      'Manti, Mohrland-Stump Flat',
      'Manti, Horn Mtn',
      'Manti, Gordon Creek-Price Canyon',
      'Manti, Ferron Canyon',
      'South Manti',
      'Manti, Northeast',
      'Manti, Northwest',
      'Manti, Southeast',
      'Manti, Southwest',
    ],
    'cache-conservation': ['Cache'],
    'wasatch-mtns-conservation': [
      'Wasatch Mtns, West',
      'Wasatch Mtns, East',
      'Wasatch Mtns, Cascade',
      'Wasatch Mtns, Currant Creek',
      'Wasatch Mtns, Timpanogos A',
      'Wasatch Mtns, Box Elder Peak',
      'Wasatch Mtns, Lone Peak',
      'Wasatch Mtns, Provo Peak',
      'Wasatch Mtns, Alpine',
    ],
    'antelope-island-conservation-expo': ['Antelope Island'],
    'book-cliffs-north-and-south': ['Book Cliffs, North', 'Book Cliffs, South'],
  };

  /*
    ============================================================================
    MAP STYLE / ORDERING CONSTANTS
    ============================================================================
  */
  const huntPlannerMapStyle = [
    { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#f2f2f2' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#aadaff' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#c8e6c9' }] },
    { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  ];

  const HUNT_TYPE_ORDER = [
    'General Season',
    'Youth',
    'Limited Entry',
    'Premium Limited Entry',
    'Management',
    'Dedicated Hunter',
    'CWMU',
    'Private Land Only',
    'Conservation',
    'Once-in-a-Lifetime',
    'Antlerless',
  ];

  const HUNT_CLASS_ORDER = [
    'General Season',
    'General Bull',
    'Spike Only',
    'Mature Bull',
    'Limited Entry',
    'Premium Limited Entry',
    'Youth',
    'Management',
    'Antlerless',
    'CWMU',
    'Private Land Only',
    'Conservation',
    'Statewide Permit',
    'Extended Archery',
  ];

  const SEX_ORDER = [
    'Buck',
    'Bull',
    'Ram',
    'Ewe',
    'Bearded',
    'Antlerless',
    'Either Sex',
    "Hunter's Choice",
  ];

  const WEAPON_ORDER = [
    'Any Legal Weapon',
    'Archery',
    'Extended Archery',
    'Restricted Archery',
    'Muzzleloader',
    'Restricted Muzzleloader',
    'Restricted Rifle',
    'HAMSS',
    'Multiseason',
    'Restricted Multiseason',
  ];

  /*
    ============================================================================
    BRAND COLORS / PATCH OVERRIDES
    ============================================================================
  */
  const DNR_ORANGE = '#ff6600';
  const DNR_BROWN = '#4f2b14';

  // Temporary hardcoded fallback coordinates for known records that must render.
  const KNOWN_OUTFITTER_COORDS = new Map([
    ['outfitter-wild-eyez-outfitters', { lat: 39.2574155, lng: -111.631482 }],
    ['wild eyez outfitters', { lat: 39.2574155, lng: -111.631482 }],
  ]);

  return {
    GOOGLE_MAPS_API_KEY,
    GOOGLE_MAPS_3D_MAP_ID,
    GOOGLE_BASELINE_DEFAULT_CENTER,
    GOOGLE_BASELINE_DEFAULT_ZOOM,
    UTAH_LOCATION_BOUNDS,

    CLOUDFLARE_BASE,
    CLOUDFLARE_R2_BASE,
    RUNTIME_MANIFEST_CANDIDATES,
    RUNTIME_MANIFEST,

    HUNT_DATA_VERSION,
    OUTFITTERS_DATA_VERSION,
    OUTFITTER_COVERAGE_VERSION,
    HUNT_RESEARCH_DATA_VERSION,

    HUNT_BOUNDARY_SOURCES,
    DISPLAY_BOUNDARY_INDEX_SOURCES,
    BOUNDARY_MANIFEST_SOURCES,
    FINALIZED_BOUNDARY_SOURCES,
    COMPOSITE_BOUNDARY_SOURCES,
    HUNT_DATA_SOURCES,
    ELK_BOUNDARY_TABLE_SOURCES,
    OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,

    OUTFITTERS_DATA_SOURCES,
    OUTFITTER_FEDERAL_COVERAGE_SOURCES,

    CONSERVATION_PERMIT_AREA_SOURCES,
    CONSERVATION_PERMIT_HUNT_TABLE_SOURCES,

    HUNT_RESEARCH_DATA_SOURCES,
    USE_PREDICTIVE_DRAW_ENGINE,
    HUNT_RESEARCH_ENGINE_MODE,
    HUNT_RESEARCH_ENGINE_SOURCES,
    HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES,
    HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES,
    HUNT_RESEARCH_LADDER_SOURCES,
    HUNT_RESEARCH_MASTER_SOURCES,
    HUNT_RESEARCH_REFERENCE_SOURCES,

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
    SPIKE_ELK_HUNT_CODES,
    HUNT_BOUNDARY_NAME_OVERRIDES,

    huntPlannerMapStyle,
    HUNT_TYPE_ORDER,
    HUNT_CLASS_ORDER,
    SEX_ORDER,
    WEAPON_ORDER,

    DNR_ORANGE,
    DNR_BROWN,
    KNOWN_OUTFITTER_COORDS,
  };
})();

