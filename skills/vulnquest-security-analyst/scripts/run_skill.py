#!/usr/bin/env python3
"""
Agent Skill CLI Runner: vulnquest-security-analyst
Compliant with Agent Skill Open Standard invocation patterns.
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(root))

from vulnquest.scanner import scan_source, scan_files, read_folder
from vulnquest.git_diff import scan_git_diff
from vulnquest.ai_provider import get_provider
from vulnquest import patcher, verification, reports

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="VulnQuest Security Analyst Agent Skill Runner")
    parser.add_argument("--file", type=str, help="Single Python file to scan")
    parser.add_argument("--folder", type=str, help="Folder containing Python files to scan")
    parser.add_argument("--diff", type=str, help="Git repo path to scan uncommitted diffs")
    parser.add_argument("--provider", type=str, default="ollama", help="AI provider (local Gemma 4 by default; hosted providers require explicit selection)")
    parser.add_argument("--model", type=str, default=None, help="AI model name")
    parser.add_argument("--auto-remediate", action="store_true", help="Generate AI remediation proposals for findings")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown", help="Output format")
    args = parser.parse_args()

    findings = []
    meta = {}

    if args.file:
        p = Path(args.file)
        if not p.is_file():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        src = p.read_text(encoding="utf-8", errors="replace")
        f_list, err = scan_source(src, path=p.name)
        findings = [f.to_dict() for f in f_list]
        meta = {"scanned": 1, "errors": [err] if err else []}

    elif args.folder:
        files, skipped = read_folder(args.folder)
        res = scan_files(files)
        findings = [f.to_dict() for f in res["findings"]]
        meta = {"scanned": res["scanned"], "skipped": skipped, "errors": res["errors"]}

    elif args.diff:
        diff_res = scan_git_diff(args.diff)
        if diff_res.get("error"):
            print(f"Error: {diff_res['error']}", file=sys.stderr)
            sys.exit(1)
        findings = diff_res.get("new_in_diff", []) + diff_res.get("preexisting", [])
        meta = {"scanned": diff_res.get("files_scanned", 0), "raw_diff": diff_res.get("raw_diff")}

    else:
        print("Error: Specify --file, --folder, or --diff", file=sys.stderr)
        sys.exit(1)

    verifications = []
    if args.auto_remediate and findings and args.file:
        provider = get_provider(args.provider, model=args.model)
        src = Path(args.file).read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()

        for f in findings:
            start_l = max(1, f["line"] - 3)
            end_l = min(len(lines), f["line"] + 3)
            context = "\n".join(lines[start_l - 1:end_l])
            proposal = provider.propose_fix(f, context, start_l, end_l)
            patched = patcher.build_patched(src, start_l, end_l, proposal["replacement"])
            v = verification.verify(args.file, src, patched, target_rule=f["rule_id"])
            verifications.append(v)

    report = reports.build_report(findings, meta=meta, verifications=verifications, provider_info=f"{args.provider} ({args.model or 'default'})")

    if args.format == "json":
        print(reports.to_json(report))
    else:
        print(reports.to_markdown(report))

if __name__ == "__main__":
    main()
