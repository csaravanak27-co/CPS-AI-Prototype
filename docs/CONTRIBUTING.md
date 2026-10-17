# Contributing to C.P.S.

Thank you for contributing to **C.P.S. — Universal AI Coding Companion**!

---

## 1. Development Workflow

### A. Environment Setup
```powershell
# Clone the repository
git clone https://github.com/your-username/cps-ai.git
cd cps-ai

# Activate Python 3.11+ virtual environment
.\.venv\Scripts\Activate.ps1

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### B. Running Tests
Run the comprehensive test suite:
```powershell
python -m pytest -v
```
All 87 tests must pass before submitting a Pull Request.

### C. Running Core Verification Benchmarks
```powershell
python -m cps.benchmark
```

### D. Testing the Browser Extension
1. Open Chrome/Edge and go to `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and choose `extension/`.
4. Ensure the background server is active:
   ```powershell
   python -m backend.server
   ```

---

## 2. Adding a New Programming Language Profile

1. Open `cps/code_engine.py`.
2. Add a new entry to `LANGUAGE_PROFILES`:
   ```python
   "newlang": {
       "name": "New Language",
       "extension": ".ext",
       "comment": "//",
       "block_comment": ("/*", "*/"),
       "entry": "main()",
       "typing": True,
       "compiled": False,
       "paradigm": "...",
       "standard_version": "...",
   }
   ```
3. If sandboxed execution is supported, configure its runner in `cps/executor.py` under `RUNTIME_CONFIG`.
4. Add unit test assertions in `tests/test_cps_suite.py`.

---

## 3. Adding a New Security Rule

1. Define the rule in `cps/rules.py` in `RULES` (ID format: `VQ###`).
2. Add the AST visitor pattern or regex in `run_rules()`.
3. Add paired vulnerable and safe code samples to `cps/benchmark.py`.
4. Run `python -m cps.benchmark` to verify precision.
