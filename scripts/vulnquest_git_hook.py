#!/usr/bin/env python3
"""
VulnQuest AI Pre-commit Hook
Scans staged Python changes for newly introduced vulnerabilities before committing.
Exits with 1 if new High-severity vulnerabilities are detected.
"""
import sys
from pathlib import Path

# Ensure vulnquest package is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from vulnquest.git_diff import scan_git_diff

def main():
    print("🛡️ VulnQuest AI — Staged Git Diff Security Scan...")
    res = scan_git_diff(".", staged=True)

    if res.get("error"):
        print(f"⚠️ Git diff scanner warning: {res['error']}")
        # Do not block commit if git diff cannot be read
        sys.exit(0)

    new_findings = res.get("new_in_diff", [])
    if not new_findings:
        print("✅ No new vulnerabilities introduced in staged changes.")
        sys.exit(0)

    high_sev = [f for f in new_findings if f.get("severity") in ("High", "Critical")]
    print(f"\n🚨 VulnQuest AI detected {len(new_findings)} newly introduced finding(s) in staged changes:")
    for f in new_findings:
        badge = "🔴" if f.get("severity") in ("High", "Critical") else "🟡"
        print(f"  {badge} [{f.get('rule_id')}] {f.get('title')}")
        print(f"     Location: {f.get('file')}:{f.get('line')}")
        print(f"     Remediation: {f.get('fix')}")
        print()

    if high_sev:
        print("❌ Commit blocked: Resolve high-severity findings before committing, or bypass with git commit --no-verify.")
        sys.exit(1)
    else:
        print("⚠️ Warning: Non-blocking medium/low findings detected in staged diff.")
        sys.exit(0)

if __name__ == "__main__":
    main()
