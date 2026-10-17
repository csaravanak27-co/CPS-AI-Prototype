// C.P.S. — AI Coding Companion | Content Script
// ============================================================================
// Injected into all web pages. Responsibilities:
//   - Detect text selections and show a floating action button (FAB)
//   - Display a dropdown menu of AI actions on FAB click
//   - Extract enriched context from known coding platforms
//   - Communicate with the background service worker
//   - All UI rendered inside a Shadow DOM to avoid style leaks
// ============================================================================

'use strict';

(() => {
  const chrome = globalThis.cpsBrowser;
  // Guard against double-injection
  if (window.__cps_content_loaded) return;
  window.__cps_content_loaded = true;

  // -------------------------------------------------------------------------
  // Configuration
  // -------------------------------------------------------------------------

  const MIN_SELECTION_LENGTH = 4;

  const ACTIONS = [
    { id: 'explain',    icon: '💡', label: 'Explain' },
    { id: 'solve',      icon: '🧩', label: 'Solve' },
    { id: 'generate',   icon: '⚡', label: 'Generate Code' },
    { id: 'debug',      icon: '🐛', label: 'Debug' },
    { id: 'fix',        icon: '🔧', label: 'Fix Error' },
    { id: 'optimize',   icon: '🚀', label: 'Optimize' },
    { id: 'convert',    icon: '🔄', label: 'Convert' },
    { id: 'complexity', icon: '📊', label: 'Complexity' },
    { id: 'tests',      icon: '🧪', label: 'Generate Tests' },
    { id: 'security',   icon: '🛡️', label: 'Security Review' },
    { id: 'summarize',  icon: '📝', label: 'Summarize' },
  ];

  const KNOWN_SITES = [
    'leetcode', 'hackerrank', 'codeforces', 'codechef',
    'geeksforgeeks', 'github', 'gitlab', 'stackoverflow',
  ];

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------

  let selectionDetectionEnabled = true;
  let currentSelection = '';
  let fabVisible = false;
  let dropdownVisible = false;

  // -------------------------------------------------------------------------
  // Shadow DOM Host
  // -------------------------------------------------------------------------

  const hostEl = document.createElement('div');
  hostEl.id = 'cps-extension-host';
  hostEl.style.cssText = 'all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647;pointer-events:none;';
  document.documentElement.appendChild(hostEl);

  const shadow = hostEl.attachShadow({ mode: 'closed' });

  // Inject styles into shadow root
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    /* --- FAB --- */
    .cps-fab {
      position: fixed;
      z-index: 2147483646;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: #0b1220;
      border: 1.5px solid #1e2d44;
      color: #4f8ff7;
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 12px rgba(0,0,0,0.35);
      opacity: 0;
      transform: scale(0.5);
      transition: opacity 180ms ease, transform 180ms ease, background 180ms ease,
                  border-color 180ms ease, box-shadow 180ms ease;
      pointer-events: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      user-select: none;
      box-sizing: border-box;
      padding: 0;
      margin: 0;
    }
    .cps-fab.visible {
      opacity: 1;
      transform: scale(1);
      pointer-events: auto;
      animation: cps-pulse 2s ease-in-out 1;
    }
    .cps-fab:hover {
      background: #111d32;
      border-color: #4f8ff7;
      box-shadow: 0 2px 12px rgba(0,0,0,0.35), 0 0 12px rgba(79,143,247,0.25);
      transform: scale(1.1);
    }
    .cps-fab:active {
      transform: scale(0.95);
      background: #243550;
    }
    @keyframes cps-pulse {
      0% { box-shadow: 0 2px 12px rgba(0,0,0,0.35); }
      50% { box-shadow: 0 2px 12px rgba(0,0,0,0.35), 0 0 16px rgba(79,143,247,0.25); }
      100% { box-shadow: 0 2px 12px rgba(0,0,0,0.35); }
    }

    /* --- Dropdown --- */
    .cps-dropdown {
      position: fixed;
      z-index: 2147483647;
      min-width: 220px;
      max-width: 280px;
      max-height: 420px;
      overflow-y: auto;
      overflow-x: hidden;
      background: #0b1220;
      border: 1px solid #1e2d44;
      border-radius: 10px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.45), 0 2px 8px rgba(0,0,0,0.3);
      padding: 6px 0;
      opacity: 0;
      transform: translateY(-8px) scale(0.96);
      transition: opacity 180ms ease, transform 180ms ease;
      pointer-events: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      box-sizing: border-box;
      scrollbar-width: thin;
      scrollbar-color: #1a2940 transparent;
    }
    .cps-dropdown::-webkit-scrollbar { width: 5px; }
    .cps-dropdown::-webkit-scrollbar-track { background: transparent; }
    .cps-dropdown::-webkit-scrollbar-thumb { background: #1a2940; border-radius: 3px; }
    .cps-dropdown.visible {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }
    .cps-dropdown-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px 10px;
      border-bottom: 1px solid #1e2d44;
      margin-bottom: 4px;
    }
    .cps-dropdown-header .logo { font-size: 14px; color: #4f8ff7; }
    .cps-dropdown-header .title {
      font-size: 11px; font-weight: 600; color: #8899b0;
      text-transform: uppercase; letter-spacing: 0.8px;
    }
    .cps-dropdown-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      font-size: 13px;
      color: #e8edf5;
      cursor: pointer;
      transition: background 180ms ease, color 180ms ease;
      border: none;
      background: none;
      width: 100%;
      text-align: left;
      font-family: inherit;
      box-sizing: border-box;
      line-height: 1.3;
      user-select: none;
    }
    .cps-dropdown-item:hover {
      background: #1a2940;
      color: #6ba3ff;
    }
    .cps-dropdown-item:active { background: #243550; }
    .cps-dropdown-item .icon { font-size: 15px; width: 20px; text-align: center; opacity: 0.85; flex-shrink: 0; }
    .cps-dropdown-item .label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* --- Toast --- */
    .cps-toast {
      position: fixed;
      z-index: 2147483647;
      bottom: 24px;
      right: 24px;
      padding: 10px 18px;
      background: #111d32;
      color: #e8edf5;
      border: 1px solid #1e2d44;
      border-radius: 6px;
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      box-shadow: 0 2px 12px rgba(0,0,0,0.35);
      opacity: 0;
      transform: translateY(12px);
      transition: opacity 250ms ease, transform 250ms ease;
      pointer-events: none;
      border-left: 3px solid #4f8ff7;
    }
    .cps-toast.visible { opacity: 1; transform: translateY(0); }
    .cps-toast.success { border-left-color: #34d399; }
    .cps-toast.error { border-left-color: #f87171; }

    @media (prefers-reduced-motion: reduce) {
      .cps-fab, .cps-dropdown, .cps-toast {
        transition: none !important;
        animation: none !important;
      }
    }
    @media print {
      .cps-fab, .cps-dropdown, .cps-toast { display: none !important; }
    }
  `;
  shadow.appendChild(styleEl);

  // -------------------------------------------------------------------------
  // Create UI Elements
  // -------------------------------------------------------------------------

  const fab = document.createElement('div');
  fab.className = 'cps-fab';
  fab.textContent = '⚡';
  fab.title = 'C.P.S. — AI Coding Companion';
  shadow.appendChild(fab);

  const dropdown = document.createElement('div');
  dropdown.className = 'cps-dropdown';
  dropdown.innerHTML = `
    <div class="cps-dropdown-header">
      <span class="logo">⚡</span>
      <span class="title">C.P.S. Actions</span>
    </div>
    ${ACTIONS.map(
      (a) => `<div class="cps-dropdown-item" data-action="${a.id}">
        <span class="icon">${a.icon}</span>
        <span class="label">${a.label}</span>
      </div>`
    ).join('')}
  `;
  shadow.appendChild(dropdown);

  const toast = document.createElement('div');
  toast.className = 'cps-toast';
  shadow.appendChild(toast);

  // -------------------------------------------------------------------------
  // UI Helpers
  // -------------------------------------------------------------------------

  /**
   * Shows the FAB near the end of the current text selection.
   * @param {Selection} selection
   */
  function showFab(selection) {
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(selection.rangeCount - 1);
    const rect = range.getBoundingClientRect();

    // Position slightly to the right and below the selection end
    let x = rect.right + 8;
    let y = rect.top - 4;

    // Viewport boundary checks
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (x + 44 > vw) x = vw - 48;
    if (x < 4) x = 4;
    if (y < 4) y = rect.bottom + 4;
    if (y + 44 > vh) y = vh - 48;

    fab.style.left = `${x}px`;
    fab.style.top = `${y}px`;
    fab.classList.add('visible');
    fabVisible = true;
  }

  /**
   * Hides the FAB.
   */
  function hideFab() {
    fab.classList.remove('visible');
    fabVisible = false;
  }

  /**
   * Shows the dropdown menu near the FAB.
   */
  function showDropdown() {
    const fabRect = fab.getBoundingClientRect();
    let x = fabRect.left;
    let y = fabRect.bottom + 4;

    // Viewport adjustments
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (x + 250 > vw) x = vw - 260;
    if (x < 4) x = 4;
    if (y + 420 > vh) y = fabRect.top - 420 - 4;
    if (y < 4) y = 4;

    dropdown.style.left = `${x}px`;
    dropdown.style.top = `${y}px`;
    dropdown.classList.add('visible');
    dropdownVisible = true;
  }

  /**
   * Hides the dropdown menu.
   */
  function hideDropdown() {
    dropdown.classList.remove('visible');
    dropdownVisible = false;
  }

  /**
   * Hides all floating UI elements.
   */
  function hideAll() {
    hideFab();
    hideDropdown();
  }

  /**
   * Shows a brief toast notification.
   * @param {string} message
   * @param {'info'|'success'|'error'} [type='info']
   * @param {number} [durationMs=2500]
   */
  function showToast(message, type = 'info', durationMs = 2500) {
    toast.textContent = message;
    toast.className = `cps-toast ${type}`;
    // Force reflow
    void toast.offsetHeight;
    toast.classList.add('visible');

    setTimeout(() => {
      toast.classList.remove('visible');
    }, durationMs);
  }

  // -------------------------------------------------------------------------
  // Site Detection & Context
  // -------------------------------------------------------------------------

  /**
   * Detects the current site name from the hostname.
   * @returns {string} Detected site name or empty string.
   */
  function detectSite() {
    const hostname = window.location.hostname.toLowerCase();
    for (const site of KNOWN_SITES) {
      if (hostname.includes(site)) return site;
    }
    return '';
  }

  /**
   * Gathers enriched context using site adapters.
   * @returns {{ siteName: string, problem: string, code: string }}
   */
  function getEnrichedContext() {
    try {
      if (typeof window._cpsGetAdapter === 'function') {
        const adapter = window._cpsGetAdapter();
        return adapter.getContext();
      }
    } catch (err) {
      console.warn('[C.P.S.] Adapter error:', err);
    }
    return { siteName: detectSite(), problem: '', code: '' };
  }

  // -------------------------------------------------------------------------
  // Action Handling
  // -------------------------------------------------------------------------

  /**
   * Sends the selected text and action to the background service worker.
   * @param {string} actionId - One of the ACTIONS ids
   * @param {string} text - Selected text
   */
  function sendAction(actionId, text) {
    const context = getEnrichedContext();

    chrome.runtime.sendMessage({
      type: 'PROCESS_SELECTION',
      action: actionId,
      text: text,
      url: window.location.href,
      siteName: context.siteName,
      context: JSON.stringify({
        problem: context.problem,
        code: context.code,
      }),
    }).then(() => {
      showToast(`Sent to C.P.S. — ${actionId}`, 'success');
    }).catch((err) => {
      showToast('Failed to send to C.P.S.', 'error');
      console.error('[C.P.S.]', err);
    });

    hideAll();
  }

  // -------------------------------------------------------------------------
  // Event Listeners
  // -------------------------------------------------------------------------

  /**
   * Handle text selection via mouseup.
   */
  document.addEventListener('mouseup', (e) => {
    if (!selectionDetectionEnabled) return;

    // Ignore clicks inside our shadow DOM host
    if (e.target === hostEl || hostEl.contains(e.target)) return;

    // Small delay to let the selection settle
    setTimeout(() => {
      const selection = window.getSelection();
      const text = selection ? selection.toString().trim() : '';

      if (text.length >= MIN_SELECTION_LENGTH) {
        currentSelection = text;
        hideDropdown();
        showFab(selection);
      } else {
        // Only hide if click isn't on our elements
        if (!fabVisible && !dropdownVisible) return;
        // Check if the click was in the shadow DOM
        const path = e.composedPath();
        const clickedInside = path.includes(fab) || path.includes(dropdown);
        if (!clickedInside) {
          hideAll();
          currentSelection = '';
        }
      }
    }, 10);
  });

  /**
   * Handle keyboard selection changes.
   */
  document.addEventListener('selectionchange', () => {
    if (!selectionDetectionEnabled) return;

    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : '';

    if (text.length < MIN_SELECTION_LENGTH && fabVisible && !dropdownVisible) {
      hideAll();
      currentSelection = '';
    }
  });

  /**
   * FAB click — show dropdown.
   */
  fab.addEventListener('click', (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (dropdownVisible) {
      hideDropdown();
    } else {
      showDropdown();
    }
  });

  /**
   * Dropdown item click — trigger action.
   */
  dropdown.addEventListener('click', (e) => {
    const item = e.target.closest('.cps-dropdown-item');
    if (!item) return;

    e.stopPropagation();
    e.preventDefault();

    const actionId = item.dataset.action;
    if (actionId && currentSelection) {
      sendAction(actionId, currentSelection);
    }
  });

  /**
   * Click outside — hide everything.
   */
  document.addEventListener('mousedown', (e) => {
    if (!fabVisible && !dropdownVisible) return;

    // Check if click is inside our shadow DOM
    const path = e.composedPath();
    const clickedInside = path.includes(fab) || path.includes(dropdown);
    if (!clickedInside) {
      hideAll();
    }
  });

  /**
   * Escape key — hide everything.
   */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (fabVisible || dropdownVisible)) {
      hideAll();
    }
  });

  /**
   * Scroll — reposition or hide FAB.
   */
  let scrollTimer = null;
  window.addEventListener('scroll', () => {
    if (fabVisible || dropdownVisible) {
      hideAll();
      currentSelection = '';
    }
  }, { passive: true });

  // -------------------------------------------------------------------------
  // Message Handling (from background / sidebar)
  // -------------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
      case 'GET_CONTEXT': {
        // Background is requesting enriched context for a context menu action
        const context = getEnrichedContext();
        const selection = window.getSelection();
        sendResponse({
          context: JSON.stringify({
            problem: context.problem,
            code: context.code,
            selectedText: selection ? selection.toString().trim() : '',
          }),
          siteName: context.siteName,
        });
        return true;
      }

      case 'GET_SELECTION': {
        // Popup or sidebar wants the current selection
        const selection = window.getSelection();
        sendResponse({
          text: selection ? selection.toString().trim() : '',
          url: window.location.href,
          siteName: detectSite(),
        });
        return true;
      }

      case 'SETTINGS_UPDATED': {
        // Settings changed — update local state
        if (message.settings && typeof message.settings.selectionDetection !== 'undefined') {
          selectionDetectionEnabled = message.settings.selectionDetection;
          if (!selectionDetectionEnabled) {
            hideAll();
            currentSelection = '';
          }
        }
        sendResponse({ success: true });
        return true;
      }

      case 'PING': {
        sendResponse({ pong: true });
        return true;
      }

      default:
        return false;
    }
  });

  // -------------------------------------------------------------------------
  // Initialisation
  // -------------------------------------------------------------------------

  /**
   * Load settings and apply selection detection preference.
   */
  function init() {
    chrome.storage.local.get('cps_settings').then((result) => {
      const settings = result.cps_settings || {};
      if (typeof settings.selectionDetection !== 'undefined') {
        selectionDetectionEnabled = settings.selectionDetection;
      }
    }).catch((err) => {
      console.warn('[C.P.S.] Could not load settings:', err);
    });
  }

  init();
  console.log('[C.P.S.] Content script loaded on', window.location.hostname);
})();
