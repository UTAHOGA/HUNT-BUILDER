(() => {
  function init() {
    const dock = document.getElementById('ownershipDock');
    if (!dock) return;
    dock.setAttribute('data-restored', 'true');
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
