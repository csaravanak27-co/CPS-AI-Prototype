# VulnQuest AI

VulnQuest AI is a local-first, Windows desktop security scanner. Python receives AST-based checks; a broader set of source and project files can be scanned with cautious lexical rules. It does not execute scanned projects. Findings are advisory and static analysis cannot prove that software is secure.

## Current implementation status

The native PySide6 desktop app includes a dark, consistent navigation and workspace style, project selection, background folder scanning, findings, local scan history, JSON/CSV/HTML/Markdown exports, and a local Ollama/Gemma 4 connection check. Interactive AI chat, the Git diff screen, and end-to-end approved source-file editing/rollback are not yet wired into the GUI. The GUI does not modify project files.

The original ZIP mentioned in the request was not present in the workspace. This audit and changes use the available checkout at `vulnquest-ai/`.

## Install and run on Windows 10/11

Install Python 3.11 or newer, then in PowerShell:

```powershell
cd path\to\vulnquest-ai
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python app.py
```

Static scanning works without an API key and without Ollama. The app opens a native desktop window, not a browser.

## Gemma 4 local inference

The configured default is `gemma4:e2b-it-q4_K_M`, an Ollama library tag for a quantized Gemma 4 E2B instruction-tuned model. It is an Ollama-distributed packaging/tag, not a Google-issued model identifier. Google identifies the family as Gemma 4 (E2B, E4B, 12B, 26B A4B, and 31B); its model card states Apache 2.0. Review the [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) and [license](https://ai.google.dev/gemma/docs/core/license) before redistribution or commercial use.

Install Ollama separately from [ollama.com](https://ollama.com), then run:

```powershell
ollama pull gemma4:e2b-it-q4_K_M
python app.py
```

The listed quantized E2B artifact is about 4.6 GB on disk. Ollama runtime memory needs exceed weight size and vary with context length, backend, and other applications; this project has not established a minimum RAM/GPU requirement through local hardware testing. In the app choose **Model Manager → Check local Ollama and model**. No automatic cloud fallback occurs. The `OllamaProvider` sends requests to the configured local Ollama endpoint; a reachable service/model is not the same as tested model quality. Real inference has not been tested in this environment.

## Using the scanner

Choose a project folder and select **Scan project source**. Discovery includes Python, JavaScript/TypeScript, Java, C/C++, C#, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala, shell, SQL, HTML, YAML, JSON, TOML, Terraform, and common project config files. Python uses AST analysis. Other languages currently get generic line-based checks for credential literals, dynamic execution, shell execution, disabled TLS, weak hashes, and unsafe deserialization; these checks do not understand language syntax or data flow and can produce false positives. This is broad file support, not full language-specific SAST coverage. The scanner skips common environment/build/cache directories, symlinks, unsupported files, and oversized files. It never executes scanned source. Review findings in Findings Explorer and export a redacted report from Reports. History is stored in a local SQLite database under `vulnquest_data/` by default. Set `VULNQUEST_DATA_DIR` to change it.

The existing scanner rules cover patterns such as SQL construction, unsafe subprocess usage, hard-coded credentials, unsafe YAML/pickle, dynamic execution, weak hashes, disabled TLS verification, insecure random, temporary files, debug/network binding, XML parsing, and assert-based security checks. Rules can produce false positives and miss vulnerabilities, especially when behavior depends on data flow or runtime configuration.

## Privacy

Folder scans and report generation are local. The desktop UI currently exposes local Ollama only; it does not offer hosted provider configuration. The legacy provider modules remain in the Python package for compatibility, but the desktop interface does not select or call them. Never place API keys in source files. Reports redact evidence snippets by default.

## Build a Windows executable

```powershell
python -m pip install -e ".[dev]"
.\scripts\build_windows.ps1
```

The script produces `dist\VulnQuestAI\` (one-folder PyInstaller output). In this audit, the build completed but the packaged executable failed its headless startup check with a QtCore DLL import error, so this output is not currently a usable release. No standalone installer has been generated. Model weights are not bundled; install Ollama and download the model separately.

## Tests

```powershell
python -m pytest -v
```

The audit used the bundled Python 3.12.14 runtime because the repository `.venv` points to a missing interpreter. `python -m pytest -q` completed with **72 passed**. The native window initialized in an offscreen smoke check with 13 pages. The synthetic scanner benchmark and isolated working-copy demo ran; the demo uses deterministic mock remediation, not Gemma inference. Ollama is reachable, but the configured Gemma 4 tag is not downloaded; the app reports that directly and will not substitute the installed Llama model. Gemma 4 inference and interactive GUI behavior remain unverified; patch editing is not implemented in the desktop UI. See [the audit](docs/AUDIT.md) for detailed evidence and gaps.

## License

VulnQuest AI source code is MIT licensed. Gemma model weights are separate artifacts governed by Google's Gemma 4 license and any distribution/runtime terms. Third-party dependencies retain their own licenses.
