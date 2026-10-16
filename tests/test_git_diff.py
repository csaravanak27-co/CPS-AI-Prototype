import subprocess
import shutil
import pytest
from pathlib import Path
from vulnquest.git_diff import (
    is_git_available,
    is_git_repo,
    parse_diff_changed_lines,
    get_git_diff,
    scan_git_diff
)

DIFF_SAMPLE = """diff --git a/vuln.py b/vuln.py
index 1234567..89abcdef 100644
--- a/vuln.py
+++ b/vuln.py
@@ -1,4 +1,5 @@
 def hello():
+    eval(input())
     return "world"
"""

def test_parse_diff_changed_lines():
    res = parse_diff_changed_lines(DIFF_SAMPLE)
    assert "vuln.py" in res
    assert 2 in res["vuln.py"]
    assert 1 not in res["vuln.py"]
    assert 3 not in res["vuln.py"]

def test_non_git_dir_returns_error(tmp_path):
    res = scan_git_diff(tmp_path)
    assert "error" in res
    assert "Not a Git repository" in res["error"]

def test_git_diff_scanning_with_temp_repo(tmp_path):
    git_bin = shutil.which("git")
    if not git_bin:
        pytest.skip("Git binary not installed")

    # Set up a test git repository
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Configure local git user to avoid commit errors
    subprocess.run([git_bin, "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run([git_bin, "-C", str(repo), "config", "user.name", "TestUser"], check=True)
    subprocess.run([git_bin, "-C", str(repo), "config", "user.email", "test@example.com"], check=True)

    # Initial commit with a pre-existing finding and clean code
    clean_file = repo / "app.py"
    clean_file.write_text(
        '# Pre-existing code\n'
        'password = "OldHardcodedPassword123"\n'
        'def run():\n'
        '    print("hello")\n',
        encoding="utf-8"
    )

    subprocess.run([git_bin, "-C", str(repo), "add", "app.py"], check=True)
    subprocess.run([git_bin, "-C", str(repo), "commit", "-m", "Initial commit"], check=True)

    # Now introduce a new vulnerability on line 5
    clean_file.write_text(
        '# Pre-existing code\n'
        'password = "OldHardcodedPassword123"\n'
        'def run():\n'
        '    print("hello")\n'
        '    eval(input())\n',
        encoding="utf-8"
    )

    # Run scan_git_diff
    res = scan_git_diff(repo, staged=False)
    assert not res.get("error")
    assert res["summary"]["total"] >= 2

    # Verify that eval(input()) is identified as newly introduced in diff
    new_in_diff_rids = {f["rule_id"] for f in res["new_in_diff"]}
    assert "VQ005" in new_in_diff_rids

    # Verify that password = "OldHardcodedPassword123" is classified as pre-existing
    preexisting_rids = {f["rule_id"] for f in res["preexisting"]}
    assert "VQ003" in preexisting_rids
