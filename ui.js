window.UOGA_UI = (() => {
  const BASKET_KEY = 'uoga_hunt_basket_v1';
  const LEGACY_BASKET_KEY = 'hunt_research_recent_hunts';
  const RECENTS_KEY = 'uoga_hunt_recent_v1';
  const SELECTED_HUNT_KEY = 'selected_hunt_code';
  const MAX_BASKET_ITEMS = 10;
  const MAX_RECENT_ITEMS = 10;
  const STYLE_ID = 'uoga-backpack-tray-styles';
  const BACKPACK_CHANGED_EVENT = 'uoga:backpack-changed';

  let trayShell = null;
  let trayButton = null;
  let trayPanel = null;
  let trayBadge = null;
  let traySections = null;
  let trayOpen = false;

  function normalizeKey(value) {
    return String(value || '').trim().toUpperCase();
  }

  function safeText(value) {
    return String(value ?? '');
  }

  function normalizeDrawPool(value) {
    const normalized = safeText(value).trim().toLowerCase().replace(/[\s-]+/g, '_');
    return normalized || 'standard';
  }

  function escapeHtml(value) {
    return safeText(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function isBuilderPage() {
    const path = String(window.location?.pathname || '').toLowerCase();
    return path.endsWith('/index.html') || path.endsWith('/builder.html') || path === '/' || path === '';
  }

  function shouldBackpackFloatWithViewport() {
    return !isBuilderPage();
  }

  function getBackpackHost() {
    if (isBuilderPage()) {
      const existingHost = document.querySelector('[data-backpack-host]') || document.querySelector('.topbar-right');
      if (existingHost) return existingHost;

      const topbar = document.querySelector('header.topbar');
      if (topbar) {
        const host = document.createElement('div');
        host.className = 'topbar-right';
        host.setAttribute('data-backpack-host', 'true');
        topbar.appendChild(host);
        return host;
      }
    }

    return document.querySelector('.controls') || document.querySelector('.nav');
  }

  function parseStoredList(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      console.warn(`Could not read localStorage key ${key}.`, error);
      return [];
    }
  }

  function saveStoredList(key, items) {
    localStorage.setItem(key, JSON.stringify(items));
  }

  function trimAndDedupe(items, maxItems) {
    const seen = new Set();
    const deduped = [];
    items.forEach((item) => {
      const huntCode = normalizeKey(item?.hunt_code);
      if (!huntCode || seen.has(huntCode)) return;
      seen.add(huntCode);
      deduped.push({ ...item, hunt_code: huntCode });
    });
    return deduped.slice(0, maxItems);
  }

  function getBasket() {
    const current = parseStoredList(BASKET_KEY);
    if (current.length) return trimAndDedupe(current, MAX_BASKET_ITEMS);
    const legacy = parseStoredList(LEGACY_BASKET_KEY);
    return trimAndDedupe(legacy, MAX_BASKET_ITEMS);
  }

  function setBasket(items) {
    const next = trimAndDedupe(items, MAX_BASKET_ITEMS);
    saveStoredList(BASKET_KEY, next);
    localStorage.removeItem(LEGACY_BASKET_KEY);
    notifyBackpackChanged();
    return next;
  }

  function getRecentHunts() {
    return trimAndDedupe(parseStoredList(RECENTS_KEY), MAX_RECENT_ITEMS);
  }

  function setRecentHunts(items) {
    const next = trimAndDedupe(items, MAX_RECENT_ITEMS);
    saveStoredList(RECENTS_KEY, next);
    notifyBackpackChanged();
    return next;
  }

  function buildHuntRecord(record) {
    const huntCode = normalizeKey(record?.hunt_code || record?.huntCode || record?.code);
    if (!huntCode) return null;
    return {
      hunt_code: huntCode,
      huntCode,
      hunt_name: safeText(record?.hunt_name || record?.huntName || record?.title || huntCode).trim() || huntCode,
      unit: safeText(record?.unit || record?.unit_name || record?.unitName || record?.dwr_unit_name || '').trim(),
      unit_code: safeText(record?.unit_code || record?.unitCode || '').trim(),
      species: safeText(record?.species || '').trim(),
      sex: safeText(record?.sex || record?.sex_type || '').trim(),
      weapon: safeText(record?.weapon || '').trim(),
      hunt_type: safeText(record?.hunt_type || record?.huntType || '').trim(),
      hunt_class: safeText(record?.hunt_class || record?.huntClass || '').trim(),
      residency: safeText(record?.residency || '').trim(),
      draw_pool: normalizeDrawPool(record?.draw_pool || record?.drawPool),
      selected_points: record?.selected_points ?? record?.points ?? null,
      points: record?.selected_points ?? record?.points ?? null,
      boundary_id: safeText(record?.boundary_id || record?.boundaryId || '').trim(),
      season_dates: safeText(record?.season_dates || record?.seasonDates || record?.dates || '').trim(),
      source: safeText(record?.source || 'hunt-builder').trim(),
      projected_total_probability_pct: record?.projected_total_probability_pct ?? null,
      updated_at: Number(record?.updated_at) || Date.now()
    };
  }

  function recordRecentHunt(record) {
    const nextRecord = buildHuntRecord(record);
    if (!nextRecord) return null;
    const items = getRecentHunts().filter((item) => normalizeKey(item.hunt_code) !== nextRecord.hunt_code);
    items.unshift(nextRecord);
    setRecentHunts(items);
    return nextRecord;
  }

  function setSelectedHuntCode(huntCode) {
    const code = normalizeKey(huntCode);
    if (!code) return;
    localStorage.setItem(SELECTED_HUNT_KEY, code);
  }

  function formatProbability(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 'Open it to see odds';
    if (parsed >= 99.95) return 'Projected 100%';
    if (parsed >= 10) return `${parsed.toFixed(1)}% projected`;
    if (parsed >= 1) return `${parsed.toFixed(2)}% projected`;
    return `${parsed.toFixed(3)}% projected`;
  }

  function formatPoints(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${parsed.toLocaleString()} pt${parsed === 1 ? '' : 's'}` : '';
  }

  function getCurrentPageHref() {
    const path = (window.location.pathname || '').toLowerCase();
    if (path.endsWith('/research.html') || path.endsWith('research.html')) return './research.html';
    if (path.endsWith('/verify.html') || path.endsWith('verify.html')) return './verify.html';
    return './index.html';
  }

  function itemMeta(item) {
    const parts = [];
    if (item.species) parts.push(item.species);
    if (item.weapon) parts.push(item.weapon);
    if (item.residency) parts.push(item.residency);
    const points = formatPoints(item.selected_points);
    if (points) parts.push(points);
    return parts.join(' · ');
  }

  function itemSubvalue(item) {
    return item.projected_total_probability_pct === null || item.projected_total_probability_pct === undefined
      ? (item.unit || 'No projected read saved yet')
      : `${formatProbability(item.projected_total_probability_pct)}${item.unit ? ` · ${item.unit}` : ''}`;
  }

  function huntDataHref(item) {
    return `./hard-copy.html?hunt_code=${encodeURIComponent(item.hunt_code)}`;
  }

  function normalizeResidency(value) {
    return safeText(value).trim().toLowerCase().replace(/[\s_-]+/g, '') === 'nonresident'
      ? 'Nonresident'
      : 'Resident';
  }

  function normalizePoints(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? Math.round(parsed) : 12;
  }

  function researchHref(item) {
    const params = new URLSearchParams({
      hunt_code: item.hunt_code,
      residency: normalizeResidency(item.residency),
      points: String(normalizePoints(item.selected_points)),
      draw_pool: normalizeDrawPool(item.draw_pool)
    });
    return `./research.html?${params.toString()}`;
  }

  function persistResearchContext(item) {
    if (!item?.hunt_code) return;
    const payload = {
      ...item,
      huntCode: item.hunt_code,
      residency: normalizeResidency(item.residency),
      selected_points: normalizePoints(item.selected_points),
      points: normalizePoints(item.selected_points),
      draw_pool: normalizeDrawPool(item.draw_pool),
      source: item.source || 'hunt-backpack',
      updated_at: Date.now()
    };
    try {
      sessionStorage.setItem('selectedHuntForResearch', JSON.stringify(payload));
    } catch (_) {}
    try {
      localStorage.setItem('selectedHuntForResearch', JSON.stringify(payload));
      localStorage.setItem(SELECTED_HUNT_KEY, payload.hunt_code);
      localStorage.setItem('selected_hunt_research_residency', payload.residency);
      localStorage.setItem('selected_hunt_research_points', String(payload.selected_points));
      localStorage.setItem('selected_hunt_research_draw_pool', payload.draw_pool);
    } catch (_) {}
  }

  function createTrayMarkup(title, items, sectionType) {
    if (!items.length) {
      const emptyTitle = sectionType === 'saved' ? 'No saved hunts yet' : 'No recent hunts yet';
      const emptyCopy = sectionType === 'saved'
        ? 'Save a hunt from Hunt Research to keep a field-ready short list for clients.'
        : 'Open hunts in Planner or Hunt Research and they will start appearing in your Hunt Backpack.';
      return `
        <div class="uoga-backpack-empty">
          <strong>${emptyTitle}</strong>
          <p>${emptyCopy}</p>
        </div>
      `;
    }

    return `
      <div class="uoga-backpack-section-head">
        <span>${title}</span>
        <span class="uoga-backpack-section-count">${items.length}</span>
      </div>
      <div class="uoga-backpack-list">
        ${items.map((item) => {
          const itemResearchHref = researchHref(item);
          const dataHref = huntDataHref(item);
          return `
          <article class="uoga-backpack-item" data-hunt-code="${escapeHtml(item.hunt_code)}">
            <div class="uoga-backpack-item-top">
              <div>
                <p class="uoga-backpack-kicker">${sectionType === 'saved' ? 'Saved shortlist' : 'Recently opened'}</p>
                <h4>${escapeHtml(item.hunt_code)}</h4>
              </div>
              <a class="uoga-backpack-chip" href="${itemResearchHref}" data-backpack-link="research" data-hunt-code="${escapeHtml(item.hunt_code)}" data-draw-pool="${escapeHtml(normalizeDrawPool(item.draw_pool))}">Resume</a>
            </div>
            <div class="uoga-backpack-name">${escapeHtml(item.hunt_name || item.hunt_code)}</div>
            <div class="uoga-backpack-meta">${escapeHtml(itemMeta(item) || 'Hunt details will fill in as more research is saved.')}</div>
            <div class="uoga-backpack-subvalue">${escapeHtml(itemSubvalue(item))}</div>
            <div class="uoga-backpack-actions">
              <a href="${itemResearchHref}" data-backpack-link="research" data-hunt-code="${escapeHtml(item.hunt_code)}" data-draw-pool="${escapeHtml(normalizeDrawPool(item.draw_pool))}">Research</a>
              <a href="${dataHref}" data-backpack-link="hunt-data" data-hunt-code="${escapeHtml(item.hunt_code)}">Hunt Data</a>
              <a href="./index.html?hunt_code=${encodeURIComponent(item.hunt_code)}" data-backpack-link="planner" data-hunt-code="${escapeHtml(item.hunt_code)}">Planner</a>
              ${sectionType === 'saved'
                ? `<button type="button" data-backpack-remove="${escapeHtml(item.hunt_code)}">Remove</button>`
                : '<span class="uoga-backpack-ghost">Recent</span>'}
            </div>
          </article>
        `;
        }).join('')}
      </div>
    `;
  }

  function renderHuntBasketSidebar() {
    const el = document.getElementById('huntBasket');
    if (!el) return;
    const basket = getBasket();
    if (!basket.length) {
      el.innerHTML = '<div class="empty-note">Save hunts to compare them here.</div>';
      return;
    }
    el.innerHTML = basket.map((item) => `
      <article class="hunt-basket-card" data-hunt-code="${escapeHtml(item.hunt_code)}">
        <div class="hunt-basket-card-head">
          <span class="hunt-basket-code">${escapeHtml(item.hunt_code)}</span>
          <button type="button" class="secondary hunt-basket-remove" aria-label="Remove from saved hunts" data-basket-sidebar-remove="${escapeHtml(item.hunt_code)}">Remove</button>
        </div>
        <div class="hunt-basket-name">${escapeHtml(item.hunt_name || item.hunt_code)}</div>
        ${itemMeta(item) ? `<div class="hunt-basket-meta">${escapeHtml(itemMeta(item))}</div>` : ''}
        <div class="hunt-basket-sub">${escapeHtml(itemSubvalue(item))}</div>
        <div class="hunt-basket-actions">
          <button type="button" class="hunt-basket-open" data-basket-sidebar-open="${escapeHtml(item.hunt_code)}">View in planner</button>
          <a href="./research.html?hunt_code=${encodeURIComponent(item.hunt_code)}">Research</a>
        </div>
      </article>
    `).join('');

    el.querySelectorAll('[data-basket-sidebar-remove]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = normalizeKey(btn.getAttribute('data-basket-sidebar-remove'));
        if (!code) return;
        const next = getBasket().filter((item) => normalizeKey(item.hunt_code) !== code);
        setBasket(next);
      });
    });

    el.querySelectorAll('[data-basket-sidebar-open]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = normalizeKey(btn.getAttribute('data-basket-sidebar-open'));
        if (!code) return;
        if (typeof window.selectHuntByCode === 'function') {
          window.selectHuntByCode(code);
          document.getElementById('selectedHuntPanel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
          window.location.href = `./index.html?hunt_code=${encodeURIComponent(code)}`;
        }
      });
    });
  }

  function refreshBackpackUI() {
    renderBackpackTray();
    renderHuntBasketSidebar();
  }

  function closeBackpackTray() {
    if (!trayShell || !trayButton || !trayPanel) return;
    trayOpen = false;
    trayShell.classList.remove('is-open');
    document.body.classList.remove('uoga-backpack-open');
    trayButton.setAttribute('aria-expanded', 'false');
    trayPanel.setAttribute('aria-hidden', 'true');
  }

  function lockBackpackTopLayer() {
    if (!trayShell || !trayPanel) return;
    if (!shouldBackpackFloatWithViewport()) {
      trayShell.style.setProperty('position', 'relative', 'important');
      trayShell.style.setProperty('top', 'auto', 'important');
      trayShell.style.setProperty('right', 'auto', 'important');
      trayShell.style.setProperty('left', 'auto', 'important');
      trayShell.style.setProperty('z-index', '120', 'important');

      trayPanel.style.setProperty('position', 'absolute', 'important');
      trayPanel.style.setProperty('top', 'calc(100% + 12px)', 'important');
      trayPanel.style.setProperty('right', '0', 'important');
      trayPanel.style.setProperty('left', 'auto', 'important');
      trayPanel.style.setProperty('bottom', 'auto', 'important');
      trayPanel.style.setProperty('z-index', '121', 'important');
      return;
    }

    trayShell.style.setProperty('position', 'fixed', 'important');
    trayShell.style.setProperty('top', '12px', 'important');
    trayShell.style.setProperty('right', '18px', 'important');
    trayShell.style.setProperty('left', 'auto', 'important');
    trayShell.style.setProperty('z-index', '2147483646', 'important');

    trayPanel.style.setProperty('position', 'fixed', 'important');
    trayPanel.style.setProperty('z-index', '2147483647', 'important');

    if (window.innerWidth <= 900) {
      trayShell.style.setProperty('top', '10px', 'important');
      trayShell.style.setProperty('right', '12px', 'important');
    }
  }

  function positionBackpackTray() {
    if (!trayButton || !trayPanel) return;
    if (!shouldBackpackFloatWithViewport()) {
      trayPanel.style.top = 'calc(100% + 12px)';
      trayPanel.style.left = 'auto';
      trayPanel.style.right = '0';
      trayPanel.style.bottom = 'auto';
      trayPanel.style.width = 'min(430px, calc(100vw - 28px))';
      trayPanel.style.maxHeight = 'min(72vh, 760px)';
      trayPanel.style.setProperty('--uoga-backpack-notch-left', 'auto');
      return;
    }
    const rect = trayButton.getBoundingClientRect();
    if (window.innerWidth <= 900) {
      trayPanel.style.top = 'auto';
      trayPanel.style.left = '14px';
      trayPanel.style.right = '14px';
      trayPanel.style.bottom = '14px';
      trayPanel.style.width = 'auto';
      trayPanel.style.maxHeight = 'min(78vh, 760px)';
      trayPanel.style.setProperty('--uoga-backpack-notch-left', 'auto');
      return;
    }
    const panelWidth = Math.min(430, Math.max(320, window.innerWidth - 28));
    const centerX = rect.left + (rect.width / 2);
    // Center panel under the button, then clamp to viewport padding.
    const left = Math.min(window.innerWidth - panelWidth - 14, Math.max(14, Math.round(centerX - (panelWidth / 2))));
    trayPanel.style.top = `${rect.bottom + 12}px`;
    trayPanel.style.left = `${left}px`;
    trayPanel.style.right = 'auto';
    trayPanel.style.bottom = 'auto';
    trayPanel.style.width = `min(430px, calc(100vw - 28px))`;
    trayPanel.style.maxHeight = `min(72vh, 760px)`;
    // Notch (the small cap above the panel) should align under the toggle.
    const notchWidth = 132;
    const notchLeft = Math.max(18, Math.min(panelWidth - notchWidth - 18, Math.round(centerX - left - (notchWidth / 2))));
    trayPanel.style.setProperty('--uoga-backpack-notch-left', `${notchLeft}px`);
  }

  function openBackpackTray() {
    if (!trayShell || !trayButton || !trayPanel) return;
    lockBackpackTopLayer();
    renderBackpackTray();
    positionBackpackTray();
    trayOpen = true;
    trayShell.classList.add('is-open');
    document.body.classList.add('uoga-backpack-open');
    trayButton.setAttribute('aria-expanded', 'true');
    trayPanel.setAttribute('aria-hidden', 'false');
  }

  function toggleBackpackTray() {
    if (trayOpen) {
      closeBackpackTray();
    } else {
      openBackpackTray();
    }
  }

  function renderBackpackTray() {
    if (!traySections || !trayBadge) return;
    const basket = getBasket();
    const recent = getRecentHunts();
    const freshRecent = recent.filter((recentItem) => !basket.some((savedItem) => normalizeKey(savedItem.hunt_code) === normalizeKey(recentItem.hunt_code)));
    trayBadge.textContent = String(basket.length);
    trayBadge.hidden = basket.length === 0;
    traySections.innerHTML = `
      <div class="uoga-backpack-hero">
        <div>
          <p class="uoga-backpack-hero-kicker">U.O.G.A.</p>
          <h3>Hunt Backpack</h3>
        </div>
        <div class="uoga-backpack-hero-media" aria-hidden="true">
          <div class="uoga-backpack-hero-badge">
            <span class="uoga-backpack-hero-badge-kicker">U.O.G.A.</span>
            <span class="uoga-backpack-hero-badge-title">Hunt Backpack</span>
            
          </div>
        </div>
        <p>Keep a short list in motion across Planner, Hunt Research, and verification without losing your place.</p>
      </div>
      ${createTrayMarkup('Saved Hunts', basket, 'saved')}
      ${createTrayMarkup('Recently Viewed', freshRecent, 'recent')}
    `;

    traySections.querySelectorAll('[data-backpack-link]').forEach((link) => {
      link.addEventListener('click', () => {
        const huntCode = link.getAttribute('data-hunt-code');
        if (huntCode) setSelectedHuntCode(huntCode);
        const item = [...basket, ...freshRecent].find((candidate) => normalizeKey(candidate.hunt_code) === normalizeKey(huntCode));
        if (item && link.getAttribute('data-backpack-link') === 'research') persistResearchContext(item);
        if (link.hasAttribute('data-draw-pool')) {
          const drawPool = normalizeDrawPool(link.getAttribute('data-draw-pool'));
          localStorage.setItem('selected_hunt_research_draw_pool', drawPool);
        }
        closeBackpackTray();
      });
    });

    traySections.querySelectorAll('[data-backpack-remove]').forEach((button) => {
      button.addEventListener('click', () => {
        const huntCode = normalizeKey(button.getAttribute('data-backpack-remove'));
        if (!huntCode) return;
        const next = getBasket().filter((item) => normalizeKey(item.hunt_code) !== huntCode);
        setBasket(next);
      });
    });
  }

  function injectBackpackStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .uoga-backpack-shell {
        position: fixed !important;
        top: 12px !important;
        right: 18px !important;
        left: auto;
        flex: 0 0 auto;
        margin-left: 0;
        z-index: 2147483646 !important;
        isolation: isolate;
      }
      .topbar-right .uoga-backpack-shell,
      [data-backpack-host] .uoga-backpack-shell {
        margin-left: 0;
      }
      .uoga-backpack-shell.is-open {
        z-index: 2147483647 !important;
      }
      .uoga-backpack-toggle {
        position: relative;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        min-height: var(--uoga-shell-min-h, 50px);
        padding: var(--uoga-shell-pad, 6px 12px 6px 8px);
        border-radius: 999px;
        border: 1px solid var(--uoga-case-border, #d1ab83);
        background: var(--uoga-case-bg,
          radial-gradient(circle at 20% 0%, rgba(255,255,255,.98), transparent 36%),
          linear-gradient(180deg, #fffefa 0%, #f7efe6 52%, #ead8c4 100%));
        color: var(--text);
        font: inherit;
        cursor: pointer;
        box-shadow: var(--uoga-case-shadow, inset 0 1px 0 rgba(255,255,255,.98), inset 0 -2px 6px rgba(84,47,18,.12), 0 10px 24px rgba(58, 37, 18, 0.16));
        transition: transform 150ms ease, border-color 150ms ease, box-shadow 150ms ease, background 150ms ease;
      }
        .uoga-backpack-shell.is-open .uoga-backpack-toggle {
          border-color: var(--accent);
          background:
            radial-gradient(circle at 20% 0%, rgba(255,255,255,.98), transparent 36%),
            linear-gradient(180deg, #fffefa 0%, #fff3e4 48%, #ead8c4 100%);
          color: #2f1d12;
          box-shadow: 0 0 0 2px rgba(240, 120, 0, 0.18), 0 12px 28px rgba(82, 44, 20, 0.28);
        }
        .uoga-backpack-toggle:hover {
          transform: translateY(-2px) scale(1.015);
          border-color: var(--accent);
          box-shadow: 0 0 0 2px rgba(240, 120, 0, 0.18), 0 12px 28px rgba(82, 44, 20, 0.28);
        }
      .uoga-backpack-mark-wrap {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: var(--uoga-shell-inner-w, 176px);
        height: var(--uoga-shell-inner-h, 38px);
        padding: 0 16px;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, var(--accent) 52%, transparent);
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.22), transparent 34%),
          linear-gradient(180deg, rgba(57, 44, 34, 0.92), rgba(28, 22, 17, 0.96));
        box-shadow: 0 8px 18px rgba(0,0,0,0.28);
        overflow: hidden;
      }
      .uoga-backpack-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: var(--accent);
        font-size: 14px;
        font-weight: 900;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        line-height: 1;
        white-space: nowrap;
        opacity: 0.98;
      }
      .uoga-backpack-labels { display: grid; gap: 2px; text-align: left; }
      .uoga-backpack-title {
        font-size: 11px;
        font-weight: 900;
        line-height: 1;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .uoga-backpack-subtitle {
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
        line-height: 1;
      }
      .uoga-backpack-badge {
        min-width: 28px;
        padding: 5px 8px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--accent) 18%, transparent);
        border: 1px solid color-mix(in srgb, var(--accent) 38%, transparent);
        color: var(--accent);
        font-size: 12px;
        font-weight: 900;
        line-height: 1;
        text-align: center;
      }
      .uoga-backpack-panel {
        position: fixed !important;
        top: 74px !important;
        right: 14px !important;
        left: auto;
        width: min(430px, calc(100vw - 28px));
        max-height: min(72vh, 760px);
        display: none;
        overflow: auto;
        padding: 12px;
        border: 1px solid var(--line);
        border-radius: 28px 28px 24px 24px;
        background:
          linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, transparent), color-mix(in srgb, var(--panel2) 98%, transparent));
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.34);
        backdrop-filter: blur(14px);
        z-index: 2147483647 !important;
        transform-origin: top right;
        isolation: isolate;
      }
      .uoga-backpack-panel::before {
          content: "";
          position: absolute;
          top: -16px;
          right: 26px;
          left: auto;
          width: 132px;
          height: 28px;
        border: 1px solid var(--line);
        border-bottom: 0;
        border-radius: 18px 18px 0 0;
        background: linear-gradient(180deg, color-mix(in srgb, var(--panel2) 90%, transparent), color-mix(in srgb, var(--panel) 96%, transparent));
        box-shadow: 0 -8px 18px rgba(0,0,0,0.12);
      }
      .uoga-backpack-shell.is-open .uoga-backpack-panel { display: block; }
      .uoga-backpack-panel[aria-hidden="true"] { display: none; }
      .uoga-backpack-sections { display: grid; gap: 14px; }
      .uoga-backpack-hero {
        display: grid;
        gap: 8px;
        padding: 14px;
        border-radius: 22px;
        border: 1px solid color-mix(in srgb, var(--accent) 26%, var(--line));
        background:
          radial-gradient(circle at top left, rgba(240, 120, 0, 0.18), transparent 42%),
          linear-gradient(180deg, color-mix(in srgb, var(--panel2) 92%, transparent), color-mix(in srgb, var(--panel) 98%, transparent));
      }
      .uoga-backpack-hero-media {
        overflow: hidden;
        border-radius: 16px;
        border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.16), transparent 34%),
          linear-gradient(180deg, rgba(51, 39, 31, 0.94), rgba(25, 19, 15, 0.98));
      }
      .uoga-backpack-hero-badge {
        display: grid;
        place-items: center;
        gap: 6px;
        width: 100%;
        min-height: 118px;
        padding: 16px;
        text-align: center;
      }
      .uoga-backpack-hero-badge-kicker {
        color: rgba(255,255,255,0.72);
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }
      .uoga-backpack-hero-badge-title {
        color: var(--accent);
        font-size: 28px;
        font-weight: 900;
        line-height: 1;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .uoga-backpack-hero-badge-subtitle {
        color: rgba(255,255,255,0.78);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
      }
      .uoga-backpack-hero-image {
        display: block;
        width: 100%;
        height: 118px;
        object-fit: contain;
        object-position: center center;
      }
      .uoga-backpack-hero-kicker,
      .uoga-backpack-kicker {
        margin: 0 0 4px;
        color: var(--accent);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .uoga-backpack-hero h3,
      .uoga-backpack-item h4 {
        margin: 0;
        color: var(--text);
        font-family: var(--font-display, var(--font-ui));
        line-height: 1;
      }
      .uoga-backpack-hero p,
      .uoga-backpack-empty p,
      .uoga-backpack-meta,
      .uoga-backpack-subvalue {
        margin: 0;
        color: var(--muted);
        line-height: 1.42;
      }
      .uoga-backpack-section-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin: 2px 2px 0;
        color: var(--text);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .uoga-backpack-section-count,
      .uoga-backpack-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        padding: 5px 9px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--accent) 16%, transparent);
        color: var(--text);
        text-decoration: none;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .05em;
        text-transform: uppercase;
      }
      .uoga-backpack-list { display: grid; gap: 10px; }
      .uoga-backpack-item,
      .uoga-backpack-empty {
        display: grid;
        gap: 7px;
        padding: 12px;
        border-radius: 18px;
        border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
        background: color-mix(in srgb, var(--panel2) 94%, transparent);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      }
      .uoga-backpack-item-top {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 12px;
      }
      .uoga-backpack-name {
        color: var(--text);
        font-size: 15px;
        font-weight: 800;
        line-height: 1.2;
      }
      .uoga-backpack-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
      .uoga-backpack-actions a,
      .uoga-backpack-actions button,
      .uoga-backpack-ghost {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 34px;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: color-mix(in srgb, var(--panel) 92%, transparent);
        color: var(--text);
        text-decoration: none;
        font: inherit;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .05em;
        text-transform: uppercase;
        cursor: pointer;
      }
      .uoga-backpack-actions a:hover,
      .uoga-backpack-actions button:hover { border-color: var(--accent); }
      .uoga-backpack-ghost {
        border-style: dashed;
        color: var(--muted);
        cursor: default;
      }
      @media (max-width: 900px) {
        .uoga-backpack-shell {
          position: fixed !important;
          top: 10px !important;
          right: 12px !important;
          left: auto;
          width: auto;
          margin-left: 0;
        }
        .uoga-backpack-toggle {
          width: auto;
          justify-content: space-between;
        }
        .uoga-backpack-panel {
          top: auto !important;
          left: 14px !important;
          right: 14px !important;
          bottom: 14px !important;
          width: auto;
          max-height: min(78vh, 760px);
          padding: 10px;
          border-radius: 24px 24px 20px 20px;
          transform-origin: bottom center;
        }
        .uoga-backpack-panel::before {
          display: none;
        }
        .uoga-backpack-sections {
          gap: 12px;
        }
        .uoga-backpack-hero {
          padding: 12px;
          border-radius: 18px;
        }
        .uoga-backpack-hero-badge,
        .uoga-backpack-hero-image {
          min-height: 98px;
          height: 98px;
        }
        .uoga-backpack-hero-badge-title {
          font-size: 24px;
        }
        .uoga-backpack-item,
        .uoga-backpack-empty {
          padding: 10px;
          border-radius: 16px;
        }
        .uoga-backpack-actions {
          gap: 6px;
        }
        .uoga-backpack-actions a,
        .uoga-backpack-actions button,
        .uoga-backpack-ghost {
          flex: 1 1 120px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function initThemeToggle() {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (!themeToggleBtn) return;

    themeToggleBtn.addEventListener('click', () => {
      document.body.classList.toggle('theme-dark');
      const isDark = document.body.classList.contains('theme-dark');
      themeToggleBtn.textContent = isDark ? 'Light Mode' : 'Dark Mode';
    });
  }

  function initBackpackTray() {
    if (trayShell) {
      refreshBackpackUI();
      return;
    }

    const host = getBackpackHost();
    if (!host) return;

    injectBackpackStyles();

    trayShell = host.querySelector('.uoga-backpack-shell') || document.querySelector('.uoga-backpack-shell');
    if (!trayShell) {
      trayShell = document.createElement('div');
      trayShell.className = 'uoga-backpack-shell';
      trayShell.innerHTML = `
        <button type="button" class="uoga-backpack-toggle" aria-expanded="false" aria-haspopup="dialog">
          <span class="uoga-backpack-mark-wrap" aria-hidden="true">
            <span class="uoga-backpack-mark">Hunt Backpack</span>
          </span>
          <span class="uoga-backpack-badge" hidden>0</span>
        </button>
        <section class="uoga-backpack-panel" aria-hidden="true">
          <div class="uoga-backpack-sections"></div>
        </section>
      `;
      host.appendChild(trayShell);
    } else if (trayShell.parentElement !== host && isBuilderPage()) {
      host.appendChild(trayShell);
    }

    // Floating pages use a body mount so fixed positioning stays viewport-locked.
    if (shouldBackpackFloatWithViewport() && trayShell.parentElement !== document.body) {
      document.body.appendChild(trayShell);
    }

    trayButton = trayShell.querySelector('.uoga-backpack-toggle');
    trayPanel = trayShell.querySelector('.uoga-backpack-panel');
    trayBadge = trayShell.querySelector('.uoga-backpack-badge');
    traySections = trayShell.querySelector('.uoga-backpack-sections');
    lockBackpackTopLayer();

    trayButton.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleBackpackTray();
    });

      document.addEventListener('click', (event) => {
        if (!trayShell || trayShell.contains(event.target)) return;
        closeBackpackTray();
      });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeBackpackTray();
    });

      window.addEventListener('storage', (event) => {
        if ([BASKET_KEY, LEGACY_BASKET_KEY, RECENTS_KEY, SELECTED_HUNT_KEY].includes(event.key || '')) {
          refreshBackpackUI();
        }
      });

      window.addEventListener('resize', () => {
        if (trayOpen) positionBackpackTray();
      });

      window.addEventListener('scroll', () => {
        if (trayOpen) positionBackpackTray();
      }, { passive: true });

      document.addEventListener(BACKPACK_CHANGED_EVENT, refreshBackpackUI);
      refreshBackpackUI();
    }

  function notifyBackpackChanged() {
    document.dispatchEvent(new CustomEvent(BACKPACK_CHANGED_EVENT));
  }

  function initShell() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initShell, { once: true });
      return;
    }
    // Light-only theme: no runtime toggle.
    initBackpackTray();
    renderHuntBasketSidebar();
  }

  return {
    BASKET_KEY,
    RECENTS_KEY,
    SELECTED_HUNT_KEY,
    initShell,
    initThemeToggle,
    initBackpackTray,
    getBasket,
    setBasket,
    getRecentHunts,
    setRecentHunts,
    recordRecentHunt,
    setSelectedHuntCode,
    notifyBackpackChanged
  };
})();

window.UOGA_UI.initShell();

