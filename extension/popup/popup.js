// C.P.S. — AI Coding Companion | Popup Script
// ============================================================================
// Handles the small popup window shown when clicking the extension icon:
//   - Connection status check on load
//   - Quick action buttons that interact with active tab selection
//   - Sidebar opening
// ============================================================================

'use strict';

(() => {
  const chrome = globalThis.cpsBrowser;
  // -------------------------------------------------------------------------
  // DOM References
  // -------------------------------------------------------------------------

  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const statusMessage = document.getElementById('statusMessage');
  const setupGuidance = document.getElementById('setupGuidance');
  const setupGuidanceTitle = document.getElementById('setupGuidanceTitle');
  const setupGuidanceSteps = document.getElementById('setupGuidanceSteps');

  const actionSidebar = document.getElementById('actionSidebar');
  const actionCards = document.querySelectorAll('.action-card[data-action]');

  const CONTENT_SCRIPT_FILES = [
    'shared/browser-api.js',
    'site_adapters/adapters.js',
    'content.js',
  ];

  // -------------------------------------------------------------------------
  // Connection Check
  // -------------------------------------------------------------------------

  /**
   * Checks backend connectivity and updates the status indicator.
   */
  async function checkConnection() {
    statusText.textContent = 'Checking…';
    statusDot.classList.remove('connected');

    try {
      const response = await chrome.runtime.sendMessage({ type: 'CHECK_CONNECTION' });

      if (response && response.connected) {
        statusDot.classList.add('connected');
        statusText.textContent = response.mode === 'direct'
          ? (response.backendStatus === 'backend-stopped' ? 'Provider online; backend stopped' : 'Provider online')
          : 'Backend connected';
        renderSetupGuidance(response);
        if (response.backendMessage) showStatus(response.backendMessage, 'info');
      } else {
        statusText.textContent = response?.backendStatus === 'backend-stopped' ? 'Backend not running' : 'Offline';
        showStatus(response?.message || 'Offline guidance is available. Choose a provider in Settings.', 'error');
        renderSetupGuidance(response);
      }
    } catch (err) {
      statusText.textContent = 'Error';
      showStatus('Could not communicate with extension background.', 'error');
      renderSetupGuidance();
      console.error('[C.P.S. Popup] Connection check failed:', err);
    }
  }

  function renderSetupGuidance(response) {
    if (!setupGuidance || !response?.setup?.steps?.length) {
      if (setupGuidance) setupGuidance.hidden = true;
      return;
    }
    setupGuidance.hidden = false;
    setupGuidanceTitle.textContent = response.setup.title || 'Connection setup';
    setupGuidanceSteps.replaceChildren();
    response.setup.steps.forEach((step) => {
      const item = document.createElement('li');
      item.textContent = step;
      setupGuidanceSteps.appendChild(item);
    });
  }

  // -------------------------------------------------------------------------
  // Status Message
  // -------------------------------------------------------------------------

  /**
   * Shows a status message below the action cards.
   * @param {string} message
   * @param {'info'|'success'|'error'} [type='info']
   * @param {number} [autoHideMs=0] — 0 means persist
   */
  function showStatus(message, type = 'info', autoHideMs = 0) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message visible ${type}`;

    if (autoHideMs > 0) {
      setTimeout(() => {
        statusMessage.classList.remove('visible');
      }, autoHideMs);
    }
  }

  /**
   * Hides the status message.
   */
  function hideStatus() {
    statusMessage.classList.remove('visible');
  }

  // -------------------------------------------------------------------------
  // Sidebar Opener
  // -------------------------------------------------------------------------

  /**
   * Opens the C.P.S. side panel.
   */
  async function openSidebar() {
    try {
      // Try the direct sidePanel API first
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) {
        await chrome.sidePanel.open({ tabId: tab.id });
      }
      // Close the popup after opening sidebar
      window.close();
    } catch (err) {
      console.warn('[C.P.S. Popup] Direct sidePanel.open failed, trying message:', err);
      try {
        await chrome.runtime.sendMessage({ type: 'OPEN_SIDEBAR' });
        window.close();
      } catch (err2) {
        showStatus('Could not open the sidebar. Try clicking the extension icon in the toolbar.', 'error');
        console.error('[C.P.S. Popup] Sidebar open failed:', err2);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Action Handling
  // -------------------------------------------------------------------------

  /**
   * Gets the current text selection from the active tab.
   * @returns {Promise<{text: string, url: string, siteName: string}>}
   */
  async function getActiveTabSelection() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        return { text: '', url: '', siteName: '' };
      }

      try {
        const response = await chrome.tabs.sendMessage(tab.id, { type: 'GET_SELECTION' });
        return response || { text: '', url: '', siteName: '' };
      } catch (firstError) {
        if (!chrome.scripting?.executeScript) throw firstError;
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: CONTENT_SCRIPT_FILES });
        const response = await chrome.tabs.sendMessage(tab.id, { type: 'GET_SELECTION' });
        return response || { text: '', url: '', siteName: '' };
      }
    } catch (err) {
      console.warn('[C.P.S. Popup] Could not get selection:', err);
      return { text: '', url: '', siteName: '' };
    }
  }

  /**
   * Handles a quick action button click.
   * @param {string} action - Action name (explain, generate, debug, security)
   */
  async function handleAction(action) {
    hideStatus();
    showStatus('Getting selection…', 'info');

    const { text, url, siteName } = await getActiveTabSelection();

    if (!text || text.trim().length < 3) {
      showStatus('Select some code or text on the page first, then try again.', 'error', 4000);
      return;
    }

    showStatus('Sending to C.P.S.…', 'info');

    try {
      // Send to background for processing and sidebar display
      chrome.runtime.sendMessage({
        type: 'PROCESS_SELECTION',
        action: action,
        text: text.trim(),
        url: url,
        siteName: siteName,
      });

      // Open sidebar to show results
      await openSidebar();
    } catch (err) {
      showStatus(`Action failed: ${err.message}`, 'error', 4000);
      console.error('[C.P.S. Popup] Action failed:', err);
    }
  }

  // -------------------------------------------------------------------------
  // Event Listeners
  // -------------------------------------------------------------------------

  // Open Sidebar
  actionSidebar.addEventListener('click', (e) => {
    e.preventDefault();
    openSidebar();
  });

  // Quick Action Cards
  actionCards.forEach((card) => {
    card.addEventListener('click', (e) => {
      e.preventDefault();
      const action = card.dataset.action;
      if (action) {
        handleAction(action);
      }
    });
  });

  // -------------------------------------------------------------------------
  // Initialisation
  // -------------------------------------------------------------------------

  checkConnection();
})();
