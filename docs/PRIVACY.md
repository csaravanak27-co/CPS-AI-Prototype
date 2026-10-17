# C.P.S. — Privacy Policy & Data Governance

## 1. Core Privacy Philosophy

C.P.S. is architected around the principle of **User Data Sovereignty**:
- Your code is your intellectual property.
- Source code is never transmitted to any third party without explicit, user-initiated action.
- Scanned repositories are analyzed locally on your machine via static AST parsing and regex patterns.
- No background telemetry, analytics, or silent uploads exist in C.P.S.

---

## 2. Information Handled by C.P.S.

| Data Type | Where It Is Processed | Transmitted To | Retention Policy |
|---|---|---|---|
| **Local Project Files** | On host machine (CPU only) | None during scanning | Source contents are not stored; only aggregate scan counts are retained locally |
| **User Selections / Prompts** | Browser / host memory | Only to the local backend or provider explicitly selected by the user | Extension history remains in browser storage until cleared; unsent content is discarded when the request ends |
| **Scan History** | Local SQLite (`%LOCALAPPDATA%\CPS\history.db` on Windows; configurable with `CPS_DATA_DIR`) | None | Aggregate records are deleted on user “Clear History” or “Clear All User Data” action |
| **API Keys** | Browser-local extension settings or OS environment variables | Chosen direct provider API headers only | Optional, user-entered, never sent with local-backend requests, logged, or included in reports |
| **Patch Backups** | Local folder (`.cps_backup/`) | None | Kept until the user removes the backup folder |

---

## 3. Provider-Specific Privacy Controls

### A. Local Ollama (Gemma 4 / LLaMA)
- All prompt tokens, code snippets, and generated outputs stay 100% on your local machine (`http://localhost:11434`).
- No external network packets are created.
- Recommended for sensitive, proprietary, or air-gapped development environments.

### B. Hosted AI Services (Groq, Gemini, OpenRouter)
- Requires explicit user selection of the provider and manual API key configuration.
- Prompt text includes only the user-selected text and explicitly authorized context.
- Before transmission, the C.P.S. Context Manager runs an automated regex scrubber to redact passwords, API keys, and certificates.
- Governed by respective third-party terms:
  - [Google Gemini API Terms of Service](https://ai.google.dev/terms)
  - [Groq Privacy Policy](https://groq.com/privacy-policy/)
  - [OpenRouter Privacy Policy](https://openrouter.ai/privacy)

No hosted AI provider is contacted unless the user selects it and submits a
request. C.P.S. does not operate a proxy, account system, analytics service,
advertising service, or telemetry endpoint.

---

## 4. Browser Extension Permissions Explained

The C.P.S. Browser Extension requests only the minimum necessary Manifest V3 permissions:
- `activeTab`: Used solely for a user-initiated selection or context-menu action.
- `storage`: Used to persist local extension settings (theme, provider choice) and conversation history on your device.
- `sidePanel`: Used to display the persistent AI Coding companion in your browser's side panel.
- `contextMenus`: Used to register the "C.P.S. — Explain Selection", "Debug Code", and "Security Review" right-click options.
- `scripting`: Used only after a user-initiated action to add the selection helper on a page that is not one of the supported coding sites.
- `host_permissions: ["http://localhost:8899/*", "http://127.0.0.1:8899/*"]`: Allows the extension to communicate with the local C.P.S. backend server.
- Optional provider origins for `api.groq.com`, `generativelanguage.googleapis.com`, and `openrouter.ai` are requested only after the user selects a hosted provider and chooses **Save Settings** or **Test Provider Connection**. They are not granted at install time.

The extension does not request access to browser history, cookies, passwords, or unrelated tabs. Static page access is limited to the supported coding-site patterns in `manifest.json`; other pages require an explicit user action before the selection helper is injected.

## 5. Web Store Privacy Disclosure

For Chrome Web Store and Microsoft Edge Add-ons listings, use the following
consistent disclosure:

- **Data sold:** None.
- **Data used for advertising:** None.
- **Data used for creditworthiness, lending, or insurance:** None.
- **Authentication:** No C.P.S. account or sign-in is required.
- **Required permissions:** `activeTab`, `storage`, `sidePanel`, `contextMenus`, and
  `scripting` support user-initiated coding assistance; the localhost host
  permission is used only to reach the local C.P.S. backend at
  `http://localhost:8899`.
- **Remote code:** None. The extension ships its JavaScript with the package;
  it does not download or execute remote scripts.
- **User control:** Users can clear extension history in the extension UI and
  can remove all local desktop records from Settings & Privacy.

The four packaged PNG assets are original C.P.S. artwork at the exact
Manifest V3 sizes: `extension/icons/16.png`, `32.png`, `48.png`, and `128.png`.
