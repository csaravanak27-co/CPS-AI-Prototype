# C.P.S. — Security Architecture & Responsible Disclosure

## 1. Security Architecture Principles

C.P.S. (Code Processing System) enforces strict security and isolation boundaries across all components:

### A. Non-Execution of Scanned Code
The C.P.S. Static Security Scanner parses Python code into an Abstract Syntax Tree (`ast.parse`) and applies deterministic pattern rules. Target source code is **never imported, executed, or dynamically evaluated** during scanning.

### B. Sandboxed Code Execution
When the user explicitly invokes the Execution Sandbox (in the desktop app or via `/api/execute`):
- Execution occurs in an isolated temporary directory.
- Execution is bounded by a hard subprocess timeout (default 10 seconds).
- Standard output and standard error are captured into separate memory buffers.
- The working directory and compiled artifacts are purged immediately after execution.

### C. Human-in-the-Loop Patching
- No source file is ever modified automatically.
- The Patch Lab requires explicit confirmation (`approved=True`) before writing changes.
- Prior to modifying any file, the pristine original is preserved in `.cps_backup/` and registered with a SHA-256 hash in `manifest.json`.
- A one-click rollback mechanism can restore original files at any time.

### D. Automated Secret & Credential Redaction
All evidence snippets, context previews, and exported reports (JSON, CSV, HTML, Markdown) are automatically sanitized using high-entropy regex filters and secret signature detectors (`cps.security.redact`). Passwords, API tokens, JWTs, AWS credentials, and private keys are replaced with `***REDACTED***`.

---

## 2. Reporting Security Vulnerabilities

If you discover a security issue or vulnerability within C.P.S., please disclose it responsibly:
- Email: `security@cps-ai.local` (or open a confidential security advisory on GitHub).
- Please provide reproduction steps and relevant version details.
- We aim to acknowledge receipt within 48 hours and provide a patch timeline promptly.
