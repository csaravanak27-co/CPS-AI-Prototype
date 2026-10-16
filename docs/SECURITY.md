# Security architecture and limits

VulnQuest scans Python source as data. It uses `ast.parse` and pattern rules; syntax checks use compilation without evaluating the resulting code object. It never imports or runs a project being scanned. This is static analysis: it can miss issues and return false positives.

The native desktop entry point is `app.py` (PySide6). Folder scanning runs on a background `QThread`; scan summaries are written to the local SQLite database managed by `vulnquest/storage.py`. Reports redact finding snippets. The UI currently uses only Ollama at the local configured endpoint for AI; the library retains optional hosted-provider modules, which the desktop app does not select.

The current desktop app does not apply patches. The legacy patch helper in `vulnquest/patcher.py` requires an `approved=True` flag and a SHA-256 freshness check, and creates a backup before writing to the selected work directory. It is not yet an atomic, encoding-preserving source editor and must not be treated as a complete approval workflow. The desktop Patch Lab explains this limitation.

Verification in `vulnquest/verification.py` is static and heuristic. It compares rule identifiers, paths, lines, and snippets. It does not execute tests from scanned projects. Finding disappearance is not proof that a vulnerability is fixed; scanner errors or skipped files make verification inconclusive.

Ollama inference is local only when pointed at a local Ollama server. A user-configured remote endpoint could transmit supplied source context; do not configure a remote endpoint unless that transmission is intended. The desktop UI does not expose hosted API providers or silent fallback.

See [AUDIT.md](AUDIT.md) for implementation status and unverified items.
