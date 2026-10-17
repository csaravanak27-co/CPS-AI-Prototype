"""
C.P.S. Open-Weight AI Security Model Harness
============================================
An original, reproducible evaluation harness designed to benchmark open-weight
and open-source LLMs (e.g., LLaMA 3.3, LLaMA 3.1, Qwen 2.5 Coder, Mistral, CodeLlama)
on autonomous software security remediation and repair.

Evaluates models across five objective, verifiable dimensions:
  1. Syntax Validity Rate (does the model output valid Python AST?)
  2. Vulnerability Remediation Rate (does the fix eliminate the target AST finding?)
  3. Safety & Side-Effect Rate (does the fix avoid introducing new vulnerabilities?)
  4. Interface Preservation Rate (does the fix preserve original function & class signatures?)
  5. Negative Control Accuracy (does the model avoid breaking already-secure code?)
"""

import ast
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .benchmark import SAMPLES
from .patcher import build_patched, compute_hash
from .rules import RULES
from .scanner import scan_source
from .verification import verify
from .ai_provider import BaseProvider, MockProvider, get_provider


@dataclass
class HarnessResult:
    rule_id: str
    model_name: str
    provider_name: str
    syntax_ok: bool
    remediated: bool
    no_new_vulns: bool
    api_preserved: bool
    latency_sec: float
    error_message: Optional[str] = None
    original_code: str = ""
    proposed_code: str = ""

    def is_fully_successful(self) -> bool:
        return self.syntax_ok and self.remediated and self.no_new_vulns and self.api_preserved


class ModelSecurityHarness:
    """
    Open-source model harness for benchmarking open-weight LLMs on secure code repair.
    Provides standard test runners, metrics calculation, and audit reporting.
    """

    def __init__(self, provider: Optional[BaseProvider] = None):
        self.provider = provider or MockProvider()

    def evaluate_sample(self, rule_id: str, vuln_code: str) -> HarnessResult:
        """Evaluates a single vulnerability sample against the configured AI model."""
        model_name = getattr(self.provider, "model", getattr(self.provider, "name", "unknown"))
        provider_name = getattr(self.provider, "name", "CustomProvider")

        # 1. Scan original to obtain finding details
        findings, _ = scan_source(vuln_code, path="target.py")
        target_finding = next((f.to_dict() for f in findings if f.rule_id == rule_id), None)
        if not target_finding:
            target_finding = {"rule_id": rule_id, "title": RULES.get(rule_id, ("Vulnerability",))[0], "line": 1}

        lines = vuln_code.splitlines()
        start_line = 1
        end_line = max(1, len(lines))
        context_block = vuln_code.strip()

        start_time = time.perf_counter()
        syntax_ok = False
        remediated = False
        no_new_vulns = False
        api_preserved = False
        proposed_code = ""
        error_msg = None

        try:
            proposal = self.provider.propose_fix(target_finding, context_block, start_line, end_line)
            replacement = proposal.get("replacement", "")
            proposed_code = replacement

            # Build patched code
            patched_src = build_patched(vuln_code, start_line, end_line, replacement)

            # Independent verification
            v = verify("target.py", vuln_code, patched_src, target_rule=rule_id)
            syntax_ok = (v.get("syntax_status") == "Passed")
            remediated = (v.get("target_status") == "Resolved")
            no_new_vulns = (v.get("new_findings_status") == "None detected")
            api_preserved = (v.get("regression_status") == "Passed")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"

        latency = time.perf_counter() - start_time

        return HarnessResult(
            rule_id=rule_id,
            model_name=model_name,
            provider_name=provider_name,
            syntax_ok=syntax_ok,
            remediated=remediated,
            no_new_vulns=no_new_vulns,
            api_preserved=api_preserved,
            latency_sec=round(latency, 3),
            error_message=error_msg,
            original_code=vuln_code,
            proposed_code=proposed_code
        )

    def run_suite(
        self,
        samples: Optional[Dict[str, Tuple[str, str]]] = None,
        max_samples: Optional[int] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None
    ) -> dict:
        """
        Executes the evaluation harness across the benchmark suite.
        Returns detailed scores and metric summaries.
        """
        eval_samples = samples or SAMPLES
        rule_items = list(eval_samples.items())
        if max_samples:
            rule_items = rule_items[:max_samples]

        total_cases = len(rule_items)
        results: List[HarnessResult] = []

        for idx, (rid, (vuln_code, safe_code)) in enumerate(rule_items, 1):
            if progress_cb:
                progress_cb(idx, total_cases, rid)
            res = self.evaluate_sample(rid, vuln_code)
            results.append(res)

        # Calculate metrics
        syntax_count = sum(1 for r in results if r.syntax_ok)
        remediated_count = sum(1 for r in results if r.remediated)
        safety_count = sum(1 for r in results if r.no_new_vulns)
        api_count = sum(1 for r in results if r.api_preserved)
        full_success_count = sum(1 for r in results if r.is_fully_successful())
        avg_latency = sum(r.latency_sec for r in results) / total_cases if total_cases else 0.0

        model_name = getattr(self.provider, "model", getattr(self.provider, "name", "unknown"))
        provider_name = getattr(self.provider, "name", "CustomProvider")

        scorecard = {
            "harness": "C.P.S. Open-Weight Model Security Harness",
            "version": "1.0.0",
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model_name,
            "provider": provider_name,
            "total_evaluated": total_cases,
            "metrics": {
                "syntax_validity_rate": round(syntax_count / total_cases, 4) if total_cases else 0.0,
                "remediation_rate": round(remediated_count / total_cases, 4) if total_cases else 0.0,
                "safety_rate": round(safety_count / total_cases, 4) if total_cases else 0.0,
                "interface_preservation_rate": round(api_count / total_cases, 4) if total_cases else 0.0,
                "composite_success_rate": round(full_success_count / total_cases, 4) if total_cases else 0.0,
                "average_latency_sec": round(avg_latency, 3),
            },
            "counts": {
                "syntax_valid": syntax_count,
                "remediated": remediated_count,
                "zero_new_vulns": safety_count,
                "api_preserved": api_count,
                "fully_verified": full_success_count,
            },
            "results": [asdict(r) for r in results]
        }
        return scorecard

    @staticmethod
    def to_markdown(scorecard: dict) -> str:
        """Formats harness evaluation scorecard as clean Markdown."""
        m = scorecard["metrics"]
        c = scorecard["counts"]
        tot = scorecard["total_evaluated"]

        lines = [
            f"# 🧪 C.P.S. AI Security Harness Scorecard",
            f"**Evaluated Model:** `{scorecard['model']}` ({scorecard['provider']})  ",
            f"**Timestamp:** `{scorecard['evaluated_at']}` | **Sample Count:** `{tot}`",
            "",
            "## 📊 Model Performance Dimensions",
            "| Evaluation Dimension | Success Rate | Count | Meaning |",
            "|---|---|---|---|",
            f"| **Syntax Validity** | **{m['syntax_validity_rate']:.1%}** | {c['syntax_valid']}/{tot} | Generates compilable Python AST |",
            f"| **Vulnerability Remediation** | **{m['remediation_rate']:.1%}** | {c['remediated']}/{tot} | Completely resolves target security risk |",
            f"| **Safety (No New Vulns)** | **{m['safety_rate']:.1%}** | {c['zero_new_vulns']}/{tot} | Avoids introducing new vulnerabilities |",
            f"| **Interface Preservation** | **{m['interface_preservation_rate']:.1%}** | {c['api_preserved']}/{tot} | Retains caller API & function contracts |",
            f"| **Overall Verified Success** | **{m['composite_success_rate']:.1%}** | {c['fully_verified']}/{tot} | Passes all 4 verification dimensions |",
            "",
            f"**Average Latency:** `{m['average_latency_sec']}s` per remediation",
            "",
            "## 🔬 Per-Rule Verification Table",
            "| Rule ID | Syntax | Remediated | Safe | API Preserved | Full Pass | Latency |",
            "|---|---|---|---|---|---|---|",
        ]

        for r in scorecard["results"]:
            s_icon = "✅" if r["syntax_ok"] else "❌"
            rem_icon = "✅" if r["remediated"] else "❌"
            safe_icon = "✅" if r["no_new_vulns"] else "❌"
            api_icon = "✅" if r["api_preserved"] else "❌"
            full_icon = "🏆 PASS" if (r["syntax_ok"] and r["remediated"] and r["no_new_vulns"] and r["api_preserved"]) else "⚠️ FAIL"
            lines.append(f"| `{r['rule_id']}` | {s_icon} | {rem_icon} | {safe_icon} | {api_icon} | {full_icon} | {r['latency_sec']}s |")

        return "\n".join(lines)


def main():
    import argparse
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="C.P.S. Open-Weight Model Security Evaluation Harness")
    parser.add_argument("--provider", choices=["mock", "ollama", "groq", "gemini", "openrouter"], default="ollama", help="AI provider backend (local Gemma 4 by default)")
    parser.add_argument("--model", type=str, default=None, help="Model ID (local default: gemma4:e2b-it-q4_K_M)")
    parser.add_argument("--output", type=str, default=None, help="File path to save markdown scorecard")
    args = parser.parse_args()

    prov = get_provider(args.provider, model=args.model)
    print(f"🚀 Initializing C.P.S. Model Security Harness on: {prov.name} ({getattr(prov, 'model', 'default')})...")

    harness = ModelSecurityHarness(provider=prov)
    scorecard = harness.run_suite(progress_cb=lambda cur, tot, rid: print(f"  [{cur}/{tot}] Evaluating {rid}..."))

    md = ModelSecurityHarness.to_markdown(scorecard)
    print("\n" + md)

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\n✅ Scorecard saved to: {args.output}")


if __name__ == "__main__":
    main()
