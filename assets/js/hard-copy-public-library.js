(() => {
  const CURRENT_YEAR = "2026";
  const MANIFEST_URLS = [
    "./hard-copy/data/documents.json",
    "./public/hard-copy/data/documents.json",
  ];
  const HUNT_INDEX_URLS = [
    "./public/hard-copy/data/library_page_data.json",
    "./public/data/library_page_data.json",
  ];
  const BASKET_KEY = "uoga_hunt_basket_v1";
  const SELECTED_HUNT_KEY = "selected_hunt_code";
  const SELECTED_RESIDENCY_KEY = "selected_hunt_research_residency";
  const SELECTED_POINTS_KEY = "selected_hunt_research_points";
  const SELECTED_DRAW_POOL_KEY = "selected_hunt_research_draw_pool";

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
    { folderId: "rules", title: "2026 Big Game Application Guidebook", subtitle: "Application rules, dates, hunt tables and permit information for Utah big game.", href: "./public/hard-copy/regulations/2026/2026%20Big%20Game%20Application.pdf", type: "pdf", year: "2026", sortOrder: 10 },
    { folderId: "rules", title: "2026 Big Game Field Regulations Guidebook", subtitle: "Field regulations, season dates, legal methods and Utah big game unit information.", href: "./public/hard-copy/regulations/2026/2026%20Big%20Game%20Field%20Regulations.pdf", type: "pdf", year: "2026", sortOrder: 20 },
    { folderId: "rules", title: "2026 Antlerless Application Guidebook", subtitle: "Application rules, hunt tables and permit information for antlerless big game.", href: "./public/hard-copy/regulations/2026/2026%20Antlerless%20Application%20Guidebook.pdf", type: "pdf", year: "2026", sortOrder: 30 },
    { folderId: "rules", title: "2026 Black Bear, Cougar & Furbearer Guidebook", subtitle: "Utah hunting, pursuit and trapping regulations for black bear, cougar and furbearers.", href: "./public/hard-copy/regulations/2026/2026%20Black%20Bear%20Cougar%20and%20Furbearer%20Guidebook.pdf", type: "pdf", year: "2026", sortOrder: 40 },
    { folderId: "rules", title: "2026-27 Waterfowl, Upland Game & Turkey Guidebook", subtitle: "Current Utah regulations for waterfowl, upland game, turkey and small game.", href: "./public/hard-copy/regulations/2026/2026%20Waterfowl%20Upland%20Game%20and%20Turkey%20Guidebook.pdf", type: "pdf", year: "2026", sortOrder: 50 },
    { folderId: "rules", title: "2026 Fishing Guidebook", subtitle: "Utah fishing laws, methods, limits and rules for specific waters.", href: "./public/hard-copy/regulations/2026/2026%20Fishing%20Guidebook.pdf", type: "pdf", year: "2026", sortOrder: 60 },
    { folderId: "harvest", title: "2025 Harvest Summary (Public)", subtitle: "Public summary workbook for harvest results.", href: "./public/hard-copy/DISPLAY%20DATA/data/2025_harvest_summary_public.xlsx", type: "xlsx", year: "2025", sortOrder: 10 },
    { folderId: "draw", title: "2025 Draw Results Summary (Public)", subtitle: "Public summary workbook for draw outcomes.", href: "./public/hard-copy/DISPLAY%20DATA/data/2025_draw_results_summary_public.xlsx", type: "xlsx", year: "2025", sortOrder: 10 },
    { folderId: "conservation", title: "Unit-Specific Conservation / Expo Bundles", subtitle: "Public workbook with conservation/expo permit bundles by unit.", href: "./public/hard-copy/DISPLAY%20DATA/harvest%20results/unit_specific_conservation_expo_bundles.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
    { folderId: "expo", title: "2026 EXPO Draw Results", subtitle: "Formatted Expo draw results (PDF).", href: "./public/hard-copy/DISPLAY%20DATA/expo%20permits/2026%20EXPO%20DRAW%20RESULTS.pdf", type: "pdf", year: "2026", sortOrder: 10 },
    { folderId: "calendar", title: "Utah DWR Significant Dates & 2026 Hunt Seasons", subtitle: "Official DWR events plus 1,358 published season ranges for 1,115 Hunt Planner hunt codes.", href: "./hunt-calendar-2026.html", type: "iframe", delivery: "embedded", year: "2026", sortOrder: 10 },
    { folderId: "units2026", title: "2026 Hunt Units / Permit Numbers", subtitle: "Current 2026 hunt code, hunt unit, and permit workbook.", href: "./public/hard-copy/DISPLAY%20DATA/data/2026_hunt_units_permit_numbers.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
    { folderId: "outfitters", title: "Utah Outfitters by Hunt Code / Hunt Name", subtitle: "Public outfitter workbook tied to hunt code and hunt name.", href: "./public/hard-copy/DISPLAY%20DATA/data/utah_outfitters_by_hunt_code_hunt_name.xlsx", type: "xlsx", year: "2026", sortOrder: 10 },
  ];
  const PUBLIC_HUNT_LIBRARY_PDF_PATHS = [
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/ANTLERLESS_DEER_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/ANTLERLESS_ELK_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/ANTLERLESS_MOOSE_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/ANTLERLESS_PERMIT_QUOTA_SUMMARY__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/BEAR_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/BEAR_RESTRICTED_PURSUIT_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/DOE_PRONGHORN_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/D_H_DEER_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/EWE_ROCKY_MTN_SHEEP_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/G_S_BUCK_DEER_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/L_E_BUCK_DEER_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/L_E_BUCK_PRONGHORN_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/L_E_BULL_ELK_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/O_I_L_BISON_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/O_I_L_BULL_MOOSE_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/O_I_L_DESERT_BIGHORN_SHEEP_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/O_I_L_MTN_GOAT_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/O_I_L_ROCKY_MTN_SHEEP_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/SPORTSMAN_DRAW_RESULTS_CONSOLIDATED_FIXED_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 HUNT DRAW RESULTS/YOUTH_ELK_DRAW_RESULTS__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/EXPO PERMITS/2026 EXPO DRAW RESULTS.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/ANTLERLESS_DEER_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/ANTLERLESS_ELK_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/ANTLERLESS_MOOSE_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/ANTLERLESS_PERMIT_QUOTA_SUMMARY__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/DOE_PRONGHORN_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
    "public/hard-copy/HUNT LIBRARY/2026 PERMITS/PERMIT QUOTAS = HUNT NAME + HUNT CODE/EWE_ROCKY_MTN_SHEEP_PERMIT_QUOTA__FIXED_DROPDOWN_NARROW_DROPDOWN.pdf",
  ];
  const PUBLIC_HUNT_LIBRARY_ITEMS = PUBLIC_HUNT_LIBRARY_PDF_PATHS.map((rel, index) => ({
    folderId: folderIdForLibraryPdfPath(rel),
    title: titleFromLibraryPdfPath(rel),
    subtitle: subtitleForLibraryPdfPath(rel),
    href: `./${rel}`,
    type: "pdf",
    year: "2026",
    sortOrder: 100 + index,
  }));
  const APPROVED_PUBLIC_EXTENSIONS = new Set(["pdf", "xlsx"]);
  const APPROVED_PUBLIC_EMBED_ORIGINS = new Set([
    "https://www.google.com",
    "https://calendar.google.com",
  ]);
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

  function titleFromLibraryPdfPath(rel) {
    const fileName = String(rel || "").split("/").pop() || "";
    return fileName
      .replace(/\.pdf$/i, "")
      .replace(/__FIXED_DROPDOWN_NARROW_DROPDOWN$/i, "")
      .replace(/_FIXED_NARROW_DROPDOWN$/i, "")
      .replace(/_/g, " ")
      .replace(/\bO I L\b/g, "O.I.L.")
      .replace(/\bL E\b/g, "L.E.")
      .replace(/\bD H\b/g, "D.H.")
      .replace(/\bG S\b/g, "G.S.")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (match) => match.toUpperCase());
  }

  function folderIdForLibraryPdfPath(rel) {
    const lower = String(rel || "").toLowerCase();
    if (lower.includes("/regulations/")) return "rules";
    if (lower.includes("expo permits")) return "expo";
    if (lower.includes("permit quotas")) return "units2026";
    return "draw";
  }

  function subtitleForLibraryPdfPath(rel) {
    const lower = String(rel || "").toLowerCase();
    if (lower.includes("/regulations/")) return "Parent rules PDF.";
    if (lower.includes("expo permits")) return "Parent Expo permit PDF.";
    if (lower.includes("permit quotas")) return "Parent permit-quota PDF by hunt code and hunt name.";
    return "Parent draw-results PDF.";
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

  function pdfViewerUrl(value) {
    const href = safeUrl(value);
    if (href === "#") return href;
    const url = new URL(href);
    url.hash = "zoom=100";
    return url.href;
  }

  function isApprovedPublicEmbedHref(href) {
    try {
      const url = new URL(String(href || ""), window.location.origin);
      if (url.origin === window.location.origin && url.pathname.endsWith("/hunt-calendar-2026.html")) return true;
      return APPROVED_PUBLIC_EMBED_ORIGINS.has(url.origin) && url.pathname.startsWith("/calendar/embed");
    } catch {
      return false;
    }
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
    const inferredExt = extractExtensionFromHref(href);
    if (type === "json") return null;
    if (!["pdf", "xlsx", "iframe", "link"].includes(type)) return null;
    if (type === "csv") return null;
    if (type === "iframe") {
      if (!isApprovedPublicEmbedHref(href)) return null;
    } else {
      if (!isApprovedPublicHref(href)) return null;
      if (!APPROVED_PUBLIC_EXTENSIONS.has(inferredExt)) return null;
    }
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
      type: type === "iframe" ? "iframe" : (inferredExt || type),
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

  async function fetchHuntIndex(url) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) return [];
      const text = await response.text();
      const parsed = JSON.parse(String(text || "").replace(/^\uFEFF/, ""));
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  async function loadHuntIndex() {
    for (const url of HUNT_INDEX_URLS) {
      const rows = await fetchHuntIndex(url);
      if (rows.length) return rows;
    }
    return [];
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
    if (panel.parentElement !== document.body) {
      document.body.appendChild(panel);
    }
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
    if (!panel || !book || !status) return;
    book.innerHTML = "";
    panel.hidden = true;
    document.body.classList.remove("uoga-modal-open");
    status.textContent = "Loading...";
  }

  async function openPdfFlipbook(item) {
    closeEmbed();
    const panel = byId("uogaPdfFlipPanel");
    const title = byId("uogaPdfFlipTitle");
    const status = byId("uogaPdfStatus");
    const book = byId("uogaPdfFlipbook");
    if (!panel || !title || !status || !book) return;
    const viewerHref = item.viewerHref || item.href;

    if (panel.parentElement !== document.body) {
      document.body.appendChild(panel);
    }
    panel.hidden = false;
    document.body.classList.add("uoga-modal-open");
    title.textContent = item.title || "PDF Viewer";
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
      frame.src = pdfViewerUrl(viewerHref);
      frame.title = item.title || "PDF Preview";
      book.appendChild(frame);
    } catch (error) {
      document.body.classList.remove("uoga-modal-open");
      status.textContent = "Could not load PDF preview.";
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

  function normalizeHuntCode(value) {
    return String(value || "").trim().toUpperCase().replace(/\s+/g, "").replace(/[^A-Z0-9]/g, "");
  }

  function rowText(row) {
    return [
      row?.hunt_code,
      row?.species,
      row?.hunt_name,
      row?.unit,
      row?.weapon,
      row?.classification,
      row?.final_state,
      row?.model_version,
    ].map((value) => String(value || "")).join(" ").toLowerCase();
  }

  function pdfScope(item) {
    const raw = `${item.title || ""} ${item.subtitle || ""} ${item.href || ""} ${item.folderId || ""}`.toLowerCase();
    const hay = raw.replace(/[_./-]+/g, " ").replace(/\s+/g, " ").trim();
    const bigGameSpecies = ["bison", "deer", "elk", "moose", "mountain goat", "pronghorn", "rocky mountain bighorn sheep", "desert bighorn sheep", "bighorn sheep"];
    if (hay.includes("antlerless deer")) return { species: ["deer"], include: ["antlerless", "da"] };
    if (hay.includes("antlerless elk")) return { species: ["elk"], include: ["antlerless", "ea"] };
    if (hay.includes("antlerless moose")) return { species: ["moose"], include: ["antlerless", "cow", "moose"] };
    if (hay.includes("doe pronghorn")) return { species: ["pronghorn"], include: ["doe", "antlerless", "pd"] };
    if (hay.includes("ewe rocky")) return { species: ["rocky mountain bighorn sheep", "bighorn sheep"], include: ["ewe", "rs"] };
    if (hay.includes("bear restricted pursuit")) return { species: ["black bear"], include: ["pursuit"] };
    if (hay.includes("bear draw")) return { species: ["black bear"], exclude: ["pursuit"] };
    if (hay.includes("youth elk")) return { species: ["elk"], include: ["youth"] };
    if (hay.includes("sportsman")) return { species: [...bigGameSpecies, "black bear", "cougar", "turkey"], include: ["sportsman"] };
    if (hay.includes("d h deer")) return { species: ["deer"], include: ["dedicated", "d h"] };
    if (hay.includes("g s buck deer")) return { species: ["deer"], include: ["general", "buck", "g s"] };
    if (hay.includes("l e buck deer")) return { species: ["deer"], include: ["limited", "premium", "buck", "db"] };
    if (hay.includes("l e bull elk")) return { species: ["elk"], include: ["limited", "bull", "eb"] };
    if (hay.includes("l e buck pronghorn")) return { species: ["pronghorn"], include: ["limited", "buck", "pb"] };
    if (hay.includes("o i l bison")) return { species: ["bison"] };
    if (hay.includes("o i l bull moose")) return { species: ["moose"], include: ["bull", "moose"] };
    if (hay.includes("o i l desert bighorn sheep")) return { species: ["desert bighorn sheep"] };
    if (hay.includes("o i l mtn goat")) return { species: ["mountain goat"] };
    if (hay.includes("o i l rocky mtn sheep")) return { species: ["rocky mountain bighorn sheep"] };
    if (hay.includes("antlerless guidebook")) return { species: ["deer", "elk", "moose", "pronghorn", "rocky mountain bighorn sheep", "bighorn sheep"], include: ["antlerless", "doe", "ewe", "cow"] };
    if (hay.includes("turkey")) return { species: ["turkey"] };
    if (hay.includes("cougar") || hay.includes("bear")) return { species: ["cougar", "black bear"] };
    if (hay.includes("big game")) return { species: bigGameSpecies };
    if (hay.includes("permit quota summary")) return { species: ["deer", "elk", "moose", "pronghorn", "rocky mountain bighorn sheep", "bighorn sheep"], include: ["antlerless", "doe", "ewe", "cow"] };
    if (hay.includes("permit") || hay.includes("unit") || hay.includes("draw")) return { species: [...bigGameSpecies, "black bear", "cougar", "turkey"] };
    return { species: [] };
  }

  function matchesPdfScope(item, row) {
    const scope = pdfScope(item);
    if (!scope.species.length) return false;
    const species = String(row?.species || "").trim().toLowerCase();
    if (!scope.species.includes(species)) return false;
    const text = rowText(row);
    const code = normalizeHuntCode(row?.hunt_code).toLowerCase();
    const searchable = `${text} ${code}`;
    if (Array.isArray(scope.include) && scope.include.length && !scope.include.some((term) => searchable.includes(term))) return false;
    if (Array.isArray(scope.exclude) && scope.exclude.length && scope.exclude.some((term) => searchable.includes(term))) return false;
    return true;
  }

  function inferMatrixBucket(row) {
    const code = normalizeHuntCode(row?.hunt_code);
    const species = String(row?.species || "").trim();
    const lowerSpecies = species.toLowerCase();
    const text = rowText(row).toUpperCase();
    if (text.includes("CWMU")) return "CWMU";
    if (text.includes("PRIVATE LAND") || text.includes("PRIVATE_LANDS") || text.includes("OTC") || text.includes("HARVEST OBJECTIVE") || text.includes("PURSUIT")) return "OVER THE COUNTER";
    if (text.includes("ANTLERLESS") || /^EA|^DA|^PD/.test(code)) return "ANTLERLESS";
    if (lowerSpecies === "turkey") return text.includes("YOUTH") ? "TURKEY YOUTH" : "TURKEY";
    if (lowerSpecies === "cougar") return "COUGAR";
    if (lowerSpecies === "black bear") return text.includes("PURSUIT") ? "BEAR PURSUIT" : "BEAR";
    if (["bison", "moose", "mountain goat", "rocky mountain bighorn sheep", "desert bighorn sheep", "bighorn sheep"].includes(lowerSpecies)) return "O.I.L.";
    if (lowerSpecies === "deer" && (text.includes("PREMIUM") || /^DB1/.test(code))) return "P.L.E. / L.E. DEER";
    if (["deer", "elk", "pronghorn"].includes(lowerSpecies)) return "L.E. BIG GAME";
    return "MATRIX REVIEW";
  }

  function buildPdfResearchGroups(item, huntRows) {
    if (item.type !== "pdf" || !huntRows.length) return [];
    const rows = huntRows
      .filter((row) => normalizeHuntCode(row?.hunt_code) && matchesPdfScope(item, row))
      .sort((a, b) => inferMatrixBucket(a).localeCompare(inferMatrixBucket(b)) || String(a.species || "").localeCompare(String(b.species || "")) || normalizeHuntCode(a.hunt_code).localeCompare(normalizeHuntCode(b.hunt_code)));
    const grouped = new Map();
    rows.forEach((row) => {
      const bucket = inferMatrixBucket(row);
      if (!grouped.has(bucket)) grouped.set(bucket, []);
      grouped.get(bucket).push(row);
    });
    return Array.from(grouped.entries()).map(([bucket, bucketRows]) => ({ bucket, rows: bucketRows }));
  }

  function researchUrlFor(row) {
    const params = new URLSearchParams({
      hunt_code: normalizeHuntCode(row?.hunt_code),
      residency: "Resident",
      points: "12",
      draw_pool: "standard",
    });
    return `./research.html?${params.toString()}`;
  }

  function builderUrlFor(row) {
    return `./builder.html?hunt_code=${encodeURIComponent(normalizeHuntCode(row?.hunt_code))}`;
  }

  function renderHuntMiniRow(row) {
    const code = normalizeHuntCode(row?.hunt_code);
    const title = [row?.species, row?.hunt_name || row?.unit].filter(Boolean).join(" | ") || "Hunt";
    const meta = [row?.weapon, row?.permits_2026 ? `${row.permits_2026} permits` : "", row?.final_state].filter(Boolean).join(" | ");
    return `
      <div class="pdf-hunt-row">
        <div>
          <strong>${esc(code)}</strong>
          <span>${esc(title)}</span>
          ${meta ? `<em>${esc(meta)}</em>` : ""}
        </div>
        <div class="pdf-hunt-actions">
          <button class="public-file-action" type="button" data-action="backpack" data-hunt-code="${esc(code)}">Backpack</button>
          <a class="public-file-action" href="${esc(researchUrlFor(row))}">Research</a>
          <a class="public-file-action" href="${esc(builderUrlFor(row))}">Builder</a>
        </div>
      </div>
    `;
  }

  function renderPdfResearchDrawer(item, huntRows) {
    const groups = buildPdfResearchGroups(item, huntRows);
    if (!groups.length) return "";
    const total = groups.reduce((sum, group) => sum + group.rows.length, 0);
    const groupHtml = groups.map((group, groupIndex) => {
      const visibleRows = group.rows.slice(0, 18);
      const overflow = group.rows.length - visibleRows.length;
      return `
        <details class="pdf-research-category"${groupIndex === 0 ? " open" : ""}>
          <summary>
            <span>${esc(group.bucket)}</span>
            <b>${group.rows.length} hunt${group.rows.length === 1 ? "" : "s"}</b>
          </summary>
          <div class="pdf-hunt-list">
            ${visibleRows.map(renderHuntMiniRow).join("")}
            ${overflow > 0 ? `<div class="pdf-hunt-more">${overflow} more. Use search to narrow.</div>` : ""}
          </div>
        </details>
      `;
    }).join("");

    return `
      <details class="public-pdf-research">
        <summary>
          <span>PDF Research</span>
          <b>${total} linked hunt${total === 1 ? "" : "s"}</b>
        </summary>
        <div class="pdf-parent-row">
          <span>Parent PDF</span>
          <strong>${esc(item.title)}</strong>
        </div>
        <div class="pdf-research-groups">${groupHtml}</div>
      </details>
    `;
  }

  function loadBackpack() {
    try {
      const parsed = JSON.parse(localStorage.getItem(BASKET_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveHuntToBackpack(row) {
    const code = normalizeHuntCode(row?.hunt_code);
    if (!code) return false;
    const payload = {
      hunt_code: code,
      hunt_name: row?.hunt_name || row?.unit || "",
      species: row?.species || "",
      weapon: row?.weapon || "",
      residency: "Resident",
      draw_pool: "standard",
      selected_points: 12,
      updated_at: Date.now(),
    };
    try {
      localStorage.setItem("selectedHuntForResearch", JSON.stringify(payload));
      sessionStorage.setItem("selectedHuntForResearch", JSON.stringify(payload));
      localStorage.setItem(SELECTED_HUNT_KEY, code);
      localStorage.setItem(SELECTED_RESIDENCY_KEY, "Resident");
      localStorage.setItem(SELECTED_DRAW_POOL_KEY, "standard");
      localStorage.setItem(SELECTED_POINTS_KEY, "12");
      const next = loadBackpack().filter((item) => normalizeHuntCode(item?.hunt_code) !== code);
      next.unshift(payload);
      localStorage.setItem(BASKET_KEY, JSON.stringify(next.slice(0, 24)));
      return true;
    } catch {
      return false;
    }
  }

  function resourceKeyFor(item) {
    const raw = `${item?.title || ""} ${item?.href || ""}`.toUpperCase();
    const slug = raw.replace(/[^A-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 56);
    return `LIBRARY:${slug || "RESOURCE"}`;
  }

  function saveLibraryResourceToBackpack(item) {
    if (!item?.href) return false;
    const key = resourceKeyFor(item);
    const payload = {
      hunt_code: key,
      huntCode: key,
      hunt_name: item.title || "Hunt Library Resource",
      unit: item.subtitle || "",
      species: item.type === "pdf" ? "Library PDF" : "Library Resource",
      weapon: item.year ? `${item.year}` : "",
      hunt_type: "Hunt Library",
      hunt_class: "Reference",
      draw_pool: "library",
      source: "hunt-library",
      resource_type: item.type === "pdf" ? "library_pdf_map" : "library_file",
      resource_title: item.title || "Hunt Library Resource",
      resource_href: item.viewerHref || item.href,
      resource_file_type: item.type || "",
      updated_at: Date.now(),
    };
    try {
      if (window.UOGA_UI?.getBasket && window.UOGA_UI?.setBasket) {
        const current = window.UOGA_UI.getBasket();
        const next = current.filter((entry) => String(entry?.hunt_code || "").toUpperCase() !== key);
        window.UOGA_UI.setBasket([payload, ...next]);
      } else {
        const next = loadBackpack().filter((entry) => String(entry?.hunt_code || "").toUpperCase() !== key);
        next.unshift(payload);
        localStorage.setItem(BASKET_KEY, JSON.stringify(next.slice(0, 24)));
        document.dispatchEvent(new CustomEvent("uoga:backpack-changed"));
      }
      return true;
    } catch {
      return false;
    }
  }

  function renderResults(items, state, huntRows, huntByCode) {
    const panel = byId("uogaResultsPanel");
    const panelTitle = byId("uogaResultsTitle");
    const panelCount = byId("uogaLibraryCount");
    const chips = byId("uogaActiveFilters");
    const grid = byId("uogaLibrarySections");
    if (!panel || !panelTitle || !panelCount || !chips || !grid) return;

    if (!shouldShowResults(state)) {
      document.body.classList.remove("library-results-open");
      panel.hidden = true;
      panel.setAttribute("aria-hidden", "true");
      chips.innerHTML = "";
      grid.innerHTML = "";
      panelCount.textContent = "0 files";
      closeEmbed();
      closePdfFlipbook();
      return;
    }

    document.body.classList.add("library-results-open");
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
        const pdfResearch = renderPdfResearchDrawer(item, huntRows);
        return `
          <div class="public-file-card">
            ${base}
            <div class="public-file-actions">
              <button class="public-file-action" type="button" data-action="flip" data-index="${idx}">Open PDF Preview</button>
              <button class="public-file-action" type="button" data-action="backpack-resource" data-index="${idx}">Backpack Map</button>
            </div>
            ${pdfResearch}
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

      return `
        <div class="public-file-card">
          ${base}
          <div class="public-file-actions">
            <button class="public-file-action public-file-action--disabled" type="button" disabled>PDF Preview Only</button>
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

    grid.querySelectorAll("[data-action='backpack-resource']").forEach((button) => {
      button.addEventListener("click", () => {
        const idx = Number(button.getAttribute("data-index"));
        if (!Number.isFinite(idx) || !filtered[idx]) return;
        if (saveLibraryResourceToBackpack(filtered[idx])) {
          button.textContent = "Saved";
          button.setAttribute("aria-label", `${filtered[idx].title || "Library resource"} saved to Hunt Backpack`);
        }
      });
    });

    grid.querySelectorAll("[data-action='backpack']").forEach((button) => {
      button.addEventListener("click", () => {
        const code = normalizeHuntCode(button.getAttribute("data-hunt-code"));
        const row = huntByCode.get(code);
        if (!row) return;
        if (saveHuntToBackpack(row)) {
          button.textContent = "Saved";
          button.setAttribute("aria-label", `${code} saved to Hunt Backpack`);
        }
      });
    });

    panel.focus({ preventScroll: true });
  }

  function start(items, huntRows) {
    const state = { activeFolder: "", query: "" };
    const huntByCode = new Map();
    huntRows.forEach((row) => {
      const code = normalizeHuntCode(row?.hunt_code);
      if (code && !huntByCode.has(code)) huntByCode.set(code, row);
    });
    const search = byId("uogaLibrarySearch");
    const clear = byId("uogaLibraryClear");
    bindStaticControls();

    const renderAll = () => {
      renderFolderButtons(items, state, (folderId) => {
        state.activeFolder = state.activeFolder === folderId ? "" : folderId;
        renderAll();
      });
      renderResults(items, state, huntRows, huntByCode);
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

  Promise.all([Promise.all(MANIFEST_URLS.map(fetchManifest)), loadHuntIndex()])
    .then(([allSets, huntRows]) => {
      const items = allSets.flat().map(toPublicItem).filter(Boolean);
      const fixed = [...FIXED_PUBLIC_ITEMS, ...PUBLIC_HUNT_LIBRARY_ITEMS].map(toPublicItem).filter(Boolean);
      return { items: dedupe([...items, ...fixed]), huntRows };
    })
    .then(({ items, huntRows }) => ({ items: enforceConservationSingleItem(items), huntRows }))
    .then(({ items, huntRows }) => filterAvailableItems(items).then((availableItems) => ({ items: availableItems, huntRows })))
    .then(({ items, huntRows }) => start(items, huntRows))
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
