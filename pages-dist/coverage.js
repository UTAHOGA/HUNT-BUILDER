(() => {
  const DATA_URL = './processed_data/coverage-matrix.json';

  const els = {
    generated: document.getElementById('coverageGenerated'),
    badges: document.getElementById('coverageBadges'),
    body: document.getElementById('coverageBody'),
    count: document.getElementById('coverageCount'),
    search: document.getElementById('searchInput'),
    bucket: document.getElementById('bucketSelect'),
    species: document.getElementById('speciesSelect'),
    needs: document.getElementById('needsSelect')
  };

  const state = {
    payload: null,
    rows: []
  };

  function safe(s) {
    return String(s || '').trim();
  }

  function escapeHtml(value) {
    return safe(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value), window.location.origin);
      return ['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol) ? url.href : '#';
    } catch {
      return '#';
    }
  }

  function pill(val) {
    const yes = !!val;
    return `<span class="pill-yn ${yes ? 'y' : 'n'}">${yes ? 'YES' : 'NO'}</span>`;
  }

  function setOptions(select, options, defaultValue) {
    if (!select) return;
    select.innerHTML = options
      .map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`)
      .join('');
    if (defaultValue) select.value = defaultValue;
  }

  function computeBadges(payload) {
    const t = payload.totals || {};
    return [
      { label: 'Total hunts', value: t.total ?? 0 },
      { label: 'Research coverage', value: t.research ?? 0 },
      { label: 'Engine rows', value: t.engine ?? 0 },
      { label: 'Ladder rows', value: t.ladder ?? 0 },
      { label: 'Harvest history', value: t.harvest ?? 0 }
    ];
  }

  function renderBadges(payload) {
    if (!els.badges) return;
    const badges = computeBadges(payload);
    els.badges.innerHTML = badges
      .map((b) => `<div class="coverage-badge"><strong>${escapeHtml(b.value)}</strong> ${escapeHtml(b.label)}</div>`)
      .join('');
  }

  function normalizeNeed(row, need) {
    if (need === 'missing_engine') return !row.hasEngineRow;
    if (need === 'missing_ladder') return !row.hasLadderRow;
    if (need === 'missing_harvest') return !row.hasHarvestHistoryRow;
    if (need === 'missing_research') return !row.hasResearchRow;
    return true;
  }

  function rowMatches(row, query) {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      safe(row.huntCode).toLowerCase().includes(q) ||
      safe(row.unitName).toLowerCase().includes(q) ||
      safe(row.species).toLowerCase().includes(q) ||
      safe(row.title).toLowerCase().includes(q) ||
      safe(row.huntType).toLowerCase().includes(q) ||
      safe(row.huntCategory).toLowerCase().includes(q)
    );
  }

  function currentFilters() {
    return {
      q: safe(els.search?.value),
      bucket: safe(els.bucket?.value),
      species: safe(els.species?.value),
      need: safe(els.needs?.value) || 'all'
    };
  }

  function applyFilters(rows, filters) {
    return rows.filter((r) => {
      if (filters.bucket && filters.bucket !== 'ALL' && safe(r.bucket) !== filters.bucket) return false;
      if (filters.species && filters.species !== 'ALL' && safe(r.species) !== filters.species) return false;
      if (!normalizeNeed(r, filters.need)) return false;
      if (!rowMatches(r, filters.q)) return false;
      return true;
    });
  }

  function renderTable(rows) {
    if (!els.body || !els.count) return;
    els.count.textContent = String(rows.length);

    const sorted = rows
      .slice()
      .sort((a, b) => (a.bucketRank ?? 999) - (b.bucketRank ?? 999) || safe(a.species).localeCompare(safe(b.species)) || safe(a.huntCode).localeCompare(safe(b.huntCode)));

    els.body.innerHTML = sorted
      .slice(0, 600) // keep fast; filters get you to what you need
      .map((r) => {
        const code = escapeHtml(r.huntCode);
        const boundaryHref = r.boundaryLink ? safeUrl(r.boundaryLink) : '';
        const link = boundaryHref && boundaryHref !== '#'
          ? `<a class="code-link" href="${escapeHtml(boundaryHref)}" target="_blank" rel="noopener noreferrer">${code}</a>`
          : code;
        return `
          <tr>
            <td>${link}</td>
            <td>${escapeHtml(r.bucket || '')}</td>
            <td>${escapeHtml(r.species || '')}</td>
            <td>${escapeHtml(r.unitName || r.unitCode || '')}</td>
            <td>${pill(r.hasResearchRow)}</td>
            <td>${pill(r.hasEngineRow)}</td>
            <td>${pill(r.hasLadderRow)}</td>
            <td>${pill(r.hasHarvestHistoryRow)}</td>
            <td>${escapeHtml(r.geometryStatus || '')}</td>
          </tr>
        `;
      })
      .join('');
  }

  function rerender() {
    if (!state.payload) return;
    const f = currentFilters();
    const filtered = applyFilters(state.rows, f);
    renderTable(filtered);
  }

  async function load() {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Failed to load ${DATA_URL}: ${res.status}`);
    const payload = await res.json();

    state.payload = payload;
    state.rows = Array.isArray(payload.rows) ? payload.rows : [];

    if (els.generated) {
      const when = payload.generatedAt ? new Date(payload.generatedAt).toLocaleString() : 'Unknown';
      els.generated.innerHTML = `<strong>Generated</strong> ${escapeHtml(when)}`;
    }

    const buckets = Array.isArray(payload.buckets) ? payload.buckets : [];
    const bucketOptions = [['ALL', 'All']].concat(buckets.map((b) => [safe(b.bucket), `${safe(b.bucket)} (${b.total ?? 0})`])); // value,label
    setOptions(els.bucket, bucketOptions, 'ALL');

    const speciesSet = new Set(state.rows.map((r) => safe(r.species)).filter(Boolean));
    const speciesOptions = [['ALL', 'All']].concat(Array.from(speciesSet).sort().map((s) => [s, s]));
    setOptions(els.species, speciesOptions, 'ALL');

    renderBadges(payload);
    rerender();
  }

  function wire() {
    ['input', 'change'].forEach((evt) => {
      els.search?.addEventListener(evt, rerender);
      els.bucket?.addEventListener(evt, rerender);
      els.species?.addEventListener(evt, rerender);
      els.needs?.addEventListener(evt, rerender);
    });
  }

  wire();
  load().catch((err) => {
    console.error(err);
    if (els.generated) els.generated.textContent = 'Failed to load coverage matrix.';
  });
})();

