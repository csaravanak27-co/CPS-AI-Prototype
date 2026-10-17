# C.P.S. — Browser Extension Installation & Deployment Guide

The C.P.S. Browser Extension is compatible with **Google Chrome, Microsoft Edge, Brave, and Firefox**, and follows the **Manifest V3** standard. It works standalone: requests try the local backend first, then a configured Groq, Gemini, or OpenRouter client, and finally provide deterministic offline guidance.

---

## 1. Unpacked Installation (Local Development)

### Step 1: Install or start the local companion
For customers, install the Windows desktop companion and launch the **C.P.S.**
shortcut. The installer creates a shortcut that starts the desktop app with the
local backend enabled. The backend binds only to `127.0.0.1` and does not need a
separate terminal window.

For a source checkout/developer setup, the extension communicates with the local
C.P.S. backend engine for AI processing and security scans:

```powershell
python -m backend.server
```
Confirm the console outputs:
```
============================================================
  C.P.S. Backend Server running on http://127.0.0.1:8899
  Compatible with C.P.S. Browser Extension & Desktop App
============================================================
```

### Step 2: Load Extension in Chrome
1. In the address bar, open: `chrome://extensions`
2. In the top-right corner, toggle **Developer mode** to ON.
3. Click the **Load unpacked** button in the top-left toolbar.
4. Browse to and select the `extension/` directory inside this repository:
   `<repository-root>/extension`
5. The extension card **C.P.S. — AI Coding Companion** (version 1.0.0) will appear.
6. Click the Extensions (puzzle piece) icon in your Chrome toolbar and pin **C.P.S.**.

### Step 3: Load Extension in Microsoft Edge
1. In the address bar, open: `edge://extensions`
2. In the left sidebar, toggle **Developer mode** to ON.
3. Click the **Load unpacked** button.
4. Select the `extension/` folder.

### Step 4: Load Extension in Firefox
1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on…** and choose `extension/manifest.json`.
3. Open the C.P.S. sidebar from the Firefox sidebar button. The extension uses
   `sidebar_action` when Firefox does not provide Chromium's `sidePanel` API.

If the desktop companion is not installed or the backend is stopped, the
extension displays setup guidance and can still use its offline provider. A
configured direct provider is optional; it is never required to install or use
local scanning features.

### Provider fallback and settings
Open the sidebar's **Settings** tab to save the backend URL, provider, model, and
API key in browser-local storage. **Test Provider Connection** checks the selected
provider directly; normal requests always try the local backend before using a
configured hosted provider. If neither is reachable, C.P.S. returns deterministic
offline guidance instead of failing silently. API keys are never included in
history entries.

---

## 2. Using Extension Features

### A. Persistent AI Sidebar
- Click the C.P.S. toolbar icon to open the popup, then click **Open Sidebar** (or click the Side Panel browser icon).
- The sidebar provides:
  - **Chat:** Conversational coding assistance and architecture questions.
  - **Code Studio:** Full code generation, explanation, debugging, optimization, test generation, and complexity analysis across 28+ languages.
  - **History:** Searchable conversation log persisted in browser storage.
  - **Settings:** Custom backend endpoints, provider selection, and themes.

### B. Highlight-to-Ask
1. On a supported coding site, highlight a snippet of code or problem statement.
   On another site, first invoke C.P.S. from the toolbar or context menu; the
   selection helper is added only for that user-initiated action.
2. A non-intrusive floating **⚡ C.P.S.** action button appears near your cursor.
3. Click it to choose from 11 specialized actions:
   - *Explain Selection*
   - *Solve Coding Question*
   - *Generate Complete Code*
   - *Debug Selected Code*
   - *Fix Error*
   - *Optimize Code*
   - *Convert Language*
   - *Explain Complexity*
   - *Generate Tests*
   - *Security Review*
   - *Summarize*

### C. Dedicated Coding Site Adapters
C.P.S. includes dedicated adapters that automatically extract problem statements and editor buffers on:
- **LeetCode:** Reads problem descriptions and Monaco editor buffers.
- **HackerRank:** Extracts problem statements and CodeMirror buffers.
- **Codeforces & CodeChef:** Captures challenge statements.
- **GeeksforGeeks:** Extracts article code blocks.
- **GitHub & GitLab:** Inspects blob files, PR diffs, and issue bodies.
- **Stack Overflow:** Extracts question text and accepted answers.

---

## 3. Official-store distribution (placeholder)

The project is not claiming an official store publication. Before a publisher
uploads a package, read `docs/STORE_LISTING.md` for reviewed copy and
`docs/STORE_RELEASE.md` for the release checklist. The publisher should use
the current official Chrome Web Store or Microsoft Edge Add-ons dashboard and
record the resulting listing identifier only after approval.

### Deterministic packaging

Run the offline validation and package commands from the repository root:

```bash
python scripts/validate_extension.py
python scripts/package_release.py
```

The extension ZIP has `manifest.json` at its root and is checked for stable
ordering, timestamps, required assets, narrow permissions, and excluded local
data. No store URL or publication status is assigned by this repository.
