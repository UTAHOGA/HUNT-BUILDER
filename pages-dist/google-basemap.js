(() => {
  const STORAGE_KEY = 'uoga_google_basemap_type_v2';
  const DEFAULT_TYPE = 'terrain';
  const VALID_TYPES = new Set(['roadmap', 'terrain', 'hybrid', 'satellite']);
  let lastMode = '';

  const CROP_BASEMAP_PANEL_ON_SELECT = true;

  function getMapTypeSelect() {
    return document.getElementById('mapTypeSelect');
  }

  function getPopover() {
    return document.getElementById('basemapPopover');
  }

  function getToggleBtn() {
    return document.getElementById('basemapToggleBtn');
  }

  function getNativeMapSelect() {
    return document.getElementById('mapTypeSelect');
  }

  function sanitizeNativeMapSelect() {
    const sel = getNativeMapSelect();
    if (!sel) return;
    sel.removeAttribute('aria-hidden');
    sel.removeAttribute('tabindex');
    sel.hidden = true;
  }

  function getPanel() {
    return document.getElementById('globeBasemapPanel');
  }

  function readPreferredType() {
    const raw = (localStorage.getItem(STORAGE_KEY) || '').trim();
    return VALID_TYPES.has(raw) ? raw : DEFAULT_TYPE;
  }

  function writePreferredType(nextType) {
    if (!VALID_TYPES.has(nextType)) return;
    localStorage.setItem(STORAGE_KEY, nextType);
  }

  function isGoogleMode() {
    const sel = getMapTypeSelect();
    return (sel && sel.value === 'google') || false;
  }

  function isEarthMode() {
    const sel = getMapTypeSelect();
    return (sel && sel.value === 'earth') || false;
  }

  function shouldShowPopover() {
    return isGoogleMode();
  }

  function getMode() {
    if (isGoogleMode()) return 'google';
    if (isEarthMode()) return 'earth';
    return 'dwr';
  }

  function applyToGoogleMap() {
    if (!isGoogleMode()) return;
    const preferred = readPreferredType();
    const map = window.googleBaselineMap;
    if (map && typeof map.setMapTypeId === 'function') {
      map.setMapTypeId(preferred);
      if (typeof map.setTilt === 'function') {
        map.setTilt(0);
      }
      if (typeof map.setHeading === 'function') {
        map.setHeading(0);
      }
    }
  }

  function syncGoogleButtons() {
    const preferred = readPreferredType();
    document.querySelectorAll('#googleBasemapGrid [data-google-basemap]').forEach((btn) => {
      const t = btn.getAttribute('data-google-basemap');
      const active = t === preferred;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function setPanelOpen(nextOpen) {
    const popover = getPopover();
    const btn = getToggleBtn();
    const panel = getPanel();
    const open = !!nextOpen;

    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (panel) {
      panel.setAttribute('aria-hidden', open ? 'false' : 'true');
      panel.hidden = !open;
      // Prevent focus from remaining inside a hidden panel (Chrome warns about aria-hidden on focused descendants).
      // inert is supported in modern Chromium and is a no-op elsewhere.
      if (open) {
        panel.removeAttribute('inert');
      } else {
        panel.setAttribute('inert', '');
        const active = document.activeElement;
        if (active && panel.contains(active) && btn) {
          btn.focus({ preventScroll: true });
        }
      }
    }
    if (popover) popover.dataset.open = open ? 'true' : 'false';
  }

  function isPanelOpen() {
    const btn = getToggleBtn();
    return btn ? btn.getAttribute('aria-expanded') === 'true' : false;
  }

  function closePanel() {
    setPanelOpen(false);
  }

  function syncModeVisibility() {
    const popover = getPopover();
    if (!popover) return;
    const mode = getMode();
    const show = shouldShowPopover();
    popover.setAttribute('aria-hidden', show ? 'false' : 'true');
    popover.hidden = !show;
    if (!show) closePanel();

    const panel = getPanel();
    if (panel) {
      panel.dataset.mapMode = isGoogleMode() ? 'google' : 'hidden';
    }

    const googleGrid = document.getElementById('googleBasemapGrid');
    if (googleGrid) googleGrid.style.opacity = '1';
    if (mode !== 'google') {
      setPanelOpen(false);
    }
    lastMode = mode;
  }

  function onToggleClick(e) {
    e.preventDefault();
    e.stopPropagation();
    setPanelOpen(!isPanelOpen());
  }

  function onDocClick(e) {
    if (!isPanelOpen()) return;
    const popover = getPopover();
    if (!popover) return;
    if (!popover.contains(e.target)) closePanel();
  }

  function onKeyDown(e) {
    if (e.key !== 'Escape') return;
    if (!isPanelOpen()) return;
    closePanel();
  }

  function onBasemapClick(e) {
    const googleBtn = e.target && e.target.closest ? e.target.closest('[data-google-basemap]') : null;
    if (googleBtn) {
      const nextType = googleBtn.getAttribute('data-google-basemap');
      if (!VALID_TYPES.has(nextType)) return;
      writePreferredType(nextType);
      syncGoogleButtons();
      applyToGoogleMap();
      if (CROP_BASEMAP_PANEL_ON_SELECT) closePanel();
      return;
    }

  }

  function onMapTypeChange(e) {
    if (!e.target || e.target.id !== 'mapTypeSelect') return;
    syncModeVisibility();
    // When the user returns to Google mode, re-apply their preferred basemap.
    applyToGoogleMap();
  }

  function wrapApplyMapMode() {
    // Some code paths switch modes without firing <select> change.
    const fn = window.applyMapMode;
    if (typeof fn !== 'function' || fn.__uogaWrapped) return;
    function wrapped(...args) {
      const res = fn.apply(this, args);
      syncModeVisibility();
      // Let other scripts finish their own mode toggles, then re-assert.
      window.setTimeout(syncModeVisibility, 0);
      return res;
    }
    wrapped.__uogaWrapped = true;
    window.applyMapMode = wrapped;
  }

  function init() {
    sanitizeNativeMapSelect();
    const btn = getToggleBtn();
    if (btn) btn.addEventListener('click', onToggleClick);

    // Force Terrain as the initial basemap on each page load.
    writePreferredType(DEFAULT_TYPE);
    syncGoogleButtons();
    syncModeVisibility();
    wrapApplyMapMode();

    document.addEventListener('click', onBasemapClick, { passive: true });
    document.addEventListener('click', onDocClick, { passive: true });
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('change', onMapTypeChange, { passive: true });

    window.UOGA_BASEMAP_UI = {
      setPanelOpen,
      syncModeVisibility,
    };

    // Google map loads async; apply preference once it's available.
    let tries = 0;
    const t = window.setInterval(() => {
      tries += 1;
      if (window.googleBaselineMap) {
        window.clearInterval(t);
        applyToGoogleMap();
        return;
      }
      if (tries > 60) window.clearInterval(t);
    }, 250);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
