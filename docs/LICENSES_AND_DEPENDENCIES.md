# C.P.S. — Dependency and Model License Inventory

## 1. Application License

C.P.S. application source code (including core libraries, desktop application, browser extension, and test harnesses) is licensed under the **MIT License**.

---

## 2. Third-Party Dependencies Inventory

| Package / Library | Version | License | Usage in C.P.S. | Compatibility Note |
|---|---|---|---|---|
| **PySide6** | 6.7.x | LGPLv3 | Native Windows Desktop GUI | Dynamic linking compliant; no GPL contamination |
| **Requests** | 2.31+ | Apache 2.0 | HTTP client for AI providers & health checks | Fully permissive commercial reuse |
| **Python-dotenv** | 1.0+ | BSD 3-Clause | Environment configuration loading | Permissive |
| **Bandit** | 1.7+ | Apache 2.0 | Optional Python static analysis plugin | Permissive |
| **FastAPI** (Optional) | 0.100+ | MIT | Shared REST API Server | Permissive |
| **Uvicorn** (Optional) | 0.20+ | BSD 3-Clause | ASGI web server | Permissive |
| **Pytest** (Dev) | 8.0+ | MIT | Automated test execution | Development only |
| **PyInstaller** (Dev) | 6.0+ | GPLv2 with special exception | Windows standalone binary packaging | Standalone executable distribution exception applies |

---

## 3. AI Model Licensing & Governance

C.P.S. connects to AI models through standardized API abstractions. The software license of C.P.S. is distinct from the licenses governing underlying AI weights and hosted API terms:

### A. Google Gemma 4
- **License:** Apache 2.0 with [Gemma Terms of Use](https://ai.google.dev/gemma/docs/core/license).
- **Redistribution:** Model weights are not bundled with C.P.S. Users download them via Ollama or HuggingFace.
- **Commercial Use:** Permitted under the Gemma Terms of Use subject to prohibited use policies.

### B. Meta LLaMA 3.3 (via Groq / OpenRouter)
- **License:** Llama 3.3 Community License Agreement.
- **Access:** Hosted via Groq API or OpenRouter; C.P.S. does not distribute weights.

### C. Google Gemini
- **License:** Hosted cloud service subject to Google Cloud / Google AI Studio API Terms.

---

## 4. Open-Source Compatibility Matrix

All chosen dependencies are compatible with MIT licensing for C.P.S. distribution:
- No copyleft viral licenses (e.g. standard GPL) are linked in the core engine.
- PySide6 uses Qt for Python under LGPLv3; proprietary and commercial applications can be distributed using unmodified dynamic PySide6 wheel bindings.
