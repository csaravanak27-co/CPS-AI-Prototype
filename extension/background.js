// C.P.S. — AI Coding Companion | Background Service Worker
// ============================================================================
// Manifest V3 service worker that handles:
//   - Context menu creation and click handling
//   - Side panel management
//   - AI query proxying to the local backend
//   - Conversation history persistence
//   - Extension settings management
// ============================================================================

import './shared/browser-api.js';

'use strict';

// Use the compatibility layer instead of depending on the browser's global
// name (`chrome` in Chromium and `browser` in Firefox).
const chrome = globalThis.cpsBrowser;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default extension settings */
const DEFAULT_SETTINGS = Object.freeze({
  backendUrl: 'http://localhost:8899',
  provider: 'mock',
  model: '',
  apiKey: '',
  theme: 'dark',
  selectionDetection: true,
});

/** Fetch timeout in milliseconds */
const FETCH_TIMEOUT_MS = 30_000;

/** Files injected after an explicit toolbar/context-menu action on other sites. */
const CONTENT_SCRIPT_FILES = Object.freeze([
  'shared/browser-api.js',
  'site_adapters/adapters.js',
  'content.js',
]);

/** Storage keys */
const STORAGE_KEY_HISTORY = 'cps_history';
const STORAGE_KEY_SETTINGS = 'cps_settings';

/** Maximum history entries to keep */
const MAX_HISTORY_ENTRIES = 200;

/**
 * Context menu action definitions.
 * Each entry maps an internal action id to a human-readable menu title.
 */
const CONTEXT_MENU_ACTIONS = [
  { id: 'explain',    title: 'C.P.S. — Explain Selection',        icon: '💡' },
  { id: 'solve',      title: 'C.P.S. — Solve Problem',            icon: '🧩' },
  { id: 'generate',   title: 'C.P.S. — Generate Code',            icon: '⚡' },
  { id: 'debug',      title: 'C.P.S. — Debug Code',               icon: '🐛' },
  { id: 'fix',        title: 'C.P.S. — Fix Error',                icon: '🔧' },
  { id: 'optimize',   title: 'C.P.S. — Optimize Code',            icon: '🚀' },
  { id: 'convert',    title: 'C.P.S. — Convert Code',             icon: '🔄' },
  { id: 'complexity', title: 'C.P.S. — Analyze Complexity',       icon: '📊' },
  { id: 'tests',      title: 'C.P.S. — Generate Tests',           icon: '🧪' },
  { id: 'security',   title: 'C.P.S. — Security Review',          icon: '🛡️' },
  { id: 'summarize',  title: 'C.P.S. — Summarize Selection',      icon: '📝' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Performs a fetch request with an AbortController-based timeout.
 * @param {string} url
 * @param {RequestInit} options
 * @param {number} [timeoutMs=FETCH_TIMEOUT_MS]
 * @returns {Promise<Response>}
 */
async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    clearTimeout(timer);
  }
}

function backendSetupGuidance(backendUrl, reason = 'stopped') {
  const endpoint = String(backendUrl || DEFAULT_SETTINGS.backendUrl).replace(/\/+$/, '');
  const reasonText = reason === 'invalid'
    ? 'The saved backend URL is not valid.'
    : 'The local backend is not running or could not be reached.';
  return {
    status: 'backend-stopped',
    title: 'Local backend not detected',
    message: `${reasonText} C.P.S. can still use offline mode, or a provider key you choose.`,
    backendUrl: endpoint,
    steps: [
      'Start the C.P.S. backend with: python -m backend.server',
      `Check that ${endpoint}/api/health opens in your browser.`,
      'Return to Settings and choose Test Provider Connection, then retry.',
    ],
  };
}

function classifyBackendFailure(error, backendUrl) {
  const invalidUrl = !/^https?:\/\//i.test(String(backendUrl || ''));
  return backendSetupGuidance(backendUrl, invalidUrl ? 'invalid' : 'stopped');
}

/**
 * Injects the content script only after a user gesture grants activeTab access.
 * Known coding sites already receive the static content script from the
 * manifest; the guard in content.js makes this safe for those pages too.
 */
async function ensureContentScript(tabId) {
  if (!tabId || !chrome.scripting?.executeScript) return false;
  await chrome.scripting.executeScript({ target: { tabId }, files: CONTENT_SCRIPT_FILES });
  return true;
}

/**
 * Retrieves current settings, merging stored values with defaults.
 * @returns {Promise<Object>}
 */
async function getSettings() {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY_SETTINGS);
    const stored = result[STORAGE_KEY_SETTINGS] || {};
    return { ...DEFAULT_SETTINGS, ...stored };
  } catch (err) {
    console.error('[C.P.S.] Failed to load settings:', err);
    return { ...DEFAULT_SETTINGS };
  }
}

/**
 * Saves settings to local storage.
 * @param {Object} settings
 * @returns {Promise<void>}
 */
async function saveSettings(settings) {
  const merged = { ...DEFAULT_SETTINGS, ...settings };
  merged.backendUrl = String(merged.backendUrl || DEFAULT_SETTINGS.backendUrl).trim().replace(/\/+$/, '');
  merged.provider = ['mock', 'ollama', 'groq', 'gemini', 'openrouter'].includes(merged.provider)
    ? merged.provider : DEFAULT_SETTINGS.provider;
  merged.model = String(merged.model || '').trim();
  merged.apiKey = String(merged.apiKey || '').trim();
  await chrome.storage.local.set({ [STORAGE_KEY_SETTINGS]: merged });
}

/**
 * Retrieves conversation history from local storage.
 * @returns {Promise<Array>}
 */
async function getHistory() {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY_HISTORY);
    return result[STORAGE_KEY_HISTORY] || [];
  } catch (err) {
    console.error('[C.P.S.] Failed to load history:', err);
    return [];
  }
}

/**
 * Saves a conversation entry to history.
 * Enforces MAX_HISTORY_ENTRIES limit by dropping oldest entries.
 * @param {Object} entry - { id, action, query, response, timestamp, url?, siteName? }
 * @returns {Promise<Array>} Updated history
 */
async function saveHistoryEntry(entry) {
  const history = await getHistory();
  const enrichedEntry = {
    id: entry.id || `cps_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    timestamp: entry.timestamp || new Date().toISOString(),
    ...entry,
  };
  history.unshift(enrichedEntry);
  if (history.length > MAX_HISTORY_ENTRIES) {
    history.length = MAX_HISTORY_ENTRIES;
  }
  await chrome.storage.local.set({ [STORAGE_KEY_HISTORY]: history });
  return history;
}

/**
 * Clears all conversation history.
 * @returns {Promise<void>}
 */
async function clearHistory() {
  await chrome.storage.local.set({ [STORAGE_KEY_HISTORY]: [] });
}

// ---------------------------------------------------------------------------
// AI Query Handler
// ---------------------------------------------------------------------------

const DIRECT_PROVIDER_DEFAULTS = Object.freeze({
  groq: { model: 'llama-3.3-70b-versatile' },
  gemini: { model: 'gemini-2.0-flash' },
  openrouter: { model: 'openai/gpt-4o-mini' },
});

function requestPrompt(payload) {
  const action = payload.action || 'chat';
  const language = payload.language || 'not specified';
  const code = payload.code || payload.text || '';
  const problem = payload.problem || '';
  const context = payload.context || '';
  return [
    `Action: ${action}`,
    `Language: ${language}`,
    problem ? `Problem statement:\n${problem}` : '',
    code ? `Code or selected text:\n${code}` : '',
    context ? `Additional context:\n${context}` : '',
    'Give a practical, concise answer. Preserve code indentation and Unicode.',
  ].filter(Boolean).join('\n\n');
}

function providerModel(settings) {
  return settings.model || DIRECT_PROVIDER_DEFAULTS[settings.provider]?.model || '';
}

function responseText(data) {
  if (typeof data === 'string') return data;
  if (data?.response && typeof data.response === 'object') {
    const structured = data.response;
    return structured.explanation || structured.code || structured.raw_response || JSON.stringify(structured, null, 2);
  }
  return data?.choices?.[0]?.message?.content
    || data?.candidates?.[0]?.content?.parts?.map((part) => part.text || '').join('')
    || data?.response?.response
    || data?.response
    || data?.result
    || '';
}

function offlineGuidance(payload) {
  const action = payload.action || 'chat';
  const subject = payload.code || payload.text || payload.problem ? 'the supplied text' : 'your request';
  const actionLabel = action === 'chat' ? 'answer' : `${action} review`;
  return [
    'C.P.S. is offline, so no remote model was contacted.',
    `You can still prepare ${actionLabel} for ${subject}:`,
    '1. Start the local C.P.S. backend at http://localhost:8899, or choose Groq, Gemini, or OpenRouter and save an API key in Settings.',
    '2. Select Test Connection, then retry this request.',
    '3. Until then, review the selected code locally: check inputs, error handling, authentication, secrets, and boundary cases.',
  ].join('\n');
}

async function queryDirectProvider(payload, settings) {
  const provider = settings.provider;
  const apiKey = settings.apiKey;
  if (!['groq', 'gemini', 'openrouter'].includes(provider)) {
    throw new Error(`Direct fallback is not configured for ${provider || 'this provider'}`);
  }
  if (!apiKey) throw new Error(`A ${provider} API key is required for direct fallback`);

  const model = providerModel(settings);
  const prompt = requestPrompt(payload);
  let url;
  let options;

  if (provider === 'gemini') {
    url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
    options = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
      body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }] }),
    };
  } else {
    url = provider === 'groq'
      ? 'https://api.groq.com/openai/v1/chat/completions'
      : 'https://openrouter.ai/api/v1/chat/completions';
    const headers = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    };
    if (provider === 'openrouter') {
      headers['HTTP-Referer'] = 'https://github.com/cps-ai';
      headers['X-Title'] = 'C.P.S. AI Coding Companion';
    }
    options = {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: 'You are C.P.S., a careful coding assistant.' },
          { role: 'user', content: prompt },
        ],
        temperature: 0.2,
      }),
    };
  }

  const response = await fetchWithTimeout(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`${provider} returned ${response.status}: ${data?.error?.message || data?.error || 'request failed'}`);
  }
  const text = responseText(data);
  if (!text) throw new Error(`${provider} returned an empty response`);
  return {
    success: true,
    data: { success: true, response: text, provider, model },
    source: 'direct',
  };
}

async function pingDirectProvider(settings) {
  const provider = settings.provider;
  if (!['groq', 'gemini', 'openrouter'].includes(provider)) {
    throw new Error(`Direct fallback is not configured for ${provider || 'this provider'}`);
  }
  if (!settings.apiKey) throw new Error(`A ${provider} API key is required for direct fallback`);

  let url;
  const headers = {};
  if (provider === 'gemini') {
    url = 'https://generativelanguage.googleapis.com/v1beta/models';
    headers['x-goog-api-key'] = settings.apiKey;
  } else if (provider === 'groq') {
    url = 'https://api.groq.com/openai/v1/models';
    headers.Authorization = `Bearer ${settings.apiKey}`;
  } else {
    url = 'https://openrouter.ai/api/v1/models';
    headers.Authorization = `Bearer ${settings.apiKey}`;
  }
  const response = await fetchWithTimeout(url, { method: 'GET', headers }, 8000);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${provider} returned ${response.status}: ${data?.error?.message || data?.error || 'request failed'}`);
  return { connected: true, mode: 'direct', provider, message: `${provider} connected`, data };
}

/**
 * Sends a query to the C.P.S. backend API.
 * @param {Object} payload
 * @param {string} payload.action   - The action type (explain, debug, etc.)
 * @param {string} [payload.code]   - Code to process
 * @param {string} [payload.language] - Programming language
 * @param {string} [payload.problem] - Problem statement
 * @param {string} [payload.context] - Additional context
 * @param {string} [payload.provider] - AI provider override
 * @param {string} [payload.model]   - Model override
 * @returns {Promise<Object>} API response
 */
async function queryAI(payload) {
  const settings = await getSettings();
  const effectiveSettings = {
    ...settings,
    provider: payload.provider || settings.provider,
    model: payload.model || settings.model,
  };
  const backendUrl = effectiveSettings.backendUrl || DEFAULT_SETTINGS.backendUrl;
  const url = `${backendUrl.replace(/\/+$/, '')}/api/query`;

  const body = {
    action: payload.action || 'chat',
    code: payload.code || '',
    language: payload.language || '',
    problem: payload.problem || '',
    context: payload.context || '',
    provider: effectiveSettings.provider || 'mock',
    model: effectiveSettings.model || '',
  };

  let localError = '';
  try {
    const response = await fetchWithTimeout(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      throw new Error(`Backend returned ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    return { success: true, data, source: 'local-backend' };
  } catch (err) {
    localError = err.name === 'AbortError'
      ? 'Local backend request timed out'
      : (err.message || 'Local backend unavailable');
  }

  // The local backend is always attempted first. Hosted providers are a
  // deliberate second choice and only receive a request when configured.
  try {
    return await queryDirectProvider(payload, effectiveSettings);
  } catch (directError) {
    const setup = classifyBackendFailure(localError, backendUrl);
    return {
      success: true,
      offline: true,
      backendStatus: setup.status,
      setup,
      data: {
        success: true,
        offline: true,
        provider: 'offline',
        response: offlineGuidance(payload),
      },
      error: `${setup.title}: ${setup.message} ${directError.message || 'Direct provider unavailable.'}`,
    };
  }
}

/**
 * Checks the backend health endpoint.
 * @returns {Promise<Object>} { connected: boolean, message?: string, data?: Object }
 */
async function checkConnection() {
  const settings = await getSettings();
  const backendUrl = settings.backendUrl || DEFAULT_SETTINGS.backendUrl;
  const url = `${backendUrl.replace(/\/+$/, '')}/api/health`;

  try {
    const response = await fetchWithTimeout(url, { method: 'GET' }, 8000);
    if (!response.ok) {
      throw new Error(`Backend returned status ${response.status}`);
    }
    const data = await response.json();
    return { connected: true, mode: 'local-backend', data, message: 'Local backend connected' };
  } catch (err) {
    const setup = classifyBackendFailure(err, backendUrl);
    try {
      const direct = await pingDirectProvider(settings);
      return {
        ...direct,
        backendStatus: setup.status,
        backendMessage: 'Local backend is not running; using the selected provider directly.',
        setup,
      };
    } catch (directError) {
      return {
        connected: false,
        mode: 'offline',
        backendStatus: setup.status,
        setup,
        fallbackAvailable: true,
        message: `${setup.title}: ${setup.message}`,
      };
    }
  }
}

async function testProviderConnection(settings) {
  if (settings.provider === 'mock') {
    return { connected: true, mode: 'offline', provider: 'mock', message: 'Offline provider ready' };
  }
  if (settings.provider === 'ollama') {
    return checkConnection();
  }
  try {
    return await pingDirectProvider(settings);
  } catch (err) {
    return { connected: false, mode: 'direct', provider: settings.provider, message: err.message || 'Provider connection failed' };
  }
}

// ---------------------------------------------------------------------------
// Context Menu Setup
// ---------------------------------------------------------------------------

/**
 * Creates all context menu entries on extension install.
 */
async function createContextMenus() {
  // Remove existing entries first to avoid duplicates on update
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({
    id: 'cps-parent',
    title: 'C.P.S. — AI Coding Companion',
    contexts: ['selection'],
  });
  for (const action of CONTEXT_MENU_ACTIONS) {
    chrome.contextMenus.create({
      id: `cps-action-${action.id}`,
      parentId: 'cps-parent',
      title: action.title,
      contexts: ['selection'],
    });
  }
}

// ---------------------------------------------------------------------------
// Event Listeners
// ---------------------------------------------------------------------------

/**
 * Extension installed / updated event.
 */
chrome.runtime.onInstalled.addListener((details) => {
  console.log(`[C.P.S.] Extension ${details.reason}: v${chrome.runtime.getManifest().version}`);
  createContextMenus().catch((err) => console.error('[C.P.S.] Context menu setup failed:', err));

  // Initialise default settings if first install
  if (details.reason === 'install') {
    chrome.storage.local.get(STORAGE_KEY_SETTINGS).then((result) => {
      if (!result[STORAGE_KEY_SETTINGS]) {
        return chrome.storage.local.set({ [STORAGE_KEY_SETTINGS]: { ...DEFAULT_SETTINGS } });
      }
      return undefined;
    }).catch(() => {});
  }
});

/**
 * Browser action (toolbar icon) clicked — open the side panel.
 */
chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (err) {
    console.error('[C.P.S.] Failed to open side panel:', err);
  }
});

/**
 * Context menu item clicked.
 * Extracts the selected text and forwards it to the sidebar.
 */
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!info.menuItemId.startsWith('cps-action-')) return;

  const actionId = info.menuItemId.replace('cps-action-', '');
  const selectedText = info.selectionText || '';

  if (!selectedText.trim()) return;

    try {
    // Send the selection to the content script to gather richer context,
    // then forward everything to the sidebar.
    let payload = {
      type: 'FROM_CONTEXT_MENU',
      action: actionId,
      text: selectedText,
      url: tab.url,
      siteName: '',
      context: '',
    };

    try {
      await ensureContentScript(tab.id);
    } catch (_) {
      // The selected text remains usable if the page refuses script access.
    }

    try {
      const response = await chrome.tabs.sendMessage(tab.id, {
        type: 'GET_CONTEXT',
        action: actionId,
      });
      if (response && response.context) {
        payload.context = response.context;
        payload.siteName = response.siteName || '';
      }
    } catch (_) {
      // Content script might not be ready — fall through
    }

    // Save as pending action so sidebar catches it even if delayed
    await chrome.storage.local.set({ cps_pending_action: payload });

    // Open the side panel
    await chrome.sidePanel.open({ tabId: tab.id });

    // Broadcast in case sidebar was already open
    chrome.runtime.sendMessage(payload).catch(() => {});
  } catch (err) {
    console.error('[C.P.S.] Context menu action failed:', err);
  }
});

/**
 * Central message handler.
 * Handles messages from the sidebar, popup, and content scripts.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // We must return true for async handlers to keep the message channel open
  const { type } = message;

  switch (type) {
    // ----- AI Query -----
    case 'QUERY_AI': {
      (async () => {
        try {
          const result = await queryAI(message.payload || message);
          // Optionally save to history
          if (result.success && message.saveHistory !== false) {
            await saveHistoryEntry({
              action: message.payload?.action || message.action || 'chat',
              query: message.payload?.code || message.payload?.problem || message.text || '',
              response: responseText(result.data),
              url: message.url || '',
              siteName: message.siteName || '',
            });
          }
          sendResponse(result);
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
      })();
      return true; // async
    }

    // ----- Connection Check -----
    case 'CHECK_CONNECTION': {
      checkConnection().then(sendResponse).catch((err) => {
        sendResponse({ connected: false, message: err.message });
      });
      return true;
    }

    // ----- Direct provider check (does not require the local backend) -----
    case 'TEST_PROVIDER': {
      getSettings().then((stored) => testProviderConnection({ ...stored, ...(message.settings || {}) })).then(sendResponse).catch((err) => {
        sendResponse({ connected: false, message: err.message || 'Provider test failed' });
      });
      return true;
    }

    // ----- History: Get -----
    case 'GET_HISTORY': {
      getHistory().then((history) => {
        sendResponse({ success: true, history });
      }).catch((err) => {
        sendResponse({ success: false, error: err.message, history: [] });
      });
      return true;
    }

    // ----- History: Save -----
    case 'SAVE_HISTORY': {
      saveHistoryEntry(message.entry || {}).then((history) => {
        sendResponse({ success: true, history });
      }).catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
      return true;
    }

    // ----- History: Clear -----
    case 'CLEAR_HISTORY': {
      clearHistory().then(() => {
        sendResponse({ success: true });
      }).catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
      return true;
    }

    // ----- Settings: Get -----
    case 'GET_SETTINGS': {
      getSettings().then((settings) => {
        sendResponse({ success: true, settings });
      }).catch((err) => {
        sendResponse({ success: false, error: err.message, settings: { ...DEFAULT_SETTINGS } });
      });
      return true;
    }

    // ----- Settings: Save -----
    case 'SAVE_SETTINGS': {
      saveSettings(message.settings || {}).then(() => {
        // Broadcast settings change to all content scripts
        chrome.tabs.query({}).then((tabs) => {
          for (const tab of tabs) {
            chrome.tabs.sendMessage(tab.id, {
                type: 'SETTINGS_UPDATED',
                settings: message.settings,
              }).catch(() => {});
          }
        }).catch(() => {});
        sendResponse({ success: true });
      }).catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
      return true;
    }

    // ----- Open Sidebar -----
    case 'OPEN_SIDEBAR': {
      (async () => {
        try {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            await chrome.sidePanel.open({ tabId: tab.id });
          }
          sendResponse({ success: true });
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
      })();
      return true;
    }

    // ----- Selection from content script -----
    case 'PROCESS_SELECTION': {
      (async () => {
        const payload = {
          type: 'FROM_CONTENT_SCRIPT',
          action: message.action,
          text: message.text,
          url: message.url,
          siteName: message.siteName,
          context: message.context || '',
        };
        // Persist pending action so sidebar catches it upon opening
        await chrome.storage.local.set({ cps_pending_action: payload });

        // Ensure side panel is opened
        try {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab) {
            await chrome.sidePanel.open({ tabId: tab.id });
          }
        } catch (_) {}

        // Broadcast to sidebar if already open
        chrome.runtime.sendMessage(payload).catch(() => {});
        sendResponse({ success: true });
      })();
      return true;
    }

    default:
      // Unknown message type — no-op
      return false;
  }
});

// ---------------------------------------------------------------------------
// Side Panel Behaviour
// ---------------------------------------------------------------------------

// Enable the side panel to open via the action button
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((err) => {
  console.warn('[C.P.S.] Could not set panel behaviour:', err);
});

console.log('[C.P.S.] Background service worker initialised.');
