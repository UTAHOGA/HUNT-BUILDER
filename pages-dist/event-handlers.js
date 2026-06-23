/**
 * UOGA Centralized Event Handlers
 * Handles SPA navigation, page-specific action buttons, and event delegation.
 * Replaces inline onclick attributes with programmatic event binding.
 */
window.UOGA_EVENTS = (() => {

  /**
   * Bind SPA navigation links.
   * Intercepts clicks on elements with [data-spa-link] and routes via the hash router.
   * @param {Element} root - Root element to search within (default: document)
   */
  function bindSpaLinks(root) {
    const container = root || document;
    container.querySelectorAll('[data-spa-link]').forEach((el) => {
      if (el.dataset.spaLinkBound) return;
      el.dataset.spaLinkBound = '1';
      el.addEventListener('click', (event) => {
        const path = el.getAttribute('data-spa-link');
        if (!path) return;
        event.preventDefault();
        if (window.UOGA_ROUTER) {
          window.UOGA_ROUTER.navigate(path);
        } else {
          window.location.hash = path;
        }
      });
    });
  }

  /**
   * Bind hunt research hero action buttons.
   * Replaces inline onclick="document.getElementById(...)" handlers.
   * @param {Element} root - Root element to search within
   */
  function bindResearchHeroActions(root) {
    const container = root || document;

    const focusBtn = container.querySelector('[data-action="focus-hunt-code"]');
    if (focusBtn) {
      focusBtn.addEventListener('click', () => {
        const input = document.getElementById('huntCodeInput');
        if (input) input.focus();
      });
    }

    const backpackBtn = container.querySelector('[data-action="scroll-backpack"]');
    if (backpackBtn) {
      backpackBtn.addEventListener('click', () => {
        const list = document.getElementById('basketList');
        if (list) list.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }

  /**
   * Update document title and body class for the current page.
   * @param {string} page - One of 'planner', 'research', 'vetting'
   */
  function applyPageMeta(page) {
    const titles = {
      planner: 'Utah Hunt Planner',
      research: 'Utah Hunt Research',
      vetting: 'Outfitter Verification',
    };
    document.title = titles[page] || titles.planner;

    document.body.classList.remove('research-page');
    if (page === 'research') {
      document.body.classList.add('research-page');
    }
  }

  /**
   * Remove stale page-specific <style> tags injected by templates.
   */
  function cleanPageStyles() {
    ['research-page-styles', 'vetting-page-styles'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
  }

  /**
   * Bind all events for the current rendered page.
   * Call after every template render.
   * @param {string} page - One of 'planner', 'research', 'vetting'
   */
  function bindPageEvents(page) {
    bindSpaLinks(document);
    applyPageMeta(page);
    if (page === 'research') {
      bindResearchHeroActions(document);
    }
    // Re-initialize the shared UI shell (backpack tray, theme toggle) after each
    // template render so they attach to the freshly rendered .controls / .nav element.
    if (window.UOGA_UI && typeof window.UOGA_UI.initShell === 'function') {
      window.UOGA_UI.initShell();
    }
  }

  return {
    bindSpaLinks,
    bindResearchHeroActions,
    applyPageMeta,
    cleanPageStyles,
    bindPageEvents,
  };
})();


