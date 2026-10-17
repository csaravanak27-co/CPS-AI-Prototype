// C.P.S. — AI Coding Companion | Sidebar Logic
// ============================================================================
// Complete sidebar controller (600+ lines) handling:
//   - Tab switching
//   - Chat with markdown rendering
//   - Code tab with action processing
//   - Conversation history management
//   - Settings persistence and connection testing
//   - Real-time message handling from content script / background
// ============================================================================

'use strict';

(() => {
  const chrome = globalThis.cpsBrowser;
  // =========================================================================
  // DOM References
  // =========================================================================

  // Header
  const connDot = document.getElementById('connDot');
  const connText = document.getElementById('connText');

  // Tabs
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  // Chat
  const chatMessages = document.getElementById('chatMessages');
  const chatWelcome = document.getElementById('chatWelcome');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');
  const chatCancelBtn = document.getElementById('chatCancelBtn');

  // Code
  const codeLanguage = document.getElementById('codeLanguage');
  const codeEditor = document.getElementById('codeEditor');
  const codeActionBtns = document.querySelectorAll('.code-action-btn');
  const codeOutputArea = document.getElementById('codeOutputArea');
  const codeOutput = document.getElementById('codeOutput');
  const copyOutputBtn = document.getElementById('copyOutputBtn');
  const exportOutputBtn = document.getElementById('exportOutputBtn');

  // History
  const historyList = document.getElementById('historyList');
  const historyEmpty = document.getElementById('historyEmpty');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');

  // Settings
  const settingBackendUrl = document.getElementById('settingBackendUrl');
  const settingProvider = document.getElementById('settingProvider');
  const settingModel = document.getElementById('settingModel');
  const settingApiKey = document.getElementById('settingApiKey');
  const settingTheme = document.getElementById('settingTheme');
  const settingSelection = document.getElementById('settingSelection');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const testConnBtn = document.getElementById('testConnBtn');
  const testConnStatus = document.getElementById('testConnStatus');

  // =========================================================================
  // State
  // =========================================================================

  let isProcessing = false;
  let currentAbortController = null;
  let lastRetryPayload = null;
  let conversationMessages = [];

  const PROVIDER_ORIGINS = {
    groq: 'https://api.groq.com/*',
    gemini: 'https://generativelanguage.googleapis.com/*',
    openrouter: 'https://openrouter.ai/*',
  };

  /**
   * Request a hosted-provider origin only when the user chooses that provider.
   * This keeps install-time warnings minimal while preserving direct fallback.
   */
  async function ensureProviderPermission(provider) {
    const origin = PROVIDER_ORIGINS[provider];
    if (!origin || !chrome.permissions?.request) return true;
    const request = { origins: [origin] };
    if (chrome.permissions.contains && await chrome.permissions.contains(request)) return true;
    return Boolean(await chrome.permissions.request(request));
  }

  // =========================================================================
  // Tab Switching
  // =========================================================================

  /**
   * Switches to the specified tab.
   * @param {string} tabId - Tab identifier (chat, code, history, settings)
   */
  function switchTab(tabId) {
    tabBtns.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    tabPanels.forEach((panel) => {
      panel.classList.toggle('active', panel.id === `panel${capitalize(tabId)}`);
    });

    // Refresh data when switching to certain tabs
    if (tabId === 'history') loadHistory();
    if (tabId === 'settings') loadSettings();
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // =========================================================================
  // Markdown Renderer
  // =========================================================================

  /**
   * Simple markdown-to-HTML converter.
   * Supports: headings, bold, italic, inline code, code blocks, lists.
   * @param {string} text - Raw markdown text
   * @returns {string} HTML string
   */
  function renderMarkdown(text) {
    if (!text) return '';

    let html = escapeHTML(text);

    // Code blocks: ```lang\n...\n```
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const langLabel = lang || 'code';
      const id = `cb_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      return `<div class="code-block-wrapper">` +
        `<div class="code-block-header">` +
        `<span>${escapeHTML(langLabel)}</span>` +
        `<button class="code-copy-btn" data-copy-id="${id}">Copy</button>` +
        `</div>` +
        `<pre class="code-block" id="${id}">${code}</pre>` +
        `</div>`;
    });

    // Headings: # to ######
    html = html.replace(/^(#{1,6})\s+(.+)$/gm, (_, hashes, text) => {
      const level = hashes.length;
      return `<h${level}>${text}</h${level}>`;
    });

    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    html = html.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, '<em>$1</em>');

    // Inline code: `code`
    html = html.replace(/`([^`]+?)`/g, '<code>$1</code>');

    // Unordered lists: - item
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

    // Ordered lists: 1. item
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

    // Paragraphs: double newline
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph if not already
    if (!html.startsWith('<') || html.startsWith('<br>')) {
      html = `<p>${html}</p>`;
    }

    return html;
  }

  /**
   * Escape HTML special characters.
   * @param {string} str
   * @returns {string}
   */
  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = String(str ?? '');
    return div.innerHTML;
  }

  /** Converts both backend structured responses and direct-provider text into
   * safe display text without losing code indentation or Unicode. */
  function responseToText(data) {
    if (typeof data === 'string') return data;
    const value = data?.response ?? data?.result ?? data;
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object') {
      return value.explanation || value.code || value.raw_response || JSON.stringify(value, null, 2);
    }
    return String(value ?? '');
  }

  // =========================================================================
  // Chat Functionality
  // =========================================================================

  /**
   * Displays a message in the chat area.
   * @param {'user'|'assistant'|'error'} role
   * @param {string} content
   * @param {string} [timestamp]
   */
  function displayMessage(role, content, timestamp) {
    // Hide welcome on first message
    if (chatWelcome) chatWelcome.style.display = 'none';

    const now = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (role === 'error') {
      const errorDiv = document.createElement('div');
      errorDiv.className = 'message-error';
      errorDiv.innerHTML = `
        <span>⚠️ ${escapeHTML(content)}</span>
        <button class="retry-btn" id="retryBtn">Retry</button>
      `;
      chatMessages.appendChild(errorDiv);

      errorDiv.querySelector('.retry-btn').addEventListener('click', () => {
        errorDiv.remove();
        retryLastMessage();
      });
    } else {
      const messageDiv = document.createElement('div');
      messageDiv.className = `message ${role === 'user' ? 'user' : 'assistant'}`;

      const roleName = role === 'user' ? 'You' : 'C.P.S.';
      const renderedContent = role === 'user' ? `<p>${escapeHTML(content)}</p>` : renderMarkdown(content);

      messageDiv.innerHTML = `
        <div class="message-header">
          <span class="message-role">${roleName}</span>
          <span class="message-time">${now}</span>
        </div>
        <div class="message-content">${renderedContent}</div>
      `;

      chatMessages.appendChild(messageDiv);

      // Attach copy handlers for code blocks
      messageDiv.querySelectorAll('.code-copy-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          const codeEl = messageDiv.querySelector(`#${btn.dataset.copyId}`);
          if (codeEl) {
            navigator.clipboard.writeText(codeEl.textContent).then(() => {
              btn.textContent = 'Copied!';
              setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
            });
          }
        });
      });
    }

    scrollToBottom();
  }

  /**
   * Shows the loading indicator in the chat.
   * @returns {HTMLElement} The loading element (for removal)
   */
  function showLoading() {
    const loader = document.createElement('div');
    loader.className = 'loading-indicator';
    loader.id = 'chatLoading';
    loader.innerHTML = '<div class="spinner"></div><span>C.P.S. is thinking…</span>';
    chatMessages.appendChild(loader);
    scrollToBottom();
    return loader;
  }

  /**
   * Removes the loading indicator.
   */
  function hideLoading() {
    const loader = document.getElementById('chatLoading');
    if (loader) loader.remove();
  }

  /**
   * Scrolls the chat container to the bottom.
   */
  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  /**
   * Sends a message to the AI backend and displays the response.
   * @param {string} text - User input or selected text
   * @param {string} [action='chat'] - Action type
   * @param {string} [context=''] - Additional context
   */
  async function sendMessage(text, action = 'chat', context = '') {
    if (!text.trim() || isProcessing) return;

    isProcessing = true;
    chatSendBtn.disabled = true;
    chatCancelBtn.classList.add('visible');

    // Save for potential retry
    lastRetryPayload = { text, action, context };

    // Display user message
    displayMessage('user', text);

    // Store in conversation
    conversationMessages.push({ role: 'user', content: text, timestamp: new Date().toISOString() });

    // Clear input
    chatInput.value = '';
    autoResizeTextarea();

    // Show loading
    showLoading();

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'QUERY_AI',
        payload: {
          action: action,
          code: text,
          language: '',
          problem: text,
          context: context,
        },
        text: text,
        saveHistory: true,
      });

      hideLoading();

      if (response && response.success) {
        const aiText = responseToText(response.data);
        displayMessage('assistant', aiText);
        conversationMessages.push({ role: 'assistant', content: aiText, timestamp: new Date().toISOString() });
      } else {
        const errMsg = response?.error || 'Unknown error occurred';
        displayMessage('error', errMsg);
      }
    } catch (err) {
      hideLoading();
      displayMessage('error', err.message || 'Failed to communicate with the extension.');
    } finally {
      isProcessing = false;
      chatSendBtn.disabled = false;
      chatCancelBtn.classList.remove('visible');
    }
  }

  /**
   * Retries the last failed message.
   */
  function retryLastMessage() {
    if (lastRetryPayload) {
      sendMessage(lastRetryPayload.text, lastRetryPayload.action, lastRetryPayload.context);
    }
  }

  /**
   * Auto-resizes the chat textarea based on content.
   */
  function autoResizeTextarea() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  }

  // Chat event listeners
  chatSendBtn.addEventListener('click', () => {
    const text = chatInput.value.trim();
    if (text) sendMessage(text);
  });

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (text) sendMessage(text);
    }
  });

  chatInput.addEventListener('input', autoResizeTextarea);

  chatCancelBtn.addEventListener('click', () => {
    // Abort current processing
    isProcessing = false;
    chatSendBtn.disabled = false;
    chatCancelBtn.classList.remove('visible');
    hideLoading();
    displayMessage('error', 'Request cancelled by user.');
  });

  // =========================================================================
  // Code Tab Functionality
  // =========================================================================

  /**
   * Processes code with the specified action.
   * @param {string} action - Action type (generate, explain, debug, etc.)
   */
  async function processCode(action) {
    const code = codeEditor.value.trim();
    const language = codeLanguage.value;

    if (!code) {
      codeOutputArea.classList.add('visible');
      codeOutput.innerHTML = '<p style="color:var(--warning);">Please enter some code first.</p>';
      return;
    }

    // Show loading in output area
    codeOutputArea.classList.add('visible');
    codeOutput.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Processing…</span></div>';

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'QUERY_AI',
        payload: {
          action: action,
          code: code,
          language: language,
          problem: '',
          context: `Language: ${language}`,
        },
        saveHistory: true,
      });

      if (response && response.success) {
        const result = responseToText(response.data);
        codeOutput.innerHTML = renderMarkdown(result);

        // Attach copy handlers for code blocks in output
        codeOutput.querySelectorAll('.code-copy-btn').forEach((btn) => {
          btn.addEventListener('click', () => {
            const codeEl = codeOutput.querySelector(`#${btn.dataset.copyId}`);
            if (codeEl) {
              navigator.clipboard.writeText(codeEl.textContent).then(() => {
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
              });
            }
          });
        });
      } else {
        codeOutput.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHTML(response?.error || 'Unknown error')}</p>`;
      }
    } catch (err) {
      codeOutput.innerHTML = `<p style="color:var(--error);">⚠️ ${escapeHTML(err.message)}</p>`;
    }
  }

  // Code action button listeners
  codeActionBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      if (action) processCode(action);
    });
  });

  // Copy output
  copyOutputBtn.addEventListener('click', () => {
    const text = codeOutput.textContent || codeOutput.innerText;
    navigator.clipboard.writeText(text).then(() => {
      copyOutputBtn.textContent = '✅ Copied!';
      setTimeout(() => { copyOutputBtn.textContent = '📋 Copy'; }, 1500);
    });
  });

  // Export output
  exportOutputBtn.addEventListener('click', () => {
    const text = codeOutput.textContent || codeOutput.innerText;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cps-output-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // Allow Tab key in code editor
  codeEditor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = codeEditor.selectionStart;
      const end = codeEditor.selectionEnd;
      codeEditor.value = codeEditor.value.substring(0, start) + '  ' + codeEditor.value.substring(end);
      codeEditor.selectionStart = codeEditor.selectionEnd = start + 2;
    }
  });

  // =========================================================================
  // History Tab
  // =========================================================================

  /**
   * Loads conversation history from storage and renders it.
   */
  async function loadHistory() {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'GET_HISTORY' });
      const history = response?.history || [];
      displayHistory(history);
    } catch (err) {
      console.error('[C.P.S. Sidebar] Failed to load history:', err);
      displayHistory([]);
    }
  }

  /**
   * Renders the history list.
   * @param {Array} history
   */
  function displayHistory(history) {
    // Remove all items except the empty placeholder
    const items = historyList.querySelectorAll('.history-item');
    items.forEach((item) => item.remove());

    if (!history || history.length === 0) {
      historyEmpty.style.display = 'block';
      return;
    }

    historyEmpty.style.display = 'none';

    history.forEach((entry) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.dataset.id = entry.id;

      const date = new Date(entry.timestamp);
      const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
                      ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      const preview = (entry.query || entry.response || '').substring(0, 80);

      item.innerHTML = `
        <div class="history-item-header">
          <span class="history-action-badge">${escapeHTML(entry.action || 'chat')}</span>
          <span class="history-date">${dateStr}</span>
        </div>
        <div class="history-preview">${escapeHTML(preview)}${preview.length >= 80 ? '…' : ''}</div>
      `;

      item.addEventListener('click', () => loadConversation(entry));
      historyList.appendChild(item);
    });
  }

  /**
   * Loads a conversation from history into the chat tab.
   * @param {Object} entry
   */
  function loadConversation(entry) {
    switchTab('chat');

    // Display the historical query and response
    if (entry.query) {
      displayMessage('user', entry.query, new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }
    if (entry.response) {
      displayMessage('assistant', entry.response, new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }
  }

  /**
   * Clears all history after confirmation.
   */
  async function clearHistoryAction() {
    if (!confirm('Are you sure you want to clear all conversation history? This cannot be undone.')) {
      return;
    }

    try {
      await chrome.runtime.sendMessage({ type: 'CLEAR_HISTORY' });
      displayHistory([]);
    } catch (err) {
      console.error('[C.P.S. Sidebar] Failed to clear history:', err);
    }
  }

  clearHistoryBtn.addEventListener('click', clearHistoryAction);

  // =========================================================================
  // Settings Tab
  // =========================================================================

  /**
   * Loads settings from storage and populates the form.
   */
  async function loadSettings() {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'GET_SETTINGS' });
      const settings = response?.settings || {};

      settingBackendUrl.value = settings.backendUrl || 'http://localhost:8899';
      settingProvider.value = settings.provider || 'mock';
      settingModel.value = settings.model || '';
      settingApiKey.value = settings.apiKey || '';

      const isDark = (settings.theme || 'dark') === 'dark';
      settingTheme.checked = isDark;
      applyTheme(isDark ? 'dark' : 'light');

      settingSelection.checked = settings.selectionDetection !== false;
    } catch (err) {
      console.error('[C.P.S. Sidebar] Failed to load settings:', err);
    }
  }

  /**
   * Saves current settings to storage.
   */
  async function saveSettings() {
    const settings = {
      backendUrl: settingBackendUrl.value.trim() || 'http://localhost:8899',
      provider: settingProvider.value,
      model: settingModel.value.trim(),
      apiKey: settingApiKey.value,
      theme: settingTheme.checked ? 'dark' : 'light',
      selectionDetection: settingSelection.checked,
    };

    try {
      const permissionGranted = await ensureProviderPermission(settings.provider);
      await chrome.runtime.sendMessage({ type: 'SAVE_SETTINGS', settings });
      applyTheme(settings.theme);
      if (!permissionGranted) {
        testConnStatus.textContent = 'Saved. Allow provider access to enable direct fallback.';
        testConnStatus.className = 'test-conn-status warning';
      }
      saveSettingsBtn.textContent = '✅ Saved!';
      setTimeout(() => { saveSettingsBtn.textContent = '💾 Save Settings'; }, 1500);
    } catch (err) {
      console.error('[C.P.S. Sidebar] Failed to save settings:', err);
      saveSettingsBtn.textContent = '❌ Failed';
      setTimeout(() => { saveSettingsBtn.textContent = '💾 Save Settings'; }, 1500);
    }
  }

  /**
   * Applies the theme to the document.
   * @param {'dark'|'light'} theme
   */
  function applyTheme(theme) {
    document.body.dataset.theme = theme;
  }

  /**
   * Tests the backend connection.
   */
  async function testConnection() {
    testConnBtn.disabled = true;
    testConnStatus.textContent = 'Testing…';
    testConnStatus.className = 'test-conn-status';

    try {
      const permissionGranted = await ensureProviderPermission(settingProvider.value);
      if (!permissionGranted) {
        throw new Error('Provider access was not granted; local backend and offline mode remain available.');
      }
      const response = await chrome.runtime.sendMessage({
        type: 'TEST_PROVIDER',
        settings: {
          backendUrl: settingBackendUrl.value.trim(),
          provider: settingProvider.value,
          model: settingModel.value.trim(),
          apiKey: settingApiKey.value.trim(),
        },
      });

      if (response && response.connected) {
        testConnStatus.textContent = `✅ ${response.message || 'Connected!'}`;
        testConnStatus.className = 'test-conn-status success';
        updateConnectionStatus(true);
      } else {
        testConnStatus.textContent = `❌ ${response?.message || 'Failed'}`;
        testConnStatus.className = 'test-conn-status error';
        updateConnectionStatus(false);
      }
    } catch (err) {
      testConnStatus.textContent = `❌ ${err.message}`;
      testConnStatus.className = 'test-conn-status error';
      updateConnectionStatus(false);
    } finally {
      testConnBtn.disabled = false;
    }
  }

  saveSettingsBtn.addEventListener('click', saveSettings);
  testConnBtn.addEventListener('click', testConnection);

  // Theme toggle live preview
  settingTheme.addEventListener('change', () => {
    applyTheme(settingTheme.checked ? 'dark' : 'light');
  });

  // =========================================================================
  // Connection Status
  // =========================================================================

  /**
   * Updates the connection status indicator in the header.
   * @param {boolean} connected
   */
  function updateConnectionStatus(connected) {
    connDot.classList.toggle('connected', connected);
    connText.textContent = connected ? 'Online' : 'Offline';
  }

  /**
   * Checks the backend connection status.
   */
  async function checkConnectionStatus() {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'CHECK_CONNECTION' });
      updateConnectionStatus(response?.connected === true);
    } catch {
      updateConnectionStatus(false);
    }
  }

  // =========================================================================
  // Message Handling (from background / content script)
  // =========================================================================

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
      case 'FROM_CONTENT_SCRIPT':
      case 'FROM_CONTEXT_MENU': {
        // Auto-switch to chat tab and process selection
        switchTab('chat');
        const text = message.text || '';
        const action = message.action || 'explain';
        const context = message.context || '';

        if (text.trim()) {
          sendMessage(text, action, context);
        }
        sendResponse({ success: true });
        return true;
      }

      case 'SETTINGS_UPDATED': {
        // Reload settings when changed externally
        loadSettings();
        sendResponse({ success: true });
        return true;
      }

      default:
        return false;
    }
  });

  // =========================================================================
  // Initialisation
  // =========================================================================

  async function init() {
    // Check connection
    await checkConnectionStatus();

    // Load settings
    await loadSettings();

    // Check for any pending action stored before sidebar finished opening
    try {
      const stored = await chrome.storage.local.get('cps_pending_action');
      if (stored && stored.cps_pending_action) {
        const actionData = stored.cps_pending_action;
        await chrome.storage.local.remove('cps_pending_action');
        switchTab('chat');
        if (actionData.text && actionData.text.trim()) {
          sendMessage(actionData.text, actionData.action || 'explain', actionData.context || '');
        }
      }
    } catch (err) {
      console.warn('[C.P.S.] Error draining pending action:', err);
    }

    // Focus chat input
    chatInput.focus();
  }

  init();
  console.log('[C.P.S.] Sidebar initialised.');
})();
