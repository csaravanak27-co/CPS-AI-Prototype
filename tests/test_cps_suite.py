"""
Comprehensive test suite for C.P.S. Core, Code Engine, Context Manager,
Executor, and Backend API.
"""
import json
import pytest
from pathlib import Path

import cps
from cps import config
from cps.ai_provider import MockProvider, get_provider
from cps.code_engine import (
    CodeEngine, CodeRequest, CodeResponse, LANGUAGE_PROFILES,
    get_supported_languages, parse_code_response
)
from cps.context_manager import ContextItem, ContextManager
from cps.executor import CodeExecutor
from cps.patcher import build_patched, unified_diff
from cps.rules import RULES
from cps.scanner import scan_source
from cps.verification import verify
from backend.server import handle_api_request


def test_cps_metadata():
    assert cps.__version__ == "1.0.0"
    assert cps.__product__ == "C.P.S."


def test_language_profiles():
    langs = get_supported_languages()
    assert len(langs) >= 27
    py = next(l for l in langs if l["id"] == "python")
    assert py["name"] == "Python"
    assert py["extension"] == ".py"


def test_code_engine_generate():
    engine = CodeEngine()
    req = CodeRequest(action="generate", problem_statement="Two Sum problem", language="python")
    res = engine.process(req)
    assert isinstance(res, CodeResponse)
    assert len(res.code) > 0
    assert "def solve" in res.code or "python" in res.language.lower()


def test_code_engine_explain_and_debug():
    engine = CodeEngine()
    exp = engine.explain("def add(a, b): return a + b", language="python")
    assert exp.explanation or exp.code

    dbg = engine.debug("def broken(): return 1/0", error="ZeroDivisionError", language="python")
    assert dbg.code or dbg.explanation


def test_code_engine_actions():
    engine = CodeEngine()
    opt = engine.optimize("for i in range(len(a)): pass", language="python")
    assert opt is not None

    conv = engine.convert("print('hello')", "python", "javascript")
    assert conv is not None

    tests = engine.generate_tests("def add(a, b): return a + b", "python")
    assert tests is not None

    comp = engine.analyze_complexity("def bubble(a): ...", "python")
    assert comp is not None


def test_context_manager():
    mgr = ContextManager()
    mgr.add_item("problem", "Solve Knapsack", language="text")
    mgr.add_item("selection", "SECRET_KEY = 'supersecretkey12345'", language="python")

    assert len(mgr.items) == 2
    mgr.redact_sensitive()
    preview = mgr.preview()
    assert "REDACTED" in preview

    prompt = mgr.build_prompt("generate", instructions="Use dynamic programming")
    assert "Solve Knapsack" in prompt
    assert "### Additional Guidance:" in prompt

    assert mgr.estimate_tokens() > 0
    mgr.clear()
    assert len(mgr.items) == 0


def test_code_executor_python():
    executor = CodeExecutor(default_timeout=5)
    res = executor.execute("print('CPS-TEST-PASS')", language="python")
    assert res.exit_code == 0
    assert "CPS-TEST-PASS" in res.stdout.strip()
    assert not res.timed_out
    assert res.duration_ms >= 0


def test_code_executor_runtimes():
    executor = CodeExecutor()
    runtimes = executor.check_all_runtimes()
    assert "python" in runtimes
    assert runtimes["python"]["available"] is True


def test_backend_api_health():
    status, body = handle_api_request("GET", "/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["product"] == "C.P.S."


def test_backend_api_languages():
    status, body = handle_api_request("GET", "/api/languages")
    assert status == 200
    assert "languages" in body
    assert len(body["languages"]) >= 27


def test_backend_api_providers():
    status, body = handle_api_request("GET", "/api/providers")
    assert status == 200
    assert "providers" in body
    assert any(p["id"] == "mock" for p in body["providers"])


def test_backend_api_query():
    status, body = handle_api_request("POST", "/api/query", {
        "action": "generate",
        "problem": "Fibonacci sequence",
        "language": "python",
        "provider": "mock"
    })
    assert status == 200
    assert body["success"] is True
    assert "response" in body


def test_backend_api_scan():
    code = 'import os\nos.system("ls " + x)\n'
    status, body = handle_api_request("POST", "/api/scan", {"code": code, "filename": "test.py"})
    assert status == 200
    assert body["success"] is True
    assert body["findings_count"] > 0
    assert any(f["rule_id"] == "VQ002" for f in body["findings"])


def test_backend_api_execute():
    status, body = handle_api_request("POST", "/api/execute", {
        "code": "print(100 * 2)",
        "language": "python"
    })
    assert status == 200
    assert body["success"] is True
    assert body["result"]["stdout"].strip() == "200"


def test_backend_api_settings():
    status, body = handle_api_request("GET", "/api/settings")
    assert status == 200
    assert "settings" in body

    status2, body2 = handle_api_request("POST", "/api/settings", {"theme": "light"})
    assert status2 == 200
    assert body2["settings"]["theme"] == "light"


def test_mock_provider_chat():
    prov = MockProvider()
    resp = prov.chat("Please generate binary search in python")
    assert "def solve" in resp or "binary" in resp.lower() or "optimal" in resp.lower()

    json_resp = prov.chat("Remediate SQL injection", json_mode=True)
    parsed = json.loads(json_resp)
    assert "replacement" in parsed
    assert "explanation" in parsed


def test_real_provider_chat_failure_raises_aierror():
    from cps.ai_provider import GroqProvider, AIError
    # Groq with empty key should fail and raise AIError, NOT silently mock
    p = GroqProvider(api_key="")
    engine = CodeEngine(provider=p)
    req = CodeRequest(action="generate", problem_statement="Two Sum", language="python")
    with pytest.raises(AIError, match="inference failed"):
        engine.process(req)


def test_patcher_atomic_write(tmp_path):
    from cps.patcher import apply_patch
    target_file = tmp_path / "sample.py"
    target_file.write_text("x = 1\n", encoding="utf-8")

    res = apply_patch(tmp_path, "sample.py", "x = 2\n", approved=True)
    assert res["file"] == "sample.py"
    assert target_file.read_text(encoding="utf-8") == "x = 2\n"

    # Pristine backup exists
    backup_file = tmp_path / ".cps_backup" / "sample.py"
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == "x = 1\n"


def test_verification_multilang():
    # 1. Python verification
    py_orig = "import os\nos.system('echo hi')\n"
    py_patch = "import subprocess\nsubprocess.run(['echo', 'hi'])\n"
    res_py = verify("test.py", py_orig, py_patch)
    assert res_py["syntax_status"] == "Passed"

    # 2. JSON verification
    json_orig = '{"key": "old"}'
    json_patch = '{"key": "new"}'
    res_json = verify("config.json", json_orig, json_patch)
    assert res_json["syntax_status"] == "Passed"

    # 3. JavaScript / generic delimiter balance verification
    js_orig = "function run() { return 1; }"
    js_patch = "function run() { return 2; }"
    res_js = verify("index.js", js_orig, js_patch)
    assert res_js["syntax_status"] == "Passed"

    # 4. Broken delimiter in JS
    js_broken = "function run() { return 2;"
    res_broken = verify("index.js", js_orig, js_broken)
    assert res_broken["syntax_status"] == "Failed"


def test_context_manager_pruning():
    mgr = ContextManager(max_tokens=50)  # ~200 characters limit
    # Add large items
    for i in range(5):
        mgr.add_item("file", f"Line {i} content repeated " * 10, language="text")
    assert mgr.estimate_tokens() > 50
    mgr.prune_to_budget(target_tokens=50)
    assert mgr.estimate_tokens() <= 50


def test_storage_chat_and_settings(tmp_path, monkeypatch):
    from cps import storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    # Chat storage
    msg_id = storage.save_chat_message("user", "Hello C.P.S.!", action="chat")
    assert msg_id > 0
    history = storage.list_chat_history()
    assert len(history) == 1
    assert history[0]["content"] == "Hello C.P.S.!"

    storage.clear_chat_history()
    assert len(storage.list_chat_history()) == 0

    # Settings storage
    storage.save_setting("theme", "cyberpunk")
    assert storage.get_setting("theme") == "cyberpunk"
    all_s = storage.get_all_settings()
    assert all_s.get("theme") == "cyberpunk"


def test_storage_corruption_recovery(tmp_path, monkeypatch):
    from cps import storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    db_path = tmp_path / "history.db"
    # Write garbage into database file to simulate corruption
    db_path.write_bytes(b"CORRUPTED_NON_SQLITE_GARBAGE_BYTES_1234567890")

    # Accessing storage should recover, backup the corrupt file, and recreate valid DB
    msg_id = storage.save_chat_message("user", "Recovered message", action="chat")
    assert msg_id > 0
    history = storage.list_chat_history()
    assert len(history) == 1
    assert history[0]["content"] == "Recovered message"

    # Corrupt backup exists
    corrupt_files = list(tmp_path.glob("history.db.corrupt.*"))
    assert len(corrupt_files) == 1


def test_backend_chat_history_api(tmp_path, monkeypatch):
    from cps import storage
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    # POST new chat message
    status, body = handle_api_request("POST", "/api/chat/history", {
        "role": "user",
        "content": "API test message"
    })
    assert status == 200
    assert body["status"] == "saved"

    # GET chat history
    status2, body2 = handle_api_request("GET", "/api/chat/history")
    assert status2 == 200
    assert len(body2["history"]) == 1
    assert body2["history"][0]["content"] == "API test message"

    # DELETE chat history
    status3, body3 = handle_api_request("DELETE", "/api/chat/history")
    assert status3 == 200
    assert body3["status"] == "cleared"

