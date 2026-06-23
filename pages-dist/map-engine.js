(() => {
  const DWR_MAP_URL = 'https://dwrapps.utah.gov/huntboundary/hbstart';

  function $(id) { return document.getElementById(id); }

  function ensureStyle() {
    if ($('uoga-map-engine-style')) return;
    const style = document.createElement('style');
    style.id = 'uoga-map-engine-style';
    style.textContent = `
      :root, body, body.theme-dark {
        --bg:#f4efe4 !important;
        --panel:rgba(255,251,244,.96) !important;
        --panel2:#fffdf8 !important;
        --line:#c9a27f !important;
        --text:#2b1c12 !important;
        --muted:#6b5646 !important;
        --accent:#f07800 !important;
        --accent-dark:#d96700 !important;
        --bg-image:none !important;
      }
      html, body { background:#f4efe4 !important; background-image:none !important; color:#2b1c12 !important; }
      .topbar, .topbar-planner { background:rgba(255,253,249,.94) !important; color:#2b1c12 !important; border-bottom:1px solid #c9a27f !important; box-shadow:0 8px 22px rgba(58,37,18,.14) !important; }
      .page-nav-strip, .utility-nav { display:flex !important; visibility:visible !important; opacity:1 !important; }
      .utility-nav { align-items:center !important; justify-content:center !important; gap:12px !important; flex-wrap:wrap !important; }
      .utility-link, .map-mode-toggle, .map-mode-option, .topbar .toggle-row, .topbar .toggle-menu summary, .basemap-toggle, .globe-basemap-btn {
        border-radius:999px !important; border:1px solid #c9a27f !important; background:linear-gradient(180deg,#fffdf9,#f2e8dc) !important; color:#2b1c12 !important; font-weight:900 !important; letter-spacing:.06em !important; text-transform:uppercase !important; box-shadow:inset 0 1px 0 rgba(255,255,255,.95), inset 0 -2px 2px rgba(0,0,0,.08), 0 4px 10px rgba(58,37,18,.14) !important;
      }
      .utility-link.active, .map-mode-option.is-active, .map-mode-toggle[aria-expanded="true"] { border-color:#f07800 !important; background:linear-gradient(180deg,#fff7ee,#ead8c4) !important; box-shadow:inset 0 0 0 2px #f07800, 0 6px 14px rgba(58,37,18,.18) !important; }
      .map-mode-native { position:absolute !important; width:1px !important; height:1px !important; opacity:0 !important; pointer-events:none !important; }
      .map-mode-control { position:relative !important; padding:0 !important; border:0 !important; background:transparent !important; box-shadow:none !important; }
      .map-mode-picker { position:relative !important; z-index:10020 !important; display:block !important; }
      .map-mode-menu[hidden] { display:none !important; }
      .map-mode-menu { position:absolute !important; top:calc(100% + 8px) !important; left:0 !important; display:grid !important; gap:8px !important; z-index:10030 !important; }
      .map-mode-toggle, .map-mode-option { display:inline-flex !important; align-items:center !important; justify-content:center !important; gap:10px !important; width:230px !important; min-height:42px !important; padding:0 14px !important; cursor:pointer !important; }
      .map-mode-logo, .map-mode-option-logo { max-height:20px !important; max-width:118px !important; width:auto !important; height:auto !important; display:block !important; }
      .map-stage { position:relative !important; overflow:hidden !important; }
      #map, #googleEarth3dMap { position:absolute !important; inset:0 !important; width:100% !important; height:100% !important; min-height:100% !important; border:0 !important; }
      #dwrMapFrame {
        position:absolute !important;
        left:0 !important;
        right:0 !important;
        bottom:0 !important;
        top:0 !important;
        width:100% !important;
        height:100% !important;
        min-height:100% !important;
        border:0 !important;
      }
      #googleEarth3dMap, #dwrMapFrame { background:#fffdf8 !important; z-index:2 !important; }
      .sidebar, .rightbar, .panel, .panel-body, .rightbar-header, .hunt-card, .outfitter-card { background:rgba(255,251,244,.96) !important; color:#2b1c12 !important; border-color:#c9a27f !important; }
      .panel h2 { background:linear-gradient(180deg,#f07800,#d96700) !important; color:#fff8f1 !important; }
      .hunt-input, .hunt-select, select, input { background:#fffdf8 !important; color:#2b1c12 !important; border-color:#c9a27f !important; }
      .helper, .empty-note, .hunt-card-meta, .map-chooser-meta { color:#6b5646 !important; }
    `;
    document.head.appendChild(style);
  }

  function ensureSelect() {
    let select = $('mapTypeSelect');
    if (!select) {
      select = document.createElement('select');
      select.id = 'mapTypeSelect';
      document.body.appendChild(select);
    }
    const values = Array.from(select.options || []).map(o => o.value);
    if (!values.includes('google') || !values.includes('earth') || !values.includes('dwr')) {
      select.innerHTML = '<option value="google" selected>Google Maps</option><option value="earth">Google Earth</option><option value="dwr">DWR Map</option>';
    }
    if (!['google', 'earth', 'dwr'].includes(select.value)) select.value = 'google';
    select.classList.add('map-mode-native');
    return select;
  }

  function ensurePicker(select) {
    let picker = document.querySelector('[data-map-mode-picker]');
    if (!picker) {
      const host = document.querySelector('.topbar-left') || document.querySelector('.topbar') || document.body;
      const control = document.createElement('div');
      control.className = 'control-group map-mode-control';
      control.innerHTML = `
        <div class="map-mode-picker" data-map-mode-picker>
          <button id="mapModeToggleBtn" class="map-mode-toggle" type="button" aria-expanded="false">
            <span class="map-mode-label">Map Selector</span>
            <span class="map-mode-current"><img class="map-mode-logo" src="./assets/logos/google-maps-logo.png" alt="Google Maps"></span>
          </button>
          <div class="map-mode-menu" hidden>
            <button type="button" class="map-mode-option" data-map-mode-value="google"><img class="map-mode-option-logo" src="./assets/logos/google-maps-logo.png" alt=""><span>Google Maps</span></button>
            <button type="button" class="map-mode-option" data-map-mode-value="earth"><img class="map-mode-option-logo" src="./assets/logos/google_earth_logo.png" alt=""><span>Google Earth</span></button>
            <button type="button" class="map-mode-option" data-map-mode-value="dwr"><span>DWR Map</span></button>
          </div>
        </div>
      `;
      host.insertBefore(control, host.firstChild);
      control.appendChild(select);
      picker = control.querySelector('[data-map-mode-picker]');
    }
    return picker;
  }

  function ensureFrames() {
    const stage = document.querySelector('.map-stage') || document.querySelector('.map-wrap');
    if (!stage) return {};
    let dwr = $('dwrMapFrame');
    if (!dwr) {
      dwr = document.createElement('iframe');
      dwr.id = 'dwrMapFrame';
      dwr.className = 'dwr-map-frame';
      dwr.title = 'Utah DWR Hunt Boundary Map';
      dwr.loading = 'lazy';
      dwr.allow = 'geolocation';
      dwr.referrerPolicy = 'no-referrer-when-downgrade';
      dwr.hidden = true;
      stage.appendChild(dwr);
    }
    if (!dwr.src) dwr.src = DWR_MAP_URL;
    return { dwr };
  }

  function renderPicker(select, picker) {
    const value = ['google', 'earth', 'dwr'].includes(select.value) ? select.value : 'google';
    const current = picker.querySelector('.map-mode-current');
    const menu = picker.querySelector('.map-mode-menu');
    if (current) {
      current.innerHTML = value === 'earth'
        ? '<img class="map-mode-logo" src="./assets/logos/google_earth_logo.png" alt="Google Earth">'
        : value === 'dwr'
          ? '<span class="map-mode-text">DWR Map</span>'
          : '<img class="map-mode-logo" src="./assets/logos/google-maps-logo.png" alt="Google Maps">';
    }
    if (menu) {
      menu.querySelectorAll('[data-map-mode-value]').forEach(btn => btn.classList.toggle('is-active', btn.dataset.mapModeValue === value));
    }
  }

  function setMode(mode) {
    const select = ensureSelect();
    const picker = ensurePicker(select);
    const { dwr } = ensureFrames();
    const next = ['google', 'earth', 'dwr'].includes(mode) ? mode : 'google';
    const didChange = select.value !== next;
    select.value = next;
    document.body.dataset.mapMode = next;
    if (didChange) {
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    renderPicker(select, picker);
  }

  function bind() {
    ensureStyle();
    const select = ensureSelect();
    const picker = ensurePicker(select);
    ensureFrames();
    const toggle = picker.querySelector('.map-mode-toggle');
    const menu = picker.querySelector('.map-mode-menu');
    if (toggle && menu && !toggle.dataset.uogaBound) {
      toggle.dataset.uogaBound = 'true';
      toggle.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        const open = menu.hidden;
        menu.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
      });
    }
    picker.querySelectorAll('[data-map-mode-value]').forEach(btn => {
      if (btn.dataset.uogaBound) return;
      btn.dataset.uogaBound = 'true';
      btn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        setMode(btn.dataset.mapModeValue);
        if (menu) menu.hidden = true;
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
      });
    });
    if (!select.dataset.uogaBound) {
      select.dataset.uogaBound = 'true';
      select.addEventListener('change', () => setMode(select.value));
    }
    document.addEventListener('click', e => {
      if (menu && !picker.contains(e.target)) {
        menu.hidden = true;
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
      }
    });
    setMode(select.value || 'google');
    window.UOGA_setMapEngine = setMode;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
  else bind();
})();

