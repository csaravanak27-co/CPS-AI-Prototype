import ast
import json
from pathlib import Path
from .rules import RULES
from .scanner import scan_source


def _c(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def get_ast_signatures(src: str) -> dict:
    """Extracts top-level and class-level API names and parameters from AST without executing code."""
    sigs = {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return sigs

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arg_names = [a.arg for a in node.args.args]
            sigs[f"func:{node.name}"] = arg_names
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            sigs[f"class:{node.name}"] = methods
    return sigs


def match_findings(before_findings: list, after_findings: list, target_rule: str = None, target_line: int = None):
    """
    Matches findings between before and after versions by rule_id, file, line proximity, and code snippet.
    Returns (resolved, remaining, new, target_status).
    """
    remaining = []
    unmatched_after = list(after_findings)
    resolved = []

    for b in before_findings:
        match_idx = None
        for i, a in enumerate(unmatched_after):
            if a.rule_id == b.rule_id and a.file == b.file:
                if abs(a.line - b.line) <= 10 or (b.snippet and b.snippet in a.snippet):
                    match_idx = i
                    break
        if match_idx is not None:
            remaining.append(unmatched_after.pop(match_idx))
        else:
            resolved.append(b)

    new_findings = unmatched_after

    if target_rule:
        target_in_before = any(b.rule_id == target_rule and (target_line is None or abs(b.line - target_line) <= 2) for b in before_findings)
        target_in_remaining = any(r.rule_id == target_rule and (target_line is None or abs(r.line - (target_line or 0)) <= 10) for r in remaining)
        target_in_resolved = any(r.rule_id == target_rule for r in resolved)

        if not target_in_before:
            target_status = "Inconclusive"
        elif target_in_remaining:
            target_status = "Still present"
        elif target_in_resolved:
            target_status = "Resolved"
        else:
            target_status = "Inconclusive"
    else:
        target_status = "Not specified"

    return resolved, remaining, new_findings, target_status


def verify(path: str, original: str, patched: str, target_rule: str = None, target_line: int = None, regression_passed: bool = None) -> dict:
    """
    Comprehensive, independent verification of proposed patch.
    Uploaded code is parsed and compiled statically, NEVER executed on host.
    """
    checks = []

    # 1. Multi-language syntax validation
    ext = Path(path).suffix.lower() if path else ".py"
    syntax = True
    syntax_status = "Passed"

    if ext in (".py", ".pyw"):
        try:
            compile(patched, path, "exec")
            checks.append(_c("Syntax validation", "passed", "patched Python source compiles without syntax errors (not executed)"))
        except SyntaxError as e:
            syntax = False
            syntax_status = "Failed"
            checks.append(_c("Syntax validation", "failed", f"Syntax error at line {e.lineno}: {e.msg}"))
    elif ext == ".json":
        try:
            json.loads(patched)
            checks.append(_c("Syntax validation", "passed", "patched JSON document parsed successfully"))
        except Exception as e:
            syntax = False
            syntax_status = "Failed"
            checks.append(_c("Syntax validation", "failed", f"JSON parsing error: {e}"))
    else:
        # Generic bracket and structure balance check for multi-language sources (JS, TS, C, Java, Go, Rust, etc.)
        if "\x00" in patched:
            syntax = False
            syntax_status = "Failed"
            checks.append(_c("Syntax validation", "failed", "Binary null character detected in text source"))
        else:
            pairs = {')': '(', ']': '[', '}': '{'}
            stack = []
            balanced = True
            mismatch_err = ""
            in_str = None
            escape = False
            lines = patched.splitlines()
            for line_idx, line in enumerate(lines, 1):
                for ch in line:
                    if in_str:
                        if escape:
                            escape = False
                        elif ch == '\\':
                            escape = True
                        elif ch == in_str:
                            in_str = None
                    elif ch in ('"', "'", '`'):
                        in_str = ch
                    elif ch in ('(', '[', '{'):
                        stack.append((ch, line_idx))
                    elif ch in (')', ']', '}'):
                        if not stack or stack[-1][0] != pairs[ch]:
                            balanced = False
                            mismatch_err = f"Unmatched '{ch}' at line {line_idx}"
                            break
                        stack.pop()
                if not balanced:
                    break

            if balanced and stack:
                unclosed, u_line = stack[-1]
                balanced = False
                mismatch_err = f"Unclosed '{unclosed}' opened at line {u_line}"

            if balanced:
                checks.append(_c("Syntax validation", "passed", f"Source structure and delimiter balance verified ({ext or 'generic'})"))
            else:
                syntax = False
                syntax_status = "Failed"
                checks.append(_c("Syntax validation", "failed", f"Structural syntax issue: {mismatch_err}"))

    # 2. Rescan & Finding matching
    before_findings, _ = scan_source(original, path)

    if syntax:
        after_findings, _ = scan_source(patched, path)
        resolved_list, remaining_list, new_list, target_status = match_findings(
            before_findings, after_findings, target_rule, target_line
        )

        resolved_count = len(resolved_list)
        remaining_count = len(remaining_list)
        new_count = len(new_list)

        new_status = "None detected" if new_count == 0 else "Detected"
        checks.append(_c("Before/after scan", "passed", f"resolved={resolved_count}, remaining={remaining_count}, new={new_count}"))
        checks.append(_c("New findings", "passed" if new_count == 0 else "failed",
                         "no new findings introduced" if new_count == 0 else f"{new_count} new finding(s) introduced"))

        if target_rule:
            if target_status == "Resolved":
                checks.append(_c("Target finding", "passed", f"{target_rule} confirmed resolved"))
            elif target_status == "Still present":
                checks.append(_c("Target finding", "failed", f"{target_rule} is still present in patched source"))
            else:
                checks.append(_c("Target finding", "inconclusive", f"{target_rule} status inconclusive"))
        else:
            checks.append(_c("Target finding", "skipped", "no specific target rule provided"))

        # 3. Regression test: public API preservation
        if regression_passed is None:
            try:
                orig_sigs = get_ast_signatures(original)
                patch_sigs = get_ast_signatures(patched)
                missing = set(orig_sigs.keys()) - set(patch_sigs.keys())

                if not missing:
                    regression_status = "Passed"
                    checks.append(_c("Regression tests (API preserved)", "passed", "all original functions, methods, and classes preserved"))
                else:
                    regression_status = "Failed"
                    checks.append(_c("Regression tests (API preserved)", "failed", f"missing definitions: {', '.join(sorted(missing))}"))
            except Exception as e:
                regression_status = "Not run"
                checks.append(_c("Regression tests (API preserved)", "unavailable", f"could not inspect API: {e}"))
        else:
            regression_status = "Passed" if regression_passed else "Failed"
            checks.append(_c("Regression tests (supplied)", "passed" if regression_passed else "failed", "externally supplied test result"))
    else:
        resolved_list, remaining_list, new_list = [], list(before_findings), []
        resolved_count = 0
        remaining_count = len(before_findings)
        new_count = 0
        new_status = "Scan failed"
        target_status = "Still present" if target_rule else "Not specified"
        regression_status = "Not run"
        checks.append(_c("Before/after scan", "unavailable", "skipped because patched source failed syntax validation"))
        checks.append(_c("New findings", "unavailable", "patched source failed syntax validation"))
        checks.append(_c("Target finding", "unavailable", "patched source failed syntax validation"))
        checks.append(_c("Regression tests", "unavailable", "patched source failed syntax validation"))

    # 4. Isolated dynamic tests disclosure
    checks.append(_c("Dynamic isolated tests", "not run", "dynamic execution omitted (untrusted code is never executed directly on host)"))

    # 5. Determine overall result
    if not syntax:
        overall_result = "Failed"
        status = "Verification failed"
    elif new_count > 0:
        overall_result = "Failed"
        status = "Verification failed"
    elif target_rule and target_status == "Still present":
        overall_result = "Failed"
        status = "Verification failed"
    elif regression_status == "Failed":
        overall_result = "Failed"
        status = "Verification failed"
    elif (target_status == "Resolved" or (not target_rule and resolved_count > 0)) and regression_status == "Passed":
        overall_result = "Verified by available checks"
        status = "Verified by configured checks"
    elif target_status == "Resolved" or resolved_count > 0:
        overall_result = "Partially verified"
        status = "Partially verified"
    else:
        overall_result = "Inconclusive"
        status = "Not verified"

    return {
        "file": path,
        "status": status,
        "overall_result": overall_result,
        "syntax_status": syntax_status,
        "target_status": target_status,
        "new_findings_status": new_status,
        "regression_status": regression_status,
        "checks": checks,
        "resolved": resolved_count,
        "remaining": remaining_count,
        "new": new_count,
        "resolved_findings": [f.to_dict() if hasattr(f, 'to_dict') else dict(f) for f in resolved_list],
        "remaining_findings": [f.to_dict() if hasattr(f, 'to_dict') else dict(f) for f in remaining_list],
        "new_findings_list": [f.to_dict() if hasattr(f, 'to_dict') else dict(f) for f in new_list],
        "limitations": "Static checks only; a finding disappearing does not prove full remediation; dynamic sandboxed execution omitted."
    }
