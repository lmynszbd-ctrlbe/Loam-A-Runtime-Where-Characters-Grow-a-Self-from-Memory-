"""Regression tests for the one-public-port gateway contract."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.unified_gateway as gateway


class _BackendHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        payload = {"backend": self.server.backend_name, "path": self.path}  # type: ignore[attr-defined]
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def _backend(name: str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BackendHandler)
    server.backend_name = name  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_routes_to_single_public_entry_point() -> None:
    core = _backend("core")
    admin = _backend("admin")
    proxy = _backend("proxy")
    old = gateway.LOAM_CORE_URL, gateway.ADMIN_URL, gateway.PROXY_URL
    public = ThreadingHTTPServer(("127.0.0.1", 0), gateway.UnifiedHandler)
    thread = threading.Thread(target=public.serve_forever, daemon=True)
    thread.start()
    try:
        gateway.LOAM_CORE_URL = f"http://127.0.0.1:{core.server_port}"
        gateway.ADMIN_URL = f"http://127.0.0.1:{admin.server_port}"
        gateway.PROXY_URL = f"http://127.0.0.1:{proxy.server_port}"
        base = f"http://127.0.0.1:{public.server_port}"

        def get(path: str) -> dict[str, str]:
            with urllib.request.urlopen(base + path, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))

        assert get("/")["backend"] == "admin"
        assert get("/v1/models")["backend"] == "proxy"
        assert get("/health")["backend"] == "core"
    finally:
        gateway.LOAM_CORE_URL, gateway.ADMIN_URL, gateway.PROXY_URL = old
        public.shutdown()
        public.server_close()
        for server in (core, admin, proxy):
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    test_routes_to_single_public_entry_point()
    print("PASS test_routes_to_single_public_entry_point")
