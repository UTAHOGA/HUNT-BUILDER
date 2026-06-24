(() => {
  const CURRENT_YEAR = "2026";
  const MANIFEST_URLS = [
    "./hard-copy/data/documents.json",
    "./public/hard-copy/data/documents.json",
  ];

  const FOLDERS = [
    { id: "rules", title: "UTAH DWR RULES & REGULATIONS", description: "Current-year/current-cycle public rules and regulation PDFs.", icon: "./assets/library-icons/mountain_goat.png" },
    { id: "harvest", title: "HARVEST DATA", description: "Public harvest reports and data across years.", icon: "./assets/library-icons/elk.png" },
    { id: "draw", title: "2026 HUNT DRAW RESULTS", description: "Public 2026 draw results and permit quota PDF documents.", icon: "./assets/library-icons/mule_deer.png" },
    { id: "conservation", title: "CONSERVATION PERMITS", description: "Current-cycle conservation permit references.", icon: "./assets/library-icons/bison.png" },
    { id: "expo", title: "HUNT EXPO", description: "Current-year Hunt Expo permit number references.", icon: "./assets/library-icons/bison.png" },
    { id: "calendar", title: "SIGNIFICANT DATES / CALENDAR", description: "Application windows, deadlines, season dates, and calendar references.", icon: "./assets/library-icons/turkey.png" },
    { id: "units2026", title: "2026 HUNT UNITS / PERMIT NUMBERS", description: "Current 2026 hunt code, hunt name, unit, and permit numbers.", icon: "./assets/library-icons/pronghorn.png" },
    { id: "outfitters", title: "UTAH OUTFITTERS BY HUNT CODE/HUNT NAME", description: "Outfitter resources tied to hunt code and hunt name.", icon: "./assets/library-icons/cougar.png" },
  ];

  const RUNTIME_DENYLIST = [
    "processed_data/hunt_master_enriched.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/draw_reality_engine_v2.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/draw_system_coverage_report.csv",
    "processed_data/predictive_coverage_report.csv",
    "processed_data/model_outputs/",
    "processed_data/audits/",
    "current_to_historical_hunt_code_crosswalk_2026.csv",
    "hard_data_manifest",
    "library_page_data.json",
    "library_page_summary.json",
    "hunt_database_complete.csv",
  ];

  const ALLOWLIST_FILES = [
    "processed_data/hard_data_exports/library/library_page_hunts.csv",
    "processed_data/library/library_page_hunts.csv",
  ];

  const FIXED_PUBLIC_ITEMS = [
    { folderId: "rules", title: "2026 Big Game Application Guidebook", subtitle: "Current-cycle big game application guidebook.", href: "./public/hard-copy/DISPLAY%20DATA/regulations/2026.biggame.app.pdf", type: "pdf", year: "2026", sortOrder: 10 },
    { folderId: "rules", title: "2026 Cougar and Bear Regulations", subtitle: "Current-cycle cougar and bear rules.", href: "./public/hard-copy/DISPLAY%20DATA/regulations/2026.regs.cougar.bear.pdf", type: "pdf", year: "2026", sortOrder: 20 },
    { folderId: "rules", title: "2026 Turkey Regulations", subtitle: "Current-cycle turkey regulations.", href: "./public/hard-copy/DISPLAY%20DATA/regulations/2026.regs.turkey.pdf", type: "pdf", year: "2026", sortOrder: 30 },
    { folderId: "harvest", title: "2025 Harvest Summary (Public)", subtitle: "Public summary workbook for harvest results.", href: "./public/hard-copy/DISPLAY%20DATA/data/2025_harvest_summary_public.xlsx", type: "xlsx", year: "2025", sortOrder: 10 },
    { folderId: "draw", title: "2025 Draw Results Summary (Public)", subtitle: "Public summary workbook for draw outcomes.", href: "./public/hard-copy/DISPLAY%20DATA/data/2025_draw_results_summary_public.xlsx", type: "xlsx", year: "2025", sortOrder: 10 },
    { folderId: "conservation", title: "Unit-Specific Conservation / Expo Bundles", subtitle: "Public workbook with conservation/expo permit bundles by unit.", href: "./public/hard-copy/DISPLAY%20DATA/harvest%20results/unit_specific_conservation_expo_bundles.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
    { folderId: "expo", title: "2026 EXPO Draw Results", subtitle: "Formatted Expo draw results (PDF).", href: "./public/hard-copy/DISPLAY%20DATA/expo%20permits/2026%20EXPO%20DRAW%20RESULTS.pdf", type: "pdf", year: "2026", sortOrder: 10 },
    { folderId: "calendar", title: "2026 Fishing Regulations Calendar Context", subtitle: "Public regulations publication with key timing context.", href: "./public/hard-copy/DISPLAY%20DATA/regulations/2026.regs.fishing.pdf", type: "pdf", year: "2026", sortOrder: 20 },
    { folderId: "units2026", title: "2026 Hunt Units / Permit Numbers", subtitle: "Current 2026 hunt code, hunt unit, and permit workbook.", href: "./public/hard-copy/DISPLAY%20DATA/data/2026_hunt_units_permit_numbers.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
    { folderId: "outfitters", title: "Utah Outfitters by Hunt Code / Hunt Name", subtitle: "Public outfitter workbook tied to hunt code and hunt name.", href: "./public/hard-copy/DISPLAY%20DATA/data/utah_outfitters_by_hunt_code_hunt_name.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
  ];
  const APPROVED_PUBLIC_EXTENSIONS = new Set(["pdf", "xlsx"]);
 const APPROVED_PUBLIC_PATH_PREFIXES = [
  "./public/hard-copy/",
  "/public/hard-copy/",
  "./hard-copy/",
  "/hard-copy/",
  "https://json.uoga.workers.dev/",
  ];
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

  function byId(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value), window.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
    } catch {
      return "#";
    }
  }

  function inferYear(item) {
    const text = `${item.year || ""} ${item.title || ""} ${item.subtitle || ""} ${item.href || ""}`;
    const yearMatch = text.match(/\b(20\d{2})\b/);
    if (yearMatch) return yearMatch[1];
    const cycleMatch = text.match(/\b(20\d{2})-(\d{2})\b/);
    if (cycleMatch) return cycleMatch[1];
    return "";
  }

  function currentCycle(text) {
    return /2026/.test(text) || /2025[-_/ ]?26/.test(text) || /2025[-_/ ]?27/.test(text);
  }

  function toFolderId(item) {
    const hay = `${item.group || ""} ${item.source || ""} ${item.title || ""} ${item.subtitle || ""} ${item.href || ""}`.toLowerCase();
    const hasWord = (term) => new RegExp(`\\b${term}\\b`, "i").test(hay);
    if (hay.includes("outfitter")) return "outfitters";
    if (hay.includes("calendar") || hay.includes("deadline") || hay.includes("season date") || hay.includes("application date")) return "calendar";
    if (hasWord("expo")) return "expo";
    if (hay.includes("conservation")) return "conservation";
    if (hay.includes("harvest")) return "harvest";
    if (hay.includes("draw") || hay.includes("odds") || hay.includes("bonus point")) return "draw";
    if (hay.includes("regulation") || hay.includes("rules") || hay.includes("guidebook") || hay.includes("proclamation") || hay.includes("application")) return "rules";
    if (hay.includes("library_page_hunts")) return "units2026";
    if (hay.includes("hunt units") || hay.includes("permit numbers") || hay.includes("allotment") || hay.includes("hunt_code")) return "units2026";
    return "";
  }

  function decodeSafe(value) {
    try {
      return decodeURIComponent(String(value || ""));
    } catch {
      return String(value || "");
    }
  }

  function hasBlockedInternalToken(value) {
    const text = decodeSafe(String(value || ""));
    return BLOCKED_INTERNAL_PATTERNS.some((pattern) => pattern.test(text));
  }

  function extractExtensionFromHref(href) {
    const cleaned = String(href || "").trim().split("#")[0].split("?")[0];
    const match = cleaned.match(/\.([a-z0-9]+)$/i);
    return match ? String(match[1]).toLowerCase() : "";
  }

  function isApprovedPublicHref(href) {
    const normalized = String(href || "").trim();
    if (!normalized) return false;
    if (!APPROVED_PUBLIC_PATH_PREFIXES.some((prefix) => normalized.startsWith(prefix))) return false;
    if (hasBlockedInternalToken(normalized)) return false;
    const ext = extractExtensionFromHref(normalized);
    return APPROVED_PUBLIC_EXTENSIONS.has(ext);
  }

  function isRuntimeDenied(item) {
    const hay = `${item.href || ""} ${item.local_href || ""} ${item.title || ""} ${item.subtitle || ""} ${item.source || ""}`.toLowerCase();
    return RUNTIME_DENYLIST.some((token) => hay.includes(token.toLowerCase()));
  }

  function isExplicitAllow(item) {
    const hay = `${item.href || ""} ${item.local_href || ""}`.toLowerCase();
    return ALLOWLIST_FILES.some((token) => hay.includes(token.toLowerCase()));
  }

  function passesFolderRules(folderId, item) {
    const hay = `${item.title || ""} ${item.subtitle || ""} ${item.href || ""}`.toLowerCase();
    const year = String(item.year || inferYear(item));
    if (folderId === "rules") return currentCycle(`${hay} ${year}`);
    if (folderId === "conservation") {
      const hasConservationPermit = /conservation[\s-]*permit/.test(hay);
      const isExpo = /\bexpo\b/.test(hay);
      const isDraw = /\bdraw\b|\bdraw result/.test(hay);
      return currentCycle(`${hay} ${year}`) && hasConservationPermit && !isExpo && !isDraw;
    }
    if (folderId === "expo") return year === CURRENT_YEAR || (currentCycle(`${hay} ${year}`) && hay.includes("permit"));
    if (folderId === "units2026") return year === CURRENT_YEAR || isExplicitAllow(item);
    if (folderId === "calendar") return true;
    return true;
  }

  function toPublicItem(raw) {
    const knownFolderIds = new Set(FOLDERS.map((folder) => folder.id));
    const title = String(raw.title || "").trim();
    const href = String(raw.href || raw.local_href || "").trim();
    const type = String(raw.type || "").trim().toLowerCase();
    const subtitle = String(raw.subtitle || "").trim();
    const group = String(raw.group || "").trim().toLowerCase();
    const delivery = String(raw.delivery || "").trim();
    const year = String(raw.year || inferYear(raw)).trim();
    const rawFolderId = String(raw.folderId || raw.folder_id || "").trim();
    const folderId = (rawFolderId && knownFolderIds.has(rawFolderId)) ? rawFolderId : toFolderId(raw);

    if (!title || !href || !folderId) return null;
    if (hasBlockedInternalToken(`${title} ${subtitle} ${raw.source || ""}`)) return null;
    if (!isApprovedPublicHref(href)) return null;
    const inferredExt = extractExtensionFromHref(href);
    if (!APPROVED_PUBLIC_EXTENSIONS.has(inferredExt)) return null;
    if (type === "json") return null;
    if (!["pdf", "xlsx", "iframe", "link"].includes(type)) return null;
    if (type === "csv") return null;
    if (isRuntimeDenied(raw) && !isExplicitAllow(raw)) return null;
    if (!passesFolderRules(folderId, { title, href, subtitle, year })) return null;

    const embedded = type === "iframe" || delivery === "embedded";
    const viewerHref = String(raw.viewer_href || "").trim();
    return {
      id: `${folderId}::${title.toLowerCase()}::${href.toLowerCase()}::${type}`,
      folderId,
      title: title.includes("library_page_hunts")
        ? "2026 Hunt Units / Permit Numbers by Hunt Code and Hunt Name"
        : title,
      subtitle:
        subtitle ||
        (folderId === "units2026"
          ? "Current 2026 hunt code, hunt name, hunt unit, and permit table."
          : "Public hunt-library source file."),
      href,
      type: inferredExt || type,
      year,
      group,
      delivery,
      embedded,
      viewerHref,
      searchText: `${title} ${subtitle} ${href} ${year} ${type} ${group} ${folderId} ${raw.source || ""} ${raw.scope || ""} ${viewerHref}`.toLowerCase(),
      sortOrder: Number(raw.sort_order || raw.sortOrder || 0),
    };
  }

  async function fetchManifest(url) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) return [];
      const text = await response.text();
      const parsed = JSON.parse(String(text || "").replace(/^\uFEFF/, ""));
      if (Array.isArray(parsed)) return parsed;
      if (parsed && Array.isArray(parsed.input_file_status)) return parsed.input_file_status;
      return [];
    } catch {
      return [];
    }
  }

  function resolveHrefCandidates(href) {
    const trimmed = String(href || "").trim();
    const candidates = new Set([trimmed]);
    const publicPrefixDot = "./public/hard-copy/";
    const publicPrefixSlash = "/public/hard-copy/";
    if (trimmed.startsWith(publicPrefixDot)) {
      candidates.add(`./hard-copy/${trimmed.slice(publicPrefixDot.length)}`);
    } else if (trimmed.startsWith(publicPrefixSlash)) {
      candidates.add(`/hard-copy/${trimmed.slice(publicPrefixSlash.length)}`);
    } else if (trimmed.startsWith("./hard-copy/")) {
      candidates.add(`./public/hard-copy/${trimmed.slice("./hard-copy/".length)}`);
    } else if (trimmed.startsWith("/hard-copy/")) {
      candidates.add(`/public/hard-copy/${trimmed.slice("/hard-copy/".length)}`);
    }
    return Array.from(candidates).filter(Boolean);
  }

  async function existsByFetch(url) {
    try {
      const response = await fetch(url, { method: "HEAD", cache: "no-store" });
      if (response.ok) return true;
      if (response.status === 405) {
        const fallback = await fetch(url, { method: "GET", cache: "no-store" });
        return fallback.ok ? true : false;
      }
      return false;
    } catch {
      return null;
    }
  }

  async function filterAvailableItems(items) {
    const checks = await Promise.all(items.map(async (item) => {
      const hrefCandidates = resolveHrefCandidates(item.href);
      let hadUnknown = false;
      for (const candidate of hrefCandidates) {
        const url = safeUrl(candidate);
        if (url === "#") continue;
        const parsed = new URL(url);
        if (parsed.origin !== window.location.origin) {
          return { ...item, href: candidate };
        }
        const exists = await existsByFetch(url);
        if (exists === true) {
          return { ...item, href: candidate };
        }
        if (exists === null) {
          hadUnknown = true;
        }
      }
      if (hadUnknown) return item;
      return null;
    }));
    return checks.filter(Boolean);
  }

  function dedupe(items) {
    const seen = new Map();
    items.forEach((item) => {
      const key = item.id || `${item.folderId || ""}::${String(item.title || "").toLowerCase()}::${String(item.href || "").toLowerCase()}::${String(item.type || "").toLowerCase()}`;
      if (!seen.has(key)) seen.set(key, item);
    });
    return Array.from(seen.values());
  }

  function enforceConservationSingleItem(items) {
    const conservation = items.filter((item) => item.folderId === "conservation");
    if (conservation.length <= 1) return items;

    const scoreItem = (item) => {
      const hay = `${item.title || ""} ${item.subtitle || ""} ${item.href || ""}`.toLowerCase();
      let score = 0;
      if (String(item.delivery || "").toLowerCase() === "pages-local") score += 200;
      if (item.type === "pdf") score += 120;
      if (/2026|2025[-/]27|2025[-/]2027/.test(`${item.year || ""} ${hay}`)) score += 90;
      if (/public\/hard-copy|manual|web/.test(hay)) score += 40;
      if (/\bexpo\b|\bdraw\b/.test(hay)) score -= 300;
      if (item.type === "csv" || item.type === "xlsx") score -= 50;
      return score;
    };

    const best = [...conservation].sort((a, b) => scoreItem(b) - scoreItem(a))[0];
    return items.filter((item) => item.folderId !== "conservation").concat(best);
  }

  function closeEmbed() {
    const panel = byId("uogaEmbedPanel");
    const frame = byId("uogaEmbedFrame");
    if (!panel || !frame) return;
    panel.hidden = true;
    frame.src = "about:blank";
    document.body.classList.remove("uoga-modal-open");
  }

  function openEmbed(item) {
    closePdfFlipbook();
    const panel = byId("uogaEmbedPanel");
    const frame = byId("uogaEmbedFrame");
    const title = byId("uogaEmbedTitle");
    if (!panel || !frame || !title) return;
    title.textContent = item.title || "Embedded Resource";
    frame.src = item.href;
    panel.hidden = false;
    panel.setAttribute("tabindex", "-1");
    document.body.classList.add("uoga-modal-open");
    panel.focus?.({ preventScroll: true });
  }

  function closePdfFlipbook() {
    const panel = byId("uogaPdfFlipPanel");
    const book = byId("uogaPdfFlipbook");
    const status = byId("uogaPdfStatus");
    const download = byId("uogaPdfDownload");
    if (!panel || !book || !status || !download) return;
    book.innerHTML = "";
    panel.hidden = true;
    document.body.classList.remove("uoga-modal-open");
    status.textContent = "Loading...";
    download.href = "#";
  }

  async function openPdfFlipbook(item) {
    closeEmbed();
    const panel = byId("uogaPdfFlipPanel");
    const title = byId("uogaPdfFlipTitle");
    const status = byId("uogaPdfStatus");
    const book = byId("uogaPdfFlipbook");
    const download = byId("uogaPdfDownload");
    if (!panel || !title || !status || !book || !download) return;
    const viewerHref = item.viewerHref || item.href;

    panel.hidden = false;
    document.body.classList.add("uoga-modal-open");
    title.textContent = item.title || "PDF Viewer";
    download.href = safeUrl(viewerHref);
    status.textContent = "In-browser PDF preview";
    const prev = byId("uogaPdfPrev");
    const next = byId("uogaPdfNext");
    if (prev) prev.disabled = true;
    if (next) next.disabled = true;
    book.innerHTML = "";

    try {
      const frame = document.createElement("iframe");
      frame.className = "uoga-pdf-inline-frame";
      frame.loading = "lazy";
      frame.referrerPolicy = "no-referrer-when-downgrade";
      frame.src = safeUrl(viewerHref);
      frame.title = item.title || "PDF Preview";
      book.appendChild(frame);
    } catch (error) {
      document.body.classList.remove("uoga-modal-open");
      status.textContent = "Could not load PDF preview. Use Download Original.";
      book.innerHTML = `<div class="public-empty">${esc(error.message || "PDF preview failed to load")}</div>`;
    }
  }

  function bindStaticControls() {
    const prev = byId("uogaPdfPrev");
    const next = byId("uogaPdfNext");
    const embedClose = byId("uogaEmbedClose");
    const pdfClose = byId("uogaPdfFlipClose");
    const pdfPanel = byId("uogaPdfFlipPanel");
    if (prev) prev.disabled = true;
    if (next) next.disabled = true;
    embedClose?.addEventListener("click", closeEmbed);
    pdfClose?.addEventListener("click", closePdfFlipbook);
    pdfPanel?.querySelector(".uoga-pdf-flip-backdrop")?.addEventListener("click", closePdfFlipbook);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeEmbed();
        closePdfFlipbook();
      }
    });
  }

  function renderFolderButtons(items, state, onFolderClick) {
    const wall = byId("uogaFolderWall");
    if (!wall) return;
    wall.innerHTML = FOLDERS.map((folder) => {
      const count = items.filter((item) => item.folderId === folder.id).length;
      const active = state.activeFolder === folder.id ? "active" : "";
      const label = `${folder.title} (${count} files)`;
      return `
        <button class="public-folder ${active}" type="button" data-folder="${esc(folder.id)}" aria-label="${esc(label)}">
          <span class="public-folder-title">${esc(folder.title)}</span>
          <span class="public-folder-icon" aria-hidden="true">
            <img src="${esc(folder.icon || "./assets/library-icons/mule_deer.png")}" alt="" loading="lazy" />
          </span>
          <span class="public-folder-description">${esc(folder.description)}</span>
          <span class="public-folder-count">${count} file${count === 1 ? "" : "s"}</span>
        </button>
      `;
    }).join("");
    wall.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => onFolderClick(button.dataset.folder || ""));
    });
  }

  function filterItems(items, state) {
    const query = state.query.trim().toLowerCase();
    return items.filter((item) => {
      if (state.activeFolder && item.folderId !== state.activeFolder) return false;
      if (!query) return true;
      const folderTitle = (FOLDERS.find((f) => f.id === item.folderId) || {}).title || "";
      return `${item.searchText} ${folderTitle}`.toLowerCase().includes(query);
    });
  }

  function shouldShowResults(state) {
    return Boolean(state.activeFolder) || state.query.trim().length > 0;
  }

  function renderResults(items, state) {
    const panel = byId("uogaResultsPanel");
    const panelTitle = byId("uogaResultsTitle");
    const panelCount = byId("uogaLibraryCount");
    const chips = byId("uogaActiveFilters");
    const grid = byId("uogaLibrarySections");
    if (!panel || !panelTitle || !panelCount || !chips || !grid) return;

    if (!shouldShowResults(state)) {
      panel.hidden = true;
      panel.setAttribute("aria-hidden", "true");
      chips.innerHTML = "";
      grid.innerHTML = "";
      panelCount.textContent = "0 files";
      closeEmbed();
      closePdfFlipbook();
      return;
    }

    panel.hidden = false;
    panel.setAttribute("aria-hidden", "false");
    panel.setAttribute("tabindex", "-1");
    panelTitle.textContent = state.activeFolder
      ? (FOLDERS.find((f) => f.id === state.activeFolder) || {}).title || "Filtered Results"
      : "Search Results";

    const filtered = filterItems(items, state).sort((a, b) => {
      const sortDelta = Number(a.sortOrder || 0) - Number(b.sortOrder || 0);
      if (sortDelta !== 0) return sortDelta;
      return (b.year || "").localeCompare(a.year || "") || a.title.localeCompare(b.title);
    });
    panelCount.textContent = `${filtered.length} files`;

    const chipsList = [];
    if (state.activeFolder) {
      chipsList.push(`<span class="public-chip">Folder: ${esc((FOLDERS.find((f) => f.id === state.activeFolder) || {}).title || "")}</span>`);
    }
    if (state.query.trim()) {
      chipsList.push(`<span class="public-chip">Search: ${esc(state.query.trim())}</span>`);
    }
    chips.innerHTML = chipsList.join("");

    if (!filtered.length) {
      grid.innerHTML = `<div class="public-empty">No public files match this folder/search.</div>`;
      closeEmbed();
      closePdfFlipbook();
      panel.focus({ preventScroll: true });
      return;
    }

    grid.innerHTML = filtered.map((item, idx) => {
      const delivery = item.delivery ? ` | ${item.delivery}` : "";
      const meta = `${item.type.toUpperCase()}${item.year ? ` | ${item.year}` : ""}${delivery}`;
      const base = `
        <strong>${esc(item.title)}</strong>
        <span>${esc(item.subtitle)}</span>
        <em>${esc(meta)}</em>
      `;

      if (item.type === "pdf") {
        const originalHref = safeUrl(item.href);
        return `
          <div class="public-file-card">
            ${base}
            <div class="public-file-actions">
              <button class="public-file-action" type="button" data-action="flip" data-index="${idx}">View Preview</button>
              <a class="public-file-action" href="${esc(originalHref)}" target="_blank" rel="noopener noreferrer">Download Original</a>
            </div>
          </div>
        `;
      }

      if (item.embedded) {
        return `
          <div class="public-file-card">
            ${base}
            <div class="public-file-actions">
              <button class="public-file-action" type="button" data-action="embed" data-index="${idx}">View Calendar</button>
            </div>
          </div>
        `;
      }

      const href = safeUrl(item.href);
      return `
        <div class="public-file-card">
          ${base}
          <div class="public-file-actions">
            <a class="public-file-action" href="${esc(href)}" target="_blank" rel="noopener noreferrer">Open File</a>
          </div>
        </div>
      `;
    }).join("");

    grid.querySelectorAll("[data-action='flip']").forEach((button) => {
      button.addEventListener("click", () => {
        const idx = Number(button.getAttribute("data-index"));
        if (Number.isFinite(idx) && filtered[idx]) openPdfFlipbook(filtered[idx]);
      });
    });

    grid.querySelectorAll("[data-action='embed']").forEach((button) => {
      button.addEventListener("click", () => {
        const idx = Number(button.getAttribute("data-index"));
        if (Number.isFinite(idx) && filtered[idx]) openEmbed(filtered[idx]);
      });
    });

    panel.focus({ preventScroll: true });
  }

  function start(items) {
    const state = { activeFolder: "", query: "" };
    const search = byId("uogaLibrarySearch");
    const clear = byId("uogaLibraryClear");
    bindStaticControls();

    const renderAll = () => {
      renderFolderButtons(items, state, (folderId) => {
        state.activeFolder = state.activeFolder === folderId ? "" : folderId;
        renderAll();
      });
      renderResults(items, state);
    };

    if (search) {
      search.addEventListener("input", () => {
        state.query = search.value || "";
        renderAll();
      });
    }

    if (clear) {
      clear.addEventListener("click", () => {
        state.query = "";
        state.activeFolder = "";
        if (search) search.value = "";
        renderAll();
      });
    }

    const resultsClose = byId("uogaResultsClose");
    if (resultsClose) {
      resultsClose.addEventListener("click", () => {
        state.query = "";
        state.activeFolder = "";
        if (search) search.value = "";
        closeEmbed();
        closePdfFlipbook();
        renderAll();
      });
    }

    renderAll();
  }

  Promise.all(MANIFEST_URLS.map(fetchManifest))
    .then((allSets) => allSets.flat().map(toPublicItem).filter(Boolean))
    .then((items) => {
      const fixed = FIXED_PUBLIC_ITEMS.map(toPublicItem).filter(Boolean);
      return dedupe([...items, ...fixed]);
    })
    .then((items) => enforceConservationSingleItem(items))
    .then((items) => filterAvailableItems(items))
    .then(start)
    .catch((error) => {
      const panel = byId("uogaResultsPanel");
      const grid = byId("uogaLibrarySections");
      if (panel && grid) {
        panel.hidden = false;
        panel.setAttribute("aria-hidden", "false");
        grid.innerHTML = `<div class="public-empty">Could not load public library manifests: ${esc(error.message)}</div>`;
        return;
      }
      const wall = byId("uogaFolderWall");
      if (wall) {
        wall.innerHTML = `<div class="public-empty">Library failed to initialize: ${esc(error.message)}</div>`;
      }
    });
})();
