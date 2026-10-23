#!/usr/bin/env python3
"""Single external HTTP entry point for Loam's internal services.

External clients only need UNIFIED_HOST:UNIFIED_PORT. Core, proxy, and admin
remain bound to loopback and are never exposed directly by the gateway host.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

UNIFIED_PORT = int(os.getenv("UNIFIED_PORT", "8783"))
UNIFIED_HOST = os.getenv("UNIFIED_HOST", "127.0.0.1")
LOAM_CORE_URL = os.getenv("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")
ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:8900").rstrip("/")
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:8781").rstrip("/")


class UnifiedHandler(BaseHTTPRequestHandler):
    """Route public paths to the corresponding loopback-only backend."""

    def do_GET(self) -> None:
        self._proxy_request()

    def do_POST(self) -> None:
        self._proxy_request()

    def do_PUT(self) -> None:
        self._proxy_request()

    def do_PATCH(self) -> None:
        self._proxy_request()

    def do_DELETE(self) -> None:
        self._proxy_request()

    def do_OPTIONS(self) -> None:
        self._proxy_request()

    def _backend_for(self, path: str) -> str:
        if path in ("/", "/index.html") or path.startswith(("/admin", "/api/proxy")):
            return ADMIN_URL
        if path.startswith("/v1/") or path == "/v1":
            return PROXY_URL
        return LOAM_CORE_URL

    def _proxy_request(self) -> None:
        path = urlparse(self.path).path
        backend_url = self._backend_for(path)
        url = f"{backend_url}{self.path}"

        try:
            body = None
            if self.command in ("POST", "PUT", "PATCH", "OPTIONS"):
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length > 0:
                    body = self.rfile.read(content_length)

            req = urllib.request.Request(url, data=body, method=self.command)
            hop_by_hop = {"host", "content-length", "connection", "transfer-encoding"}
            for key, value in self.headers.items():
                if key.lower() not in hop_by_hop:
                    req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=180) as response:
                self._send_response(response.status, response.headers, response.read())
        except urllib.error.HTTPError as exc:
            self._send_response(exc.code, exc.headers, exc.read())
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"[gateway] backend unavailable ({path}): {type(exc).__name__}: {exc}", flush=True)
            self._error(502, "backend unavailable")

    def _send_response(self, status: int, headers: Any, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() not in {"transfer-encoding", "connection", "content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> int:
    print(f"[gateway] listening on http://{UNIFIED_HOST}:{UNIFIED_PORT}")
    print(f"[gateway] core={LOAM_CORE_URL} admin={ADMIN_URL} proxy={PROXY_URL}")
    srv = ThreadingHTTPServer((UNIFIED_HOST, UNIFIED_PORT), UnifiedHandler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
