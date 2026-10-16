"""Repeatable end-to-end demo (no network, no AI): scan -> patch -> separate working copy -> verify -> report.
Run: python examples/regression_tests.py"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vulnquest import patcher, reports, verification
from vulnquest.scanner import scan_files

here = Path(__file__).parent
vuln = (here / "vulnerable_demo.py").read_bytes(); safer = (here / "safer_demo.py").read_bytes()
r = scan_files({"vulnerable_demo.py": vuln, "safer_demo.py": safer})
by = {f.file: sorted(x.rule_id for x in r["findings"] if x.file == f.file) for f in r["findings"]}
print("findings:", by)
assert "safer_demo.py" not in by, "safer demo must be clean"
assert {"VQ001", "VQ002", "VQ003", "VQ004", "VQ009"} <= set(by["vulnerable_demo.py"])
src = vuln.decode(); sqli = next(f for f in r["findings"] if f.rule_id == "VQ001")
new = patcher.build_patched(src, sqli.line, sqli.line, '    return conn.cursor().execute("SELECT * FROM users WHERE id=?", (uid,))\n')
with tempfile.TemporaryDirectory() as td:
    patcher.create_workcopy({"vulnerable_demo.py": vuln}, Path(td))
    patcher.apply_patch(td, "vulnerable_demo.py", new, approved=True)
    assert (here / "vulnerable_demo.py").read_bytes() == vuln, "original must be untouched"
    patcher.rollback(td, "vulnerable_demo.py"); assert (Path(td) / "vulnerable_demo.py").read_bytes() == vuln
v = verification.verify("vulnerable_demo.py", src, new, "VQ001")
print("verification:", v["status"]); [print(" -", c["status"], c["name"], "|", c["detail"]) for c in v["checks"]]
assert v["status"] == "Verified by configured checks"
print("report bytes:", len(reports.to_json(reports.build_report([f.to_dict() for f in r["findings"]], verifications=[v]))))
print("DEMO OK")
