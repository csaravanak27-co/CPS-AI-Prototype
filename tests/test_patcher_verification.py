import pytest
from pathlib import Path
from vulnquest import patcher, verification

SRC = """import sqlite3
def get_user(conn, uid):
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=" + uid)
    return c.fetchone()
"""

FIXED = """    c.execute("SELECT * FROM users WHERE id=?", (uid,))"""

WORSE_SYNTAX = """    c.execute(SELECT * FROM users"""

NEW_VULN = """    import os
    os.system("echo " + uid)
    c.execute("SELECT * FROM users WHERE id=?", (uid,))"""

def test_stale_patch_preview_rejected():
    orig_hash = patcher.compute_hash(SRC)
    # If source changes before applying patch:
    changed_src = SRC + "# modified comment\n"

    with pytest.raises(ValueError, match="hash mismatch"):
        patcher.build_patched(changed_src, 4, 4, FIXED, expected_sha256=orig_hash)

def test_patch_application_and_backup_preservation(tmp_path):
    workdir = tmp_path / "work"
    workdir.mkdir()
    patcher.create_workcopy({"app.py": SRC.encode("utf-8")}, workdir)

    orig_hash = patcher.compute_hash(SRC)
    patched_code = patcher.build_patched(SRC, 4, 4, FIXED, expected_sha256=orig_hash)

    # 1. Approval required
    with pytest.raises(PermissionError, match="explicit human approval required"):
        patcher.apply_patch(workdir, "app.py", patched_code, approved=False)

    # 2. Apply patch with approval
    res = patcher.apply_patch(workdir, "app.py", patched_code, approved=True, original_sha256=orig_hash)
    assert res["file"] == "app.py"
    assert (workdir / "app.py").read_text(encoding="utf-8") == patched_code

    # 3. Apply a second patch (e.g. user modifies again) — verify pristine backup is NOT overwritten
    second_patch = patched_code + "# second modification\n"
    res2 = patcher.apply_patch(workdir, "app.py", second_patch, approved=True)

    # 4. Rollback must restore original pristine SRC
    patcher.rollback(workdir, "app.py")
    restored = (workdir / "app.py").read_text(encoding="utf-8")
    assert restored == SRC

def test_verification_syntax_failure():
    bad_code = patcher.build_patched(SRC, 4, 4, WORSE_SYNTAX)
    v = verification.verify("app.py", SRC, bad_code, target_rule="VQ001")
    assert v["syntax_status"] == "Failed"
    assert v["overall_result"] == "Failed"
    assert "Syntax error" in v["checks"][0]["detail"]

def test_verification_resolved_and_clean():
    clean_code = patcher.build_patched(SRC, 4, 4, FIXED)
    v = verification.verify("app.py", SRC, clean_code, target_rule="VQ001", target_line=4)
    assert v["syntax_status"] == "Passed"
    assert v["target_status"] == "Resolved"
    assert v["new_findings_status"] == "None detected"
    assert v["regression_status"] == "Passed"
    assert v["overall_result"] == "Verified by available checks"
    assert v["resolved"] == 1
    assert v["new"] == 0

def test_verification_new_finding_detected():
    bad_fix = patcher.build_patched(SRC, 4, 4, NEW_VULN)
    v = verification.verify("app.py", SRC, bad_fix, target_rule="VQ001")
    assert v["syntax_status"] == "Passed"
    assert v["new_findings_status"] == "Detected"
    assert v["new"] >= 1
    assert v["overall_result"] == "Failed"
    new_rids = {f["rule_id"] for f in v["new_findings_list"]}
    assert "VQ002" in new_rids

def test_verification_regression_public_api_removed():
    # Remove get_user function entirely
    gutted_code = "import sqlite3\nx = 1\n"
    v = verification.verify("app.py", SRC, gutted_code, target_rule="VQ001")
    assert v["regression_status"] == "Failed"
    assert v["overall_result"] == "Failed"
