(function () {
  const AUDIT_CSV = './processed_data/normalized-staging-audit.csv';

  const els = {
    summary: document.getElementById('auditSummary'),
    body: document.getElementById('auditTableBody')
  };

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function parseCsv(text) {
    const lines = String(text || '').trim().split(/\r?\n/);
    if (!lines.length) return [];
    const header = lines[0].split(',').map((h) => h.trim());
    const rows = [];
    for (let i = 1; i < lines.length; i += 1) {
      const parts = lines[i].split(',');
      const row = {};
      header.forEach((h, idx) => {
        row[h] = parts[idx] ?? '';
      });
      rows.push(row);
    }
    return rows;
  }

  function pill(value) {
    const v = String(value || '').toUpperCase();
    const good = v === 'YES';
    const bad = v === 'NO';
    const cls = good ? 'likelihood-guaranteed' : bad ? 'likelihood-longshot' : 'likelihood-unknown';
    const label = good ? 'YES' : bad ? 'NO' : v || '—';
    return `<span class="${cls}" style="font-weight:800;">${label}</span>`;
  }

  function valueRatio(hit, scanned) {
    const h = Number(hit || 0);
    const s = Number(scanned || 0);
    if (!s) return '—';
    const pct = Math.round((h / s) * 100);
    const cls = h > 0 ? 'likelihood-guaranteed' : 'likelihood-longshot';
    return `<span class="${cls}" style="font-weight:800;">${h}/${s} (${pct}%)</span>`;
  }

  async function load() {
    try {
      const res = await fetch(`${AUDIT_CSV}?v=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      const rows = parseCsv(text);

      const structured = rows.filter((r) => String(r.structured).toUpperCase() === 'YES').length;
      const blob = rows.filter((r) => String(r.blob_style).toUpperCase() === 'YES').length;

      els.summary.textContent = `Files: ${rows.length}. Structured (header-level): ${structured}. Blob-style: ${blob}.`;

      els.body.innerHTML = rows
        .map((r) => {
          const matched = Number(r.sample_codes_in_canonical || 0);
          const sampled = Number(r.sample_unique_hunt_codes || 0);
          const pct = sampled ? Math.round((matched / sampled) * 100) : 0;
          const scanned = Number(r.sample_rows_scanned_for_values || 0);
          return `
            <tr>
              <td style="font-weight:700;">${escapeHtml(r.file)}</td>
              <td>${pill(r.structured)}</td>
              <td>${pill(r.blob_style)}</td>
              <td>${valueRatio(r.sample_rows_with_points_value, scanned)}</td>
              <td>${valueRatio(r.sample_rows_with_applicants_value, scanned)}</td>
              <td>${valueRatio(r.sample_rows_with_permits_value, scanned)}</td>
              <td>${sampled ? `${matched}/${sampled} (${pct}%)` : '—'}</td>
            </tr>
          `;
        })
        .join('');
    } catch (err) {
      els.summary.textContent = 'Could not load staging audit.';
      console.error(err);
    }
  }

  load();
})();
