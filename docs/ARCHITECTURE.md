# Architecture

```mermaid
flowchart LR
    User --> Desktop[PySide6 desktop app]
    Desktop --> Scanner[AST and pattern scanner]
    Scanner --> Findings[Finding objects]
    Desktop --> SQLite[Local scan-summary database]
    Desktop --> Reports[Redacted JSON CSV HTML Markdown]
    Desktop -. optional local inference .-> Ollama[Local Ollama endpoint]
    Ollama --> Gemma[Gemma 4 model tag]
```

The native entry point is `app.py`. Core analysis, report, storage, provider, patch, and verification modules remain under `vulnquest/`. See [AUDIT.md](AUDIT.md): the patch approval workflow, interactive assistant, Git diff UI, and desktop verification UI are not complete. Legacy hosted provider code exists but is not selected by the desktop app.
