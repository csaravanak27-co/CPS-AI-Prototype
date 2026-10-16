# Project audit — 2026-10-16

## Input and test environment

The pasted brief referred to an uploaded ZIP, but no ZIP exists in the workspace. The available project checkout was audited instead. It includes source, docs, examples, tests, a local `.env`, an ignored `vulnquest_data/history.db`, and a `.venv` directory. The `.env` contents were not inspected or included in the source release ZIP. The `.venv` Python executable resolves to a missing Python 3.11 installation; tests were run using the available bundled Python 3.12.14 runtime. A clean source ZIP was created outside the project folder. PyInstaller completed an onedir build, but the packaged executable failed startup due to a QtCore DLL import error.

## Feature audit

| Feature | Expected behavior | Original implementation and evidence | Original status | Final status / required follow-up |
|---|---|---|---|---|
| Static scanner | Deterministic Python analysis; no source execution | `vulnquest/scanner.py`, `vulnquest/rules.py`; AST parse and 16 rules | PARTIAL | PARTIAL — retained and exposed by native UI; no runtime verification possible; rule accuracy is heuristic and malformed-file errors need clearer GUI presentation |
| Windows desktop GUI | Native responsive app, 13 screens | Original `app.py`, `vulnquest/ui.py`, `pages/*.py` used Streamlit | FAIL | PARTIAL — Python source initializes offscreen with all 13 pages; project scan, findings, history, export, and model-status paths are wired; packaged EXE startup fails importing QtCore; patch, verification, diff, and assistant screens disclose they are not wired |
| Gemma 4 identity/runtime | Verified Gemma 4 local inference, exact model/distribution, errors | Generic `OllamaProvider`, default `llama3.1`; default AI setting was Groq | FAIL | PARTIAL — default is Ollama tag `gemma4:e2b-it-q4_K_M`; runtime check confirmed Ollama is reachable but this tag is absent (only `llama3.2:latest` reported); no fallback occurs; inference not tested |
| Hosted-provider privacy | Local by default; hosted only by explicit choice | Multiple hosted providers and silent app default Groq; privacy statement overstated consent behavior | FAIL | PARTIAL — native UI selects only local Ollama, no hosted configuration/transmission path in the desktop shell; legacy hosted provider classes remain in library |
| Patch approval/application | Exact displayed patch approval, stale check, atomic write, backup, verify, rollback | `vulnquest/patcher.py` requires `approved=True`, hash check and backup; direct non-atomic writes; operating on workspace copy | PARTIAL | PARTIAL — retained as library code but not accessible from desktop UI; full source-file approval workflow and atomic write remain unimplemented |
| Verification Center | Stable finding matching, scanner-error distinction, new finding detection | `vulnquest/verification.py` uses rule/file plus 10-line proximity or snippet match; ignores scanner errors | PARTIAL | PARTIAL — not integrated into GUI; matching can confuse nearby same-rule findings and skipped/failed scans with resolution |
| Git diff scanner | Changed-line analysis, safe subprocess, edge cases | `vulnquest/git_diff.py` parses changed lines and calls `git diff`; limitations for renames, deletions, external context | PARTIAL | PARTIAL — library retained; native screen not wired up; only existing unit tests provide intended evidence, not run here |
| Local scan history | SQLite, local data, clear control | `vulnquest/storage.py` stores scan summary counts | PARTIAL | PARTIAL — UI exposes local history and clear action; does not store detailed findings or project metadata |
| Report exports | Redacted JSON/CSV/HTML/Markdown | `vulnquest/reports.py` implements formats/redaction | PASS | PARTIAL — native UI wires export functions; UI path not executed; removed DigitalOcean upload helper and module |
| Dependency/configuration | App dependencies match UI and defaults | `requirements.txt` and `pyproject.toml` listed Streamlit/Plotly/Pandas; defaults inconsistent with local-first claim; package discovery was ambiguous | FAIL | PARTIAL — manifests now specify PySide6, requests, dotenv and Bandit; explicit `vulnquest` package discovery added; `pip wheel . --no-deps --no-build-isolation` successfully built a wheel; complete dependency installation in the user's Python 3.11 venv is not verified |
| DigitalOcean | No DigitalOcean APIs or paid resources | `vulnquest/digitalocean.py` and automatic report upload helper existed | FAIL | PASS — upload module/helper removed; no current app reference remains |
| Credentials/release privacy | No secrets, databases, caches, venvs in release | `.env`, database, `.venv`, caches present in working checkout; `.gitignore` excludes most local artifacts | PARTIAL | PARTIAL — release instructions exclude these; no ZIP built because no Python runtime and no supplied ZIP; `.env` was not inspected |
| Tests | Run safety, scanner, model, patch, GUI tests | Existing `tests/` includes scanner/provider/patch/git tests and Streamlit startup tests | PARTIAL | PARTIAL — Streamlit startup tests replaced with offscreen PySide startup/navigation coverage; bundled Python `-m pytest -q`: 72 passed; model integration remains mocked/not tested |
| Windows packaging | Reproducible Windows build and tested artifact | No packaging script | NOT IMPLEMENTED | FAIL — added `scripts/build_windows.ps1`; PyInstaller emitted an onedir folder, but `VulnQuestAI.exe --self-check` failed with `ImportError: DLL load failed while importing QtCore`; no usable executable/installer |
| Documentation | Accurate Windows, Gemma, privacy and limitation guidance | README promised Streamlit, mock and broad feature completion | FAIL | PARTIAL — README rewritten with current UI, Gemma tag/license/size, setup and explicit gaps; several detailed workflow docs still need revision |

## Gemma 4 availability

Google's current Gemma 4 model card identifies E2B, E4B, 12B, 26B A4B, and 31B variants and lists Apache 2.0 licensing. Ollama's current library lists `gemma4:e2b-it-q4_K_M` at about 4.6 GB. This is an Ollama distribution tag for a quantized model; it is not presented as a Google-issued Ollama identifier. E2B is the practical default selected here. The model download is separate from this application. Actual RAM/GPU requirements depend on runtime, context, and offload settings; no hardware was available to measure them.

Sources: [Google Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4), [Google Gemma 4 license](https://ai.google.dev/gemma/docs/core/license), [Ollama Gemma 4 tags and sizes](https://registry.ollama.com/library/gemma4/tags).

## Required remaining work

1. Diagnose and fix the PyInstaller QtCore DLL load error; rerun the packaged self-check and launch/inspect the Windows GUI.
2. Finish patch proposal validation and an explicit per-patch approval UI; add atomic writes, encoding/line-ending preservation, isolated backups, rollback, concurrent-change and symlink tests.
3. Correct verification matching and report unable-to-verify when the before/after scanner errors or skips analysis.
4. Connect Git diff, assistant, and verification screens to the existing modules with background workers and actionable errors.
5. Test the default Gemma 4 model against a running Ollama install; measure startup/inference and resource use on a supported Windows machine.
6. Rebuild the PyInstaller output and confirm it starts; only then publish an executable release as tested.
