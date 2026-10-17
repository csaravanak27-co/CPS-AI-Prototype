# C.P.S. — Universal AI Coding Companion & Security Platform

**C.P.S.** is an intelligent, multi-platform coding companion, browser extension, and security analysis workbench designed for modern software development, competitive programming, and code security analysis.

---

## 🌟 Key Capabilities

1. **Browser Extension (Chrome & Microsoft Edge, Manifest V3)**
   - Persistent AI sidebar with multi-tab interface (Chat, Code Studio, History, Settings).
   - Non-intrusive **Highlight-to-Ask** action button with intelligent context menus.
   - Dedicated site adapters for **LeetCode, HackerRank, Codeforces, CodeChef, GeeksforGeeks, GitHub, GitLab, and Stack Overflow**.
   - Generic DOM selection fallback for arbitrary documentation sites and web editors.

2. **Multi-Language Code Generation Engine**
   - Supports **28+ programming languages** (Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, PHP, Ruby, Kotlin, Swift, Dart, R, SQL, Bash, PowerShell, HTML, CSS, Scala, Perl, Lua, Julia, MATLAB, Haskell, Solidity).
   - Solution generation, step-by-step algorithmic explanation, bug fixes, performance optimization, multi-language translation, test generation, and algorithmic complexity analysis.

3. **Hybrid AI Provider Architecture**
   - **Local Inference (100% Private):** Ollama integration with Gemma 4 (`gemma4:e2b-it-q4_K_M`) or open-weight models. Zero telemetry or network transmission.
   - **Hosted Inference (High Speed):** Groq (LLaMA 3.3 70B), Google Gemini (Gemini 2.0 Flash), and OpenRouter.
   - **Deterministic Offline Assistant:** Built-in Mock provider requiring zero API keys, network access, or downloads.

4. **Static Code Security & Verification Engine**
   - Deterministic AST-based vulnerability scanning for Python and lexical security checks across all supported languages.
   - Interactive **Patch Lab** with unified diff previews, mandatory human approval, pristine backup preservation, and one-click rollback.
   - Independent **Verification Center** evaluating syntax validity, target vulnerability resolution, zero new findings introduced, and public API preservation.
   - **Git Diff Scanner** identifying newly introduced security flaws in working trees and staged commits.

5. **Safe Code Execution Sandbox**
   - Sandboxed local execution for Python, JavaScript (Node.js), C, C++, Go, Rust, and Java.
   - Strict process timeouts, memory limits, and isolated standard output/error separation.
   - Never executes code automatically — requires explicit human action.

6. **Native Windows Desktop Application (PySide6)**
   - Unified desktop workbench sharing the identical backend and core logic.
   - 13 specialized pages covering Code Studio, AI Chat, Project Scanner, Findings Explorer, Patch Lab, Verification Center, Git Diff Scanner, Sandbox, Reports, History, Model Manager, and Settings.

---

## 🚀 Quick Start Guide

### Prerequisites
- Windows 10/11
- Python 3.11+
- (Optional) [Ollama](https://ollama.com) for private local AI inference

### 1. Setup Environment

```powershell
# Clone or navigate to the repository
cd C.P.S

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install editable package
pip install -e .
```

### 2. Launch Desktop Application

```powershell
python app.py
```

### 3. Launch Shared Backend Server (for Extension & API)

```powershell
python -m backend.server
```
The server will start on `http://127.0.0.1:8899`.

### 4. Install Browser Extension in Chrome / Edge

1. Open your browser and navigate to:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
2. Enable **Developer mode** (toggle in upper right corner).
3. Click **Load unpacked**.
4. Select the `extension/` directory inside this repository.
5. Click the C.P.S. extension icon in your browser toolbar or press the side panel shortcut.

---

## 🔒 Privacy & Safety Boundaries

- **Zero Host Execution by Default:** Source code scanned by the security scanner is parsed into an abstract syntax tree and never executed.
- **Explicit Execution Sandboxing:** The Execution Sandbox executes user code strictly upon explicit user request with bounded subprocesses and timeouts.
- **Automated Credential Redaction:** Passwords, API tokens, high-entropy secrets, and private keys are redacted from scan previews and reports automatically.
- **Local-First Processing:** With the Ollama local provider, prompt context remains 100% on the local computer.

---

## 🧪 Testing & Verification

Run the full automated test suite (covering core, providers, scanner, code engine, context manager, executor, backend API, release packaging, and desktop UI):

```powershell
python -m pytest -v
```

For a reproducible Linux or CI run, use the checked-in runtime and lockfile:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
make test
make self-check
make package
```

The test suite is offline-safe: provider tests use deterministic mocks and
network calls are not required. `QT_QPA_PLATFORM=offscreen` is set by the
Makefile for headless self-checks.

### Docker build and deploy

The repository includes a pinned Python 3.11 Docker build with the system
libraries required by PySide6. Build and run the local backend with:

```bash
docker build -t cps-ai:1.0.0 .
docker run --rm -p 8899:8899 cps-ai:1.0.0
```

The backend listens on `http://127.0.0.1:8899` inside the container. For a
desktop install, use the native setup above; Docker is intended for the
headless backend and CI/release validation.

### Release archives

Run `python scripts/package_release.py` (or `make package`) to create clean,
deterministic archives under `dist/`:

- `dist/cps-extension-v1.0.0.zip` — store-uploadable extension package.
- `dist/cps-v1.0.0-release.zip` — standalone source and desktop release.

Local databases, backups, caches, `.env`, build output, and development
artifacts are excluded from both release workflows as appropriate.

---

## 📦 Project Architecture

```
C.P.S/
├── cps/                      # Core C.P.S. Python package
│   ├── ai_provider.py        # Multi-provider abstraction (Mock, Ollama, Groq, Gemini, OpenRouter)
│   ├── code_engine.py        # Multi-language code generation & analysis engine
│   ├── context_manager.py    # Context assembly, token budgeting & secret redaction
│   ├── executor.py           # Sandboxed code execution engine
│   ├── scanner.py            # Static AST & multi-language security scanner
│   ├── rules.py              # Detection rules (VQ001-VQ016)
│   ├── patcher.py            # Safe patch application, backup management & rollback
│   ├── verification.py       # Independent patch verification
│   ├── reports.py            # Redacted audit report generator (JSON, CSV, HTML, Markdown)
│   ├── git_diff.py           # Git diff change scanner
│   ├── storage.py            # Local SQLite scan history
│   ├── harness.py            # Model evaluation benchmark harness
│   └── config.py             # Configuration & environment loader
├── backend/                  # Shared Backend API
│   ├── __init__.py
│   └── server.py             # Dual FastAPI / Zero-dependency HTTP server (port 8899)
├── extension/                # Manifest V3 Browser Extension
│   ├── manifest.json         # Extension manifest
│   ├── background.js         # Service worker & context menu handler
│   ├── content.js            # Highlight-to-ask & DOM extraction
│   ├── content.css           # Floating action button styles
│   ├── icons/                # Extension badge icons (16, 32, 48, 128px)
│   ├── sidebar/              # Persistent side panel UI & logic
│   ├── popup/                # Extension toolbar popup UI & logic
│   └── site_adapters/        # Dedicated adapters for LeetCode, GitHub, HackerRank, etc.
├── desktop/                  # Native Desktop Application
│   └── app.py                # PySide6 desktop launcher
├── tests/                    # Comprehensive unit and integration tests (99 passed)
├── docs/                     # Full technical documentation suite
└── app.py                    # Root desktop application entry point
```

---

## 📄 License & Attribution

- **C.P.S. Application Code:** Released under the MIT License.
- **Gemma 4 Models:** Governed by Google's [Gemma Terms of Use](https://ai.google.dev/gemma/docs/core/license) and Apache 2.0 license.
- **Third-Party Dependencies:** PySide6 (LGPLv3), Requests (Apache 2.0), Bandit (Apache 2.0).
