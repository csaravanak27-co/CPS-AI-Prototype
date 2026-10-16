---
name: vulnquest-security-analyst
description: Autonomous SAST and AI secure code remediation skill compliant with the Agent Skill Open Standard. Statically scans Python source code, repositories, and Git diffs for vulnerabilities (rules VQ001-VQ016), generates verifiable minimal patches with open-weight models, verifies syntax and regressions without executing untrusted code, and outputs structured audit reports.
version: 1.0.0
author: VulnQuest AI Team
license: MIT
tags:
  - security
  - sast
  - code-repair
  - open-weight-ai
  - python
  - vulnerability-scanner
inputs:
  source_code:
    type: string
    description: Python source code text to analyze statically
    required: false
  folder_path:
    type: string
    description: Path to local folder containing Python files to scan
    required: false
  git_repo:
    type: string
    description: Path to local Git repository to scan uncommitted diffs
    required: false
  provider:
    type: string
    description: AI provider backend for remediation (mock, ollama, groq, gemini, openrouter)
    default: "ollama"
  model:
    type: string
    description: "Open-weight or hosted model identifier (local default: gemma4:e2b-it-q4_K_M)"
    default: null
outputs:
  status:
    type: string
    description: Overall execution status (success, error)
  findings_count:
    type: integer
    description: Total number of security findings detected
  findings:
    type: array
    description: List of detected security findings with rule ID, severity, confidence, line number, and evidence
  patches:
    type: array
    description: Proposed minimal patches with side-by-side diffs and fix rationale
  verification:
    type: object
    description: Independent verification report with syntax status, target status, and regression checks
---

# VulnQuest Security Analyst Agent Skill

## Overview
The **vulnquest-security-analyst** skill equips AI agents (such as Antigravity, AutoGen, CrewAI, Claude Desktop, and LangChain agents) with autonomous static application security testing (SAST), vulnerability explanation, open-weight AI remediation, and verified patch application.

## Key Capabilities
1. **Deterministic Static Analysis (VQ001–VQ016):**
   - Detects SQL injection (`VQ001`), Command injection (`VQ002`), Hardcoded credentials (`VQ003`), Unsafe deserialization (`VQ004`, `VQ006`), Dynamic code execution (`VQ005`), Path traversal (`VQ007`), Insecure temp files (`VQ008`), Weak cryptography (`VQ009`), Disabled TLS verification (`VQ010`), Insecure randomness (`VQ011`), Dynamic subprocess commands (`VQ012`), Insecure debug configurations (`VQ013`), 0.0.0.0 binds (`VQ014`), Insecure XML/XXE (`VQ015`), and Security assertion bypasses (`VQ016`).
2. **Git Diff Pre-Commit Scanning:**
   - Scans uncommitted or staged changes via `git diff` using safe subprocess argument lists without shell interpolation, highlighting newly introduced vulnerabilities on modified lines.
3. **Open-Weight AI Remediation:**
   - Employs open-weight models (LLaMA 3.3/3.1, Qwen 2.5 Coder, Mistral) via local Ollama or hosted endpoints, with fallback to built-in deterministic templates.
4. **Independent Verification Engine:**
   - Validates that proposed patches compile into valid Python AST, actually resolve the target finding, introduce zero new findings, and preserve caller functions and classes without executing untrusted code on the host.

---

## When to Activate This Skill
Activate this skill whenever:
- The user requests a security review, vulnerability scan, or audit of Python code.
- Code is about to be committed or submitted in a pull request.
- The user asks how to remediate an insecure Python pattern (e.g., SQLi, command injection, path traversal).
- The user wants an automated benchmark or verification of an open-weight model on code repair.

---

## Agent Execution Instructions

### Step 1: Scan Target Code
Execute the scanner programmatically using Python:
```python
from vulnquest.scanner import scan_source, read_folder
from vulnquest.git_diff import scan_git_diff

# Scan a code snippet:
findings, error = scan_source(code_string, path="app.py")

# Or scan an entire project directory:
files, skipped = read_folder("./src")

# Or scan Git uncommitted changes:
diff_report = scan_git_diff("./repo", staged=True)
```

### Step 2: Request Remediation from Open-Weight Provider
Initialize the desired provider backend:
```python
from vulnquest.ai_provider import get_provider

# Use Gemma 4 locally via Ollama (requires pulling the separate model package):
provider = get_provider("ollama", model="gemma4:e2b-it-q4_K_M")

# Or use offline deterministic mode (zero network/keys):
provider = get_provider("mock")

# Request safe fix proposal:
proposal = provider.propose_fix(finding_dict, context_lines, start_line, end_line)
```

### Step 3: Generate Unified Diff & Review
```python
from vulnquest import patcher

patched_code = patcher.build_patched(original_code, start_line, end_line, proposal["replacement"])
diff = patcher.unified_diff(original_code, patched_code, "app.py")
```

### Step 4: Independently Verify the Fix
```python
from vulnquest import verification

ver_report = verification.verify(
    path="app.py",
    original=original_code,
    patched=patched_code,
    target_rule=finding["rule_id"],
    target_line=finding["line"]
)
assert ver_report["overall_result"] == "Verified by available checks"
```

### Step 5: Generate Redacted Audit Report
```python
from vulnquest import reports

report = reports.build_report([f.to_dict() for f in findings], verifications=[ver_report])
markdown_output = reports.to_markdown(report)
```

---

## Safety Guarantees & Constraints
- **NEVER execute untrusted source code.** All validation is performed via AST parsing and inert compilation.
- **NEVER output raw API keys or secrets.** Always invoke `redact()` before presenting code snippets to users.
- **Always require explicit user confirmation** before modifying working files.
