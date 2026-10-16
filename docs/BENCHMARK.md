# 📊 VulnQuest AI — Static Scanner Benchmark Report

**Evaluation Type:** Deterministic Rule Verification & Precision Benchmark  
**Total Test Samples:** 35 (16 rule pairs + 3 edge cases)  
**Methodology:** Evaluates AST rules and regex patterns against paired vulnerable code snippets, clean equivalents, and non-trivial false-positive edge cases.

---

## 📈 Benchmark Summary Metrics

| Metric | Score | Formula / Meaning |
|---|---|---|
| **True Positives (TP)** | `16` | Vulnerabilities correctly detected |
| **True Negatives (TN)** | `19` | Safe code correctly ignored |
| **False Positives (FP)** | `0` | Safe code erroneously flagged |
| **False Negatives (FN)** | `0` | Vulnerable code missed |
| **Precision** | **100.00%** | `TP / (TP + FP)` |
| **Recall (Sensitivity)** | **100.00%** | `TP / (TP + FN)` |
| **F1 Score** | **100.00%** | Harmonic mean of Precision & Recall |

---

## 🔬 Rule-by-Rule Detection Table

| Rule ID | Vulnerable Code Detection | Safe Code Rejection |
|---|---|---|
| `VQ001` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ002` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ003` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ004` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ005` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ006` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ007` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ008` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ009` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ010` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ011` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ012` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ013` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ014` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ015` | ✅ Detected (TP) | ✅ Clean (TN) |
| `VQ016` | ✅ Detected (TP) | ✅ Clean (TN) |

---

## 🧪 Edge Case & False Positive Validation

| Rule ID | Edge Case Description | Scanner Result | Test Outcome |
|---|---|---|---|
| `VQ001` | Commented SQL pattern | Clean | ✅ Passed |
| `VQ011` | Non-credential randomness | Clean | ✅ Passed |
| `VQ001` | Static SQL query | Clean | ✅ Passed |

---

## ⚠️ Benchmark Methodology & Real-World Limitations

1. **Synthetic Nature:** This benchmark is composed of hand-crafted AST unit samples designed to test rule correctness and regression resistance. It measures whether deterministic rules execute as intended, not real-world zero-day discovery.
2. **Deterministic Rules vs. AI:** This benchmark measures the **deterministic static scanner only**. Optional AI provider suggestions are evaluated independently in the Verification Center.
3. **No Dynamic Execution:** All checks are performed via AST parsing and static matching. No code is executed at runtime.
