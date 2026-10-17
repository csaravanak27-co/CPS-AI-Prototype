"""Lifecycle helper for the opt-in, desktop-managed local backend."""
from __future__ import annotations

import threading
import json
from urllib.request import urlopen

from .server import create_http_server, is_loopback_host


class LocalBackend:
    """Start and stop the HTTP backend without taking over the Qt event loop."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8899):
        if not is_loopback_host(host):
            raise ValueError("desktop-managed backend must bind to a loopback host")
        if not 0 <= int(port) <= 65535:
            raise ValueError("backend port must be between 0 and 65535")
        self.host = host
        self.port = int(port)
        self._server = None
        self._thread: threading.Thread | None = None
        self._external = False

    @property
    def running(self) -> bool:
        return self._external or (self._server is not None and self._thread is not None and self._thread.is_alive())

    @property
    def address(self) -> tuple[str, int] | None:
        if self._external:
            return self.host, self.port
        if self._server is None:
            return None
        return self._server.server_address

    def start(self) -> "LocalBackend":
        if self._server is not None:
            return self
        try:
            self._server = create_http_server(self.host, self.port)
        except OSError:
            if not self._probe_existing_backend():
                raise
            self._external = True
            return self
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="cps-local-backend",
            daemon=True,
        )
        self._thread.start()
        return self

    def _probe_existing_backend(self) -> bool:
        """Accept an already-running C.P.S. backend, but not an arbitrary port owner."""
        try:
            with urlopen(f"http://{self.host}:{self.port}/api/health", timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok" and payload.get("product") == "C.P.S."
        except Exception:
            return False

    def stop(self) -> None:
        server, thread = self._server, self._thread
        external = self._external
        self._server = None
        self._thread = None
        self._external = False
        if external:
            return
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
