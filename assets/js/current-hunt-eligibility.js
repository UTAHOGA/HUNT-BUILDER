/* Selection eligibility only. Original catalogs and historical detail URLs remain intact. */
window.UOGA_HUNT_ELIGIBILITY = (() => {
  let manifest = null;
  let pending = null;
  const codeOf = value => String(typeof value === 'string' ? value
    : value?.hunt_code || value?.huntCode || value?.code || '').trim().toUpperCase();
  function install(value) {
    if (value?.schema !== 'hunt-eligibility.v1' || value.year !== 2026 || !value.records) {
      throw new Error('Current hunt eligibility evidence is invalid.');
    }
    manifest = value;
    return value;
  }
  async function load() {
    if (manifest) return manifest;
    if (!pending) pending = (async () => {
      const response = await fetch('./data/hunt-eligibility-2026.json?v=20260921-eligibility-1');
      if (!response.ok) throw new Error('Current hunt eligibility could not be verified.');
      return install(await response.json());
    })().catch(error => { pending = null; throw error; });
    return pending;
  }
  const get = value => manifest?.records?.[codeOf(value)] || null;
  const isCurrent = value => get(value)?.current_selectable === true;
  return { load, install, get, isCurrent };
})();
