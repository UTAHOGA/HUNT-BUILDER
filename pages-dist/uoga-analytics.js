(() => {
  const config = window.UOGA_LOCAL_CONFIG?.POSTHOG_CONFIG || window.UOGA_CONFIG?.POSTHOG_CONFIG || {};
  const keyFromConfig = String(
    window.UOGA_LOCAL_CONFIG?.POSTHOG_PROJECT_KEY
    || window.UOGA_CONFIG?.POSTHOG_PROJECT_KEY
    || ''
  ).trim();
  const keyFromStorage = String(localStorage.getItem('uoga_posthog_project_key') || '').trim();
  const projectKey = keyFromStorage || keyFromConfig;

  const noop = { track: () => {} };
  window.UOGA_ANALYTICS = noop;

  if (!projectKey) {
    return;
  }

  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://us.i.posthog.com/static/array.js';
  script.onload = () => {
    if (!window.posthog) return;
    const host = String(window.location?.hostname || '').toLowerCase();
    const isLocal = host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
    const enableSessionRecording = !!config.enableSessionRecording;
    window.posthog.init(projectKey, {
      api_host: 'https://us.i.posthog.com',
      person_profiles: 'identified_only',
      capture_pageview: true,
      autocapture: false,
      capture_pageleave: false,
      disable_session_recording: !enableSessionRecording,
      mask_all_text: true,
      mask_all_element_attributes: true,
      loaded: () => {
        if (isLocal) {
          window.posthog.opt_out_capturing();
        }
      },
    });
    window.UOGA_ANALYTICS = {
      track: (event, props = {}) => {
        try {
          if (isLocal) return;
          window.posthog.capture(event, props);
        } catch (_) {
          // no-op
        }
      },
    };
  };
  document.head.appendChild(script);
})();
