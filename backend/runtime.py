"""Lifecycle helper for the opt-in, desktop-managed local backend."""
from __future__ import annotations

import threading

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

    @property
    def running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    @property
    def address(self) -> tuple[str, int] | None:
        if self._server is None:
            return None
        return self._server.server_address

    def start(self) -> "LocalBackend":
        if self._server is not None:
            return self
        self._server = create_http_server(self.host, self.port)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="cps-local-backend",
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5)
