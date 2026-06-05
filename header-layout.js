(() => {
  const DWR_MAP_URL = 'https://dwrapps.utah.gov/huntboundary/hbstart';
  const PRIMARY_HEADER_NAV_ITEMS = [
    { href: 'https://www.uoga.org', label: 'U.O.G.A. HOME', tip: 'U.O.G.A. MAIN' },
    { href: './', label: 'HUNT BUILDER', tip: 'FIND YOUR\nDREAM HUNT' },
    { href: './research.html', label: 'HUNT RESEARCH', tip: 'MATCH\nHUNT = POINTS' },
    { href: './verify.html', label: 'OUTFITTERS', tip: 'OPTIMIZE\nYOUR ODDS' },
    { href: './hard-copy.html', label: 'HUNTING BIBLE', tip: 'YOUR BIBLE\nSOURCE DOCS' },
  ];
  const isBuilderPage = () => {
    const path = (window.location && window.location.pathname ? window.location.pathname : '').toLowerCase();
    return path.endsWith('/index.html') || path.endsWith('/builder.html') || path === '/' || path === '';
  };

  function bindPageNavControl(wrapper) {
    if (!wrapper || wrapper.__uogaPageNavBound) return;
    const toggle = wrapper.querySelector('.uoga-page-nav-toggle');
    const menu = wrapper.querySelector('.uoga-page-nav-menu');
    if (!toggle || !menu) return;
    wrapper.__uogaPageNavBound = true;

    const setMenuOpen = (isOpen) => {
      menu.hidden = !isOpen;
      menu.style.display = isOpen ? 'grid' : 'none';
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    };

    setMenuOpen(false);

    toggle.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      setMenuOpen(menu.hidden);
    });

    menu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        setMenuOpen(false);
      });
    });

    document.addEventListener('click', event => {
      if (!wrapper.contains(event.target)) setMenuOpen(false);
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') setMenuOpen(false);
    });
  }

  function closeTopbarOverlays(exceptId = '') {
    const pageNavToggle = document.getElementById('pageNavToggleBtn');
    const pageNavMenu = document.querySelector('.uoga-page-nav-menu');
    if (exceptId !== 'pageNavToggleBtn' && pageNavMenu && pageNavToggle) {
      pageNavMenu.hidden = true;
      pageNavMenu.style.display = 'none';
      pageNavToggle.setAttribute('aria-expanded', 'false');
    }

    const mapModeToggle = document.getElementById('mapModeToggleBtn');
    const mapModeMenu = document.querySelector('.map-mode-menu');
    if (exceptId !== 'mapModeToggleBtn' && mapModeMenu && mapModeToggle) {
      mapModeMenu.hidden = true;
      mapModeToggle.setAttribute('aria-expanded', 'false');
    }

    const instructionsTab = document.getElementById('instructionsTab');
    const instructionsPanel = document.getElementById('instructionsPanel');
    if (exceptId !== 'instructionsTab' && instructionsTab && instructionsPanel) {
      instructionsPanel.hidden = true;
      instructionsTab.setAttribute('aria-expanded', 'false');
    }
  }

  function bindTopbarOverlayPriority() {
    if (document.body?.dataset.uogaOverlayPriorityBound) return;
    if (document.body) document.body.dataset.uogaOverlayPriorityBound = 'true';

    document.addEventListener('click', (event) => {
      const trigger = event.target?.closest?.('#mapModeToggleBtn, #pageNavToggleBtn, #instructionsTab');
      if (!trigger) return;
      closeTopbarOverlays(trigger.id);
    }, { capture: true });
  }

  function normalizeHeaderNavLabel(text) {
    const label = String(text || '').replace(/\s+/g, ' ').trim();
    if (!label) return '';
    if (label.toUpperCase() === 'HARD COPIES') return 'HUNTING BIBLE';
    if (label.toUpperCase() === 'HUNT LIBRARY') return 'HUNTING BIBLE';
    return label.toUpperCase();
  }

  function getHeaderNavItems(links) {
    const activeLabels = new Set();
    const activeHrefs = new Set();

    links.forEach(link => {
      const href = link.getAttribute('href') || '#';
      const label = normalizeHeaderNavLabel(link.textContent);
      const active = link.classList.contains('active') || link.getAttribute('aria-current') === 'page';
      if (active && label) activeLabels.add(label);
      if (active && href) activeHrefs.add(href);
    });

    return PRIMARY_HEADER_NAV_ITEMS.map(item => ({
      ...item,
      active: activeLabels.has(item.label) || activeHrefs.has(item.href),
    }));
  }

  function ensurePrimaryHeaderNav(header, links) {
    if (!header || !links || !links.length) return;
    header.classList.toggle('uoga-header-has-left-controls', !!header.querySelector('.topbar-left'));
    let nav = header.querySelector('.uoga-primary-nav');
    if (!nav) {
      nav = document.createElement('nav');
      nav.className = 'uoga-primary-nav';
      nav.setAttribute('aria-label', 'Primary site navigation');
    }

    nav.textContent = '';
    getHeaderNavItems(links).forEach(item => {
      const anchor = document.createElement('a');
      anchor.href = item.href;
      anchor.textContent = item.label;
      if (item.tip) {
        anchor.dataset.navTip = item.tip;
        anchor.title = item.tip;
      }
      if (item.active) {
        anchor.className = 'active';
        anchor.setAttribute('aria-current', 'page');
      }
      nav.appendChild(anchor);
    });

    if (!nav.parentElement) {
      const rightRail = header.querySelector('.topbar-right, .controls');
      if (rightRail && rightRail.parentElement === header) {
        header.insertBefore(nav, rightRail);
      } else {
        header.appendChild(nav);
      }
    }
  }

  function buildPageNavDropdown() {
    const strip = document.querySelector('.page-nav-strip');
    const header = document.querySelector('header.topbar');
    const existingWrapper = document.querySelector('[data-uoga-page-nav]');
    if (existingWrapper) {
      const existingLinks = Array.from(existingWrapper.querySelectorAll('a'));
      const stripLinks = strip ? Array.from(strip.querySelectorAll('a.utility-link')) : [];
      ensurePrimaryHeaderNav(header || existingWrapper.closest('header.topbar'), stripLinks.length ? stripLinks : existingLinks);
      bindPageNavControl(existingWrapper);
      if (strip) strip.remove();
      return;
    }
    if (!strip || !header) return;
    const nav = strip.querySelector('.utility-nav');
    if (!nav) return;
    const links = Array.from(nav.querySelectorAll('a.utility-link'));
    if (!links.length) return;
    const active = links.find(link => link.classList.contains('active')) || links[0];
    const activeLabel = normalizeHeaderNavLabel(active?.textContent) || 'HUNT BUILDER';
    ensurePrimaryHeaderNav(header, links);
    const wrapper = document.createElement('div');
    wrapper.className = 'uoga-page-nav-control';
    wrapper.setAttribute('data-uoga-page-nav', 'true');
    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'pageNavToggleBtn';
    toggleBtn.className = 'uoga-page-nav-toggle';
    toggleBtn.type = 'button';
    toggleBtn.setAttribute('aria-expanded', 'false');

    const label = document.createElement('span');
    label.className = 'uoga-page-nav-label';
    const kicker = document.createElement('span');
    kicker.className = 'uoga-page-nav-kicker';
    kicker.textContent = 'Page Navigation';
    const current = document.createElement('span');
    current.className = 'uoga-page-nav-current-page';
    current.textContent = activeLabel;
    const hamburger = document.createElement('span');
    hamburger.className = 'uoga-page-nav-hamburger';
    hamburger.setAttribute('aria-hidden', 'true');
    hamburger.innerHTML = '<span></span><span></span><span></span>';

    label.appendChild(kicker);
    label.appendChild(current);
    toggleBtn.appendChild(hamburger);
    toggleBtn.appendChild(label);

    const menu = document.createElement('div');
    menu.className = 'uoga-page-nav-menu';
    menu.hidden = true;

    wrapper.appendChild(toggleBtn);
    wrapper.appendChild(menu);
    links.forEach(link => {
      const clone = link.cloneNode(true);
      clone.classList.add('uoga-page-nav-link');
      const span = clone.querySelector('span');
      if (span) {
        span.textContent = normalizeHeaderNavLabel(span.textContent);
      } else {
        clone.textContent = normalizeHeaderNavLabel(clone.textContent);
      }
      menu.appendChild(clone);
    });
    const host = header.querySelector('.topbar-left') || header;
    const mapControl = host.querySelector('.map-mode-control');
    if (mapControl && mapControl.parentElement === host) {
      mapControl.insertAdjacentElement('beforebegin', wrapper);
    } else {
      host.insertBefore(wrapper, host.firstChild);
    }
    strip.remove();
    bindPageNavControl(wrapper);
  }

  function normalizeTopbarControlOrder() {
    const host = document.querySelector('.topbar-left');
    if (!host) return;
    const pageNav = host.querySelector('.uoga-page-nav-control');
    const mapControl = host.querySelector('.map-mode-control, [data-uoga-engine-pills], [data-map-mode-picker]');
    const instructions = host.querySelector('.instructions-control');

    // Desired order mirrors the visual header: action button, map selector, hidden mobile nav fallback.
    if (instructions && instructions.parentElement === host) host.prepend(instructions);
    if (mapControl && mapControl.parentElement === host) {
      if (instructions && instructions.parentElement === host) instructions.insertAdjacentElement('afterend', mapControl);
      else host.prepend(mapControl);
    }
    if (pageNav && pageNav.parentElement === host) host.appendChild(pageNav);
  }

  function injectLightPillStyle() {
    if (document.getElementById('uoga-light-pill-system-fix')) return;
    const style = document.createElement('style');
    style.id = 'uoga-light-pill-system-fix';
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
        --selected-fill:#fff7ee !important;
        --selected-fill-dark:#ead8c4 !important;
        --selected-text:#2b1c12 !important;
        --selected-outline:#f07800 !important;
        --bg-image:url('./assets/backgrounds/White Topo 20.jpg') !important;
      }
      html, body {
        background-color:#f4efe4 !important;
        color:#2b1c12 !important;
      }
      body.builder-page {
        background:
          radial-gradient(circle at 8% 0%, rgba(46, 88, 64, 0.15), transparent 28rem),
          radial-gradient(circle at 92% 6%, rgba(178, 94, 31, 0.15), transparent 24rem),
          linear-gradient(180deg, rgba(246, 240, 231, 0.9), rgba(246, 240, 231, 0.96)),
          url('./assets/backgrounds/White Topo 20.jpg') center top / 1720px auto repeat,
          #f6f0e7 !important;
      }
      .topbar, .topbar.topbar-planner {
        background:rgba(255,253,249,.94) !important;
        border-bottom:1px solid #c9a27f !important;
        box-shadow:0 8px 22px rgba(58,37,18,.14) !important;
        color:#2b1c12 !important;
        position:sticky !important;
        top:0 !important;
        z-index:12000 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:space-between !important;
        gap:18px !important;
        flex-wrap:nowrap !important;
        min-height:70px !important;
        padding:10px clamp(14px, 2.2vw, 30px) !important;
      }
      .page-nav-strip { display:none !important; visibility:hidden !important; opacity:0 !important; background:transparent !important; border:0 !important; }
      .uoga-primary-nav {
        order:2 !important;
        position:absolute !important;
        left:50% !important;
        top:50% !important;
        transform:translate(-50%, -50%) !important;
        width:max-content !important;
        max-width:calc(100vw - 560px) !important;
        flex:0 0 auto !important;
        min-height:54px !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        gap:6px !important;
        padding:6px 7px !important;
        border:1px solid rgba(209,171,131,.92) !important;
        border-radius:999px !important;
        background:
          radial-gradient(circle at 20% 0%, rgba(255,255,255,.92), transparent 34%),
          linear-gradient(180deg,#fffdfa 0%,#f4eadc 48%,#dfc9af 100%) !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.98), inset 0 -3px 7px rgba(84,47,18,.16), 0 10px 24px rgba(58,37,18,.16) !important;
        isolation:isolate !important;
        overflow:visible !important;
        z-index:1 !important;
      }
      .uoga-primary-nav::before {
        content:"" !important;
        position:absolute !important;
        inset:6px !important;
        z-index:0 !important;
        border-radius:999px !important;
        border:1px solid rgba(209,171,131,.80) !important;
        background:
          radial-gradient(circle at 18% 0%, rgba(255,255,255,.98), transparent 38%),
          linear-gradient(180deg,#fffefa 0%,#f8efe3 52%,#ead8c4 100%) !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.98), inset 0 -2px 5px rgba(84,47,18,.10) !important;
        pointer-events:none !important;
      }
      .uoga-primary-nav a {
        position:relative !important;
        z-index:1 !important;
        display:inline-flex !important;
        align-items:center !important;
        justify-content:center !important;
        min-height:38px !important;
        padding:0 16px !important;
        border:1px solid rgba(240,120,0,.40) !important;
        border-radius:999px !important;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,.16), transparent 36%),
          linear-gradient(180deg, rgba(57,44,34,.92), rgba(28,22,17,.96)) !important;
        box-shadow:0 7px 16px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,170,76,.08) !important;
        color:#f07800 !important;
        font-size:12px !important;
        font-weight:950 !important;
        line-height:1 !important;
        letter-spacing:.22em !important;
        text-transform:uppercase !important;
        text-decoration:none !important;
        text-shadow:0 1px 0 rgba(0,0,0,.46), 0 0 12px rgba(240,120,0,.22) !important;
        white-space:nowrap !important;
        transition:transform 150ms ease, color 150ms ease, background 150ms ease, border-color 150ms ease, box-shadow 150ms ease !important;
        transform-origin:center center !important;
      }
      .uoga-primary-nav a:hover,
      .uoga-primary-nav a:focus-visible {
        color:transparent !important;
        outline:none !important;
        transform:translateY(-2px) scale(1.035) !important;
        border-color:#ff8c14 !important;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,.18), transparent 38%),
          linear-gradient(180deg,#4f3a23,#21170f) !important;
        box-shadow:0 10px 20px rgba(20,12,7,.30), 0 0 0 2px rgba(255,140,20,.22) !important;
        z-index:4 !important;
        text-shadow:none !important;
      }
      .uoga-primary-nav a[data-nav-tip]::before {
        content:attr(data-nav-tip) !important;
        position:absolute !important;
        inset:0 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        padding:0 6px !important;
        color:#ffffff !important;
        font-size:12px !important;
        font-weight:950 !important;
        line-height:1.02 !important;
        letter-spacing:.095em !important;
        text-align:center !important;
        white-space:pre-line !important;
        text-shadow:0 1px 0 rgba(0,0,0,.82), 0 0 14px rgba(255,255,255,.32) !important;
        opacity:0 !important;
        pointer-events:none !important;
        transition:opacity 150ms ease !important;
      }
      .uoga-primary-nav a[data-nav-tip]:hover::before,
      .uoga-primary-nav a[data-nav-tip]:focus-visible::before {
        opacity:1 !important;
      }
      .uoga-primary-nav a.active[data-nav-tip]::before,
      .uoga-primary-nav a.active[data-nav-tip]:hover::before,
      .uoga-primary-nav a.active[data-nav-tip]:focus-visible::before {
        opacity:0 !important;
      }
      .uoga-primary-nav a.active {
        color:#ffffff !important;
        outline:none !important;
        border-color:#ff8c14 !important;
        background:linear-gradient(180deg,rgba(65,47,29,.84),rgba(30,22,15,.92)) !important;
        text-shadow:0 1px 0 rgba(0,0,0,.76), 0 0 14px rgba(255,255,255,.22) !important;
      }
      .page-nav-case { display:flex !important; align-items:center !important; justify-content:center !important; width:100% !important; }
      .utility-nav { display:flex !important; align-items:center !important; justify-content:center !important; gap:12px !important; flex-wrap:wrap !important; }
      .utility-link,
      .map-mode-toggle,
      .map-mode-option,
      .uoga-page-nav-toggle,
      .uoga-page-nav-link,
      .ownership-dock .toggle-row,
      .ownership-dock .toggle-menu summary,
      .basemap-toggle,
      .globe-basemap-btn,
      .uoga-engine-pill {
        border-radius:999px !important;
        border:1px solid #c9a27f !important;
        background:linear-gradient(180deg,#fffdf9,#f2e8dc) !important;
        color:#2b1c12 !important;
        font-weight:900 !important;
        letter-spacing:.06em !important;
        text-transform:uppercase !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.95), inset 0 -2px 2px rgba(0,0,0,.08), 0 4px 10px rgba(58,37,18,.14) !important;
      }
      .utility-link.active,
      .uoga-page-nav-link.active,
      .map-mode-option.is-active,
      .map-mode-toggle[aria-expanded="true"],
      .uoga-page-nav-toggle[aria-expanded="true"],
      .uoga-engine-pill.is-active {
        border-color:#f07800 !important;
        background:linear-gradient(180deg,#fff7ee,#ead8c4) !important;
        box-shadow:inset 0 0 0 2px #f07800, 0 6px 14px rgba(58,37,18,.18) !important;
      }
      .sidebar, .rightbar, .panel, .panel-body, .rightbar-header, .hunt-card, .outfitter-card {
        background:rgba(255,251,244,.96) !important;
        color:#2b1c12 !important;
        border-color:#c9a27f !important;
      }
      .panel h2 {
        background:linear-gradient(180deg,#f07800,#d96700) !important;
        color:#fff8f1 !important;
      }
      .hunt-input, .hunt-select, select, input {
        background:#fffdf8 !important;
        color:#2b1c12 !important;
        border-color:#c9a27f !important;
      }
      .helper, .empty-note, .hunt-card-meta, .map-chooser-meta { color:#6b5646 !important; }
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
      .map-mode-native { position:absolute !important; width:1px !important; height:1px !important; opacity:0 !important; pointer-events:none !important; }
       .topbar-left { position:relative !important; display:flex !important; align-items:center !important; justify-content:flex-start !important; gap:14px !important; flex:0 0 auto !important; width:auto !important; min-width:0 !important; order:1 !important; z-index:30070 !important; }
       .topbar-right {
         position:relative !important;
         display:flex !important;
         align-items:center !important;
         justify-content:flex-end !important;
         flex:0 0 auto !important;
         margin-left:auto !important;
         order:3 !important;
         z-index:20040 !important;
       }
       .uoga-page-nav-control { display:none !important; }
       .map-mode-control { position:relative !important; display:flex !important; align-items:center !important; justify-content:center !important; }
       .map-mode-picker { position:relative !important; z-index:30080 !important; }
       .map-mode-menu { z-index:30090 !important; }
       .uoga-page-nav-toggle,
       .map-mode-toggle { display:inline-flex !important; flex-direction:column !important; align-items:center !important; justify-content:center !important; gap:2px !important; width:224px !important; min-height:48px !important; padding:5px 14px !important; cursor:pointer !important; }
       .map-mode-toggle {
         border:2px solid #f07800 !important;
         background:linear-gradient(180deg,#fffefb,#f7efe6) !important;
         box-shadow:inset 0 1px 0 rgba(255,255,255,.95), 0 7px 15px rgba(58,37,18,.16) !important;
       }
       .uoga-page-nav-label,
       .map-mode-label { font-size:10px !important; line-height:1 !important; color:#f07800 !important; white-space:nowrap !important; }
       .uoga-page-nav-current,
       .map-mode-current { display:inline-flex !important; align-items:center !important; justify-content:center !important; width:100% !important; min-width:0 !important; }
       .map-mode-logo--dwr-current { max-height:28px !important; max-width:190px !important; width:auto !important; height:auto !important; object-fit:contain !important; }
       .map-mode-option--icononly[data-map-mode-value=\"dwr\"] { min-height:42px !important; }
       .map-mode-option-logo--dwr { width:170px !important; height:34px !important; max-width:170px !important; max-height:34px !important; object-fit:contain !important; }
       .uoga-page-nav-label {
         display:inline-flex !important;
         flex-direction:column !important;
         align-items:center !important;
         justify-content:center !important;
         min-width:176px !important;
         min-height:38px !important;
         padding:0 18px !important;
         border-radius:999px !important;
         border:1px solid color-mix(in srgb, var(--accent) 52%, transparent) !important;
         background:radial-gradient(circle at top left, rgba(255,255,255,0.22), transparent 34%), linear-gradient(180deg, rgba(57, 44, 34, 0.92), rgba(28, 22, 17, 0.96)) !important;
         box-shadow:0 8px 18px rgba(0,0,0,0.28) !important;
         color:var(--accent) !important;
           font-size:15px !important;
         font-weight:900 !important;
         letter-spacing:.10em !important;
         text-transform:uppercase !important;
         line-height:1.02 !important;
         white-space:nowrap !important;
         text-align:center !important;
       }
       .uoga-page-nav-kicker,
       .uoga-page-nav-current-page { display:block !important; }
       .uoga-page-nav-current-page { color:#f4efe4 !important; font-size:12px !important; letter-spacing:.14em !important; margin-top:2px !important; }
       .uoga-page-nav-menu,
       .map-mode-menu { position:absolute !important; top:calc(100% + 8px) !important; left:50% !important; transform:translateX(-50%) !important; display:grid !important; grid-template-columns:1fr !important; gap:8px !important; z-index:30090 !important; min-width:224px !important; }
       .uoga-page-nav-menu[hidden] { display:none !important; }
       .map-mode-menu[hidden] { display:none !important; }
       .uoga-page-nav-menu { padding:12px !important; min-width:224px !important; }
       .uoga-page-nav-menu .utility-link,
       .uoga-page-nav-menu .uoga-page-nav-link { width:100% !important; min-height:42px !important; justify-content:center !important; }
       .map-mode-option-logo--dwr { width:170px !important; height:34px !important; max-width:170px !important; max-height:34px !important; object-fit:contain !important; }
        .instructions-tab {
          display:inline-flex !important;
          align-items:center !important;
          justify-content:center !important;
          min-height:42px !important;
          min-width:166px !important;
          padding:8px 20px !important;
          border-radius:999px !important;
          border:1px solid #b45e00 !important;
          background:linear-gradient(180deg,#f28a12,#d66f00) !important;
          color:#2b1c12 !important;
          font-weight:900 !important;
          letter-spacing:.06em !important;
          text-transform:uppercase !important;
          box-shadow:inset 0 1px 0 rgba(255,236,214,.66), inset 0 -2px 3px rgba(62,33,6,.26), 0 6px 14px rgba(58,37,18,.20) !important;
          flex:0 0 auto !important;
        }
        .instructions-tab[aria-expanded=\"true\"],
        .instructions-tab:hover {
          border-color:#f7a142 !important;
          background:linear-gradient(180deg,#f7a142,#e07900) !important;
          box-shadow:inset 0 0 0 2px rgba(255,235,210,.42), 0 8px 18px rgba(58,37,18,.24) !important;
        }
        .instructions-panel {
          display:flex !important;
          flex:1 1 0 !important;
          min-width:0 !important;
          align-items:center !important;
          justify-content:flex-start !important;
          gap:10px 14px !important;
          flex-wrap:nowrap !important;
          overflow-x:auto !important;
        }
        .instructions-panel .qs-step {
          flex:0 0 auto !important;
        }
        .instructions-panel[hidden] { display:none !important; }
       .instructions-control {
         position:relative !important;
         display:flex !important;
         align-items:center !important;
         justify-content:center !important;
         flex:0 0 auto !important;
         order:0 !important;
         margin-right:0 !important;
         margin-left:0 !important;
       }
       .instructions-control .instructions-panel { position:absolute !important; top:calc(100% + 8px) !important; left:50% !important; transform:translateX(-50%) !important; display:grid !important; grid-template-columns:1fr !important; gap:8px !important; width:236px !important; max-width:calc(100vw - 28px) !important; padding:8px !important; border:1px solid #c9a27f !important; border-radius:16px !important; background:rgba(255,253,248,.98) !important; box-shadow:0 14px 34px rgba(58,37,18,.22) !important; z-index:10035 !important; }
       .instructions-control .instructions-panel[hidden] { display:none !important; }
       .instructions-control .qs-step { width:100% !important; max-width:none !important; flex:0 0 auto !important; padding:9px 10px !important; font-size:11px !important; font-weight:900 !important; }
       .map-wrap .ownership-dock {
         position:absolute !important;
         left:14px !important;
         top:14px !important;
         right:auto !important;
         z-index:34 !important;
         display:flex !important;
         align-items:flex-start !important;
         justify-content:flex-start !important;
         max-width:260px !important;
       }
       .uoga-backpack-open .map-wrap .ownership-dock { left:14px !important; max-width:260px !important; }
       .map-wrap .ownership-case { display:flex !important; justify-content:flex-start !important; align-items:flex-start !important; width:100% !important; }
       .map-wrap .ownership-dock .toggle-row {
      display:grid !important;
         grid-template-columns:1fr !important;
         justify-items:stretch !important;
         align-items:stretch !important;
         gap:8px !important;
         width:100% !important;
         max-width:260px !important;
         padding:10px !important;
         border-radius:14px !important;
         background:rgba(255,253,248,.96) !important;
         border:1px solid #c9a27f !important;
         backdrop-filter:blur(10px) !important;
         -webkit-backdrop-filter:blur(10px) !important;
      overflow:visible !important;
    }
    .map-wrap .ownership-dock .ownership-toggle-row[hidden] {
      display:none !important;
    }
      .map-wrap .ownership-panel-title {
        width:100% !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        min-height:28px !important;
        padding:4px 10px 6px !important;
        border-bottom:1px solid rgba(75,42,17,.18) !important;
        color:#4b2a11 !important;
        font-size:11px !important;
        font-weight:950 !important;
        letter-spacing:.12em !important;
        line-height:1 !important;
        text-transform:uppercase !important;
      }
       .map-wrap .ownership-hunt-units-chip {
         justify-content:flex-start !important;
         padding:8px 10px !important;
         border:1px solid var(--line) !important;
         border-radius:12px !important;
         background:var(--panel2) !important;
       }
       .map-wrap .ownership-hunt-units-chip .toggle-chip-label { text-align:left !important; }
       .map-wrap .ownership-group {
         width:100% !important;
         margin:0 !important;
       }
       .map-wrap .ownership-group > summary {
         width:100% !important;
         min-height:38px !important;
         padding:8px 10px !important;
         border-radius:12px !important;
         justify-content:space-between !important;
         display:flex !important;
       }
       .map-wrap .ownership-dock .toggle-menu-panel {
         z-index:10040 !important;
         left:0 !important;
         right:auto !important;
         width:min(280px, calc(100vw - 30px)) !important;
       }
      .map-wrap .ownership-group:not([open]):not(:hover):not(:focus-within) > .toggle-menu-panel {
        display:none !important;
      }
      .map-wrap .ownership-group:hover > .toggle-menu-panel,
      .map-wrap .ownership-group:focus-within > .toggle-menu-panel {
        display:grid !important;
      }
      .map-wrap .ownership-group:hover > summary::after,
      .map-wrap .ownership-group:focus-within > summary::after {
        content:"^" !important;
      }
       .basemap-pop { position:absolute !important; top:68px !important; right:14px !important; z-index:31 !important; display:grid !important; justify-items:end !important; gap:8px !important; transition:right 160ms ease !important; }
       .basemap-pop[aria-hidden="true"] { display:none !important; }
       .uoga-backpack-open .basemap-pop { right:min(458px, calc(100% - 320px)) !important; }
       .basemap-pop .globe-basemap-panel { position:static !important; display:none !important; width:196px !important; padding:6px !important; border-radius:12px !important; box-shadow:0 14px 30px rgba(26,16,10,.34) !important; }
       .basemap-pop[data-open="true"] .globe-basemap-panel { display:grid !important; gap:6px !important; }
       .basemap-pop .globe-basemap-grid { grid-template-columns:1fr !important; gap:6px !important; }
       .basemap-pop .globe-basemap-btn { min-height:30px !important; padding:5px 10px !important; font-size:11px !important; box-shadow:0 6px 14px rgba(34,22,13,.26) !important; }
       .uoga-engine-control { display:flex !important; align-items:center !important; gap:8px !important; }
       .uoga-engine-label { font-size:10px !important; font-weight:900 !important; color:#f07800 !important; letter-spacing:.08em !important; text-transform:uppercase !important; }
       .uoga-engine-pill { min-height:40px !important; padding:0 16px !important; cursor:pointer !important; display:inline-flex !important; align-items:center !important; justify-content:center !important; gap:8px !important; }
      .uoga-engine-pill img { max-height:20px !important; max-width:110px !important; display:block !important; }
      @media (max-width: 1200px) {
        .topbar, .topbar.topbar-planner {
          flex-wrap:wrap !important;
          justify-content:center !important;
        }
        .topbar-left {
          display:flex !important;
          flex-wrap:wrap !important;
          justify-content:flex-start !important;
          align-items:center !important;
          gap:12px !important;
        }
        .topbar.uoga-header-has-left-controls .uoga-primary-nav {
          order:4 !important;
          flex:1 1 100% !important;
          position:relative !important;
          left:auto !important;
          top:auto !important;
          transform:none !important;
          width:100% !important;
          max-width:100% !important;
          overflow-x:auto !important;
        }
        .uoga-primary-nav a { padding:0 12px !important; }
        .topbar-right { margin-left:auto !important; }
        .instructions-control {
          margin-left:0 !important;
          margin-right:0 !important;
          order:0 !important;
        }
      }
      @media (max-width: 900px) {
        html, body {
          max-width:100vw !important;
          overflow-x:hidden !important;
        }
        .topbar,
        .topbar.topbar-planner {
          display:grid !important;
          grid-template-columns:minmax(0, 1fr) !important;
          justify-items:center !important;
          align-items:center !important;
          width:100% !important;
          max-width:100vw !important;
          min-width:0 !important;
          overflow:hidden !important;
          padding:10px 12px !important;
        }
        .topbar-left {
          display:flex !important;
          flex-wrap:wrap !important;
          justify-content:center !important;
          align-items:center !important;
          gap:10px !important;
          width:100% !important;
          max-width:100% !important;
          min-width:0 !important;
          flex:0 1 auto !important;
        }
        .instructions-control { margin:0 !important; order:0 !important; }
        .uoga-page-nav-control {
          display:flex !important;
          position:relative !important;
          order:0 !important;
          flex:0 0 auto !important;
          width:auto !important;
          max-width:none !important;
        }
        .uoga-page-nav-toggle {
          width:64px !important;
          height:56px !important;
          min-width:64px !important;
          min-height:56px !important;
          padding:0 !important;
          display:inline-flex !important;
          align-items:center !important;
          justify-content:center !important;
          border:3px solid #4b2a11 !important;
          border-radius:4px !important;
          background:
            radial-gradient(circle at 22% 12%, rgba(255,255,255,.88), transparent 36%),
            linear-gradient(180deg, #fffdf8, #ead8c4) !important;
          box-shadow:
            0 0 0 2px #f4efe4,
            0 8px 18px rgba(58,37,18,.28),
            inset 0 1px 0 rgba(255,255,255,.92),
            inset 0 -3px 5px rgba(84,47,18,.12) !important;
          cursor:pointer !important;
        }
        .uoga-page-nav-toggle:hover,
        .uoga-page-nav-toggle:focus-visible,
        .uoga-page-nav-toggle[aria-expanded="true"] {
          border-color:#ffffff !important;
          background:
            radial-gradient(circle at 22% 12%, rgba(255,255,255,.94), transparent 36%),
            linear-gradient(180deg,#fff7ee,#dfc0a0) !important;
          box-shadow:
            0 0 0 3px #f07800,
            0 10px 22px rgba(58,37,18,.36),
            inset 0 1px 0 rgba(255,255,255,.95),
            inset 0 -3px 5px rgba(84,47,18,.18) !important;
          outline:none !important;
        }
        .uoga-page-nav-hamburger {
          display:grid !important;
          gap:7px !important;
          width:27px !important;
        }
        .uoga-page-nav-hamburger span {
          display:block !important;
          height:3px !important;
          width:100% !important;
          border-radius:999px !important;
          background:#4b2a11 !important;
          box-shadow:0 1px 0 rgba(255,255,255,.55), 0 0 0 1px rgba(43,28,18,.16) !important;
        }
        .uoga-page-nav-label {
          position:absolute !important;
          width:1px !important;
          height:1px !important;
          overflow:hidden !important;
          clip:rect(0,0,0,0) !important;
          clip-path:inset(50%) !important;
          white-space:nowrap !important;
          border:0 !important;
          padding:0 !important;
          min-width:0 !important;
          min-height:0 !important;
        }
        .uoga-page-nav-menu {
          position:absolute !important;
          top:calc(100% + 10px) !important;
          left:auto !important;
          right:0 !important;
          transform:none !important;
          display:grid !important;
          grid-template-columns:1fr !important;
          gap:9px !important;
          width:min(268px, calc(100vw - 24px)) !important;
          min-width:0 !important;
          padding:12px !important;
          border:2px solid #f4efe4 !important;
          border-radius:8px !important;
          background:linear-gradient(180deg,#21160e,#070403) !important;
          box-shadow:0 0 0 2px #2b1c12, 0 18px 38px rgba(0,0,0,.48) !important;
          z-index:10070 !important;
        }
        .uoga-page-nav-menu[hidden] { display:none !important; }
        .uoga-page-nav-menu .utility-link,
        .uoga-page-nav-menu .uoga-page-nav-link {
          width:100% !important;
          min-height:46px !important;
          justify-content:center !important;
          border:1px solid rgba(240,120,0,.72) !important;
          border-radius:999px !important;
          background:linear-gradient(180deg,#fffdf8,#ecd6bd) !important;
          color:#2b1c12 !important;
          box-shadow:0 7px 16px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.92) !important;
          font-size:12px !important;
          letter-spacing:.13em !important;
        }
        .uoga-page-nav-menu .uoga-page-nav-link.active {
          background:linear-gradient(180deg,#f7a142,#d96c00) !important;
          color:#1a0d04 !important;
          border-color:#fffdf8 !important;
        }
        .map-mode-control,
        .control-group.map-mode-control {
          width:min(224px, calc(100vw - 28px)) !important;
          max-width:100% !important;
          min-width:0 !important;
        }
        .instructions-tab {
          width:min(166px, calc(100vw - 28px)) !important;
          min-width:0 !important;
          padding-left:14px !important;
          padding-right:14px !important;
        }
        .uoga-page-nav-toggle, .map-mode-toggle {
          width:100% !important;
          max-width:100% !important;
        }
        .uoga-primary-nav {
          display:none !important;
        }
        .uoga-primary-nav a {
          flex:0 0 auto !important;
          min-height:40px !important;
          padding:0 10px !important;
          font-size:10px !important;
          letter-spacing:.16em !important;
        }
        .topbar-right {
          width:100% !important;
          max-width:100% !important;
          min-width:0 !important;
          justify-content:center !important;
          margin-left:0 !important;
          flex:0 1 auto !important;
        }
        .map-wrap .ownership-dock, .uoga-backpack-open .map-wrap .ownership-dock {
          left:10px !important;
          top:10px !important;
          max-width:min(240px, calc(100vw - 26px)) !important;
          justify-content:flex-start !important;
        }
        .map-wrap .ownership-dock .toggle-row {
          overflow:visible !important;
          max-width:min(240px, calc(100vw - 26px)) !important;
          justify-items:stretch !important;
        }
        .basemap-pop, .uoga-backpack-open .basemap-pop { top:74px !important; right:12px !important; left:auto !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureFrames() {
    const stage = document.querySelector('.map-stage') || document.querySelector('.map-wrap');
    if (!stage) return {};
    let dwr = document.getElementById('dwrMapFrame');
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
    return { dwr };
  }

  function normalizeMapSelect() {
    if (!isBuilderPage()) return document.getElementById('mapTypeSelect');
    let select = document.getElementById('mapTypeSelect');
    if (!select) {
      select = document.createElement('select');
      select.id = 'mapTypeSelect';
      select.className = 'map-mode-native';
      select.setAttribute('aria-hidden', 'true');
      select.tabIndex = -1;
      document.body.appendChild(select);
    }
    const hasEngineValues = Array.from(select.options || []).some(opt => ['google', 'earth', 'dwr'].includes(opt.value));
    if (!hasEngineValues) {
      select.innerHTML = '<option value="google" selected>Google Maps</option><option value="earth">Google Earth</option><option value="dwr">DWR Map</option>';
    }
    if (!['google', 'earth', 'dwr'].includes(select.value)) select.value = 'google';
    select.classList.add('map-mode-native');
    return select;
  }

  function ensureVisibleEnginePills(select) {
    if (!isBuilderPage() || !select || document.querySelector('[data-uoga-engine-pills]') || document.querySelector('[data-map-mode-picker]')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'uoga-engine-control';
    wrapper.setAttribute('data-uoga-engine-pills', 'true');
    wrapper.innerHTML = `
      <span class="uoga-engine-label">Map Selector</span>
      <button type="button" class="uoga-engine-pill" data-engine="google"><img src="./assets/logos/google-maps-logo.png" alt="Google Maps"><span>Google</span></button>
      <button type="button" class="uoga-engine-pill" data-engine="earth"><img src="./assets/logos/google_earth_logo.png?v=20260430-map-selector-1" alt="Google Earth"><span>Earth</span></button>
      <button type="button" class="uoga-engine-pill" data-engine="dwr"><img src="./assets/logos/DWR-LOGO-maps.png?v=20260430-dwr-pill-1" alt="Utah DWR Map"><span>DWR Map</span></button>
    `;
    const oldGroup = select.closest('.control-group');
    const host = document.querySelector('.topbar-left') || document.querySelector('.topbar') || document.body;
    if (oldGroup) oldGroup.replaceWith(wrapper);
    else host.insertBefore(wrapper, host.firstChild);
    wrapper.appendChild(select);
    wrapper.querySelectorAll('[data-engine]').forEach(btn => {
      btn.addEventListener('click', () => {
        select.value = btn.dataset.engine;
        select.dispatchEvent(new Event('change', { bubbles:true }));
      });
    });
  }

  function setMode(mode) {
    const select = normalizeMapSelect();
    const { dwr } = ensureFrames();
    const next = ['google', 'earth', 'dwr'].includes(mode) ? mode : 'google';
    const didChange = !!select && select.value !== next;
    if (select) select.value = next;
    if (dwr && !dwr.src) dwr.src = DWR_MAP_URL;
    document.body.dataset.mapMode = next;
    if (didChange) {
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    document.querySelectorAll('[data-engine], [data-map-mode-value]').forEach(btn => {
      const v = btn.dataset.engine || btn.dataset.mapModeValue;
      btn.classList.toggle('is-active', v === next);
    });
  }

  function bindMapEngine() {
    const select = normalizeMapSelect();
    if (!select || !isBuilderPage()) return;
    ensureFrames();
    ensureVisibleEnginePills(select);
    select.addEventListener('change', () => window.setTimeout(() => setMode(select.value), 0));
    document.addEventListener('click', event => {
      const btn = event.target.closest?.('[data-map-mode-value]');
      if (!btn) return;
      window.setTimeout(() => setMode(btn.dataset.mapModeValue), 0);
    });
    setMode(select.value || 'google');
  }

  function init() {
    injectLightPillStyle();
    buildPageNavDropdown();
    normalizeTopbarControlOrder();
    bindTopbarOverlayPriority();
    bindMapEngine();
    normalizeTopbarControlOrder();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
