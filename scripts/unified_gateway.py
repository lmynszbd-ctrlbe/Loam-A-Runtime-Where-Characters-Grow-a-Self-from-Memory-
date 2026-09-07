#!/usr/bin/env python3
"""Unified Gateway: Single-port HTTP reverse proxy for Loam services.

Routing (pure HTTP forwarding):
  /admin, /          -> Admin service (8900)
  /v1/*              -> Forced Proxy service (8781 internal or 8900)
  /health, /context  -> Loam Core API (8765)
"""
import sys
import os
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
import urllib.request
import urllib.error

# Configuration
UNIFIED_PORT = int(os.getenv("UNIFIED_PORT", "8783"))
UNIFIED_HOST = os.getenv("UNIFIED_HOST", "127.0.0.1")

# Backend services (will be started separately)
LOAM_CORE_URL = os.getenv("LOAM_URL", "http://127.0.0.1:8765")
ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:8900")
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:8782")


class UnifiedHandler(BaseHTTPRequestHandler):
    """Pure HTTP reverse proxy routing requests to backend services."""

    def do_GET(self):
        self._proxy_request()

    def do_POST(self):
        self._proxy_request()

    def _proxy_request(self):
        path = urlparse(self.path).path
        
        # Route to backend
        if path in ("/", "/index.html") or path.startswith("/admin") or path.startswith("/api/proxy"):
            backend_url = ADMIN_URL
        elif path.startswith("/v1/"):
            backend_url = PROXY_URL
        else:
            backend_url = LOAM_CORE_URL
        
        url = f"{backend_url}{self.path}"
        
        try:
            # Read request body if present
            body = None
            if self.command in ("POST", "PUT", "PATCH"):
                cl = int(self.headers.get("Content-Length", 0))
                if cl > 0:
                    body = self.rfile.read(cl)
            
            # Build forwarding request
            req = urllib.request.Request(url, data=body, method=self.command)
            for k, v in self.headers.items():
                if k.lower() not in ("host", "content-length"):
                    req.add_header(k, v)
            
            # Forward and relay response
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
                
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
            
        except Exception as e:
            print(f"[gateway] proxy error: {backend_url} - {e}")
            self._error(502, f"backend unreachable: {e}")

    def _error(self, code: int, msg: str):
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": msg}).encode())
        except:
            pass

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> int:
    print(f"[gateway] Unified Gateway (Reverse Proxy Mode)")
    print(f"[gateway]   Listening: {UNIFIED_HOST}:{UNIFIED_PORT}")
    print(f"[gateway]   Loam Core: {LOAM_CORE_URL}")
    print(f"[gateway]   Admin UI:  {ADMIN_URL}")
    print(f"[gateway]   Proxy API: {PROXY_URL}")
    print(f"[gateway] Routing:")
    print(f"[gateway]   /         -> {ADMIN_URL}")
    print(f"[gateway]   /v1/*     -> {PROXY_URL}")
    print(f"[gateway]   /health   -> {LOAM_CORE_URL}")
    
    srv = ThreadingHTTPServer((UNIFIED_HOST, UNIFIED_PORT), UnifiedHandler)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    print(f"[gateway] ✨ Ready!")
    
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[gateway] Shutting down...")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
