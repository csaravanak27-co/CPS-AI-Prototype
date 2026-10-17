"""
Deterministic rule benchmark: evaluates scanner against vulnerable samples and safe negative samples.
All metrics are dynamically calculated from actual scanner runs.
"""
from pathlib import Path
from .scanner import scan_source

# Dataset: (vulnerable_snippet, safe_negative_sample)
SAMPLES = {
    "VQ001": (
        'c.execute("SELECT * FROM u WHERE id=" + uid)\n',
        'c.execute("SELECT * FROM u WHERE id=?", (uid,))\n'
    ),
    "VQ002": (
        'import os\nos.system("ls " + x)\n',
        'import subprocess\nsubprocess.run(["ls", x], check=True)\n'
    ),
    "VQ003": (
        'password = "SuperSecretPassword123"\n',
        'import os\npassword = os.environ.get("APP_PASSWORD")\n'
    ),
    "VQ004": (
        'import yaml\nyaml.load(s)\n',
        'import yaml\nyaml.safe_load(s)\n'
    ),
    "VQ005": (
        'eval(s)\n',
        'import ast\nast.literal_eval(s)\n'
    ),
    "VQ006": (
        'import pickle\npickle.loads(d)\n',
        'import json\njson.loads(d)\n'
    ),
    "VQ007": (
        'open("/data/" + name)\n',
        'import os\nbase = "/data"\np = os.path.basename(name)\nopen(os.path.join(base, p))\n'
    ),
    "VQ008": (
        'import tempfile\ntempfile.mktemp()\n',
        'import tempfile\ntempfile.NamedTemporaryFile()\n'
    ),
    "VQ009": (
        'import hashlib\nhashlib.md5(b"x")\n',
        'import hashlib\nhashlib.sha256(b"x")\n'
    ),
    "VQ010": (
        'import requests\nrequests.get(u, verify=False)\n',
        'import requests\nrequests.get(u, verify=True)\n'
    ),
    "VQ011": (
        'import random\napi_key = random.randint(0, 99999)\n',
        'import secrets\napi_key = secrets.token_hex(16)\n'
    ),
    "VQ012": (
        'import subprocess\nsubprocess.run(f"ls {c}")\n',
        'import subprocess\nsubprocess.run(["ls", c], check=True)\n'
    ),
    "VQ013": (
        'app.run(debug=True)\n',
        'import os\napp.run(debug=os.getenv("FLASK_DEBUG") == "1")\n'
    ),
    "VQ014": (
        'app.run(host="0.0.0.0", port=5000)\n',
        'app.run(host="127.0.0.1", port=5000)\n'
    ),
    "VQ015": (
        'import xml.etree.ElementTree as ET\nET.parse(user_xml)\n',
        'import defusedxml.ElementTree as ET\nET.parse(user_xml)\n'
    ),
    "VQ016": (
        'assert user.is_admin, "Unauthorized access"\n',
        'if not user.is_admin:\n    raise PermissionError("Unauthorized access")\n'
    ),
}

# Edge cases for testing potential false positives and negatives
EDGE_CASES = [
    # Safe comment mentioning execute with concatenation should not trigger
    ("VQ001", '# cursor.execute("SELECT * FROM " + table)\n', False, "Commented SQL pattern"),
    # Non-sensitive random dice roll should not trigger VQ011
    ("VQ011", 'import random\ndice = random.randint(1, 6)\n', False, "Non-credential randomness"),
    # String literal query with no dynamic interpolation
    ("VQ001", 'cursor.execute("SELECT id, name FROM users WHERE active = 1")\n', False, "Static SQL query"),
]


def run():
    """Runs the benchmark suite and calculates true/false positives and negatives."""
    tp = fp = fn = tn = 0
    rows = []

    for rid, (vuln, safe) in SAMPLES.items():
        v_detected = rid in {f.rule_id for f in scan_source(vuln)[0]}
        s_detected = rid in {f.rule_id for f in scan_source(safe)[0]}

        tp += int(v_detected)
        fn += int(not v_detected)
        fp += int(s_detected)
        tn += int(not s_detected)

        rows.append((rid, v_detected, s_detected, "Standard Rule Sample"))

    # Run edge cases
    edge_rows = []
    for rid, code, expect_detect, description in EDGE_CASES:
        detected = rid in {f.rule_id for f in scan_source(code)[0]}
        if expect_detect:
            if detected:
                tp += 1
            else:
                fn += 1
        else:
            if detected:
                fp += 1
            else:
                tn += 1
        edge_rows.append((rid, detected, expect_detect, description))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "total_samples": len(SAMPLES) * 2 + len(EDGE_CASES),
        "rows": rows,
        "edge_rows": edge_rows
    }


def to_markdown(r: dict) -> str:
    """Formats benchmark results as clean GitHub-flavored markdown."""
    t = "\n".join(
        f"| `{rid}` | {'✅ Detected (TP)' if vd else '❌ Missed (FN)'} | {'❌ False Alarm (FP)' if sd else '✅ Clean (TN)'} |"
        for rid, vd, sd, _ in r["rows"]
    )
    edge_t = "\n".join(
        f"| `{rid}` | {desc} | {'Detected' if det else 'Clean'} | {'✅ Passed' if det == exp else '❌ Failed'} |"
        for rid, det, exp, desc in r["edge_rows"]
    )

    return f"""# 📊 C.P.S. — Static Scanner Benchmark Report

**Evaluation Type:** Deterministic Rule Verification & Precision Benchmark  
**Total Test Samples:** {r['total_samples']} ({len(r['rows'])} rule pairs + {len(r['edge_rows'])} edge cases)  
**Methodology:** Evaluates AST rules and regex patterns against paired vulnerable code snippets, clean equivalents, and non-trivial false-positive edge cases.

---

## 📈 Benchmark Summary Metrics

| Metric | Score | Formula / Meaning |
|---|---|---|
| **True Positives (TP)** | `{r['tp']}` | Vulnerabilities correctly detected |
| **True Negatives (TN)** | `{r['tn']}` | Safe code correctly ignored |
| **False Positives (FP)** | `{r['fp']}` | Safe code erroneously flagged |
| **False Negatives (FN)** | `{r['fn']}` | Vulnerable code missed |
| **Precision** | **{r['precision']:.2%}** | `TP / (TP + FP)` |
| **Recall (Sensitivity)** | **{r['recall']:.2%}** | `TP / (TP + FN)` |
| **F1 Score** | **{r['f1']:.2%}** | Harmonic mean of Precision & Recall |

---

## 🔬 Rule-by-Rule Detection Table

| Rule ID | Vulnerable Code Detection | Safe Code Rejection |
|---|---|---|
{t}

---

## 🧪 Edge Case & False Positive Validation

| Rule ID | Edge Case Description | Scanner Result | Test Outcome |
|---|---|---|---|
{edge_t}

---

## ⚠️ Benchmark Methodology & Real-World Limitations

1. **Synthetic Nature:** This benchmark is composed of hand-crafted AST unit samples designed to test rule correctness and regression resistance. It measures whether deterministic rules execute as intended, not real-world zero-day discovery.
2. **Deterministic Rules vs. AI:** This benchmark measures the **deterministic static scanner only**. Optional AI provider suggestions are evaluated independently in the Verification Center.
3. **No Dynamic Execution:** All checks are performed via AST parsing and static matching. No code is executed at runtime.
"""
