/*
  Local development overrides for U.O.G.A.
  ------------------------------------------------------------------
  This file is loaded by the public pages, so it must stay harmless when
  the site is served from production or GitHub Pages.

  For local testing, put a browser-restricted localhost key below or set
  localStorage.uoga_google_maps_api_key in your browser dev tools.
*/
(function () {
  function isPrivateIpv4Host(host) {
    return /^10\./.test(host)
      || /^192\.168\./.test(host)
      || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
  }

  function isLocalDevHost() {
    if (typeof window === 'undefined') return false;
    if (window.location && window.location.protocol === 'file:') return true;
    var host = String((window.location && window.location.hostname) || '').toLowerCase();
    return host === 'localhost'
      || host === '127.0.0.1'
      || host === '::1'
      || host === '[::1]'
      || host.endsWith('.local')
      || host.endsWith('.lan')
      || isPrivateIpv4Host(host);
  }

  if (!isLocalDevHost()) return;

  var localConfig = {
    GOOGLE_MAPS_API_KEY: '',
    GOOGLE_MAPS_3D_MAP_ID: '',
    CLOUDFLARE_R2_BASE: '',
    POSTHOG_PROJECT_KEY: '',
    POSTHOG_CONFIG: {
      enableSessionRecording: false
    }
  };

  window.UOGA_LOCAL_CONFIG = Object.assign({}, window.UOGA_LOCAL_CONFIG || {}, localConfig);

  if (
    window.UOGA_CONFIG
    && localConfig.GOOGLE_MAPS_API_KEY
    && /^AIza[0-9A-Za-z_-]{35}$/.test(localConfig.GOOGLE_MAPS_API_KEY)
  ) {
    window.UOGA_CONFIG.GOOGLE_MAPS_API_KEY = localConfig.GOOGLE_MAPS_API_KEY;
  }
})();
