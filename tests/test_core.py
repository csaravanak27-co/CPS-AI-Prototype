import io, json, zipfile, pytest
from vulnquest.scanner import scan_source, scan_files
from vulnquest.security import extract_zip, redact
from vulnquest import patcher, verification, reports
from vulnquest.ai_provider import GroqProvider, AIError, parse_response

CASES = {
 "VQ001": 'c=db.cursor()\nc.execute("SELECT * FROM u WHERE id=" + uid)\n',
 "VQ002": 'import os\nos.system("ls " + x)\n',
 "VQ003": 'password = "SuperSecret123"\n',
 "VQ004": 'import yaml\nyaml.load(s)\n',
 "VQ005": 'eval(input())\n',
 "VQ006": 'import pickle\npickle.loads(d)\n',
 "VQ007": 'open("/var/data/" + name)\n',
 "VQ008": 'import tempfile\ntempfile.mktemp()\n',
 "VQ009": 'import hashlib\nhashlib.md5(b"x")\n',
 "VQ010": 'import requests\nrequests.get("https://x", verify=False)\n',
 "VQ011": 'import random\ntoken = random.randint(0, 999999)\n',
 "VQ012": 'import subprocess\nsubprocess.run(f"ls {cmd}")\n',
 "VQ013": 'app.run(debug=True)\n',
 "VQ014": 'app.run(host="0.0.0.0")\n',
 "VQ015": 'import xml.etree.ElementTree as ET\nET.parse(x)\n',
 "VQ016": 'assert user.is_admin, "denied"\n',
}
CLEAN = ('import subprocess, hashlib, yaml, os\nc.execute("SELECT * FROM u WHERE id=?", (1,))\n'
         'subprocess.run(["ls","-l"])\nhashlib.sha256(b"x")\nyaml.safe_load("a: 1")\npassword = os.environ.get("PW")\n')

@pytest.mark.parametrize("rid,code", CASES.items())
def test_rule_detects(rid, code):
    assert rid in {f.rule_id for f in scan_source(code)[0]}

def test_chained_execute():
    assert "VQ001" in {f.rule_id for f in scan_source('conn.cursor().execute("A" + u)\n')[0]}

def test_clean_code_no_findings():
    assert scan_source(CLEAN)[0] == []

def test_secret_redacted():
    f = scan_source(CASES["VQ003"])[0][0]
    assert "SuperSecret123" not in f.snippet
    assert "SuperSecret123" not in redact('api_key = "SuperSecret123"')

def test_unsupported_and_binary_skipped():
    r = scan_files({"a.txt": b"x", "b.py": b"\x00\x01", "c.py": b"eval(input())\n"})
    assert r["scanned"] == 1 and len(r["skipped"]) == 2 and r["findings"]

def _zip(entries):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in entries.items(): z.writestr(n, d)
    return b.getvalue()

def test_zip_traversal_rejected():
    f, s = extract_zip(_zip({"../evil.py": "x", "/abs.py": "x", "ok/a.py": "x=1"}))
    assert list(f) == ["ok/a.py"] and len(s) == 2

def test_bad_zip():
    assert extract_zip(b"nope")[0] == {}

SRC = 'import sqlite3\ndef f(c, u):\n    c.execute("SELECT * FROM t WHERE id=" + u)\n'
GOOD = '    c.execute("SELECT * FROM t WHERE id=?", (u,))\n'

def test_patch_and_verify():
    new = patcher.build_patched(SRC, 3, 3, GOOD)
    v = verification.verify("a.py", SRC, new, "VQ001")
    assert v["status"] == "Verified by configured checks" and v["resolved"] == 1 and v["new"] == 0

def test_bad_patches_fail_verification():
    assert verification.verify("a.py", SRC, SRC + "def (:\n", "VQ001")["status"] == "Verification failed"
    worse = patcher.build_patched(SRC, 3, 3, "    eval(u)\n")
    assert verification.verify("a.py", SRC, worse, "VQ001")["status"] == "Verification failed"

def test_apply_requires_approval_and_preserves_original(tmp_path):
    patcher.create_workcopy({"a.py": SRC.encode()}, tmp_path)
    with pytest.raises(PermissionError):
        patcher.apply_patch(tmp_path, "a.py", "x=1\n")
    patcher.apply_patch(tmp_path, "a.py", "x=1\n", approved=True)
    assert (tmp_path / "a.py").read_text() == "x=1\n"
    patcher.rollback(tmp_path, "a.py")
    assert (tmp_path / "a.py").read_text() == SRC

@pytest.mark.parametrize("p", ["../x.py", "/etc/passwd", "C:/x.py"])
def test_unsafe_patch_paths(p, tmp_path):
    with pytest.raises(ValueError):
        patcher.apply_patch(tmp_path, p, "x", approved=True)

def test_invalid_range():
    with pytest.raises(ValueError):
        patcher.build_patched(SRC, 9, 10, "x")

class R:
    def __init__(self, s, body=None): self.status_code, self._b, self.text = s, body, ""
    def json(self): return self._b
def ok(txt): return R(200, {"choices": [{"message": {"content": txt}}]})
FIND = {"rule_id": "VQ001", "title": "t", "line": 3}
J = json.dumps({"explanation": "e", "replacement": "x=1", "assumptions": "a", "tests": ["t"]})

def test_ai_success_and_fenced():
    p = GroqProvider("k", post=lambda *a, **k: ok("```json\n" + J + "\n```"))
    assert p.propose_fix(FIND, "c", 1, 2)["replacement"] == "x=1"

def test_ai_failures():
    for s in (401, 404):
        with pytest.raises(AIError):
            GroqProvider("k", post=lambda *a, **k: R(s)).propose_fix(FIND, "c", 1, 2)
    with pytest.raises(AIError):
        GroqProvider("", post=None.__class__ and (lambda *a, **k: ok(J))).propose_fix(FIND, "c", 1, 2)
    for bad in ("", "not json", '{"replacement": 1}'):
        with pytest.raises(AIError):
            parse_response(bad)

def test_ai_retries_rate_limit():
    seq = iter([R(429), ok(J)])
    p = GroqProvider("k", post=lambda *a, **k: next(seq), sleep=lambda s: None)
    assert p.propose_fix(FIND, "c", 1, 2)["explanation"] == "e"

def test_reports_redact():
    fs = [f.to_dict() for f in scan_source(CASES["VQ003"], "a.py")[0]]
    for red in (True, False):
        rep = reports.build_report(fs, redact_snippets=red)
        for out in (reports.to_json(rep), reports.to_csv(rep), reports.to_html(rep)):
            assert "SuperSecret123" not in out
    assert "VQ003" in reports.to_csv(rep)

def test_app_starts():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app import VulnQuestWindow
    application = QApplication.instance() or QApplication([])
    window = VulnQuestWindow()
    assert window.stack.count() == len(window.PAGES)
    window.close()
