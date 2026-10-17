"""
C.P.S. Shared Backend API Server
================================
Provides a REST API for the C.P.S. Browser Extension and Desktop Application.
Supports:
  - Code generation, explanation, debugging, optimization, conversion, tests
  - Static security scanning and rule analysis
  - Provider management (Mock, Local Ollama, Groq, Gemini, OpenRouter)
  - Safe sandboxed code execution
  - Scan history and persistent settings

Built with dual architecture:
  - Full FastAPI application when FastAPI is installed.
  - Built-in zero-dependency HTTP server fallback so it runs out-of-the-box.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# Ensure project root is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import C.P.S. core modules
from cps import __version__, __product__
from cps import config
from cps import storage
from cps.ai_provider import get_provider, BaseProvider, MockProvider, OllamaProvider, GroqProvider, GeminiProvider, OpenRouterProvider
from cps.code_engine import CodeEngine, CodeRequest, get_supported_languages
from cps.executor import CodeExecutor
from cps.scanner import scan_source, scan_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cps.backend")

# Active settings cache
SETTINGS_FILE = config.DATA_DIR / "backend_settings.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "provider": config.DEFAULT_PROVIDER,
        "model": config.MODEL,
        "ollama_host": config.DEFAULT_OLLAMA_HOST,
        "theme": "dark",
        "selection_detection": True,
    }


def save_settings(data: dict):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = load_settings()
    current.update(data)
    SETTINGS_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def get_current_provider(
    prov_name: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    host: Optional[str] = None,
) -> BaseProvider:
    s = load_settings()
    name = prov_name or s.get("provider", "mock")
    m = model or s.get("model", None)
    key = api_key or s.get("apiKey") or s.get("api_key") or None
    h = host or s.get("ollama_host") or None
    try:
        return get_provider(name, model=m, api_key=key, host=h)
    except Exception:
        return MockProvider()


def _handle_api_request(method: str, path: str, body: Optional[dict] = None) -> Tuple[int, dict]:
    """Implementation for all C.P.S. API endpoints."""
    # 0. Root welcome / status page
    if path in ("/", "/favicon.ico"):
        return 200, {
            "status": "online",
            "product": __product__,
            "version": __version__,
            "message": "C.P.S. Shared Backend API Server is active.",
            "endpoints": [
                "GET  /api/health",
                "GET  /api/languages",
                "GET  /api/providers",
                "POST /api/providers/test",
                "POST /api/query",
                "POST /api/generate",
                "POST /api/explain",
                "POST /api/debug",
                "POST /api/scan",
                "POST /api/execute",
                "GET  /api/runtimes",
                "GET  /api/history",
                "GET  /api/chat/history",
                "GET  /api/settings",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # 1. Health check
    if path == "/api/health" or path == "/health":
        return 200, {
            "status": "ok",
            "product": __product__,
            "version": __version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # 2. Languages registry
    if path == "/api/languages":
        return 200, {"languages": get_supported_languages()}

    # 3. Providers listing
    if path == "/api/providers":
        provs = [
            {"id": "mock", "name": "Mock / Offline", "description": "Deterministic offline assistant (no keys or model needed)"},
            {"id": "ollama", "name": "Ollama (Local Gemma 4)", "description": "100% private local inference"},
            {"id": "groq", "name": "Groq (Hosted LLaMA 3.3)", "description": "Ultra-fast hosted inference"},
            {"id": "gemini", "name": "Google Gemini", "description": "Gemini 2.0 Flash API"},
            {"id": "openrouter", "name": "OpenRouter", "description": "Multi-model hosted gateway"},
        ]
        active_p = get_current_provider()
        for p in provs:
            try:
                inst = get_provider(p["id"])
                p["available"] = inst.available()
                ok, msg = inst.configuration_status()
                p["status_message"] = msg
            except Exception as e:
                p["available"] = False
                p["status_message"] = str(e)
            p["active"] = (p["id"] == active_p.name.lower() or p["id"] in active_p.name.lower())
        return 200, {"providers": provs, "active_provider": active_p.name}

    # 4. Test provider connection
    if path == "/api/providers/test":
        data = body or {}
        p_name = data.get("provider", "mock")
        m_name = data.get("model")
        p_key = data.get("apiKey") or data.get("api_key")
        p_host = data.get("host") or data.get("ollama_host")
        try:
            inst = get_provider(p_name, model=m_name, api_key=p_key, host=p_host)
            ok, msg = inst.test_connection()
            return 200, {"provider": p_name, "ok": ok, "message": msg}
        except Exception as e:
            return 200, {"provider": p_name, "ok": False, "message": str(e)}

    # 5. AI Query / Code Action (generate, explain, debug, optimize, convert, tests, complexity, security, summarize)
    if path in ("/api/query", "/api/generate", "/api/explain", "/api/debug"):
        data = body or {}
        action = data.get("action", "generate")
        if path == "/api/generate":
            action = "generate"
        elif path == "/api/explain":
            action = "explain"
        elif path == "/api/debug":
            action = "debug"

        prov_req = data.get("provider")
        model_req = data.get("model")
        key_req = data.get("apiKey") or data.get("api_key")
        host_req = data.get("host") or data.get("ollama_host")
        engine = CodeEngine(provider=get_current_provider(prov_req, model_req, api_key=key_req, host=host_req))

        req = CodeRequest(
            action=action,
            source_code=data.get("code") or data.get("source_code") or data.get("text") or "",
            language=data.get("language") or "python",
            target_language=data.get("target_language") or "",
            problem_statement=data.get("problem") or data.get("problem_statement") or "",
            error_message=data.get("error") or data.get("error_message") or "",
            constraints=data.get("constraints") or "",
            context=data.get("context") or "",
            additional_instructions=data.get("additional") or data.get("instructions") or "",
        )

        try:
            resp = engine.process(req)
            return 200, {
                "success": True,
                "action": action,
                "response": resp.to_dict(),
                "model_used": resp.model_used,
                "provider": engine.provider.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error("AI query processing failed: %s", e)
            return 500, {"success": False, "error": str(e)}

    # 6. Static Security Scan
    if path == "/api/scan":
        data = body or {}
        code = data.get("code", "")
        filename = data.get("filename", "input.py")
        findings, err = scan_source(code, path=filename)
        return 200, {
            "success": True,
            "filename": filename,
            "findings": [f.to_dict() for f in findings],
            "findings_count": len(findings),
            "parse_error": err,
        }

    # 7. Safe Code Execution
    if path == "/api/execute":
        data = body or {}
        code = data.get("code", "")
        lang = data.get("language", "python")
        stdin = data.get("stdin", "")
        timeout = data.get("timeout", 10)

        executor = CodeExecutor(default_timeout=timeout)
        res = executor.execute(code, language=lang, stdin=stdin, timeout=timeout)
        return 200, {
            "success": True,
            "result": res.to_dict(),
        }

    # 8. Check runtime environments
    if path == "/api/runtimes":
        executor = CodeExecutor()
        return 200, {"runtimes": executor.check_all_runtimes()}

    # 9. Scan History
    if path == "/api/history":
        if method == "GET":
            rows = storage.list_scans()
            return 200, {
                "scans": [
                    {"id": r[0] if len(r) > 4 else idx, "timestamp": r[0], "files": r[1], "findings": r[2], "severity": json.loads(r[3]) if isinstance(r[3], str) else r[3]}
                    for idx, r in enumerate(rows, 1)
                ]
            }
        elif method == "DELETE":
            storage.clear_history()
            return 200, {"status": "cleared"}

    # 9b. Chat History
    if path == "/api/chat/history":
        if method == "GET":
            return 200, {"history": storage.list_chat_history()}
        elif method == "POST":
            data = body or {}
            msg_id = storage.save_chat_message(
                role=data.get("role", "user"),
                content=data.get("content", ""),
                action=data.get("action", "chat"),
                model=data.get("model", ""),
                provider=data.get("provider", "")
            )
            return 200, {"status": "saved", "id": msg_id}
        elif method == "DELETE":
            storage.clear_chat_history()
            return 200, {"status": "cleared"}

    # 10. Settings
    if path == "/api/settings":
        if method == "GET":
            return 200, {"settings": load_settings()}
        elif method == "POST":
            saved = save_settings(body or {})
            return 200, {"settings": saved, "status": "saved"}

    return 404, {"error": f"Endpoint not found: {path}"}


def handle_api_request(method: str, path: str, body: Optional[dict] = None) -> Tuple[int, dict]:
    """Unified API boundary that returns JSON errors instead of crashing callers."""
    try:
        return _handle_api_request(method, path, body)
    except Exception as exc:
        logger.exception("API request failed for %s %s", method, path)
        return 500, {"success": False, "error": "internal server error", "detail": str(exc)}


class CPSHTTPRequestHandler(BaseHTTPRequestHandler):
    """C.P.S. built-in zero-dependency HTTP server with CORS support."""

    # Do not keep worker request threads alive when the listening server stops.
    daemon_threads = True

    def _dispatch(self, method: str, path: str, body: Optional[dict] = None):
        """Dispatch a request without allowing malformed input to kill a thread."""
        try:
            return handle_api_request(method, path, body)
        except Exception as exc:
            logger.exception("Unhandled API request failure for %s %s", method, path)
            return 500, {"error": "internal server error", "detail": str(exc)}

    def _set_cors_headers(self, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        status, resp = self._dispatch("GET", parsed.path)
        self._set_cors_headers(status)
        try:
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Client disconnected before GET response was written")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            content_len = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._set_cors_headers(400)
            self.wfile.write(json.dumps({"error": "invalid Content-Length"}).encode("utf-8"))
            return
        if content_len < 0:
            self._set_cors_headers(400)
            self.wfile.write(json.dumps({"error": "invalid Content-Length"}).encode("utf-8"))
            return
        body_bytes = self.rfile.read(content_len) if content_len else b""
        body_json = {}
        if body_bytes:
            try:
                body_json = json.loads(body_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": "request body must be valid JSON"}).encode("utf-8"))
                return
            if not isinstance(body_json, dict):
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"error": "request body must be a JSON object"}).encode("utf-8"))
                return
        status, resp = self._dispatch("POST", parsed.path, body_json)
        self._set_cors_headers(status)
        try:
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Client disconnected before POST response was written")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        status, resp = self._dispatch("DELETE", parsed.path)
        self._set_cors_headers(status)
        try:
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Client disconnected before DELETE response was written")

    def log_message(self, format, *args):
        # Clean logging
        logger.info("%s - %s", self.address_string(), format % args)


def run_standalone_server(host: str = "127.0.0.1", port: int = 8899):
    """Runs the built-in HTTP server."""
    server_address = (host, port)
    try:
        httpd = ThreadingHTTPServer(server_address, CPSHTTPRequestHandler)
    except OSError as err:
        print(f"[C.P.S.] Error binding to http://{host}:{port}: {err}")
        return False

    print(f"============================================================")
    print(f"  C.P.S. Backend Server running on http://{host}:{port}")
    print(f"  Compatible with C.P.S. Browser Extension & Desktop App")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping C.P.S. Backend Server...")
    finally:
        httpd.server_close()
    return True


# Optional FastAPI application if installed
try:
    from fastapi import FastAPI, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    app = FastAPI(title="C.P.S. API", version=__version__, description="C.P.S. AI Coding Companion Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    async def catch_all(request: Request, path_name: str):
        if request.method == "OPTIONS":
            return Response(status_code=204)
        body = None
        if request.method in ("POST", "PUT"):
            try:
                body = await request.json()
            except Exception:
                body = {}
        status, resp = handle_api_request(request.method, "/" + path_name, body)
        return JSONResponse(status_code=status, content=resp)

except ImportError:
    app = None


if __name__ == "__main__":
    port = int(os.getenv("CPS_PORT", "8899"))
    host = os.getenv("CPS_HOST", "127.0.0.1")
    run_standalone_server(host=host, port=port)
