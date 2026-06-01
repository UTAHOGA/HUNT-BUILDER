(function () {
  const ENGINE_MODE = (window.UOGA_CONFIG && window.UOGA_CONFIG.HUNT_RESEARCH_ENGINE_MODE)
    ? String(window.UOGA_CONFIG.HUNT_RESEARCH_ENGINE_MODE).trim().toLowerCase()
    : 'observed';
  const DATA_SOURCES = (window.UOGA_CONFIG && Array.isArray(window.UOGA_CONFIG.HUNT_RESEARCH_DATA_SOURCES) && window.UOGA_CONFIG.HUNT_RESEARCH_DATA_SOURCES.length)
    ? window.UOGA_CONFIG.HUNT_RESEARCH_DATA_SOURCES
    : ['./processed_data/hunt_research_2026.json'];
  const ENGINE_SOURCES = (window.UOGA_CONFIG && Array.isArray(window.UOGA_CONFIG.HUNT_RESEARCH_ENGINE_SOURCES) && window.UOGA_CONFIG.HUNT_RESEARCH_ENGINE_SOURCES.length)
    ? window.UOGA_CONFIG.HUNT_RESEARCH_ENGINE_SOURCES
    : ['./processed_data/draw_reality_engine.csv'];

  const LADDER_SOURCES = (window.UOGA_CONFIG && Array.isArray(window.UOGA_CONFIG.HUNT_RESEARCH_LADDER_SOURCES) && window.UOGA_CONFIG.HUNT_RESEARCH_LADDER_SOURCES.length)
    ? window.UOGA_CONFIG.HUNT_RESEARCH_LADDER_SOURCES
    : ['./processed_data/point_ladder_view.csv'];

  const MASTER_SOURCES = (window.UOGA_CONFIG && Array.isArray(window.UOGA_CONFIG.HUNT_RESEARCH_MASTER_SOURCES) && window.UOGA_CONFIG.HUNT_RESEARCH_MASTER_SOURCES.length)
    ? window.UOGA_CONFIG.HUNT_RESEARCH_MASTER_SOURCES
    : ['./processed_data/hunt_master_enriched.csv'];

  const REFERENCE_SOURCES = (window.UOGA_CONFIG && Array.isArray(window.UOGA_CONFIG.HUNT_RESEARCH_REFERENCE_SOURCES) && window.UOGA_CONFIG.HUNT_RESEARCH_REFERENCE_SOURCES.length)
    ? window.UOGA_CONFIG.HUNT_RESEARCH_REFERENCE_SOURCES
    : ['./processed_data/hunt_unit_reference_linked.csv'];
  const ALLOW_LEGACY_FALLBACK = Boolean(window.UOGA_CONFIG?.HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK);

  const SELECTED_HUNT_KEY = 'selected_hunt_code';
  const SELECTED_RESIDENCY_KEY = 'selected_hunt_research_residency';
  const SELECTED_POINTS_KEY = 'selected_hunt_research_points';
  const SELECTED_DRAW_POOL_KEY = 'selected_hunt_research_draw_pool';
  const BASKET_KEY = 'uoga_hunt_basket_v1';
  const LEGACY_BASKET_KEY = 'hunt_research_recent_hunts';
  const PAGE_PARAMS = new URLSearchParams(window.location.search);
  const SHOW_AUDIT_ONLY_ROWS = (() => {
    const configured = window.UOGA_CONFIG?.HUNT_RESEARCH_DEBUG_AUDIT_MODE;
    const configuredText = typeof configured === 'boolean'
      ? String(configured)
      : String(configured || '').trim().toLowerCase();
    const flagText = String(PAGE_PARAMS.get('debug') || PAGE_PARAMS.get('audit') || '').trim().toLowerCase();
    return ['1', 'true', 'yes', 'on'].includes(flagText)
      || ['1', 'true', 'yes', 'on'].includes(configuredText);
  })();
  // Public draw permits already account for Expo permits. Conservation permits are not part of draw odds.

  const state = {
    loaded: false,
    loadingPromise: null,
    inputRunTimer: null,
    selectedHuntCode: '',
    selectedFilters: null,
    selectedMeta: null,
    engineRows: [],
    ladderRows: [],
    masterRows: [],
    referenceRows: [],
    engineByKey: new Map(),
    engineGroups: new Map(),
    ladderGroups: new Map(),
    masterPointByKey: new Map(),
    masterByResidency: new Map(),
    masterByCode: new Map(),
    referenceByKey: new Map(),
    referenceByCode: new Map(),
    engineHistoryByPoint: new Map(),
    engineMode: ENGINE_MODE,
    loadedSources: null,
  };

  const els = {
    huntCodeInput: document.getElementById('huntCodeInput'),
    residencySelect: document.getElementById('residencySelect'),
    drawPoolSelect: document.getElementById('drawPoolSelect'),
    pointsInput: document.getElementById('pointsInput'),
    filterReadout: document.getElementById('filterReadout'),
    plannerReadout: document.getElementById('plannerReadout'),
    runResearchButton: document.getElementById('runResearchButton'),
    clearFiltersButton: document.getElementById('clearFiltersButton'),
    addToBasketButton: document.getElementById('addToBasketButton'),

    verdictBadge: document.getElementById('verdictBadge'),
    verdictMessage: document.getElementById('verdictMessage'),

    selectedOutlook: document.getElementById('selectedOutlook'),
    selectedHuntCodeRead: document.getElementById('selectedHuntCodeRead'),
    selectedHarvestSuccess: document.getElementById('selectedHarvestSuccess'),
    selectedResidentPermits: document.getElementById('selectedResidentPermits'),
    selectedNonresidentPermits: document.getElementById('selectedNonresidentPermits'),

    detailTitle: document.getElementById('detailTitle'),
    detailSubtitle: document.getElementById('detailSubtitle'),
    detailEmpty: document.getElementById('detailEmpty'),
    detailContent: document.getElementById('detailContent'),
    openPlannerLink: document.getElementById('openPlannerLink'),
    openDwrLink: document.getElementById('openDwrLink'),

    summaryGuaranteedTop: document.getElementById('summaryGuaranteedTop'),
    summaryPointsTop: document.getElementById('summaryPointsTop'),
    summaryOddsTop: document.getElementById('summaryOddsTop'),

    summaryGuaranteed: document.getElementById('summaryGuaranteed'),
    summaryPoints: document.getElementById('summaryPoints'),
    summaryStatus: document.getElementById('summaryStatus'),
    summaryOdds: document.getElementById('summaryOdds'),
    selectedOutlookText: document.getElementById('selectedOutlookText'),
    summaryTrend: document.getElementById('summaryTrend'),
    summaryTrendText: document.getElementById('summaryTrendText'),
    summaryRecommendation: document.getElementById('summaryRecommendation'),

    ladderTableEmpty: document.getElementById('ladderTableEmpty'),
    ladderTableWrap: document.getElementById('ladderTableWrap'),
    ladderTableBody: document.getElementById('ladderTableBody'),
    ladderHeaderCol1: document.getElementById('ladderHeaderCol1'),
    ladderHeaderCol2: document.getElementById('ladderHeaderCol2'),
    ladderHeaderCol3: document.getElementById('ladderHeaderCol3'),
    ladderHeaderCol4: document.getElementById('ladderHeaderCol4'),
    ladderHeaderCol5: document.getElementById('ladderHeaderCol5'),
    ladderRange: document.getElementById('ladderRange'),
    jumpToPointsBtn: document.getElementById('jumpToPointsBtn'),
    pointLadderAccordion: document.getElementById('pointLadderAccordion'),

    sourceModal: document.getElementById('sourceModal'),
    sourceModalTitle: document.getElementById('sourceModalTitle'),
    sourceModalSubtitle: document.getElementById('sourceModalSubtitle'),
    sourceModalGrid: document.getElementById('sourceModalGrid'),
    sourceModalClose: document.getElementById('sourceModalClose'),

    basketCount: document.getElementById('basketCount'),
    basketList: document.getElementById('basketList'),
    clearBasketButton: document.getElementById('clearBasketButton'),
  };

  function normalizeKey(value) {
    return String(value || '').trim().toUpperCase();
  }

  function normalizeResidencyLabel(value) {
    return String(value || '').trim().toLowerCase() === 'nonresident' ? 'Nonresident' : 'Resident';
  }

  function normalizeDrawPool(value) {
    const normalized = String(value || '').trim().toLowerCase();
    return normalized || 'standard';
  }

  function getDrawPoolHandoffLabel(drawPool) {
    const labels = {
      youth: 'Youth draw',
      lifetime: 'Lifetime license draw',
      dedicated_hunter: 'Dedicated Hunter',
      youth_dedicated_hunter: 'Youth Dedicated Hunter',
      youth_mature_bull: 'Youth mature bull',
      youth_turkey: 'Youth turkey',
    };
    return labels[normalizeDrawPool(drawPool)] || '';
  }

  function groupKey(huntCode, residency, drawPool) {
    return `${normalizeKey(huntCode)}__${normalizeResidencyLabel(residency)}__${normalizeDrawPool(drawPool)}`;
  }

  function rowKey(huntCode, residency, points, drawPool) {
    return `${groupKey(huntCode, residency, drawPool)}__${String(points ?? '')}`;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function num(value) {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function hasValue(value) {
    const text = String(value ?? '').trim();
    return !!text && text.toUpperCase() !== 'N/A' && text.toUpperCase() !== 'NOT AVAILABLE';
  }

  function isOutOfScopeNonTargetRow(row) {
    return String(row?.algorithm_status || '').trim().toUpperCase() === 'OUT_OF_SCOPE_NON_TARGET'
      || String(row?.draw_system_type || '').trim().toUpperCase() === 'OUT_OF_SCOPE_NON_TARGET';
  }

  function getOutOfScopeAuditLabel() {
    return 'Out of scope / not a target prediction category';
  }

  function firstAvailable(source, keys) {
    if (!source || !Array.isArray(keys)) return null;
    for (const key of keys) {
      const value = source[key];
      if (hasValue(value)) return value;
    }
    return null;
  }

  function formatInteger(value) {
    const parsed = num(value);
    return parsed === null ? 'Not available' : parsed.toLocaleString();
  }

  function formatProbability(value) {
    const parsed = num(value);
    if (parsed === null || parsed <= 0) return 'Not available';
    if (parsed >= 99.95) return '100%';
    if (parsed >= 10) return `${parsed.toFixed(1)}%`;
    if (parsed >= 1) return `${parsed.toFixed(2)}%`;
    return `${parsed.toFixed(3)}%`;
  }

  function formatOddsAsOneInOrPercent(percentValue) {
    const parsed = num(percentValue);
    if (!Number.isFinite(parsed)) return 'Not available';
    if (parsed <= 0) return 'No modeled chance';

    const capped = clamp(parsed, 0, 100);
    const percentText = Number.isInteger(capped)
      ? `${capped}%`
      : `${Number(capped.toFixed(1)).toString()}%`;

    if (capped >= 99.9) return `~1 in 1 or ${percentText}`;

    const denominator = 100 / capped;
    const denominatorText = denominator < 10
      ? Number(denominator.toFixed(1)).toString()
      : Math.round(denominator).toString();

    return `~1 in ${denominatorText} or ${percentText}`;
  }

  const MAX_POINT_POOL_GUARANTEED_DISPLAY = '~1 in 1 or 99%';
  const DOCUMENTED_DRAW_RESULT_PREFIX = '=';
  const DRAW_MODE = {
    PREFERENCE: 'PREFERENCE',
    BONUS: 'BONUS',
    YOUTH_RESERVE: 'YOUTH_RESERVE',
    ALLOCATION_AVAILABILITY: 'ALLOCATION_AVAILABILITY',
    STATUS_ONLY: 'STATUS_ONLY',
  };

  function normalizeHistoricalOddsDisplay(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (/[0-9]\s*in\s*[0-9]/i.test(text)) {
      return text.replace(/~/g, DOCUMENTED_DRAW_RESULT_PREFIX);
    }

    const pct = num(text);
    if (pct === null || pct <= 0) return '';
    return formatOddsAsOneInOrPercent(pct).replace(/~/g, DOCUMENTED_DRAW_RESULT_PREFIX);
  }

  function formatHistoricalDrawResult(row) {
    const dwrDisplay = normalizeHistoricalOddsDisplay(row?.dwr_result_display);
    if (dwrDisplay) return dwrDisplay;

    const display = normalizeHistoricalOddsDisplay(row?.display_2025_draw_results);
    if (display) return display;

    const totalPermits = num(row?.total_permits);
    if (totalPermits === null || totalPermits <= 0) return '';

    const applicants = num(row?.applicants ?? row?.eligible_applicants);
    if (applicants === null || applicants <= 0) return '';

    const denominator = applicants / totalPermits;
    const percent = Math.min(100, 100 / denominator);
    return `${DOCUMENTED_DRAW_RESULT_PREFIX}1 in ${denominator.toFixed(1)} or ${percent.toFixed(1)}%`;
  }

  function getMaxPointPoolDisplay(row) {
    const zone = String(row?.point_pool_zone || '').trim();
    if (!['max_point_pool', 'max_pool_guaranteed', 'max_pool_cutoff_mixed'].includes(zone)) return '';
    if (zone === 'max_point_pool' || zone === 'max_pool_guaranteed') {
      return MAX_POINT_POOL_GUARANTEED_DISPLAY;
    }

    const display = String(row?.display_2026_max_point_pool || '').trim();
    if (display) return display;

    const pMaxPool = num(row?.p_max_pool_mean);
    if (pMaxPool !== null) return formatOddsAsOneInOrPercent(toProbabilityPercent(pMaxPool));
    const pMaxPoolPct = num(row?.p_max_pool_mean_pct ?? row?.p_max_pool_pct);
    if (pMaxPoolPct !== null) return formatOddsAsOneInOrPercent(pMaxPoolPct);
    const maxPoolProjection = firstAvailable(row, ['max_pool_projection_2026', 'odds_2026_projected']);
    return maxPoolProjection ? formatOddsAsOneInOrPercent(maxPoolProjection) : '';
  }

  function getRandomDrawDisplay(row) {
    const display = String(row?.display_2026_random_draw || '').trim();
    if (display) return display;

    const zone = String(row?.point_pool_zone || '').trim();
    if (!['random_pool', 'max_pool_cutoff_mixed'].includes(zone)) return '';
    const pRandomPool = num(row?.p_random_pool);
    if (pRandomPool !== null) return formatOddsAsOneInOrPercent(toProbabilityPercent(pRandomPool));
    const pRandomPoolPct = num(row?.p_random_pool_pct);
    if (pRandomPoolPct !== null) return formatOddsAsOneInOrPercent(pRandomPoolPct);
    const randomDraw = firstAvailable(row, ['random_draw_projection_2026', 'random_draw_odds_2026']);
    return randomDraw ? formatOddsAsOneInOrPercent(randomDraw) : '';
  }

  function cleanDisplayValue(value) {
    const text = String(value ?? '').trim();
    const lower = text.toLowerCase();
    if (!text || text === '0.000%' || ['not available', 'not applicable', 'n/a', 'null', 'undefined'].includes(lower)) return '';
    return text;
  }

  function renderLadderCell(value) {
    const text = cleanDisplayValue(value);
    if (!text) {
      return '<td class="is-empty-cell" aria-label="No useful data"></td>';
    }
    return `<td>${escapeHtml(text)}</td>`;
  }

  function formatGapStatus(gap) {
    const parsed = num(gap);
    if (parsed === null) return 'Not available';
    if (parsed > 0) return `${parsed} pts short of guaranteed`;
    if (parsed === 0) return 'At guaranteed';
    return `${Math.abs(parsed)} pts above guaranteed`;
  }

  const ML_OPTIONS = {
    enabled: false,
    useMlForOddsWhenConfidenceGte: null,
    maxDivergenceGuardPct: null,
    ...(window.UOGA_CONFIG?.HUNT_RESEARCH_ML_OPTIONS || {}),
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function toProbabilityPercent(value) {
    const parsed = num(value);
    if (parsed === null) return null;
    if (parsed >= 0 && parsed <= 1) return parsed * 100;
    return clamp(parsed, 0, 100);
  }

  function toProbabilityUnit(value) {
    const parsed = num(value);
    if (parsed === null) return null;
    if (parsed >= 0 && parsed <= 1) return parsed;
    if (parsed >= 0 && parsed <= 100) return parsed / 100;
    return clamp(parsed / 100, 0, 1);
  }

  function hasModeledProbabilityFields(row) {
    if (!row) return false;
    return [
      row.p_draw_pct,
      row.p_draw,
      row.p_bonus_pool_pct,
      row.p_random_pool_pct,
      row.display_odds_pct,
      row.p_draw_mean,
      row.p_draw_p10,
      row.p_draw_p90,
      row.guaranteed_probability,
    ].some(hasValue);
  }

  function getGuaranteedProbability(row) {
    return toProbabilityUnit(firstAvailable(row, ['guaranteed_probability']));
  }

  function isRandomOnlyBonusCase(meta, row, referenceRow) {
    if (isPreferenceFamily(meta, row, referenceRow)) return false;
    const maxPointPermits = num(row?.max_point_permits_2026);
    const randomPermits = num(row?.random_permits_2026);
    return maxPointPermits !== null && maxPointPermits <= 0 && randomPermits !== null && randomPermits > 0;
  }

  function getCurrentPoints() {
    const value = num(els.pointsInput.value);
    return value === null ? 0 : Math.max(0, Math.min(32, value));
  }

  function getResidencyKey() {
    return normalizeResidencyLabel(els.residencySelect.value);
  }

  function getDrawPoolKey() {
    return normalizeDrawPool(els.drawPoolSelect?.value);
  }

  function getBasket() {
    try {
      const current = localStorage.getItem(BASKET_KEY);
      if (current) {
        const parsed = JSON.parse(current);
        return Array.isArray(parsed) ? parsed : [];
      }
      const legacy = localStorage.getItem(LEGACY_BASKET_KEY);
      if (legacy) {
        const parsed = JSON.parse(legacy);
        return Array.isArray(parsed) ? parsed : [];
      }
    } catch (error) {
      console.warn('Could not read hunt pack.', error);
    }
    return [];
  }

  function saveBasket(items) {
    const trimmed = items.slice(0, 20);
    localStorage.setItem(BASKET_KEY, JSON.stringify(trimmed));
    localStorage.removeItem(LEGACY_BASKET_KEY);
    window.UOGA_UI?.notifyBackpackChanged?.();
  }

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let value = '';
    let inQuotes = false;

    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      const next = text[i + 1];

      if (char === '"') {
        if (inQuotes && next === '"') {
          value += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        row.push(value);
        value = '';
      } else if ((char === '\n' || char === '\r') && !inQuotes) {
        if (char === '\r' && next === '\n') i += 1;
        row.push(value);
        rows.push(row);
        row = [];
        value = '';
      } else {
        value += char;
      }
    }

    if (value.length || row.length) {
      row.push(value);
      rows.push(row);
    }

    if (!rows.length) return [];

    const headers = rows.shift().map((header, index) => {
      const cleaned = String(header || '').trim();
      return index === 0 ? cleaned.replace(/^\uFEFF/, '') : cleaned;
    });

    return rows
      .filter((record) => record.some((cell) => String(cell || '').trim() !== ''))
      .map((record) => {
        const mapped = {};
        headers.forEach((header, index) => {
          mapped[header] = record[index] ?? '';
        });
        return mapped;
      });
  }
  function isGitLfsPointerText(text) {
    return String(text || '').startsWith('version https://git-lfs.github.com/spec/v1');
  }

  async function tryLoadText(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Request failed for ${url}`);
    }
    const text = await response.text();

    if (isGitLfsPointerText(text)) {
      throw new Error(`Git LFS pointer served instead of data for ${url}`);
    }

    return text;
  }

  async function loadFirstAvailable(sources) {
    let lastError = null;
    for (const source of sources) {
      try {
        return {
          source,
          text: await tryLoadText(source),
        };
      } catch (error) {
        lastError = error;
        console.warn(`Failed source: ${source}`, error);
      }
    }
    throw lastError || new Error('No data source could be loaded.');
  }

  function parseJsonRows(text) {
    const parsed = JSON.parse(String(text || '[]'));
    if (Array.isArray(parsed)) return parsed;
    if (parsed && Array.isArray(parsed.rows)) return parsed.rows;
    if (parsed && Array.isArray(parsed.data)) return parsed.data;
    throw new Error('Canonical contract JSON did not contain a row array.');
  }

  function deriveCanonicalRuntimeTables(contractRows) {
    const engineRows = Array.isArray(contractRows) ? contractRows : [];
    const ladderRows = engineRows;
    const masterRows = [];
    const referenceRows = [];
    const seenMasterGroups = new Set();
    const seenReferenceGroups = new Set();
    const seenReferenceCodes = new Set();

    engineRows.forEach((row) => {
      const huntCode = normalizeKey(row?.hunt_code);
      if (!huntCode) return;
      const residency = normalizeResidencyLabel(row?.residency);
      const drawPool = normalizeDrawPool(row?.draw_pool);
      const group = groupKey(huntCode, residency, drawPool);
      const codeOnlyKey = huntCode;

      if (!seenMasterGroups.has(group)) {
        seenMasterGroups.add(group);
        masterRows.push({
          ...row,
          hunt_code: huntCode,
          residency,
          draw_pool: drawPool,
        });
      }

      if (!seenReferenceGroups.has(group)) {
        seenReferenceGroups.add(group);
        referenceRows.push({
          ...row,
          hunt_code: huntCode,
          residency,
          draw_pool: drawPool,
        });
      }

      if (!seenReferenceCodes.has(codeOnlyKey)) {
        seenReferenceCodes.add(codeOnlyKey);
        referenceRows.push({
          ...row,
          hunt_code: huntCode,
          residency,
          draw_pool: drawPool,
        });
      }
    });

    return { engineRows, ladderRows, masterRows, referenceRows };
  }

  function indexData(engineRows, ladderRows, masterRows, referenceRows) {
    state.engineRows = engineRows;
    state.ladderRows = ladderRows;
    state.masterRows = masterRows;
    state.referenceRows = referenceRows;
    state.engineByKey = new Map();
    state.engineGroups = new Map();
    state.ladderGroups = new Map();
    state.masterPointByKey = new Map();
    state.masterByResidency = new Map();
    state.masterByCode = new Map();
    state.referenceByKey = new Map();
    state.referenceByCode = new Map();
    state.engineHistoryByPoint = new Map();

    engineRows.forEach((row) => {
      const residency = normalizeResidencyLabel(row.residency);
      const drawPool = normalizeDrawPool(row.draw_pool);
      const year = num(row.year);
      const points = num(row.points);
      const key = rowKey(row.hunt_code, residency, points, drawPool);
      const group = groupKey(row.hunt_code, residency, drawPool);
      const normalized = { ...row, residency, points, year, draw_pool: drawPool };
      state.engineByKey.set(key, normalized);
      if (!state.engineGroups.has(group)) state.engineGroups.set(group, []);
      state.engineGroups.get(group).push(normalized);

      if (points !== null) {
        const historical = state.engineHistoryByPoint.get(key);
        const historicalYear = num(historical?.year);
        if (!historical || (year !== null && (historicalYear === null || year > historicalYear))) {
          state.engineHistoryByPoint.set(key, normalized);
        }
      }
    });

    masterRows.forEach((row) => {
      const residency = normalizeResidencyLabel(row.residency);
      const drawPool = normalizeDrawPool(row.draw_pool);
      const group = groupKey(row.hunt_code, residency, drawPool);
      const points = num(row.points);
      const key = rowKey(row.hunt_code, residency, points, drawPool);
      const normalized = { ...row, residency, draw_pool: drawPool };
      if (!state.masterByResidency.has(group)) {
        state.masterByResidency.set(group, normalized);
      }
      if (!state.masterByCode.has(normalizeKey(row.hunt_code))) {
        state.masterByCode.set(normalizeKey(row.hunt_code), normalized);
      }
      if (points !== null) {
        state.masterPointByKey.set(key, { ...row, residency, points, draw_pool: drawPool });
      }
    });
    ladderRows.forEach((row) => {
      const residency = normalizeResidencyLabel(row.residency);
      const drawPool = normalizeDrawPool(row.draw_pool);
      const group = groupKey(row.hunt_code, residency, drawPool);
      const points = num(row.points);
      const key = rowKey(row.hunt_code, residency, points, drawPool);
      const engineMatch = state.engineByKey.get(key);
      const masterPointMatch = state.masterPointByKey.get(key);
      const normalized = engineMatch
        ? { ...(masterPointMatch || {}), ...engineMatch, ...row, residency, points, draw_pool: drawPool }
        : { ...(masterPointMatch || {}), ...row, residency, points, draw_pool: drawPool };
      if (!state.ladderGroups.has(group)) state.ladderGroups.set(group, []);
      state.ladderGroups.get(group).push(normalized);

      if (engineMatch) {
        const enrichedEngine = { ...engineMatch, ...row, residency, points };
        state.engineByKey.set(key, enrichedEngine);
        const engineGroupRows = state.engineGroups.get(group);
        if (engineGroupRows && engineGroupRows.length) {
          const replaceIndex = engineGroupRows.findIndex((candidate) => candidate.points === points);
          if (replaceIndex >= 0) {
            engineGroupRows[replaceIndex] = enrichedEngine;
          }
        }
      }
    });

    referenceRows.forEach((row) => {
      const residency = normalizeResidencyLabel(row.residency);
      const drawPool = normalizeDrawPool(row.draw_pool);
      const huntCode = normalizeKey(row.hunt_code);
      const group = groupKey(row.hunt_code, residency, drawPool);
      state.referenceByKey.set(group, { ...row, residency, draw_pool: drawPool });
      if (huntCode && !state.referenceByCode.has(huntCode)) {
        state.referenceByCode.set(huntCode, { ...row, residency, draw_pool: drawPool });
      }
    });

    state.engineGroups.forEach((rows) => rows.sort((a, b) => (b.points ?? 0) - (a.points ?? 0)));
    state.ladderGroups.forEach((rows) => rows.sort((a, b) => (b.points ?? 0) - (a.points ?? 0)));
    state.loaded = true;
  }

  function buildFilters() {
    return {
      huntCode: normalizeKey(els.huntCodeInput.value),
      residency: getResidencyKey(),
      drawPool: getDrawPoolKey(),
      points: getCurrentPoints(),
    };
  }

  function findMeta(huntCode, residency, drawPool) {
    return state.masterByResidency.get(groupKey(huntCode, residency, drawPool))
      || state.masterByCode.get(normalizeKey(huntCode))
      || null;
  }

  function getEngineRow(huntCode, residency, points, drawPool) {
    return state.engineByKey.get(rowKey(huntCode, residency, points, drawPool)) || null;
  }

  function getLadderRows(huntCode, residency, drawPool) {
    return state.ladderGroups.get(groupKey(huntCode, residency, drawPool)) || [];
  }

  function getReferenceRow(huntCode, residency, drawPool) {
    return state.referenceByKey.get(groupKey(huntCode, residency, drawPool))
      || state.referenceByKey.get(groupKey(huntCode, residency, 'standard'))
      || state.referenceByCode.get(normalizeKey(huntCode))
      || null;
  }

  function getEngineRows(huntCode, residency, drawPool) {
    return state.engineGroups.get(groupKey(huntCode, residency, drawPool)) || [];
  }

  function getEngineGroupFallbackRow(huntCode, residency, drawPool) {
    const rows = getEngineRows(huntCode, residency, drawPool);
    return rows.length ? rows[0] : null;
  }

  function getModeledCoverageStatus(meta, hasEngineGroup) {
    if (hasEngineGroup) return '';
    if (!meta) return 'Hunt not found in the current production backbone.';
    return 'This hunt exists in the canonical hunt backbone, but it does not currently have modeled draw-pressure coverage.';
  }

  function getMlOddsCandidate(row) {
    return num(firstAvailable(row, ['ml_draw_probability_2026', 'ml_draw_prob_2026', 'ml_draw_probability_pct']));
  }

  function getMlConfidence(row) {
    return num(firstAvailable(row, ['ml_confidence', 'ml_confidence_score']));
  }

  function getDeterministicOddsCandidate(row) {
    if (!row) return null;
    const displayOddsPct = num(firstAvailable(row, ['display_odds_pct']));
    if (displayOddsPct !== null) return displayOddsPct;
    const pDrawMean = num(firstAvailable(row, ['p_draw_mean']));
    if (pDrawMean !== null) return toProbabilityPercent(pDrawMean);
    return num(firstAvailable(row, [
      'odds_2026_projected',
      'max_pool_projection_2026',
      'random_draw_odds_2026',
      'random_draw_projection_2026',
    ]));
  }

  function selectDrawOddsPercent(row) {
    if (!row) return { percent: null, source: 'unavailable' };

    const displayOddsPct = num(firstAvailable(row, ['display_odds_pct']));
    if (displayOddsPct !== null && displayOddsPct > 0) {
      return { percent: clamp(displayOddsPct, 0, 100), source: 'display_odds_pct' };
    }

    const zone = String(row?.point_pool_zone || '').trim();
    const maxPoolProjection = num(firstAvailable(row, ['max_pool_projection_2026']));
    const randomDrawOdds = num(firstAvailable(row, ['random_draw_odds_2026']));
    const randomDrawProjection = num(firstAvailable(row, ['random_draw_projection_2026']));
    const projectedOdds = num(firstAvailable(row, ['odds_2026_projected']));
    const pDrawMean = num(firstAvailable(row, ['p_draw_mean']));
    const pDrawMeanPct = pDrawMean !== null ? toProbabilityPercent(pDrawMean) : null;

    if ((zone === 'max_point_pool' || zone === 'max_pool_guaranteed' || zone === 'max_pool_cutoff_mixed')
      && maxPoolProjection !== null && maxPoolProjection > 0) {
      return { percent: clamp(maxPoolProjection, 0, 100), source: 'max_pool_projection_2026' };
    }

    if ((zone === 'random_pool' || zone === 'max_pool_cutoff_mixed') && randomDrawOdds !== null && randomDrawOdds > 0) {
      return { percent: clamp(randomDrawOdds, 0, 100), source: 'random_draw_odds_2026' };
    }
    if ((zone === 'random_pool' || zone === 'max_pool_cutoff_mixed') && randomDrawProjection !== null && randomDrawProjection > 0) {
      return { percent: clamp(randomDrawProjection, 0, 100), source: 'random_draw_projection_2026' };
    }

    if (pDrawMeanPct !== null && pDrawMeanPct > 0) {
      return {
        percent: clamp(pDrawMeanPct, 0, 100),
        source: 'p_draw_mean',
      };
    }

    if (projectedOdds !== null && projectedOdds > 0) return { percent: clamp(projectedOdds, 0, 100), source: 'odds_2026_projected' };
    if (maxPoolProjection !== null && maxPoolProjection > 0) return { percent: clamp(maxPoolProjection, 0, 100), source: 'max_pool_projection_2026' };
    if (randomDrawOdds !== null && randomDrawOdds > 0) return { percent: clamp(randomDrawOdds, 0, 100), source: 'random_draw_odds_2026' };
    if (randomDrawProjection !== null && randomDrawProjection > 0) return { percent: clamp(randomDrawProjection, 0, 100), source: 'random_draw_projection_2026' };

    // Fall back to zero-valued fields only when no non-zero modeled field exists.
    if (displayOddsPct !== null) return { percent: clamp(displayOddsPct, 0, 100), source: 'display_odds_pct' };
    if (pDrawMeanPct !== null) return { percent: clamp(pDrawMeanPct, 0, 100), source: 'p_draw_mean' };
    if (projectedOdds !== null) return { percent: clamp(projectedOdds, 0, 100), source: 'odds_2026_projected' };
    if (maxPoolProjection !== null) return { percent: clamp(maxPoolProjection, 0, 100), source: 'max_pool_projection_2026' };
    if (randomDrawOdds !== null) return { percent: clamp(randomDrawOdds, 0, 100), source: 'random_draw_odds_2026' };
    if (randomDrawProjection !== null) return { percent: clamp(randomDrawProjection, 0, 100), source: 'random_draw_projection_2026' };

    return { percent: null, source: 'unavailable' };
  }

  function selectPreferenceOddsPercent(row) {
    if (!row) return { percent: null, source: 'unavailable' };

    const displayOddsPct = num(firstAvailable(row, ['display_odds_pct']));
    if (displayOddsPct !== null && displayOddsPct > 0) return { percent: clamp(displayOddsPct, 0, 100), source: 'display_odds_pct' };

    const pDrawMean = num(firstAvailable(row, ['p_draw_mean']));
    const pDrawMeanPct = pDrawMean !== null ? toProbabilityPercent(pDrawMean) : null;
    if (pDrawMeanPct !== null && pDrawMeanPct > 0) {
      return { percent: clamp(pDrawMeanPct, 0, 100), source: 'p_draw_mean' };
    }

    const oddsProjected = num(firstAvailable(row, ['odds_2026_projected']));
    if (oddsProjected !== null && oddsProjected > 0) return { percent: clamp(oddsProjected, 0, 100), source: 'odds_2026_projected' };

    const preferenceSpecific = num(firstAvailable(row, [
      'preference_draw_odds_2026',
      'preference_projection_2026',
      'modeled_preference_probability',
      'draw_probability',
    ]));
    const preferenceSpecificPct = preferenceSpecific !== null ? toProbabilityPercent(preferenceSpecific) : null;
    if (preferenceSpecificPct !== null && preferenceSpecificPct > 0) {
      return { percent: clamp(preferenceSpecificPct, 0, 100), source: 'preference_specific' };
    }

    const p50 = num(firstAvailable(row, ['p50']));
    const p50Pct = p50 !== null ? toProbabilityPercent(p50) : null;
    if (p50Pct !== null && p50Pct > 0) return { percent: clamp(p50Pct, 0, 100), source: 'p50' };

    if (displayOddsPct !== null) return { percent: clamp(displayOddsPct, 0, 100), source: 'display_odds_pct' };
    if (pDrawMeanPct !== null) return { percent: clamp(pDrawMeanPct, 0, 100), source: 'p_draw_mean' };
    if (oddsProjected !== null) return { percent: clamp(oddsProjected, 0, 100), source: 'odds_2026_projected' };
    if (preferenceSpecificPct !== null) return { percent: clamp(preferenceSpecificPct, 0, 100), source: 'preference_specific' };
    if (p50Pct !== null) return { percent: clamp(p50Pct, 0, 100), source: 'p50' };

    return { percent: null, source: 'unavailable' };
  }

  function shouldUseMlHybridOdds(row) {
    if (!ML_OPTIONS?.enabled) return false;
    const mlOdds = getMlOddsCandidate(row);
    if (mlOdds === null) return false;

    const confidence = getMlConfidence(row);
    const minConfidence = num(ML_OPTIONS.useMlForOddsWhenConfidenceGte);
    if (confidence !== null && minConfidence !== null && confidence < minConfidence) return false;

    const baselineOdds = getDeterministicOddsCandidate(row);
    const maxDrift = num(ML_OPTIONS.maxDivergenceGuardPct);
    if (baselineOdds !== null && maxDrift !== null && Math.abs(mlOdds - baselineOdds) > maxDrift) return false;

    return true;
  }

  function selectModeOddsPercent(meta, row, referenceRow) {
    if (isPreferenceFamily(meta, row, referenceRow) || isYouthReserveFamily(meta, row, referenceRow)) {
      return selectPreferenceOddsPercent(row);
    }
    return selectDrawOddsPercent(row);
  }

  function getDisplayedOdds(meta, row, referenceRow) {
    const selectedOdds = selectModeOddsPercent(meta, row, referenceRow);
    return {
      value: formatOddsAsOneInOrPercent(selectedOdds.percent),
      source: selectedOdds.source,
      percent: selectedOdds.percent,
    };
  }

  function getDrawSystemType(meta, row, referenceRow) {
    return String(
      row?.draw_system_type
      || row?.draw_2026_system_type
      || row?.draw_system
      || referenceRow?.draw_system_type
      || referenceRow?.draw_2026_system_type
      || (String(row?.algorithm_status || '').trim().toUpperCase() === 'MODELED_PREFERENCE' ? 'PREFERENCE_INFERRED' : '')
      || (String(row?.algorithm_status || '').trim().toUpperCase() === 'MODELED_BONUS' ? 'BONUS_INFERRED' : '')
      || meta?.draw_system_type
      || meta?.draw_2026_system_type
      || meta?.draw_model_class
      || '',
    ).trim().toUpperCase();
  }

  function isPreferenceFamily(meta, row, referenceRow) {
    return getDrawSystemType(meta, row, referenceRow).startsWith('PREFERENCE_');
  }

  function isBonusFamily(meta, row, referenceRow) {
    return getDrawSystemType(meta, row, referenceRow).startsWith('BONUS_');
  }

  function isYouthReserveFamily(meta, row, referenceRow) {
    return [
      'YOUTH_GENERAL_DEER_RESERVE',
      'YOUTH_ANTLERLESS_OR_DOE_RESERVE',
      'YOUTH_DRAW_ONLY_ELK',
      'YOUTH_OTC_OR_AVAILABILITY',
    ].includes(getDrawSystemType(meta, row, referenceRow));
  }

  function isAllocationAvailabilityFamily(meta, row, referenceRow) {
    const drawSystemType = getDrawSystemType(meta, row, referenceRow);
    const status = String(row?.algorithm_status || '').trim().toUpperCase();
    return [
      'SPORTSMAN_PERMIT',
      'BEAR_DRAW',
      'MOUNTAIN_LION_DRAW',
      'PRIVATE_LANDS_ONLY_ANTLERLESS_ELK',
      'OTC_OR_REMAINING_TARGET',
      'RANDOM_ONLY_TARGET',
    ].includes(drawSystemType)
      || ['MODELED_AVAILABILITY', 'MODELED_ALLOCATION', 'MODELED_SPORTSMAN_DRAW'].includes(status);
  }

  function detectLadderMode(meta, rows, referenceRow) {
    const firstRow = (rows && rows.length) ? rows[0] : null;
    if (isPreferenceFamily(meta, firstRow, referenceRow)) return DRAW_MODE.PREFERENCE;
    if (isBonusFamily(meta, firstRow, referenceRow)) return DRAW_MODE.BONUS;
    if (isYouthReserveFamily(meta, firstRow, referenceRow)) return DRAW_MODE.YOUTH_RESERVE;
    if (isAllocationAvailabilityFamily(meta, firstRow, referenceRow)) return DRAW_MODE.ALLOCATION_AVAILABILITY;

    // Fallback when ladder rows are sparse/legacy and draw_system_type is blank.
    const refType = String(
      referenceRow?.draw_system_type
      || referenceRow?.draw_2026_system_type
      || meta?.draw_system_type
      || meta?.draw_2026_system_type
      || '',
    ).trim().toUpperCase();
    if (refType.startsWith('PREFERENCE_')) return DRAW_MODE.PREFERENCE;
    if (refType.startsWith('BONUS_')) return DRAW_MODE.BONUS;

    const permitStatus = String(referenceRow?.permit_status || meta?.permit_status || '').trim().toUpperCase();
    const huntType = String(referenceRow?.hunt_type || meta?.hunt_type || '').trim().toLowerCase();
    const species = String(referenceRow?.species || meta?.species || '').trim().toLowerCase();
    if (permitStatus === 'TOTAL_ONLY' && huntType.includes('general season') && species.includes('deer')) {
      return DRAW_MODE.PREFERENCE;
    }
    return DRAW_MODE.STATUS_ONLY;
  }

  function getRecommendation(meta, row, referenceRow) {
    if (!row) {
      return 'No modeled point-level row is available yet. Use Sources to verify historical draw pages and compare nearby point rows while this hunt is being rebuilt into the modeled ladder.';
    }

    if (isRandomOnlyBonusCase(meta, row, referenceRow)) {
      return 'This hunt has no meaningful max-pool path at this residency. Your outcome depends on weighted random draw only.';
    }

    if (isPreferenceFamily(meta, row, referenceRow)) {
      const selectedOdds = selectPreferenceOddsPercent(row);
      if ((selectedOdds.percent !== null && selectedOdds.percent >= 99.9) || num(row.gap) === 0) {
        return 'This hunt is currently inside the preference-point line at your selected point level.';
      }
      if (row.draw_outlook === 'POINT CREEP DEFEAT') {
        return 'The preference line is moving away faster than your point gain. This is not a realistic catch-up hunt.';
      }
      if (row.draw_outlook === 'MAY DRAW IN 5-10 YEARS') {
        return 'You are still behind the preference line, but the hunt remains potentially catchable if pressure stabilizes.';
      }
      return 'You are below the current preference line and need the line to soften or more permits to appear.';
    }

    switch (row.draw_outlook) {
      case 'GREEN LIGHT':
        return 'This hunt is currently inside the max-point pool at your selected point level.';
      case 'POINT CREEP DEFEAT':
        return 'The guaranteed line is moving away faster than your point gain. This is not a realistic catch-up hunt.';
      case 'MAY DRAW IN 5-10 YEARS':
        return 'You are still behind the line, but the hunt remains potentially catchable if trend pressure stabilizes.';
      default:
        return 'You are outside the guaranteed line and relying on the remaining random pool.';
    }
  }

  function getPrimaryOddsLabel(meta, row, displayedOdds, referenceRow) {
    if (displayedOdds.source === 'ml_hybrid') {
      const confidence = displayedOdds.confidence === null ? null : Number(displayedOdds.confidence);
      const confidenceLabel = Number.isFinite(confidence) ? ` (conf ${confidence.toFixed(2)})` : '';
      return `2026 ML Hybrid Draw: ${displayedOdds.value}${confidenceLabel}`;
    }
    if (isPreferenceFamily(meta, row, referenceRow)) {
      return `2026 Preference Draw: ${displayedOdds.value}`;
    }
    if (isRandomOnlyBonusCase(meta, row, referenceRow)) {
      return `2026 Random Draw: ${displayedOdds.value}`;
    }
    return `2026 Random Draw: ${displayedOdds.value}`;
  }

  function getOutlookSignal(meta, row, referenceRow) {
    const guaranteedProbability = getGuaranteedProbability(row);
    if (guaranteedProbability !== null && guaranteedProbability >= 0.999) return 'green';

    const selectedOdds = selectModeOddsPercent(meta, row, referenceRow);
    if (selectedOdds.percent !== null) {
      if (selectedOdds.percent >= 99.9) return 'green';
      if (selectedOdds.percent >= 25) return 'yellow';
      return 'red';
    }

    const maxPointPermits = num(row?.max_point_permits_2026);
    if (maxPointPermits !== null && maxPointPermits <= 0) return 'red';

    const nonresidentPermits = num(meta?.public_nonresident_permits);
    const residentPermits = num(meta?.public_resident_permits);

    if ((nonresidentPermits !== null || residentPermits !== null) && maxPointPermits === 0) return 'red';
    if (row?.draw_outlook === 'MAY DRAW IN 5-10 YEARS' || num(row?.gap) === 1) return 'yellow';
    if (row?.draw_outlook === 'GREEN LIGHT') return 'green';

    return 'red';
  }

  function renderOutlookLight(signal) {
    if (!els.selectedOutlook) return;
    const active = signal || 'red';
    const labels = {
      red: 'Long Shot / Not Catchable',
      yellow: 'On the Line / Watch Closely',
      green: 'In Reach / Strong',
    };
    els.selectedOutlook.innerHTML = `
      <span class="outlook-light red${active === 'red' ? ' is-active' : ''}" aria-hidden="true"></span>
      <span class="outlook-light yellow${active === 'yellow' ? ' is-active' : ''}" aria-hidden="true"></span>
      <span class="outlook-light green${active === 'green' ? ' is-active' : ''}" aria-hidden="true"></span>
    `;
    els.selectedOutlook.setAttribute('aria-label', `${labels[active] || labels.red} draw outlook`);
    if (els.selectedOutlookText) els.selectedOutlookText.textContent = labels[active] || labels.red;
  }

  function getTrendSignal(row) {
    const trend = String(row?.trend || '').trim().toUpperCase();
    if (trend === 'GREEN') return 'green';
    if (trend === 'YELLOW') return 'yellow';
    return 'red';
  }

  function renderTrendLight(signal) {
    if (!els.summaryTrend) return;
    const active = signal || 'red';
    els.summaryTrend.innerHTML = `
      <span class="outlook-light red${active === 'red' ? ' is-active' : ''}" aria-hidden="true"></span>
      <span class="outlook-light yellow${active === 'yellow' ? ' is-active' : ''}" aria-hidden="true"></span>
      <span class="outlook-light green${active === 'green' ? ' is-active' : ''}" aria-hidden="true"></span>
    `;
    els.summaryTrend.setAttribute('aria-label', `${active} trend`);
  }

  function getTrendLabelText(trendValue) {
    const trend = String(trendValue || '').trim().toUpperCase();
    if (trend === 'GREEN') return 'In Reach / Strong';
    if (trend === 'YELLOW') return 'On the Line / Watch Closely';
    if (trend === 'RED') return 'Long Shot / Not Catchable';
    return 'Not available';
  }

  function setLadderHeaders(mode) {
    if (!els.ladderHeaderCol1 || !els.ladderHeaderCol2 || !els.ladderHeaderCol3 || !els.ladderHeaderCol4 || !els.ladderHeaderCol5) return;
    const headersByMode = {
      [DRAW_MODE.PREFERENCE]: ['Points', '2025 Draw Results', '2026 Draw Odds', 'Point Status', 'Notes'],
      [DRAW_MODE.BONUS]: [
        'Points',
        '2025 Draw Results',
        { label: '2026 Max Point Draw', sublabel: '50% of Tags' },
        { label: '2026 Random Draw', sublabel: '50% of Tags' },
        'Notes',
      ],
      [DRAW_MODE.YOUTH_RESERVE]: ['Points', '2025 Draw Results', '2026 Youth Reserve', '2026 Rollover', 'Notes'],
      [DRAW_MODE.ALLOCATION_AVAILABILITY]: ['Status', 'Permit Availability', '2026 Allocation', 'Rule / Source', 'Notes'],
      [DRAW_MODE.STATUS_ONLY]: ['Points', '2025 Draw Results', '2026 Status', 'Estimated Odds', 'Notes'],
    };
    const headers = headersByMode[mode] || headersByMode[DRAW_MODE.STATUS_ONLY];
    [
      els.ladderHeaderCol1,
      els.ladderHeaderCol2,
      els.ladderHeaderCol3,
      els.ladderHeaderCol4,
      els.ladderHeaderCol5,
    ].forEach((cell, index) => {
      const header = headers[index];
      if (typeof header === 'string') {
        cell.textContent = header;
        return;
      }
      cell.innerHTML = `
        <span class="ladder-header-main">${escapeHtml(header.label)}</span>
        <span class="ladder-header-subline">${escapeHtml(header.sublabel)}</span>
      `;
    });
  }

  function getDrawPoolPositionLabel(meta, row, referenceRow) {
    if (!row) return 'No modeled point row is loaded yet.';
    if (isPreferenceFamily(meta, row, referenceRow)) {
      const gap = num(row.gap);
      if (gap !== null && gap <= 0) return 'Inside the preference line.';
      return 'Below the preference line.';
    }
    const zone = String(row.point_pool_zone || '').trim();
    if (zone === 'max_point_pool' || zone === 'max_pool_guaranteed') return 'In the max-point pool.';
    if (zone === 'max_pool_cutoff_mixed') return 'On the max-point cutoff line; some applicants at this point level may spill into random.';
    if (zone === 'random_pool') return 'In the random pool.';
    if (isRandomOnlyBonusCase(meta, row, referenceRow)) return 'Random draw only.';
    return 'Draw pool not classified yet.';
  }

  function getCatchTrainSummary(meta, row, filters, referenceRow) {
    if (!row) return 'No row is modeled yet, so we cannot tell if this train is catchable.';
    const selectedOdds = selectModeOddsPercent(meta, row, referenceRow);
    const gap = num(row.gap);
    const trend = String(row.trend || '').trim().toUpperCase();
    if (selectedOdds.percent !== null && selectedOdds.percent >= 99.9) {
      return `Yes. At ${formatInteger(filters.points)} points, this is effectively at the line now.`;
    }
    if (gap !== null && gap <= 0) {
      return `Yes. You are ${Math.abs(gap)} point${Math.abs(gap) === 1 ? '' : 's'} above the modeled line.`;
    }
    if (row.draw_outlook === 'POINT CREEP DEFEAT' || trend === 'RED') {
      return 'Not under the current trend. The line is moving faster than a normal one-point-per-year climb.';
    }
    if (row.draw_outlook === 'MAY DRAW IN 5-10 YEARS' || trend === 'YELLOW') {
      return 'Maybe. You are still behind, but the line is close enough to watch instead of writing it off.';
    }
    if (isRandomOnlyBonusCase(meta, row, referenceRow)) {
      return 'No guaranteed train to catch here. This one is about weighted random chance.';
    }
    return 'Possible, but the model needs more history before calling it a confident catch-up hunt.';
  }

  function getPlainFormulaText(meta, row, referenceRow) {
    if (!row) return 'We need a modeled point row before the formula can be explained for this hunt.';
    if (isPreferenceFamily(meta, row, referenceRow)) {
      return 'Preference-style logic is mostly line math: compare your points to the last modeled draw line, then adjust for permit change and point creep.';
    }
    if (isRandomOnlyBonusCase(meta, row, referenceRow)) {
      return 'Random-only logic uses the remaining random permits and the applicant stack at this point level. More points can help weight, but they do not create a guaranteed line.';
    }
    return 'Bonus-style logic separates the max-point pool from the random pool. First we test whether your points reach the guaranteed line; if not, your odds come from the random pool.';
  }

  function getPointCreepDisplay(row) {
    if (!row) return 'Not available';
    const parts = [];
    if (hasMeaningfulValue(row.trend)) parts.push(`Trend: ${row.trend}`);
    if (hasMeaningfulValue(row.gap)) parts.push(formatGapStatus(row.gap));
    if (hasMeaningfulValue(row.delta_gap)) parts.push(`Gap change: ${row.delta_gap}`);
    if (hasMeaningfulValue(row.draw_outlook)) parts.push(row.draw_outlook);
    return parts.length ? parts.join(' | ') : 'Not available';
  }

  function renderFilterReadout(filters) {
    const parts = filters.huntCode
      ? [filters.huntCode, filters.residency]
      : [filters.residency];
    const poolLabel = getDrawPoolHandoffLabel(filters.drawPool);
    if (poolLabel) parts.push(poolLabel);
    parts.push(`${filters.points} point${filters.points === 1 ? '' : 's'}`);
    els.filterReadout.textContent = `${parts.join(' | ')}.`;

    els.plannerReadout.textContent = state.selectedHuntCode
      ? `Hunt Builder handoff active: ${state.selectedHuntCode}.`
      : 'Hunt Builder handoff ready.';
  }

  function getHarvestSuccessDisplay(meta, referenceRow, row) {
    const fromRow = firstAvailable(row, ['harvest_success_percent_2025', 'success_percent', 'percent_success', 'prior_year_success_rate']);
    if (fromRow !== null) {
      const pct = num(fromRow);
      if (pct !== null) {
        const normalized = pct <= 1 ? pct * 100 : pct;
        return `${Number(normalized.toFixed(1)).toString()}%`;
      }
      return String(fromRow);
    }
    if (referenceRow?.harvest_success_percent_2025 !== undefined && referenceRow?.harvest_success_percent_2025 !== null && String(referenceRow.harvest_success_percent_2025).trim() !== '') {
      return `${referenceRow.harvest_success_percent_2025}%`;
    }
    if (meta?.success_percent !== undefined && meta?.success_percent !== null && String(meta.success_percent).trim() !== '') {
      return `${meta.success_percent}%`;
    }
    return 'Not available';
  }

  function getResidentPermitsDisplay(meta, referenceRow) {
    const total = firstAvailable(referenceRow, ['permits_2026_total', 'permit_allotment_2026_total', 'public_permits_2026'])
      || firstAvailable(meta, ['permits_2026_total', 'permit_allotment_2026_total', 'public_permits_2026']);
    const permitStatus = String(referenceRow?.permit_status || meta?.permit_status || '').trim().toUpperCase();
    if (permitStatus === 'TOTAL_ONLY' && total) {
      return `${total} total`;
    }
    const resident = firstAvailable(referenceRow, ['permits_2026_res'])
      || firstAvailable(meta, ['public_resident_permits', 'permits_2026_res', 'permit_allotment_2026_res']);
    if (resident) return resident;
    return total ? `${total} total` : 'Not available';
  }

  function getNonresidentPermitsDisplay(meta, referenceRow) {
    const total = firstAvailable(referenceRow, ['permits_2026_total', 'permit_allotment_2026_total', 'public_permits_2026'])
      || firstAvailable(meta, ['permits_2026_total', 'permit_allotment_2026_total', 'public_permits_2026']);
    const permitStatus = String(referenceRow?.permit_status || meta?.permit_status || '').trim().toUpperCase();
    if (permitStatus === 'TOTAL_ONLY' && total) {
      return `${total} total`;
    }
    const nonresident = firstAvailable(referenceRow, ['permits_2026_nr'])
      || firstAvailable(meta, ['public_nonresident_permits', 'permits_2026_nr', 'permit_allotment_2026_nr']);
    if (nonresident) return nonresident;
    return total ? `${total} total` : 'Not available';
  }

  function getVerdictState(meta, row, filters, coverageMessage, referenceRow) {
    if (!row) {
      return {
        badge: 'Not available',
        message: coverageMessage || 'No modeled row available for this hunt and residency yet.',
        className: 'is-red',
      };
    }

    if (isOutOfScopeNonTargetRow(row)) {
      return {
        badge: 'Out of scope',
        message: getOutOfScopeAuditLabel(),
        className: 'is-red',
      };
    }

    if (isRandomOnlyBonusCase(meta, row, referenceRow)) {
      return {
        badge: 'Random Chance Only',
        message: 'This hunt does not currently offer a meaningful guaranteed path at this residency. Your outcome depends on the random draw only.',
        className: 'is-red',
      };
    }

    const guaranteedProbability = getGuaranteedProbability(row);
    if (guaranteedProbability !== null && guaranteedProbability >= 0.999) {
      return {
        badge: 'Guaranteed',
        message: `At ${formatInteger(filters.points)} points, this hunt is analytically or modeled as guaranteed.`,
        className: 'is-green',
      };
    }

    const selectedOdds = selectModeOddsPercent(meta, row, referenceRow);
    if (selectedOdds.percent !== null) {
      if (selectedOdds.percent >= 99.9) {
        return {
          badge: 'Guaranteed',
          message: `At ${formatInteger(filters.points)} points, the selected draw-odds field is effectively 100%.`,
          className: 'is-green',
        };
      }
      if (selectedOdds.percent >= 90) {
        return {
          badge: 'Very likely',
          message: 'This hunt is very likely to draw at your selected point level.',
          className: 'is-green',
        };
      }
      if (selectedOdds.percent >= 25) {
        return {
          badge: 'On the Line',
          message: 'You are near the modeled line. Pressure and point creep still matter.',
          className: 'is-yellow',
        };
      }
      if (selectedOdds.percent > 0) {
        return {
          badge: 'Random / Long-shot Chance',
          message: 'This hunt still has some modeled draw chance, but it is a long shot.',
          className: 'is-red',
        };
      }
      return {
        badge: 'Not Catchable Right Now',
        message: 'The modeled draw probability is currently zero at this point level.',
        className: 'is-red',
      };
    }

    if (row.draw_outlook === 'MAY DRAW IN 5-10 YEARS' || num(row.gap) === 1) {
      return {
        badge: 'On the Line',
        message: 'You are near the edge of the guaranteed path. This hunt is still in reach, but pressure and point creep matter.',
        className: 'is-yellow',
      };
    }

    if (row.draw_outlook === 'POINT CREEP DEFEAT') {
      return {
        badge: 'Not Catchable Right Now',
        message: 'Point creep is outrunning your yearly gain. This is not a realistic catch-up hunt under the current trend.',
        className: 'is-red',
      };
    }

    return {
      badge: 'Random Chance Only',
      message: 'You are outside the guaranteed line and relying on the remaining random pool.',
      className: 'is-red',
    };
  }

  function renderVerdict(meta, row, filters, coverageMessage, referenceRow) {
    if (!els.verdictBadge || !els.verdictMessage) return;

    const verdict = getVerdictState(meta, row, filters, coverageMessage, referenceRow);
    els.verdictBadge.className = `verdict-badge ${verdict.className}`;
    els.verdictBadge.textContent = verdict.badge;
    els.verdictMessage.textContent = verdict.message;
  }

  function getGuaranteedLinePointForDisplay(meta, row, filters) {
    const ladderRows = getLadderRows(filters.huntCode, filters.residency, filters.drawPool);
    const referenceRow = getReferenceRow(filters.huntCode, filters.residency, filters.drawPool);
    const mode = detectLadderMode(meta, ladderRows, referenceRow);
    return getGuaranteedLinePoint(row, ladderRows, mode);
  }

  function renderTopSummary(meta, row, filters, displayedOdds, referenceRow) {
    const guaranteedLinePoint = row ? getGuaranteedLinePointForDisplay(meta, row, filters) : null;
    if (els.summaryGuaranteedTop) {
      els.summaryGuaranteedTop.textContent = row
        ? (isRandomOnlyBonusCase(meta, row, referenceRow) ? 'Not applicable' : (guaranteedLinePoint === null ? 'Not available pts' : `${formatInteger(guaranteedLinePoint)} pts`))
        : 'Not available';
    }

    if (els.summaryPointsTop) {
      els.summaryPointsTop.textContent = `${formatInteger(filters.points)} pts`;
    }

    if (els.summaryOddsTop) {
      els.summaryOddsTop.textContent = row ? displayedOdds.value : 'Not available';
    }

    if (els.selectedHuntCodeRead) {
      els.selectedHuntCodeRead.textContent = meta?.hunt_code || filters.huntCode || 'Not available';
    }
  }

  function renderSummary(meta, row, filters, coverageMessage, referenceRow) {
    const displayedOdds = getDisplayedOdds(meta, row, referenceRow);

    renderVerdict(meta, row, filters, coverageMessage, referenceRow);
    renderTopSummary(meta, row, filters, displayedOdds, referenceRow);

    if (!row) {
      renderOutlookLight('red');
      if (els.summaryGuaranteed) els.summaryGuaranteed.textContent = 'Not available';
      if (els.summaryPoints) els.summaryPoints.textContent = `${formatInteger(filters.points)} pts`;
      if (els.summaryStatus) els.summaryStatus.textContent = coverageMessage || 'No modeled row available.';
      if (els.summaryOdds) els.summaryOdds.textContent = 'Not available';
      renderTrendLight('red');
      if (els.summaryTrendText) els.summaryTrendText.textContent = 'Not available';
      if (els.summaryRecommendation) els.summaryRecommendation.textContent = coverageMessage || 'Recommendation not available.';

      if (els.selectedResidentPermits) {
        els.selectedResidentPermits.textContent = getResidentPermitsDisplay(meta, referenceRow);
      }
      if (els.selectedNonresidentPermits) {
        els.selectedNonresidentPermits.textContent = getNonresidentPermitsDisplay(meta, referenceRow);
      }
      if (els.selectedHarvestSuccess) {
        els.selectedHarvestSuccess.textContent = getHarvestSuccessDisplay(meta, referenceRow, row);
      }
      return;
    }

    if (isOutOfScopeNonTargetRow(row)) {
      renderOutlookLight('red');
      if (els.summaryGuaranteed) els.summaryGuaranteed.textContent = 'Not applicable';
      if (els.summaryPoints) els.summaryPoints.textContent = `${formatInteger(filters.points)} pts`;
      if (els.summaryStatus) els.summaryStatus.textContent = getOutOfScopeAuditLabel();
      if (els.summaryOdds) els.summaryOdds.textContent = 'Not available';
      renderTrendLight('red');
      if (els.summaryTrendText) els.summaryTrendText.textContent = getOutOfScopeAuditLabel();
      if (els.summaryRecommendation) els.summaryRecommendation.textContent = getOutOfScopeAuditLabel();

      if (els.selectedResidentPermits) {
        els.selectedResidentPermits.textContent = getResidentPermitsDisplay(meta, referenceRow);
      }

      if (els.selectedNonresidentPermits) {
        els.selectedNonresidentPermits.textContent = getNonresidentPermitsDisplay(meta, referenceRow);
      }

      if (els.selectedHarvestSuccess) {
        els.selectedHarvestSuccess.textContent = getHarvestSuccessDisplay(meta, referenceRow, row);
      }
      return;
    }

    renderOutlookLight(getOutlookSignal(meta, row, referenceRow));
    const guaranteedLinePoint = getGuaranteedLinePointForDisplay(meta, row, filters);

    if (els.summaryGuaranteed) {
      els.summaryGuaranteed.textContent = isRandomOnlyBonusCase(meta, row, referenceRow)
        ? 'Not applicable'
        : (guaranteedLinePoint === null ? 'Not available pts' : `${formatInteger(guaranteedLinePoint)} pts`);
    }

    if (els.summaryPoints) {
      els.summaryPoints.textContent = `${formatInteger(filters.points)} pts`;
    }

    if (els.summaryStatus) {
      els.summaryStatus.textContent = isRandomOnlyBonusCase(meta, row, referenceRow)
        ? 'Random draw only'
        : formatGapStatus(row.gap);
    }

    if (els.summaryOdds) {
      els.summaryOdds.textContent = getPrimaryOddsLabel(meta, row, displayedOdds, referenceRow);
    }

    renderTrendLight(getTrendSignal(row));

    if (els.summaryTrendText) {
      els.summaryTrendText.textContent = isRandomOnlyBonusCase(meta, row, referenceRow)
        ? 'Not applicable'
        : getTrendLabelText(row.trend);
    }

    if (els.summaryRecommendation) {
      els.summaryRecommendation.textContent = getRecommendation(meta, row, referenceRow);
    }

    if (els.selectedResidentPermits) {
      els.selectedResidentPermits.textContent = getResidentPermitsDisplay(meta, referenceRow);
    }

    if (els.selectedNonresidentPermits) {
      els.selectedNonresidentPermits.textContent = getNonresidentPermitsDisplay(meta, referenceRow);
    }

    if (els.selectedHarvestSuccess) {
      els.selectedHarvestSuccess.textContent = getHarvestSuccessDisplay(meta, referenceRow, row);
    }
  }

  function hasMeaningfulValue(value) {
    const text = String(value ?? '').trim();
    return !!text && text.toUpperCase() !== 'N/A' && text.toUpperCase() !== 'NOT AVAILABLE';
  }

  function hasSourceData(meta, row, referenceRow) {
    if (referenceRow) return true;
    if (!meta || !row) return false;
    return [
      row.odds_2025_actual,
      meta.success_percent,
      meta.success_hunters,
      meta.success_harvest,
      meta.public_permits_2025,
      meta.public_permits_2026,
    ].some(hasMeaningfulValue);
  }

  function buildSourceBoxes(meta, row, referenceRow) {
    const quotaSourceStatus = String(row?.quota_source_status || referenceRow?.quota_source_status || '').trim();
    const quotaSourceDisplay = quotaSourceStatus
      ? `2026 quota source: ${quotaSourceStatus}`
      : '2026 quota source: Not available';
    const boxes = [
      ['2025 Draw Results', formatHistoricalDrawResult(row)
        || (Number.isFinite(num(row?.odds_2025_actual))
          ? formatOddsAsOneInOrPercent(row?.odds_2025_actual)
          : (row?.odds_2025_actual || ''))],
      ['2026 Draw Odds', getDisplayedOdds(meta, row, referenceRow).value],
      ['2026 Quota Source', quotaSourceDisplay],
      ['2025 Harvest Success', hasMeaningfulValue(referenceRow?.harvest_success_percent_2025)
        ? `${referenceRow.harvest_success_percent_2025}%`
        : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}%` : 'Not available')],
      ['Harvest / Hunters', hasMeaningfulValue(referenceRow?.harvest_2025) || hasMeaningfulValue(referenceRow?.harvest_hunters_2025)
        ? `${referenceRow?.harvest_2025 || '0'} / ${referenceRow?.harvest_hunters_2025 || '0'}`
        : (hasMeaningfulValue(meta?.success_harvest) || hasMeaningfulValue(meta?.success_hunters)
          ? `${meta?.success_harvest || '0'} / ${meta?.success_hunters || '0'}`
          : 'Not available')],
      ['2025 Public Permits', referenceRow?.permits_2025_total || meta?.public_permits_2025 || 'Not available'],
      ['2026 Public Permits', referenceRow?.permits_2026_total || meta?.public_permits_2026 || 'Not available'],
      ['Odds Source', referenceRow?.has_bg_odds_page === 'TRUE'
        ? `Big Game Odds p. ${referenceRow.bg_odds_printed_page || referenceRow.bg_odds_pdf_page_index || ''}`.trim()
        : (referenceRow?.has_antlerless_odds_page === 'TRUE'
          ? `Antlerless Odds row ${referenceRow.antlerless_odds_row_start || ''}`.trim()
          : 'Not available')],
      ['RAC Source', hasMeaningfulValue(referenceRow?.rac_page)
        ? `${referenceRow?.source_pdf || 'RAC packet'} p. ${referenceRow.rac_page}`
        : 'Not available'],
    ];

    return boxes.map(([label, value]) => `
      <section class="source-box">
        <span class="label">${escapeHtml(label)}</span>
        <strong class="value">${escapeHtml(value)}</strong>
      </section>
    `).join('');
  }

  function getHarvestSnapshot(meta, referenceRow) {
    const success = hasMeaningfulValue(referenceRow?.harvest_success_percent_2025)
      ? `${referenceRow.harvest_success_percent_2025}% success`
      : (hasMeaningfulValue(meta?.success_percent) ? `${meta.success_percent}% success` : '');
    const harvestCount = hasMeaningfulValue(referenceRow?.harvest_2025) || hasMeaningfulValue(referenceRow?.harvest_hunters_2025)
      ? `${referenceRow?.harvest_2025 || '0'} harvest / ${referenceRow?.harvest_hunters_2025 || '0'} hunters`
      : (hasMeaningfulValue(meta?.success_harvest) || hasMeaningfulValue(meta?.success_hunters)
        ? `${meta?.success_harvest || '0'} harvest / ${meta?.success_hunters || '0'} hunters`
        : '');
    const days = hasMeaningfulValue(referenceRow?.harvest_average_days_2025)
      ? `${referenceRow.harvest_average_days_2025} avg days`
      : '';
    const satisfaction = hasMeaningfulValue(referenceRow?.harvest_satisfaction_2025)
      ? `${referenceRow.harvest_satisfaction_2025} satisfaction`
      : '';
    const parts = [success, harvestCount, days, satisfaction].filter(Boolean);
    return parts.length ? parts.join(' | ') : 'Harvest data is not mapped to this hunt row yet.';
  }

  function buildDecisionBoxes(meta, row, referenceRow, filters) {
    const displayedOdds = getDisplayedOdds(meta, row, referenceRow);
    const maxPoolDisplay = getMaxPointPoolDisplay(row) || 'Not currently a max-pool row.';
    const randomDisplay = getRandomDrawDisplay(row) || (isRandomOnlyBonusCase(meta, row, referenceRow) ? displayedOdds.value : 'Not currently a random-pool row.');
    const boxes = [
      ['Your Points Draw Odds', row ? displayedOdds.value : 'Not available'],
      ['Your Draw Pool', getDrawPoolPositionLabel(meta, row, referenceRow)],
      ['Can You Catch The Train?', getCatchTrainSummary(meta, row, filters, referenceRow)],
      ['Point Creep Readout', getPointCreepDisplay(row)],
      ['Max Point Pool', maxPoolDisplay],
      ['Random Pool', randomDisplay],
      ['Last Draw Result', formatHistoricalDrawResult(row) || 'Not available'],
      ['Permit Context', `${referenceRow?.permits_2026_total || meta?.public_permits_2026 || 'Not available'} total public permits in 2026`],
      ['Harvest Snapshot', getHarvestSnapshot(meta, referenceRow)],
      ['Plain-English Formula', getPlainFormulaText(meta, row, referenceRow), 'is-wide'],
      ['What I Would Do With This', getRecommendation(meta, row, referenceRow), 'is-wide'],
    ];

    return boxes.map(([label, value, className]) => `
      <section class="source-box ${escapeHtml(className || '')}">
        <span class="label">${escapeHtml(label)}</span>
        <strong class="value">${escapeHtml(value)}</strong>
      </section>
    `).join('');
  }

  function openSourceModal(meta, row, referenceRow, residency) {
    if (!els.sourceModal || !els.sourceModalGrid || !els.sourceModalTitle || !els.sourceModalSubtitle) return;
    const pointLabel = formatInteger(row?.points);
    const filters = state.selectedFilters || buildFilters();
    els.sourceModalTitle.textContent = 'Hunt Data Snapshot';
    els.sourceModalSubtitle.textContent = `${meta?.hunt_code || ''} | ${meta?.hunt_name || ''} | ${residency || ''} | ${pointLabel} points`;
    els.sourceModalGrid.innerHTML = `
      <p class="source-plain-note">This is the quick interpretation layer: where your points sit, whether you are in the max-point or random pool, what point creep is doing, and what the harvest row says when mapped.</p>
      ${buildDecisionBoxes(meta, row, referenceRow, filters)}
    `;
    els.sourceModal.hidden = false;
    document.body.classList.add('modal-open');
  }

  function closeSourceModal() {
    if (!els.sourceModal) return;
    els.sourceModal.hidden = true;
    document.body.classList.remove('modal-open');
  }

  function strictNum(value) {
    const text = String(value ?? '').trim();
    if (!text || !/[0-9]/.test(text)) return null;
    const parsed = Number(text.replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function firstNumericValue(sources, keys) {
    for (const source of sources) {
      for (const key of keys) {
        const parsed = strictNum(source?.[key]);
        if (parsed !== null) return parsed;
      }
    }
    return null;
  }

  function formatCompactNumber(value) {
    const parsed = strictNum(value);
    if (parsed === null) return '';
    if (Number.isInteger(parsed)) return parsed.toLocaleString();
    return Number(parsed.toFixed(1)).toString();
  }

  function formatMetricPercent(value) {
    const parsed = strictNum(value);
    if (parsed === null) return '';
    const normalized = parsed <= 1 ? parsed * 100 : parsed;
    return `${Number(normalized.toFixed(1)).toString()}%`;
  }

  function getPermitSummaryLine(row, referenceRow, meta) {
    const sources = [row, referenceRow, meta];
    const resident = firstNumericValue(sources, ['permits_2026_res', 'permit_allotment_2026_res', 'public_resident_permits']);
    const nonresident = firstNumericValue(sources, ['permits_2026_nr', 'permit_allotment_2026_nr', 'public_nonresident_permits']);
    const publishedTotal = firstNumericValue(sources, ['permits_2026_total', 'permit_allotment_2026_total', 'public_permits_2026']);
    const computedTotal = resident !== null || nonresident !== null ? (resident || 0) + (nonresident || 0) : null;
    const total = publishedTotal !== null ? publishedTotal : computedTotal;
    if (resident === null && nonresident === null && total === null) return '';
    if (resident !== null || nonresident !== null) {
      return `Permits: ${(resident ?? 0).toLocaleString()} R / ${(nonresident ?? 0).toLocaleString()} NR / ${(total ?? ((resident ?? 0) + (nonresident ?? 0))).toLocaleString()} Total`;
    }
    return total !== null ? `Permits: ${total.toLocaleString()} Total` : '';
  }

  function getLadderHarvestSnapshotLine(row, referenceRow, meta) {
    const sources = [row, referenceRow, meta];
    const success = firstAvailable(row, ['harvest_success_percent_2025', 'success_percent', 'percent_success', 'prior_year_success_rate'])
      || firstAvailable(referenceRow, ['harvest_success_percent_2025', 'success_percent', 'percent_success', 'prior_year_success_rate'])
      || firstAvailable(meta, ['harvest_success_percent_2025', 'success_percent', 'percent_success', 'prior_year_success_rate']);
    const days = firstNumericValue(sources, ['harvest_average_days_2025', 'average_days_hunted', 'avg_days_hunted', 'average_days_hunted_2025']);
    const averageAge = firstNumericValue(sources, ['average_harvest_age']);
    const currentAge = firstNumericValue(sources, ['current_age_3yr_average']);
    const successText = formatMetricPercent(success);
    if (!successText && (days === null || days <= 0) && (averageAge === null || averageAge <= 0) && (currentAge === null || currentAge <= 0)) {
      return '';
    }
    const summaryParts = [];
    if (successText) summaryParts.push(`${successText} success`);
    if (days !== null && days > 0) summaryParts.push(`${formatCompactNumber(days)} avg days`);
    if (averageAge !== null && averageAge > 0) {
      summaryParts.push(`${formatCompactNumber(averageAge)} avg age`);
    } else if (currentAge !== null && currentAge > 0) {
      summaryParts.push(`${formatCompactNumber(currentAge)} 3-yr age`);
    }
    return summaryParts.length ? `Harvest: ${summaryParts.join(' / ')}` : '';
  }

  function getPointCreepRiskLine(row) {
    const trend = String(row?.trend || '').trim().toUpperCase();
    const outlook = String(row?.draw_outlook || '').trim().toUpperCase();
    if (outlook.includes('POINT CREEP') || trend === 'RED' || trend === 'YELLOW') return 'Point Creep Risk';
    return '';
  }

  function getPoolMarkerLine(row) {
    const zone = String(row?.point_pool_zone || '').trim();
    if (zone === 'random_pool') return 'Random Pool';
    if (['max_point_pool', 'max_pool_guaranteed', 'max_pool_cutoff_mixed'].includes(zone)) return 'Max Pool';
    return '';
  }

  function isLowValueLadderNote(value) {
    const text = String(value ?? '').trim().toUpperCase();
    return !text || ['GREEN', 'YELLOW', 'RED', 'NOT AVAILABLE', 'N/A'].includes(text);
  }

  function buildLadderNoteLines({ meta, row, referenceRow, rows, mode, isUserRow, isGuaranteedLine, cells, userPoints }) {
    const lines = [];
    const rowPoint = strictNum(row?.points);
    const guaranteedLinePoint = getGuaranteedLinePoint(row, rows, mode);
    const poolMarker = getPoolMarkerLine(row);
    const pointCreepRisk = getPointCreepRiskLine(row);

    if (isGuaranteedLine) {
      lines.push('Draw Line');
    } else if (rowPoint !== null && guaranteedLinePoint !== null) {
      lines.push(rowPoint > guaranteedLinePoint ? 'Above Line' : 'Below Line');
    }

    if (isUserRow) {
      lines.push('Your Rung');
    }

    if (poolMarker) {
      lines.push(poolMarker);
    }

    if (pointCreepRisk) {
      lines.push(pointCreepRisk);
    }

    if (isUserRow || isGuaranteedLine) {
      [getPermitSummaryLine(row, referenceRow, meta), getLadderHarvestSnapshotLine(row, referenceRow, meta)]
        .filter(Boolean)
        .forEach((line) => lines.push(line));
    }

    return [...new Set(lines)];
  }

  function renderLadderNotes(lines) {
    if (!Array.isArray(lines) || !lines.length) return '';
    return `<div class="ladder-note-list">${lines.map((line) => `<div>${escapeHtml(line)}</div>`).join('')}</div>`;
  }

  function markerHtml(markers) {
    if (!markers.length) return '';
    return `<div class="marker-stack">${markers.map((marker) => {
      if (marker.kind === 'sources') {
        return `<button type="button" class="marker-pill sources" data-source-pill="true" data-point="${escapeHtml(marker.point)}">${escapeHtml(marker.label)}</button>`;
      }
      if (marker.kind === 'user') {
        return `<span class="ladder-rung-signal" aria-label="Visitor point rung"><span class="ladder-rung-light"></span><span>${escapeHtml(marker.label)}</span></span>`;
      }
      return `<span class="marker-line-label ${marker.kind}">${escapeHtml(marker.label)}</span>`;
    }).join('')}</div>`;
  }

  function deriveGuaranteedLinePoint(rows, mode) {
    if (!Array.isArray(rows) || !rows.length) return null;
    const guaranteedPoints = rows
      .map((candidate) => {
        const points = num(candidate?.points);
        if (points === null) return null;
        const odds = (mode === DRAW_MODE.PREFERENCE || mode === DRAW_MODE.YOUTH_RESERVE)
          ? selectPreferenceOddsPercent(candidate)
          : selectDrawOddsPercent(candidate);
        if (odds.percent !== null && odds.percent >= 99.9) return points;
        return null;
      })
      .filter((value) => value !== null);
    if (!guaranteedPoints.length) return null;
    return Math.min(...guaranteedPoints);
  }

  function getGuaranteedLinePoint(row, rows = [], mode = DRAW_MODE.STATUS_ONLY) {
    const summaryGuaranteedPoint = num(row?.guaranteed_at_2026);
    if (summaryGuaranteedPoint !== null) return summaryGuaranteedPoint;
    const projected = num(row?.projected_2026_max_cutoff_point);
    if (projected !== null) return projected;
    return deriveGuaranteedLinePoint(rows, mode);
  }

  function isGuaranteedLineRow(row, rows = [], mode = DRAW_MODE.STATUS_ONLY) {
    if (!row) return false;
    const rowPoint = num(row.points);
    const guaranteedLinePoint = getGuaranteedLinePoint(row, rows, mode);
    if (rowPoint !== null && guaranteedLinePoint !== null) {
      return Math.round(rowPoint) === Math.round(guaranteedLinePoint);
    }
    if (row.guaranteed_marker === 'TRUE') return true;
    return false;
  }

  function isAboveGuaranteedLineRow(row, rows = [], mode = DRAW_MODE.STATUS_ONLY) {
    if (!row) return false;
    const rowPoint = num(row.points);
    const guaranteedLinePoint = getGuaranteedLinePoint(row, rows, mode);
    if (rowPoint === null || guaranteedLinePoint === null) return false;
    return rowPoint > guaranteedLinePoint;
  }

  function renderLadder(meta, huntCode, residency, points, drawPool) {
    if (!els.ladderTableWrap || !els.ladderTableEmpty || !els.ladderTableBody) return;

    const rows = getLadderRows(huntCode, residency, drawPool);
    const ladderReferenceRow = getReferenceRow(huntCode, residency, drawPool);
    const mode = detectLadderMode(meta, rows, ladderReferenceRow);
    setLadderHeaders(mode);
    if (!rows.length) {
      els.ladderTableWrap.hidden = true;
      els.ladderTableEmpty.hidden = false;
      els.ladderTableBody.innerHTML = '';
      if (els.ladderRange) els.ladderRange.textContent = 'Rows: 0';
      return;
    }

    const pointValues = rows
      .map((row) => num(row.points))
      .filter((value) => value !== null)
      .sort((a, b) => a - b);
    const minPoint = pointValues.length ? pointValues[0] : null;
    const maxPoint = pointValues.length ? pointValues[pointValues.length - 1] : null;
    if (els.ladderRange) {
      els.ladderRange.textContent = `Rows: ${rows.length}${minPoint !== null && maxPoint !== null ? ` | Points ${minPoint}-${maxPoint}` : ''}`;
    }

    function getRowCells(row, markers, historicalPointRow) {
      const actual2025Display = formatHistoricalDrawResult(row)
        || formatHistoricalDrawResult(historicalPointRow)
        || '';
      const odds = (mode === DRAW_MODE.PREFERENCE || mode === DRAW_MODE.YOUTH_RESERVE)
        ? selectPreferenceOddsPercent(row)
        : selectDrawOddsPercent(row);
      const oddsDisplay = formatOddsAsOneInOrPercent(odds.percent);

      if (mode === DRAW_MODE.PREFERENCE) {
        const pointStatus = hasMeaningfulValue(row?.gap) ? formatGapStatus(row.gap) : '';
        return [
          formatInteger(row.points),
          actual2025Display,
          oddsDisplay,
          pointStatus,
          '',
        ];
      }

      if (mode === DRAW_MODE.BONUS) {
        const bonusProjection = (isGuaranteedLineRow(row, rows, mode) || isAboveGuaranteedLineRow(row, rows, mode))
          ? MAX_POINT_POOL_GUARANTEED_DISPLAY
          : (getMaxPointPoolDisplay(row) || '');
        const randomChance = isAboveGuaranteedLineRow(row, rows, mode) ? '' : (getRandomDrawDisplay(row) || oddsDisplay);
        return [
          formatInteger(row.points),
          actual2025Display,
          bonusProjection,
          randomChance || '',
          '',
        ];
      }

      if (mode === DRAW_MODE.YOUTH_RESERVE) {
        const reservePool = firstAvailable(row, ['quota_2026_youth_reserve']) || '';
        const youthOdds = formatOddsAsOneInOrPercent(toProbabilityPercent(firstAvailable(row, ['youth_reserve_probability', 'p_preference_draw'])));
        const rollover = formatOddsAsOneInOrPercent(toProbabilityPercent(firstAvailable(row, ['youth_rollover_main_draw_probability', 'p_random_pool'])));
        const notes = String(row?.preference_model_note || '').trim() || String(row?.data_quality_flags || '').trim() || '';
        return [
          formatInteger(row.points),
          String(reservePool),
          youthOdds || oddsDisplay,
          rollover || '',
          notes,
        ];
      }

      if (mode === DRAW_MODE.ALLOCATION_AVAILABILITY) {
        const status = firstAvailable(row, ['availability_status', 'allocation_status', 'status', 'draw_outlook']) || '';
        const availability = firstAvailable(row, ['availability_pct', 'p_availability', 'permits_remaining', 'permits_sold_or_used']) || '';
        const allocation = firstAvailable(row, ['permit_allotment_2026_total', 'public_permits_2026', 'permits_allotted']) || '';
        const ruleSource = firstAvailable(row, ['rule_status', 'permit_allotment_2026_source', 'reason']) || '';
        return [
          status,
          String(availability),
          String(allocation),
          String(ruleSource),
          String(row?.data_quality_flags || '').trim() || '',
        ];
      }

      const statusOnly = firstAvailable(row, ['status', 'draw_outlook', 'algorithm_status']) || '';
      return [
        formatInteger(row.points),
        actual2025Display,
        statusOnly,
        oddsDisplay,
        String(row?.reason || '').trim() || '',
      ];
    }

    els.ladderTableBody.innerHTML = rows.map((row) => {
      const markers = [];
      const classes = [];
      const referenceRow = ladderReferenceRow;
      const historicalPointRow = state.engineHistoryByPoint.get(rowKey(huntCode, residency, row.points, drawPool)) || null;
      const userPoints = getCurrentPoints();
      const isUserRow = Number(row.points) === Number(userPoints);
      const isGuaranteedLine = isGuaranteedLineRow(row, rows, mode);

      if (isUserRow) {
        markers.push({ kind: 'user', label: 'YOUR RUNG' });
        classes.push('is-user-row');
      }

      if (isGuaranteedLine) {
        markers.push({ kind: 'guaranteed', label: 'DRAW LINE' });
        classes.push('is-guaranteed-row');
      }

      if ((isUserRow || isGuaranteedLine) && hasSourceData(meta, row, referenceRow)) {
        markers.push({ kind: 'sources', label: 'Hunt Data', point: row.points });
      }
      const cells = getRowCells(row, markers, historicalPointRow);
      const zone = String(row?.point_pool_zone || '').trim();
      const blankMaxCell = mode === DRAW_MODE.BONUS && zone === 'random_pool';
      const blankRandomCell = mode === DRAW_MODE.BONUS && (
        ['max_point_pool', 'max_pool_guaranteed'].includes(zone)
        || isAboveGuaranteedLineRow(row, rows, mode)
      );
      const markersBlock = markerHtml(markers);
      const noteLines = buildLadderNoteLines({
        meta,
        row,
        referenceRow,
        rows,
        mode,
        isUserRow,
        isGuaranteedLine,
        cells,
        userPoints,
      });
      const notesBlock = [
        renderLadderNotes(noteLines),
        markersBlock,
      ].filter(Boolean).join('');
      const tableCells = [
        renderLadderCell(cells[0]),
        renderLadderCell(cells[1]),
        renderLadderCell(blankMaxCell ? '' : cells[2]),
        renderLadderCell(blankRandomCell ? '' : cells[3]),
        notesBlock ? `<td class="ladder-notes-cell">${notesBlock}</td>` : '<td class="is-empty-cell ladder-notes-cell" aria-label="No highlighted notes"></td>',
      ].join('');

      const rowClass = [isUserRow ? 'is-user-row' : '', ...classes.filter((name) => name !== 'is-user-row')]
        .filter(Boolean)
        .join(' ');

      return `
        <tr class="${rowClass}" data-ladder-point="${escapeHtml(row.points)}">
          ${tableCells}
        </tr>`;
    }).join('');

    els.ladderTableEmpty.hidden = true;
    els.ladderTableWrap.hidden = false;

    if (els.jumpToPointsBtn) {
      const target = els.ladderTableBody.querySelector(`tr[data-ladder-point="${String(points)}"]`);
      els.jumpToPointsBtn.hidden = !target;
    }
  }

  function renderEmpty(filters, coverageMessage) {
    if (els.detailEmpty) els.detailEmpty.hidden = false;
    if (els.detailContent) els.detailContent.hidden = true;
    renderSummary(null, null, filters, coverageMessage, null);
    if (els.ladderTableWrap) els.ladderTableWrap.hidden = true;
    if (els.ladderTableEmpty) els.ladderTableEmpty.hidden = false;
    if (els.ladderTableBody) els.ladderTableBody.innerHTML = '';
  }

  function openPointLadder(reason = '') {
    if (!els.pointLadderAccordion || els.pointLadderAccordion.open) return;
    els.pointLadderAccordion.open = true;
    if (reason) {
      els.pointLadderAccordion.dataset.openedBy = reason;
    }
  }

  function setupLadderAutoOpen() {
    if (!els.pointLadderAccordion) return;

    els.pointLadderAccordion.addEventListener('mouseenter', () => openPointLadder('mouse'));
    els.pointLadderAccordion.addEventListener('focusin', () => openPointLadder('focus'));

    if (!('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.18) {
          openPointLadder('scroll');
          observer.disconnect();
        }
      });
    }, {
      root: null,
      threshold: [0.18, 0.4],
    });
    observer.observe(els.pointLadderAccordion);
  }

  function renderDetail(filters) {
    const meta = findMeta(filters.huntCode, filters.residency, filters.drawPool);
    const rawEngineRows = getEngineRows(filters.huntCode, filters.residency, filters.drawPool);
    const rawEngineRow = getEngineRow(filters.huntCode, filters.residency, filters.points, filters.drawPool);
    const rawEngineGroupFallbackRow = getEngineGroupFallbackRow(filters.huntCode, filters.residency, filters.drawPool);
    const engineRows = SHOW_AUDIT_ONLY_ROWS
      ? rawEngineRows
      : rawEngineRows.filter((row) => !isOutOfScopeNonTargetRow(row));
    const engineRow = SHOW_AUDIT_ONLY_ROWS || !isOutOfScopeNonTargetRow(rawEngineRow)
      ? rawEngineRow
      : null;
    const engineGroupFallbackRow = SHOW_AUDIT_ONLY_ROWS || !isOutOfScopeNonTargetRow(rawEngineGroupFallbackRow)
      ? rawEngineGroupFallbackRow
      : null;
    const ladderRows = getLadderRows(filters.huntCode, filters.residency, filters.drawPool);
    const ladderPointRow = ladderRows.find((row) => Number(row.points) === Number(filters.points)) || null;
    // Prefer exact engine row when present. For non-point families like Sportsman,
    // availability/status rows, and youth pending groups, fall back to the first
    // engine group row before falling back to the ladder row.
    const summaryRow = engineRow || engineGroupFallbackRow || ladderPointRow || null;
    const referenceRow = getReferenceRow(filters.huntCode, filters.residency, filters.drawPool);
    const onlyOutOfScopeRowsHidden = !SHOW_AUDIT_ONLY_ROWS && rawEngineRows.length > 0 && engineRows.length === 0;
    const coverageMessage = onlyOutOfScopeRowsHidden
      ? 'This category is outside the approved target prediction universe and is hidden from the standard Hunt Research view.'
      : (SHOW_AUDIT_ONLY_ROWS && isOutOfScopeNonTargetRow(summaryRow)
        ? getOutOfScopeAuditLabel()
        : getModeledCoverageStatus(meta, engineRows.length > 0 || ladderRows.length > 0));

    if (!filters.huntCode || onlyOutOfScopeRowsHidden || (!meta && !engineRows.length)) {
      renderEmpty(filters, coverageMessage || 'Type a hunt code or load one from Hunt Backpack.');
      return;
    }

    if (els.detailEmpty) els.detailEmpty.hidden = true;
    if (els.detailContent) els.detailContent.hidden = false;

    if (els.detailTitle) {
      els.detailTitle.textContent = meta ? `${meta.hunt_code} | ${meta.hunt_name}` : filters.huntCode;
    }

    if (els.detailSubtitle) {
      els.detailSubtitle.textContent = meta
        ? `${meta.species || 'Unknown'} | ${meta.weapon || 'Unknown weapon'} | ${filters.residency}`
        : `${filters.residency} | ${formatInteger(filters.points)} points`;
    }

    if (els.openPlannerLink) {
      els.openPlannerLink.href = `./builder.html?hunt_code=${encodeURIComponent(filters.huntCode)}`;
    }

    if (els.openDwrLink) {
      els.openDwrLink.href = '#';
      if (referenceRow?.has_any_odds_source === 'TRUE') {
        els.openDwrLink.removeAttribute('aria-disabled');
      } else {
        els.openDwrLink.setAttribute('aria-disabled', 'true');
      }
    }

    renderSummary(meta, summaryRow, filters, coverageMessage, referenceRow);
    renderLadder(meta, filters.huntCode, filters.residency, filters.points, filters.drawPool);

    state.selectedMeta = meta;
    state.selectedFilters = filters;

    window.UOGA_HUNT_RESEARCH_SNAPSHOT = {
      filters,
      meta,
      summaryRow,
      referenceRow,
      ladderRows,
      engineRows,
      masterRows: state.masterRows,
      referenceRows: state.referenceRows,
      loadedSources: state.loadedSources,
      engineMode: state.engineMode,
    };
    window.dispatchEvent(new CustomEvent('uoga:hunt-research-rendered', {
      detail: window.UOGA_HUNT_RESEARCH_SNAPSHOT,
    }));

    if (meta) {
      upsertBasketItem(meta, filters, summaryRow);
    }
  }

  function upsertBasketItem(meta, filters, engineRow) {
    if (!meta) return;

    const items = getBasket().filter((item) => normalizeKey(item.hunt_code) !== normalizeKey(meta.hunt_code));
    items.unshift({
      hunt_code: meta.hunt_code,
      hunt_name: meta.hunt_name,
      species: meta.species,
      weapon: meta.weapon,
      residency: filters.residency,
      draw_pool: filters.drawPool,
      selected_points: filters.points,
      draw_outlook: engineRow?.draw_outlook || '',
      updated_at: Date.now(),
    });

    saveBasket(items);
    renderBasket();
  }

  function removeBasketItem(huntCode) {
    saveBasket(getBasket().filter((item) => normalizeKey(item.hunt_code) !== normalizeKey(huntCode)));
    renderBasket();
  }

  function renderBasket() {
    const items = getBasket();

    if (els.basketCount) {
      els.basketCount.textContent = String(items.length);
    }

    if (!els.basketList) return;

    if (!items.length) {
      els.basketList.innerHTML = `
        <div class="backpack-card">
          <strong style="display:block;margin-bottom:8px;color:#2b1c12;">No hunts saved yet</strong>
          <p>Add a selected hunt to keep it moving between Hunt Planner and Hunt Research.</p>
        </div>`;
      return;
    }

    els.basketList.innerHTML = items.map((item) => {
      const poolLabel = getDrawPoolHandoffLabel(item.draw_pool);
      return `
        <div class="backpack-card">
          <span class="label">${escapeHtml(item.hunt_code)}</span>
          <h4>${escapeHtml(item.hunt_name || item.hunt_code)}</h4>
          <p>${escapeHtml(item.species || '')}${item.weapon ? ` | ${escapeHtml(item.weapon)}` : ''} | ${escapeHtml(item.residency || 'Resident')} | ${formatInteger(item.selected_points)} points</p>
          ${poolLabel ? `<p>${escapeHtml(poolLabel)}</p>` : ''}
          <p>${escapeHtml(item.draw_outlook || 'Saved for later review.')}</p>
          <div class="backpack-actions">
            <button class="mini-btn" type="button" data-basket-load="${escapeHtml(item.hunt_code)}">Load</button>
            <button class="mini-btn" type="button" data-basket-remove="${escapeHtml(item.hunt_code)}">Remove</button>
          </div>
        </div>`;
    }).join('');

    els.basketList.querySelectorAll('[data-basket-load]').forEach((button) => {
      button.addEventListener('click', () => {
        const huntCode = normalizeKey(button.getAttribute('data-basket-load'));
        const item = items.find((entry) => normalizeKey(entry.hunt_code) === huntCode);
        if (!item) return;
        els.huntCodeInput.value = item.hunt_code || '';
        els.residencySelect.value = item.residency || 'Resident';
        if (els.drawPoolSelect) els.drawPoolSelect.value = normalizeDrawPool(item.draw_pool);
        els.pointsInput.value = String(item.selected_points ?? 0);
        runResearch();
      });
    });

    els.basketList.querySelectorAll('[data-basket-remove]').forEach((button) => {
      button.addEventListener('click', () => removeBasketItem(button.getAttribute('data-basket-remove')));
    });
  }

  async function loadData() {
    if (state.loaded && state.loadedSources) return state.loadedSources;
    if (state.loadingPromise) return state.loadingPromise;

    state.loadingPromise = (async () => {
      try {
        const canonical = await loadFirstAvailable(DATA_SOURCES);
        const contractRows = parseJsonRows(canonical.text);
        const derived = deriveCanonicalRuntimeTables(contractRows);

        indexData(
          derived.engineRows,
          derived.ladderRows,
          derived.masterRows,
          derived.referenceRows
        );

        state.loadedSources = {
          engineMode: ENGINE_MODE,
          canonicalContract: canonical.source,
          canonicalRows: contractRows.length,
          engine: 'derived_from_canonical_contract',
          ladder: 'derived_from_canonical_contract',
          master: 'derived_from_canonical_contract',
          reference: 'derived_from_canonical_contract',
          legacyFallbackUsed: false,
          legacyFallbackAllowed: ALLOW_LEGACY_FALLBACK,
        };
        state.loaded = true;
        return state.loadedSources;
      } catch (canonicalError) {
        console.warn('Canonical Hunt Research contract load failed.', canonicalError);
        if (!ALLOW_LEGACY_FALLBACK) {
          throw new Error('Canonical Hunt Research contract is unavailable. Legacy fallback is disabled.');
        }
        console.warn('Legacy Hunt Research fallback is enabled via HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK. Loading legacy parallel feeds.');
      }

      const [engine, ladder, master, reference] = await Promise.all([
        loadFirstAvailable(ENGINE_SOURCES),
        loadFirstAvailable(LADDER_SOURCES),
        loadFirstAvailable(MASTER_SOURCES),
        loadFirstAvailable(REFERENCE_SOURCES),
      ]);

      indexData(
        parseCsv(engine.text),
        parseCsv(ladder.text),
        parseCsv(master.text),
        parseCsv(reference.text)
      );

      state.loadedSources = {
        engineMode: ENGINE_MODE,
        engine: engine.source,
        ladder: ladder.source,
        master: master.source,
        reference: reference.source,
        legacyFallbackUsed: true,
        legacyFallbackAllowed: true,
      };
      state.loaded = true;
      return state.loadedSources;
    })().finally(() => {
      state.loadingPromise = null;
    });

    return state.loadingPromise;
  }

  function bootstrapSelection() {
    const params = new URLSearchParams(window.location.search);
    const queryHunt = normalizeKey(params.get('hunt_code'));
    const queryResidency = params.has('residency') ? normalizeResidencyLabel(params.get('residency')) : '';
    const queryDrawPool = params.has('draw_pool') ? normalizeDrawPool(params.get('draw_pool')) : '';
    const queryPoints = params.has('points') ? params.get('points') : '';
    const storedHunt = normalizeKey(localStorage.getItem(SELECTED_HUNT_KEY));
    const storedResidency = queryResidency || normalizeResidencyLabel(localStorage.getItem(SELECTED_RESIDENCY_KEY));
    const storedDrawPool = queryDrawPool || normalizeDrawPool(localStorage.getItem(SELECTED_DRAW_POOL_KEY));
    const storedPoints = queryPoints !== '' ? queryPoints : localStorage.getItem(SELECTED_POINTS_KEY);
    const bootstrapHunt = queryHunt || storedHunt;

    if (bootstrapHunt) {
      els.huntCodeInput.value = bootstrapHunt;
      state.selectedHuntCode = bootstrapHunt;
    }

    els.residencySelect.value = storedResidency;
    if (els.drawPoolSelect) els.drawPoolSelect.value = storedDrawPool;

    if (storedPoints !== null && storedPoints !== '') {
      els.pointsInput.value = storedPoints;
    }

    if (queryHunt) {
      localStorage.setItem(SELECTED_HUNT_KEY, queryHunt);
    }

    if (queryDrawPool) {
      localStorage.setItem(SELECTED_DRAW_POOL_KEY, queryDrawPool);
    }

    if (queryResidency) {
      localStorage.setItem(SELECTED_RESIDENCY_KEY, queryResidency);
    }

    if (queryPoints !== '') {
      localStorage.setItem(SELECTED_POINTS_KEY, queryPoints);
    }
  }

  async function runResearch() {
    const filters = buildFilters();
    state.selectedHuntCode = filters.huntCode;

    localStorage.setItem(SELECTED_RESIDENCY_KEY, filters.residency);
    localStorage.setItem(SELECTED_DRAW_POOL_KEY, filters.drawPool);
    localStorage.setItem(SELECTED_POINTS_KEY, String(filters.points));

    if (filters.huntCode) {
      localStorage.setItem(SELECTED_HUNT_KEY, filters.huntCode);
    } else {
      localStorage.removeItem(SELECTED_HUNT_KEY);
    }

    renderFilterReadout(filters);

    if (!filters.huntCode) {
      renderEmpty(filters, 'Select a hunt in Hunt Builder or enter a hunt code to load the report.');
      return;
    }

    if (!state.loaded) {
      els.filterReadout.textContent = `${filters.huntCode} | ${filters.residency} | ${filters.points} points. Loading runtime rows...`;
      try {
        await loadData();
      } catch (error) {
        console.error(error);
        els.filterReadout.textContent = (error && error.message)
          ? `${error.message} (checked canonical Hunt Research contract sources).`
          : 'Hunt Research data failed to load (checked canonical Hunt Research contract sources).';
        els.plannerReadout.textContent = 'Page loaded. Production data did not.';
        renderEmpty(filters, 'Runtime rows could not be loaded yet.');
        return;
      }
    }

    renderDetail(filters);
  }

  function clearFilters() {
    els.huntCodeInput.value = '';
    els.residencySelect.value = 'Resident';
    if (els.drawPoolSelect) els.drawPoolSelect.value = 'standard';
    els.pointsInput.value = '12';
    state.selectedHuntCode = '';
    localStorage.removeItem(SELECTED_HUNT_KEY);
    localStorage.setItem(SELECTED_RESIDENCY_KEY, 'Resident');
    localStorage.setItem(SELECTED_DRAW_POOL_KEY, 'standard');
    localStorage.setItem(SELECTED_POINTS_KEY, '12');
    runResearch();
  }

  function jumpToUserPoints() {
    document.querySelector('.report-table tbody tr.is-user-row')
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function bindEvents() {
    els.runResearchButton?.addEventListener('click', runResearch);
    els.clearFiltersButton?.addEventListener('click', clearFilters);

    els.addToBasketButton?.addEventListener('click', () => {
      const filters = buildFilters();
      const meta = findMeta(filters.huntCode, filters.residency, filters.drawPool);
      const engineRow = getEngineRow(filters.huntCode, filters.residency, filters.points, filters.drawPool);
      upsertBasketItem(meta, filters, engineRow);
    });

    els.clearBasketButton?.addEventListener('click', () => {
      saveBasket([]);
      renderBasket();
    });

    els.jumpToPointsBtn?.addEventListener('click', () => {
      jumpToUserPoints();
      const target = document.querySelector('.report-table tbody tr.is-user-row');
      if (!target) return;
      target.classList.add('jump-flash');
      window.setTimeout(() => target.classList.remove('jump-flash'), 900);
    });

    [els.residencySelect, els.drawPoolSelect].forEach((el) => {
      el?.addEventListener('change', () => { runResearch(); });
    });

    [els.huntCodeInput, els.pointsInput].forEach((el) => {
      el?.addEventListener('input', () => {
        if (state.inputRunTimer) window.clearTimeout(state.inputRunTimer);
        state.inputRunTimer = window.setTimeout(() => {
          runResearch();
        }, 180);
      });
    });

    els.ladderTableBody?.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-source-pill="true"]');
      if (!trigger || !state.selectedMeta || !state.selectedFilters) return;

      const point = Number.parseInt(trigger.getAttribute('data-point') || '', 10);
      const row = getLadderRows(state.selectedFilters.huntCode, state.selectedFilters.residency, state.selectedFilters.drawPool)
        .find((candidate) => Number(candidate.points) === point);

      if (!row) return;

      const referenceRow = getReferenceRow(state.selectedFilters.huntCode, state.selectedFilters.residency, state.selectedFilters.drawPool);
      openSourceModal(state.selectedMeta, row, referenceRow, state.selectedFilters.residency);
    });

    els.sourceModalClose?.addEventListener('click', closeSourceModal);

    els.sourceModal?.addEventListener('click', (event) => {
      if (event.target === els.sourceModal) {
        closeSourceModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeSourceModal();
      }
    });
  }

  async function init() {
    try {
      renderBasket();
      bootstrapSelection();
      bindEvents();
      setupLadderAutoOpen();
      if (state.selectedHuntCode) {
        await runResearch();
      } else {
        els.filterReadout.textContent = 'Select a hunt in Hunt Builder, then run Hunt Research.';
      }
    } catch (error) {
      console.error(error);
      els.filterReadout.textContent = (error && error.message)
        ? `${error.message} (checked canonical Hunt Research contract sources).`
        : 'Hunt Research data failed to load (checked canonical Hunt Research contract sources).';
      els.plannerReadout.textContent = 'Page loaded. Production data did not.';
    }
  }

  init();
})();
