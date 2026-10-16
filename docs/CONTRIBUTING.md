# Contributing to VulnQuest AI

Thank you for helping improve VulnQuest AI!

## Development Workflow

1. **Fork & Clone** the repository:
   ```bash
   git clone https://github.com/your-username/vulnquest-ai.git
   cd vulnquest-ai
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Running Tests & Linters**:
   ```bash
   python -m pytest -v
   python -m vulnquest.benchmark
   python examples/demo_workflow.py
   ```
   *All 71 automated tests must pass before submitting a Pull Request.*

---

## Adding a New Security Rule

1. Define the rule metadata in `RULES` inside `vulnquest/rules.py` (Rule ID format: `VQ###`).
2. Add the AST visitor pattern or regex in `run_rules()`.
3. Add a paired vulnerable sample and safe sample to `SAMPLES` in `vulnquest/benchmark.py`.
4. Run `python -m vulnquest.benchmark` to verify 100% precision and recall on the new rule.
5. Add unit test cases in `tests/test_core.py`.
