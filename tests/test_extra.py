import json, sys, subprocess, pathlib
from types import SimpleNamespace
import pytest
from vulnquest import bandit_runner, benchmark, config, storage, verification
from vulnquest.scanner import read_folder, scan_files
from vulnquest.ai_provider import OllamaProvider, AIError

ROOT = pathlib.Path(__file__).parent.parent

def test_bandit_missing_degrades(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="No module named bandit"))
    f, note = bandit_runner.run_bandit({"a.py": b"x=1\n"})
    assert f == [] and "not installed" in note

def test_bandit_parse(monkeypatch):
    def fake(cmd, **k):
        root = cmd[cmd.index("-r") + 1]
        out = {"results": [{"filename": root + "/a.py", "test_id": "B602", "issue_text": "shell", "issue_severity": "HIGH",
                            "issue_confidence": "HIGH", "line_number": 2, "code": "x", "more_info": "u"}]}
        return SimpleNamespace(returncode=1, stdout=json.dumps(out), stderr="")
    monkeypatch.setattr(subprocess, "run", fake)
    f, _ = bandit_runner.run_bandit({"a.py": b"x=1\n"})
    assert f[0].rule_id == "B602" and f[0].source == "bandit"

def test_bandit_real():
    pytest.importorskip("bandit")
    r = scan_files({"a.py": b"import subprocess\nsubprocess.call('ls', shell=True)\n"}, use_bandit=True)
    assert any(f.source == "bandit" for f in r["findings"])

def test_read_folder(tmp_path):
    (tmp_path / "a.py").write_text("x=1"); (tmp_path / "b.txt").write_text("x"); (tmp_path / ".git").mkdir(); (tmp_path / ".git" / "c.py").write_text("x")
    f, s = read_folder(tmp_path)
    assert list(f) == ["a.py"]
    assert read_folder(tmp_path / "nope")[0] == {}

def test_regression_check_catches_removed_function():
    v = verification.verify("a.py", "def f(u):\n    eval(u)\n", "x = 1\n", "VQ005")
    assert v["status"] == "Verification failed"

def test_benchmark_all_rules():
    r = benchmark.run()
    assert r["fn"] == 0 and r["fp"] == 0 and r["recall"] == 1.0

def test_storage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    storage.save_scan(2, 3, {"High": 3}); assert len(storage.list_scans()) == 1
    storage.clear_history(); assert storage.list_scans() == []

def test_ollama_mock():
    body = {"message": {"content": json.dumps({"explanation": "e", "replacement": "x=1"})}}
    p = OllamaProvider(post=lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: body))
    assert p.propose_fix({"rule_id": "VQ001", "title": "t", "line": 1}, "c", 1, 1)["replacement"] == "x=1"
    def boom(*a, **k): raise ConnectionError()
    with pytest.raises(AIError): OllamaProvider(post=boom).propose_fix({"rule_id": "x", "title": "t", "line": 1}, "c", 1, 1)

def test_ollama_default_ignores_legacy_model_override(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")
    p = OllamaProvider(get=lambda *a, **k: None, post=lambda *a, **k: None)
    assert p.model == "gemma4:e2b-it-q4_K_M"

