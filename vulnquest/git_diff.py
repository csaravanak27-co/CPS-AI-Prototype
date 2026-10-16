import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .rules import Finding
from .scanner import scan_source

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

def is_git_available() -> Tuple[bool, str]:
    """Checks if git binary is installed and executable via safe subprocess list."""
    git_bin = shutil.which("git")
    if not git_bin:
        return False, "Git binary not found in system PATH."
    try:
        p = subprocess.run([git_bin, "--version"], capture_output=True, text=True, timeout=5)
        if p.returncode == 0:
            return True, p.stdout.strip()
        return False, f"Git returned non-zero exit code: {p.stderr.strip()}"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Could not execute git: {e}"

def is_git_repo(folder_path: Path | str) -> Tuple[bool, str]:
    """Verifies that folder_path is a valid Git repository root or worktree."""
    p_path = Path(folder_path).resolve()
    if not p_path.is_dir():
        return False, f"Directory does not exist: {folder_path}"

    git_bin = shutil.which("git") or "git"
    try:
        p = subprocess.run(
            [git_bin, "-C", str(p_path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if p.returncode == 0 and "true" in p.stdout.strip():
            return True, "Valid Git repository"
        return False, "Not a Git repository (run 'git init' first)"
    except Exception as e:
        return False, f"Git repository check failed: {e}"

def has_commits(folder_path: Path | str) -> bool:
    """Checks whether the repository has at least one commit on HEAD."""
    git_bin = shutil.which("git") or "git"
    try:
        p = subprocess.run(
            [git_bin, "-C", str(folder_path), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return p.returncode == 0
    except Exception:
        return False

def get_git_diff(folder_path: Path | str, staged: bool = False, compare_ref: str = None) -> Tuple[str, str]:
    """
    Safely retrieves git diff string using subprocess argument list.
    Handles unborn branches (no commits) gracefully.
    """
    git_bin = shutil.which("git") or "git"
    p_path = str(Path(folder_path).resolve())

    cmd = [git_bin, "-C", p_path, "diff"]
    if compare_ref:
        cmd.append(compare_ref)
    elif staged:
        cmd.append("--cached")
    else:
        # If repo has commits, compare working tree against HEAD; otherwise plain git diff
        if has_commits(p_path):
            cmd.append("HEAD")

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if p.returncode != 0:
            # Fallback to plain git diff if HEAD ref comparison fails
            p2 = subprocess.run([git_bin, "-C", p_path, "diff"], capture_output=True, text=True, timeout=10)
            if p2.returncode == 0:
                return p2.stdout, ""
            return "", p.stderr.strip() or "Failed to compute git diff"
        return p.stdout, ""
    except Exception as e:
        return "", f"Git diff execution failed: {type(e).__name__}: {e}"

def parse_diff_changed_lines(diff_text: str) -> Dict[str, Set[int]]:
    """
    Parses unified diff to extract mapped line numbers that were added or modified per file.
    Returns: { 'relative/path.py': {line_num1, line_num2, ...} }
    """
    changed_lines: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    current_line = 0

    lines = diff_text.splitlines()
    for line in lines:
        if line.startswith("diff --git "):
            current_file = None
        elif line.startswith("+++ b/"):
            target_path = line[6:].strip()
            if target_path != "/dev/null":
                current_file = target_path
                if current_file not in changed_lines:
                    changed_lines[current_file] = set()
            else:
                current_file = None
        elif line.startswith("+++ /dev/null"):
            current_file = None
        elif line.startswith("@@ ") and current_file:
            m = HUNK_HEADER.match(line)
            if m:
                new_start = int(m.group(3))
                current_line = new_start
        elif current_file is not None and not line.startswith("--- "):
            if line.startswith("+"):
                changed_lines[current_file].add(current_line)
                current_line += 1
            elif line.startswith("-"):
                # Deleted line does not increment new file's line number
                pass
            else:
                # Context line
                current_line += 1

    return changed_lines

def scan_git_diff(
    repo_path: Path | str,
    staged: bool = False,
    compare_ref: str = None,
    use_bandit: bool = False
) -> dict:
    """
    Scans a Git repository's changed Python files and highlights findings on modified lines.
    Never modifies, commits, or alters git history.
    """
    avail, avail_msg = is_git_available()
    if not avail:
        return {"error": avail_msg, "all_findings": [], "new_in_diff": [], "preexisting": []}

    is_repo, repo_msg = is_git_repo(repo_path)
    if not is_repo:
        return {"error": repo_msg, "all_findings": [], "new_in_diff": [], "preexisting": []}

    diff_text, err = get_git_diff(repo_path, staged=staged, compare_ref=compare_ref)
    if err and not diff_text:
        return {"error": f"Could not read git diff: {err}", "all_findings": [], "new_in_diff": [], "preexisting": []}

    changed_lines_map = parse_diff_changed_lines(diff_text)
    root = Path(repo_path).resolve()

    all_findings: List[dict] = []
    new_in_diff_findings: List[dict] = []
    preexisting_findings: List[dict] = []

    files_scanned = 0
    for rel_path, changed_lines in sorted(changed_lines_map.items()):
        if not rel_path.lower().endswith(".py"):
            continue

        file_full_path = (root / rel_path).resolve()
        if not file_full_path.exists() or not file_full_path.is_file():
            continue

        try:
            content = file_full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        findings, scan_err = scan_source(content, path=rel_path)
        files_scanned += 1

        for f in findings:
            f_dict = f.to_dict()
            line_no = f_dict.get("line", 1)
            # Check if this finding falls on an added/modified line
            if line_no in changed_lines:
                f_dict["diff_status"] = "Newly introduced in diff"
                f_dict["is_new_in_diff"] = True
                new_in_diff_findings.append(f_dict)
            else:
                f_dict["diff_status"] = "Pre-existing in file"
                f_dict["is_new_in_diff"] = False
                preexisting_findings.append(f_dict)
            all_findings.append(f_dict)

    return {
        "repo": str(root),
        "files_changed_count": len(changed_lines_map),
        "files_scanned": files_scanned,
        "changed_files": list(changed_lines_map.keys()),
        "raw_diff": diff_text,
        "all_findings": all_findings,
        "new_in_diff": new_in_diff_findings,
        "preexisting": preexisting_findings,
        "summary": {
            "total": len(all_findings),
            "new_in_diff": len(new_in_diff_findings),
            "preexisting": len(preexisting_findings)
        }
    }
