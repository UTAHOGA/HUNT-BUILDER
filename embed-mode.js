(() => {
  function enforceCanonicalHost() {
    if (typeof window === 'undefined' || !window.location) return;
    const host = String(window.location.hostname || '').toLowerCase();
    const isAltDomain = host === 'hunt-builder.uoga.org';
    if (!isAltDomain) return;
    const target = `https://huntbuilder.uoga.org${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (window.location.href === target) return;
    window.location.replace(target);
  }

  function isEmbedded() {
    try {
      return window.self !== window.top;
    } catch {
      return true;
    }
  }

  function resolveEmbedMode() {
    const params = new URLSearchParams(window.location.search);
    const forced = params.get('embed');
    if (forced === '1' || forced === 'true') return true;
    if (forced === '0' || forced === 'false') return false;
    return isEmbedded();
  }

  function cloudflareFirst(values) {
    if (!Array.isArray(values)) return values;
    const seen = new Set();
    const clean = values.filter(Boolean).filter((value) => {
      const key = String(value);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    return [
      ...clean.filter((value) => /https:\/\/json\.uoga\.workers\.dev/i.test(String(value))),
      ...clean.filter((value) => !/https:\/\/json\.uoga\.workers\.dev/i.test(String(value))),
    ];
  }

  function normalizeResearchSources(config) {
    if (!config || typeof config !== 'object') return config;
    config.HUNT_RESEARCH_ENGINE_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_ENGINE_SOURCES);
    config.HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_OBSERVED_ENGINE_SOURCES);
    config.HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_PREDICTIVE_ENGINE_SOURCES);
    config.HUNT_RESEARCH_LADDER_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_LADDER_SOURCES);
    config.HUNT_RESEARCH_MASTER_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_MASTER_SOURCES);
    config.HUNT_RESEARCH_REFERENCE_SOURCES = cloudflareFirst(config.HUNT_RESEARCH_REFERENCE_SOURCES);
    return config;
  }

  function installConfigNormalizer() {
    const existing = window.UOGA_CONFIG;
    let stored = normalizeResearchSources(existing);
    try {
      Object.defineProperty(window, 'UOGA_CONFIG', {
        configurable: true,
        enumerable: true,
        get() {
          return stored;
        },
        set(value) {
          stored = normalizeResearchSources(value);
        },
      });
    } catch {
      if (existing) window.UOGA_CONFIG = normalizeResearchSources(existing);
    }
  }

  installConfigNormalizer();
  enforceCanonicalHost();

  if (resolveEmbedMode()) {
    document.documentElement.classList.add('embed');
    if (document.body) document.body.classList.add('embed');
  }
})();
