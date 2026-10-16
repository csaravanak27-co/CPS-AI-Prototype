"""
VulnQuest AI - Complete End-to-End Demonstration Script
Demonstrates:
  1. Offline static vulnerability scanning (VQ001-VQ016)
  2. AI Security Analyst remediation and safe patch preview
  3. Working copy patching with hash verification and pristine backup
  4. Independent verification (syntax, target resolved, no regressions)
  5. Rollback verification to pristine original
  6. Audit report generation (JSON, CSV, HTML, Markdown)
  7. Git diff scanning for pre-commit security verification
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import tempfile
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from vulnquest import patcher, reports, verification
from vulnquest.scanner import scan_files
from vulnquest.ai_provider import MockProvider
from vulnquest.git_diff import is_git_available, scan_git_diff

def main():
    print("=" * 70)
    print("🛡️  VULNQUEST AI — AUTONOMOUS SECURITY ANALYST DEMO")
    print("=" * 70)

    # 1. Scan files
    examples_dir = Path(__file__).parent
    vuln_code = (examples_dir / "vulnerable_demo.py").read_bytes()
    safer_code = (examples_dir / "safer_demo.py").read_bytes()

    print("\n[Step 1] Scanning sample files statically (never executed)...")
    res = scan_files({"vulnerable_demo.py": vuln_code, "safer_demo.py": safer_code})
    print(f"  Files scanned: {res['scanned']}")
    print(f"  Total findings: {len(res['findings'])}")

    sqli = next(f for f in res["findings"] if f.rule_id == "VQ001")
    print(f"  Target finding: [{sqli.rule_id}] {sqli.title} on line {sqli.line}")
    print(f"  Evidence snippet: {sqli.snippet}")

    # 2. AI Security Analyst remediation
    print("\n[Step 2] Requesting AI Security Analyst remediation (Offline Mock Mode)...")
    provider = MockProvider()
    lines = vuln_code.decode().splitlines()
    proposal = provider.propose_fix(sqli.to_dict(), lines[sqli.line - 1], sqli.line, sqli.line)
    print(f"  Explanation: {proposal['explanation']}")
    print(f"  Attack Scenario: {proposal['attack_scenario']}")
    print(f"  Safe Replacement:\n{proposal['replacement']}")

    # 3. Patch creation & preview
    print("\n[Step 3] Building unified diff...")
    original_text = vuln_code.decode()
    patched_text = patcher.build_patched(original_text, sqli.line, sqli.line, proposal["replacement"])
    diff = patcher.unified_diff(original_text, patched_text, "vulnerable_demo.py")
    print("--- Unified Diff Preview ---")
    print(diff)

    # 4. Working copy patch application & backup
    print("[Step 4] Applying patch to isolated working copy with approval...")
    with tempfile.TemporaryDirectory(prefix="vq_demo_") as td:
        patcher.create_workcopy({"vulnerable_demo.py": vuln_code}, Path(td))
        meta = patcher.apply_patch(td, "vulnerable_demo.py", patched_text, approved=True)
        print(f"  Applied safely to working copy: {td}")
        print(f"  Before SHA-256: {meta['before_sha256'][:16]}...")
        print(f"  After SHA-256:  {meta['sha256'][:16]}...")

        # 5. Independent verification
        print("\n[Step 5] Running independent Verification Center checks...")
        ver = verification.verify("vulnerable_demo.py", original_text, patched_text, target_rule="VQ001", target_line=sqli.line)
        print(f"  Overall Status:   {ver['overall_result']}")
        print(f"  Syntax Check:     {ver['syntax_status']}")
        print(f"  Target Finding:   {ver['target_status']}")
        print(f"  New Findings:     {ver['new_findings_status']}")
        print(f"  Regression Check: {ver['regression_status']}")
        for c in ver["checks"]:
            print(f"    - [{c['status'].upper()}] {c['name']}: {c['detail']}")

        # 6. Rollback verification
        print("\n[Step 6] Testing reliable rollback to pristine backup...")
        patcher.rollback(td, "vulnerable_demo.py")
        restored = (Path(td) / "vulnerable_demo.py").read_bytes()
        assert restored == vuln_code, "Rollback failed to restore exact pristine byte content"
        print("  Rollback confirmed: Pristine original restored perfectly.")

    # 7. Audit Report Generation
    print("\n[Step 7] Generating full security audit reports...")
    report = reports.build_report([f.to_dict() for f in res["findings"]], verifications=[ver], provider_info="Mock Offline Engine")
    json_bytes = len(reports.to_json(report))
    csv_bytes = len(reports.to_csv(report))
    html_bytes = len(reports.to_html(report))
    md_bytes = len(reports.to_markdown(report))
    print(f"  JSON report:     {json_bytes} bytes")
    print(f"  CSV report:      {csv_bytes} bytes")
    print(f"  HTML report:     {html_bytes} bytes")
    print(f"  Markdown report: {md_bytes} bytes")

    # 8. Git Diff Scanner
    print("\n[Step 8] Checking Git Diff Scanner availability...")
    git_ok, git_msg = is_git_available()
    print(f"  Git status: {'Available' if git_ok else 'Unavailable'} ({git_msg})")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE: the isolated working-copy library workflow ran; this is not a claim that every desktop screen or AI backend is production-ready.")
    print("=" * 70)

if __name__ == "__main__":
    main()
