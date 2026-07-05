(() => {
  "use strict";

  const DASHBOARD_ID = "uogaApplicationOutlookDashboard";
  const SELECTED_HUNT_KEY = "selected_hunt_code";
  const SELECTED_RESIDENCY_KEY = "selected_hunt_research_residency";
  const SELECTED_POINTS_KEY = "selected_hunt_research_points";
  const SELECTED_DRAW_POOL_KEY = "selected_hunt_research_draw_pool";

  const state = {
    loaded: false,
    loading: false,
    loadPromise: null,
    coreReady: false,
    error: "",
    coreWaitAttempts: 0,
    rows: {
      engine: [],
      ladder: [],
      master: [],
      reference: [],
      management: [],
      outlook: [],
    },
    sources: {},
  };

  function isResearchPage() {
    const path = String(window.location.pathname || "").toLowerCase();
    return path.endsWith("/research.html") || path.endsWith("research.html");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeCode(value) {
    return String(value || "").trim().toUpperCase();
  }

  function normalizeResidency(value) {
    const text = String(value || "").trim().toLowerCase();
    if (["nr", "non-res", "nonresident", "non-resident"].includes(text)) return "Nonresident";
    return "Resident";
  }

  function normalizeDrawPool(value) {
    return String(value || "").trim().toLowerCase() || "standard";
  }

  function num(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function hasValue(value) {
    const text = String(value ?? "").trim();
    return !!text && !["N/A", "NA", "NOT AVAILABLE", "NULL", "NONE"].includes(text.toUpperCase());
  }

  function firstValue(source, keys) {
    if (!source) return "";
    for (const key of keys) {
      if (hasValue(source[key])) return source[key];
    }
    return "";
  }

  function formatValue(value, fallback = "Not available") {
    return hasValue(value) ? String(value).trim() : fallback;
  }

  function normalizeDrawDesignLabel(value) {
    const text = String(value || "").trim();
    const lower = text.toLowerCase();
    const upper = text.toUpperCase();
    if (!text) return "";
    if (lower.includes("preference")) return "Preference";
    if (lower.includes("sportsman") || lower === "random" || upper.includes("SPORTSMAN")) return "Random";
    if (lower.includes("max") || lower.includes("weighted") || lower.includes("bonus") || lower.includes("split") || upper.includes("BEAR_DRAW")) return "Max/Weighted Split";
    if (lower.includes("capped") || lower.includes("allotment") || lower.includes("private_lands_only")) return "Capped Permits";
    if (lower.includes("unlimited")) return "Unlimited";
    if (lower.includes("allocation") || lower.includes("reference only") || lower.includes("conservation") || lower.includes("tribal")) return "Allocation / Reference Only";
    return text;
  }

  function formatInteger(value) {
    const parsed = num(value);
    return parsed === null ? "Not available" : parsed.toLocaleString();
  }

  function formatAge(value) {
    const parsed = num(value);
    return parsed === null || parsed <= 0 ? "No verified age data" : parsed.toFixed(1);
  }

  function formatPercent(value) {
    const parsed = num(value);
    if (parsed === null) return "Not available";
    const pct = parsed <= 1 && parsed > 0 ? parsed * 100 : parsed;
    if (pct >= 99.95) return "100%";
    if (pct >= 10) return `${pct.toFixed(1)}%`;
    return `${pct.toFixed(2)}%`;
  }

  function pipeList(value) {
    return String(value || "")
      .split("|")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function readParams() {
    const search = new URLSearchParams(window.location.search || "");
    const hash = new URLSearchParams(String(window.location.hash || "").replace(/^#/, ""));
    return {
      get(name) {
        return search.get(name) || hash.get(name) || "";
      },
      has(name) {
        return search.has(name) || hash.has(name);
      },
    };
  }

  function readStoredSelectionObject() {
    const stores = [window.sessionStorage, window.localStorage].filter(Boolean);
    for (const store of stores) {
      try {
        const raw = store.getItem("selectedHuntForResearch");
        if (!raw) continue;
        if (raw.trim().startsWith("{")) return JSON.parse(raw);
        return { hunt_code: raw };
      } catch {
        // Storage can be blocked in embedded contexts; URL parameters still work.
      }
    }
    return {};
  }

  function readStorageValue(key) {
    for (const store of [window.sessionStorage, window.localStorage].filter(Boolean)) {
      try {
        const value = store.getItem(key);
        if (hasValue(value)) return value;
      } catch {
        // Ignore blocked storage.
      }
    }
    return "";
  }

  function getSelection() {
    const params = readParams();
    const storedObject = readStoredSelectionObject();
    const huntInput = document.getElementById("huntCodeInput");
    const residencyInput = document.getElementById("residencySelect");
    const drawPoolInput = document.getElementById("drawPoolSelect");
    const pointsInput = document.getElementById("pointsInput");
    const huntCode = normalizeCode(
      params.get("hunt_code")
      || huntInput?.value
      || storedObject.hunt_code
      || storedObject.huntCode
      || readStorageValue(SELECTED_HUNT_KEY)
    );
    const residency = normalizeResidency(
      params.get("residency")
      || residencyInput?.value
      || storedObject.residency
      || readStorageValue(SELECTED_RESIDENCY_KEY)
    );
    const drawPool = normalizeDrawPool(
      params.has("draw_pool") ? params.get("draw_pool")
        : (drawPoolInput?.value || storedObject.draw_pool || storedObject.drawPool || readStorageValue(SELECTED_DRAW_POOL_KEY))
    );
    const points = num(
      params.get("points")
      || pointsInput?.value
      || storedObject.points
      || storedObject.selected_points
      || readStorageValue(SELECTED_POINTS_KEY)
      || "0"
    );
    return { huntCode, residency, drawPool, points: points ?? 0 };
  }

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let value = "";
    let inQuotes = false;
    const source = String(text || "");

    for (let i = 0; i < source.length; i += 1) {
      const char = source[i];
      const next = source[i + 1];
      if (char === '"') {
        if (inQuotes && next === '"') {
          value += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === "," && !inQuotes) {
        row.push(value);
        value = "";
      } else if ((char === "\n" || char === "\r") && !inQuotes) {
        if (char === "\r" && next === "\n") i += 1;
        row.push(value);
        if (row.some((cell) => String(cell || "").trim() !== "")) rows.push(row);
        row = [];
        value = "";
      } else {
        value += char;
      }
    }

    if (value.length || row.length) {
      row.push(value);
      if (row.some((cell) => String(cell || "").trim() !== "")) rows.push(row);
    }

    if (rows.length < 2) return [];
    const headers = rows[0].map((header) => String(header || "").trim());
    return rows.slice(1).map((record) => {
      const mapped = {};
      headers.forEach((header, index) => {
        mapped[header] = record[index] ?? "";
      });
      return mapped;
    });
  }

  async function fetchText(url) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Request failed for ${url}`);
      const text = await response.text();
      if (text.startsWith("version https://git-lfs.github.com/spec/v1")) {
        throw new Error(`Git LFS pointer served instead of data for ${url}`);
      }
      return text;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function loadFirst(sources) {
    let lastError = null;
    for (const source of (sources || []).filter(Boolean)) {
      try {
        return { source, text: await fetchText(source) };
      } catch (error) {
        lastError = error;
        console.warn("Outlook dashboard source failed:", source, error);
      }
    }
    throw lastError || new Error("No dashboard data source could be loaded.");
  }

  function getManagementSources() {
    const version = window.UOGA_CONFIG?.HUNT_RESEARCH_DATA_VERSION || "research-outlook-dashboard-2";
    const cloudflare = "https://json.uoga.workers.dev";
    return [
      `${cloudflare}/processed_data/management_context/hunt_management_objective_context.json?v=${version}`,
      `${cloudflare}/management_context/hunt_management_objective_context.json?v=${version}`,
      `./processed_data/management_context/hunt_management_objective_context.json?v=${version}`,
    ];
  }

  function getOutlookSources() {
    const version = window.UOGA_CONFIG?.HUNT_RESEARCH_DATA_VERSION || "research-outlook-dashboard-2";
    const cloudflare = "https://json.uoga.workers.dev";
    return [
      `${cloudflare}/processed_data/public_contracts/hunt_application_outlook.json?v=${version}`,
      `${cloudflare}/public_contracts/hunt_application_outlook.json?v=${version}`,
      `${cloudflare}/processed_data/research_page/hunt_application_outlook.json?v=${version}`,
      `${cloudflare}/research_page/hunt_application_outlook.json?v=${version}`,
      `./processed_data/public_contracts/hunt_application_outlook.json?v=${version}`,
      `./processed_data/research_page/hunt_application_outlook.json?v=${version}`,
    ];
  }

  async function loadData() {
    if (state.loaded) return;
    if (state.loadPromise) return state.loadPromise;
    state.loading = true;
    state.loadPromise = (async () => {
      const [outlookResult, managementResult] = await Promise.allSettled([
        loadFirst(getOutlookSources()),
        loadFirst(getManagementSources()),
      ]);

      if (outlookResult.status === "fulfilled") {
        state.rows.outlook = JSON.parse(outlookResult.value.text);
        state.sources.outlook = outlookResult.value.source;
      } else {
        state.rows.outlook = [];
        state.sources.outlook = "";
        console.info("No Hunt Application Outlook contract loaded for dashboard.", outlookResult.reason);
      }

      if (managementResult.status === "fulfilled") {
        state.rows.management = JSON.parse(managementResult.value.text);
        state.sources.management = managementResult.value.source;
      } else {
        state.rows.management = [];
        state.sources.management = "";
        console.info("No management objective context loaded for dashboard.", managementResult.reason);
      }

      state.loaded = true;
      state.loading = false;
    })();

    try {
      await state.loadPromise;
    } catch (error) {
      state.loading = false;
      state.loadPromise = null;
      throw error;
    }
  }

  function applyCoreSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return;
    state.rows.engine = Array.isArray(snapshot.engineRows) ? snapshot.engineRows : [];
    state.rows.ladder = Array.isArray(snapshot.ladderRows) ? snapshot.ladderRows : [];
    state.rows.master = Array.isArray(snapshot.masterRows) ? snapshot.masterRows : [];
    state.rows.reference = Array.isArray(snapshot.referenceRows)
      ? snapshot.referenceRows
      : (snapshot.referenceRow ? [snapshot.referenceRow] : []);
    state.sources = {
      ...(snapshot.loadedSources || {}),
      management: state.sources.management || "",
    };
    state.coreReady = true;
  }

  function rowMatches(row, selection) {
    return normalizeCode(row.hunt_code) === selection.huntCode
      && normalizeResidency(row.residency) === selection.residency
      && normalizeDrawPool(row.draw_pool) === selection.drawPool;
  }

  function findContext(selection) {
    const masterRows = state.rows.master.filter((row) => rowMatches(row, selection));
    const meta = masterRows.find((row) => num(row.points) === selection.points)
      || masterRows[0]
      || state.rows.master.find((row) => normalizeCode(row.hunt_code) === selection.huntCode)
      || null;
    const reference = state.rows.reference.find((row) => rowMatches(row, selection))
      || state.rows.reference.find((row) => normalizeCode(row.hunt_code) === selection.huntCode)
      || null;
    const ladderRows = state.rows.ladder
      .filter((row) => rowMatches(row, selection))
      .sort((a, b) => (num(b.points) ?? 0) - (num(a.points) ?? 0));
    const ladderPoint = ladderRows.find((row) => num(row.points) === selection.points) || null;
    const engineRows = state.rows.engine
      .filter((row) => rowMatches(row, selection))
      .sort((a, b) => (num(b.points) ?? 0) - (num(a.points) ?? 0));
    const enginePoint = engineRows.find((row) => num(row.points) === selection.points) || null;
    const selectedRow = enginePoint || ladderPoint || engineRows[0] || ladderRows[0] || meta || reference || {};
    const managementRows = Array.isArray(state.rows.management)
      ? state.rows.management.filter((row) => normalizeCode(row.hunt_code) === selection.huntCode)
      : [];
    const outlookRows = Array.isArray(state.rows.outlook) ? state.rows.outlook : [];
    const outlookRow = outlookRows.find((row) => normalizeCode(row.hunt_code) === selection.huntCode && normalizeResidency(row.residency) === selection.residency)
      || outlookRows.find((row) => normalizeCode(row.hunt_code) === selection.huntCode)
      || null;
    const comparable = buildComparableRows(selection, meta, selectedRow, outlookRow);
    return { meta, reference, ladderRows, ladderPoint, engineRows, enginePoint, selectedRow, managementRows, outlookRow, comparable };
  }

  function buildComparableRows(selection, meta, selectedRow, outlookRow = null) {
    const species = String(outlookRow?.species || meta?.species || selectedRow?.species || "").trim().toLowerCase();
    const huntType = String(outlookRow?.hunt_type || meta?.hunt_type || selectedRow?.hunt_type || "").trim().toLowerCase();
    const drawDesign = String(
      normalizeDrawDesignLabel(outlookRow?.draw_design || meta?.draw_design || selectedRow?.draw_design || outlookRow?.draw_system_type || meta?.draw_system_type || selectedRow?.draw_system_type)
    ).trim().toLowerCase();
    const huntClass = String(outlookRow?.hunt_class || meta?.hunt_class || selectedRow?.hunt_class || "").trim().toLowerCase();
    const seen = new Set([selection.huntCode]);
    const rows = [];
    const sourceRows = state.rows.outlook.length ? state.rows.outlook : state.rows.master;
    for (const row of sourceRows) {
      const code = normalizeCode(row.hunt_code);
      if (!code || seen.has(code)) continue;
      if (normalizeResidency(row.residency) !== selection.residency) continue;
      if (hasValue(row.draw_pool) && normalizeDrawPool(row.draw_pool) !== selection.drawPool) continue;
      if (species && String(row.species || "").trim().toLowerCase() !== species) continue;
      if (drawDesign) {
        const rowDesign = normalizeDrawDesignLabel(row.draw_design || row.draw_system_type || row.draw_2026_system_type).toLowerCase();
        if (rowDesign !== drawDesign) continue;
      }
      if (huntType && String(row.hunt_type || "").trim().toLowerCase() !== huntType) continue;
      if (!drawDesign && !huntType && huntClass && String(row.hunt_class || "").trim().toLowerCase() !== huntClass) continue;
      seen.add(code);
      rows.push(row);
      if (rows.length >= 5) break;
    }
    return rows;
  }

  function metricRow(label, value, note = "") {
    return `
      <div class="uoga-outlook-metric">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
        ${note ? `<small>${escapeHtml(note)}</small>` : ""}
      </div>`;
  }

  function panel(title, body, extraClass = "") {
    return `
      <section class="uoga-outlook-panel ${extraClass}">
        <h3>${escapeHtml(title)}</h3>
        ${body}
      </section>`;
  }

  function panelKicker(label) {
    return `<p class="uoga-panel-kicker">${escapeHtml(label)}</p>`;
  }

  function listRows(items) {
    if (!items.length) return `<p class="uoga-outlook-muted">Not available from the loaded runtime rows.</p>`;
    return `<div class="uoga-outlook-metrics">${items.join("")}</div>`;
  }

  function getHarvestSuccess(meta, reference, selectedRow) {
    return firstValue(meta, ["harvest_success_pct", "success_percent", "harvest_success_percent_2025", "percent_harvest_success", "success_harvest"])
      || firstValue(reference, ["harvest_success_percent_2025", "success_percent", "percent_harvest_success"])
      || firstValue(selectedRow, ["success_ratio"]);
  }

  function getAverageDays(meta, reference) {
    return firstValue(meta, ["average_days_hunted", "harvest_average_days_2025", "avg_days_hunted"])
      || firstValue(reference, ["harvest_average_days_2025", "average_days_hunted", "avg_days_hunted"]);
  }

  function getAge(meta, reference, selectedRow) {
    return firstValue(meta, ["average_harvest_age"])
      || firstValue(reference, ["average_harvest_age"])
      || firstValue(selectedRow, ["average_harvest_age"]);
  }

  function getCurrentAge(meta, reference, selectedRow) {
    return firstValue(meta, ["current_age_3yr_average"])
      || firstValue(reference, ["current_age_3yr_average"])
      || firstValue(selectedRow, ["current_age_3yr_average"]);
  }

  function formatOddsAsOneInOrPercent(percentValue) {
    const parsed = num(percentValue);
    if (parsed === null) return "Not available";
    const pct = Math.max(0, Math.min(100, parsed));
    if (pct <= 0) return "No modeled chance";
    const percentText = pct >= 10 ? `${pct.toFixed(1)}%` : `${pct.toFixed(1)}%`;
    if (pct >= 99.95) return `~1 in 1 or ${percentText}`;
    const denominator = 100 / pct;
    const denominatorText = denominator < 10 ? Number(denominator.toFixed(1)).toString() : Math.round(denominator).toString();
    return `~1 in ${denominatorText} or ${percentText}`;
  }

  function firstNumericValue(source, keys) {
    if (!source) return null;
    for (const key of keys) {
      const parsed = num(source[key]);
      if (parsed !== null) return parsed;
    }
    return null;
  }

  function unitOrPercentToPercent(value) {
    const parsed = num(value);
    if (parsed === null) return null;
    return parsed <= 1 && parsed > 0 ? parsed * 100 : parsed;
  }

  function isPreferencePointRow(row, meta) {
    const text = [
      row?.draw_system_type,
      row?.draw_2026_system_type,
      row?.draw_system,
      row?.draw_design,
      meta?.draw_system_type,
      meta?.draw_2026_system_type,
      meta?.draw_design,
    ].filter(Boolean).join(" ").toUpperCase();
    return text.includes("PREFERENCE");
  }

  function preferenceLineMetPercent(row, meta) {
    if (!isPreferencePointRow(row, meta)) return null;
    const selected = num(row?.points);
    const guaranteed = num(firstValue(row, ["guaranteed_at_2026", "projected_2026_max_cutoff_point", "guaranteed_line"])
      || firstValue(meta, ["guaranteed_at_2026", "projected_2026_max_cutoff_point", "guaranteed_line"]));
    if (selected !== null && guaranteed !== null && selected > guaranteed) return 100;
    return null;
  }

  function getSelectedOddsInfo(selectedRow, ladderPoint, meta, contract) {
    const sourceRows = [selectedRow, ladderPoint, meta].filter(Boolean);
    for (const row of sourceRows) {
      const display = firstValue(row, ["display_2026_random_draw", "display_2026_max_point_pool", "display_odds_pct"]);
      if (hasValue(display) && /[0-9]/.test(String(display))) {
        const displayPercent = firstNumericValue(row, ["random_draw_odds_2026", "p_random_pool_pct", "p_max_pool_pct", "p_draw_pct", "odds_2026_projected"]);
        const unitPercent = unitOrPercentToPercent(firstValue(row, ["p_draw_mean", "success_ratio"]));
        return { display: String(display), percent: displayPercent ?? unitPercent };
      }

      const percent = firstNumericValue(row, ["random_draw_odds_2026", "p_random_pool_pct", "p_max_pool_pct", "p_draw_pct", "odds_2026_projected"]);
      if (percent !== null && percent > 0) return { display: formatOddsAsOneInOrPercent(percent), percent };

      const unitPercent = unitOrPercentToPercent(firstValue(row, ["p_draw_mean", "success_ratio"]));
      if (unitPercent !== null && unitPercent > 0) return { display: formatOddsAsOneInOrPercent(unitPercent), percent: unitPercent };

      const lineMetPercent = preferenceLineMetPercent(row, meta);
      if (lineMetPercent !== null) return { display: formatOddsAsOneInOrPercent(lineMetPercent), percent: lineMetPercent };
    }

    const contractPercent = unitOrPercentToPercent(firstValue(contract, ["modeled_draw_probability"]));
    if (contractPercent !== null) return { display: formatPercent(contractPercent), percent: contractPercent };
    return { display: "Not available", percent: null };
  }

  function getPointStatusLabel(selection, selectedRow, meta) {
    const selected = num(selection?.points);
    const guaranteed = num(getGuaranteedLine(selectedRow, meta));
    if (selected !== null && guaranteed !== null) {
      const delta = guaranteed - selected;
      if (delta > 0) return `${delta} pts short of guaranteed`;
      if (delta === 0) return "At guaranteed";
      return `${Math.abs(delta)} pts above guaranteed`;
    }
    return firstValue(selectedRow, ["status", "draw_outlook", "point_status"])
      || firstValue(meta, ["status", "draw_outlook", "point_status"]);
  }

  function getPermitTotal(meta, reference, selectedRow) {
    return firstValue(meta, ["permits_2026_total", "public_permits_2026"])
      || firstValue(reference, ["permits_2026_total", "public_permits_2026"])
      || firstValue(selectedRow, ["total_permits", "quota_2026_total"]);
  }

  function getPercentFivePlus(meta, reference, selectedRow) {
    return firstValue(meta, ["percent_5_plus", "percent_5plus", "percent_five_plus", "harvest_age_percent_5plus"])
      || firstValue(reference, ["percent_5_plus", "percent_5plus", "percent_five_plus", "harvest_age_percent_5plus"])
      || firstValue(selectedRow, ["percent_5_plus", "percent_5plus", "percent_five_plus", "harvest_age_percent_5plus"]);
  }

  function getGuaranteedLine(selectedRow, meta) {
    return firstValue(selectedRow, ["guaranteed_at_2026", "guaranteed_points", "min_points_guaranteed", "guaranteed_line"])
      || firstValue(meta, ["guaranteed_at_2026", "guaranteed_points", "min_points_guaranteed", "guaranteed_line"]);
  }

  function getPointTrend(selectedRow, meta) {
    return firstValue(selectedRow, ["point_creep", "point_trend", "trend", "draw_trend"])
      || firstValue(meta, ["point_creep", "point_trend", "trend", "draw_trend"]);
  }

  function isStatusOnlyContext(meta, reference, selectedRow) {
    const text = [
      meta?.hunt_type,
      meta?.draw_design,
      meta?.hunt_class,
      meta?.permit_type,
      reference?.hunt_type,
      reference?.draw_design,
      selectedRow?.hunt_type,
      selectedRow?.draw_design,
      selectedRow?.hunt_class,
      selectedRow?.status,
    ].filter(Boolean).join(" ").toLowerCase();
    return /statewide|conservation|expo|harvest objective|status only|availability|extended archery|pursuit/.test(text);
  }

  function decisionLabel(odds, context = {}) {
    if (context.statusOnly) return "STATUS / AVAILABILITY ONLY";
    const parsed = num(odds);
    if (parsed === null) return "INSUFFICIENT DATA";
    const pct = parsed <= 1 && parsed > 0 ? parsed * 100 : parsed;
    if (pct >= 60) return "STRONG APPLY";
    if (pct >= 25) return "WITHIN REACH";
    if (context.highQuality && pct < 25) return "QUALITY LONG SHOT";
    return "LONG SHOT";
  }

  function recommendationSentence(odds, permitTotal, decision) {
    if (decision === "STATUS / AVAILABILITY ONLY") {
      return "This hunt is best read as a status or availability item, not a modeled draw-odds decision.";
    }
    if (decision === "INSUFFICIENT DATA") {
      return "The loaded rows do not provide enough modeled odds data for a confident application read.";
    }
    const parsed = num(odds);
    const permits = num(permitTotal);
    if (parsed === null) return "Draw outlook is waiting on a verified odds row for this selected point level.";
    const pct = parsed <= 1 && parsed > 0 ? parsed * 100 : parsed;
    if (pct >= 60) return "Based on your points, this hunt appears within reach.";
    if (pct >= 20) return "This is a reach application; use comparable hunts to decide if the upside is worth it.";
    if (permits !== null && permits <= 5) return "Odds are thin and permit volume is very small, so treat this as a premium swing.";
    return "Odds are thin at this point level; consider comparable hunts with better opportunity.";
  }

  function badge(label, variant = "") {
    return `<span class="uoga-badge ${variant ? `is-${escapeHtml(variant)}` : ""}">${escapeHtml(label)}</span>`;
  }

  function qualitySignal(row) {
    const harvest = firstValue(row, ["harvest_success_pct", "success_percent", "harvest_success_percent_2025", "percent_harvest_success"]);
    const age = row.average_harvest_age;
    const harvestNum = num(harvest);
    const ageNum = num(age);
    if (ageNum !== null && ageNum > 0) return `${formatAge(age)} avg age`;
    if (harvestNum !== null) return `${formatPercent(harvest)} harvest`;
    return "Limited quality data";
  }

  function comparableStatus(row) {
    const odds = firstValue(row, ["modeled_draw_probability", "p_draw_pct", "random_draw_odds_2026", "odds_2026_projected", "success_ratio"]);
    const status = firstValue(row, ["status", "draw_outlook", "point_status"]);
    return hasValue(odds) ? formatPercent(odds) : formatValue(status, "Status not loaded");
  }

  function renderComparableCards(rows) {
    if (!rows.length) return `<p class="uoga-outlook-muted">No comparable rows loaded for this species/type/residency slice.</p>`;
    return `
      <p class="uoga-outlook-muted">Hunt-level comparison only. Confirm point-rung odds in the ladder before using these as substitutes.</p>
      <div class="uoga-comparable-grid">
        <table class="uoga-comparable-table">
          <thead>
            <tr><th>Hunt</th><th>Hunt-Level Odds / Status</th><th>Quality Signal</th><th>Why similar</th></tr>
          </thead>
          <tbody>
            ${rows.slice(0, 3).map((row) => `
              <tr>
                <td><strong>${escapeHtml(row.hunt_code || "")}</strong><span>${escapeHtml(row.hunt_name || "Comparable hunt")}</span></td>
                <td>${escapeHtml(comparableStatus(row))}</td>
                <td>${escapeHtml(qualitySignal(row))}</td>
                <td>Same species/type pool</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  function renderManagementPanel(rows) {
    const row = rows[0] || {};
    const objectiveRange = hasValue(row.management_objective_range)
      ? formatValue(row.management_objective_range)
      : hasValue(row.management_objective_min)
      ? `${formatValue(row.management_objective_min)}${hasValue(row.management_objective_max) ? ` to ${formatValue(row.management_objective_max)}` : ""} ${formatValue(row.objective_unit, "")}`.trim()
      : "No objective row loaded";
    const managementDirection = hasValue(row.management_direction)
      ? formatValue(row.management_direction)
      : hasValue(row.objective_status)
      ? formatValue(row.objective_status)
      : "Objective known, observed evidence is limited.";
    return panel("U.O.G.A. Curated Context", `
      ${panelKicker("U.O.G.A. curated fields")}
      <div class="uoga-badge-row">${badge("Management Plan Context", "management")}</div>
      ${listRows([
        metricRow("State objective", `${formatValue(row.management_objective_type, "Objective type pending")} / ${objectiveRange}`),
        metricRow("Observed evidence", formatValue(row.management_objective_note || row.notes || row.objective_status_rule, "Observed comparison details are limited.")),
        metricRow("Management direction", managementDirection),
        metricRow("Permit direction watch", formatValue(row.permit_direction_watch, "Use as context only; does not change draw odds.")),
      ])}
      <p class="uoga-outlook-muted">Benchmark only. This is context and does not change modeled draw probability.</p>
    `);
  }

  function hasPersonaData(contract) {
    return pipeList(contract.persona_tags).length > 0
      || num(contract.sleeper_score) !== null
      || hasValue(firstValue(contract, ["sleeper_reasons"]));
  }

  function renderPersonaPanel(contract) {
    const tags = pipeList(contract.persona_tags);
    const sleeperScore = num(contract.sleeper_score);
    const sleeperReasons = firstValue(contract, ["sleeper_reasons"]);
    const tagBadges = tags.slice(0, 8).map((tag) => badge(tag.replace(/_/g, " "), "modeled")).join("");
    return `
      <div class="uoga-badge-row">${tagBadges}</div>
      ${listRows([
        metricRow("Sleeper score", sleeperScore === null ? "Not available" : formatValue(sleeperScore)),
        metricRow("Sleeper rationale", formatValue(sleeperReasons)),
        metricRow("How to use this", "Use these as comparison hints only; they do not override draw odds."),
      ])}
    `;
  }

  function getFreshnessLabel(contract, meta, selectedRow) {
    const explicit = firstValue(contract, ["data_updated_label", "data_freshness_label"]);
    if (hasValue(explicit)) return explicit;
    const predictionYear = firstValue(contract, ["prediction_year"])
      || firstValue(meta, ["prediction_year", "source_year"])
      || firstValue(selectedRow, ["prediction_year", "source_year"]);
    if (hasValue(predictionYear)) return `Data Updated ${predictionYear}`;
    return "Data Updated 2026";
  }
  function sourceDetails(selection, selectedRow, meta) {
    const sourceFile = firstValue(selectedRow, ["source_file", "truth_source_file", "average_harvest_age_source_file"])
      || firstValue(meta, ["truth_source_file", "average_harvest_age_source_file", "harvest_source_file", "age_source_file"]);
    const sourcePage = firstValue(selectedRow, ["page_number", "source_page", "truth_source_page"])
      || firstValue(meta, ["page_number", "source_page", "truth_source_page", "harvest_source_page", "age_source_page"]);
    const tableTitle = firstValue(selectedRow, ["source_table_title", "table_title", "truth_source_table_title"])
      || firstValue(meta, ["source_table_title", "table_title", "truth_source_table_title", "age_source_table_title"]);
    return `
      <details class="uoga-source-details">
        <summary>Source / freshness / model details</summary>
        <div class="uoga-source-grid">
          ${metricRow("Engine mode", window.UOGA_CONFIG?.HUNT_RESEARCH_ENGINE_MODE || "observed")}
          ${metricRow("Data version", window.UOGA_CONFIG?.HUNT_RESEARCH_DATA_VERSION || "not configured")}
          ${metricRow("Data freshness", getFreshnessLabel(meta, meta, selectedRow))}
          ${metricRow("Model version", firstValue(meta, ["model_version"]) || window.UOGA_CONFIG?.HUNT_RESEARCH_MODEL_VERSION || "display-only dashboard")}
          ${metricRow("Rule version", firstValue(meta, ["rule_version"]) || window.UOGA_CONFIG?.HUNT_RESEARCH_RULE_VERSION || "core Research rules")}
          ${metricRow("Selected hunt", `${selection.huntCode} / ${selection.residency} / ${selection.points} pts`)}
          ${metricRow("Source file", formatValue(sourceFile))}
          ${metricRow("Source page", formatValue(sourcePage))}
          ${metricRow("Source table", formatValue(tableTitle))}
        </div>
      </details>`;
  }
  function dashboardHtml(selection, context) {
    const { meta, reference, ladderPoint, selectedRow, managementRows, outlookRow, comparable } = context;
    const contract = outlookRow || {};
    const title = meta?.hunt_name || selectedRow?.hunt_name || reference?.hunt_name || contract.hunt_name || selection.huntCode || "Selected hunt";
    const oddsInfo = getSelectedOddsInfo(selectedRow, ladderPoint, meta, contract);
    const odds = oddsInfo.percent;
    const oddsDisplay = oddsInfo.display;
    const averageAge = getAge(meta, reference, selectedRow) || firstValue(contract, ["average_harvest_age"]);
    const currentAge = getCurrentAge(meta, reference, selectedRow) || firstValue(contract, ["current_age_3yr_average"]);
    const harvestSuccess = getHarvestSuccess(meta, reference, selectedRow) || firstValue(contract, ["harvest_success_pct"]);
    const avgDays = getAverageDays(meta, reference) || firstValue(contract, ["average_days_hunted"]);
    const permitTotal = getPermitTotal(meta, reference, selectedRow) || firstValue(contract, ["permits_2026_total"]);
    const huntType = firstValue(meta, ["hunt_type"]) || firstValue(reference, ["hunt_type"]) || firstValue(selectedRow, ["hunt_type"]) || firstValue(contract, ["hunt_type"]);
    const drawDesign = normalizeDrawDesignLabel(
      firstValue(contract, ["draw_design"])
      || firstValue(meta, ["draw_design", "draw_system_type", "draw_2026_system_type", "draw_family"])
      || firstValue(reference, ["draw_design", "draw_system_type", "draw_2026_system_type", "draw_family"])
      || firstValue(selectedRow, ["draw_design", "draw_system_type", "draw_2026_system_type", "draw_family"])
    );
    const guaranteedLine = getGuaranteedLine(selectedRow, meta) || firstValue(contract, ["guaranteed_line_points"]);
    const pointTrend = getPointTrend(selectedRow, meta) || firstValue(contract, ["point_creep_1yr"]);
    const pointStatus = getPointStatusLabel(selection, selectedRow, meta);
    const percentFivePlus = firstValue(contract, ["percent_5plus"]) || getPercentFivePlus(meta, reference, selectedRow);
    const hasSelectedPointRow = selectedRow && hasValue(selectedRow.hunt_code) && num(selectedRow.points) !== null;
    const sourceBadges = pipeList(contract.source_badges)
      .filter((label) => !(hasSelectedPointRow && label.toLowerCase().includes("status")));
    const statusOnly = isStatusOnlyContext(meta, reference, selectedRow)
      || (!hasSelectedPointRow && pipeList(contract.source_badges).some((item) => item.toLowerCase().includes("status")));
    const highQuality = (num(harvestSuccess) ?? 0) >= 50 || (num(averageAge) ?? 0) >= 5;
    const decision = odds !== null
      ? decisionLabel(odds, { statusOnly, highQuality })
      : (firstValue(contract, ["decision_label"]) || decisionLabel(odds, { statusOnly, highQuality }));
    const recommendation = odds !== null
      ? recommendationSentence(odds, permitTotal, decision)
      : (firstValue(contract, ["recommended_action"]) || recommendationSentence(odds, permitTotal, decision));
    const limitedData = odds === null || !hasValue(harvestSuccess) || !hasValue(averageAge);
    const managementRow = {
      management_objective_type: contract.management_objective_type,
      management_objective_min: "",
      management_objective_max: "",
      objective_unit: contract.management_objective_range,
      objective_status: contract.management_objective_status,
      notes: contract.management_objective_note,
      management_direction: contract.management_direction,
      permit_direction_watch: contract.permit_direction_watch,
      management_objective_note: contract.management_objective_note,
    };
    const effectiveManagementRows = hasValue(contract.management_objective_type) || hasValue(contract.management_objective_status)
      ? [managementRow]
      : managementRows;
    return `
      <div class="uoga-outlook-dashboard">
        <section class="uoga-outlook-hero">
          <div class="uoga-outlook-hero-title">
            <p>Hunt Application Outlook</p>
            <h2>${escapeHtml(selection.huntCode || "No hunt selected")} - ${escapeHtml(title)}</h2>
            <span>${escapeHtml(selection.residency)} &middot; ${escapeHtml(String(selection.points))} points &middot; ${escapeHtml(formatValue(huntType))} &middot; ${escapeHtml(formatValue(drawDesign, "Draw design pending"))}</span>
            <div class="uoga-badge-row">
              ${(sourceBadges.length ? sourceBadges : ["Official DWR Source", "U.O.G.A. Modeled Output"]).map((label) => {
                const lower = label.toLowerCase();
                const variant = lower.includes("official") ? "official"
                  : lower.includes("modeled") ? "modeled"
                    : lower.includes("status") ? "status"
                      : lower.includes("management") ? "management"
                        : "limited";
                return badge(label, variant);
              }).join("")}
              ${badge(getFreshnessLabel(contract, meta, selectedRow), "official")}
              ${badge(`Model ${formatValue(firstValue(contract, ["model_version"]) || firstValue(meta, ["model_version"]) || "v1")}`, "modeled")}
              ${limitedData && !sourceBadges.some((item) => item.toLowerCase().includes("limited")) ? badge("Review / Limited Data", "limited") : ""}
            </div>
          </div>
          ${metricRow("Decision", decision)}
          ${metricRow("Estimated odds", oddsDisplay)}
          ${metricRow("2026 permits", formatInteger(permitTotal))}
          <p class="uoga-outlook-recommendation">${escapeHtml(recommendation)}</p>
        </section>
        <div class="uoga-outlook-grid">
          ${panel("Model-Generated Draw Outlook", `
            ${panelKicker("Model-generated fields")}
            ${listRows([
            metricRow("Estimated draw odds", oddsDisplay),
            metricRow("Point status", formatValue(pointStatus)),
            metricRow("Guaranteed line", formatValue(guaranteedLine)),
            metricRow("Point creep / trend", formatValue(pointTrend)),
            metricRow("Permits", formatInteger(permitTotal)),
            metricRow("Hunt type", formatValue(huntType)),
            metricRow("Draw design", formatValue(drawDesign, "Draw design pending")),
          ])}
          `, "is-modeled")}
          ${panel("Official DWR Field Evidence", `
            ${panelKicker("Official DWR source fields")}
            ${listRows([
            metricRow("Harvest success", formatPercent(harvestSuccess)),
            metricRow("Average days hunted", formatValue(avgDays)),
            metricRow("Average harvest age", formatAge(averageAge)),
            metricRow("Current 3-year age avg", formatAge(currentAge)),
            metricRow("Percent 5+", formatPercent(percentFivePlus)),
          ])}
          `, "is-official")}
          ${renderManagementPanel(effectiveManagementRows)}
        </div>
        ${hasPersonaData(contract) ? `
        <details class="uoga-outlook-panel is-compact uoga-outlook-wide uoga-collapsed-panel">
          <summary>Hunter-Fit Signals</summary>
          <div class="uoga-collapsed-panel-body">${renderPersonaPanel(contract)}</div>
        </details>` : ""}
        <details class="uoga-outlook-panel is-compact uoga-outlook-wide uoga-collapsed-panel">
          <summary>Comparable Hunts</summary>
          <div class="uoga-collapsed-panel-body">${renderComparableCards(comparable)}</div>
        </details>
        ${sourceDetails(selection, selectedRow, { ...(meta || {}), ...contract })}
      </div>`;
  }

  function ensureStyles() {
    if (document.getElementById("uogaOutlookDashboardStyles")) return;
    const style = document.createElement("style");
    style.id = "uogaOutlookDashboardStyles";
    style.textContent = `
      #${DASHBOARD_ID} {
        margin: 12px 0 18px;
        border: 1px solid rgba(124, 77, 38, 0.28);
        border-radius: 22px;
        overflow: hidden;
        min-width: 0;
        background:
          radial-gradient(circle at top left, rgba(240, 120, 0, 0.14), transparent 32%),
          linear-gradient(180deg, rgba(255, 252, 246, 0.96), rgba(244, 233, 219, 0.96));
        color: var(--text);
        box-shadow: 0 18px 42px rgba(70, 43, 20, 0.12);
      }
      .uoga-outlook-dashboard {
        display: grid;
        gap: 14px;
        margin: 18px 0;
        min-width: 0;
        padding: 14px;
      }
      .uoga-outlook-hero {
        align-items: stretch;
        background:
          linear-gradient(180deg, rgba(255,250,242,.96), rgba(246,235,219,.96));
        border: 1px solid rgba(122,76,38,.28);
        border-radius: 18px;
        box-shadow: 0 12px 28px rgba(58,37,18,.10);
        display: grid;
        gap: 12px;
        grid-template-columns: minmax(280px, 1.4fr) repeat(3, minmax(150px, .65fr));
        min-width: 0;
        padding: 16px;
      }
      .uoga-outlook-hero-title {
        min-width: 0;
      }
      .uoga-outlook-hero-title p,
      .uoga-outlook-panel h3,
      .uoga-source-details summary {
        color: #5c2f10;
        font-size: 11px;
        font-weight: 950;
        letter-spacing: .06em;
        text-transform: uppercase;
      }
      .uoga-outlook-hero-title p {
        margin: 0 0 4px;
      }
      .uoga-outlook-hero-title h2,
      .uoga-outlook-hero-title h3 {
        font-family: var(--font-display);
        font-size: clamp(28px, 2vw, 40px);
        line-height: 1;
        margin: 0;
        overflow-wrap: anywhere;
      }
      .uoga-outlook-hero-title span {
        color: #5f4936;
        display: block;
        font-weight: 850;
        margin-top: 6px;
      }
      .uoga-outlook-recommendation {
        align-self: stretch;
        background: rgba(255, 255, 255, .58);
        border: 1px solid rgba(124, 77, 38, 0.15);
        border-radius: 16px;
        color: #2b1c12;
        display: flex;
        flex-direction: column;
        font-weight: 800;
        justify-content: center;
        line-height: 1.38;
        margin: 0;
        padding: 12px;
      }
      .uoga-outlook-grid {
        display: grid;
        gap: 14px;
        grid-template-columns: 1fr 1fr 1fr;
        min-width: 0;
      }
      .uoga-outlook-panel {
        background: rgba(255,253,248,.82);
        border: 1px solid rgba(122,76,38,.22);
        border-radius: 16px;
        box-shadow: 0 8px 20px rgba(58,37,18,.08);
        min-height: auto;
        min-width: 0;
        padding: 14px;
      }
      .uoga-outlook-panel.is-compact {
        min-height: auto;
      }
      .uoga-outlook-panel h3 {
        font-family: var(--font-display);
        margin: 0 0 10px;
      }
      .uoga-panel-kicker {
        color: #7a3f0c;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .05em;
        margin: 0 0 8px;
        text-transform: uppercase;
      }
      .uoga-outlook-wide { grid-column: 1 / -1; }
      .uoga-outlook-metrics {
        display: grid;
        gap: 8px;
      }
      .uoga-outlook-panel .uoga-outlook-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .uoga-outlook-metric {
        background: rgba(255, 248, 238, .72);
        border: 1px solid rgba(124, 77, 38, 0.18);
        border-radius: 13px;
        display: grid;
        gap: 2px;
        padding: 8px 9px;
      }
      .uoga-outlook-metric span {
        color: #7a3f0c;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .04em;
        text-transform: uppercase;
      }
      .uoga-outlook-metric strong {
        color: #24170f;
        font-size: 16px;
        line-height: 1.12;
        overflow-wrap: anywhere;
      }
      .uoga-outlook-metric small,
      .uoga-outlook-muted,
      .uoga-outlook-note {
        color: #5f4936;
        line-height: 1.45;
      }
      .uoga-badge {
        background: rgba(0, 166, 80, .12);
        border: 1px solid rgba(0, 128, 72, .25);
        border-radius: 999px;
        color: #006c3b;
        display: inline-flex;
        font-size: 11px;
        font-weight: 950;
        margin-bottom: 9px;
        padding: 6px 9px;
        text-transform: uppercase;
      }
      .uoga-badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-top: 10px;
      }
      .uoga-badge.is-official {
        background: rgba(33, 99, 132, .12);
        border-color: rgba(33, 99, 132, .26);
        color: #1f5d7c;
      }
      .uoga-badge.is-modeled {
        background: rgba(124, 77, 38, .12);
        border-color: rgba(124, 77, 38, .26);
        color: #5c2f10;
      }
      .uoga-badge.is-limited,
      .uoga-badge.is-status {
        background: rgba(196, 118, 0, .12);
        border-color: rgba(196, 118, 0, .28);
        color: #884f00;
      }
      .uoga-badge.is-management {
        background: rgba(0, 128, 72, .12);
        border-color: rgba(0, 128, 72, .28);
        color: #006c3b;
      }
      .uoga-outlook-note {
        margin: 10px 0 0;
      }
      .uoga-comparable-grid {
        min-width: 0;
        overflow-x: auto;
      }
      .uoga-comparable-table {
        border-collapse: collapse;
        width: 100%;
      }
      .uoga-comparable-table th,
      .uoga-comparable-table td {
        border-bottom: 1px solid rgba(124, 77, 38, 0.13);
        padding: 8px 9px;
        text-align: left;
        vertical-align: top;
      }
      .uoga-comparable-table th {
        color: #5c2f10;
        font-size: 11px;
        font-weight: 950;
        letter-spacing: .05em;
        text-transform: uppercase;
      }
      .uoga-comparable-table td {
        color: #2b1c12;
        font-weight: 800;
      }
      .uoga-comparable-table td span {
        color: #5f4936;
        display: block;
        font-weight: 700;
        margin-top: 2px;
      }
      .uoga-source-details {
        background: rgba(255,253,248,.72);
        border: 1px solid rgba(122,76,38,.22);
        border-radius: 14px;
        margin-top: 4px;
        min-width: 0;
        padding: 12px 14px;
      }
      .uoga-collapsed-panel summary {
        color: #5c2f10;
        cursor: pointer;
        font-family: var(--font-display);
        font-size: 18px;
        font-weight: 800;
        letter-spacing: .02em;
        list-style: none;
        margin: 0;
      }
      .uoga-collapsed-panel summary::-webkit-details-marker {
        display: none;
      }
      .uoga-collapsed-panel summary::after {
        content: "v";
        float: right;
        font-size: 14px;
      }
      .uoga-collapsed-panel[open] summary::after {
        content: "^";
      }
      .uoga-collapsed-panel-body {
        margin-top: 10px;
      }
      .uoga-source-details summary {
        cursor: pointer;
      }
      .uoga-source-details[open] {
        padding-bottom: 12px;
      }
      .uoga-source-grid {
        display: grid;
        gap: 8px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        margin-top: 10px;
      }
      .uoga-source-paths {
        display: none !important;
      }
      @media (max-width: 1220px) {
        .uoga-outlook-hero {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .uoga-outlook-hero-title,
        .uoga-outlook-recommendation {
          grid-column: 1 / -1;
        }
        .uoga-outlook-grid,
        .uoga-source-grid {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 768px) {
        .uoga-outlook-dashboard,
        .uoga-outlook-hero,
        .uoga-outlook-grid,
        .uoga-source-grid,
        .uoga-outlook-panel .uoga-outlook-metrics {
          grid-template-columns: 1fr;
        }
        .uoga-comparable-table {
          min-width: 680px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    const ladder = document.getElementById("pointLadderAccordion");
    const detailContent = document.getElementById("detailContent");
    const parent = ladder?.parentElement || detailContent || document.querySelector(".result-card .card-body") || document.querySelector(".main-stack");
    if (!parent) return null;

    let panel = document.getElementById(DASHBOARD_ID);
    if (!panel) {
      panel = document.createElement("section");
      panel.id = DASHBOARD_ID;
      panel.setAttribute("aria-live", "polite");
    }
    if (ladder && ladder.parentElement) {
      ladder.parentElement.insertBefore(panel, ladder);
    } else if (detailContent && !panel.parentElement) {
      detailContent.insertAdjacentElement("afterend", panel);
    } else if (!panel.parentElement) {
      parent.appendChild(panel);
    }
    return panel;
  }

  function renderLoading(panel, selection) {
    panel.innerHTML = `
      <div class="uoga-outlook-dashboard">
        <section class="uoga-outlook-hero">
          <div class="uoga-outlook-hero-title">
            <p>Hunt Application Outlook</p>
            <h3>${escapeHtml(selection.huntCode || "Selected hunt")}</h3>
            <span>${escapeHtml(selection.residency)} &middot; ${escapeHtml(String(selection.points))} points</span>
          </div>
          <p class="uoga-outlook-recommendation">Loading Research rows for the dashboard display layer.</p>
        </section>
      </div>`;
  }

  async function render() {
    if (!isResearchPage()) return;
    ensureStyles();
    const panel = ensurePanel();
    if (!panel) return;
    if (!state.coreReady && window.UOGA_HUNT_RESEARCH_SNAPSHOT) {
      applyCoreSnapshot(window.UOGA_HUNT_RESEARCH_SNAPSHOT);
    }

    const selection = getSelection();
    if (!selection.huntCode) {
      panel.innerHTML = `
        <div class="uoga-outlook-dashboard">
          <section class="uoga-outlook-hero">
            <div class="uoga-outlook-hero-title">
              <p>Hunt Application Outlook</p>
              <h3>No hunt selected yet</h3>
              <span>Start in Hunt Builder, then return here for decision analysis.</span>
            </div>
            <p class="uoga-outlook-recommendation">Select a hunt in Hunt Builder first. This page is the decision dashboard for that selected hunt.</p>
          </section>
        </div>`;
      return;
    }

    if (!state.coreReady) {
      renderLoading(panel, selection);
      if (state.coreWaitAttempts < 120) {
        state.coreWaitAttempts += 1;
        window.setTimeout(render, 500);
      }
      return;
    }
    state.coreWaitAttempts = 0;
    try {
      await loadData();
      const context = findContext(selection);
      panel.innerHTML = dashboardHtml(selection, context);
    } catch (error) {
      state.error = error && error.message ? error.message : String(error);
      panel.innerHTML = `
        <div class="uoga-outlook-dashboard">
          <section class="uoga-outlook-hero">
            <div class="uoga-outlook-hero-title">
              <p>Hunt Application Outlook</p>
              <h3>${escapeHtml(selection.huntCode)}</h3>
              <span>${escapeHtml(selection.residency)} &middot; ${escapeHtml(String(selection.points))} points</span>
            </div>
            <p class="uoga-outlook-recommendation">${escapeHtml(state.error)}</p>
          </section>
        </div>`;
    }
  }

  function bindRefreshEvents() {
    const snapshotTimer = window.setInterval(() => {
      if (!state.coreReady && window.UOGA_HUNT_RESEARCH_SNAPSHOT) {
        applyCoreSnapshot(window.UOGA_HUNT_RESEARCH_SNAPSHOT);
        render();
      }
      if (state.coreReady) window.clearInterval(snapshotTimer);
    }, 500);
    window.setTimeout(() => window.clearInterval(snapshotTimer), 90000);

    window.addEventListener("uoga:hunt-research-rendered", (event) => {
      applyCoreSnapshot(event.detail);
      window.setTimeout(render, 0);
    });

    ["huntCodeInput", "residencySelect", "drawPoolSelect", "pointsInput", "runResearchButton"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const eventName = id === "runResearchButton" ? "click" : "change";
      el.addEventListener(eventName, () => window.setTimeout(render, 0));
      if (id === "huntCodeInput" || id === "pointsInput") {
        el.addEventListener("input", () => window.setTimeout(render, 120));
      }
    });

    const detail = document.getElementById("detailContent");
    if (detail && window.MutationObserver) {
      const observer = new MutationObserver(() => window.setTimeout(render, 0));
      observer.observe(detail, { attributes: true, attributeFilter: ["hidden"], childList: true, subtree: true });
    }
  }

  function init() {
    bindRefreshEvents();
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
