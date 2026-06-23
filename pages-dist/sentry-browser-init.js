(() => {
  if (typeof window === 'undefined' || !window.Sentry) return;

  const host = String(window.location?.hostname || '').toLowerCase();
  const isLocal = host === 'localhost'
    || host === '127.0.0.1'
    || host === '::1'
    || host === '[::1]';

  window.Sentry.init({
    dsn: 'https://26137c5576f01423efc85f47076f9548@o4511313324736512.ingest.us.sentry.io/4511313367334912',
    environment: isLocal ? 'development' : 'production',
    tracesSampleRate: isLocal ? 1.0 : 0.1,
    replaysSessionSampleRate: isLocal ? 0.0 : 0.05,
    replaysOnErrorSampleRate: 1.0,
    ignoreErrors: [
      'ResizeObserver loop limit exceeded',
      'Non-Error promise rejection captured',
    ],
  });
})();

