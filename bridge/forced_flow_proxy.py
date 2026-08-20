#!/usr/bin/env python3
"""强制流程代理（OpenAI 兼容入口，支持多上游）。

固定流程（不依赖模型工具调用）：
  1) 取 loam context
  2) 调上游模型
  3) 把本轮 user+assistant 原文落 loam ingest

多上游能力：
- /v1/models 会聚合所有上游，并把模型 id 前缀成 provider/model
- /v1/chat/completions 可按以下方式选上游：
  a) model="provider/model"
  b) model="provider:model"
  c) Header: X-Upstream: provider
  d) 都不传则走默认上游
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROXY_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8780"))

LOAM_URL = os.environ.get("LOAM_URL", "http://127.0.0.1:8765").rstrip("/")

DEFAULT_SESSION = os.environ.get("LOAM_SESSION", "proxy-default")
LEARN_ON_CONTEXT = os.environ.get("LOAM_CONTEXT_LEARN", "0") not in ("0", "false", "False")
FORCE_DIGEST = os.environ.get("LOAM_FORCE_DIGEST", "0") in ("1", "true", "True")

STORE = Path(os.environ.get("PROXY_STATE_PATH", "~/.loam/proxy_state.json")).expanduser()
STORE.parent.mkdir(parents=True, exist_ok=True)

UPSTREAMS_CONFIG = Path(os.environ.get("UPSTREAMS_CONFIG", "~/.loam/upstreams.json")).expanduser()
UPSTREAM_DEFAULT = os.environ.get("UPSTREAM_DEFAULT", "").strip()

# 兼容单上游老参数
LEGACY_BASE_URL = os.environ.get("UPSTREAM_BASE_URL", "https://api.deepseek.com").rstrip("/")
LEGACY_API_KEY = os.environ.get("UPSTREAM_API_KEY", "").strip()
LEGACY_MODEL = os.environ.get("UPSTREAM_MODEL", "deepseek-chat").strip()

_LOCK = threading.Lock()


def _load_state() -> Dict[str, int]:
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, int]) -> None:
    STORE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_turn(session: str) -> int:
    with _LOCK:
        state = _load_state()
        n = int(state.get(session, 0)) + 1
        state[session] = n
        _save_state(state)
        return n


def _json_post(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _json_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    hs = {"Accept": "application/json"}
    if headers:
        hs.update(headers)
    req = urllib.request.Request(url, headers=hs, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: List[str] = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                out.append(str(p.get("text", "")))
        return "\n".join([x for x in out if x.strip()])
    return str(content or "")


def _last_user(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            text = _extract_text(m.get("content"))
            if text.strip():
                return text.strip()
    return ""


def _assistant_text(resp: Dict[str, Any]) -> str:
    try:
        msg = resp["choices"][0]["message"]
        return _extract_text(msg.get("content", "")).strip()
    except Exception:
        return ""


def _session_from(req_body: Dict[str, Any], headers: Dict[str, str]) -> str:
    s = headers.get("x-loam-session", "").strip()
    if s:
        return s
    user = str(req_body.get("user") or "").strip()
    if user:
        return user
    return DEFAULT_SESSION


def _build_messages_with_context(orig: List[Dict[str, Any]], ctx_text: str) -> List[Dict[str, Any]]:
    mem = {
        "role": "system",
        "content": (
            "以下是角色的长期记忆上下文（由 loam 提供）。"
            "请作为隐式背景使用，不要逐条复述。\n\n" + ctx_text
        ),
    }
    return [mem] + orig


def _load_upstreams() -> Tuple[Dict[str, Dict[str, str]], str]:
    providers: Dict[str, Dict[str, str]] = {}
    cfg_default = ""

    if UPSTREAMS_CONFIG.exists():
        try:
            cfg = json.loads(UPSTREAMS_CONFIG.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                cfg_default = str(cfg.get("default") or "").strip()
                raw_providers = cfg.get("providers") or {}
                if isinstance(raw_providers, dict):
                    for name, item in raw_providers.items():
                        if not isinstance(item, dict):
                            continue
                        base = str(item.get("base_url") or "").strip().rstrip("/")
                        key = str(item.get("api_key") or "").strip()
                        dmodel = str(item.get("default_model") or item.get("model") or "").strip()
                        if not base:
                            continue
                        providers[str(name)] = {
                            "base_url": base,
                            "api_key": key,
                            "default_model": dmodel,
                        }
        except Exception:
            providers = {}
            cfg_default = ""

    if not providers:
        providers["default"] = {
            "base_url": LEGACY_BASE_URL,
            "api_key": LEGACY_API_KEY,
            "default_model": LEGACY_MODEL,
        }

    default_name = UPSTREAM_DEFAULT or cfg_default
    if not default_name or default_name not in providers:
        default_name = next(iter(providers.keys()))

    return providers, default_name


UPSTREAMS, DEFAULT_UPSTREAM = _load_upstreams()


def _pick_upstream(req_model: str, header_upstream: str = "") -> Tuple[str, str, str]:
    """返回 (provider, upstream_model, exposed_model)。"""
    provider = ""
    model = req_model.strip()

    if header_upstream and header_upstream in UPSTREAMS:
        provider = header_upstream

    if not provider and model:
        if "/" in model:
            p, m = model.split("/", 1)
            if p in UPSTREAMS and m.strip():
                provider, model = p, m.strip()
        elif ":" in model:
            p, m = model.split(":", 1)
            if p in UPSTREAMS and m.strip():
                provider, model = p, m.strip()

    if not provider:
        provider = DEFAULT_UPSTREAM

    cfg = UPSTREAMS.get(provider)
    if not cfg:
        raise ValueError(f"未知上游 provider: {provider}")

    if not model:
        model = cfg.get("default_model", "").strip()
    if not model:
        raise ValueError(f"provider={provider} 未指定模型，且无 default_model")

    exposed = f"{provider}/{model}"
    return provider, model, exposed


def _provider_headers(provider: str) -> Dict[str, str]:
    key = (UPSTREAMS.get(provider) or {}).get("api_key", "").strip()
    if not key:
        raise ValueError(f"provider={provider} 缺少 api_key")
    return {"Authorization": f"Bearer {key}"}


def _provider_base(provider: str) -> str:
    base = (UPSTREAMS.get(provider) or {}).get("base_url", "").strip().rstrip("/")
    if not base:
        raise ValueError(f"provider={provider} 缺少 base_url")
    return base


def _models_merged() -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for name in UPSTREAMS.keys():
        try:
            data = _json_get(
                f"{_provider_base(name)}/v1/models",
                headers=_provider_headers(name),
                timeout=30,
            )
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list):
                continue
            for m in items:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("id") or "").strip()
                if not mid:
                    continue
                c = dict(m)
                c["id"] = f"{name}/{mid}"
                c["owned_by"] = f"{name}:{m.get('owned_by', '')}".strip(":")
                out.append(c)
        except Exception:
            continue
    return {"object": "list", "data": out}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "not found"}})
            return

        try:
            req = self._read_json()
            if bool(req.get("stream")):
                self._send(400, {"error": {"message": "stream=true 暂不支持"}})
                return

            messages = req.get("messages")
            if not isinstance(messages, list) or not messages:
                self._send(400, {"error": {"message": "messages 不能为空"}})
                return

            headers_low = {k.lower(): v for k, v in self.headers.items()}
            session = _session_from(req, headers_low)
            user_text = _last_user(messages)

            # 1) 强制取 context（失败不中断主链路）
            ctx_text = ""
            if user_text:
                try:
                    c = _json_post(
                        f"{LOAM_URL}/context",
                        {"query": user_text, "learn": LEARN_ON_CONTEXT},
                        timeout=30,
                    )
                    ctx_text = str(c.get("text") or "")
                except Exception as exc:
                    print(f"[proxy] context fetch failed: {type(exc).__name__}: {exc}")
                    ctx_text = ""

            merged = _build_messages_with_context(messages, ctx_text) if ctx_text else messages

            # 2) 选上游并转发
            req_model = str(req.get("model") or "")
            hdr_up = str(headers_low.get("x-upstream") or "").strip()
            provider, upstream_model, exposed_model = _pick_upstream(req_model, hdr_up)

            up_payload = dict(req)
            up_payload["model"] = upstream_model
            up_payload["messages"] = merged

            up_resp = _json_post(
                f"{_provider_base(provider)}/v1/chat/completions",
                up_payload,
                headers=_provider_headers(provider),
            )

            # 3) 强制落本轮原文到 loam
            assistant = _assistant_text(up_resp)
            if user_text and assistant:
                try:
                    turn = _next_turn(session)
                    _json_post(
                        f"{LOAM_URL}/ingest",
                        {
                            "session": session,
                            "turns": [
                                {"turn": turn, "role": "user", "content": user_text},
                                {"turn": turn, "role": "assistant", "content": assistant},
                            ],
                            "client": "forced-flow-proxy",
                            "model": exposed_model,
                            "meta": {"provider": provider, "upstream_model": upstream_model},
                        },
                        timeout=30,
                    )
                    if FORCE_DIGEST:
                        _json_post(f"{LOAM_URL}/digest", {}, timeout=60)
                except Exception as exc:
                    print(f"[proxy] ingest failed: {type(exc).__name__}: {exc}")

            self._send(200, up_resp)
        except ValueError as e:
            self._send(400, {"error": {"message": str(e)}})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"error": {"message": raw or str(e)}}
            self._send(e.code, data)
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": {"message": f"{type(e).__name__}: {e}"}})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(
                200,
                {
                    "ok": True,
                    "name": "forced-flow-proxy",
                    "time": time.time(),
                    "default_upstream": DEFAULT_UPSTREAM,
                    "upstreams": list(UPSTREAMS.keys()),
                },
            )
            return

        if self.path == "/v1/models":
            self._send(200, _models_merged())
            return

        self._send(404, {"error": {"message": "not found"}})

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b"{}"
        if not raw.strip():
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body 必须是对象")
        return data

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return


def main() -> int:
    srv = ThreadingHTTPServer((PROXY_HOST, PROXY_PORT), Handler)
    print(f"forced-flow-proxy listening on http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"loam={LOAM_URL} default_upstream={DEFAULT_UPSTREAM} upstreams={list(UPSTREAMS.keys())}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())