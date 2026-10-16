import json
import pytest
from types import SimpleNamespace
from vulnquest.ai_provider import (
    AIError,
    parse_response,
    MockProvider,
    GroqProvider,
    GeminiProvider,
    OpenRouterProvider,
    OllamaProvider,
    get_provider
)

def test_parse_response_valid():
    raw = '{"explanation": "SQLi risk", "replacement": "c.execute(q, (u,))", "assumptions": "sqlite", "tests": ["t1"]}'
    res = parse_response(raw)
    assert res["explanation"] == "SQLi risk"
    assert res["replacement"] == "c.execute(q, (u,))"
    assert res["tests"] == ["t1"]

def test_parse_response_markdown_fenced():
    raw = '```json\n{"explanation": "Command injection", "replacement": "subprocess.run([\\"ls\\", x])"}\n```'
    res = parse_response(raw)
    assert res["explanation"] == "Command injection"
    assert "subprocess.run" in res["replacement"]

def test_parse_response_invalid_json():
    with pytest.raises(AIError, match="Malformed JSON"):
        parse_response("not valid json at all")

def test_parse_response_empty():
    with pytest.raises(AIError, match="Empty model response"):
        parse_response("")

def test_mock_provider_deterministic():
    p = MockProvider()
    assert p.available() is True
    ok, msg = p.test_connection()
    assert ok is True

    finding = {"rule_id": "VQ001", "title": "SQL Injection", "line": 5}
    fix = p.propose_fix(finding, "query = 'SELECT * FROM ' + uid", 5, 5)
    assert "SQL" in fix["explanation"]
    assert "execute" in fix["replacement"]
    assert len(fix["tests"]) >= 1

def test_groq_provider_missing_key():
    p = GroqProvider(api_key="")
    assert p.available() is False
    with pytest.raises(AIError, match="GROQ_API_KEY is not set"):
        p.propose_fix({"rule_id": "VQ001"}, "code", 1, 1)

def test_groq_provider_connection_mocked():
    fake_body = {"choices": [{"message": {"content": json.dumps({"explanation": "test", "replacement": "x=1"})}}]}
    fake_post = lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: fake_body, text="")
    p = GroqProvider(api_key="gsk_test1234567890", post=fake_post)
    ok, msg = p.test_connection()
    assert ok is True

def test_gemini_provider_mocked():
    fake_body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps({"explanation": "Gemini explanation", "replacement": "safe_call()"})}
                    ]
                }
            }
        ]
    }
    fake_post = lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: fake_body, text="")
    p = GeminiProvider(api_key="AIzaSyTestKey123", post=fake_post)
    assert p.available() is True
    ok, msg = p.test_connection()
    assert ok is True
    fix = p.propose_fix({"rule_id": "VQ002"}, "context", 1, 1)
    assert fix["replacement"] == "safe_call()"

def test_gemini_provider_error():
    fake_post = lambda *a, **k: SimpleNamespace(status_code=403, text="Invalid API key")
    p = GeminiProvider(api_key="AIzaSyBadKey", post=fake_post)
    ok, msg = p.test_connection()
    assert ok is False
    assert "authentication" in msg.lower() or "403" in msg

def test_openrouter_provider_mocked():
    fake_body = {"choices": [{"message": {"content": json.dumps({"explanation": "OpenRouter test", "replacement": "remediated()"})}}]}
    fake_post = lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: fake_body, text="")
    p = OpenRouterProvider(api_key="sk-or-test123456", post=fake_post)
    assert p.available() is True
    ok, msg = p.test_connection()
    assert ok is True
    fix = p.propose_fix({"rule_id": "VQ003"}, "context", 1, 1)
    assert fix["replacement"] == "remediated()"

def test_ollama_provider_server_down():
    def boom(*a, **k):
        raise ConnectionError("connection refused")
    p = OllamaProvider(get=boom, post=boom)
    ok, msg = p.test_connection()
    assert ok is False
    assert "unreachable" in msg.lower()

def test_ollama_provider_model_missing():
    fake_tags = {"models": [{"name": "mistral:latest"}, {"name": "codellama:latest"}]}
    fake_get = lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: fake_tags)
    p = OllamaProvider(model="llama3.1", get=fake_get)
    ok, msg = p.test_connection()
    assert ok is False
    assert "model 'llama3.1' is not pulled" in msg

def test_ollama_provider_model_ready():
    fake_tags = {"models": [{"name": "llama3.1:latest"}, {"name": "llama3.1"}]}
    fake_get = lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: fake_tags)
    p = OllamaProvider(model="llama3.1", get=fake_get)
    ok, msg = p.test_connection()
    assert ok is True
    assert "ready" in msg

def test_get_provider_factory():
    assert isinstance(get_provider("mock"), MockProvider)
    assert isinstance(get_provider("Gemini"), GeminiProvider)
    assert isinstance(get_provider("OpenRouter"), OpenRouterProvider)
    assert isinstance(get_provider("Ollama"), OllamaProvider)
    assert isinstance(get_provider("Groq"), GroqProvider)

def test_get_provider_factory_rejects_unknown_provider():
    with pytest.raises(AIError, match="Select a provider explicitly"):
        get_provider("typo")
