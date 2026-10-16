"""Optional Bandit integration. Files are copied to a temp dir and analysed statically; nothing is executed."""
import json, subprocess, sys, tempfile
from pathlib import Path
from .patcher import _inside
from .rules import Finding
from .security import redact

def run_bandit(files, timeout=60):
    """Returns (findings, note). Degrades gracefully if Bandit is missing or fails."""
    py = {p: d for p, d in files.items() if p.lower().endswith(".py")}
    if not py:
        return [], None
    with tempfile.TemporaryDirectory(prefix="vq_bandit_") as td:
        root = Path(td)
        for rel, data in py.items():
            try:
                t = _inside(root, rel)
            except ValueError:
                continue
            t.parent.mkdir(parents=True, exist_ok=True); t.write_bytes(data)
        try:
            p = subprocess.run([sys.executable, "-m", "bandit", "-r", str(root), "-f", "json", "-q"],
                               capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return [], f"Bandit unavailable: {type(e).__name__}"
        if "No module named bandit" in (p.stderr or ""):
            return [], "Bandit not installed (pip install bandit)"
        try:
            data = json.loads(p.stdout)
        except (json.JSONDecodeError, TypeError):
            return [], "Bandit produced unreadable output"
        out = []
        for r in data.get("results", []):
            try:
                rel = Path(r["filename"]).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            out.append(Finding(r["test_id"], r["issue_text"][:90], r["issue_severity"].title(), r["issue_confidence"].title(),
                               rel, r["line_number"], redact(r.get("code", "").strip().splitlines()[0][:200] if r.get("code") else ""),
                               r["issue_text"], "See Bandit docs: " + r.get("more_info", ""), "bandit", source="bandit"))
        return out, f"Bandit: {len(out)} finding(s)"
